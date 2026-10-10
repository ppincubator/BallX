# Milestone 1 validation — 2026-10-10

## Actual results

| Check executed | Result |
|---|---|
| Full suite in local Python virtual environment with live PostgreSQL/PostGIS | 71 passed, 2 warnings in 1.47s before adding the positive match/strip association test |
| Final full suite through `docker compose --profile test run --rm test` | **72 passed, 0 failed, 0 skipped, 2 warnings in 1.63s** |
| Final test breakdown | 30 unit tests, 42 integration tests |
| `ruff check src tests migrations` | All checks passed |
| `ruff format --check src tests migrations` | 24 files already formatted |
| `python -m pip check` | No broken requirements found |
| `alembic upgrade head` on development PostGIS | Completed successfully |
| `alembic check` | No new upgrade operations detected |
| Integration migration roundtrip | Downgrade to base, upgrade to 0001, extension retained, schema aligned |
| Docker image build with managed proxy CA | Completed successfully |
| `docker compose config --quiet` | Valid configuration |
| `docker compose up -d --no-build --wait` | DB and API healthy, migration service exited 0 |
| HTTP `/health/ready` | 200, `{"status":"ready"}` |
| HTTP `/api/v1/grounds` and `/api/v1/pitches` | 200, empty arrays as expected |

Host interpreter: Python 3.12.14; container interpreter: Python 3.12.15. Containers
used PostgreSQL 16.9 and PostGIS 3.5.2 from `postgis/postgis:16-3.5`, with a separate
ephemeral `ballx_test` database.
Dependencies are recorded in `requirements.lock`.

The final suite covers nullable strip identity, no automatic strip creation or match
assignment, valid and cross-ground match/strip links, source-scoped match deduplication,
separate association/owner/operator references, reviewed identity gates, raw snapshot
idempotency, collection permission checks, database SHA-256 validation, raw/evidence
source agreement, append-only UPDATE/DELETE/TRUNCATE protection, superseding evidence,
field provenance targets, atomic API rollback, spatial coordinate order/SRID, input
validation, API reads, pagination, readiness, and migration roundtrip/schema drift.
Every fixture is synthetic; no real ground, strip, or soil data was inserted.

## Non-failing warnings

1. Starlette 1.7's TestClient deprecates its `httpx` backend in favor of `httpx2`.
   The pinned FastAPI/Starlette/httpx combination passed the suite. A later dependency
   change should migrate the test client deliberately.
2. Alembic warns that the generated `ground.location` computed default cannot be
   automatically modified. The spatial integration test verifies the generated WGS84
   point, coordinate order, and SRID. Any future generated-expression change needs an
   explicit migration rather than reliance on autogeneration.

The first container test attempt exposed unreadable workspace file permissions for
the non-root image user. The Dockerfile now grants read/traverse access to `/app`;
the corrected image passed the final suite. Compose also has API health checking so
the documented startup waits until HTTP readiness is available.

## Test limits

All required local database and Docker infrastructure was available and exercised.
No production infrastructure, external provider ingestion, real-world strip identity,
source licensing decision, load/concurrency benchmark, or predictive model was tested.
Those activities are outside Milestone 1. GitHub Actions is configured to run the
suite on PRs; this report's results are local/container results, not an assertion that
remote GitHub Actions has completed. Python versions newer than 3.12 were not tested.
