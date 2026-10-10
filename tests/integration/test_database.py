import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from ballx.domain.models import (
    Association,
    DataSource,
    Evidence,
    Ground,
    Match,
    Organization,
    PitchStrip,
    RawArtifact,
    RecordProvenance,
)
from ballx.ingestion.storage import store_snapshot


def match_values(source):
    return {
        "source_id": source.id,
        "provider_match_id": "synthetic-match-1",
        "format": "test-fixture",
        "start_time": datetime(2026, 1, 1, tzinfo=UTC),
    }


def test_unknown_match_ground_and_strip_are_null(session, source):
    match = Match(**match_values(source))
    session.add(match)
    session.flush()
    session.refresh(match)
    assert match.ground_id is None and match.pitch_id is None


def test_ground_match_does_not_inherit_an_existing_strip(session, source, evidence):
    ground = Ground(name="Synthetic ground")
    session.add(ground)
    session.flush()
    session.add(PitchStrip(ground_id=ground.id, evidence_id=evidence.id))
    match = Match(ground_id=ground.id, **match_values(source))
    session.add(match)
    session.flush()
    assert match.pitch_id is None


def test_match_accepts_verified_strip_at_its_ground(session, source, evidence):
    ground = Ground(name="Synthetic ground")
    session.add(ground)
    session.flush()
    pitch = PitchStrip(ground_id=ground.id, evidence_id=evidence.id)
    session.add(pitch)
    session.flush()
    match = Match(ground_id=ground.id, pitch_id=pitch.id, **match_values(source))
    session.add(match)
    session.flush()
    assert match.pitch_id == pitch.id


@pytest.mark.parametrize("has_ground", [True, False])
def test_match_cannot_reference_a_strip_of_another_ground(session, source, evidence, has_ground):
    grounds = [Ground(name="Synthetic A"), Ground(name="Synthetic B")]
    session.add_all(grounds)
    session.flush()
    pitch = PitchStrip(ground_id=grounds[0].id, evidence_id=evidence.id)
    session.add(pitch)
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            Match(
                ground_id=grounds[1].id if has_ground else None,
                pitch_id=pitch.id,
                **match_values(source),
            )
        )
        session.flush()


def test_match_identity_is_unique_within_source(session, source):
    session.add(Match(**match_values(source)))
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(Match(**match_values(source)))
        session.flush()


def test_association_owner_and_operator_have_separate_references(session):
    association = Association(name="Synthetic cricket association", jurisdiction="Synthetic")
    owner = Organization(name="Synthetic owner")
    operator = Organization(name="Synthetic operator")
    session.add_all([association, owner, operator])
    session.flush()
    ground = Ground(
        name="Synthetic ground",
        association_id=association.id,
        owner_id=owner.id,
        operator_id=operator.id,
    )
    session.add(ground)
    session.flush()
    assert len({ground.association_id, ground.owner_id, ground.operator_id}) == 3


def test_snapshot_storage_is_idempotent(session, snapshot):
    first = store_snapshot(session, snapshot)
    second = store_snapshot(session, snapshot)
    assert first.id == second.id
    assert first.payload == snapshot.payload
    assert session.scalar(select(func.count()).select_from(RawArtifact)) == 1
    assert session.scalar(select(func.count()).select_from(Ground)) == 0


@pytest.mark.parametrize("allowed", [None, False])
def test_collection_requires_reviewed_permission(session, source, snapshot, allowed):
    source.collection_allowed = allowed
    session.flush()
    with pytest.raises(ValueError, match="explicitly reviewed"):
        store_snapshot(session, snapshot)


def test_permission_requires_review_date(session, source, snapshot):
    source.checked_at = None
    session.flush()
    with pytest.raises(ValueError, match="explicitly reviewed"):
        store_snapshot(session, snapshot)


def test_raw_artifact_hash_is_enforced_by_database(session, snapshot):
    with pytest.raises(IntegrityError), session.begin_nested():
        values = snapshot.model_dump(exclude={"source_url"})
        session.add(RawArtifact(**values, source_url=str(snapshot.source_url), sha256="0" * 64))
        session.flush()


@pytest.mark.parametrize("table", ["raw.artifact", "gpid.evidence", "gpid.record_provenance"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "TRUNCATE"])
def test_evidence_raw_and_provenance_are_immutable(session, evidence, table, operation):
    ground = Ground(name="Synthetic ground")
    session.add(ground)
    session.flush()
    session.add(
        RecordProvenance(
            ground_id=ground.id,
            evidence_id=evidence.id,
            field_name="name",
            asserted_value=ground.name,
        )
    )
    session.flush()
    statements = {
        "UPDATE": f"UPDATE {table} SET id = id",
        "DELETE": f"DELETE FROM {table}",
        "TRUNCATE": f"TRUNCATE {table} CASCADE",
    }
    with pytest.raises(DBAPIError) as error, session.begin_nested():
        session.execute(text(statements[operation]))
    assert error.value.orig.sqlstate == "55000"


def test_provenance_requires_exactly_one_valid_entity(session, evidence):
    grounds = [Ground(name="Synthetic A"), Ground(name="Synthetic B")]
    session.add_all(grounds)
    session.flush()
    for target in [
        {},
        {"ground_id": uuid.uuid4()},
        {"ground_id": grounds[0].id, "match_id": uuid.uuid4()},
    ]:
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                RecordProvenance(
                    evidence_id=evidence.id, field_name="name", asserted_value="Synthetic", **target
                )
            )
            session.flush()


def test_artifact_and_evidence_source_must_agree(session, evidence, artifact):
    other = DataSource(provider="Other synthetic source", url="https://example.test/other")
    session.add(other)
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            Evidence(
                source_id=other.id,
                artifact_id=artifact.id,
                source_url=evidence.source_url,
                original_locator="fixture/source-mismatch",
                retrieved_at=evidence.retrieved_at,
                excerpt_or_measurement={"excerpt": "Synthetic source mismatch"},
                evidence_type="observed",
            )
        )
        session.flush()


def test_evidence_correction_appends_a_new_record(session, evidence):
    replacement = Evidence(
        source_id=evidence.source_id,
        source_url=evidence.source_url,
        original_locator="fixture/correction",
        retrieved_at=evidence.retrieved_at,
        excerpt_or_measurement={"excerpt": "Synthetic corrected assertion"},
        evidence_type="observed",
        supersedes_evidence_id=evidence.id,
    )
    session.add(replacement)
    session.flush()
    assert replacement.id != evidence.id
    assert session.scalar(select(func.count()).select_from(Evidence)) == 2


def test_direct_sql_cannot_bypass_strip_evidence_gate(session, evidence):
    ground = Ground(name="Synthetic ground")
    unreviewed = Evidence(
        source_id=evidence.source_id,
        source_url=evidence.source_url,
        original_locator="fixture/unreviewed",
        retrieved_at=evidence.retrieved_at,
        excerpt_or_measurement={"excerpt": "Synthetic unreviewed assertion"},
        evidence_type="observed",
    )
    session.add_all([ground, unreviewed])
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(PitchStrip(ground_id=ground.id, evidence_id=unreviewed.id))
        session.flush()


@pytest.mark.parametrize(
    "fields", [{"latitude": 10}, {"latitude": 91, "longitude": 0}, {"confidence": 2}]
)
def test_database_rejects_invalid_ground_values(session, fields):
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(Ground(name="Synthetic invalid values", **fields))
        session.flush()
