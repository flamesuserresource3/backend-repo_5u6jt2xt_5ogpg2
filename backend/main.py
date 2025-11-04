from datetime import datetime, timedelta
import os
from typing import List, Optional, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "app")
client = MongoClient(DATABASE_URL)
db = client[DATABASE_NAME]

# Ensure indexes
_db_ideas = db["idea"]
_db_comments = db["comment"]
_db_ideas.create_index([("created_at", DESCENDING)])
_db_ideas.create_index([("votes", DESCENDING)])
_db_comments.create_index([("idea_id", ASCENDING), ("created_at", DESCENDING)])


# Helpers
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        try:
            return ObjectId(str(v))
        except Exception as e:
            raise ValueError("Invalid ObjectId") from e


def serialize_id(doc):
    if not doc:
        return doc
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


# Schemas
class IdeaCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class IdeaOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    votes: int
    created_at: datetime
    updated_at: datetime
    comments_count: int = 0


class CommentCreate(BaseModel):
    author: Optional[str] = Field(default=None, max_length=100)
    content: str = Field(min_length=1, max_length=2000)


class CommentOut(BaseModel):
    id: str
    idea_id: str
    author: Optional[str] = None
    content: str
    created_at: datetime
    updated_at: datetime


# FastAPI app
app = FastAPI(title="VibeCoders Ideas API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/test")
def test():
    # Ping database
    db.command("ping")
    return {"status": "ok"}


@app.post("/ideas", response_model=IdeaOut)
def create_idea(payload: IdeaCreate):
    now = datetime.utcnow()
    doc = {
        "title": payload.title.strip(),
        "description": (payload.description.strip() if payload.description else None),
        "votes": 0,
        "created_at": now,
        "updated_at": now,
    }
    result = _db_ideas.insert_one(doc)
    saved = _db_ideas.find_one({"_id": result.inserted_id})
    serialized = serialize_id(saved)
    serialized["comments_count"] = 0
    return IdeaOut(**serialized)


@app.get("/ideas", response_model=List[IdeaOut])
def list_ideas(range: Literal["all", "month", "week"] = "all", sort: Literal["votes", "comments"] = "votes"):
    # Time filter
    filter_q = {}
    if range != "all":
        now = datetime.utcnow()
        if range == "month":
            start = now - timedelta(days=30)
        else:  # week
            start = now - timedelta(days=7)
        filter_q["created_at"] = {"$gte": start}

    ideas = list(_db_ideas.find(filter_q))

    # Compute comment counts for all ideas in one pass
    idea_ids = [i["_id"] for i in ideas]
    counts = {iid: 0 for iid in idea_ids}
    if idea_ids:
        pipeline = [
            {"$match": {"idea_id": {"$in": [str(iid) for iid in idea_ids]}}},
            {"$group": {"_id": "$idea_id", "count": {"$sum": 1}}},
        ]
        for row in _db_comments.aggregate(pipeline):
            try:
                oid = ObjectId(row["_id"])  # convert back to ObjectId to map
            except Exception:
                continue
            counts[oid] = row["count"]

    items = []
    for i in ideas:
        s = serialize_id(i)
        s["comments_count"] = counts.get(i["_id"], 0)
        items.append(s)

    # Sort
    reverse = True
    if sort == "votes":
        items.sort(key=lambda x: (x.get("votes", 0), x["created_at"]), reverse=True)
    else:
        items.sort(key=lambda x: (x.get("comments_count", 0), x["created_at"]), reverse=True)

    return [IdeaOut(**it) for it in items]


@app.post("/ideas/{idea_id}/upvote", response_model=IdeaOut)
def upvote_idea(idea_id: str):
    res = _db_ideas.find_one_and_update(
        {"_id": PyObjectId.validate(idea_id)},
        {"$inc": {"votes": 1}, "$set": {"updated_at": datetime.utcnow()}},
        return_document=True,
    )
    if not res:
        raise HTTPException(status_code=404, detail="Idea not found")
    # comment count
    count = _db_comments.count_documents({"idea_id": idea_id})
    s = serialize_id(res)
    s["comments_count"] = count
    return IdeaOut(**s)


@app.get("/ideas/{idea_id}/comments", response_model=List[CommentOut])
def list_comments(idea_id: str):
    docs = list(_db_comments.find({"idea_id": idea_id}).sort("created_at", DESCENDING))
    return [CommentOut(**serialize_id(d)) for d in docs]


@app.post("/ideas/{idea_id}/comments", response_model=CommentOut)
def add_comment(idea_id: str, payload: CommentCreate):
    # ensure idea exists
    idea = _db_ideas.find_one({"_id": PyObjectId.validate(idea_id)})
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    now = datetime.utcnow()
    doc = {
        "idea_id": idea_id,
        "author": (payload.author.strip() if payload.author else None),
        "content": payload.content.strip(),
        "created_at": now,
        "updated_at": now,
    }
    result = _db_comments.insert_one(doc)
    saved = _db_comments.find_one({"_id": result.inserted_id})
    return CommentOut(**serialize_id(saved))
