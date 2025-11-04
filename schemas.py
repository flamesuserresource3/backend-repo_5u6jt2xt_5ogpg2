"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional

# Product Hunt-style app for ideas and comments

class Idea(BaseModel):
    """
    Ideas to build for VibeCoders
    Collection name: "idea"
    """
    title: str = Field(..., description="Short idea title")
    description: Optional[str] = Field(None, description="Optional details about the idea")
    votes: int = Field(0, ge=0, description="Total upvotes")

class Comment(BaseModel):
    """
    Comments on ideas
    Collection name: "comment"
    """
    idea_id: str = Field(..., description="ID of the idea this comment belongs to")
    author: Optional[str] = Field(None, description="Name or handle of commenter")
    content: str = Field(..., description="Comment text")
