import hashlib
import json
import zipfile
from datetime import UTC, datetime, timedelta

import pytest

from ballx.ingestion.manifest import load_manifest, load_payload
from ballx.ingestion.pilot import ARCHIVE_URL, LATITUDE, LONGITUDE, prepare, select_members
from tests.ingestion_fixtures import match_record, weather_record


def archive(path, count=6):
    with zipfile.ZipFile(path, "w") as output:
        for i in reversed(range(count)):
            record = match_record()
            record["info"].update(
                venue="M Chinnaswamy Stadium",
                city="Bangalore",
                event={"name": "Indian Premier League"},
                dates=[f"2008-04-{18 + i:02}"],
            )
            output.writestr(f"{100000 + i}.json", json.dumps(record))
        output.writestr("README.txt", "Synthetic archive notice")


def test_annual_selection_is_explicit_ordered_and_bounded(tmp_path):
    path = tmp_path / "annual.zip"
    archive(path)
    selected, notices = select_members(path)
    assert len(selected) == 5
    assert [s[1] for s in selected] == [f"{100000 + i}.json" for i in range(5)]
    assert notices == [("README.txt", b"Synthetic archive notice")]
    assert selected[0][3] == zipfile.ZipFile(path).read("100000.json")


def test_selection_does_not_fill_missing_real_matches(tmp_path):
    path = tmp_path / "annual.zip"
    archive(path, count=4)
    with pytest.raises(ValueError, match="five matches"):
        select_members(path)


def test_prepare_pins_original_bytes_and_does_not_overwrite(tmp_path, monkeypatch):
    path = tmp_path / "annual.zip"
    archive(path)

    def fake_download(url, destination, **kwargs):
        if url == ARCHIVE_URL:
            payload = path.read_bytes()
        elif "hourly/point" in url:
            weather = weather_record()
            weather["geometry"]["coordinates"] = [LONGITUDE, LATITUDE, 0]
            payload = json.dumps(weather).encode()
        else:
            payload = b"Synthetic license notice fixture"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return hashlib.sha256(payload).hexdigest()

    monkeypatch.setattr("ballx.ingestion.pilot.download", fake_download)
    output = tmp_path / "frozen"
    manifest_path = prepare(output, tmp_path / "cache")
    manifest, _ = load_manifest(manifest_path)
    assert manifest.expected_matches == 5
    assert manifest.expected_weather_matches == 5
    for spec in manifest.artifacts:
        load_payload(output, spec)
    first = next(a for a in manifest.artifacts if a.key == "100000")
    assert load_payload(output, first) == zipfile.ZipFile(path).read("100000.json")
    assert "Cricsheet" in (output / "ATTRIBUTION.md").read_text()
    with pytest.raises(ValueError, match="already frozen"):
        prepare(output, tmp_path / "cache")


def test_prepare_stops_on_expired_rights_review(tmp_path, monkeypatch):
    monkeypatch.setattr("ballx.ingestion.pilot.REVIEWED_AT", datetime.now(UTC) - timedelta(days=91))
    with pytest.raises(ValueError, match="review expired"):
        prepare(tmp_path / "frozen", tmp_path / "cache")
