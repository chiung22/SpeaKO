"""결과 화면 빨간 하이라이팅 + 상세 피드백의 감점 요인 검증.

기획 확정 사항이 두 개고, 이 파일은 그 둘이 코드에서 지켜지는지만 본다.

  1) **빨간색으로 칠하는 '틀린 워딩'은 누락(Omission)과 삽입(Insertion) 두 가지뿐이다.**
     발음이 흐린 것(Mispronunciation)은 단어를 틀리게 읽은 게 아니라서 빨강이 아니다.
  2) **상세 피드백은 감점 요인을 근거로 말한다.** 즉 "왜 깎였는가"가 들어가야 한다.
     누락은 아예 안 읽은 단어라 '점수 낮은 단어' 목록에 안 잡히므로, 이걸 따로 넘기지 않으면
     완성도 39점짜리 녹음에도 발음 얘기만 하는 피드백이 나온다(실측).
"""
import re

import pytest

from utils import error_highlights as eh
from clova.feedback.generator import collect_weak_words, _deduction_lines


REFERENCE = "메타버스와 인프라 구축의 특징을 살펴봅시다"
RECOGNIZED = "메타버스와 음 구축의 특징을"


def _words():
    """위 두 문장에 정확히 대응하는 단어 목록.

    - '인프라'  : 대본에 있는데 안 읽음        → 누락  (빨강)
    - '음'      : 대본에 없는데 말함           → 삽입  (빨강)
    - '구축의'  : 읽긴 했는데 점수가 낮음      → 발음  (빨강 아님)
    - '살펴봅시다': 뒷부분을 안 읽음            → 누락  (빨강)
    """
    detail = [
        {"word": "메타버스와", "accuracy_score": 95.0, "error_type": "None"},
        {"word": "인프라", "accuracy_score": 0.0, "error_type": "Omission"},
        {"word": "음", "accuracy_score": 0.0, "error_type": "Insertion"},
        {"word": "구축의", "accuracy_score": 55.0, "error_type": "Mispronunciation"},
        {"word": "특징을", "accuracy_score": 91.0, "error_type": "None"},
        {"word": "살펴봅시다", "accuracy_score": 0.0, "error_type": "Omission"},
    ]
    eh.attach_spans(detail, REFERENCE, RECOGNIZED)
    return detail


# ------------------------------------------------------------ 분류

def test_omission_and_insertion_are_the_only_red():
    """기획 확정: 틀린 워딩 = 누락 + 대본에 없는 말. 이 두 가지만 빨간색이다."""
    assert eh.classify({"error_type": "Omission"}) == "omission"
    assert eh.classify({"error_type": "Insertion"}) == "insertion"

    assert eh._TYPE_META["omission"][0] == eh.LEVEL_ERROR
    assert eh._TYPE_META["insertion"][0] == eh.LEVEL_ERROR
    # 발음이 흐린 건 단어를 틀리게 읽은 게 아니다 — 같은 빨강으로 칠하면 안 된다.
    assert eh._TYPE_META["mispronunciation"][0] == eh.LEVEL_WARNING


def test_low_score_counts_as_mispronunciation_even_without_the_label():
    """Azure는 어지간해선 Mispronunciation을 안 붙이고 점수만 낮춘다. 그것도 잡아야 한다."""
    assert eh.classify({"error_type": "None", "accuracy_score": 40.0}) == "mispronunciation"
    assert eh.classify({"error_type": "None", "accuracy_score": 95.0}) is None


def test_classify_survives_garbage():
    for junk in (None, 123, "문자열", [], {"word": "빈칸"}):
        assert eh.classify(junk) is None


# ------------------------------------------------------------ 하이라이팅

def test_omission_paints_the_script_not_the_transcript():
    """안 읽은 단어는 **대본에만** 존재한다. 인식 텍스트에 칠할 자리가 없다."""
    result = eh.build_highlights(_words())

    ref_words = {item["word"] for item in result["reference"]}
    rec_words = {item["word"] for item in result["recognized"]}

    assert "인프라" in ref_words
    assert "인프라" not in rec_words


def test_insertion_paints_the_transcript_not_the_script():
    """대본에 없는 말은 **인식 텍스트에만** 존재한다."""
    result = eh.build_highlights(_words())

    assert "음" in {item["word"] for item in result["recognized"]}
    assert "음" not in {item["word"] for item in result["reference"]}


def test_spans_point_at_the_right_characters():
    """오프셋이 한 글자라도 밀리면 화면에서 엉뚱한 글자가 빨개진다."""
    result = eh.build_highlights(_words())

    for item in result["reference"]:
        assert REFERENCE[item["start"]:item["end"]] == item["word"]
    for item in result["recognized"]:
        assert RECOGNIZED[item["start"]:item["end"]] == item["word"]


def test_counts_separate_red_from_the_rest():
    result = eh.build_highlights(_words())

    assert result["counts"]["omission"] == 2
    assert result["counts"]["insertion"] == 1
    assert result["counts"]["mispronunciation"] == 1
    # 빨간 개수는 누락 + 삽입. 발음은 포함되지 않는다.
    assert result["counts"]["error"] == 3
    assert result["has_errors"] is True


def test_every_red_item_carries_a_reason():
    """화면이 툴팁으로 "왜 빨간지"를 띄운다. 이유 없이 칠하면 사용자는 영문을 모른다."""
    result = eh.build_highlights(_words())
    reds = [i for i in result["reference"] + result["recognized"] if i["level"] == eh.LEVEL_ERROR]

    assert reds
    for item in reds:
        assert item["reason"]


def test_highlights_are_sorted_by_position():
    """정렬 안 하면 프론트가 겹친 구간을 그릴 때 순서가 뒤엉킨다."""
    result = eh.build_highlights(_words())

    for bucket in ("reference", "recognized"):
        starts = [item["start"] for item in result[bucket]]
        assert starts == sorted(starts)


def test_perfect_reading_has_no_highlights():
    detail = [{"word": "메타버스와", "accuracy_score": 98.0, "error_type": "None"}]
    eh.attach_spans(detail, REFERENCE, REFERENCE)

    result = eh.build_highlights(detail)

    assert result["reference"] == [] and result["recognized"] == []
    assert result["has_errors"] is False


def test_old_records_without_spans_are_recovered_from_text():
    """2026-08-15 이전 평가엔 span이 저장돼 있지 않다. 그래도 화면이 비면 안 된다."""
    stored = [{"word": "인프라", "accuracy_score": 0.0, "error_type": "Omission"}]

    without_text = eh.build_highlights(stored)
    with_text = eh.build_highlights(stored, REFERENCE, RECOGNIZED)

    assert without_text["reference"] == []       # 칠할 위치를 모르니 칠하지 않는다
    assert without_text["counts"]["error"] == 1  # 개수는 여전히 셀 수 있다
    assert with_text["reference"][0]["word"] == "인프라"
    # 저장된 원본을 건드리면 안 된다(DB에 그대로 다시 써질 수 있다).
    assert "reference_span" not in stored[0]


def test_unfindable_word_is_left_unpainted():
    """대본에 없는 형태로 인식된 단어는 억지로 맞추지 않는다. 엉뚱한 곳을 칠하느니 안 칠한다."""
    detail = [{"word": "없는단어", "accuracy_score": 10.0, "error_type": "Mispronunciation"}]
    eh.attach_spans(detail, REFERENCE, RECOGNIZED)

    result = eh.build_highlights(detail)

    assert result["reference"] == [] and result["recognized"] == []
    assert result["counts"]["mispronunciation"] == 1


def test_repeated_word_paints_the_right_occurrence():
    """같은 단어가 여러 번 나올 때 error_type만으로는 어느 것인지 못 고른다 — span이 있는 이유."""
    reference = "발표 준비 발표 자료 발표 연습"
    detail = [
        {"word": "발표", "accuracy_score": 95.0, "error_type": "None"},
        {"word": "준비", "accuracy_score": 95.0, "error_type": "None"},
        {"word": "발표", "accuracy_score": 0.0, "error_type": "Omission"},   # 두 번째 것만 누락
        {"word": "자료", "accuracy_score": 95.0, "error_type": "None"},
    ]
    eh.attach_spans(detail, reference, "발표 준비 자료")

    result = eh.build_highlights(detail)

    assert len(result["reference"]) == 1
    start = result["reference"][0]["start"]
    assert start == reference.index("발표", 1)  # 첫 번째가 아니라 두 번째 '발표'


@pytest.mark.parametrize("junk", [None, [], "문자열", 123, {}])
def test_build_highlights_survives_garbage(junk):
    result = eh.build_highlights(junk)
    assert result["has_errors"] is False
    assert result["counts"]["error"] == 0


def test_malformed_span_is_ignored():
    """span이 깨진 채 저장돼 있으면(문자열, 음수, 역순) 그리지 않는다 — 프론트가 터진다."""
    for bad in ([5, 2], [-1, 3], ["0", "3"], [1], "0,3", None):
        detail = [{"word": "인프라", "error_type": "Omission",
                   "reference_span": bad, "recognized_span": None}]
        assert eh.build_highlights(detail)["reference"] == []


# ------------------------------------------------------------ 감점 요인

def test_deductions_name_omission_and_insertion():
    """상세 피드백이 "왜 깎였는가"를 말하려면 이 두 가지가 반드시 잡혀야 한다."""
    summary = eh.summarize_deductions(_words())
    keys = {factor["key"] for factor in summary["factors"]}

    assert "omission" in keys
    assert "insertion" in keys
    assert summary["counts"]["omission"] == 2
    assert summary["counts"]["insertion"] == 1


def test_deduction_maps_each_factor_to_the_score_it_lowers():
    """누락은 완성도, 삽입·발음은 정확도. 화면이 "어느 점수가 왜 낮은지"를 잇는 근거다."""
    factors = {f["key"]: f for f in eh.summarize_deductions(_words())["factors"]}

    assert factors["omission"]["affects"] == ["completeness"]
    assert factors["insertion"]["affects"] == ["accuracy"]
    assert factors["mispronunciation"]["affects"] == ["accuracy"]


def test_deduction_messages_never_invent_a_point_value():
    """⚠️ Azure는 요인별 감점 폭을 공개하지 않는다. "12점 감점" 같은 숫자를 지어내면 안 된다."""
    metrics = {
        "filler_words": {"count": 4, "ratio_percent": 6.0, "by_word": [{"word": "음", "count": 4}]},
        "pauses": {"available": True, "count": 3, "threshold_seconds": 0.7,
                   "longest_seconds": 2.1, "items": [{"after_word": "특징을"}]},
        "speech_rate": {"available": True, "words_per_minute": 210.0},
    }
    summary = eh.summarize_deductions(_words(), {"accuracy": 70}, metrics)

    # "12점 감점", "5점이 깎였습니다" 같은 표현. 요인별 감점 폭은 Azure가 알려주지 않는다.
    claims_a_point_value = re.compile(r"\d+\s*점\s*(?:이|을|가)?\s*(?:감점|깎|차감|하락)")
    for factor in summary["factors"]:
        assert not claims_a_point_value.search(factor["message"]), (
            f"감점 폭을 지어낸 문장: {factor['message']}"
        )


def test_deduction_message_is_a_finished_sentence():
    """HCX가 실패해도 상세 피드백 화면이 비면 안 된다. message만으로 화면이 서야 한다."""
    for factor in eh.summarize_deductions(_words())["factors"]:
        assert factor["message"].endswith((".", "다.", "요."))
        assert len(factor["message"]) > 10


def test_factors_are_ordered_worst_first():
    """화면이 위에서부터 읽히므로 제일 큰 원인이 맨 위여야 한다."""
    order = {"high": 0, "medium": 1, "low": 2}
    factors = eh.summarize_deductions(_words())["factors"]

    ranks = [order[f["severity"]] for f in factors]
    assert ranks == sorted(ranks)
    assert factors[0]["key"] == eh.summarize_deductions(_words())["primary"]


def test_omission_ratio_excludes_inserted_words():
    """분모를 잘못 잡으면 비율이 틀린다. 삽입은 대본에 없던 말이라 대본 길이가 아니다."""
    detail = [
        {"word": "가", "error_type": "None", "accuracy_score": 95.0},
        {"word": "나", "error_type": "Omission", "accuracy_score": 0.0},
        {"word": "음", "error_type": "Insertion", "accuracy_score": 0.0},
        {"word": "다", "error_type": "None", "accuracy_score": 95.0},
    ]
    factors = {f["key"]: f for f in eh.summarize_deductions(detail)["factors"]}

    # 대본 단어는 가/나/다 3개 → 1/3
    assert factors["omission"]["ratio_percent"] == pytest.approx(33.3, abs=0.1)
    # 말한 단어는 가/음/다 3개 → 1/3
    assert factors["insertion"]["ratio_percent"] == pytest.approx(33.3, abs=0.1)


def test_habits_become_deduction_factors():
    """간투어·멈춤은 Azure 점수에 안 드러난다. 감점 요인에 안 실으면 피드백이 영영 언급 못 한다."""
    metrics = {
        "filler_words": {"count": 7, "ratio_percent": 9.0, "by_word": [{"word": "음", "count": 7}]},
        "pauses": {"available": True, "count": 4, "threshold_seconds": 0.7,
                   "longest_seconds": 3.2, "items": [{"after_word": "특징을"}]},
        "speech_rate": {"available": True, "words_per_minute": 60.0},
    }
    keys = {f["key"] for f in eh.summarize_deductions([], {}, metrics)["factors"]}

    assert {"filler", "pause", "speech_rate"} <= keys


def test_unmeasured_pauses_are_not_reported_as_zero():
    """시간 정보가 없어 못 잰 것과 '멈춤이 없었다'는 다르다. 못 잰 걸 지적하면 안 된다."""
    metrics = {"pauses": {"available": False, "count": 0}, "filler_words": {"count": 0},
               "speech_rate": {"available": False}}

    keys = {f["key"] for f in eh.summarize_deductions([], {}, metrics)["factors"]}

    assert "pause" not in keys
    assert "speech_rate" not in keys


def test_normal_speech_rate_is_not_nagged_about():
    metrics = {"speech_rate": {"available": True, "words_per_minute": 130.0}}
    assert not eh.summarize_deductions([], {}, metrics)["factors"]


def test_clean_recording_has_no_factors():
    detail = [{"word": "메타버스와", "accuracy_score": 98.0, "error_type": "None"}]
    summary = eh.summarize_deductions(detail, {"accuracy": 98})

    assert summary["factors"] == []
    assert summary["primary"] is None


@pytest.mark.parametrize("junk", [None, [], "문자열", 123])
def test_summarize_survives_garbage(junk):
    summary = eh.summarize_deductions(junk, junk, junk if isinstance(junk, dict) else None)
    assert summary["factors"] == []


# ------------------------------------------------------------ 피드백 생성기 연결

def test_inserted_words_are_not_treated_as_bad_pronunciation():
    """⚠️ 회귀 방지. 삽입 단어는 정확도 0으로 오는데, 이걸 '점수 낮은 단어'로 넘기면
    모델이 "'음'을 또박또박 발음하세요"라고 쓴다. 간투어는 발음 문제가 아니다."""
    weak = collect_weak_words(_words())
    assert "음" not in {w["word"] for w in weak}
    # 안 읽은 단어를 발음 지적하는 것도 마찬가지로 말이 안 된다.
    assert "인프라" not in {w["word"] for w in weak}
    # 실제로 흐리게 읽은 단어는 남아 있어야 한다.
    assert "구축의" in {w["word"] for w in weak}


def test_deduction_lines_reach_the_prompt():
    summary = eh.summarize_deductions(_words())
    block = _deduction_lines(summary)

    assert "대본 누락" in block
    assert "대본에 없는 말" in block
    assert "인프라" in block  # 지적을 구체적으로 쓰라고 예시 단어도 넘긴다


def test_deduction_lines_handle_a_clean_recording():
    """요인이 없을 때 빈 문자열을 넣으면 프롬프트에 빈 칸이 생겨 모델이 지어낸다."""
    assert "관찰되지 않았습니다" in _deduction_lines({"factors": []})
    assert "관찰되지 않았습니다" in _deduction_lines(None)


# ------------------------------------------------------------ 엔드포인트 연결
#
# 위 테스트들은 순수 함수만 본다. 함수가 맞게 계산해도 응답에 안 실리면 화면은 여전히 비어
# 있으므로, 실제 API가 무엇을 돌려주는지 여기서 따로 고정한다.

import io

from fastapi.testclient import TestClient

import main
from main import app
from db import models

client = TestClient(app)

API_SCRIPT = "안녕하세요 여러분 반갑습니다 오늘은"
API_RECOGNIZED = "안녕하세요 음 반갑습니다"
API_WORDS = [
    {"word": "안녕하세요", "accuracy_score": 95.0, "error_type": "None"},
    {"word": "여러분", "accuracy_score": 0.0, "error_type": "Omission"},
    {"word": "음", "accuracy_score": 0.0, "error_type": "Insertion"},
    {"word": "반갑습니다", "accuracy_score": 45.0, "error_type": "Mispronunciation"},
    {"word": "오늘은", "accuracy_score": 0.0, "error_type": "Omission"},
]


def _evaluate(monkeypatch, db_session_factory):
    db = db_session_factory()
    try:
        project = models.Project(name="하이라이팅 테스트", filename=None, topic=None, keywords=[])
        project.slides = [models.Slide(slide_number=1, source_content="원문", script=API_SCRIPT)]
        db.add(project)
        db.commit()
        db.refresh(project)
        project_id = project.id
    finally:
        db.close()

    def _fake_convert(input_path, output_path):
        with open(output_path, "wb") as handle:
            handle.write(b"wav")
        return True

    monkeypatch.setattr(main.audio_converter, "convert_to_wav", _fake_convert)
    monkeypatch.setattr(
        main.azure_evaluator, "evaluate_audio",
        lambda audio_file_path, reference_text: {
            "status": "success",
            "overall_scores": {"accuracy": 70.0, "fluency": 75.0,
                               "completeness": 40.0, "pronunciation_score": 62.0},
            "words_detail": [dict(w) for w in API_WORDS],
            "recognized_text": API_RECOGNIZED,
        },
    )
    response = client.post(
        "/api/evaluation/audio",
        data={"project_id": str(project_id)},
        files={"audio_file": ("rec.webm", io.BytesIO(b"fake"), "audio/webm")},
    )
    return project_id, response


def test_audio_response_carries_highlights(monkeypatch, db_session_factory):
    """결과 화면이 응답 하나로 빨간 줄을 그릴 수 있어야 한다."""
    _, response = _evaluate(monkeypatch, db_session_factory)
    assert response.status_code == 200
    highlights = response.json()["highlights"]

    assert highlights["counts"]["error"] == 3   # 누락 2 + 삽입 1
    assert highlights["counts"]["mispronunciation"] == 1

    reference_text = response.json()["reference_text"]
    for item in highlights["reference"]:
        assert reference_text[item["start"]:item["end"]] == item["word"]


def test_audio_response_carries_deductions(monkeypatch, db_session_factory):
    """상세 피드백(HCX)을 부르기 전에도 "왜 깎였는지"를 보여줄 수 있어야 한다."""
    _, response = _evaluate(monkeypatch, db_session_factory)
    deductions = response.json()["deductions"]

    keys = {f["key"] for f in deductions["factors"]}
    assert {"omission", "insertion", "mispronunciation"} <= keys
    # 완성도가 왜 40점인지 화면이 바로 이을 수 있도록 점수도 함께 온다.
    assert deductions["scores"]["completeness"] == 40.0
    assert deductions["primary"] == "omission"  # 대본 절반을 안 읽었으니 이게 제일 크다


def test_project_detail_carries_highlights(monkeypatch, db_session_factory):
    """지난 평가를 다시 열어도 같은 자리가 빨개져야 한다."""
    project_id, _ = _evaluate(monkeypatch, db_session_factory)

    evaluation = client.get(f"/api/projects/{project_id}").json()["data"]["evaluations"][0]

    assert evaluation["highlights"]["counts"]["error"] == 3
    reference_text = evaluation["reference_text"]
    for item in evaluation["highlights"]["reference"]:
        assert reference_text[item["start"]:item["end"]] == item["word"]


def test_evaluation_list_carries_counts_only(monkeypatch, db_session_factory):
    """목록엔 뱃지용 개수만. 강조 위치까지 실으면 코칭 내역이 무거워진다."""
    _evaluate(monkeypatch, db_session_factory)

    listed = client.get("/api/evaluations").json()["data"][0]

    assert listed["highlight_counts"]["error"] == 3
    assert "highlights" not in listed


def test_feedback_receives_the_deductions(monkeypatch, db_session_factory):
    """⚠️ 이게 이 기능의 핵심. 감점 요인이 HCX 프롬프트까지 도달하는지.

    안 도달하면 완성도 40점짜리 녹음에도 "발음이 조금 부정확했습니다"만 나온다.
    """
    _, response = _evaluate(monkeypatch, db_session_factory)
    evaluation_id = response.json()["evaluation_id"]

    captured = {}

    def fake_generate(overall_scores, weak_words, script_excerpt="", strong_words=None,
                      deductions=None):
        captured["deductions"] = deductions
        captured["weak_words"] = weak_words
        return {"summary": "요약", "strengths": [], "improvements": ["끝까지 읽어보세요."],
                "practice_tips": []}

    monkeypatch.setattr(main.feedback_generator, "generate_feedback", fake_generate)
    body = client.post(f"/api/evaluation/{evaluation_id}/feedback").json()

    assert captured["deductions"]["counts"]["omission"] == 2
    assert captured["deductions"]["primary"] == "omission"
    # 간투어 '음'을 '발음이 나쁜 단어'로 넘기면 모델이 발음 교정을 지시한다.
    assert "음" not in {w["word"] for w in captured["weak_words"]}
    # 화면이 감점 요인 카드를 그리도록 응답에도 실려야 한다.
    assert body["data"]["deductions"]["primary"] == "omission"


def test_cached_feedback_gets_deductions_backfilled(monkeypatch, db_session_factory):
    """감점 요인을 넣기 전에 만들어진 피드백도 화면이 비면 안 된다(HCX 재호출 없이)."""
    _, response = _evaluate(monkeypatch, db_session_factory)
    evaluation_id = response.json()["evaluation_id"]

    db = db_session_factory()
    try:
        evaluation = db.get(models.PronunciationEvaluation, evaluation_id)
        evaluation.feedback = {"summary": "옛날 피드백", "strengths": [],
                               "improvements": [], "practice_tips": []}
        db.commit()
    finally:
        db.close()

    def _explode(*args, **kwargs):
        raise AssertionError("캐시가 있는데 HCX를 다시 불렀습니다")

    monkeypatch.setattr(main.feedback_generator, "generate_feedback", _explode)
    body = client.post(f"/api/evaluation/{evaluation_id}/feedback").json()

    assert body["cached"] is True
    assert body["data"]["deductions"]["counts"]["omission"] == 2


def test_stale_span_is_dropped_when_the_text_no_longer_matches():
    """대본이 수정되면 저장된 오프셋이 밀린다. 그대로 칠하면 멀쩡한 글자가 빨개진다.

    ⚠️ 이걸 잡으려면 build_highlights에 **텍스트를 함께 넘겨야** 한다. 안 넘기면 검증할
    방법이 없어서 저장된 span을 그대로 믿는다.
    """
    detail = [{"word": "인프라", "accuracy_score": 0.0, "error_type": "Omission"}]
    eh.attach_spans(detail, REFERENCE, RECOGNIZED)
    assert detail[0]["reference_span"], "전제 조건: 원래 대본에서는 위치를 찾았어야 한다"

    edited = "완전히 다른 대본으로 바뀌었습니다 그리고 더 길어졌습니다"

    assert eh.build_highlights(detail, edited, RECOGNIZED)["reference"] == []
    # 위치는 못 그려도 "누락이 1건 있었다"는 사실은 남는다.
    assert eh.build_highlights(detail, edited, RECOGNIZED)["counts"]["omission"] == 1


def test_word_without_a_name_is_not_highlighted():
    """이름 없는 빨간 줄은 화면에 그릴 수도, 왜 빨간지 설명할 수도 없다."""
    detail = [{"word": None, "accuracy_score": 10.0, "error_type": "Mispronunciation",
               "reference_span": [0, 3], "recognized_span": None}]

    result = eh.build_highlights(detail)

    assert result["reference"] == []
    assert result["counts"]["mispronunciation"] == 0
