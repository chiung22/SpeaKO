"""
이미지로만 된 슬라이드를 읽을 때, **동시에 부르되 순서는 지키는가**에 대한 테스트.

배경(2026-08-16 실측): 글자가 없는 10장짜리 PPT를 업로드했더니 **추출에만 116초**가 걸렸다.
정작 대본 생성은 12초다 — 사용자가 기다리는 시간의 대부분이 이미지를 한 장씩 순서대로
읽는 데 쓰이고 있었다. 이미지들끼리는 서로 의존하지 않으므로 한꺼번에 보내면 된다.

병렬로 바꾸면서 생기는 위험이 정확히 하나다. **순서가 뒤섞이는 것.**
슬라이드 본문은 "텍스트박스 → 큰 이미지 → 작은 이미지" 순으로 이어 붙는데, 완료되는
순서대로 담으면 문장이 뒤죽박죽이 된다. 대본 생성은 이 텍스트를 근거로 삼으므로
조용히 이상한 대본이 나올 뿐 에러는 안 난다 — 그래서 여기서 못 박는다.
"""
import io
import threading
import time

import pytest
from pptx import Presentation
from pptx.util import Inches

from utils.ppt_extractor import PptExtractor


def _png(width, height, color=(120, 140, 200)):
    """python-pptx가 받아줄 최소 PNG 바이트."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    buf.seek(0)
    return buf


def _deck(tmp_path, slides):
    """slides = [(텍스트 or None, [(가로, 세로), ...])] → .pptx 파일 경로."""
    prs = Presentation()
    blank = prs.slide_layouts[6]
    for text, images in slides:
        slide = prs.slides.add_slide(blank)
        if text:
            box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(6), Inches(1))
            box.text_frame.text = text
        for index, (w, h) in enumerate(images):
            slide.shapes.add_picture(
                _png(w, h), Inches(0.5), Inches(1.5 + index * 1.2), Inches(3), Inches(1)
            )
    path = tmp_path / "deck.pptx"
    prs.save(str(path))
    return str(path)


class _Recorder:
    """비전 호출을 가로채, 이미지 크기별로 정해진 문자열을 돌려준다."""

    def __init__(self, delay=0.0, fail_on=None):
        self.delay = delay
        self.fail_on = fail_on
        self.calls = []
        self.concurrent = 0
        self.peak = 0
        self._lock = threading.Lock()

    def extract_text_from_image(self, blob, context_hint, content_type):
        from PIL import Image

        size = Image.open(io.BytesIO(blob)).size
        with self._lock:
            self.calls.append(size)
            self.concurrent += 1
            self.peak = max(self.peak, self.concurrent)
        try:
            if self.delay:
                time.sleep(self.delay)
            if self.fail_on and size == self.fail_on:
                raise RuntimeError("비전 호출 실패")
            return "이미지%dx%d" % size
        finally:
            with self._lock:
                self.concurrent -= 1


def _extract(tmp_path, slides, recorder):
    extractor = PptExtractor()
    extractor.image_text_extractor = recorder
    return extractor.extract_structured_data(_deck(tmp_path, slides))


# ── 순서 ────────────────────────────────────────────────────────────────────

def test_textbox_comes_before_image_text(tmp_path):
    """텍스트박스 내용이 이미지에서 읽은 것보다 앞에 와야 한다."""
    result = _extract(tmp_path, [("제목", [(400, 300)])], _Recorder())
    content = result["slides"][0]["content"]

    assert content.index("제목") < content.index("이미지400x300")


def test_bigger_image_comes_first(tmp_path):
    """넓이 순으로 읽는 규칙은 병렬로 바꿔도 유지돼야 한다(큰 이미지가 본문일 확률이 높다)."""
    slides = [(None, [(200, 200), (600, 500), (300, 300)])]
    result = _extract(tmp_path, slides, _Recorder())
    lines = result["slides"][0]["content"].splitlines()

    assert lines == ["이미지600x500", "이미지300x300", "이미지200x200"]


def test_slides_keep_their_own_text(tmp_path):
    """완료 순서가 뒤섞여도 각 슬라이드는 자기 이미지 결과만 가져야 한다.

    앞 슬라이드가 느리고 뒤 슬라이드가 빠르면 결과가 역순으로 도착한다 —
    그때 내용이 남의 슬라이드로 새면 대본이 통째로 어긋난다.
    """
    slides = [(None, [(500, 400)]), (None, [(450, 400)]), (None, [(400, 400)])]
    result = _extract(tmp_path, slides, _Recorder(delay=0.05))

    assert [s["content"] for s in result["slides"]] == [
        "이미지500x400", "이미지450x400", "이미지400x400",
    ]
    assert [s["slide_number"] for s in result["slides"]] == [1, 2, 3]


# ── 병렬성 ──────────────────────────────────────────────────────────────────

def test_images_are_read_concurrently(tmp_path):
    """실제로 동시에 나가야 한다. 순차로 돌아가면 이 테스트가 실패한다."""
    slides = [(None, [(400 + i, 400)]) for i in range(6)]
    recorder = _Recorder(delay=0.15)

    started = time.time()
    _extract(tmp_path, slides, recorder)
    elapsed = time.time() - started

    assert recorder.peak > 1, "동시에 실행된 호출이 없습니다 — 순차 처리로 되돌아갔습니다"
    # 순차면 6 × 0.15 = 0.9초 이상. 동시 4개면 두 번에 나눠 0.3초대.
    assert elapsed < 0.75, "순차 실행에 가까운 시간이 걸렸습니다 (%.2f초)" % elapsed


def test_all_images_are_read_exactly_once(tmp_path):
    """묶어서 보내다 빠뜨리거나 두 번 보내면 안 된다(유료 호출이다)."""
    slides = [(None, [(500, 400), (450, 400)]), ("글자만 있는 장", []), (None, [(600, 400)])]
    recorder = _Recorder()
    _extract(tmp_path, slides, recorder)

    assert sorted(recorder.calls) == [(450, 400), (500, 400), (600, 400)]


# ── 안전장치 ────────────────────────────────────────────────────────────────

def test_one_failed_image_does_not_break_the_upload(tmp_path):
    """이미지 한 장이 실패해도 나머지는 살아야 한다. 업로드 전체가 죽으면 안 된다."""
    slides = [(None, [(600, 400)]), (None, [(500, 400)])]
    result = _extract(tmp_path, slides, _Recorder(fail_on=(600, 400)))

    # 실패한 장은 내용이 없어 목록에서 빠지고, 나머지는 정상이어야 한다.
    contents = {s["slide_number"]: s["content"] for s in result["slides"]}
    assert contents.get(2) == "이미지500x400"
    assert 1 not in contents


def test_text_heavy_slides_skip_vision_entirely(tmp_path):
    """글자가 충분한 슬라이드는 이미지를 읽지 않는다 — 유료 호출을 아끼는 규칙이다."""
    long_text = "이 슬라이드에는 충분히 긴 설명이 이미 텍스트로 들어 있습니다. " * 2
    recorder = _Recorder()
    result = _extract(tmp_path, [(long_text, [(600, 400)])], recorder)

    assert recorder.calls == []
    assert "이미지" not in result["slides"][0]["content"]


def test_deck_without_images_needs_no_vision(tmp_path):
    """이미지가 없으면 스레드풀을 아예 열지 않는다."""
    recorder = _Recorder()
    result = _extract(tmp_path, [("첫 장입니다.", []), ("둘째 장입니다.", [])], recorder)

    assert recorder.calls == []
    assert [s["content"] for s in result["slides"]] == ["첫 장입니다.", "둘째 장입니다."]
