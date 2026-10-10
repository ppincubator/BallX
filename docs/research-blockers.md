# Missing specifications and unresolved blockers

These gaps do not prevent the empty Milestone 1 foundation from running. They block
trustworthy pilot ingestion, scientific measurements, or production exposure.
No missing fact has been filled with an invented identity, measurement, or license.

| Gap | Evidence in the supplied specification | Decision needed before dependent work |
|---|---|---|
| Source rights and access | Registry calls for current terms review; inventory records cautions only | Per-source collection/redistribution decision, terms version, attribution text, review expiry, permitted content, rate limits, and commercial Open-Meteo plan |
| Ground identity matrix | No validated 20-ground dataset; selection criteria are qualitative | Verified pilot ground IDs, aliases, countries, coordinates, timezone, coverage and diversity matrix; collision and merge rules |
| Physical strip identity | Official maps and construction logs are often non-public | Ground/strip maps or curator partnerships; proof of distinct unnamed strips; rules for labels changing or strips being rebuilt/moved |
| Match-to-strip assignment | Hand-off explicitly permits null pitch IDs | Date-specific use logs or other reviewed evidence; no default assignment to one venue strip |
| Physical measurements | Soil/moisture/rolling records need partnerships | Property ontology, units, methods, sampling depth, sampling location, timestamps, uncertainty, instrument calibration and measured vs descriptive soil terminology |
| Time precision | Matches require start_time but providers may only give dates | Representation of date-only or multi-day matches and missing times; never invent midnight as an observed start time |
| Identity confidence | Confidence fields exist without a scoring rubric | Document a reviewer-based rubric, evidence strength and conflict handling; no arbitrary threshold is applied |
| Review and correction workflow | Evidence must be immutable, but reviewers and states are not fully specified | Reviewer identity, audit events, supersession adjudication and normalized-record revisions; how superseded evidence affects existing records |
| Field provenance | The handoff specifies citations, not a complete normalization policy | Field-specific multi-source resolution, schema/mapping versions and selection reasons; split API writes by supporting evidence until a richer assertion workflow exists |
| Weather semantics | Reanalysis is modeled and soil moisture is a grid estimate | Variables, units, provider/station/grid IDs, spatial resolution/distance, UTC matching and observation-kind vocabulary; no pitch measurement inference |
| ICC ratings | Official assessments are match-level and have rights caveats | Match identity mapping, versioned rating vocabulary, assessment dates and approved redistribution; do not attach ratings as physical strip measurements |
| Deliveries and participants | Nullable player IDs and event_data are listed | Participant identity/alias rules, innings/over/delivery semantics, source revision deduplication and event schema |
| Ball-passport integration | Existing ball/session IDs are named but no system contract is present | Existing system schema/API, stable physical-ball IDs and link evidence; no invented external foreign keys |
| Deterioration and PDI | Feature vector is provisional; PDI experimental | Actual timestamped observations and measurement definitions; validated protocol before composite scores |
| Prediction research | No validated universal PDI or image-to-swing model | Seven-workstream review, rights for broadcast/tracking, controls, leakage-safe validation and baseline experiments after separate authorization |
| Research breadth | Full discovery and country-specific legal review are outstanding | Complete source discovery, literature matrix and country review before global claims |
| Production operation | No deployment/security/retention requirements supplied | Auth roles, source-dependent visibility, least-privilege DB roles, secrets, migrations ownership, backup/restore, storage limits and retention policy |

The supplied eight-source handoff and four-row inventory are preserved as received.
They are not a complete seven-workstream literature review and do not establish any
global predictive thresholds. The controlled studies inform research hypotheses,
not observed values for the pilot's grounds.

Milestone 1 review should confirm the ground/strip boundary, evidence gates,
nullable identity behavior, schema choices, API contract, and test results. Milestone 2
must remain paused until that review. No scraping, source ingestion, source terms
approval, or predictive work has been executed as part of this change.
