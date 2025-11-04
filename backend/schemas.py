from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Idea(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    votes: int = 0
    created_at: datetime
    updated_at: datetime


class Comment(BaseModel):
    idea_id: str
    author: Optional[str] = Field(default=None, max_length=100)
    content: str = Field(min_length=1, max_length=2000)
    created_at: datetime
    updated_at: datetime
