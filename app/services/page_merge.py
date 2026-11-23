"""分页合并：切流账册形态（甲侧，已择定，禁止双轨并开）。

账册一旦落笔即锁住合并当刻的分页键与合并指纹：
- 同一分页重复合并一律拒回刷；
- 回炉侧只读本账册的合并引用，不另开读轨；
- 复核放行前重算指纹，偏了即拦；
- 合并徽标由键号与指纹派生，拧花即拦回炉。
"""
from __future__ import annotations

import hashlib
import sqlite3

from app.db import get_db
from app.services.errors import ServiceError

MODE = "切流账册"
READ_TRACK = "只读账册"
_KEY_PREFIX = "MG-"


def _fingerprint(batch_id: int, page_key: str, items: list[dict]) -> str:
    """页内容指纹：只锁分页键集与报文（错位即变）。

    质量标记与流转状态是台上工作态，回炉洗白不算指纹偏移。
    """
    h = hashlib.sha1()
    h.update(f"{batch_id}|{page_key}|".encode("utf-8"))
    for it in sorted(items, key=lambda x: str(x["item_key"])):
        h.update(f"{it['item_key']}#{it['payload']};".encode("utf-8"))
    return h.hexdigest()


def _badge(merge_key: str, fingerprint: str) -> str:
    return f"{merge_key}·{fingerprint[:8]}"


def _current_fingerprint(conn, batch_id: int, page_key: str) -> str:
    items = conn.execute(
        "SELECT item_key, payload FROM capture_items WHERE batch_id=?",
        (batch_id,),
    ).fetchall()
    return _fingerprint(batch_id, page_key, [dict(i) for i in items])


def _merge_for_batch(conn, batch_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT * FROM page_merges WHERE batch_id=? ORDER BY id DESC LIMIT 1
        """,
        (batch_id,),
    ).fetchone()
    return dict(row) if row else None


def merge_for_batch(batch_id: int, db_path: str | None = None) -> dict | None:
    with get_db(db_path) as conn:
        return _merge_for_batch(conn, batch_id)


def commit_merge(
    batch_id: int,
    page_key: str = "",
    actor: str = "admin",
    db_path: str | None = None,
) -> dict:
    """整笔落账：合并头 + 落点行同一事务写完，失败整笔回滚并吐白话。"""
    page_key = (page_key or "").strip() or "P1"
    actor = (actor or "admin").strip() or "admin"
    try:
        with get_db(db_path) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError:
                raise ServiceError("另一仓管正在合并同一分页，请稍后重试", 409)
            batch = conn.execute(
                "SELECT * FROM capture_batches WHERE id=?", (batch_id,)
            ).fetchone()
            if not batch:
                raise ServiceError("批次不存在", 404)
            items = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT id, item_key, quality, payload
                    FROM capture_items WHERE batch_id=? ORDER BY id
                    """,
                    (batch_id,),
                ).fetchall()
            ]
            if not items:
                raise ServiceError("批次暂无条目，无法合并落账")
            existing = conn.execute(
                "SELECT merge_key FROM page_merges WHERE batch_id=? AND page_key=?",
                (batch_id, page_key),
            ).fetchone()
            if existing:
                raise ServiceError(
                    f"分页{page_key}已合并落账（{existing['merge_key']}），拒绝回刷",
                    409,
                )
            fp = _fingerprint(batch_id, page_key, items)
            seq = conn.execute(
                "SELECT COUNT(*) AS c FROM page_merges"
            ).fetchone()["c"] + 1
            merge_key = f"{_KEY_PREFIX}{seq:04d}"
            badge = _badge(merge_key, fp)
            cur = conn.execute(
                """
                INSERT INTO page_merges(
                  merge_key, batch_id, page_key, fingerprint, badge, actor
                ) VALUES (?,?,?,?,?,?)
                """,
                (merge_key, batch_id, page_key, fp, badge, actor),
            )
            merge_id = cur.lastrowid
            landing = 0
            for it in items:
                if it["quality"] == "合格":
                    continue
                qrow = conn.execute(
                    "SELECT id, bin_id FROM quarantine_rows WHERE item_id=?",
                    (it["id"],),
                ).fetchone()
                conn.execute(
                    """
                    INSERT INTO page_merge_rows(merge_id, item_id, row_id, bin_id)
                    VALUES (?,?,?,?)
                    """,
                    (
                        merge_id,
                        it["id"],
                        qrow["id"] if qrow else None,
                        qrow["bin_id"] if qrow else None,
                    ),
                )
                landing += 1
            conn.execute(
                "UPDATE page_merges SET landing_count=? WHERE id=?",
                (landing, merge_id),
            )
    except ServiceError:
        raise
    except sqlite3.IntegrityError:
        raise ServiceError("另一仓管正在合并同一分页，请稍后重试", 409)
    except sqlite3.OperationalError:
        raise ServiceError("合并落账被占用，请稍后重试", 409)
    except sqlite3.Error:
        raise ServiceError("合并落账失败，已整笔回滚", 500)
    from app.services import audit as audit_svc

    audit_svc.write_event(
        "分页合并落账",
        "page_merge",
        merge_id,
        f"{merge_key} 页{page_key} 落点{landing}",
        actor=actor,
        db_path=db_path,
    )
    return {
        "ok": True,
        "merge_key": merge_key,
        "badge": badge,
        "batch_id": batch_id,
        "page_key": page_key,
        "fingerprint": fp,
        "landing_count": landing,
        "message": f"合并已落账：{merge_key}（落点{landing}行）",
    }


def assert_release_allowed(conn, item) -> None:
    """复核放行闸：账册在案则重算指纹，偏了即拦。"""
    merge = _merge_for_batch(conn, item["batch_id"])
    if not merge:
        return
    fp_now = _current_fingerprint(conn, item["batch_id"], merge["page_key"])
    if fp_now != merge["fingerprint"]:
        raise ServiceError(
            f"合并指纹已偏移（账册{merge['merge_key']}），禁止放行", 409
        )


def assert_rework_allowed(conn, item) -> None:
    """回炉闸：徽标与键号拧花、指纹偏移，都拦。"""
    merge = _merge_for_batch(conn, item["batch_id"])
    if not merge:
        return
    if merge["badge"] != _badge(merge["merge_key"], merge["fingerprint"]):
        raise ServiceError("合并徽标与合并键号拧花，已拦回炉", 409)
    fp_now = _current_fingerprint(conn, item["batch_id"], merge["page_key"])
    if fp_now != merge["fingerprint"]:
        raise ServiceError(
            f"合并指纹已偏移（账册{merge['merge_key']}），已拦回炉", 409
        )


def list_merges(db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT m.*, b.batch_code
            FROM page_merges m
            JOIN capture_batches b ON b.id=m.batch_id
            ORDER BY m.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def merge_rows(merge_id: int, db_path: str | None = None) -> list[dict]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """
            SELECT pmr.*, i.item_key, i.quality, b.bin_code
            FROM page_merge_rows pmr
            JOIN capture_items i ON i.id=pmr.item_id
            LEFT JOIN quarantine_bins b ON b.id=pmr.bin_id
            WHERE pmr.merge_id=?
            ORDER BY pmr.id
            """,
            (merge_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def spec(db_path: str | None = None) -> dict:
    """合并口径：设置页只读展示。"""
    with get_db(db_path) as conn:
        merges = conn.execute("SELECT COUNT(*) AS c FROM page_merges").fetchone()["c"]
        landings = conn.execute(
            "SELECT COUNT(*) AS c FROM page_merge_rows"
        ).fetchone()["c"]
        latest = conn.execute(
            "SELECT merge_key, fingerprint FROM page_merges ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return {
        "mode": MODE,
        "read_track": READ_TRACK,
        "reject_refresh": True,
        "merge_count": merges,
        "landing_count": landings,
        "latest_merge_key": latest["merge_key"] if latest else "",
        "latest_fingerprint": latest["fingerprint"][:8] if latest else "",
    }


def dashboard(db_path: str | None = None) -> dict:
    return {
        "title": "分页合并",
        "spec": spec(db_path),
        "merges": list_merges(db_path),
    }
