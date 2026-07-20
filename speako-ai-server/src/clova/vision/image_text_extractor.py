import os
import base64
import requests
from dotenv import load_dotenv

from utils.usage_tracker import log_hcx_call

load_dotenv()

REQUEST_TIMEOUT_SECONDS = 30


class ImageTextExtractor:
    """
    HCX-005의 비전(이미지 이해) 기능으로 이미지 안의 텍스트를 읽어온다.
    CLOVA OCR과 달리 새 키가 필요 없다 — 이미 대본 생성에 쓰는 HCX_API_KEY를 그대로 재사용한다.
    전용 OCR만큼 글자 단위로 정밀하진 않지만, 발표 슬라이드처럼 크고 또렷한 텍스트에는 충분히 쓸 만하다.
    """

    def __init__(self):
        self.api_key = os.getenv("HCX_API_KEY")
        self.model_name = os.getenv("HCX_MODEL_NAME", "HCX-005")
        self.endpoint = f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{self.model_name}"

    def extract_text_from_image(self, image_bytes: bytes, context_hint: str = "") -> str:
        """
        image_bytes: 슬라이드에서 뽑은 이미지 바이너리 (PNG/JPG/BMP/WEBP, 20MB 이하)
        context_hint: 발표 주제/목차 등, 모델이 애매한 글자를 문맥에 맞게 더 정확히 읽도록 돕는 힌트.
                      비워두면 힌트 없이 그대로 읽는다.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        instruction = (
            "이 이미지 안에 보이는 글자를 전부 그대로 옮겨 적어줘. "
            "이미지에 대한 설명이나 해석, 요약은 하지 말고 실제로 적힌 텍스트만 나열해줘. "
            "글자가 하나도 없으면 빈 문자열로만 답해."
        )
        if context_hint:
            instruction = f"[참고 — 이 이미지가 속한 발표 맥락]\n{context_hint}\n\n{instruction}"

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "dataUri": {"data": base64.b64encode(image_bytes).decode("utf-8")}},
                        {"type": "text", "text": instruction},
                    ],
                }
            ],
            "maxTokens": 500,
            "temperature": 0.1,
            "topP": 0.8,
        }

        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()

            result = response.json()
            text = result["result"]["message"]["content"].strip()

            usage = result.get("result", {}).get("usage", {})
            log_hcx_call(
                "vision_image_text",
                usage.get("promptTokens", 0),
                usage.get("completionTokens", 0),
                usage.get("totalTokens", 0),
            )

            return text

        except Exception as e:
            print(f"❌ HCX 비전 이미지 텍스트 추출 중 에러가 발생했습니다: {e}")
            return ""
