"""발표 습관 지표 — 간투어(filler word)와 멈춤(pause) 계산.

Azure 발음 평가는 정확도·유창성·완성도만 준다. "음…", "어…" 같은 군더더기 말이나
말이 끊긴 구간은 점수에 직접 드러나지 않는데, 발표 코칭에서는 그게 더 자주 지적된다.
그래서 Azure가 돌려준 단어 목록(words_detail)에서 이 둘을 따로 계산한다.

입력은 `words_detail` 하나뿐이고 네트워크·DB를 건드리지 않는 순수 함수라, 테스트에서
실제 음성 없이 단어 목록만 만들어 넣으면 전부 검증된다.

## 간투어를 어떻게 가려내나

단어 사전만으로 세면 "그 방법은"의 '그'까지 간투어가 된다. 그래서 Azure가 붙여주는
`error_type`을 같이 본다(enable_miscue=True라서 대본에 없는데 말한 단어는 "Insertion"이다).

- `Omission`: 대본에 있는데 **말하지 않은** 단어다. 절대 세지 않는다.
- 확실한 간투어(음/어/으/흠/엄/머/에): 대본에 이런 단어가 홀로 있는 경우는 사실상 없으므로
  error_type과 무관하게 센다.
- 애매한 간투어(그/저/뭐/이제/막/좀…): 실제 문장에서도 쓰이는 말이라, **Insertion일 때만**
  센다. 대본에 있던 '그'를 읽은 것은 군더더기가 아니다.

## 멈춤을 어떻게 재나

Azure 상세 결과의 단어별 Offset/Duration(100ns 틱)을 초로 바꿔, 앞 단어가 끝난 시각과
다음 단어가 시작한 시각의 차이를 잰다. 그 차이가 임계값 이상이면 멈춤 한 번으로 센다.

임계값 0.7초는 문장 사이의 자연스러운 호흡(0.2~0.5초)은 넘기고, 청중이 "끊겼다"고 느끼는
구간만 잡도록 잡은 값이다. 호출부에서 바꿀 수 있다.
"""
import re
from collections import Counter

# Azure가 쓰는 시간 단위. 1틱 = 100나노초.
TICKS_PER_SECOND = 10_000_000

# 이 값 이상 벌어지면 멈춤 한 번으로 센다. 위 독스트링의 근거 참고.
DEFAULT_PAUSE_THRESHOLD_SECONDS = 0.7

# 대본에 홀로 등장하는 일이 사실상 없는 간투어. error_type과 무관하게 센다.
CERTAIN_FILLERS = frozenset({"음", "어", "으", "흠", "엄", "머", "에"})

# 실제 문장에서도 쓰이는 말들. 대본에 없는데 말한 경우(Insertion)만 간투어로 센다.
CONTEXTUAL_FILLERS = frozenset({
    "그", "저", "뭐", "이제", "인제", "그니까", "그러니까", "저기", "막", "좀",
    "약간", "이렇게", "아", "오", "우", "네", "자", "뭐랄까", "아니", "근데",
})

# 말하지 않은 단어. 간투어로도, 멈춤 계산의 시간축으로도 쓰면 안 된다.
_OMISSION = "omission"
_INSERTION = "insertion"

# 조사·문장부호를 떼기 위한 것이 아니라, 인식 결과에 붙는 구두점만 털어낸다.
_PUNCTUATION = r"[\s.,!?~…·:;\"'`´‘’“”()\[\]{}<>_\-]+"
_REPEATED_CHAR = re.compile(r"(.)\1+")


def normalize_token(word):
    """간투어 사전과 맞춰보기 위한 표준형. '어어어…' → '어', '음,' → '음'."""
    if not word:
        return ""
    stripped = re.sub(_PUNCTUATION, "", str(word))
    # 늘여 말한 간투어(어어어, 으으)를 한 글자로 접는다. 실제 단어에는 같은 글자가
    # 연달아 오는 경우가 드물어서(예: '있있다' 없음) 오탐 위험이 낮다.
    return _REPEATED_CHAR.sub(r"\1", stripped)


def _error_type(word_entry):
    return str(word_entry.get("error_type") or "").strip().lower()


def _seconds(word_entry, seconds_key, ticks_key, azure_key):
    """초 → 틱 → Azure 원본 키 순으로 시간 값을 찾는다. 없으면 None."""
    value = word_entry.get(seconds_key)
    if isinstance(value, (int, float)):
        return float(value)

    for key in (ticks_key, azure_key):
        ticks = word_entry.get(key)
        if isinstance(ticks, (int, float)) and ticks >= 0:
            return float(ticks) / TICKS_PER_SECOND
    return None


def _prepare(words_detail):
    """words_detail을 계산하기 쉬운 형태로 펼친다. 원본은 건드리지 않는다.

    평가 모듈이 리스트가 아닌 것을 주더라도(포맷 변경·오류 응답) 여기서 막는다.
    지표 계산이 터져서 평가 점수까지 502가 되면 안 된다.
    """
    if not isinstance(words_detail, (list, tuple)):
        return []

    prepared = []
    for index, entry in enumerate(words_detail):
        if not isinstance(entry, dict):
            continue
        surface = entry.get("word")
        start = _seconds(entry, "offset_seconds", "offset_ticks", "Offset")
        length = _seconds(entry, "duration_seconds", "duration_ticks", "Duration")
        prepared.append({
            "index": index,
            "word": surface,
            "normalized": normalize_token(surface),
            "error_type": _error_type(entry),
            "start": start,
            "end": (start + length) if (start is not None and length is not None) else None,
        })
    return prepared


def _spoken(prepared):
    """실제로 말한 단어만. Omission은 대본에만 있고 소리가 없다."""
    return [w for w in prepared if w["error_type"] != _OMISSION]


def detect_filler_words(words_detail):
    """간투어를 세어 돌려준다.

    반환:
        count            총 개수
        by_word          단어별 횟수 (많은 순)
        occurrences      등장 위치 하나하나 (프론트가 인식 텍스트에 표시할 때 쓴다)
        spoken_word_count 말한 단어 총 개수 (비율 계산의 분모)
        ratio_percent    말한 단어 중 간투어 비율
    """
    prepared = _prepare(words_detail)
    spoken = _spoken(prepared)

    occurrences = []
    for word in spoken:
        token = word["normalized"]
        if not token:
            continue
        if token in CERTAIN_FILLERS:
            pass  # error_type과 무관하게 센다
        elif token in CONTEXTUAL_FILLERS and word["error_type"] == _INSERTION:
            pass  # 대본에 없는데 말했을 때만 센다
        else:
            continue

        occurrences.append({
            "word": word["word"],
            "normalized": token,
            "word_index": word["index"],
            "offset_seconds": round(word["start"], 3) if word["start"] is not None else None,
        })

    counter = Counter(item["normalized"] for item in occurrences)
    spoken_count = len(spoken)
    return {
        "count": len(occurrences),
        "by_word": [
            {"word": token, "count": count}
            for token, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "occurrences": occurrences,
        "spoken_word_count": spoken_count,
        "ratio_percent": round(len(occurrences) / spoken_count * 100, 1) if spoken_count else 0.0,
    }


def detect_pauses(words_detail, threshold_seconds=DEFAULT_PAUSE_THRESHOLD_SECONDS):
    """단어 사이가 threshold_seconds 이상 벌어진 구간을 멈춤으로 센다.

    시간 정보가 없으면(예: Azure 상세 JSON을 못 받은 경우) available=False로 알린다.
    0을 돌려주면 "멈춤이 없었다"와 "잴 수 없었다"가 구분되지 않는다.
    """
    prepared = _prepare(words_detail)
    timed = [w for w in _spoken(prepared) if w["start"] is not None and w["end"] is not None]

    if len(timed) < 2:
        return {
            "available": False,
            "reason": "단어별 시간 정보가 없어 멈춤을 계산할 수 없습니다.",
            "threshold_seconds": threshold_seconds,
            "count": 0,
            "total_seconds": 0.0,
            "longest_seconds": 0.0,
            "items": [],
        }

    timed.sort(key=lambda w: w["start"])

    items = []
    for previous, current in zip(timed, timed[1:]):
        gap = current["start"] - previous["end"]
        # 겹쳐서 인식된 경우(음수)는 멈춤이 아니다.
        if gap < threshold_seconds:
            continue
        items.append({
            "after_word": previous["word"],
            "after_word_index": previous["index"],
            "before_word": current["word"],
            "start_seconds": round(previous["end"], 3),
            "duration_seconds": round(gap, 3),
        })

    durations = [item["duration_seconds"] for item in items]
    return {
        "available": True,
        "threshold_seconds": threshold_seconds,
        "count": len(items),
        "total_seconds": round(sum(durations), 3),
        "longest_seconds": round(max(durations), 3) if durations else 0.0,
        "items": items,
    }


def measure_speech_rate(words_detail):
    """말한 구간 길이와 분당 어절 수. 발표 속도가 빠른지 느린지 판단하는 근거."""
    prepared = _prepare(words_detail)
    timed = [w for w in _spoken(prepared) if w["start"] is not None and w["end"] is not None]

    if len(timed) < 2:
        return {"available": False, "speaking_seconds": 0.0, "words_per_minute": 0.0}

    start = min(w["start"] for w in timed)
    end = max(w["end"] for w in timed)
    span = end - start
    if span <= 0:
        return {"available": False, "speaking_seconds": 0.0, "words_per_minute": 0.0}

    return {
        "available": True,
        "speaking_seconds": round(span, 3),
        "words_per_minute": round(len(timed) / span * 60, 1),
    }


def analyze(words_detail, pause_threshold_seconds=DEFAULT_PAUSE_THRESHOLD_SECONDS):
    """평가 응답에 실을 발표 습관 지표 한 덩어리."""
    return {
        "filler_words": detect_filler_words(words_detail),
        "pauses": detect_pauses(words_detail, pause_threshold_seconds),
        "speech_rate": measure_speech_rate(words_detail),
    }
