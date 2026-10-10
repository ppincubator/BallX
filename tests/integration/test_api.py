import uuid

import pytest
from sqlalchemy import func, select, text

from ballx.domain.models import Evidence, Ground, PitchStrip, RecordProvenance


def ground(client, evidence, **changes):
    response = client.post(
        "/api/v1/grounds",
        json={"name": "Synthetic ground", "evidence_id": str(evidence.id), **changes},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_ground_creation_and_spatial_provenance(client, session, evidence):
    record = ground(
        client, evidence, latitude="51.5000000", longitude="-0.1000000", timezone="Europe/London"
    )
    assert client.get(f"/api/v1/grounds/{record['id']}").json() == record
    assert client.get("/api/v1/grounds").json() == [record]
    coordinates = session.execute(
        text(
            "SELECT ST_X(location), ST_Y(location), ST_SRID(location) FROM gpid.ground WHERE id=:id"
        ),
        {"id": record["id"]},
    ).one()
    assert coordinates == (-0.1, 51.5, 4326)
    provenance = client.get(f"/api/v1/grounds/{record['id']}/provenance").json()
    assert {p["field_name"] for p in provenance} == {"name", "latitude", "longitude", "timezone"}
    assert all(p["evidence_id"] == str(evidence.id) for p in provenance)


def test_ground_does_not_automatically_create_strip(client, session, evidence):
    record = ground(client, evidence)
    assert record["latitude"] is None and record["confidence"] is None
    assert client.get("/api/v1/pitches", params={"ground_id": record["id"]}).json() == []
    assert session.scalar(select(func.count()).select_from(PitchStrip)) == 0


def test_ground_write_requires_existing_evidence(client):
    response = client.post(
        "/api/v1/grounds", json={"name": "Synthetic", "evidence_id": str(uuid.uuid4())}
    )
    assert response.status_code == 422


def test_strip_creation_nullable_label_and_provenance(client, evidence):
    record = ground(client, evidence)
    response = client.post(
        "/api/v1/pitches", json={"ground_id": record["id"], "evidence_id": str(evidence.id)}
    )
    assert response.status_code == 201, response.text
    pitch = response.json()
    assert pitch["local_strip_identifier"] is None
    assert pitch["construction_type"] is None
    assert response.headers["Location"] == f"/api/v1/pitches/{pitch['id']}"
    assert client.get(response.headers["Location"]).json() == pitch
    assert client.get("/api/v1/pitches", params={"ground_id": record["id"]}).json() == [pitch]
    provenance = client.get(f"/api/v1/pitches/{pitch['id']}/provenance").json()
    assert provenance[0]["field_name"] == "ground_id"


def test_duplicate_local_strip_returns_conflict_without_partial_provenance(
    client, session, evidence
):
    record = ground(client, evidence)
    values = {
        "ground_id": record["id"],
        "evidence_id": str(evidence.id),
        "local_strip_identifier": "fixture-strip-A",
    }
    assert client.post("/api/v1/pitches", json=values).status_code == 201
    before = session.scalar(select(func.count()).select_from(RecordProvenance))
    assert client.post("/api/v1/pitches", json=values).status_code == 409
    assert session.scalar(select(func.count()).select_from(PitchStrip)) == 1
    assert session.scalar(select(func.count()).select_from(RecordProvenance)) == before


@pytest.mark.parametrize(
    ("verification", "kind"),
    [
        ("unreviewed", "observed"),
        ("rejected", "observed"),
        ("verified", "modeled"),
        ("verified", "proxy"),
        ("verified", "experimental"),
    ],
)
def test_strip_identity_evidence_gate(client, session, evidence, verification, kind):
    record = ground(client, evidence)
    unsupported = Evidence(
        source_id=evidence.source_id,
        source_url=evidence.source_url,
        original_locator="fixture/not-strip-identity",
        retrieved_at=evidence.retrieved_at,
        excerpt_or_measurement={"excerpt": "Unsupported synthetic identity evidence"},
        evidence_type=kind,
        verification_status=verification,
    )
    session.add(unsupported)
    session.flush()
    response = client.post(
        "/api/v1/pitches", json={"ground_id": record["id"], "evidence_id": str(unsupported.id)}
    )
    assert response.status_code == 422
    assert client.get("/api/v1/pitches").json() == []


def test_foreign_key_conflict_rolls_back_ground_and_provenance(client, session, evidence):
    response = client.post(
        "/api/v1/grounds",
        json={
            "name": "Synthetic",
            "evidence_id": str(evidence.id),
            "association_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 409
    assert session.scalar(select(func.count()).select_from(Ground)) == 0
    assert session.scalar(select(func.count()).select_from(RecordProvenance)) == 0


def test_unknown_entities_and_bounded_pagination(client):
    missing = str(uuid.uuid4())
    for path in [f"/api/v1/grounds/{missing}", f"/api/v1/pitches/{missing}"]:
        assert client.get(path).status_code == 404
    assert client.get("/api/v1/pitches", params={"ground_id": missing}).status_code == 404
    for params in [{"limit": 0}, {"limit": 101}, {"offset": -1}]:
        assert client.get("/api/v1/grounds", params=params).status_code == 422


def test_readiness_checks_postgis_and_migrated_schema(client):
    assert client.get("/health/ready").json() == {"status": "ready"}
