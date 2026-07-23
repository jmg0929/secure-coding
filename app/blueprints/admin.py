"""관리자 페이지: 통계, 신고 처리, 유저 차단/권한, 상품 숨김/복구."""
from flask import (
    Blueprint, render_template, redirect, url_for, flash, abort, g, request,
)

from ..db import get_db
from ..security import admin_required, new_uuid

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _audit(action: str, target: str = None) -> None:
    """관리자 행위 기록. 권한 오남용을 사후 추적할 수 있어야 한다."""
    db = get_db()
    db.execute(
        """INSERT INTO audit_logs (id, actor_id, action, target, ip)
           VALUES (?, ?, ?, ?, ?)""",
        (new_uuid(), g.user["id"], action, target, request.remote_addr),
    )
    db.commit()


def _collect_stats(db) -> dict:
    """대시보드 통계. 모두 고정 리터럴 쿼리 + 집계."""
    users = dict(db.execute(
        "SELECT status, COUNT(*) FROM users GROUP BY status").fetchall())
    roles = dict(db.execute(
        "SELECT role, COUNT(*) FROM users GROUP BY role").fetchall())
    products = dict(db.execute(
        "SELECT status, COUNT(*) FROM products GROUP BY status").fetchall())
    trades = dict(db.execute(
        "SELECT status, COUNT(*) FROM trades GROUP BY status").fetchall())
    reports = dict(db.execute(
        "SELECT status, COUNT(*) FROM reports GROUP BY status").fetchall())

    volume = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM trades WHERE status = 'confirmed'"
    ).fetchone()[0]
    new_users_7d = db.execute(
        "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 days')"
    ).fetchone()[0]
    new_products_7d = db.execute(
        "SELECT COUNT(*) FROM products WHERE created_at >= datetime('now', '-7 days')"
    ).fetchone()[0]
    messages = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    return {
        "users_total": sum(users.values()),
        "users_active": users.get("active", 0),
        "users_blocked": users.get("blocked", 0),
        "admins": roles.get("admin", 0),
        "new_users_7d": new_users_7d,

        "products_total": sum(products.values()),
        "products_available": products.get("available", 0),
        "products_sold": products.get("sold", 0),
        "products_hidden": products.get("hidden", 0),
        "new_products_7d": new_products_7d,

        "trades_total": sum(trades.values()),
        "trades_ongoing": (trades.get("requested", 0) + trades.get("accepted", 0)
                           + trades.get("sent", 0)),
        "trades_done": trades.get("confirmed", 0),
        "trades_cancelled": trades.get("cancelled", 0),
        "volume": volume,

        "reports_open": reports.get("open", 0),
        "reports_total": sum(reports.values()),
        "messages": messages,
    }


@bp.route("/")
@admin_required
def dashboard():
    db = get_db()
    reports = db.execute(
        """SELECT r.*, u.username AS reporter_name
           FROM reports r JOIN users u ON r.reporter_id = u.id
           ORDER BY (r.status = 'open') DESC, r.created_at DESC""",
    ).fetchall()
    users = db.execute(
        "SELECT id, username, role, status, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    hidden = db.execute(
        """SELECT p.*, u.username AS seller_name
           FROM products p JOIN users u ON p.seller_id = u.id
           WHERE p.status = 'hidden'
           ORDER BY p.created_at DESC""",
    ).fetchall()
    # 거래 내역. 계좌 등 민감정보는 조회하지 않고 거래 메타데이터만 표시한다.
    trades = db.execute(
        """SELECT t.*, p.title AS product_title,
                  b.username AS buyer_name, s.username AS seller_name
           FROM trades t
           JOIN products p ON t.product_id = p.id
           JOIN users b ON t.buyer_id  = b.id
           JOIN users s ON t.seller_id = s.id
           ORDER BY t.updated_at DESC""",
    ).fetchall()
    # 감사 로그. 행위자가 탈퇴해도 기록은 남으므로 LEFT JOIN 으로 조회한다.
    # (로그 조회 자체는 감사 대상이 아니다 — 조회할 때마다 로그가 늘어나는 것을 방지)
    logs = db.execute(
        """SELECT a.*, u.username AS actor_name
           FROM audit_logs a LEFT JOIN users u ON a.actor_id = u.id
           ORDER BY a.created_at DESC
           LIMIT 100""",
    ).fetchall()
    return render_template(
        "admin/dashboard.html",
        stats=_collect_stats(db), reports=reports, users=users,
        hidden=hidden, trades=trades, logs=logs,
    )


@bp.route("/user/<user_id>/block", methods=["POST"])
@admin_required
def toggle_block(user_id):
    db = get_db()
    target = db.execute(
        "SELECT id, username, status, role FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if target is None:
        abort(404)
    if target["role"] == "admin":
        flash("관리자 계정은 차단할 수 없습니다.")
        return redirect(url_for("admin.dashboard"))

    new_status = "active" if target["status"] == "blocked" else "blocked"
    db.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
    db.commit()
    _audit(f"user.{new_status}", target=target["username"])
    flash(f"'{target['username']}' 계정을 {'차단' if new_status == 'blocked' else '차단 해제'}했습니다.")
    return redirect(url_for("admin.dashboard"))


@bp.route("/user/<user_id>/role", methods=["POST"])
@admin_required
def toggle_role(user_id):
    """관리자 권한 부여/회수.

    권한 상승(privilege escalation)에 해당하는 가장 민감한 기능이므로
    아래 안전장치를 둔다.
      - 자기 자신의 권한은 변경할 수 없다 (실수로 스스로를 잠그는 것 방지)
      - 마지막 남은 관리자는 강등할 수 없다 (관리자 0명 상태 방지)
      - 차단된 계정은 승격할 수 없다
      - 모든 변경을 감사 로그에 남긴다
    """
    db = get_db()
    target = db.execute(
        "SELECT id, username, role, status FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if target is None:
        abort(404)

    if target["id"] == g.user["id"]:
        flash("자기 자신의 권한은 변경할 수 없습니다.")
        return redirect(url_for("admin.dashboard"))

    if target["role"] == "admin":
        admin_count = db.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'"
        ).fetchone()[0]
        if admin_count <= 1:
            flash("마지막 관리자는 강등할 수 없습니다.")
            return redirect(url_for("admin.dashboard"))
        new_role = "user"
    else:
        if target["status"] == "blocked":
            flash("차단된 계정은 관리자로 지정할 수 없습니다. 먼저 차단을 해제하세요.")
            return redirect(url_for("admin.dashboard"))
        new_role = "admin"

    db.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    db.commit()
    _audit(f"user.role.{new_role}", target=target["username"])
    flash(f"'{target['username']}' 계정을 {'관리자로 지정' if new_role == 'admin' else '일반 사용자로 변경'}했습니다.")
    return redirect(url_for("admin.dashboard"))


@bp.route("/product/<product_id>/hide", methods=["POST"])
@admin_required
def hide_product(product_id):
    db = get_db()
    row = db.execute(
        "SELECT id, title, status FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if row is None:
        abort(404)
    if row["status"] == "hidden":
        flash("이미 숨김 처리된 상품입니다.")
        return redirect(url_for("admin.dashboard"))

    db.execute("UPDATE products SET status = 'hidden' WHERE id = ?", (product_id,))
    db.commit()
    _audit("product.hide", target=row["title"])
    flash(f"'{row['title']}' 상품을 숨김 처리했습니다.")
    return redirect(url_for("admin.dashboard"))


@bp.route("/product/<product_id>/unhide", methods=["POST"])
@admin_required
def unhide_product(product_id):
    """숨김 해제 → 다시 판매중 상태로 되돌린다."""
    db = get_db()
    row = db.execute(
        "SELECT id, title, status FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if row is None:
        abort(404)
    if row["status"] != "hidden":
        flash("숨김 상태인 상품만 복구할 수 있습니다.")
        return redirect(url_for("admin.dashboard"))

    db.execute("UPDATE products SET status = 'available' WHERE id = ?", (product_id,))
    db.commit()
    _audit("product.unhide", target=row["title"])
    flash(f"'{row['title']}' 상품을 다시 판매중으로 복구했습니다.")
    return redirect(url_for("admin.dashboard"))


@bp.route("/report/<report_id>/resolve", methods=["POST"])
@admin_required
def resolve_report(report_id):
    db = get_db()
    row = db.execute("SELECT id FROM reports WHERE id = ?", (report_id,)).fetchone()
    if row is None:
        abort(404)
    db.execute("UPDATE reports SET status = 'resolved' WHERE id = ?", (report_id,))
    db.commit()
    _audit("report.resolve", target=report_id)
    flash("신고를 처리 완료로 변경했습니다.")
    return redirect(url_for("admin.dashboard"))
