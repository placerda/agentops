# `waf-checklist.csv` — workspace WAF checklist

This CSV is a **workspace override** for the AgentOps Doctor's WAF
knowledge base. The Doctor reads `.agentops/waf-checklist.csv` on
every run; rows here either:

* **Override** rows shipped in the packaged checklist
  (`agentops/agent/knowledge/waf-checklist.csv`) by matching the
  `doctor_check_id` column, **or**
* **Extend** the checklist with new rows that map your own custom
  finding ids onto WAF pillars.

The seed file copied into your workspace by `agentops init` ships a
**curated 50-item shortlist** (10 per WAF pillar) drawn from the
public **Microsoft Azure AI Landing Zones Checklist** (177 items).

## Curation policy

* Sourced from the public AI Landing Zones Checklist
  (https://learn.microsoft.com/azure/cloud-adoption-framework/scenarios/ai/).
* Limited to items the AgentOps Doctor can reach with its current
  data sources (`results_history`, `azure_monitor`, `foundry_control`,
  `azure_resources`, `workspace_files`) **or** items that warrant a
  manual audit step the team should track.
* High-severity / high-leverage items first; per-pillar coverage
  deliberately broad rather than deep.

## Column reference

| Column | Meaning |
|---|---|
| `pillar` | WAF pillar — `Security`, `Reliability`, `Performance`, `OperationalExcellence`, or `Cost`. |
| `area` | Free-text sub-area (e.g. `Identity`, `CI-CD`, `Telemetry`). |
| `item_id` | Stable short id. Items sourced from the AI Landing Zones Checklist use `ai_lz.AI.<n>`. |
| `title` | User-facing short label. Includes the original `[AI.<n>]` reference for traceability. |
| `detection_source` | Doctor source(s) that can reach this signal — `results_history`, `azure_monitor`, `foundry_control`, `azure_resources`, `workspace_files`, or `manual`. |
| `detection_signal` | Short description of how the rule checks the signal (or the artifact that proves compliance when `manual`). |
| `doctor_check_id` | The finding id Doctor emits. `manual.<pillar>.<x>` is reserved for items with no automated rule today. **A row with this column empty is ignored by the loader.** |
| `status` | `implemented` (a rule fires today and surfaces this signal automatically) or `manual` (audit-only — Doctor cannot verify; the team is responsible for the review). |
| `reference_url` | Public Microsoft Learn URL for the WAF pillar. |

## How to extend

Add a new row at the bottom of the CSV. Example:

```csv
OperationalExcellence,Custom,my.team.review_cadence,Monthly review cadence is documented,manual,team review log,manual.opex.review_cadence,manual,https://your-wiki/policies/review
```

Two practical rules to keep in mind:

1. **Stay strict on `doctor_check_id`** — the loader skips rows
   whose `doctor_check_id` is empty. Use a meaningful prefix
   (`manual.<pillar>.<topic>`) even when there's no automated rule
   yet, so future rules with that id will pick up the WAF citation
   automatically.
2. **No comment lines.** CSV has no portable comment syntax; this
   `README.md` is the canonical place for documentation. The Doctor's
   loader currently tolerates `#`-prefixed lines (they're skipped at
   the `_row_to_item` filter), but Excel / pandas / any third-party
   parser will treat them as data and clutter the file.

## Distribution of the seed shortlist

The seed file ships only items where the Doctor has a **working,
deterministic rule today** (`implemented`) or where the item is an
**audit step that requires human judgement** (`manual`). We
intentionally do not ship `planned` items — they add a "we will do
this later" promise that is easy to forget. New rules earn their
spot in this file when they actually run, not before.

| Pillar | Items | Implemented | Manual |
|---|---:|---:|---:|
| Security | 10 | 6 | 4 |
| OperationalExcellence | 9 | 7 | 2 |
| Reliability | 7 | 3 | 4 |
| Performance | 9 | 3 | 6 |
| Cost | 8 | 0 | 8 |
| **Total** | **43** | **19** | **24** |
