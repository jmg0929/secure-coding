"""메인 페이지: 상품 목록, 검색, 필터/정렬."""
from flask import Blueprint, render_template, request

from ..db import get_db

bp = Blueprint("main", __name__)

# 필터/정렬 화이트리스트.
#   사용자 입력은 '키를 고르는 용도'로만 쓰고, 실제 SQL 조각은 아래 상수에서만 가져온다.
#   따라서 사용자 입력이 SQL 문자열에 직접 들어가는 경로가 존재하지 않는다.
_FILTERS = {
    "all":       "p.status != 'hidden'",
    "available": "p.status = 'available'",
    "sold":      "p.status = 'sold'",
}
_SORTS = {
    "recent": "p.created_at DESC",
    "low":    "p.price ASC, p.created_at DESC",
    "high":   "p.price DESC, p.created_at DESC",
}
_DEFAULT_FILTER = "all"
_DEFAULT_SORT = "recent"


@bp.route("/")
def index():
    db = get_db()
    query = (request.args.get("q") or "").strip()

    # 화이트리스트에 없는 값은 조용히 기본값으로 대체
    f_key = request.args.get("f") if request.args.get("f") in _FILTERS else _DEFAULT_FILTER
    s_key = request.args.get("s") if request.args.get("s") in _SORTS else _DEFAULT_SORT

    where = [_FILTERS[f_key]]
    params = []

    if query:
        # 사용자 입력의 LIKE 와일드카드(%, _)는 이스케이프하고 값은 바인딩으로 전달
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        where.append(
            "(p.title LIKE ? ESCAPE '\\' OR p.description LIKE ? ESCAPE '\\')"
        )
        params.extend([like, like])

    # 판매중을 먼저 노출(전체 보기일 때만 의미 있음)
    order = _SORTS[s_key]
    if f_key == "all":
        order = "(p.status = 'available') DESC, " + order

    sql = (
        "SELECT p.*, u.username AS seller_name "
        "FROM products p JOIN users u ON p.seller_id = u.id "
        "WHERE " + " AND ".join(where) + " ORDER BY " + order
    )
    products = db.execute(sql, params).fetchall()

    # 필터 탭에 표시할 건수
    counts = dict(db.execute(
        """SELECT status, COUNT(*) FROM products
           WHERE status != 'hidden' GROUP BY status"""
    ).fetchall())
    stats = {
        "all": sum(counts.values()),
        "available": counts.get("available", 0),
        "sold": counts.get("sold", 0),
    }

    return render_template(
        "index.html", products=products, q=query,
        f=f_key, s=s_key, stats=stats,
    )
