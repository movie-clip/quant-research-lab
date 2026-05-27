# Epic Roadmap

*Living execution snapshot. Updated: 2026-05-27.*

---

## Completed Epic: Epic 11 — Factor Return Attribution

**PRD:** [`docs/product/prd/epic-11-factor-return-attribution.md`](product/prd/epic-11-factor-return-attribution.md)

### Goal

Give the researcher a clear answer to "where did my returns come from?" by decomposing portfolio daily returns into per-factor contributions (β × orthogonalized factor return) and a residual, displayed as a cumulative line chart and period attribution table in the Exposure tab.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-11.1 | Attribution engine + endpoint | Done |
| US-11.2 | Attribution card (chart + table) | Done |
| US-11.3 | Docs, contracts, roadmap close-out | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-27 | US-11.1 | `analytics/attribution.py` + Pydantic schema + `POST /engines/attribution/run` route + attribution_engine service — 15 backend tests green (239 total) |
| 2026-05-27 | US-11.2 | `FactorAttributionCard` in Exposure tab: cumulative line chart, 20d/60d/252d window selector, period attribution table, Synthetic badge with tooltip, unavailable/loading/error states — 14 frontend tests green (92 total); `npx tsc --noEmit` clean |
| 2026-05-27 | US-11.3 | `docs/contracts/attribution-fields.md` created; `financial-methodology.md` §Factor Return Attribution verified complete; roadmap and story files updated |

---

## Active Epic: Epic 10 — Multi-broker Import Correctness

**PRD:** [`docs/product/prd/epic-10-multi-broker-import-correctness.md`](product/prd/epic-10-multi-broker-import-correctness.md)

### Goal

Add regression coverage for the three-broker import scenario (IB + Freedom24 + ESPP): backend pytest for `combine_imported_snapshots` + `import_statements` + analytics bootstrap; frontend vitest for the sequential `overlayImportedSnapshot` add-statement flow.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-10.1 | 3-way combine and API-level import tests | Done |
| US-10.2 | Sequential add-statement overlay tests | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-27 | US-10.1 | 3 new backend pytest: 3-way combine, import_statements API, analytics bootstrap — 18 tests green |
| 2026-05-27 | US-10.2 | 3 new frontend vitest: sequential overlay, symbol dedup, sourceFileNames dedup — 3 tests green |

---

## Parked Epic: Epic 9 — Portfolio Correlation & Co-movement Analysis

**PRD:** [`docs/product/prd/epic-9-correlation-analysis.md`](product/prd/epic-9-correlation-analysis.md)

### Goal

Give the portfolio researcher a quantitative view of how their portfolio
co-moves with major market indexes — a day-by-day indexed return chart, a
rolling correlation chart (30d/60d/90d Pearson ρ), and a multi-benchmark
snapshot table (ρ, β, R² vs SPY/QQQ/GLD/IEF/VT) — all in the Exposure tab.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-9.1 | Indexed return time-series chart | Next phase |
| US-9.2 | Rolling correlation engine and chart | Next phase |
| US-9.3 | Multi-benchmark correlation matrix | Next phase |
| US-9.4 | Fix rolling factor loadings methodology | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-26 | US-9.4 | Fixed rolling factor model: per-window Gram-Schmidt orthogonalization replaces global GS; Market loading blowup (−4.60) eliminated; 221 backend + 98 frontend tests green |

---

## Completed Epic: Epic 8 — Reset to Portfolio Analysis Core

**PRD:** [`docs/product/prd/epic-8-reset-to-analysis-core.md`](product/prd/epic-8-reset-to-analysis-core.md)

### Goal
Strip the product to Dashboard + Exposure, clean up the codebase and docs, then add one additive feature: portfolio drift vs index benchmarks in the Exposure tab.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-8.1 | Remove workflow tabs from navigation | Done |
| US-8.2 | Strip Workspace and Monitoring frontend | Done |
| US-8.3 | Strip ranking and optimizer frontend | Done |
| US-8.4 | Strip App.tsx workflow state and storage | Done |
| US-8.5 | Remove ranking, construction, and optimizer backend | Done |
| US-8.6 | Remove backtest and monitoring backend | Done |
| US-8.7 | Prune portfolio feature directory | Done |
| US-8.8 | Reset docs and contracts | Done |
| US-8.9 | Add portfolio drift vs index benchmarks | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-25 | US-8.1 | Removed 6 nav tabs; app shows only Dashboard and Exposure |
| 2026-05-25 | US-8.2 | Deleted features/backtest/ (21 files, ~9k lines) |
| 2026-05-25 | US-8.3 | Deleted features/strategy-lab/, generic-ranking/, optimizer/ (38 files, ~25k lines) |
| 2026-05-25 | US-8.4 | Stripped App.tsx from ~3100 to 901 lines; portfolioWorkspaceStorage.ts from ~3300 to 707 lines |
| 2026-05-25 | US-8.5+8.6 | Deleted 4 backend route modules, ~26 service files, 6 schemas, 16+ test files, 7 artifact directories |
| 2026-05-25 | US-8.7 | Deleted 10 dead portfolio components; App.tsx tab type narrowed to dashboard/exposure |
| 2026-05-25 | US-8.8 | Deleted 5 contract docs, 2 old PRDs; rewrote CLAUDE.md, current-product-state.md, epic-roadmap.md |
| 2026-05-25 | US-8.9 | Added drift vs benchmark panel to Exposure tab; new /engines/drift/run endpoint |

---

## Archived Epics

| Epic | Title | Status |
|---|---|---|
| Epic 1 | Imported-portfolio truth & reconciliation | Foundation — superseded by Epic 8 pivot |
| Epic 2 | Ranking & selection methodology | Cancelled — features removed in Epic 8 |
| Epic 3 | Construction & optimizer methodology | Cancelled — features removed in Epic 8 |
| Epic 4 | Monitoring & overlay review | Cancelled — features removed in Epic 8 |
| Epic 5 | Usable Core Flow | Complete — superseded by Epic 8 |
