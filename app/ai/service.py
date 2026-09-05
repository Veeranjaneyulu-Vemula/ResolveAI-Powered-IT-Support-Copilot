from openai import (
    APIConnectionError,
    APIError,
    APIResponseValidationError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)
from pydantic import ValidationError

from app.ai.prompts import SYSTEM_INSTRUCTIONS, build_ticket_analysis_prompt
from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.models import Ticket
from app.schemas import TicketAIAnalysis


class AIServiceUnavailableError(Exception):
    pass


class AIServiceResponseError(Exception):
    pass


def analyze_ticket(ticket: Ticket) -> TicketAIAnalysis:
    if not OPENAI_API_KEY:
        raise AIServiceUnavailableError("OpenAI API key is not configured")

    prompt = build_ticket_analysis_prompt(
        title=ticket.title,
        description=ticket.description,
        status=ticket.status,
    )

    try:
        client = OpenAI(api_key=OPENAI_API_KEY, max_retries=1)
        response = client.responses.parse(
            model=OPENAI_MODEL,
            instructions=SYSTEM_INSTRUCTIONS,
            input=prompt,
            text_format=TicketAIAnalysis,
            temperature=0.2,
            max_output_tokens=600,
            store=False,
            timeout=30.0,
        )
    except (APITimeoutError, APIConnectionError, RateLimitError) as error:
        raise AIServiceUnavailableError(
            "OpenAI is temporarily unavailable"
        ) from error
    except (APIResponseValidationError, ValidationError) as error:
        raise AIServiceResponseError(
            "OpenAI returned an invalid structured response"
        ) from error
    except APIError as error:
        raise AIServiceUnavailableError(
            "OpenAI request could not be completed"
        ) from error

    if response.output_parsed is None:
        raise AIServiceResponseError(
            "OpenAI did not return a structured analysis"
        )

    return response.output_parsed
