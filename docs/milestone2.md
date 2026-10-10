# Milestone 2 — bounded ingestion, real execution pending

Milestone 1 is merged. This change implements the first ingestion pipeline but
does not claim that the real-data validation gate has passed. As of 10 October
2026, **0 real matches and 0 real weather records have been imported or verified**.
The managed environment's proxy rejects the required provider hosts with HTTP 403.
No global-scale ingestion or predictive work has started.

## Architecture and scientific boundaries

One Python service and one PostgreSQL/PostGIS database are retained. Provider
adapters implement the existing versioned source contracts. A strict manifest
lists every selected artifact, permission review, curation assertion, and hash.
All payload hashes and path containment are checked before writes. Original
source bytes stay in `raw.artifact`; normalized rows, evidence, provenance and
run/item receipts stay in `gpid`. Originals are retained even when an individual
record is quarantined. Raw ingestion errors before a valid source plan roll back
the transaction.

Migration `0002` adds reviewed source-specific ground aliases and venue IDs,
ingestion receipts, deliveries, modeled atmospheric weather, and match/weather
links. Existing timestamp-based matches remain valid. New Cricsheet records use
ordered source dates, with `time_precision=date` and null start/end timestamps.
The migration refuses to downgrade date-only matches into mandatory timestamps.

Match identity is `(source_id, numeric ZIP member filename)`, never the tournament
match number. Delivery identity is `(match, innings, over, delivery position)`;
wides/no-balls retain their real delivery positions and original event JSON.
Provider person IDs are preserved where present; no global person identities are
invented. JSON versions 1.0–1.3 are supported. Unrecognized versions fail closed.

Venue keys use Unicode normalization, case folding and whitespace normalization.
Punctuation and city aliases require explicit reviewed mappings. An unknown
stable venue ID cannot inherit a ground solely from a similar venue name. Missing
or unmatched venues remain null and fail required ground coverage. Ground identity
and physical strip identity remain distinct; the pipeline creates no pitch strips.

An exact replay creates a new receipt but no new source, raw artifact, evidence,
match, delivery, weather or link rows. Changed bytes for an existing provider match
are retained and quarantined rather than silently replacing reviewed facts.
Weather revisions with changed values/units/model metadata also require review.
A PostgreSQL transaction advisory lock serializes these bounded replay operations.
Each record/response uses a savepoint, preserving other valid imports and raw
quarantine evidence. Immutable weather/delivery/receipt/link triggers and same-ground
weather links supplement application checks.

NASA POWER is chosen because the free Open-Meteo API excludes commercial research.
The request uses four atmospheric variables and explicit UTC. Provider missing
values become null, never zero. The source model names, units, native meteorological
grid resolution (0.5° latitude × 0.625° longitude), response metadata and point
coordinates are retained. The API point is not a fabricated station/grid-cell ID.
Weather is linked to native hour starts falling within each played local calendar
date; exact match-time exposure is unknown. No measured pitch soil moisture or
strip identity is inferred. The weather schema accepts modeled atmospheric records
only, with verified modeled evidence from the same source.

## Fixed first sample and reproduction

The `prepare` command reads the published 2008 JSON archive, selects the first five
chronologically ordered men's IPL T20 matches at the explicitly reviewed
M. Chinnaswamy Stadium, retains original member bytes and all archive notices,
and downloads one bounded NASA response. It checks source venue IDs for agreement
and records reviewed venue/city aliases. The ground facts are explicitly labeled
BallX manual transcription from Wikidata Q1861907/P625; coordinates are not surveyed
strip positions. The first live response still needs validation against current
provider schemas before these commands can establish real-data correctness.

See the README for commands. Frozen manifests plus source files are the reproducible
unit. Re-fetching a provider archive is not assumed byte-identical: upstream revisions
are possible. Preserve the manifest, attribution file, source notices and hashes.
Preparation uses only approved HTTPS hosts, inherited proxy/TLS settings, bounded
downloads, timeouts and limited retries. It never crawls other years or tournaments.

The JSON quality report records actual newly imported and duplicate matches,
quarantine statuses, source hashes, ground/country/format/gender coverage, delivery
counts, unknown times/strips, and complete versus missing weather coverage. It
explicitly reports **zero independently scorecard-audited matches**; schema/byte
validation is not an independent audit or validation of scientific measurements.
Only a fully passing report may support further review of this pipeline.

## Validation and remaining blockers

The local Python/PostGIS suite passed **113 tests** at the last completed run,
with two dependency warnings (Starlette httpx deprecation and Alembic's computed
PostGIS-column comparison). Tests use explicitly synthetic records and roll back
their transactions; their counts never count toward real imports. Migration
upgrade/downgrade roundtrip and schema alignment are covered.

The built Docker image also passed **113 tests**, and its installed `ballx-ingest`
entry point ran successfully. The local development database was upgraded to
`0002`. Executing the real `prepare` command exited 1 with
`Ingestion failed before completion: 403 Forbidden`, before downloading any
match data. See [machine-readable execution status](milestone2-status.json).

Provider network access is required to freeze and execute the real pilot, validate
current actual NASA response metadata, and publish its source-pinned coverage
report. The environment must permit `cricsheet.org`, `opendatacommons.org`, and
`power.larc.nasa.gov`; no proxy bypass is attempted. Real import and duplicate
replay results must replace the pending execution status before Milestone 2 is
declared complete.

Global ground curation, measured soil protocols, official match-to-strip evidence,
reviewer correction/supersession workflow, independent scorecard audits, research
breadth and production access controls remain unresolved. The earlier
[Milestone 1 blocker analysis](research-blockers.md) is historical context; date
precision, bounded duplicate handling and atmospheric weather representation are
implemented here, while the broader research/production decisions remain open.
