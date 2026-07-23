# ARCHITECTURE

## 저장소 구성

현재 이 레포에는 백엔드 컴포넌트 하나만 존재합니다. 프론트엔드(웹/모바일 클라이언트)는 아직 이 레포에 포함되어 있지 않습니다.

```
SpeaKO/
└── speako-ai-server/     # FastAPI 기반 AI 마이크로서비스 (이 레포의 유일한 서비스)
    ├── src/
    │   ├── main.py                 # API 엔드포인트(라우터) 정의
    │   ├── db/                     # SQLite + SQLAlchemy (projects/slides/difficult_words/pronunciation_evaluations)
    │   ├── utils/ppt_extractor.py  # PPTX → 구조화 텍스트 추출 (텍스트가 거의 없는 장표는 HCX 비전으로 이미지 텍스트 인식)
    │   ├── utils/pdf_extractor.py  # PDF → 페이지별(슬라이드) 또는 전체(코칭용 문서) 텍스트 추출
    │   ├── utils/docx_extractor.py # DOCX → 전체 텍스트 추출 (발음 코칭용, 완성된 대본 파일 업로드)
    │   ├── utils/audio_converter.py # ffmpeg로 MP3/M4A → 16kHz mono WAV 변환 (Azure 평가 입력용)
    │   ├── utils/stdict_client.py  # 국립국어원 표준국어대사전 API — 단어의 장단음(모음 길이) 판정
    │   ├── utils/hangul_phonology.py # 한글 음절 분해 + 연음(받침+무초성) 구조 판정
    │   ├── clova/
    │   │   ├── full_generation/    # 전체 발표 대본 생성 + 어투 고도화 (HyperCLOVA X)
    │   │   ├── partial_generation/ # 슬라이드 단위 대본 재생성 (HyperCLOVA X)
    │   │   ├── vision/             # 이미지 전용 슬라이드의 텍스트를 HCX-005 비전으로 인식
    │   │   └── toon_parser.py      # 전체/부분 생성 공용 TOON 응답 파서
    │   ├── etri/etri_client.py     # 형태소 분석 → 발음 주의 단어 추출 (ETRI WiseNLU, 키 있을 때만)
    │   ├── nlp/kiwi_analyzer.py    # 형태소 분석 로컬 대체 (Kiwi/kiwipiepy, 키 불필요 — 현재 단어추출 주력)
    │   ├── g2p/g2p_client.py       # 단어 → 발음 기호 변환 (g2pkk, Windows 미지원 시 자체 사전으로 대체)
    │   ├── tts/clova_voice_client.py # 단어 발음 음성 합성 (Clova Voice)
    │   └── azure_speech/azure_client.py # 사용자 발화 발음 평가 (Azure Speech)
    ├── tests/                      # pytest 스모크 테스트
    ├── requirements.txt / requirements-dev.txt
    └── .env.example
```

## 요청 흐름 (End-to-End)

```
1. 프로젝트 생성        POST /api/projects           → 아래 3가지 입력 방식 중 하나로 DB에 project/slides 생성
2. 전체 대본 생성       POST /api/script/full        → FullScriptGenerator (HyperCLOVA X, TOON 포맷) → 슬라이드별로 DB 저장
3. 부분 대본 재생성     POST /api/script/partial     → PartialScriptGenerator (HyperCLOVA X) → 해당 슬라이드 DB 갱신
4. 발음 주의 단어 분석   POST /api/analysis/words     → (ETRI 키 있으면 ETRI, 없으면 Kiwi 로컬 분석) → G2pConverter → 카테고리 분류(장단음/연음/표기-발음불일치) → DB에 스냅샷 저장
5. 사용자 발음 평가     POST /api/evaluation/audio   → (WAV 아니면 audio_converter로 변환) → PronunciationEvaluator (Azure Speech) → DB에 히스토리로 누적
6. 프로젝트 조회        GET /api/projects, /api/projects/{id} → 위에서 쌓인 슬라이드/대본/단어/평가 히스토리 조회
```

**1번(프로젝트 생성)의 입력 방식** (Figma 디자인 "AI Set Page"/"Select page"/"Coach Set Page" 기준, `mode` 폼 필드로 구분):
- `mode="script"`(기본값) + `file`(PPTX 또는 PDF) 업로드 — `PptExtractor`(텍스트박스) 또는 `pdf_extractor.extract_structured_data`(페이지별 텍스트)로 슬라이드 추출. `topic`/`outline`은 이미지 슬라이드 인식 정확도를 높이는 선택적 힌트. ("AI 대본 생성" 플로우)
- `mode="script"` + `file` 없이 `topic` + `outline` 텍스트만 — PPT 없이 주제/가이드라인만으로 프로젝트를 만듦(단일 슬라이드에 브리프 저장). 이후 2번에서 대본을 생성함.
- `script_text` (mode 무관) — 이미 완성된 발표 대본을 그대로 붙여넣어, 2번(생성) 없이 바로 4~5번(코칭/평가)으로 넘어감.
- `mode="coaching"` + `file`(DOCX/TXT/PDF) 업로드 — 이미 완성된 대본을 파일로 올림. `docx_extractor`/`pdf_extractor.extract_full_text`/일반 텍스트 디코딩으로 문서 전체를 하나의 대본으로 추출해 `script_text`와 동일하게 처리(생성 스킵). ("발표 발음 코칭" 플로우, PPTX는 이 모드에서 415로 거부됨)

2~5번 전부 1번에서 받은 `project_id`를 기준으로 이어집니다 — 대본 생성은 DB에 저장된 슬라이드 원문을 읽고,
부분 재생성은 클라이언트가 원본 대본을 다시 보낼 필요 없이 DB에 저장된 최신 대본을 쓰고, 발음 평가는
`reference_text`를 안 주면 DB의 대본을 기준으로 채점합니다. 2번(전체 생성)은 `style`(`"격식체"`/`"편안한 말투"`)과
선택적 `extra_requirement`(자유 텍스트)를 받으며, 모델이 원본 슬라이드 수와 다르게(예: topic/outline 브리프 1개를
여러 슬라이드로) 대본을 쪼개 생성하면 없는 슬라이드 번호는 새로 만들어서 저장합니다(upsert). 자세한 스키마는
[docs/generated/db-schema.md](docs/generated/db-schema.md) 참고.

`style`의 어투 정의는 [clova/styles.py](speako-ai-server/src/clova/styles.py)에 한 곳으로 모아 두고, 전체 생성·부분
재생성·고도화가 공용으로 씁니다. **"격식체"라는 단어만 프롬프트에 던지면 모델이 해요체(~이고요/~해보았고요)로
흘러내려서**(ClipRoute 대본 실측), 각 스타일은 "어떤 어미를 쓰고 어떤 어미를 금지하는지"를 문장으로 못박고 프롬프트
맨 뒤(`[반드시 지킬 것 — 말투]`)에 둡니다. 발표 오프닝/마무리 인사 처리도 여기서 위치별 지시로 관리합니다(첫 장만 인사,
중간 장은 곧바로 본론, 마지막 장만 마무리).

### 대본 생성은 슬라이드 한 장씩 요청합니다

여러 장을 한 요청에 넣으면 슬라이드와 대본의 정렬이 밀립니다. 아래는 전부 이 프로젝트에서 실측한 것입니다.

| 넣은 방식 | 결과 |
|---|---|
| 19장을 한 번에 | 모델이 TOON을 버리고 발표 전체를 **줄글 하나**로 씀 → 1장만 저장 |
| 6장씩 묶어서 | 어떤 장은 건너뛰고 어떤 장은 두 줄로 쪼갬 → **전체의 26%가 이웃 슬라이드 내용**을 말함 |
| 한 장씩 | 19/19 생성, 정렬 정확 |

한 장만 보내면 무슨 응답이 오든 그 장의 대본이므로 **정렬이 구조적으로 보장**됩니다. 이때 중요한 점:

- **TOON을 쓰지 않습니다.** 응답 전체가 곧 그 슬라이드의 대본이라 구분자가 필요 없습니다. 오히려 껍데기를 요구하면
  모델이 그걸 안 지켜서 멀쩡한 대본이 버려집니다(실측: 내용은 완벽한데 TOON이 아니라는 이유로 19장 중 18장 폐기).
  혹시 모델이 습관적으로 붙인 `slides[1]{...}`나 `Slide 1:` 라벨은 `_clean_single_slide_script()`가 걷어냅니다.
- **위치를 지시문으로 넘깁니다.** 매 장이 독립 요청이라 모델은 자기가 발표 중간인 걸 모릅니다. 위치를 단순 라벨로만
  주면 무시하고 장마다 인사합니다(19장 중 16장이 "안녕하세요"). 그래서 "인사말로 시작하지 마세요"를 문장으로 못박고
  프롬프트 **맨 뒤**에 둡니다.
- **이웃 슬라이드 내용은 넘기지 않습니다.** 흐름을 위해 앞뒤 원문을 맥락으로 줘봤지만, 모델이 그 내용의 대본까지
  써버려서(3번 대본이 4번 내용을 설명) 정렬이 다시 깨졌습니다. 위치만 알려주고 내용은 주지 않습니다.
- 한 장이 실패하면 그 슬라이드는 영구 누락이므로(다른 장이 대신 채워주지 않음) **한 번 재시도**합니다.

고도화(`ScriptRefiner`)는 `Slide N:` 라벨을 유지하는 작업이라 6장씩 묶어 처리하되, 다듬은 결과의 슬라이드 번호 목록이
입력과 다르면 자연스러움보다 내용 보존을 택해 초안을 그대로 유지합니다.

단, 원본이 한 덩어리뿐인 경우(PPT 없이 주제/목차만 받은 프로젝트)는 모델이 여러 슬라이드로 확장하는 것이 정상이라
이 경로에서만 TOON을 쓰고, 번호를 손대지 않고 그대로 upsert 합니다.

TTS 합성(`ClovaVoiceClient`)은 아직 전용 라우터가 없고, `run_pipeline_test.py` 통합 테스트에서만 직접 호출됩니다. 단어 발음을 들려주는 API가 필요하면 `/api/pronunciation/audio` 같은 엔드포인트 추가를 검토하세요 (자세한 내용은 [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) 참고).

**4번(발음 주의 단어 분석)의 카테고리 분류**: 철자와 실제 발음(G2P 결과)이 다른 단어만 분류 대상이며, 우선순위대로 판정합니다.
1. **장단음** — `stdict_client.has_long_vowel()`이 국립국어원 표준국어대사전에서 이 단어의 발음 표기에 장음 기호(`ː`)가 있는지 조회.
2. **연음** — `hangul_phonology.has_liaison_pattern()`이 "받침 있는 음절 + 초성 없는(ㅇ) 다음 음절" 구조를 한글 자모 분해로 판정.
3. **표기-발음불일치** — 위 둘에 해당하지 않는 나머지(비음화/경음화 등).

`/api/analysis/words` 응답에 카테고리별 개수 집계(`summary`)가 같이 내려갑니다. 동음이의어의 의미 중의성은 해소하지 않고(표준국어대사전 검색 결과 첫 항목 기준), 연음 판정도 구조적 가능성만 보는 휴리스틱이라 완벽하지 않습니다 — 자세한 한계는 [tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) 참고.

## 이미지로만 된 슬라이드 처리 (HCX 비전)

캡처/디자인 이미지를 통째로 붙여넣은 장표는 텍스트박스가 비어 있어서 그냥 두면 대본 생성에서 통째로 누락됩니다.
`PptExtractor`는 이런 장표를 HCX-005 비전으로 읽어 살리되, 비전 호출이 슬라이드당 유료 API 호출이라 다음 기준으로 추립니다.

- **장식용 제외**: 150×100px 미만이거나 가로세로 비율이 5:1을 넘는 이미지(아이콘/구분선)는 보내지 않음.
- **텍스트가 이미 충분한 장표는 생략**: 텍스트박스에서 읽힌 글자가 50자 이상이면 이미지를 읽지 않음(얻을 게 적음).
- **슬라이드당 상한 3장**: 넓이가 큰 것부터. 한 장에 후보 이미지가 97개인 실제 PPT가 있었음.
- **포맷 정규화**: HCX가 받는 건 PNG/JPEG/BMP/WEBP뿐. EMF/WMF/TIFF는 Pillow로 PNG 변환 후 전송하고, 변환도 실패하면 건너뜀.

⚠️ **주의(과거 사고)**: HCX의 `dataUri.data`는 순수 base64가 아니라 `data:<mime>;base64,<payload>` 형태여야 합니다.
접두어를 빼면 400(`40001 Invalid parameter`)으로 **전량 거절**되는데, 호출부는 실패 시 빈 문자열을 반환하므로(안전 모드)
겉으로는 "이미지에 글자가 없었다"와 구분되지 않습니다. 실제로 이 때문에 비전 인식이 100% 실패하는 상태가 한동안 방치됐고,
이미지 전용 PPT 5개의 대본 추출이 조용히 실패했습니다. 지금은 4xx/5xx 응답 본문을 로그로 남기고,
`tests/test_image_text_extractor.py`가 요청 포맷을 회귀 테스트로 고정합니다.

## 핵심 설계 패턴: 안전 모드(Fallback/Mock)

5개의 외부 AI 클라이언트(HyperCLOVA X, ETRI, g2pkk, Clova Voice, Azure Speech) 전부 **API 키가 없거나 호출이 실패해도 서버가 죽지 않고 모의 데이터를 반환**하도록 설계되어 있습니다. 이는 우연이 아니라 이 프로젝트의 핵심 설계 원칙입니다. 자세한 배경은 [docs/design-docs/core-beliefs.md](docs/design-docs/core-beliefs.md)를 참고하세요.

## 아직 없는 것

- **인증/인가**: 모든 엔드포인트가 무인증으로 열려 있습니다. DB에 `project_id`가 생겼지만 누구나 남의 프로젝트를 조회/수정할 수 있는 상태입니다.
- **프론트엔드**: `origins = ["http://localhost:3000"]` 설정만 보면 Next.js/React 계열 프론트가 예정되어 있는 것으로 보이나, 아직 이 레포에는 없습니다. Figma 디자인(`docs/figma/`)은 있음 — 화면 구성과 백엔드 계약을 맞추는 데 참고.
- **배포 파이프라인**: PR마다 `pytest`를 돌리는 CI(`.github/workflows/tests.yml`)는 있지만, Dockerfile이나 실제 배포(CD) 설정은 없습니다.
- **발음 평가 결과에 AI 생성 정성 피드백 없음**: Figma "Coach View Page"/"Feedback Page"의 점수 옆 "발음 팁"/"상세 피드백"처럼, AI가 생성한 정성적 코멘트를 보여주는 부분은 아직 없습니다(`/api/evaluation/audio`는 Azure의 숫자 점수만 반환). 카테고리별 하이라이트(장단음/연음/표기-발음불일치)는 구현됨 — 위 "4번" 설명 참고. [tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) 참고.

각 항목의 상세 논의는 [RELIABILITY.md](RELIABILITY.md), [SECURITY.md](SECURITY.md), [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md)에 분산되어 있습니다.
