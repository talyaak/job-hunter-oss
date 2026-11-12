"""Shared test setup: hermetic temp DB, and every TestClient authenticated unless a test passes ``headers``."""

import os
import tempfile

# Must happen before ``app`` is imported anywhere so the engine points at a throwaway database.
_TMP = tempfile.mkdtemp(prefix="jh-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.session import Base, engine  # noqa: E402
from app.db import models  # noqa: E402,F401

TEST_TOKEN = "test-token-0123456789"
Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _access_token(monkeypatch):
    monkeypatch.setattr(settings, "access_token", TEST_TOKEN)
    original_init = TestClient.__init__

    def init(self, *args, **kwargs):
        if "headers" not in kwargs:
            kwargs["headers"] = {"Authorization": f"Bearer {TEST_TOKEN}"}
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", init)
