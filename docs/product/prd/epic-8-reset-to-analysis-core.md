# Epic 8 — Reset to Portfolio Analysis Core

**Status:** Planning  
**Last updated:** 2026-05-24

---

## Problem

The product has accumulated five years of features across eight tabs that do not all pull in the same direction. The researcher finds **Dashboard (partially) and Exposure (fully)** genuinely useful for portfolio analysis. Everything else — Workspace, Backtest, Strategy Lab, ETF Ranking, Generic Ranking, Diagnostics — is either confusing, broken for the researcher's actual workflow, or solving a problem they don't have right now.

Carrying dead surface area has real costs:
- The codebase is hard to navigate — a simple change touches dozens of files in features the researcher never opens.
- The test suite runs 1,277 backend + 537 frontend tests, the majority of which cover removed functionality.
- The backend has ~30 service files and 11 route modules, most for features being cut.
- Documentation is spread across four epics' worth of contracts, PRDs, and stories.
- Every time a new feature is added to Dashboard or Exposure it has to compete with a sea of imports, types, and abstractions designed for the Workspace/Optimizer workflow.

The researcher also identifies a **concrete missing feature**: portfolio drift against index benchmarks was useful in an earlier version of the product and should come back — placed prominently at the top of the Exposure tab.

---

## Goals

1. **Strip the product to Dashboard + Exposure only.** Remove every tab, route, service, schema, and test that exists solely to support Workspace/Backtest/Ranking/Construction/Optimizer/Monitoring functionality.
2. **Leave the codebase in a working state at every step.** The test suite is green at the end of each story. No story leaves orphaned imports or dead references.
3. **Keep the backend minimal but honest.** Retain only the routes and services that Dashboard and Exposure actually call. Delete the rest — do not comment out or flag for later.
4. **Add portfolio drift vs index benchmarks to Exposure.** At the top of the Exposure tab, show how the portfolio is moving relative to configurable market indexes (S&P 500 baseline, selectable others). Rolling windows: 1 month, 3 months, 6 months, 12 months, since import.
5. **Reset the docs.** Clean up contracts, PRDs, and the epic roadmap to reflect the new surface area.

---

## Non-goals

- Re-evaluating whether the ranking/construction/optimizer workflows were good ideas. They were — this is a deliberate focus shift, not a quality judgment.
- Keeping stub code "in case we want it back." If a feature is removed it is removed. Git history is the archive.
- Rebuilding the Workspace or Backtest tabs in a simpler form. That's a future epic if the researcher decides they want it.
- Changing the financial methodology for what remains. Dashboard and Exposure analytics are unchanged — this epic is deletion and one additive feature.
- Adding any backend infrastructure beyond what the drift vs index feature needs.

---

## What stays after this epic

### Frontend tabs
| Tab | Kept | Notes |
|---|---|---|
| Dashboard | ✅ | Unchanged functionality |
| Exposure | ✅ | Gains drift vs index panel at top |
| Workspace | ❌ | Removed |
| Backtest | ❌ | Removed |
| Strategy Lab | ❌ | Removed |
| ETF Ranking | ❌ | Removed |
| Generic Ranking | ❌ | Removed |
| Diagnostics | ❌ | Removed as standalone tab — the underlying engine endpoint stays because Exposure uses it internally |

### Backend routes
| Route module | Kept | Notes |
|---|---|---|
| `exposure.py` | ✅ | Exposure tab |
| `dashboard_history.py` | ✅ | Dashboard tab |
| `diagnostics.py` | ✅ | Exposure tab internal calls |
| `imports.py` | ✅ | Broker import |
| `market_data.py` | ✅ | Price data for analytics |
| `health.py` | ✅ | Health check |
| `backtests.py` | ❌ | Removed entirely |
| `construction.py` | ❌ | Removed |
| `optimizer.py` | ❌ | Removed |
| `strategy_lab.py` | ❌ | Removed |

### Backend services (keep)
`benchmark_service`, `dashboard_history_engine`, `diagnostics_engine`, `exposure_engine`, `history_context_builder`, `holdings_history`, `import_admission`, `import_engine`, `import_engine_composer`, `market_data`, `portfolio_proof`, `portfolio_snapshot_builder`, `statement_importer`

> `backtest_engine_service` and `portfolio_backtest_engine` need investigation: keep only the slice consumed by `dashboard_history_engine` and `diagnostics_engine`. Everything else goes.

### Backend services (remove)
`candidate_constraints`, `candidate_construction`, `candidate_formation`, `construction_artifact_service`, `construction_policy_catalog`, `construction_ranking_handoff_service`, `construction_run_service`, `cross_sectional_research_artifact_service`, `cross_sectional_research_service`, `etf_ranking_artifact_service`, `generic_ranking_artifact_service`, `generic_ranking_service`, `monitor_definition_artifact_service`, `optimizer_alpha_fundamentals`, `optimizer_alpha_service`, `optimizer_artifact_service`, `optimizer_handoff_constraints`, `optimizer_preview_service`, `optimizer_risk_service`, `optimizer_service`, `ranking_artifact_catalog_service`, `ranking_artifact_open_service`, `replacement_ranking`, `replacement_ranking_artifact_service`, `review_snapshot_artifact_service`, `strategy_lab`, `universe_resolver`

### Schemas (keep)
`dashboard_history`, `diagnostics`, `exposure`, `import_bootstrap`, `imports`, `portfolio`, `portfolio_engine`, `return_basis`, `reconciliation`

### Schemas (remove)
`backtest_engine`, `construction`, `generic_ranking`, `optimizer`, `ranking`, `research`

### Data artifact directories (remove)
`data/artifacts/construction-artifacts/`, `data/artifacts/cross-sectional-research-artifacts/`, `data/artifacts/etf-ranking-artifacts/`, `data/artifacts/etf-replacement-ranking-artifacts/`, `data/artifacts/generic-ranking-artifacts/`, `data/artifacts/optimizer-handoffs/`, `data/artifacts/monitor-definitions/`

### Frontend feature directories (remove)
`features/backtest/`, `features/strategy-lab/`, `features/generic-ranking/`, `features/optimizer/`

### Frontend feature directory (prune — keep only what Dashboard + Exposure use)
`features/portfolio/` — remove: `PersistedReplacementRankingReview.tsx`, `ReplacementRankingReview.tsx`, `VariantList.tsx`, and any test files for removed components.

### Contract docs (keep)
`dashboard-fields.md`, `diagnostics-fields.md`, `exposure-fields.md`, `import-admission-fields.md`

### Contract docs (remove)
`backtest-fields.md`, `candidate-workflow-fields.md`, `etf-ranking-fields.md`, `generic-ranking-fields.md`, `research-artifact-fields.md`

---

## Success signals

- `python scripts/run_all_tests.py` is green after every story.
- `npx tsc --noEmit` is clean after every story.
- Backend has ≤ 6 route modules and ≤ 15 service files.
- Frontend has 2 tabs and no imports from removed feature directories.
- The Exposure tab shows a "vs Market" drift panel at the top with rolling portfolio vs benchmark figures.
- The codebase can be navigated without knowledge of ranking, construction, optimizer, or monitoring concepts.

---

## Story list

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-8.1](#us-81) | Remove workflow tabs from navigation | Frontend — nav only | Backlog |
| [US-8.2](#us-82) | Strip Workspace and Monitoring frontend | Frontend — features/backtest/ | Backlog |
| [US-8.3](#us-83) | Strip ranking and optimizer frontend | Frontend — features/strategy-lab/, features/generic-ranking/, features/optimizer/ | Backlog |
| [US-8.4](#us-84) | Strip App.tsx workflow state and storage | Frontend — App.tsx, workspace storage | Backlog |
| [US-8.5](#us-85) | Remove ranking, construction, and optimizer backend | Backend — routes, services, schemas | Backlog |
| [US-8.6](#us-86) | Remove backtest and monitoring backend | Backend — routes, services, schemas | Backlog |
| [US-8.7](#us-87) | Prune portfolio feature directory | Frontend — features/portfolio/ dead code | Backlog |
| [US-8.8](#us-88) | Reset docs and contracts | Docs — contracts, PRDs, roadmap | Backlog |
| [US-8.9](#us-89) | Add portfolio drift vs index benchmarks | Backend + Frontend — new Exposure feature | Backlog |

Stories 8.1–8.8 are pure deletion. They must be done in order (each leaves a compilable, test-green state for the next). Story 8.9 is the one additive story and should come last so it builds on the cleaned-up foundation.

---

## Stories

### US-8.1
**Remove workflow tabs from navigation**

> As a portfolio researcher, I want to open the app and see only Dashboard and Exposure in the nav, so that the product surface matches what I actually use.

Remove from App.tsx's `appTabs` array: Workspace, Backtest, Strategy Lab, ETF Ranking, Generic Ranking, Diagnostics. Leave all feature-directory code in place — this is only a nav change. Update the tab-order regression test.

**Why this is story 1:** It is the lowest-risk change and immediately improves the UX. Subsequent stories delete the now-detached feature code. Keeping this step isolated means if something breaks in a later story, we still have a clean nav.

**Acceptance criteria:**
- App renders exactly two tabs: Dashboard and Exposure, in that order.
- No tab-navigation link to Workspace, Backtest, Strategy Lab, ETF Ranking, Generic Ranking, or Diagnostics exists in the DOM.
- The app still imports and boots without TypeScript errors (feature code not yet deleted).
- Tests pass.

---

### US-8.2
**Strip Workspace and Monitoring frontend**

> As a developer, I want the features/backtest/ directory gone so the codebase no longer carries ~50 components, hooks, and tests for a workflow that's not in the product.

Delete the entire `features/backtest/` directory. Remove all imports of anything from that directory in `App.tsx`, `app/store/`, and any other consumers. Update App.tsx to remove all state, callbacks, and types that exist solely for the Workspace/Backtest/Monitoring workflow. Remove the test files that covered those components.

Scope of deletion in `features/backtest/`:
- PortfolioImprovementWorkspaceShell.tsx + test
- All three Persisted*Browser components + test
- BacktestWorkspacePanel + PortfolioAllocationBacktestPanel + StrategyBacktestPanel + tests
- MonitoringPanel + test
- constructionPolicyCatalog, rankingArtifactConstructionHandoff, rankingConstructionMaxPositionWeight
- All other files in that directory

**Acceptance criteria:**
- `features/backtest/` directory does not exist.
- `npx tsc --noEmit` is clean.
- `npx vitest run` passes — all remaining tests green.
- App.tsx has no imports from `features/backtest/`.

---

### US-8.3
**Strip ranking and optimizer frontend**

> As a developer, I want the features/strategy-lab/, features/generic-ranking/, and features/optimizer/ directories gone.

Delete:
- `features/strategy-lab/` (EtfRankingPanel and all related files + EtfRankingPanel.test.tsx)
- `features/generic-ranking/` (GenericRankingView, GenericRankingRequestForm + test)
- `features/optimizer/` (whatever is there)

Remove all imports of anything from those directories in App.tsx and elsewhere.

**Acceptance criteria:**
- Those three feature directories do not exist.
- `tsc --noEmit` clean, `vitest run` green.
- App.tsx has no imports from removed directories.

---

### US-8.4
**Strip App.tsx workflow state and workspace storage**

> As a developer, I want App.tsx to be a thin shell over Dashboard and Exposure — no ranking artifacts, no construction state, no optimizer handoffs, no monitoring sessions.

This is the most invasive frontend story. App.tsx currently owns ~3,500 lines of state, effects, and callbacks for the full workflow. After stories 8.2 and 8.3, those callbacks compile but serve nothing. This story removes them.

Scope:
- Remove all state variables, `useEffect` hooks, and callback functions that were consumed only by removed tabs/features (workspace draft state, candidate state, construction state, optimizer state, monitoring state, proposal state, etc.).
- Remove from `app/portfolioWorkspaceStorage.ts` and `app/startupSelectionValidation.ts` all storage keys and restore logic for removed features.
- Remove from `app/types/` all TS type definitions that exist only for the removed features.
- Shrink `App.tsx` to the subset that serves Dashboard and Exposure (import, snapshot loading, tab switching, analytics calls).

**Acceptance criteria:**
- App.tsx is materially shorter (target: under 600 lines, from ~3,500).
- No state variable, type, or callback survives that is not consumed by a visible component.
- `tsc --noEmit` clean, full test suite green.
- `portfolioWorkspaceStorage.test.ts` passes with tests for remaining storage behavior only.

---

### US-8.5
**Remove ranking, construction, and optimizer backend**

> As a developer, I want the construction, optimizer, and strategy-lab route modules gone from the backend so the API surface reflects what Dashboard and Exposure actually call.

Delete:
- `app/api/routes/construction.py`
- `app/api/routes/optimizer.py`
- `app/api/routes/strategy_lab.py`
- Unregister them from `app/main.py`

Delete backend services:
- `candidate_constraints`, `candidate_construction`, `candidate_formation`
- `construction_artifact_service`, `construction_policy_catalog`, `construction_ranking_handoff_service`, `construction_run_service`
- `cross_sectional_research_artifact_service`, `cross_sectional_research_service`
- `etf_ranking_artifact_service`, `generic_ranking_artifact_service`, `generic_ranking_service`
- `optimizer_alpha_fundamentals`, `optimizer_alpha_service`, `optimizer_artifact_service`, `optimizer_handoff_constraints`, `optimizer_preview_service`, `optimizer_risk_service`, `optimizer_service`
- `ranking_artifact_catalog_service`, `ranking_artifact_open_service`
- `replacement_ranking`, `replacement_ranking_artifact_service`, `review_snapshot_artifact_service`
- `strategy_lab`, `universe_resolver`

Delete schemas: `construction.py`, `generic_ranking.py`, `optimizer.py`, `ranking.py`, `research.py`

Delete data artifact directories: `data/artifacts/construction-artifacts/`, `data/artifacts/cross-sectional-research-artifacts/`, `data/artifacts/etf-ranking-artifacts/`, `data/artifacts/etf-replacement-ranking-artifacts/`, `data/artifacts/generic-ranking-artifacts/`, `data/artifacts/optimizer-handoffs/`

Delete test files for removed features: `test_construction_generic_ranking_handoff.py`, `test_construction_run_service.py`, `test_etf_ranking_artifact_service.py`, `test_etf_replacement_ranking.py`, `test_etf_replacement_ranking_artifact_service.py`, `test_generic_ranking.py`, `test_generic_ranking_phase2.py`, `test_optimizer_alpha_fundamentals.py`, `test_optimizer_alpha_service.py`, `test_optimizer_risk_service.py`, `test_optimizer_service.py`, `test_strategy_lab.py`, `test_universe_resolver_russell1000.py`, `test_candidate_constraints.py`, `test_candidate_construction.py`, `test_candidate_formation.py`

**Acceptance criteria:**
- Backend starts cleanly with no import errors.
- `pytest` passes on the remaining tests.
- No reference to removed modules exists anywhere in the remaining codebase.

---

### US-8.6
**Remove backtest and monitoring backend**

> As a developer, I want the backtests route module gone — the routes it served are no longer in the product.

`app/api/routes/backtests.py` is large (~1,500+ lines) and covers: portfolio allocation backtests, replacement-intent replay, overlay preview, optimizer handoff replay, construction artifact preview, monitoring definitions (CRUD, alerts, timelines, episodes), and more.

The only question before deletion: do `dashboard_history_engine.py` or `diagnostics_engine.py` import from `portfolio_backtest_engine.py` or `backtest_engine_service.py`? If yes, those service files are trimmed to the used subset only, not deleted. If no, they are deleted.

Steps:
1. Audit imports: grep for what `dashboard_history_engine` and `diagnostics_engine` actually import from the backtest layer.
2. Delete `app/api/routes/backtests.py`, unregister from `main.py`.
3. Delete `monitor_definition_artifact_service.py`.
4. Delete or trim `portfolio_backtest_engine.py` and `backtest_engine_service.py` based on audit.
5. Delete `data/artifacts/monitor-definitions/`.
6. Delete test files: `test_backtests.py`, `test_portfolio_allocation_backtests.py`, `test_mocked_flows.py`.

Delete schema: `backtest_engine.py` (if no longer imported by kept services).

**Acceptance criteria:**
- `pytest` green on the remaining tests.
- Backend starts cleanly.
- `backtests.py` route module does not exist.

---

### US-8.7
**Prune portfolio feature directory**

> As a developer, I want features/portfolio/ to contain only components that Dashboard and Exposure actually render — no orphaned replacement-ranking or variant components.

Delete from `features/portfolio/`:
- `PersistedReplacementRankingReview.tsx` (was used by Workspace Candidate Idea)
- `ReplacementRankingReview.tsx` + `ReplacementRankingReview.test.tsx`
- `VariantList.tsx` (was used by Workspace / Exposure variant picker — verify Exposure still works after removal)
- `TrendRiskOverlaysPanel.tsx` + test (was a Workspace/Monitoring component — verify Exposure doesn't use it)

Also prune `features/portfolio/types.ts` of all types that supported removed features (ranking artifact types, construction types, optimizer handoff types, monitor definition types, etc.).

**Acceptance criteria:**
- `features/portfolio/` contains only files consumed by Dashboard or Exposure.
- Exposure tab and Dashboard tab render correctly (no visual regression).
- `tsc --noEmit` clean, `vitest run` green.

---

### US-8.8
**Reset docs and contracts**

> As a developer joining the project, I want the documentation to reflect only what the product actually does, so I can onboard without learning about features that no longer exist.

Scope:
- Delete `docs/contracts/`: `backtest-fields.md`, `candidate-workflow-fields.md`, `etf-ranking-fields.md`, `generic-ranking-fields.md`, `research-artifact-fields.md`
- Archive or delete `docs/product/prd/epic-3-construction-optimizer-methodology.md` and `docs/product/prd/epic-5-usable-core-flow.md` (replaced by this epic)
- Rewrite `docs/product/current-product-state.md` to describe only Dashboard + Exposure
- Rewrite `docs/product/epic-roadmap.md` — archive old slice log, record Epic 8 as the active epic
- Update `docs/product/stories/README.md` — mark old stories as archived
- Rewrite `CLAUDE.md` — remove references to ranking/construction/optimizer/monitoring architecture, update the feature directory map, remove obsolete guardrails
- Update `docs/finance/financial-methodology.md` — remove methodology sections for deleted features

**Acceptance criteria:**
- No doc references a removed tab, route, service, or artifact kind.
- `CLAUDE.md` gives an accurate picture of the two-tab product.
- A developer following `CLAUDE.md` can orient themselves without encountering dead ends.

---

### US-8.9
**Add portfolio drift vs index benchmarks to Exposure**

> As a portfolio researcher, I want to see how my portfolio return compares to major market indexes at the top of Exposure, so that I immediately understand whether my holdings are tracking, outperforming, or underperforming the market.

**What to show:**
A compact "vs Market" panel at the very top of the Exposure tab (above the holdings breakdown). For the currently loaded portfolio:
- Rolling return: portfolio vs benchmark for 1-month, 3-month, 6-month, 12-month, and since-import windows
- Benchmark default: S&P 500 (SPY). User can switch to other available indexes (Russell 1000, MSCI World / VT proxy if data allows) via a small dropdown.
- Delta cards: each window shows portfolio return, benchmark return, and the spread (alpha). Color-coded green/red for positive/negative outperformance.
- A sparkline or small chart showing cumulative portfolio return vs benchmark return since import.

**Backend:**
New endpoint (or extend an existing analytics engine response) that accepts the portfolio snapshot and a benchmark symbol, and returns per-window return pairs. The benchmark_service.py already fetches index return data; the dashboard_history_engine already computes portfolio returns. This story wires them together into a dedicated drift surface.

**Acceptance criteria:**
- Exposure tab shows a "vs Market" section above the current holdings breakdown.
- Section displays return vs S&P 500 (SPY) for 1m, 3m, 6m, 12m, and since-import windows.
- User can select a different benchmark from a dropdown; the section refreshes.
- When market data is unavailable for a window, that window shows "—" (unavailable), not zero.
- Portfolio analytics below the new section are unchanged.
- Backend endpoint follows the existing trust-level semantics (verified/degraded/unavailable — no fabrication).

---

## Delivery order rationale

Stories 8.1 → 8.2 → 8.3 → 8.4 are ordered so the frontend is always compilable: first detach tabs (8.1), then delete feature directories (8.2, 8.3), then clean up App.tsx state (8.4). Attempting 8.4 before 8.2–8.3 would leave dangling imports.

Stories 8.5 → 8.6 clean the backend independently of the frontend. They can begin after 8.1 if desired, since the frontend no longer calls those routes.

Stories 8.7 → 8.8 clean up residual references and docs — they follow naturally after the major deletions.

Story 8.9 is last intentionally: it builds on the cleaned-up, focused codebase rather than adding new code into the current cluttered state.
