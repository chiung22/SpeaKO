# AGENTS

이 문서는 이 레포지토리에서 활동하는 에이전트(LLM)를 위한 진입점입니다. 코드를 건드리기 전에 아래 문서들을 이 순서대로 참고하세요.

## 읽는 순서

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** — 저장소 구조와 요청 흐름을 먼저 파악합니다.
2. **[docs/product-specs/index.md](docs/product-specs/index.md)** — 각 기능이 "무엇을" 해야 하는지.
3. **[docs/design-docs/core-beliefs.md](docs/design-docs/core-beliefs.md)** — 절대 깨면 안 되는 규칙(특히 "안전 모드" 패턴).
4. **[SECURITY.md](SECURITY.md)** — API 키/시크릿을 다루는 규칙.
5. **[docs/exec-plans/tech-debt-tracker.md](docs/exec-plans/tech-debt-tracker.md)** — 알려진 미비점. 새로 발견한 이슈도 아니라면 여기에 먼저 있는지 확인.

## 작업 기록 규칙

- 진행 중인 작업 계획은 `docs/exec-plans/active/`에 마크다운 파일로 둡니다.
- 작업이 끝나면 해당 파일을 `docs/exec-plans/completed/`로 옮기고, 무엇을 왜 했는지 간단히 남깁니다.
- DB 스키마를 변경했다면 `docs/generated/db-schema.md`를 함께 최신화합니다 (아직 DB가 없다면 이 단계는 해당 없음).

## 이 레포에서 지켜야 할 것

- **외부 AI API를 호출하는 코드는 항상 안전 모드(fallback/mock)를 갖춰야 합니다.** 키가 없거나 호출이 실패해도 서버가 죽으면 안 됩니다. 기존 5개 클라이언트(`clova`, `etri`, `g2p`, `tts`, `azure_speech`)의 패턴을 그대로 따르세요.
- **`.env`에 실제 키를 커밋하지 않습니다.** 새 키가 필요하면 `.env.example`에 플레이스홀더를 추가하세요.
- **API 실패는 HTTP 상태코드로 정직하게 알립니다.** `{"success": false}`를 200으로 감추지 않습니다.
- **패키지 이름이 잘 알려진 서드파티 네임스페이스(`azure`, `google` 등)와 겹치지 않게 합니다.** (`src/azure/`를 `src/azure_speech/`로 바꾼 전례가 있습니다.)
- 새 기능을 추가하면 `speako-ai-server/tests/`에 최소 스모크 테스트를 하나 이상 추가합니다.

## 로컬 실행

```bash
cd speako-ai-server
python -m venv venv && source venv/Scripts/activate   # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env   # 필요한 키를 채우거나, 비워둔 채로 안전 모드로 실행
python src/main.py
pytest tests/
```
