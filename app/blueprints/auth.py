"""회원가입 / 로그인 / 로그아웃."""
from flask import (
    Blueprint, render_template, redirect, url_for, flash, session, g,
)

from ..db import get_db
from ..extensions import limiter
from ..forms import RegisterForm, LoginForm
from ..security import hash_password, verify_password, new_uuid

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")  # 계정 대량 생성 억제
def register():
    if g.user:
        return redirect(url_for("main.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        db = get_db()
        exists = db.execute(
            "SELECT 1 FROM users WHERE username = ?", (form.username.data,)
        ).fetchone()
        if exists:
            flash("이미 사용 중인 아이디입니다.")
            return render_template("auth/register.html", form=form)

        db.execute(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
            (new_uuid(), form.username.data, hash_password(form.password.data)),
        )
        db.commit()
        flash("회원가입이 완료되었습니다. 로그인해 주세요.")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")  # 무차별 대입(brute force) 완화
def login():
    if g.user:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (form.username.data,)
        ).fetchone()

        # 아이디/비밀번호 어느 쪽이 틀렸는지 노출하지 않는다(계정 열거 방지).
        if user is None or not verify_password(user["password_hash"], form.password.data):
            flash("아이디 또는 비밀번호가 올바르지 않습니다.")
            return render_template("auth/login.html", form=form)

        if user["status"] == "blocked":
            flash("차단된 계정입니다. 관리자에게 문의하세요.")
            return render_template("auth/login.html", form=form)

        # 세션 고정 공격 방지: 로그인 성공 시 세션 갱신
        session.clear()
        session["user_id"] = user["id"]
        session.permanent = True
        flash("로그인되었습니다.")
        return redirect(url_for("main.index"))

    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])  # 상태변경은 POST + CSRF 토큰
def logout():
    session.clear()
    flash("로그아웃되었습니다.")
    return redirect(url_for("main.index"))
