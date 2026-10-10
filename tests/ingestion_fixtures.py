"""Deliberately synthetic provider-shaped data. Never counted as real imported matches."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from ballx.ingestion.manifest import SampleManifest
from ballx.ingestion.nasa_power import PARAMETERS


def match_record():
    return {
        "meta": {"data_version": "1.1.0", "revision": 1},
        "info": {
            "dates": ["2008-04-18"],
            "teams": ["Synthetic A", "Synthetic B"],
            "match_type": "T20",
            "gender": "male",
            "city": "Synthetic City",
            "venue": "Synthetic Ground",
            "event": {"name": "Synthetic professional fixture"},
            "registry": {
                "people": {"Synthetic batter": "12345678", "Synthetic bowler": "abcdef01"}
            },
        },
        "innings": [
            {
                "team": "Synthetic A",
                "overs": [
                    {
                        "over": 0,
                        "deliveries": [
                            {
                                "batter": "Synthetic batter",
                                "bowler": "Synthetic bowler",
                                "non_striker": "Synthetic other",
                                "runs": {"batter": 0, "extras": 1, "total": 1},
                                "extras": {"wides": 1},
                            },
                            {
                                "batter": "Synthetic batter",
                                "bowler": "Synthetic bowler",
                                "non_striker": "Synthetic other",
                                "runs": {"batter": 4, "extras": 0, "total": 4},
                            },
                        ],
                    }
                ],
            }
        ],
    }


def weather_record():
    keys = [
        (datetime(2008, 4, 17, tzinfo=UTC) + timedelta(hours=i)).strftime("%Y%m%d%H")
        for i in range(72)
    ]
    return {
        "header": {
            "time_standard": "UTC",
            "sources": ["MERRA2"],
            "fill_value": -999,
            "api": {"version": "synthetic-test"},
        },
        "geometry": {"type": "Point", "coordinates": [77.5, 12.5, 0]},
        "properties": {
            "parameter": {p: {k: (60 if p == "RH2M" else 1) for k in keys} for p in PARAMETERS}
        },
        "parameters": {
            p: {"units": u} for p, u in zip(PARAMETERS, ["C", "%", "mm/hour", "m/s"], strict=True)
        },
    }


def write_manifest(directory, *, match=None, weather=None, include_weather=True):
    now = datetime.now(UTC).isoformat()
    source = {
        "provider": "Synthetic Cricsheet-shaped fixture",
        "url": "https://cricsheet.org/",
        "terms_url": "https://cricsheet.org/licensing/",
        "license": "Synthetic test data",
        "reviewed_at": now,
        "collection_allowed": True,
        "attribution_required": True,
        "attribution": "Synthetic test fixtures, not real provider data",
        "review_notes": "Synthetic rights fixture",
    }
    sources = {
        "cricsheet": source,
        "registry": dict(
            source, provider="Synthetic registry", url="https://example.test/registry"
        ),
    }
    artifacts = []

    def add(key, record, source_key, kind, locator, adapter, **kwargs):
        payload = json.dumps(record).encode()
        (directory / f"{key}.json").write_bytes(payload)
        artifacts.append(
            {
                "key": key,
                "source": source_key,
                "kind": kind,
                "path": f"{key}.json",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "source_url": str(sources[source_key]["url"]) + key,
                "retrieved_at": now,
                "media_type": "application/json",
                "original_locator": locator,
                "adapter_name": adapter,
                "adapter_version": "1",
                **kwargs,
            }
        )

    add("registry", {"synthetic": True}, "registry", "registry", "synthetic/ground", "curation")
    add("match", match or match_record(), "cricsheet", "cricsheet", "123456.json", "cricsheet-json")
    if include_weather:
        sources["weather"] = dict(
            source,
            provider="Synthetic NASA-shaped fixture",
            url="https://power.larc.nasa.gov/",
            terms_url="https://power.larc.nasa.gov/docs/",
        )
        add(
            "weather",
            weather or weather_record(),
            "weather",
            "weather",
            "/properties/parameter",
            "nasa-power-hourly",
            ground_key="synthetic",
            match_ids=["123456"],
        )
    document = {
        "schema_version": 1,
        "name": "Synthetic ingestion test",
        "sources": sources,
        "artifacts": artifacts,
        "grounds": [
            {
                "key": "synthetic",
                "name": "Synthetic Ground",
                "country_code": "IN",
                "latitude": 12.5,
                "longitude": 77.5,
                "timezone": "Asia/Kolkata",
                "evidence_artifact": "registry",
                "evidence_locator": "synthetic/ground",
                "reviewed_facts": {"synthetic": True},
                "aliases": [{"name": "Synthetic Ground", "city": "Synthetic City"}],
            }
        ],
        "expected_matches": 1,
        "expected_weather_matches": int(include_weather),
        "professional_scope": "Synthetic test only",
    }
    (directory / "manifest.json").write_text(json.dumps(document))
    return SampleManifest.model_validate(document)
