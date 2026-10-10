"""Coverage for the explicit sample, with source validation and scientific limits separated."""

from collections import Counter
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from ballx.domain.ingestion_models import (
    Delivery,
    IngestionItem,
    MatchWeatherLink,
    WeatherObservation,
)
from ballx.domain.models import Ground, Match, RawArtifact
from ballx.ingestion.nasa_power import PARAMETERS


def expected_hours(match, timezone):
    """Native UTC hour starts falling inside each played local calendar date (DST aware)."""
    result = set()
    for date_key in match.played_dates:
        start = datetime.fromisoformat(date_key).replace(tzinfo=ZoneInfo(timezone))
        lower = start.astimezone(UTC)
        upper = (start + timedelta(days=1)).astimezone(UTC)
        timestamp = lower.replace(minute=0, second=0, microsecond=0)
        if timestamp < lower:
            timestamp += timedelta(hours=1)
        while timestamp < upper:
            result.add(timestamp)
            timestamp += timedelta(hours=1)
    return result


def quality_report(session, run):
    items = list(session.scalars(select(IngestionItem).where(IngestionItem.run_id == run.id)))
    match_items = [i for i in items if i.record_kind == "cricsheet"]
    ids = list({i.match_id for i in match_items if i.match_id is not None})
    matches = list(session.scalars(select(Match).where(Match.id.in_(ids))))
    details = []
    complete_weather = 0
    for match in sorted(matches, key=lambda m: m.provider_match_id):
        ground = session.get(Ground, match.ground_id) if match.ground_id else None
        rows = list(
            session.scalars(
                select(WeatherObservation)
                .join(MatchWeatherLink, MatchWeatherLink.weather_id == WeatherObservation.id)
                .where(MatchWeatherLink.match_id == match.id)
            )
        )
        expected = (
            {(t, p) for t in expected_hours(match, ground.timezone) for p in PARAMETERS}
            if ground
            else set()
        )
        available = {(r.timestamp_utc, r.variable) for r in rows if r.value is not None}
        complete = bool(expected) and available == expected and len(rows) == len(expected)
        complete_weather += int(complete)
        delivery_count = session.scalar(
            select(func.count()).select_from(Delivery).where(Delivery.match_id == match.id)
        )
        artifact = session.get(RawArtifact, match.source_artifact_id)
        details.append(
            {
                "provider_match_id": match.provider_match_id,
                "ground_id": str(match.ground_id) if ground else None,
                "ground": ground.name if ground else None,
                "country": ground.country_code if ground else None,
                "played_dates": match.played_dates,
                "format": match.format,
                "gender": match.gender_category,
                "time_precision": match.time_precision,
                "start_time": None if match.start_time is None else match.start_time.isoformat(),
                "pitch_strip_id": str(match.pitch_id) if match.pitch_id else None,
                "deliveries": delivery_count,
                "source_sha256": artifact.sha256 if artifact else None,
                "weather": {
                    "scope": "local_calendar_day",
                    "expected_hourly_variable_records": len(expected),
                    "linked_records": len(rows),
                    "missing_values": sum(r.value is None for r in rows),
                    "complete": complete,
                },
            }
        )
    statuses = {
        kind: dict(Counter(i.status for i in items if i.record_kind == kind))
        for kind in ("cricsheet", "weather")
    }
    checks = {
        "all_planned_matches_source_validated": len(matches) == run.summary["expected_matches"],
        "all_matches_linked_to_reviewed_grounds": bool(matches)
        and all(m.ground_id for m in matches),
        "no_conflicted_or_rejected_records": all(
            i.status in {"imported", "duplicate"} for i in items
        ),
        "requested_weather_coverage_complete": complete_weather
        >= run.summary["expected_weather_matches"],
        "no_inferred_pitch_strips": all(m.pitch_id is None for m in matches),
        "date_only_precision_preserved": all(
            m.time_precision == "date" and m.start_time is None and m.end_time is None
            for m in matches
        ),
    }
    return {
        "run_id": str(run.id),
        "manifest_sha256": run.manifest_sha256,
        "pipeline_version": run.pipeline_version,
        "name": run.summary["name"],
        "professional_scope": run.summary["professional_scope"],
        "counts": {
            "source_validated_matches": len(matches),
            "independently_scorecard_verified_matches": 0,
            "newly_imported_matches": statuses["cricsheet"].get("imported", 0),
            "duplicate_matches": statuses["cricsheet"].get("duplicate", 0),
            "matches_with_complete_modeled_weather": complete_weather,
            "delivery_records": sum(d["deliveries"] for d in details),
            "pitch_strip_assignments": sum(m.pitch_id is not None for m in matches),
        },
        "statuses": statuses,
        "validation": {"passed": all(checks.values()), "checks": checks},
        "items": [
            {
                "provider_record_id": i.provider_record_id,
                "kind": i.record_kind,
                "status": i.status,
                "issues": i.issues,
            }
            for i in items
        ],
        "matches": details,
        "attribution": run.summary["attribution"],
        "limitations": [
            "Source validated means schema, bytes, identities and mappings; "
            "no independent scorecard audit.",
            "Hourly weather is NASA POWER atmospheric grid model output, "
            "not station or pitch soil measurements.",
            "Calendar-day weather context is not actual match-time exposure; "
            "start/end times are unknown.",
            "The selected sample does not establish global coverage or justify global ingestion.",
        ],
    }
