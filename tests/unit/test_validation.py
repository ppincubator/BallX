import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ballx.api.schemas import GroundCreate, PitchCreate
from ballx.config import Settings
from ballx.ingestion.contracts import SourceSnapshot
from ballx.main import create_app


def ground_data(**changes):
    return {"name": "Synthetic test ground", "evidence_id": uuid.uuid4(), **changes}


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "   "},
        {"latitude": 10},
        {"longitude": 10},
        {"latitude": 91, "longitude": 0},
        {"latitude": 0, "longitude": -181},
        {"latitude": "NaN", "longitude": 0},
        {"confidence": -0.1},
        {"confidence": 1.1},
        {"confidence": "NaN"},
        {"timezone": "Invented/Timezone"},
        {"timezone": "../UTC"},
        {"soil_clay_percentage": 55},
    ],
)
def test_ground_rejects_invalid_or_unspecified_fields(changes):
    with pytest.raises(ValidationError):
        GroundCreate(**ground_data(**changes))


def test_unknown_ground_fields_remain_unknown():
    ground = GroundCreate(**ground_data())
    assert ground.latitude is None and ground.longitude is None
    assert ground.confidence is None
    assert ground.timezone is None


@pytest.mark.parametrize("name", ["Asia/Kolkata", "Australia/Sydney", "Europe/London", "UTC"])
def test_iana_timezones(name):
    assert GroundCreate(**ground_data(timezone=name)).timezone == name


def test_unknown_local_strip_identifier_is_null():
    pitch = PitchCreate(ground_id=uuid.uuid4(), evidence_id=uuid.uuid4())
    assert pitch.local_strip_identifier is None
    assert pitch.construction_type is None
    assert pitch.identity_confidence is None


@pytest.mark.parametrize(
    "changes",
    [
        {"local_strip_identifier": " "},
        {"construction_type": "black soil"},
        {"identity_confidence": 2},
        {"soil_moisture": 20},
    ],
)
def test_pitch_rejects_invalid_fields(changes):
    with pytest.raises(ValidationError):
        PitchCreate(ground_id=uuid.uuid4(), evidence_id=uuid.uuid4(), **changes)


def test_identity_evidence_is_required():
    with pytest.raises(ValidationError):
        GroundCreate(name="Synthetic test ground")
    with pytest.raises(ValidationError):
        PitchCreate(ground_id=uuid.uuid4())


def test_database_must_be_postgres():
    with pytest.raises(ValidationError, match="postgresql"):
        Settings(database_url="sqlite:///fake.db", _env_file=None)


def test_settings_hide_credentials():
    settings = Settings(
        database_url="postgresql+psycopg://user:test_secret@db/test", _env_file=None
    )
    assert "test_secret" not in repr(settings)


def test_snapshot_requires_timezone_aware_retrieval():
    values = {
        "source_id": uuid.uuid4(),
        "source_url": "https://example.test/fixture",
        "media_type": "application/json",
        "adapter_name": "test",
        "adapter_version": "1",
        "payload": b"{}",
    }
    with pytest.raises(ValidationError):
        SourceSnapshot(retrieved_at=datetime(2026, 1, 1), **values)
    snapshot = SourceSnapshot(retrieved_at=datetime(2026, 1, 1, tzinfo=UTC), **values)
    assert snapshot.sha256 == "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


def test_liveness_does_not_require_database():
    with TestClient(create_app()) as client:
        assert client.get("/health/live").json() == {"status": "ok"}


def test_openapi_documents_nullable_strip_identifier():
    schema = create_app().openapi()
    assert {"type": "null"} in schema["components"]["schemas"]["PitchCreate"]["properties"][
        "local_strip_identifier"
    ]["anyOf"]
    assert "/api/v1/grounds" in schema["paths"]
    assert "/api/v1/pitches" in schema["paths"]
