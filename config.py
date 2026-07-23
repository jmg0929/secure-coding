"""애플리케이션 설정.

보안 관련 값은 코드에 하드코딩하지 않고 환경변수(.env)에서 읽어온다.
"""
import os
import secrets
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # --- 핵심 비밀 값 ---
    # 운영 환경에서는 반드시 환경변수로 주입한다. 없으면 임시 키를 생성하되,
    # 프로세스 재시작 시 세션이 모두 무효화되므로 운영에서는 사용하면 안 된다.
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    # --- 데이터베이스 ---
    DATABASE = os.environ.get("DATABASE_PATH") or os.path.join(basedir, "instance", "market.db")

    # --- 세션 / 쿠키 보안 ---
    # 자바스크립트에서 세션 쿠키 접근 차단 (XSS 로 인한 세션 탈취 완화)
    SESSION_COOKIE_HTTPONLY = True
    # CSRF 완화: 외부 사이트발 요청에는 쿠키 미전송
    SESSION_COOKIE_SAMESITE = "Lax"
    # HTTPS 환경에서만 쿠키 전송 (운영에서 True 권장)
    SESSION_COOKIE_SECURE = _get_bool("SESSION_COOKIE_SECURE", default=False)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=6)

    # --- CSRF ---
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 초

    # --- 파일 업로드 ---
    UPLOAD_FOLDER = os.path.join(basedir, "app", "static", "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 요청 최대 5MB (업로드 폭탄 방지)
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # --- 민감정보(계좌번호) 암호화 키 ---
    # hex 64자(32바이트). 미설정 시 SECRET_KEY 에서 HKDF 로 파생한다.
    # 운영에서는 SECRET_KEY 와 분리된 별도 키를 KMS 등으로 관리할 것.
    ACCOUNT_ENC_KEY = os.environ.get("ACCOUNT_ENC_KEY")

    # --- 초기 관리자 계정 ---
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")  # 미설정 시 관리자 자동생성 생략


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = _get_bool("SESSION_COOKIE_SECURE", default=True)

    def __init__(self):
        # 운영에서 SECRET_KEY 미설정은 치명적 → 명시적으로 실패시킨다.
        if not os.environ.get("SECRET_KEY"):
            raise RuntimeError(
                "운영 환경에서는 SECRET_KEY 환경변수를 반드시 설정해야 합니다."
            )


def get_config():
    env = os.environ.get("FLASK_ENV", "development").lower()
    if env == "production":
        return ProductionConfig()
    return DevelopmentConfig()
