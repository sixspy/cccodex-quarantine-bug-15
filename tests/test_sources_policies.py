
from app.services import captures, policies, sources, audit


def test_source_and_policy_chain(db_path):
    site = sources.create_site("站内目录戊", "https://mock.local/e", 50, "新源", db_path)
    assert site["status"] == "启用"
    sources.set_status(site["id"], "观察", db_path)
    sources.update_quota(site["id"], 70, db_path)
    batch = captures.create_batch("站内目录戊", "策略批", db_path)
    captures.add_item(batch["id"], "sku-e1", "{}", "缺字段", db_path)
    captures.add_item(batch["id"], "sku-e2", "", "编码空", db_path)
    result = policies.apply_to_batch(batch["id"], db_path)
    assert result["entered"] >= 2
    events = audit.list_events(50, db_path)
    assert any(e["action"] == "批内套规则" for e in events)
    assert audit.summary(db_path)["total"] >= 1
