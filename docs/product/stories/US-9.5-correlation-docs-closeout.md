# US-9.5: Docs, contracts, and roadmap close-out

**Epic:** Epic 9 — Portfolio Correlation & Co-movement Analysis
**PRD:** [`epic-9-correlation-analysis.md`](../prd/epic-9-correlation-analysis.md)
**Status:** Done
**Last updated:** 2026-05-28

## Story

As a **portfolio researcher**, I want the correlation feature's contract fields,
financial methodology, and roadmap status to be fully documented, so that any
future implementer can understand exactly which backend fields drive every UI
value without reading scattered source files.

## Context

US-9.1, US-9.2, and US-9.3 deliver the three user-visible features of Epic 9.
This story creates the field-level contract doc (`docs/contracts/correlation-fields.md`),
verifies the `financial-methodology.md` sections for the four formulas used
(Indexed Return Series, Rolling Pearson Correlation, Beta, R²), updates the epic
snapshot in `epic-roadmap.md`, and sets all stories to Done.

No code changes. No new backend or frontend work.

Implementer must read:
- `docs/finance/financial-methodology.md` — §Indexed Return Series, §Rolling
  Pearson Correlation, §Beta (Market Beta), §R² — verify they are complete
- `docs/contracts/attribution-fields.md` — style reference for contract docs
- `docs/product/stories/README.md` — add the US-9.5 slice

## Acceptance criteria

- [x] AC1 — `docs/contracts/correlation-fields.md` exists and contains a table
  for every field in `DriftDailyPoint` (US-9.1), `RollingRiskPoint`
  correlation/beta columns (US-9.2), and `BenchmarkStats` (US-9.3), with
  columns: Field | Backend type | TS type | UI display | Trust | Nullable.
- [x] AC2 — `docs/finance/financial-methodology.md` contains a complete section
  for each of the four formulas used in this epic (Indexed Return Series,
  Rolling Pearson Correlation, Beta, R²), each with: formula block, symbol
  definitions, edge-case rules, and at least one academic citation.
- [x] AC3 — `docs/product/epic-roadmap.md` shows Epic 9 status as Active (not
  Parked) and the slice log contains an entry for each of US-9.1, US-9.2,
  US-9.3, and US-9.5.
- [x] AC4 — `docs/product/stories/README.md` shows US-9.1, US-9.2, US-9.3,
  and US-9.5 as Done; US-9.4 remains Done.
- [x] AC5 — No acceptance criterion in US-9.1, US-9.2, or US-9.3 references a
  formula not documented in `financial-methodology.md`.

## Test plan

Backend (pytest):
- No backend changes; all tests must remain green as a regression check.

Frontend (vitest):
- No frontend changes; all tests must remain green as a regression check.

Regression / guardrail:
- `python scripts/run_all_tests.py` must pass without modification.
- `npx tsc --noEmit` must pass without modification.

## Tickets

- [x] T-9.5.1 — **Contract doc**: create
  `docs/contracts/correlation-fields.md` with field inventory tables for
  US-9.1 (indexed return chart fields), US-9.2 (rolling correlation/beta
  chart fields from `RollingRiskPoint`), and US-9.3 (multi-benchmark table
  fields from `BenchmarkStats` and `MultiBenchmarkCorrelationResult`). Follow
  the style of `docs/contracts/attribution-fields.md`.

- [x] T-9.5.2 — **Methodology verification**: read
  `docs/finance/financial-methodology.md` §Indexed Return Series, §Rolling
  Pearson Correlation, §Beta (Market Beta), §R² — confirm all four sections
  contain formula blocks, symbol definitions, edge-case rules, and academic
  citations. Add any missing content; make no changes if already complete.

- [x] T-9.5.3 — **Roadmap and story close-out**: update
  `docs/product/epic-roadmap.md` — change Epic 9 from "Parked" to "Active"
  header, add slice log entries for US-9.1, US-9.2, US-9.3, US-9.5; update
  `docs/product/stories/README.md` — set US-9.1, US-9.2, US-9.3, US-9.5
  to Done; check all AC boxes in each story file.

## Out of scope

- No code changes of any kind.
- No new methodology — all formulas must already exist in
  `financial-methodology.md` before this story runs.
- No PRD changes — the Epic 9 PRD is final.

## Notes / decisions

- **US-9.4 is already Done** (rolling factor loadings fix, shipped 2026-05-26).
  This story closes the remaining three stories (9.1, 9.2, 9.3) and itself.
- **Contract doc style**: follow `docs/contracts/attribution-fields.md` exactly.
  Each table row: Field | Backend schema type | TypeScript type | UI display
  location | Trust class | Nullable? | Notes.
- **Formula sections already drafted** by the quant-research skill (2026-05-28).
  T-9.5.2 is a verification pass, not an authoring pass.
