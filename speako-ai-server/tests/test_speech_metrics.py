"""발표 습관 지표(간투어·멈춤) 검증.

Azure 점수만으로는 "음…" 같은 군더더기 말과 끊긴 구간이 드러나지 않아 따로 계산한다.
계산은 순수 함수(utils/speech_metrics.py)라 실제 음성 없이 단어 목록만 만들어 검증한다.

가장 조심할 오탐 두 가지를 회귀로 고정한다.
- 대본에 있던 '그'를 읽은 것은 간투어가 아니다 (Insertion일 때만 센다)
- 말하지 않은 단어(Omission)는 시간이 0으로 오므로, 시간축에 넣으면 멈춤이 엉터리가 된다
"""
import io

from fastapi.testclient import TestClient

import main
from main import app
from db import models
from utils import speech_metrics

client = TestClient(app)


def _word(word, error_type="None", start=None, duration=None, accuracy=90.0):
    entry = {"word": word, "accuracy_score": accuracy, "error_type": error_type}
    if start is not None:
        entry["offset_seconds"] = start
        entry["duration_seconds"] = duration if duration is not None else 0.4
    return entry


# ------------------------------------------------------------------ 간투어

def test_certain_filler_is_counted_even_without_insertion_flag():
    """'음', '어' 같은 말은 대본에 홀로 있는 경우가 없어서 error_type과 무관하게 센다."""
    words = [_word("안녕하세요"), _word("음", error_type="None"), _word("반갑습니다")]

    result = speech_metrics.detect_filler_words(words)

    assert result["count"] == 1
    assert result["by_word"] == [{"word": "음", "count": 1}]


def test_contextual_filler_counts_only_when_inserted():
    """대본에 있던 '그'를 읽은 것은 군더더기가 아니다. 대본에 없는데 말했을 때만 센다."""
    from_script = [_word("그"), _word("방법은")]
    inserted = [_word("그", error_type="Insertion"), _word("방법은")]

    assert speech_metrics.detect_filler_words(from_script)["count"] == 0
    assert speech_metrics.detect_filler_words(inserted)["count"] == 1


def test_omitted_word_is_never_a_filler():
    """Omission은 대본에만 있고 실제로 말하지 않은 단어다. 세면 안 한 말을 셈하는 꼴이 된다."""
    words = [_word("음", error_type="Omission"), _word("안녕하세요")]

    result = speech_metrics.detect_filler_words(words)

    assert result["count"] == 0
    assert result["spoken_word_count"] == 1


def test_elongated_and_punctuated_fillers_are_normalized():
    """'어어어…'와 '음,'도 같은 간투어로 잡아야 한다. 인식 결과는 표기가 들쭉날쭉하다."""
    words = [_word("어어어…", error_type="Insertion"), _word("음,"), _word("발표를")]

    result = speech_metrics.detect_filler_words(words)

    assert result["count"] == 2
    assert {item["word"] for item in result["by_word"]} == {"어", "음"}


def test_filler_ratio_uses_spoken_words_as_denominator():
    words = [_word("음"), _word("하나"), _word("둘"), _word("셋"), _word("빠뜨린", error_type="Omission")]

    result = speech_metrics.detect_filler_words(words)

    assert result["spoken_word_count"] == 4
    assert result["ratio_percent"] == 25.0


def test_filler_occurrence_carries_position_and_time():
    """프론트가 인식 텍스트 위에 표시하려면 몇 번째 단어였는지가 필요하다."""
    words = [_word("안녕하세요", start=0.0), _word("음", start=1.5, duration=0.3)]

    occurrence = speech_metrics.detect_filler_words(words)["occurrences"][0]

    assert occurrence["word_index"] == 1
    assert occurrence["offset_seconds"] == 1.5


# ------------------------------------------------------------------ 멈춤

def test_pause_counted_when_gap_reaches_threshold():
    words = [
        _word("안녕하세요", start=0.0, duration=1.0),   # 1.0에 끝남
        _word("반갑습니다", start=2.0, duration=1.0),   # 1.0초 공백 → 멈춤
    ]

    result = speech_metrics.detect_pauses(words, threshold_seconds=0.7)

    assert result["available"] is True
    assert result["count"] == 1
    assert result["items"][0]["duration_seconds"] == 1.0
    assert result["items"][0]["after_word"] == "안녕하세요"
    assert result["longest_seconds"] == 1.0


def test_short_breath_is_not_a_pause():
    """문장 사이 0.2~0.5초 호흡까지 세면 모든 발표가 '멈춤 투성이'가 된다."""
    words = [
        _word("안녕하세요", start=0.0, duration=1.0),
        _word("반갑습니다", start=1.3, duration=1.0),  # 0.3초
    ]

    assert speech_metrics.detect_pauses(words, threshold_seconds=0.7)["count"] == 0


def test_pause_is_unavailable_without_timing():
    """시간 정보가 없을 때 0을 주면 '멈춤 없음'과 '못 쟀음'이 구분되지 않는다."""
    words = [_word("안녕하세요"), _word("반갑습니다")]

    result = speech_metrics.detect_pauses(words)

    assert result["available"] is False
    assert result["count"] == 0
    assert "계산할 수 없" in result["reason"]


def test_omitted_words_do_not_corrupt_the_timeline():
    """Omission은 시간이 없거나 0으로 온다. 시간축에 섞이면 없는 멈춤이 생긴다."""
    words = [
        _word("안녕하세요", start=10.0, duration=1.0),
        _word("빠뜨린말", error_type="Omission", start=0.0, duration=0.0),
        _word("반갑습니다", start=11.2, duration=1.0),
    ]

    result = speech_metrics.detect_pauses(words, threshold_seconds=0.7)

    assert result["count"] == 0, "말하지 않은 단어가 시간축에 끼어들었다"


def test_overlapping_words_do_not_produce_negative_pauses():
    words = [
        _word("안녕하세요", start=0.0, duration=2.0),
        _word("반갑습니다", start=1.5, duration=1.0),  # 겹침
    ]

    result = speech_metrics.detect_pauses(words, threshold_seconds=0.7)

    assert result["count"] == 0


def test_multiple_pauses_are_summed():
    words = [
        _word("하나", start=0.0, duration=0.5),
        _word("둘", start=1.5, duration=0.5),   # 1.0초
        _word("셋", start=4.0, duration=0.5),   # 2.0초
    ]

    result = speech_metrics.detect_pauses(words, threshold_seconds=0.7)

    assert result["count"] == 2
    assert result["total_seconds"] == 3.0
    assert result["longest_seconds"] == 2.0


def test_pause_threshold_is_configurable():
    words = [_word("하나", start=0.0, duration=0.5), _word("둘", start=1.0, duration=0.5)]  # 0.5초

    assert speech_metrics.detect_pauses(words, threshold_seconds=0.7)["count"] == 0
    assert speech_metrics.detect_pauses(words, threshold_seconds=0.4)["count"] == 1


# ------------------------------------------------------------------ 발화 속도

def test_speech_rate_uses_spoken_span():
    words = [_word("하나", start=0.0, duration=0.5), _word("둘", start=29.5, duration=0.5)]

    rate = speech_metrics.measure_speech_rate(words)

    assert rate["available"] is True
    assert rate["speaking_seconds"] == 30.0
    assert rate["words_per_minute"] == 4.0


def test_speech_rate_unavailable_without_timing():
    assert speech_metrics.measure_speech_rate([_word("하나"), _word("둘")])["available"] is False


# ------------------------------------------------------------------ 빈 입력 방어

def test_empty_and_malformed_input_does_not_crash():
    """지표 계산이 터져서 평가 점수까지 502가 되면 안 된다. 리스트가 아닌 입력도 포함."""
    for bad in (None, [], {}, 123, 3.14, "문자열", [None], [[]], ["문자열"], [{"no_word_key": 1}]):
        result = speech_metrics.analyze(bad)
        assert result["filler_words"]["count"] == 0
        assert result["pauses"]["count"] == 0


def test_broken_timing_does_not_disable_filler_counting():
    """시간 값만 깨진 경우다. 단어 자체는 멀쩡하므로 간투어는 그대로 세야 한다."""
    words = [{"word": "음", "error_type": "None", "offset_seconds": "숫자아님", "duration_seconds": None}]

    result = speech_metrics.analyze(words)

    assert result["filler_words"]["count"] == 1
    assert result["pauses"]["available"] is False


# ------------------------------------------------------------------ 엔드포인트

def _project_with_script(db_session_factory, script):
    db = db_session_factory()
    try:
        project = models.Project(name="습관 지표 테스트", filename=None, topic=None, keywords=[])
        project.slides = [models.Slide(slide_number=1, source_content="원문", script=script)]
        db.add(project)
        db.commit()
        db.refresh(project)
        return project.id
    finally:
        db.close()


def _evaluate(monkeypatch, db_session_factory, script, recognized, words_detail):
    project_id = _project_with_script(db_session_factory, script)

    def _fake_convert(input_path, output_path):
        with open(output_path, "wb") as f:
            f.write(b"wav")
        return True

    monkeypatch.setattr(main.audio_converter, "convert_to_wav", _fake_convert)
    monkeypatch.setattr(
        main.azure_evaluator, "evaluate_audio",
        lambda audio_file_path, reference_text: {
            "status": "success",
            "overall_scores": {"accuracy": 80.0, "fluency": 80.0, "completeness": 80.0, "pronunciation_score": 80.0},
            "words_detail": words_detail,
            "recognized_text": recognized,
        },
    )
    response = client.post(
        "/api/evaluation/audio",
        data={"project_id": str(project_id)},
        files={"audio_file": ("rec.webm", io.BytesIO(b"fake"), "audio/webm")},
    )
    return project_id, response


_SAMPLE_WORDS = [
    _word("안녕하세요", start=0.0, duration=1.0),
    _word("음", error_type="Insertion", start=1.2, duration=0.3),
    _word("반갑습니다", start=3.0, duration=1.0),   # 1.5초 공백 → 멈춤 1회
]


def test_evaluation_response_includes_speech_metrics(monkeypatch, db_session_factory):
    _, response = _evaluate(
        monkeypatch, db_session_factory, "안녕하세요 반갑습니다", "안녕하세요 음 반갑습니다", _SAMPLE_WORDS,
    )

    assert response.status_code == 200
    metrics = response.json()["speech_metrics"]

    assert metrics["filler_words"]["count"] == 1
    assert metrics["pauses"]["count"] == 1
    assert metrics["pauses"]["longest_seconds"] == 1.5
    assert metrics["speech_rate"]["available"] is True


def test_speech_metrics_survive_a_reload(monkeypatch, db_session_factory):
    """평가 직후 응답에만 있고 저장이 안 되면, 코칭 내역 화면에서 지표가 사라진다."""
    project_id, response = _evaluate(
        monkeypatch, db_session_factory, "안녕하세요 반갑습니다", "안녕하세요 음 반갑습니다", _SAMPLE_WORDS,
    )
    assert response.status_code == 200

    detail = client.get(f"/api/projects/{project_id}").json()["data"]["evaluations"][0]
    assert detail["speech_metrics"]["filler_words"]["count"] == 1

    listed = client.get("/api/evaluations").json()["data"][0]
    assert listed["speech_metrics"]["pauses"]["count"] == 1


def test_evaluation_still_succeeds_without_word_timing(monkeypatch, db_session_factory):
    """Azure 상세 JSON을 못 받아도 점수는 나와야 한다. 멈춤만 '계산 불가'로 표시된다."""
    words = [_word("안녕하세요"), _word("음", error_type="Insertion"), _word("반갑습니다")]

    _, response = _evaluate(monkeypatch, db_session_factory, "안녕하세요 반갑습니다", "안녕하세요 음 반갑습니다", words)

    assert response.status_code == 200
    metrics = response.json()["speech_metrics"]
    assert metrics["filler_words"]["count"] == 1, "시간이 없어도 간투어는 셀 수 있어야 한다"
    assert metrics["pauses"]["available"] is False


# ------------------------------------------------- Azure 상세 JSON 파싱 (멈춤의 원천)
#
# 단어별 시각은 SDK 객체에 없고 원본 응답 JSON에만 있다. 이 파싱이 조용히 실패하면
# 점수는 정상으로 나오면서 멈춤만 영원히 '계산 불가'가 되므로, 실제 응답 모양으로 고정한다.

from azure_speech import azure_client  # noqa: E402  (위 픽스처 정의 뒤에 두는 편이 읽기 쉽다)

_AZURE_JSON = """
{
  "RecognitionStatus": "Success",
  "Offset": 5000000,
  "Duration": 33000000,
  "DisplayText": "안녕하세요 반갑습니다",
  "NBest": [
    {
      "Confidence": 0.95,
      "Lexical": "안녕하세요 반갑습니다",
      "Display": "안녕하세요 반갑습니다",
      "PronunciationAssessment": {"AccuracyScore": 90, "FluencyScore": 88,
                                  "CompletenessScore": 100, "PronScore": 91},
      "Words": [
        {"Word": "안녕하세요", "Offset": 5000000, "Duration": 10000000,
         "PronunciationAssessment": {"AccuracyScore": 95, "ErrorType": "None"}},
        {"Word": "빠뜨린말", "Offset": 0, "Duration": 0,
         "PronunciationAssessment": {"AccuracyScore": 0, "ErrorType": "Omission"}},
        {"Word": "반갑습니다", "Offset": 25000000, "Duration": 8000000,
         "PronunciationAssessment": {"AccuracyScore": 88, "ErrorType": "None"}}
      ]
    }
  ]
}
"""


class _FakeAzureResult:
    def __init__(self, json_payload):
        self.json = json_payload


def test_word_timings_parsed_from_azure_json():
    """틱(100ns) → 초 변환과 위치 매핑. 0.5초 시작, 1.0초 길이."""
    timings = azure_client._word_timings(_FakeAzureResult(_AZURE_JSON))

    assert timings[0] == {"offset_seconds": 0.5, "duration_seconds": 1.0}
    assert timings[2] == {"offset_seconds": 2.5, "duration_seconds": 0.8}


def test_omitted_word_gets_no_timing():
    """Duration이 0인 Omission에 시각을 붙이면 0초 지점에 단어가 있는 것처럼 보인다."""
    timings = azure_client._word_timings(_FakeAzureResult(_AZURE_JSON))

    assert 1 not in timings


def test_word_timings_survive_broken_payloads():
    """응답 포맷이 달라져도 평가 자체는 계속돼야 한다 (멈춤만 계산 불가로 표시)."""
    for payload in ("", None, "not json", "{}", '{"NBest": []}', '{"NBest": [{}]}'):
        assert azure_client._word_timings(_FakeAzureResult(payload)) == {}


def test_timings_reach_words_detail_end_to_end(monkeypatch, tmp_path):
    """SDK 콜백 → words_detail까지 시각이 실제로 흘러가는지. 여기가 끊기면 멈춤이 항상 0이 된다."""

    class _Signal:
        def __init__(self):
            self.handlers = []

        def connect(self, handler):
            self.handlers.append(handler)

        def fire(self, evt=None):
            for handler in self.handlers:
                handler(evt)

    class _Evt:
        def __init__(self, result):
            self.result = result

    class _Result:
        reason = None  # 아래에서 _Sdk.ResultReason.RecognizedSpeech로 채운다
        text = "안녕하세요 반갑습니다"
        json = _AZURE_JSON

    class _PronWord:
        def __init__(self, word, score, error_type):
            self.word, self.accuracy_score, self.error_type = word, score, error_type

    class _PronResult:
        """실제 SDK처럼 결과 객체를 받아 단어 목록을 만든다(순서는 JSON과 동일)."""

        def __init__(self, result):
            import json as _json
            words = _json.loads(result.json)["NBest"][0]["Words"]
            self.words = [
                _PronWord(w["Word"], w["PronunciationAssessment"]["AccuracyScore"],
                          w["PronunciationAssessment"]["ErrorType"])
                for w in words
            ]
            self.accuracy_score, self.fluency_score = 90.0, 88.0
            self.completeness_score, self.pronunciation_score = 100.0, 91.0

    class _Recognizer:
        def __init__(self, *args, **kwargs):
            self.recognized = _Signal()
            self.canceled = _Signal()
            self.session_stopped = _Signal()

        def start_continuous_recognition(self):
            self.recognized.fire(_Evt(_Result()))
            self.session_stopped.fire()

        def stop_continuous_recognition(self):
            pass

    class _Sdk:
        class audio:
            @staticmethod
            def AudioConfig(**kwargs):
                return object()

        @staticmethod
        def SpeechConfig(**kwargs):
            class _C:
                speech_recognition_language = None
            return _C()

        class PronunciationAssessmentGradingSystem:
            HundredMark = object()

        class PronunciationAssessmentGranularity:
            Word = object()

        class ResultReason:
            RecognizedSpeech = object()

        class CancellationReason:
            Error = object()

        @staticmethod
        def PronunciationAssessmentConfig(**kwargs):
            class _Cfg:
                def apply_to(self, recognizer):
                    pass
            return _Cfg()

        SpeechRecognizer = _Recognizer
        PronunciationAssessmentResult = _PronResult

    _Result.reason = _Sdk.ResultReason.RecognizedSpeech

    monkeypatch.setattr(azure_client, "speechsdk", _Sdk)
    evaluator = azure_client.PronunciationEvaluator()
    monkeypatch.setattr(evaluator, "use_fallback", False)
    evaluator.speech_key, evaluator.service_region = "key", "koreacentral"

    result = evaluator.evaluate_audio(str(tmp_path / "nope.wav"), "안녕하세요 반갑습니다")

    assert result["status"] == "success"
    words = result["words_detail"]
    assert words[0]["offset_seconds"] == 0.5
    assert words[2]["offset_seconds"] == 2.5
    assert "offset_seconds" not in words[1], "Omission에는 시각이 붙으면 안 된다"

    # 그리고 그 시각으로 멈춤이 실제로 잡혀야 한다 (1.5초 끝 → 2.5초 시작 = 1.0초)
    metrics = speech_metrics.analyze(words)
    assert metrics["pauses"]["count"] == 1
    assert metrics["pauses"]["longest_seconds"] == 1.0
