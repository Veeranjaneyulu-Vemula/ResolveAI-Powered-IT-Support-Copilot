from fastapi import FastAPI

from app.auth_routes import router as auth_router
from app.ticket_routes import router as ticket_router


app = FastAPI(
    title="ResolveAI Lite API",
    description="A simple API for learning the ResolveAI ticket flow.",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(ticket_router)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "ResolveAI Lite API"}
