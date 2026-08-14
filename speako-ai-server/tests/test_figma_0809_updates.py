"""피그마 갱신본(2026-08-09) 대조에서 나온 변경 4건의 회귀 테스트.

`docs/figma/SpeaKO_screenshot/` 22장을 실제 구현과 대조해 나온 차이들이다.

1. 점수 표기 — 0~100 **정수**로 내려준다
   (등급 A~F는 2026-08-15에 없앴다. 화면이 `87점/100`을 그리는데 등급 문자가 따로 필요
    없었고, 소수점은 자릿수가 흔들려 레이아웃이 밀렸다.)
2. 프로젝트명 수정 — AI Script Edit Page ⑬ "사용자가 직접 입력하여 수정"
3. .docx 다운로드 — ㉒ "13의 제목명.docx로 저장", ㉙ "하이라이팅_대본.docx로 저장"
4. 대본 생성 4단계 진행 — AI Set Page (Loading)의 4단계 표시
   (+ 구버전 .ppt는 **지원하지 않기로** 결정. 안내 메시지만 정확히 준다)
"""
import io
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

import main
from main import app
from db import models
from utils import job_store

client = TestClient(app)


def _project(db_session_factory, name="발표자료", slides=(("원문1", "첫 번째 대본입니다."),)):
    db = db_session_factory()
    try:
        project = models.Project(name=name, filename=None, topic=None, keywords=[])
        project.slides = [
            models.Slide(slide_number=i + 1, source_content=src, script=script)
            for i, (src, script) in enumerate(slides)
        ]
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id
    finally:
        db.close()


# ---------------------------------------------------------------- 1. 정수 점수

def test_evaluation_response_returns_integer_scores(monkeypatch, db_session_factory):
    """화면이 `87점 / 100`으로 그린다. 소수점이 붙으면 자릿수가 흔들려 레이아웃이 밀린다."""
    project_id = _project(db_session_factory)
    monkeypatch.setattr(main.audio_converter, "convert_to_wav",
                        lambda i, o: (open(o, "wb").write(b"wav") or True))
    monkeypatch.setattr(main.audio_converter, "probe_duration_seconds", lambda p: 60.0)
    monkeypatch.setattr(main.azure_evaluator, "evaluate_audio", lambda path, text: {
        "status": "success",
        "overall_scores": {"accuracy": 93.2, "fluency": 85.5,
                           "completeness": 71.4, "pronunciation_score": 64.6},
        "recognized_text": "안녕하세요",
        "words_detail": [{"word": "안녕하세요", "accuracy_score": 88.7, "error_type": "None"}],
    })

    response = client.post(
        "/api/evaluation/audio",
        data={"project_id": str(project_id)},
        files={"audio_file": ("rec.m4a", io.BytesIO(b"fake"), "audio/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["overall_scores"] == {
        "accuracy": 93, "fluency": 86, "completeness": 71, "pronunciation_score": 65,
    }
    # 한 화면에 "종합 65"와 "안녕하세요 88.7"이 같이 뜨면 어느 쪽이 기준인지 알 수 없다.
    assert body["words_detail"][0]["accuracy_score"] == 89
    for value in body["overall_scores"].values():
        assert isinstance(value, int) and not isinstance(value, bool)


def test_grades_are_gone(monkeypatch, db_session_factory):
    """등급 A~F는 없앴다(2026-08-15). 프론트가 옛 필드를 계속 읽고 있으면 여기서 걸린다."""
    project_id = _project(db_session_factory)
    monkeypatch.setattr(main.audio_converter, "convert_to_wav",
                        lambda i, o: (open(o, "wb").write(b"wav") or True))
    monkeypatch.setattr(main.audio_converter, "probe_duration_seconds", lambda p: 60.0)
    monkeypatch.setattr(main.azure_evaluator, "evaluate_audio", lambda path, text: {
        "status": "success",
        "overall_scores": {"accuracy": 93.2, "fluency": 85.0,
                           "completeness": 71.4, "pronunciation_score": 64.0},
        "recognized_text": "안녕하세요", "words_detail": [],
    })

    response = client.post(
        "/api/evaluation/audio",
        data={"project_id": str(project_id)},
        files={"audio_file": ("rec.m4a", io.BytesIO(b"fake"), "audio/mp4")},
    )

    assert "grades" not in response.json()


def test_history_rounds_scores_saved_before_the_change(db_session_factory):
    """정수로 바꾸기 전에 저장된 행은 소수로 남아 있다. 옛 기록만 87.4로 보이면 안 된다."""
    project_id = _project(db_session_factory)
    db = db_session_factory()
    try:
        db.add(models.PronunciationEvaluation(
            project_id=project_id, accuracy_score=95.4, fluency_score=72.5,
            completeness_score=55.6, pronunciation_score=88.0,
        ))
        db.commit()
    finally:
        db.close()

    row = client.get("/api/evaluations").json()["data"][0]

    assert row["accuracy_score"] == 95
    assert row["fluency_score"] == 72      # .5는 짝수로 반올림된다(파이썬 기본)
    assert row["completeness_score"] == 56
    assert row["pronunciation_score"] == 88
    assert "grades" not in row

    detail = client.get(f"/api/projects/{project_id}").json()["data"]["evaluations"][0]
    assert detail["accuracy_score"] == 95
    assert "grades" not in detail


def test_missing_score_stays_null_not_zero(db_session_factory):
    """평가에 실패해 점수가 없는 것과 0점은 다르다. 0으로 채우면 F를 받은 것처럼 보인다."""
    project_id = _project(db_session_factory)
    db = db_session_factory()
    try:
        db.add(models.PronunciationEvaluation(project_id=project_id))
        db.commit()
    finally:
        db.close()

    row = client.get("/api/evaluations").json()["data"][0]
    assert row["accuracy_score"] is None
    assert row["pronunciation_score"] is None


# ---------------------------------------------------------------- 2. 프로젝트명 수정

def test_project_name_can_be_updated(db_session_factory):
    project_id = _project(db_session_factory, name="파일이름.pptx")

    response = client.put(f"/api/projects/{project_id}", json={"name": "중간발표 최종본"})

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "중간발표 최종본"
    assert client.get(f"/api/projects/{project_id}").json()["data"]["name"] == "중간발표 최종본"


def test_blank_project_name_is_rejected(db_session_factory):
    """공백만 넣으면 이름 없는 프로젝트가 되고, 그게 그대로 docx 파일명이 된다."""
    project_id = _project(db_session_factory)
    assert client.put(f"/api/projects/{project_id}", json={"name": "   "}).status_code == 422


def test_update_missing_project_returns_404():
    assert client.put("/api/projects/999999", json={"name": "없음"}).status_code == 404


# ---------------------------------------------------------------- 3. docx 다운로드

def _is_docx(content: bytes) -> bool:
    """docx는 zip 컨테이너다. 앞 두 바이트가 PK가 아니면 워드가 못 연다."""
    return content[:2] == b"PK"


def test_script_docx_download(db_session_factory):
    project_id = _project(db_session_factory, name="중간발표",
                          slides=(("원문1", "첫 장 대본."), ("원문2", "둘째 장 대본.")))

    response = client.get(f"/api/projects/{project_id}/script.docx")

    assert response.status_code == 200
    assert _is_docx(response.content)
    # 파일명은 프로젝트명이다(피그마 ㉒ "13의 제목명.docx로 저장"). 한글이라 퍼센트 인코딩된다.
    assert "중간발표.docx" in unquote(response.headers["Content-Disposition"])


def test_highlight_docx_download(db_session_factory):
    project_id = _project(db_session_factory, name="중간발표",
                          slides=(("원문", "국물을 신라면과 함께 먹었습니다."),))
    db = db_session_factory()
    try:
        db.add(models.DifficultWord(project_id=project_id, word="국물", phoneme="[궁물]",
                                    category="표기-발음불일치", description="비음화"))
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/projects/{project_id}/highlight.docx")

    assert response.status_code == 200
    assert _is_docx(response.content)
    assert "하이라이팅_중간발표.docx" in unquote(response.headers["Content-Disposition"])


def test_docx_download_without_script_is_rejected(db_session_factory):
    """대본이 없는데 빈 파일을 내려주면 사용자는 다운로드가 된 줄 안다."""
    project_id = _project(db_session_factory, slides=(("원문만 있음", ""),))

    assert client.get(f"/api/projects/{project_id}/script.docx").status_code == 422
    assert client.get(f"/api/projects/{project_id}/highlight.docx").status_code == 422


def test_docx_download_missing_project_returns_404():
    assert client.get("/api/projects/999999/script.docx").status_code == 404
    assert client.get("/api/projects/999999/highlight.docx").status_code == 404


def test_highlighted_docx_colors_match_figma():
    """색상은 피그마 Coach View Page ㉜에 적힌 값 그대로여야 한다.
    화면과 다운로드본의 색이 다르면 같은 단어가 다른 분류처럼 보인다."""
    from utils.docx_builder import CATEGORY_COLORS

    assert str(CATEGORY_COLORS["장단음"]) == "F7358E"
    assert str(CATEGORY_COLORS["연음"]) == "0072F2"
    assert str(CATEGORY_COLORS["표기-발음불일치"]) == "F79322"


def test_highlighted_docx_prefers_longer_word():
    """'발표'와 '발표자'가 둘 다 주의 단어면 긴 쪽이 먼저 걸려야 한다.
    짧은 쪽이 먼저 매칭되면 긴 단어가 쪼개져 색이 반만 칠해진다."""
    from utils import docx_builder

    content = docx_builder.build_highlighted_script_docx(
        "제목", [(1, "발표자가 발표를 합니다.")],
        [{"word": "발표", "phoneme": "[발표]", "category": "장단음"},
         {"word": "발표자", "phoneme": "[발표자]", "category": "연음"}],
    )
    assert _is_docx(content)  # 매칭 루프가 무한루프에 빠지지 않고 끝나는지까지 함께 본다


# ---------------------------------------------------------------- 4. 4단계 진행

def test_job_reports_step(monkeypatch, db_session_factory):
    """피그마 AI Set Page (Loading)이 4단계를 그린다. status만으론 '처리중'밖에 못 그린다."""
    project_id = _project(db_session_factory)
    monkeypatch.setattr(main.full_generator, "generate_full_script",
                        lambda *a, **k: {"slides": [{"slide_number": 1, "script": "생성된 대본"}]})

    accepted = client.post("/api/script/full", json={
        "project_id": project_id, "presentation_time": 5, "style": "격식체",
    })
    assert accepted.status_code == 202

    job = client.get(f"/api/script/jobs/{accepted.json()['job_id']}").json()
    assert job["status"] == "completed"
    assert job["total_steps"] == 4
    assert job["step"] == job_store.DONE_STEP
    assert job["step_label"] == "완료"


def test_job_starts_at_script_writing_step():
    """업로드·추출은 작업이 생기기 전에 끝난다. 그래서 3단계(대본 작성)에서 시작한다."""
    job_id = job_store.create_job()

    job = job_store.get_job(job_id)
    assert job["step"] == 3
    assert job_store.step_label(job["step"]) == "대본 작성"


def test_legacy_job_without_step_still_renders():
    """step 컬럼이 생기기 전에 만들어진 작업이 0단계로 그려지면 안 된다."""
    job_id = job_store.create_job()
    db = job_store.session_factory()
    try:
        db.get(models.ScriptJob, job_id).step = None
        db.commit()
    finally:
        db.close()

    assert job_store.get_job(job_id)["step"] == job_store.INITIAL_STEP


# ---------------------------------------------------------------- 구버전 .ppt

def test_legacy_ppt_is_rejected_with_actionable_message():
    """지원하지 않기로 결정(2026-08-09). 다만 무엇을 하면 되는지는 알려줘야 한다 —
    허용 목록만 보여주면 사용자는 자기 파일이 왜 거절됐는지 모른다."""
    response = client.post(
        "/api/projects",
        files={"file": ("발표.ppt", io.BytesIO(b"legacy ole binary"), "application/vnd.ms-powerpoint")},
    )

    assert response.status_code == 415
    detail = response.json()["detail"]
    assert ".pptx" in detail
    assert "다른 이름으로 저장" in detail
