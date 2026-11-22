"""分页合并读轨审计：汇总切流账册与双写两轨两侧引用。"""
from __future__ import annotations

from app.db import get_db
from app.services.page_merge_cutover import board as cutover_board
from app.services.page_merge_dualwrite import dual_board, half_dual


def audit_list(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT key, value FROM meta WHERE key LIKE ? ORDER BY key",
            ("page_merge_evt_%",),
        ).fetchall()
        return [{"key": r["key"], "value": r["value"]} for r in rows]


def audit_summary(db_path: str | None = None) -> dict:
    return {
        "title": "分页合并审计",
        "events": audit_list(db_path),
        "cutover": cutover_board(db_path),
        "dualwrite": dual_board(db_path),
        "half": half_dual(db_path),
    }
