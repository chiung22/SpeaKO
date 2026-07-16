from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
import shutil

# 1. 분리해둔 AI 클라이언트 모듈들 임포트
from clova.full_generation.generator import FullScriptGenerator
from clova.partial_generation.generator import PartialScriptGenerator
from etri.etri_client import EtriLanguageAnalyzer
from g2p.g2p_client import G2pConverter
from azure.azure_client import PronunciationEvaluator

# 2. FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="SpeaKO AI Server",
    description="SpeaKO 프로젝트의 대본 생성 및 발음 분석을 담당하는 AI 마이크로서비스입니다.",
    version="1.0.0"
)

# 3. CORS(교차 출처 리소스 공유) 설정
origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. 각 AI 모듈 객체 생성
full_generator = FullScriptGenerator()
partial_generator = PartialScriptGenerator()
etri_analyzer = EtriLanguageAnalyzer()
g2p_converter = G2pConverter()
azure_evaluator = PronunciationEvaluator()

# ==========================================
# 📦 프론트엔드와 통신할 데이터 모델 (JSON 바디 정의)
# ==========================================
class FullScriptRequest(BaseModel):
    ppt_text: str
    presentation_time: int
    style: str

class PartialScriptRequest(BaseModel):
    original_script: str
    target_slide: int
    feedback: str

class AnalysisRequest(BaseModel):
    script_text: str

    class Config:
        json_schema_extra = {
            "example": {
                "script_text": "메타버스와 인프라 구축의 특징을 살펴봅시다."
            }
        }

# ==========================================
# 🚀 API 엔드포인트(라우터) 정의
# ==========================================
@app.get("/")
async def root():
    return {"message": "SpeaKO AI 서버가 정상적으로 실행 중입니다!"}

@app.post("/api/script/full")
async def create_full_script(request: FullScriptRequest):
    """[대본 전체 생성 API]"""
    result = full_generator.generate_full_script(request.ppt_text, request.presentation_time, request.style)
    
    if result:
        return {"success": True, "data": result}
    else:
        return {"success": False, "message": "대본 생성에 실패했습니다."}

@app.post("/api/script/partial")
async def create_partial_script(request: PartialScriptRequest):
    """[대본 부분 재생성 API]"""
    result = partial_generator.generate_partial_script(request.original_script, request.target_slide, request.feedback)
    
    if result:
        return {"success": True, "data": result}
    else:
        return {"success": False, "message": "대본 부분 재생성에 실패했습니다."}

@app.post("/api/analysis/words")
async def extract_and_convert_words(request: AnalysisRequest):
    """[발음 주의 단어 추출 및 G2P 변환 API]"""
    # 1. ETRI API로 단어 추출
    extracted_words = etri_analyzer.extract_difficult_words(request.script_text)
    
    # ETRI API 키가 없거나 오류가 발생했을 때를 대비한 안전 모드(Fallback)
    if not extracted_words:
        print("⚠️ ETRI API 호출 실패 또는 결과 없음. 임시 단어 리스트(Fallback)를 사용합니다.")
        extracted_words = ["메타버스", "인프라", "특징", "구축"]
        
    # 2. G2P 모듈로 발음 기호 획득
    final_result = g2p_converter.convert_words(extracted_words)
    
    return {"success": True, "data": final_result}

@app.post("/api/evaluation/audio")
async def evaluate_pronunciation(
    reference_text: str = Form(...),
    audio_file: UploadFile = File(...)
):
    """[사용자 음성 발음 평가 API] 사용자의 오디오 파일(WAV)과 대본을 받아 점수를 매깁니다."""
    
    # 임시 파일로 오디오 저장 (Azure SDK가 물리적인 파일 경로를 요구함)
    temp_file_path = f"temp_{audio_file.filename}"
    try:
        # 업로드된 파일을 로컬 디스크에 임시 복사
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        
        # Azure 평가 모듈 호출
        result = azure_evaluator.evaluate_audio(temp_file_path, reference_text)
        
        return result
    except Exception as e:
        return {"status": "error", "message": f"서버 내부 오류: {str(e)}"}
    finally:
        # 평가가 완료되었거나 에러가 났더라도, 서버 용량 낭비를 막기 위해 임시 파일 삭제
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# 6. 서버 실행 코드
if __name__ == "__main__":
    print("🌟 SpeaKO AI 서버를 시작합니다... (http://localhost:8000)")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)