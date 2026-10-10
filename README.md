# BallX — Global Pitch Intelligence Database

Milestone 1 provides a Python 3.12+ modular FastAPI service, SQLAlchemy models,
Alembic migrations, PostgreSQL 16/PostGIS, provenance, and automated tests.
The database starts empty. Ground and individual physical pitch strip are separate
entities; an unknown match strip remains `NULL`.

The research specification is [BALLX_CODEX_HANDOFF.md](BALLX_CODEX_HANDOFF.md),
[SOURCE_REGISTRY.md](SOURCE_REGISTRY.md), and [SOURCE_INVENTORY.csv](SOURCE_INVENTORY.csv).
These are preliminary research inputs, not a validated global dataset or approved
source permissions. See [architecture and scope](docs/architecture.md),
[research blockers](docs/research-blockers.md), and [actual validation results](docs/validation.md).
Milestone 1 was merged in PR #1. Milestone 2 adds a bounded Cricsheet JSON replay
pipeline and NASA POWER atmospheric weather adapter. Its real-data validation is
pending provider network access; synthetic tests are not real imported matches.
See [Milestone 2 execution and status](docs/milestone2.md).

## Start with Docker Compose

Requirements: Docker Engine with Compose v2. This configuration is for local
development; API and database ports bind to `127.0.0.1`.

```bash
cp .env.example .env
docker compose up --build -d --wait
docker compose ps -a
curl --fail http://localhost:8000/health/ready
```

Compose starts PostGIS, runs `alembic upgrade head` as a one-shot `migrate` service,
then starts the API. An exited `migrate` container with exit code 0 is expected.
Open [Swagger UI](http://localhost:8000/docs) or [OpenAPI](http://localhost:8000/openapi.json).
If startup fails, use `docker compose logs db migrate api`. Change `DB_PORT` or
`API_PORT` in `.env` if a host port is occupied. The development password is in
`.env.example`; use a URL-encoded password when configuring connection URLs.

```bash
docker compose stop          # preserve database volume
docker compose up -d --wait  # resume after checking API health
docker compose run --rm migrate alembic current
```

Do not run `docker compose down -v` against data you need: it removes the development
database volume. Raw artifacts, evidence, and provenance are append-only during
normal operation; database owners can still destroy a database or disable triggers.

## Run Python locally

Requirements: Python 3.12+ and a PostgreSQL database with PostGIS available.
SQLite is deliberately unsupported because it cannot test the spatial, JSONB,
composite foreign key, and trigger invariants.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
cp .env.example .env
docker compose up -d --wait db
alembic upgrade head
uvicorn ballx.main:app --reload --host 127.0.0.1 --port 8000
```

`DATABASE_URL` must use the `postgresql+psycopg://` driver. Environment variables
override `.env`. Migrations use the same settings as the API; credentials are not
stored in `alembic.ini`. Creating the initial extension/schema requires an appropriately
privileged migration account. Provision PostGIS administratively first when managed
PostgreSQL does not allow `CREATE EXTENSION`. The initial downgrade removes GPID
tables and schemas and retains the potentially shared PostGIS extension.

## API

| Method | Endpoint | Behavior |
|---|---|---|
| GET | `/health/live` | Process liveness without a DB connection |
| GET | `/health/ready` | Checks PostGIS and migrated ground table |
| GET, POST | `/api/v1/grounds` | List or create evidence-backed grounds |
| GET | `/api/v1/grounds/{ground_id}` | One ground, or 404 |
| GET | `/api/v1/grounds/{ground_id}/provenance` | Field assertions and evidence IDs |
| GET, POST | `/api/v1/pitches` | List or create individual physical strips |
| GET | `/api/v1/pitches/{pitch_id}` | One pitch strip, or 404 |
| GET | `/api/v1/pitches/{pitch_id}/provenance` | Field assertions and evidence IDs |

Lists accept `limit` (1–100, default 50) and `offset` (default 0). Pitch listing also
accepts `ground_id`. UUIDs identify normalized entities; the optional local strip
label is independent of the UUID. All unknown fields remain null. Coordinates must
be supplied as a pair; a PostGIS WGS84 point is generated from them.

Ground and pitch creation require an existing, verified, observed or measured
`evidence_id`. A human curator must confirm that the evidence supports every supplied
field and, for a strip, identifies a distinct physical strip. A venue name or
ground-level scorecard alone does not support strip creation. The system checks
review status and evidence type, but cannot establish the factual truth of a source.
See [manual curation](docs/curation.md) before submitting real records.

Example request bodies **after** real curation (replace the symbolic IDs):

```json
{"name": "<verified ground name>", "evidence_id": "<reviewed ground evidence UUID>"}
```

```json
{
  "ground_id": "<ground UUID>",
  "local_strip_identifier": null,
  "construction_type": null,
  "evidence_id": "<reviewed evidence identifying a distinct physical strip>"
}
```

If a distinct strip cannot be identified, create no pitch record and retain
`match.pitch_id = NULL`. Creating a ground never creates a strip. Successful writes
return 201 and `Location`; invalid input/evidence returns 422, unknown entities 404,
and duplicate strip labels or invalid foreign references 409. Writes and their field
provenance commit together. No soil measurements are populated or inferred.

The service has no authentication or public deployment configuration in Milestone 1.
Keep it on a trusted local machine until access controls and rights-based evidence
exposure have been designed and reviewed. No raw-artifact API is exposed.

## Tests and checks

Run everything against the isolated Compose test database:

```bash
docker compose --profile test build test
docker compose --profile test run --rm test
docker compose --profile test stop test-db
```

`test-db` uses an ephemeral filesystem and is separate from the development database.
For a local Python run:

```bash
pytest tests/unit -q
ruff check src tests migrations
ruff format --check src tests migrations
# Use an existing, dedicated PostgreSQL/PostGIS test database, never the development DB.
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/ballx_test pytest -q
```

Integration tests require a database name ending in `_test`, run Alembic migrations,
and roll back each test's synthetic data. The migration roundtrip test drops/recreates
the GPID schemas in that dedicated database. When `TEST_DATABASE_URL` is absent,
integration tests report skips; skips do not establish PostgreSQL correctness.
GitHub Actions runs the full suite with PostGIS on pull requests.

`requirements.lock` pins the tested runtime and development dependencies. After an
intentional dependency update, resolve the project in a clean virtual environment,
regenerate the lock, and run all checks. Python 3.12 is the currently validated version.

## Project layout

```text
src/ballx/
  api/         request/response schemas and REST routes
  domain/      models, provisional vocabulary, creation services
  db/          SQLAlchemy base and session configuration
  ingestion/   versioned adapter contracts and idempotent raw artifact storage
migrations/    explicit, reviewable Alembic schema and trigger migrations
tests/unit/    input validation, adapter contracts, OpenAPI and liveness
tests/integration/  API, spatial DB, provenance, immutability, migration roundtrip
docs/          architecture, curation, blockers, validation evidence
```

The ingestion package includes explicit sample preparation, strict provider adapters,
reviewed venue mappings, hash-pinned replay, receipts, and coverage reporting.
Global scraping and predictive models remain outside this milestone.

## Milestone 2: prepare and replay the bounded sample

Run these commands in the local Python environment after `alembic upgrade head`:

```bash
# Uses the inherited HTTPS proxy and TLS trust. Downloads one 2008 annual archive,
# selects five IPL matches at one reviewed ground, and makes one weather request.
python -m ballx.ingestion.cli prepare --directory work/milestone2-sample

# Replays the frozen original source bytes, without network calls.
python -m ballx.ingestion.cli run \
  --manifest work/milestone2-sample/manifest.json \
  --report work/milestone2-quality.json

# Repeating run should import zero new matches and report five duplicates.
python -m ballx.ingestion.cli run \
  --manifest work/milestone2-sample/manifest.json \
  --report work/milestone2-replay-quality.json
```

The installed `ballx-ingest` command has the same interface. Preparation requires
HTTPS access to `cricsheet.org`, `opendatacommons.org`, and `power.larc.nasa.gov`.
It stops if its recorded rights review is more than 90 days old; re-review current
terms before renewing it. It refuses to overwrite a frozen manifest. Source
archives can change: first preparation records the archive hash; reproduction
means replaying the retained, hash-pinned member bytes and weather response.

Replay permits at most 25 selected matches and 10 weather responses per manifest.
CLI exit 0 means the requested coverage checks passed, exit 2 means raw records
and rejection/conflict receipts were committed but coverage failed, and exit 1
means local input preparation failed. Database/infrastructure errors also fail
the command. Inspect the full JSON report, including issues and attribution.

Cricsheet match dates remain dates; unavailable start/end times and pitch-strip
assignments remain `NULL`. Weather is an hourly atmospheric grid model estimate
linked by the reviewed ground's local calendar date. It is not measured soil
moisture, a ground-station observation, or actual match-time exposure.

## Builds in a managed proxy environment

On ordinary local Docker, no extra certificate secret is required. Managed cloud
environments with a custom proxy CA must supply their combined trusted CA bundle
through BuildKit, preserving the platform's proxy configuration:

```bash
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t ballx-gpid:dev .
docker compose up -d --no-build --wait
```

The CA mount is used only while pip runs and is not copied into the image. A managed
Compose build can equivalently declare the `proxy_ca` secret under each service's
`build.secrets` in a local override file. Keep TLS verification enabled.
