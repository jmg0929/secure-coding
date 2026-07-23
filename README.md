# Tiny Second-hand Shopping Platform

Flask 기반의 소규모 중고거래 플랫폼입니다. **Secure Coding** 과목 과제로,
개발 전 과정에서 보안 약점이 최소화되도록 설계했습니다.

## 주요 기능

- 회원가입 / 로그인 / 로그아웃 (비밀번호 해시 저장)
- 상품 등록 · 조회 · 수정 · 삭제 (이미지 업로드 포함)
- 상품 **검색 · 상태 필터 · 가격 정렬**
- 판매 상태 관리 (판매중 ↔ 거래완료)
- 프로필 조회 / 소개글 수정 / 비밀번호 변경
- **1:1 실시간 채팅** 및 전체 채팅 (Flask-SocketIO)
- **직거래 송금** — 거래 요청·수락·송금·입금확인 4단계 상태 관리
  - 판매자 계좌는 **AES-256-GCM 암호화** 저장, 수락된 거래의 구매자에게만 노출
  - PC 사용자를 위한 **QR 코드 송금 브릿지**
- 유저 / 상품 **신고**
- **관리자** 대시보드
  - 통계(사용자·상품·거래·신고 현황)
  - 신고 처리, 유저 차단/해제, 관리자 권한 지정/해제
  - 상품 숨김/복구, 거래 내역 조회, **감사 로그 열람**

> 💡 **송금 방식** — 이 플랫폼은 사용자의 자금을 보유하거나 중개하지 않습니다.
> 구매자가 본인의 은행 앱으로 판매자에게 직접 이체하고, 플랫폼은 거래 상태만 기록합니다.

## 기술 스택

| 구분 | 사용 기술 |
|------|-----------|
| 언어 | Python 3.13 (개발·검증 기준) |
| 웹 프레임워크 | Flask 3 |
| 실시간 | Flask-SocketIO |
| 폼/CSRF | Flask-WTF (WTForms) |
| 속도 제한 | Flask-Limiter |
| 암호화 | cryptography (AES-256-GCM) |
| QR 생성 | qrcode |
| 데이터베이스 | SQLite (파라미터 바인딩) |
| 템플릿 | Jinja2 (자동 이스케이프) |
| 폰트 | Pretendard Variable (SIL OFL 1.1, 자체 호스팅) |

## 프로젝트 구조

```
secure-coding/
├── run.py                # 실행 진입점 (socketio.run)
├── config.py             # 환경별 설정 (보안 옵션 포함)
├── requirements.txt
├── .env.example          # 환경변수 템플릿
└── app/
    ├── __init__.py       # 애플리케이션 팩토리, 보안 헤더, CLI
    ├── extensions.py     # csrf / limiter / socketio 인스턴스
    ├── db.py             # SQLite 연결 관리
    ├── schema.sql        # DB 스키마 (7개 테이블)
    ├── security.py       # 인증/인가 데코레이터, 해싱, 업로드 검증
    ├── crypto.py         # AES-256-GCM 암·복호화, 키 파생(HKDF)
    ├── forms.py          # WTForms 정의 (서버측 입력 검증)
    ├── blueprints/       # auth, main, product, user, chat, trade, admin
    ├── templates/        # Jinja2 템플릿
    └── static/
        ├── style.css
        ├── js/           # 직접 작성 5개 + Socket.IO 클라이언트
        ├── fonts/        # Pretendard (OFL 라이선스 동봉)
        └── uploads/      # 사용자 업로드 이미지 (git 제외)
```

## 환경 설정 및 실행 방법

### 1. 저장소 클론

```bash
git clone https://github.com/jmg0929/secure-coding.git
cd secure-coding
```

### 2. 가상환경 생성 및 의존성 설치

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 환경변수 설정

`.env.example` 을 `.env` 로 복사한 뒤 값을 채웁니다.
`.env` 는 `.gitignore` 에 포함되어 커밋되지 않습니다.

```bash
cp .env.example .env       # Windows: copy .env.example .env
```

안전한 `SECRET_KEY` 생성:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`.env` 예시:
```
SECRET_KEY=<위에서 생성한 64자 hex>
FLASK_ENV=development
SESSION_COOKIE_SECURE=False
ACCOUNT_ENC_KEY=
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<원하는 관리자 비밀번호>
```

> `ACCOUNT_ENC_KEY` 는 계좌번호 암호화 키입니다. 비워두면 `SECRET_KEY` 에서
> HKDF 로 파생되며, 운영 환경에서는 별도 키를 지정하는 것을 권장합니다.

### 4. 데이터베이스 초기화 (테이블 생성 + 관리자 계정 시드)

```bash
flask --app app init-db
```

### 5. 서버 실행

```bash
python run.py
```

브라우저에서 <http://127.0.0.1:5000> 접속.

> 운영(production) 배포 시에는 `FLASK_ENV=production`, `SESSION_COOKIE_SECURE=True`
> 로 설정하고 HTTPS 를 적용하세요. `SECRET_KEY` 가 없으면 실행이 중단됩니다.

## 보안 설계 요약

이 프로젝트에서 방어한 대표적인 취약점과 대응 방식입니다.

| # | 위협 | 대응 방식 | 위치 |
|---|------|-----------|------|
| 1 | SQL Injection | 모든 쿼리 **파라미터 바인딩(`?`)**, 문자열 결합 금지 | 전 blueprint |
| 2 | XSS (반사/저장/DOM) | Jinja2 자동 이스케이프, 채팅은 서버측 escape + `textContent` 삽입, 엄격한 CSP | 템플릿, `chat.py`, `dm.js` |
| 3 | CSRF | Flask-WTF CSRF 토큰 전 폼 적용, 상태변경은 POST 만 | `forms.py`, 템플릿 |
| 4 | 비밀번호 평문 저장 | `pbkdf2:sha256` 해시 + salt 저장 | `security.py` |
| 5 | **계좌번호 노출** | **AES-256-GCM 암호화**(평문 컬럼 없음), 수락된 거래의 구매자에게만 복호화 | `crypto.py`, `trade.py` |
| 6 | 인증/인가 우회 | `login_required` / `admin_required` 데코레이터, 소유자·거래 당사자 검증 | `security.py`, `product.py`, `trade.py` |
| 7 | 타인 대화 열람 | 채팅방 이름을 본인 세션 ID 로 생성 → 타 사용자 대화 참여 불가 | `chat.py` |
| 8 | 세션 탈취/고정 | `HttpOnly`·`SameSite=Lax`·`Secure` 쿠키, 로그인 시 세션 재발급 | `config.py`, `auth.py` |
| 9 | 무차별 대입 / 남용 | Flask-Limiter 로 로그인·회원가입 속도 제한 | `auth.py` |
| 10 | 악성 파일 업로드 | 확장자 화이트리스트, 무작위 파일명, 용량 제한(5MB) | `security.py`, `config.py` |
| 11 | 계정 열거 | 로그인 실패 메시지 단일화 | `auth.py` |
| 12 | **경쟁 상태(Race Condition)** | 조건부 UPDATE + `rowcount` 검증, DB 부분 UNIQUE 인덱스 | `trade.py`, `schema.sql` |
| 13 | Clickjacking / MIME 스니핑 | `X-Frame-Options`, `X-Content-Type-Options`, CSP 응답 헤더 | `__init__.py` |
| 14 | 비밀정보 하드코딩 | `SECRET_KEY` 등 환경변수 분리, `.env` 커밋 제외 | `config.py`, `.gitignore` |
| 15 | **공급망 공격** | 외부 CDN 미사용 — Socket.IO·폰트·QR 전부 자체 호스팅/생성 | `static/` |
| 16 | **권한 오남용** | 민감 행위 감사 로그 기록(append-only), 관리자 권한 변경 4중 안전장치 | `admin.py`, `trade.py` |

## 기본 계정

- 관리자: `.env` 의 `ADMIN_USERNAME` / `ADMIN_PASSWORD` (기본 `admin`)
- 일반 사용자는 회원가입으로 생성

## 라이선스

교육용 과제 프로젝트입니다.

포함된 서드파티 자원:

| 자원 | 라이선스 |
|------|----------|
| [Pretendard](https://github.com/orioncactus/pretendard) (`app/static/fonts/`) | SIL Open Font License 1.1 — 전문은 `fonts/OFL.txt` 참고 |
| [Socket.IO Client](https://socket.io/) (`app/static/js/socket.io.min.js`) | MIT License |
