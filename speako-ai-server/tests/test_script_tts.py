"""전체 대본 듣기(POST /api/tts/script) 검증.

단어 하나를 읽어주는 /api/tts/word와 달리 대본은 수천 자다. 그래서 두 가지가 추가로 걸린다.

  · Clova Voice는 요청당 글자 수 상한이 있다 → 문장 경계로 잘라 여러 번 부른다
  · 한국어 음운 규칙을 일부만 적용한다 → 발음 주의 단어 자리를 표준 발음으로 바꾼다

둘 다 조용히 깨질 수 있는 종류다. 자르기가 문장 중간을 끊어도 소리는 나오고(어색할 뿐),
발음 치환이 빠져도 오디오는 정상으로 보인다 — 들어봐야 안다. 그래서 여기서 고정한다.
"""
import pytest
from fastapi.testclient import TestClient

import main
from main import app
from tts import script_tts

client = TestClient(app)


def _project(db_session_factory, scripts, difficult_words=()):
    from db import models

    db = db_session_factory()
    try:
        project = models.Project(name="전체 듣기", filename="deck.pptx", topic="주제", keywords=[])
        project.slides = [
            models.Slide(slide_number=i, source_content=f"원문{i}", script=script)
            for i, script in enumerate(scripts, start=1)
        ]
        project.difficult_words = [
            models.DifficultWord(word=word, phoneme=phoneme, category="표기-발음불일치")
            for word, phoneme in difficult_words
        ]
        db.add(project)
        db.commit()
        return project.id
    finally:
        db.close()


@pytest.fixture
def captured_tts(monkeypatch):
    """Clova에 **실제로 넘어간 문자열**을 순서대로 잡아둔다."""
    calls = []

    def _fake_synthesize(text, speaker="ndain", speed=0):
        calls.append({"text": text, "speaker": speaker, "speed": speed})
        return b"\xff\xfb" + text.encode("utf-8")   # 조각마다 다른 바이트라 이어붙임을 검증할 수 있다

    monkeypatch.setattr(main.tts_client, "synthesize_bytes", _fake_synthesize)
    return calls


# ---------------------------------------------------------------- 순수 로직


def test_split_keeps_sentences_whole():
    """문장 중간에서 자르면 이음새에서 말이 끊겨 들린다."""
    text = "첫 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다."
    chunks = script_tts.split_for_tts(text, limit=20)

    assert chunks, "조각이 하나도 안 나왔다"
    for chunk in chunks:
        assert chunk.endswith("."), f"문장 중간에서 잘렸다: {chunk!r}"


def test_split_respects_the_limit():
    text = "가나다라마바사아자차. " * 50
    chunks = script_tts.split_for_tts(text, limit=100)

    assert all(len(c) <= 100 for c in chunks), [len(c) for c in chunks]


def test_split_packs_chunks_instead_of_one_per_sentence():
    """조각 수가 곧 Clova 호출 횟수다. 문장마다 한 번씩 부르면 18장 대본이 수백 번이 된다."""
    text = "짧은 문장. " * 20
    chunks = script_tts.split_for_tts(text, limit=200)

    assert len(chunks) < 20, f"문장을 묶지 않고 {len(chunks)}조각으로 쪼갰다"


def test_split_force_cuts_a_sentence_longer_than_the_limit():
    """마침표가 하나도 없는 대본을 올리는 사용자가 있다. 상한을 넘겨 보내면 Clova가 거부한다."""
    chunks = script_tts.split_for_tts("가" * 500, limit=100)

    assert all(len(c) <= 100 for c in chunks)
    assert "".join(chunks) == "가" * 500, "강제로 자르면서 글자가 사라졌다"


def test_split_drops_empty_chunks():
    """빈 문자열을 Clova에 보내면 400이 난다."""
    assert script_tts.split_for_tts("\n\n   \n") == []
    assert script_tts.split_for_tts("") == []


def test_pronunciation_replaces_only_the_listed_words():
    text = "각자의 책임을 다합시다."
    result = script_tts.apply_pronunciations(text, [("각자", "각짜"), ("책임", "채김")])

    assert result == "각짜의 채김을 다합시다."


def test_pronunciation_does_not_cascade():
    """순차 치환이면 앞서 바꾼 결과 위에 또 치환이 걸린다. 자리를 먼저 확정해야 한다."""
    result = script_tts.apply_pronunciations("책임", [("책임", "채김"), ("김", "낌")])

    assert result == "채김", f"이미 바꾼 결과에 또 치환이 걸렸다: {result!r}"


def test_pronunciation_prefers_the_longer_word():
    """'발표'와 '발표자'가 둘 다 목록에 있으면 긴 쪽이 이겨야 한다."""
    result = script_tts.apply_pronunciations(
        "발표자가 말합니다.", [("발표", "발표"), ("발표자", "발표짜")])

    assert result == "발표짜가 말합니다."


def test_pronunciation_skips_when_spelling_equals_sound():
    """철자=발음이면 바꿀 이유가 없다(장단음 단어가 대개 여기 해당한다)."""
    text = "밤에 만납시다."
    assert script_tts.apply_pronunciations(text, [("밤", "밤")]) == text


# ---------------------------------------------------------------- 엔드포인트


def test_script_tts_returns_mp3_bytes(db_session_factory, captured_tts):
    """응답은 JSON이 아니라 audio/mpeg다 — 스프링이 audio_url을 찾다가 틀렸던 자리다."""
    project_id = _project(db_session_factory, ["안녕하세요. 발표를 시작하겠습니다."])

    res = client.post("/api/tts/script", json={"project_id": project_id})

    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "audio/mpeg"
    assert res.content, "빈 오디오가 나왔다"


def test_script_tts_reads_every_slide(db_session_factory, captured_tts):
    project_id = _project(
        db_session_factory, ["첫 장입니다.", "둘째 장입니다.", "셋째 장입니다."])

    client.post("/api/tts/script", json={"project_id": project_id})

    spoken = " ".join(call["text"] for call in captured_tts)
    for expected in ("첫 장입니다", "둘째 장입니다", "셋째 장입니다"):
        assert expected in spoken, f"{expected!r}를 읽지 않았다"


def test_script_tts_never_says_slide_labels(db_session_factory, captured_tts):
    """발표자는 '슬라이드 일'이라고 말하지 않는다. 평가 기준 텍스트와 같은 이유다."""
    project_id = _project(db_session_factory, ["첫 장입니다.", "둘째 장입니다."])

    client.post("/api/tts/script", json={"project_id": project_id})

    spoken = " ".join(call["text"] for call in captured_tts)
    assert "Slide" not in spoken, f"라벨이 소리로 나갔다: {spoken!r}"


def test_script_tts_applies_stored_pronunciation(db_session_factory, captured_tts):
    """이게 빠지면 발음 교정 서비스가 '각자'를 [각자]로 읽어준다."""
    project_id = _project(
        db_session_factory,
        ["각자의 책임이 중요합니다."],
        difficult_words=[("각자", "[각짜]"), ("책임", "[채김]")],
    )

    client.post("/api/tts/script", json={"project_id": project_id})

    spoken = " ".join(call["text"] for call in captured_tts)
    assert "각짜" in spoken and "채김" in spoken, spoken
    assert "각자" not in spoken and "책임" not in spoken, spoken


def test_script_tts_can_turn_pronunciation_off(db_session_factory, captured_tts):
    project_id = _project(
        db_session_factory, ["각자의 몫입니다."], difficult_words=[("각자", "[각짜]")])

    client.post("/api/tts/script",
                json={"project_id": project_id, "apply_pronunciation": False})

    spoken = " ".join(call["text"] for call in captured_tts)
    assert "각자" in spoken and "각짜" not in spoken, spoken


def test_script_tts_reads_one_slide_when_asked(db_session_factory, captured_tts):
    project_id = _project(
        db_session_factory, ["첫 장입니다.", "둘째 장입니다.", "셋째 장입니다."])

    res = client.post("/api/tts/script",
                      json={"project_id": project_id, "slide_number": 2})

    assert res.status_code == 200, res.text
    spoken = " ".join(call["text"] for call in captured_tts)
    assert "둘째 장입니다" in spoken
    assert "첫 장입니다" not in spoken and "셋째 장입니다" not in spoken


def test_script_tts_concatenates_chunks_in_order(db_session_factory, captured_tts, monkeypatch):
    """조각 순서가 섞이면 대본이 뒤죽박죽으로 읽힌다."""
    monkeypatch.setattr(script_tts, "MAX_CHARS_PER_REQUEST", 20)
    project_id = _project(
        db_session_factory, ["첫 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다."])

    res = client.post("/api/tts/script", json={"project_id": project_id})

    assert len(captured_tts) > 1, "쪼개지지 않았다 — 이어붙임을 검증할 수 없다"
    expected = b"".join(b"\xff\xfb" + c["text"].encode("utf-8") for c in captured_tts)
    assert res.content == expected, "조각이 순서대로 이어붙지 않았다"


def test_script_tts_second_call_is_free(db_session_factory, captured_tts):
    """Clova는 글자 수만큼 과금된다. 같은 대본을 또 들으면 돈이 또 나가면 안 된다."""
    project_id = _project(db_session_factory, ["안녕하세요. 반갑습니다."])

    first = client.post("/api/tts/script", json={"project_id": project_id})
    calls_after_first = len(captured_tts)
    second = client.post("/api/tts/script", json={"project_id": project_id})

    assert first.headers["x-tts-cache"] == "miss"
    assert second.headers["x-tts-cache"] == "hit"
    assert len(captured_tts) == calls_after_first, "캐시가 있는데 또 합성했다"
    assert second.content == first.content


def test_script_tts_reuses_chunks_when_one_sentence_changes(
        db_session_factory, captured_tts, monkeypatch):
    """한 문장만 고쳤는데 전부 다시 합성하면 대본을 편집할 때마다 돈이 나간다."""
    from db import models
    monkeypatch.setattr(script_tts, "MAX_CHARS_PER_REQUEST", 20)

    project_id = _project(
        db_session_factory, ["첫 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다."])
    client.post("/api/tts/script", json={"project_id": project_id})
    calls_after_first = len(captured_tts)

    db = db_session_factory()
    try:
        slide = db.query(models.Slide).filter(models.Slide.project_id == project_id).first()
        slide.script = "첫 문장입니다. 두 번째 문장입니다. 바뀐 문장입니다."
        db.commit()
    finally:
        db.close()

    client.post("/api/tts/script", json={"project_id": project_id})

    new_calls = len(captured_tts) - calls_after_first
    assert 0 < new_calls < calls_after_first, (
        f"바뀐 조각만 다시 합성해야 하는데 {new_calls}조각을 합성했다 "
        f"(처음엔 {calls_after_first}조각)")


def test_script_tts_404_for_unknown_project(db_session_factory, captured_tts):
    res = client.post("/api/tts/script", json={"project_id": 999999})

    assert res.status_code == 404
    assert not captured_tts, "없는 프로젝트인데 합성을 불렀다"


def test_script_tts_404_for_unknown_slide(db_session_factory, captured_tts):
    project_id = _project(db_session_factory, ["첫 장입니다."])

    res = client.post("/api/tts/script",
                      json={"project_id": project_id, "slide_number": 9})

    assert res.status_code == 404
    assert "9번 슬라이드" in res.json()["detail"]


def test_script_tts_422_when_no_script_yet(db_session_factory, captured_tts):
    """업로드만 하고 대본 생성 전에 누르면 여기로 온다. 원인을 알려줘야 한다."""
    project_id = _project(db_session_factory, [None, None])

    res = client.post("/api/tts/script", json={"project_id": project_id})

    assert res.status_code == 422
    assert "대본 생성" in res.json()["detail"]
    assert not captured_tts


def test_script_tts_422_when_script_too_long(db_session_factory, captured_tts, monkeypatch):
    """상한이 없으면 요청 하나가 Clova 과금을 얼마든지 끌어올릴 수 있다."""
    monkeypatch.setattr(main, "MAX_TTS_SCRIPT_LEN", 50)
    project_id = _project(db_session_factory, ["가나다라마바사아자차. " * 20])

    res = client.post("/api/tts/script", json={"project_id": project_id})

    assert res.status_code == 422
    assert "너무 깁니다" in res.json()["detail"]
    assert not captured_tts, "상한을 넘었는데 합성을 불렀다"


def test_script_tts_502_when_synthesis_fails(db_session_factory, monkeypatch):
    monkeypatch.setattr(main.tts_client, "synthesize_bytes", lambda *a, **k: None)
    project_id = _project(db_session_factory, ["안녕하세요."])

    res = client.post("/api/tts/script", json={"project_id": project_id})

    assert res.status_code == 502


def test_script_tts_rejects_speed_out_of_range(db_session_factory, captured_tts):
    project_id = _project(db_session_factory, ["안녕하세요."])

    res = client.post("/api/tts/script", json={"project_id": project_id, "speed": 99})

    assert res.status_code == 422
    assert not captured_tts


def test_script_tts_passes_voice_and_speed_through(db_session_factory, captured_tts):
    project_id = _project(db_session_factory, ["안녕하세요."])

    client.post("/api/tts/script",
                json={"project_id": project_id, "voice": "혜리", "speed": -2})

    assert captured_tts[0]["speed"] == -2
    assert captured_tts[0]["speaker"] != "ndain", "화자 선택이 전달되지 않았다"
