from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProductOut(BaseSchema):
    id: str
    name: str
    brand: str
    category: str
    price: float
    description: str
    stock: int
    rating: float


class ReviewOut(BaseSchema):
    id: int
    product_id: str
    rating: float
    text: str
    date: Optional[date]


class SentimentBreakdown(BaseSchema):
    positive: int = 0
    neutral: int = 0
    negative: int = 0


class Theme(BaseSchema):
    word: str
    count: int


class ReviewSummary(BaseSchema):
    average_rating: float
    total_reviews: int
    sentiment: SentimentBreakdown
    themes: List[Theme]
    summary_text: str = ""


class PriceComparison(BaseSchema):
    base: ProductOut
    min: float
    max: float
    avg: float
    cheaper: List[ProductOut]
    updated_at: str


class PolicyOut(BaseSchema):
    policy_type: str
    description: str
    conditions: List[str]
    timeframe: int


class RecommendationOut(BaseSchema):
    product: ProductOut
    reason: Optional[str] = None


class UserProfileOut(BaseSchema):
    id: str
    name: str
    preferred_categories: List[str] = []
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None


class UserProfileIn(BaseSchema):
    id: str
    name: str
    preferred_categories: List[str] = []
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None


class UserProfileUpdate(BaseSchema):
    name: Optional[str] = None
    preferred_categories: Optional[List[str]] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None


class UserEventIn(BaseSchema):
    user_id: str
    product_id: str
    event_type: str


class ChatRequest(BaseSchema):
    message: str = Field(..., min_length=1)
    product_id: Optional[str] = None
    user_id: Optional[str] = None


class ChatResponse(BaseSchema):
    reply: str
    intent: str
    payload: dict
