"""Health check."""

import redis
from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.db import get_engine
from app.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    settings = get_settings()

    db_status = "ok"
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_status = "error"

    redis_status = "ok"
    try:
        redis.Redis.from_url(settings.redis_url).ping()
    except Exception:  # noqa: BLE001
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthOut(status=overall, db=db_status, redis=redis_status)
