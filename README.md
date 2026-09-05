# ResolveAI: AI-Powered IT Support Copilot

ResolveAI is a FastAPI backend that helps IT support engineers analyze tickets, find relevant historical incidents and knowledge-base evidence, generate grounded troubleshooting recommendations, and draft resolution notes and customer emails.

AI output is advisory. Engineers review the evidence and drafts before taking action. This portfolio MVP uses synthetic support data and does not automatically close tickets, assign engineers, execute commands, or send email.

## Features

- Ticket creation, retrieval, update, and deletion
- JWT authentication with Argon2 password hashing
- Role-based access control for employees, support engineers, and admins
- Employee ticket ownership and access restrictions
- Structured AI ticket analysis with OpenAI
- PostgreSQL and pgvector embeddings
- Similar resolved-ticket retrieval
- Knowledge-base chunking and deterministic RAG retrieval
- Grounded troubleshooting recommendations with database-backed sources
- Draft resolution notes and customer emails
- Interactive Swagger documentation

## Technology

- Python 3.10+
- FastAPI and Uvicorn
- PostgreSQL with pgvector
- SQLAlchemy and Alembic
- Pydantic v2
- OpenAI SDK
- PyJWT and pwdlib with Argon2
- Docker Compose

## API

Start the application and open `http://127.0.0.1:8000/docs` for interactive documentation.

| Method | Endpoint | Access |
| --- | --- | --- |
| GET | `/` | Public health check |
| POST | `/api/v1/auth/register` | Public |
| POST | `/api/v1/auth/login` | Public |
| GET | `/api/v1/auth/me` | Authenticated |
| POST | `/api/v1/tickets` | Authenticated |
| GET | `/api/v1/tickets` | Authenticated |
| GET | `/api/v1/tickets/{ticket_id}` | Authenticated |
| PATCH | `/api/v1/tickets/{ticket_id}` | Support engineer, admin |
| DELETE | `/api/v1/tickets/{ticket_id}` | Admin |
| POST | `/api/v1/tickets/{ticket_id}/ai/analyze` | Support engineer, admin |
| GET | `/api/v1/tickets/{ticket_id}/similar` | Support engineer, admin |
| POST | `/api/v1/tickets/{ticket_id}/ai/troubleshoot` | Support engineer, admin |
| POST | `/api/v1/tickets/{ticket_id}/ai/resolution-draft` | Support engineer, admin |
| POST | `/api/v1/tickets/{ticket_id}/ai/email-draft` | Support engineer, admin |

## Local Setup

Requirements:

- Python 3.10 or later
- Docker Desktop
- An OpenAI API key

Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with a local database password, a long JWT secret, and your OpenAI API key. Then start PostgreSQL, apply migrations, seed the synthetic data, and run the API:

```powershell
docker compose up -d
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_resolved_tickets
.\.venv\Scripts\python.exe -m scripts.seed_knowledge_base
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

The seed scripts are idempotent and skip unchanged records.

## Project Structure

```text
app/
  main.py              FastAPI application
  auth.py              Password hashing and JWT authentication
  authorization.py     Role-based access dependencies
  auth_routes.py       Registration, login, and current-user routes
  ticket_routes.py     Ticket and AI endpoints
  models.py            SQLAlchemy models
  schemas.py           Pydantic request and response schemas
  ai/                  Analysis, embeddings, retrieval, copilot, and drafts
alembic/                Database migrations
scripts/                Synthetic data seed scripts
compose.yaml            PostgreSQL and pgvector service
requirements.txt        Python dependencies
```

## AI Safety

- AI recommendations do not change ticket status, assignment, or priority.
- Retrieval sources come from database records rather than model-generated IDs.
- Weak retrieval is filtered by similarity thresholds.
- Resolution drafts require engineer-supplied work details.
- Customer emails are drafts only and are never sent by the application.

## Limitations

- No frontend UI
- No automated test suite
- No background workers or task queue
- No SSO, ServiceNow, Microsoft Copilot, or Outlook integration
- OpenAI API access is required for analysis, embeddings, and drafts

## License

This is a personal portfolio and learning project. Use synthetic data only. Do not load proprietary tickets or confidential documentation.
