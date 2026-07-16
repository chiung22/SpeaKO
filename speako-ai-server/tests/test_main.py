import io

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root_returns_ok():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"]


def test_script_full_fails_without_api_key():
    # API 키가 설정되지 않은 테스트 환경에서는 HyperCLOVA 호출이 실패해야 하고,
    # 서버는 이를 200이 아닌 502로 정직하게 알려야 한다.
    response = client.post(
        "/api/script/full",
        json={"ppt_text": "테스트 슬라이드", "presentation_time": 1, "style": "격식체"},
    )
    assert response.status_code == 502


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
