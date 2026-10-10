"""Reviewed ground mappings, immutable import receipts, and modeled atmospheric weather."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Double, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ballx.db.base import Base, IdentityMixin


class GroundAlias(IdentityMixin, Base):
    __tablename__ = "ground_alias"
    __table_args__ = (
        UniqueConstraint("source_id", "normalized_name", "city_key"),
        {"schema": "gpid"},
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.source_registry.id"))
    ground_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.ground.id"))
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.evidence.id"))
    name: Mapped[str] = mapped_column(Text)
    normalized_name: Mapped[str] = mapped_column(Text)
    city_key: Mapped[str] = mapped_column(Text)
    normalization_version: Mapped[str] = mapped_column(String(32))


class GroundSourceIdentity(IdentityMixin, Base):
    __tablename__ = "ground_source_identity"
    __table_args__ = (UniqueConstraint("source_id", "provider_ground_id"), {"schema": "gpid"})
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.source_registry.id"))
    ground_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.ground.id"))
    provider_ground_id: Mapped[str] = mapped_column(String(255))
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.evidence.id"))


class IngestionRun(IdentityMixin, Base):
    __tablename__ = "ingestion_run"
    __table_args__ = ({"schema": "gpid"},)
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    pipeline_version: Mapped[str] = mapped_column(String(32))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class IngestionItem(IdentityMixin, Base):
    __tablename__ = "ingestion_item"
    __table_args__ = (
        CheckConstraint(
            "status IN ('imported', 'duplicate', 'rejected', 'conflict')", name="status"
        ),
        {"schema": "gpid"},
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.ingestion_run.id"), index=True)
    artifact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw.artifact.id"))
    match_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gpid.match.id"))
    provider_record_id: Mapped[str] = mapped_column(String(255))
    record_kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    issues: Mapped[list[str]] = mapped_column(JSONB, default=list)


class WeatherObservation(IdentityMixin, Base):
    __tablename__ = "weather"
    __table_args__ = (
        UniqueConstraint("source_id", "ground_id", "timestamp_utc", "variable", "model"),
        CheckConstraint("observation_kind = 'modeled'", name="modeled_only"),
        CheckConstraint(
            "value IS NULL OR (value > '-Infinity'::float8 AND value < 'Infinity'::float8)",
            name="finite_value",
        ),
        CheckConstraint(
            "variable IN ('T2M', 'RH2M', 'PRECTOTCORR', 'WS10M')", name="atmospheric_only"
        ),
        {"schema": "gpid"},
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.source_registry.id"))
    ground_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.ground.id"), index=True)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    variable: Mapped[str] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Double)
    unit: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(255))
    model: Mapped[str] = mapped_column(String(64))
    station_or_grid_id: Mapped[str | None] = mapped_column(Text)
    model_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB)
    observation_kind: Mapped[str] = mapped_column(String(32), server_default="modeled")
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.evidence.id"))


class MatchWeatherLink(IdentityMixin, Base):
    __tablename__ = "match_weather_link"
    __table_args__ = (
        UniqueConstraint("match_id", "weather_id"),
        CheckConstraint("scope = 'local_calendar_day'", name="scope"),
        {"schema": "gpid"},
    )
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.match.id"), index=True)
    weather_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.weather.id"))
    scope: Mapped[str] = mapped_column(String(64), server_default="local_calendar_day")


class Delivery(IdentityMixin, Base):
    __tablename__ = "delivery"
    __table_args__ = (
        UniqueConstraint("match_id", "innings", "over_index", "delivery_index"),
        CheckConstraint("innings >= 1 AND over_index >= 0 AND delivery_index >= 1", name="indices"),
        {"schema": "gpid"},
    )
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.match.id"), index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.source_registry.id"))
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.evidence.id"))
    innings: Mapped[int]
    over_index: Mapped[int]
    delivery_index: Mapped[int]
    original_locator: Mapped[str] = mapped_column(Text)
    bowler_source_id: Mapped[str | None] = mapped_column(String(64))
    batter_source_id: Mapped[str | None] = mapped_column(String(64))
    event_data: Mapped[dict[str, Any]] = mapped_column(JSONB)
