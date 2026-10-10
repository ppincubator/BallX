"""All data is synthetic and every test transaction is rolled back."""

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from ballx.db.session import get_session
from ballx.domain.models import DataSource, Evidence
from ballx.ingestion.contracts import SourceSnapshot
from ballx.ingestion.storage import store_snapshot
from ballx.main import create_app


def pytest_collection_modifyitems(items):
    for item in items:
        if "/integration/" in str(item.path):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is unset; PostgreSQL/PostGIS integration tests were not run")
    parsed = make_url(url)
    if parsed.drivername != "postgresql+psycopg" or not (parsed.database or "").endswith("_test"):
        pytest.fail("Integration tests require a dedicated PostgreSQL database named *_test")
    test_engine = create_engine(url, pool_pre_ping=True)
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    with test_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


@pytest.fixture
def client(session):
    app = create_app()

    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client


@pytest.fixture
def source(session):
    source = DataSource(
        provider="Synthetic test fixture",
        url="https://example.test/fixtures",
        license="Synthetic test data",
        collection_allowed=True,
        checked_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session.add(source)
    session.flush()
    return source


@pytest.fixture
def snapshot(source):
    return SourceSnapshot(
        source_id=source.id,
        source_url="https://example.test/fixtures/identity",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        media_type="application/json",
        adapter_name="synthetic-test",
        adapter_version="1",
        payload=b'{"fixture": "synthetic, not a real ground or strip"}',
    )


@pytest.fixture
def artifact(session, snapshot):
    return store_snapshot(session, snapshot)


@pytest.fixture
def evidence(session, source, artifact):
    evidence = Evidence(
        source_id=source.id,
        artifact_id=artifact.id,
        source_url=artifact.source_url,
        retrieved_at=artifact.retrieved_at,
        original_locator="fixture/identity/1",
        excerpt_or_measurement={"excerpt": "Synthetic verified ground and distinct strip fixture"},
        rights_class="synthetic-test",
        verification_status="verified",
        evidence_type="observed",
    )
    session.add(evidence)
    session.flush()
    return evidence
