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
| 연속 인식 + miscue 정렬이 pause가 여러 번 있으면 살짝 흐트러짐 | 낮음~중간 | (아래 "고친 항목" 참고 — `recognize_once_async()` 문제는 연속 인식으로 해결했으나) pause가 여러 번 있는 긴 녹음에서는 각 pause로 나뉜 구간이 전체 reference_text에 대해 각자 독립적으로 정렬되는 것으로 보임. 27슬라이드 reference로 3분 24초 녹음을 테스트했을 때 391개 단어가 인식되긴 했지만(=연속 인식 자체는 성공), 뒷부분 단어 순서가 원문 순서와 어긋나는 현상이 관찰됨(예: "절차를 단계 이후 발전 각 해줍니다 통한" 처럼 원래 문장 순서와 다르게 나옴). 한 호흡에 이어 읽는 녹음(pause 적음)에는 문제 없음. 여러 번 크게 쉬는 긴 녹음을 완벽하게 정렬하려면, 세그먼트별로 "아직 안 읽은 나머지 reference"만 순차적으로 넘겨주는 더 정교한 구조가 필요함. |
| CLOVA OCR 키 미발급으로 이미지 전용 슬라이드 3건 대본화 대기 중 | 중간 | `ppt_extractor.py` + `ocr/clova_ocr_client.py`로 OCR 연동 코드는 완료했지만, `CLOVA_OCR_SECRET_KEY`/`CLOVA_OCR_INVOKE_URL`이 아직 미발급이라 실제로는 fallback(빈 문자열)만 반환 중. `02분반 1조 ㅎㅎㅎㅎ`, `UMC PM-DAY_진순`, `동아해커톤` 3개 프로젝트가 이 상태로 대본 생성을 못하고 있음. 키 발급되면 `_batch_generate_and_refine.py`로 이 3건만 재시도하면 됨. |

## 이번 라운드에서 고친 항목 (참고)

아래는 이미 해결되어 더 이상 부채가 아닙니다. 자세한 내용은 [completed/0001-initial-harness-and-reliability-fixes.md](completed/0001-initial-harness-and-reliability-fixes.md) 참고.

- PPT 추출 엔드포인트 미연결 → 해결
- 임시파일 레이스 컨디션 → 해결
- `azure` 패키지명 네임스페이스 충돌 위험 → 해결
- 의존성 명세 부재(`requirements.txt`) → 해결
- 실수로 커밋된 mock mp3 아티팩트 → 해결
- 대본 생성 API가 실패해도 200 반환 → 해결 (`/api/script/*`만; `/api/evaluation/audio`는 위 표에 남아있음)
- Azure 발음 평가가 `recognize_once_async()` 때문에 긴 녹음(여러 슬라이드 낭독)에서 처음 pause 이후를 아예 안 듣던 문제 → 연속 인식(`start_continuous_recognition`) + `enable_miscue=True`로 교체해 해결. 이제 사용자가 어디까지 읽었는지 미리 알려주지 않아도, 전체 대본(예: 27슬라이드 전체)을 reference로 줘도 실제 말한 부분만 알아서 채점함. 다만 pause가 여러 번 있을 때의 단어 순서 정렬은 위 표에 남은 잔여 이슈 참고.
- 생성된 대본의 화자 시점이 부자연스러움(관찰자 시점 "~설명합니다") → `ScriptRefiner`(`full_generation/generator.py`) 추가로 해결. 초안을 2차 HCX 호출로 다시 리뷰시켜 발표자 1인칭 구어체("~설명드리겠습니다")로 다듬음. 실제 3건(ClipRoute, 글챌 ppt, 에시설_02분반_4조_PromeAI)에서 자연스럽게 나온 것 확인.
- PPT 내 이미지/도형 안의 텍스트는 추출 안 됨 → CLOVA OCR 연동으로 해결(코드 레벨). `ppt_extractor.py`가 텍스트박스 없는 PICTURE 도형을 만나면 `ocr/clova_ocr_client.py`로 이미지를 보내 텍스트를 뽑아옴. 다만 `CLOVA_OCR_SECRET_KEY`/`CLOVA_OCR_INVOKE_URL`이 아직 미발급이라 실사용은 안 됨 — 위 표의 새 항목 참고.
