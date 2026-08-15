"""
발음 평가의 기준 텍스트는 **발표자가 실제로 소리 내어 읽는 말**이어야 한다.

왜 따로 테스트하나: 프로젝트 대본은 슬라이드로 쪼개져 저장돼서, 어딘가에서 이어붙여야 한다.
그 이어붙이기가 두 군데에서 쓰이는데 요구사항이 정반대다.

  · 모델에게 줄 때(HCX 프롬프트) → "Slide 1: ..." 라벨이 **있어야** 맥락을 잡는다.
  · Azure에 채점 기준으로 줄 때  → 라벨이 **있으면 안 된다.**

라벨이 섞이면 Azure는 "Slide"와 번호도 읽어야 할 단어로 세고, 발표자는 그걸 말하지 않으므로
전부 누락(Omission)이 된다. 결과는 두 가지로 드러난다.
  1) 완성도 점수가 실제보다 낮게 나온다 (12장이면 없는 오류가 24개 생긴다)
  2) 결과 화면 원본 대본에 **"Slide 1"이 빨갛게 칠해진다** — 하이라이팅 기능이 대놓고 틀려 보인다

한 함수를 두 용도로 쓰다 실제로 겪은 문제라(2026-08-15), 다시 합쳐지지 않게 여기서 고정한다.
"""
import io

from fastapi.testclient import TestClient

import main
from main import app

client = TestClient(app)


def _project_with_slides(db_session_factory, scripts):
    from db import models

    db = db_session_factory()
    try:
        project = models.Project(name="기준 텍스트 테스트", filename="deck.pptx", topic="주제", keywords=[])
        project.slides = [
            models.Slide(slide_number=i, source_content=f"원문{i}", script=script)
            for i, script in enumerate(scripts, start=1)
        ]
        db.add(project)
        db.commit()
        return project.id
    finally:
        db.close()


def _capture_reference_text(monkeypatch, project_id, **form):
    """평가를 한 번 돌리고 Azure에 **실제로 넘어간 기준 텍스트**를 잡아낸다."""
    seen = {}

    def _fake_evaluate(audio_file_path, reference_text):
        seen["reference_text"] = reference_text
        return {
            "status": "success",
            "overall_scores": {"accuracy": 90.0, "fluency": 90.0, "completeness": 90.0,
                               "pronunciation_score": 90.0},
            "words_detail": [],
            "recognized_text": "",
        }

    monkeypatch.setattr(main.azure_evaluator, "evaluate_audio", _fake_evaluate)
    monkeypatch.setattr(main.audio_converter, "convert_to_wav",
                        lambda src, dst: (open(dst, "wb").write(b"wav"), True)[1])

    response = client.post(
        "/api/evaluation/audio",
        data={"project_id": str(project_id), **form},
        files={"audio_file": ("rec.webm", io.BytesIO(b"fake"), "audio/webm")},
    )
    assert response.status_code == 200, response.text
    return seen["reference_text"]


def test_full_recording_reference_has_no_slide_labels(monkeypatch, db_session_factory):
    """전체 녹음 채점 기준에 "Slide 1:"이 들어가면 안 된다."""
    project_id = _project_with_slides(
        db_session_factory, ["안녕하세요 반갑습니다.", "오늘 주제를 소개합니다."]
    )
    reference = _capture_reference_text(monkeypatch, project_id)

    assert "Slide" not in reference
    assert "안녕하세요 반갑습니다." in reference
    assert "오늘 주제를 소개합니다." in reference


def test_slide_labels_do_not_sneak_in_as_digits(monkeypatch, db_session_factory):
    """라벨을 지우면서 대본 안의 숫자까지 지우면 안 된다 — 대본의 숫자는 실제로 읽는 말이다."""
    project_id = _project_with_slides(db_session_factory, ["2026년 매출은 3배 늘었습니다."])
    reference = _capture_reference_text(monkeypatch, project_id)

    assert reference == "2026년 매출은 3배 늘었습니다."


def test_partial_recording_uses_only_that_slide(monkeypatch, db_session_factory):
    """슬라이드 하나만 녹음하면 그 대본만 기준이어야 한다(안 그러면 완성도가 바닥으로 나온다)."""
    project_id = _project_with_slides(
        db_session_factory, ["첫 장 내용입니다.", "둘째 장 내용입니다.", "셋째 장 내용입니다."]
    )
    reference = _capture_reference_text(monkeypatch, project_id, slide_number="2")

    assert reference == "둘째 장 내용입니다."
    assert "첫 장" not in reference and "셋째 장" not in reference


def test_explicit_reference_text_wins(monkeypatch, db_session_factory):
    """스프링이 직접 조합해 보낸 대본이 있으면 그것을 그대로 쓴다."""
    project_id = _project_with_slides(db_session_factory, ["저장된 대본입니다."])
    reference = _capture_reference_text(
        monkeypatch, project_id, reference_text="스프링이 보낸 대본입니다."
    )

    assert reference == "스프링이 보낸 대본입니다."


def test_slides_without_script_are_skipped(monkeypatch, db_session_factory):
    """대본이 아직 없는 슬라이드가 빈 줄로 남으면 그것도 채점 기준을 흐린다."""
    project_id = _project_with_slides(db_session_factory, ["첫 장입니다.", None, "셋째 장입니다."])
    reference = _capture_reference_text(monkeypatch, project_id)

    assert reference == "첫 장입니다.\n셋째 장입니다."
    assert "\n\n" not in reference


def test_project_detail_serves_the_joined_full_script(db_session_factory):
    """'대본 확인' 화면이 쓸 전체 대본을 서버가 합쳐서 준다.

    프론트가 각자 합치면 라벨을 붙이거나 순서가 어긋나기 쉽고, 그 텍스트를 평가 기준으로
    되보내면 점수가 망가진다. 합치는 규칙은 한 곳에만 둔다.
    """
    project_id = _project_with_slides(
        db_session_factory, ["첫 장입니다.", "둘째 장입니다.", "셋째 장입니다."]
    )
    data = client.get(f"/api/projects/{project_id}").json()["data"]

    assert data["full_script"] == "첫 장입니다.\n둘째 장입니다.\n셋째 장입니다."
    assert "Slide" not in data["full_script"]
    # 슬라이드별 대본도 그대로 남는다(편집 화면은 장 단위로 그린다).
    assert [s["script"] for s in data["slides"]] == ["첫 장입니다.", "둘째 장입니다.", "셋째 장입니다."]


def test_full_script_is_empty_string_when_no_script_yet(db_session_factory):
    """대본 생성 전에도 키는 있어야 한다 — 없으면 프론트가 undefined를 그린다."""
    project_id = _project_with_slides(db_session_factory, [None, None])
    data = client.get(f"/api/projects/{project_id}").json()["data"]

    assert data["full_script"] == ""


def test_model_prompt_keeps_the_slide_labels(db_session_factory):
    """반대 방향 고정: HCX에 줄 텍스트에는 라벨이 **남아 있어야** 한다.

    발음 평가를 고친다고 라벨을 전역으로 없애면, 모델이 슬라이드 맥락을 잃는다.
    """
    from db import models

    project_id = _project_with_slides(db_session_factory, ["첫 장입니다.", "둘째 장입니다."])
    db = db_session_factory()
    try:
        project = db.get(models.Project, project_id)
        assert main._compiled_script_text(project) == "Slide 1: 첫 장입니다.\nSlide 2: 둘째 장입니다."
        assert main._plain_script_text(project) == "첫 장입니다.\n둘째 장입니다."
    finally:
        db.close()
