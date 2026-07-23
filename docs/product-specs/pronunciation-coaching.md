# 발음 코칭

## 사용자 시나리오

1. 생성된(또는 붙여넣은) 대본에서 발음하기 어려운 단어(명사/고유명사/외래어)를 자동으로 뽑아준다. (`POST /api/analysis/words`, 형태소분석: ETRI 키 있으면 ETRI, 없으면 Kiwi 로컬 분석기)
2. 각 단어의 실제 발음 기호를 보여주고, 왜 주의해야 하는지 **장단음/연음/표기-발음불일치** 카테고리로 분류해준다. (같은 엔드포인트 내 g2pkk 변환 + 표준국어대사전 장단음 조회 + 한글 자모 분석)
3. (파이프라인 테스트 단계에서만 구현됨) 해당 단어를 정확히 발음하는 음성을 들려준다. (Clova Voice TTS)
4. 사용자가 대본을 읽고 녹음(WAV/MP3/M4A)하면, 정확도/유창성/완성도 점수를 매겨 히스토리로 저장한다. (`POST /api/evaluation/audio`, Azure Speech)

## 현재 구현 상태

| 단계 | 엔드포인트 | 상태 |
|---|---|---|
| 발음 주의 단어 추출 + 발음기호 변환 + 카테고리 분류 | `POST /api/analysis/words` | 구현됨 (응답에 카테고리별 집계 `summary` 포함) |
| 단어 음성 합성(TTS) | 없음 | `ClovaVoiceClient`는 존재하나 API 라우터에 연결 안 됨. 실제 키(`CLOVA_VOICE_*`) 발급 대기로 보류 |
| 사용자 발음 평가 | `POST /api/evaluation/audio` | 구현됨 (Azure Speech, 연속 인식). WAV 외 MP3/M4A는 ffmpeg로 변환 후 평가 |

## 알려진 제약

- **TTS 엔드포인트가 없습니다.** `ClovaVoiceClient.synthesize_word`를 `/api/pronunciation/audio` 같은 라우터에 연결하는 작업이 남아 있으며, `CLOVA_VOICE_CLIENT_ID`/`SECRET` 발급을 기다리는 중입니다.
- g2pkk가 로드되지 않는 환경(Windows 등)에서는 자체 fallback 사전(`g2p_client.py`의 `fallback_dict`, 현재 약 31단어)을 쓰는데, 수작업 사전이라 커버리지가 제한적입니다.
- 발음 평가는 연속 인식(`start_continuous_recognition`)으로 전체 대본을 한 번에 채점하지만, 녹음 중 pause가 여러 번이면 뒷부분 단어 정렬이 흐트러질 수 있습니다. [tech-debt-tracker](../exec-plans/tech-debt-tracker.md) 참고.
- 카테고리 분류에는 한계가 있습니다: 장단음은 표준국어대사전 검색 첫 결과만 대표로 쓰므로 동음이의어 중의성을 해소하지 못하고, 연음은 "받침+무초성" 구조만 보는 휴리스틱이라 구개음화 등이 연음으로 잘못 분류될 수 있습니다. 또한 단어당 외부 사전 조회가 들어가므로 한 요청에서 분석하는 단어 수에 상한(현재 40개)이 있습니다.
