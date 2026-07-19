import io

import pytest
from fastapi.testclient import TestClient

import main
from main import app
from clova.full_generation import generator as full_gen_module

client = TestClient(app)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_root_returns_ok():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"]


def test_script_full_fails_without_api_key(monkeypatch):
    # 로컬 .env에 실제 키가 있어도 이 테스트는 결정적으로 동작해야 하므로,
    # 키가 없는 상황을 강제로 재현해서 검증한다.
    monkeypatch.setattr(main.full_generator, "api_key", None)
    # API 키가 없으면 HyperCLOVA 호출이 실패해야 하고,
    # 서버는 이를 200이 아닌 502로 정직하게 알려야 한다.
    response = client.post(
        "/api/script/full",
        json={"ppt_text": "테스트 슬라이드", "presentation_time": 1, "style": "격식체"},
    )
    assert response.status_code == 502


def test_script_full_parses_real_world_toon_variant(monkeypatch):
    # HCX-005는 v3 chat-completions 전용이며, 실제 응답은 프롬프트의 헤더+행 구조를
    # 정확히 지키지 않고 slides[N]{...}를 슬라이드마다 반복하기도 한다.
    # 네트워크 호출 없이, 그 변형된 실제 응답 형태를 그대로 파싱할 수 있는지 검증한다.
    raw_toon = (
        "slides[2]{1,메타버스의 개념에 대해 설명하겠습니다.}\n\n"
        "slides[2]{2,이제 시장 규모에 대해 알아보겠습니다.}\n\n"
        "이상 발표를 마치겠습니다. 감사합니다."
    )
    fake_payload = {"result": {"message": {"content": raw_toon}}}
    monkeypatch.setattr(full_gen_module.requests, "post", lambda *a, **k: _FakeResponse(fake_payload))

    response = client.post(
        "/api/script/full",
        json={"ppt_text": "테스트 슬라이드", "presentation_time": 1, "style": "격식체"},
    )
    assert response.status_code == 200
    slides = response.json()["data"]["slides"]
    assert [s["slide_number"] for s in slides] == ["1", "2"]
    assert "메타버스의 개념" in slides[0]["script"]


def test_analysis_words_falls_back_when_etri_unavailable():
    # ETRI 키가 없어도 fallback 단어 리스트로 G2P 변환까지 끝까지 성공해야 한다.
    response = client.post(
        "/api/analysis/words",
        json={"script_text": "메타버스와 인프라 구축의 특징을 살펴봅시다."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) > 0


def test_ppt_extract_rejects_invalid_file():
    fake_file = io.BytesIO(b"not a real pptx file")
    response = client.post(
        "/api/ppt/extract",
        files={"file": ("broken.pptx", fake_file, "application/octet-stream")},
    )
    assert response.status_code == 422


def test_ppt_extract_rejects_wrong_extension():
    fake_file = io.BytesIO(b"not a pptx at all")
    response = client.post(
        "/api/ppt/extract",
        files={"file": ("notes.txt", fake_file, "text/plain")},
    )
    assert response.status_code == 415


def test_ppt_extract_rejects_oversized_file(monkeypatch):
    # 매 요청마다 20MB 페이로드를 만들지 않도록, 제한 값만 낮춰서 검증한다.
    monkeypatch.setattr(main, "MAX_PPT_SIZE_BYTES", 10)
    fake_file = io.BytesIO(b"x" * 100)
    response = client.post(
        "/api/ppt/extract",
        files={"file": ("slides.pptx", fake_file, "application/octet-stream")},
    )
    assert response.status_code == 413


def test_evaluation_audio_rejects_wrong_extension():
    fake_file = io.BytesIO(b"not a wav file")
    response = client.post(
        "/api/evaluation/audio",
        data={"reference_text": "테스트 문장입니다."},
        files={"audio_file": ("clip.mp3", fake_file, "audio/mpeg")},
    )
    assert response.status_code == 415


def test_evaluation_audio_returns_502_on_failure(monkeypatch):
    # 다른 엔드포인트와 동일하게, 평가 실패는 200이 아닌 502로 알려야 한다.
    monkeypatch.setattr(
        main.azure_evaluator,
        "evaluate_audio",
        lambda audio_file_path, reference_text: {"status": "error", "message": "평가 중 오류 발생: 테스트"},
    )

    fake_file = io.BytesIO(b"RIFF....WAVEfmt ")
    response = client.post(
        "/api/evaluation/audio",
        data={"reference_text": "테스트 문장입니다."},
        files={"audio_file": ("clip.wav", fake_file, "audio/wav")},
    )
    assert response.status_code == 502
