import os
import requests
import csv
from io import StringIO
from dotenv import load_dotenv

load_dotenv()

class FullScriptGenerator:
    def __init__(self):
        self.api_key = os.getenv("HCX_API_KEY")
        self.apigw_key = os.getenv("HCX_APIGW_KEY")
        self.model_name = "HCX-005" 
        self.endpoint = f"https://clovastudio.apigw.ntruss.com/testapp/v1/chat-completions/{self.model_name}"

    def generate_full_script(self, ppt_text, presentation_time, style):
        headers = {
            "X-NCP-CLOVASTUDIO-API-KEY": self.api_key,
            "X-NCP-APIGW-API-KEY": self.apigw_key,
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
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "topP": 0.8,
            "topK": 0,
            "maxTokens": 2000, # TOON 포맷으로 인해 필요 토큰 수가 대폭 줄어듭니다.
            "temperature": 0.5, 
            "repeatPenalty": 5.0
        }

        print("🚀 HyperCLOVA X에 대본 생성을 요청합니다 (TOON 포맷)...")
        
        try:
            response = requests.post(self.endpoint, headers=headers, json=payload)
            response.raise_for_status() 
            
            result = response.json()
            toon_text = result['result']['message']['content']
            
            # TOON 포맷을 파이썬 딕셔너리로 파싱 (선택적 사용)
            parsed_data = self._parse_toon_format(toon_text)
            return parsed_data
            
        except Exception as e:
            print(f"❌ 전체 대본 생성 API 호출 중 에러가 발생했습니다: {e}")
            return None

    def _parse_toon_format(self, toon_text):
        """TOON 텍스트를 읽어 JSON(Dict) 형태로 복원하는 헬퍼 함수"""
        try:
            lines = toon_text.strip().split('\n')
            if not lines:
                return []
            
            # 헤더 파싱 (예: slides[3]{slide_number,script}:)
            header = lines[0]
            keys_str = header.split('{')[1].split('}')[0]
            keys = [k.strip() for k in keys_str.split(',')]
            
            # 데이터 파싱
            data_list = []
            f = StringIO("\n".join(lines[1:]))
            reader = csv.reader(f, skipinitialspace=True)
            for row in reader:
                if len(row) == len(keys):
                    data_list.append(dict(zip(keys, row)))
            
            return {"slides": data_list}
        except Exception as e:
            print(f"⚠️ TOON 포맷 파싱 에러: {e}")
            return {"raw_toon": toon_text}

if __name__ == "__main__":
    ai_client = FullScriptGenerator()
    sample_ppt = "Slide 1: 메타버스 개요. Slide 2: 시장 규모."
    print(ai_client.generate_full_script(sample_ppt, 1, "격식체"))