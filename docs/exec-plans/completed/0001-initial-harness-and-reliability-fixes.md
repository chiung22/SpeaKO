# 0001. 초기 문서 하네스 구축 + 신뢰성 결함 수정

**완료: 2026-07-16**

## 배경

`speako-ai-server` 코드만 있고 저장소 차원의 문서/규칙 하네스(AGENTS.md, ARCHITECTURE.md, docs/ 등)가 없는 상태에서 시작. 코드를 전수 검토한 결과 몇 가지 방치하면 안 되는 결함도 함께 발견되어 같이 처리함.

## 한 일

**코드 수정**
- `main.py`에 `/api/ppt/extract` 엔드포인트를 추가해, 만들어져 있었지만 라우터에 연결되지 않았던 `PptExtractor`를 실제로 호출 가능하게 함.
- `/api/script/full`, `/api/script/partial`이 실패 시 200 대신 502를 반환하도록 수정 (기존에는 `{"success": false}`를 200으로 감추고 있었음).
- `/api/evaluation/audio`, 신규 `/api/ppt/extract`의 임시 파일명에 `uuid`를 붙여 동시 요청 시 파일명 충돌(레이스 컨디션) 가능성을 제거.
- `src/azure/` 패키지를 `src/azure_speech/`로 이름 변경 — 설치된 `azure-cognitiveservices-speech` SDK가 쓰는 `azure` 네임스페이스와 로컬 패키지명이 겹치는 것을 방지.
- `run_pipeline_test.py`에 PPT 추출 단계를 추가해, 통합 테스트가 파이프라인의 첫 단계부터 검증하도록 함.
- 실수로 커밋되어 있던 mock TTS 결과물(`test_pronunciation_구축.mp3`, 내용물이 문자 그대로 `mock_mp3_data_for_testing`이었음)을 제거하고, 이후 같은 실수가 반복되지 않도록 `.gitignore`에 `*.mp3`/`*.wav` 추가.
- `requirements.txt`/`requirements-dev.txt` 신설. 기존에 의존성 명세가 전혀 없었고, 실제로 로컬 venv에는 `azure-cognitiveservices-speech`와 `python-multipart`(FastAPI 파일 업로드에 필수)가 누락되어 있었음 — 즉 발음 평가·PPT 업로드 엔드포인트가 실제로는 동작하지 않는 상태였음을 확인.
- `.env.example` 추가.
- `speako-ai-server/tests/`에 pytest 스모크 테스트 4개 추가, 로컬에서 전부 통과 확인.

**문서 하네스**
- 루트: `AGENTS.md`, `ARCHITECTURE.md`, `DESIGN.md`, `FRONTEND.md`, `PLANS.md`, `PRODUCT_SENSE.md`, `QUALITY_SCORE.md`, `RELIABILITY.md`, `SECURITY.md`
- `docs/design-docs/`: `index.md`, `core-beliefs.md`
- `docs/product-specs/`: `index.md`, `script-generation.md`, `pronunciation-coaching.md`
- `docs/generated/db-schema.md`: DB가 아직 없어 제안 스키마 초안만 기록
- `docs/references/`: 기존 `hyperclova_prompt_guide.md`를 `speako-ai-server/`에서 이곳으로 이동 + `index.md`
- `docs/exec-plans/`: `active/`, `completed/`, `tech-debt-tracker.md`

## 의도적으로 하지 않은 것

- **인증/인가 구현**: 프론트엔드가 아직 없는 상태에서 API 키 요구사항을 임의로 추가하면 향후 연동을 막을 수 있어, 구현 대신 `SECURITY.md`에 권고사항만 기록.
- **영속성 계층(DB) 구현**: 스키마 선택(RDB vs 문서형), 호스팅 방식 등은 제품 결정이 필요해 `docs/generated/db-schema.md`에 초안만 남김.
- **전면 구조화 로깅 도입**: 7개 파일의 `print()` 호출을 전부 바꾸는 것은 범위가 크고 지금 당장 기능에 영향이 없어 `tech-debt-tracker.md`에 기록만 함.

## 관련 문서

- [../tech-debt-tracker.md](../tech-debt-tracker.md) — 여기서 다루지 않은 나머지 항목.
