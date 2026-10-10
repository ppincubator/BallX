import hashlib
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from ballx.domain.ingestion_models import (
    Delivery,
    IngestionItem,
    MatchWeatherLink,
    WeatherObservation,
)
from ballx.domain.models import Evidence, Ground, Match, PitchStrip, RawArtifact, RecordProvenance
from ballx.ingestion.pipeline import run_manifest
from ballx.ingestion.report import quality_report
from tests.ingestion_fixtures import match_record, weather_record, write_manifest


def replay(session, manifest, directory):
    return run_manifest(
        session,
        manifest,
        hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest(),
        directory,
    )


def counts(session):
    return {
        model.__tablename__: session.scalar(select(func.count()).select_from(model))
        for model in (
            Match,
            Delivery,
            RawArtifact,
            Evidence,
            RecordProvenance,
            WeatherObservation,
            MatchWeatherLink,
            Ground,
            PitchStrip,
        )
    }


def test_bounded_replay_weather_timezone_and_idempotency(session, tmp_path):
    manifest = write_manifest(tmp_path)
    run = replay(session, manifest, tmp_path)
    report = quality_report(session, run)
    assert report["validation"]["passed"]
    assert report["counts"]["newly_imported_matches"] == 1
    assert report["counts"]["delivery_records"] == 2
    assert report["counts"]["matches_with_complete_modeled_weather"] == 1
    match = session.scalar(select(Match))
    assert match.pitch_id is None and match.start_time is None and match.end_time is None
    assert match.played_dates == ["2008-04-18"]
    times = list(
        session.scalars(
            select(WeatherObservation.timestamp_utc)
            .distinct()
            .order_by(WeatherObservation.timestamp_utc)
        )
    )
    assert len(times) == 24
    assert times[0].isoformat() == "2008-04-17T19:00:00+00:00"
    assert times[-1].isoformat() == "2008-04-18T18:00:00+00:00"
    before = counts(session)
    repeat = replay(session, manifest, tmp_path)
    repeated_report = quality_report(session, repeat)
    assert repeated_report["counts"]["newly_imported_matches"] == 0
    assert repeated_report["counts"]["duplicate_matches"] == 1
    assert repeated_report["validation"]["passed"]
    assert before == counts(session)


def test_changed_provider_match_is_quarantined_without_overwrite(session, tmp_path):
    manifest = write_manifest(tmp_path, include_weather=False)
    replay(session, manifest, tmp_path)
    original = session.scalar(select(Match.source_artifact_id))
    record = match_record()
    record["meta"]["revision"] = 2
    revised = write_manifest(tmp_path, match=record, include_weather=False)
    run = replay(session, revised, tmp_path)
    report = quality_report(session, run)
    assert report["statuses"]["cricsheet"] == {"conflict": 1}
    assert not report["validation"]["passed"]
    assert session.scalar(select(Match.source_artifact_id)) == original
    assert session.scalar(select(func.count()).select_from(RawArtifact)) == 3
    assert session.scalar(select(func.count()).select_from(Delivery)) == 2


def test_unknown_venue_stays_unlinked_and_does_not_create_ground_or_strip(session, tmp_path):
    record = match_record()
    record["info"]["venue"] = "Unreviewed spelling"
    manifest = write_manifest(tmp_path, match=record, include_weather=False)
    run = replay(session, manifest, tmp_path)
    assert session.scalar(select(Match.ground_id)) is None
    assert session.scalar(select(func.count()).select_from(Ground)) == 1
    assert session.scalar(select(func.count()).select_from(PitchStrip)) == 0
    report = quality_report(session, run)
    assert not report["validation"]["passed"]
    assert report["items"][0]["issues"] == ["unresolved_ground"]


def test_unknown_stable_venue_id_requires_curated_identity(session, tmp_path):
    record = match_record()
    record["meta"]["data_version"] = "1.3.0"
    record["info"]["registry"]["venues"] = {"Synthetic Ground": "87654321"}
    manifest = write_manifest(tmp_path, match=record, include_weather=False)
    replay(session, manifest, tmp_path)
    assert session.scalar(select(Match.ground_id)) is None


def test_missing_weather_is_null_and_fails_requested_coverage(session, tmp_path):
    record = weather_record()
    record["properties"]["parameter"]["T2M"]["2008041800"] = -999
    manifest = write_manifest(tmp_path, weather=record)
    run = replay(session, manifest, tmp_path)
    report = quality_report(session, run)
    assert not report["validation"]["passed"]
    assert report["matches"][0]["weather"]["missing_values"] == 1
    assert (
        session.scalar(
            select(WeatherObservation.value).where(
                WeatherObservation.timestamp_utc == datetime(2008, 4, 18, tzinfo=UTC),
                WeatherObservation.variable == "T2M",
            )
        )
        is None
    )


def test_invalid_match_retains_raw_without_partial_normalized_records(session, tmp_path):
    record = match_record()
    record["info"]["dates"] = []
    manifest = write_manifest(tmp_path, match=record, include_weather=False)
    run = replay(session, manifest, tmp_path)
    assert session.scalar(select(func.count()).select_from(Match)) == 0
    assert session.scalar(select(func.count()).select_from(Delivery)) == 0
    assert session.scalar(select(func.count()).select_from(RawArtifact)) == 2
    item = session.scalar(select(IngestionItem).where(IngestionItem.run_id == run.id))
    assert item.status == "rejected"


def test_hash_failure_precedes_all_writes(session, tmp_path):
    manifest = write_manifest(tmp_path)
    (tmp_path / "match.json").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        replay(session, manifest, tmp_path)
    assert session.scalar(select(func.count()).select_from(RawArtifact)) == 0
    assert session.scalar(select(func.count()).select_from(Ground)) == 0


@pytest.mark.parametrize("table", ["weather", "delivery", "ingestion_item", "match_weather_link"])
def test_ingested_evidence_rows_cannot_be_updated_or_truncated(session, tmp_path, table):
    manifest = write_manifest(tmp_path)
    replay(session, manifest, tmp_path)
    with pytest.raises(DBAPIError), session.begin_nested():
        session.execute(text(f"UPDATE gpid.{table} SET created_at = now()"))
    with pytest.raises(DBAPIError), session.begin_nested():
        session.execute(text(f"TRUNCATE gpid.{table} CASCADE"))


def test_date_only_cannot_acquire_a_guessed_timestamp(session, tmp_path):
    manifest = write_manifest(tmp_path, include_weather=False)
    replay(session, manifest, tmp_path)
    with pytest.raises(DBAPIError), session.begin_nested():
        session.execute(text("UPDATE gpid.match SET start_time = '2008-04-18T00:00:00Z'"))


def test_weather_rejects_observed_evidence(session, tmp_path):
    manifest = write_manifest(tmp_path)
    replay(session, manifest, tmp_path)
    row = session.scalar(select(WeatherObservation))
    observed = session.scalar(select(Evidence).where(Evidence.evidence_type == "observed"))
    with pytest.raises(DBAPIError), session.begin_nested():
        session.add(
            WeatherObservation(
                source_id=row.source_id,
                ground_id=row.ground_id,
                timestamp_utc=datetime(2000, 1, 1, tzinfo=UTC),
                variable="T2M",
                value=0,
                unit="C",
                provider=row.provider,
                model="MERRA2",
                model_metadata={},
                evidence_id=observed.id,
                observation_kind="modeled",
            )
        )
        session.flush()


def test_weather_link_requires_the_match_ground(session, tmp_path):
    manifest = write_manifest(tmp_path)
    replay(session, manifest, tmp_path)
    other = Ground(name="Another synthetic ground")
    session.add(other)
    session.flush()
    original = session.scalar(select(Match))
    another_match = Match(
        source_id=original.source_id,
        provider_match_id="654321",
        ground_id=other.id,
        format="T20",
        start_time=datetime.now(UTC),
    )
    session.add(another_match)
    session.flush()
    weather = session.scalar(select(WeatherObservation))
    with pytest.raises(DBAPIError, match="same ground"), session.begin_nested():
        session.add(MatchWeatherLink(match_id=another_match.id, weather_id=weather.id))
        session.flush()


def test_bad_source_database_value_is_quarantined_per_record(session, tmp_path):
    record = match_record()
    record["info"]["match_type"] = "X" * 1000
    manifest = write_manifest(tmp_path, match=record, include_weather=False)
    run = replay(session, manifest, tmp_path)
    item = session.scalar(select(IngestionItem).where(IngestionItem.run_id == run.id))
    assert item.status == "rejected"
    assert item.issues == ["database_reference_identity_or_value_error"]
    assert session.scalar(select(func.count()).select_from(Match)) == 0
