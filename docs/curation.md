# Manual curation contract

The database is intentionally empty after migration. There are no licensed-source
seeds or real pilot records. Automated tests use explicitly synthetic fixtures in a
separate test database and roll them back.

The API's writes require existing evidence. For Milestone 1, a researcher can prepare
these records with SQLAlchemy in a trusted local Python session; no public source or
evidence creation endpoint is exposed.

1. Review the source's actual current rights and record `DataSource` provider, URL,
   terms URL, license, access status, review time, attribution and collection decision.
   Leave unknown booleans null. Set `collection_allowed=True` only following a real
   review, not because a URL appears in the repository inventory.
2. When authorized, retain already-retrieved source bytes as a `SourceSnapshot` with
   source URL, aware retrieval time, media type, locator, adapter name and version.
   `store_snapshot(session, snapshot)` stores them without fetching or normalizing.
   It requires both collection permission and a recorded review time.
3. Create `Evidence` with source and optional artifact IDs, exact locator, source URL,
   retrieval/published times, excerpt or source-supplied measurement JSON, rights class,
   and evidence type. Store only content whose retention is permitted. A locator-only
   citation can omit `artifact_id` when retaining the source bytes is inappropriate.
4. A human reviewer checks the assertion and sets its initial `verification_status`
   accurately. New evidence is unreviewed by default. Once inserted, review changes
   or factual corrections require a new evidence record with `supersedes_evidence_id`;
   the old record cannot be modified.
5. Create grounds only from evidence supporting their identity and every supplied
   field. Create strips only where evidence identifies distinct physical strips.
   A verified venue citation does not establish strip identity. Null local labels
   mean a documented distinct strip lacks an available label; they do not authorize
   a placeholder strip for every ground.
6. Submit a ground or pitch through the API with the appropriate evidence UUID.
   If different fields have different evidence, use the minimal supported API payload;
   richer multi-evidence curation requires a reviewed future service. API writes add
   one provenance assertion for each supplied non-null field.

Available Python interfaces:

```python
from sqlalchemy.orm import Session
from ballx.db.session import get_engine
from ballx.domain.models import DataSource, Evidence, Association, Organization, Match
from ballx.ingestion.contracts import SourceSnapshot
from ballx.ingestion.storage import store_snapshot

# Fill models only with actual, reviewed facts. This example performs no data writes.
with Session(get_engine()) as session:
    with session.begin():
        # Add reviewed source/evidence records using the fields documented above.
        # Use session.flush() to obtain their UUIDs before linking records.
        pass
```

Direct ORM creation of associations, organizations, or matches must also explicitly
write `RecordProvenance` assertions. `Match.source_id` records provider provenance;
its individual field evidence belongs in `RecordProvenance`. A match without strip
evidence retains `pitch_id=None`, even when the ground has known strip records.
Never transfer a regional soil label, a modeled weather grid value, or an experimental
soil result into a measured pitch assertion.

The app verifies existence, declared review status, evidence class, and referential
integrity. It does not inspect source meaning or replace researcher verification.
Correction reconciliation, reviewer audit identities, and duplicate unnamed-strip
resolution are outstanding specifications, listed in `research-blockers.md`.
