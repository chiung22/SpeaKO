"""
발음 주의 단어를 **대본 위에 칠하려면** 무엇이 더 필요한가에 대한 테스트.

배경(2026-08-16): 스프링이 하이라이트를 저장하는 `PronunciationHighlight` 엔티티는
`standardPronunciation` / `category(enum) / ruleDesc / positionStart / positionEnd`를 요구하는데,
AI 서버는 `word / phoneme / category(한국어) / description`만 주고 있었다. 배포된 JAR을
`javap`으로 확인해서 드러난 두 가지 구멍:

  1. 스프링이 `HighlightCategory.valueOf(category.toUpperCase())`를 부른다. "장단음"에는
     대문자가 없어 **항상 예외**가 나고 전부 기본값 하나로 떨어진다 — 세 카테고리 색이 같아진다.
  2. 위치 정보가 아예 없어서 대본의 **어디를** 칠할지 알 수 없다.

그래서 한국어 이름은 그대로 두고(화면에 그대로 뜨는 값이다) 영문 코드와 위치를 덧붙였다.
여기서 고정하는 것은 "덧붙인 것이 사라지지 않을 것"과 "위치가 실제 그 단어를 가리킬 것"이다.
"""
from fastapi.testclient import TestClient

import main
from main import DIFFICULT_WORD_CATEGORY_CODES, app

client = TestClient(app)


def _project_with(db_session_factory, scripts, words):
    from db import models

    db = db_session_factory()
    try:
        project = models.Project(name="하이라이트 테스트", filename=None, topic="주제", keywords=[])
        project.slides = [
            models.Slide(slide_number=i, source_content=f"원문{i}", script=s)
            for i, s in enumerate(scripts, start=1)
        ]
        project.difficult_words = [
            models.DifficultWord(word=w, phoneme=p, category=c, description=d)
            for w, p, c, d in words
        ]
        db.add(project)
        db.commit()
        return project.id
    finally:
        db.close()


def _detail(project_id):
    return client.get(f"/api/projects/{project_id}").json()["data"]


# ── 카테고리 코드 ────────────────────────────────────────────────────────────

def test_every_category_has_an_english_code():
    """한국어 이름 세 개 모두 코드가 있어야 한다. 하나라도 빠지면 그 카테고리만 조용히 null이 된다."""
    assert set(DIFFICULT_WORD_CATEGORY_CODES) == set(main.DIFFICULT_WORD_CATEGORIES)
    assert set(DIFFICULT_WORD_CATEGORY_CODES.values()) == {"LENGTH", "LIAISON", "MISMATCH"}


def test_codes_survive_upper_casing():
    """스프링이 `valueOf(code.toUpperCase())`를 부른다. 이미 대문자여야 그대로 통과한다."""
    for code in DIFFICULT_WORD_CATEGORY_CODES.values():
        assert code == code.upper()
        assert code.isascii()


def test_detail_carries_both_the_korean_name_and_the_code(db_session_factory):
    """한국어 이름은 화면에 그대로 뜨는 값이라 없애면 안 된다 — 코드는 덧붙이는 것이다."""
    pid = _project_with(
        db_session_factory,
        ["책임을 다하겠습니다."],
        [("책임", "[채김]", "연음", "연음: 앞 받침이 뒤 모음으로 넘어가 발음됩니다.")],
    )
    word = _detail(pid)["difficult_words"][0]

    assert word["category"] == "연음"
    assert word["category_code"] == "LIAISON"


def test_unknown_category_gives_null_code_not_a_crash(db_session_factory):
    """옛 데이터에 모르는 카테고리가 있어도 조회가 죽으면 안 된다."""
    pid = _project_with(
        db_session_factory, ["문장입니다."], [("단어", "[단어]", "알수없음", "설명")]
    )
    word = _detail(pid)["difficult_words"][0]

    assert word["category"] == "알수없음"
    assert word["category_code"] is None


# ── 스프링 필드명 별칭 ───────────────────────────────────────────────────────

def test_spring_field_aliases_are_present(db_session_factory):
    """standard_pronunciation / rule_desc는 스프링 엔티티 필드명에 맞춘 별칭이다."""
    pid = _project_with(
        db_session_factory,
        ["역할을 맡았습니다."],
        [("역할", "[여ː칼]", "장단음", "장단음: 첫 음절을 길게 발음합니다.")],
    )
    word = _detail(pid)["difficult_words"][0]

    # 대괄호와 장음기호(ː)를 벗긴, 그대로 읽을 수 있는 형태여야 한다.
    assert word["standard_pronunciation"] == "여칼"
    assert "[" not in word["standard_pronunciation"]
    assert word["rule_desc"] == word["description"]
    # 원래 값도 그대로 남는다(기존 프론트가 phoneme을 쓴다).
    assert word["phoneme"] == "[여ː칼]"


# ── 위치 ────────────────────────────────────────────────────────────────────

def test_occurrence_offsets_point_at_the_actual_word(db_session_factory):
    """좌표가 실제로 그 단어를 가리켜야 한다 — 여기가 틀리면 엉뚱한 글자가 칠해진다."""
    scripts = ["오늘은 책임에 대해 말씀드립니다.", "책임 있는 자세가 필요합니다."]
    pid = _project_with(db_session_factory, scripts, [("책임", "[채김]", "연음", "설명")])
    data = _detail(pid)

    occurrences = data["difficult_words"][0]["occurrences"]
    assert len(occurrences) == 2

    by_slide = {s["slide_number"]: s["script"] for s in data["slides"]}
    for occ in occurrences:
        script = by_slide[occ["slide_number"]]
        assert script[occ["position_start"]:occ["position_end"]] == "책임"


def test_repeated_word_in_one_slide_gets_every_position(db_session_factory):
    """한 슬라이드에 두 번 나오면 두 자리 모두 칠해져야 한다."""
    pid = _project_with(
        db_session_factory, ["책임 그리고 또 책임입니다."], [("책임", "[채김]", "연음", "설명")]
    )
    occurrences = _detail(pid)["difficult_words"][0]["occurrences"]

    assert [o["position_start"] for o in occurrences] == [0, 9]
    assert all(o["slide_number"] == 1 for o in occurrences)


def test_word_missing_from_the_script_gets_no_occurrences(db_session_factory):
    """대본을 고쳐 그 단어가 사라졌으면 빈 목록이어야 한다. 옛 좌표를 남기면 엉뚱한 데가 칠해진다."""
    pid = _project_with(
        db_session_factory, ["완전히 다른 내용입니다."], [("책임", "[채김]", "연음", "설명")]
    )
    assert _detail(pid)["difficult_words"][0]["occurrences"] == []


def test_offsets_follow_an_edited_script(db_session_factory):
    """저장해두지 않고 읽을 때 계산하는 이유. 대본이 바뀌면 좌표도 따라와야 한다."""
    pid = _project_with(db_session_factory, ["책임입니다."], [("책임", "[채김]", "연음", "설명")])
    assert _detail(pid)["difficult_words"][0]["occurrences"][0]["position_start"] == 0

    client.put(f"/api/projects/{pid}/slides/1", json={"script": "앞말 붙이고 책임입니다."})

    occ = _detail(pid)["difficult_words"][0]["occurrences"][0]
    assert occ["position_start"] == 7
    detail = _detail(pid)
    script = detail["slides"][0]["script"]
    assert script[occ["position_start"]:occ["position_end"]] == "책임"


def test_offsets_are_per_slide_not_across_the_joined_script(db_session_factory):
    """스프링은 하이라이트를 슬라이드(Script) 단위로 저장한다 — 좌표도 그 기준이어야 한다."""
    pid = _project_with(
        db_session_factory,
        ["첫 장은 길게 씁니다. 아주 길게요.", "책임입니다."],
        [("책임", "[채김]", "연음", "설명")],
    )
    occ = _detail(pid)["difficult_words"][0]["occurrences"][0]

    assert occ["slide_number"] == 2
    # 전체 대본 기준이면 앞 슬라이드 길이만큼 밀린 큰 값이 나온다.
    assert occ["position_start"] == 0
