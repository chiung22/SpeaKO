# ARCHITECTURE

## 저장소 구성

현재 이 레포에는 백엔드 컴포넌트 하나만 존재합니다. 프론트엔드(웹/모바일 클라이언트)는 아직 이 레포에 포함되어 있지 않습니다.

```
SpeaKO/
└── speako-ai-server/     # FastAPI 기반 AI 마이크로서비스 (이 레포의 유일한 서비스)
    ├── src/
    │   ├── main.py                 # API 엔드포인트(라우터) 정의
    │   ├── utils/ppt_extractor.py  # PPTX → 구조화 텍스트 추출
    │   ├── clova/
    │   │   ├── full_generation/    # 전체 발표 대본 생성 (HyperCLOVA X)
    │   │   └── partial_generation/ # 슬라이드 단위 대본 재생성 (HyperCLOVA X)
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
1. PPT 업로드          POST /api/ppt/extract        → PptExtractor (python-pptx)
2. 전체 대본 생성       POST /api/script/full        → FullScriptGenerator (HyperCLOVA X, TOON 포맷)
3. 부분 대본 재생성     POST /api/script/partial     → PartialScriptGenerator (HyperCLOVA X)
4. 발음 주의 단어 분석   POST /api/analysis/words     → EtriLanguageAnalyzer → G2pConverter
5. 사용자 발음 평가     POST /api/evaluation/audio   → PronunciationEvaluator (Azure Speech)
```

TTS 합성(`ClovaVoiceClient`)은 아직 전용 라우터가 없고, `run_pipeline_test.py` 통합 테스트에서만 직접 호출됩니다. 단어 발음을 들려주는 API가 필요하면 `/api/pronunciation/audio` 같은 엔드포인트 추가를 검토하세요 (자세한 내용은 [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) 참고).

## 핵심 설계 패턴: 안전 모드(Fallback/Mock)

5개의 외부 AI 클라이언트(HyperCLOVA X, ETRI, g2pkk, Clova Voice, Azure Speech) 전부 **API 키가 없거나 호출이 실패해도 서버가 죽지 않고 모의 데이터를 반환**하도록 설계되어 있습니다. 이는 우연이 아니라 이 프로젝트의 핵심 설계 원칙입니다. 자세한 배경은 [docs/design-docs/core-beliefs.md](docs/design-docs/core-beliefs.md)를 참고하세요.

## 아직 없는 것

- **영속성 계층**: 생성된 대본/평가 결과를 저장하는 DB가 없습니다. 모든 요청이 stateless입니다.
- **인증/인가**: 모든 엔드포인트가 무인증으로 열려 있습니다.
- **프론트엔드**: `origins = ["http://localhost:3000"]` 설정만 보면 Next.js/React 계열 프론트가 예정되어 있는 것으로 보이나, 아직 이 레포에는 없습니다.
- **배포 파이프라인**: Dockerfile, CI/CD 설정이 없습니다.

각 항목의 상세 논의는 [RELIABILITY.md](RELIABILITY.md), [SECURITY.md](SECURITY.md), [docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md)에 분산되어 있습니다.
