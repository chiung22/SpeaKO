import os
try:
    from pptx import Presentation
except ImportError:
    print("⚠️ python-pptx 라이브러리가 설치되지 않았습니다. 터미널에서 'pip install python-pptx'를 실행해주세요.")

class PptExtractor:
    def __init__(self):
        pass

    def extract_structured_data(self, file_path: str) -> dict:
        """
        [업데이트] PPTX 파일 경로를 입력받아 아래와 같이 구조화된 딕셔너리를 반환합니다.
        1. 발표 주제 및 목차/키워드 자동 추출
        2. 슬라이드 번호별 텍스트 완벽 분리
        """
        if not os.path.exists(file_path):
            print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
            return {"metadata": {"topic": "", "keywords": []}, "slides": []}

        try:
            prs = Presentation(file_path)
            slides_data = []
            front_text_for_analysis = []

            for i, slide in enumerate(prs.slides):
                slide_texts = []
                
                # 슬라이드 내의 모든 도형(Shape)에서 텍스트 추출
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_texts.append(shape.text.strip())
                
                slide_content = "\n".join(slide_texts)
                
                # [요구사항 5 반영] 슬라이드별 텍스트가 존재하는 경우에만 객체로 분리하여 추가
                if slide_content.strip():
                    slides_data.append({
                        "slide_number": i + 1,
                        "content": slide_content
                    })
                    
                    # 주제 및 목차 추출을 위해 초반 1~3장 텍스트만 별도 수집
                    if i < 3:
                        front_text_for_analysis.extend(slide_texts)

            # [요구사항 4 반영] 초반 슬라이드 텍스트 기반 주제/목차 키워드 추출
            topic, keywords = self._extract_metadata(front_text_for_analysis)

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

    def _extract_metadata(self, texts: list):
        """초반 슬라이드 텍스트를 분석하여 발표 주제와 목차(키워드)를 휴리스틱하게 추론합니다."""
        if not texts:
            return "주제 미상", []

        # 보통 첫 번째 텍스트 덩어리가 발표 주제(Title)일 확률이 높음
        topic = texts[0].strip()
        keywords = []

        # '목차', 'index', 'agenda' 등의 단어가 포함된 문자열 주변을 키워드로 간주
        for i, text in enumerate(texts):
            lower_text = text.lower()
            if any(keyword in lower_text for keyword in ['목차', 'index', 'contents', '순서', 'agenda']):
                # 목차라는 단어 이후에 나오는 3~5개의 텍스트를 키워드로 수집
                keywords = texts[i+1 : i+6]
                break
        
        # 키워드가 비어있다면, 텍스트 중 길이가 짧은 명사형 텍스트 일부를 임의 추출
        if not keywords and len(texts) > 1:
            keywords = [t for t in texts[1:6] if len(t) < 15]

        return topic, keywords

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