import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ballx.api.schemas import (
    GroundCreate,
    GroundRead,
    PitchCreate,
    PitchRead,
    ProvenanceRead,
)
from ballx.db.session import get_session
from ballx.domain.models import Ground, PitchStrip, RecordProvenance
from ballx.domain.services import create_ground, create_pitch

router = APIRouter()
Database = Annotated[Session, Depends(get_session)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", tags=["health"])
def ready(session: Database) -> dict[str, str]:
    try:
        session.execute(text("SELECT PostGIS_Version()"))
        session.execute(select(Ground.id).limit(1))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database or migrated schema is unavailable") from exc
    return {"status": "ready"}


@router.post("/api/v1/grounds", response_model=GroundRead, status_code=201, tags=["grounds"])
def post_ground(data: GroundCreate, session: Database, response: Response) -> Ground:
    ground = create_ground(session, data)
    response.headers["Location"] = f"/api/v1/grounds/{ground.id}"
    return ground


@router.get("/api/v1/grounds", response_model=list[GroundRead], tags=["grounds"])
def list_grounds(session: Database, limit: Limit = 50, offset: Offset = 0) -> list[Ground]:
    return list(session.scalars(select(Ground).order_by(Ground.id).limit(limit).offset(offset)))


@router.get("/api/v1/grounds/{ground_id}", response_model=GroundRead, tags=["grounds"])
def get_ground(ground_id: uuid.UUID, session: Database) -> Ground:
    ground = session.get(Ground, ground_id)
    if ground is None:
        raise HTTPException(404, "Ground not found")
    return ground


@router.get(
    "/api/v1/grounds/{ground_id}/provenance", response_model=list[ProvenanceRead], tags=["grounds"]
)
def ground_provenance(
    ground_id: uuid.UUID, session: Database, limit: Limit = 50, offset: Offset = 0
) -> list[RecordProvenance]:
    get_ground(ground_id, session)
    return list(
        session.scalars(
            select(RecordProvenance)
            .where(RecordProvenance.ground_id == ground_id)
            .order_by(RecordProvenance.created_at, RecordProvenance.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.post("/api/v1/pitches", response_model=PitchRead, status_code=201, tags=["pitches"])
def post_pitch(data: PitchCreate, session: Database, response: Response) -> PitchStrip:
    pitch = create_pitch(session, data)
    response.headers["Location"] = f"/api/v1/pitches/{pitch.id}"
    return pitch


@router.get("/api/v1/pitches", response_model=list[PitchRead], tags=["pitches"])
def list_pitches(
    session: Database, ground_id: uuid.UUID | None = None, limit: Limit = 50, offset: Offset = 0
) -> list[PitchStrip]:
    statement = select(PitchStrip)
    if ground_id is not None:
        get_ground(ground_id, session)
        statement = statement.where(PitchStrip.ground_id == ground_id)
    return list(session.scalars(statement.order_by(PitchStrip.id).limit(limit).offset(offset)))


@router.get("/api/v1/pitches/{pitch_id}", response_model=PitchRead, tags=["pitches"])
def get_pitch(pitch_id: uuid.UUID, session: Database) -> PitchStrip:
    pitch = session.get(PitchStrip, pitch_id)
    if pitch is None:
        raise HTTPException(404, "Pitch strip not found")
    return pitch


@router.get(
    "/api/v1/pitches/{pitch_id}/provenance", response_model=list[ProvenanceRead], tags=["pitches"]
)
def pitch_provenance(
    pitch_id: uuid.UUID, session: Database, limit: Limit = 50, offset: Offset = 0
) -> list[RecordProvenance]:
    get_pitch(pitch_id, session)
    return list(
        session.scalars(
            select(RecordProvenance)
            .where(RecordProvenance.pitch_id == pitch_id)
            .order_by(RecordProvenance.created_at, RecordProvenance.id)
            .limit(limit)
            .offset(offset)
        )
    )
