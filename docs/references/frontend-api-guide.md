# 프론트엔드 연동 가이드 (AI 서버 API)

SpeaKO AI 서버(FastAPI)의 엔드포인트 계약입니다. 프론트엔드가 이 문서만 보고 붙일 수 있게 정리했습니다.

- **Base URL**: 배포 주소 (로컬은 `http://localhost:8000`)
- **인증**: `SPEAKO_API_KEY`가 설정돼 있으면 모든 `/api/*` 요청에 `X-API-Key: <키>` 헤더 필요. 미설정이면 인증이 꺼집니다(로컬 개발용).
- **CORS**: 배포 프론트 도메인이 서버의 `CORS_ALLOW_ORIGINS`에 있어야 브라우저가 응답을 받습니다. 기본값에 `https://speakofront.vercel.app`과 `*.vercel.app`이 포함돼 있습니다.
- **실패 규약**: 잘못된 입력 `422`, 대상 없음 `404`, 외부 AI 호출 실패 `502`.

---

## 전체 흐름 한눈에

```
[AI 대본 생성]
POST /api/projects            파일/주제 업로드 → project_id
POST /api/script/full         생성 시작 → job_id (즉시 202)
GET  /api/script/jobs/{id}    1~2초마다 폴링 → completed면 대본
PUT  /api/projects/{id}/slides/{n}   사용자가 고친 대본 저장
POST /api/script/partial      슬라이드 하나만 다시 생성

[발표 발음 코칭]
POST /api/analysis/words      발음 주의 단어 + 발음기호 (하이라이팅용)
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
{ "project_id": 12, "presentation_time": 8, "style": "격식체",
  "topic": "발표 주제", "audience": "교수님", "extra_requirement": "" }
```
- `style`: `"격식체"` 또는 `"편안한 말투"` (필수, 다른 값은 422)
- `topic`/`audience`/`extra_requirement`: 선택. `topic`을 비우면 프로젝트에 저장된 주제를 씁니다.

**응답 `202`** — 기다리지 않고 바로 옵니다.
```json
{ "success": true, "job_id": "abc123...", "status": "processing" }
```

### 2-1. 상태 폴링 — `GET /api/script/jobs/{job_id}`

1~2초 간격으로 호출하며 스피너를 돌립니다.

```json
// 처리 중
{ "success": true, "job_id": "abc123", "status": "processing" }

// 완료
{ "success": true, "job_id": "abc123", "status": "completed", "project_id": 12,
  "data": { "slides": [{"slide_number": "1", "script": "안녕하십니까..."}],
            "missing_slide_numbers": [] } }

// 실패
{ "success": true, "job_id": "abc123", "status": "failed", "error": "대본 생성에 실패했습니다." }
```
- `status`가 `processing`이 아니면 폴링을 멈춥니다.
- 없는 `job_id`는 `404`.
- `data.missing_slide_numbers`에 번호가 있으면 그 슬라이드는 대본이 비어 있습니다 — "다시 생성" 안내 후 `POST /api/script/partial`로 그 장만 재생성하면 됩니다.
- ⚠️ 작업 상태는 서버 메모리에 있습니다. **서버가 재시작되면 진행 중이던 작업은 사라지므로**, 폴링이 404를 받으면 "다시 시도"를 안내해 주세요.

---

## 3. 대본 편집

| 목적 | 요청 |
|---|---|
| 사용자가 고친 대본 저장 | `PUT /api/projects/{id}/slides/{n}` — body `{ "script": "고친 내용" }` |
| 슬라이드 추가 | `POST /api/projects/{id}/slides` — body `{ "position": 2, "script": "" }` (position 없으면 맨 끝) |
| 슬라이드 삭제 | `DELETE /api/projects/{id}/slides/{n}` |

- 셋 다 응답에 **정리된 전체 슬라이드 목록**이 옵니다: `{ "data": { "slides": [...] } }`
- 추가/삭제 후 번호는 **1..N으로 자동 재정렬**됩니다.
- 마지막 한 장은 삭제할 수 없습니다 (`422`).
- PPT 없이 만든 프로젝트(전체 대본 한 덩어리)는 `slide_number = 1`에 저장하면 됩니다.

### 슬라이드 부분 재생성 — `POST /api/script/partial`
```json
{ "project_id": 12, "target_slide": 3, "style": "격식체",
  "audience": "면접관", "extra_requirement": "더 짧게" }
```
기존 대본을 다시 보낼 필요 없이 서버에 저장된 것을 씁니다. (동기 호출, 몇 초)

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

## 5. 녹음 평가 — `POST /api/evaluation/audio`

`multipart/form-data`
- `project_id` (필수)
- `audio_file` (필수) — `.webm` / `.wav` / `.mp3` / `.m4a`, **최대 10MB**
- `slide_number` (선택) — 슬라이드별로 나눠 녹음할 때 그 번호
- `reference_text` (선택)

평가 기준 대본 우선순위: `reference_text` > `slide_number`(그 장 대본만) > 대본 전체.
슬라이드 하나만 읽었는데 전체를 기준으로 채점하면 완성도가 바닥으로 나오므로, 부분 녹음이면 `slide_number`를 넣어주세요.

```json
{ "success": true, "project_id": 12, "evaluation_id": 5,
  "slide_number": 3,
  "overall_scores": { "accuracy": 87.4, "fluency": 82.1,
                      "completeness": 95.0, "pronunciation_score": 84.3 },
  "recognized_text": "실제로 인식된 문장",
  "words_detail": [{ "word": "발전", "accuracy_score": 52.0, "error_type": "Mispronunciation" }] }
```
- 점수는 **소수 1자리(0~100)**. 그대로 표시하면 됩니다. 종합 점수는 `pronunciation_score`.
- `recognized_text`와 원본 대본을 좌우로 놓으면 "원본 ↔ 인식 텍스트" 비교 화면이 됩니다.
- `error_type`: `None`(정상) / `Mispronunciation`(틀림) / `Omission`(안 읽음).
- 중간에 멈춰도 **읽은 부분까지만** 채점됩니다. 어디까지 읽었는지 알려줄 필요 없습니다.

---

## 6. AI 코칭 피드백 — `POST /api/evaluation/{evaluation_id}/feedback`

```json
{ "success": true, "evaluation_id": 5, "cached": false,
  "data": {
    "summary": "전반적으로 또렷합니다...",
    "strengths": ["'평가'를 정확하게 발음하셨습니다."],
    "improvements": ["'발전'의 받침을 끝까지 발음하세요."],
    "practice_tips": ["거울을 보며 입 모양을 확인하세요."],
    "weak_words": [{ "word": "발전", "accuracy_score": 52.0, "error_type": "Mispronunciation" }]
  } }
```
- 생성에 몇 초 걸립니다. 스피너를 띄워주세요.
- **이미 만든 피드백이 있으면 재생성하지 않고 그대로 반환**합니다(`cached: true`). 여러 번 눌러도 비용이 늘지 않습니다.

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
