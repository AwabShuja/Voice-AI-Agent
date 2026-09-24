from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import select, text

from app.api import patients, vapi
from app.core.config import Settings
from app.core.errors import AppError, install_error_handlers
from app.core.logging import configure_logging
from app.db.session import build_engine, session_factory
from app.models import Patient
from app.services.registration import RegistrationService
from app.voice.state import DraftStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            with engine.connect() as connection:
                connection.execute(select(Patient.patient_id).limit(1))
        except Exception:
            engine.dispose()
            raise RuntimeError("Database is not ready. Run: alembic upgrade head") from None
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Voice Patient Registration",
        description="Synthetic data assessment. Patient routes require X-API-Key.",
        version="0.1.0",
        lifespan=lifespan,
        responses={
            code: {"description": label}
            for code, label in {
                400: "Malformed request",
                401: "Unauthorized",
                404: "Not found",
                422: "Validation failed",
                500: "Internal error",
            }.items()
        },
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory(engine)
    app.state.registration_service = RegistrationService(
        DraftStore(settings.draft_ttl_seconds, settings.max_drafts)
    )
    install_error_handlers(app)
    app.include_router(patients.router)
    app.include_router(vapi.router)

    @app.get("/health", tags=["health"])
    def health(request: Request):
        try:
            with request.app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            raise AppError(503, "database_unavailable", "Database is unavailable.") from exc
        return {"data": {"status": "ok"}, "error": None}

    return app
