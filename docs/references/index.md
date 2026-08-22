# References

에이전트가 코드를 작성할 때 참고해야 할 외부 문서, API 가이드, 프롬프트 규칙 모음입니다.

- [hyperclova_prompt_guide.md](hyperclova_prompt_guide.md) — HyperCLOVA X 대본 생성용 시스템 프롬프트 설계와 TOON 포맷(토큰 절감용 커스텀 직렬화 포맷) 규격. `speako-ai-server/src/clova/full_generation/generator.py`와 `partial_generation/generator.py`가 이 문서의 프롬프트를 그대로 구현하고 있으므로, 프롬프트를 수정할 때는 반드시 이 문서와 코드를 함께 갱신해야 합니다.
- [api-key-setup-guide.md](api-key-setup-guide.md) — `.env`에 필요한 5개 키(HCX, ETRI, Azure Speech, Clova Voice)를 각각 어디서 어떻게 발급받는지 정리한 가이드.
- [스프링_최종_수정목록.md](스프링_최종_수정목록.md) — **스프링 담당자에게는 이 문서 하나만 보내면 됩니다.** 실제 `PresentationService.java` 소스와 EC2 배포 JAR을 함께 보고 작성했습니다. 파일 → 메서드 → 메서드 안 위치까지 짚어두었고, 적용 순서가 정해져 있습니다(DTO 필드가 먼저, 그걸 쓰는 서비스가 나중 — 순서가 틀리면 `cannot find symbol`이 납니다).
- [스프링_수정목록_2026-08-17.md](스프링_수정목록_2026-08-17.md) — 위 문서의 이전 판. **이미 해결된 항목이 섞여 있으므로 새로 전달할 때는 쓰지 마세요.** AI 서버 응답 예시(상세 피드백 `data` 구조, `difficult_words` 필드, `speech_metrics` 실측값)는 여기가 더 자세해서 참고용으로 남겨둡니다.
- [스프링_썸네일_연동.md](스프링_썸네일_연동.md) — 슬라이드 미리보기(썸네일)를 프론트까지 내보내기 위해 스프링에서 추가해야 할 중계 엔드포인트와 DTO 필드 2개. AI 서버 쪽은 동작 확인이 끝났고, 지금 막혀 있는 지점은 스프링 DTO 하나입니다.
- [스프링_연동_대조_2026-08-15.md](스프링_연동_대조_2026-08-15.md) — EC2에 배포된 스프링 JAR을 `javap`으로 뜯어 AI 서버 응답과 필드 단위로 대조한 결과. **추측이 아니라 배포된 바이트코드에서 읽은 값**이라, 연동이 안 될 때 여기부터 보면 됩니다. `ai_project_id`가 null인 원인과 `slide_number` 누락으로 점수가 왜곡되는 문제를 담고 있습니다.

향후 추가될 수 있는 참고 문서:
- ETRI 형태소 분석 API(`WiseNLU`) 응답 스펙
- Azure Speech Pronunciation Assessment 채점 기준 문서
- Naver Clova Voice Premium TTS 파라미터 가이드
- (프론트엔드 합류 시) 디자인 시스템 레퍼런스

- [아키텍처 회고 및 보완책](아키텍처_회고_및_보완책.md) — 시연까지의 실제 구조·실측 병목·보완책·운영 사고·다음 프로젝트 체크리스트 (2026-08-22)
