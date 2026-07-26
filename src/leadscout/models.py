from __future__ import annotations

from pydantic import BaseModel


class RedditPost(BaseModel):
    post_id: str
    subreddit: str
    title: str
    permalink: str
    author: str
    created_utc: float
    body_snippet: str


class Classification(BaseModel):
    score: float
    reason: str


class Lead(BaseModel):
    post_id: str
    subreddit: str
    title: str
    permalink: str
    author: str
    created_utc: float
    body_snippet: str
    keyword_matched: str
    llm_score: float
    llm_reason: str
    status: str = "new"
    first_seen: str
