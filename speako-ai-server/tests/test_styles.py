"""
발표 어투(스타일) 지시가 프롬프트에 실제로 주입되는지에 대한 회귀 테스트.

배경: 예전엔 프롬프트에 "발표 스타일: 격식체"라는 단어만 넣어서, 모델이 제멋대로
해석해 해요체(~이고요/~해보았고요/~에요)로 흘러내렸다(ClipRoute 대본 실측).
"격식체"가 무슨 어미를 쓰고 무슨 어미를 금지하는지 문장으로 못박아야 한다.
"""

import clova.full_generation.generator as generator_module
from clova.full_generation.generator import FullScriptGenerator
from clova.styles import STYLE_INSTRUCTIONS, style_instruction


def test_formal_style_forbids_casual_endings():
    formal = STYLE_INSTRUCTIONS["격식체"]
    assert "하십시오체" in formal or "습니다" in formal
    for banned in ("이고요", "해요", "답니다"):
        assert banned in formal, f"금지 어미 '{banned}'가 지시에 명시돼야 한다"


def test_unknown_style_falls_back_to_formal():
    assert style_instruction("존재하지-않는-스타일") == STYLE_INSTRUCTIONS["격식체"]


class _FakeResponse:
    def __init__(self, content):
        self._content = content
        self.status_code = 200
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


def _capture_prompts(monkeypatch):
    sent = []

    def fake_post(url, headers=None, json=None, timeout=None):
        sent.append(json["messages"][-1]["content"][0]["text"])
        return _FakeResponse("한 문장 대본입니다.")

    monkeypatch.setattr(generator_module.requests, "post", fake_post)
    return sent


def test_style_instruction_is_injected_into_generation_prompt(monkeypatch):
    generator = FullScriptGenerator()
    generator.api_key = "test-key"
    generator.use_fallback = False

    sent = _capture_prompts(monkeypatch)
    generator.generate_full_script("Slide 1: 첫 내용\nSlide 2: 둘째 내용", 4, "격식체")

    # 단어("격식체")만이 아니라 어미 지시가 프롬프트에 들어가야 한다.
    assert all("하십시오체" in prompt for prompt in sent)
    assert all("말투" in prompt for prompt in sent)
