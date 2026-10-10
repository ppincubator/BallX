"""Small, explicit replay manifests with reviewed rights and byte-level source identity."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, field_validator

from ballx.ingestion.contracts import SourceSnapshot
from ballx.ingestion.cricsheet import read_json


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewedSource(StrictModel):
    provider: str
    url: HttpUrl
    terms_url: HttpUrl
    license: str
    reviewed_at: AwareDatetime
    collection_allowed: Literal[True]
    attribution_required: bool
    attribution: str = Field(min_length=1)
    review_notes: str = Field(min_length=1)


class ArtifactSpec(StrictModel):
    key: str
    source: str
    kind: Literal["cricsheet", "weather", "registry", "notice"]
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_url: HttpUrl
    retrieved_at: AwareDatetime
    media_type: str
    original_locator: str
    adapter_name: str
    adapter_version: str
    match_ids: list[str] = Field(default_factory=list)
    ground_key: str | None = None

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("Artifact paths must stay inside the manifest directory")
        return value


class AliasSpec(StrictModel):
    name: str = Field(min_length=1)
    city: str = Field(min_length=1)


class GroundSpec(StrictModel):
    key: str
    name: str
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    timezone: str
    evidence_artifact: str
    evidence_locator: str
    reviewed_facts: dict
    aliases: list[AliasSpec] = Field(min_length=1)
    cricsheet_venue_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{8}$")

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        ZoneInfo(value)
        return value


class SampleManifest(StrictModel):
    schema_version: Literal[1]
    name: str
    sources: dict[str, ReviewedSource]
    artifacts: list[ArtifactSpec]
    grounds: list[GroundSpec]
    expected_matches: int = Field(ge=1, le=25)
    expected_weather_matches: int = Field(ge=0, le=25)
    professional_scope: str
    selection: dict = Field(default_factory=dict)

    def validate_plan(self, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        keys = [a.key for a in self.artifacts]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate artifact keys")
        if len({g.key for g in self.grounds}) != len(self.grounds):
            raise ValueError("Duplicate curated ground keys")
        matches = [a for a in self.artifacts if a.kind == "cricsheet"]
        if "cricsheet" not in self.sources:
            raise ValueError("A reviewed Cricsheet source is required")
        if self.expected_weather_matches > self.expected_matches:
            raise ValueError("Weather coverage cannot exceed the selected matches")
        if len({a.original_locator for a in matches}) != len(matches):
            raise ValueError("Duplicate source match members in plan")
        if len(matches) != self.expected_matches or len(matches) > 25:
            raise ValueError("Explicit match count differs from the bounded plan")
        if len([a for a in self.artifacts if a.kind == "weather"]) > 10:
            raise ValueError("At most ten bounded weather responses are supported")
        for source in self.sources.values():
            age = (now - source.reviewed_at).total_seconds()
            if age < -86400 or age > 90 * 86400:
                raise ValueError("Source terms review must be renewed after 90 days")
        for artifact in self.artifacts:
            if artifact.source not in self.sources:
                raise ValueError("Artifact references an unreviewed source")
            expected = {
                "cricsheet": ("cricsheet-json", "1"),
                "weather": ("nasa-power-hourly", "1"),
            }.get(artifact.kind)
            if expected and (artifact.adapter_name, artifact.adapter_version) != expected:
                raise ValueError("Unknown adapter identity or version")
            if artifact.kind == "cricsheet" and artifact.source != "cricsheet":
                raise ValueError("Cricsheet matches require the reviewed Cricsheet source")
            if artifact.kind == "weather" and (
                not artifact.match_ids or len(artifact.match_ids) != len(set(artifact.match_ids))
            ):
                raise ValueError("Weather requires unique, explicit match targets")
        for ground in self.grounds:
            if ground.evidence_artifact not in keys:
                raise ValueError("Ground mapping has no retained curation artifact")


def load_manifest(path: Path) -> tuple[SampleManifest, str]:
    payload = path.read_bytes()
    manifest = SampleManifest.model_validate(read_json(payload))
    manifest.validate_plan()
    return manifest, hashlib.sha256(payload).hexdigest()


def load_payload(directory: Path, artifact: ArtifactSpec) -> bytes:
    path = (directory / artifact.path).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise ValueError("Artifact symlink escapes manifest directory")
    if path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("Selected artifact exceeds the 5 MiB bound")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != artifact.sha256:
        raise ValueError(f"Source byte hash mismatch: {artifact.key}")
    return payload


def snapshot(artifact: ArtifactSpec, source_id, payload: bytes) -> SourceSnapshot:
    return SourceSnapshot(
        source_id=source_id,
        source_url=artifact.source_url,
        retrieved_at=artifact.retrieved_at,
        media_type=artifact.media_type,
        original_locator=artifact.original_locator,
        adapter_name=artifact.adapter_name,
        adapter_version=artifact.adapter_version,
        payload=payload,
    )
