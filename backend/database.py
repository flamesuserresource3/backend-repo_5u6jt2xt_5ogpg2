import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import MongoClient
from bson import ObjectId

DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "app")

_client = MongoClient(DATABASE_URL)
db = _client[DATABASE_NAME]


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    if doc is None:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


def create_document(collection_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.utcnow()
    payload = {**data, "created_at": now, "updated_at": now}
    col = db[collection_name]
    res = col.insert_one(payload)
    saved = col.find_one({"_id": res.inserted_id})
    return _serialize(saved)


def get_documents(collection_name: str, filter_dict: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    col = db[collection_name]
    cursor = col.find(filter_dict or {})
    if limit:
        cursor = cursor.limit(limit)
    return [_serialize(d) for d in cursor]
