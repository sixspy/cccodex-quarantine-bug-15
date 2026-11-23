from __future__ import annotations

from app.db import _meta_get, _meta_set, ensure_db, get_db


def seed_if_needed(db_path: str | None = None) -> None:
    ensure_db()
    with get_db(db_path) as conn:
        if _meta_get(conn, "seeded") == "1":
            return
        settings = [
            ("max_bin_open", "3", "同时开放隔离舱上限"),
            ("auto_enter_bad", "1", "缺字段自动入舱"),
            ("rework_max_attempt", "3", "回炉最大次数"),
            ("reconcile_label", "隔离对账口径A", "对账口径标签"),
            ("audit_keep_days", "30", "审计保留天数"),
            ("policy_default_bin", "BIN-A", "规则默认入舱号"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO lab_settings(key, value, label) VALUES (?,?,?)",
            settings,
        )
        sites = [
            ("SRC-001", "站内目录甲", "https://mock.local/a", "启用", 120, "主采集源"),
            ("SRC-002", "站内目录乙", "https://mock.local/b", "启用", 80, "次采集源"),
            ("SRC-003", "站内目录丙", "https://mock.local/c", "观察", 40, "观察源"),
            ("SRC-004", "站内目录丁", "https://mock.local/d", "停用", 20, "已停用"),
        ]
        for code, name, url, status, quota, note in sites:
            conn.execute(
                """
                INSERT INTO source_sites(site_code, site_name, base_url, status, daily_quota, note)
                VALUES (?,?,?,?,?,?)
                """,
                (code, name, url, status, quota, note),
            )
        rules = [
            ("POL-001", "缺字段入A舱", "缺字段", "入舱", "BIN-A", "默认缺字段策略"),
            ("POL-002", "编码空入A舱", "编码空", "入舱", "BIN-A", "空编码策略"),
            ("POL-003", "重复键入B舱", "重复键", "入舱", "BIN-B", "重复键策略"),
            ("POL-004", "合格观察", "合格", "观察", "", "合格不自动处理"),
        ]
        for code, title, qm, action, bin_code, note in rules:
            conn.execute(
                """
                INSERT INTO policy_rules(
                  rule_code, title, quality_match, action, target_bin_code, enabled, note
                ) VALUES (?,?,?,?,?,1,?)
                """,
                (code, title, qm, action, bin_code, note),
            )
        bins = [
            ("BIN-A", "缺字段舱", "开放", 80, "缺字段与空编码"),
            ("BIN-B", "重复键舱", "开放", 60, "同批重复键"),
            ("BIN-C", "归档观察舱", "锁定", 40, "已锁只读观察"),
            ("BIN-D", "高优隔离舱", "开放", 50, "紧急坏件"),
        ]
        for code, title, status, cap, note in bins:
            conn.execute(
                "INSERT INTO quarantine_bins(bin_code, title, status, capacity, note) VALUES (?,?,?,?,?)",
                (code, title, status, cap, note),
            )
        batches = [
            ("CAP-20261121-01", "站内目录甲", "已收齐", "首轮样例批"),
            ("CAP-20261121-02", "站内目录乙", "采集中", "进行中批"),
            ("CAP-20261121-03", "站内目录丙", "已关闭", "历史关闭批"),
            ("CAP-20261121-04", "站内目录甲", "采集中", "同日第二批"),
        ]
        batch_ids = []
        for code, src, status, note in batches:
            cur = conn.execute(
                "INSERT INTO capture_batches(batch_code, source_name, status, note) VALUES (?,?,?,?)",
                (code, src, status, note),
            )
            batch_ids.append(cur.lastrowid)
        items = [
            (batch_ids[0], "sku-1001", '{"title":"茶杯"}', "合格", "待检"),
            (batch_ids[0], "sku-1002", '{"title":""}', "缺字段", "待检"),
            (batch_ids[0], "sku-1003", "", "编码空", "待检"),
            (batch_ids[0], "sku-1004", '{"title":"壶嘴"}', "合格", "待检"),
            (batch_ids[1], "sku-2001", '{"title":"托盘"}', "合格", "待检"),
            (batch_ids[1], "sku-2002", '{"title":"托盘"}', "重复键", "待检"),
            (batch_ids[1], "sku-2003", '{"title":"盖子"}', "合格", "待检"),
            (batch_ids[1], "sku-2004", '{"title":""}', "缺字段", "待检"),
            (batch_ids[2], "sku-3001", '{"title":"旧货"}', "合格", "已关闭"),
            (batch_ids[2], "sku-3002", '{"title":""}', "缺字段", "入舱"),
            (batch_ids[3], "sku-4001", '{"title":"新货"}', "合格", "待检"),
            (batch_ids[3], "sku-4002", "", "编码空", "待检"),
        ]
        item_ids = []
        for bid, key, payload, quality, status in items:
            cur = conn.execute(
                "INSERT INTO capture_items(batch_id, item_key, payload, quality, status) VALUES (?,?,?,?,?)",
                (bid, key, payload, quality, status),
            )
            item_ids.append(cur.lastrowid)
        bin_a = conn.execute("SELECT id FROM quarantine_bins WHERE bin_code='BIN-A'").fetchone()["id"]
        conn.execute(
            "INSERT INTO quarantine_rows(bin_id, item_id, reason, status) VALUES (?,?,?,?)",
            (bin_a, item_ids[9], "历史缺字段样例", "待复核"),
        )
        row_id = conn.execute("SELECT id FROM quarantine_rows ORDER BY id DESC LIMIT 1").fetchone()["id"]
        conn.execute(
            "INSERT INTO review_tickets(ticket_code, row_id, decision, reviewer, comment) VALUES (?,?,?,?,?)",
            ("REV-001", row_id, "待决", "", "等待复核"),
        )
        for bid in batch_ids:
            cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM capture_items WHERE batch_id=?", (bid,)
            ).fetchone()["c"]
            bad = conn.execute(
                "SELECT COUNT(*) AS c FROM capture_items WHERE batch_id=? AND quality!='合格'",
                (bid,),
            ).fetchone()["c"]
            conn.execute(
                "UPDATE capture_batches SET item_count=?, bad_count=? WHERE id=?",
                (cnt, bad, bid),
            )
        conn.execute(
            """
            INSERT INTO audit_events(actor, action, entity_type, entity_id, detail)
            VALUES ('system', '种子初始化', 'lab', 0, '首次启动写入样例')
            """
        )
        _meta_set(conn, "seeded", "1")
