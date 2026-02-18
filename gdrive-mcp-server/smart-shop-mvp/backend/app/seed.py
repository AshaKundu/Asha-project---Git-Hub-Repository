from __future__ import annotations

import csv
import os
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Product, Review, StorePolicy, UserEvent, UserProfile

DEFAULT_DATA_DIR = Path("C:/Users/ashad/Downloads/Smart Shop")


def _load_csv(path: Path):
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            with path.open("r", encoding=encoding) as handle:
                reader = csv.DictReader(handle)
                return list(reader)
        except UnicodeDecodeError:
            continue
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle)
        return list(reader)


def seed_database(session: Session, data_dir: Path) -> None:
    products_path = data_dir / "products.csv"
    reviews_path = data_dir / "reviews.csv"
    policies_path = data_dir / "store_policies.csv"
    users_path = data_dir / "users.csv"
    events_path = data_dir / "user_events.csv"

    if not products_path.exists():
        raise FileNotFoundError(f"Missing {products_path}")
    if not reviews_path.exists():
        raise FileNotFoundError(f"Missing {reviews_path}")
    if not policies_path.exists():
        raise FileNotFoundError(f"Missing {policies_path}")

    products = _load_csv(products_path)
    reviews = _load_csv(reviews_path)
    policies = _load_csv(policies_path)

    session.query(UserEvent).delete()
    session.query(UserProfile).delete()
    session.query(Review).delete()
    session.query(StorePolicy).delete()
    session.query(Product).delete()

    for idx, row in enumerate(products):
        session.add(
            Product(
                id=row["id"],
                name=row["name"],
                brand=row["brand"],
                category=row["category"],
                price=float(row["price"]),
                description=row["description"],
                stock=int(row["stock"]),
                rating=float(row["rating"]),
                row_index=idx,
            )
        )

    for row in reviews:
        review_date = date.fromisoformat(row["date"]) if row.get("date") else None
        session.add(
            Review(
                product_id=row["product_id"],
                rating=float(row["rating"]),
                text=row["text"],
                date=review_date,
            )
        )

    for row in policies:
        conditions = row.get("conditions", "").split("|") if row.get("conditions") else []
        session.add(
            StorePolicy(
                policy_type=row["policy_type"],
                description=row["description"],
                conditions=conditions,
                timeframe=int(row["timeframe"]),
            )
        )

    _seed_users(session, users_path)

    if events_path.exists():
        events = _load_csv(events_path)
        for row in events:
            event_date = date.fromisoformat(row["date"]) if row.get("date") else date.today()
            session.add(
                UserEvent(
                    user_id=row["user_id"],
                    product_id=row["product_id"],
                    event_type=row.get("event_type", "view"),
                    created_at=event_date,
                )
            )

    session.commit()


def _seed_users(session: Session, users_path: Path) -> None:
    if users_path.exists():
        users = _load_csv(users_path)
        for row in users:
            categories = (
                row.get("preferred_categories", "").split("|")
                if row.get("preferred_categories")
                else []
            )
            session.add(
                UserProfile(
                    id=row["id"],
                    name=row["name"],
                    preferred_categories=categories,
                    budget_min=float(row["budget_min"]) if row.get("budget_min") else None,
                    budget_max=float(row["budget_max"]) if row.get("budget_max") else None,
                )
            )
        return

    session.add_all(
        [
            UserProfile(
                id="U001",
                name="Alex Kim",
                preferred_categories=["smartphone", "laptop"],
                budget_min=300,
                budget_max=1200,
            ),
            UserProfile(
                id="U002",
                name="Jordan Lee",
                preferred_categories=["smart_tv", "speaker"],
                budget_min=200,
                budget_max=2000,
            ),
            UserProfile(
                id="U003",
                name="Sam Rivera",
                preferred_categories=["laptop"],
                budget_min=500,
                budget_max=1800,
            ),
        ]
    )


def seed_if_needed(session: Session) -> bool:
    has_products = session.execute(select(Product).limit(1)).scalars().first()
    if has_products:
        has_users = session.execute(select(UserProfile).limit(1)).scalars().first()
        if not has_users:
            data_dir = Path(os.getenv("SMART_SHOP_DATA_DIR", str(DEFAULT_DATA_DIR)))
            _seed_users(session, data_dir / "users.csv")
            session.commit()
            return True
        return False

    data_dir = Path(os.getenv("SMART_SHOP_DATA_DIR", str(DEFAULT_DATA_DIR)))
    seed_database(session, data_dir)
    return True
