import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Idea as IdeaSchema, Comment as CommentSchema

app = FastAPI(title="VibeCoders Ideas API")

# Configure CORS. Note: allow_credentials=False when using wildcard origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utilities

def serialize_doc(doc):
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    # Convert datetimes to isoformat strings
    for k, v in list(doc.items()):
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc

# Request models
class CreateIdeaRequest(BaseModel):
    title: str
    description: Optional[str] = None

class CreateCommentRequest(BaseModel):
    author: Optional[str] = None
    content: str

# Health
@app.get("/")
def read_root():
    return {"message": "VibeCoders Ideas API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, "name") else "❌ Unknown"
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()[:10]
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# Ideas Endpoints
@app.post("/ideas")
def create_idea(payload: CreateIdeaRequest):
    idea = IdeaSchema(title=payload.title, description=payload.description, votes=0)
    new_id = create_document("idea", idea)
    # Return full document
    doc = db["idea"].find_one({"_id": ObjectId(new_id)})
    return serialize_doc(doc)

@app.get("/ideas")
def list_ideas(range: str = "all", sort: str = "votes"):
    # Time filter
    filter_query = {}
    now = datetime.now(timezone.utc)
    if range == "week":
        filter_query["created_at"] = {"$gte": now - timedelta(days=7)}
    elif range == "month":
        filter_query["created_at"] = {"$gte": now - timedelta(days=30)}

    ideas = list(db["idea"].find(filter_query))

    # Attach comments_count for each idea
    idea_ids = [i["_id"] for i in ideas]
    if idea_ids:
        pipeline = [
            {"$match": {"idea_id": {"$in": [str(_id) for _id in idea_ids]}}},
            {"$group": {"_id": "$idea_id", "count": {"$sum": 1}}}
        ]
        counts = {doc["_id"]: doc["count"] for doc in db["comment"].aggregate(pipeline)}
    else:
        counts = {}

    enriched = []
    for i in ideas:
        s = serialize_doc(i)
        s["comments_count"] = counts.get(s["id"], 0)
        enriched.append(s)

    if sort == "comments":
        enriched.sort(key=lambda x: x.get("comments_count", 0), reverse=True)
    else:  # default votes
        enriched.sort(key=lambda x: x.get("votes", 0), reverse=True)

    return enriched

@app.post("/ideas/{idea_id}/upvote")
def upvote_idea(idea_id: str):
    try:
        oid = ObjectId(idea_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid idea id")

    result = db["idea"].find_one_and_update(
        {"_id": oid},
        {"$inc": {"votes": 1}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Idea not found")
    return serialize_doc(result)

# Comments Endpoints
@app.get("/ideas/{idea_id}/comments")
def get_comments(idea_id: str):
    try:
        _ = ObjectId(idea_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid idea id")

    comments = list(db["comment"].find({"idea_id": idea_id}).sort("created_at", -1))
    return [serialize_doc(c) for c in comments]

@app.post("/ideas/{idea_id}/comments")
def add_comment(idea_id: str, payload: CreateCommentRequest):
    try:
        _ = ObjectId(idea_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid idea id")

    # Ensure idea exists
    idea = db["idea"].find_one({"_id": ObjectId(idea_id)})
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    comment = CommentSchema(idea_id=idea_id, author=payload.author, content=payload.content)
    new_id = create_document("comment", comment)
    doc = db["comment"].find_one({"_id": ObjectId(new_id)})
    return serialize_doc(doc)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
