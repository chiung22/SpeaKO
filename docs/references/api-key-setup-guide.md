# 외부 API 키 발급 가이드

`speako-ai-server/.env.example`에 정의된 5개 키를 어디서, 어떻게 발급받는지 정리합니다. 실제 발급 절차는 각 서비스 정책에 따라 바뀔 수 있으니, 화면 구성이 다르면 해당 서비스의 최신 공식 문서를 우선하세요.

## 1. HCX_API_KEY — Naver CLOVA Studio (HyperCLOVA X)

대본 생성(`clova/full_generation`, `clova/partial_generation`)에 사용됩니다.

1. [Naver Cloud Platform](https://www.ncloud.com)에 가입하고 콘솔에 로그인합니다. (개인/사업자 인증 필요할 수 있음)
2. 콘솔에서 **CLOVA Studio**로 이동합니다 (AI·Application Service 카테고리, 또는 [clovastudio.ncloud.com](https://clovastudio.ncloud.com) 직접 접속).
3. CLOVA Studio 내 **API 키** 메뉴에서 테스트 API 키(또는 서비스 앱 등록 후 서비스 API 키)를 발급합니다.
4. 발급된 키를 `.env`의 `HCX_API_KEY`에 넣습니다. 호출 시 `Authorization: Bearer {API_KEY}` 헤더 하나로 인증합니다.
5. 코드의 `model_name = "HCX-005"`가 실제로 콘솔에서 사용 가능한 모델명과 일치하는지 확인하세요. 모델명이 바뀌었다면 `full_generation/generator.py`, `partial_generation/generator.py` 둘 다 수정해야 합니다.

> `X-NCP-APIGW-API-KEY`(API Gateway 인증키, 구 `HCX_APIGW_KEY`)는 2025년 1월 이전에 만든 앱에만 해당하는 구버전 인증 방식입니다. 새로 발급받는 키는 API Gateway 키가 따로 없고, 위의 단일 API 키 + Bearer 헤더만으로 인증됩니다.

> 무료 크레딧이 제공되긴 하지만, 사용량에 따라 과금될 수 있습니다. 콘솔에서 결제 수단 등록이 필요할 수 있습니다.

## 2. ETRI_API_KEY — ETRI 개방형 API (WiseNLU 형태소분석)

발음 주의 단어 추출(`etri/etri_client.py`)에 사용됩니다.

1. [ETRI 오픈API·오픈데이터 포털](https://aiopen.etri.re.kr)에 회원가입합니다.
2. 로그인 후 **API 신청** 메뉴에서 **언어분석(자연어처리) - WiseNLU** API를 선택해 신청합니다.
3. 신청 사유 등을 입력하면 (연구/개인 개발 목적은 보통 빠르게) 승인되고, **마이페이지 > 발급받은 Key**에서 키를 확인할 수 있습니다.
4. 발급받은 키를 `Authorization` 헤더 값으로 그대로 사용합니다 (`etri_client.py`가 이미 그렇게 구현되어 있음).

> 개인/연구용은 무료지만 일일 호출 횟수 제한이 있을 수 있습니다. 서비스 규모가 커지면 별도 협의가 필요할 수 있습니다.

## 3. AZURE_SPEECH_KEY / AZURE_SPEECH_REGION — Microsoft Azure AI Speech

사용자 발음 평가(`azure_speech/azure_client.py`, Pronunciation Assessment)에 사용됩니다.

1. [Azure Portal](https://portal.azure.com)에 가입/로그인합니다 (Microsoft 계정 필요, 최초 가입 시 신용카드 인증이 필요하지만 무료 등급 한도 내에서는 과금되지 않음).
2. 포털 상단 검색창에서 **"Speech" 또는 "Speech services"**를 검색해 리소스를 생성합니다 (또는 "Cognitive Services" > "Speech").
3. 생성 시 **구독(Subscription)**, **리소스 그룹**, **지역(Region)**, **가격 책정 계층(Free F0 또는 Standard S0)**을 선택합니다. 코드 기본값이 `koreacentral`이므로 리전을 Korea Central로 맞추면 `.env`의 `AZURE_SPEECH_REGION` 수정 없이 그대로 씁니다.
4. 리소스가 생성되면 좌측 메뉴 **"키 및 엔드포인트(Keys and Endpoint)"**에서 **키 1** 값을 `AZURE_SPEECH_KEY`에 넣습니다.
5. 같은 화면에 표시되는 **위치/지역** 값을 `AZURE_SPEECH_REGION`에 넣습니다 (예: `koreacentral`).

> 무료(F0) 등급은 월 일정 시간까지 무료입니다. 발음 평가(Pronunciation Assessment)는 Speech-to-Text 기능의 일부로 포함됩니다.

## 4. CLOVA_VOICE_CLIENT_ID / CLOVA_VOICE_CLIENT_SECRET — Naver Clova Voice Premium (TTS)

단어 발음 음성 합성(`tts/clova_voice_client.py`)에 사용됩니다. 현재 API 라우터에는 연결되어 있지 않고 `run_pipeline_test.py`에서만 쓰입니다 ([tech-debt-tracker.md](../exec-plans/tech-debt-tracker.md) 참고).

1. HCX 키와 마찬가지로 [Naver Cloud Platform](https://www.ncloud.com) 콘솔에 로그인합니다.
2. **AI·Application Service > CLOVA Voice Premium**으로 이동해 서비스 이용 신청을 합니다.
3. NCP 콘솔의 **API Gateway** 또는 **CLOVA Voice 서비스 신청 앱** 화면에서 **Client ID**, **Client Secret**을 발급받습니다.
4. HCX와 마찬가지로 NCP 계정 하나로 여러 AI 서비스(CLOVA Studio, CLOVA Voice) 키를 함께 관리하게 됩니다 — 두 서비스를 각각 별도로 "이용 신청"해야 키가 나온다는 점에 유의하세요.

## 키를 다 받은 뒤

1. `speako-ai-server/.env.example`을 복사해 `speako-ai-server/.env`를 만들고 (이미 되어 있다면 생략) 각 값을 채워 넣습니다.
2. 절대 `.env`를 커밋하지 마세요 (`.gitignore`가 이미 막고 있음).
3. 서버를 실행해 실제 응답이 오는지 확인합니다. 키가 잘못되었거나 비어 있으면 각 클라이언트가 자동으로 안전 모드(mock)로 전환되므로, "에러 없이 조용히 mock 데이터가 나오는" 상황과 "진짜 API가 성공한" 상황을 헷갈리지 않도록 응답 내용을 직접 확인하세요.
