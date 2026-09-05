# ResolveAI

ResolveAI is an AI-assisted IT support copilot that helps engineers understand tickets, retrieve similar historical incidents and knowledge-base evidence, generate grounded troubleshooting recommendations, and draft resolution notes and customer emails.

It does not replace support engineers. Recommendations remain advisory. Engineers investigate, decide, and close tickets.

---

## Overview

Enterprise IT support engineers receive tickets for VPN failures, authentication problems, Outlook issues, application errors, and printer or network problems. Engineers already know how to troubleshoot. The cost is time spent:

- reading long ticket descriptions
- searching historical incidents
- searching knowledge-base documentation
- writing resolution notes
- drafting repetitive customer communication

ResolveAI reduces that search and documentation time. It retrieves evidence first, then generates grounded suggestions. A human reviews every AI output before any ticket update, assignment, or customer message.

This repository is a backend MVP. It uses synthetic IT support data only. It is not a production support platform.

---

## Problem Statement

Support work is slow for reasons that are not usually technical skill:

1. Tickets are written in different language than historical records.
2. Useful resolutions exist in past tickets, but keyword search misses them.
3. Knowledge articles are long, and the relevant section is easy to miss.
4. After a fix, engineers still spend time writing internal notes and customer emails.

ResolveAI assists by:

- summarizing and classifying a ticket
- retrieving semantically similar resolved tickets
- retrieving relevant knowledge-base chunks
- generating troubleshooting steps from retrieved evidence
- drafting resolution notes and customer emails from engineer-supplied facts

The engineer remains responsible for the final action.

---

## Key Features

Implemented in the current codebase:

- Ticket create, read, update, and delete
- JWT Bearer authentication
- Role-based access control: `EMPLOYEE`, `SUPPORT_ENGINEER`, `ADMIN`
- Ticket ownership for employees
- Structured AI ticket analysis
- OpenAI embeddings stored in PostgreSQL with pgvector
- Similar resolved-ticket search
- Synthetic knowledge base with chunking
- Deterministic RAG retrieval over knowledge chunks
- Support Copilot that combines ticket context, similar incidents, and KB evidence
- Database-backed source attribution
- AI resolution-note drafts
- AI customer-email drafts
- Interactive Swagger/OpenAPI documentation

Not implemented:

- frontend UI
- Redis, Celery, or background workers
- LangChain, LangGraph, or multi-agent frameworks
- SSO / Microsoft Copilot / ServiceNow / Outlook sending
- automated ticket closure or command execution
- automated test suite

---

## End-to-End Workflow

```text
Employee or Support Engineer
  → creates a support ticket
Support Engineer
  → opens the ticket
  → AI analysis (summary, category, priority recommendation)
  → similar historical incidents
  → knowledge-base retrieval
  → grounded Support Copilot recommendation
  → investigates and performs the work
  → supplies actual work performed
  → AI resolution-note draft
  → AI customer-email draft
  → reviews and edits
  → manually updates or closes the ticket
```

AI never closes the ticket, assigns an engineer, or sends email.

---

## Technology Stack

| Layer | Technology | How ResolveAI uses it |
| --- | --- | --- |
| Language | Python | Backend application language |
| API | FastAPI + Uvicorn | REST API, dependency injection, Swagger UI |
| Validation | Pydantic v2 | Request/response schemas and structured LLM output |
| Database | PostgreSQL 18 | Persistence for users, tickets, KB articles, and vectors |
| ORM | SQLAlchemy 2.x | Models, sessions, queries |
| Driver | psycopg | PostgreSQL connectivity |
| Migrations | Alembic | Schema versioning; runtime `create_all()` is not used |
| Auth | PyJWT + HTTP Bearer | Access tokens with `sub` and `exp` |
| Password hashing | pwdlib (Argon2) | Store password hashes, never plaintext |
| Authorization | FastAPI role dependencies | Endpoint RBAC |
| LLM | Official OpenAI Python SDK | Structured analysis, Copilot generation, drafts |
| Embeddings | OpenAI `text-embedding-3-small` | 1536-dimension vectors |
| Vector search | pgvector | Cosine-distance nearest-neighbor search |
| Config | python-dotenv | Environment-based secrets and settings |
| Local database | Docker Compose | PostgreSQL image with pgvector preinstalled |

---

## Architecture

```text
Client / Swagger UI
        │
        ▼
   FastAPI (app/main.py)
        │
        ├── /api/v1/auth/*     auth_routes.py
        └── /api/v1/tickets/*  ticket_routes.py
                │
                ├── JWT Bearer  →  get_current_user()
                └── RBAC        →  require_roles()
                        │
                        ▼
        ┌───────────────┴────────────────┐
        │                                │
        ▼                                ▼
 PostgreSQL + pgvector              OpenAI API
 SQLAlchemy / Alembic               LLM + embeddings
 users, tickets,                    gpt-4o-mini
 knowledge_articles,                text-embedding-3-small
 knowledge_chunks
```

ResolveAI is a modular monolith. There is one FastAPI process and one PostgreSQL database. There is no microservice split and no separate vector database.

---

## AI Architecture

### Ticket analysis

```text
Ticket title + description
  → OpenAI Responses structured parse
  → Pydantic TicketAIAnalysis
  → returned to the caller
```

The ticket record is not modified. Analysis is not persisted.

### Similar incident search

```text
Current ticket title, description, and resolution (if present)
  → embedding model
  → query vector
  → pgvector cosine distance on tickets.embedding
  → top 3 RESOLVED/CLOSED tickets that already have a resolution and a matching embedding model
```

Lower cosine distance means greater similarity.

### Knowledge-base RAG

```text
Knowledge article
  → 120-word chunks with 20-word overlap
  → embedding
  → knowledge_chunks.embedding

Query
  → embedding
  → cosine-distance search, max 0.55
  → up to 4 article-diverse chunks
```

### Support Copilot

```text
Current ticket + optional question
  → one query embedding
  → similar historical tickets
  → KB chunks
  → OpenAI structured Copilot output
  → KB sources and incident sources from PostgreSQL
```

If neither retrieval path returns useful evidence, OpenAI is not called.

### Resolution and email drafts

```text
Engineer-supplied facts
  + ticket title/description
  → OpenAI structured draft
  → application-level safety overrides
  → draft returned only
```

Drafts are not saved and do not change ticket status.

---

## RAG Pipeline

Ingestion:

```text
KnowledgeArticle
  → chunk_text() + article title/category context
  → generate_embedding()
  → KnowledgeChunk stored in PostgreSQL
```

Query:

```text
Ticket / optional question
  → query embedding
  → retrieve_knowledge_by_embedding()
  → cosine_distance <= 0.55
  → top_k = 4, one chunk per article
  → retrieved text added to the prompt
  → OpenAI generates troubleshooting
  → sources built from retrieved rows, not from model text
```

This is retrieval-augmented generation. It does not train or fine-tune the model.

---

## Database Design

```text
users
  id
  email (unique)
  username (unique)
  hashed_password
  is_active
  role          EMPLOYEE | SUPPORT_ENGINEER | ADMIN
  created_at

tickets
  id
  requester_id ──► users.id
  title
  description
  resolution
  status        OPEN | IN_PROGRESS | RESOLVED | CLOSED
  embedding     vector(1536)
  embedding_model
  embedding_updated_at
  created_at

knowledge_articles
  id
  title
  content
  category
  source_name
  created_at
  updated_at

knowledge_chunks
  id
  article_id ──► knowledge_articles.id  (CASCADE)
  chunk_index
  content
  embedding     vector(1536)
  embedding_model
  created_at
```

Relationships:

```text
User 1 ─── many Tickets

KnowledgeArticle 1 ─── many KnowledgeChunks
```

---

## Authentication and Authorization

```text
Register
  → hash password with Argon2
  → store user with default role EMPLOYEE

Login
  → find user by email or username
  → verify password against stored hash
  → return JWT access token

Protected request
  → Authorization: Bearer <token>
  → decode and verify signature/expiration
  → load user from PostgreSQL
  → require_roles() for privileged actions
```

Authentication answers “who is this user?” Authorization answers “may this role perform this action?”

A valid JWT is not a permission grant. Role checks run on the backend.

MVP policy:

| Action | EMPLOYEE | SUPPORT_ENGINEER | ADMIN |
| --- | --- | --- | --- |
| Register / login / `/me` | yes | yes | yes |
| Create ticket | yes | yes | yes |
| List/view tickets | own tickets | all | all |
| Update ticket | no | yes | yes |
| Delete ticket | no | no | yes |
| AI analysis / Copilot / drafts / similar search | no | yes | yes |

Public registration cannot choose `ADMIN`.

---

## API Endpoints

### Health

| Method | Path | Auth |
| --- | --- | --- |
| GET | `/` | Public |

### Authentication

| Method | Path | Auth |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Public |
| POST | `/api/v1/auth/login` | Public |
| GET | `/api/v1/auth/me` | Bearer |

### Tickets

| Method | Path | Auth |
| --- | --- | --- |
| POST | `/api/v1/tickets` | EMPLOYEE, SUPPORT_ENGINEER, ADMIN |
| GET | `/api/v1/tickets` | Authenticated; employees see own tickets |
| GET | `/api/v1/tickets/{ticket_id}` | Authenticated; ownership enforced for employees |
| PATCH | `/api/v1/tickets/{ticket_id}` | SUPPORT_ENGINEER, ADMIN |
| DELETE | `/api/v1/tickets/{ticket_id}` | ADMIN |

### AI and retrieval

| Method | Path | Auth |
| --- | --- | --- |
| POST | `/api/v1/tickets/{ticket_id}/ai/analyze` | SUPPORT_ENGINEER, ADMIN |
| POST | `/api/v1/tickets/{ticket_id}/embedding` | SUPPORT_ENGINEER, ADMIN; ticket must be RESOLVED/CLOSED with a resolution |
| GET | `/api/v1/tickets/{ticket_id}/similar` | SUPPORT_ENGINEER, ADMIN |
| POST | `/api/v1/tickets/{ticket_id}/ai/troubleshoot` | SUPPORT_ENGINEER, ADMIN |
| POST | `/api/v1/tickets/{ticket_id}/ai/resolution-draft` | SUPPORT_ENGINEER, ADMIN |
| POST | `/api/v1/tickets/{ticket_id}/ai/email-draft` | SUPPORT_ENGINEER, ADMIN |

Interactive docs: `http://127.0.0.1:8000/docs`

---

## Project Structure

```text
ResolveAI-Enterprise AI Support Copilot/
├── app/
│   ├── main.py                 FastAPI app, router includes, health check
│   ├── config.py               Environment configuration
│   ├── database.py             Engine, session factory, get_db()
│   ├── models.py               SQLAlchemy User, Ticket, KB models
│   ├── schemas.py              Pydantic request/response contracts
│   ├── enums.py                UserRole
│   ├── auth.py                 Password hashing, JWT, get_current_user
│   ├── authorization.py        require_roles()
│   ├── auth_routes.py          Register, login, /me
│   ├── ticket_routes.py        Ticket CRUD and AI endpoints
│   └── ai/
│       ├── service.py          Structured ticket analysis
│       ├── prompts.py          System instructions and prompt builders
│       ├── embeddings.py       OpenAI embedding client
│       ├── embedding_text.py   Ticket/query text construction
│       ├── similar_tickets.py  Historical incident retrieval
│       ├── chunking.py         Word-based KB chunking
│       ├── retrieval.py        KB vector retrieval
│       ├── copilot.py          Support Copilot generation
│       └── drafts.py           Resolution and email drafts
├── alembic/
│   ├── env.py
│   └── versions/               Schema migrations
├── scripts/
│   ├── seed_resolved_tickets.py
│   └── seed_knowledge_base.py
├── compose.yaml                PostgreSQL + pgvector
├── alembic.ini
├── requirements.txt
└── .env.example
```

---

## Database Migrations

Alembic owns schema evolution. The application does not call `Base.metadata.create_all()`.

Applied revisions:

1. `1728ee81cbaf` — create tickets table
2. `6e28f857f8d9` — create users table
3. `92a1515994cb` — roles and ticket ownership
4. `eee693a449da` — enable pgvector; add ticket resolution and embeddings
5. `cf38a3fbc0d1` — knowledge articles and chunks

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

---

## AI Safety / Human-in-the-Loop

Safeguards present in code:

- AI recommendations do not update ticket status, assignment, or priority
- similar incidents are retrieved evidence, not confirmed root causes
- Copilot prompt distinguishes possible cause from confirmed root cause
- KB and incident sources are built from database rows, not model-invented IDs
- weak retrieval is filtered by cosine-distance thresholds
- if no useful evidence exists, Copilot skips the LLM call
- resolution drafts require engineer-supplied `work_performed`
- resolution drafts overwrite invented root cause with `"Root cause not confirmed"` unless the engineer supplied `confirmed_cause`
- missing validation cannot be rewritten as successful verification
- email drafts are returned, never sent, and append a verification disclaimer when validation is missing
- employees cannot call AI endpoints

---

## Running Locally

Requirements:

- Python 3.10 or later (`str | None` type hints)
- Docker Desktop for PostgreSQL
- an OpenAI API key

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with a local database password, JWT secret, and OpenAI API key. Do not wrap the API key in quotes.

```powershell
docker compose up -d
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_resolved_tickets
.\.venv\Scripts\python.exe -m scripts.seed_knowledge_base
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

Seed scripts are idempotent and skip unchanged records.

---

## Environment Variables

Names only:

```text
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
DATABASE_URL
JWT_SECRET_KEY
JWT_ALGORITHM
JWT_ACCESS_TOKEN_EXPIRE_MINUTES
OPENAI_API_KEY
OPENAI_MODEL
OPENAI_EMBEDDING_MODEL
```

`OPENAI_EMBEDDING_DIMENSIONS` is a code constant (`1536`), not an environment variable.

---

## Example Workflow

Synthetic ticket:

```text
Title: VPN stopped working after corporate password change
Description: User can log into Windows but VPN authentication fails
after their password was updated.
```

Expected behavior in this MVP:

1. Employee creates the ticket.
2. Support Engineer analyzes it. The model typically classifies a VPN/authentication issue and recommends a priority. The ticket is not changed.
3. Similar-ticket search returns historical VPN/password incidents, not printer tickets.
4. Support Copilot retrieves VPN/MFA/GlobalProtect knowledge chunks plus similar incidents, then returns troubleshooting steps and database-backed sources.
5. The engineer performs the work.
6. The engineer submits actual work performed, optional confirmed cause, and optional validation.
7. ResolveAI drafts internal notes and a customer email.
8. The engineer edits the drafts and manually updates the ticket.

---

## Testing

There is no project `tests/` directory and no pytest configuration.

Verification during development used FastAPI `TestClient`, live OpenAI calls, and PostgreSQL queries. Those checks are not checked into an automated suite.

---

## Design Decisions

| Decision | Reason |
| --- | --- |
| PostgreSQL + pgvector | Keep tickets, users, KB, and vectors in one database |
| Official OpenAI SDK | Keep the LLM/embedding path visible; no LangChain required |
| Deterministic retrieval before generation | The model cannot skip search or invent sources |
| Human-in-the-loop | AI assists; it does not close, assign, or email |
| Combined Copilot retrieval | One query embedding feeds both similar-ticket and KB search |
| Alembic migrations | Schema changes are reviewable and reversible |
| Modular monolith | FastAPI routers and AI modules, not microservices |
| Draft-only resolution/email output | Unreviewed LLM text is not stored as ticket truth |
| Synthetic data | Portfolio-safe IT examples; no production tickets |

---

## Current Limitations

- synthetic tickets and knowledge articles only
- no frontend
- no SSO or enterprise identity provider
- no real company knowledge-base connector
- no Outlook/ServiceNow/SharePoint integration
- no Redis/Celery job queue
- no production monitoring or audit log table
- no automated test suite
- no HNSW/IVF index; vector search is exact cosine distance
- unpinned `requirements.txt`
- Docker Compose runs PostgreSQL only; the API is not containerized
- Day 6 analysis results are not persisted

---

## Future Enhancements

These are not in the current stack:

- Redis / Celery
- SSO
- enterprise KB connectors
- Microsoft Copilot Studio integration
- audit logging
- monitoring
- frontend
- evaluation framework
- automatic email sending
- approved-draft persistence after human confirmation

---

## What I Learned

This project demonstrates:

- REST API design with FastAPI
- SQLAlchemy ORM and PostgreSQL persistence
- Alembic schema migrations
- JWT authentication and password hashing
- backend RBAC and ticket ownership
- LLM integration with structured Pydantic output
- embeddings and vector similarity search
- RAG with deterministic retrieval
- grounding and database-backed source attribution
- human-in-the-loop AI design
- evidence vs inference in resolution documentation

---

## Interview Discussion

Questions this project can support:

1. Why store vectors in PostgreSQL with pgvector instead of using a separate vector database?
2. How is an embedding different from an LLM completion?
3. What is cosine distance, and does a lower or higher value mean more similar?
4. Why must embedding dimension match the pgvector column?
5. How is similar-ticket search different from RAG?
6. Why does retrieval happen before generation?
7. How do you prevent the model from inventing source article IDs?
8. Why is RAG not the same as fine-tuning?
9. How does JWT authentication work, and why is the payload not secret?
10. What is the difference between authentication and authorization, and between 401 and 403?
11. Why use Alembic instead of `create_all()`?
12. Why should AI not automatically close a ticket or apply a historical resolution?
13. What is the difference between a possible cause and a confirmed root cause?
14. How would this architecture change if the knowledge base grew to millions of chunks?
15. What would you add before calling this production-ready?

---

## License

This is a personal portfolio/learning project. Use synthetic data only. Do not load proprietary company tickets or confidential documentation.
