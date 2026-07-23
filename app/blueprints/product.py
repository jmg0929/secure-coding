"""상품 등록 / 상세 / 수정 / 삭제 / 신고."""
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, g,
    current_app, abort,
)

from ..db import get_db
from ..forms import ProductForm, ReportForm
from ..security import login_required, new_uuid, save_uploaded_image

bp = Blueprint("product", __name__, url_prefix="/product")


def _get_product_or_404(product_id):
    db = get_db()
    row = db.execute(
        """SELECT p.*, u.username AS seller_name
           FROM products p JOIN users u ON p.seller_id = u.id
           WHERE p.id = ?""",
        (product_id,),
    ).fetchone()
    if row is None:
        abort(404)
    return row


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = ProductForm()
    if form.validate_on_submit():
        image_name = None
        try:
            image_name = save_uploaded_image(
                request.files.get("image"),
                current_app.config["UPLOAD_FOLDER"],
                current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
            )
        except ValueError as e:
            flash(str(e))
            return render_template("product/form.html", form=form, mode="new")

        db = get_db()
        db.execute(
            """INSERT INTO products (id, seller_id, title, description, price, image_path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (new_uuid(), g.user["id"], form.title.data, form.description.data,
             form.price.data, image_name),
        )
        db.commit()
        flash("상품이 등록되었습니다.")
        return redirect(url_for("main.index"))

    return render_template("product/form.html", form=form, mode="new")


@bp.route("/<product_id>")
def detail(product_id):
    product = _get_product_or_404(product_id)
    report_form = ReportForm()
    return render_template("product/detail.html", product=product, report_form=report_form)


@bp.route("/<product_id>/edit", methods=["GET", "POST"])
@login_required
def edit(product_id):
    product = _get_product_or_404(product_id)
    # 인가: 소유자 또는 관리자만 수정 가능 (수평적 권한 상승 차단)
    if product["seller_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)

    form = ProductForm(data={
        "title": product["title"],
        "description": product["description"],
        "price": product["price"],
    })
    if form.validate_on_submit():
        image_name = product["image_path"]
        try:
            uploaded = save_uploaded_image(
                request.files.get("image"),
                current_app.config["UPLOAD_FOLDER"],
                current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
            )
            if uploaded:
                image_name = uploaded
        except ValueError as e:
            flash(str(e))
            return render_template("product/form.html", form=form, mode="edit", product=product)

        db = get_db()
        db.execute(
            """UPDATE products SET title = ?, description = ?, price = ?, image_path = ?
               WHERE id = ?""",
            (form.title.data, form.description.data, form.price.data,
             image_name, product_id),
        )
        db.commit()
        flash("상품이 수정되었습니다.")
        return redirect(url_for("product.detail", product_id=product_id))

    return render_template("product/form.html", form=form, mode="edit", product=product)


@bp.route("/<product_id>/delete", methods=["POST"])
@login_required
def delete(product_id):
    product = _get_product_or_404(product_id)
    if product["seller_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)
    db = get_db()
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    flash("상품이 삭제되었습니다.")
    return redirect(url_for("main.index"))


@bp.route("/<product_id>/status", methods=["POST"])
@login_required
def toggle_status(product_id):
    """판매중 ↔ 판매완료 전환. 판매자 본인(또는 관리자)만 가능."""
    product = _get_product_or_404(product_id)
    if product["seller_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)

    # 관리자가 숨김 처리한 상품은 판매자가 되돌릴 수 없다.
    if product["status"] == "hidden":
        flash("숨김 처리된 상품은 상태를 변경할 수 없습니다.")
        return redirect(url_for("product.detail", product_id=product_id))

    new_status = "sold" if product["status"] == "available" else "available"
    db = get_db()
    db.execute("UPDATE products SET status = ? WHERE id = ?", (new_status, product_id))
    db.commit()
    flash("판매완료로 변경했습니다." if new_status == "sold" else "다시 판매중으로 변경했습니다.")
    return redirect(url_for("product.detail", product_id=product_id))


@bp.route("/<product_id>/report", methods=["POST"])
@login_required
def report(product_id):
    _get_product_or_404(product_id)   # 존재하지 않는 상품에 대한 신고 차단
    form = ReportForm()
    if form.validate_on_submit():
        db = get_db()
        db.execute(
            """INSERT INTO reports (id, reporter_id, target_type, target_id, reason)
               VALUES (?, ?, 'product', ?, ?)""",
            (new_uuid(), g.user["id"], product_id, form.reason.data),
        )
        db.commit()
        flash("신고가 접수되었습니다.")
    else:
        flash("신고 사유를 확인해 주세요.")
    return redirect(url_for("product.detail", product_id=product_id))
