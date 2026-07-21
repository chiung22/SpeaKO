# Next Step — 진행 현황

API 키(ETRI/Azure/Clova Voice) 발급 대기 중 진행 가능한 작업들을 정리합니다. "정리하자"라고 말하면 이 시점까지 작업을 PR/머지하고 이 파일을 최신 상태로 정리합니다.

## ✅ 완료 (2026-07-21): 발음 코칭 카테고리별 하이라이트(장단음/연음/표기-발음불일치) 설계+구현

장단음 데이터 소스(표준국어대사전 API)를 확보한 김에, 남아있던 카테고리별 하이라이트 기능을 설계하고 구현함.

- `utils/hangul_phonology.py`(신규) — 한글 완성형 음절을 초성/중성/종성 인덱스로 분해하는 유틸 + "받침 있는 음절 + 초성 없는(ㅇ) 다음 음절" 구조를 검사하는 `has_liaison_pattern()`(연음 판정).
- `utils/stdict_client.py`(신규) — `STDICT_API_KEY`로 표준국어대사전 검색(search.do, JSON) → 대표 표제어의 발음(view.do, XML — JSON은 빈 응답이 와서 XML로 요청) 조회 → 장음 기호(`ː`) 포함 여부로 장단음 판정.
- `DifficultWord`에 `category` 컬럼 추가(로컬 dev DB는 마이그레이션 도구가 없어서 파일 삭제 후 재생성함 — 개인 테스트 데이터라 문제없음).
- `/api/analysis/words`: 철자≠발음인 단어를 **장단음 → 연음 → 표기-발음불일치** 순으로 분류(우선순위 있음 — 장단음 판정이 먼저), 응답을 `{"words": [...], "summary": {"장단음":N,"연음":M,"표기-발음불일치":K}}` 형태로 변경(기존엔 flat list였음 — breaking change지만 실제 프론트 소비자가 없어서 바로 교체). `GET /api/projects/{id}`의 `difficult_words`에도 `category` 포함.
- 실제 라이브 호출로 검증: 대본에 "국민"(→"궁민")이 포함된 프로젝트로 `/api/analysis/words` 호출 → `category: "표기-발음불일치"`로 정확히 분류되어 응답/DB 양쪽에 저장되는 것 확인.
- 테스트: `tests/test_hangul_phonology.py`(신규, 순수 유닛 테스트), `tests/test_stdict_client.py`(신규, HTTP 모킹), `/api/analysis/words` 카테고리 분류 통합 테스트 추가. pytest 35 → **44건**.

**알려둘 한계** (tech-debt-tracker.md에도 기록):
- 장단음은 동음이의어 검색 결과 중 첫 번째만 대표로 씀 — 문맥상 의미 중의성은 해소 안 함.
- 연음은 "받침+무초성" 구조만 보는 휴리스틱이라, 실제로는 구개음화 등 다른 음운 현상(예: "굳이"→"구지")도 구조가 같으면 연음으로 분류될 수 있음.

## ✅ 완료 (2026-07-21): TTS는 키 발급 대기로 보류 기록 + CI 파이프라인 구축

## ✅ 완료 (2026-07-21): 장단음 판정 데이터 소스 확보

사용자가 국립국어원 오픈 API 인증키를 발급받아 옴(표준국어대사전, `stdict.korean.go.kr`). `.env`에 `STDICT_API_KEY`로 저장, `.env.example`에도 플레이스홀더 추가.

실제 호출로 검증: 동음이의어 "눈"의 두 target_code(71074=눈 오는 눈, 409998=보는 눈)를 `https://stdict.korean.go.kr/api/view.do?key=...&q={target_code}&method=target_code`로 조회했더니, `pronunciation` 필드가 각각 `"눈ː"`(장음 표시 있음)와 `"눈"`(없음)으로 정확히 구분됨 — **장단음 판정이 실제로 가능하다는 게 확인됨.** 이전에 "장단음은 데이터 자체가 없어서 근본적으로 막혀있다"고 했던 부분이 풀림.

아직 이 API를 호출해서 실제 단어 목록에 장단음을 매기는 클라이언트 코드는 안 만듦 — 카테고리별 하이라이트(장단음/연음/표기-발음불일치) 기능 전체를 구현할 때 같이 진행 예정. 연음/표기-발음불일치 분류 규칙과 `/api/analysis/words` 응답 포맷 설계는 여전히 남아있음.

## ✅ 완료 (2026-07-21): 보류 항목 중 2개(DOCX 코칭 업로드, MP3/M4A) 추가 처리 + 장단음 API 조사

Figma 기반 작업에서 "설계 필요"로 보류했던 4개 항목 중 사용자가 진행 가능하다고 판단한 것들을 이어서 처리함.

- **DOCX/TXT 코칭 파일 업로드**: `python-docx` 추가, `POST /api/projects`에 `mode="coaching"` 신규 — DOCX(`utils/docx_extractor.py`)/TXT/PDF(`pdf_extractor.extract_full_text`, 신규) 업로드 시 전체 텍스트를 그대로 완성 대본으로 저장(생성 스킵). 실제 docx/txt 파일 만들어서 테스트 통과 확인.
- **오디오 MP3/M4A 지원**: "서버 관리자가 ffmpeg 설치 가능하다고 함" → `utils/audio_converter.py`(ffmpeg subprocess, 신규) 추가, WAV 아니면 16kHz mono WAV로 변환 후 Azure에 넘김. **로컬에 ffmpeg가 실제로 설치되어 있어서(`ffmpeg -version` 확인) 진짜로 무음 mp3를 만들어 ffmpeg 변환 → 실제 Azure 호출까지 라이브로 검증**(무음이라 502 "음성을 인식할 수 없습니다"가 뜬 것 자체가 변환 성공의 증거 — 변환 실패였다면 다른 에러 메시지가 떴을 것).
- **장단음 API 조사**: 사용자가 `kli.korean.go.kr/term`(국립국어원 전문용어 API) 링크를 주고 장단음 판정에 쓸 수 있는지 질문 → WebFetch로 확인. 이 API도, 더 적합해 보이는 `stdict.korean.go.kr/openapi`(표준국어대사전)도 `pronunciation`/`pronunciation_info` 필드는 있지만 문서상 장단음 구분이 명시적으로 안 나와 있음 — **API 키 발급받아 실제 응답을 확인해봐야 확실해짐**. `kli.korean.go.kr/term`은 전문용어 사전이라 일반 발표 어휘엔 안 맞을 수 있어, `stdict.korean.go.kr`쪽이 더 적합해 보임. `tech-debt-tracker.md`/`PLANS.md`에 "실제 키 발급 대기" 항목으로 기록.
- pytest 29 → **35건**, 전체 통과.

**남은 보류 항목**: 카테고리별 하이라이트(장단음 부분은 위 API 키 대기, 연음/표기-발음불일치는 규칙 설계 필요), AI 생성 정성 피드백/팁(새 프롬프트 설계 필요) — 둘 다 설계 결정이 더 필요해서 계속 보류 중.

## ✅ 완료 (2026-07-21): Figma 디자인 확보 + 백엔드 계약을 실제 화면에 맞춤

사용자가 Figma에서 프레임을 전부 Export해서 `docs/figma/`에 넣어줌 — "UMC 10th_SpeaKO" 폴더(랜딩/로그인/회원가입/디자인시스템)와 "UMC 10th_SpeaKO (1)" 폴더(전체 플로우: AI Set Page, AI Script Edit Page, Coach Set/View Page, Feedback Page, Select page 등). 그동안 대기 중이던 "Figma dev code" 문제가 이걸로 해결됨 — 실제 화면을 직접 보고 필드명/플로우를 확인함.

**AI Set Page에서 확인한 것** (그동안 막혀있던 topic/outline 연동의 정답):
- 발표 주제(필수 아닌 조건부 필수) / 발표 시간 / 목차·가이드라인 / 발표 스타일(격식체·편안한 말투) 4개 입력
- 빨간 툴팁: "파일 업로드를 하지 않을 시, 발표 주제와 가이드라인을 필수로 입력하셔야 합니다" → **PPT 업로드가 필수가 아니라 선택**이라는 걸 확인. 지금까지 만든 API는 PPT 파일이 무조건 필요했음.

**AI Script Edit Page에서 확인한 것**: 전체 재생성/부분 재생성 토글이 발표 스타일(격식체/편안한 말투) + "재생성 요구사항(자유 입력)"을 공유해서 씀 — 부분 재생성에만 있던 `style`/`extra_requirement`가 전체 생성(재생성)에도 필요하다는 뜻.

**Select page / Coach Set Page에서 확인한 것**: "AI 대본 생성"과 "발표 발음 코칭"이 완전히 분리된 두 입구. 코칭 쪽은 "이미 준비된 대본이 있으신가요?"라며 대본을 직접 붙여넣거나 DOCX/TXT/PDF로 올려서 **생성 단계 없이 바로 코칭/평가로 직행**하는 경로가 따로 있음.

### 구현한 것

- `POST /api/ppt/extract` → **`POST /api/projects`로 교체**, 3가지 입력 방식 지원:
  1. `file`(PPTX 또는 PDF) — PDF는 `utils/pdf_extractor.py`(신규, pypdf 재사용) 추가해서 지원
  2. `file` 없이 `topic` + `outline` — 없으면 422 (Figma 툴팁 로직 그대로)
  3. `script_text` — 이미 완성된 대본을 바로 저장, 생성 단계 스킵하고 코칭/평가로 직행 가능
- `FullScriptRequest`: `style`을 자유 텍스트 → `Literal["격식체","편안한 말투"]`로, `extra_requirement`(선택) 신규 추가. `FullScriptGenerator.generate_full_script()`에 반영.
- **실제 라이브 테스트 중 버그 발견/수정**: topic+outline만으로 만든 프로젝트(원본 슬라이드 1개)로 대본을 생성했더니 모델이 4개 슬라이드로 쪼개서 응답했는데, 기존 코드가 "원본에 없는 슬라이드 번호"를 전부 버려서 2~4번째 슬라이드가 통째로 유실되고 있었음. 없는 슬라이드 번호는 새로 만들어서 저장하도록(upsert) 수정, 회귀 테스트 추가.
- 테스트 24 → **29건**, 전부 실제 라이브 HCX 호출로도 검증(topic+outline만으로 프로젝트 생성 → 4슬라이드 대본 생성 → DB에 4개 다 저장 확인, 실제 PDF 파일로 프로젝트 생성 확인).

### 의도적으로 보류한 것 (Figma에서 발견했지만 스펙 미확정)

Figma의 "Coach View Page"/"Feedback Page"를 보면 이번에 구현한 것보다 훨씬 정교한 화면이 있음:
- **장단음/연음/표기-발음불일치 3분류 하이라이트** — 지금은 단어+발음기호 flat list만 있고 이런 분류가 없음. 분류 규칙 설계 필요.
- **AI 생성 "발음 팁"/"상세 피드백"** — Azure는 숫자 점수만 주기 때문에, 이 정성적 피드백 문장은 별도 HCX 호출로 새로 만들어야 함. 프롬프트 설계 필요.
- **오디오 MP3/M4A 지원** — Figma는 "MP3/WAV/M4A" 명시하는데 지금은 WAV만 됨. ffmpeg 변환 파이프라인이라는 새 의존성이 필요해서 보류.
- **코칭 대본 DOCX/TXT 파일 업로드** — 텍스트 붙여넣기(`script_text`)는 되지만 파일 업로드는 안 됨. DOCX는 `python-docx` 새 의존성 필요.

이 4가지는 전부 "코드만 있으면 바로 되는" 수준이 아니라 분류 규칙/프롬프트/새 의존성 등 설계 결정이 필요해서, 이번엔 스펙이 명확한 것들(위 "구현한 것")만 먼저 반영하고 `PLANS.md`/`tech-debt-tracker.md`에 남겨둠.

## ✅ 완료 (2026-07-21): TTS는 키 발급 대기로 보류 기록 + CI 파이프라인 구축

"TTS 엔드포인트 연결이 실제 키가 필요하면 기록해두고 다음 단계로 가라"는 요청 →
`CLOVA_VOICE_CLIENT_ID`/`SECRET` 미발급 상태라 라우터를 연결해도 fallback만 나가 실효성이 없다고 판단, `PLANS.md`에 "보류(실제 키 발급 대기)" 섹션으로 옮기고 다음 키-불필요 우선순위로 넘어감.

`.github/workflows/tests.yml` 신규 — `main` push/PR마다 `speako-ai-server/`에서 `requirements-dev.txt` 설치 후 `pytest tests/ -q` 자동 실행. 외부 API 키 없이도(`.env` 자체가 CI엔 없음) 모든 클라이언트가 이미 fallback 모드로 안전하게 초기화되도록 설계돼 있어서 별도 시크릿 없이 24건 그대로 통과할 것으로 예상 — **실제 GitHub에 push된 후 Actions 탭에서 첫 실행 결과 확인 필요** (로컬에서는 워크플로우 자체를 실행해볼 수 없음).

## ✅ 완료 (2026-07-21): 인증 경계 설정 (X-API-Key)

DB 작업 직후, "SQLite는 서버에 연결하는 게 아니지 않냐, 실제 서버 담당자/프론트 팀이 있는데"라는 질문이 나옴 →
SQLite는 DB 서버가 아니라 FastAPI 프로세스에 내장된 파일이고, 프론트는 여전히 HTTP로 FastAPI 서버에만 붙는 구조라 지금 당장은 문제 없다고 설명. 다만 서버리스/멀티 인스턴스 배포 시엔 못 씀. 배포 계획을 물어보니 아직 미정이라 **SQLite 유지, 필요해지면 SQLAlchemy 덕분에 `DATABASE_URL`만 바꿔서 Postgres로 쉽게 전환 가능**하다는 걸로 정리하고 다음 우선순위(PLANS.md 1번, 인증)로 진행.

- `main.py`에 `verify_api_key` 의존성 추가 — `X-API-Key` 헤더를 `SPEAKO_API_KEY` 환경변수와 비교. `/api/*` 전부를 별도 `APIRouter(dependencies=[Depends(verify_api_key)])`로 묶어서 일괄 적용, `/`(헬스체크)만 인증 제외.
- **fail-open 설계**: `SPEAKO_API_KEY`가 비어있거나 플레이스홀더(`여기에_...`)면 인증을 아예 건너뜀 — 로컬 개발 편의. 배포 전에 반드시 실제 값을 채워야 함. 안 채우면 지금처럼 무인증 상태 그대로 나감 — `SECURITY.md`에 명시.
- 겸사겸사 SECURITY.md에 남아있던 다른 체크리스트 항목도 같이 해결: 업로드 파일명을 그대로 서버 경로에 쓰던 것(`temp_{uuid}_{원본파일명}`) → `_safe_temp_path()`로 확장자만 추출해 새 임의 이름 생성하도록 교체 (경로 조작 방지).
- 테스트 3건 추가(인증 꺼진 기본 상태 통과, 켜졌을 때 키 없음/틀림 401, 올바른 키면 통과, `/`는 인증 상태와 무관하게 항상 통과) — pytest 21 → **24건**, 전체 통과.
- 실제 서버로 스모크 테스트 재실행(`_db_smoke_test.py`) — 인증 꺼진 기본 상태에서 기존 플로우 그대로 동작하는 것 재확인.

**한계**: 지금은 공유 비밀키 하나뿐이라 "정당한 호출인지"만 구분하고 "누구인지"는 구분 못함 — 유효한 키만 있으면 아무 `project_id`나 조회/수정 가능. 사용자 계정 시스템이 생겨야 근본 해결됨. `PLANS.md`/`tech-debt-tracker.md`에 후속 작업으로 기록.

## ✅ 완료 (2026-07-21): 영속성 계층(DB) + 프로젝트 개념을 실제 API에 연결

"ETRI/CLOVA Voice 키 없이 지금 가능한 것" 목록 중 사용자가 가장 임팩트 크다고 판단한 두 개(프로젝트 개념 없음 + 영속성 계층 없음)를 먼저 처리.

**핵심 문제**: 로컬 테스트 스크립트(`run_pipeline_test.py` 등)는 `projects/<이름>/` 폴더로 PPT↔대본↔녹음을 묶어서 관리했지만, 실제 `/api/*`는 완전히 stateless라 어떤 대본이 어떤 PPT에서 나왔는지, 지난번 평가 결과가 뭐였는지 전혀 안 남았음.

**구현**:
- SQLite + SQLAlchemy 도입(`speako-ai-server/src/db/database.py`, `models.py`). DB 파일은 `speako-ai-server/data/speako.db`(gitignore 대상). 서버 기동 시 테이블 자동 생성, 별도 마이그레이션 도구는 아직 없음(스키마 자주 안 바뀔 거라 지금은 과함 — 필요해지면 Alembic 검토).
- 테이블 4개: `projects`, `slides`(project_id fk), `difficult_words`(project_id fk), `pronunciation_evaluations`(project_id fk, 매 평가마다 새 행 추가 → 히스토리). 상세 스키마와 원안 대비 변경점은 [db-schema.md](docs/generated/db-schema.md).
- **`/api/ppt/extract`**: 이제 PPT 업로드 시 `projects` + `slides` row를 만들고 `project_id`를 응답에 포함. `project_name`(선택), `topic_hint`/`outline_hint`(선택, HCX 비전 이미지 인식 정확도용)도 폼 필드로 받음.
- **`/api/script/full`**: `ppt_text` 직접 입력 대신 `project_id`만 받음. DB의 슬라이드 원문으로 대본을 생성하고, 결과를 슬라이드별로 다시 DB에 저장.
- **`/api/script/partial`**: `original_script` 필드 삭제 — 클라이언트가 원본 대본 전문을 다시 보낼 필요 없이 DB에 저장된 최신 대본을 그대로 씀. `project_id` + `target_slide` + `style`/`extra_requirement`만 받음.
- **`/api/analysis/words`**: `script_text` 대신 `project_id`. 겸사겸사 **버그도 하나 고침** — ETRI 키 없을 때 실제 대본과 무관하게 고정된 4개 단어(`메타버스`,`인프라`,`특징`,`구축`)만 반환하던 문제를, 이 프로젝트의 실제 대본에서 빈도 기반으로 후보를 뽑는 로컬 휴리스틱(`utils/text_heuristics.py`, `ppt_extractor.py`의 키워드 추출 로직과 공용화)으로 교체.
- **`/api/evaluation/audio`**: `project_id`(폼 필드) 추가, `reference_text`는 이제 선택 — 안 주면 DB에 저장된 대본 전체로 평가함. 평가 결과를 매번 `pronunciation_evaluations`에 새 행으로 저장(히스토리 누적).
- **신규 `GET /api/projects`**(목록), **`GET /api/projects/{id}`**(슬라이드별 대본 + 발음 주의 단어 + 평가 히스토리 상세) — db-schema.md가 원래 의도했던 "히스토리 조회" 요구사항을 충족.

**검증**:
- pytest 9건 → **21건**으로 확장(테스트마다 인메모리 SQLite로 격리, `tests/conftest.py`의 autouse fixture). 새 계약(project_id 기반) 반영 + 404/422 경계 케이스 추가.
- 실제 서버 코드로 라이브 스모크 테스트(`src/_db_smoke_test.py`, mock 없이 진짜 HCX 호출): PPT 업로드(`부산대_체교과_교수지도안_발표`) → 전체 대본 생성(18/18 슬라이드 DB 저장 확인) → 부분 재생성(원본 재전송 없이 project_id만으로 동작) → 단어 분석(ETRI 키 없어도 실제 대본에서 뽑은 단어 확인, 더 이상 고정 리스트 아님) → `/api/projects` 목록 조회까지 전부 실제로 이어지는 것 확인.

**부수 정리**: `main.py`가 매 요청마다 `generated_scripts/`에 파일도 같이 저장하던 로직 제거(DB가 이제 authoritative source, 파일 중복 저장은 불필요한 복잡도라 판단). 로컬 테스트 스크립트들(`run_pipeline_test.py` 등)은 DB와 무관하게 `projects/` 폴더 기반으로 계속 동작 — 영향 없음.

**남은 것**: 인증/인가가 여전히 없어서, `project_id`를 알면 누구나 남의 프로젝트를 조회/수정할 수 있음. `tech-debt-tracker.md`에 우선순위 올려서 기록함.

## ✅ 머지 완료 (2026-07-21)

CLOVA OCR → HCX-005 비전 교체 작업 [PR #6](https://github.com/chiung22/SpeaKO/pull/6) `feat/hcx-vision-image-extraction` 브랜치로 머지 완료. pytest 9건 통과 상태로 `main` 반영. (중간 발표 대본은 요청대로 git에 올리지 않고 `docs/presentations/`에 로컬 파일로만 남겨둠.)

## ✅ 완료 (2026-07-21): 부분 재생성(어투 전환) 테스트

"대본 생성된 PPT 기준으로 랜덤 부분 재생성, 기존과 다른 어투로" 요청 → 테스트함.

**말투 정의 확정**: 격식체(공식적/전문적 어조, 하십시오체) vs 편안한 말투(친근하고 자연스러운 대화체, 해요체) 두 가지로 고정. 부분 재생성 요청 시 사용자가 추가 요구사항(자유 텍스트, 공백 허용)도 같이 넣을 수 있어야 함.

`src/_partial_regen_test.py` 신규 — 프로젝트/슬라이드를 랜덤으로 고르고(지정도 가능), 기존 대본의 말투를 어미 패턴(습니다/드립니다 vs 해요/네요)으로 추정해서 반대 어투를 자동 요청, `feedback`에 어투 지시문 + (있으면) 추가 요구사항을 합쳐서 기존 `PartialScriptGenerator.generate_partial_script()`를 그대로 호출. 별도 API 변경 없이 기존 `feedback: str` 필드를 그대로 활용.

**테스트 결과**: `부산대_체교과_교수지도안_발표` 프로젝트, 슬라이드 18 (전체가 한 슬라이드로 합쳐진 그 대본) — 기존이 격식체로 판정되어 편안한 말투로 재생성 요청. 실제로 "안녕하세요 여러분! ... 자랑스럽기도 하네요" 식으로 확연히 다른 캐주얼한 톤이 나온 것 확인. `projects/부산대_체교과_교수지도안_발표/scripts/partial/`에 저장됨.

**남은 자잘한 이슈**: `PartialScriptGenerator`는 TOON 파싱을 안 하기 때문에 결과 맨 앞에 `slides[18]{Slide_18, script}:` 같은 포맷 헤더가 그대로 섞여 나옴 (전체 생성과 달리 원문 그대로 반환하는 구조라서). 실제 API 응답으로 쓰려면 파싱해서 헤더를 제거해야 함 — 지금은 로컬 테스트 스크립트 결과 파일에만 남아있고 프로덕션 코드엔 영향 없음.

**→ 후속: 실제 API에 반영 완료 (2026-07-21)**

`/api/script/partial` 정식 스키마 변경:
- `feedback: str` 자유 텍스트 필드 삭제 → `style: Literal["격식체", "편안한 말투"]`(필수) + `extra_requirement: Optional[str] = ""`(선택, 공백 허용)로 교체. 기존에 이 필드를 쓰는 프론트/테스트가 없어서(grep으로 확인) 하위호환 없이 바로 교체함.
- `PartialScriptGenerator.generate_partial_script(original_script, target_slide, style, extra_requirement="")`로 시그니처 변경. 어투별 지시문(`STYLE_INSTRUCTIONS`)을 생성기 안에 내장.
- **부분 재생성도 TOON 파싱 적용**: 기존엔 전체 생성(`FullScriptGenerator`)만 TOON 응답을 파싱했고 부분 생성은 원문 그대로 반환해서 `slides[N]{...}` 헤더가 응답에 그대로 섞여 나왔음. `src/clova/toon_parser.py`(신규, `parse_toon_slides()`)로 파싱 로직을 공용화해서 전체/부분 생성기 둘 다 재사용하도록 정리. 이제 `/api/script/partial` 응답의 `data`가 `{"slide_number": "3", "script": "..."}` 형태의 깨끗한 구조화 데이터로 나옴 (파싱 실패 시엔 안전하게 `{"raw_toon": ...}`로 폴백).
- 프롬프트 예시 문장에 있던 "수정된 대본 내용입니다"라는 문구를 모델이 그대로 따라 쓰는 현상 발견 → 예시를 실제 발표 문장으로 교체해서 해결.
- 테스트 3건 추가(`tests/test_main.py`): 잘못된 style 값 422 거부, TOON 파싱 후 구조화 데이터 검증, 키 없을 때 502 검증. pytest 12건 전체 통과.
- 실제 라이브 호출 2건으로 검증: `글챌 ppt`/`에시설_02분반_4조_PromeAI` 슬라이드를 격식체로 재생성 — 자연스러운 격식체 결과 확인, TOON 헤더 잔재 없음.

**TOON 파싱이 성능에 영향 있는지 질문에 대한 답**: 없음. 파싱 자체는 정규식 몇 번 돌리는 수준이라 밀리초 미만이고, 오히려 TOON처럼 압축된 출력 포맷을 요청하면 모델이 생성해야 할 completion 토큰 수가 JSON 대비 줄어서 응답 속도/비용 면에서는 유리한 쪽. 실제 병목은 "속도"가 아니라 "신뢰성"이었음 — 모델이 가끔 프롬프트에 지정한 헤더 구조를 정확히 안 지키고 변형된 형태로 응답해서(예: `slides[N]{...}`를 슬라이드마다 반복) 엄격한 파서로는 깨지는 문제. 그래서 헤더 구조를 엄격히 가정하지 않고 "숫자,텍스트" 패턴 자체를 관대하게 정규식으로 찾아내는 방식(`parse_toon_slides`)으로 만들어서 표준/변형 포맷 둘 다 견디도록 함.

## ⏸️ 대기 중 (2026-07-20): Figma 유저플로우 dev code 받으면 topic/outline 입력 연동

이미지 전용 슬라이드 3건(`02분반 1조 ㅎㅎㅎㅎ`, `UMC PM-DAY_진순`, `동아해커톤`) 처리 방식을 CLOVA OCR 대신 **HCX-005 비전**(새 키 불필요, 이미 있는 `HCX_API_KEY` 재사용)으로 바꾸기로 함. 정확도를 높이려면 사용자가 입력하는 "발표 주제/목차"를 이미지 인식 프롬프트에 문맥으로 같이 넣어주는 게 좋은데, 실제로 Figma 유저플로우 상 사용자가 주제/목차를 입력하는 화면이 있다고 확인함.

**구현된 것**: `ppt_extractor.extract_structured_data(file_path, topic_hint="", outline_hint="")`가 이미 `topic_hint`/`outline_hint`를 받아서 `clova/vision/image_text_extractor.py`(HCX 비전 클라이언트, 신규)로 전달하도록 준비해둠. 작은 아이콘/구분선 이미지는 크기(150x100px 미만)·가로세로비(5:1 초과) 기준으로 걸러내고, 내용 있을 법한 큰 이미지만 비전 모델에 보냄.

**대기 중인 것**: 디자이너에게 dev code(정확한 필드명/데이터 형태) 요청함 — 이게 와야 실제 프론트-백엔드 계약에 맞게 `/api/ppt/extract` 요청에 topic/outline을 실어 보내는 부분을 마무리할 수 있음. 받으면 이어서 진행.

**당장 테스트하려면**: 위 3개 프로젝트의 주제/목차를 사용자가 채팅으로 알려주면, 그걸 `topic_hint`/`outline_hint`로 임시로 넣어서 바로 테스트 가능 (dev code 안 기다려도 됨).

## 🔁 폐기됨: CLOVA OCR 연동 → HCX-005 비전으로 대체 (2026-07-20)

처음엔 이미지 전용 슬라이드 3건(`02분반 1조 ㅎㅎㅎㅎ`, `UMC PM-DAY_진순`, `동아해커톤`) 처리를 위해 CLOVA OCR(네이버)을 연동했었음 (`src/ocr/clova_ocr_client.py`, `.env`의 `CLOVA_OCR_SECRET_KEY`/`CLOVA_OCR_INVOKE_URL`, `usage_tracker.py`의 OCR 집계 등). 그런데 CLOVA OCR은 **새 키 발급이 필요**했고, 어차피 대본 생성에 쓰는 `HCX-005`가 비전(이미지 이해) 모델이라는 걸 확인해서 **새 키 없이 기존 `HCX_API_KEY`로 이미지를 직접 읽는 방식**으로 완전히 대체함.

"정리하자" 시점에 `ocr/clova_ocr_client.py` 삭제, `.env`/`.env.example`/설정 가이드/`usage_tracker.py`에서 CLOVA OCR 관련 내용 전부 정리함. 위 섹션이 현재 유효한 접근 방식.

## ✅ 머지 완료 (2026-07-19)

이 문서에 기록된 작업 전부 [PR #5](https://github.com/chiung22/SpeaKO/pull/5) `fix/hcx-v3-and-pipeline-hardening` 브랜치로 커밋 → 푸시 → 머지 완료. `main`에 반영됨. pytest 9건 통과 상태로 머지.

다음에 이어서 할 만한 것 (아래 "보류" 섹션 참고):
- ETRI API 키 발급 대기 중 (문의 메일 발송함, 응답 대기)
- 사용량 단가(KRW/USD) 확인되면 `usage_tracker.py`에 채워서 실제 비용 계산
- 대본 화자 시점/이미지 텍스트 추출/Azure 다중 pause 정렬 — `tech-debt-tracker.md` 참고

## 🔄 진행 중 (2026-07-20): PPT 일괄 대본 추출 + 자기 고도화

사용자가 새 PPT 5개(+PDF 1개를 pptx로 변환한 것 1개, 총 6개)를 `projects/` 밑에 프로젝트 폴더로 정리 요청 → 완료.
이어서 "PPT 전부 대본 추출하고, 추출한 대본을 스스로 고도화해서 자연스럽게 만들어줘" 요청.

**적용 범위**: `projects/` 밑 프로젝트 폴더 전체
- `ClipRoute` (기존)
- `부산대_체교과_교수지도안_발표` (PDF→pptx 변환, 대본 초안까지 생성 완료 — 이번에 고도화 대상)
- `02분반 1조 ㅎㅎㅎㅎ`, `UMC PM-DAY_진순`, `글챌 ppt`, `동아해커톤`, `에시설_02분반_4조_PromeAI` (신규, 대본 생성부터)

**"스스로 고도화" 구현 방식**: HCX 대본 생성(1차, `FullScriptGenerator`) → 생성된 초안을 다시 HCX에 넣어 "1인칭 발표자 구어체로 자연스럽게 다듬어라"는 별도 시스템 프롬프트로 리뷰·재작성시키는 2차 호출(`ScriptRefiner`, 신규) → 초안과 고도화본을 둘 다 저장. 무한 반복 루프는 아니고 초안→리뷰 1왕복.

HCX 실제 호출이 프로젝트당 2회(생성+고도화)씩 총 12회 정도 발생함 — `usage_log.md`에 기록됨.

### 결과 (2026-07-20)

- **성공 (3건)**: `ClipRoute`, `글챌 ppt`, `에시설_02분반_4조_PromeAI` — 대본 생성 + 고도화 모두 완료, `scripts/full/*_refined_*.txt`에 저장. 1인칭 발표자 구어체로 자연스럽게 나온 것 육안 확인함.
- **재사용 + 고도화만 (1건)**: `부산대_체교과_교수지도안_발표` — 기존에 만들어둔 초안을 재사용해서 고도화만 새로 돌림.
- **실패 (3건)**: `02분반 1조 ㅎㅎㅎㅎ`, `UMC PM-DAY_진순`, `동아해커톤` — **3건 전부 슬라이드가 텍스트박스가 아니라 전부 이미지(PICTURE) shape로만 구성되어 있어서 `python-pptx`로 텍스트를 한 글자도 추출 못함** (표지/장표를 이미지로 export해서 넣은 PPT로 추정). 기존에 알려진 "이미지 속 텍스트 추출 불가" 한계와 동일 이슈, `tech-debt-tracker.md`에 기록된 항목. OCR 도입 여부는 사용자 결정 필요 → 다음 세션에서 논의.

pytest 9건 통과 유지. 신규 헬퍼 스크립트: `src/_convert_pdf_to_pptx.py`(PDF→PPTX, 페이지 텍스트를 슬라이드 텍스트박스로), `src/_batch_generate_and_refine.py`(프로젝트 전체 순회하며 대본 생성+고도화). `generator.py`에 `ScriptRefiner` 클래스 추가(초안을 1인칭 구어체로 리뷰·재작성하는 2차 HCX 호출).

## 배경

- ETRI epretx.etri.re.kr 가입 페이지 500 에러 → ETRI 측에 문의 메일 발송 완료, 응답 대기 중
- HCX_API_KEY는 이미 발급되어 있음 (`.env`에 설정됨)
- ETRI_API_KEY / AZURE_SPEECH_KEY / CLOVA_VOICE_CLIENT_ID·SECRET은 아직 미발급 → 관련 기능은 fallback(mock) 모드로만 동작

## 진행 중 / 예정 작업 (외부 API 키 불필요)

(현재 없음 — 아래 "완료" 참고)

## 이번 세션에서 발견한 심각한 버그 (수정 완료)

`더 고도화 할 거 없어? PPT 파일만 있으면 실행돼?` 질문에 답하려고 실제 HCX_API_KEY로 라이브 호출을 해보다가 발견함. **API 키 문제가 아니라 순수 코드 버그였고, 지금까지 대본 생성 기능은 한 번도 실제로 성공한 적이 없었음.**

1. **잘못된 API 버전/엔드포인트**: `HCX-005` 모델은 `v3` chat-completions 전용인데, 코드는 구버전 `v1` 엔드포인트(`.../testapp/v1/chat-completions/...`)를 호출하고 있어서 매 호출이 `40084 Unsupported API for model`로 실패했음. `https://clovastudio.stream.ntruss.com/v3/chat-completions/{model}`로 수정하고, v3가 요구하는 `content: [{"type":"text","text":...}]` 메시지 포맷으로 변경. 실제 키로 호출해 200 응답과 실제 생성된 대본을 확인함.
2. **TOON 파서가 실제 모델 출력을 못 따라감**: 엔드포인트를 고치고 나니, 모델이 `slides[N]{slide_number,script}:` 헤더+행 구조를 정확히 안 지키고 `slides[N]{...}`를 슬라이드마다 반복하는 걸 확인함. 기존 파서(헤더 1줄 가정 + CSV 파싱)는 이런 변형에서 완전히 엉뚱한 결과를 냄. `slide_number,script` 패턴 자체를 정규식으로 관대하게 추출하는 방식으로 교체 — 표준 포맷과 변형 포맷 둘 다 통과 확인.
3. `partial_generation/generator.py`도 동일한 v1→v3 엔드포인트/포맷 버그가 있어 같이 수정 (여긴 원래 TOON 파싱 없이 원문 그대로 반환하는 구조라 파서는 안 건드림). 실제 호출로 정상 동작 확인.

수정 파일: `clova/full_generation/generator.py`, `clova/partial_generation/generator.py`
테스트: `tests/test_main.py`에 (a) 키 없을 때 502를 결정적으로 검증하는 테스트 수정(로컬 `.env`의 실제 키에 의존하지 않도록 monkeypatch), (b) 네트워크 호출 없이 변형된 실제 응답 포맷을 파싱하는 회귀 테스트 추가. 9건 전체 통과.

> 참고: 이 과정에서 진단을 위해 HyperCLOVA X에 실제로 몇 차례 소규모 테스트 호출(수십~수백 토큰)을 보냈습니다 — 무료 크레딧 범위 내일 가능성이 높지만 참고해주세요.

## 실제 .pptx + .wav로 전체 체인 수동 검증 (완료)

샘플 .pptx(2슬라이드)와 무음 더미 .wav를 만들어 4개 엔드포인트를 순서대로 직접 호출해봤습니다.

| 단계 | 엔드포인트 | 결과 |
|---|---|---|
| PPT 추출 | `/api/ppt/extract` | 실제 동작, 200 |
| 대본 생성 | `/api/script/full` | 실제 HCX 호출 성공, 200 (위 버그 수정 후 확인) |
| 단어 추출 + G2P | `/api/analysis/words` | G2P는 실제 동작. ETRI는 `ETRI_API_KEY`가 플레이스홀더라 **`'latin-1' codec can't encode` 에러로 매번 크래시**하고 있었음 → 발견/수정 (아래) |
| 음성 평가 | `/api/evaluation/audio` | **`AZURE_SPEECH_KEY`가 이미 실제 키로 채워져 있어서 mock이 아니라 진짜 Azure 호출이 나감.** 무음 더미 파일을 넣었더니 Azure가 정직하게 "음성을 인식할 수 없습니다"(502)로 응답 — 정상 동작. 실제 목소리 녹음 파일로 테스트하면 진짜 발음 점수가 나올 것으로 보임 |

### 새로 발견/수정한 버그
- **ETRI 클라이언트 크래시**: `ETRI_API_KEY`가 미설정(플레이스홀더)일 때, 그 문자열을 그대로 `Authorization` 헤더에 넣어 요청을 보내려다 `requests`가 헤더를 latin-1로 인코딩하려 하면서 한글 때문에 `UnicodeEncodeError`가 났음 (`etri_client.py`). `except Exception`으로 잡히긴 해서 최종 API 응답 자체는 200으로 fallback 되지만, 에러 로그가 진짜 원인(키 미설정)을 가려서 디버깅에 방해가 됨. `azure_client.py`/`clova_voice_client.py`와 동일하게 `use_fallback` 가드를 추가해서, 키가 없으면 아예 네트워크 호출을 시도하지 않고 깔끔하게 `[]`를 반환하도록 수정.

### 확인된 좋은 소식
- `AZURE_SPEECH_KEY`가 이미 실제 키로 채워져 있음 (언제 넣으셨는지는 모르겠지만) → **발음 평가 기능은 ETRI 키 없이도 이미 실제로 동작 가능한 상태**. 실제 목소리로 녹음한 .wav만 있으면 진짜 점수를 받아볼 수 있음.

pytest 9건 전체 통과 유지.

## 파일 구조 정리 + 생성 결과 파일 저장 (완료)

`speako-ai-server/` 밑에 폴더를 나눴습니다:

- `pptx/` — 테스트용 .pptx 원본 넣는 곳 (`20232693_송치웅.pptx` 여기로 이동함)
- `generated_scripts/full/` — `/api/script/full` 및 `run_pipeline_test.py`가 생성한 전체 대본 저장 (JSON)
- `generated_scripts/partial/` — `/api/script/partial`이 생성한 부분 재생성 대본 저장 (TXT)

둘 다 `.gitignore`에 추가함(개인 테스트 데이터/런타임 산출물이라 커밋 대상 아님).

- `src/utils/script_storage.py` 신규 — `save_generated_script(kind, content, stem, extension)` 공용 함수. `main.py`의 두 대본 생성 엔드포인트와 `run_pipeline_test.py`가 공유해서 사용.
- `main.py`: `/api/script/full`, `/api/script/partial` 성공 시 자동으로 파일 저장 + 저장 경로를 콘솔에 로그.
- `run_pipeline_test.py`: `_resolve_pptx_path()`가 이제 `pptx/` 폴더에서 자동으로 찾음(기존엔 `speako-ai-server/` 루트 바로 밑을 봤음). STEP 1 성공 시 `generated_scripts/full/`에 저장.

실제 API 호출 없이(mock으로) 두 엔드포인트가 각각 올바른 폴더에 저장하는 것까지 확인했고, pptx 자동 탐지도 새 경로(`pptx/20232693_송치웅.pptx`)를 정확히 찾는 것 확인. pytest 9건 통과 유지.

## 재구조화: 프로젝트 단위 폴더로 통합 (완료)

"녹음 파일 폴더도 만들자"는 요청에 "근데 어떤 녹음이 어떤 PPT/대본에 해당하는지 어떻게 아나?"라는 질문이 이어져서, 평평한(flat) `pptx/` + `generated_scripts/` 구조를 프로젝트별 폴더로 재구성했습니다. 파일명으로 짝을 맞추는 대신, **같은 폴더 안에 있다는 것 자체가 대응 관계**가 되도록 함.

```
speako-ai-server/projects/
  <프로젝트 이름>/              예: ClipRoute/
    <아무이름>.pptx              사용자가 직접 넣음
    scripts/
      full/   *.json            전체 대본 생성 결과
      partial/ *.txt            부분 재생성 결과
    recordings/
      <아무이름>.wav             사용자가 직접 넣음 (다음 단계에서 여기에 넣으면 됨)
```

- `20232693_송치웅.pptx`와 기존 생성 대본을 `projects/ClipRoute/`로 이동.
- `src/utils/script_storage.py`: `save_generated_script()`에 `project_dir` 옵션 추가 (주어지면 `<project_dir>/scripts/<kind>/`에 저장, 없으면 기존 `generated_scripts/<kind>/`로 fallback). `find_file_with_ext(folder, extensions)` 헬퍼 추가.
- `run_pipeline_test.py`: `_resolve_pptx_path()` → `_resolve_project_dir()`로 교체. 인자로 프로젝트 폴더를 받거나, `projects/` 밑 폴더를 자동 탐지(여러 개면 안내 후 첫 번째 사용). 그 프로젝트 폴더 안에서 pptx/스크립트저장/녹음파일을 전부 찾고 저장함. **STEP 5(Azure 평가)가 이제 프로젝트의 `recordings/` 폴더에서 `.wav`를 자동으로 찾아 사용** — 더 이상 존재하지 않는 더미 경로를 쓰지 않음.
- `.gitignore`: `speako-ai-server/pptx/` → `speako-ai-server/projects/`로 교체.

### 남은 간극 (알아둘 것)
`main.py`의 실제 API(`/api/script/full`, `/api/script/partial`, `/api/evaluation/audio`)는 여전히 "프로젝트/세션" 개념이 없습니다. 요청 바디에 PPT 파일이나 프로젝트명을 안 받기 때문에, 실제 API를 통해 생성된 대본은 여전히 예전처럼 평평한 `generated_scripts/<kind>/`에 저장되고 어떤 PPT에서 왔는지는 안 남습니다. 지금은 로컬 수동 테스트(`run_pipeline_test.py`) 쪽만 프로젝트 폴더로 묶었고, 실제 API까지 연결하려면 요청 스키마에 project_name 같은 필드를 추가하는 결정이 필요함 (프론트엔드와 계약이 걸리는 부분이라 별도로 논의 필요) — `영속성 계층 없음` 항목과 사실상 같은 이슈.

pytest 9건 통과 유지, 프로젝트 폴더 자동 탐지/저장 직접 확인 완료.

## 대본 품질 피드백 + 실제 녹음 파일로 발음 평가 테스트 (완료)

사용자가 실제 생성된 대본을 검토하고 두 가지 피드백을 줌 → `docs/exec-plans/tech-debt-tracker.md`에 정식으로 기록함:
1. 대본 문장이 발표자 1인칭 어투가 아니라 관찰자 시점("~설명합니다")으로 어색하게 나옴 → 시스템 프롬프트 손볼 필요.
2. PPT 안 이미지/도형(화살표 등)에 들어있는 텍스트는 추출이 안 됨 (python-pptx 구조적 한계, OCR 없이는 근본 해결 불가).

또한 "부분 재생성 시 슬라이드 번호를 어떻게 아냐"는 질문에 대해, 대본을 이어붙일 때 `"Slide N: 내용"` 형식을 그대로 텍스트에 남기도록 수정함 (`run_pipeline_test.py`, `main.py` `/api/script/full` 둘 다 — JSON 저장본 옆에 평문(`_plain.txt`) 버전도 같이 저장).

**실제 녹음 파일로 테스트:**
- 사용자가 `.m4a` 파일을 프로젝트 폴더의 `scripts/`(잘못된 위치)에 넣어서, `ffmpeg`로 16kHz mono `.wav`로 변환 후 `recordings/`로 이동 (원본 `.m4a`도 `recordings/`에 보관).
- 실제 Azure Speech로 발음 평가 확인 — **진짜로 동작함** (mock 아님). 대본 앞 2슬라이드 분량을 reference로 주니 정확도 86/유창성 83/완전성 82로 합리적인 점수가 나옴.
- **중요한 한계 발견**: `azure_client.py`가 쓰는 `recognize_once_async()`는 파일 길이와 무관하게 앞부분 약 15~25초만 인식함. 녹음(3분24초, 27슬라이드 전체 낭독) 중 앞 2슬라이드로 테스트하면 정상 점수가 나오지만, 6슬라이드 분량으로 늘리면 완전성 25/유창성 37로 무너짐 — 인식된 구간은 그대로인데 reference만 길어져서 뒷부분이 다 어긋난 것. **여러 슬라이드를 한 번에 녹음해서 평가하는 용도로는 못 씀, 한 슬라이드씩 짧게 녹음해야 정확하게 동작함.** tech-debt-tracker.md에 기록, 연속 인식(`start_continuous_recognition`)으로 바꿔야 근본 해결됨.

결론: PPT 추출 → 대본 생성 → 발음 평가까지 전체 파이프라인이 실제 키로 실제 동작하는 것을 확인함 (ETRI 단어 추출만 키 없어서 fallback). pytest 9건 통과 유지.

## Azure 평가를 연속 인식으로 교체 + API 사용량 로그 추가 (완료)

사용자가 "녹음을 어디까지 했는지는 나도 몰라, AI가 듣고 알아서 판단해야지"라고 지적 → 정당한 지적이라 판단하고 근본 수정함.

- `azure_client.py`: `recognize_once_async()`(pause 한 번 만나면 그 이후는 아예 안 들음) → `start_continuous_recognition()` + `PronunciationAssessmentConfig(enable_miscue=True)`로 교체. 이제 **전체 대본(예: 27슬라이드 전체)을 통째로 reference로 줘도**, 실제 사용자가 어디까지 말했는지 미리 알려줄 필요 없이 Azure가 알아서 말한 부분만 채점하고 나머지는 Omission 처리함.
- 실제 3분 24초 녹음 + 12슬라이드 분량 reference로 검증: 391개 단어 인식됨(이전엔 처음 pause 지점까지인 약 50개 단어에서 멈췄었음). 다만 pause가 여러 번 있으면 뒷부분 단어 순서가 원문과 살짝 어긋나는 현상 발견 → `tech-debt-tracker.md`에 잔여 이슈로 기록(한 호흡으로 이어 읽는 녹음에는 문제 없음).
- `src/utils/usage_tracker.py` 신규: HCX(토큰 수), Azure Speech(오디오 초), Clova Voice(글자 수), ETRI(호출 수, 무료) 사용량을 호출마다 자동 누적 기록. `speako-ai-server/usage_log.md`(사람이 보는 로그) + `.usage_state.json`(누적 상태, 내부용) 둘 다 생성 — **둘 다 `.gitignore`에 추가함**. 정확한 단가(KRW/USD)는 확인 전이라 비용 칸은 "TBD"로 표시됨 — 콘솔에서 확인한 단가를 알려주면 `usage_tracker.py` 상단 상수에 채워서 실제 비용까지 계산되게 할 수 있음.
- 네 클라이언트(`full_generation`, `partial_generation`, `etri_client`, `clova_voice_client`) + `azure_client`에 로깅 호출 삽입.

pytest 9건 통과 유지.

## 보류 (설계 결정 필요, 이번 라운드 범위 아님)

- 인증/인가 체계 추가 — 방식/범위 결정 필요
- 영속성 계층(DB) 추가 — DB 선택, 스키마 적용 결정 필요
- 구조화 로깅 도입 — 전부 `print()`로 되어있음, 로깅 라이브러리/포맷 결정 필요
- CI 파이프라인 구축 — PR마다 pytest 자동 실행
- **PPT 추출 → 대본 생성이 자동으로 안 이어짐**: `/api/ppt/extract`가 반환하는 `slides` 데이터를 `/api/script/full`의 `ppt_text` 문자열로 변환하는 건 프론트엔드(또는 별도 조합 로직) 몫으로 남아있음. 지금은 각 엔드포인트가 독립적이라 "PPT 파일 하나로 끝까지 실행"이 안 됨. 프론트/백엔드 계약을 어떻게 가져갈지 결정 필요.
- `run_pipeline_test.py`가 실제 대본 생성 결과(`script_result`)를 무시하고 `script_text`를 하드코딩된 문장으로 덮어씀 (85번째 줄 부근, "JSON 파싱 등을 거쳐 순수 텍스트만 추출했다고 가정" 주석은 실제로 구현 안 됨) — 로컬 통합 테스트 스크립트일 뿐 API 라우터에는 영향 없지만, 실제 생성 결과를 확인하려면 손봐야 함.

## 완료 (이번 세션, 아직 커밋/PR 안 됨 — "정리하자" 시 PR/머지)

| 항목 | 파일 | 비고 |
|---|---|---|
| 외부 API 호출에 timeout(30초) 추가 | `clova/full_generation/generator.py`, `clova/partial_generation/generator.py`, `etri/etri_client.py`, `tts/clova_voice_client.py` | 외부 API 지연 시 워커가 무한 대기하는 문제 방지 |
| `/api/evaluation/audio` 실패 시 200 반환 버그 수정 | `main.py` | 다른 엔드포인트(`/api/script/*`)와 동일하게 502로 통일 |
| 업로드 파일 크기/타입 제한 추가 | `main.py` | PPT 20MB(.pptx만), 오디오 10MB(.wav만), 초과/타입 불일치 시 413/415 |
| HCX 모델명 하드코딩 → 환경변수화 | `clova/full_generation/generator.py`, `clova/partial_generation/generator.py` | `HCX_MODEL_NAME` env var 추가, 미설정 시 기존값 `HCX-005` 유지(하위호환) |
| G2P fallback 사전 확장 (10 → 31단어) | `g2p/g2p_client.py` | 비음화/유음화/격음화/구개음화/경음화 대표 사례 추가 |
| PPT 키워드 추출 휴리스틱 개선 | `utils/ppt_extractor.py` | 목차 슬라이드가 없는 PPT는 전체 슬라이드 텍스트 기반 빈도 분석으로 키워드 추론 (기존엔 임의 텍스트 추출) |
| 테스트 4건 추가 | `tests/test_main.py` | 업로드 확장자/크기 제한, 평가 실패 시 502 검증 |

pytest 8건 전체 통과 확인 완료 (`speako-ai-server`에서 `venv/Scripts/python.exe -m pytest tests/ -q`).

### 첫 번째 HCX/CLOVA Studio 인증 수정 (이전 세션)
`HCX_APIGW_KEY`(구버전 API Gateway 키) 제거, `Authorization: Bearer` 단일 헤더로 전환. `.env`, `.env.example`, `docs/references/api-key-setup-guide.md`, `apikey_발급.txt` 갱신 완료.
