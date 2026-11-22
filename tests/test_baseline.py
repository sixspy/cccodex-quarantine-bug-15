from app.services import captures, quarantine, reconcile, review, rework, settings


def test_seed_has_batches(db_path):
    batches = captures.list_batches(db_path)
    assert len(batches) >= 3
    bins = quarantine.list_bins(db_path)
    assert len(bins) >= 3
    assert settings.list_settings(db_path)


def test_dashboard_counts(db_path):
    dash = reconcile.dashboard(db_path)
    assert dash["batches"] >= 3
    assert dash["items"] >= 5
