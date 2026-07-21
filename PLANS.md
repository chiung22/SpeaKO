# PLANS

전체 로드맵과 마일스톤입니다. 세부 실행 단위는 [docs/exec-plans/](docs/exec-plans/active/)에 기록합니다.

## 완료

- [x] AI 파이프라인 MVP: PPT 추출 → 대본 생성/재생성 → 발음 분석 → 발음 평가 (5개 외부 API 연동 + 각각의 안전 모드)
- [x] 문서 하네스 구축 (AGENTS.md, ARCHITECTURE.md, docs/ 등) + 알려진 기술 부채 정리
- [x] 의존성 명세(`requirements.txt`), 환경변수 템플릿(`.env.example`), 기본 스모크 테스트
- [x] 영속성 계층 도입 — SQLite + SQLAlchemy로 `projects`/`slides`/`difficult_words`/`pronunciation_evaluations` 저장, `project_id` 기반으로 전체 API가 연결됨. 히스토리 조회용 `GET /api/projects`, `GET /api/projects/{id}` 추가. ([docs/generated/db-schema.md](docs/generated/db-schema.md))
- [x] 인증 경계 설정(1차) — `/api/*`에 `X-API-Key` 헤더 검증 추가(`SPEAKO_API_KEY`). 무단 외부 호출로 인한 비용 남용은 막지만, 사용자별 소유권 인가(내 프로젝트만 접근)는 아직 아님 — 계정 시스템 생기면 후속 작업 필요. ([SECURITY.md](SECURITY.md))
- [x] CI 파이프라인 — `.github/workflows/tests.yml` 추가. `main` push/PR마다 `pytest` 자동 실행.
- [x] Figma 디자인("UMC 10th_SpeaKO") 확보 후 백엔드 계약을 실제 화면에 맞춤: `POST /api/projects`가 PPT/PDF 업로드, topic+outline만 입력, 완성된 대본(`script_text`) 직접 붙여넣기 3가지 방식을 모두 지원하도록 재설계. 전체 대본 생성도 부분 재생성처럼 `style`(격식체/편안한 말투) + `extra_requirement`를 받도록 통일. ([docs/figma/](docs/figma/), [ARCHITECTURE.md](ARCHITECTURE.md))
- [x] 코칭 대본 DOCX/TXT 파일 업로드 — `POST /api/projects`에 `mode="coaching"` 추가, DOCX(`python-docx`)/TXT/PDF 업로드 시 전체 텍스트를 그대로 완성된 대본으로 저장(생성 단계 스킵).
- [x] 오디오 MP3/M4A 지원 — 서버 담당자가 ffmpeg 설치 가능 확인 → `utils/audio_converter.py` 추가, WAV 아니면 16kHz mono WAV로 변환 후 Azure 평가. 실제 ffmpeg 변환 + 실제 Azure 호출까지 라이브로 검증함.
- [x] 발음 코칭 카테고리별 하이라이트 — Figma "Coach View Page"의 장단음/연음/표기-발음불일치 3분류 구현. 국립국어원 표준국어대사전 API(`utils/stdict_client.py`, 장단음)와 한글 자모 분해 기반 구조 판정(`utils/hangul_phonology.py`, 연음)을 결합. `/api/analysis/words`가 카테고리별 개수 집계(`summary`)까지 함께 반환. 판정 정확도의 알려진 한계는 [tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md) 참고.

## 보류 (실제 키 발급 대기)

- **TTS 엔드포인트 연결** — `ClovaVoiceClient`를 API 라우터에 연결하는 작업 자체는 코드만으로 가능하지만, `CLOVA_VOICE_CLIENT_ID`/`SECRET`이 아직 미발급이라 연결해봐야 fallback만 나가고 실제 음성은 안 나옴. 실효성이 없어서 **키 발급 후로 미룸**. ([tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md))

## 보류 (설계 필요 — Figma에서 발견했지만 스펙이 확정 안 됨)

- **AI 생성 정성 피드백/팁** — Figma "Coach View Page"/"Feedback Page"의 "발음 팁"/"상세 피드백" 텍스트. 새 HCX 프롬프트 설계 필요.

## 다음 우선순위 (제안, 키 불필요·설계 불필요)

1. **프론트엔드 합류** — 이 레포 또는 별도 레포에 실제 클라이언트 코드가 추가되면 [FRONTEND.md](FRONTEND.md), [DESIGN.md](DESIGN.md)를 채웁니다.
2. **사용자 계정/소유권 기반 인가** — 프론트엔드가 붙어서 실제 사용자 개념이 생기면, 공유 API 키만으로는 부족해짐(남의 `project_id` 접근 가능). 계정 시스템과 함께 설계 필요.
3. **구조화 로깅 도입** — 전부 `print()`로 되어있음, 로깅 라이브러리/포맷 결정 필요.

우선순위는 추측이며, 실제 기획 결정이 나오면 이 문서를 갱신하세요.
