from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.copilot import (
    CopilotServiceResponseError,
    CopilotServiceUnavailableError,
    generate_support_copilot,
)
from app.ai.drafts import (
    DraftServiceResponseError,
    DraftServiceUnavailableError,
    generate_customer_email_draft,
    generate_resolution_draft,
)
from app.ai.embedding_text import (
    build_ticket_embedding_text,
    build_troubleshooting_query,
)
from app.ai.embeddings import (
    EmbeddingServiceResponseError,
    EmbeddingServiceUnavailableError,
    generate_embedding,
)
from app.ai.retrieval import (
    KnowledgeRetrievalError,
    RetrievedKnowledge,
    retrieve_knowledge_by_embedding,
)
from app.ai.similar_tickets import (
    HISTORICAL_TICKET_STATUSES,
    RetrievedSimilarTicket,
    SimilarTicketRetrievalError,
    retrieve_similar_tickets,
)
from app.ai.service import (
    AIServiceResponseError,
    AIServiceUnavailableError,
    analyze_ticket,
)
from app.auth import get_current_user
from app.authorization import require_roles
from app.config import OPENAI_EMBEDDING_MODEL
from app.database import get_db
from app.enums import UserRole
from app.models import Ticket as TicketModel
from app.models import User as UserModel
from app.schemas import (
    CustomerEmailDraftResponse,
    KnowledgeSource,
    ResolutionDraftRequest,
    ResolutionDraftResponse,
    SimilarTicketResponse,
    SimilarTicketSource,
    TicketAIAnalysis,
    TicketCreate,
    TicketEmbeddingResponse,
    TicketResponse,
    TicketUpdate,
    TroubleshootRequest,
    TroubleshootingResponse,
)


router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


def generate_embedding_for_api(text: str) -> list[float]:
    try:
        return generate_embedding(text)
    except EmbeddingServiceUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service is temporarily unavailable",
        ) from error
    except EmbeddingServiceResponseError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Embedding provider returned an invalid response",
        ) from error


def retrieve_knowledge_for_api(
    db: Session,
    query_embedding: list[float],
) -> list[RetrievedKnowledge]:
    try:
        return retrieve_knowledge_by_embedding(db, query_embedding)
    except KnowledgeRetrievalError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve knowledge-base context",
        ) from error


def retrieve_similar_tickets_for_api(
    db: Session,
    query_embedding: list[float],
    *,
    exclude_ticket_id: int,
) -> list[RetrievedSimilarTicket]:
    try:
        return retrieve_similar_tickets(
            db,
            query_embedding,
            exclude_ticket_id=exclude_ticket_id,
        )
    except SimilarTicketRetrievalError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve similar historical tickets",
        ) from error


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket(
    ticket_data: TicketCreate,
    current_user: UserModel = Depends(
        require_roles(
            UserRole.EMPLOYEE,
            UserRole.SUPPORT_ENGINEER,
            UserRole.ADMIN,
        )
    ),
    db: Session = Depends(get_db),
) -> TicketModel:
    ticket = TicketModel(
        requester_id=current_user.id,
        title=ticket_data.title,
        description=ticket_data.description,
    )

    try:
        db.add(ticket)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create ticket",
        ) from error

    db.refresh(ticket)
    return ticket


@router.get("", response_model=list[TicketResponse])
def get_tickets(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TicketModel]:
    statement = select(TicketModel).order_by(TicketModel.id)

    if current_user.role == UserRole.EMPLOYEE:
        statement = statement.where(
            TicketModel.requester_id == current_user.id
        )

    return list(db.scalars(statement).all())


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TicketModel:
    ticket = db.get(TicketModel, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    if (
        current_user.role == UserRole.EMPLOYEE
        and ticket.requester_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ticket",
        )

    return ticket


@router.post(
    "/{ticket_id}/ai/analyze",
    response_model=TicketAIAnalysis,
)
def analyze_existing_ticket(
    ticket_id: int,
    _: UserModel = Depends(
        require_roles(UserRole.SUPPORT_ENGINEER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> TicketAIAnalysis:
    ticket = db.get(TicketModel, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    try:
        return analyze_ticket(ticket)
    except AIServiceUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI analysis service is temporarily unavailable",
        ) from error
    except AIServiceResponseError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider returned an invalid analysis",
        ) from error


@router.post(
    "/{ticket_id}/ai/resolution-draft",
    response_model=ResolutionDraftResponse,
)
def draft_ticket_resolution(
    ticket_id: int,
    request_data: ResolutionDraftRequest,
    _: UserModel = Depends(
        require_roles(UserRole.SUPPORT_ENGINEER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> ResolutionDraftResponse:
    ticket = db.get(TicketModel, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    try:
        return generate_resolution_draft(
            ticket=ticket,
            evidence=request_data,
        )
    except DraftServiceUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI drafting service is temporarily unavailable",
        ) from error
    except DraftServiceResponseError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider returned an invalid resolution draft",
        ) from error


@router.post(
    "/{ticket_id}/ai/email-draft",
    response_model=CustomerEmailDraftResponse,
)
def draft_customer_email(
    ticket_id: int,
    request_data: ResolutionDraftRequest,
    _: UserModel = Depends(
        require_roles(UserRole.SUPPORT_ENGINEER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> CustomerEmailDraftResponse:
    ticket = db.get(TicketModel, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    try:
        return generate_customer_email_draft(
            ticket=ticket,
            evidence=request_data,
        )
    except DraftServiceUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI drafting service is temporarily unavailable",
        ) from error
    except DraftServiceResponseError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider returned an invalid customer email draft",
        ) from error


@router.post(
    "/{ticket_id}/ai/troubleshoot",
    response_model=TroubleshootingResponse,
)
def troubleshoot_ticket(
    ticket_id: int,
    request_data: TroubleshootRequest,
    _: UserModel = Depends(
        require_roles(UserRole.SUPPORT_ENGINEER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> TroubleshootingResponse:
    ticket = db.get(TicketModel, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    retrieval_query = build_troubleshooting_query(
        title=ticket.title,
        description=ticket.description,
        question=request_data.question,
    )
    query_embedding = generate_embedding_for_api(retrieval_query)
    knowledge_context = retrieve_knowledge_for_api(db, query_embedding)
    similar_tickets = retrieve_similar_tickets_for_api(
        db,
        query_embedding,
        exclude_ticket_id=ticket.id,
    )

    if not knowledge_context and not similar_tickets:
        return TroubleshootingResponse(
            summary=(
                "Available evidence is limited. Review relevant application "
                "logs or escalate to the appropriate support team."
            ),
            troubleshooting_steps=[],
            possible_causes=[],
            escalation_recommended=True,
            confidence=0.0,
            sources=[],
            similar_incident_insights=[],
            similar_ticket_sources=[],
        )

    try:
        analysis = generate_support_copilot(
            ticket=ticket,
            question=request_data.question,
            knowledge_context=knowledge_context,
            similar_tickets=similar_tickets,
        )
    except CopilotServiceUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Support Copilot service is temporarily unavailable",
        ) from error
    except CopilotServiceResponseError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider returned invalid Support Copilot output",
        ) from error

    knowledge_sources = [
        KnowledgeSource(
            article_id=item.article_id,
            article_title=item.article_title,
            chunk_id=item.chunk_id,
            source_name=item.source_name,
            cosine_distance=item.cosine_distance,
        )
        for item in knowledge_context
    ]
    similar_ticket_sources = [
        SimilarTicketSource(
            ticket_id=item.ticket_id,
            ticket_title=item.title,
            cosine_distance=item.cosine_distance,
        )
        for item in similar_tickets
    ]
    return TroubleshootingResponse(
        summary=analysis.summary,
        troubleshooting_steps=analysis.troubleshooting_steps,
        possible_causes=analysis.possible_causes,
        escalation_recommended=analysis.escalation_recommended,
        confidence=analysis.confidence,
        sources=knowledge_sources,
        similar_incident_insights=analysis.similar_incident_insights,
        similar_ticket_sources=similar_ticket_sources,
    )


@router.post(
    "/{ticket_id}/embedding",
    response_model=TicketEmbeddingResponse,
)
def create_ticket_embedding(
    ticket_id: int,
    _: UserModel = Depends(
        require_roles(UserRole.SUPPORT_ENGINEER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> TicketEmbeddingResponse:
    ticket = db.get(TicketModel, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    if ticket.status not in HISTORICAL_TICKET_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only resolved or closed tickets can be embedded",
        )

    if not ticket.resolution or not ticket.resolution.strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A resolution is required before embedding a ticket",
        )

    embedding_text = build_ticket_embedding_text(
        title=ticket.title,
        description=ticket.description,
        resolution=ticket.resolution,
    )
    ticket.embedding = generate_embedding_for_api(embedding_text)
    ticket.embedding_model = OPENAI_EMBEDDING_MODEL
    ticket.embedding_updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store ticket embedding",
        ) from error

    return TicketEmbeddingResponse(
        ticket_id=ticket.id,
        embedding_model=ticket.embedding_model,
        embedding_updated_at=ticket.embedding_updated_at,
    )


@router.get(
    "/{ticket_id}/similar",
    response_model=list[SimilarTicketResponse],
)
def get_similar_tickets(
    ticket_id: int,
    _: UserModel = Depends(
        require_roles(UserRole.SUPPORT_ENGINEER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> list[SimilarTicketResponse]:
    ticket = db.get(TicketModel, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    query_text = build_ticket_embedding_text(
        title=ticket.title,
        description=ticket.description,
        resolution=ticket.resolution,
    )
    query_embedding = generate_embedding_for_api(query_text)
    matches = retrieve_similar_tickets_for_api(
        db,
        query_embedding,
        exclude_ticket_id=ticket.id,
    )

    return [
        SimilarTicketResponse(
            id=historical_ticket.ticket_id,
            title=historical_ticket.title,
            description=historical_ticket.description,
            resolution=historical_ticket.resolution,
            status=historical_ticket.status,
            cosine_distance=historical_ticket.cosine_distance,
        )
        for historical_ticket in matches
    ]


@router.patch("/{ticket_id}", response_model=TicketResponse)
def update_ticket(
    ticket_id: int,
    ticket_data: TicketUpdate,
    _: UserModel = Depends(
        require_roles(UserRole.SUPPORT_ENGINEER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> TicketModel:
    ticket = db.get(TicketModel, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    update_fields = ticket_data.model_dump(exclude_unset=True, mode="json")
    for field_name, value in update_fields.items():
        setattr(ticket, field_name, value)

    searchable_fields = {"title", "description", "resolution"}
    if searchable_fields.intersection(update_fields):
        ticket.embedding = None
        ticket.embedding_model = None
        ticket.embedding_updated_at = None

    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not update ticket",
        ) from error

    db.refresh(ticket)
    return ticket


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_ticket(
    ticket_id: int,
    _: UserModel = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> Response:
    ticket = db.get(TicketModel, ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    try:
        db.delete(ticket)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete ticket",
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
