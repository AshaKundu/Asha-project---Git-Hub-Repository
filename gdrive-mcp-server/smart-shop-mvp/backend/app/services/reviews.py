from __future__ import annotations

import re
from collections import Counter
import json
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai_schemas import ReviewSummaryAI
from ..models import Review
from ..schemas import ReviewSummary, SentimentBreakdown, Theme
from .ai_client import DEFAULT_MODEL, get_client

STOPWORDS = {
    "the",
    "and",
    "a",
    "an",
    "is",
    "it",
    "this",
    "that",
    "to",
    "of",
    "for",
    "in",
    "on",
    "with",
    "very",
    "really",
    "my",
    "our",
    "your",
    "all",
    "at",
    "as",
    "was",
    "were",
    "be",
    "are",
    "but",
    "so",
    "if",
    "by",
    "from",
    "has",
    "have",
    "had",
    "its",
    "i",
    "me",
    "we",
    "you",
    "they",
}

SENTIMENT_LEXICON = {
    "positive": {
        "great",
        "excellent",
        "amazing",
        "love",
        "fast",
        "snappy",
        "beautiful",
        "clear",
        "crystal",
        "smooth",
        "awesome",
        "perfect",
        "good",
        "durable",
        "battery",
        "bright",
    },
    "negative": {
        "bad",
        "poor",
        "slow",
        "broken",
        "cracked",
        "damage",
        "overheats",
        "lag",
        "laggy",
        "heavy",
        "dim",
        "terrible",
        "awful",
        "disappoint",
        "noisy",
    },
}


def _tokenize(text: str) -> List[str]:
    tokens = re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()
    return [token for token in tokens if token and token not in STOPWORDS]


def _score_sentiment(text: str) -> int:
    score = 0
    for token in _tokenize(text):
        if token in SENTIMENT_LEXICON["positive"]:
            score += 1
        if token in SENTIMENT_LEXICON["negative"]:
            score -= 1
    return score


def get_review_summary(session: Session, product_id: str) -> ReviewSummary:
    stmt = select(Review).where(Review.product_id == product_id)
    reviews = session.execute(stmt).scalars().all()

    if not reviews:
        return ReviewSummary(
            average_rating=0,
            total_reviews=0,
            sentiment=SentimentBreakdown(),
            themes=[],
            summary_text="No reviews yet.",
        )

    total_rating = sum(review.rating for review in reviews)
    sentiment = SentimentBreakdown()
    tokens = Counter()

    for review in reviews:
        score = _score_sentiment(review.text)
        if review.rating >= 4 or score > 0:
            sentiment.positive += 1
        elif review.rating <= 2 or score < 0:
            sentiment.negative += 1
        else:
            sentiment.neutral += 1

        tokens.update(_tokenize(review.text))

    themes = [Theme(word=word, count=count) for word, count in tokens.most_common(5)]
    summary_text = ""

    client = get_client()
    if client:
        try:
            parsed: ReviewSummaryAI = client.parse(
                DEFAULT_MODEL,
                [
                    {
                        "role": "system",
                        "content": (
                            "Summarize customer reviews with a short summary and 3-5 themes."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "reviews": [review.text for review in reviews],
                                "average_rating": round(total_rating / len(reviews), 2),
                                "sentiment": sentiment.model_dump(),
                            }
                        ),
                    },
                ],
                ReviewSummaryAI,
            )
            summary_text = parsed.summary_text
            if parsed.themes:
                themes = [Theme(word=word, count=tokens.get(word, 1)) for word in parsed.themes]
        except Exception:
            summary_text = ""

    avg = round(total_rating / len(reviews), 2)
    return ReviewSummary(
        average_rating=avg,
        total_reviews=len(reviews),
        sentiment=sentiment,
        themes=themes,
        summary_text=summary_text,
    )
