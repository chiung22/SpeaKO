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

## 이번 라운드에서 고친 항목 (참고)

아래는 이미 해결되어 더 이상 부채가 아닙니다. 자세한 내용은 [completed/0001-initial-harness-and-reliability-fixes.md](completed/0001-initial-harness-and-reliability-fixes.md) 참고.

- PPT 추출 엔드포인트 미연결 → 해결
- 임시파일 레이스 컨디션 → 해결
- `azure` 패키지명 네임스페이스 충돌 위험 → 해결
- 의존성 명세 부재(`requirements.txt`) → 해결
- 실수로 커밋된 mock mp3 아티팩트 → 해결
- 대본 생성 API가 실패해도 200 반환 → 해결 (`/api/script/*`만; `/api/evaluation/audio`는 위 표에 남아있음)
