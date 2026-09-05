from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.enums import UserRole


class TicketStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketAICategory(str, Enum):
    AUTHENTICATION = "Authentication"
    VPN_NETWORK = "VPN / Network"
    MICROSOFT_365 = "Microsoft 365"
    HARDWARE = "Hardware"
    PRINTER = "Printer"
    APPLICATION_SUPPORT = "Application Support"
    CLAIMS_APPLICATION = "Claims Application"
    POLICY_APPLICATION = "Policy Application"
    ACCESS_REQUEST = "Access Request"
    OTHER = "Other"


class TicketAIPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TicketCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={
            "example": {
                "title": "VPN authentication failure",
                "description": (
                    "User cannot connect to VPN after changing their "
                    "corporate password."
                ),
            }
        }
    )


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    resolution: str | None = Field(default=None, min_length=1)
    status: TicketStatus | None = None

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={"example": {"status": "IN_PROGRESS"}},
    )

    @model_validator(mode="after")
    def validate_update_fields(self) -> "TicketUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")

        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")

        return self


class TicketResponse(BaseModel):
    id: int
    requester_id: int
    title: str
    description: str
    resolution: str | None
    status: TicketStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    password: str = Field(min_length=12, max_length=128)

    model_config = ConfigDict(extra="forbid")

    @field_validator("email", "username", mode="before")
    @classmethod
    def strip_identity_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    is_active: bool
    role: UserRole
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1)
    password: str = Field(min_length=1, max_length=128)

    model_config = ConfigDict(extra="forbid")

    @field_validator("identifier", mode="before")
    @classmethod
    def strip_identifier(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int


class TicketAIAnalysis(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    category: TicketAICategory
    priority: TicketAIPriority
    suggested_team: str = Field(min_length=1, max_length=100)
    key_issue: str = Field(min_length=1, max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale_summary: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid")


class TicketEmbeddingResponse(BaseModel):
    ticket_id: int
    embedding_model: str
    embedding_updated_at: datetime


class SimilarTicketResponse(BaseModel):
    id: int
    title: str
    description: str
    resolution: str
    status: TicketStatus
    cosine_distance: float


class TroubleshootRequest(BaseModel):
    question: str | None = Field(default=None, min_length=1, max_length=1000)

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class KnowledgeSource(BaseModel):
    article_id: int
    article_title: str
    chunk_id: int
    source_name: str
    cosine_distance: float


class SimilarTicketSource(BaseModel):
    ticket_id: int
    ticket_title: str
    cosine_distance: float


class SupportCopilotAnalysis(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    troubleshooting_steps: list[str] = Field(min_length=1, max_length=8)
    possible_causes: list[str] = Field(max_length=5)
    escalation_recommended: bool
    confidence: float = Field(ge=0.0, le=1.0)
    similar_incident_insights: list[str] = Field(max_length=5)

    model_config = ConfigDict(extra="forbid")


class TroubleshootingResponse(BaseModel):
    summary: str
    troubleshooting_steps: list[str]
    possible_causes: list[str]
    escalation_recommended: bool
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[KnowledgeSource]
    similar_incident_insights: list[str] = Field(default_factory=list)
    similar_ticket_sources: list[SimilarTicketSource] = Field(
        default_factory=list
    )


ResolutionFact = Annotated[str, Field(min_length=1, max_length=500)]


class ResolutionDraftRequest(BaseModel):
    work_performed: list[ResolutionFact] = Field(min_length=1, max_length=20)
    confirmed_cause: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    validation_performed: list[ResolutionFact] | None = Field(
        default=None,
        max_length=10,
    )
    additional_notes: str | None = Field(
        default=None,
        min_length=1,
        max_length=1000,
    )

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ResolutionDraftResponse(BaseModel):
    issue_summary: str = Field(min_length=1, max_length=500)
    root_cause: str = Field(min_length=1, max_length=500)
    actions_taken: list[str] = Field(min_length=1, max_length=20)
    validation_summary: str = Field(min_length=1, max_length=1000)
    final_resolution: str = Field(min_length=1, max_length=1000)
    follow_up_required: bool

    model_config = ConfigDict(extra="forbid")


class CustomerEmailDraftResponse(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=3000)

    model_config = ConfigDict(extra="forbid")
