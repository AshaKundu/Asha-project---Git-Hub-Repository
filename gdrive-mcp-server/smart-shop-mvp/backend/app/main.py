from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from .db import Base, SessionLocal, engine, get_db
from .models import Product, UserProfile, Review
from .schemas import (
    ChatRequest,
    ChatResponse,
    PolicyOut,
    PriceComparison,
    ProductOut,
    RecommendationOut,
    ReviewSummary,
    ReviewOut,
    UserEventIn,
    UserProfileIn,
    UserProfileOut,
    UserProfileUpdate,
)
from .seed import seed_if_needed
from .services.chat import handle_chat
from .services.policies import get_policy_by_category, get_policy_for_product
from .services.price_compare import get_price_comparison
from .services.recommendations import recommend_products
from .services.reviews import get_review_summary
from .services.users import create_user, get_user, list_users, record_event, update_user

Base.metadata.create_all(bind=engine)
with engine.begin() as connection:
    connection.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS row_index INTEGER"))

app = FastAPI(title="Smart Shop MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"] ,
)


@app.on_event("startup")
def _startup() -> None:
    if os.getenv("AUTO_SEED", "true").lower() == "true":
        session = SessionLocal()
        try:
            seed_if_needed(session)
        finally:
            session.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/products", response_model=list[ProductOut])
def list_products(
    query: str | None = None,
    category: str | None = None,
    user_id: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock_only: bool = False,
    db: Session = Depends(get_db),
):
    query_obj = db.query(Product)
    if category:
        query_obj = query_obj.filter(Product.category == category)
    if query:
        like = f"%{query.lower()}%"
        query_obj = query_obj.filter(
            Product.name.ilike(like)
            | Product.brand.ilike(like)
            | Product.description.ilike(like)
            | Product.category.ilike(like)
        )
    if min_price is not None:
        query_obj = query_obj.filter(Product.price >= min_price)
    if max_price is not None:
        query_obj = query_obj.filter(Product.price <= max_price)
    if in_stock_only:
        query_obj = query_obj.filter(Product.stock > 0)
    if user_id:
        user = db.get(UserProfile, user_id)
        if user and user.id.lower() == "ashad" and user.preferred_categories:
            query_obj = query_obj.filter(Product.category.in_(user.preferred_categories))
    query_obj = query_obj.order_by(Product.row_index.asc())
    return [ProductOut.model_validate(item) for item in query_obj.limit(100).all()]


@app.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut.model_validate(product)


@app.get("/recommendations", response_model=list[RecommendationOut])
def recommendations(
    product_id: str | None = None,
    query: str | None = None,
    user_id: str | None = None,
    db: Session = Depends(get_db),
):
    return recommend_products(db, product_id=product_id, query=query, user_id=user_id)


@app.get("/reviews/summary", response_model=ReviewSummary)
def review_summary(product_id: str, db: Session = Depends(get_db)):
    return get_review_summary(db, product_id)


@app.get("/reviews", response_model=list[ReviewOut])
def list_reviews(product_id: str, db: Session = Depends(get_db)):
    reviews = (
        db.query(Review)
        .filter_by(product_id=product_id)
        .order_by(Review.date.desc())
        .limit(10)
        .all()
    )
    return [ReviewOut.model_validate(review) for review in reviews]


@app.get("/price-compare", response_model=PriceComparison)
def price_compare(product_id: str, db: Session = Depends(get_db)):
    comparison = get_price_comparison(db, product_id)
    if not comparison:
        raise HTTPException(status_code=404, detail="Product not found")
    return comparison


@app.get("/policy", response_model=PolicyOut)
def policy(
    product_id: str | None = None,
    category: str | None = None,
    policy_type: str | None = "returns",
    db: Session = Depends(get_db),
):
    policy_type = policy_type or "returns"
    if product_id:
        policy_out = get_policy_for_product(db, product_id, policy_type)
    elif category:
        policy_out = get_policy_by_category(db, category, policy_type)
    else:
        raise HTTPException(status_code=400, detail="product_id or category required")
    if not policy_out:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy_out


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    return handle_chat(db, request.message, request.product_id, request.user_id)


@app.get("/users", response_model=list[UserProfileOut])
def users(db: Session = Depends(get_db)):
    return list_users(db)


@app.get("/users/{user_id}", response_model=UserProfileOut)
def user_detail(user_id: str, db: Session = Depends(get_db)):
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/users", response_model=UserProfileOut)
def user_create(payload: UserProfileIn, db: Session = Depends(get_db)):
    if get_user(db, payload.id):
        raise HTTPException(status_code=400, detail="User already exists")
    return create_user(db, payload)


@app.put("/users/{user_id}", response_model=UserProfileOut)
def user_update(user_id: str, payload: UserProfileUpdate, db: Session = Depends(get_db)):
    updated = update_user(db, user_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@app.post("/users/events")
def user_event(event: UserEventIn, db: Session = Depends(get_db)):
    record_event(db, event)
    return {"status": "ok"}
