import os
import requests
import csv
from io import StringIO
from dotenv import load_dotenv

from utils.usage_tracker import log_hcx_call

load_dotenv()

REQUEST_TIMEOUT_SECONDS = 30

class PartialScriptGenerator:
    def __init__(self):
        self.api_key = os.getenv("HCX_API_KEY")
        self.model_name = os.getenv("HCX_MODEL_NAME", "HCX-005")
        self.endpoint = f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{self.model_name}"

    def generate_partial_script(self, original_script, target_slide, feedback):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # [수정됨] 부분 재생성 역시 TOON 포맷으로 출력 강제
        system_prompt = """
        당신은 프레젠테이션 스피치 라이터입니다.
        사용자의 피드백을 반영하여 특정 슬라이드의 대본만 다시 작성해주세요.
        
        [작성 가이드라인]
        1. 대본(script) 내부에 쉼표(,)는 마침표(.)나 띄어쓰기로 대체하세요.
        2. 출력은 반드시 아래의 [TOON 포맷]을 엄격히 준수하세요.

        [TOON 출력 포맷 예시]
        slides[1]{slide_number,script}:
         3,네 세 번째 슬라이드 시장 분석 부분입니다. 수정된 대본 내용입니다.
        """

        user_prompt = f"""
        [대상 슬라이드 번호]
        Slide {target_slide}

        [기존 대본 내용]
        {original_script}

        [사용자 피드백]
        {feedback}
        """

        payload = {
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
            ],
            "topP": 0.8,
            "topK": 0,
            "maxTokens": 800, # 부분 재생성 & TOON 포맷 최적화
            "temperature": 0.7, # 1. 문장 출력 다양성을 위해 0.7로 상향 조정
            "repeatPenalty": 5.0
        }

        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()

            result = response.json()
            usage = result.get('result', {}).get('usage', {})
            log_hcx_call(
                "partial",
                usage.get('promptTokens', 0),
                usage.get('completionTokens', 0),
                usage.get('totalTokens', 0),
            )

            return result['result']['message']['content']
        except Exception as e:
            return None