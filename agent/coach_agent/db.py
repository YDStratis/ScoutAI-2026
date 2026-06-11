"""MongoDB Atlas connection for the Scout.AI Coach Agent.

Lazy by design: nothing connects at import time. A clear error is raised
only when a tool actually needs the database.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

# Load .env from the repo root (ScoutAI-2026/.env), wherever we're run from.
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")
load_dotenv()  # also honor a local .env / already-exported vars

_client = None


def get_db_name() -> str:
    """DB name: SCOUT_DB_NAME overrides, falls back to existing DB_NAME, default 'scoutai'."""
    return os.getenv("SCOUT_DB_NAME") or os.getenv("DB_NAME") or "scoutai"


def get_client() -> MongoClient:
    global _client
    if _client is None:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError(
                "MONGODB_URI is not set. Add it to ScoutAI-2026/.env "
                "(see README_AGENT.md)."
            )
        if "<db_password>" in uri:
            raise RuntimeError(
                "MONGODB_URI still contains the <db_password> placeholder. "
                "Replace it with your real Atlas password in .env."
            )
        _client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    return _client


def get_db():
    """Return the scoutai database handle (lazy connection)."""
    return get_client()[get_db_name()]


def ping_mongo() -> dict:
    """Ping MongoDB Atlas. Returns {'ok': True, 'db': name} or {'ok': False, 'error': ...}."""
    try:
        get_client().admin.command("ping")
        return {"ok": True, "db": get_db_name()}
    except Exception as e:  # noqa: BLE001 - surface any driver error clearly
        return {"ok": False, "error": str(e)}
