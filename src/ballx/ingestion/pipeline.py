"""Transactional, bounded source replay with explicit mappings and conflict quarantine."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from ballx.domain.ingestion_models import (
    Delivery,
    GroundAlias,
    GroundSourceIdentity,
    IngestionItem,
    IngestionRun,
    MatchWeatherLink,
    WeatherObservation,
)
from ballx.domain.models import DataSource, Evidence, Ground, Match, RawArtifact, RecordProvenance
from ballx.ingestion.cricsheet import NORMALIZATION_VERSION, CricsheetAdapter, name_key
from ballx.ingestion.manifest import SampleManifest, load_payload, snapshot
from ballx.ingestion.nasa_power import NasaPowerAdapter
from ballx.ingestion.storage import store_snapshot

PIPELINE_VERSION = "milestone2-v1"


class SourceConflict(ValueError):
    pass


def evidence_for(session, artifact, locator, content, kind):
    locator = f"{locator} [pipeline={PIPELINE_VERSION}]"
    evidence = session.scalar(
        select(Evidence).where(
            Evidence.artifact_id == artifact.id, Evidence.original_locator == locator
        )
    )
    if evidence is None:
        evidence = Evidence(
            source_id=artifact.source_id,
            artifact_id=artifact.id,
            source_url=artifact.source_url,
            retrieved_at=artifact.retrieved_at,
            original_locator=locator,
            excerpt_or_measurement=content,
            rights_class="source-license-see-registry",
            verification_status="verified",
            evidence_type=kind,
        )
        session.add(evidence)
        session.flush()
    return evidence


def provenance(session, evidence_id, target, values):
    for field, value in values.items():
        if value is not None and value != []:
            session.add(
                RecordProvenance(
                    evidence_id=evidence_id, field_name=field, asserted_value=value, **target
                )
            )


def register_sources(session, manifest):
    sources = {}
    for key, spec in manifest.sources.items():
        source = session.scalar(
            select(DataSource).where(
                DataSource.url == str(spec.url), DataSource.provider == spec.provider
            )
        )
        if source is None:
            source = DataSource(
                provider=spec.provider,
                url=str(spec.url),
                terms_url=str(spec.terms_url),
                license=spec.license,
                access_status="reviewed_bounded_sample",
                checked_at=spec.reviewed_at,
                attribution_required=spec.attribution_required,
                collection_allowed=True,
                notes=json.dumps(
                    {"attribution": spec.attribution, "review_notes": spec.review_notes}
                ),
            )
            session.add(source)
            session.flush()
        elif source.collection_allowed is not True or source.license != spec.license:
            raise ValueError("Existing source registry does not authorize this declared license")
        sources[key] = source
    return sources


def register_grounds(session, manifest, sources, artifacts):
    grounds = {}
    cricket_source = sources["cricsheet"]
    for spec in manifest.grounds:
        artifact = artifacts[spec.evidence_artifact]
        evidence = evidence_for(
            session,
            artifact,
            spec.evidence_locator,
            {
                "curated_facts": spec.reviewed_facts,
                "verification_scope": (
                    "manual venue identity and public coordinate transcription; not a survey"
                ),
            },
            "observed",
        )
        ground_id = uuid.uuid5(uuid.NAMESPACE_URL, "https://ballx.example/ground/" + spec.key)
        values = {
            "name": spec.name,
            "country_code": spec.country_code,
            "latitude": spec.latitude,
            "longitude": spec.longitude,
            "timezone": spec.timezone,
        }
        ground = session.get(Ground, ground_id)
        if ground is None:
            ground = Ground(
                id=ground_id, aliases=list(dict.fromkeys(a.name for a in spec.aliases)), **values
            )
            session.add(ground)
            session.flush()
            provenance(session, evidence.id, {"ground_id": ground.id}, values)
        else:
            for key, value in values.items():
                actual = getattr(ground, key)
                same = (
                    abs(float(actual) - value) <= 0.0000001
                    if key in {"latitude", "longitude"} and actual is not None
                    else actual == value
                )
                if not same:
                    raise SourceConflict(
                        "Curated ground revision requires review; existing facts were preserved"
                    )
        for alias in spec.aliases:
            existing = session.scalar(
                select(GroundAlias).where(
                    GroundAlias.source_id == cricket_source.id,
                    GroundAlias.normalized_name == name_key(alias.name),
                    GroundAlias.city_key == name_key(alias.city),
                )
            )
            if existing and existing.ground_id != ground.id:
                raise SourceConflict("A curated alias already identifies a different ground")
            if existing is None:
                session.add(
                    GroundAlias(
                        source_id=cricket_source.id,
                        ground_id=ground.id,
                        evidence_id=evidence.id,
                        name=alias.name,
                        normalized_name=name_key(alias.name),
                        city_key=name_key(alias.city),
                        normalization_version=NORMALIZATION_VERSION,
                    )
                )
        if spec.cricsheet_venue_id:
            known = session.scalar(
                select(GroundSourceIdentity).where(
                    GroundSourceIdentity.source_id == cricket_source.id,
                    GroundSourceIdentity.provider_ground_id == spec.cricsheet_venue_id,
                )
            )
            if known and known.ground_id != ground.id:
                raise SourceConflict("Source venue ID maps to a different curated ground")
            if known is None:
                session.add(
                    GroundSourceIdentity(
                        source_id=cricket_source.id,
                        ground_id=ground.id,
                        evidence_id=evidence.id,
                        provider_ground_id=spec.cricsheet_venue_id,
                    )
                )
        grounds[spec.key] = ground
    session.flush()
    return grounds


def resolve_ground(session, source_id, parsed):
    external = None
    if parsed.venue_source_id:
        external = session.scalar(
            select(GroundSourceIdentity.ground_id).where(
                GroundSourceIdentity.source_id == source_id,
                GroundSourceIdentity.provider_ground_id == parsed.venue_source_id,
            )
        )
    alias = None
    if parsed.venue and parsed.city:
        alias = session.scalar(
            select(GroundAlias.ground_id).where(
                GroundAlias.source_id == source_id,
                GroundAlias.normalized_name == name_key(parsed.venue),
                GroundAlias.city_key == name_key(parsed.city),
            )
        )
    if external and alias and external != alias:
        raise SourceConflict("Venue identifier and curated alias disagree")
    # An unknown stable ID is never assigned solely because its name resembles a known ground.
    if parsed.venue_source_id and external is None:
        return None
    return external or alias


def import_match(session, source, artifact, source_snapshot):
    adapter = CricsheetAdapter()
    parsed = adapter.parse_match(source_snapshot)
    existing = session.scalar(
        select(Match).where(
            Match.source_id == source.id, Match.provider_match_id == parsed.provider_match_id
        )
    )
    if existing:
        old = (
            session.get(RawArtifact, existing.source_artifact_id)
            if existing.source_artifact_id
            else None
        )
        if old is None or old.sha256 != artifact.sha256:
            raise SourceConflict(
                "Provider match changed; incoming raw revision retained for review"
            )
        return existing, "duplicate", parsed.issues
    ground_id = resolve_ground(session, source.id, parsed)
    issues = parsed.issues + ([] if ground_id else ["unresolved_ground"])
    draft = next(iter(adapter.parse(source_snapshot)))
    evidence = evidence_for(
        session, artifact, draft.original_locator, draft.excerpt_or_measurement, "observed"
    )
    match = Match(
        source_id=source.id,
        provider_match_id=parsed.provider_match_id,
        ground_id=ground_id,
        pitch_id=None,
        start_time=None,
        end_time=None,
        time_precision="date",
        start_date=parsed.dates[0],
        end_date=parsed.dates[-1],
        played_dates=[d.isoformat() for d in parsed.dates],
        teams=parsed.teams,
        format=parsed.format,
        gender_category=parsed.gender,
        competition=parsed.competition,
        source_venue=parsed.venue,
        source_revision=parsed.revision,
        data_version=parsed.data_version,
        source_artifact_id=artifact.id,
    )
    session.add(match)
    session.flush()
    provenance(
        session,
        evidence.id,
        {"match_id": match.id},
        {
            "provider_match_id": match.provider_match_id,
            "ground_id": str(ground_id) if ground_id else None,
            "played_dates": match.played_dates,
            "time_precision": "date",
            "teams": match.teams,
            "format": match.format,
            "gender_category": match.gender_category,
            "competition": match.competition,
            "source_venue": match.source_venue,
            "source_revision": match.source_revision,
        },
    )
    for delivery in parsed.deliveries:
        session.add(
            Delivery(
                match_id=match.id,
                source_id=source.id,
                evidence_id=evidence.id,
                innings=delivery.innings,
                over_index=delivery.over_index,
                delivery_index=delivery.delivery_index,
                original_locator=f"{source_snapshot.original_locator}#{delivery.locator}",
                event_data=delivery.event_data,
                bowler_source_id=delivery.bowler_source_id,
                batter_source_id=delivery.batter_source_id,
            )
        )
    session.flush()
    return match, "imported", issues


def import_weather(session, source, artifact, source_snapshot, spec, grounds, matches):
    ground = grounds.get(spec.ground_key)
    if ground is None:
        raise ValueError("Weather target must be a reviewed ground")
    selected = [matches[mid] for mid in spec.match_ids if mid in matches]
    if len(selected) != len(spec.match_ids) or not selected:
        raise ValueError("Weather plan references missing or conflicted matches")
    if any(match.ground_id != ground.id for match in selected):
        raise SourceConflict("Weather cannot be linked to a match at another ground")
    values = NasaPowerAdapter().parse_values(source_snapshot)
    metadata = values[0].metadata
    coordinates = (metadata.get("geometry") or {}).get("coordinates")
    if (
        not coordinates
        or len(coordinates) < 2
        or abs(coordinates[0] - float(ground.longitude)) > 0.01
        or abs(coordinates[1] - float(ground.latitude)) > 0.01
    ):
        raise ValueError("Weather response point differs from the reviewed ground request")
    evidence = evidence_for(
        session,
        artifact,
        "/properties/parameter",
        {
            "model_metadata": metadata,
            "scope": "local_calendar_day; match start/end times unknown",
            "verification_scope": (
                "source schema, UTC timestamps, point and units; not station validation"
            ),
        },
        "modeled",
    )
    timezone = ZoneInfo(ground.timezone)
    issues, created = [], 0
    for value in values:
        date_key = value.timestamp_utc.astimezone(timezone).date().isoformat()
        relevant = [match for match in selected if date_key in match.played_dates]
        if not relevant:
            continue
        row = session.scalar(
            select(WeatherObservation).where(
                WeatherObservation.source_id == source.id,
                WeatherObservation.ground_id == ground.id,
                WeatherObservation.timestamp_utc == value.timestamp_utc,
                WeatherObservation.variable == value.variable,
                WeatherObservation.model == value.model,
            )
        )
        if row:
            if (
                row.value != value.value
                or row.unit != value.unit
                or row.model_metadata != value.metadata
            ):
                raise SourceConflict("Weather source revision differs; original values preserved")
        else:
            row = WeatherObservation(
                source_id=source.id,
                ground_id=ground.id,
                timestamp_utc=value.timestamp_utc,
                variable=value.variable,
                value=value.value,
                unit=value.unit,
                model=value.model,
                model_metadata=value.metadata,
                provider=source.provider,
                evidence_id=evidence.id,
                observation_kind="modeled",
            )
            session.add(row)
            session.flush()
            created += 1
        if value.value is None and "missing_weather_values" not in issues:
            issues.append("missing_weather_values")
        for match in relevant:
            linked = session.scalar(
                select(MatchWeatherLink.id).where(
                    MatchWeatherLink.match_id == match.id, MatchWeatherLink.weather_id == row.id
                )
            )
            if linked is None:
                session.add(MatchWeatherLink(match_id=match.id, weather_id=row.id))
    session.flush()
    return "imported" if created else "duplicate", issues


def run_manifest(
    session: Session, manifest: SampleManifest, manifest_hash: str, directory: Path
) -> IngestionRun:
    """Caller owns commit. Verify every local byte before any source/data mutation."""
    manifest.validate_plan()
    payloads = {spec.key: load_payload(directory, spec) for spec in manifest.artifacts}
    session.execute(text("SELECT pg_advisory_xact_lock(hashtext('ballx-bounded-ingestion-v1'))"))
    sources = register_sources(session, manifest)
    artifacts, snapshots = {}, {}
    for spec in manifest.artifacts:
        source_snapshot = snapshot(spec, sources[spec.source].id, payloads[spec.key])
        snapshots[spec.key] = source_snapshot
        artifacts[spec.key] = store_snapshot(session, source_snapshot)
    grounds = register_grounds(session, manifest, sources, artifacts)
    run = IngestionRun(manifest_sha256=manifest_hash, pipeline_version=PIPELINE_VERSION)
    session.add(run)
    session.flush()
    matches = {}
    for spec in sorted(manifest.artifacts, key=lambda a: a.kind == "weather"):
        if spec.kind not in {"cricsheet", "weather"}:
            continue
        status, issues, match = "rejected", [], None
        try:
            with session.begin_nested():
                if spec.kind == "cricsheet":
                    match, status, issues = import_match(
                        session, sources[spec.source], artifacts[spec.key], snapshots[spec.key]
                    )
                else:
                    status, issues = import_weather(
                        session,
                        sources[spec.source],
                        artifacts[spec.key],
                        snapshots[spec.key],
                        spec,
                        grounds,
                        matches,
                    )
        except SourceConflict as exc:
            status, issues = "conflict", [str(exc)]
        except (ValueError, TypeError, KeyError, AttributeError, IntegrityError, DataError) as exc:
            status, issues = (
                "rejected",
                [
                    "database_reference_identity_or_value_error"
                    if isinstance(exc, (IntegrityError, DataError))
                    else str(exc)
                ],
            )
        if match is not None and status in {"imported", "duplicate"}:
            matches[match.provider_match_id] = match
        session.add(
            IngestionItem(
                run_id=run.id,
                artifact_id=artifacts[spec.key].id,
                match_id=match.id
                if match is not None and status in {"imported", "duplicate"}
                else None,
                provider_record_id=spec.original_locator,
                record_kind=spec.kind,
                status=status,
                issues=issues,
            )
        )
    run.completed_at = datetime.now(UTC)
    run.summary = {
        "expected_matches": manifest.expected_matches,
        "expected_weather_matches": manifest.expected_weather_matches,
        "name": manifest.name,
        "professional_scope": manifest.professional_scope,
        "attribution": {key: spec.attribution for key, spec in manifest.sources.items()},
    }
    session.flush()
    return run
