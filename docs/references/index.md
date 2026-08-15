# References

에이전트가 코드를 작성할 때 참고해야 할 외부 문서, API 가이드, 프롬프트 규칙 모음입니다.

- [hyperclova_prompt_guide.md](hyperclova_prompt_guide.md) — HyperCLOVA X 대본 생성용 시스템 프롬프트 설계와 TOON 포맷(토큰 절감용 커스텀 직렬화 포맷) 규격. `speako-ai-server/src/clova/full_generation/generator.py`와 `partial_generation/generator.py`가 이 문서의 프롬프트를 그대로 구현하고 있으므로, 프롬프트를 수정할 때는 반드시 이 문서와 코드를 함께 갱신해야 합니다.
- [api-key-setup-guide.md](api-key-setup-guide.md) — `.env`에 필요한 5개 키(HCX, ETRI, Azure Speech, Clova Voice)를 각각 어디서 어떻게 발급받는지 정리한 가이드.
- [스프링_연동_대조_2026-08-15.md](스프링_연동_대조_2026-08-15.md) — EC2에 배포된 스프링 JAR을 `javap`으로 뜯어 AI 서버 응답과 필드 단위로 대조한 결과. **추측이 아니라 배포된 바이트코드에서 읽은 값**이라, 연동이 안 될 때 여기부터 보면 됩니다. `ai_project_id`가 null인 원인과 `slide_number` 누락으로 점수가 왜곡되는 문제를 담고 있습니다.

향후 추가될 수 있는 참고 문서:
- ETRI 형태소 분석 API(`WiseNLU`) 응답 스펙
- Azure Speech Pronunciation Assessment 채점 기준 문서
- Naver Clova Voice Premium TTS 파라미터 가이드
- (프론트엔드 합류 시) 디자인 시스템 레퍼런스
