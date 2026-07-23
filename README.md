# Tiny Second-hand Shopping Platform

Flask 기반의 소규모 중고거래 플랫폼입니다. **Secure Coding** 과목 과제로,
개발 전 과정에서 보안 약점이 최소화되도록 설계했습니다.

## 주요 기능

- 회원가입 / 로그인 / 로그아웃 (비밀번호 해시 저장)
- 상품 등록 · 조회 · 수정 · 삭제 (이미지 업로드 포함)
- 상품 키워드 검색
- 프로필 조회 / 소개글 수정 / 비밀번호 변경
- 사용자 간 **송금** (잔액 관리)
- **실시간 전체 채팅** (Flask-SocketIO)
- 유저 / 상품 **신고**
- **관리자** 대시보드 (신고 처리, 유저 차단, 상품 숨김)

## 기술 스택

| 구분 | 사용 기술 |
|------|-----------|
| 언어 | Python 3.11+ |
| 웹 프레임워크 | Flask 3 |
| 실시간 | Flask-SocketIO |
| 폼/CSRF | Flask-WTF (WTForms) |
| 속도 제한 | Flask-Limiter |
| 데이터베이스 | SQLite (파라미터 바인딩) |
| 템플릿 | Jinja2 (자동 이스케이프) |

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
    ├── schema.sql        # DB 스키마
    ├── security.py       # 인증/인가 데코레이터, 해싱, 업로드 검증
    ├── forms.py          # WTForms 정의 (서버측 입력 검증)
    ├── blueprints/       # auth, main, product, user, admin, chat
    ├── templates/        # Jinja2 템플릿
    └── static/           # CSS, JS(socket.io 클라이언트 포함), 업로드 폴더
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
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<원하는 관리자 비밀번호>
```

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
| 2 | XSS (반사/저장/DOM) | Jinja2 자동 이스케이프, 채팅은 서버측 escape + `textContent` 삽입, 엄격한 CSP | 템플릿, `chat.py`, `chat.js` |
| 3 | CSRF | Flask-WTF CSRF 토큰 전 폼 적용, 상태변경은 POST 만 | `forms.py`, 템플릿 |
| 4 | 비밀번호 평문 저장 | `pbkdf2:sha256` 해시 + salt 저장 | `security.py` |
| 5 | 인증/인가 우회 | `login_required` / `admin_required` 데코레이터, 소유자 검증 | `security.py`, `product.py` |
| 6 | 세션 탈취/고정 | `HttpOnly`·`SameSite=Lax`·`Secure` 쿠키, 로그인 시 세션 재발급 | `config.py`, `auth.py` |
| 7 | 무차별 대입 / 남용 | Flask-Limiter 로 로그인·회원가입 속도 제한 | `auth.py` |
| 8 | 악성 파일 업로드 | 확장자 화이트리스트, 무작위 파일명, 용량 제한(5MB) | `security.py`, `config.py` |
| 9 | 계정 열거 | 로그인 실패 메시지 단일화 | `auth.py` |
| 10 | Clickjacking / MIME 스니핑 | `X-Frame-Options`, `X-Content-Type-Options`, CSP 응답 헤더 | `__init__.py` |
| 11 | 비밀정보 하드코딩 | `SECRET_KEY` 등 환경변수 분리, `.env` 커밋 제외 | `config.py`, `.gitignore` |

## 기본 계정

- 관리자: `.env` 의 `ADMIN_USERNAME` / `ADMIN_PASSWORD` (기본 `admin`)
- 일반 사용자는 회원가입으로 생성

## 라이선스

교육용 과제 프로젝트.
