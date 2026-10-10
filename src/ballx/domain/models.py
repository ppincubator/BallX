"""PostgreSQL models. Raw bytes, evidence, and normalized facts remain separate."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ballx.db.base import Base, IdentityMixin

SCHEMA = "gpid"


class Organization(IdentityMixin, Base):
    """Owner/operator identity, distinct from a cricket association."""

    __tablename__ = "organization"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="name"), {"schema": SCHEMA})
    name: Mapped[str] = mapped_column(String(255))


class Association(IdentityMixin, Base):
    __tablename__ = "association"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name"),
        CheckConstraint("length(trim(jurisdiction)) > 0", name="jurisdiction"),
        {"schema": SCHEMA},
    )
    name: Mapped[str] = mapped_column(String(255))
    jurisdiction: Mapped[str] = mapped_column(String(255))


class DataSource(IdentityMixin, Base):
    __tablename__ = "source_registry"
    __table_args__ = (
        UniqueConstraint("url", "provider"),
        CheckConstraint("length(trim(provider)) > 0", name="provider"),
        {"schema": SCHEMA},
    )
    url: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(255))
    terms_url: Mapped[str | None] = mapped_column(Text)
    license: Mapped[str | None] = mapped_column(Text)
    access_status: Mapped[str] = mapped_column(String(64), server_default="unreviewed")
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attribution_required: Mapped[bool | None] = mapped_column(Boolean)
    collection_allowed: Mapped[bool | None] = mapped_column(Boolean)
    notes: Mapped[str | None] = mapped_column(Text)


class RawArtifact(IdentityMixin, Base):
    """Immutable retrieved payload; URL + source + hash identifies duplicate snapshots."""

    __tablename__ = "artifact"
    __table_args__ = (
        UniqueConstraint("source_id", "source_url", "sha256"),
        UniqueConstraint("id", "source_id"),
        CheckConstraint("sha256 = encode(sha256(payload), 'hex')", name="payload_hash"),
        {"schema": "raw"},
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.source_registry.id"))
    source_url: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    media_type: Mapped[str] = mapped_column(String(255))
    original_locator: Mapped[str | None] = mapped_column(Text)
    adapter_name: Mapped[str] = mapped_column(String(255))
    adapter_version: Mapped[str] = mapped_column(String(64))
    sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[bytes] = mapped_column(LargeBinary)


class Evidence(IdentityMixin, Base):
    """Append-only citation or measurement; a correction creates a superseding record."""

    __tablename__ = "evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["artifact_id", "source_id"], ["raw.artifact.id", "raw.artifact.source_id"]
        ),
        CheckConstraint(
            "verification_status IN ('unreviewed', 'verified', 'rejected')", name="verification"
        ),
        CheckConstraint(
            "evidence_type IN ('observed', 'measured', 'modeled', 'proxy', 'experimental')",
            name="evidence_type",
        ),
        CheckConstraint("jsonb_typeof(excerpt_or_measurement) = 'object'", name="content_object"),
        CheckConstraint(
            "supersedes_evidence_id IS NULL OR supersedes_evidence_id != id", name="self"
        ),
        {"schema": SCHEMA},
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.source_registry.id"), index=True)
    artifact_id: Mapped[uuid.UUID | None]
    source_url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    original_locator: Mapped[str] = mapped_column(Text)
    excerpt_or_measurement: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rights_class: Mapped[str] = mapped_column(String(64), server_default="unreviewed")
    verification_status: Mapped[str] = mapped_column(String(32), server_default="unreviewed")
    evidence_type: Mapped[str] = mapped_column(String(32))
    supersedes_evidence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gpid.evidence.id"))


class Ground(IdentityMixin, Base):
    __tablename__ = "ground"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name"),
        CheckConstraint("jsonb_typeof(aliases) = 'array'", name="aliases_array"),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="coordinate_pair"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence"),
        Index("ix_ground_location", "location", postgresql_using="gist"),
        {"schema": SCHEMA},
    )
    name: Mapped[str] = mapped_column(String(255))
    aliases: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    location: Mapped[WKBElement | None] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False),
        Computed(
            "CASE WHEN latitude IS NULL THEN NULL ELSE "
            "ST_SetSRID(ST_MakePoint(longitude::double precision, "
            "latitude::double precision), 4326) END",
            persisted=True,
        ),
    )
    timezone: Mapped[str | None] = mapped_column(String(128))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gpid.organization.id"))
    operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gpid.organization.id"))
    association_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gpid.association.id"), index=True
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))


class PitchStrip(IdentityMixin, Base):
    __tablename__ = "pitch_strip"
    __table_args__ = (
        UniqueConstraint("ground_id", "local_strip_identifier"),
        UniqueConstraint("id", "ground_id"),
        CheckConstraint(
            "local_strip_identifier IS NULL OR length(trim(local_strip_identifier)) > 0",
            name="identifier",
        ),
        CheckConstraint(
            "construction_type IN ('natural', 'hybrid', 'synthetic', 'drop-in', 'unknown')",
            name="construction",
        ),
        CheckConstraint("identity_confidence BETWEEN 0 AND 1", name="identity_confidence"),
        {"schema": SCHEMA},
    )
    ground_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.ground.id"), index=True)
    local_strip_identifier: Mapped[str | None] = mapped_column(String(128))
    construction_type: Mapped[str | None] = mapped_column(String(32))
    identity_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.evidence.id"))


class Match(IdentityMixin, Base):
    __tablename__ = "match"
    __table_args__ = (
        UniqueConstraint("source_id", "provider_match_id"),
        ForeignKeyConstraint(
            ["pitch_id", "ground_id"], ["gpid.pitch_strip.id", "gpid.pitch_strip.ground_id"]
        ),
        CheckConstraint("pitch_id IS NULL OR ground_id IS NOT NULL", name="pitch_requires_ground"),
        CheckConstraint("end_time IS NULL OR end_time >= start_time", name="time_order"),
        CheckConstraint("length(trim(provider_match_id)) > 0", name="provider_match_id"),
        {"schema": SCHEMA},
    )
    provider_match_id: Mapped[str] = mapped_column(String(255))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.source_registry.id"))
    ground_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gpid.ground.id"), index=True)
    pitch_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    format: Mapped[str] = mapped_column(String(64))
    gender_category: Mapped[str | None] = mapped_column(String(64))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    competition: Mapped[str | None] = mapped_column(String(255))


class RecordProvenance(IdentityMixin, Base):
    """Field assertions with real foreign keys; conflicts can coexist for review."""

    __tablename__ = "record_provenance"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(association_id, ground_id, pitch_id, match_id, organization_id) = 1",
            name="one_target",
        ),
        CheckConstraint("length(trim(field_name)) > 0", name="field_name"),
        {"schema": SCHEMA},
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("gpid.evidence.id"), index=True)
    association_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gpid.association.id"))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gpid.organization.id"))
    ground_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gpid.ground.id"), index=True)
    pitch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gpid.pitch_strip.id"), index=True
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gpid.match.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(128))
    asserted_value: Mapped[Any] = mapped_column(JSONB, nullable=False)
