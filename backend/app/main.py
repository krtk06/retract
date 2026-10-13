"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import analyses, auth, graph, health, repos, trust

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    # Not fatal — the app runs fine without mail — but it is not harmless either:
    # address verification cannot happen, so GitHub sign-ins never link to email
    # accounts and the only symptom is the duplicate-account behaviour that linking
    # exists to prevent. Say so once, at startup, rather than once per sign-up.
    if settings.is_production and not settings.smtp_url:
        logger.warning(
            "RETRACT_SMTP_URL is not set: address-verification emails cannot be sent, "
            "so GitHub sign-ins will not link to existing email accounts."
        )

    app = FastAPI(title="Retract", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(repos.router, prefix="/api")
    app.include_router(analyses.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")
    app.include_router(trust.router, prefix="/api")

    return app


app = create_app()
