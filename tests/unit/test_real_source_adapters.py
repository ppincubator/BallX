import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from ballx.ingestion.contracts import SourceSnapshot
from ballx.ingestion.cricsheet import CricsheetAdapter, name_key, read_json
from ballx.ingestion.http import download
from ballx.ingestion.manifest import load_manifest, load_payload
from ballx.ingestion.nasa_power import NasaPowerAdapter, request_url
from tests.ingestion_fixtures import match_record, weather_record, write_manifest


def snapshot(record, locator="123456.json"):
    return SourceSnapshot(
        source_id=uuid.uuid4(),
        source_url="https://cricsheet.org/downloads/fixture.zip",
        retrieved_at=datetime.now(UTC),
        media_type="application/json",
        original_locator=locator,
        adapter_name="synthetic",
        adapter_version="1",
        payload=json.dumps(record).encode(),
    )


def test_cricsheet_identity_dates_and_delivery_positions():
    parsed = CricsheetAdapter().parse_match(snapshot(match_record()))
    assert parsed.provider_match_id == "123456"
    assert parsed.dates[0].isoformat() == "2008-04-18"
    assert len(parsed.deliveries) == 2
    assert [d.delivery_index for d in parsed.deliveries] == [1, 2]
    assert parsed.deliveries[0].event_data["extras"] == {"wides": 1}
    assert parsed.deliveries[0].batter_source_id == "12345678"


def test_missing_venue_is_unknown_and_stable_id_is_preserved():
    record = match_record()
    del record["info"]["venue"]
    parsed = CricsheetAdapter().parse_match(snapshot(record))
    assert parsed.venue is None
    assert "missing_venue" in parsed.issues
    record["meta"]["data_version"] = "1.3.0"
    record["info"]["venue"] = "Synthetic Ground"
    record["info"]["registry"]["venues"] = {"Synthetic Ground": "87654321"}
    assert CricsheetAdapter().parse_match(snapshot(record)).venue_source_id == "87654321"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r["meta"].update(data_version="9.0.0"),
        lambda r: r["info"].update(dates=[]),
        lambda r: r["info"].update(dates=["2008-04-18", "2008-04-18"]),
        lambda r: r["info"].update(teams=["A"]),
        lambda r: r["innings"][0]["overs"][0]["deliveries"][0]["runs"].update(total=99),
        lambda r: r["innings"][0].update(overs=None),
    ],
)
def test_invalid_match_is_rejected(mutation):
    record = match_record()
    mutation(record)
    with pytest.raises(ValueError):
        CricsheetAdapter().parse_match(snapshot(record))


@pytest.mark.parametrize("payload", [b'{"x":1,"x":2}', b'{"x":NaN}', b"[]"])
def test_json_does_not_silently_overwrite_or_accept_nonfinite(payload):
    with pytest.raises(ValueError):
        read_json(payload)


def test_name_key_is_conservative():
    assert name_key("  SYNTHETIC\t Ground ") == "synthetic ground"
    assert name_key("M. Ground") != name_key("M Ground")


def test_weather_missing_values_and_model_provenance():
    record = weather_record()
    record["properties"]["parameter"]["T2M"]["2008041700"] = -999
    values = NasaPowerAdapter().parse_values(snapshot(record))
    assert len(values) == 72 * 4
    assert values[0].value is None
    assert values[0].timestamp_utc.tzinfo == UTC
    assert values[0].metadata["native_resolution_degrees"]["longitude"] == 0.625
    assert values[0].model == "MERRA2"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r["header"].update(time_standard="LST"),
        lambda r: r["properties"]["parameter"].update(SOIL_MOISTURE={}),
        lambda r: r["properties"]["parameter"]["RH2M"].update({"2008041700": 200}),
        lambda r: r["properties"]["parameter"]["WS10M"].pop("2008041700"),
        lambda r: r["parameters"]["T2M"].pop("units"),
    ],
)
def test_invalid_weather_or_soil_is_rejected(mutation):
    record = weather_record()
    mutation(record)
    with pytest.raises(ValueError):
        NasaPowerAdapter().parse_values(snapshot(record))


def test_weather_request_is_explicitly_utc_and_atmospheric():
    query = parse_qs(
        urlsplit(request_url(12.5, 77.5, datetime(2008, 4, 17), datetime(2008, 4, 19))).query
    )
    assert query["time-standard"] == ["UTC"]
    assert query["parameters"] == ["T2M,RH2M,PRECTOTCORR,WS10M"]


def test_manifest_pins_source_bytes_and_stale_terms(tmp_path):
    manifest = write_manifest(tmp_path)
    loaded, digest = load_manifest(tmp_path / "manifest.json")
    assert len(digest) == 64
    assert loaded == manifest
    spec = manifest.artifacts[1]
    (tmp_path / spec.path).write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_payload(tmp_path, spec)
    manifest.sources["cricsheet"].reviewed_at = datetime.now(UTC) - timedelta(days=91)
    with pytest.raises(ValueError, match="90 days"):
        manifest.validate_plan()


def test_manifest_rejects_path_escape_and_duplicate_match(tmp_path):
    manifest = write_manifest(tmp_path)
    with pytest.raises(ValueError):
        type(manifest.artifacts[0]).model_validate(
            {**manifest.artifacts[0].model_dump(), "path": "../outside"}
        )
    manifest.artifacts.append(manifest.artifacts[1])
    with pytest.raises(ValueError):
        manifest.validate_plan()


def test_download_hash_and_bounds(tmp_path):
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"real bytes"))
    )
    path = tmp_path / "snapshot"
    digest = hashlib.sha256(b"real bytes").hexdigest()
    assert (
        download(
            "https://cricsheet.org/downloads/sample", path, client=client, expected_sha256=digest
        )
        == digest
    )
    assert path.read_bytes() == b"real bytes"
    with pytest.raises(ValueError, match="bound"):
        download("https://cricsheet.org/downloads/sample", path, client=client, max_bytes=2)
    assert path.read_bytes() == b"real bytes"
    with pytest.raises(ValueError, match="pinned"):
        download(
            "https://cricsheet.org/downloads/sample", path, client=client, expected_sha256="0" * 64
        )
    with pytest.raises(ValueError, match="HTTPS"):
        download("https://unreviewed.test/file", path, client=client)
