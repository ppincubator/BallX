"""Prepare five IPL 2008 matches at one explicitly reviewed ground. No global crawl."""

import hashlib
import json
import re
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ballx.ingestion.contracts import SourceSnapshot
from ballx.ingestion.cricsheet import CricsheetAdapter, read_json
from ballx.ingestion.http import download
from ballx.ingestion.manifest import SampleManifest
from ballx.ingestion.nasa_power import request_url

ARCHIVE_URL = "https://cricsheet.org/downloads/2008_json.zip"
REVIEWED_AT = datetime(2026, 10, 10, tzinfo=UTC)
GROUND_KEY = "in-bengaluru-m-chinnaswamy"
GROUND_URL = "https://www.wikidata.org/wiki/Q1861907"
LATITUDE = round(12 + 58 / 60 + 43.70 / 3600, 7)
LONGITUDE = round(77 + 35 / 60 + 58.40 / 3600, 7)
VENUES = {"M Chinnaswamy Stadium", "M. Chinnaswamy Stadium"}
CITIES = {"Bangalore", "Bengaluru"}


def select_members(archive_path):
    """Inspect only the bounded annual archive; preserve selected original member bytes."""
    selected, notices = [], []
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) > 1000 or sum(m.file_size for m in members) > 100 * 1024 * 1024:
            raise ValueError("Annual archive exceeds the bounded sample plan")
        if len({m.filename for m in members}) != len(members):
            raise ValueError("Duplicate archive member paths")
        for member in members:
            if member.is_dir():
                continue
            if member.file_size > 5 * 1024 * 1024:
                raise ValueError("Archive member exceeds the artifact bound")
            filename = Path(member.filename).name
            if not re.fullmatch(r"[0-9]+\.json", filename):
                if any(
                    word in filename.lower() for word in ("license", "licence", "readme", "copying")
                ):
                    notices.append((member.filename, archive.read(member)))
                continue
            payload = archive.read(member)
            record = read_json(payload)
            info = record.get("info") or {}
            if (
                info.get("venue") not in VENUES
                or info.get("city") not in CITIES
                or (info.get("event") or {}).get("name") != "Indian Premier League"
                or info.get("match_type") != "T20"
                or info.get("gender") != "male"
            ):
                continue
            dates = info.get("dates") or []
            if not dates or any(not d.startswith("2008-") for d in dates):
                continue
            selected.append((dates[0], filename, member.filename, payload))
    selected.sort(key=lambda entry: (entry[0], int(entry[1].removesuffix(".json"))))
    if len(selected) < 5:
        raise ValueError("The fixed reviewed venue/competition plan did not yield five matches")
    return selected[:5], notices


def prepare(directory: Path, cache: Path):
    """Freeze a new sample, retaining attribution, source notices, and all original responses."""
    if datetime.now(UTC) - REVIEWED_AT > timedelta(days=90):
        raise ValueError(
            "Pilot source rights review expired; review current terms before preparing"
        )
    if (directory / "manifest.json").exists():
        raise ValueError("Sample already frozen; use a new directory instead of overwriting")
    cache.mkdir(parents=True, exist_ok=True)
    archive_path = cache / "2008_json.zip"
    archive_hash = download(ARCHIVE_URL, archive_path)
    selected, notices = select_members(archive_path)
    now = datetime.now(UTC).isoformat()
    sources = {
        "cricsheet": {
            "provider": "Cricsheet",
            "url": "https://cricsheet.org/",
            "terms_url": "https://cricsheet.org/licensing/",
            "license": "ODC-BY-1.0",
            "reviewed_at": REVIEWED_AT.isoformat(),
            "collection_allowed": True,
            "attribution_required": True,
            "attribution": "Cricket data from Cricsheet (https://cricsheet.org/), licensed under "
            "Open Data Commons Attribution License v1.0 "
            "(https://opendatacommons.org/licenses/by/1-0/).",
            "review_notes": "Current JSON license checked on 2026-10-10. Commercial database use "
            "allowed with attribution and notices. This bounded sample excludes withheld data. "
            "This is not a determination of independent third-party rights.",
        },
        "weather": {
            "provider": "NASA POWER",
            "url": "https://power.larc.nasa.gov/",
            "terms_url": (
                "https://www.earthdata.nasa.gov/engage/open-data-services-software/data-use-policy"
            ),
            "license": "NASA public-domain data; acknowledge NASA POWER",
            "reviewed_at": REVIEWED_AT.isoformat(),
            "collection_allowed": True,
            "attribution_required": True,
            "attribution": "Meteorological data obtained from the NASA POWER Project "
            "at NASA Langley "
            "Research Center, funded through the NASA Earth Science/Applied Science Program.",
            "review_notes": "NASA POWER team confirms public-domain use including commercial use: "
            "https://forum.earthdata.nasa.gov/viewtopic.php?t=506 and "
            "https://forum.earthdata.nasa.gov/viewtopic.php?t=82 . "
            "Use UTC atmospheric model data with acknowledgment; no NASA endorsement.",
        },
        "curation": {
            "provider": "BallX manual ground curation",
            "url": GROUND_URL,
            "terms_url": "https://www.wikidata.org/wiki/Wikidata:Licensing",
            "license": "CC0-1.0 facts",
            "reviewed_at": REVIEWED_AT.isoformat(),
            "collection_allowed": True,
            "attribution_required": False,
            "attribution": "Ground coordinates transcribed from Wikidata Q1861907/P625. "
            "BallX manual curation is explicitly labeled; it is not an upstream API response.",
            "review_notes": "Wikidata structured facts are CC0; identity/location and coordinates "
            "reviewed on 2026-10-10. Timezone Asia/Kolkata reviewed from India location. "
            "Coordinates are not a survey or a pitch-strip position.",
        },
    }
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = []

    def retain(key, payload, source, kind, source_url, locator, adapter, **extra):
        path = f"{key}.json" if kind in {"cricsheet", "weather", "registry"} else f"{key}.txt"
        (directory / path).write_bytes(payload)
        artifacts.append(
            {
                "key": key,
                "source": source,
                "kind": kind,
                "path": path,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "source_url": source_url,
                "retrieved_at": now,
                "media_type": "application/json" if path.endswith(".json") else "text/plain",
                "original_locator": locator,
                "adapter_name": adapter,
                "adapter_version": "1",
                **extra,
            }
        )

    for index, (member, payload) in enumerate(notices):
        retain(
            f"archive-notice-{index}",
            payload,
            "cricsheet",
            "notice",
            ARCHIVE_URL,
            member,
            "source-notice",
        )
    for key, url in (
        ("cricsheet-license", "https://cricsheet.org/licensing/"),
        ("odc-by-license", "https://opendatacommons.org/licenses/by/1-0/"),
    ):
        path = cache / f"{key}.html"
        download(url, path, max_bytes=1024 * 1024)
        retain(key, path.read_bytes(), "cricsheet", "notice", url, "complete HTML", "source-notice")
        artifacts[-1]["media_type"] = "text/html"

    aliases, venue_ids, match_ids = set(), set(), []
    all_dates = []
    for _, filename, member, payload in selected:
        spec_snapshot = SourceSnapshot(
            source_id="00000000-0000-0000-0000-000000000000",
            source_url=ARCHIVE_URL,
            retrieved_at=datetime.now(UTC),
            media_type="application/json",
            original_locator=member,
            adapter_name="cricsheet-json",
            adapter_version="1",
            payload=payload,
        )
        parsed = CricsheetAdapter().parse_match(spec_snapshot)
        aliases.add((parsed.venue, parsed.city))
        if parsed.venue_source_id:
            venue_ids.add(parsed.venue_source_id)
        match_ids.append(parsed.provider_match_id)
        all_dates.extend(parsed.dates)
        retain(
            filename.removesuffix(".json"),
            payload,
            "cricsheet",
            "cricsheet",
            ARCHIVE_URL,
            member,
            "cricsheet-json",
        )
    if len(venue_ids) > 1:
        raise ValueError("Selected source venue IDs disagree; manual registry review required")
    curation = {
        "kind": "BallX manual transcription, not original Wikidata bytes",
        "source_url": GROUND_URL,
        "property": "P625",
        "source_coordinates_dms": "12°58′43.70″N 77°35′58.40″E",
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "timezone": "Asia/Kolkata",
        "timezone_basis": "Reviewed India location",
        "country_code": "IN",
        "ground_name": "M. Chinnaswamy Stadium",
        "reviewed_aliases": sorted(aliases),
        "reviewed_source_venue_id": next(iter(venue_ids), None),
    }
    retain(
        "ground-curation",
        json.dumps(curation, indent=2).encode(),
        "curation",
        "registry",
        GROUND_URL,
        "manual transcription of Q1861907/P625 and reviewed venue aliases",
        "ballx-manual-curation",
    )
    lower = datetime.combine(min(all_dates) - timedelta(days=1), datetime.min.time(), UTC)
    upper = datetime.combine(max(all_dates) + timedelta(days=1), datetime.min.time(), UTC)
    weather_url = request_url(LATITUDE, LONGITUDE, lower, upper)
    weather_path = cache / "nasa-power-hourly.json"
    download(weather_url, weather_path, max_bytes=5 * 1024 * 1024)
    retain(
        "nasa-power-hourly",
        weather_path.read_bytes(),
        "weather",
        "weather",
        weather_url,
        "/properties/parameter",
        "nasa-power-hourly",
        ground_key=GROUND_KEY,
        match_ids=match_ids,
    )
    manifest = SampleManifest.model_validate(
        {
            "schema_version": 1,
            "name": "Five IPL 2008 matches at M. Chinnaswamy Stadium",
            "sources": sources,
            "artifacts": artifacts,
            "grounds": [
                {
                    "key": GROUND_KEY,
                    "name": "M. Chinnaswamy Stadium",
                    "country_code": "IN",
                    "latitude": LATITUDE,
                    "longitude": LONGITUDE,
                    "timezone": "Asia/Kolkata",
                    "evidence_artifact": "ground-curation",
                    "evidence_locator": "Q1861907/P625/manual",
                    "reviewed_facts": curation,
                    "aliases": [{"name": n, "city": c} for n, c in sorted(aliases)],
                    "cricsheet_venue_id": next(iter(venue_ids), None),
                }
            ],
            "expected_matches": 5,
            "expected_weather_matches": 5,
            "professional_scope": "First five chronologically ordered men's IPL 2008 matches at "
            "the explicitly reviewed Bengaluru ground; neither global nor representative.",
            "selection": {
                "archive_url": ARCHIVE_URL,
                "archive_sha256": archive_hash,
                "rule": "fixed venue/city whitelist, IPL event, 2008, T20, male; "
                "date then numeric source ID",
                "selected_provider_match_ids": match_ids,
            },
        }
    )
    manifest.validate_plan()
    (directory / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    attribution = "\n\n".join(s["attribution"] for s in sources.values())
    (directory / "ATTRIBUTION.md").write_text(attribution + "\n")
    return directory / "manifest.json"
