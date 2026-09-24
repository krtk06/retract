"""Test fixtures: SQLite DB, fakeredis event bus, eager Celery, TestClient."""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import fakeredis
import pytest

_TMP = Path(tempfile.mkdtemp(prefix="ai-intel-test-"))
os.environ["AI_INTEL_DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["AI_INTEL_REDIS_URL"] = "redis://localhost:6379/15"
os.environ["AI_INTEL_DEV_LOGIN"] = "1"
os.environ["AI_INTEL_DATA_DIR"] = str(_TMP / "data")
os.environ["AI_INTEL_JWT_SECRET"] = "test-secret-key-that-is-at-least-32-bytes-long"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, get_engine, reset_db_state  # noqa: E402
from app.events import RedisEventBus, set_bus  # noqa: E402
from app.main import create_app  # noqa: E402
from app.tasks.celery_app import celery_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup() -> Generator[None, None, None]:
    reset_db_state()
    Base.metadata.create_all(get_engine())
    celery_app.conf.task_always_eager = True
    set_bus(RedisEventBus(fakeredis.FakeRedis(decode_responses=True)))
    yield
    set_bus(None)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    response = client.get("/api/auth/dev/login", params={"login": "tester"})
    assert response.status_code == 200
    return client
