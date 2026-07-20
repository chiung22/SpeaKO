import os
import re
from collections import Counter
try:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE
except ImportError:
    print("⚠️ python-pptx 라이브러리가 설치되지 않았습니다. 터미널에서 'pip install python-pptx'를 실행해주세요.")

from ocr.clova_ocr_client import ClovaOcrClient

# 빈도 기반 키워드 추출 시 제외할 일반 어미/접속사류
_STOPWORDS = {
    "그리고", "그러나", "하지만", "그래서", "따라서", "또한", "즉", "먼저", "마지막으로",
    "합니다", "습니다", "있습니다", "됩니다", "그것", "이것", "저것", "이번",
    "오늘", "여러분", "우리", "대한", "위한", "통해", "대해", "에서", "그런",
}

class PptExtractor:
    def __init__(self):
        self.ocr_client = ClovaOcrClient()

    def extract_structured_data(self, file_path: str) -> dict:
        """
        [업데이트] PPTX 파일 경로를 입력받아 아래와 같이 구조화된 딕셔너리를 반환합니다.
        1. 발표 주제 및 목차/키워드 자동 추출
        2. 슬라이드 번호별 텍스트 완벽 분리
        3. 텍스트박스가 아니라 이미지(캡처/스캔)로만 된 슬라이드는 CLOVA OCR로 텍스트 추출 시도
        """
        if not os.path.exists(file_path):
            print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
            return {"metadata": {"topic": "", "keywords": []}, "slides": []}

        try:
            prs = Presentation(file_path)
            slides_data = []
            front_text_for_analysis = []
            all_slide_texts = []

            for i, slide in enumerate(prs.slides):
                slide_texts = []

                # 슬라이드 내의 모든 도형(Shape)에서 텍스트 추출
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_texts.append(shape.text.strip())
                    elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                        # 텍스트박스 없이 이미지로만 들어간 슬라이드 대응 (예: 캡처/스캔해서 넣은 장표)
                        ocr_text = self.ocr_client.extract_text_from_image(shape.image.blob, shape.image.ext)
                        if ocr_text.strip():
                            slide_texts.append(ocr_text.strip())

                slide_content = "\n".join(slide_texts)

                # [요구사항 5 반영] 슬라이드별 텍스트가 존재하는 경우에만 객체로 분리하여 추가
                if slide_content.strip():
                    slides_data.append({
                        "slide_number": i + 1,
                        "content": slide_content
                    })

                    all_slide_texts.extend(slide_texts)

                    # 주제 및 목차 탐지를 위해 초반 1~3장 텍스트는 별도로도 수집
                    if i < 3:
                        front_text_for_analysis.extend(slide_texts)

            # [요구사항 4 반영] 초반 슬라이드 텍스트 기반 주제 추출 + 전체 슬라이드 기반 키워드 추출
            topic, keywords = self._extract_metadata(front_text_for_analysis, all_slide_texts)

            print(f"✅ PPT 구조화 추출 완료! (총 {len(slides_data)}장 분석)")
            return {
                "metadata": {
                    "topic": topic,
                    "keywords": keywords
                },
                "slides": slides_data
            }

        except Exception as e:
            print(f"❌ PPT 추출 중 오류 발생: {e}")
            return {"metadata": {"topic": "", "keywords": []}, "slides": []}

    def _extract_metadata(self, front_texts: list, all_texts: list = None):
        """초반 슬라이드 텍스트로 발표 주제를, 전체 슬라이드 텍스트로 키워드를 휴리스틱하게 추론합니다."""
        if not front_texts:
            return "주제 미상", []

        all_texts = all_texts if all_texts else front_texts

        # 보통 첫 번째 텍스트 덩어리가 발표 주제(Title)일 확률이 높음
        topic = front_texts[0].strip()
        keywords = []

        # '목차', 'index', 'agenda' 등의 단어가 포함된 슬라이드가 있다면 그 직후 텍스트를 키워드로 간주
        for i, text in enumerate(all_texts):
            lower_text = text.lower()
            if any(keyword in lower_text for keyword in ['목차', 'index', 'contents', '순서', 'agenda', '차례', 'outline']):
                keywords = all_texts[i + 1: i + 6]
                break

        # 목차 슬라이드가 없다면, 전체 슬라이드 텍스트에서 자주 등장하는 단어를 키워드로 추론
        if not keywords:
            keywords = self._extract_keywords_by_frequency(all_texts, topic)

        return topic, keywords

    def _extract_keywords_by_frequency(self, texts: list, topic: str, top_n: int = 5) -> list:
        """목차 슬라이드가 없는 PPT를 위한 대체 키워드 추출: 전체 텍스트에서 자주 등장하는 단어를 뽑는다."""
        tokens = []
        for text in texts:
            for token in re.split(r"[\s,.\-·:;()\[\]/\\|!?\"']+", text):
                token = token.strip()
                if len(token) >= 2 and token != topic and token not in _STOPWORDS:
                    tokens.append(token)

        if not tokens:
            return []

        counts = Counter(tokens)
        return [word for word, _ in counts.most_common(top_n)]

# ==========================================
# 🧪 [테스트 코드]
# ==========================================
if __name__ == "__main__":
    extractor = PptExtractor()
    test_file = "sample.pptx" 
    
    if os.path.exists(test_file):
        # 기존 통글 추출 대신 구조화된 데이터 추출 메서드 사용
        result_data = extractor.extract_structured_data(test_file)
        
        import json
        print("\n✨ [추출된 PPT 구조화 데이터] ✨")
        print(json.dumps(result_data, indent=2, ensure_ascii=False))
    else:
        print(f"⚠️ '{test_file}' 파일이 존재하지 않아 추출 테스트를 건너뜁니다.")