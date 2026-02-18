from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class IntentResponse(BaseModel):
    intent: str = Field(..., description="One of: policy, review, price, recommend, search")
    category: Optional[str] = None
    product_id: Optional[str] = None


class ReviewSummaryAI(BaseModel):
    summary_text: str
    themes: List[str] = []


class RecommendationAI(BaseModel):
    recommended_ids: List[str]
    reasons: List[str]


class ChatResponseAI(BaseModel):
    reply: str
