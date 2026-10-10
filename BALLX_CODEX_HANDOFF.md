# BallX GPID — Research-to-Codex handoff (initial verified-source edition)
Date: 2026-10-10
Status: preliminary; not a completed seven-workstream literature review or validated 20-ground dataset.

## Mission
Build an evidence-traceable ground, individual pitch-strip, match, environmental, deterioration and ball-wear research database. Keep raw evidence, measured values, proxies and predictions separate. Do not equate a venue with an individual pitch strip.

## Verified starting sources
| Source | URL | Value | Access/licensing caution |
|---|---|---|---|
| Cricsheet | https://cricsheet.org/downloads/ | structured match and delivery records, JSON and CSV | JSON/CSV Open Data Commons Attribution; check licensing terms and exclusions before ingestion |
| Open-Meteo archive | https://open-meteo.com/en/docs/historical-weather-api | historical weather and reanalysis | noncommercial vs commercial API plans and attribution must be reviewed; soil moisture is model grid estimate, not pitch measurement |
| ICC pitch ratings | https://www.icc-cricket.com/news/pitch-ratings | referee match-level pitch/outfield assessment | official ratings, not physical measurements; verify redistribution permission |
| ICC regulations | https://www.icc-cricket.com/about/cricket/rules-and-regulations/playing-conditions | pitch monitoring regulatory framework | document use and rights separately |
| Ekwue et al., water content/compaction | https://journals.sta.uwi.edu/ojs/index.php/wije/article/view/7735 | controlled soil, moisture, compaction, bounce/pace/turn relationships | experimental evidence not ground-specific measurements |
| Crowther et al., contrasting soil pitches | https://pubmed.ncbi.nlm.nih.gov/31698997/ | 276 spin deliveries and soil contrast | experimental evidence, not global predictive thresholds |
| Baker et al., soil profiles | https://shura.shu.ac.uk/2208/ | construction, hardness, rebound and pace | historic controlled study |
| Eudoxie & Nagassar, pitch preparation | https://journals.sta.uwi.edu/ojs/index.php/ta/article/view/971 | surface hardness and moisture management | limited experimental context |

## Canonical objects and minimum fields
- `source_registry`: source_id, url, provider, terms_url, license, access_status, checked_at, attribution_required, collection_allowed, notes.
- `evidence`: evidence_id, source_id, source_url, published_at, retrieved_at, original_locator, excerpt_or_measurement, rights_class, verification_status.
- `association`: association_id, name, jurisdiction.
- `ground`: ground_id, name, aliases, latitude, longitude, timezone, owner_id, operator_id, association_id, confidence.
- `pitch_strip`: pitch_id, ground_id, local_strip_identifier_nullable, construction_type_nullable, identity_confidence, evidence_id.
- `pitch_measurement`: pitch_id_nullable, ground_id_nullable, property, value, unit, method, sampling_depth_nullable, observation_time, evidence_type, evidence_id, uncertainty.
- `match`: match_id, provider_match_id, ground_id_nullable, pitch_id_nullable, format, gender_category, start_time, end_time_nullable, competition, source_id.
- `delivery`: match_id, innings, over_index, delivery_index, bowler_id_nullable, batter_id_nullable, event_data, source_id.
- `weather`: ground_id, timestamp_utc, variable, value, unit, provider, station_or_grid_id, distance_or_resolution, observation_kind, evidence_id.
- `pitch_condition`: ground_id, pitch_id_nullable, match_id_nullable, observation_time, phase, feature, value, unit_nullable, observation_kind, evidence_id, confidence.
- `ball_passport_link`: existing_ball_id, match_id_nullable, session_id_nullable, pitch_id_nullable, link_confidence.
- `derived_feature`: feature_id, entity_type, entity_id, feature_name, value, model_or_rule_version, input_evidence_ids, calculated_at.

Required invariant: Unknown strip ID is NULL, not a guessed pitch. Never transfer regional soil composition to pitch measurements. Weather reanalysis must be labeled as modeled. Preserve immutable evidence and version derived results.

## Taxonomy v0 — provisional, not validated numerical cutoffs
Construction: natural, hybrid, synthetic, drop-in, unknown.
Soil: measured clay/silt/sand percentages and mineralogy; separate descriptive local terms such as black/red soil; unknown permitted.
Surface multi-label: grass-covered, bare, dry, damp, cracked, dusty, footmarked, abraded, unknown.
Observed behavior: bounce, pace retention, turn, lateral deviation, variability — retain raw measurement and method before categorical labels.
Deterioration feature vector: visible crack extent, grass coverage change, footmark extent, loose material, abrasion, bounce variability, pace-retention change; each independently tagged by evidence type. Composite PDI is experimental only.

## Research hypotheses
H1 soil mechanics and ball-impact bounce/pace/deviation; H2 moisture and ball-pitch interaction; H3 cumulative usage and deterioration; H4 pitch/weather + image-based ball wear improves measurable performance prediction versus wear-only baseline; H5 within-match pitch states improve prediction over venue averages.
Control for physical ball, ball age, release speed, bowler, seam orientation, match format, ground, weather, and time. Separate aerodynamic flight from ball-pitch impact.

## Pilot design and acceptance
Select 20 grounds from India, Australia and England after verifying ground IDs, match coverage, diversity and available evidence. Do not pre-assign soil labels or strip identities.
1. Ingest at least one Cricsheet subset with source provenance and no duplicates.
2. Attach historical weather for a subset of verified match dates and grounds, with model/station metadata.
3. Record ICC rating as match-level assessment only where verified.
4. Demonstrate pitch_id null handling; do not misassign all ground matches to a single strip.
5. Produce field completeness, conflicts, license/access audit, and coverage by country and format.
6. Add deterioration observations only when actual timestamped evidence exists.

## Unresolved / research required
- Official ground/strip maps and strip-specific construction logs are often non-public.
- Curator-maintained soil/moisture/rolling records may require direct partnerships.
- Match broadcasts and ball-tracking data may require licenses.
- No validated universal PDI or direct image-to-swing causal model is established.
- Full global source discovery, country-specific legal review and 20-ground evidence matrix remain outstanding.
