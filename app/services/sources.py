
from __future__ import annotations

from app.db import get_db
from app.services import audit as audit_svc
from app.services.errors import ServiceError


def list_sites(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT s.*,
              (SELECT COUNT(*) FROM capture_batches b WHERE b.source_name=s.site_name) AS batch_count
            FROM source_sites s
            ORDER BY s.id
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_site(site_id: int, db_path: str | None = None) -> dict:
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM source_sites WHERE id=?", (site_id,)).fetchone()
        if not row:
            raise ServiceError("源站不存在", 404)
        batches = conn.execute(
            """
            SELECT id, batch_code, status, item_count, bad_count, created_at
            FROM capture_batches
            WHERE source_name=?
            ORDER BY id DESC
            """,
            (row["site_name"],),
        ).fetchall()
        data = dict(row)
        data["batches"] = [dict(b) for b in batches]
        return data


def create_site(
    site_name: str,
    base_url: str = "",
    daily_quota: int = 100,
    note: str = "",
    db_path: str | None = None,
) -> dict:
    site_name = (site_name or "").strip()
    if not site_name:
        raise ServiceError("源站名不能空")
    daily_quota = max(1, int(daily_quota or 100))
    with get_db(db_path) as conn:
        exists = conn.execute(
            "SELECT id FROM source_sites WHERE site_name=?", (site_name,)
        ).fetchone()
        if exists:
            raise ServiceError("源站名已存在")
        n = conn.execute("SELECT COUNT(*) AS c FROM source_sites").fetchone()["c"] + 1
        code = f"SRC-{n:03d}"
        cur = conn.execute(
            """
            INSERT INTO source_sites(site_code, site_name, base_url, status, daily_quota, note)
            VALUES (?, ?, ?, '启用', ?, ?)
            """,
            (code, site_name, base_url or "", daily_quota, note or ""),
        )
        site_id = cur.lastrowid
    audit_svc.write_event("创建源站", "source_site", site_id, site_name, db_path=db_path)
    return get_site(site_id, db_path)


def set_status(site_id: int, status: str, db_path: str | None = None) -> dict:
    if status not in ("启用", "停用", "观察"):
        raise ServiceError("源站状态无效")
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM source_sites WHERE id=?", (site_id,)).fetchone()
        if not row:
            raise ServiceError("源站不存在", 404)
        conn.execute(
            "UPDATE source_sites SET status=? WHERE id=?", (status, site_id)
        )
    audit_svc.write_event(
        "改源站状态", "source_site", site_id, status, db_path=db_path
    )
    return get_site(site_id, db_path)


def update_quota(site_id: int, daily_quota: int, db_path: str | None = None) -> dict:
    daily_quota = max(1, int(daily_quota or 1))
    with get_db(db_path) as conn:
        row = conn.execute("SELECT id FROM source_sites WHERE id=?", (site_id,)).fetchone()
        if not row:
            raise ServiceError("源站不存在", 404)
        conn.execute(
            "UPDATE source_sites SET daily_quota=? WHERE id=?",
            (daily_quota, site_id),
        )
    audit_svc.write_event(
        "改日配额", "source_site", site_id, str(daily_quota), db_path=db_path
    )
    return get_site(site_id, db_path)
