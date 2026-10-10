from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ballx.domain.models import DataSource, RawArtifact
from ballx.ingestion.contracts import SourceSnapshot


def store_snapshot(session: Session, snapshot: SourceSnapshot) -> RawArtifact:
    """Store reviewed, already-retrieved bytes idempotently; caller owns the transaction."""
    source = session.get(DataSource, snapshot.source_id)
    if source is None or source.collection_allowed is not True or source.checked_at is None:
        raise ValueError("Source collection permission must be explicitly reviewed and allowed")
    values = snapshot.model_dump(exclude={"source_url"})
    values.update(source_url=str(snapshot.source_url), sha256=snapshot.sha256)
    session.execute(
        insert(RawArtifact)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["source_id", "source_url", "sha256"])
    )
    return session.scalars(
        select(RawArtifact).where(
            RawArtifact.source_id == snapshot.source_id,
            RawArtifact.source_url == str(snapshot.source_url),
            RawArtifact.sha256 == snapshot.sha256,
        )
    ).one()
