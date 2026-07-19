# Tech Debt Tracker

의도적으로 지금 고치지 않고 남겨둔 문제들입니다. 새 이슈를 발견하면 여기에 먼저 추가하고, 관련 작업을 시작할 때 [active/](active/)로 계획을 옮기세요.

| 항목 | 영향 | 상세 |
|---|---|---|
| 인증/인가 없음 | 높음 | 모든 API가 무인증. 외부 API(HCX/ETRI/Azure/Clova) 비용 남용 위험. [SECURITY.md](../../SECURITY.md) |
| 영속성 계층 없음 | 높음 | 대본/평가 결과가 저장되지 않음. 히스토리 조회 불가. [docs/generated/db-schema.md](../generated/db-schema.md)에 제안 스키마만 존재 |
| TTS 엔드포인트 미연결 | 중간 | `ClovaVoiceClient`가 API 라우터에 없음. `run_pipeline_test.py`에서만 호출됨. [pronunciation-coaching.md](../product-specs/pronunciation-coaching.md) |
| 구조화 로깅 없음 | 중간 | 전부 `print()`. 요청 추적 ID 없음. 운영 중 디버깅 어려움. [RELIABILITY.md](../../RELIABILITY.md) |
| 재시도/타임아웃 정책 없음 | 중간 | `requests.post(...)` 호출에 timeout이 없음. 외부 API 지연 시 워커가 계속 잡힘. |
| `/api/evaluation/audio`가 실패해도 200 반환 | 중간 | 다른 엔드포인트는 502/422로 실패를 알리는데 이 엔드포인트만 예외. 일관성 없음. |
| G2P fallback 사전이 10단어뿐 | 낮음 | g2pkk 로드 실패 환경(Windows 등)에서 실사용 커버리지가 매우 낮음. `g2p_client.py`의 `fallback_dict` |
| 업로드 파일 크기/타입 제한 없음 | 낮음~중간 | PPT/오디오 업로드 모두 상한 없음. DoS 벡터. [SECURITY.md](../../SECURITY.md) |
| CI 파이프라인 없음 | 낮음 | PR마다 `pytest` 자동 실행이 안 됨. |
| PPT 주제/키워드 추출이 휴리스틱 | 낮음 | "목차/index/agenda" 키워드 탐지 방식이라 목차 슬라이드 없는 PPT에서 품질 저하. `ppt_extractor.py` |
| HCX 모델명 하드코딩 | 낮음 | `model_name = "HCX-005"`가 코드에 고정. 모델 버전 교체 시 두 파일(`full_generation`, `partial_generation`)을 모두 고쳐야 함. 환경변수화 검토. |
| 생성된 대본의 화자 시점이 부자연스러움 | 중간 | 실제 생성 결과를 사용자가 검토해보니 "~설명합니다", "~보여줍니다" 같은 문장이 발표자가 청중에게 말하는 어투가 아니라, 마치 AI가 사용자에게 설명하는 듯한 3인칭 관찰자 시점으로 읽힘. 예: "만약 중복 체크를 하지 않을 경우 발생할 수 있는 상황을 설명합니다" → 발표자가 실제로 할 법한 말은 "~상황을 보여드리겠습니다/보여드리고 있습니다" 쪽에 가까움. `full_generation/generator.py`의 시스템 프롬프트(화자 1인칭·청중 대상 어투 강제)를 손볼 필요 있음. 스타일 파라미터로 어느 정도 조절 가능하지만, 기본 프롬프트 자체의 시점 문제라 스타일과 별개로 남아있음. |
| PPT 내 이미지/도형 안의 텍스트는 추출 안 됨 | 낮음~중간 | `ppt_extractor.py`는 `shape.text`가 있는 도형(텍스트박스 등)만 읽는다. 사용자 PPT처럼 화살표 이미지 안에 단계별 설명이 그림으로 들어있는 경우, 그 안의 텍스트는 통째로 스킵되어 대본에도 반영되지 않음. OCR 등을 붙이지 않는 한 python-pptx 구조상 근본적으로 못 읽는 부분이라, 텍스트를 도형/텍스트박스로 넣어달라고 안내하거나 OCR 도입을 검토해야 함. |
| 연속 인식 + miscue 정렬이 pause가 여러 번 있으면 살짝 흐트러짐 | 낮음~중간 | (아래 "고친 항목" 참고 — `recognize_once_async()` 문제는 연속 인식으로 해결했으나) pause가 여러 번 있는 긴 녹음에서는 각 pause로 나뉜 구간이 전체 reference_text에 대해 각자 독립적으로 정렬되는 것으로 보임. 27슬라이드 reference로 3분 24초 녹음을 테스트했을 때 391개 단어가 인식되긴 했지만(=연속 인식 자체는 성공), 뒷부분 단어 순서가 원문 순서와 어긋나는 현상이 관찰됨(예: "절차를 단계 이후 발전 각 해줍니다 통한" 처럼 원래 문장 순서와 다르게 나옴). 한 호흡에 이어 읽는 녹음(pause 적음)에는 문제 없음. 여러 번 크게 쉬는 긴 녹음을 완벽하게 정렬하려면, 세그먼트별로 "아직 안 읽은 나머지 reference"만 순차적으로 넘겨주는 더 정교한 구조가 필요함. |

## 이번 라운드에서 고친 항목 (참고)

아래는 이미 해결되어 더 이상 부채가 아닙니다. 자세한 내용은 [completed/0001-initial-harness-and-reliability-fixes.md](completed/0001-initial-harness-and-reliability-fixes.md) 참고.

- PPT 추출 엔드포인트 미연결 → 해결
- 임시파일 레이스 컨디션 → 해결
- `azure` 패키지명 네임스페이스 충돌 위험 → 해결
- 의존성 명세 부재(`requirements.txt`) → 해결
- 실수로 커밋된 mock mp3 아티팩트 → 해결
- 대본 생성 API가 실패해도 200 반환 → 해결 (`/api/script/*`만; `/api/evaluation/audio`는 위 표에 남아있음)
- Azure 발음 평가가 `recognize_once_async()` 때문에 긴 녹음(여러 슬라이드 낭독)에서 처음 pause 이후를 아예 안 듣던 문제 → 연속 인식(`start_continuous_recognition`) + `enable_miscue=True`로 교체해 해결. 이제 사용자가 어디까지 읽었는지 미리 알려주지 않아도, 전체 대본(예: 27슬라이드 전체)을 reference로 줘도 실제 말한 부분만 알아서 채점함. 다만 pause가 여러 번 있을 때의 단어 순서 정렬은 위 표에 남은 잔여 이슈 참고.
