# Tech Debt Tracker

의도적으로 지금 고치지 않고 남겨둔 문제들입니다. 새 이슈를 발견하면 여기에 먼저 추가하고, 관련 작업을 시작할 때 [active/](active/)로 계획을 옮기세요.

| 항목 | 영향 | 상세 |
|---|---|---|
| **발음기호에 장음 기호(ː)가 없음** | 중간 | 피그마 `Coach View Page-4`(단어 목록)는 `구성 › [구ː성]`처럼 장음 위치를 보여주는데, g2pkk 결과엔 ː가 없어 우리는 `[구성]`을 준다. **장단음으로 분류해놓고 어디를 길게 읽는지 안 알려주면 그 카테고리 자체가 무의미하다.** `stdict_client.has_long_vowel()`이 이미 사전 발음을 조회하므로, 여부(bool) 대신 **위치까지** 받아 phoneme에 합성해야 한다. (2026-08-05 피그마 실측에서 발견) |
| **단어별 설명 문구가 없음** | 중간 | 피그마 단어 목록은 카테고리 고정 문구가 아니라 **구체적 음운 현상 이름 + 설명**을 보여준다(`특정` → "경음화: 받침 뒤에 오는 예사소리(ㄱ/ㄷ/ㅂ/ㅅ/ㅈ)가 된소리로 바뀌어 발음됩니다"). 지금 `/api/analysis/words`는 `word`/`phoneme`/`category`만 준다. 규칙 판정기(비음화·경음화·유음화·구개음화…)를 만들거나 HCX로 생성해야 함. **피그마의 연음 예시 설명문은 앞뒤가 안 맞는 더미 텍스트이므로 문구가 아니라 형식만 요구사항으로 볼 것.** PM에게 서버 생성 여부 확인 필요. (2026-08-05) |
| **발음 평가 오답의 텍스트 내 위치(offset) 없음** | 중간 | 피그마 `Feedback Page`는 틀린 부분을 **원본·인식 양쪽에** `#FF7676`으로 강조한다. `words_detail`에 단어별 `error_type`(Omission/Insertion/Mispronunciation)은 있지만 위치가 없어, **같은 단어가 여러 번 나오면 프론트가 어디를 칠할지 정할 수 없다.** Omission은 원본에만·Insertion은 인식에만 존재한다는 것도 구분 필요. 수정: 원본/인식 각각의 문자 오프셋을 응답에 포함. (2026-08-05) |
| 사용자 계정/소유권 기반 인가 없음 | 중간 | X-API-Key로 "정당한 호출인지"는 걸러지지만(아래 고친 항목 참고), "누가 호출했는지"는 구분 못함. 지금은 유효한 키만 있으면 아무나 `project_id`를 바꿔가며 남의 프로젝트를 조회/수정 가능. 사용자 계정 시스템이 생겨야 근본 해결. [SECURITY.md](../../SECURITY.md) |
| TTS 엔드포인트 미연결 | 중간 | `ClovaVoiceClient`가 API 라우터에 없음. `run_pipeline_test.py`/`_batch_generate_and_refine.py`에서만 호출됨. **실제 키(`CLOVA_VOICE_CLIENT_ID`/`SECRET`) 없이는 라우터 연결해도 fallback만 나가서 실질적으로 의미가 없음 — 키 발급 전까지는 보류.** [pronunciation-coaching.md](../product-specs/pronunciation-coaching.md) |
| DB 마이그레이션 도구 없음 | 낮음(완화됨) | `Base.metadata.create_all()`은 없는 테이블만 만들고 기존 테이블에 컬럼을 못 붙인다. **완화(2026-08-04)**: `db/database.py`의 `_add_missing_columns()`가 `_EXPECTED_COLUMNS`와 실제 스키마를 비교해 빠진 컬럼만 `ALTER TABLE ADD COLUMN` 해준다(현재 `pronunciation_evaluations`의 `feedback`/`reference_text`/`recognized_text`/`slide_number`). 컬럼 **추가**만 커버하고 타입 변경·삭제·백필은 못 하므로, 스키마 변경이 잦아지면 Alembic 도입 검토. [db-schema.md](../generated/db-schema.md) |
| `slides.script`에 버전 이력 없음 | 낮음 | 전체 생성/부분 재생성 둘 다 같은 컬럼을 덮어써서, 재생성 전 대본으로 되돌릴 방법이 없음. 필요해지면 별도 이력 테이블 검토. |
| 구조화 로깅 없음 | 중간 | 전부 `print()`. 요청 추적 ID 없음. 운영 중 디버깅 어려움. [RELIABILITY.md](../../RELIABILITY.md) |
| ~~핸들러가 `async def`인데 블로킹 I/O를 직접 호출~~ | — | **해결(2026-08-04)**. 아래 해결 목록 참고. |
| ~~업로드 크기 제한이 multipart 파싱 이후에만 적용됨~~ | — | **해결(2026-08-04)**. 아래 해결 목록 참고. |
| ~~레이트 리밋 없음~~ | — | **해결(2026-08-04)**. 아래 해결 목록 참고. |
| ~~슬라이드 개수 상한 없음~~ | — | **해결(2026-08-04)**. 아래 해결 목록 참고. |
| 레이트 리밋/작업 상태가 단일 프로세스 전제 | 낮음(현재), 중간(워커 늘리면) | `job_store`는 DB로 옮겼지만(2026-08-04) **레이트 리밋 카운터는 여전히 프로세스 메모리**다. `--workers 2` 이상으로 띄우면 워커별로 각자 세어서 실효 상한이 워커 수만큼 늘어난다. 또 프론트가 스프링을 거쳐 호출하므로 스프링이 `X-Forwarded-For`를 넘겨주지 않으면 IP 기준 제한이 **전역 상한**처럼 동작한다(그래서 기본값을 넉넉히 잡음). 수정: 워커를 늘리게 되면 Redis 등 공용 저장소로. `utils/rate_limit.py` 주석 참고. |
| `(project_id, slide_number)` 유니크 제약 없음 | 낮음~중간 | `Slide`에 유니크 제약이 없어, 동시/재시도 `/api/script/full` 호출이 같은 슬라이드 번호를 각각 새로 insert하면 중복 행이 생길 수 있음. `_compiled_script_text`가 둘 다 이어붙여 대본이 꼬임. 단일 사용자 개발 단계에선 발생 확률 낮아 보류. 수정: 모델에 `UniqueConstraint` 추가(+ dev DB 재생성). (Fable5 검토) |
| TOON 파서가 줄 첫머리 "숫자," 를 슬라이드 구분자로 오인 가능 | 낮음 | `toon_parser.py`의 lookahead가 "줄바꿈 + 숫자 + 쉼표"를 새 레코드로 봄. 대본 줄이 "1,000명이 참석했습니다"처럼 줄 첫머리에 천단위 숫자로 시작하면 거기서 잘림. 시스템 프롬프트로 쉼표 자제를 유도하지만 강제는 아님. (Fable5 검토) |
| 대본 생성 잘림(`maxTokens`) 감지 없음 | 낮음~중간 | `maxTokens=2000`에 걸려 마지막 슬라이드가 잘려도 잘림 사유를 확인하지 않고 `success: True`로 저장됨. 수정: API의 finish/stop reason 확인. (생성 슬라이드 수를 원본과 비교하는 쪽은 2026-07-23에 구현됨 — 아래 "슬라이드 유실" 항목 참고) |
| **슬라이드가 많으면 `/api/script/full` 한 요청이 오래 걸림** | 중간(배포 시) | 정렬 보장을 위해 슬라이드 한 장씩 생성한다. **1단계 완화(2026-07-23)**: 슬라이드별 호출이 독립적이라 동시 실행으로 병렬화(`ThreadPoolExecutor`, 동시 상한 `HCX_MAX_CONCURRENCY` 기본 4) + `run_in_threadpool` 오프로드. **실측: AHP 19장 순차 ≈ 80~95초 → 병렬 24.7초(≈3.5배).** 그래도 30장+면 수십 초라 느린 네트워크·프록시 idle 타임아웃엔 여전히 취약. **2단계 완료(2026-08-04)**: 백그라운드 작업으로 전환. `POST /api/script/full`이 202 + `job_id`를 즉시 반환하고 `GET /api/script/jobs/{job_id}`로 폴링한다(`utils/job_store.py`, `ThreadPoolExecutor`). 프록시 idle 타임아웃 문제는 이걸로 해소됨. 다만 **작업 상태가 프로세스 메모리에 있어서 워커를 2개 이상 띄우면 깨진다**(아래 별도 행 참고). "12/30" 진행률은 아직 미제공(상태는 processing/completed/failed 3종). |
| ~~작업 상태(job_store)가 프로세스 메모리에 있음~~ | — | **해결(2026-08-04)**. 아래 해결 목록 참고. |
| 로컬 헬퍼 스크립트(`src/_*.py`)와 실제 API의 이중 파이프라인 | 낮음 | `run_pipeline_test.py`/`_batch_generate_and_refine.py` 등은 `script_storage.py`로 `projects/<name>/scripts/`에 파일로 저장하는 옛 구조를 씀. 실제 API는 DB에 저장. `script_storage.py`는 `main.py`가 안 씀(고아). 로컬 디버깅 전용임을 명시하거나 정리 필요. (Fable5 검토) |
| 카테고리 분류 정확도 한계 | 낮음~중간 | 장단음은 표준국어대사전 검색 첫 결과만 대표로 씀 — 동음이의어 의미 중의성(문맥상 어떤 뜻인지)은 해소 안 함. 연음은 "받침+무초성 음절" 구조만 보는 휴리스틱이라, 실제로는 구개음화 등 다른 음운 현상인 경우도 연음으로 분류될 수 있음(예: "굳이"→"구지"는 구개음화지만 구조상 연음 패턴과 같아 연음으로 분류됨). `utils/stdict_client.py`, `utils/hangul_phonology.py` 참고. |
| ETRI_API_KEY 미발급 | 낮음(완화됨) | 문의 답변 대기 중이나, **Kiwi(kiwipiepy) 로컬 형태소 분석기로 대체**해서 키 없이도 실사용 품질로 동작함(2026-07-22). 단어 추출 체인이 ETRI(키 있을 때) → Kiwi(현재 주력) → 빈도 휴리스틱(방어) 순이라, 나중에 ETRI 키가 발급되면 그냥 키만 넣으면 ETRI가 우선한다. Kiwi가 ETRI와 완전히 동일한 정확도를 보장하진 않지만(태그셋/학습데이터 상이), 여기서 필요한 "명사/고유명사/외국어 2글자+ 추출"은 관대한 과제라 실질 차이가 작고, 오히려 조사 제거·단일글자 처리는 기존 빈도 폴백보다 나음. `nlp/kiwi_analyzer.py` |
| CLOVA_VOICE 키 미발급 | 낮음 | TTS가 API 라우터에 아직 연결 안 돼 있어서(위 항목) 지금 당장 급하지 않음 |
| Azure Speech / Clova Voice / CLOVA OCR 단가 미확인 | 낮음 | HCX는 실제 단가 반영됨(`usage_tracker.py`). 나머지 세 서비스는 콘솔에서 단가 확인 전까지 `Token.md`에 비용이 TBD로만 표시됨 |
| G2P fallback 사전이 소규모 | 낮음 | 10 → 31단어로 확장했으나(비음화/유음화/격음화/구개음화/경음화 대표 사례), 여전히 수작업 사전이라 커버리지는 제한적. `g2p_client.py`의 `fallback_dict` |
| PPT 주제/키워드 추출이 휴리스틱 | 낮음 | 목차 슬라이드 없을 때 빈도 기반 폴백을 추가해 품질을 개선했지만, 본질적으로 정교한 NLP가 아니라 휴리스틱인 건 여전함. `ppt_extractor.py` |
| 연속 인식 + miscue 정렬이 pause가 여러 번 있으면 살짝 흐트러짐 | 낮음~중간 | (아래 "고친 항목" 참고 — `recognize_once_async()` 문제는 연속 인식으로 해결했으나) pause가 여러 번 있는 긴 녹음에서는 각 pause로 나뉜 구간이 전체 reference_text에 대해 각자 독립적으로 정렬되는 것으로 보임. 27슬라이드 reference로 3분 24초 녹음을 테스트했을 때 391개 단어가 인식되긴 했지만(=연속 인식 자체는 성공), 뒷부분 단어 순서가 원문 순서와 어긋나는 현상이 관찰됨(예: "절차를 단계 이후 발전 각 해줍니다 통한" 처럼 원래 문장 순서와 다르게 나옴). 한 호흡에 이어 읽는 녹음(pause 적음)에는 문제 없음. 여러 번 크게 쉬는 긴 녹음을 완벽하게 정렬하려면, 세그먼트별로 "아직 안 읽은 나머지 reference"만 순차적으로 넘겨주는 더 정교한 구조가 필요함. |

## 이번 라운드에서 고친 항목 (참고)

아래는 이미 해결되어 더 이상 부채가 아닙니다. 자세한 내용은 [completed/0001-initial-harness-and-reliability-fixes.md](completed/0001-initial-harness-and-reliability-fixes.md) 참고.

- 업로드 크기 제한이 multipart 파싱 이후에만 적용됨 → 해결(2026-08-04). `utils/body_limit.py`의 `MaxBodySizeMiddleware`가 라우팅·파싱 전에 끊는다. `Content-Length`가 상한(기본 25MB, `MAX_REQUEST_BODY_MB`)을 넘으면 **본문을 한 바이트도 받기 전에** 413. 헤더가 없거나 거짓일 수 있으므로 실제 흘러온 바이트도 세다가 넘으면 연결을 끊는다. 실서버에 26MB를 실제로 보내 413 확인.
- 레이트 리밋 없음 → 해결(2026-08-04). `utils/rate_limit.py`. 유료 API를 태우는 POST(`/api/projects`·`/api/script/*`·`/api/analysis/*`·`/api/evaluation/*`)는 분당 60건(`RATE_LIMIT_EXPENSIVE_PER_MINUTE`), 나머지는 300건(`RATE_LIMIT_PER_MINUTE`). **폴링(`GET /api/script/jobs/{id}`)과 CORS preflight는 유료 등급에서 제외** — 프론트가 1~2초마다 폴링하므로 여기 걸리면 정상 흐름이 깨진다. 429에 `Retry-After` 포함. slowapi를 쓰지 않은 이유는 모듈 주석 참고(기본 저장소가 똑같이 인메모리라 단일 워커에선 차이가 없음). 실서버에서 60건 통과 → 429 확인.
- 슬라이드 개수 상한 없음 → 해결(2026-08-04). `MAX_SLIDES_PER_PROJECT`(기본 100) 초과 시 413.
- 작업 상태(job_store)가 프로세스 메모리에 있음 → 해결(2026-08-04). `script_jobs` 테이블(`db/models.ScriptJob`)로 이전. dict → DB로 바꾸면서 워커 수 제약이 사라졌다. 다만 **작업을 돌리는 스레드풀은 여전히 프로세스 안**이라, 재시작하면 그때 `processing`이던 작업은 아무도 이어받지 않는다 → 부팅 시 `fail_stale_jobs()`가 30분 이상 묵은 `processing`을 실패로 정리한다(안 그러면 프론트가 영원히 폴링한다).
- 핸들러가 `async def`인데 블로킹 I/O를 직접 호출 → 해결(2026-08-04). 남아 있던 동기 호출을 전부 `run_in_threadpool`로 넘겼다: `/api/analysis/words`(형태소 분석 CPU + ETRI·표준국어대사전 HTTP → `_analyze_difficult_words`로 묶어서 오프로드), `/api/evaluation/audio`(ffmpeg `subprocess.run` + 업로드 저장), `/api/projects`(PPTX/PDF/DOCX 추출 — **PPTX는 이미지 장표에서 HCX 비전을 유료 호출**하므로 네트워크 왕복이 여럿, + 업로드 저장). Azure 평가와 `/api/script/*`는 이전 라운드에 이미 처리됨.
  - `tests/test_blocking_offload.py` 9건으로 고정. 기능 테스트는 오프로드를 되돌려도 그대로 통과하므로(응답이 같음), 블로킹 함수 안에서 `asyncio.get_running_loop()`가 **실패해야** 정상이라는 방식으로 "어느 스레드에서 돌았는가"를 직접 본다. 오프로드를 지우면 실제로 깨지는 것까지 확인함.
  - 핸들러가 `def`로 바뀌면 FastAPI가 통째로 스레드풀에 넣어 이 검증이 항상 통과하게 되므로, 대상 핸들러가 `async def`로 남아 있는지도 같이 고정한다.
- 입력 길이 상한 없음 → 해결(2026-08-04). `main.py`에 `MAX_*_LEN` 상수를 두고 Pydantic `Field(max_length=/ge=/le=)`와 `Form(max_length=)`로 강제. 커버: `script_text`·`topic`·`outline`·`extra_requirement`·`audience`·`project_name`·슬라이드 `script`/`source_content` 길이, `presentation_time` 범위(1~180분), `project_id`/`target_slide`/`position` 양수. **파일 업로드 우회도 같이 막음** — 코칭용 파일에서 추출한 텍스트가 상한을 넘으면 413(자르지 않고 거절). `tests/test_input_limits.py` 11건으로 고정.
- PPT 추출 엔드포인트 미연결 → 해결
- 임시파일 레이스 컨디션 → 해결
- `azure` 패키지명 네임스페이스 충돌 위험 → 해결
- 의존성 명세 부재(`requirements.txt`) → 해결
- 실수로 커밋된 mock mp3 아티팩트 → 해결
- 대본 생성 API 및 `/api/evaluation/audio`가 실패해도 200 반환 → 전부 해결. 모든 엔드포인트가 실패 시 502/422/413/415로 정직하게 응답
- 외부 API 호출에 재시도/타임아웃 정책 없음 → `requests.post` 전부에 30초 timeout 추가 (HCX/ETRI/Clova Voice)
- 업로드 파일 크기/타입 제한 없음 → PPT 20MB(.pptx만), 오디오 10MB(.wav만) 제한 추가, 초과 시 413/415
- HCX 모델명 하드코딩 → `HCX_MODEL_NAME` 환경변수로 뺌 (미설정 시 기존값 `HCX-005` 유지)
- Azure 발음 평가가 `recognize_once_async()` 때문에 긴 녹음(여러 슬라이드 낭독)에서 처음 pause 이후를 아예 안 듣던 문제 → 연속 인식(`start_continuous_recognition`) + `enable_miscue=True`로 교체해 해결. 이제 사용자가 어디까지 읽었는지 미리 알려주지 않아도, 전체 대본(예: 27슬라이드 전체)을 reference로 줘도 실제 말한 부분만 알아서 채점함. 다만 pause가 여러 번 있을 때의 단어 순서 정렬은 위 표에 남은 잔여 이슈 참고.
- 생성된 대본의 화자 시점이 부자연스러움(관찰자 시점 "~설명합니다") → `ScriptRefiner`(`full_generation/generator.py`) 추가로 해결. 초안을 2차 HCX 호출로 다시 리뷰시켜 발표자 1인칭 구어체("~설명드리겠습니다")로 다듬음. 실제 3건(ClipRoute, 글챌 ppt, 에시설_02분반_4조_PromeAI)에서 자연스럽게 나온 것 확인.
- PPT 내 이미지/도형 안의 텍스트는 추출 안 됨 → 해결. 처음엔 CLOVA OCR(별도 키 필요)을 검토했지만, 이미 쓰는 `HCX-005`가 비전 모델이라는 걸 확인하고 새 키 없이 HCX로 이미지를 직접 읽게 함(`clova/vision/image_text_extractor.py`). 아이콘/구분선 같은 장식 이미지는 크기(150x100px 미만)·가로세로비(5:1 초과) 기준으로 걸러내고 내용 있을 법한 이미지만 보냄. 정확도 보강용 topic/outline 힌트 연동은 위 표의 잔여 항목 참고.
- 영속성 계층 없음 + 실제 API에 프로젝트/세션 개념 없음 → 해결. SQLite + SQLAlchemy(`speako-ai-server/src/db/`) 도입. `/api/ppt/extract`가 이제 `projects`/`slides`를 DB에 만들고 `project_id`를 반환하며, `/api/script/full`·`/api/script/partial`·`/api/analysis/words`·`/api/evaluation/audio`가 전부 이 `project_id`로 이어짐(대본은 슬라이드에 저장, 발음 평가는 프로젝트별 히스토리로 누적). `GET /api/projects`, `GET /api/projects/{id}`로 히스토리 조회 가능. 스키마는 [db-schema.md](../generated/db-schema.md) 참고. 부분 재생성 시 클라이언트가 원본 대본 전문을 다시 보낼 필요도 없어짐(DB에서 조회).
- `/api/analysis/words`가 ETRI 키 없을 때 실제 대본과 무관하게 고정된 4개 단어(`메타버스`,`인프라`,`특징`,`구축`)만 반환하던 버그 → 위 DB 작업 하는 김에 같이 해결. 이 프로젝트의 실제 대본에서 빈도 기반으로 후보를 뽑는 로컬 휴리스틱(`utils/text_heuristics.py`, `ppt_extractor.py`의 키워드 추출 로직과 공용화)으로 교체.
- 인증/인가 없음(모든 API 무인증) → 해결. `X-API-Key` 헤더 검증을 `main.py`에 `APIRouter` 의존성(`verify_api_key`)으로 추가, `SPEAKO_API_KEY` 환경변수로 설정. 값이 비어있거나 플레이스홀더면 로컬 개발 편의를 위해 인증을 건너뛰는 fail-open이라, **배포 전에 반드시 실제 값으로 채워야 함**(안 채우면 지금처럼 무인증 그대로 배포됨 — SECURITY.md 체크리스트 참고). `/`(헬스체크)는 인증 제외. 단일 공유키 방식이라 "누구인지" 구분은 못 함 — 위 표의 "사용자 계정/소유권 기반 인가 없음" 항목이 잔여 이슈로 남음.
- 업로드된 파일명을 그대로 서버 경로에 써서 경로 조작(`../`) 가능성이 있던 문제 → 해결. `_safe_temp_path()`로 원본 파일명 대신 확장자만 추출해 새 임의 이름(`temp_{uuid}{ext}`)을 만들도록 교체(`/api/ppt/extract`, `/api/evaluation/audio` 둘 다 적용).
- CI 파이프라인 없음 → 해결. `.github/workflows/tests.yml` 추가 — `main` push/PR마다 `speako-ai-server`에서 `requirements-dev.txt` 설치 후 `pytest tests/ -q` 자동 실행. 외부 API 키가 전혀 없어도(`.env` 없는 CI 환경) 전 클라이언트가 fallback 모드로 초기화되도록 이미 설계되어 있어서 별도 시크릿 설정 없이 24건 전부 통과할 것으로 예상 — 실제 GitHub Actions 첫 실행에서 최종 확인 필요.
- topic/outline 힌트가 실제 입력 필드에 연동 안 됨(Figma dev code 대기) → 해결. Figma 디자인("AI Set Page")을 직접 확보해서 필드명/조건 확인함: 발표 주제(topic)·목차/가이드라인(outline)은 PPT 미업로드 시 필수, 업로드 시엔 이미지 인식 정확도용 선택 힌트. `POST /api/projects`에 `topic`/`outline` 폼 필드로 반영, 없으면 422.
- 프로젝트 생성이 PPT 필수였음(Figma에서 PPT가 선택 사항으로 확인됨) → 해결. `/api/ppt/extract`를 `POST /api/projects`로 교체하고 3가지 입력 방식 지원: ①PPTX/PDF 파일 ②PPT 없이 topic+outline ③이미 완성된 대본을 바로 붙여넣는 `script_text`(생성 단계 스킵). PDF는 `utils/pdf_extractor.py`(pypdf 재사용, 페이지=슬라이드) 신규 추가로 지원.
- 전체 대본 생성 `style`이 자유 텍스트였고 재생성 요구사항을 못 받았음 → 해결. Figma "AI Script Edit Page"에서 전체 재생성도 부분 재생성과 동일하게 격식체/편안한 말투 토글 + "재생성 요구사항(자유 입력)" 박스를 쓰는 걸 확인 → `FullScriptRequest.style`을 `Literal["격식체","편안한 말투"]`로, `extra_requirement`(선택) 추가해서 `FullScriptGenerator`에 반영.
- **버그**: topic/outline만으로(원본 슬라이드 1개) 대본을 생성했더니 모델이 여러 슬라이드로 쪼개 응답했는데, 기존 코드가 "원본에 없는 슬라이드 번호"를 전부 버려서 2번째 슬라이드부터 유실되던 문제 발견/수정. 실제 라이브 호출로 재현 후 확인 — 이제 없는 슬라이드 번호는 새로 만들어서(upsert) 저장함. 회귀 테스트 추가.
- 발음 코칭 대본 업로드가 텍스트 붙여넣기만 지원 → 해결. `python-docx` 의존성 추가하고 `POST /api/projects`에 `mode="coaching"` 추가 — DOCX(`utils/docx_extractor.py`)/TXT/PDF(`pdf_extractor.extract_full_text`, 페이지 구분 없이 전체 텍스트) 파일을 올리면 슬라이드 추출 없이 곧바로 완성된 대본으로 저장되어 생성 단계를 건너뜀. PPTX는 이 모드에서 거부(415)됨 — 슬라이드 덱이 아니라 완성 문서용이라서.
- 오디오 업로드가 WAV만 허용 → 해결. `utils/audio_converter.py`(ffmpeg subprocess) 신규 추가, `ALLOWED_AUDIO_EXTENSIONS`에 `.mp3`/`.m4a` 추가. WAV가 아니면 16kHz mono PCM WAV로 변환한 뒤 그 결과로 Azure 평가. 실제 ffmpeg로 만든 무음 mp3를 업로드해서 변환→Azure 실제 호출까지 라이브로 검증(무음이라 "음성을 인식할 수 없습니다" 502가 정상적으로 뜨는 것까지 확인 — 변환 자체는 성공했다는 뜻). 변환 실패 시 502로 명확히 알림. 서버에 ffmpeg가 설치되어 있어야 동작함(배포 환경에 설치 필요 — 서버 담당자 확인함).
- 장단음 판정용 사전 데이터 없음 → 해결. 국립국어원 표준국어대사전 오픈 API 키 발급받음(`STDICT_API_KEY`).
- 발음 코칭 화면의 카테고리별 하이라이트 미구현(장단음/연음/표기-발음불일치) → 해결. `utils/stdict_client.py`(표준국어대사전 API로 장단음 판정) + `utils/hangul_phonology.py`(한글 자모 분해로 연음 구조 판정) 신규 추가. `DifficultWord`에 `category` 컬럼 추가, `/api/analysis/words`가 이제 철자≠발음인 단어를 장단음→연음→표기-발음불일치 순으로 분류하고 응답에 `{"words": [...], "summary": {"장단음":N,"연음":M,"표기-발음불일치":K}}` 형태로 집계까지 내려줌(기존 `data`가 flat list였던 것에서 breaking change — 아직 실제 프론트 소비자가 없어서 바로 교체함). `GET /api/projects/{id}`의 `difficult_words`에도 `category` 포함. 판정 정확도의 한계는 위 표의 "카테고리 분류 정확도 한계" 참고.

### 2026-07-21 Fable5 다각도 재검토(서브에이전트 3명 병렬)에서 발견·수정한 항목

- **장단음 카테고리가 사실상 죽은 코드였음** → 해결. `_classify_word_category`가 `is_different=True`(철자≠발음)일 때만 `has_long_vowel`를 확인했는데, 장단음(모음 길이)은 한글 철자에 안 드러나서 G2P의 철자≠발음 판정에 거의 안 걸림 → 장단음이 사실상 발동 안 됨. 장단음은 별개 신호이므로 `is_different`와 무관하게 먼저 조회하도록 순서 변경.
- **`/api/analysis/words`의 표준국어대사전 조회가 무제한 fan-out** → 해결. 단어마다 최대 2번의 직렬 HTTP 호출이 드는데 캐시/상한이 없어 대본이 길면 수백 번 호출 가능. `StdictClient`에 프로세스 내 단어→결과 캐시 추가 + 요청당 분석 단어 수 상한(`MAX_DIFFICULT_WORDS=40`, 초과 시 로그) 도입.
- **HCX 계열 클라이언트 4개에 `use_fallback` 가드 없었음** → 해결. `FullScriptGenerator`/`ScriptRefiner`/`PartialScriptGenerator`/`ImageTextExtractor`가 키가 없어도 무조건 네트워크를 때리고(플레이스홀더 키로 `Authorization: Bearer None` 전송) 실패에 의존했음 — 다른 4개 클라이언트의 `use_fallback` 패턴과 불일치이자 core-beliefs #1 위반. 가드 추가로 키 없으면 즉시 안전 모드. 부수 효과로 CI에서 실제 HCX를 때리던 "no api key" 테스트 2개가 오프라인·결정적이 됨.
- **phantom 슬라이드 `source_content=None` 오염** → 해결. topic/outline-only 프로젝트를 재생성하면 upsert로 생긴 슬라이드(`source_content=NULL`)가 `"Slide 2: None"`으로 HCX에 재전송됐음. 신규 슬라이드에 원본 브리프를 복사하고, `ppt_text` 조립 시 `None`을 빈 문자열로 방어.
- **stdict XML을 `response.text`로 파싱** → `response.content`(bytes)로 변경. 한국 정부 API가 charset을 안 붙이면 requests가 ISO-8859-1로 잘못 디코딩해 한글이 깨질 수 있어, ElementTree가 XML 선언 인코딩을 쓰도록 바이트로 넘김.
- **손상된 PDF/DOCX 업로드가 raw 500** → 해결. `pdf_extractor`/`docx_extractor` 호출을 try/except로 감싸 422로 정직하게 알림(PPTX 추출기는 자체 방어가 있었음).
- **`/api/evaluation/audio`가 내부 예외 메시지를 그대로 응답에 노출** → 해결. `str(e)`를 클라이언트에 안 보내고 서버 로그로만, 응답은 일반 메시지.
- **인증 비교가 비상수 시간(`!=`)** → `hmac.compare_digest`로 변경(타이밍 사이드채널 제거).
- **`finally`의 `os.remove`가 Windows에서 이미 raise된 HTTPException을 500으로 덮을 수 있음** → 각 삭제를 try/except로 방어.
- **SQLite 동시성 미튜닝** → `PRAGMA journal_mode=WAL` + `busy_timeout=15000` + `connect_args timeout=15` 추가로 'database is locked' 완화.
- **`_db_smoke_test.py`가 삭제된 `/api/ppt/extract` 호출** → `/api/projects`로 수정.
- **`apikey_발급.txt`가 `.gitignore` 미포함(레포 공개 전환 후)** → `apikey*` 패턴 추가(현재 파일에 실제 키는 없으나 실수 방지용).

> 위에서 **고치지 않고 문서화만 한** 항목(이벤트루프 블로킹, 업로드 본문 크기, 레이트리밋, 유니크 제약, TOON 줄첫머리 숫자, maxTokens 잘림 감지 등)은 이 표 상단에 별도 행으로 추가되어 있음. 대부분 "프론트 붙고 실제 배포하기 전" 처리 대상.

### 2026-08-04 라운드에서 고친 항목

라이브 서버(실제 HCX/Azure 키)로 직접 호출해가며 검증한 라운드. **단위 테스트만으론 안 잡히던 버그가 두 건 나왔다** — 아래 첫 두 항목.

- **부분 재생성이 항상 502로 실패하고 있었음(실사용 기능 정지)** → 해결. 시스템 프롬프트가 TOON 형식을 요구했는데 모델은 `slides[2]{slide_number,script}:` 헤더만 붙이고 본문은 평문으로 썼다. 파서가 빈 결과를 내고 **멀쩡한 대본이 502로 폐기**됐다. 단위 테스트의 모킹 응답은 TOON을 지켰기 때문에 통과 중이었고, 라이브 호출에서만 드러났다. 한 장짜리 요청에 TOON 껍데기는 애초에 필요가 없어서 요구를 제거하고, 라벨/마크다운을 털어내는 `clean_script_text()`를 `toon_parser.py`에 공용으로 뺐다(전체 생성도 같은 함수 사용). 라이브 재현 → 502에서 200으로 확인.
- **G2P가 조용히 폴백 모드로 돌고 있었음** → 해결. `g2pkk`가 의존하는 eunjeon MeCab 사전이 없어서 예외 없이 "철자 그대로" 반환 중이었다(실시간→[실시간], 연음 탐지 0건). 즉 발음 코칭의 하이라이트 기능이 사실상 죽어 있었다. Kiwi(kiwipiepy)로 `pos()` 인터페이스를 흉내내는 shim(`_KiwiMecabShim`)을 만들어 주입. 초기화 시 `g2p("국물") == "궁물"`로 **실제 변환을 돌려서 검증**하게 했는데, 이 과정에서 리눅스에서 터질 잠복 버그도 같이 잡혔다(mecab=None은 생성 시점엔 통과하고 호출할 때마다 실패).
- API 응답에 슬라이드 유실 경고가 없음 → 해결. `generate_full_script`가 `{"slides": [...], "missing_slide_numbers": [...]}`를 반환하고 폴링 응답의 `data`에 그대로 실린다. 프론트가 "3, 7번 슬라이드는 생성에 실패했습니다"를 띄울 수 있음.
- 부분 재생성 시 대본 없는 슬라이드는 근거 부족 → 해결. `main.py`가 `target_slide.source_content`를 `generate_partial_script()`에 넘기고, 생성기가 `[대상 슬라이드 원문 — 이 내용을 근거로 쓰세요]` 블록을 전체 대본 컨텍스트보다 **앞에** 넣는다.
- 발음 평가에 AI 생성 정성 피드백 없음 → 해결. `clova/feedback/generator.py` 신규. `POST /api/evaluation/{evaluation_id}/feedback`이 총평/발음 팁/상세 피드백/연습 제안 4개 섹션을 생성하고 `evaluations.feedback`에 캐시한다(재요청 시 HCX 재호출 안 함). **근거 없는 칭찬을 막는 게 핵심**이었다 — 초기 버전이 점수 데이터에 없는 단어("인공지능", "서비스")를 지어내 칭찬해서, 잘한 단어도 실제 점수(≥90)에서 뽑아 넘기고 "여기 있는 단어에서만 고르라"는 규칙을 프롬프트에 박았다.
- 대본 생성 결과 편집 불가 → 해결. `PUT/POST/DELETE /api/projects/{id}/slides[/{n}]`. 추가·삭제 후 항상 1..N으로 재정렬(`_resequence`), 마지막 한 장 삭제는 422로 차단.
- 슬라이드별 부분 녹음을 평가해도 몇 번 슬라이드였는지 기록에 안 남음 → 해결. `/api/evaluation/audio`에 `slide_number` 폼 필드 추가(주면 그 슬라이드 대본을 reference로 씀), `pronunciation_evaluations`에 `slide_number`/`reference_text`/`recognized_text` 컬럼 추가.
- Figma의 "원문 vs 인식된 발음" 대조 화면을 만들 수 없었음 → 해결. Azure 연속 인식 콜백에서 세그먼트를 모아 `recognized_text`로 반환.
- 대본 중간 슬라이드가 "감사합니다"로 끝나거나 "OOO" 자리표시자가 남음 → 해결. 첫 슬라이드 지시문 수정 + 마지막 장이 아니면 맺음 인사를 정규식으로 제거(`_strip_closing_greeting`). 프롬프트로 부탁만 하지 않고 후처리로 확정.
- 배포 시 프론트에서 CORS로 전부 막혔을 상태 → 해결. `CORS_ALLOW_ORIGINS` 환경변수 + Vercel 프리뷰 도메인용 `allow_origin_regex`. `speakofront.vercel.app` 기본 포함.
- ffmpeg 설치 방법이 문서에만 있고 배포 재현이 안 됨 → 해결. `Dockerfile` 추가(python:3.12-slim + ffmpeg). 워커 1개 전제인 이유도 주석으로 명시.
- Figma export 폴더가 3개로 갈라져 어느 게 최신인지 알 수 없었음 → 해결. `docs/figma/UMC 10th_SpeaKO (1)/` 하나로 통합(겹치면 최신본 우선, 고유 파일 전부 이관).
