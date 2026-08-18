import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

from utils.usage_tracker import log_hcx_call
from clova.hcx_request import post_with_retry
from clova.toon_parser import clean_script_text, parse_toon_slides
from clova.styles import (
    FIRST_SLIDE_INSTRUCTION,
    LAST_SLIDE_INSTRUCTION,
    MIDDLE_SLIDE_INSTRUCTION,
    audience_instruction as _audience_instruction,
    style_instruction,
)

load_dotenv()

REQUEST_TIMEOUT_SECONDS = 30

# 슬라이드별 생성/고도화는 서로 독립적이라 동시에 부를 수 있다. 순차로 30장을 부르면
# 장당 2~4초 × 30 = 1~2분이 걸리지만, 동시에 부르면 그만큼 줄어든다.
# 다만 HCX 레이트리밋이 있으므로 동시 개수에 상한을 둔다(환경변수로 조정 가능).
MAX_CONCURRENT_REQUESTS = max(1, int(os.getenv("HCX_MAX_CONCURRENCY", "4")))

# 고도화(리뷰)는 "Slide N:" 라벨을 그대로 유지하는 작업이라 여러 장을 함께 넘겨도 정렬이 안 밀린다.
# 다만 입력이 길면 슬라이드를 통째로 빠뜨리므로 이 단위로 나눈다.
REFINE_SLIDES_PER_REQUEST = 6


def _is_placeholder_key(api_key):
    """HCX_API_KEY가 없거나 .env.example의 플레이스홀더 그대로면 True (안전 모드로 전환)."""
    return not api_key or "여기에_" in api_key


def _split_slide_blocks(ppt_text):
    """"Slide N: 내용" 평문을 [(슬라이드번호, 해당 블록 원문)] 목록으로 나눈다."""
    matches = list(re.finditer(r"(?m)^\s*Slide\s+(\d+)\s*:", ppt_text))
    if not matches:
        return []

    blocks = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(ppt_text)
        blocks.append((match.group(1), ppt_text[match.start():end].strip()))
    return blocks


def _clean_single_slide_script(text):
    """한 장짜리 응답에서 대본 문장만 남긴다. 정리 규칙은 부분 재생성과 공유한다(clova/toon_parser.py)."""
    return clean_script_text(text)


# 원문이 이 글자 수 미만이면 "제목만 있고 내용은 없는 슬라이드"로 본다.
# 디자인 이미지 한 장뿐인 슬라이드, 섹션 표지, 도표만 있는 슬라이드가 여기 해당한다.
THIN_SOURCE_CHARS = int(os.getenv("THIN_SLIDE_SOURCE_CHARS", "30"))

# "Slide 20:" 라벨과 "[발표자 가이드]" 같은 머리표는 근거 분량에 넣지 않는다.
_SOURCE_LABELS = re.compile(r"^\s*Slide\s+\d+\s*:|\[[^\]]{1,30}\]")


def _is_thin_source(block):
    """
    이 슬라이드에 대본의 근거가 될 원문이 사실상 없는가.

    왜 필요한가: 원문이 "서비스 기술 스택" 한 줄뿐이면 모델은 빈칸을 그럴듯한 추측으로 채운다.
    실측(2026-08-06): 텍스트가 0인 기술 스택 슬라이드에 React·Redux·Node.js·Express·MongoDB·
    WebSocket을 통째로 지어냈다. 시스템 프롬프트에 "지어내지 마세요"를 넣어도 재발했다 —
    모델 입장에서는 발표 대본을 써야 하는데 쓸 거리가 없으니 만들어내는 것이다.
    그래서 **그런 슬라이드임을 감지해서 다른 지시를 준다**(무엇을 쓸지 대신 알려준다).
    """
    body = _SOURCE_LABELS.sub(" ", block or "")
    return len(re.sub(r"\s+", "", body)) < THIN_SOURCE_CHARS


# 근거가 없는 슬라이드에 주는 지시. "지어내지 마세요"만으로는 부족하고,
# 대신 무엇을 쓰면 되는지를 알려줘야 모델이 빈칸을 추측으로 채우지 않는다.
#
# 화면을 가리키는 예시 표현을 슬라이드 번호에 따라 돌리는 이유: 장마다 독립 호출이라
# 같은 지시를 주면 같은 문장이 나온다. 실측(2026-08-18, 이미지형 14장): 빈 장 4개 중
# 3개가 "보시는 바와 같이 화면에 정리된 내용을 통해…"로 사실상 같은 대본이었다.
_THIN_POINTING_EXAMPLES = (
    "'보시는 바와 같이', '화면에 정리했습니다'",
    "'지금 보시는 화면처럼', '이 슬라이드에 담긴 것처럼'",
    "'화면의 내용을 함께 봐주시기 바랍니다', '슬라이드에 정리된 대로'",
)


def _is_empty_source(block):
    """라벨을 떼면 글자가 하나도 없는가 — thin(제목 한 줄)보다 더 극단적인 상태."""
    body = _SOURCE_LABELS.sub(" ", block or "")
    return not re.sub(r"\s+", "", body)


# 장 역할 분석 결과("번호: 역할 한 줄")를 읽는 패턴. 분석 프롬프트는 아래
# FullScriptGenerator._analyze_slide_roles 참고.
_ROLE_LINE = re.compile(r"^\s*(\d+)\s*[:：]\s*(.+?)\s*$", re.MULTILINE)


# 비전이 글자는 못 읽고 장면 설명만 얻은 장의 표식 (ppt_extractor 3차 라운드가 붙인다).
_SCENE_LABEL = "[화면 묘사]"


def _thin_source_instruction(slide_number, block=None, role_hint=None):
    pointing = _THIN_POINTING_EXAMPLES[(int(slide_number) - 1) % len(_THIN_POINTING_EXAMPLES)]

    # 덱 전체 분석(_analyze_slide_roles)이 이 장의 역할을 판단해줬으면 그걸 최우선으로 쓴다.
    # 장별 독립 생성이라 모델은 덱 맥락을 모른다 — "진순"이 발표자 이름인 건 다른 장들과
    # 함께 봐야 알 수 있다(실측 2026-08-19: 맥락 없이 "핵심 기능인 진순"으로 단정).
    if role_hint:
        # 분석조차 "불명"이라고 답한 장: 해석하면 반드시 지어내기가 된다(실측: '진순'을
        # "음식 관련 용어"로 해석). 모르면 아무 의미도 부여하지 말고 화면만 가리킨다.
        if "불명" in role_hint:
            return (
                "이 슬라이드의 원문은 몇 단어뿐이고, 그 의미를 덱 맥락으로도 확정할 수 "
                "없습니다. **원문 단어의 뜻을 해석하거나 추측해서 설명하지 마세요.** "
                f"{pointing}처럼 화면을 봐 달라는 안내 한두 문장만 쓰세요. "
                "청중에게 던지는 질문으로 시작하지 마세요."
            )
        return (
            f"이 슬라이드는 원문이 빈약하지만, 덱 전체를 분석한 결과 이 장의 역할은 "
            f"'{role_hint}'입니다. 이 역할에 맞는 대본을 한두 문장으로만 쓰세요. "
            "역할 설명 문구를 그대로 낭독하지 말고 자연스러운 발표 말로 바꾸세요. "
            "원문과 역할에 없는 기능·숫자·이름을 지어내지 마세요. "
            f"필요하면 {pointing}처럼 화면을 가리키는 표현을 써도 됩니다. "
            "청중에게 던지는 질문으로 시작하지 마세요."
        )

    # 글자 대신 장면 설명만 있는 장: 묘사를 "장의 역할" 힌트로만 쓰게 한다.
    # 묘사를 내용처럼 단정하면 과거 환각 사고가 재발한다(비전이 화면을 설명한 문장이
    # 대본 근거로 오염됐던 건 — image_text_extractor.py 상단 주석 참고).
    if block is not None and _SCENE_LABEL in block:
        return (
            f"이 슬라이드에는 읽을 수 있는 글자가 없고, 화면이 어떤 장면인지에 대한 "
            f"설명({_SCENE_LABEL} 부분)만 있습니다. 이 설명은 슬라이드에 적힌 내용이 "
            "아니라 **화면의 생김새**입니다 — 그대로 읽거나 사실처럼 인용하지 마세요. "
            "대신 장면으로 장의 역할을 짐작해 한두 문장으로 자연스럽게 말하세요. "
            "예: 인물이 인사하는 장면이면 발표자를 소개하는 말, 고민하는 장면이면 "
            "문제 상황을 여는 말. 묘사에 없는 구체 정보(이름·숫자·기능)를 지어내지 말고, "
            "두 문장을 넘기지 마세요. 청중에게 던지는 질문으로 시작하지도 마세요."
        )

    # 완전히 빈 장(원문 0자)은 안내할 "주제 한 줄"조차 없다. 여기서 2~3문장을 요구하면
    # 모델이 발표 주제로 슬라이드 내용을 **추측해서 단정한다** — 실측(2026-08-18):
    # 발표자 소개 사진뿐인 장에 "핵심 기능과 혜택들을 간략히 설명드리고자 합니다"라고 썼고,
    # PPT 주인이 "그 장은 그냥 자기소개 장인데 대본이 엄청 많다"고 지적했다.
    if block is not None and _is_empty_source(block):
        return (
            "이 슬라이드에서는 읽을 수 있는 텍스트가 없습니다. 무엇이 담긴 슬라이드인지 "
            "알 수 없으므로, 슬라이드의 내용이나 주제를 **절대 단정하거나 추측하지 마세요.** "
            f"{pointing}처럼 화면을 봐 달라는 안내 **한 문장**만 쓰세요. 두 문장을 넘기지 마세요. "
            "청중에게 던지는 질문으로 시작하지도 마세요. "
            "⚠️ '이 슬라이드에는 내용이 없습니다', '내용을 확인할 수 없습니다' 같은 말을 "
            "청중에게 하면 안 됩니다 — 그건 지금 당신에게 주는 사정 설명이지 발표 대사가 아닙니다."
        )

    return (
        "이 슬라이드에는 위 [PPT 텍스트]에 적힌 몇 단어 외에 참고할 내용이 없습니다. "
        "**그 몇 단어가 이 장의 전부입니다 — 대본은 반드시 그 단어들을 중심으로 쓰세요.** "
        "예를 들어 원문이 사람·캐릭터 이름뿐이면 그 인물을 소개하는 장이지, 발표 주제를 "
        "요약하는 장이 아닙니다. 원문에 없는 서비스 설명·기능·주제 요약을 덧붙이지 마세요. "
        "구체적인 항목 — 기술·제품·회사 이름, 숫자, 목록 항목 — 을 지어내는 것도 금지입니다. "
        f"2~3문장이면 충분하고, 세부는 {pointing}처럼 슬라이드를 가리키는 표현으로 넘기세요. "
        "청중에게 던지는 질문('여러분은 혹시 ~하신 적 있으신가요?')으로 장을 시작하지 마세요 — "
        "여러 장이 똑같은 질문으로 시작하게 됩니다. "
        "짧아도 괜찮습니다. 분량을 채우려고 없는 내용을 만들어내면 안 됩니다."
    )
_NORMAL_SOURCE_INSTRUCTION = (
    "위 [PPT 텍스트]에 있는 내용만 근거로 쓰세요. 거기 없는 구체적 사실은 지어내지 마세요."
)


# 발표 중간 슬라이드에서 나오면 안 되는 마무리 인사·마무리 문장. 프롬프트로 금지해도 모델이 종종 붙인다
# (실측 1: 제로 PPT 재생성 8장 중 2장이 중간인데 "감사합니다"로 끝남).
# (실측 2: 2026-08-18 체육 지도안 18장 — 1·2장이 "이상으로 …를 소개해 드렸습니다"로,
#  1장은 "여러분의 많은 관심과 조언 부탁드립니다"까지 붙여 장마다 발표가 끝나는 것처럼 들렸다.
#  단어형 인사만 지우던 기존 패턴이 문장형 마무리를 통과시킨 것). 지시에만 기대지 않고 코드로 지운다.
_CLOSING_UNIT = (
    r"이상입니다|감사합니다|경청해\s*주셔서\s*감사합니다|들어주셔서\s*감사합니다|"
    r"감사드립니다|고맙습니다"
    # "이상으로 …를 소개해 드렸습니다" — 문장 전체가 마무리다
    r"|이상으로[^.!?]*"
    # "지금까지 …를 말씀드렸습니다/살펴보았습니다" — 위와 같은 발표 전체 요약형 마무리
    r"|지금까지[^.!?]*(?:드렸|보았|살펴보)[^.!?]*"
    # "(여러분의) 많은 관심과 조언 부탁드립니다" — 관심·조언·성원·격려가 있을 때만 지워,
    # "자료 확인을 부탁드립니다" 같은 본문 요청은 살린다
    r"|[^.!?]*(?:관심|조언|성원|격려)[^.!?]*부탁드립니다"
    # "기대해 주시기 바랍니다" / "다음 내용도 기대해 주세요" — 권유형 맺음 (PPT 주인 피드백
    # 2026-08-19: 장마다 이런 맺음이 나와 슬라이드 간 연결성이 끊긴다)
    r"|[^.!?]*기대해\s*주[^.!?]*"
    # "발표 실력을 한 단계 업그레이드해 보시길 바랍니다" — '~해 보시길' 권유 맺음.
    # ⚠️ '봐주시기 바랍니다'(빈 장의 화면 안내 문장)와 헷갈리면 안 된다 — '보시길'만 잡는다
    r"|[^.!?]*보시길\s*바랍니다"
)
# 각 마무리 단위는 문자열 시작 또는 문장 끝(.!?) 뒤에서만 시작한다.
# 앵커가 없으면 "참여율을 80% 이상으로 끌어올리는 것이 목표입니다"의 문장 중간 '이상으로'까지
# 마무리로 오인해 본문을 잘라먹는다.
_CLOSING_GREETING_PATTERN = re.compile(
    r"(?:(?:^|(?<=[.!?]))\s*(?:" + _CLOSING_UNIT + r")[.!?]?\s*)+$"
)


def _strip_closing_greeting(script):
    """중간 슬라이드 끝에 붙은 마무리 인사를 제거한다. 인사만 남으면(=지우면 빈 대본) 원문을 유지한다."""
    if not script:
        return script
    stripped = _CLOSING_GREETING_PATTERN.sub("", script).strip()
    return stripped if stripped else script


# 중간 슬라이드가 마무리 인사로 **시작**하는 경우 (실측 2026-08-18, 이미지형 14장 중 10장:
# "여러분, 지금까지 저희 발표를 들어주셔서 감사합니다. 이제 마지막으로…").
# 끝에 붙는 인사만 지우던 안전망이 시작 인사를 통과시켰다. 뒤 문장은 본문이므로 인사만 벗긴다.
_LEADING_CLOSING_PATTERN = re.compile(
    r"^\s*(?:여러분[,.!]?\s*)?지금까지\s*(?:저희\s*|제\s*)?(?:발표를?\s*)?"
    r"(?:들어|경청해|함께해)\s*주셔서\s*감사합니다[.!]?\s*"
)


def _strip_leading_closing(script):
    """중간 슬라이드 첫머리의 마무리 인사를 제거한다. 인사뿐이면 원문을 유지한다."""
    if not script:
        return script
    stripped = _LEADING_CLOSING_PATTERN.sub("", script, count=1).strip()
    return stripped if stripped else script


# 중간 슬라이드 첫머리의 여는 인사("안녕하세요, 여러분. 오늘은 …"). 프롬프트로 금지해도
# 재발한다(실측 2026-08-19: 12장이 "안녕하세요, 여러분."으로 시작). 인사만 벗기고 본문은 살린다.
_LEADING_GREETING_PATTERN = re.compile(
    r"^\s*(?:안녕하세요|안녕하십니까|반갑습니다)[,.!]?\s*(?:여러분[,.!]?\s*)?"
)


def _strip_leading_greeting(script):
    """중간 슬라이드 첫머리의 여는 인사를 제거한다. 인사뿐이면 원문을 유지한다."""
    if not script:
        return script
    stripped = _LEADING_GREETING_PATTERN.sub("", script, count=1).strip()
    return stripped if stripped else script


# 빈 장(원문 0자) 대본에서 지시문의 사정 설명이 대사로 새는 경우.
# "한 문장만, 단정 금지"까지는 프롬프트가 지키게 만들었지만, "내용을 확인할 수 없습니다.
# 양해 부탁드립니다"처럼 **상황 자체를 청중에게 말해버리는 것**은 금지 지시(274eda7)로도
# 재발했다(실측 2026-08-19). 여기는 지시가 아니라 코드로 끝낸다.
_EMPTY_LEAK_PATTERN = re.compile(r"내용[을이]?\s*(?:확인할 수 없|없습니다|찾을 수 없)|양해")

# _thin_source_instruction의 화면 안내 예시와 같은 결의 대체 문장 (장 번호로 순환)
_EMPTY_FALLBACK_SCRIPTS = (
    "화면의 내용을 함께 봐주시기 바랍니다.",
    "지금 보시는 화면을 함께 살펴보겠습니다.",
    "이 슬라이드는 화면으로 직접 확인해 보시죠.",
)


def _replace_leaked_empty_script(script, slide_number):
    """빈 장 대본이 '내용이 없다'는 사정을 말하면 화면 안내 한 문장으로 통째로 교체한다."""
    if script and _EMPTY_LEAK_PATTERN.search(script):
        return _EMPTY_FALLBACK_SCRIPTS[(int(slide_number) - 1) % len(_EMPTY_FALLBACK_SCRIPTS)]
    return script


# 발표자 이름이 자료에 없을 때 모델이 채워 넣는 자리표시자.
# clova/styles.py의 FIRST_SLIDE_INSTRUCTION이 이미 "'OOO'나 '홍길동'을 쓰지 말라"고 못박고 있는데도
# 모델이 그대로 어긴다(실측: 4개 발표 중 2개의 첫 장이 각각 "홍길동입니다", "발표자 OOO입니다").
# 마무리 인사와 같은 이유로, 지시에만 기대지 않고 코드로 지운다.
_PLACEHOLDER_NAME = r"(?:홍길동|길동이?|OOO+|ooo+|XXX+|xxx+|○+|◯+|△+|□+|\*{2,}|아무개|모모)"

# "…을 맡은 홍길동입니다" → "…을 시작하겠습니다" 처럼, 이름만 빼고 문장은 살린다.
# '맡았습니다'가 아니라 '시작하겠습니다'로 바꾸는 이유: PPT 주인 피드백(2026-08-18) —
# "~의 발표를 맡았습니다"보다 "~ 발표 시작하겠습니다"가 실제 발표에서 자연스럽다.
_PLACEHOLDER_INTRO_PATTERNS = (
    (re.compile(rf"(발표를?|진행을?)\s*(맡은|맡게 된|담당한)\s*{_PLACEHOLDER_NAME}\s*(?:입니다|이라고 합니다)"), r"\1 시작하겠습니다"),
    (re.compile(rf"발표자\s*{_PLACEHOLDER_NAME}\s*(?:입니다|이라고 합니다)"), "발표를 시작하겠습니다"),
    # 자기소개 문장이 통째로 자리표시자뿐이면 문장을 지운다("저는 OOO입니다.").
    (re.compile(rf"\s*저(?:는|희는)?\s*{_PLACEHOLDER_NAME}\s*(?:입니다|이라고 합니다)[.!]?"), ""),
    # 남은 형태("팀 OOO입니다")는 이름만 들어낸다.
    (re.compile(rf"\s*{_PLACEHOLDER_NAME}(?=\s*(?:입니다|이라고 합니다))"), ""),
)


def _strip_placeholder_name(script):
    """자료에 없는 발표자 이름을 모델이 자리표시자로 채운 경우, 이름을 빼고 문장을 살린다."""
    if not script:
        return script
    cleaned = script
    for pattern, replacement in _PLACEHOLDER_INTRO_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    # 문장을 통째로 지웠을 때 남는 이중 공백을 정리한다.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return cleaned if cleaned else script


def _position_label(index, total):
    """
    발표 중 이 슬라이드의 위치를 "지시문"으로 돌려준다.

    매 슬라이드를 독립 요청으로 만들면 모델은 자기가 발표 중간에 있다는 걸 모른다.
    위치를 단순 라벨("3번째 슬라이드")로만 주면 무시하고 장마다 "안녕하세요"로 시작한다
    (실측: 19장 중 16장). 그래서 하지 말아야 할 것을 문장으로 못박는다(clova/styles.py).

    ⚠️ 이웃 슬라이드의 "내용"을 맥락으로 함께 넘겨봤지만 역효과였다 — 모델이 그 내용까지
    대본으로 써버려서(3번 대본이 4번 내용을 설명) 정렬이 다시 깨졌다. 위치만 알려준다.
    """
    if total <= 1:
        return ""
    if index == 0:
        return f"전체 {total}장 중 첫 번째 슬라이드입니다. {FIRST_SLIDE_INSTRUCTION}"
    if index == total - 1:
        return f"전체 {total}장 중 마지막 슬라이드입니다. {LAST_SLIDE_INSTRUCTION}"
    return f"전체 {total}장 중 {index + 1}번째 슬라이드입니다. {MIDDLE_SLIDE_INSTRUCTION}"


class FullScriptGenerator:
    def __init__(self):
        self.api_key = os.getenv("HCX_API_KEY")
        self.model_name = os.getenv("HCX_MODEL_NAME", "HCX-005")
        self.endpoint = f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{self.model_name}"
        # 키가 없으면 다른 4개 클라이언트(ETRI/Azure/Clova Voice/stdict)와 동일하게
        # 네트워크 호출 없이 곧장 안전 모드로 빠진다. (플레이스홀더 키로 실제 요청을 보내면
        # 무의미한 30초 타임아웃 대기 + 불필요한 외부 호출이 발생한다)
        self.use_fallback = _is_placeholder_key(self.api_key)
        if self.use_fallback:
            print("⚠️ [경고] HCX_API_KEY가 설정되지 않았습니다. 대본 생성은 안전 모드(None 반환)로 동작합니다.")

    def generate_full_script(self, ppt_text, presentation_time, style, extra_requirement="", audience="", topic=""):
        """
        슬라이드를 **한 장씩** 요청해서 결과를 합친다.
        audience: 발표 대상/청중(예: "교수님", "면접관"). 있으면 그 청중에 맞춘 어조·설명 수준으로 작성.
        topic: 발표 주제(피그마의 유일한 필수 입력). 슬라이드 원문만으로는 놓치기 쉬운 발표의 큰 줄기를
               모델에 알려줘, 각 장이 주제에서 벗어나지 않게 한다.

        여러 장을 한 번에 넣으면 모델이 어떤 장은 건너뛰고 어떤 장은 두 줄로 쪼개는데,
        그러면 슬라이드와 대본의 정렬이 통째로 밀린다. (실측: 목차 장을 건너뛰는 바람에
        2번 대본에 3번 내용이 들어갔고, 전체의 26%가 이웃 슬라이드 내용을 말하고 있었다)
        한 장만 보내면 무슨 응답이 오든 그 장의 대본이므로 정렬이 구조적으로 보장된다.
        대신 대본이 앞뒤로 자연스럽게 이어지도록 이웃 슬라이드를 맥락으로 함께 넘긴다.
        """
        if self.use_fallback:
            return None

        blocks = _split_slide_blocks(ppt_text)
        if len(blocks) <= 1:
            # 원본이 없거나 한 덩어리(주제/목차 브리프)일 때는 모델이 여러 슬라이드로 "확장"하는 것이
            # 정상 동작이다. PPT 없이 주제만 받은 프로젝트는 이 확장 결과가 곧 슬라이드가 된다.
            # 그러니 여기서는 번호를 손대지 않고 모델이 매긴 그대로 돌려준다.
            return self._request_raw(ppt_text, presentation_time, style, extra_requirement, None, audience, topic)

        per_slide_time = max(1, round(presentation_time / len(blocks)))

        # 근거 없이 만든 슬라이드를 사용자에게 알려주기 위해 미리 표시해둔다(아래 반환값 주석 참고).
        thin = [number for number, block in blocks if _is_thin_source(block)]

        # ── 분석 패스: 빈약한 장들의 "역할"을 덱 전체 맥락으로 한 번에 판단한다.
        # 장별 독립 생성은 맥락이 없어서 "진순"(발표자 이름)을 기능으로 단정했다(2026-08-19).
        # 규칙 하드코딩 대신 모델이 덱 전체를 보고 판단하게 한다 — 호출은 덱당 1회다.
        roles = {}
        if thin:
            try:
                roles = self._analyze_slide_roles(ppt_text, thin, topic)
            except Exception as err:
                print(f"⚠️ 장 역할 분석 실패(일반 지시로 진행): {err}")

        # 슬라이드별 호출은 서로 독립적이라(각 장은 자기 내용 + 위치만 씀) 동시에 부른다.
        # 순서는 결과를 슬라이드 번호로 정렬해 맞추므로 완료 순서가 뒤섞여도 문제없다.
        def build_one(item):
            index, (number, block) = item
            slides = self._request_one_slide(
                number, block, _position_label(index, len(blocks)), per_slide_time, style, extra_requirement, audience, topic,
                is_last=(index == len(blocks) - 1),
                is_first=(index == 0),
                role_hint=roles.get(str(int(number))),
            )
            return number, slides

        all_slides = []
        missing = []
        workers = min(MAX_CONCURRENT_REQUESTS, len(blocks))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for number, slides in pool.map(build_one, enumerate(blocks)):
                if slides:
                    all_slides.extend(slides)
                else:
                    missing.append(number)

        if missing:
            print(f"  ⚠️ 슬라이드 {missing} 생성 실패(모델이 포맷을 안 지킴).")
        if not all_slides:
            return None

        all_slides.sort(key=lambda s: int(s["slide_number"]))
        # 끝내 못 만든 슬라이드는 콘솔에만 찍고 넘어가면 프론트가 "왜 이 장만 비어 있지?"를 알 수 없다.
        # 결과에 실어 보내서 화면에서 "이 슬라이드는 다시 생성해 주세요"를 안내할 수 있게 한다.
        #
        # thin_source_slide_numbers: 원문이 제목 한 줄뿐이라 **내용을 근거로 쓸 수 없었던** 슬라이드.
        # 여기 대본은 슬라이드를 가리키는 일반적인 안내문이므로 발표자가 직접 채워야 한다.
        # 조용히 그럴듯한 대본을 주면 발표자가 그대로 읽다가 사실이 아닌 말을 하게 된다.
        return {
            "slides": all_slides,
            "missing_slide_numbers": missing,
            "thin_source_slide_numbers": thin,
        }

    def _analyze_slide_roles(self, ppt_text, thin_numbers, topic=""):
        """빈약한 장들의 역할을 덱 전체 맥락으로 판단한다. {장번호(str): 역할 한 줄}.

        왜 덱 전체를 주나: "진순" 한 단어가 발표자 이름인지 기능명인지는 그 장만 봐서는
        알 수 없다 — 표지·마지막 장·다른 장들의 내용과 함께 봐야 한다. 호출은 덱당 1회.
        실패하면 빈 dict — 생성은 일반 thin 지시로 진행되므로 분석이 죽어도 대본은 나온다.
        """
        numbers = ", ".join(str(int(n)) for n in thin_numbers)
        user_prompt = (
            "[장 역할 분석]\n"
            f"발표 주제: {topic or '(미상)'}\n\n"
            "아래는 발표 자료의 장별 원문입니다.\n\n"
            f"{ppt_text}\n\n"
            f"원문이 빈약한 장: {numbers}\n\n"
            "위 장들 각각이 발표에서 어떤 역할의 장인지, 덱 전체 맥락으로 판단해주세요. "
            "판단 순서: ① 원문이 사람 이름으로 보이는가 — 그렇다면 누구인지"
            "(발표자·팀원·고객 페르소나·캐릭터)를 밝히세요. ② 아니라면 앞뒤 장과의 관계로 "
            "역할(제목·전환·강조·마무리 등)을 정하세요. "
            "⚠️ 원문 단어에 새 의미를 지어 붙이지 마세요(예: 이름을 약어·구호로 재해석 금지). "
            "확실하지 않으면 '불명'이라고 쓰세요 — 추측으로 기능·제품이라 단정하지 마세요.\n"
            "출력은 설명 없이 아래 형식의 줄만:\n"
            "장번호: 역할 한 줄\n"
            "예) 2: 발표자 자기소개 — '진순'은 발표자 이름"
        )
        text = self._call_hcx(
            "너는 발표 자료 분석가다. 장별 원문을 보고 각 장의 역할을 판단한다. "
            "지시된 출력 형식 외의 말은 하지 않는다.",
            user_prompt,
            temperature=0.1,   # 판단 작업 — 다양성이 아니라 일관성이 필요하다 (위 _call_hcx 주석)
        )
        roles = {}
        for match in _ROLE_LINE.finditer(text or ""):
            number, role = match.group(1), match.group(2).strip()
            # '불명'도 버리지 않는다 — "모른다"는 판정 자체가 중요한 정보다. 버리면 일반
            # thin 지시로 흘러가 모델이 자유 연상을 한다(실측 2026-08-19: '진순'을
            # "음식 관련 용어"라고 해석). 불명이면 아래 2차 객관식으로 좁힌다.
            if role and str(int(number)) in {str(int(n)) for n in thin_numbers}:
                roles[str(int(number))] = role[:80]

        # ── 2차: '불명'으로 답한 장은 객관식으로 다시 묻는다.
        # 열린 질문("역할이 뭐냐")에는 모델이 소심하게 불명으로 도망가지만(temp 0.1에서 더 심함),
        # 단서를 깔고 보기에서 고르게 하면 판단을 내린다 — 약한 모델에서 추론을 끌어내는 정석.
        for number in list(roles):
            if "불명" in roles[number]:
                guessed = self._force_classify_slide(ppt_text, number, topic)
                roles[number] = guessed if guessed else roles[number]

        if roles:
            print(f"🧭 장 역할 분석: {roles}")
        return roles

    def _force_classify_slide(self, ppt_text, slide_number, topic=""):
        """1차 분석이 '불명'이라 한 장을 단서 + 객관식으로 다시 묻는다. 실패하면 빈 문자열."""
        user_prompt = (
            "[장 역할 분석 — 2차]\n"
            f"발표 주제: {topic or '(미상)'}\n\n"
            f"{ppt_text}\n\n"
            f"{int(slide_number)}번 장의 역할을 판단해야 합니다. 단서:\n"
            f"- 이 장의 원문(위 Slide {int(slide_number)}: 뒤의 내용)이 몇 단어뿐입니다\n"
            "- 그 단어가 다른 장에도 나오는지, 발표의 몇 번째 장인지(표지 직후면 소개일 가능성)를 보세요\n\n"
            "반드시 아래 중 **하나만** 고르세요. '모름'은 답이 아닙니다:\n"
            "a) 발표자 또는 팀 소개 — 원문 단어는 이름\n"
            "b) 인물·캐릭터·페르소나 소개 — 원문 단어는 이름\n"
            "c) 제품·브랜드 이름 강조\n"
            "d) 섹션 전환·꾸밈 장\n"
            "출력은 딱 한 줄: 선택한 보기의 설명 부분만 (예: 발표자 또는 팀 소개 — 원문 단어는 이름)"
        )
        text = self._call_hcx(
            "너는 발표 자료 분석가다. 주어진 보기 중 가장 그럴듯한 하나를 반드시 고른다.",
            user_prompt,
            temperature=0.1,
        )
        line = (text or "").strip().splitlines()[0].strip() if (text or "").strip() else ""
        # 보기를 벗어난 답(설명문, '모름')은 버린다.
        if line and "모름" not in line and "불명" not in line and len(line) <= 60:
            return f"{line} (추정)"
        return ""

    def _request_one_slide(self, slide_number, block, position, presentation_time, style, extra_requirement, audience="", topic="", is_last=True, is_first=False, role_hint=None):
        """
        한 장만 요청할 때는 **TOON 포맷을 쓰지 않는다.**
        응답 전체가 곧 이 슬라이드의 대본이므로 구분자가 필요 없고, 오히려 껍데기를 요구하면
        모델이 그걸 안 지켜서 멀쩡한 대본이 버려진다. (실측: 내용은 완벽한데 TOON이 아니라는
        이유로 19장 중 18장을 폐기했다)

        한 장이 실패하면 그 슬라이드는 영구 누락이므로 한 번 더 시도한다.
        """
        # 근거가 될 원문이 없는 슬라이드에는 다른 지시를 준다 — 안 그러면 모델이 빈칸을 지어낸다.
        # 장면 묘사는 30자를 넘어 thin 판정을 안 탈 수 있으므로 라벨로도 명시 분기한다 —
        # 일반 지시("원문만 근거로")로 새면 모델이 묘사를 슬라이드 내용처럼 읽는다.
        needs_guard = _is_thin_source(block) or _SCENE_LABEL in (block or "")
        evidence = _thin_source_instruction(slide_number, block, role_hint) if needs_guard else _NORMAL_SOURCE_INSTRUCTION

        for attempt in range(2):
            text = self._call_hcx(
                self._SINGLE_SLIDE_PROMPT,
                self._build_user_prompt(block, presentation_time, style, extra_requirement, position, audience, topic, evidence),
            )
            script = _clean_single_slide_script(text)
            if script:
                # 마지막 장이 아니면 "감사합니다" 같은 마무리 인사를 지운다(프롬프트 금지를 모델이 자주 어김).
                if not is_last:
                    script = _strip_closing_greeting(script)
                    script = _strip_leading_closing(script)
                    # 첫 장이 아닌데 "안녕하세요"로 시작하는 것도 같은 이유로 코드에서 지운다.
                    if not is_first:
                        script = _strip_leading_greeting(script)
                # 자료에 없는 발표자 이름("홍길동입니다")도 같은 이유로 코드에서 지운다.
                script = _strip_placeholder_name(script)
                # 빈 장 대본이 "내용이 없다"는 사정을 대사로 말하면 화면 안내 한 문장으로 교체
                if _is_empty_source(block):
                    script = _replace_leaked_empty_script(script, slide_number)
                return [{"slide_number": slide_number, "script": script}]
            if attempt == 0:
                print(f"  ↻ 슬라이드 {slide_number} 응답이 비어 한 번 더 시도합니다.")

        return []

    # 슬라이드 한 장의 대본만 쓰는 경우(정상 경로). 지시가 짧을수록 결과가 안정적이다 —
    # 규칙을 8개까지 늘렸더니 오히려 19장 중 13장이 형식을 못 지켰다.
    _SINGLE_SLIDE_PROMPT = """
        당신은 대한민국 최고의 '프레젠테이션 스피치 라이터'입니다.
        주어진 슬라이드 **한 장**에 대해, 발표자가 그 슬라이드를 띄워놓고 말할 대본을 작성하세요.

        [작성 가이드라인]
        1. 슬라이드에 적힌 내용만 다루세요. 자료에 없는 **구체적 사실**(기술·제품·회사 이름, 숫자,
           사람 이름)은 절대 지어내지 말고, 근거가 없으면 그 부분은 일반적인 표현으로 넘기세요.
           자료에 근거가 없으면 '저희가 개발한'처럼 만든 주체를 단정하지도 마세요.
        2. 발표자가 청중 앞에서 실제로 말하듯 자연스럽게 작성하세요. 문어체(보고서 문장)는 피하되,
           말투(문장 끝맺음)는 아래 [반드시 지킬 것 — 말투]를 그대로 따르세요.
        3. [추가 요구사항]이 주어지면 반드시 반영하세요.
        4. [반드시 지킬 것 — 위치]의 지시를 그대로 따르세요.

        출력은 대본 문장만 쓰세요. "Slide 1:" 같은 라벨이나 머리말, 해설을 덧붙이지 마세요.
        """

    # 원본이 브리프 한 덩어리뿐이라, 모델이 여러 슬라이드로 확장해야 하는 경우.
    _MULTI_SLIDE_PROMPT = """
        당신은 대한민국 최고의 '프레젠테이션 스피치 라이터'입니다.
        사용자가 제공하는 [PPT 텍스트]와 [발표 조건]을 바탕으로 자연스러운 전체 발표 대본을 작성해주세요.

        [작성 가이드라인]
        1. 각 슬라이드의 핵심 메시지를 파악해 발표자가 말하듯 작성하세요.
           말투(문장 끝맺음)는 [반드시 지킬 것 — 말투]를 그대로 따르세요.
        2. 대본 내용(script) 안에는 쉼표(,) 대신 마침표(.)나 띄어쓰기를 사용하세요. (파싱 오류 방지)
        3. [추가 요구사항]이 주어지면 반드시 반영하세요.
        4. 출력은 반드시 토큰 최적화된 아래의 [TOON 포맷]을 엄격히 준수하며, 다른 텍스트는 덧붙이지 마세요.
        5. 슬라이드마다 한 줄씩 출력하고, 각 줄은 슬라이드 번호와 쉼표로 시작하세요.
           전체를 하나의 줄글로 쓰면 안 됩니다.

        [TOON 출력 포맷 예시]
        slides[슬라이드총개수]{slide_number,script}:
         1,안녕하세요 오늘 발표를 맡은 진행자입니다. 첫 번째 슬라이드입니다.
         2,다음으로 넘어가겠습니다. 시장 규모를 살펴보면...
        """

    def _build_user_prompt(self, ppt_text, presentation_time, style, extra_requirement, position, audience="", topic="", evidence=""):
        # [위치]와 [말투] 지시는 프롬프트 맨 뒤에 둔다. 중간에 끼워 넣었더니 모델이 무시하고
        # 장마다 인사말로 시작하거나(19장 중 16장) 해요체로 흘러내렸다.
        # "발표 스타일: 격식체"처럼 단어만 주면 안 되고, 어미까지 문장으로 못박아야 한다.
        # 발표 주제는 [발표 조건]에 한 줄로만 넣는다 — 규칙을 늘리면 오히려 형식을 못 지키므로
        # 슬라이드가 주제에서 벗어나지 않을 정도의 '맥락'으로만 제공한다.
        return f"""
        [발표 조건]
        - 발표 시간: {presentation_time}분
        - 발표 주제: {topic or '자료 내용에서 파악'}
        - 발표 대상(청중): {audience or '특정하지 않음(일반 청중)'}

        [추가 요구사항]
        {extra_requirement or '없음'}

        [PPT 텍스트]
        {ppt_text}

        [반드시 지킬 것 — 근거]
        {evidence or _NORMAL_SOURCE_INSTRUCTION}

        [반드시 지킬 것 — 위치]
        {position or '전체 발표 대본을 작성하세요.'}

        [반드시 지킬 것 — 대상]
        {_audience_instruction(audience)}

        [반드시 지킬 것 — 말투]
        {style_instruction(style)}
        """

    def _request_raw(self, ppt_text, presentation_time, style, extra_requirement, valid_slide_numbers, audience="", topic=""):
        """브리프 한 덩어리를 여러 슬라이드로 확장하는 경로. 여기서만 TOON이 필요하다."""
        toon_text = self._call_hcx(
            self._MULTI_SLIDE_PROMPT,
            self._build_user_prompt(ppt_text, presentation_time, style, extra_requirement, "", audience, topic),
        )
        if toon_text is None:
            return None
        return self._parse_toon_format(toon_text, valid_slide_numbers)

    def _call_hcx(self, system_prompt, user_prompt, temperature=0.5):
        """HCX 호출 공통부. 응답 본문 문자열을 돌려주고, 실패하면 None.

        temperature: 대본 생성은 0.5(표현 다양성). 역할 **분석**은 판단 작업이라 0.1 —
        0.5로 돌리면 같은 덱에서 "발표자 이름"↔"불안 통계"로 판정이 널뛴다(2026-08-19 실측,
        3회 중 1회 오판 → 대본이 "진순이란 진정성 있는 소통"이라는 지어내기로 이어짐).
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload = {
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
            ],
            "topP": 0.8,
            "topK": 0,
            "maxTokens": 2000, # TOON 포맷으로 인해 필요 토큰 수가 대폭 줄어듭니다.
            "temperature": temperature,
            "repeatPenalty": 5.0
        }

        try:
            # 429(분당 한도)는 슬라이드마다 호출하는 이 구조에서 정상적으로 발생한다.
            # 재시도 없이 던지면 그 슬라이드가 영구 누락된다(clova/hcx_request.py 참고).
            response = post_with_retry(self.endpoint, headers, payload, REQUEST_TIMEOUT_SECONDS, label="full")
            result = response.json()

            usage = result.get('result', {}).get('usage', {})
            log_hcx_call(
                "full",
                usage.get('promptTokens', 0),
                usage.get('completionTokens', 0),
                usage.get('totalTokens', 0),
            )

            return result['result']['message']['content']

        except Exception as e:
            print(f"❌ 전체 대본 생성 API 호출 중 에러가 발생했습니다: {e}")
            return None

    def _parse_toon_format(self, toon_text, valid_slide_numbers=None):
        try:
            data_list = parse_toon_slides(toon_text, valid_slide_numbers)
            if not data_list:
                return {"raw_toon": toon_text}
            return {"slides": data_list}
        except Exception as e:
            print(f"⚠️ TOON 포맷 파싱 에러: {e}")
            return {"raw_toon": toon_text}

class ScriptRefiner:
    """
    FullScriptGenerator가 만든 초안 대본을 다시 HCX에 넣어
    발표자 1인칭 구어체로 더 자연스럽게 다듬는 2차 리뷰 단계.
    입력/출력 모두 "Slide N: 내용" 형식의 평문 대본이다.
    """

    def __init__(self):
        self.api_key = os.getenv("HCX_API_KEY")
        self.model_name = os.getenv("HCX_MODEL_NAME", "HCX-005")
        self.endpoint = f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{self.model_name}"
        self.use_fallback = _is_placeholder_key(self.api_key)

    def refine_script(self, script_text, style="격식체"):
        """
        생성 단계와 같은 이유로(입력이 길면 모델이 슬라이드를 빠뜨리거나 줄글로 합쳐버림)
        긴 대본은 나눠서 다듬는다. 다듬은 결과에서 슬라이드가 사라졌으면 그 묶음은 초안을 그대로 쓴다.
        """
        if self.use_fallback:
            return None

        blocks = _split_slide_blocks(script_text)
        if not blocks:
            return self._refine_chunk(script_text, style)

        chunks = [blocks[start:start + REFINE_SLIDES_PER_REQUEST] for start in range(0, len(blocks), REFINE_SLIDES_PER_REQUEST)]

        # 묶음(chunk)들도 서로 독립적이라 동시에 다듬는다. pool.map은 입력 순서대로 결과를 돌려주므로
        # refined_parts를 그대로 이어 붙여도 슬라이드 순서가 유지된다.
        def refine_one(chunk):
            chunk_text = "\n\n".join(block for _, block in chunk)
            refined = self._refine_chunk(chunk_text, style)
            # 다듬다가 슬라이드를 잃어버렸거나 번호가 바뀌었으면 자연스러움보다 내용 보존이 우선이다.
            expected = [number for number, _ in chunk]
            if not refined or [number for number, _ in _split_slide_blocks(refined)] != expected:
                print(f"  ⚠️ 슬라이드 {chunk[0][0]}~{chunk[-1][0]} 고도화 결과가 원본과 안 맞아 초안을 유지합니다.")
                refined = chunk_text
            # 다듬는 과정에서 발표자 이름을 자리표시자로 "보강"해 넣는 경우가 있어 여기서도 한 번 더 지운다.
            return _strip_placeholder_name(refined)

        workers = min(MAX_CONCURRENT_REQUESTS, len(chunks))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            refined_parts = list(pool.map(refine_one, chunks))

        return "\n\n".join(refined_parts)

    def _refine_chunk(self, script_text, style):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        system_prompt = """
        당신은 발표 대본을 다듬는 전문 감수자입니다.
        입력으로 주어지는 초안 대본은 "Slide N: 내용" 형식의 줄들로 구성되어 있습니다.
        이 대본을 발표자가 청중 앞에서 실제로 말하듯 자연스럽게 다듬어주세요.

        [다듬을 때 기준]
        1. 관찰자 시점("~설명합니다", "~보여줍니다")이 아니라 발표자가 청중에게 직접 말하는 어투("~설명드리겠습니다", "~보여드리겠습니다")로 통일하세요.
        2. 문장이 어색하거나 번역체스러운 부분, 반복되는 표현은 자연스럽게 고치세요.
        3. 문장 끝맺음(말투)은 아래 [반드시 지킬 것 — 말투]를 그대로 따르세요.
        4. 각 슬라이드의 핵심 내용과 정보, 슬라이드 순서는 그대로 유지하세요. 새로운 정보를 추가하거나 빼지 마세요.
        5. "Slide N:" 라벨과 슬라이드 개수는 절대 바꾸지 마세요. 입력에 있던 슬라이드 번호를 그대로 유지하세요.
        6. 과도하게 길이를 늘리거나 줄이지 말고, 자연스러움 개선에만 집중하세요.

        출력은 반드시 입력과 동일하게 "Slide N: 내용" 형식의 줄들로만 구성하고, 다른 설명이나 안내 문구는 절대 덧붙이지 마세요.
        """

        user_prompt = f"""
        [초안 대본]
        {script_text}

        [반드시 지킬 것 — 말투]
        {style_instruction(style)}
        """

        payload = {
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
            ],
            "topP": 0.8,
            "topK": 0,
            "maxTokens": 2000,
            "temperature": 0.4,
            "repeatPenalty": 3.0,
        }

        print("🚀 HyperCLOVA X에 대본 자연스러움 고도화(리뷰)를 요청합니다...")

        try:
            response = post_with_retry(self.endpoint, headers, payload, REQUEST_TIMEOUT_SECONDS, label="refine")
            result = response.json()
            refined_text = result["result"]["message"]["content"]

            usage = result.get("result", {}).get("usage", {})
            log_hcx_call(
                "refine",
                usage.get("promptTokens", 0),
                usage.get("completionTokens", 0),
                usage.get("totalTokens", 0),
            )

            return refined_text.strip()

        except Exception as e:
            print(f"❌ 대본 고도화 API 호출 중 에러가 발생했습니다: {e}")
            return None


if __name__ == "__main__":
    ai_client = FullScriptGenerator()
    sample_ppt = "Slide 1: 메타버스 개요. Slide 2: 시장 규모."
    print(ai_client.generate_full_script(sample_ppt, 1, "격식체"))