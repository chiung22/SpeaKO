# SpeaKO AI 서버 (FastAPI)
#
# ffmpeg가 반드시 필요하다: 브라우저 녹음(webm)과 mp3/m4a를 Azure 발음 평가가 요구하는
# 16kHz 모노 PCM WAV로 변환하는 데 쓴다. 없으면 wav 외 모든 녹음 업로드가 502로 실패한다.
FROM python:3.12-slim

# ffmpeg: 오디오 변환용 / build-essential: kiwipiepy 등 일부 패키지가 소스 빌드될 때 필요
#
# 썸네일용 3종 (편집 화면 왼쪽 슬라이드 미리보기):
#   libreoffice-impress : PPTX → PDF 변환. 브라우저에서 PPTX를 그릴 방법이 없어 서버가 만든다.
#                         impress만 넣는다(전체 libreoffice는 Writer/Calc까지 딸려와 수백 MB 더 커진다).
#   poppler-utils       : PDF → 슬라이드별 PNG (pdftoppm)
#   fonts-nanum         : ⚠️ 없으면 한글이 전부 두부(□□□)로 렌더링된다. 썸네일이 무의미해진다.
#                         (fonts-nanum-coding은 현재 데비안에서 fonts-nanum에 통합돼 별도 설치 불가)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg build-essential \
        libreoffice-impress poppler-utils fonts-nanum \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성만 먼저 복사해서 레이어 캐시를 살린다(소스만 바뀌면 재설치 안 함).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# SQLite 파일과 사용량 로그가 저장되는 위치. 컨테이너를 다시 만들어도 데이터가 남도록 볼륨으로 마운트할 것.
RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

EXPOSE 8000

# --workers는 기본 1이다.
# 대본 생성 작업 상태(job_store)는 DB(script_jobs 테이블)로 옮겼으므로 워커를 늘려도
# 폴링이 404가 나지는 않는다. 다만 레이트 리밋 카운터(utils/rate_limit.py)는 아직
# 프로세스 메모리라, 워커를 N개로 늘리면 실효 상한이 N배가 된다.
# 워커를 늘리려면 레이트 리밋을 공용 저장소(Redis 등)로 먼저 옮길 것.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]
