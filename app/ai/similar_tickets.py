from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import OPENAI_EMBEDDING_MODEL
from app.models import Ticket


HISTORICAL_TICKET_STATUSES = ("RESOLVED", "CLOSED")
MAX_SIMILAR_TICKET_COSINE_DISTANCE = 0.55


@dataclass(frozen=True)
class RetrievedSimilarTicket:
    ticket_id: int
    title: str
    description: str
    resolution: str
    status: str
    cosine_distance: float


class SimilarTicketRetrievalError(Exception):
    pass


def retrieve_similar_tickets(
    db: Session,
    query_embedding: list[float],
    *,
    exclude_ticket_id: int,
    limit: int = 3,
    max_cosine_distance: float = MAX_SIMILAR_TICKET_COSINE_DISTANCE,
) -> list[RetrievedSimilarTicket]:
    if limit <= 0:
        raise ValueError("limit must be positive")

    cosine_distance = Ticket.embedding.cosine_distance(query_embedding)
    statement = (
        select(Ticket, cosine_distance.label("cosine_distance"))
        .where(
            Ticket.id != exclude_ticket_id,
            Ticket.status.in_(HISTORICAL_TICKET_STATUSES),
            Ticket.resolution.is_not(None),
            func.length(func.trim(Ticket.resolution)) > 0,
            Ticket.embedding.is_not(None),
            Ticket.embedding_model == OPENAI_EMBEDDING_MODEL,
            cosine_distance <= max_cosine_distance,
        )
        .order_by(cosine_distance)
        .limit(limit)
    )

    try:
        matches = db.execute(statement).all()
    except SQLAlchemyError as error:
        raise SimilarTicketRetrievalError(
            "Could not search historical ticket embeddings"
        ) from error

    return [
        RetrievedSimilarTicket(
            ticket_id=ticket.id,
            title=ticket.title,
            description=ticket.description,
            resolution=ticket.resolution or "",
            status=ticket.status,
            cosine_distance=float(distance),
        )
        for ticket, distance in matches
    ]
