"""Claude 비전으로 이미지 글자를 읽는 폴백 OCR.

## 왜 존재하는가 (2026-08-19 실험 — nextStep 백로그 참고)
HCX-005 비전은 큰 일반 폰트("반갑습니다! 진순 입니다:)")조차 못 읽는다 — 확대 2·3배,
프롬프트 4종 전부 실패했다. 같은 이미지를 Claude 비전은 완벽히 읽었다. 그래서 **HCX가
글자를 하나도 못 읽은 이미지에 한해서만** Claude를 부른다. 대본 생성은 그대로 HCX다 —
Claude는 글자 전사만 한다.

## 키가 없으면
ANTHROPIC_API_KEY가 없으면 조용히 꺼진다(빈 문자열 반환) — 다른 클라이언트
(ETRI/Azure/Clova Voice)와 같은 안전 모드 규약이다. 키는 EC2 .env에 직접 넣는다
(채팅·저장소 금지).
"""
import base64
import os

from dotenv import load_dotenv

from utils.usage_tracker import log_claude_ocr_call

load_dotenv()

# OCR은 "적힌 글자를 옮겨 적는" 단순 작업이라 최상위 모델이 필요 없다.
# Haiku가 비전을 지원하고 가장 싸다 (입력 $1/M — 이미지 한 장에 1원 미만).
MODEL = os.getenv("CLAUDE_OCR_MODEL", "claude-haiku-4-5")

_INSTRUCTION = (
    "이 이미지에 적힌 글자를 전부 그대로 옮겨 적어줘. "
    "설명·해석·요약 없이 실제로 적힌 텍스트만. "
    "글자가 하나도 없으면 NO_TEXT 한 단어만 답해."
)


class ClaudeOcrClient:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.use_fallback = not self.api_key or "여기에_" in self.api_key
        self._client = None
        if self.use_fallback:
            print("ℹ️ ANTHROPIC_API_KEY가 없어 Claude OCR 폴백은 꺼져 있습니다 (HCX 비전만 사용).")

    def _get_client(self):
        # anthropic 패키지가 없거나 키가 없어도 서버 기동은 죽지 않아야 하므로 지연 임포트.
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def extract_text_from_image(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """이미지 속 글자를 그대로 돌려준다. 글자가 없거나 실패하면 빈 문자열."""
        if self.use_fallback or not image_bytes:
            return ""

        media_type = mime_type if mime_type in (
            "image/png", "image/jpeg", "image/gif", "image/webp") else "image/png"
        try:
            response = self._get_client().messages.create(
                model=MODEL,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image",
                         "source": {"type": "base64", "media_type": media_type,
                                    "data": base64.b64encode(image_bytes).decode("ascii")}},
                        {"type": "text", "text": _INSTRUCTION},
                    ],
                }],
            )
            text = "".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            ).strip()
            usage = getattr(response, "usage", None)
            log_claude_ocr_call(
                getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0))
            if not text or "NO_TEXT" in text:
                return ""
            return text
        except Exception as e:
            print(f"⚠️ Claude OCR 실패(무시하고 진행): {e}")
            return ""
