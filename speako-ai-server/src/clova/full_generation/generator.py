import os
import requests
from dotenv import load_dotenv

from utils.usage_tracker import log_hcx_call
from clova.toon_parser import parse_toon_slides

load_dotenv()

REQUEST_TIMEOUT_SECONDS = 30

def _is_placeholder_key(api_key):
    """HCX_API_KEY가 없거나 .env.example의 플레이스홀더 그대로면 True (안전 모드로 전환)."""
    return not api_key or "여기에_" in api_key


class FullScriptGenerator:
    def __init__(self):
        self.api_key = os.getenv("HCX_API_KEY")
        self.model_name = os.getenv("HCX_MODEL_NAME", "HCX-005")
        self.endpoint = f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{self.model_name}"
        # 키가 없으면 다른 4개 클라이언트(ETRI/Azure/Clova Voice/stdict)와 동일하게
        # 네트워크 호출 없이 곧장 안전 모드로 빠진다. (플레이스홀더 키로 실제 요청을 보내면
        # 무의미한 30초 타임아웃 대기 + 불필요한 외부 호출이 발생한다)
        self.use_fallback = _is_placeholder_key(self.api_key)
        if self.use_fallback:
            print("⚠️ [경고] HCX_API_KEY가 설정되지 않았습니다. 대본 생성은 안전 모드(None 반환)로 동작합니다.")

    def generate_full_script(self, ppt_text, presentation_time, style, extra_requirement=""):
        if self.use_fallback:
            return None
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
        3. [추가 요구사항]이 주어지면 반드시 반영하세요.
        4. 출력은 반드시 토큰 최적화된 아래의 [TOON 포맷]을 엄격히 준수하며, 다른 텍스트는 덧붙이지 마세요.

        [TOON 출력 포맷 예시]
        slides[슬라이드총개수]{slide_number,script}:
         1,안녕하세요 오늘 발표를 맡은 진행자입니다. 첫 번째 슬라이드입니다.
         2,다음으로 넘어가겠습니다. 시장 규모를 살펴보면...
        """

        user_prompt = f"""
        [발표 조건]
        - 발표 시간: {presentation_time}분
        - 발표 스타일: {style}

        [추가 요구사항]
        {extra_requirement or '없음'}

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
        try:
            data_list = parse_toon_slides(toon_text)
            if not data_list:
                return {"raw_toon": toon_text}
            return {"slides": data_list}
        except Exception as e:
            print(f"⚠️ TOON 포맷 파싱 에러: {e}")
            return {"raw_toon": toon_text}

class ScriptRefiner:
    """
    FullScriptGenerator가 만든 초안 대본을 다시 HCX에 넣어
    발표자 1인칭 구어체로 더 자연스럽게 다듬는 2차 리뷰 단계.
    입력/출력 모두 "Slide N: 내용" 형식의 평문 대본이다.
    """

    def __init__(self):
        self.api_key = os.getenv("HCX_API_KEY")
        self.model_name = os.getenv("HCX_MODEL_NAME", "HCX-005")
        self.endpoint = f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{self.model_name}"
        self.use_fallback = _is_placeholder_key(self.api_key)

    def refine_script(self, script_text, style="신뢰감을 주는 발표자 스타일"):
        if self.use_fallback:
            return None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        system_prompt = """
        당신은 발표 대본을 다듬는 전문 감수자입니다.
        입력으로 주어지는 초안 대본은 "Slide N: 내용" 형식의 줄들로 구성되어 있습니다.
        이 대본을 발표자가 청중 앞에서 실제로 말하듯 자연스러운 1인칭 구어체로 다듬어주세요.

        [다듬을 때 기준]
        1. 관찰자 시점("~설명합니다", "~보여줍니다")이 아니라 발표자가 청중에게 직접 말하는 어투("~설명드리겠습니다", "~보여드리겠습니다")로 통일하세요.
        2. 문장이 어색하거나 번역체스러운 부분, 반복되는 표현은 자연스러운 한국어 구어체로 고치세요.
        3. 각 슬라이드의 핵심 내용과 정보, 슬라이드 순서는 그대로 유지하세요. 새로운 정보를 추가하거나 빼지 마세요.
        4. "Slide N:" 라벨과 슬라이드 개수는 절대 바꾸지 마세요. 입력에 있던 슬라이드 번호를 그대로 유지하세요.
        5. 과도하게 길이를 늘리거나 줄이지 말고, 자연스러움 개선에만 집중하세요.

        출력은 반드시 입력과 동일하게 "Slide N: 내용" 형식의 줄들로만 구성하고, 다른 설명이나 안내 문구는 절대 덧붙이지 마세요.
        """

        user_prompt = f"""
        [발표 스타일]
        {style}

        [초안 대본]
        {script_text}
        """

        payload = {
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
            ],
            "topP": 0.8,
            "topK": 0,
            "maxTokens": 2000,
            "temperature": 0.4,
            "repeatPenalty": 3.0,
        }

        print("🚀 HyperCLOVA X에 대본 자연스러움 고도화(리뷰)를 요청합니다...")

        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()

            result = response.json()
            refined_text = result["result"]["message"]["content"]

            usage = result.get("result", {}).get("usage", {})
            log_hcx_call(
                "refine",
                usage.get("promptTokens", 0),
                usage.get("completionTokens", 0),
                usage.get("totalTokens", 0),
            )

            return refined_text.strip()

        except Exception as e:
            print(f"❌ 대본 고도화 API 호출 중 에러가 발생했습니다: {e}")
            return None


if __name__ == "__main__":
    ai_client = FullScriptGenerator()
    sample_ppt = "Slide 1: 메타버스 개요. Slide 2: 시장 규모."
    print(ai_client.generate_full_script(sample_ppt, 1, "격식체"))