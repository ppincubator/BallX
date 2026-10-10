# BallX GPID — source registry (initial)

See `BALLX_CODEX_HANDOFF.md` for source links, data uses and caveats. This is an initial verified-source shortlist, not exhaustive global discovery. Before production ingestion, verify current terms, rate limits, rights, and required attribution for each source.

## Milestone 2 bounded pilot review — 10 October 2026

| Source | Reviewed terms and scope | Decision |
|---|---|---|
| [Cricsheet JSON](https://cricsheet.org/licensing/) | JSON and registers use [ODC-BY 1.0](https://opendatacommons.org/licenses/by/1-0/); commercial database use requires attribution and retained notices | Approved for this bounded pilot. Download only the published 2008 archive; select five IPL matches. Do not collect withheld data. Independent third-party content rights are not blanket-approved. |
| [NASA POWER](https://power.larc.nasa.gov/) | [Earthdata policy](https://www.earthdata.nasa.gov/engage/open-data-services-software/data-use-policy); NASA POWER team confirms public-domain commercial use in [this response](https://forum.earthdata.nasa.gov/viewtopic.php?t=506) | Approved for one hourly atmospheric point request with NASA POWER acknowledgment. UTC required; parameters limited to T2M, RH2M, PRECTOTCORR, WS10M. Serial requests; no soil interpretation. |
| [Wikidata ground facts](https://www.wikidata.org/wiki/Q1861907) | Structured facts use [CC0](https://www.wikidata.org/wiki/Wikidata:Licensing) | BallX manual coordinate/identity transcription explicitly labeled as curation; no claim that this transcription is an original upstream response or survey. |
| [Open-Meteo free API](https://open-meteo.com/en/terms) | Free API excludes commercial use, including private commercial research | Not used. A separately authorized commercial plan would be required. |

The implementation records provider URLs, terms URLs, license descriptions,
review dates, attribution, source byte hashes, original ZIP member locators,
adapter versions and import receipts. Rights reviews expire after 90 days.
No actual provider match or weather record has yet been downloaded/imported in
the managed execution environment: its proxy blocks the required destinations.
The handoff inventory is preserved; this addition covers the bounded pilot only.
