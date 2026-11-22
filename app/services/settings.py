from __future__ import annotations

from app.db import get_db
from app.services.errors import ServiceError


def list_settings(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT key, value, label FROM lab_settings ORDER BY key"
        ).fetchall()
        return [dict(r) for r in rows]


def update_setting(key: str, value: str, db_path: str | None = None) -> dict:
    if not key or value is None:
        raise ServiceError("参数不完整")
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT key, value, label FROM lab_settings WHERE key=?", (key,)
        ).fetchone()
        if not row:
            raise ServiceError("设置项不存在", 404)
        conn.execute("UPDATE lab_settings SET value=? WHERE key=?", (str(value), key))
        out = conn.execute(
            "SELECT key, value, label FROM lab_settings WHERE key=?", (key,)
        ).fetchone()
        return dict(out)


def get_value(key: str, default: str = "", db_path: str | None = None) -> str:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM lab_settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else default
