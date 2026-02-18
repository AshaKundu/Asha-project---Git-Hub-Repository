from __future__ import annotations

import json
import re
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from ..ai_schemas import ChatResponseAI, IntentResponse
from ..models import Product, Review
from ..schemas import ChatResponse
from .ai_client import DEFAULT_MODEL, get_client
from .policies import get_policy_by_category, get_policy_for_product
from .price_compare import get_price_comparison
from .recommendations import recommend_products
from .reviews import get_review_summary


def _heuristic_intent(message: str) -> str:
    text = message.lower()
    if any(word in text for word in ["policy", "return", "warranty"]):
        return "policy"
    if any(word in text for word in ["review", "summary", "sentiment"]):
        return "review"
    if any(word in text for word in ["compare", "price", "cheaper"]):
        return "price"
    if any(word in text for word in ["recommend", "suggest", "similar"]):
        return "recommend"
    return "search"


def _extract_category(message: str) -> Optional[str]:
    text = message.lower()
    if any(word in text for word in ["mobile", "phone", "smartphone"]):
        return "smartphone"
    if "laptop" in text:
        return "laptop"
    if "speaker" in text:
        return "speaker"
    if "tv" in text:
        return "smart_tv"
    return None


def _is_cheapest_request(message: str) -> bool:
    text = message.lower()
    return any(word in text for word in ["cheap", "cheapest", "lowest", "budget", "affordable"])


def _extract_budget_limit(message: str) -> Optional[float]:
    text = message.lower()
    match = re.search(r"(under|below|less than)\s*\$?\s*(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(2))
    match = re.search(r"\$\s*(\d+(?:\.\d+)?)", text)
    if match:
        return float(match.group(1))
    return None


def _extract_product_id(message: str) -> Optional[str]:
    match = re.search(r"\b[A-Z]{2,4}\d{3,5}\b", message)
    return match.group(0) if match else None


def _extract_product_ids(message: str) -> list[str]:
    return re.findall(r"\b[A-Z]{2,4}\d{3,5}\b", message)


def _detect_intent(message: str) -> IntentResponse:
    client = get_client()
    if client:
        try:
            parsed: IntentResponse = client.parse(
                DEFAULT_MODEL,
                [
                    {
                        "role": "system",
                        "content": "Classify the customer intent.",
                    },
                    {"role": "user", "content": message},
                ],
                IntentResponse,
            )
            if parsed.intent:
                return parsed
        except Exception:
            pass
    return IntentResponse(intent=_heuristic_intent(message))


def handle_chat(
    session: Session, message: str, product_id: Optional[str], user_id: Optional[str]
) -> ChatResponse:
    intent_data = _detect_intent(message)
    intent = intent_data.intent
    payload = {}

    budget = _extract_budget_limit(message)
    if budget is not None:
        category = _extract_category(message)
        stmt = select(Product)
        if category:
            stmt = stmt.where(Product.category == category)
        stmt = stmt.where(Product.price <= budget).order_by(Product.price.asc()).limit(10)
        matches = session.execute(stmt).scalars().all()
        payload["results"] = [
            {"product": {"name": item.name, "price": item.price, "id": item.id}}
            for item in matches
        ]
        if matches:
            reply = f"Here are {category or 'products'} under ${budget:.0f}."
        else:
            reply = f"No {category or 'products'} found under ${budget:.0f}."
        return ChatResponse(reply=reply, intent="budget_search", payload=payload)

    if intent == "policy":
        policy = None
        if product_id:
            policy = get_policy_for_product(session, product_id)
        if not policy and intent_data.category:
            policy = get_policy_by_category(session, intent_data.category)
        payload["policy"] = policy.model_dump() if policy else None
        reply = (
            f"Return policy: {policy.description}. Timeframe: {policy.timeframe} days."
            if policy
            else "I couldn't find a matching policy. Provide a product ID or category."
        )

    elif intent == "review":
        review_target = product_id or _extract_product_id(message)
        if not review_target:
            category = _extract_category(message)
            if category:
                stmt = select(Product).where(Product.category == category).order_by(Product.rating.desc()).limit(1)
                candidate = session.execute(stmt).scalars().first()
                review_target = candidate.id if candidate else None
        if not review_target:
            reply = "Tell me the product ID or name for review details."
        else:
            summary = get_review_summary(session, review_target)
            payload["summary"] = summary.model_dump()
            stmt = (
                select(Product)
                .where(Product.id == review_target)
                .limit(1)
            )
            product = session.execute(stmt).scalars().first()
            review_stmt = (
                select(Review)
                .where(Review.product_id == review_target)
                .order_by(Review.date.desc())
                .limit(5)
            )
            review_rows = session.execute(review_stmt).scalars().all()
            payload["reviews"] = [
                {"rating": row.rating, "text": row.text, "date": row.date.isoformat() if row.date else None}
                for row in review_rows
            ]
            product_name = product.name if product else review_target
            if review_rows:
                reply = f"Here are recent reviews for {product_name}."
            else:
                reply = f"No reviews found for {product_name}."

    elif intent == "price":
        if not product_id:
            ids = _extract_product_ids(message)
            if len(ids) >= 2:
                left = session.get(Product, ids[0])
                right = session.get(Product, ids[1])
                if left and right:
                    left_summary = get_review_summary(session, left.id)
                    right_summary = get_review_summary(session, right.id)
                    left_policy = get_policy_for_product(session, left.id)
                    right_policy = get_policy_for_product(session, right.id)
                    payload["comparison_pair"] = {
                        "left": {
                            "id": left.id,
                            "name": left.name,
                            "price": left.price,
                            "category": left.category,
                            "rating": left.rating,
                            "review_summary": left_summary.model_dump(),
                            "policy": left_policy.model_dump() if left_policy else None,
                        },
                        "right": {
                            "id": right.id,
                            "name": right.name,
                            "price": right.price,
                            "category": right.category,
                            "rating": right.rating,
                            "review_summary": right_summary.model_dump(),
                            "policy": right_policy.model_dump() if right_policy else None,
                        },
                    }
                    reply = (
                        f"{left.name} (${left.price:.2f}) vs {right.name} (${right.price:.2f}). "
                        f"Categories: {left.category} vs {right.category}."
                    )
                else:
                    reply = "I couldn't find one of those products. Check the IDs."
            else:
                reply = "Tell me the product ID to compare prices."
        else:
            comparison = get_price_comparison(session, product_id)
            if comparison:
                payload["comparison"] = comparison.model_dump()
                reply = (
                    f"Price range for {comparison.base.category}: "
                    f"${comparison.min} - ${comparison.max} (avg ${comparison.avg})."
                )
            else:
                reply = "I couldn't find that product."

    elif intent == "recommend":
        if _is_cheapest_request(message):
            category = _extract_category(message)
            stmt = select(Product)
            if category:
                stmt = stmt.where(Product.category == category)
            stmt = stmt.order_by(Product.price.asc()).limit(5)
            cheapest = session.execute(stmt).scalars().all()
            payload["cheapest"] = [
                {"id": item.id, "name": item.name, "price": item.price, "category": item.category}
                for item in cheapest
            ]
            if cheapest:
                reply = "Here are the cheapest options I found."
            else:
                reply = "I couldn't find cheap options for that category."
        elif _extract_budget_limit(message) is not None:
            category = _extract_category(message)
            budget = _extract_budget_limit(message)
            stmt = select(Product)
            if category:
                stmt = stmt.where(Product.category == category)
            stmt = stmt.where(Product.price <= budget).order_by(Product.price.asc()).limit(10)
            matches = session.execute(stmt).scalars().all()
            payload["results"] = [
                {"product": {"name": item.name, "price": item.price, "id": item.id}}
                for item in matches
            ]
            if matches:
                reply = f"Here are {category or 'products'} under ${budget:.0f}."
            else:
                reply = f"No {category or 'products'} found under ${budget:.0f}."
        else:
            recommendations = recommend_products(
                session, product_id=product_id, query=message, user_id=user_id
            )
            payload["recommendations"] = [rec.model_dump() for rec in recommendations]
            reply = "Here are recommendations based on your request."

    else:
        recommendations = recommend_products(session, query=message, user_id=user_id)
        payload["results"] = [rec.model_dump() for rec in recommendations]
        reply = "Here are products that might match."

    client = get_client()
    if client:
        try:
            parsed: ChatResponseAI = client.parse(
                DEFAULT_MODEL,
                [
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful e-commerce assistant. "
                            "Rewrite the response to be friendly and concise."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "message": message,
                                "intent": intent,
                            "draft_reply": reply,
                            "user_id": user_id,
                            }
                        ),
                    },
                ],
                ChatResponseAI,
            )
            reply = parsed.reply
        except Exception:
            pass

    return ChatResponse(reply=reply, intent=intent, payload=payload)
