# 프론트엔드 연동 가이드 (AI 서버 API)

SpeaKO AI 서버(FastAPI)의 엔드포인트 계약입니다. 프론트엔드가 이 문서만 보고 붙일 수 있게 정리했습니다.

- **Base URL**: 배포 주소 (로컬은 `http://localhost:8000`)
- **인증**: `SPEAKO_API_KEY`가 설정돼 있으면 모든 `/api/*` 요청에 `X-API-Key: <키>` 헤더 필요. 미설정이면 인증이 꺼집니다(로컬 개발용).
- **CORS**: 배포 프론트 도메인이 서버의 `CORS_ALLOW_ORIGINS`에 있어야 브라우저가 응답을 받습니다. 기본값에 `https://speakofront.vercel.app`과 `*.vercel.app`이 포함돼 있습니다.
- **실패 규약**: 잘못된 입력 `422`, 대상 없음 `404`, 크기/길이 초과 `413`, **요청이 너무 잦음 `429`**, 외부 AI 호출 실패 `502`.

### 요청 횟수 제한 (429)

유료 AI 호출 비용을 막기 위한 것입니다. 넘으면 `429`와 함께 **`Retry-After` 헤더(초)** 가 옵니다 — 그 시간만큼 기다렸다 재시도하세요.

| 대상 | 상한 |
|---|---|
| 대본 생성·재생성, 프로젝트 생성, 단어 분석, 발음 평가·피드백 (POST) | 분당 60건 |
| 그 외 조회 | 분당 300건 |

**생성 상태 폴링(`GET /api/script/jobs/{id}`)과 CORS preflight는 위 60건에 포함되지 않습니다** — 1~2초 간격 폴링을 그대로 하셔도 됩니다.

> ⚠️ 스프링을 거쳐 호출하는 구조라면, **스프링이 `X-Forwarded-For` 헤더를 그대로 넘겨줘야** 사용자별로 집계됩니다. 안 넘기면 모든 사용자가 하나의 상한을 나눠 쓰게 됩니다.

### 요청 본문 크기

전체 본문이 **25MB**를 넘으면 `413`입니다(파일 자체 상한은 아래 각 API 참고). 개별 파일 상한을 지켜도 여러 필드를 합쳐 25MB를 넘기면 걸립니다.

### ⚠️ 스프링을 거쳐 호출한다면 (백엔드 확인 필요)

프론트 → 스프링 → AI 서버 구조라면, 스프링이 아래를 그대로 통과시켜야 합니다. 하나라도 막히면 AI 서버까지 오지도 않습니다.

| 항목 | 필요한 설정 |
|---|---|
| **multipart 크기** | Spring Boot 기본값이 **파일 1MB / 요청 10MB**로 AI 서버(20MB/25MB)보다 훨씬 작습니다. `spring.servlet.multipart.max-file-size=25MB`, `spring.servlet.multipart.max-request-size=30MB`로 올려야 20MB PPT가 통과합니다. |
| **`X-Forwarded-For`** | 그대로 전달해야 사용자별로 요청 횟수가 집계됩니다. 안 넘기면 전원이 분당 60건을 나눠 씁니다. |
| **`X-API-Key`** | 그대로 전달(또는 스프링이 서버 키 주입). |
| **`Retry-After`** | `429` 응답의 이 헤더를 삼키지 마세요. 재시도 간격 계산에 씁니다. |
| **상태코드** | `202`/`413`/`422`/`429`/`502`를 그대로. 특히 **`202`를 `200`으로 바꾸면 프론트가 폴링을 시작하지 않습니다.** |
| **폴링 경로** | `GET /api/script/jobs/{id}`를 통과시켜야 합니다(1~2초 간격 호출). |
| **타임아웃** | `POST /api/evaluation/audio`는 Azure가 녹음을 실시간의 약 0.5배 속도로 처리합니다. **실측: 5분 녹음 → 148초**, 상한인 15분 녹음이면 약 7분. 이 경로만 읽기 타임아웃을 **600초**로. |

### 입력 길이 상한

유료 AI 호출 비용을 막기 위해 서버가 강제합니다. **넘으면 `422`** (파일에서 추출한 대본이 넘으면 `413`).
프론트에서 미리 글자 수를 세어 막아주면 사용자가 긴 글을 다 쓰고 나서 거절당하는 일을 피할 수 있습니다.

| 필드 | 상한 |
|---|---|
| `script_text` (붙여넣기 대본), 파일에서 추출한 대본 | 50,000자 |
| 슬라이드 `script` / `source_content` | 20,000자 |
| `outline` (목차·가이드라인) | 5,000자 |
| `extra_requirement` (추가 요구사항) | 1,000자 |
| `topic` (발표 주제), `project_name` | 200자 |
| `audience` (발표 대상) | 100자 |
| `presentation_time` | 1~180 (분) |
| `project_id` / `target_slide` / `position` | 1 이상 |
| 프로젝트당 슬라이드 수 (PPTX/PDF 업로드) | 100장 (초과 시 `413`) |

### 단어 목록 응답 (`POST /api/analysis/words`)

`Coach View Page` 단어 목록 탭에 필요한 값이 전부 들어 있습니다.

```json
{ "word": "특정", "phoneme": "[특쩡]", "category": "표기-발음불일치",
  "description": "경음화: 받침 뒤에 오는 예사소리(ㄱ, ㄷ, ㅂ, ㅅ, ㅈ)가 된소리로 바뀌어 발음됩니다." }
```

- `category`: `"장단음"` / `"연음"` / `"표기-발음불일치"` / `null`(철자=발음). **색은 프론트가 정합니다** (장단음 `#F7358E`, 연음 `#0072F2`, 표기불일치 `#F79322`).
- `phoneme`: 장단음이면 **장음 기호 `ː`가 해당 음절 뒤에 붙습니다** (`구성` → `[구ː성]`).
- `description`: 구체적 음운 현상 이름 + 설명. 규칙 판정에 실패하면 "표기와 발음이 다릅니다…"로 물러납니다.
- `summary`의 카테고리별 개수를 필터 칩 숫자에 그대로 쓰면 됩니다.

같은 값이 `GET /api/projects/{id}`의 `difficult_words`에도 저장돼 내려갑니다.

### 발음 평가 응답 (`POST /api/evaluation/audio`)

`Feedback Page`에서 틀린 부분을 **원본·인식 양쪽에** `#FF7676`으로 강조하는 데 필요한 값입니다.

```json
{ "reference_text": "Slide 1: 안녕하세요 여러분",
  "recognized_text": "안녕하세요 그리고",
  "words_detail": [
    { "word": "여러분", "error_type": "Omission",
      "reference_span": [12, 15], "recognized_span": null }
  ] }
```

- `reference_span` / `recognized_span`은 **`[시작, 끝]` 문자 인덱스**입니다. `null`이면 그쪽 텍스트에는 없다는 뜻입니다(`Omission`은 원본에만, `Insertion`은 인식에만).
- ⚠️ 오프셋은 **응답의 `reference_text` 기준**입니다. 대본을 이어붙일 때 `"Slide N: "` 접두어가 붙으므로, 프론트가 따로 가지고 있는 원본 문자열로 자르면 엉뚱한 곳이 나옵니다. **반드시 응답의 `reference_text`를 쓰세요.**
- 위치를 못 찾으면 `null`입니다(문장부호 차이 등). 엉뚱한 곳을 칠하지 않도록 일부러 비웁니다.

### AI 피드백 응답 (`POST /api/evaluation/{id}/feedback`)

`practice_tips`는 `Coach View Page` 우측 "발음 팁"(아이콘 + 제목 + 설명 **4개**)에 대응합니다.
피그마 갱신본 ㊹ "음성 파일 AI 피드백 (자음/끝소리/강세억양/속도)"과 같은 4분류가 한 개씩 나옵니다.

```json
"practice_tips": [
  { "key": "consonant", "title": "명확한 자음 발음", "description": "'ㄷ, ㅈ, ㅅ' 계열 자음을 더 또렷하게 발음해보세요." }
]
```

**아이콘은 `key`로 매핑하세요** — `title`은 매번 달라지므로 제목으로 아이콘을 고르면 안 됩니다.

| `key` | 뜻 | 아이콘 |
|---|---|---|
| `consonant` | 자음 발음 | 피그마 기존 (파형) |
| `ending` | 끝소리 | 피그마 기존 (음파) |
| `intonation` | 강세·억양 | 피그마 기존 (막대) |
| `speed` | 말하기 속도 | 피그마 갱신본 "천천히 강조하기" |
| `general` | 분류 없음 (옛 데이터 포함) | 기본 아이콘 |

**성량(`volume`)은 내려가지 않습니다.** 녹음 음량은 마이크와의 거리에 좌우돼서 발표자의 실제 목소리 크기를 뜻하지 않고, Azure가 주는 점수에도 성량 정보가 없어 팁을 쓰면 근거 없는 조언이 됩니다. 아이콘을 준비하지 않으셔도 됩니다.

---

## 전체 흐름 한눈에

```
[AI 대본 생성]
POST /api/projects            파일/주제 업로드 → project_id
POST /api/script/full         생성 시작 → job_id (즉시 202)
GET  /api/script/jobs/{id}    1~2초마다 폴링 → completed면 대본
PUT  /api/projects/{id}/slides/{n}   사용자가 고친 대본 저장
POST /api/script/partial      슬라이드 하나만 다시 생성
PUT  /api/projects/{id}       프로젝트명 수정
GET  /api/projects/{id}/script.docx      대본 다운로드 (.docx)
GET  /api/projects/{id}/highlight.docx   하이라이팅 대본 다운로드 (.docx)

[발표 발음 코칭]
POST /api/analysis/words      발음 주의 단어 + 발음기호 (하이라이팅용)
POST /api/tts/word            단어 발음 듣기 → MP3 바이트 (스피커 버튼, voice/speed 선택 가능)
GET  /api/tts/voices          발음 듣기 목소리 목록 + 속도 범위 (설정 화면용)
POST /api/evaluation/audio    녹음 업로드 → 점수 + 인식 텍스트
POST /api/evaluation/{id}/feedback   AI 코칭 피드백

[마이페이지]
GET    /api/projects          대본 생성 기록
GET    /api/evaluations       발표 코칭 내역
GET    /api/projects/{id}     상세(대본·단어·평가 전부)
DELETE /api/projects/{id}     기록 삭제
```

---

## 1. 프로젝트 생성 — `POST /api/projects`

`multipart/form-data`. 세 가지 입력 방식 중 하나를 씁니다.

| 방식 | 보낼 것 | 쓰이는 화면 |
|---|---|---|
| ① PPT/PDF 업로드 | `file` (`.pptx`/`.pdf`) + `topic`(권장) | AI 대본 생성 (PPT O) |
| ② 자료 없이 주제만 | `topic` + `outline` | AI 대본 생성 (PPT X) |
| ③ 완성된 대본 | `script_text`, 또는 `mode=coaching` + `file`(`.docx`/`.txt`/`.pdf`) | 발표 발음 코칭 |

기타 필드: `project_name`(선택).

> ⚠️ **`.ppt`(구버전)는 지원하지 않습니다.** `.pptx`로 저장해서 올려야 합니다. 업로드 상한 20MB.

**응답**
```json
{ "success": true, "project_id": 12,
  "data": { "metadata": {"topic": "...", "keywords": []},
            "slides": [{"slide_number": 1, "content": "슬라이드 원문"}] } }
```

---

## 2. 대본 생성 (비동기) — `POST /api/script/full`

생성은 20~30초 걸리므로 **요청을 붙잡지 않습니다.** 접수번호를 즉시 받고 상태를 물어보는 방식입니다.

**요청** (`application/json`)
```json
{ "project_id": 12, "presentation_time": 8, "style": "formal",
  "topic": "발표 주제", "audience": "교수님", "extra_requirement": "" }
```
- `style`: `"formal"`(격식체) 또는 `"casual"`(편안한 말투) — 필수. 구버전 한국어 값(`"격식체"`/`"편안한 말투"`)도 계속 받습니다. 그 외 값은 422
- `topic`/`audience`/`extra_requirement`: 선택. `topic`을 비우면 프로젝트에 저장된 주제를 씁니다.

**응답 `202`** — 기다리지 않고 바로 옵니다.
```json
{ "success": true, "job_id": "abc123...", "status": "processing" }
```

### 2-1. 상태 폴링 — `GET /api/script/jobs/{job_id}`

1~2초 간격으로 호출하며 스피너를 돌립니다.

```json
// 처리 중
{ "success": true, "job_id": "abc123", "status": "processing",
  "step": 3, "total_steps": 4, "step_label": "대본 작성" }

// 완료
{ "success": true, "job_id": "abc123", "status": "completed",
  "step": 4, "total_steps": 4, "step_label": "완료", "project_id": 12,
  "data": { "slides": [{"slide_number": "1", "script": "안녕하십니까..."}],
            "missing_slide_numbers": [],
            "thin_source_slide_numbers": ["20"] } }

// 실패
{ "success": true, "job_id": "abc123", "status": "failed", "error": "대본 생성에 실패했습니다." }
```
- `status`가 `processing`이 아니면 폴링을 멈춥니다.
- 없는 `job_id`는 `404`.
- **`step` / `total_steps` / `step_label`** — 피그마 로딩 화면의 4단계 표시용입니다.
  `① 파일 수령 → ② 텍스트 추출 → ③ 대본 작성 → ④ 완료`
  ①②는 `POST /api/projects`(업로드·추출)에서 이미 끝난 뒤에 이 화면이 뜨므로, **작업은 항상 3단계에서 시작**합니다. 피그마도 ①②는 채워진 상태로 그려져 있습니다.
  > 하이라이팅(`/api/analysis/words`)과 음성 분석(`/api/evaluation/audio`)은 **동기 호출이라 폴링할 job이 없습니다.** 그 두 로딩 화면의 단계 표시는 **프론트에서 연출**합니다 — 아래 참고.

### 동기 API의 로딩 4단계는 프론트에서 연출합니다 (결정, 2026-08-09)

대본 생성만 위처럼 실제 단계를 줍니다. 하이라이팅·음성 분석은 요청 하나가 끝날 때까지 연결을 붙잡는 **동기 호출**이라, 서버가 중간에 "2단계 끝났어요"라고 알릴 창구가 없습니다(응답이 한 번뿐입니다). 비동기로 바꾸면 프론트·스프링·명세가 함께 바뀌어야 해서 **시연 일정상 하지 않기로** 했습니다.

**단계 순서 자체는 사실입니다** — 서버가 실제로 그 순서로 일합니다. 연출로 채우는 건 타이밍뿐입니다.

| 화면 | 실제 소요 | 연출 방법 |
|---|---|---|
| 발음 하이라이팅 | 2~5초 | 1→2단계를 0.5초 간격으로 넘기고, 3단계에서 응답 대기 → 응답 오면 4단계 |
| 음성 분석 | **최대 7분** | 위와 같되, **"최대 7분 걸릴 수 있어요" 안내와 경과 시간(mm:ss)을 반드시 함께** 표시 |

⚠️ **음성 분석은 안내 문구가 필수입니다.** 녹음 길이에 비례해서 최대 7분이 걸리는데(15분 녹음 기준), 아무 설명 없이 3단계에서 7분을 머무르면 사용자는 멈춘 줄 알고 새로고침합니다. 가짜 단계를 빠르게 넘기는 것보다 **예상 시간 + 경과 시간**을 보여주는 쪽이 훨씬 덜 답답합니다.

> 혹시 사용자가 도중에 이탈해도 **결과는 서버 DB에 저장됩니다.** `GET /api/evaluations`(코칭 내역)에서 확인할 수 있으니, 실패 화면에 "마이페이지에서 확인하세요"를 안내해 주세요.
- `data.missing_slide_numbers`에 번호가 있으면 그 슬라이드는 대본이 비어 있습니다 — "다시 생성" 안내 후 `POST /api/script/partial`로 그 장만 재생성하면 됩니다.
- `data.thin_source_slide_numbers`에 번호가 있으면 그 슬라이드는 **PPT에서 읽은 내용이 제목 한 줄뿐이라 대본의 근거가 없었던** 장입니다. 대본은 비어 있지 않지만 "화면에 정리한 내용을 보시겠습니다" 수준의 일반적인 안내문이니, **"이 슬라이드는 내용을 직접 확인·보완해 주세요"** 배지를 띄워 주세요.
  - 왜 필요한가: 이런 장에 모델이 그럴듯한 대본을 지어내면 발표자가 그대로 읽다가 사실이 아닌 말을 하게 됩니다. 실측으로 텍스트가 0인 "기술 스택" 장에 쓰지도 않은 스택 이름이 통째로 들어간 적이 있어서, 지어내는 대신 일반적인 문장으로 두고 이 필드로 알리는 방식을 택했습니다.
  - `missing_slide_numbers`와 달리 재생성해도 결과는 같습니다(원문이 없는 게 원인). 발표자가 슬라이드 내용을 추가하거나 `POST /api/script/partial`의 `extra_requirement`로 내용을 직접 알려줘야 채워집니다.
- ⚠️ 작업 상태는 서버 메모리에 있습니다. **서버가 재시작되면 진행 중이던 작업은 사라지므로**, 폴링이 404를 받으면 "다시 시도"를 안내해 주세요.

---

## 3. 대본 편집

| 목적 | 요청 |
|---|---|
| 사용자가 고친 대본 저장 | `PUT /api/projects/{id}/slides/{n}` — body `{ "script": "고친 내용" }` |
| **프로젝트명 수정** | `PUT /api/projects/{id}` — body `{ "name": "중간발표 최종본" }` (빈 문자열은 `422`) |
| 슬라이드 추가 | `POST /api/projects/{id}/slides` — body `{ "position": 2, "script": "" }` (position 없으면 맨 끝) |
| 슬라이드 삭제 | `DELETE /api/projects/{id}/slides/{n}` |

- 셋 다 응답에 **정리된 전체 슬라이드 목록**이 옵니다: `{ "data": { "slides": [...] } }`
- 추가/삭제 후 번호는 **1..N으로 자동 재정렬**됩니다.
- 마지막 한 장은 삭제할 수 없습니다 (`422`).
- PPT 없이 만든 프로젝트(전체 대본 한 덩어리)는 `slide_number = 1`에 저장하면 됩니다.

### 전체 대본 — 직접 이어붙이지 마세요 (`full_script`)

'대본 확인' 화면처럼 **슬라이드를 합친 전체 대본**이 필요하면 `GET /api/projects/{id}` 응답의 `full_script`를 쓰세요. 서버가 `slide_number` 순서대로 이어붙여 내려줍니다.

```json
{ "data": {
    "slides": [ {"slide_number": 1, "script": "첫 장입니다."}, {"slide_number": 2, "script": "둘째 장입니다."} ],
    "full_script": "첫 장입니다.\n둘째 장입니다."
} }
```

- 대본이 아직 생성되지 않았으면 **빈 문자열**입니다(키는 항상 있습니다).
- 대본이 없는 슬라이드는 건너뜁니다 — 빈 줄이 생기지 않습니다.

⚠️ **직접 합치실 경우 `"Slide 1:"` 같은 라벨을 붙이지 마세요.** 그 텍스트를 `reference_text`로 되보내면 라벨까지 *읽어야 할 말*로 채점돼서, 없는 누락이 무더기로 생기고 결과 화면에 `"Slide 1"`이 빨갛게 칠해집니다. 합치는 규칙을 한 곳(서버)에만 두려고 이 필드를 만들었습니다.

### 슬라이드 부분 재생성 — `POST /api/script/partial`
```json
{ "project_id": 12, "target_slide": 3, "style": "formal",
  "audience": "면접관", "extra_requirement": "더 짧게" }
```
기존 대본을 다시 보낼 필요 없이 서버에 저장된 것을 씁니다. (동기 호출, 몇 초)

### 3-1. `.docx` 다운로드

| 목적 | 요청 | 파일명 |
|---|---|---|
| 대본 저장 | `GET /api/projects/{id}/script.docx` | `{프로젝트명}.docx` |
| 하이라이팅 대본 저장 | `GET /api/projects/{id}/highlight.docx` | `하이라이팅_{프로젝트명}.docx` |

- 응답은 JSON이 아니라 **docx 바이트**입니다. `Content-Disposition: attachment`가 붙어 있어서 `<a href>`나 `window.open`으로 바로 받아도 됩니다.
- 파일명은 **프로젝트명**입니다(피그마 ㉒ "13의 제목명.docx로 저장"). 이름을 바꾸려면 위 `PUT /api/projects/{id}`를 먼저 부르세요.
- 하이라이팅본은 발음 주의 단어에 **피그마와 같은 색**을 칠하고 범례를 붙입니다 — 장단음 `F7358E` / 연음 `0072F2` / 표기-발음불일치 `F79322`.
- 아직 대본이 없으면 `422`.

---

## 4. 발음 주의 단어 — `POST /api/analysis/words`

body: `{ "project_id": 12 }`

```json
{ "success": true, "project_id": 12,
  "data": {
    "words": [{ "word": "발전", "phoneme": ["발쩐"], "category": "표기-발음불일치" }],
    "summary": { "장단음": 6, "연음": 1, "표기-발음불일치": 3 }
  } }
```
- `category`: `"장단음"` / `"연음"` / `"표기-발음불일치"` / `null`(철자=발음)
- 하이라이트 범례·요약 개수는 `summary`를 그대로 쓰면 됩니다.

---

## 4-1. 발음 듣기 — `POST /api/tts/word`

단어 목록의 **스피커 버튼**용입니다. JSON이 아니라 **MP3 바이트를 그대로** 돌려줍니다.

body: `{ "project_id": 12, "word": "각자", "voice": "고은", "speed": -2 }`

| 필드 | 필수 | 설명 |
|---|---|---|
| `word` | ✅ | 화면에 보이는 철자. 최대 100자 |
| `project_id` | | 있으면 이 프로젝트에 저장된 발음기호를 먼저 씁니다(권장 — 재분석이 없어 가장 빠릅니다) |
| `pronunciation` | | 합성할 발음을 직접 지정. `"[여칼]"`처럼 대괄호가 있어도 됩니다 |
| `voice` | | 목소리: `"동현"`·`"대성"`(남성) / `"혜리"`·`"고은"`(여성). 미지정 시 서버 기본 화자 |
| `speed` | | 속도 `-5`(빠르게)~`+5`(느리게), 기본 `0`. 범위 밖은 422 |

응답: `Content-Type: audio/mpeg` + MP3 바이트.

**목소리 목록은 `GET /api/tts/voices`로 받으세요** — `{"voices": [{"name": "동현", "gender": "남성"}, …], "speed": {"min": -5, "max": 5, "default": 0}}`.
설정 화면의 선택지를 하드코딩하지 말고 이걸 그리면, 화자 구성이 바뀌어도 프론트 수정이 없습니다.
`name` 값을 그대로 `voice`에 넣으면 됩니다.

```js
const res = await fetch(`${API}/api/tts/word`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": KEY },
  body: JSON.stringify({ project_id, word }),
});
new Audio(URL.createObjectURL(await res.blob())).play();
```

**⚠️ 들려주는 건 철자가 아니라 표준 발음입니다.** `각자`를 요청하면 `[각짜]`가, `책임`을 요청하면
`[채김]`이 재생됩니다. Clova Voice가 한국어 음운 규칙을 일부만 적용해서(실측: 격음화·유음화는
적용, 경음화·연음은 미적용), 철자를 그대로 합성하면 틀린 발음이 나가기 때문입니다.
철자 그대로 들려주고 싶으면 `pronunciation`에 철자를 넣으세요.

**⚠️ 장단음 단어는 소리로 구분되지 않습니다.** `[최ː소]`의 장음 기호 `ː`는 Clova Voice 평문
입력으로 표현할 방법이 없어서 빼고 보냅니다. 즉 `최소`의 발음 듣기는 철자를 그대로 읽은 것과
같은 소리가 납니다(틀린 소리는 아니지만, 길게 읽으라는 정보가 소리에는 안 담깁니다).
실측(2026-08-09, 제로 대본): 주의 단어 19개 중 **11개가 장단음**이라 적은 비율이 아닙니다.
→ 장단음 단어는 화면에서 `[최ː소]`의 `ː`를 눈에 띄게 보여주거나 "첫 음절을 길게" 문구를
함께 띄워 주세요. 소리만으로는 전달되지 않습니다.

- 같은 단어를 다시 요청하면 서버 캐시에서 나갑니다(응답 헤더 `X-TTS-Cache: hit`). 프론트에서
  따로 캐싱하지 않아도 됩니다.
- 유료 경로라 **분당 60건 제한**에 포함됩니다(429). 스피커 버튼 연타는 프론트에서 막아주세요.
- 합성 실패 시 `502`.

---

## 5. 녹음 평가 — `POST /api/evaluation/audio`

`multipart/form-data`
- `project_id` (필수)
- `audio_file` (필수) — `.webm` / `.wav` / `.mp3` / `.m4a`, **최대 20MB이면서 15분 이내**
- `slide_number` (선택) — 슬라이드별로 나눠 녹음할 때 그 번호
- `reference_text` (선택)

평가 기준 대본 우선순위: `reference_text` > `slide_number`(그 장 대본만) > 대본 전체.
슬라이드 하나만 읽었는데 전체를 기준으로 채점하면 완성도가 바닥으로 나오므로, 부분 녹음이면 `slide_number`를 넣어주세요.

### 업로드 제한 — 크기와 길이 **둘 다** 봅니다

| 제한 | 값 | 초과 시 |
|---|---|---|
| 파일 크기 | **20MB** | `413` |
| 녹음 길이 | **15분** | `422` |

**왜 둘 다 있나요?** 같은 20MB라도 녹음 품질에 따라 재생 길이가 3배 넘게 차이 납니다(실측: 폰 녹음 124kbps는 21분, 브라우저 녹음 40kbps는 67분). 그런데 평가 시간은 **길이에 비례**하므로, 크기만 막으면 처리 시간이 무제한이 됩니다.

두 경우 모두 `detail`에 사용자에게 그대로 보여줄 수 있는 한국어 문구가 들어 있습니다.

```json
413 → { "detail": "파일 크기가 너무 큽니다. (최대 20MB) 슬라이드별로 나눠 녹음하시면 한 번에 올리는 분량이 줄어듭니다." }
422 → { "detail": "녹음이 너무 깁니다. (18.3분 / 최대 15분) 슬라이드별로 나눠 녹음하시면 한 번에 올리는 분량이 줄어듭니다." }
```

### 녹음 화면에 넣어주실 안내 문구 (hint text)

에러가 난 **뒤에** 알려주면 사용자는 이미 긴 녹음을 마친 뒤입니다. 녹음 시작 화면에 미리 띄워주세요.

> 한 번에 **15분, 20MB**까지 올릴 수 있어요. 발표가 길면 슬라이드별로 나눠 녹음해보세요.

- 브라우저에서 녹음 중이라면 **경과 시간을 표시**하고 15분에 가까워지면 알려주는 게 가장 확실합니다.
- 파일을 고르는 방식이라면 업로드 전에 `File.size`로 20MB를 먼저 걸러주세요. 서버까지 갔다 오는 시간이 절약됩니다.
- 길이는 프론트에서도 `<audio>`의 `duration`으로 미리 잴 수 있습니다. 미리 거르면 15분짜리 파일을 올리는 시간 자체가 없어집니다.

```json
{ "success": true, "project_id": 12, "evaluation_id": 5,
  "slide_number": 3,
  "overall_scores": { "accuracy": 87, "fluency": 82,
                      "completeness": 95, "pronunciation_score": 84 },
  "reference_text": "Slide 1: 안녕하세요 ...",
  "recognized_text": "실제로 인식된 문장",
  "words_detail": [{ "word": "발전", "accuracy_score": 52, "error_type": "Mispronunciation",
                     "reference_span": [12, 14], "recognized_span": [10, 12] }],
  "highlights": { "reference": [], "recognized": [],
                  "counts": { "omission": 0, "insertion": 0, "mispronunciation": 1, "error": 0 },
                  "has_errors": false },
  "deductions": { "factors": [], "counts": {}, "scores": {}, "primary": null } }
```
- ⚠️ 응답은 **`data`로 감싸지 않고 평평하게** 내려옵니다. (AI 피드백 API만 `data`로 감쌉니다)
- 🔴 **점수는 0~100 정수입니다. 화면에 그대로 쓰세요** (2026-08-15 변경).
  - 이전에는 등급(A~F)만 표기하고 숫자를 감췄는데, **`grades` 필드는 없어졌습니다.** 옛 코드가 `grades`를 읽고 있으면 `undefined`가 됩니다.
  - 소수점도 없어졌습니다. `87.4`가 아니라 `87`입니다 — `toFixed()`로 자르던 코드가 있으면 지우세요.
  - 원형 게이지 호(arc)의 채움 비율은 그대로 `pronunciation_score / 100`으로 계산하면 됩니다.
- 좌우 대조 화면의 하이라이트는 **`highlights`를 쓰세요.** `words_detail`로 직접 계산하지 않아도 됩니다 — 서버가 어디를 무슨 색으로 칠할지 정해서 내려줍니다. 자세한 내용은 아래 [4-1. 결과창 하이라이팅](#4-1-결과창-하이라이팅) 참고.
- `recognized_text`와 원본 대본을 좌우로 놓으면 "원본 ↔ 인식 텍스트" 비교 화면이 됩니다.
- `error_type`: `None`(정상) / `Mispronunciation`(발음이 흐림) / `Omission`(안 읽음) / `Insertion`(대본에 없는 말).
- 중간에 멈춰도 **읽은 부분까지만** 채점됩니다. 어디까지 읽었는지 알려줄 필요 없습니다.

---

## 4-1. 결과창 하이라이팅

**틀린 워딩은 빨간색입니다.** 어디를 무슨 색으로 칠할지는 서버가 정해서 `highlights`로 내려줍니다. `error_type`을 보고 프론트에서 규칙을 다시 세우지 마세요 — 화면마다 기준이 달라집니다.

```json
"highlights": {
  "reference":  [ { "word": "인프라", "start": 12, "end": 15, "type": "omission",
                    "level": "error", "reason": "대본에 있지만 말하지 않았습니다.",
                    "accuracy_score": 0 } ],
  "recognized": [ { "word": "음", "start": 6, "end": 7, "type": "insertion",
                    "level": "error", "reason": "대본에 없는 말을 했습니다.",
                    "accuracy_score": 0 } ],
  "counts": { "omission": 5, "insertion": 1, "mispronunciation": 2, "error": 6 },
  "has_errors": true
}
```

**`level`이 `"error"`인 것만 빨간색으로 칠하세요.**

| `type` | 뜻 | `level` | 색 |
|---|---|---|---|
| `omission` | 대본에 있는데 안 읽음 | `error` | 🔴 빨강 |
| `insertion` | 대본에 없는데 말함 | `error` | 🔴 빨강 |
| `mispronunciation` | 읽긴 했는데 발음이 흐림 | `warning` | 빨강 아님 (주황/밑줄 등) |

발음이 흐린 건 **단어를 틀리게 읽은 게 아닙니다.** 같은 빨강으로 칠하면 "대본을 틀리게 읽었다"는 잘못된 인상을 줍니다.

- `reference`는 **원본 대본**에, `recognized`는 **인식 텍스트**에 칠합니다. 누락은 원본에만, 삽입은 인식 쪽에만 나옵니다(당연히 — 안 읽은 말은 인식 텍스트에 없습니다).
- `start`/`end`는 **응답의 `reference_text` / `recognized_text` 기준** 문자 오프셋입니다. 대본을 이어붙일 때 `"Slide N:"` 접두어가 붙으므로, 따로 들고 있는 원본 문자열로 자르면 엉뚱한 글자가 빨개집니다.
- 이미 위치순으로 정렬돼 있습니다. 그대로 순회하면서 칠하면 됩니다.
- 위치를 확신할 수 없는 단어는 목록에서 빠집니다(엉뚱한 곳을 칠하느니 안 칠합니다). 그래서 **`counts`와 목록 길이가 다를 수 있습니다** — 뱃지 숫자는 `counts`를, 칠할 자리는 목록을 쓰세요.
- `reason`은 완성된 문장이라 툴팁에 그대로 넣으면 됩니다.

`GET /api/projects/{id}`의 평가 이력에도 같은 `highlights`가 들어 있어서, 지난 평가를 다시 열어도 같은 자리가 빨개집니다. `GET /api/evaluations`(코칭 내역 목록)에는 개수만(`highlight_counts`) 들어갑니다.

---

## 6. AI 코칭 피드백 — `POST /api/evaluation/{evaluation_id}/feedback`

```json
{ "success": true, "evaluation_id": 5, "cached": false,
  "data": {
    "summary": "전반적으로 또렷합니다...",
    "strengths": ["'평가'를 정확하게 발음하셨습니다."],
    "improvements": ["'발전'의 받침을 끝까지 발음하세요."],
    "practice_tips": ["거울을 보며 입 모양을 확인하세요."],
    "weak_words": [{ "word": "발전", "accuracy_score": 52, "error_type": "Mispronunciation" }],
    "deductions": { "...": "아래 참고" }
  } }
```
- 생성에 몇 초 걸립니다. 스피너를 띄워주세요.
- **이미 만든 피드백이 있으면 재생성하지 않고 그대로 반환**합니다(`cached: true`). 여러 번 눌러도 비용이 늘지 않습니다.

### 감점 요인 (`deductions`) — 상세 피드백 화면

"무엇 때문에 깎였는가"입니다. `/api/evaluation/audio` 응답에도 같이 들어 있어서, **피드백을 부르기 전에도 그릴 수 있습니다.**

```json
"deductions": {
  "factors": [
    { "key": "omission", "label": "대본 누락", "count": 5, "ratio_percent": 55.6,
      "affects": ["completeness"], "severity": "high",
      "examples": ["인프라", "첫째로", "확장성이"],
      "message": "대본에 있는 단어 5개를 읽지 않았습니다(대본의 55.6%). 완성도 점수가 그만큼 내려갑니다." }
  ],
  "counts": { "omission": 5, "insertion": 1, "mispronunciation": 2, "filler": 1, "pause": 1 },
  "scores": { "accuracy": 72, "fluency": 64, "completeness": 40, "pronunciation_score": 58 },
  "primary": "omission"
}
```

- `factors`는 **심각한 순으로 정렬**돼 있습니다. 위에서부터 그리면 제일 큰 원인이 먼저 보입니다.
- `message`는 **완성된 문장**입니다. 그대로 카드에 넣으세요. AI 피드백을 안 불렀거나 실패해도 이건 항상 나옵니다.
- `key`: `omission` / `insertion` / `mispronunciation` / `filler` / `pause` / `speech_rate` 여섯 가지. 아이콘 고를 때 쓰세요.
- `severity`: `high` / `medium` / `low`. 카드 강조에 쓰세요.
- ⚠️ **요인별로 몇 점 깎였는지는 안 내려갑니다.** Azure가 공개하지 않는 값이라 지어낼 수 없습니다. "누락 −12점"처럼 쓰지 마시고, `affects`가 가리키는 점수를 `scores`에서 꺼내 **"완성도 40 — 대본 누락 5개 때문입니다"** 형태로 이으세요.
- `speech_rate`는 개수로 셀 수 있는 요인이 아니라 `count`가 `0`입니다. 이 항목만 개수를 표시하지 마세요.

---

## 7. 마이페이지

| 목적 | 요청 | 비고 |
|---|---|---|
| 대본 생성 기록 | `GET /api/projects` | `id`, `name`, `topic`, `slide_count`, `created_at` |
| 발표 코칭 내역 | `GET /api/evaluations` | 프로젝트 구분 없이 최신순. 점수·`feedback`·`recognized_text` 포함 |
| 상세 | `GET /api/projects/{id}` | 슬라이드·주의 단어·평가 이력 전부 |
| 기록 삭제 | `DELETE /api/projects/{id}` | 슬라이드·단어·평가까지 함께 삭제 |

---

## 연동 순서 (권장)

1. `POST /api/projects` → `project_id` 보관
2. `POST /api/script/full` → `job_id` 보관, 스피너 시작
3. `GET /api/script/jobs/{job_id}` 1~2초 폴링 → `completed`면 대본 렌더, 스피너 종료
4. 사용자가 편집하면 `PUT .../slides/{n}`
5. `POST /api/analysis/words` → 하이라이팅
6. 녹음 → `POST /api/evaluation/audio` → 점수·인식 텍스트 표시
7. `POST /api/evaluation/{id}/feedback` → 코칭 피드백 표시

## 아직 없는 것

- **슬라이드 미리보기 썸네일**: 서버는 PPT에서 텍스트만 추출합니다. 슬라이드 이미지 렌더링은 제공하지 않습니다(프론트에서 처리).
- **단어 발음 듣기(TTS)**: 클라이언트 구현은 돼 있으나 엔드포인트 미연결.
