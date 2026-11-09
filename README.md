# 🍞 FrenchToast

Python(discord.py) 디스코드 봇 · 접두사 `+` · Render.com 무료 플랜 24시간 구동

## 기능

| 명령어 | 설명 | 권한 |
|---|---|---|
| `+움짤` + 이미지 | 이미지를 GIF 로 변환해 요청자 프로필·닉네임과 함께 임베드로 출력 | 누구나 |
| `+입장설정 #채널 [메시지]` | 입장 메시지 채널/문구 설정 | 서버 관리 |
| `+퇴장설정 #채널 [메시지]` | 퇴장 메시지 채널/문구 설정 | 서버 관리 |
| `+입장끄기` / `+퇴장끄기` | 끄기 | 서버 관리 |
| `+입장테스트` / `+퇴장테스트` | 본인으로 미리 보내보기 | 서버 관리 |
| `+설정확인` | 현재 서버 설정 보기 | 서버 관리 |
| `+도움말` / `+핑` | 도움말 / 지연시간 | 누구나 |

**`+움짤` 입력 방법**: 이미지 첨부, 이미지 URL, 커스텀 이모지, 또는 이미지가 있는 메시지에 답장하면서 `+움짤`.
뒤에 텍스트를 붙이면 캡션이 됩니다 (`+움짤 오늘 점심`). PNG/JPG/WEBP/GIF/APNG/BMP 지원 (움직이는 WEBP·APNG 도 애니메이션 유지).
서버 업로드 한도(기본 10MB)를 넘으면 자동으로 크기를 줄입니다. 봇에 **메시지 관리** 권한이 있으면 원본 명령 메시지는 지워집니다.

**메시지 치환자**: `{user}` 멘션 · `{name}` 닉네임 · `{username}` 아이디 · `{server}` 서버 이름 · `{count}` 인원 수
예) `+입장설정 #환영 {user}님 어서오세요! {server}의 {count}번째 멤버입니다 🎉`

## 1. 디스코드 봇 만들기

1. https://discord.com/developers/applications → **New Application** → 이름 `FrenchToast`
2. **Bot** 탭 → **Reset Token** 으로 토큰 복사 (= `DISCORD_TOKEN`)
3. 같은 Bot 탭의 **Privileged Gateway Intents** 에서 아래 두 개 **반드시 켜기**
   - `SERVER MEMBERS INTENT` (입장/퇴장 감지)
   - `MESSAGE CONTENT INTENT` (`+` 명령어 인식)
4. **OAuth2 → URL Generator**: scope `bot`, 권한 `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`, `View Channels`, (선택) `Manage Messages` → 생성된 URL 로 서버에 초대

## 2. 설정 저장용 MongoDB (무료)

Render 무료 플랜은 디스크가 휘발성이라 재시작마다 파일이 사라집니다. 서버별 설정을 유지하려면:

1. https://www.mongodb.com/atlas 에서 무료(M0) 클러스터 생성
2. Database Access 에서 사용자 생성, Network Access 에 `0.0.0.0/0` 추가
3. Connect → Drivers → 연결 문자열 복사 (= `MONGODB_URI`, `<password>` 부분 교체)

## 3. Render 배포

1. 이 폴더를 GitHub 저장소로 push
2. Render 대시보드 → **New → Blueprint** → 저장소 선택 (`render.yaml` 자동 인식)
   - 또는 **New → Web Service**, Build `pip install -r requirements.txt`, Start `python main.py`, Instance Type **Free**
3. 환경변수 `DISCORD_TOKEN`, `MONGODB_URI` 입력 → 배포

### 24시간 깨어 있게 하기

Render 무료 Web Service 는 **15분간 HTTP 요청이 없으면 슬립**합니다(봇도 오프라인이 됨).
https://uptimerobot.com (무료) 에서 HTTP(s) 모니터를 만들고 `https://<앱이름>.onrender.com/health` 를 **5분 간격**으로 등록하세요.

> 참고: Render 무료 플랜은 월 750 인스턴스 시간 제공 → 봇 1개를 한 달 내내 돌리기에 충분합니다.

## 로컬 실행

```bash
python -m venv .venv
```
```bash
.venv\Scripts\activate
```
```bash
pip install -r requirements.txt
```
```bash
copy .env.example .env
```
`.env` 에 토큰을 넣고:
```bash
python main.py
```

## 구조

```
main.py            봇 진입점, 에러 처리
keep_alive.py      Render 용 HTTP 서버 (/ , /health)
cogs/welcome.py    입장/퇴장 메시지
cogs/gif.py        +움짤 GIF 변환
cogs/general.py    도움말, 핑
utils/storage.py   MongoDB / JSON 저장소
```
