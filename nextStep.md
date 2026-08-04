# Next Step — 진행 현황

API 키(ETRI/Azure/Clova Voice) 발급 대기 중 진행 가능한 작업들을 정리합니다. "정리하자"라고 말하면 이 시점까지 작업을 PR/머지하고 이 파일을 최신 상태로 정리합니다.

---

# 🔖 작업 재개 지점 (2026-08-04 기준)

> **대화 컨텍스트가 비워진 뒤 이어서 작업할 때 여기부터 읽으세요.** 아래 "다음에 할 일"의 1번부터 그대로 진행하면 됩니다.

## 지금 상태

| 항목 | 값 |
|---|---|
| 작업 디렉터리 | `c:\Users\송치웅\Desktop\Project\SpeaKO` (AI 서버는 `speako-ai-server/`) |
| 브랜치 | `main` (워킹트리 깨끗함, 로컬 브랜치 main 하나) |
| 최신 커밋 | `ac8754e` (PR #18 머지) |
| 테스트 | **149건 통과** |
| 엔드포인트 | 15개 (`src/main.py`) |

**테스트 실행법** — 반드시 venv 파이썬을 쓸 것. 시스템 파이썬엔 pytest가 없습니다:
```
cd speako-ai-server && ./venv/Scripts/python.exe -m pytest tests/ -q
```

## 다음에 할 일 (우선순위 순)

배포하면 터지지만 로컬에선 안 터지는 것들부터. 전부 [tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) 표에 근거가 있습니다.

1. **입력 길이 상한 추가** — `main.py`의 `script_text`/`topic`/`outline`/`extra_requirement`에 Pydantic `Field(max_length=...)`가 없어, 호출자가 유료 API(HCX/Azure) 비용을 무제한으로 유발할 수 있음.
2. **블로킹 I/O 오프로드 마무리** — `/api/script/full`만 `run_in_threadpool`로 처리됨. `/api/evaluation/audio`(ffmpeg `subprocess.run` + Azure `done.wait`), `/api/analysis/words`(stdict HTTP)는 아직 `async def` 안에서 동기 호출 중 → 한 요청이 이벤트루프를 잡으면 다른 요청이 멈춤.
3. **업로드 본문 크기 상한** — `_save_upload_with_limit`는 413을 내지만, 그 시점엔 이미 multipart 전체가 파싱된 뒤. ASGI 미들웨어 또는 프록시 레벨 차단 필요.
4. **레이트 리밋** (slowapi 등).
5. **`job_store` 외부화** — 지금은 프로세스 메모리라 워커 2개 이상이면 폴링이 404. 단일 워커 전제로 배포하거나 Redis/DB로 옮겨야 함.

## 건드리지 말 것 / 대기 중

- **TTS(Clova Voice) 연결** — 사용자가 8/11 주로 미뤘음. 지시 전까지 착수 금지.
- **`speakO-Back` 저장소 push 금지** — 명시적 지시 있을 때까지 `chiung22/SpeaKO`에만 반영.
- 실제 사람 목소리 녹음 검증 / PM의 AI 화면 Figma — 둘 다 사용자·외부 대기.

## 이번 정리 라운드(8/04)에 한 것

- Figma export 폴더 3개(07-21 / 07-27 / 08-04)를 `docs/figma/UMC 10th_SpeaKO (1)/` 하나로 통합. 겹치면 최신본 우선, 고유 파일 전부 이관 후 나머지 삭제(유실 0 확인). 워킹트리 미커밋 162건 → 0건. (PR #17)
- [tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md)를 실제 코드와 동기화 — 이미 고친 11건이 부채 표에 남아 있어 잔여 작업 판단이 불가능했음. 새 부채 1건(`job_store` 메모리) 추가. (PR #18)
- 머지 완료된 로컬 브랜치 6개 삭제. **원격 머지 완료 브랜치 8개는 아직 남아 있음** — 사용자에게 삭제 여부 물어본 상태.

---

## ✅ 현재 상태 (2026-08-04) — 시연 8/21, 개발 완료 목표 8/19

**엔드포인트 15개, pytest 149건 통과.** TTS(Clova Voice) 연결을 제외하면 피그마가 요구한 AI 서버 기능은 전부 구현됨.

### 이 라운드에 들어간 것 (PR #10~#15)
- **대상(청중)·발표 주제**를 생성 프롬프트에 주입. 파일 업로드 시 사용자가 입력한 주제를 자동 감지값보다 우선 저장.
- **결과 화면 편집**: 대본 저장(PUT), 슬라이드 추가/삭제(POST/DELETE, 1..N 자동 재정렬, 마지막 한 장 삭제 금지).
- **대본 생성 비동기화**: `POST /api/script/full` → 202 + `job_id`, `GET /api/script/jobs/{id}` 폴링. 생성이 20~30초라 요청을 붙잡으면 타임아웃에 끊긴다. 로딩 표현은 **스피너만(A안)** 으로 확정 — 단계/진행률은 요구되지 않음.
- **발음 평가**: 점수를 **소수 1자리(0~100)** 로 반환(0~5점 압축 아님). `overall_scores` 키 불일치 버그 수정(실제 Azure 경로에서 DB에 None이 저장되고 있었음).
- **인식 텍스트**: Azure가 실제로 들은 문장(`recognized_text`)과 기준 대본(`reference_text`)을 저장·반환 — 피그마 Feedback Page의 "원본 ↔ 인식" 좌우 비교용.
- **AI 코칭 피드백**: 총평/잘한 점/개선할 점/연습 팁 + 근거 단어. 재호출 시 캐시 반환(HCX 비용 방지). 칭찬도 고득점 단어를 근거로 주게 해서 허구 칭찬 제거.
- **슬라이드별 부분 녹음**: `slide_number`를 주면 그 장 대본만 기준으로 채점하고 이력에 남긴다(전체 기준이면 한 장만 읽었을 때 완성도가 바닥).
- **마이페이지**: 프로젝트 삭제, 발표 코칭 내역 목록.

### 배포 블로커로 발견·수정한 것
- **CORS가 localhost 하드코딩** — 배포 프론트에서 호출하면 브라우저가 전부 차단. 환경변수화 + 배포 도메인/`*.vercel.app` 허용.
- **G2P가 조용히 죽어 있었음** — g2pkk가 요구하는 eunjeon/mecab 사전이 없어 폴백 사전(30여 단어)으로 동작 → 발음기호가 철자와 동일하게 나왔다(실측: 실시간 → [실시간], 연음 0건). 이미 쓰는 **Kiwi로 대체**해 정상화(국물→궁물, 신라→실라, 발음→바름). Linux 경로는 mecab 없이도 예외 없이 생성돼 호출할 때마다 터지므로, **로드 여부가 아니라 실제 변환 결과로 판정**하도록 바꿈.
- **Dockerfile 없음** — ffmpeg가 없으면 webm/mp3 녹음이 전부 502. ffmpeg 포함 Dockerfile 추가.
- **부분 재생성이 502로 실패** — 모델이 TOON 헤더만 붙이고 본문은 평문으로 써서 파서가 빈 결과를 냈고, 내용이 멀쩡한 대본이 폐기됐다. 전체 생성에서 이미 뺐던 TOON 요구를 부분 재생성에서도 제거하고, 정리 로직을 `toon_parser.clean_script_text`로 공용화(헤더/라벨/마크다운 제거).

### 라이브 검증 완료 (실제 서버 + 실제 HCX/Azure)
PPT 업로드·주제만·대본 직접 입력·코칭 파일 / 비동기 생성 202+폴링 / 부분 재생성 / 편집(저장·추가·삭제·재정렬) / 발음 주의 단어 / webm·mp3 → 16kHz 모노 WAV 변환 / 인증(401·200, preflight 통과) / 동시 작업 격리 / 경계값(415·413·422·404).

### 남은 것
1. **TTS(Clova Voice) 엔드포인트 연결** — 클라이언트 구현은 되어 있음. 8/11 주에 진행 예정.
2. **실제 사람 목소리 녹음으로 발음 평가 최종 확인** — 톤 오디오로는 "음성 인식 불가"까지만 검증됨(정상 동작).
3. **배포 서버에 AI API 연결** — 프론트는 스프링을 거쳐서 AI 서버를 호출하는 구조. 스프링이 폴링(`GET /api/script/jobs/{id}`)과 multipart 업로드를 그대로 통과시켜야 함.
4. **피그마에 AI 기능 화면이 없음** — 대본 생성 흐름/코칭/피드백 프레임이 현재 파일에 없어 PM에게 요청함(`docs/references/PM_디자인요청_*.txt`). 구현은 이전 버전 피그마 기준.
5. 프론트 전달용 문서: `docs/references/SpeaKO_AI서버_API명세서.txt`(txt), `frontend-api-guide.md`(md).

### 알아둘 한계
- 작업 상태(`job_store`)는 **프로세스 메모리**에 있다. 서버를 여러 워커/여러 대로 늘리면 폴링이 다른 프로세스로 가서 404가 난다. 그때는 DB 구현으로 교체 필요(모듈이 create/complete/fail/get 4개만 노출하도록 분리돼 있음).
- 슬라이드 미리보기(썸네일)는 서버가 만들지 않는다. 프론트에서 PPT를 렌더링하는 것으로 합의됨.

## 🔄 진행 중 (2026-07-27): 업데이트된 피그마 반영 (AI 서버 기준)

사용자가 업데이트된 피그마(`docs/figma/UMC 10th_SpeaKO/`)를 넣고 "피그마 참고해서 작업, 앞으로 모든 작업은 AI 서버 기준"이라고 함. 핵심 스펙은 `image 332`(기능 선택 화면), `image 333`(AI 대본 생성 전체 흐름 상세)에 주석까지 달려 있음.

**피그마 → AI 서버 gap 분석**:
1. **대상(청중) 필드** — 생성 입력·결과화면 재생성에 "대상"(예: 교수님/면접관)이 있는데 AI 서버엔 없었음. → **구현함**(아래).
2. 생성 로딩이 단계별(분석중→구성중→대본생성중→완료). → Phase 2(백그라운드 job+폴링) 필요. 프론트 협의 대상. (tech-debt-tracker 참고)
3. 발음 평가 점수 형태. → **결정·구현됨**: 백엔드가 측정해서 **1점 단위 정수(0~100)로 반올림**해 내려주고 프론트는 표시만 함(사용자 지시: "우리가 측정하고 프론트는 점수를 띄워만", "0~5점 말고 1점 단위로"). 이 과정에서 **키 불일치 버그도 수정** — main.py가 `result.get("scores")`로 읽었는데 azure_client는 `overall_scores`로 반환해, 실제 Azure 경로에서 DB에 점수가 None으로 저장되고 있었음(테스트가 `scores`로 목킹해 미검출). `overall_scores`로 바로잡고 정수 반올림(전체 점수 + 단어별 정확도) 적용, `evaluate_audio`도 `run_in_threadpool`로 오프로드.
4. 말투 = 격식체/편안한 말투 → 이미 일치.
5. 발표 주제만 필수, 나머지 선택 → 대체로 일치.
6. 녹음 최대 4분 → 10MB 상한으로 커버.

**대상(청중) 구현 (완료)**:
- `FullScriptRequest`/`PartialScriptRequest`에 선택 필드 `audience` 추가.
- `clova/styles.py`에 `audience_instruction()` 추가(스타일과 동일한 공용 패턴). 비어 있으면 "일반 청중", 값 있으면 그 청중에 맞춘 존대/용어/강조.
- 전체 생성·부분 재생성 프롬프트 `[반드시 지킬 것 — 대상]`에 주입. 기존 호출부는 기본값("")이라 안 깨짐.
- `create_partial_script`도 `run_in_threadpool`로 오프로드(전체 생성과 동일 패턴).
- 테스트 `test_styles.py`에 대상 주입 검증 추가.

## 🔄 진행 중 (2026-07-22): ETRI → Kiwi 로컬 형태소 분석기로 대체 + 팀원 PPT 일괄 대본 추출

**배경**: ETRI 문의 답변이 안 와서, 사용자가 "답변 오기 전까지 Kiwi로 설계하자"고 함. + 팀원 4명(리릭/민실/제로/진순) PPT를 `projects/<닉네임>/` 밑에 넣어두고 대본 추출을 요청함(자연스러운지 판단해 팀원 컨펌 받으려고).

**Kiwi 통합 (완료)**:
- ETRI가 하는 일은 결국 한국어 형태소 분석(명사/고유명사/외국어 2글자+ 추출)뿐 → 로컬 라이브러리로 대체 가능. `kiwipiepy`(Windows wheel, Java 불필요, 키 불필요, 오프라인) 설치·검증. `사건`/`정보`/`ChatGPT`/`현대자동차` 등 ETRI와 동일 태그(NNG/NNP/SL)로 정확히 추출, 조사도 제대로 분리 확인.
- `src/nlp/kiwi_analyzer.py`(신규, 기존 클라이언트의 `use_fallback` 패턴 준수, 로드 실패 시 빈 리스트).
- `/api/analysis/words` 단어 추출을 **ETRI(키 있으면) → Kiwi(현재 주력) → 빈도 휴리스틱(방어)** 3단계 체인으로. ETRI 키가 나중에 오면 그냥 키만 넣으면 ETRI 우선. "Slide N:" 접두어를 분석 전 제거(안 그러면 "Slide"가 외국어로 잡힘).
- `requirements.txt`에 `kiwipiepy==0.23.2` 추가. `tests/test_kiwi_analyzer.py`(신규) + `/api/analysis/words`가 Kiwi로 조사 뗀 명사 뽑는지 검증. **pytest 52건 통과.**
- **정확도 관련 정직한 답변**: Kiwi가 ETRI와 "수치까지 동일"하진 않지만(태그셋/학습데이터 상이), 이 프로젝트의 관대한 과제(명사류 추출)에선 실질 차이가 작고 오히려 조사/단일글자 처리는 기존 폴백보다 나음. 진짜 나란히 비교는 ETRI 키가 없어 불가.

**팀원 PPT 일괄 추출 + 그 과정에서 드러난 대형 버그 2건 (2026-07-23)**:
- `src/_batch_extract_team.py`(신규): `projects/` 재귀 탐색으로 모든 .pptx를 찾아 대본 생성+고도화, **각 PPT 바로 옆에 `<파일명>_대본.txt`로 저장**(팀원이 찾기 쉽게). PPT 텍스트 추출 결과는 `.<파일명>_추출캐시.json`으로 캐싱 — 이미지 슬라이드 추출은 비전 호출(유료)이라 재실행 때 두 번 내면 안 됨. PDF는 참고자료로만 목록.
- 저장물은 `projects/`가 gitignore라 커밋 안 됨(개인 테스트 데이터).

**버그 1 — HCX 비전이 100% 실패하고 있었음 (조용히)**:
- `dataUri.data`에 `data:<mime>;base64,` 접두어 없이 순수 base64만 보내 HCX가 전량 400(`40001`)으로 거절. 실패 시 빈 문자열을 반환하는 안전 모드 때문에 로그상 "이미지에 글자 없음"과 구분 불가 → **이미지 전용 PPT 5개의 추출이 조용히 실패**.
- 처음엔 원인을 "PowerPoint의 EMF/WMF 포맷"으로 **오진해 사용자에게 보고까지 함**. 실제로 열어보니 EMF는 0장, 전부 PNG/JPEG였음. 결정적 증거는 사용량 로그의 **비전 성공 0건/92건**.
- 수정: 접두어 추가 + 실제 `content_type` 전달 + HCX가 못 읽는 포맷은 Pillow로 PNG 변환 + **4xx/5xx 응답 본문 로깅**(이게 없어서 안 보였음). 슬라이드당 비전 3장 상한 + 텍스트 50자 이상인 장표는 비전 생략(비용).

**버그 2 — 대본의 26%가 이웃 슬라이드 내용을 말하고 있었음**:
- 슬라이드를 묶어서 요청하면 모델이 어떤 장은 건너뛰고 어떤 장은 두 줄로 쪼개서 **정렬이 통째로 밀림**. "넣은 개수 == 나온 개수" 검증으로도 못 잡음(하나 건너뛰고 하나 쪼개면 개수는 동일).
- 그 전에 19장을 통째로 넣었을 땐 모델이 TOON을 버리고 줄글로 써서 **19장짜리가 1장으로 저장**되기도 했음. 게다가 배치 스크립트가 *입력* 장수를 결과인 양 보고해서 이 유실이 "성공"으로 보였음.
- 수정: **슬라이드 한 장씩 요청**(한 장만 보내면 무슨 응답이 오든 그 장의 대본 → 정렬이 구조적으로 보장). 한 장 요청엔 **TOON을 쓰지 않음**(응답 전체가 곧 대본. 껍데기를 요구했더니 내용은 완벽한데 형식 위반으로 19장 중 18장 폐기). 위치는 라벨이 아니라 **지시문으로 프롬프트 맨 뒤에**(라벨로 주면 무시하고 19장 중 16장이 "안녕하세요"로 시작). 이웃 슬라이드 내용은 넘기지 않음(넘겼더니 그 내용의 대본을 써버려 정렬 재파괴).
- 검증: AHP 19장 기준 **1장 → 19/19**, 정렬 정확, 중간 인사 0건.
- 신규 테스트 `tests/test_toon_parser.py`, `tests/test_full_generation_chunking.py`, `tests/test_image_text_extractor.py` — 위 실측 사례를 전부 회귀 테스트로 고정. **pytest 76건 통과.**

**최종 결과 (2026-07-23)**: PPT 14개 전부 재생성 완료, **14/14 완전**(총 262장). 저장 위치는 각 PPT 바로 옆 `<파일명>_대본.txt`.
- 밀림 의심 25장(10%)은 전수 확인 결과 **전부 오탐** — 슬라이드 템플릿 푸터("Artificial Intelligence, Assembled Intelligence" 등)가 모든 장에 반복돼 이웃과 어휘가 겹친 탓. 실제 내용은 자기 슬라이드와 일치. 애초에 한 장씩 생성하므로 구조적으로 밀릴 수 없음.
- 추출 장수 < PPT 장수인 자료가 있음(예: With_Corona 12/19, 물류 9/10) — 텍스트도 이미지도 없는 빈/간지 슬라이드라 정상.
- 처리 안 한 PDF 3건: `민실/물류유통관리론/발표대본.pdf`, `민실/창업과사회적경제/통합자료.pdf`, `진순/부산대_체교과_교수지도안_발표/...pdf` (대본 생성 대상 아님, 참고자료).
- **HCX 비용(이 작업 전체)**: 1,062회 호출 / 1,250,062 토큰(입력 1,073,233 + 출력 176,829) → **2,226원(VAT 별도) / 2,448원(VAT 포함)**. 진단·재작업 반복분이 포함된 값이고, 한 장씩 생성으로 바꾸면서 호출 수가 늘었음(정렬 정확도와 맞바꾼 비용).

**어투(격식체) 수정 (2026-07-23, 사용자 피드백)**:
- 사용자가 대본이 어색하다고 지적: 오프닝 "안녕하세요 여러분 저는 송치웅이고요"(해요체·풀어짐) → "안녕하십니까. 이번 ClipRoute 발표를 맡은 송치웅입니다"(발표 관례)로, "~해보았고요" 같은 해요체 어미도 전부 격식체로.
- 원인: 프롬프트에 `발표 스타일: 격식체`라는 **단어만** 줘서 모델이 제멋대로 해석해 해요체로 흘러내림. 어미 정의가 없었음.
- 수정: 어투 정의를 `src/clova/styles.py` 한 곳으로 모으고(전체 생성/부분 재생성/고도화 공용), "모든 문장을 ~습니다/~입니다로 끝맺고 ~이고요/~해요는 금지"처럼 **어미를 문장으로 못박아** 프롬프트 맨 뒤 `[반드시 지킬 것 — 말투]`에 주입. 오프닝은 예시 문형("이번 OOO 발표를 맡은 OOO입니다")까지 제시.
- **ClipRoute만 재생성**(사용자 요청 — 비용 절약): 해요체/구어체 어미 잔여 **0건** 확인. 재생성 비용 약 71원(VAT 별도).
- ⚠️ **나머지 13개 대본은 아직 옛 해요체 톤 그대로**임(재생성 안 함). 코드는 고쳐졌으니 재생성하면 격식체로 나옴. 필요하면 배치 재실행(추출 캐시 있어서 비전 비용 없음, 대본 생성 비용만).
- 테스트 `tests/test_styles.py` 신규 — 어미 지시가 프롬프트에 실제 주입되는지 검증. **pytest 79건 통과.**

## ✅ 완료 (2026-07-21): Fable5 다각도 재검토 + 발견 문제 수정 + Fable5.md 코칭 문서

사용자가 "프로젝트 전체 재점검, 하위 모델 써서"라고 요청 → 서브에이전트 3명(정확성/버그, 보안/신뢰성, 테스트/아키텍처)을 병렬로 돌려 심층 검토하고, 발견된 문제 중 **정확성 버그 + 값싼 보안 개선**을 실제로 수정했다. 프로덕션 하드닝(이벤트루프 블로킹, 레이트리밋, 업로드 본문 크기 등)은 아직 프론트/배포 전이라 tech-debt-tracker에 문서화만 함.

**핵심으로 고친 것 (대부분 최근 라운드에 새로 넣은 코드의 버그):**
- 장단음 카테고리가 사실상 죽은 코드였음 — `is_different`와 무관하게 판정하도록 순서 변경. **실제 표준국어대사전 API로 검증: 사건/정보/가구가 이제 장단음으로 잡힘(예전 로직이면 0개, 이제 정상 발동).**
- `/api/analysis/words` stdict 무제한 fan-out → 캐시 + 상한(40) 추가.
- HCX 클라이언트 4개에 `use_fallback` 가드 없던 것 → 추가(CI 실네트워크 호출 테스트 2개도 오프라인·결정적으로 바뀜).
- phantom 슬라이드 `source_content=None`이 `"Slide 2: None"`으로 재전송되던 것 → 방어.
- stdict `search.do`가 조사 붙은 단어엔 빈 본문을 줘서 `.json()`이 터지던 것 → 빈 본문 가드. XML은 `response.content`로 파싱(인코딩 안전).
- 손상 PDF/DOCX 업로드 raw 500 → 422. 예외 메시지 응답 노출 제거. 인증 상수시간 비교(hmac). `finally` os.remove 방어. SQLite WAL+timeout. `_db_smoke_test.py` 엔드포인트 픽스. `apikey*` gitignore.

**문서:** `Fable5.md` 신규(하위 모델용 코칭 — 이 프로젝트 실제 버그에서 뽑은 11개 재발방지 규칙). `docs/product-specs/*` 코드와 어긋난 부분 갱신. tech-debt-tracker에 수정/문서화 항목 정리.

**검증:** pytest 44 → **49건**(회귀 테스트 5개 추가: 장단음 reachability, category=None, 손상 docx 422, project-not-found 404 등). 실제 stdict API로 장단음 발동 + 캐시 동작 라이브 확인.

**알아둘 한계(정직하게):** ETRI 키가 없으면 fallback 단어 추출이 조사를 못 떼고 단일 글자를 안 뽑아서, 카테고리(특히 장단음) 커버리지가 크게 떨어짐 — ETRI 키가 있으면 개선됨. 장단음은 동음이의어 첫 결과만 대표로 씀(밤/눈 같은 단어는 단음 쪽이 먼저 잡힘).

> 아직 커밋/푸시 진행 중. (이 라운드는 별도 PR 없이 main 직접 반영 예정 — 사용자 지시 따름)

## ✅ 머지 완료 (2026-07-21) — PR #7

[PR #7](https://github.com/chiung22/SpeaKO/pull/7) `feat/db-persistence-figma-pronunciation-categories` 브랜치로 머지 완료. pytest 44건 통과 상태로 `main` 반영. 이번 라운드 핵심 내용:

- **영속성 계층(DB)**: SQLite + SQLAlchemy 도입, `projects`/`slides`/`difficult_words`/`pronunciation_evaluations` 테이블. `project_id` 기준으로 전체 API(대본 생성/재생성/단어분석/발음평가)가 이어짐. 히스토리 조회용 `GET /api/projects`, `GET /api/projects/{id}` 추가. 스키마는 [db-schema.md](docs/generated/db-schema.md).
- **인증**: `X-API-Key` 헤더 검증(`SPEAKO_API_KEY`, fail-open — 미설정 시 로컬 개발용으로 인증 꺼짐, 배포 전 반드시 채워야 함).
- **CI**: `.github/workflows/tests.yml` 추가. 첫 4번의 실행이 **GitHub Actions 지출 한도($12) 소진**으로 실패함("recent account payments have failed or your spending limit needs to be increased") — 코드/테스트 문제 아님. 원인은 저장소가 **프라이빗**이라 월 2,000분 무료 제공분이 있고 그걸 넘으면 과금되는 구조였기 때문. **레포를 퍼블릭으로 전환**하면서 해결됨 — 퍼블릭 저장소는 GitHub Actions가 완전 무료(무제한)라 지출 한도 자체가 적용 안 됨. 전환 전에 git 히스토리 전체(실제 키 값, `.env`, `apikey_발급.txt`)를 검사해서 커밋된 시크릿이 없는 걸 확인 후 진행함. 전환 직후 이전에 실패했던 워크플로우 재실행 → **44 passed로 정상 확인**.
- **Figma 기반 API 재설계**: 실제 디자인 화면 확보 후 `POST /api/projects`가 PPT/PDF 업로드, PPT 없이 topic+outline만 입력, 완성된 대본 직접 붙여넣기(`script_text`)/파일 업로드(`mode=coaching`, DOCX/TXT/PDF) 세 방식 모두 지원하도록 재설계. 전체 대본 생성도 부분 재생성처럼 `style`(격식체/편안한 말투)+`extra_requirement` 지원.
- **오디오 MP3/M4A 지원**: ffmpeg 변환 파이프라인 추가(배포 서버에 ffmpeg 설치 필요).
- **발음 코칭 카테고리별 하이라이트**: 장단음(국립국어원 표준국어대사전 API)/연음(한글 자모 분해)/표기-발음불일치 3분류, `/api/analysis/words` 응답에 집계(`summary`) 포함.
- **버그 수정 2건**: ETRI 미설정 시 실제 대본과 무관한 고정 단어 반환하던 문제, topic/outline-only 프로젝트 전체 재생성 시 슬라이드 유실되던 문제.

다음에 이어서 할 만한 것 (아래 "보류" 섹션 참고):
- TTS 엔드포인트 연결 — `CLOVA_VOICE_CLIENT_ID`/`SECRET` 발급 대기
- AI 생성 정성 피드백/팁(Coach View Page/Feedback Page) — 새 HCX 프롬프트 설계 필요
- 사용자 계정/소유권 기반 인가 — 프론트엔드 연동 시 필요

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
