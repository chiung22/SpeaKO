# ARCHITECTURE

## 저장소 구성

현재 이 레포에는 백엔드 컴포넌트 하나만 존재합니다. 프론트엔드(웹/모바일 클라이언트)는 아직 이 레포에 포함되어 있지 않습니다.

```
SpeaKO/
└── speako-ai-server/     # FastAPI 기반 AI 마이크로서비스 (이 레포의 유일한 서비스)
    ├── src/
    │   ├── main.py                 # API 엔드포인트(라우터) 정의
    │   ├── db/                     # SQLite + SQLAlchemy (projects/slides/difficult_words/pronunciation_evaluations)
    │   ├── utils/ppt_extractor.py  # PPTX → 구조화 텍스트 추출 (텍스트박스 없으면 HCX 비전으로 이미지 텍스트 인식)
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
    │   ├── etri/etri_client.py     # 형태소 분석 → 발음 주의 단어 추출 (ETRI WiseNLU)
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
4. 발음 주의 단어 분석   POST /api/analysis/words     → EtriLanguageAnalyzer → G2pConverter → 카테고리 분류(장단음/연음/표기-발음불일치) → DB에 스냅샷 저장
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

TTS 합성(`ClovaVoiceClient`)은 아직 전용 라우터가 없고, `run_pipeline_test.py` 통합 테스트에서만 직접 호출됩니다. 단어 발음을 들려주는 API가 필요하면 `/api/pronunciation/audio` 같은 엔드포인트 추가를 검토하세요 (자세한 내용은 [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) 참고).

**4번(발음 주의 단어 분석)의 카테고리 분류**: 철자와 실제 발음(G2P 결과)이 다른 단어만 분류 대상이며, 우선순위대로 판정합니다.
1. **장단음** — `stdict_client.has_long_vowel()`이 국립국어원 표준국어대사전에서 이 단어의 발음 표기에 장음 기호(`ː`)가 있는지 조회.
2. **연음** — `hangul_phonology.has_liaison_pattern()`이 "받침 있는 음절 + 초성 없는(ㅇ) 다음 음절" 구조를 한글 자모 분해로 판정.
3. **표기-발음불일치** — 위 둘에 해당하지 않는 나머지(비음화/경음화 등).

`/api/analysis/words` 응답에 카테고리별 개수 집계(`summary`)가 같이 내려갑니다. 동음이의어의 의미 중의성은 해소하지 않고(표준국어대사전 검색 결과 첫 항목 기준), 연음 판정도 구조적 가능성만 보는 휴리스틱이라 완벽하지 않습니다 — 자세한 한계는 [tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) 참고.

## 핵심 설계 패턴: 안전 모드(Fallback/Mock)

5개의 외부 AI 클라이언트(HyperCLOVA X, ETRI, g2pkk, Clova Voice, Azure Speech) 전부 **API 키가 없거나 호출이 실패해도 서버가 죽지 않고 모의 데이터를 반환**하도록 설계되어 있습니다. 이는 우연이 아니라 이 프로젝트의 핵심 설계 원칙입니다. 자세한 배경은 [docs/design-docs/core-beliefs.md](docs/design-docs/core-beliefs.md)를 참고하세요.

## 아직 없는 것

- **인증/인가**: 모든 엔드포인트가 무인증으로 열려 있습니다. DB에 `project_id`가 생겼지만 누구나 남의 프로젝트를 조회/수정할 수 있는 상태입니다.
- **프론트엔드**: `origins = ["http://localhost:3000"]` 설정만 보면 Next.js/React 계열 프론트가 예정되어 있는 것으로 보이나, 아직 이 레포에는 없습니다. Figma 디자인(`docs/figma/`)은 있음 — 화면 구성과 백엔드 계약을 맞추는 데 참고.
- **배포 파이프라인**: PR마다 `pytest`를 돌리는 CI(`.github/workflows/tests.yml`)는 있지만, Dockerfile이나 실제 배포(CD) 설정은 없습니다.
- **발음 평가 결과에 AI 생성 정성 피드백 없음**: Figma "Coach View Page"/"Feedback Page"의 점수 옆 "발음 팁"/"상세 피드백"처럼, AI가 생성한 정성적 코멘트를 보여주는 부분은 아직 없습니다(`/api/evaluation/audio`는 Azure의 숫자 점수만 반환). 카테고리별 하이라이트(장단음/연음/표기-발음불일치)는 구현됨 — 위 "4번" 설명 참고. [tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) 참고.

각 항목의 상세 논의는 [RELIABILITY.md](RELIABILITY.md), [SECURITY.md](SECURITY.md), [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md)에 분산되어 있습니다.
