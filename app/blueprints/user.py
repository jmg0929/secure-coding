"""프로필 조회/수정, 비밀번호 변경, 송금, 유저 신고."""
from flask import (
    Blueprint, render_template, redirect, url_for, flash, g, abort,
)

from ..db import get_db
from ..forms import ProfileForm, PasswordChangeForm, ReportForm
from ..security import (
    login_required, hash_password, verify_password, new_uuid,
)

bp = Blueprint("user", __name__, url_prefix="/user")


@bp.route("/<username>")
def profile(username):
    db = get_db()
    user = db.execute(
        "SELECT id, username, bio, role, status, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if user is None:
        abort(404)
    products = db.execute(
        """SELECT * FROM products
           WHERE seller_id = ? AND status != 'hidden'
           ORDER BY created_at DESC""",
        (user["id"],),
    ).fetchall()
    report_form = ReportForm()
    return render_template("user/profile.html", user=user, products=products,
                           report_form=report_form)


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    form = ProfileForm(data={"bio": g.user["bio"]})
    if form.validate_on_submit():
        db = get_db()
        db.execute("UPDATE users SET bio = ? WHERE id = ?",
                   (form.bio.data or "", g.user["id"]))
        db.commit()
        flash("프로필이 업데이트되었습니다.")
        return redirect(url_for("user.profile", username=g.user["username"]))
    return render_template("user/settings.html", form=form)


@bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    form = PasswordChangeForm()
    if form.validate_on_submit():
        db = get_db()
        row = db.execute(
            "SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)
        ).fetchone()
        # 현재 비밀번호 재확인 (세션 탈취/CSRF 대비 민감작업 보호)
        if not verify_password(row["password_hash"], form.current_password.data):
            flash("현재 비밀번호가 올바르지 않습니다.")
            return render_template("user/password.html", form=form)
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                   (hash_password(form.new_password.data), g.user["id"]))
        db.commit()
        flash("비밀번호가 변경되었습니다.")
        return redirect(url_for("user.profile", username=g.user["username"]))
    return render_template("user/password.html", form=form)


@bp.route("/<username>/report", methods=["POST"])
@login_required
def report(username):
    db = get_db()
    target = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if target is None:
        abort(404)
    form = ReportForm()
    if form.validate_on_submit():
        db.execute(
            """INSERT INTO reports (id, reporter_id, target_type, target_id, reason)
               VALUES (?, ?, 'user', ?, ?)""",
            (new_uuid(), g.user["id"], target["id"], form.reason.data),
        )
        db.commit()
        flash("신고가 접수되었습니다.")
    else:
        flash("신고 사유를 확인해 주세요.")
    return redirect(url_for("user.profile", username=username))
