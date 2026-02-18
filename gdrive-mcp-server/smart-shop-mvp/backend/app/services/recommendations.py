from __future__ import annotations

from typing import List, Optional

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

import json

from ..ai_schemas import RecommendationAI
from ..models import Product, UserEvent, UserProfile
from ..schemas import ProductOut, RecommendationOut
from .ai_client import DEFAULT_MODEL, get_client


def _product_out(product: Product) -> ProductOut:
    return ProductOut(
        id=product.id,
        name=product.name,
        brand=product.brand,
        category=product.category,
        price=product.price,
        description=product.description,
        stock=product.stock,
        rating=product.rating,
    )


def _score_candidate(base: Product, candidate: Product) -> float:
    price_diff = abs(candidate.price - base.price)
    price_score = 1 - min(price_diff / max(base.price, 1), 1)
    stock_score = 1 if candidate.stock > 0 else 0
    return (candidate.rating or 0) * 2 + price_score + stock_score


def _fetch_candidates(
    session: Session, product_id: Optional[str], query: Optional[str], user: Optional[UserProfile]
) -> List[Product]:
    hard_pref = bool(user and user.id.lower() == "ashad" and user.preferred_categories)

    def _apply_budget(items: List[Product]) -> List[Product]:
        if not user:
            return items
        if user.budget_min is None or user.budget_max is None:
            return items
        return [item for item in items if user.budget_min <= item.price <= user.budget_max]

    if product_id:
        base = session.get(Product, product_id)
        if not base:
            return []
        if hard_pref and base.category not in user.preferred_categories:
            return []
        stmt = select(Product).where(Product.category == base.category, Product.id != product_id)
        return _apply_budget(session.execute(stmt).scalars().all())

    if query:
        like = f"%{query.lower()}%"
        stmt = select(Product).where(
            or_(
                Product.name.ilike(like),
                Product.brand.ilike(like),
                Product.category.ilike(like),
                Product.description.ilike(like),
            )
        )
        if hard_pref:
            stmt = stmt.where(Product.category.in_(user.preferred_categories))
        return _apply_budget(session.execute(stmt).scalars().all())

    if hard_pref:
        stmt_pref = (
            select(Product)
            .where(Product.category.in_(user.preferred_categories))
            .order_by(Product.rating.desc())
            .limit(24)
        )
        return _apply_budget(session.execute(stmt_pref).scalars().all())

    candidates = []
    if user and user.preferred_categories:
        stmt_pref = (
            select(Product)
            .where(Product.category.in_(user.preferred_categories))
            .order_by(Product.rating.desc())
            .limit(24)
        )
        candidates = session.execute(stmt_pref).scalars().all()
        candidates = _apply_budget(candidates)

    if len(candidates) < 12:
        stmt = select(Product).order_by(Product.rating.desc()).limit(24)
        top_rated = session.execute(stmt).scalars().all()
        existing_ids = {product.id for product in candidates}
        candidates.extend([product for product in top_rated if product.id not in existing_ids])
        candidates = _apply_budget(candidates)
    if candidates:
        return candidates

    stmt = select(Product).order_by(Product.rating.desc()).limit(24)
    return _apply_budget(session.execute(stmt).scalars().all())


def recommend_products(
    session: Session,
    product_id: Optional[str] = None,
    query: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 6,
) -> List[RecommendationOut]:
    user = session.get(UserProfile, user_id) if user_id else None
    candidates = _fetch_candidates(session, product_id, query, user)
    if not candidates:
        return []

    base = session.get(Product, product_id) if product_id else None
    affinity = {}
    if user:
        weight_case = case(
            (UserEvent.event_type == "purchase", 3),
            (UserEvent.event_type == "wishlist", 2),
            else_=1,
        )
        stmt = (
            select(Product.category, func.sum(weight_case))
            .join(UserEvent, UserEvent.product_id == Product.id)
            .where(UserEvent.user_id == user.id)
            .group_by(Product.category)
        )
        affinity = {row[0]: float(row[1] or 0) for row in session.execute(stmt).all()}

    if base:
        scored = sorted(
            candidates,
            key=lambda p: _score_candidate(base, p) + affinity.get(p.category, 0),
            reverse=True,
        )
    else:
        def _score(p: Product) -> float:
            base_score = (p.rating or 0) + (1 if p.stock > 0 else 0)
            pref_bonus = 2 if user and p.category in user.preferred_categories else 0
            affinity_bonus = affinity.get(p.category, 0)
            budget_bonus = 0
            if user and user.budget_min is not None and user.budget_max is not None:
                if user.budget_min <= p.price <= user.budget_max:
                    budget_bonus = 1
            return base_score + pref_bonus + affinity_bonus + budget_bonus

        scored = sorted(candidates, key=_score, reverse=True)

    shortlist = scored[: max(limit * 2, limit)]
    client = get_client()
    if client and shortlist:
        try:
            prompt = {
                "role": "system",
                "content": (
                    "You are an e-commerce recommendation engine. "
                    "Select the best products from the provided list and provide concise reasons."
                ),
            }
            user_msg = {
                "role": "user",
                "content": json.dumps(
                    {
                        "base_product": _product_out(base).model_dump() if base else None,
                        "candidates": [
                            {
                                "id": product.id,
                                "name": product.name,
                                "brand": product.brand,
                                "category": product.category,
                                "price": product.price,
                                "rating": product.rating,
                                "stock": product.stock,
                            }
                            for product in shortlist
                        ],
                        "limit": limit,
                    }
                ),
            }
            parsed: RecommendationAI = client.parse(
                DEFAULT_MODEL,
                [prompt, user_msg],
                RecommendationAI,
            )
            recommendations = []
            for idx, product_id in enumerate(parsed.recommended_ids[:limit]):
                product = next((p for p in shortlist if p.id == product_id), None)
                if product:
                    reason = parsed.reasons[idx] if idx < len(parsed.reasons) else None
                    recommendations.append(
                        RecommendationOut(product=_product_out(product), reason=reason)
                    )
            if recommendations:
                return recommendations
        except Exception:
            pass

    return [RecommendationOut(product=_product_out(product)) for product in shortlist[:limit]]
