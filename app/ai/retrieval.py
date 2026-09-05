from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import OPENAI_EMBEDDING_MODEL
from app.models import KnowledgeArticle, KnowledgeChunk


DEFAULT_TOP_K = 4
MAX_COSINE_DISTANCE = 0.55


@dataclass(frozen=True)
class RetrievedKnowledge:
    chunk_id: int
    article_id: int
    article_title: str
    source_name: str
    content: str
    cosine_distance: float


class KnowledgeRetrievalError(Exception):
    pass


def retrieve_knowledge_by_embedding(
    db: Session,
    query_embedding: list[float],
    *,
    top_k: int = DEFAULT_TOP_K,
    max_cosine_distance: float = MAX_COSINE_DISTANCE,
) -> list[RetrievedKnowledge]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    cosine_distance = KnowledgeChunk.embedding.cosine_distance(
        query_embedding
    )

    statement = (
        select(
            KnowledgeChunk,
            KnowledgeArticle,
            cosine_distance.label("cosine_distance"),
        )
        .join(
            KnowledgeArticle,
            KnowledgeArticle.id == KnowledgeChunk.article_id,
        )
        .where(
            KnowledgeChunk.embedding.is_not(None),
            KnowledgeChunk.embedding_model == OPENAI_EMBEDDING_MODEL,
            cosine_distance <= max_cosine_distance,
        )
        .order_by(cosine_distance)
        .limit(top_k * 4)
    )

    try:
        matches = db.execute(statement).all()
    except SQLAlchemyError as error:
        raise KnowledgeRetrievalError(
            "Could not search knowledge embeddings"
        ) from error

    retrieved: list[RetrievedKnowledge] = []
    seen_article_ids: set[int] = set()

    for chunk, article, distance in matches:
        if article.id in seen_article_ids:
            continue

        retrieved.append(
            RetrievedKnowledge(
                chunk_id=chunk.id,
                article_id=article.id,
                article_title=article.title,
                source_name=article.source_name,
                content=chunk.content,
                cosine_distance=float(distance),
            )
        )
        seen_article_ids.add(article.id)

        if len(retrieved) == top_k:
            break

    return retrieved
