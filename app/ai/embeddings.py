import math

from openai import (
    APIConnectionError,
    APIError,
    APIResponseValidationError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from app.config import (
    OPENAI_API_KEY,
    OPENAI_EMBEDDING_DIMENSIONS,
    OPENAI_EMBEDDING_MODEL,
)


class EmbeddingServiceUnavailableError(Exception):
    pass


class EmbeddingServiceResponseError(Exception):
    pass


def generate_embedding(text: str) -> list[float]:
    if not OPENAI_API_KEY:
        raise EmbeddingServiceUnavailableError(
            "OpenAI API key is not configured"
        )

    clean_text = text.strip()
    if not clean_text:
        raise EmbeddingServiceResponseError("Embedding text cannot be empty")

    try:
        client = OpenAI(api_key=OPENAI_API_KEY, max_retries=1)
        response = client.embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,
            input=clean_text,
            dimensions=OPENAI_EMBEDDING_DIMENSIONS,
            encoding_format="float",
            timeout=30.0,
        )
    except (APITimeoutError, APIConnectionError, RateLimitError) as error:
        raise EmbeddingServiceUnavailableError(
            "OpenAI embeddings are temporarily unavailable"
        ) from error
    except APIResponseValidationError as error:
        raise EmbeddingServiceResponseError(
            "OpenAI returned an invalid embedding response"
        ) from error
    except APIError as error:
        raise EmbeddingServiceUnavailableError(
            "OpenAI embedding request could not be completed"
        ) from error

    if not response.data:
        raise EmbeddingServiceResponseError(
            "OpenAI did not return an embedding"
        )

    embedding = list(response.data[0].embedding)
    if len(embedding) != OPENAI_EMBEDDING_DIMENSIONS:
        raise EmbeddingServiceResponseError(
            "OpenAI returned an embedding with an unexpected dimension"
        )

    if not all(math.isfinite(value) for value in embedding):
        raise EmbeddingServiceResponseError(
            "OpenAI returned an invalid embedding vector"
        )

    return embedding
