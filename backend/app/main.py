"""ProjectVerse AI API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth_routes import router as auth_router
from app.api.routes import router
from app.auth import bootstrap_admin
from app.config import get_settings
from app.db import get_engine
from app.models import Base, SimulationRun

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("projectverse")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    engine = get_engine()
    configuration_error = settings.production_configuration_error()
    if configuration_error:
        logger.error("%s Project routes will reject requests until this is fixed.", configuration_error)
    if not settings.is_production:
        Base.metadata.create_all(bind=engine)
    from app.db import get_sessionmaker

    session = get_sessionmaker()()
    try:
        interrupted = (
            session.query(SimulationRun)
            .filter(SimulationRun.status.in_(["queued", "running"]))
            .all()
        )
        for run in interrupted:
            run.status = "failed"
            run.error_message = "Interrupted by process restart."
        session.commit()
        bootstrap_admin(session, settings)
    finally:
        session.close()
    yield


app = FastAPI(
    title="ProjectVerse AI",
    version="1.0.0",
    description=(
        "Natural-language project planning, deterministic scheduling, cost modeling, "
        "seeded Monte Carlo simulation, and conceptual 3D scene parameters. "
        "Results are planning-model outputs, not quotations or engineering certifications."
    ),
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(auth_router)

settings = get_settings()
_cors_origins = [origin for origin in settings.cors_origin_list if origin != "*"]
if not settings.is_production and not _cors_origins:
    _cors_origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def limit_request_body(request: Request, call_next):
    limit = get_settings().max_body_bytes
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > limit:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "payload_too_large",
                            "message": "Request body exceeds the configured limit.",
                        }
                    },
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "invalid_content_length", "message": "Content-Length is not valid."}},
            )
    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": str(exc.detail)}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "details": jsonable_encoder(exc.errors()),
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled error")
    message = "An unexpected error occurred."
    details = None if get_settings().is_production else str(exc)
    body = {"error": {"code": "internal_error", "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=500, content=body)


@app.get("/health")
def root_health() -> JSONResponse:
    """Unauthenticated liveness plus database check for proxies and uptime monitors."""

    from app.db import check_database

    healthy = check_database()
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "database": "ok" if healthy else "unavailable"},
    )


@app.get("/")
def root() -> dict:
    return {"name": "ProjectVerse AI", "docs": "/docs", "health": "/health"}
