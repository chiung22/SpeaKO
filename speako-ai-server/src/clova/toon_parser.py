import re


def parse_toon_slides(toon_text: str) -> list:
    """
    "slides[N]{slide_number,script}:" 형태의 TOON 응답에서 (slide_number, script) 쌍을 추출한다.
    모델이 프롬프트의 헤더+행 구조를 정확히 지키지 않고 `slides[N]{...}`를
    슬라이드마다 반복하는 등 변형된 형태로 응답하는 경우가 있어,
    엄격한 헤더 파싱 대신 "숫자,텍스트" 패턴 자체를 관대하게 찾아내는 방식으로 복구한다.
    """
    cleaned = re.sub(r"slides\[\d+\]\{", "", toon_text)
    cleaned = cleaned.replace("}", "\n")

    pattern = re.compile(r"(\d+)\s*,\s*(.+?)(?=\n\s*\d+\s*,|\Z)", re.DOTALL)
    return [
        {"slide_number": num.strip(), "script": re.sub(r"\s+", " ", script).strip()}
        for num, script in pattern.findall(cleaned)
        if script.strip()
    ]
