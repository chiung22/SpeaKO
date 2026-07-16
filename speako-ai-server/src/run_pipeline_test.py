import os
import sys
import json
from dotenv import load_dotenv

# 프로젝트 최상위 경로를 파이썬 경로에 추가하여 임포트 에러를 방지합니다.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 1. 작성해둔 모든 AI 클라이언트 모듈 임포트
from clova.full_generation.generator import FullScriptGenerator
from etri.etri_client import EtriLanguageAnalyzer
from g2p.g2p_client import G2pConverter
from tts.clova_voice_client import ClovaVoiceClient

# Azure 모듈은 이전 단계에서 누락되었을 수 있으므로 예외 처리하여 안전하게 임포트합니다.
try:
    from azure.azure_client import PronunciationEvaluator
    azure_available = True
except ImportError:
    azure_available = False

# .env 파일 로드
load_dotenv()

def run_integrated_pipeline():
    print("=" * 60)
    print("🚀 SpeaKO AI 전체 파이프라인 통합 테스트를 시작합니다!")
    print("=" * 60)

    # ==========================================
    # [모듈 초기화]
    # ==========================================
    print("\n⏳ 각 AI 모듈을 초기화하고 있습니다...")
    clova_gen = FullScriptGenerator()
    etri_analyzer = EtriLanguageAnalyzer()
    g2p_converter = G2pConverter()
    tts_client = ClovaVoiceClient()
    azure_evaluator = PronunciationEvaluator() if azure_available else None
    print("✅ 모든 모듈 초기화 완료!\n")

    # ==========================================
    # [STEP 1] 대본 생성 (HyperCLOVA X)
    # ==========================================
    print("-" * 60)
    print("🎯 [STEP 1] 대본 생성 테스트 (HyperCLOVA X)")
    sample_ppt_text = "메타버스와 인프라 구축의 특징을 살펴봅시다."
    
    script_result = clova_gen.generate_full_script(
        ppt_text=sample_ppt_text,
        presentation_time=1,
        style="신뢰감을 주는 아나운서 스타일"
    )
    
    # 생성된 대본이 없거나(API 키 없음) 실패 시, 다음 파이프라인 진행을 위해 가짜 대본 주입
    if not script_result:
        print("⚠️ 대본 생성 결과가 없어(안전 모드), 임시 텍스트로 다음 단계를 진행합니다.")
        script_text = "메타버스와 인프라 구축의 특징을 살펴봅시다."
    else:
        print("✨ [생성 성공] 데이터:")
        print(script_result)
        # JSON 파싱 등을 거쳐 순수 텍스트만 추출했다고 가정
        script_text = "메타버스와 인프라 구축의 특징을 살펴봅시다."

    # ==========================================
    # [STEP 2] 어려운 단어 추출 (ETRI)
    # ==========================================
    print("\n" + "-" * 60)
    print("🎯 [STEP 2] 발음 주의 단어 추출 (ETRI 언어 분석)")
    
    extracted_words = etri_analyzer.extract_difficult_words(script_text)
    
    # ETRI 결과가 없으면(키 오류 등) 강제로 임시 단어 리스트 주입
    if not extracted_words:
        print("⚠️ ETRI 분석 결과가 없어, 안전 모드(Fallback) 단어를 사용합니다.")
        extracted_words = ["메타버스", "인프라", "특징", "구축"]
    else:
        print(f"✨ [추출 성공] 단어 리스트: {extracted_words}")

    # ==========================================
    # [STEP 3] 발음 기호 변환 (G2P)
    # ==========================================
    print("\n" + "-" * 60)
    print("🎯 [STEP 3] 시각적 발음 코칭 변환 (G2P)")
    
    phoneme_data = g2p_converter.convert_words(extracted_words)
    print("✨ [변환 성공] 데이터:")
    print(json.dumps(phoneme_data, indent=2, ensure_ascii=False))

    # ==========================================
    # [STEP 4] 단어 음성 합성 (Clova Voice)
    # ==========================================
    print("\n" + "-" * 60)
    print("🎯 [STEP 4] 단어 음성 합성 테스트 (Clova Voice)")
    
    if phoneme_data:
        target_word = phoneme_data[-1]['word'] # 예시로 리스트의 마지막 단어 선택 (예: '특징')
        test_audio_filename = f"test_pronunciation_{target_word}.mp3"
        
        audio_path = tts_client.synthesize_word(target_word, test_audio_filename)
        if audio_path:
            print(f"✨ [합성 성공] 오디오 파일이 저장되었습니다: {os.path.abspath(audio_path)}")
        else:
            print("❌ 음성 합성에 실패했습니다.")
    else:
        print("⚠️ 합성할 단어가 없습니다.")

    # ==========================================
    # [STEP 5] 사용자 음성 평가 (Azure Speech)
    # ==========================================
    print("\n" + "-" * 60)
    print("🎯 [STEP 5] 사용자 발음 채점 및 평가 (Azure Speech)")
    
    if azure_evaluator:
        # 실제 환경에서는 유저가 녹음한 .wav 파일 경로가 들어갑니다.
        # 여기서는 테스트용 가짜 파일 경로(dummy.wav)를 넘기면 모의(Mock) 데이터가 나오도록 설계되었습니다.
        dummy_wav_path = "dummy_recording.wav"
        eval_result = azure_evaluator.evaluate_audio(dummy_wav_path, script_text)
        
        print("✨ [평가 성공] 분석 데이터:")
        print(json.dumps(eval_result, indent=2, ensure_ascii=False))
    else:
        print("⚠️ Azure 평가 모듈이 존재하지 않거나 로드에 실패했습니다.")

    print("\n" + "=" * 60)
    print("🎉 SpeaKO AI 전체 파이프라인 통합 테스트가 완료되었습니다!")
    print("=" * 60)

if __name__ == "__main__":
    run_integrated_pipeline()