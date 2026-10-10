from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ballx.api.schemas import GroundCreate, PitchCreate
from ballx.domain.models import Evidence, Ground, PitchStrip, RecordProvenance


class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        self.message = message
        self.status_code = status_code


def get_identity_evidence(session: Session, evidence_id: Any) -> Evidence:
    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        raise DomainError("Evidence record does not exist")
    if evidence.verification_status != "verified":
        raise DomainError("Identity evidence must be verified")
    if evidence.evidence_type not in {"observed", "measured"}:
        raise DomainError(
            "Identity cannot be assigned from modeled, proxy, or experimental evidence"
        )
    return evidence


def commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DomainError("Record conflicts with an existing identity or reference", 409) from exc


def add_field_provenance(
    session: Session, evidence_id: Any, target: dict[str, Any], fields: dict[str, Any]
) -> None:
    for field_name, value in fields.items():
        if value is not None and value != []:
            session.add(
                RecordProvenance(
                    evidence_id=evidence_id, field_name=field_name, asserted_value=value, **target
                )
            )


def create_ground(session: Session, data: GroundCreate) -> Ground:
    get_identity_evidence(session, data.evidence_id)
    ground = Ground(**data.model_dump(exclude={"evidence_id"}))
    session.add(ground)
    try:
        session.flush()
        add_field_provenance(
            session,
            data.evidence_id,
            {"ground_id": ground.id},
            data.model_dump(mode="json", exclude={"evidence_id"}),
        )
        commit(session)
    except IntegrityError as exc:
        session.rollback()
        raise DomainError("Ground references an unknown organization or association", 409) from exc
    session.refresh(ground)
    return ground


def create_pitch(session: Session, data: PitchCreate) -> PitchStrip:
    if session.get(Ground, data.ground_id) is None:
        raise DomainError("Ground does not exist", 404)
    get_identity_evidence(session, data.evidence_id)
    pitch = PitchStrip(**data.model_dump())
    session.add(pitch)
    try:
        session.flush()
        add_field_provenance(
            session,
            data.evidence_id,
            {"pitch_id": pitch.id},
            data.model_dump(mode="json", exclude={"evidence_id"}),
        )
        commit(session)
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "A strip with this local identifier already exists at this ground", 409
        ) from exc
    session.refresh(pitch)
    return pitch
