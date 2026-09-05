import os

from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable is not set")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

try:
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )
except ValueError as error:
    raise RuntimeError(
        "JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be an integer"
    ) from error

if JWT_ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
    raise RuntimeError("JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be positive")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv(
    "OPENAI_EMBEDDING_MODEL",
    "text-embedding-3-small",
)
OPENAI_EMBEDDING_DIMENSIONS = 1536
