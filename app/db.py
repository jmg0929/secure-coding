"""SQLite 연결 관리 및 초기화.

- 요청(request) 단위로 연결을 재사용하고 요청 종료 시 닫는다.
- 모든 쿼리는 호출부에서 파라미터 바인딩(?)을 사용해 SQL 인젝션을 방지한다.
"""
import os
import sqlite3

from flask import current_app, g


def get_db() -> sqlite3.Connection:
    """현재 요청에 바인딩된 DB 연결을 반환(없으면 생성)."""
    if "db" not in g:
        db_path = current_app.config["DATABASE"]
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row          # 컬럼명으로 접근
        g.db.execute("PRAGMA foreign_keys = ON")  # 외래키 제약 활성화
    return g.db


def close_db(exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    """스키마를 적용해 테이블을 생성한다."""
    db = get_db()
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
