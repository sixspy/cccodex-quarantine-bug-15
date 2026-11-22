"""分页合并双写两轨：应将旧档送入只读归档并改读新旗；当前只亮镜像芯片。"""
from __future__ import annotations

from app.db import get_db
from app.services.page_merge import (
    active_read_ref,
    archive_rows,
    dashboard,
    live_flag,
    paint_ok,
    truth_flag,
)

_SLUG = "page_merge"
_OK = "合并已亮"
_BAD = "舱内仍漏"
_TITLE = "分页合并"


def _meta_set(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        (key, value),
    )


def dual_chip(db_path: str | None = None) -> str:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM meta WHERE key=?",
            (f"{_SLUG}_dual_chip",),
        ).fetchone()
        return row["value"] if row else _OK


def seed_dual(db_path: str | None = None) -> None:
    with get_db(db_path) as conn:
        _meta_set(conn, f"{_SLUG}_dual_chip", _OK)
        _meta_set(conn, f"{_SLUG}_dual_truth", _BAD)
        # missing archive move + live_flag + active_read=live_flag


def apply_dualwrite(note: str = "", db_path: str | None = None) -> dict:
    seed_dual(db_path)
    paint_ok(db_path)
    with get_db(db_path) as conn:
        _meta_set(conn, f"{_SLUG}_dual_note", note or _TITLE)
        # intentionally skip archive_% and live_flag rewrite
    return {
        "dual_chip": dual_chip(db_path),
        "truth": truth_flag(db_path),
        "active_read": active_read_ref(db_path),
        "archive_count": len(archive_rows(db_path)),
        "live_flag": live_flag(db_path),
    }


def dual_board(db_path: str | None = None) -> dict:
    seed_dual(db_path)
    dash = dashboard(db_path)
    return {
        "dual_chip": dual_chip(db_path),
        "truth": truth_flag(db_path),
        "active_read": active_read_ref(db_path),
        "archive": archive_rows(db_path),
        "live_flag": live_flag(db_path),
        "dash": dash,
        "fate": "dualwrite",
        "panel_pack_mismatch": True,
        "title": f"{_TITLE}双写面",
    }


def half_dual(db_path: str | None = None) -> dict:
    paint_ok(db_path)
    seed_dual(db_path)
    return {
        "dual_chip": dual_chip(db_path),
        "truth": truth_flag(db_path),
        "active_read": active_read_ref(db_path),
    }
