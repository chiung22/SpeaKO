# DB Schema

## 현재 상태

**아직 데이터베이스가 없습니다.** `speako-ai-server`의 모든 엔드포인트는 stateless이며, 요청-응답 사이에 아무것도 저장하지 않습니다.

이 문서는 실제 DB가 도입될 때 계속 최신 상태로 유지되어야 하는 스키마 문서의 자리입니다. 아래는 코드에서 다루는 데이터 모델을 근거로 한 **제안 스키마**이며, 실제 테이블이 생기기 전까지는 참고용 초안입니다.

## 제안 스키마 (초안, 미구현)

```
presentations
  id            uuid pk
  user_id       uuid fk -> users.id   -- 인증 도입 후 연결
  filename      text
  topic         text                 -- PptExtractor._extract_metadata 결과
  keywords      text[]
  created_at    timestamptz

slides
  id                uuid pk
  presentation_id   uuid fk -> presentations.id
  slide_number      int
  source_content    text     -- PPT에서 추출한 원본 텍스트
  script            text     -- 생성된 대본 (부분 재생성 시 갱신됨)
  updated_at        timestamptz

difficult_words
  id            uuid pk
  slide_id      uuid fk -> slides.id
  word          text
  phoneme       text          -- G2pConverter 결과
  created_at    timestamptz

pronunciation_evaluations
  id                uuid pk
  slide_id          uuid fk -> slides.id
  accuracy_score    float
  fluency_score     float
  completeness_score float
  pronunciation_score float
  words_detail      jsonb     -- PronunciationEvaluator.evaluate_audio의 words_detail
  created_at        timestamptz
```

## 이 스키마가 필요해지는 시점

`docs/product-specs/script-generation.md`와 `pronunciation-coaching.md`에 정리된 "알려진 제약" 중 "대본이 저장되지 않음", "히스토리 조회 불가" 항목을 해결하려면 이 스키마(또는 이를 다듬은 버전)의 구현이 선행되어야 합니다. 실제 테이블을 만들면 이 문서를 실제 마이그레이션 파일과 일치하도록 갱신하세요.
