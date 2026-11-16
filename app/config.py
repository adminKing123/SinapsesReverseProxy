import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


def _default_database_uri() -> str:
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    db_path = (INSTANCE_DIR / "db.sqlite3").as_posix()
    return f"sqlite:///{db_path}"


def load_syn_core_config() -> dict:
    raw = os.environ.get("SYN_CORE_CONFIG", "{}")
    try:
        config = json.loads(raw)
    except json.JSONDecodeError:
        config = {}
    return {
        "HR_CODE": config.get("HR_CODE", ""),
        "API_BASE": (config.get("API_BASE", "") or "").rstrip("/"),
        "DEFAULT_USER_ID": config.get("DEFAULT_USER_ID", ""),
        "DEFAULT_SIGNED_ARRAY": config.get("DEFAULT_SIGNED_ARRAY", ""),
        "DATE_FMT": config.get("DATE_FMT", "%m/%d/%Y"),
    }


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _default_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SYNCORE_SERVICE_KEY = os.environ.get("SYNCORE_SERVICE_KEY", "")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    SYN_CORE_CONFIG = load_syn_core_config()