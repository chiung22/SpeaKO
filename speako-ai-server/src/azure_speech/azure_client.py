import os
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class PronunciationEvaluator:
    def __init__(self):
        self.speech_key = os.getenv("AZURE_SPEECH_KEY")
        self.service_region = os.getenv("AZURE_SPEECH_REGION")
        
        # API 키가 없거나 '여기에_' 같은 기본값이면 안전 모드(Fallback)로 작동
        self.use_fallback = not self.speech_key or "여기에_" in self.speech_key
        
        if self.use_fallback:
            print("⚠️ [경고] Azure Speech API 키가 설정되지 않았습니다.")
            print("⚠️ 프론트엔드 테스트를 위해 임시 모의(Mock) 데이터를 반환합니다.\n")

    def evaluate_audio(self, audio_file_path: str, reference_text: str):
        """
        사용자의 음성 파일(WAV)과 읽어야 할 대본 텍스트를 받아 발음을 평가합니다.
        """
        if self.use_fallback:
            return self._mock_evaluation()

        try:
            # 1. 오디오 설정 및 스피치 설정
            audio_config = speechsdk.audio.AudioConfig(filename=audio_file_path)
            speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.service_region)
            
            # 한국어 설정
            speech_config.speech_recognition_language = "ko-KR"

            # 2. 발음 평가 옵션 설정 (기준 텍스트 제공)
            pronunciation_config = speechsdk.PronunciationAssessmentConfig(
                reference_text=reference_text,
                grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                granularity=speechsdk.PronunciationAssessmentGranularity.Word
            )

            # 3. 인식기 생성 및 평가 모듈 결합
            speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
            pronunciation_config.apply_to(speech_recognizer)

            print(f"🚀 Azure 서버에 발음 평가를 요청합니다... (기준 문장: {reference_text})")
            
            # 4. 음성 인식 및 평가 실행 (단일 문장 기준)
            result = speech_recognizer.recognize_once_async().get()

            # 5. 결과 파싱
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
                
                # 단어별 세부 평가 데이터 파싱
                words_data = []
                for word in pronunciation_result.words:
                    words_data.append({
                        "word": word.word,
                        "accuracy_score": word.accuracy_score,
                        "error_type": word.error_type
                    })

                return {
                    "status": "success",
                    "overall_scores": {
                        "accuracy": pronunciation_result.accuracy_score,
                        "fluency": pronunciation_result.fluency_score,
                        "completeness": pronunciation_result.completeness_score,
                        "pronunciation_score": pronunciation_result.pronunciation_score
                    },
                    "words_detail": words_data
                }
            elif result.reason == speechsdk.ResultReason.NoMatch:
                return {"status": "error", "message": "음성을 인식할 수 없습니다."}
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                return {"status": "error", "message": f"평가 취소됨: {cancellation_details.reason}"}

        except Exception as e:
            return {"status": "error", "message": f"평가 중 오류 발생: {str(e)}"}

    def _mock_evaluation(self):
        """안전 모드(Fallback): API 키가 없을 때 반환하는 가짜 테스트 데이터"""
        import time
        time.sleep(1.5) # 실제 네트워크 호출처럼 약간의 딜레이
        
        return {
            "status": "success",
            "overall_scores": {
                "accuracy": 85.0,
                "fluency": 90.0,
                "completeness": 100.0,
                "pronunciation_score": 88.5
            },
            "words_detail": [
                {"word": "메타버스와", "accuracy_score": 95.0, "error_type": "None"},
                {"word": "인프라", "accuracy_score": 98.0, "error_type": "None"},
                {"word": "구축의", "accuracy_score": 60.0, "error_type": "Mispronunciation"},
                {"word": "특징을", "accuracy_score": 50.0, "error_type": "Mispronunciation"},
                {"word": "살펴봅시다.", "accuracy_score": 92.0, "error_type": "None"}
            ]
        }

# ==========================================
# 🧪 [테스트 코드]
# ==========================================
if __name__ == "__main__":
    evaluator = PronunciationEvaluator()
    
    # 더미 오디오 경로 (실제 실행 시에는 존재하는 wav 파일을 넣어야 합니다)
    test_audio_path = "test_recording.wav"
    test_text = "메타버스와 인프라 구축의 특징을 살펴봅시다."
    
    result = evaluator.evaluate_audio(test_audio_path, test_text)
    
    import json
    print("\n✨ [Azure 발음 평가 결과] ✨")
    print(json.dumps(result, indent=2, ensure_ascii=False))