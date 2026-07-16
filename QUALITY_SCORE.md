# QUALITY_SCORE

코드가 머지되기 전에 통과해야 하는 최소 품질 기준입니다.

## API 엔드포인트

- [ ] 외부 API 호출이 실패해도 서버가 죽지 않아야 한다 (안전 모드 필수 — [core-beliefs.md](docs/design-docs/core-beliefs.md) 참고).
- [ ] 실패는 200이 아닌 적절한 HTTP 상태코드로 알려야 한다 (4xx: 클라이언트 입력 문제, 5xx/502: 외부 API 실패).
- [ ] 업로드 등으로 생성하는 임시 파일은 요청마다 고유한 이름을 쓰고 (`uuid` 등), `finally` 블록에서 반드시 정리해야 한다.
- [ ] 새 엔드포인트를 추가하면 `speako-ai-server/tests/`에 최소 1개의 스모크 테스트를 함께 추가한다.

## 시크릿/설정

- [ ] 새 API 키가 필요하면 `.env.example`에 플레이스홀더를 추가한다.
- [ ] 실제 키 값이 커밋되지 않았는지 diff를 확인한다.
- [ ] 새 파이썬 의존성을 추가하면 `requirements.txt`(런타임) 또는 `requirements-dev.txt`(테스트/개발 전용)에 반영한다.

## 문서

- [ ] 이 기능이 새로운 사용자 시나리오를 추가한다면 `docs/product-specs/`에 반영한다.
- [ ] DB 스키마를 바꾸면 `docs/generated/db-schema.md`를 함께 갱신한다.
- [ ] 알고 있지만 지금 고치지 않기로 한 문제는 `docs/exec-plans/tech-debt-tracker.md`에 남긴다 (침묵하지 않는다).

## 실행 검증

- [ ] `pytest speako-ai-server/tests/`가 통과해야 한다.
- [ ] 가능하면 실제로 서버를 띄워서 (`python src/main.py`) 새/변경된 엔드포인트를 한 번은 직접 호출해본다.
