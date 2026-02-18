from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Product, StorePolicy
from ..schemas import PolicyOut

CATEGORY_POLICY_MAP = {
    "returns": {
        "laptop": "Laptop Return Policy",
        "smartphone": "Smartphone Return Policy",
        "smart_tv": "Smart TV Return Policy",
        "speaker": "Speaker Return Policy",
    },
    "warranty": {
        "laptop": "Standard Laptop Warranty",
        "smartphone": "Standard Smartphone Warranty",
        "speaker": "Speaker Warranty",
    },
}


def _policy_out(policy: StorePolicy) -> PolicyOut:
    return PolicyOut(
        policy_type=policy.policy_type,
        description=policy.description,
        conditions=policy.conditions,
        timeframe=policy.timeframe,
    )


def get_policy_by_category(
    session: Session, category: str, policy_type: str = "returns"
) -> PolicyOut | None:
    policy_name = CATEGORY_POLICY_MAP.get(policy_type, {}).get(category)
    if not policy_name:
        return None
    stmt = select(StorePolicy).where(StorePolicy.description == policy_name)
    policy = session.execute(stmt).scalar_one_or_none()
    return _policy_out(policy) if policy else None


def get_policy_for_product(
    session: Session, product_id: str, policy_type: str = "returns"
) -> PolicyOut | None:
    product = session.get(Product, product_id)
    if not product:
        return None
    return get_policy_by_category(session, product.category, policy_type)
