from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..models import Product
from ..schemas import PriceComparison, ProductOut


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


def get_price_comparison(session: Session, product_id: str) -> PriceComparison | None:
    product = session.get(Product, product_id)
    if not product:
        return None

    stmt = select(func.min(Product.price), func.max(Product.price), func.avg(Product.price)).where(
        Product.category == product.category
    )
    min_price, max_price, avg_price = session.execute(stmt).one()

    cheaper_stmt = (
        select(Product)
        .where(Product.category == product.category, Product.price < product.price)
        .order_by(Product.price.asc())
        .limit(5)
    )
    cheaper = session.execute(cheaper_stmt).scalars().all()

    return PriceComparison(
        base=_product_out(product),
        min=round(min_price or product.price, 2),
        max=round(max_price or product.price, 2),
        avg=round(float(avg_price or product.price), 2),
        cheaper=[_product_out(item) for item in cheaper],
        updated_at=datetime.utcnow().isoformat() + "Z",
    )
