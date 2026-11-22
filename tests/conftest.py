from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.db import ensure_db
from app.seed import seed_if_needed


@pytest.fixture()
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    from app import config

    config.Config.DATABASE_PATH = path
    config.Config.INSTANCE_DIR = tmp_path
    ensure_db()
    seed_if_needed(str(path))
    return str(path)
