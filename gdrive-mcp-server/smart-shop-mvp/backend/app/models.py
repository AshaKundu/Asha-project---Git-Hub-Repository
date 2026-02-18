from __future__ import annotations

from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .db import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    brand = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    price = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    stock = Column(Integer, nullable=False)
    rating = Column(Float, nullable=False)
    row_index = Column(Integer, nullable=False, index=True, default=0)

    reviews = relationship("Review", back_populates="product")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False, index=True)
    rating = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    date = Column(Date, nullable=True)

    product = relationship("Product", back_populates="reviews")


class StorePolicy(Base):
    __tablename__ = "store_policies"

    id = Column(Integer, primary_key=True, index=True)
    policy_type = Column(String, nullable=False, index=True)
    description = Column(String, nullable=False)
    conditions = Column(JSONB, nullable=False)
    timeframe = Column(Integer, nullable=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    preferred_categories = Column(JSONB, nullable=False, default=list)
    budget_min = Column(Float, nullable=True)
    budget_max = Column(Float, nullable=True)

    events = relationship("UserEvent", back_populates="user")


class UserEvent(Base):
    __tablename__ = "user_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("user_profiles.id"), nullable=False, index=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    created_at = Column(Date, nullable=False)

    user = relationship("UserProfile", back_populates="events")
    product = relationship("Product")
