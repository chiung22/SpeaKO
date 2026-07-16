# 발음 코칭

## 사용자 시나리오

1. 생성된 대본에서 발음하기 어려운 단어(명사/고유명사/외래어)를 자동으로 뽑아준다. (`POST /api/analysis/words`, ETRI 형태소분석)
2. 각 단어의 실제 발음 기호를 보여준다 (예: "특징" → "[특찡]"). (같은 엔드포인트 내 g2pkk 변환)
3. (파이프라인 테스트 단계에서만 구현됨) 해당 단어를 정확히 발음하는 음성을 들려준다. (Clova Voice TTS)
4. 사용자가 대본을 읽고 녹음하면, 정확도/유창성/완성도 점수를 매겨준다. (`POST /api/evaluation/audio`, Azure Speech)

## 현재 구현 상태

| 단계 | 엔드포인트 | 상태 |
|---|---|---|
| 발음 주의 단어 추출 + 발음기호 변환 | `POST /api/analysis/words` | 구현됨 |
| 단어 음성 합성(TTS) | 없음 | `ClovaVoiceClient`는 존재하나 API 라우터에 연결되어 있지 않음 — `run_pipeline_test.py`에서만 호출됨 |
| 사용자 발음 평가 | `POST /api/evaluation/audio` | 구현됨 (Azure Speech Pronunciation Assessment) |

## 알려진 제약

- **TTS 엔드포인트가 없습니다.** 사용자가 "정답 발음"을 들어볼 방법이 API 레벨에서는 아직 없습니다. `/api/pronunciation/audio` 같은 엔드포인트를 추가해 `ClovaVoiceClient.synthesize_word`를 연결하는 작업이 다음 우선순위로 보입니다.
- g2pkk가 로드되지 않는 환경(Windows 등)에서는 자체 fallback 사전(`g2p_client.py`의 `fallback_dict`)을 쓰는데, 현재 10개 단어만 등록되어 있어 실사용 커버리지가 매우 낮습니다.
- 발음 평가는 문장 단위(`recognize_once_async`)로만 동작합니다. 긴 대본 전체를 한 번에 평가하려면 문장 분리 후 순차 평가하는 로직이 필요합니다.
