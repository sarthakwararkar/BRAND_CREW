"""MongoDB connection (sync pymongo - crews run in background threads)."""
from __future__ import annotations

from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from backend.config import settings


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    return MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)


def get_db() -> Database:
    return get_client()[settings.mongodb_db]


def ensure_indexes() -> None:
    db = get_db()
    db.runs.create_index("created_at")
    db.outputs.create_index("run_id")
    db.ratings.create_index("output_id")
    db.metrics.create_index("output_id")
    db.lesson_refs.create_index("run_id")
