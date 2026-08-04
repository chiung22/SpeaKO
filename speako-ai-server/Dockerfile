# SpeaKO AI 서버 (FastAPI)
#
# ffmpeg가 반드시 필요하다: 브라우저 녹음(webm)과 mp3/m4a를 Azure 발음 평가가 요구하는
# 16kHz 모노 PCM WAV로 변환하는 데 쓴다. 없으면 wav 외 모든 녹음 업로드가 502로 실패한다.
FROM python:3.12-slim

# ffmpeg: 오디오 변환용 / 나머지: kiwipiepy 등 일부 패키지가 소스 빌드될 때 필요
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg build-essential \
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

# --workers는 기본 1이다. 지금 대본 생성 작업 상태(job_store)는 프로세스 메모리에 있어서,
# 워커를 여러 개로 늘리면 생성 상태 조회가 다른 워커로 가서 404가 날 수 있다.
# 워커를 늘리려면 job_store를 DB 구현으로 먼저 바꿔야 한다.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "src"]
