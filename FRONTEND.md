# FRONTEND

## 현재 상태

이 레포에는 프론트엔드 코드가 없습니다. `speako-ai-server/src/main.py`의 CORS 설정(`origins = ["http://localhost:3000"]`)으로 미루어보아 Next.js/React 계열 클라이언트가 `localhost:3000`에서 이 서버를 호출하는 구성이 예정되어 있는 것으로 보이나, 실제 코드는 별도 레포에 있거나 아직 작성되지 않았습니다.

프론트엔드가 이 레포에 합류하면 이 문서에 다음을 채우세요.

- 프레임워크/상태관리 선택과 이유
- 렌더링 전략 (CSR/SSR/SSG)
- 로컬 개발 환경 세팅 (`.env.local` 등)
- 백엔드 API base URL 설정 방법

## 지금 당장 알아야 할 백엔드 연동 정보

| 항목 | 값 |
|---|---|
| 서버 실행 | `python speako-ai-server/src/main.py` → `http://localhost:8000` |
| 허용된 Origin | `http://localhost:3000` (다른 포트/도메인이면 `main.py`의 `origins` 리스트에 추가 필요) |
| 인증 | 없음 (모든 엔드포인트 무인증 — 프로덕션 배포 전 [SECURITY.md](SECURITY.md) 필독) |

### 엔드포인트 요약

| 메서드 | 경로 | 용도 | 실패 시 상태코드 |
|---|---|---|---|
| GET | `/` | 헬스체크 | - |
| POST | `/api/ppt/extract` | PPT 업로드 → 슬라이드별 텍스트/주제 추출 | 422 (추출 실패) |
| POST | `/api/script/full` | 전체 발표 대본 생성 | 502 (LLM 호출 실패) |
| POST | `/api/script/partial` | 슬라이드 단위 대본 재생성 | 502 |
| POST | `/api/analysis/words` | 발음 주의 단어 + 발음기호 | - (항상 fallback으로 200) |
| POST | `/api/evaluation/audio` | 사용자 발음 평가 (multipart: `reference_text` + `audio_file`) | 바디의 `status: "error"` 필드로 구분 |

`/api/ppt/extract`와 `/api/script/*`는 실패를 HTTP 상태코드로 알리지만, `/api/evaluation/audio`는 아직 항상 200을 반환하고 바디의 `status` 필드로만 성공/실패를 구분합니다 — 프론트에서 응답 바디를 반드시 확인하세요.
