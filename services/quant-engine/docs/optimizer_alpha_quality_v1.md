# Optimizer Alpha Quality V1

`alpha_quality_v1` is the shipped backend quality alpha package for narrow-scope PIT fundamentals.

## What the PIT path guarantees now

- Immutable raw bundles and immutable normalized PIT snapshots are both required for trust.
- A trust gate runs per `as_of_date` before any live PIT snapshot is treated as optimizer-eligible.
- The gate validates raw-to-normalized lineage integrity, duplicate or missing snapshot artifacts, deterministic replay equivalence, and approved-universe coverage only for `U.S.` `USD` operating equities.
- Unsupported or ambiguous cases fail closed and emit machine-readable `trust_report.json` output with explicit issue codes.
- The alpha package is point-in-time only and uses only records whose effective availability date is on or before the requested `as_of_date`.
- Reporting lag policy is explicit: quarterly statements default to 45 days and annual statements default to 90 days.
- Stale fundamentals fail conservative freshness checks after 450 days.
- Missing, stale, or lag-blocked component inputs do not fabricate strength; they receive a conservative negative fallback score.
- The package is a fixed transparent composite of four quality legs:
  - `profitability`: gross profitability, falling back to EBIT/assets
  - `cash_generation`: CFO/assets, falling back to FCF/assets
  - `accrual_quality`: lower accruals via `(net_income - operating_cash_flow) / assets`
  - `leverage_discipline`: lower net debt burden via `(total_debt - cash_and_equivalents) / assets`
- Cross-sectional normalization is deterministic: winsorize each component at the configured lower and upper quantiles, then z-score and cap the result.
- Composite weights are fixed and inspectable:
  - profitability `0.35`
  - cash_generation `0.30`
  - accrual_quality `0.20`
  - leverage_discipline `0.15`
- Trusted PIT output can now be attached to optimizer preview request assembly when the preview requests `pit_alpha`.

## Current shipped boundary

- The attachment path is still narrow to the shipped optimizer preview workflow.
- Coverage remains limited to `U.S.` `USD` operating equities.
- The package remains fixed to `alpha_quality_v1`; it is not yet a broader alpha platform.

## What the PIT path does not yet guarantee

- It does not broaden region, currency, or security-type coverage beyond `U.S.` `USD` operating equities.
- It does not recover or reconcile advanced restatement patterns; multiple records for the same symbol, statement date, and period type are surfaced and quarantined.
- It does not repair broken lineage, replace missing raw artifacts, or substitute latest-available data for a requested `as_of_date`.
- It does not overwrite immutable raw or normalized snapshots.
- It does not by itself make optimizer output applied portfolio truth; downstream optimizer artifacts and handoffs remain hypothetical.

## When to quarantine a snapshot

- Quarantine any snapshot whose `normalized/pit_fundamentals.json` is missing, malformed, stale relative to the directory `as_of_date`, or internally duplicated.
- Quarantine any snapshot whose `raw/*.json` bundles are missing, duplicated, malformed, stale, or symbol-misaligned with the normalized universe.
- Quarantine any snapshot whose deterministic replay from immutable raw bundles does not exactly reproduce the normalized PIT payload.
- Quarantine any snapshot that includes unsupported restatement patterns or falls outside the approved `U.S.` `USD` operating-equity universe.
- Quarantine any snapshot whose trust report status is `quarantined`; do not route it downstream as optimizer-ready.

## Snapshot artifacts

- `raw/*.json`: immutable per-symbol vendor payloads captured at ingestion time
- `normalized/pit_fundamentals.json`: immutable normalized PIT snapshot used for alpha package construction
- `normalized/coverage.json`: immutable ingestion coverage manifest
- `normalized/trust_report.json`: latest machine-readable trust decision for that immutable snapshot set
