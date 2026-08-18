"""
슬라이드를 한 장씩 나눠서 생성하는 로직의 회귀 테스트.

배경 (전부 실측):
- 19장짜리 PPT를 한 번에 넣었더니 모델이 TOON 포맷을 버리고 전체를 줄글 하나로 써서 18장이 유실됐다.
- 모델은 입력 번호가 13~18이든 상관없이 **응답을 항상 1번부터** 매긴다. 절대 번호를 믿으면 통째로 버려진다.
- 여러 장을 한 번에 넣으면 어떤 장은 건너뛰고 어떤 장은 두 줄로 쪼개서 **정렬이 밀린다**.
  (2번 대본에 3번 내용이 들어감 / 전체의 26%가 이웃 슬라이드 내용을 말하고 있었다)
  그래서 지금은 한 장씩 요청한다 — 한 장만 보내면 무슨 응답이 오든 그 장의 대본이다.
"""

import clova.full_generation.generator as generator_module
from clova.full_generation.generator import FullScriptGenerator, _split_slide_blocks


def _generator():
    instance = FullScriptGenerator()
    instance.api_key = "test-key"
    instance.use_fallback = False
    return instance


def _ppt_text(count):
    return "\n".join(f"Slide {i}: {i}번 슬라이드 내용" for i in range(1, count + 1))


class _FakeResponse:
    def __init__(self, content, status_code=200):
        self._content = content
        self.status_code = status_code
        self.text = content

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "result": {
                "message": {"content": self._content},
                "usage": {"promptTokens": 1, "completionTokens": 1, "totalTokens": 2},
            }
        }


def _stub_hcx(monkeypatch, responder):
    """responder(user_prompt) -> 모델이 반환할 문자열. None을 반환하면 API 실패로 취급한다."""
    sent = []

    def fake_post(url, headers=None, json=None, timeout=None):
        user_prompt = json["messages"][-1]["content"][0]["text"]
        sent.append(user_prompt)
        content = responder(user_prompt)
        if content is None:
            return _FakeResponse("", status_code=500)
        return _FakeResponse(content)

    monkeypatch.setattr(generator_module.requests, "post", fake_post)
    return sent


def test_split_slide_blocks_keeps_numbers_and_content():
    blocks = _split_slide_blocks("Slide 1: 첫 내용\nSlide 2: 둘째 내용")

    assert [num for num, _ in blocks] == ["1", "2"]
    assert "첫 내용" in blocks[0][1]


def test_each_slide_gets_its_own_request(monkeypatch):
    def responder(user_prompt):
        return "slides[1]{slide_number,script}:\n 1,이 슬라이드의 대본입니다."

    sent = _stub_hcx(monkeypatch, responder)
    result = _generator().generate_full_script(_ppt_text(5), 10, "격식체")

    assert len(sent) == 5, "슬라이드마다 한 번씩 요청해야 정렬이 보장된다"
    assert [s["slide_number"] for s in result["slides"]] == ["1", "2", "3", "4", "5"]


def test_each_request_contains_only_its_own_slide(monkeypatch):
    """
    정렬이 밀리는 근본 원인은 한 요청에 여러 장이 들어가는 것이었다.
    대본을 쓸 대상 슬라이드는 항상 하나여야 한다(이웃은 [앞뒤 맥락]으로만 들어간다).
    """

    def responder(user_prompt):
        return "slides[1]{slide_number,script}:\n 1,대본"

    sent = _stub_hcx(monkeypatch, responder)
    _generator().generate_full_script(_ppt_text(4), 8, "격식체")

    for prompt in sent:
        target_section = prompt.split("[PPT 텍스트]")[1]
        assert target_section.count("Slide ") == 1


def test_position_is_given_so_middle_slides_do_not_greet(monkeypatch):
    """
    매 슬라이드가 독립 요청이라 모델이 자기가 발표 중간인 걸 모르고 장마다 인사한다.
    위치를 알려줘야 첫 장에서만 인사하고 마지막 장에서만 마무리한다.

    ⚠️ 이웃 슬라이드의 "내용"까지 넘겼더니 모델이 그 내용의 대본을 써버려서(3번이 4번을 설명)
    정렬이 다시 깨졌다. 그래서 내용이 아니라 위치만 넘긴다.
    """

    def responder(user_prompt):
        return "slides[1]{slide_number,script}:\n 1,대본"

    sent = _stub_hcx(monkeypatch, responder)
    _generator().generate_full_script(_ppt_text(3), 6, "격식체")

    # 슬라이드별 호출이 병렬이라 sent의 순서는 보장되지 않는다. 위치가 아니라 내용으로 프롬프트를 찾는다.
    def position_for(slide_marker):
        prompt = next(p for p in sent if slide_marker in p.split("[PPT 텍스트]")[1])
        return prompt.split("[반드시 지킬 것 — 위치]")[1]

    assert "첫 번째" in position_for("1번 슬라이드 내용")
    middle = position_for("2번 슬라이드 내용")
    assert "인사말" in middle and "시작하지 말고" in middle
    assert "마지막" in position_for("3번 슬라이드 내용")
    # 이웃 슬라이드 내용이 2번 프롬프트에 새어 들어가면 안 된다.
    second = next(p for p in sent if "2번 슬라이드 내용" in p.split("[PPT 텍스트]")[1])
    assert "3번 슬라이드 내용" not in second


def test_failed_slide_is_retried_once(monkeypatch):
    """한 장이 실패하면 그 슬라이드는 영구 누락이므로 한 번은 다시 시도해야 한다."""
    import threading

    lock = threading.Lock()
    failed_once = set()

    def responder(user_prompt):
        # 병렬 실행이라 스레드 안전하게, 1번 슬라이드만 첫 시도에서 실패시키고 재시도에서 성공시킨다.
        if "1번 슬라이드 내용" in user_prompt.split("[PPT 텍스트]")[1]:
            with lock:
                first_try = "s1" not in failed_once
                failed_once.add("s1")
            return None if first_try else "두 번째 시도 대본"
        return "2번 슬라이드 대본"

    _stub_hcx(monkeypatch, responder)
    result = _generator().generate_full_script(_ppt_text(2), 4, "격식체")

    scripts = {s["slide_number"]: s["script"] for s in result["slides"]}
    assert scripts["1"] == "두 번째 시도 대본"  # 재시도로 살아남음
    assert scripts["2"] == "2번 슬라이드 대본"


def test_local_numbering_is_mapped_back_to_real_slide_numbers(monkeypatch):
    """13~18번을 보내도 모델은 1~6으로 답한다. 그대로 두면 전부 버려진다."""

    def responder(user_prompt):
        return "slides[6]{slide_number,script}:\n" + "\n".join(f" {i},{i}번째 대본" for i in range(1, 7))

    _stub_hcx(monkeypatch, responder)
    ppt_text = "\n".join(f"Slide {i}: 내용 {i}" for i in range(13, 19))
    result = _generator().generate_full_script(ppt_text, 5, "격식체")

    assert [s["slide_number"] for s in result["slides"]] == ["13", "14", "15", "16", "17", "18"]


def test_extra_rows_are_merged_into_the_requested_slide(monkeypatch):
    """
    한 장을 보냈는데 모델이 2~3번까지 써버려도, 그 내용은 결국 그 장에서 할 말이다.
    한 장의 대본으로 합쳐야 한다 — 새 슬라이드로 만들면 원본에 없는 슬라이드가 생긴다.
    """

    def responder(user_prompt):
        return "slides[1]{1,앞부분입니다.}\n{2,뒷부분입니다.}"

    _stub_hcx(monkeypatch, responder)
    result = _generator().generate_full_script(_ppt_text(2), 4, "격식체")

    assert [s["slide_number"] for s in result["slides"]] == ["1", "2"]
    assert all(s["script"] == "앞부분입니다. 뒷부분입니다." for s in result["slides"])


def test_failed_slide_does_not_shift_the_others(monkeypatch):
    """한 장이 끝내 실패해도 나머지 슬라이드 번호가 밀리면 안 된다."""

    def responder(user_prompt):
        if "2번 슬라이드 내용" in user_prompt.split("[PPT 텍스트]")[1]:
            return None
        return "정상 대본"

    _stub_hcx(monkeypatch, responder)
    result = _generator().generate_full_script(_ppt_text(3), 6, "격식체")

    assert [s["slide_number"] for s in result["slides"]] == ["1", "3"]


def test_toon_wrapper_is_stripped_from_plain_response(monkeypatch):
    """평문으로 답하라고 해도 모델이 습관적으로 TOON 껍데기를 붙이는 경우가 있다."""

    def responder(user_prompt):
        return "slides[1]{slide_number,script}:\n 1,실제 대본 문장입니다."

    _stub_hcx(monkeypatch, responder)
    result = _generator().generate_full_script(_ppt_text(2), 4, "격식체")

    assert all(s["script"] == "실제 대본 문장입니다." for s in result["slides"])


def test_slide_label_is_stripped_from_plain_response(monkeypatch):
    def responder(user_prompt):
        return "Slide 1: 라벨이 붙은 대본입니다."

    _stub_hcx(monkeypatch, responder)
    result = _generator().generate_full_script(_ppt_text(2), 4, "격식체")

    assert all(s["script"] == "라벨이 붙은 대본입니다." for s in result["slides"])


def test_single_source_slide_may_expand_into_many(monkeypatch):
    """
    반대로 원본이 브리프 한 덩어리뿐이면(PPT 없이 주제/목차만 받은 프로젝트),
    모델이 여러 슬라이드로 확장하는 것이 정상이므로 합치지 말고 그대로 둔다.
    """

    def responder(user_prompt):
        return "slides[3]{slide_number,script}:\n 1,도입부\n 2,본론\n 3,마무리"

    _stub_hcx(monkeypatch, responder)
    result = _generator().generate_full_script("Slide 1: 주제와 목차 브리프", 5, "격식체")

    assert [s["slide_number"] for s in result["slides"]] == ["1", "2", "3"]


def test_non_slide_input_is_sent_as_is(monkeypatch):
    """주제/목차 브리프처럼 "Slide N:" 형식이 아닌 입력은 나누지 않고 그대로 보낸다."""

    def responder(user_prompt):
        return "slides[1]{slide_number,script}:\n 1,브리프 기반 대본"

    sent = _stub_hcx(monkeypatch, responder)
    result = _generator().generate_full_script("주제: 메타버스\n목차: 개요, 사례", 5, "격식체")

    assert len(sent) == 1
    assert result["slides"][0]["script"] == "브리프 기반 대본"


# ── 중간 슬라이드의 마무리 인사 제거 ──────────────────────────────────────────
# 프롬프트에 "마무리 인사(감사합니다 등)를 넣지 마세요"라고 이미 금지했는데도 모델이 자주 어긴다
# (실측: 제로 PPT 8장 재생성에서 중간 슬라이드 2장이 "감사합니다"로 끝남). 코드로 확실히 지운다.

def test_closing_greeting_is_stripped_from_middle_slides(monkeypatch):
    def responder(user_prompt):
        return "이 슬라이드의 내용을 설명드리겠습니다. 감사합니다."

    _stub_hcx(monkeypatch, responder)
    result = _generator().generate_full_script(_ppt_text(3), 3, "격식체")

    scripts = {s["slide_number"]: s["script"] for s in result["slides"]}
    assert scripts["1"] == "이 슬라이드의 내용을 설명드리겠습니다."
    assert scripts["2"] == "이 슬라이드의 내용을 설명드리겠습니다."
    # 마지막 장은 마무리 인사가 정상이므로 그대로 둔다.
    assert scripts["3"] == "이 슬라이드의 내용을 설명드리겠습니다. 감사합니다."


def test_various_closing_greetings_are_stripped(monkeypatch):
    from clova.full_generation.generator import _strip_closing_greeting

    assert _strip_closing_greeting("본문입니다. 경청해 주셔서 감사합니다.") == "본문입니다."
    assert _strip_closing_greeting("본문입니다. 이상입니다.") == "본문입니다."
    assert _strip_closing_greeting("본문입니다. 감사합니다. 이상입니다.") == "본문입니다."
    # 인사가 없으면 그대로 둔다.
    assert _strip_closing_greeting("본문입니다.") == "본문입니다."
    # 문장 중간의 '감사'는 건드리지 않는다.
    assert _strip_closing_greeting("감사 인사를 전하는 문화를 살펴봅니다.") == "감사 인사를 전하는 문화를 살펴봅니다."


def test_greeting_only_script_is_kept(monkeypatch):
    """지우면 빈 대본이 되는 경우엔 원문을 유지한다(내용 유실 방지)."""
    from clova.full_generation.generator import _strip_closing_greeting

    assert _strip_closing_greeting("감사합니다.") == "감사합니다."


def test_sentence_style_closings_are_stripped(monkeypatch):
    """단어형 인사만 지우던 시절의 구멍(2026-08-18 체육 지도안 실측).

    1·2장이 "이상으로 …를 소개해 드렸습니다"로, 1장은 "많은 관심과 조언 부탁드립니다"까지
    붙여 끝났다 — 문장형 마무리라 기존 패턴을 그대로 통과했다. 연속으로 읽으면 장마다
    발표가 끝나는 것처럼 들린다.
    """
    from clova.full_generation.generator import _strip_closing_greeting

    # 실제로 나왔던 형태 그대로
    assert _strip_closing_greeting(
        "평가는 과정 중심으로 이루어집니다. 이상으로 저희가 준비한 체육 교수·학습 지도안을 소개해 드렸습니다. "
        "여러분의 많은 관심과 조언 부탁드립니다."
    ) == "평가는 과정 중심으로 이루어집니다."
    assert _strip_closing_greeting(
        "정리 단계에서는 자기 평가를 진행합니다. 이상으로 체육 교수·학습 지도안의 개요를 소개해 드렸습니다."
    ) == "정리 단계에서는 자기 평가를 진행합니다."
    assert _strip_closing_greeting(
        "본문입니다. 지금까지 프로젝트 구조를 말씀드렸습니다."
    ) == "본문입니다."


def test_content_requests_are_not_mistaken_for_closings(monkeypatch):
    """본문에 있는 요청·설명 문장까지 지우면 내용이 유실된다."""
    from clova.full_generation.generator import _strip_closing_greeting

    # '부탁드립니다'라도 관심·조언·성원·격려가 없으면 본문 요청이다.
    assert _strip_closing_greeting(
        "실습 전에 안전 수칙 확인을 부탁드립니다."
    ) == "실습 전에 안전 수칙 확인을 부탁드립니다."
    # 문장 중간의 '이상으로'(수단·기준 의미)는 문장 시작이 아니면 건드리지 않는다.
    assert _strip_closing_greeting(
        "참여율을 80% 이상으로 끌어올리는 것이 목표입니다."
    ) == "참여율을 80% 이상으로 끌어올리는 것이 목표입니다."


def test_missing_slides_are_reported_in_result(monkeypatch):
    """끝내 못 만든 슬라이드는 콘솔에만 찍지 말고 결과에 실어야 한다.
    안 그러면 프론트가 '왜 이 장만 비어 있지?'를 알 수 없다."""

    def responder(user_prompt):
        # 2번 슬라이드만 계속 빈 응답 -> 재시도까지 실패
        return "" if "2번 슬라이드 내용" in user_prompt else "정상 대본입니다."

    _stub_hcx(monkeypatch, responder)
    result = _generator().generate_full_script(_ppt_text(3), 3, "격식체")

    assert [s["slide_number"] for s in result["slides"]] == ["1", "3"]
    assert result["missing_slide_numbers"] == ["2"]


def test_no_missing_slides_reports_empty_list(monkeypatch):
    _stub_hcx(monkeypatch, lambda user_prompt: "정상 대본입니다.")
    result = _generator().generate_full_script(_ppt_text(2), 2, "격식체")
    assert result["missing_slide_numbers"] == []


# ------------------------------------------------- 근거 없는 내용 지어내기 방지

def test_placeholder_presenter_name_is_stripped():
    """자료에 발표자 이름이 없으면 모델이 '홍길동'/'OOO'로 채운다(실측: 4개 발표 중 2개의 첫 장).
    프롬프트로 이미 금지했는데도 어기므로 코드에서 지운다."""
    from clova.full_generation.generator import _strip_placeholder_name

    # '맡았습니다'가 아니라 '시작하겠습니다' — PPT 주인 피드백(2026-08-18):
    # "~의 발표를 맡았습니다"보다 "~ 발표 시작하겠습니다"가 실제 발표에서 자연스럽다.
    assert _strip_placeholder_name(
        "안녕하세요. 이번 발표를 맡은 홍길동입니다."
    ) == "안녕하세요. 이번 발표를 시작하겠습니다."
    assert _strip_placeholder_name(
        "안녕하세요. 발표자 OOO입니다."
    ) == "안녕하세요. 발표를 시작하겠습니다."
    assert _strip_placeholder_name(
        "안녕하세요. 저는 ○○○입니다. 발표를 시작하겠습니다."
    ) == "안녕하세요. 발표를 시작하겠습니다."


def test_real_presenter_name_is_kept():
    """진짜 이름까지 지우면 자료에 있는 정보를 잃는다."""
    from clova.full_generation.generator import _strip_placeholder_name

    original = "안녕하세요. 이번 발표를 맡은 김진순입니다."
    assert _strip_placeholder_name(original) == original


def test_placeholder_stripping_does_not_empty_the_script():
    from clova.full_generation.generator import _strip_placeholder_name

    assert _strip_placeholder_name("저는 홍길동입니다.") == "저는 홍길동입니다."


def test_placeholder_name_is_stripped_in_generated_script(monkeypatch):
    """단위 함수만이 아니라 실제 생성 경로에서도 걸러져야 한다."""
    # 슬라이드가 2장 이상이어야 장별 생성 경로(_request_one_slide)를 탄다.
    _stub_hcx(monkeypatch, lambda user_prompt: "안녕하세요. 이번 발표를 맡은 홍길동입니다.")
    result = _generator().generate_full_script(_ppt_text(2), 2, "격식체")

    assert "홍길동" not in result["slides"][0]["script"]


def test_prompt_forbids_inventing_concrete_facts(monkeypatch):
    """가이드라인이 짧은 슬라이드(예: '서비스 기술 스택')에서 모델이 스택을 통째로 지어냈다.
    구체적 사실을 지어내지 말라는 지시가 시스템 프롬프트에 살아 있어야 한다."""
    from clova.full_generation.generator import FullScriptGenerator

    prompt = FullScriptGenerator._SINGLE_SLIDE_PROMPT
    assert "지어내지" in prompt
    assert "저희가 개발한" in prompt, "만든 주체를 단정하지 말라는 지시가 없습니다"


def test_thin_source_slide_gets_a_different_instruction(monkeypatch):
    """원문이 제목 한 줄뿐이면 모델은 빈칸을 추측으로 채운다.
    실측(2026-08-06): 텍스트가 0인 '서비스 기술 스택' 장에 React·Node.js·MongoDB를 통째로 지어냈다.
    '지어내지 마세요'만으로는 재발했으므로, 그런 장임을 감지해 무엇을 쓸지 대신 알려준다."""
    from clova.full_generation.generator import _thin_source_instruction

    seen = []
    _stub_hcx(monkeypatch, lambda user_prompt: seen.append(user_prompt) or "대본입니다.")
    _generator().generate_full_script(
        "Slide 1: 서비스 기술 스택\nSlide 2: " + "구체적인 내용이 충분히 들어 있는 슬라이드입니다. " * 3,
        2, "격식체",
    )

    thin_prompt = next(p for p in seen if "서비스 기술 스택" in p)
    rich_prompt = next(p for p in seen if "구체적인 내용이 충분히" in p)
    assert _thin_source_instruction(1) in thin_prompt
    assert _thin_source_instruction(2) not in rich_prompt, "내용이 있는 장까지 일반 안내문으로 만들면 대본이 부실해진다"


def test_thin_source_slides_are_reported(monkeypatch):
    """근거 없이 만든 장을 조용히 넘기면 발표자가 그대로 읽다가 사실이 아닌 말을 하게 된다."""
    _stub_hcx(monkeypatch, lambda user_prompt: "대본입니다.")
    result = _generator().generate_full_script(
        "Slide 1: 목차\nSlide 2: " + "실제 내용이 충분히 들어 있는 슬라이드입니다. " * 3,
        2, "격식체",
    )

    assert result["thin_source_slide_numbers"] == ["1"]


def test_thin_source_detection_ignores_labels():
    """'Slide 20:'이나 '[발표자 가이드]' 같은 머리표는 근거가 아니다."""
    from clova.full_generation.generator import _is_thin_source

    assert _is_thin_source("Slide 20: [발표자 가이드] 서비스 기술 스택")
    assert not _is_thin_source(
        "Slide 20: [발표자 가이드] 서비스 기술 스택 / [슬라이드에서 읽힌 글자] "
        "프론트엔드 React 백엔드 Spring Boot 데이터베이스 PostgreSQL 배포 AWS EC2"
    )


def test_leading_closing_is_stripped_on_middle_slides():
    """중간 장이 마무리 인사로 **시작**하는 경우(2026-08-18 실측, 이미지형 14장 중 10장).

    "여러분, 지금까지 저희 발표를 들어주셔서 감사합니다. 이제 마지막으로…" — 끝 인사만
    지우던 안전망이 시작 인사를 통과시켰다. 인사만 벗기고 뒤 본문은 살려야 한다.
    """
    from clova.full_generation.generator import _strip_leading_closing

    assert _strip_leading_closing(
        "여러분, 지금까지 저희 발표를 들어주셔서 감사합니다. 이제 한 가지 중요한 사실을 알려드리겠습니다."
    ) == "이제 한 가지 중요한 사실을 알려드리겠습니다."
    assert _strip_leading_closing(
        "지금까지 경청해 주셔서 감사합니다. 다음 내용입니다."
    ) == "다음 내용입니다."
    # 본문이 '지금까지'로 시작하는 정상 문장은 건드리지 않는다.
    assert _strip_leading_closing(
        "지금까지의 판매 실적을 분석해 보겠습니다."
    ) == "지금까지의 판매 실적을 분석해 보겠습니다."
    # 인사뿐이면 원문 유지(빈 대본 방지).
    assert _strip_leading_closing(
        "지금까지 들어주셔서 감사합니다."
    ) == "지금까지 들어주셔서 감사합니다."


def test_thin_instruction_varies_by_slide_number():
    """빈 장 지시가 전부 같으면 빈 장 대본도 전부 같아진다(실측: 빈 장 4개 중 3개가 동일 문장).

    화면을 가리키는 예시 표현이 장 번호에 따라 달라져야 하고, 질문형 도입 금지도 들어가야 한다.
    """
    from clova.full_generation.generator import _thin_source_instruction

    first, second, third = (_thin_source_instruction(n) for n in (1, 2, 3))
    assert len({first, second, third}) == 3, "장 번호가 달라도 지시가 같다"
    assert _thin_source_instruction(4) == first, "3개 예시를 순환해야 한다"
    for text in (first, second, third):
        assert "질문" in text and "지어내" in text


def test_completely_empty_slide_gets_one_sentence_instruction():
    """원문 0자인 장에 '2~3문장 안내'를 요구하면 모델이 주제를 추측해 단정한다.

    실측(2026-08-18): 발표자 소개 사진뿐인 장에 "핵심 기능과 혜택들을 설명드리고자
    합니다"라고 썼고, PPT 주인이 "그냥 자기소개 장인데 대본이 엄청 많다"고 지적했다.
    빈 장은 한 문장 + 내용 단정 금지여야 한다.
    """
    from clova.full_generation.generator import _thin_source_instruction

    empty = _thin_source_instruction(2, "Slide 2: ")
    assert "한 문장" in empty and "단정" in empty

    # 제목 한 줄이라도 있으면 기존 thin 지시(2~3문장 안내)를 유지한다.
    thin = _thin_source_instruction(2, "Slide 2: 서비스 기술 스택")
    assert "2~3문장" in thin
    assert thin != empty


def test_appeal_endings_are_stripped_on_middle_slides():
    """권유형 맺음이 장마다 나오면 슬라이드 간 연결이 끊긴다 (PPT 주인 피드백 2026-08-19).

    "기대해 주시기 바랍니다", "~해 보시길 바랍니다"로 중간 장이 끝나면
    장마다 발표가 일단락된 것처럼 들린다.
    """
    from clova.full_generation.generator import _strip_closing_greeting

    assert _strip_closing_greeting(
        "다음으로는 이 서비스의 활용법을 설명해 드리겠습니다. 기대해 주시기 바랍니다."
    ) == "다음으로는 이 서비스의 활용법을 설명해 드리겠습니다."
    assert _strip_closing_greeting(
        "실시간 피드백 시스템을 제공합니다. 이제 여러분의 발표 실력을 한 단계 업그레이드해 보시길 바랍니다."
    ) == "실시간 피드백 시스템을 제공합니다."
    assert _strip_closing_greeting(
        "핵심 기능은 세 가지입니다. 다음 내용도 기대해 주세요."
    ) == "핵심 기능은 세 가지입니다."


def test_screen_pointing_sentence_is_not_stripped():
    """빈 장의 화면 안내('봐주시기 바랍니다')는 우리가 시킨 문장이다 — 지우면 대본이 빈다."""
    from clova.full_generation.generator import _strip_closing_greeting

    keep = "화면의 내용을 함께 봐주시기 바랍니다."
    assert _strip_closing_greeting(keep) == keep


def test_middle_slide_leading_greeting_is_stripped():
    """중간 장의 '안녕하세요, 여러분.' 시작 — 프롬프트 금지로도 재발해 코드로 지운다(2026-08-19 실측: 12장)."""
    from clova.full_generation.generator import _strip_leading_greeting

    assert _strip_leading_greeting(
        "안녕하세요, 여러분. 오늘은 저희가 기획한 서비스에 대해 설명드리겠습니다."
    ) == "오늘은 저희가 기획한 서비스에 대해 설명드리겠습니다."
    assert _strip_leading_greeting("안녕하십니까. 본론입니다.") == "본론입니다."
    # 본문 중간의 인사말·인사 아닌 문장은 건드리지 않는다.
    assert _strip_leading_greeting("발표 첫머리에 안녕하세요라고 인사합니다.") == \
        "발표 첫머리에 안녕하세요라고 인사합니다."
    # 인사뿐이면 원문 유지(빈 대본 방지).
    assert _strip_leading_greeting("안녕하세요.") == "안녕하세요."


def test_empty_slide_leak_is_replaced_with_pointing_sentence():
    """빈 장 대본이 '내용을 확인할 수 없습니다'라고 청중에게 말하면 발표 사고다.

    금지 지시(274eda7)로도 재발해서(2026-08-19 실측: 13장 "내용을 확인할 수 없습니다.
    양해를 부탁드리며…") 코드에서 화면 안내 한 문장으로 통째로 교체한다.
    """
    from clova.full_generation.generator import _replace_leaked_empty_script

    leaked = "보시는 바와 같이, 이번 슬라이드에는 내용을 확인할 수 없습니다. 양해를 부탁드립니다."
    replaced = _replace_leaked_empty_script(leaked, 13)
    assert "확인할 수 없" not in replaced and "양해" not in replaced
    assert replaced.endswith(("바랍니다.", "살펴보겠습니다.", "보시죠."))

    # 정상적인 화면 안내는 그대로 둔다.
    ok = "화면의 내용을 함께 봐주시기 바랍니다."
    assert _replace_leaked_empty_script(ok, 3) == ok


def test_role_hint_overrides_generic_thin_instruction():
    """분석이 준 역할이 있으면 thin 지시 대신 역할 기반 지시를 쓴다.

    이름 정규식 하드코딩("한글 2~4자=이름") 대신 덱 전체 분석으로 판단한다 —
    사용자 피드백(2026-08-19): "하드코딩보다 분석을 그런 식으로".
    """
    from clova.full_generation.generator import _thin_source_instruction

    hinted = _thin_source_instruction(2, "Slide 2: 진순", role_hint="발표자 자기소개 — '진순'은 발표자 이름")
    assert "발표자 자기소개" in hinted and "지어내지 마세요" in hinted

    # 역할이 없으면 기존 thin 지시 그대로.
    normal = _thin_source_instruction(2, "Slide 2: 서비스 기술 스택")
    assert "2~3문장" in normal


def test_role_analysis_parses_roles_and_drops_unknown(monkeypatch):
    """분석 응답("번호: 역할")을 dict로 읽고, '불명'과 목록 밖 번호는 버린다."""
    gen = _generator()
    monkeypatch.setattr(gen, "_call_hcx", lambda system, user, **kwargs:
        "2: 발표자 자기소개 — '진순'은 발표자 이름\n3: 불명\n9: 목록에 없는 장")

    roles = type(gen)._analyze_slide_roles_real(gen, "Slide 2: 진순\nSlide 3: ", ["2", "3"], "SpeaKO")

    assert roles == {"2": "발표자 자기소개 — '진순'은 발표자 이름"}


def test_role_hint_reaches_the_slide_prompt(monkeypatch):
    """분석이 판단한 역할이 그 장의 생성 프롬프트에 실려야 한다 — 하드코딩 규칙의 대체물이다."""
    from clova.full_generation.generator import FullScriptGenerator
    monkeypatch.setattr(FullScriptGenerator, "_analyze_slide_roles",
                        lambda self, *a, **k: {"2": "발표자 자기소개 — '진순'은 발표자 이름"})

    sent = _stub_hcx(monkeypatch, lambda p: "대본입니다.")
    _generator().generate_full_script("Slide 1: " + "충분히 긴 첫 장 원문입니다. " * 3 + "\nSlide 2: 진순", 4, "격식체")

    second = next(p for p in sent if "진순" in p.split("[PPT 텍스트]")[1])
    assert "발표자 자기소개" in second, "역할 힌트가 프롬프트에 실리지 않았다"
    first = next(p for p in sent if "첫 장 원문" in p.split("[PPT 텍스트]")[1])
    assert "발표자 자기소개" not in first, "다른 장 프롬프트로 힌트가 샜다"


def test_role_analysis_failure_falls_back_to_generic_thin(monkeypatch):
    """분석이 죽어도 생성은 일반 thin 지시로 계속돼야 한다."""
    from clova.full_generation.generator import FullScriptGenerator
    monkeypatch.setattr(FullScriptGenerator, "_analyze_slide_roles",
                        lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("분석 죽음")))

    _stub_hcx(monkeypatch, lambda p: "대본입니다.")
    result = _generator().generate_full_script(_ppt_text(2), 4, "격식체")

    assert [s["slide_number"] for s in result["slides"]] == ["1", "2"]
