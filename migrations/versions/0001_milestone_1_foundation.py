"""Milestone 1 foundation

Revision ID: 0001
Revises:
"""

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE SCHEMA gpid")
    op.execute("CREATE SCHEMA raw")
    op.create_table(
        "association",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("jurisdiction", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(jurisdiction)) > 0", name=op.f("ck_association_jurisdiction")
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_association_name")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_association")),
        schema="gpid",
    )
    op.create_table(
        "organization",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_organization_name")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization")),
        schema="gpid",
    )
    op.create_table(
        "source_registry",
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=255), nullable=False),
        sa.Column("terms_url", sa.Text(), nullable=True),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column(
            "access_status", sa.String(length=64), server_default="unreviewed", nullable=False
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attribution_required", sa.Boolean(), nullable=True),
        sa.Column("collection_allowed", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(trim(provider)) > 0", name=op.f("ck_source_registry_provider")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_registry")),
        sa.UniqueConstraint("url", "provider", name=op.f("uq_source_registry_url")),
        schema="gpid",
    )
    op.create_table(
        "ground",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("latitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=10, scale=7), nullable=True),
        sa.Column(
            "location",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            sa.Computed(
                "CASE WHEN latitude IS NULL THEN NULL ELSE "
                "ST_SetSRID(ST_MakePoint(longitude::double precision, "
                "latitude::double precision), 4326) END",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("timezone", sa.String(length=128), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("association_id", sa.Uuid(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("jsonb_typeof(aliases) = 'array'", name=op.f("ck_ground_aliases_array")),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)", name=op.f("ck_ground_coordinate_pair")
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name=op.f("ck_ground_confidence")),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name=op.f("ck_ground_latitude")),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_ground_name")),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name=op.f("ck_ground_longitude")),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["gpid.association.id"],
            name=op.f("fk_ground_association_id_association"),
        ),
        sa.ForeignKeyConstraint(
            ["operator_id"],
            ["gpid.organization.id"],
            name=op.f("fk_ground_operator_id_organization"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["gpid.organization.id"], name=op.f("fk_ground_owner_id_organization")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ground")),
        schema="gpid",
    )
    op.create_index(
        op.f("ix_ground_association_id"), "ground", ["association_id"], unique=False, schema="gpid"
    )
    op.create_index(
        "ix_ground_location",
        "ground",
        ["location"],
        unique=False,
        schema="gpid",
        postgresql_using="gist",
    )
    op.create_table(
        "artifact",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("original_locator", sa.Text(), nullable=True),
        sa.Column("adapter_name", sa.String(length=255), nullable=False),
        sa.Column("adapter_version", sa.String(length=64), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sha256 = encode(sha256(payload), 'hex')", name=op.f("ck_artifact_payload_hash")
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["gpid.source_registry.id"],
            name=op.f("fk_artifact_source_id_source_registry"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact")),
        sa.UniqueConstraint("id", "source_id", name=op.f("uq_artifact_id")),
        sa.UniqueConstraint(
            "source_id", "source_url", "sha256", name=op.f("uq_artifact_source_id")
        ),
        schema="raw",
    )
    op.create_table(
        "evidence",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_locator", sa.Text(), nullable=False),
        sa.Column(
            "excerpt_or_measurement", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "rights_class", sa.String(length=64), server_default="unreviewed", nullable=False
        ),
        sa.Column(
            "verification_status", sa.String(length=32), server_default="unreviewed", nullable=False
        ),
        sa.Column("evidence_type", sa.String(length=32), nullable=False),
        sa.Column("supersedes_evidence_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "evidence_type IN ('observed', 'measured', 'modeled', 'proxy', 'experimental')",
            name=op.f("ck_evidence_evidence_type"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(excerpt_or_measurement) = 'object'",
            name=op.f("ck_evidence_content_object"),
        ),
        sa.CheckConstraint(
            "verification_status IN ('unreviewed', 'verified', 'rejected')",
            name=op.f("ck_evidence_verification"),
        ),
        sa.CheckConstraint(
            "supersedes_evidence_id IS NULL OR supersedes_evidence_id != id",
            name=op.f("ck_evidence_self"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id", "source_id"],
            ["raw.artifact.id", "raw.artifact.source_id"],
            name=op.f("fk_evidence_artifact_id_artifact"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["gpid.source_registry.id"],
            name=op.f("fk_evidence_source_id_source_registry"),
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_evidence_id"],
            ["gpid.evidence.id"],
            name=op.f("fk_evidence_supersedes_evidence_id_evidence"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
        schema="gpid",
    )
    op.create_index(
        op.f("ix_evidence_source_id"), "evidence", ["source_id"], unique=False, schema="gpid"
    )
    op.create_table(
        "pitch_strip",
        sa.Column("ground_id", sa.Uuid(), nullable=False),
        sa.Column("local_strip_identifier", sa.String(length=128), nullable=True),
        sa.Column("construction_type", sa.String(length=32), nullable=True),
        sa.Column("identity_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "construction_type IN ('natural', 'hybrid', 'synthetic', 'drop-in', 'unknown')",
            name=op.f("ck_pitch_strip_construction"),
        ),
        sa.CheckConstraint(
            "identity_confidence BETWEEN 0 AND 1", name=op.f("ck_pitch_strip_identity_confidence")
        ),
        sa.CheckConstraint(
            "local_strip_identifier IS NULL OR length(trim(local_strip_identifier)) > 0",
            name=op.f("ck_pitch_strip_identifier"),
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["gpid.evidence.id"], name=op.f("fk_pitch_strip_evidence_id_evidence")
        ),
        sa.ForeignKeyConstraint(
            ["ground_id"], ["gpid.ground.id"], name=op.f("fk_pitch_strip_ground_id_ground")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pitch_strip")),
        sa.UniqueConstraint(
            "ground_id", "local_strip_identifier", name=op.f("uq_pitch_strip_ground_id")
        ),
        sa.UniqueConstraint("id", "ground_id", name=op.f("uq_pitch_strip_id")),
        schema="gpid",
    )
    op.create_index(
        op.f("ix_pitch_strip_ground_id"), "pitch_strip", ["ground_id"], unique=False, schema="gpid"
    )
    op.create_table(
        "match",
        sa.Column("provider_match_id", sa.String(length=255), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("ground_id", sa.Uuid(), nullable=True),
        sa.Column("pitch_id", sa.Uuid(), nullable=True),
        sa.Column("format", sa.String(length=64), nullable=False),
        sa.Column("gender_category", sa.String(length=64), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("competition", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "end_time IS NULL OR end_time >= start_time", name=op.f("ck_match_time_order")
        ),
        sa.CheckConstraint(
            "length(trim(provider_match_id)) > 0", name=op.f("ck_match_provider_match_id")
        ),
        sa.CheckConstraint(
            "pitch_id IS NULL OR ground_id IS NOT NULL", name=op.f("ck_match_pitch_requires_ground")
        ),
        sa.ForeignKeyConstraint(
            ["ground_id"], ["gpid.ground.id"], name=op.f("fk_match_ground_id_ground")
        ),
        sa.ForeignKeyConstraint(
            ["pitch_id", "ground_id"],
            ["gpid.pitch_strip.id", "gpid.pitch_strip.ground_id"],
            name=op.f("fk_match_pitch_id_pitch_strip"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["gpid.source_registry.id"],
            name=op.f("fk_match_source_id_source_registry"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_match")),
        sa.UniqueConstraint("source_id", "provider_match_id", name=op.f("uq_match_source_id")),
        schema="gpid",
    )
    op.create_index(op.f("ix_match_ground_id"), "match", ["ground_id"], unique=False, schema="gpid")
    op.create_index(op.f("ix_match_pitch_id"), "match", ["pitch_id"], unique=False, schema="gpid")
    op.create_table(
        "record_provenance",
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("association_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("ground_id", sa.Uuid(), nullable=True),
        sa.Column("pitch_id", sa.Uuid(), nullable=True),
        sa.Column("match_id", sa.Uuid(), nullable=True),
        sa.Column("field_name", sa.String(length=128), nullable=False),
        sa.Column("asserted_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(field_name)) > 0", name=op.f("ck_record_provenance_field_name")
        ),
        sa.CheckConstraint(
            "num_nonnulls(association_id, ground_id, pitch_id, match_id, organization_id) = 1",
            name=op.f("ck_record_provenance_one_target"),
        ),
        sa.ForeignKeyConstraint(
            ["association_id"],
            ["gpid.association.id"],
            name=op.f("fk_record_provenance_association_id_association"),
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["gpid.evidence.id"],
            name=op.f("fk_record_provenance_evidence_id_evidence"),
        ),
        sa.ForeignKeyConstraint(
            ["ground_id"], ["gpid.ground.id"], name=op.f("fk_record_provenance_ground_id_ground")
        ),
        sa.ForeignKeyConstraint(
            ["match_id"], ["gpid.match.id"], name=op.f("fk_record_provenance_match_id_match")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["gpid.organization.id"],
            name=op.f("fk_record_provenance_organization_id_organization"),
        ),
        sa.ForeignKeyConstraint(
            ["pitch_id"],
            ["gpid.pitch_strip.id"],
            name=op.f("fk_record_provenance_pitch_id_pitch_strip"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_record_provenance")),
        schema="gpid",
    )
    op.create_index(
        op.f("ix_record_provenance_evidence_id"),
        "record_provenance",
        ["evidence_id"],
        unique=False,
        schema="gpid",
    )
    op.create_index(
        op.f("ix_record_provenance_ground_id"),
        "record_provenance",
        ["ground_id"],
        unique=False,
        schema="gpid",
    )
    op.create_index(
        op.f("ix_record_provenance_match_id"),
        "record_provenance",
        ["match_id"],
        unique=False,
        schema="gpid",
    )
    op.create_index(
        op.f("ix_record_provenance_pitch_id"),
        "record_provenance",
        ["pitch_id"],
        unique=False,
        schema="gpid",
    )
    op.execute("""
        CREATE FUNCTION gpid.reject_evidence_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Evidence, provenance, and raw artifacts are append-only'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    for table in ("raw.artifact", "gpid.evidence", "gpid.record_provenance"):
        op.execute(f"""
            CREATE TRIGGER protect_mutation BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION gpid.reject_evidence_mutation()
        """)
        op.execute(f"""
            CREATE TRIGGER protect_truncate BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION gpid.reject_evidence_mutation()
        """)
    op.execute("""
        CREATE FUNCTION gpid.require_strip_identity_evidence() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM gpid.evidence
                WHERE id = NEW.evidence_id AND verification_status = 'verified'
                    AND evidence_type IN ('observed', 'measured')
            ) THEN
                RAISE EXCEPTION 'Strip identity requires verified observed or measured evidence'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER verify_strip_identity BEFORE INSERT OR UPDATE ON gpid.pitch_strip
        FOR EACH ROW EXECUTE FUNCTION gpid.require_strip_identity_evidence()
    """)


def downgrade() -> None:
    op.drop_index(
        op.f("ix_record_provenance_pitch_id"), table_name="record_provenance", schema="gpid"
    )
    op.drop_index(
        op.f("ix_record_provenance_match_id"), table_name="record_provenance", schema="gpid"
    )
    op.drop_index(
        op.f("ix_record_provenance_ground_id"), table_name="record_provenance", schema="gpid"
    )
    op.drop_index(
        op.f("ix_record_provenance_evidence_id"), table_name="record_provenance", schema="gpid"
    )
    op.drop_table("record_provenance", schema="gpid")
    op.drop_index(op.f("ix_match_pitch_id"), table_name="match", schema="gpid")
    op.drop_index(op.f("ix_match_ground_id"), table_name="match", schema="gpid")
    op.drop_table("match", schema="gpid")
    op.drop_index(op.f("ix_pitch_strip_ground_id"), table_name="pitch_strip", schema="gpid")
    op.drop_table("pitch_strip", schema="gpid")
    op.drop_index(op.f("ix_evidence_source_id"), table_name="evidence", schema="gpid")
    op.drop_table("evidence", schema="gpid")
    op.drop_table("artifact", schema="raw")
    op.drop_index("ix_ground_location", table_name="ground", schema="gpid", postgresql_using="gist")
    op.drop_index(op.f("ix_ground_association_id"), table_name="ground", schema="gpid")
    op.drop_table("ground", schema="gpid")
    op.drop_table("source_registry", schema="gpid")
    op.drop_table("organization", schema="gpid")
    op.drop_table("association", schema="gpid")
    op.execute("DROP FUNCTION gpid.require_strip_identity_evidence()")
    op.execute("DROP FUNCTION gpid.reject_evidence_mutation()")
    op.execute("DROP SCHEMA raw")
    op.execute("DROP SCHEMA gpid")
    # PostGIS may be shared by other applications; retain the extension on downgrade.
