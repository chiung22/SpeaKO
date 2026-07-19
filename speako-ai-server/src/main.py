import sys

# Windows 콘솔의 기본 코드페이지(cp949)는 이모지를 인코딩하지 못해
# print() 호출 시 서버가 부팅도 되기 전에 죽는다. UTF-8로 강제 전환.
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
import json
import uuid

# 1. 분리해둔 AI 클라이언트 모듈들 임포트
from clova.full_generation.generator import FullScriptGenerator
from clova.partial_generation.generator import PartialScriptGenerator
from etri.etri_client import EtriLanguageAnalyzer
from g2p.g2p_client import G2pConverter
from azure_speech.azure_client import PronunciationEvaluator
from utils.ppt_extractor import PptExtractor
from utils.script_storage import save_generated_script

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

# 업로드 파일 제한 (DoS 방지)
MAX_PPT_SIZE_BYTES = 20 * 1024 * 1024   # 20MB
MAX_AUDIO_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
ALLOWED_PPT_EXTENSIONS = {".pptx"}
ALLOWED_AUDIO_EXTENSIONS = {".wav"}
UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB


def _save_upload_with_limit(upload_file: UploadFile, dest_path: str, max_bytes: int, allowed_extensions: set):
    """확장자를 검사하고, 크기 제한을 지키며 업로드 파일을 디스크에 저장합니다."""
    ext = os.path.splitext(upload_file.filename or "")[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=415,
            detail=f"허용되지 않는 파일 형식입니다. ({', '.join(sorted(allowed_extensions))}만 허용)"
        )

    total_bytes = 0
    with open(dest_path, "wb") as buffer:
        while True:
            chunk = upload_file.file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"파일 크기가 너무 큽니다. (최대 {max_bytes // (1024 * 1024)}MB)"
                )
            buffer.write(chunk)

# 4. 각 AI 모듈 객체 생성
full_generator = FullScriptGenerator()
partial_generator = PartialScriptGenerator()
etri_analyzer = EtriLanguageAnalyzer()
g2p_converter = G2pConverter()
azure_evaluator = PronunciationEvaluator()
ppt_extractor = PptExtractor()

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

@app.post("/api/ppt/extract")
async def extract_ppt(file: UploadFile = File(...)):
    """[PPT 구조화 추출 API] 업로드된 PPTX 파일에서 슬라이드별 텍스트와 주제/키워드를 추출합니다."""
    temp_file_path = f"temp_{uuid.uuid4().hex}_{file.filename}"
    try:
        _save_upload_with_limit(file, temp_file_path, MAX_PPT_SIZE_BYTES, ALLOWED_PPT_EXTENSIONS)

        result = ppt_extractor.extract_structured_data(temp_file_path)

        if not result["slides"]:
            raise HTTPException(status_code=422, detail="PPT에서 텍스트를 추출하지 못했습니다.")

        return {"success": True, "data": result}
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.post("/api/script/full")
async def create_full_script(request: FullScriptRequest):
    """[대본 전체 생성 API]"""
    result = full_generator.generate_full_script(request.ppt_text, request.presentation_time, request.style)

    if not result:
        raise HTTPException(status_code=502, detail="대본 생성에 실패했습니다.")

    saved_path = save_generated_script("full", json.dumps(result, ensure_ascii=False, indent=2), stem="full_script", extension="json")
    print(f"💾 생성된 전체 대본 저장: {saved_path}")

    # "Slide N: 내용" 평문도 같이 저장 — 부분 재생성 시 원본 텍스트에서 슬라이드 위치를
    # 별도 매핑 없이 바로 찾을 수 있게 하기 위함.
    if result.get("slides"):
        plain_text = "\n".join(f"Slide {slide['slide_number']}: {slide['script']}" for slide in result["slides"])
        save_generated_script("full", plain_text, stem="full_script_plain", extension="txt")

    return {"success": True, "data": result}

@app.post("/api/script/partial")
async def create_partial_script(request: PartialScriptRequest):
    """[대본 부분 재생성 API]"""
    result = partial_generator.generate_partial_script(request.original_script, request.target_slide, request.feedback)

    if not result:
        raise HTTPException(status_code=502, detail="대본 부분 재생성에 실패했습니다.")

    saved_path = save_generated_script("partial", result, stem=f"slide{request.target_slide}_script", extension="txt")
    print(f"💾 재생성된 부분 대본 저장: {saved_path}")

    return {"success": True, "data": result}

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
    # 동시 요청 시 파일명이 겹치지 않도록 uuid를 붙임
    temp_file_path = f"temp_{uuid.uuid4().hex}_{audio_file.filename}"
    try:
        # 업로드된 파일을 로컬 디스크에 임시 복사 (크기/타입 제한 적용)
        _save_upload_with_limit(audio_file, temp_file_path, MAX_AUDIO_SIZE_BYTES, ALLOWED_AUDIO_EXTENSIONS)

        # Azure 평가 모듈 호출
        result = azure_evaluator.evaluate_audio(temp_file_path, reference_text)

        # 다른 엔드포인트(/api/script/*)와 동일하게, 실패는 200이 아닌 502로 알린다.
        if result.get("status") != "success":
            raise HTTPException(status_code=502, detail=result.get("message", "발음 평가에 실패했습니다."))

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"서버 내부 오류: {str(e)}")
    finally:
        # 평가가 완료되었거나 에러가 났더라도, 서버 용량 낭비를 막기 위해 임시 파일 삭제
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# 6. 서버 실행 코드
if __name__ == "__main__":
    print("🌟 SpeaKO AI 서버를 시작합니다... (http://localhost:8000)")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)