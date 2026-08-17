"""전체 대본 듣기(TTS)에 넘길 텍스트를 준비한다.

대본을 Clova Voice에 그대로 던질 수 없는 이유가 둘이다.

## ① 요청당 글자 수 상한
실측 대본이 7,346자(18장)라 한 번에 못 보낸다. **문장 경계로 잘라** 여러 번 부르고
MP3를 이어 붙인다. 문장 중간에서 자르면 이음새에서 말이 끊겨 들리므로 경계가 중요하다.

## ② 한국어 음운 규칙을 일부만 적용한다 (2026-08-09 실측)

    역할 → [여칼] ✅ 격음화 적용      권리 → [궐리] ✅ 유음화 적용
    각자 → [각자] ❌ 경음화 미적용    책임 → [책임] ❌ 연음 미적용

발음 교정 서비스가 틀린 발음을 들려주면 기능 자체가 무너진다. 그렇다고 대본 전체에 G2P를
돌리면 (1) 문장부호가 사라져 억양이 뭉개지고 (2) G2P 오류가 문장마다 누적된다. 그래서
**이미 검출해 둔 발음 주의 단어 자리만** 표준 발음으로 바꿔 넣는다. 나머지 글자는 원문
그대로라 문장부호도 억양도 살아 있다.
"""
import re

# Clova Voice Premium 요청 1회당 텍스트 상한. 공식 한도(2,000자)보다 낮게 잡은 이유는
# 발음 치환이 글자 수를 늘릴 수 있어서다('책임'(2) → '채김'(2)처럼 대개 같지만 항상은 아니다).
MAX_CHARS_PER_REQUEST = 1500

# 문장 끝(마침표·물음표·느낌표·말줄임표) 뒤 공백, 또는 줄바꿈에서 자른다.
# 구분자는 앞 문장에 붙여 남긴다 — 마침표가 빠지면 Clova가 문장을 이어 읽는다.
_SENTENCE_BREAK = re.compile(r"(?<=[.!?…])\s+|\n+")

# 한 문장이 통째로 상한을 넘을 때의 2차 분할 지점. 쉼표 뒤에서 자르면 그나마 덜 어색하다.
_CLAUSE_BREAK = re.compile(r"(?<=[,、·])\s*")


def apply_pronunciations(text: str, replacements) -> str:
    """대본에서 발음 주의 단어 자리를 표준 발음으로 바꾼다.

    replacements: (철자, 발음) 순서쌍들. 발음이 비었거나 철자와 같으면 무시한다.

    ⚠️ 치환을 순차적으로 돌리면(text.replace를 단어마다) **이미 바꾼 결과 위에 또 치환이
    걸린다.** '책임'을 '채김'으로 바꾼 뒤 '김'이 다른 단어의 발음에 섞이는 식이다. 그래서
    자리(span)를 먼저 전부 확정하고 **뒤에서부터 한 번에** 적용한다.

    긴 단어를 먼저 잡는 이유: '발표'와 '발표자'가 둘 다 목록에 있으면 '발표자'가 이겨야
    한다. 짧은 쪽이 먼저 자리를 차지하면 '발표자'가 '발표+자'로 쪼개져 어색하게 읽힌다.
    """
    if not text:
        return text

    pairs = []
    for word, pronunciation in replacements or []:
        if not isinstance(word, str) or not isinstance(pronunciation, str):
            continue
        word = word.strip()
        pronunciation = pronunciation.strip()
        # 철자=발음이면 바꿀 이유가 없다(장단음 단어가 대개 여기 해당한다).
        if not word or not pronunciation or word == pronunciation:
            continue
        pairs.append((word, pronunciation))

    if not pairs:
        return text

    pairs.sort(key=lambda p: len(p[0]), reverse=True)

    claimed = []          # 확정된 (시작, 끝) — 겹치는 자리는 뒤에 온 단어가 포기한다
    spans = []            # (시작, 끝, 바꿔 넣을 문자열)

    def overlaps(start, end):
        return any(start < c_end and c_start < end for c_start, c_end in claimed)

    for word, pronunciation in pairs:
        start = text.find(word)
        while start != -1:
            end = start + len(word)
            if not overlaps(start, end):
                claimed.append((start, end))
                spans.append((start, end, pronunciation))
            start = text.find(word, start + 1)

    if not spans:
        return text

    spans.sort(key=lambda s: s[0], reverse=True)
    result = text
    for start, end, pronunciation in spans:
        result = result[:start] + pronunciation + result[end:]
    return result


def split_for_tts(text: str, limit: int = None) -> list:
    """합성 요청 단위로 자른다. 각 조각은 limit 글자 이하이고, 되도록 문장 경계에서 끊긴다.

    빈 조각은 돌려주지 않는다 — Clova에 빈 문자열을 보내면 400이 난다.

    limit을 기본 인자로 박지 않는 이유: 기본값은 def가 실행되는 import 시점에 한 번만
    평가되므로, 나중에 MAX_CHARS_PER_REQUEST를 바꿔도(테스트·환경변수) 반영되지 않는다.
    """
    if limit is None:
        limit = MAX_CHARS_PER_REQUEST
    if not text or not text.strip():
        return []
    if limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다.")

    sentences = [s.strip() for s in _SENTENCE_BREAK.split(text) if s and s.strip()]

    # 상한을 넘는 문장은 절 단위로, 그래도 넘으면 글자 수로 강제로 쪼갠다.
    units = []
    for sentence in sentences:
        if len(sentence) <= limit:
            units.append(sentence)
            continue
        for clause in _CLAUSE_BREAK.split(sentence):
            clause = clause.strip()
            if not clause:
                continue
            while len(clause) > limit:
                units.append(clause[:limit])
                clause = clause[limit:]
            if clause:
                units.append(clause)

    # 상한 안에서 최대한 이어 붙인다. 조각 수가 곧 호출 횟수라 적을수록 빠르고 이음새도 적다.
    chunks = []
    current = ""
    for unit in units:
        if not current:
            current = unit
        elif len(current) + 1 + len(unit) <= limit:
            current = f"{current} {unit}"
        else:
            chunks.append(current)
            current = unit
    if current:
        chunks.append(current)

    return chunks
