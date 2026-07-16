# PLANS

전체 로드맵과 마일스톤입니다. 세부 실행 단위는 [docs/exec-plans/](docs/exec-plans/active/)에 기록합니다.

## 완료

- [x] AI 파이프라인 MVP: PPT 추출 → 대본 생성/재생성 → 발음 분석 → 발음 평가 (5개 외부 API 연동 + 각각의 안전 모드)
- [x] 문서 하네스 구축 (AGENTS.md, ARCHITECTURE.md, docs/ 등) + 알려진 기술 부채 정리
- [x] 의존성 명세(`requirements.txt`), 환경변수 템플릿(`.env.example`), 기본 스모크 테스트

## 다음 우선순위 (제안)

1. **TTS 엔드포인트 연결** — `ClovaVoiceClient`를 API 라우터에 연결해 "정답 발음 들려주기" 기능을 실제로 사용 가능하게 만듭니다. ([product-specs](docs/product-specs/pronunciation-coaching.md))
2. **영속성 계층 도입** — 생성된 대본과 평가 결과를 저장해 히스토리 조회가 가능하게 합니다. ([docs/generated/db-schema.md](docs/generated/db-schema.md)에 초안 스키마 있음)
3. **인증 경계 설정** — 최소한 API 키 또는 게이트웨이 레벨 인증을 추가해 외부 API 비용 남용을 막습니다. ([SECURITY.md](SECURITY.md))
4. **프론트엔드 합류** — 이 레포 또는 별도 레포에 실제 클라이언트 코드가 추가되면 [FRONTEND.md](FRONTEND.md), [DESIGN.md](DESIGN.md)를 채웁니다.
5. **CI 파이프라인** — PR마다 `pytest` 자동 실행.

우선순위는 추측이며, 실제 기획 결정이 나오면 이 문서를 갱신하세요.
