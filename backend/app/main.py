from __future__ import annotations

from contextlib import asynccontextmanager
import re
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import admin, auth, catalog, documents, qa
from app.core.config import get_settings, validate_runtime_settings
from app.core.request_context import reset_request_id, set_request_id
from app.database import SessionLocal, init_db
from app.seed import seed_database
from app.services.graph import graph_service
from app.services.llm import llm_gateway


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_runtime_settings(settings)
    init_db()
    seed_database(include_demo=settings.seed_demo_data)
    yield
    graph_service.close()


settings = get_settings()
app = FastAPI(
    title="机床售后技术支持工作台 API",
    version="0.2.0",
    description="面向数控机床售后团队的知识协同与故障辅助工作台",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.app_env != "production" else None,
    openapi_url="/api/openapi.json" if settings.app_env != "production" else None,
)

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else uuid4().hex
    token = set_request_id(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        reset_request_id(token)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

prefix = "/api/v1"
app.include_router(auth.router, prefix=prefix)
app.include_router(catalog.router, prefix=prefix)
app.include_router(documents.router, prefix=prefix)
app.include_router(qa.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)


def _database_ready() -> bool:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


@app.get(f"{prefix}/health/live", tags=["系统"])
def liveness():
    return {"status": "ok"}


@app.get(f"{prefix}/health/ready", tags=["系统"])
def readiness(response: Response):
    database_ok = _database_ready()
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if database_ok else "not_ready", "database": database_ok}


@app.get(f"{prefix}/health", tags=["系统"])
def health():
    database_ok = _database_ready()
    llm = llm_gateway.status()
    return {
        "status": "ok" if database_ok else "degraded",
        "database": database_ok,
        "neo4j": graph_service.health(),
        "llm_configured": llm.configured,
        "llm_model": llm.model or None,
        "safety_mode": "engineer_confirmation_required",
    }
