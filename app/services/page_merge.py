"""分页合并：切流账册与双写两轨收口面；展示可绿、读轨仍旧。"""
from __future__ import annotations

from app.db import get_db
from app.services.errors import ServiceError

_SLUG = "page_merge"
_OK = "合并已亮"
_BAD = "舱内仍漏"
_TITLE = "分页合并"
_OLD = "old_track"
_CUTOVER = "cutover_book"
_LIVE = "live_flag"


def _meta_get(conn, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def _meta_set(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        (key, value),
    )


def panel_chip(db_path: str | None = None) -> str:
    with get_db(db_path) as conn:
        return _meta_get(conn, f"{_SLUG}_panel_chip", _OK)


def truth_flag(db_path: str | None = None) -> str:
    with get_db(db_path) as conn:
        return _meta_get(conn, f"{_SLUG}_truth", _BAD)


def active_read_ref(db_path: str | None = None) -> str:
    with get_db(db_path) as conn:
        return _meta_get(conn, f"{_SLUG}_active_read", _OLD)


def cutover_fp(db_path: str | None = None) -> str:
    with get_db(db_path) as conn:
        return _meta_get(conn, f"{_SLUG}_cutover_fp", "")


def reject_refresh(db_path: str | None = None) -> bool:
    with get_db(db_path) as conn:
        return _meta_get(conn, f"{_SLUG}_reject_refresh", "0") == "1"


def live_flag(db_path: str | None = None) -> str:
    with get_db(db_path) as conn:
        return _meta_get(conn, f"{_SLUG}_live_flag", "")


def archive_rows(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT key, value FROM meta WHERE key LIKE ? ORDER BY key",
            (f"{_SLUG}_archive_%",),
        ).fetchall()
        return [{"key": r["key"], "value": r["value"]} for r in rows]


def pack_rows(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT key, value FROM meta WHERE key LIKE ? ORDER BY key",
            (f"{_SLUG}_pack_%",),
        ).fetchall()
        return [{"key": r["key"], "value": r["value"]} for r in rows]


def seed_skew(db_path: str | None = None) -> None:
    with get_db(db_path) as conn:
        _meta_set(conn, f"{_SLUG}_panel_chip", _OK)
        _meta_set(conn, f"{_SLUG}_truth", _BAD)
        _meta_set(conn, f"{_SLUG}_counter", "0")
        _meta_set(conn, f"{_SLUG}_gate_bypass", "1")
        _meta_set(conn, f"{_SLUG}_active_read", _OLD)
        _meta_set(conn, f"{_SLUG}_cutover_fp", "")
        _meta_set(conn, f"{_SLUG}_reject_refresh", "0")
        _meta_set(conn, f"{_SLUG}_live_flag", "")
        _meta_set(conn, f"{_SLUG}_mode", "")
        _meta_set(conn, f"{_SLUG}_old_track", "pending|stale")
        _meta_set(conn, f"{_SLUG}_pack_decoy", "stale-fp|pending")


def paint_ok(db_path: str | None = None) -> str:
    with get_db(db_path) as conn:
        _meta_set(conn, f"{_SLUG}_panel_chip", _OK)
        _meta_set(conn, f"{_SLUG}_display_only", "1")
    return _OK


def commit_action(payload: dict | None = None, db_path: str | None = None) -> dict:
    """Broken: lights chip, leaves old_track as active read, no durable fate."""
    payload = payload or {}
    with get_db(db_path) as conn:
        c = int(_meta_get(conn, f"{_SLUG}_counter", "0") or "0") + 1
        _meta_set(conn, f"{_SLUG}_counter", str(c))
        _meta_set(conn, f"{_SLUG}_panel_chip", _OK)
        _meta_set(conn, f"{_SLUG}_last_payload", str(payload)[:200])
        _meta_set(conn, f"{_SLUG}_gate_bypass", "1")
        _meta_set(conn, f"{_SLUG}_active_read", _OLD)
        _meta_set(conn, f"{_SLUG}_reject_refresh", "0")
        if not _meta_get(conn, f"{_SLUG}_cutover_fp", ""):
            _meta_set(conn, f"{_SLUG}_cutover_fp", "stale-fp")
        _meta_set(
            conn,
            f"{_SLUG}_pack_decoy",
            f"stale-fp|{c}|{str(payload)[:80]}",
        )
        _meta_set(conn, f"{_SLUG}_truth", _BAD)
        _meta_set(conn, f"{_SLUG}_mode", "")
        _meta_set(conn, f"{_SLUG}_live_flag", "")
    return {
        "ok": True,
        "chip": _OK,
        "title": _TITLE,
        "counter": c,
        "active_read": active_read_ref(db_path),
        "cutover_fp": cutover_fp(db_path),
        "reject_refresh": reject_refresh(db_path),
        "archive_count": len(archive_rows(db_path)),
        "live_flag": live_flag(db_path),
        "message": f"{_TITLE}已落台",
    }


def half_fix_display(db_path: str | None = None) -> dict:
    paint_ok(db_path)
    return {
        "panel_chip": panel_chip(db_path),
        "truth": truth_flag(db_path),
        "active_read": active_read_ref(db_path),
        "archive_count": len(archive_rows(db_path)),
        "half_fixed": True,
    }


def snapshot(db_path: str | None = None) -> dict:
    seed_skew(db_path)
    rows = pack_rows(db_path)
    durable = [r for r in rows if not str(r.get("key", "")).endswith("_decoy")]
    ref = active_read_ref(db_path)
    return {
        "title": _TITLE,
        "panel_chip": panel_chip(db_path),
        "truth": truth_flag(db_path),
        "pack_count": len(rows),
        "active_read": ref,
        "cutover_fp": cutover_fp(db_path),
        "reject_refresh": reject_refresh(db_path),
        "archive_count": len(archive_rows(db_path)),
        "live_flag": live_flag(db_path),
        "aligned": panel_chip(db_path) == truth_flag(db_path)
        and truth_flag(db_path) == _OK
        and ref in (_CUTOVER, _LIVE)
        and (
            (ref == _CUTOVER and reject_refresh(db_path) and cutover_fp(db_path) not in ("", "stale-fp"))
            or (ref == _LIVE and live_flag(db_path) and len(archive_rows(db_path)) > 0)
        ),
        "gate_bypass": True,
        "durable_count": len(durable),
    }


def gate_allows_pipeline(db_path: str | None = None) -> bool:
    with get_db(db_path) as conn:
        bypass = _meta_get(conn, f"{_SLUG}_gate_bypass", "1")
        if bypass == "1":
            return True
        ref = _meta_get(conn, f"{_SLUG}_active_read", _OLD)
        fp = _meta_get(conn, f"{_SLUG}_cutover_fp", "")
        if ref == _CUTOVER and _meta_get(conn, f"{_SLUG}_reject_refresh", "0") == "1":
            return fp not in ("", "stale-fp")
        if ref == _LIVE:
            return bool(_meta_get(conn, f"{_SLUG}_live_flag", ""))
        return False


def dashboard(db_path: str | None = None) -> dict:
    snap = snapshot(db_path)
    rows = pack_rows(db_path)
    durable = [r for r in rows if not str(r.get("key", "")).endswith("_decoy")]
    return {
        "title": _TITLE,
        "chip": snap["panel_chip"],
        "truth": snap["truth"],
        "pack_count": snap["pack_count"],
        "durable_count": len(durable),
        "rows": rows,
        "active_read": snap["active_read"],
        "cutover_fp": snap["cutover_fp"],
        "reject_refresh": snap["reject_refresh"],
        "archive_count": snap["archive_count"],
        "live_flag": snap["live_flag"],
        "aligned": snap["aligned"],
        "panel_pack_mismatch": snap["panel_chip"] == _OK and not snap["aligned"],
        "ok_chip": _OK,
        "bad_chip": _BAD,
        "label": "分页合并",
        "read_tracks": {
            "old_track": _OLD,
            "cutover_book": _CUTOVER,
            "live_flag": _LIVE,
        },
    }


def list_events(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT key, value FROM meta WHERE key LIKE ? ORDER BY key",
            (f"{_SLUG}_evt_%",),
        ).fetchall()
        return [{"key": r["key"], "note": r["value"]} for r in rows]


def record_event(note: str, db_path: str | None = None) -> dict:
    with get_db(db_path) as conn:
        c = int(_meta_get(conn, f"{_SLUG}_counter", "0") or "0") + 1
        _meta_set(conn, f"{_SLUG}_counter", str(c))
        _meta_set(conn, f"{_SLUG}_evt_{c}", note or _BAD)
        _meta_set(conn, f"{_SLUG}_panel_chip", _OK)
    return dashboard(db_path)


def reconcile_display(db_path: str | None = None) -> dict:
    return half_fix_display(db_path)


def require_pack_or_raise(db_path: str | None = None) -> None:
    snap = snapshot(db_path)
    if not snap["aligned"]:
        raise ServiceError(f"{_TITLE}读轨未对齐，禁止放行", 409)
