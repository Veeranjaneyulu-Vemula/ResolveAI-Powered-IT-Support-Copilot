from openai import (
    APIConnectionError,
    APIError,
    APIResponseValidationError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)
from pydantic import ValidationError

from app.ai.prompts import (
    COPILOT_SYSTEM_INSTRUCTIONS,
    build_support_copilot_prompt,
)
from app.ai.retrieval import RetrievedKnowledge
from app.ai.similar_tickets import RetrievedSimilarTicket
from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.models import Ticket
from app.schemas import SupportCopilotAnalysis


class CopilotServiceUnavailableError(Exception):
    pass


class CopilotServiceResponseError(Exception):
    pass


def generate_support_copilot(
    *,
    ticket: Ticket,
    question: str | None,
    knowledge_context: list[RetrievedKnowledge],
    similar_tickets: list[RetrievedSimilarTicket],
) -> SupportCopilotAnalysis:
    if not OPENAI_API_KEY:
        raise CopilotServiceUnavailableError(
            "OpenAI API key is not configured"
        )

    if not knowledge_context and not similar_tickets:
        raise CopilotServiceResponseError(
            "Support Copilot requires retrieved evidence"
        )

    knowledge_input = [
        {
            "article_id": item.article_id,
            "article_title": item.article_title,
            "chunk_id": item.chunk_id,
            "content": item.content,
        }
        for item in knowledge_context
    ]
    incident_input = [
        {
            "ticket_id": item.ticket_id,
            "title": item.title,
            "description": item.description,
            "resolution": item.resolution,
        }
        for item in similar_tickets
    ]
    prompt = build_support_copilot_prompt(
        ticket_title=ticket.title,
        ticket_description=ticket.description,
        ticket_status=ticket.status,
        question=question,
        knowledge_context=knowledge_input,
        similar_incidents=incident_input,
    )

    try:
        client = OpenAI(api_key=OPENAI_API_KEY, max_retries=1)
        response = client.responses.parse(
            model=OPENAI_MODEL,
            instructions=COPILOT_SYSTEM_INSTRUCTIONS,
            input=prompt,
            text_format=SupportCopilotAnalysis,
            temperature=0.1,
            max_output_tokens=1200,
            store=False,
            timeout=30.0,
        )
    except (APITimeoutError, APIConnectionError, RateLimitError) as error:
        raise CopilotServiceUnavailableError(
            "OpenAI is temporarily unavailable"
        ) from error
    except (APIResponseValidationError, ValidationError) as error:
        raise CopilotServiceResponseError(
            "OpenAI returned an invalid Support Copilot response"
        ) from error
    except APIError as error:
        raise CopilotServiceUnavailableError(
            "OpenAI Support Copilot request could not be completed"
        ) from error

    if response.output_parsed is None:
        raise CopilotServiceResponseError(
            "OpenAI did not return structured Support Copilot output"
        )

    return response.output_parsed
