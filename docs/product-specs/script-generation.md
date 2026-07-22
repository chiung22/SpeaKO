# 발표 대본 생성

## 사용자 시나리오

1. 사용자가 프로젝트를 만든다. 방식은 세 가지: (a) 발표용 PPT/PDF 파일 업로드, (b) 파일 없이 발표 주제+목차 텍스트만 입력, (c) 이미 완성된 대본을 붙여넣거나 DOCX/TXT/PDF로 업로드(코칭 전용). (`POST /api/projects`)
2. 서버가 슬라이드별 텍스트와 발표 주제/목차 키워드를 추출해 프로젝트로 DB에 저장하고 `project_id`를 돌려준다.
3. 사용자가 발표 시간(분)과 스타일(`격식체`/`편안한 말투`), 선택적 추가 요구사항을 지정하면, 슬라이드별 구어체 대본이 자동 생성되어 각 슬라이드에 저장된다. (`POST /api/script/full`)
4. 특정 슬라이드의 대본이 마음에 들지 않으면, 스타일/추가 요구사항을 바꿔 해당 슬라이드만 다시 생성할 수 있다. 원본 대본을 다시 보낼 필요 없이 `project_id`와 `target_slide`만 넘기면 된다. (`POST /api/script/partial`)

## 현재 구현 상태

| 단계 | 엔드포인트 | 상태 |
|---|---|---|
| 프로젝트 생성(파일/주제·목차/대본) | `POST /api/projects` | 구현됨 |
| 전체 대본 생성 | `POST /api/script/full` | 구현됨 (HyperCLOVA X, 초안 생성 → 자동 어투 고도화 2단계) |
| 부분 재생성 | `POST /api/script/partial` | 구현됨 (HyperCLOVA X) |
| 프로젝트/대본/평가 히스토리 조회 | `GET /api/projects`, `GET /api/projects/{id}` | 구현됨 |

## 알려진 제약

- `PptExtractor`의 주제/키워드 추출은 "목차/index/agenda 같은 단어가 나오면 그 다음 텍스트를 키워드로 본다"는 휴리스틱이라, 목차 슬라이드가 없는 PPT에서는 품질이 떨어질 수 있습니다.
- `style`은 이제 자유 텍스트가 아니라 `격식체`/`편안한 말투` 두 값으로 고정되어 있습니다(Figma 디자인 반영). 세밀한 조정은 `extra_requirement`(자유 텍스트)로 받습니다.
- PDF 업로드는 `pypdf` 텍스트 추출만 하며, 이미지로만 된 PDF 슬라이드에는 HCX 비전 보조가 적용되지 않습니다(PPTX만 비전 폴백 있음). [tech-debt-tracker](../exec-plans/tech-debt-tracker.md) 참고.
- 긴 발표(10슬라이드+)에서 HCX 응답이 `maxTokens`에 걸려 잘려도 잘림 감지가 없어 마지막 슬라이드가 미완성일 수 있습니다. [tech-debt-tracker](../exec-plans/tech-debt-tracker.md) 참고.

> 대본/평가 결과는 이제 SQLite(`Project`/`Slide` 등)에 저장됩니다 — "저장되지 않음/히스토리 없음" 제약은 해소되었습니다. 스키마는 [docs/generated/db-schema.md](../generated/db-schema.md) 참고.
