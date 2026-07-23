"""직거래(송금) 기능.

플랫폼은 사용자의 돈을 보유·중개하지 않는다.
구매자가 **자신의 은행 앱으로 판매자에게 직접 이체**하고,
플랫폼은 거래 진행 상태만 기록한다.

거래 상태 흐름
    requested → accepted → sent → confirmed
       (구매자)   (판매자)   (구매자) (판매자)

핵심 보안 규칙
  - 판매자 계좌번호는 AES-GCM 암호문으로만 저장한다.
  - 계좌 평문은 **수락된 거래의 구매자**에게만, 그 순간에만 복호화해 보여준다.
  - 각 상태 전이는 정해진 당사자만 수행할 수 있다(구매자/판매자 구분).
  - 계좌 열람은 감사 로그에 남긴다.
"""
import base64
import io
from urllib.parse import quote

import qrcode
import qrcode.image.svg
from flask import (
    Blueprint, render_template, redirect, url_for, flash, g, abort,
    current_app, request,
)

from ..db import get_db
from ..crypto import derive_key, encrypt, decrypt, DecryptError
from ..forms import PayoutAccountForm, TradeActionForm
from ..security import login_required, new_uuid

bp = Blueprint("trade", __name__, url_prefix="/trade")


# --- 감사 로그 -------------------------------------------------------------
def _audit(action: str, target: str = None) -> None:
    db = get_db()
    db.execute(
        """INSERT INTO audit_logs (id, actor_id, action, target, ip)
           VALUES (?, ?, ?, ?, ?)""",
        (new_uuid(), g.user["id"] if g.user else None, action, target,
         request.remote_addr),
    )
    db.commit()


# --- 송금 링크 / QR ---------------------------------------------------------
def toss_send_link(bank_name: str, account_no: str, amount: int) -> str:
    """토스 송금 딥링크.

    딥링크는 해당 앱이 설치된 모바일에서만 동작한다. PC 에는 이를 처리할
    앱이 없고, 은행들도 외부 사이트가 송금창을 열도록 허용하지 않는다
    (허용하면 그 자체가 CSRF 공격 벡터가 된다).
    → PC 에서는 아래 QR 을 휴대폰으로 스캔하는 방식으로 우회한다.
    """
    return (
        "supertoss://send"
        f"?bank={quote(bank_name)}"
        f"&accountNo={quote(account_no)}"
        f"&amount={amount}"
    )


def qr_data_uri(text: str) -> str:
    """QR 코드를 SVG data URI 로 생성.

    <img src="data:..."> 로 삽입하므로 CSP(img-src 'self' data:)를 유지한 채
    인라인 스크립트나 외부 CDN 없이 렌더링된다.
    """
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage,
                      box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:image/svg+xml;base64," + b64


def _get_trade_or_404(trade_id):
    row = get_db().execute(
        """SELECT t.*, p.title AS product_title, p.image_path,
                  b.username AS buyer_name, s.username AS seller_name
           FROM trades t
           JOIN products p ON t.product_id = p.id
           JOIN users b ON t.buyer_id  = b.id
           JOIN users s ON t.seller_id = s.id
           WHERE t.id = ?""",
        (trade_id,),
    ).fetchone()
    if row is None:
        abort(404)
    return row


def _require_participant(trade):
    """거래 당사자(또는 관리자)만 접근 허용."""
    if g.user["id"] not in (trade["buyer_id"], trade["seller_id"]) \
            and g.user["role"] != "admin":
        abort(403)


def _set_status(trade_id, new_status, expected_current):
    """상태 전이. 현재 상태가 기대값일 때만 바뀌므로 중복/역행 전이를 막는다."""
    db = get_db()
    cur = db.execute(
        """UPDATE trades SET status = ?, updated_at = datetime('now')
           WHERE id = ? AND status = ?""",
        (new_status, trade_id, expected_current),
    )
    db.commit()
    return cur.rowcount == 1


# --- 정산 계좌 등록 --------------------------------------------------------
@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    db = get_db()
    existing = db.execute(
        "SELECT bank_name, account_last4, holder_name, updated_at "
        "FROM payout_accounts WHERE user_id = ?",
        (g.user["id"],),
    ).fetchone()

    form = PayoutAccountForm()
    if form.validate_on_submit():
        # 계좌번호에서 숫자만 남긴다(하이픈/공백 허용 입력)
        digits = "".join(ch for ch in form.account_no.data if ch.isdigit())
        if not (8 <= len(digits) <= 20):
            flash("계좌번호는 숫자 8~20자리여야 합니다.")
            return render_template("trade/account.html", form=form, existing=existing)

        key = derive_key(current_app.config)
        db.execute(
            """INSERT INTO payout_accounts
                   (user_id, bank_name, account_enc, account_last4, holder_name, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET
                   bank_name = excluded.bank_name,
                   account_enc = excluded.account_enc,
                   account_last4 = excluded.account_last4,
                   holder_name = excluded.holder_name,
                   updated_at = datetime('now')""",
            (g.user["id"], form.bank_name.data, encrypt(digits, key),
             digits[-4:], form.holder_name.data),
        )
        db.commit()
        _audit("payout_account.upsert")
        flash("정산 계좌가 저장되었습니다.")
        return redirect(url_for("trade.account"))

    return render_template("trade/account.html", form=form, existing=existing)


# --- 거래 목록 / 상세 ------------------------------------------------------
@bp.route("/")
@login_required
def my_trades():
    db = get_db()
    rows = db.execute(
        """SELECT t.*, p.title AS product_title, p.image_path,
                  b.username AS buyer_name, s.username AS seller_name
           FROM trades t
           JOIN products p ON t.product_id = p.id
           JOIN users b ON t.buyer_id  = b.id
           JOIN users s ON t.seller_id = s.id
           WHERE t.buyer_id = ? OR t.seller_id = ?
           ORDER BY t.updated_at DESC""",
        (g.user["id"], g.user["id"]),
    ).fetchall()
    return render_template("trade/list.html", trades=rows)


@bp.route("/<trade_id>")
@login_required
def detail(trade_id):
    trade = _get_trade_or_404(trade_id)
    _require_participant(trade)

    is_buyer = g.user["id"] == trade["buyer_id"]
    account_info = None

    # 계좌 평문은 '수락된 이후'의 '구매자'에게만 노출한다.
    if is_buyer and trade["status"] in ("accepted", "sent"):
        row = get_db().execute(
            "SELECT bank_name, account_enc, holder_name FROM payout_accounts WHERE user_id = ?",
            (trade["seller_id"],),
        ).fetchone()
        if row:
            try:
                account_no = decrypt(row["account_enc"], derive_key(current_app.config))
                link = toss_send_link(row["bank_name"], account_no, trade["amount"])
                account_info = {
                    "bank_name": row["bank_name"],
                    "holder_name": row["holder_name"],
                    "account_no": account_no,
                    "toss_link": link,
                    # PC 에서 휴대폰으로 넘기기 위한 QR
                    "qr_uri": qr_data_uri(link),
                    # 앱이 없어도 쓸 수 있도록 계좌 정보 자체를 담은 QR
                    "qr_text_uri": qr_data_uri(
                        f"{row['bank_name']} {account_no} {row['holder_name']} "
                        f"{trade['amount']}원"
                    ),
                }
                _audit("payout_account.view", target=trade_id)
            except DecryptError:
                current_app.logger.error("계좌 복호화 실패: trade=%s", trade_id)
                flash("계좌 정보를 불러올 수 없습니다. 판매자에게 문의하세요.")

    return render_template(
        "trade/detail.html",
        trade=trade, is_buyer=is_buyer,
        account_info=account_info, form=TradeActionForm(),
    )


# --- 상태 전이 -------------------------------------------------------------
@bp.route("/request/<product_id>", methods=["POST"])
@login_required
def create(product_id):
    """구매 요청 (구매자)."""
    form = TradeActionForm()
    if not form.validate_on_submit():
        abort(400)

    db = get_db()
    product = db.execute(
        "SELECT id, seller_id, price, status FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if product is None:
        abort(404)
    if product["seller_id"] == g.user["id"]:
        flash("자신의 상품은 구매할 수 없습니다.")
        return redirect(url_for("product.detail", product_id=product_id))
    if product["status"] != "available":
        flash("이미 거래가 완료되었거나 판매 중이 아닌 상품입니다.")
        return redirect(url_for("product.detail", product_id=product_id))

    # 판매자가 정산 계좌를 등록하지 않았다면 거래를 시작할 수 없다.
    has_account = db.execute(
        "SELECT 1 FROM payout_accounts WHERE user_id = ?", (product["seller_id"],)
    ).fetchone()
    if not has_account:
        flash("판매자가 아직 정산 계좌를 등록하지 않았습니다. 채팅으로 문의해 보세요.")
        return redirect(url_for("product.detail", product_id=product_id))

    trade_id = new_uuid()
    try:
        db.execute(
            """INSERT INTO trades (id, product_id, buyer_id, seller_id, amount)
               VALUES (?, ?, ?, ?, ?)""",
            (trade_id, product_id, g.user["id"], product["seller_id"], product["price"]),
        )
        db.commit()
    except Exception:
        # UNIQUE 인덱스 위반 = 이미 진행 중인 거래가 있음
        db.rollback()
        existing = db.execute(
            """SELECT id FROM trades
               WHERE product_id = ? AND buyer_id = ?
                 AND status IN ('requested', 'accepted', 'sent')""",
            (product_id, g.user["id"]),
        ).fetchone()
        if existing:
            flash("이미 진행 중인 거래가 있습니다.")
            return redirect(url_for("trade.detail", trade_id=existing["id"]))
        flash("거래 요청 중 오류가 발생했습니다.")
        return redirect(url_for("product.detail", product_id=product_id))

    flash("구매 요청을 보냈습니다. 판매자의 수락을 기다려 주세요.")
    return redirect(url_for("trade.detail", trade_id=trade_id))


@bp.route("/<trade_id>/accept", methods=["POST"])
@login_required
def accept(trade_id):
    """거래 수락 (판매자만)."""
    form = TradeActionForm()
    if not form.validate_on_submit():
        abort(400)
    trade = _get_trade_or_404(trade_id)
    if g.user["id"] != trade["seller_id"]:
        abort(403)
    if not _set_status(trade_id, "accepted", "requested"):
        flash("이미 처리된 거래입니다.")
    else:
        flash("거래를 수락했습니다. 구매자에게 계좌가 안내됩니다.")
    return redirect(url_for("trade.detail", trade_id=trade_id))


@bp.route("/<trade_id>/sent", methods=["POST"])
@login_required
def mark_sent(trade_id):
    """송금 완료 표시 (구매자만)."""
    form = TradeActionForm()
    if not form.validate_on_submit():
        abort(400)
    trade = _get_trade_or_404(trade_id)
    if g.user["id"] != trade["buyer_id"]:
        abort(403)
    if not _set_status(trade_id, "sent", "accepted"):
        flash("지금은 송금 완료로 표시할 수 없습니다.")
    else:
        flash("송금 완료로 표시했습니다. 판매자의 입금 확인을 기다려 주세요.")
    return redirect(url_for("trade.detail", trade_id=trade_id))


@bp.route("/<trade_id>/confirm", methods=["POST"])
@login_required
def confirm(trade_id):
    """입금 확인 (판매자만) → 상품을 판매완료 처리."""
    form = TradeActionForm()
    if not form.validate_on_submit():
        abort(400)
    trade = _get_trade_or_404(trade_id)
    if g.user["id"] != trade["seller_id"]:
        abort(403)

    if not _set_status(trade_id, "confirmed", "sent"):
        flash("지금은 입금 확인을 할 수 없습니다.")
        return redirect(url_for("trade.detail", trade_id=trade_id))

    db = get_db()
    db.execute("UPDATE products SET status = 'sold' WHERE id = ?", (trade["product_id"],))
    db.commit()
    _audit("trade.confirmed", target=trade_id)
    flash("입금을 확인했습니다. 거래가 완료되었습니다!")
    return redirect(url_for("trade.detail", trade_id=trade_id))


@bp.route("/<trade_id>/cancel", methods=["POST"])
@login_required
def cancel(trade_id):
    """거래 취소 (양쪽 모두 가능, 단 입금확인 전까지)."""
    form = TradeActionForm()
    if not form.validate_on_submit():
        abort(400)
    trade = _get_trade_or_404(trade_id)
    _require_participant(trade)

    if trade["status"] in ("confirmed", "cancelled"):
        flash("이미 종료된 거래입니다.")
        return redirect(url_for("trade.detail", trade_id=trade_id))

    db = get_db()
    db.execute(
        """UPDATE trades SET status = 'cancelled', updated_at = datetime('now')
           WHERE id = ? AND status NOT IN ('confirmed', 'cancelled')""",
        (trade_id,),
    )
    db.commit()
    flash("거래를 취소했습니다.")
    return redirect(url_for("trade.detail", trade_id=trade_id))
