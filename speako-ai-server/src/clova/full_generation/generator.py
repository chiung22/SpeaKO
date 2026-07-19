import os
import re
import requests
from dotenv import load_dotenv

from utils.usage_tracker import log_hcx_call

load_dotenv()

REQUEST_TIMEOUT_SECONDS = 30

class FullScriptGenerator:
    def __init__(self):
        self.api_key = os.getenv("HCX_API_KEY")
        self.model_name = os.getenv("HCX_MODEL_NAME", "HCX-005")
        self.endpoint = f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{self.model_name}"

    def generate_full_script(self, ppt_text, presentation_time, style):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # [수정됨] JSON 대신 토큰 최적화된 TOON 포맷을 강제하는 시스템 프롬프트
        system_prompt = """
        당신은 대한민국 최고의 '프레젠테이션 스피치 라이터'입니다.
        사용자가 제공하는 [PPT 텍스트]와 [발표 조건]을 바탕으로 자연스러운 전체 발표 대본을 작성해주세요.

        [작성 가이드라인]
        1. 각 슬라이드의 핵심 메시지를 파악하여 구어체로 작성하세요.
        2. 대본 내용(script) 안에는 쉼표(,) 대신 마침표(.)나 띄어쓰기를 사용하세요. (파싱 오류 방지)
        3. 출력은 반드시 토큰 최적화된 아래의 [TOON 포맷]을 엄격히 준수하며, 다른 텍스트는 덧붙이지 마세요.

        [TOON 출력 포맷 예시]
        slides[슬라이드총개수]{slide_number,script}:
         1,안녕하세요 오늘 발표를 맡은 진행자입니다. 첫 번째 슬라이드입니다.
         2,다음으로 넘어가겠습니다. 시장 규모를 살펴보면...
        """

        user_prompt = f"""
        [발표 조건]
        - 발표 시간: {presentation_time}분
        - 발표 스타일: {style}

        [PPT 텍스트]
        {ppt_text}
        """

        payload = {
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
            ],
            "topP": 0.8,
            "topK": 0,
            "maxTokens": 2000, # TOON 포맷으로 인해 필요 토큰 수가 대폭 줄어듭니다.
            "temperature": 0.5,
            "repeatPenalty": 5.0
        }

        print("🚀 HyperCLOVA X에 대본 생성을 요청합니다 (TOON 포맷)...")
        
        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status() 
            
            result = response.json()
            toon_text = result['result']['message']['content']

            usage = result.get('result', {}).get('usage', {})
            log_hcx_call(
                "full",
                usage.get('promptTokens', 0),
                usage.get('completionTokens', 0),
                usage.get('totalTokens', 0),
            )

            # TOON 포맷을 파이썬 딕셔너리로 파싱 (선택적 사용)
            parsed_data = self._parse_toon_format(toon_text)
            return parsed_data
            
        except Exception as e:
            print(f"❌ 전체 대본 생성 API 호출 중 에러가 발생했습니다: {e}")
            return None

    def _parse_toon_format(self, toon_text):
        """
        TOON 텍스트에서 (slide_number, script) 쌍을 추출합니다.
        모델이 매번 프롬프트의 헤더+행 구조를 정확히 지키지 않고
        `slides[N]{...}`를 슬라이드마다 반복하는 등 변형된 형태로 응답하는 경우가 있어,
        엄격한 헤더 파싱 대신 "숫자,텍스트" 패턴 자체를 관대하게 찾아내는 방식으로 복구한다.
        """
        try:
            # slides[N]{ 같은 래퍼/헤더 조각과 닫는 중괄호를 제거해 "숫자,텍스트" 패턴만 남긴다.
            cleaned = re.sub(r"slides\[\d+\]\{", "", toon_text)
            cleaned = cleaned.replace("}", "\n")

            pattern = re.compile(r"(\d+)\s*,\s*(.+?)(?=\n\s*\d+\s*,|\Z)", re.DOTALL)
            data_list = [
                {"slide_number": num.strip(), "script": re.sub(r"\s+", " ", script).strip()}
                for num, script in pattern.findall(cleaned)
                if script.strip()
            ]

            if not data_list:
                return {"raw_toon": toon_text}

            return {"slides": data_list}
        except Exception as e:
            print(f"⚠️ TOON 포맷 파싱 에러: {e}")
            return {"raw_toon": toon_text}

if __name__ == "__main__":
    ai_client = FullScriptGenerator()
    sample_ppt = "Slide 1: 메타버스 개요. Slide 2: 시장 규모."
    print(ai_client.generate_full_script(sample_ppt, 1, "격식체"))