import os
import xml.etree.ElementTree as ET
import requests
from dotenv import load_dotenv

from utils.usage_tracker import log_stdict_call

load_dotenv()

REQUEST_TIMEOUT_SECONDS = 10
SEARCH_ENDPOINT = "https://stdict.korean.go.kr/api/search.do"
VIEW_ENDPOINT = "https://stdict.korean.go.kr/api/view.do"
LENGTH_MARK = "ː"  # MODIFIER LETTER TRIANGULAR COLON — 표준국어대사전이 장음 표기에 쓰는 문자
# 사이트가 view.do의 req_type=json을 지원하지 않아(빈 응답) XML로 요청한다. search.do는 json이 정상 동작한다.
_BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0"}


class StdictClient:
    """
    국립국어원 표준국어대사전 오픈 API로 단어의 장단음(모음 길이)을 판정한다.
    동음이의어가 여러 개면 검색 결과의 첫 번째 항목을 대표로 사용한다 — 문맥상 어떤 의미인지
    중의성을 해소하지는 않으므로, "이 단어가 장음으로 읽힐 수 있다"는 참고 신호로만 쓴다.
    """

    def __init__(self):
        self.api_key = os.getenv("STDICT_API_KEY")
        self.use_fallback = not self.api_key or "여기에_" in self.api_key
        if self.use_fallback:
            print("⚠️ [경고] STDICT_API_KEY가 설정되지 않았습니다.")
            print("⚠️ 장단음 판정은 호출자 쪽 안전 모드(Fallback, 항상 False)에 맡깁니다.\n")

    def has_long_vowel(self, word: str) -> bool:
        if self.use_fallback or not word or not word.strip():
            return False

        try:
            target_code = self._find_target_code(word.strip())
            if not target_code:
                return False
            return self._pronunciation_has_length_mark(target_code)
        except Exception as e:
            print(f"❌ 표준국어대사전 API 호출 중 에러가 발생했습니다: {e}")
            return False

    def _find_target_code(self, word: str):
        response = requests.get(
            SEARCH_ENDPOINT,
            params={"key": self.api_key, "q": word, "req_type": "json"},
            headers=_BROWSER_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        log_stdict_call()

        items = response.json().get("channel", {}).get("item") or []
        if isinstance(items, dict):
            items = [items]
        return items[0].get("target_code") if items else None

    def _pronunciation_has_length_mark(self, target_code: str) -> bool:
        response = requests.get(
            VIEW_ENDPOINT,
            params={"key": self.api_key, "q": target_code, "method": "target_code"},
            headers=_BROWSER_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        log_stdict_call()

        root = ET.fromstring(response.text)
        for pronunciation_el in root.findall(".//pronunciation_info/pronunciation"):
            if pronunciation_el.text and LENGTH_MARK in pronunciation_el.text:
                return True
        return False
