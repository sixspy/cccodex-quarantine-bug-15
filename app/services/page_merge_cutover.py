"""分页合并切流账册：应锁当刻指纹并拒回刷；当前只记软笔记。"""
from __future__ import annotations

from app.db import get_db
from app.services.page_merge import (
    active_read_ref,
    cutover_fp,
    dashboard,
    panel_chip,
    record_event,
    reject_refresh,
    truth_flag,
)

_SLUG = "page_merge"
_TITLE = "分页合并"
_OK = "合并已亮"
_BAD = "舱内仍漏"


def append_cutover(ref_id: int, note: str, db_path: str | None = None) -> dict:
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            (f"{_SLUG}_cutover_note_{ref_id}", note or _TITLE),
        )
        # missing: durable fp lock + reject_refresh=1 + active_read=cutover_book
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            (f"{_SLUG}_panel_chip", _OK),
        )
    record_event(f"cutover-note ref={ref_id} {note}", db_path)
    return {
        "ref_id": ref_id,
        "note": note,
        "panel": panel_chip(db_path),
        "truth": truth_flag(db_path),
        "active_read": active_read_ref(db_path),
        "cutover_fp": cutover_fp(db_path),
        "reject_refresh": reject_refresh(db_path),
    }


def cutover_rows(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT key, value FROM meta WHERE key LIKE ? ORDER BY key",
            (f"{_SLUG}_cutover_%",),
        ).fetchall()
        return [
            {
                "key": r["key"],
                "value": r["value"],
                "chip": panel_chip(db_path),
                "active_read": active_read_ref(db_path),
            }
            for r in rows
        ]


def board(db_path: str | None = None) -> dict:
    dash = dashboard(db_path)
    dash["cutover"] = cutover_rows(db_path)
    dash["fate"] = "cutover_book"
    dash["panel_pack_mismatch"] = dash.get("panel_pack_mismatch", True)
    return dash
