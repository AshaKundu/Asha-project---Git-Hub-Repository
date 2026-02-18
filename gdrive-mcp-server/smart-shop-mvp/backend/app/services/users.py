from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Product, UserEvent, UserProfile
from ..schemas import UserEventIn, UserProfileIn, UserProfileOut, UserProfileUpdate


def list_users(session: Session) -> List[UserProfileOut]:
    users = session.execute(select(UserProfile).order_by(UserProfile.name.asc())).scalars().all()
    return [UserProfileOut.model_validate(user) for user in users]


def get_user(session: Session, user_id: str) -> UserProfileOut | None:
    user = session.get(UserProfile, user_id)
    return UserProfileOut.model_validate(user) if user else None


def create_user(session: Session, payload: UserProfileIn) -> UserProfileOut:
    user = UserProfile(
        id=payload.id,
        name=payload.name,
        preferred_categories=payload.preferred_categories,
        budget_min=payload.budget_min,
        budget_max=payload.budget_max,
    )
    session.add(user)
    session.commit()
    return UserProfileOut.model_validate(user)


def update_user(session: Session, user_id: str, payload: UserProfileUpdate) -> UserProfileOut | None:
    user = session.get(UserProfile, user_id)
    if not user:
        return None
    if payload.name is not None:
        user.name = payload.name
    if payload.preferred_categories is not None:
        user.preferred_categories = payload.preferred_categories
    user.budget_min = payload.budget_min
    user.budget_max = payload.budget_max
    session.commit()
    return UserProfileOut.model_validate(user)


def record_event(session: Session, event: UserEventIn) -> None:
    user = session.get(UserProfile, event.user_id)
    product = session.get(Product, event.product_id)
    if not user or not product:
        return
    session.add(
        UserEvent(
            user_id=event.user_id,
            product_id=event.product_id,
            event_type=event.event_type,
            created_at=date.today(),
        )
    )
    session.commit()
