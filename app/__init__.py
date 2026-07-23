"""애플리케이션 팩토리."""
import mimetypes
import os

import click
from flask import Flask, render_template

# 일부 환경에서 .woff2 MIME 이 등록되어 있지 않아 application/octet-stream 으로
# 응답된다. nosniff 헤더를 함께 쓰므로 정확한 타입을 명시해 준다.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")

from config import get_config
from . import db
from .extensions import csrf, limiter, socketio
from .security import load_logged_in_user, hash_password, new_uuid


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or get_config())

    # 업로드 폴더 보장
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # 확장 초기화
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    socketio.init_app(app)

    # 요청마다 로그인 사용자 로딩
    @app.before_request
    def _load_user():
        load_logged_in_user()

    # 보안 응답 헤더 (Clickjacking / MIME 스니핑 / 기본 XSS 완화)
    @app.after_request
    def _security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        # 자체 리소스만 허용하는 보수적인 CSP (인라인 스크립트 차단)
        # 폰트는 외부 CDN 없이 자체 호스팅하므로 font-src 도 'self' 로 제한한다.
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; "
            "style-src 'self'; script-src 'self'; font-src 'self'; "
            "connect-src 'self'; frame-ancestors 'none'"
        )
        return resp

    # 블루프린트 등록
    from .blueprints import auth, main, product, user, admin, chat, trade
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(product.bp)
    app.register_blueprint(user.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(chat.bp)
    app.register_blueprint(trade.bp)

    # 에러 핸들러
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, message="접근 권한이 없습니다."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="페이지를 찾을 수 없습니다."), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("error.html", code=413, message="업로드 용량이 너무 큽니다."), 413

    _register_cli(app)
    return app


def _register_cli(app):
    @app.cli.command("init-db")
    def init_db_command():
        """DB 테이블 생성 후 관리자 계정을 시드한다."""
        db.init_db()
        _seed_admin(app)
        click.echo("데이터베이스 초기화 완료.")


def _seed_admin(app):
    """환경변수로 지정된 관리자 계정을 생성(없을 때만)."""
    admin_user = app.config.get("ADMIN_USERNAME")
    admin_pw = app.config.get("ADMIN_PASSWORD")
    if not admin_pw:
        click.echo("ADMIN_PASSWORD 미설정 → 관리자 자동 생성을 건너뜁니다.")
        return
    conn = db.get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (admin_user,)
    ).fetchone()
    if existing:
        return
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role) VALUES (?, ?, ?, 'admin')",
        (new_uuid(), admin_user, hash_password(admin_pw)),
    )
    conn.commit()
    click.echo(f"관리자 계정 '{admin_user}' 생성 완료.")
