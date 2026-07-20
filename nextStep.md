# Next Step — 진행 현황

API 키(ETRI/Azure/Clova Voice) 발급 대기 중 진행 가능한 작업들을 정리합니다. "정리하자"라고 말하면 이 시점까지 작업을 PR/머지하고 이 파일을 최신 상태로 정리합니다.

## ✅ 머지 완료 (2026-07-21)

CLOVA OCR → HCX-005 비전 교체 작업 [PR #6](https://github.com/chiung22/SpeaKO/pull/6) `feat/hcx-vision-image-extraction` 브랜치로 머지 완료. pytest 9건 통과 상태로 `main` 반영. (중간 발표 대본은 요청대로 git에 올리지 않고 `docs/presentations/`에 로컬 파일로만 남겨둠.)

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
