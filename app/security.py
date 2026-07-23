"""인증/인가 및 보안 유틸리티."""
import functools
import os
import uuid

from flask import g, redirect, session, url_for, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from .db import get_db


# --- 비밀번호 해싱 ---------------------------------------------------------
# pbkdf2:sha256 는 표준 라이브러리만으로 동작하며 플랫폼 의존성이 없다.
def hash_password(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)


def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def new_uuid() -> str:
    return uuid.uuid4().hex


# --- 현재 사용자 로딩 ------------------------------------------------------
def load_logged_in_user() -> None:
    """세션의 user_id 로 사용자 정보를 g.user 에 적재. before_request 에서 호출."""
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return
    db = get_db()
    g.user = db.execute(
        "SELECT id, username, bio, role, status FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    # 세션은 살아있으나 계정이 삭제/차단된 경우 세션 무효화
    if g.user is None or g.user["status"] == "blocked":
        session.clear()
        g.user = None


# --- 접근 제어 데코레이터 --------------------------------------------------
def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("로그인이 필요합니다.")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        if g.user["role"] != "admin":
            abort(403)  # 권한 없음 (수평/수직 권한 상승 차단)
        return view(*args, **kwargs)
    return wrapped


# --- 파일 업로드 검증 ------------------------------------------------------
def is_allowed_image(filename: str, allowed_exts: set) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_exts


def save_uploaded_image(file_storage, upload_folder: str, allowed_exts: set):
    """업로드 이미지를 검증 후 안전한 무작위 파일명으로 저장.

    반환: 저장된 파일명(성공) 또는 None(파일 없음/무시).
    확장자 화이트리스트를 통과하지 못하면 ValueError.
    """
    if file_storage is None or file_storage.filename == "":
        return None

    original = secure_filename(file_storage.filename)  # 경로 조작 방지
    if not is_allowed_image(original, allowed_exts):
        raise ValueError("허용되지 않는 이미지 형식입니다.")

    ext = original.rsplit(".", 1)[1].lower()
    safe_name = f"{new_uuid()}.{ext}"          # 사용자 입력 파일명 신뢰하지 않음
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, safe_name))
    return safe_name
