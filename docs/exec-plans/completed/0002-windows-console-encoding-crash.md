# 0002. Windows 콘솔 인코딩으로 인한 서버 부팅 실패 수정

**완료: 2026-07-16**

## 배경

"API 키만 연결하면 바로 작동하는가?"를 검증하기 위해 `python src/main.py`로 실제 서버를 띄워봤더니, 부팅 도중 `UnicodeEncodeError: 'cp949' codec can't encode character '⏳'`로 죽는 것을 확인함.

## 원인

한국어 Windows의 기본 콘솔 코드페이지(cp949)는 이모지(⏳, ⚠️, 🚀 등)를 인코딩하지 못합니다. `g2p_client.py`, `azure_client.py` 등 여러 모듈이 초기화 시점에 이모지가 섞인 `print()`를 호출하는데, `main.py`가 이 모듈들을 임포트/인스턴스화하는 순간 바로 크래시가 났습니다. `pytest`로는 이 문제가 드러나지 않았는데, pytest의 출력 캡처가 콘솔 코드페이지와 무관하게 UTF-8을 쓰기 때문입니다 — 즉 테스트 통과와 실제 실행 가능 여부가 별개였습니다.

## 수정

`main.py`와 `run_pipeline_test.py` 최상단에서, 콘솔 인코딩이 UTF-8이 아니면 `sys.stdout`/`sys.stderr`를 UTF-8로 재설정하도록 추가.

## 검증

- `PYTHONIOENCODING` 환경변수 없이 `python src/main.py` 실행 → 정상 기동 확인
- `GET /`, `GET /docs` 200 확인
- `POST /api/analysis/words` 실제 호출 → ETRI/G2P fallback 정상 동작 확인 (`특징` → `[특찡]`)
- `pytest tests/` 4개 재통과 확인

## 남은 주의사항

`etri_client.py`, `g2p_client.py`, `azure_speech/azure_client.py`, `tts/clova_voice_client.py`, `utils/ppt_extractor.py`의 `if __name__ == "__main__":` 테스트 블록을 **개별 스크립트로 직접 실행**하면(`main.py`를 거치지 않으므로) 여전히 같은 인코딩 문제가 재현될 수 있습니다. 이 파일들을 단독 실행해서 디버깅할 때는 `PYTHONIOENCODING=utf-8 python 파일명.py`로 실행하세요.
