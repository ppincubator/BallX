"""NASA POWER hourly atmospheric model data; no pitch measurements or soil variables."""

import math
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from pydantic import BaseModel

from ballx.domain.types import EvidenceType
from ballx.ingestion.contracts import EvidenceDraft, SourceSnapshot
from ballx.ingestion.cricsheet import read_json

PARAMETERS = ("T2M", "RH2M", "PRECTOTCORR", "WS10M")
NASA_ENDPOINT = "https://power.larc.nasa.gov/api/temporal/hourly/point"


class WeatherValue(BaseModel):
    timestamp_utc: datetime
    variable: str
    value: float | None
    unit: str
    model: str
    metadata: dict[str, Any]


def request_url(latitude: float, longitude: float, start: datetime, end: datetime) -> str:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180) or end < start:
        raise ValueError("Invalid weather coordinates or time interval")
    return (
        NASA_ENDPOINT
        + "?"
        + urlencode(
            {
                "parameters": ",".join(PARAMETERS),
                "community": "AG",
                "longitude": longitude,
                "latitude": latitude,
                "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
                "format": "JSON",
                "time-standard": "UTC",
            }
        )
    )


class NasaPowerAdapter:
    name = "nasa-power-hourly"
    version = "1"

    def parse_values(self, snapshot: SourceSnapshot) -> list[WeatherValue]:
        response = read_json(snapshot.payload)
        header = response.get("header") or {}
        if str(header.get("time_standard", "")).upper() != "UTC":
            raise ValueError("NASA POWER response must explicitly use UTC")
        fill_value = header.get("fill_value", -999)
        data = (response.get("properties") or {}).get("parameter")
        units = response.get("parameters")
        if not isinstance(data, dict) or not isinstance(units, dict):
            raise ValueError("Missing NASA POWER parameters")
        if set(data) != set(PARAMETERS):
            raise ValueError("Only the four requested atmospheric variables are supported")
        key_sets = [set(data[p]) for p in PARAMETERS]
        if not key_sets[0] or any(keys != key_sets[0] for keys in key_sets):
            raise ValueError("Weather parameter time axes must agree and be nonempty")
        sources = header.get("sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError("NASA model provenance is required")
        model = "+".join(sources)
        metadata = {
            "source_models": sources,
            "api_version": header.get("api"),
            "native_resolution_degrees": {"latitude": 0.5, "longitude": 0.625},
            "time_standard": "UTC",
            "temporal_resolution": "hourly",
            "geometry": response.get("geometry"),
            "geometry_role": "API point coordinates; native grid cell ID not supplied",
            "interpretation": (
                "modeled atmospheric grid estimate, not a ground station or pitch measurement"
            ),
        }
        result = []
        for key in sorted(key_sets[0]):
            if len(key) != 10 or not key.isdigit():
                raise ValueError("Invalid NASA hourly timestamp")
            timestamp = datetime.strptime(key, "%Y%m%d%H").replace(tzinfo=UTC)
            for parameter in PARAMETERS:
                raw = data[parameter][key]
                value = None if raw is None or raw == fill_value else raw
                if value is not None:
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                    ):
                        raise ValueError(
                            "Weather values must be finite numbers or source missing values"
                        )
                    if parameter == "RH2M" and not 0 <= value <= 100:
                        raise ValueError("Invalid relative humidity")
                    if parameter in {"WS10M", "PRECTOTCORR"} and value < 0:
                        raise ValueError("Invalid wind speed or precipitation")
                unit = (units.get(parameter) or {}).get("units")
                if not isinstance(unit, str) or not unit:
                    raise ValueError("Weather source units are required")
                result.append(
                    WeatherValue(
                        timestamp_utc=timestamp,
                        variable=parameter,
                        value=value,
                        unit=unit,
                        model=model,
                        metadata=metadata,
                    )
                )
        return result

    def parse(self, snapshot: SourceSnapshot) -> Iterable[EvidenceDraft]:
        values = self.parse_values(snapshot)
        yield EvidenceDraft(
            original_locator="/properties/parameter",
            excerpt_or_measurement={
                "model_metadata": values[0].metadata,
                "variables": list(PARAMETERS),
            },
            evidence_type=EvidenceType.MODELED,
        )
