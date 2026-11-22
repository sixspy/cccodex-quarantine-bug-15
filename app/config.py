from __future__ import annotations

import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    INSTANCE_DIR = Path(os.environ.get("INSTANCE_DIR", BASE_DIR / "instance"))
    DATABASE_PATH = Path(
        os.environ.get("DATABASE_PATH", INSTANCE_DIR / "quarantine_lab.db")
    )
    SECRET = os.environ.get("APP_SECRET", "cc-quarantine-lab-dev-secret")
    COOKIE_NAME = "qtn_session"
    ADMIN_USER = "admin"
    ADMIN_PASS = "123456"
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", "7500"))
