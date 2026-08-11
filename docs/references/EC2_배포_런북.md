# EC2 배포 런북 — AI 서버 (speako-ai-server)

2026-08-12 작성. 스프링과 **같은 EC2**에 AI 서버(Docker)를 올리는 절차.
명령은 위에서 아래로 순서대로 실행한다. `${새IP}`는 인스턴스 재시작 후 받은 퍼블릭 IP.

## 0. 전제 조건 (스프링 팀 완료 확인)

- [ ] 인스턴스 유형 **t3.medium**(4GB)으로 변경 완료 (중지 → 유형 변경 → 시작)
- [ ] EBS 루트 볼륨 **20GB**로 확장 + 파티션 확장(`growpart`/`resize2fs`) 완료 — `df -h /`에서 Avail 13GB 안팎
- [ ] `.pem` 키 확보 (채팅·메신저 평문 전송 금지)
- [ ] 보안그룹: 22/8080만 개방, **8000은 개방하지 않음** (스프링이 localhost로 호출)

⚠️ 중지→시작으로 **퍼블릭 IP가 바뀐다.** 프론트가 스프링 주소를 IP로 들고 있으면 갱신할 것.

## 1. Docker 설치 (EC2에서, 최초 1회)

```bash
sudo apt-get update && sudo apt-get install -y docker.io
sudo usermod -aG docker ubuntu   # ubuntu 계정이 sudo 없이 docker 쓰게
exit                              # 재접속해야 그룹이 반영됨
```

## 2. 코드 받기 (EC2에서)

```bash
git clone https://github.com/chiung22/SpeaKO.git
cd SpeaKO/speako-ai-server
```

## 3. `.env` 준비

**(로컬 PC에서)** 로컬의 `.env`를 EC2로 복사한다 — 키 값이 채팅을 거치지 않는 유일한 경로:

```powershell
scp -i 키.pem c:/Users/송치웅/Desktop/Project/SpeaKO/speako-ai-server/.env ubuntu@${새IP}:~/SpeaKO/speako-ai-server/.env
```

**(EC2에서)** `SPEAKO_API_KEY`를 이 자리에서 생성해 덧붙인다 (값이 머신 밖으로 안 나감):

```bash
cd ~/SpeaKO/speako-ai-server
echo "SPEAKO_API_KEY=$(openssl rand -hex 32)" >> .env
grep -c SPEAKO_API_KEY .env   # 1이어야 함 (2 이상이면 중복 — 파일 열어 정리)
```

스프링도 같은 값이 필요하다. **같은 머신이므로** 스프링 담당자가 EC2 안에서 직접 읽어 가면 된다:
`grep SPEAKO_API_KEY ~/SpeaKO/speako-ai-server/.env`

## 4. 빌드 & 실행 (EC2에서)

```bash
cd ~/SpeaKO/speako-ai-server
docker build -t speako-ai .
docker run -d --name speako-ai --restart always \
  -p 127.0.0.1:8000:8000 \
  --env-file .env \
  -v /home/ubuntu/speako-data:/app/data \
  speako-ai
```

- `127.0.0.1:8000` 바인딩: 보안그룹 실수로 8000이 열려도 외부에서 접근 불가(이중 안전장치).
- `-v /home/ubuntu/speako-data`: SQLite·사용량 로그 보존. 컨테이너를 지워도 데이터가 남는다.

## 5. 헬스체크 (EC2에서)

```bash
curl -s localhost:8000/            # 서버 소개 JSON이 나와야 함
docker logs speako-ai | tail -20   # "SPEAKO_API_KEY가 비어 있습니다" 경고가 없어야 함
```

## 6. 스프링 쪽 수정 2가지

### (1) AI 서버 주소 → localhost (환경변수)

```java
// 트라이클라우드페어 주소 대신:
private static final String AI_BASE_URL =
        System.getenv().getOrDefault("AI_BASE_URL", "http://localhost:8000");
```

### (2) 모든 AI 서버 호출에 `X-API-Key` 헤더 (없으면 전부 401)

로컬 테스트에선 키가 꺼져 있어 통과됐지만 EC2에선 켜진다. `PresentationService`·`EvaluationService`
등 **AI 서버를 부르는 모든 곳**의 헤더에 추가:

```java
headers.set("X-API-Key", System.getenv("SPEAKO_API_KEY"));
```

⚠️ **폴링 GET도 예외가 아니다.** `getForEntity`는 헤더를 못 실으므로 `exchange`로 바꿔야 한다:

```java
HttpEntity<Void> authEntity = new HttpEntity<>(headers);   // X-API-Key 포함된 headers
ResponseEntity<Map> statusResponse = restTemplate.exchange(
        AI_BASE_URL + "/api/script/jobs/" + jobId,
        HttpMethod.GET, authEntity, Map.class);
```

스프링 실행 환경변수 예 (systemd면 Environment=, 직접 실행이면 export):

```bash
export AI_BASE_URL=http://localhost:8000
export SPEAKO_API_KEY=<.env에서 읽은 값>
java -Xmx1g -jar app.jar   # 4GB 공유 머신이므로 JVM 상한 1GB 권장
```

## 7. E2E 검증 (배포 완료 판정)

1. 스프링 경유 대본 생성 1회 (202 → 폴링 → completed → DB 저장)
2. 스프링 경유 발음 평가 1회 — **이번엔 긴 녹음(1분 50초짜리)도 가능** (터널 120초 상한이 사라짐)
3. `docker logs speako-ai`에서 401/422/500 없는지 확인

## 8. 운영 명령 모음

```bash
docker logs -f speako-ai                      # 실시간 로그
docker restart speako-ai                      # 재시작
# 코드 갱신 재배포:
cd ~/SpeaKO && git pull && cd speako-ai-server \
  && docker build -t speako-ai . \
  && docker rm -f speako-ai && docker run -d --name speako-ai --restart always \
     -p 127.0.0.1:8000:8000 --env-file .env -v /home/ubuntu/speako-data:/app/data speako-ai
```

## 9. 철거 (2026-08-22 이후)

시연이 끝나면 외부 API를 전부 해지하기로 확정(8/09). EC2도 같이 정리:
컨테이너/이미지 삭제 → 인스턴스 중지(요금 절약) 또는 종료 → `.env`의 키들은 해지로 무효화됨.
