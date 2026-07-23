"""채팅 기능.

- 전체 채팅방 (모든 사용자)
- 1:1 채팅 (구매자 ↔ 판매자), DB 에 대화 내용 저장

보안:
- 모든 SocketIO 이벤트에서 세션 기반 인증을 다시 확인한다.
- 1:1 방 이름은 두 사용자 ID 로만 결정되며, 참여자는 반드시 본인 세션 ID 를
  포함해야 하므로 임의의 방을 훔쳐볼 수 없다.
- 메시지는 서버에서 이스케이프 후 저장/전송한다.
"""
from flask import Blueprint, render_template, session, g, abort
from markupsafe import escape
from flask_socketio import emit, join_room

from ..extensions import socketio
from ..db import get_db
from ..security import login_required, new_uuid

bp = Blueprint("chat", __name__, url_prefix="/chat")

MAX_MESSAGE_LEN = 1000


def dm_room_name(user_a: str, user_b: str) -> str:
    """두 사용자 ID 로 결정되는 방 이름 (순서 무관)."""
    return "dm_" + "_".join(sorted([user_a, user_b]))


# --- HTTP 라우트 -----------------------------------------------------------
@bp.route("/")
@login_required
def inbox():
    """내 1:1 대화 목록."""
    db = get_db()
    me = g.user["id"]
    rooms = db.execute(
        """
        SELECT u.id, u.username,
               (SELECT body FROM messages m
                 WHERE (m.sender_id = ? AND m.receiver_id = u.id)
                    OR (m.sender_id = u.id AND m.receiver_id = ?)
                 ORDER BY m.created_at DESC LIMIT 1) AS last_body,
               (SELECT created_at FROM messages m
                 WHERE (m.sender_id = ? AND m.receiver_id = u.id)
                    OR (m.sender_id = u.id AND m.receiver_id = ?)
                 ORDER BY m.created_at DESC LIMIT 1) AS last_at
        FROM users u
        WHERE u.id IN (
            SELECT receiver_id FROM messages WHERE sender_id = ?
            UNION
            SELECT sender_id   FROM messages WHERE receiver_id = ?
        )
        ORDER BY last_at DESC
        """,
        (me, me, me, me, me, me),
    ).fetchall()
    return render_template("chat/inbox.html", rooms=rooms)


@bp.route("/dm/<peer_id>")
@login_required
def dm(peer_id):
    """특정 사용자와의 1:1 대화방."""
    if peer_id == g.user["id"]:
        abort(404)  # 자기 자신과의 대화는 없음

    db = get_db()
    peer = db.execute(
        "SELECT id, username, status FROM users WHERE id = ?", (peer_id,)
    ).fetchone()
    if peer is None:
        abort(404)

    me = g.user["id"]
    history = db.execute(
        """SELECT m.*, u.username AS sender_name
           FROM messages m JOIN users u ON m.sender_id = u.id
           WHERE (m.sender_id = ? AND m.receiver_id = ?)
              OR (m.sender_id = ? AND m.receiver_id = ?)
           ORDER BY m.created_at ASC
           LIMIT 200""",
        (me, peer_id, peer_id, me),
    ).fetchall()

    return render_template("chat/dm.html", peer=peer, history=history)


@bp.route("/all")
@login_required
def room():
    """전체 채팅방."""
    return render_template("chat/room.html")


# --- SocketIO: 공통 인증 ---------------------------------------------------
def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db()
    user = db.execute(
        "SELECT id, username, status FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user is None or user["status"] == "blocked":
        return None
    return user


def _clean_message(raw):
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw:
        return None
    return raw[:MAX_MESSAGE_LEN]


# --- SocketIO: 전체 채팅 ---------------------------------------------------
@socketio.on("send_message")
def handle_send_message(data):
    user = _current_user()
    if user is None:
        return

    msg = _clean_message((data or {}).get("message", ""))
    if msg is None:
        return

    emit(
        "receive_message",
        {
            "username": str(escape(user["username"])),
            "message": str(escape(msg)),
        },
        broadcast=True,
    )


# --- SocketIO: 1:1 채팅 ----------------------------------------------------
@socketio.on("join_dm")
def handle_join_dm(data):
    """본인 세션 ID + 상대 ID 로만 방을 만들므로 타인 대화 참여가 불가능하다."""
    user = _current_user()
    if user is None:
        return

    peer_id = (data or {}).get("peer_id")
    if not isinstance(peer_id, str) or peer_id == user["id"]:
        return

    db = get_db()
    peer = db.execute("SELECT id FROM users WHERE id = ?", (peer_id,)).fetchone()
    if peer is None:
        return

    join_room(dm_room_name(user["id"], peer_id))


@socketio.on("dm_message")
def handle_dm_message(data):
    user = _current_user()
    if user is None:
        return

    data = data or {}
    peer_id = data.get("peer_id")
    if not isinstance(peer_id, str) or peer_id == user["id"]:
        return

    msg = _clean_message(data.get("message", ""))
    if msg is None:
        return

    db = get_db()
    peer = db.execute(
        "SELECT id, status FROM users WHERE id = ?", (peer_id,)
    ).fetchone()
    if peer is None or peer["status"] == "blocked":
        return

    # 대화 내용 저장 (파라미터 바인딩)
    db.execute(
        """INSERT INTO messages (id, sender_id, receiver_id, body)
           VALUES (?, ?, ?, ?)""",
        (new_uuid(), user["id"], peer_id, msg),
    )
    db.commit()

    emit(
        "dm_receive",
        {
            "sender_id": user["id"],
            "username": str(escape(user["username"])),
            "message": str(escape(msg)),
        },
        room=dm_room_name(user["id"], peer_id),
    )
