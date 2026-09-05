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
    EMAIL_DRAFT_SYSTEM_INSTRUCTIONS,
    RESOLUTION_DRAFT_SYSTEM_INSTRUCTIONS,
    build_customer_email_draft_prompt,
    build_resolution_draft_prompt,
)
from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.models import Ticket
from app.schemas import (
    CustomerEmailDraftResponse,
    ResolutionDraftRequest,
    ResolutionDraftResponse,
)


class DraftServiceUnavailableError(Exception):
    pass


class DraftServiceResponseError(Exception):
    pass


def generate_resolution_draft(
    *,
    ticket: Ticket,
    evidence: ResolutionDraftRequest,
) -> ResolutionDraftResponse:
    if not OPENAI_API_KEY:
        raise DraftServiceUnavailableError("OpenAI API key is not configured")

    validation_performed = evidence.validation_performed or []
    prompt = build_resolution_draft_prompt(
        ticket_title=ticket.title,
        ticket_description=ticket.description,
        work_performed=evidence.work_performed,
        confirmed_cause=evidence.confirmed_cause,
        validation_performed=validation_performed,
        additional_notes=evidence.additional_notes,
    )

    try:
        client = OpenAI(api_key=OPENAI_API_KEY, max_retries=1)
        response = client.responses.parse(
            model=OPENAI_MODEL,
            instructions=RESOLUTION_DRAFT_SYSTEM_INSTRUCTIONS,
            input=prompt,
            text_format=ResolutionDraftResponse,
            temperature=0.1,
            max_output_tokens=900,
            store=False,
            timeout=30.0,
        )
    except (APITimeoutError, APIConnectionError, RateLimitError) as error:
        raise DraftServiceUnavailableError(
            "OpenAI is temporarily unavailable"
        ) from error
    except (APIResponseValidationError, ValidationError) as error:
        raise DraftServiceResponseError(
            "OpenAI returned an invalid resolution draft"
        ) from error
    except APIError as error:
        raise DraftServiceUnavailableError(
            "OpenAI resolution draft request could not be completed"
        ) from error

    if response.output_parsed is None:
        raise DraftServiceResponseError(
            "OpenAI did not return a structured resolution draft"
        )

    draft = response.output_parsed
    draft.actions_taken = list(evidence.work_performed)

    draft.root_cause = (
        evidence.confirmed_cause
        if evidence.confirmed_cause is not None
        else "Root cause not confirmed"
    )

    if validation_performed:
        draft.validation_summary = "; ".join(validation_performed)
    else:
        draft.validation_summary = "Validation not provided"
        draft.final_resolution = (
            "The documented work was performed, but successful resolution "
            "has not been validated."
        )
        draft.follow_up_required = True

    return draft


def generate_customer_email_draft(
    *,
    ticket: Ticket,
    evidence: ResolutionDraftRequest,
) -> CustomerEmailDraftResponse:
    if not OPENAI_API_KEY:
        raise DraftServiceUnavailableError("OpenAI API key is not configured")

    validation_performed = evidence.validation_performed or []
    prompt = build_customer_email_draft_prompt(
        ticket_title=ticket.title,
        ticket_description=ticket.description,
        work_performed=evidence.work_performed,
        confirmed_cause=evidence.confirmed_cause,
        validation_performed=validation_performed,
        additional_notes=evidence.additional_notes,
    )

    try:
        client = OpenAI(api_key=OPENAI_API_KEY, max_retries=1)
        response = client.responses.parse(
            model=OPENAI_MODEL,
            instructions=EMAIL_DRAFT_SYSTEM_INSTRUCTIONS,
            input=prompt,
            text_format=CustomerEmailDraftResponse,
            temperature=0.2,
            max_output_tokens=700,
            store=False,
            timeout=30.0,
        )
    except (APITimeoutError, APIConnectionError, RateLimitError) as error:
        raise DraftServiceUnavailableError(
            "OpenAI is temporarily unavailable"
        ) from error
    except (APIResponseValidationError, ValidationError) as error:
        raise DraftServiceResponseError(
            "OpenAI returned an invalid customer email draft"
        ) from error
    except APIError as error:
        raise DraftServiceUnavailableError(
            "OpenAI email draft request could not be completed"
        ) from error

    if response.output_parsed is None:
        raise DraftServiceResponseError(
            "OpenAI did not return a structured customer email draft"
        )

    draft = response.output_parsed
    if not validation_performed:
        draft.body = (
            f"{draft.body.rstrip()}\n\n"
            "Please note: successful resolution has not yet been verified."
        )

    return draft
