# DB Schema

## 현재 상태

**구현되어 있습니다.** SQLite + SQLAlchemy ORM(`speako-ai-server/src/db/`). 파일 위치는
`speako-ai-server/data/speako.db`(로컬 실행 데이터라 `.gitignore` 대상, 스키마의 원본은 `src/db/models.py`).
서버 기동 시(`main.py`의 `init_db()`) 테이블이 없으면 자동 생성됩니다. 마이그레이션 도구(Alembic 등)는
아직 없고, `Base.metadata.create_all()`로 없는 테이블만 만드는 방식이라 기존 테이블 스키마 변경 시
수동으로 DB 파일을 지우거나 마이그레이션을 추가해야 합니다.

## 실제 스키마

```
projects
  id            integer pk (autoincrement)
  name          text                 -- 업로드 시 project_name 또는 파일명에서 유도
  filename      text                 -- 원본 PPT 파일명
  topic         text                 -- PptExtractor._extract_metadata 결과
  keywords      json                 -- list[str]
  created_at    datetime

slides
  id                integer pk
  project_id        integer fk -> projects.id (ondelete cascade)
  slide_number      integer
  source_content    text     -- PPT에서 추출한 원본 텍스트 (또는 이미지 슬라이드면 HCX 비전 결과)
  script            text, nullable   -- 생성된 대본. 전체 생성/부분 재생성 둘 다 이 컬럼을 덮어씀 (버전 이력은 없음)
  updated_at        datetime

difficult_words
  id            integer pk
  project_id    integer fk -> projects.id (ondelete cascade)
  word          text
  phoneme       text          -- G2pConverter 결과, 예: "[학쓥]"
  category      text, nullable  -- "장단음" | "연음" | "표기-발음불일치" | null(철자=발음, 분류 대상 아님)
  created_at    datetime

pronunciation_evaluations
  id                    integer pk
  project_id            integer fk -> projects.id (ondelete cascade)
  accuracy_score        float
  fluency_score         float
  completeness_score    float
  pronunciation_score   float
  words_detail          json     -- PronunciationEvaluator.evaluate_audio의 words_detail
  created_at            datetime
```

## 최초 제안(2026-07-19 초안)과 달라진 점

- `presentations` → `projects`로 이름 변경(코드/제품 용어와 통일).
- `uuid` pk 대신 `integer autoincrement` pk 사용 — 인증이 아직 없어서 UUID로 얻는 이점(추측 불가능한 외부 노출 ID)이 당장 없고, SQLite에서 더 간단함. 인증 도입 시 재검토 가능.
- `user_id`는 아직 추가하지 않음 — 인증 자체가 없어서 지금 넣어봐야 항상 null인 컬럼. 인증 도입 시점에 추가.
- `difficult_words`/`pronunciation_evaluations`를 원안의 `slide_id` 대신 **`project_id`**에 직접 연결함. 실제 구현에서 ETRI 단어 추출은 슬라이드 하나가 아니라 프로젝트의 전체 대본(모든 슬라이드를 이어붙인 텍스트)을 대상으로 하고, Azure 발음 평가도 연속 인식으로 전체 대본을 reference로 받아 프로젝트 단위 결과 하나를 만들기 때문. 슬라이드 단위로 쪼개서 분석하지 않음.
- `slides.script`는 버전 이력을 남기지 않고 최신 값으로 덮어씀 (전체 생성/부분 재생성 둘 다). `pronunciation_evaluations`는 반대로 매 평가마다 새 행을 추가해서 히스토리(연습 기록)를 남김 — 사용자가 여러 번 연습하며 점수 변화를 볼 수 있어야 하기 때문.
- `difficult_words`는 `/api/analysis/words` 호출마다 해당 프로젝트의 기존 행을 지우고 새로 채움 (현재 대본 기준 스냅샷이지 히스토리가 아님).
- `difficult_words.category`는 2026-07-21 추가. 철자와 발음(G2P 결과)이 다른 단어만 장단음/연음/표기-발음불일치 3가지로 분류함 — 장단음은 국립국어원 표준국어대사전 API(`utils/stdict_client.py`)의 발음 표기에 장음 기호(`ː`)가 있는지로, 연음은 한글 자모 분해 기반 구조 판정(`utils/hangul_phonology.py`, 받침+무초성 음절 패턴)으로, 나머지는 표기-발음불일치로 분류. `/api/analysis/words` 응답에도 프로젝트별 카테고리 집계(`summary`)가 같이 내려감.

## API 연동

`POST /api/projects`가 새 `projects` row + `slides` row들을 만들고 `project_id`를 응답에 포함합니다
(PPT/PDF 업로드, topic+outline만 입력, 완성된 대본 직접 붙여넣기/파일 업로드 등 여러 입력 방식 지원 — 자세한 내용은
[ARCHITECTURE.md](../../ARCHITECTURE.md) 참고). 이후 `/api/script/full`, `/api/script/partial`,
`/api/analysis/words`, `/api/evaluation/audio`는 전부 `project_id`를 받아서 이 프로젝트에 묶인 데이터를
읽고 씁니다. `GET /api/projects`(목록)와 `GET /api/projects/{id}`(상세: 슬라이드별 대본 + 발음 주의 단어(카테고리 포함)
+ 평가 히스토리)로 조회할 수 있습니다.
