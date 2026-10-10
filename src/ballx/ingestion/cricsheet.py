"""Strict Cricsheet JSON 1.x parsing without venue-to-strip inference."""

import json
import re
import unicodedata
from collections.abc import Iterable
from datetime import date
from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict

from ballx.domain.types import EvidenceType
from ballx.ingestion.contracts import EvidenceDraft, SourceSnapshot

SUPPORTED_VERSIONS = {"1.0.0", "1.1.0", "1.2.0", "1.3.0"}
NORMALIZATION_VERSION = "nfkc-casefold-whitespace-v1"


def name_key(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(payload: bytes) -> dict[str, Any]:
    def reject_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    parsed = json.loads(payload, object_pairs_hook=_object, parse_constant=reject_constant)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object")
    return parsed


class ParsedDelivery(BaseModel):
    innings: int
    over_index: int
    delivery_index: int
    locator: str
    event_data: dict[str, Any]
    bowler_source_id: str | None
    batter_source_id: str | None


class ParsedMatch(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    provider_match_id: str
    data_version: str
    revision: int
    dates: list[date]
    teams: list[str]
    format: str
    gender: str | None
    venue: str | None
    city: str | None
    venue_source_id: str | None
    competition: str | None
    info: dict[str, Any]
    deliveries: list[ParsedDelivery]
    issues: list[str]


class CricsheetAdapter:
    name = "cricsheet-json"
    version = "1"

    def parse_match(self, snapshot: SourceSnapshot) -> ParsedMatch:
        member = PurePosixPath(snapshot.original_locator or "").name
        if not re.fullmatch(r"[0-9]+\.json", member):
            raise ValueError("Cricsheet identity must come from a numeric JSON member filename")
        record = read_json(snapshot.payload)
        meta, info = record.get("meta"), record.get("info")
        if not isinstance(meta, dict) or not isinstance(info, dict):
            raise ValueError("Required meta/info objects are missing")
        version = meta.get("data_version")
        if version not in SUPPORTED_VERSIONS:
            raise ValueError("Unsupported Cricsheet JSON version")
        revision = meta.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError("A positive source revision is required")
        raw_dates = info.get("dates")
        if not isinstance(raw_dates, list) or not raw_dates:
            raise ValueError("At least one source match date is required")
        if any(
            not isinstance(d, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in raw_dates
        ):
            raise ValueError("Match dates must use source ISO calendar dates")
        dates = [date.fromisoformat(d) for d in raw_dates]
        if dates != sorted(set(dates)):
            raise ValueError("Source match dates must be unique and ordered")
        teams = info.get("teams")
        if (
            not isinstance(teams, list)
            or len(teams) != 2
            or any(not isinstance(t, str) or not t.strip() for t in teams)
        ):
            raise ValueError("Two source teams are required")
        format_ = info.get("match_type")
        if not isinstance(format_, str) or not format_.strip():
            raise ValueError("Source match type is required")
        issues = []
        optional = {}
        for field in ("venue", "city", "gender"):
            value = info.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"Invalid source {field}")
            optional[field] = value
            if value is None:
                issues.append(f"missing_{field}")
        competition = (info.get("event") or {}).get("name")
        if competition is not None and (
            not isinstance(competition, str) or not competition.strip()
        ):
            raise ValueError("Invalid competition name")
        if competition is None:
            issues.append("missing_competition")
        registry = info.get("registry") or {}
        venue_ids = registry.get("venues") or {}
        venue_id = venue_ids.get(optional["venue"])
        if venue_id is not None and not re.fullmatch(r"[0-9a-f]{8}", venue_id):
            raise ValueError("Invalid Cricsheet venue registry identifier")
        people = registry.get("people") or {}
        innings = record.get("innings")
        if not isinstance(innings, list):
            raise ValueError("Required innings array is missing")
        deliveries = []
        for innings_index, inning in enumerate(innings):
            if not isinstance(inning, dict) or not isinstance(inning.get("overs"), list):
                raise ValueError("Each innings requires an overs array")
            seen_overs = set()
            for over_position, over in enumerate(inning.get("overs", [])):
                over_index = over.get("over")
                if (
                    not isinstance(over_index, int)
                    or isinstance(over_index, bool)
                    or over_index < 0
                ):
                    raise ValueError("Invalid over index")
                if over_index in seen_overs:
                    raise ValueError("Duplicate over index in innings")
                seen_overs.add(over_index)
                events = over.get("deliveries")
                if not isinstance(events, list):
                    raise ValueError("Each over requires a deliveries array")
                for delivery_position, event in enumerate(events):
                    if (
                        not isinstance(event, dict)
                        or not {"batter", "bowler", "runs"} <= event.keys()
                    ):
                        raise ValueError("Invalid source delivery")
                    if any(
                        not isinstance(event[field], str) or not event[field].strip()
                        for field in ("batter", "bowler")
                    ):
                        raise ValueError("Delivery batter and bowler names are required")
                    runs = event["runs"]
                    if (
                        not isinstance(runs, dict)
                        or not {"batter", "extras", "total"} <= runs.keys()
                    ):
                        raise ValueError("Delivery runs breakdown is required")
                    if (
                        any(
                            type(runs[field]) is not int or runs[field] < 0
                            for field in ("batter", "extras", "total")
                        )
                        or runs["total"] != runs["batter"] + runs["extras"]
                    ):
                        raise ValueError("Inconsistent delivery runs breakdown")
                    deliveries.append(
                        ParsedDelivery(
                            innings=innings_index + 1,
                            over_index=over_index,
                            delivery_index=delivery_position + 1,
                            locator=f"/innings/{innings_index}/overs/{over_position}/deliveries/{delivery_position}",
                            event_data=event,
                            bowler_source_id=people.get(event["bowler"]),
                            batter_source_id=people.get(event["batter"]),
                        )
                    )
        return ParsedMatch(
            provider_match_id=member.removesuffix(".json"),
            data_version=version,
            revision=revision,
            dates=dates,
            teams=teams,
            format=format_.strip().upper(),
            competition=competition,
            venue_source_id=venue_id,
            info=info,
            deliveries=deliveries,
            issues=issues,
            **optional,
        )

    def parse(self, snapshot: SourceSnapshot) -> Iterable[EvidenceDraft]:
        match = self.parse_match(snapshot)
        yield EvidenceDraft(
            original_locator=f"{snapshot.original_locator}#/info",
            excerpt_or_measurement={
                "info": match.info,
                "verification_scope": (
                    "source_schema_and_identity_mapping; no independent scorecard audit"
                ),
                "adapter_version": self.version,
            },
            evidence_type=EvidenceType.OBSERVED,
        )
