import os
import time
import uuid
import base64
import requests
from dotenv import load_dotenv

from utils.usage_tracker import log_clova_ocr_call

load_dotenv()

REQUEST_TIMEOUT_SECONDS = 30


class ClovaOcrClient:
    def __init__(self):
        # CLOVA OCR General은 CLOVA Studio와 별개 서비스라 인증 방식도 다르다:
        # 도메인별 Secret Key + API Gateway Invoke URL 조합.
        self.secret_key = os.getenv("CLOVA_OCR_SECRET_KEY")
        self.invoke_url = os.getenv("CLOVA_OCR_INVOKE_URL")

        self.use_fallback = (
            not self.secret_key or "여기에_" in self.secret_key
            or not self.invoke_url or "여기에_" in self.invoke_url
        )

        if self.use_fallback:
            print("⚠️ [경고] CLOVA OCR 키/Invoke URL이 설정되지 않았습니다.")
            print("⚠️ 이미지 안 텍스트 추출은 건너뜁니다 (빈 문자열 반환).\n")

    def extract_text_from_image(self, image_bytes: bytes, image_format: str) -> str:
        """
        이미지 바이너리를 CLOVA OCR General API로 보내 인식된 텍스트를 이어붙여 반환한다.
        키가 없으면 빈 문자열을 반환한다 — 호출자(ppt_extractor)는 이 경우 해당 이미지에서
        텍스트를 못 얻은 것으로 취급하고 넘어가면 된다.
        """
        if self.use_fallback:
            return ""

        headers = {
            "Content-Type": "application/json",
            "X-OCR-SECRET": self.secret_key,
        }

        payload = {
            "version": "V1",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "lang": "ko",
            "images": [
                {
                    "format": image_format,
                    "name": "slide_image",
                    "data": base64.b64encode(image_bytes).decode("utf-8"),
                }
            ],
        }

        try:
            response = requests.post(self.invoke_url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()

            result = response.json()
            fields = result.get("images", [{}])[0].get("fields", [])
            text = " ".join(f["inferText"] for f in fields if f.get("inferText"))

            log_clova_ocr_call(len(fields))
            return text

        except Exception as e:
            print(f"❌ CLOVA OCR 호출 중 에러가 발생했습니다: {e}")
            return ""
