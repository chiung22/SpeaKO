# SpeaKO

발표 대본을 만들고, 발음이 헷갈리는 단어를 짚어주고, 녹음한 발표를 평가해주는 서비스입니다.
이 저장소는 그중 **AI 마이크로서비스**([`speako-ai-server/`](speako-ai-server/), FastAPI)를 담고 있습니다.

## ⚠️ 외부 API 키는 2026-08-22부로 해지됩니다

이 서버는 HyperCLOVA X(대본 생성·피드백), Azure Speech(발음 평가), Clova Voice(음성 합성),
표준국어대사전(장단음)을 호출합니다. 시연(2026-08-21)이 끝나면 **비용 때문에 모든 키를 해지합니다.**
즉 그 이후에 이 저장소를 열었다면 키는 없는 상태가 정상입니다.

**키 없이도 그대로 돌아갑니다.** 키가 비어 있으면 각 모듈이 **안전 모드**로 떠서 외부 API를
호출하지 않고 목(mock) 응답을 돌려줍니다. 서버 기동, 전체 테스트, 화면 연동 확인이 전부 됩니다.

```bash
cd speako-ai-server
pip install -r requirements-dev.txt
python -m pytest tests/          # 265건, 키 없이 통과합니다
python src/main.py               # http://localhost:8000/docs
```

> 🚨 **해지된 키를 값만 남겨두지 마세요.** 안전 모드 판정은 "키가 있는가"만 보고 유효성은
> 보지 않습니다. 죽은 키가 남아 있으면 서버가 실호출을 시도했다가 401을 맞고 **502로 실패**합니다.
> 다시 쓰시려면 [`speako-ai-server/.env.example`](speako-ai-server/.env.example)을 `.env`로
> 복사한 뒤 새 키를 채우세요. 발급 절차는
> [docs/references/api-key-setup-guide.md](docs/references/api-key-setup-guide.md)에 있습니다.

## 문서

| 문서 | 내용 |
|---|---|
| [docs/references/frontend-api-guide.md](docs/references/frontend-api-guide.md) | 프론트엔드 연동 가이드 (엔드포인트별 요청·응답, 상한값) |
| [docs/references/SpeaKO_AI서버_API명세서.txt](docs/references/SpeaKO_AI서버_API명세서.txt) | 같은 내용의 전달용 명세서 |
| [docs/references/스프링_연동요청.md](docs/references/스프링_연동요청.md) | 스프링 게이트웨이가 지켜야 할 것 (XFF, 타임아웃, 바이너리 통과) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 구조 |
| [nextStep.md](nextStep.md) | 진행 현황과 작업 재개 지점 |

## 알아둘 것

- 테스트는 **`pytest tests/`**로 돌리세요. 인자 없이 `pytest`만 치면 `src/_db_smoke_test.py`를
  수집하다 실패합니다.
- **발음 듣기(`POST /api/tts/word`)는 철자가 아니라 표준 발음을 합성합니다.** Clova Voice가
  한국어 음운 규칙을 일부만 적용하기 때문입니다(실측: 격음화·유음화는 적용, 경음화·연음은 미적용).
  `각자`를 요청하면 `[각짜]`가 재생됩니다. 자세한 근거는
  [tests/test_tts_endpoint.py](speako-ai-server/tests/test_tts_endpoint.py) 상단에 있습니다.
- 형태소 분석은 ETRI 키가 없으면 로컬 **Kiwi**가 대신합니다. 품질 차이가 거의 없어 키 없이 써도 됩니다.
