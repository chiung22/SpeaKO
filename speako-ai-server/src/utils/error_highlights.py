"""결과 화면의 **빨간 하이라이팅**과, 상세 피드백이 근거로 쓰는 **감점 요인**을 계산한다.

두 가지를 한 곳에서 만드는 이유: 둘 다 "무엇 때문에 점수를 잃었는가"라는 같은 질문의 답이다.
화면은 그것을 색으로 보여주고(어디가 틀렸나), 상세 피드백은 문장으로 설명한다(왜 깎였나).
근거가 갈리면 "빨간 줄은 12개인데 피드백은 발음 얘기만 하는" 어긋난 화면이 나온다.

[틀린 워딩의 정의 — 기획 확정]
    빨간색으로 칠하는 '틀린 워딩'은 **두 가지뿐**이다.
      1) 누락(Omission)   : 대본에 있는데 말하지 않은 단어
      2) 삽입(Insertion)  : 대본에 없는데 말한 단어
    발음 부정확(Mispronunciation)은 **틀린 워딩이 아니다.** 단어 자체는 맞게 읽었고 소리만
    흐렸을 뿐이라, 같은 빨강으로 칠하면 "대본을 틀리게 읽었다"는 잘못된 인상을 준다.
    그래서 level을 나눠서 내려준다 — 빨강은 error(누락·삽입)만, 발음은 warning이다.

[왜 서버가 span까지 주는가]
    `error_type`만으로는 같은 단어가 대본에 여러 번 나올 때 어느 것을 칠할지 정할 수 없다.
    ("발표"가 5번 나오는데 3번째만 빠뜨린 경우) 그래서 문자 오프셋을 함께 준다.
"""

from collections import Counter

# Azure Pronunciation Assessment의 오류 유형 (enable_miscue=True일 때만 누락/삽입이 나온다)
OMISSION = "Omission"
INSERTION = "Insertion"
MISPRONUNCIATION = "Mispronunciation"

# 화면 강조 단계. error만 빨간색이다(위 '틀린 워딩의 정의' 참고).
LEVEL_ERROR = "error"
LEVEL_WARNING = "warning"

# 이 점수 미만이면 error_type이 None이어도 발음이 흐렸다고 본다.
# clova/feedback/generator.py의 WEAK_WORD_THRESHOLD와 같은 값을 쓴다 — 화면에서 노랗게 칠한
# 단어와 피드백이 지적하는 단어가 달라지면 안 된다.
WEAK_ACCURACY_THRESHOLD = 70

# 한 요인당 프롬프트·화면에 실을 예시 단어 개수. 전부 넣으면 입력이 길어지고 요점이 흐려진다.
MAX_EXAMPLES = 5

def _text(value):
    """JSON에서 온 값을 문자열로 안전하게 꺼낸다.

    words_detail은 DB에 JSON으로 저장되고 스프링을 거쳐 오기도 해서, 필드 타입을 믿을 수
    없다. `(value or "").strip()`은 숫자가 들어오면 AttributeError로 터지고, 그러면 결과
    화면 전체가 500이 된다 — 단어 하나가 이상하다고 평가 결과를 통째로 못 보면 안 된다.
    """
    return value.strip() if isinstance(value, str) else ""


_TYPE_META = {
    "omission": (LEVEL_ERROR, "대본에 있지만 말하지 않았습니다."),
    "insertion": (LEVEL_ERROR, "대본에 없는 말을 했습니다."),
    "mispronunciation": (LEVEL_WARNING, "발음이 정확하지 않았습니다."),
}


# ── 문자 오프셋 붙이기 ────────────────────────────────────────────────────────

def attach_spans(words_detail, reference_text, recognized_text):
    """단어마다 원본/인식 텍스트 안에서의 위치(문자 오프셋)를 붙인다. 리스트를 제자리에서 수정한다.

    Azure는 단어를 발화 순서대로 돌려주므로, 각 텍스트를 커서로 훑으며 앞에서부터 맞춰간다.
    - Omission(빠뜨림): 원본에만 있다 → recognized_span은 None
    - Insertion(덧붙임): 실제로 말한 것뿐이다 → reference_span은 None
    찾지 못하면(문장부호·정규화 차이 등) 억지로 맞추지 않고 None으로 둔다 — 엉뚱한 곳을
    칠하느니 칠하지 않는 편이 낫다.
    """
    if not words_detail:
        return

    reference_text = reference_text or ""
    recognized_text = recognized_text or ""
    ref_cursor = 0
    rec_cursor = 0

    for entry in words_detail:
        if not isinstance(entry, dict):
            continue
        word = _text(entry.get("word"))
        error_type = _text(entry.get("error_type"))
        entry["reference_span"] = None
        entry["recognized_span"] = None
        if not word:
            continue

        if error_type != INSERTION:
            found = reference_text.find(word, ref_cursor)
            if found != -1:
                entry["reference_span"] = [found, found + len(word)]
                ref_cursor = found + len(word)

        if error_type != OMISSION:
            found = recognized_text.find(word, rec_cursor)
            if found != -1:
                entry["recognized_span"] = [found, found + len(word)]
                rec_cursor = found + len(word)


# ── 분류 ──────────────────────────────────────────────────────────────────────

def classify(word_entry):
    """단어 하나를 화면 강조 종류로 분류한다. 강조할 필요가 없으면 None.

    발음 부정확은 Azure가 Mispronunciation이라고 못 박은 경우와, 유형은 None인데 정확도가
    기준 미만인 경우를 함께 본다. 후자가 실제로 훨씬 많다(Azure는 어지간해선 Mispronunciation을
    안 붙이고 점수만 낮춘다).
    """
    if not isinstance(word_entry, dict):
        return None

    error_type = _text(word_entry.get("error_type"))
    if error_type == OMISSION:
        return "omission"
    if error_type == INSERTION:
        return "insertion"
    if error_type == MISPRONUNCIATION:
        return "mispronunciation"

    score = word_entry.get("accuracy_score")
    if isinstance(score, (int, float)) and score < WEAK_ACCURACY_THRESHOLD:
        return "mispronunciation"
    return None


# ── 하이라이팅 ────────────────────────────────────────────────────────────────

def build_highlights(words_detail, reference_text=None, recognized_text=None):
    """결과 화면이 그대로 칠할 수 있는 강조 목록을 만든다.

    프론트가 error_type을 보고 규칙을 다시 세우게 두면 화면마다 기준이 달라진다(등급 A~F를
    서버가 정하는 것과 같은 이유). 여기서 색 단계까지 정해서 내려준다.

    **두 텍스트를 함께 넘기는 것을 권장한다.** 그러면 (1) span이 없는 예전 기록도 그 자리에서
    계산하고, (2) 저장된 span이 정말 그 단어를 가리키는지 잘라서 확인한다. 안 넘기면 저장된
    span을 그대로 믿는데, 대본이 나중에 수정됐다면 밀린 자리가 빨개진다.
    (span은 2026-08-15 이후 평가부터 저장된다 — 그 전 기록엔 없다.)
    """
    empty = {
        "reference": [],
        "recognized": [],
        "counts": {"omission": 0, "insertion": 0, "mispronunciation": 0, "error": 0},
        "has_errors": False,
    }
    if not isinstance(words_detail, (list, tuple)) or not words_detail:
        return empty

    entries = [w for w in words_detail if isinstance(w, dict)]
    if not entries:
        return empty

    # 예전 기록엔 span이 없다. 원본 텍스트를 같이 받았다면 지금 계산한다. 저장된 JSON을
    # 건드리면 안 되므로 사본에 붙인다.
    if any("reference_span" not in w and "recognized_span" not in w for w in entries):
        if reference_text is not None or recognized_text is not None:
            entries = [dict(w) for w in entries]
            attach_spans(entries, reference_text, recognized_text)

    reference = []
    recognized = []
    counter = Counter()

    for entry in entries:
        kind = classify(entry)
        word = _text(entry.get("word"))
        # 이름 없는 강조는 화면에 그릴 수도, 이유를 설명할 수도 없다.
        if not kind or not word:
            continue
        counter[kind] += 1
        level, reason = _TYPE_META[kind]

        item_base = {
            "word": word,
            "type": kind,
            "level": level,
            "reason": reason,
            "accuracy_score": entry.get("accuracy_score"),
        }

        # 누락은 원본에만, 삽입은 인식 텍스트에만 존재한다. 발음 부정확은 양쪽에 다 있다.
        if kind != "insertion":
            span = _checked_span(entry.get("reference_span"), word, reference_text)
            if span:
                reference.append({**item_base, "start": span[0], "end": span[1]})
        if kind != "omission":
            span = _checked_span(entry.get("recognized_span"), word, recognized_text)
            if span:
                recognized.append({**item_base, "start": span[0], "end": span[1]})

    reference.sort(key=lambda item: item["start"])
    recognized.sort(key=lambda item: item["start"])

    error_count = counter["omission"] + counter["insertion"]
    return {
        "reference": reference,
        "recognized": recognized,
        "counts": {
            "omission": counter["omission"],
            "insertion": counter["insertion"],
            "mispronunciation": counter["mispronunciation"],
            # 빨간색으로 칠할 총 개수 = 틀린 워딩 개수
            "error": error_count,
        },
        "has_errors": error_count > 0,
    }


def _checked_span(span, word, text):
    """그릴 수 있는 span이면 (start, end)를, 아니면 None을 돌려준다.

    모양 검사만으로는 부족하다. 텍스트를 함께 받았다면 **그 자리를 잘랐을 때 정말 그 단어가
    나오는지**까지 확인한다. 저장된 span은 평가 당시의 텍스트 기준이라, 대본이 나중에 수정되면
    한 글자씩 밀린 채 남는다. 그대로 칠하면 멀쩡한 글자가 빨개지고 사용자는 서버가 틀렸다고
    본다 — 안 칠하는 편이 낫다.
    """
    if not (isinstance(span, (list, tuple)) and len(span) == 2
            and all(isinstance(n, int) and not isinstance(n, bool) for n in span)
            and 0 <= span[0] < span[1]):
        return None
    if isinstance(text, str) and text[span[0]:span[1]] != word:
        return None
    return span[0], span[1]


# ── 감점 요인 ─────────────────────────────────────────────────────────────────
#
# 상세 피드백은 "몇 점입니다"가 아니라 "무엇 때문에 깎였습니다"를 말하는 자리다.
# 아래 표는 각 요인이 Azure의 어느 점수를 끌어내리는지에 대한 대응이다.
#   - 누락      → 완성도(completeness). 대본 대비 얼마나 읽었는지를 재는 점수다.
#   - 삽입      → 정확도(accuracy). 대본에 없는 발화라 맞춰볼 기준이 없다.
#   - 발음 부정확 → 정확도(accuracy).
#   - 간투어/멈춤 → 유창성(fluency). 다만 간투어는 우리가 따로 센 값이다(Azure는 안 준다).
#
# ⚠️ Azure가 각 요인에서 **몇 점을** 깎았는지는 공개되지 않는다. 그러니 "누락으로 12점 감점"
#    같은 숫자는 절대 지어내지 않는다. 개수·비율(관찰된 사실)과 어느 점수에 영향을 주는지
#    (문서화된 정의)까지만 말한다.

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# 발화 속도 판단 구간(어절/분). Azure의 단어 단위가 한국어에선 어절이라, 음절 기준 통계를
# 그대로 쓸 수 없어 실측 녹음 기준으로 잡은 경험값이다. 애매한 구간은 아예 지적하지 않는다.
SLOW_WPM = 90
FAST_WPM = 180


def summarize_deductions(words_detail, overall_scores=None, metrics=None):
    """감점 요인을 큰 것부터 정리한다. 상세 피드백의 근거이자, 화면에 그대로 쓸 수 있는 요약.

    반환:
        factors  요인 목록(심각한 순). 각 항목의 message는 서버가 쓴 문장이라 HCX가
                 실패해도 화면에 그대로 띄울 수 있다.
        counts   요인별 개수
        primary  가장 큰 감점 요인의 key. 없으면 None.
    """
    # 호출자가 DB에서 꺼낸 JSON을 그대로 넘기므로 타입을 믿을 수 없다. 예전 기록엔 None이,
    # 손상된 기록엔 엉뚱한 값이 들어 있을 수 있는데 여기서 터지면 결과 화면 전체가 500이 된다.
    entries = [w for w in words_detail if isinstance(w, dict)] \
        if isinstance(words_detail, (list, tuple)) else []
    overall_scores = overall_scores if isinstance(overall_scores, dict) else {}
    metrics = metrics if isinstance(metrics, dict) else {}

    buckets = {"omission": [], "insertion": [], "mispronunciation": []}
    for entry in entries:
        kind = classify(entry)
        if kind and _text(entry.get("word")):
            buckets[kind].append(entry)

    # 분모: 대본에 있던 단어 수 = 삽입을 뺀 나머지. 삽입은 대본에 없던 말이라 대본 길이가 아니다.
    reference_word_count = sum(1 for w in entries if _text(w.get("error_type")) != INSERTION)
    spoken_word_count = sum(1 for w in entries if _text(w.get("error_type")) != OMISSION)

    factors = []

    omitted = buckets["omission"]
    if omitted:
        ratio = _percent(len(omitted), reference_word_count)
        factors.append(_factor(
            key="omission",
            label="대본 누락",
            words=omitted,
            ratio_percent=ratio,
            affects=["completeness"],
            severity=_severity(ratio, high=20, medium=5),
            message=(
                f"대본에 있는 단어 {len(omitted)}개를 읽지 않았습니다"
                + (f"(대본의 {ratio}%)." if ratio is not None else ".")
                + " 완성도 점수가 그만큼 내려갑니다."
            ),
        ))

    inserted = buckets["insertion"]
    if inserted:
        ratio = _percent(len(inserted), spoken_word_count)
        factors.append(_factor(
            key="insertion",
            label="대본에 없는 말",
            words=inserted,
            ratio_percent=ratio,
            affects=["accuracy"],
            severity=_severity(ratio, high=15, medium=5),
            message=(
                f"대본에 없는 말을 {len(inserted)}번 하셨습니다"
                + (f"(말한 단어의 {ratio}%)." if ratio is not None else ".")
                + " 정확도 점수에 반영됩니다."
            ),
        ))

    weak = buckets["mispronunciation"]
    if weak:
        ratio = _percent(len(weak), spoken_word_count)
        factors.append(_factor(
            key="mispronunciation",
            label="부정확한 발음",
            words=weak,
            ratio_percent=ratio,
            affects=["accuracy"],
            severity=_severity(ratio, high=25, medium=10),
            message=(
                f"{len(weak)}개 단어가 정확도 {WEAK_ACCURACY_THRESHOLD}점 미만이었습니다"
                + (f"(말한 단어의 {ratio}%)." if ratio is not None else ".")
            ),
        ))

    factors.extend(_habit_factors(metrics))

    factors.sort(key=lambda f: (_SEVERITY_ORDER.get(f["severity"], 3), -f["count"]))

    return {
        "factors": factors,
        "counts": {
            "omission": len(omitted),
            "insertion": len(inserted),
            "mispronunciation": len(weak),
            "filler": _metric_count(metrics, "filler_words"),
            "pause": _metric_count(metrics, "pauses"),
        },
        # 각 요인의 affects가 가리키는 점수의 실제 값. 화면이 "완성도 39.5 — 대본 누락 12개
        # 때문입니다"를 한 번의 응답으로 그릴 수 있게 같이 싣는다.
        "scores": {
            key: overall_scores.get(key)
            for key in ("accuracy", "fluency", "completeness", "pronunciation_score")
        },
        "primary": factors[0]["key"] if factors else None,
    }


def _habit_factors(metrics):
    """간투어·멈춤·속도. Azure 점수엔 안 드러나지만 발표 코칭에서 제일 자주 지적되는 부분이다."""
    factors = []

    fillers = metrics.get("filler_words") or {}
    filler_count = fillers.get("count") or 0
    if filler_count:
        ratio = fillers.get("ratio_percent")
        examples = [item.get("word") for item in (fillers.get("by_word") or [])[:MAX_EXAMPLES]]
        examples = [w for w in examples if w]
        # 실제로 쓴 군말을 그대로 인용한다. "'음', '어' 같은"처럼 예시를 고정해 두면 정작
        # 사용자가 쓴 말이 '그니까'였을 때 엉뚱한 지적이 된다.
        quoted = ", ".join(f"'{word}'" for word in examples[:3]) if examples else "군말"
        factors.append({
            "key": "filler",
            "label": "간투어",
            "count": filler_count,
            "ratio_percent": ratio,
            "affects": ["fluency"],
            "severity": _severity(ratio, high=5, medium=2),
            "examples": examples,
            "message": f"{quoted} 같은 군말을 {filler_count}번 사용하셨습니다. 유창성 점수를 끌어내립니다.",
        })

    pauses = metrics.get("pauses") or {}
    if pauses.get("available") and (pauses.get("count") or 0):
        count = pauses["count"]
        longest = pauses.get("longest_seconds")
        factors.append({
            "key": "pause",
            "label": "긴 멈춤",
            "count": count,
            "ratio_percent": None,
            "affects": ["fluency"],
            "severity": _severity(count, high=6, medium=2),
            "examples": [item.get("after_word") for item in (pauses.get("items") or [])[:MAX_EXAMPLES]
                         if item.get("after_word")],
            "message": (
                f"{pauses.get('threshold_seconds')}초 이상 말이 끊긴 구간이 {count}번 있었습니다"
                + (f"(가장 긴 구간 {longest}초)." if longest else ".")
            ),
        })

    rate = metrics.get("speech_rate") or {}
    if rate.get("available"):
        wpm = rate.get("words_per_minute") or 0
        if wpm and (wpm < SLOW_WPM or wpm > FAST_WPM):
            too_fast = wpm > FAST_WPM
            factors.append({
                "key": "speech_rate",
                "label": "발화 속도",
                "count": 0,  # 개수로 셀 수 있는 요인이 아니다
                "ratio_percent": None,
                "affects": ["fluency"],
                "severity": "medium",
                "examples": [],
                "message": (
                    f"분당 {wpm}어절로 {'빠른' if too_fast else '느린'} 편입니다. "
                    + ("듣는 사람이 따라오기 어려울 수 있습니다."
                       if too_fast else "청중의 집중이 흐트러질 수 있습니다.")
                ),
            })

    return factors


def _factor(key, label, words, ratio_percent, affects, severity, message):
    return {
        "key": key,
        "label": label,
        "count": len(words),
        "ratio_percent": ratio_percent,
        "affects": affects,
        "severity": severity,
        "examples": [w.get("word") for w in words[:MAX_EXAMPLES] if w.get("word")],
        "message": message,
    }


def _percent(part, whole):
    if not whole:
        return None
    return round(part / whole * 100, 1)


def _severity(value, high, medium):
    """값이 클수록 심각. value가 None이면(비율을 못 구한 경우) 가장 낮게 본다."""
    if value is None:
        return "low"
    if value >= high:
        return "high"
    if value >= medium:
        return "medium"
    return "low"


def _metric_count(metrics, key):
    section = metrics.get(key) or {}
    return section.get("count") or 0
