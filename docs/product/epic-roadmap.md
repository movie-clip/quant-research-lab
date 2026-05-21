# Epic Roadmap

This file is the living execution roadmap for the four active product epics.

- Shipped-state truth belongs in `docs/product/current-product-state.md`.
- Future-looking product direction belongs in `docs/product/roadmap.md`.
- Future-looking technical sequencing belongs in `docs/product/technical-roadmap.md`.

After every shipped slice or epic checkpoint, update this file first, then update shipped-state docs and contracts if the slice changed product truth.

## Roadmap Snapshot

| Epic | Objective | Current status | Current slice | Next slice | Last updated |
| --- | --- | --- | --- | --- | --- |
| 1. Imported-portfolio truth and reconciliation guard | Keep imported portfolio truth, trust semantics, and reconciliation explicit before downstream methodology layers | Read-only admission summary and sanitized desktop-local review metadata shipped/stabilized | Save-time current-evidence matching shipped | Deeper reconciliation workflow only if needed; local metadata remains non-trust-changing | 2026-05-10 |
| 2. Ranking and selection methodology guard | Generalize ranking into a broader methodology platform with explicit selection guardrails and artifact-backed reuse | **Phase closed / functionally complete.** generic_ranking platform, construction eligibility, Workspace integration, Russell 1000 universe, AND desktop discovery migration all shipped | No active slice | Pivot to Epic 3 breadth (more construction policies + richer constraints). Future Universe Expansion items (Russell 2000, MSCI EAFE, full IWB ingestion) are deferred to backlog — see Epic 2 Open Gaps | 2026-05-11 |
| 3. Construction and optimizer methodology guard | Deepen deterministic construction and constrained optimizer review on top of stronger upstream ranking contracts | Active epic — sector-concentration constraint milestone complete (slices 1-3 of 3: `max_sector_weight` constraint + sector metadata threading + desktop input) | Sector concentration constraint milestone complete | Next: risk-aware weighting policy (inverse-volatility), promote inverse-rank-weight excluded → opt_in, surface Top N in legacy ETF Ranking tab. Older breadth items remain valid (richer constraints, broader policy coverage, cleanup of narrow lineage assumptions). | 2026-05-12 |
| 4. Monitoring and overlay review guard | Extend narrow review-scoped monitoring into broader persisted discipline workflows | Phase closed / stabilized for current phase; shipped breadth includes persisted benchmark-trend and data-quality review families | No active slice | Future monitoring breadth only: broader monitor/overlay families, scheduling, remediation, and threshold management remain explicitly out of current phase | 2026-05-09 |

## Cross-Epic Guardrails

- Truth classes, degradation, withholding, and unavailability remain explicit.
- Persisted artifacts and typed handoffs remain authoritative.
- Desktop stays thin on finance logic.
- Optimization remains hypothetical and subordinate to rule-based construction.
- Fail-closed loading and lineage validation must not be weakened.

## Program Snapshot

- Current stage: prototype flow stabilized, regression green, desktop build green.
- Active epic: `2. Ranking and selection methodology guard`.
- Current sequence: `Epic 2 -> Epic 3 -> Epic 4`, while `Epic 1` remains the foundational guardrail.
- Epic 3 is phase closed / guardrail-complete for this phase; remaining construction and optimizer work is breadth expansion rather than guardrail closeout.
- Epic 4 is phase closed / stabilized for this phase; remaining monitoring and overlay work is breadth expansion rather than closeout work.
- Biggest current gap: **Epic 2 is functionally complete and phase-closed.** All stated Open Gaps are addressed: generic_ranking platform end-to-end (run → catalog → preflight → construction handoff → Workspace browser → review), two `index_constituent` families (sp500 live + russell1000 static-snapshot), and full desktop discovery migration to the generalized cross-kind path. The next active priority is Epic 3 breadth (more construction policies + richer constraints — risk-parity weighting, sector caps, turnover models). Epic 2 future-universe items (Russell 2000, MSCI EAFE, full IWB ingestion) are explicitly deferred to backlog rather than active slices.

## Epic 1. Imported-Portfolio Truth and Reconciliation Guard

### Objective

Keep imported portfolio truth, trust semantics, and reconciliation explicit before downstream ranking, construction, optimizer, or monitoring workflows are allowed to overclaim certainty.

### Shipped baseline

- Broker import, workspace snapshots, immutable saved nodes, and working drafts are shipped.
- Dashboard, Exposure, diagnostics, and replay now carry explicit trust/degradation/withholding semantics.
- Imported-history and combined-statement regression coverage was recently hardened.
- Imported bootstrap responses and the desktop Dashboard expose a read-only `ImportAdmissionSummaryV1` for residual cash, symbol/security identity, parsed position market-value reconciliation, and NAV comparability checks; it does not block workspace creation, rewrite values, or upgrade trust.
- Desktop-local `ImportAdmissionReviewDispositionV1` persistence is shipped/stabilized for non-pass admission checks; it records reviewer rationale and disposition locally without changing admission decision, trust level, broker truth, imported values, derived portfolio truth, or backend truth.
- Runtime load/build boundaries sanitize malformed local metadata, pass-status evidence, unknown extras, and non-finite captured numeric evidence without read-time IndexedDB rewrite; saves require captured evidence to match the current non-pass check evidence after null/default normalization.

### Target state

- Imported portfolio truth exposes explicit reconciliation evidence before downstream workflows make stronger claims from it.
- Residual cash, symbol mismatches, NAV breaks, and unsupported evidence states are reviewable as first-class non-mutating reconciliation outcomes.

### Open gaps

- No backend-authoritative exception-management workflow for residual breaks or import mismatches; shipped review metadata remains local and non-trust-changing.

### Planned slices

- Expand read-only admission summary into a deeper reconciliation surface only if needed.
- Future exception workflows must stay explicit about desktop-local metadata versus any separate backend-authoritative evidence flow; local dispositions do not change trust.

### Dependencies

- Feeds all other epics.

### Evidence to keep aligned

- `docs/product/current-product-state.md`
- `docs/finance/financial-methodology.md`
- `docs/contracts/exposure-fields.md`
- import, analytics, and route tests under `services/quant-engine/app/tests`

### Exit criteria

- Imported truth admission evidence is explicit, reviewable, and prevents downstream overclaiming without blocking workspace creation or mutating trust.

## Epic 2. Ranking and Selection Methodology Guard

### Objective

Generalize ranking into a broader methodology platform with explicit selection guardrails, reusable artifact-backed discovery, and canonical downstream handoffs.

### Shipped baseline

- Persisted ETF ranking artifacts are shipped.
- Persisted intent-bound replacement ranking artifacts are shipped.
- Generalized ranking artifact catalog and recent discovery are shipped backend capabilities.
- Desktop can reopen recent ETF ranking runs and carry selected ranking artifacts into review.
- **Generic ranking platform (`generic_ranking` artifact kind) is shipped**: backend `POST /strategy-lab/ranking/run`, `GET /strategy-lab/ranking/artifacts/recent`, `GET /strategy-lab/ranking/artifacts/{artifact_id}`; desktop `Generic Ranking` tab with universe spec, score config presets, and persisted run reload; cross-kind catalog now surfaces generic_ranking alongside ETF and replacement artifacts.
- **Generic ranking factor coverage**: 11 price-bar factors (momentum, volatility, drawdown, liquidity) + 8 fundamental factors (4 quality via Novy-Marx/Sloan/AQR formulas, 4 value via FMP TTM ratios — Greenblatt/Fama-French).
- **Generic ranking universe coverage**: `etf_peer_group`, `custom_list`, `broad_equity_screen`, `sector_screen`, and `index_constituent` (S&P 500 via FMP `/stable/sp500-constituent`).

### Target state

- Ranking discovery, open, and downstream handoff work through the generalized artifact platform rather than ETF-only seams.
- Selection methodology becomes more explicit than a simple ordered list.

### Open gaps

- All ETF Ranking desktop discovery now routes through the generalized cross-kind path (`/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking`). The legacy ETF-native `/recent/metadata` endpoint is no longer called by the desktop — peer-group filter options are derived client-side from the unfiltered generalized recent response. The legacy backend route remains for any external consumers but is not on a desktop-blocking path.
- Generic ranking artifacts are construction-eligible AND surfaced in the Workspace Candidate Idea section via `PersistedGenericRankingConstructionBrowser`. The end-to-end seam (run → catalog → preflight → handoff → construction review) is closed.
- Epic 2 has no remaining blocking gaps. Future breadth work is captured in the Future Universe Expansion section below as a deferred backlog rather than active slices.

### Future Universe Expansion (deferred backlog)

When the platform is ready for broader cross-universe ranking research, the following extensions reuse the shipped generic ranking + static-snapshot patterns without new infrastructure:

- **Full Russell 1000 ingestion**: replace the bundled 26-name representative sample at `data/universe/index_snapshots/russell1000.json` with the full ~1000 names. Approach: scripted download of iShares IWB ETF holdings CSV from BlackRock, normalize symbol + sector, write to the snapshot file with refreshed `snapshot_date` and `source_url`. The bundled file format (`index_snapshot_v1`) is already wired and validated; only an ingestion script is missing. Defer until full Russell 1000 ranking is actively needed for research workflows.
- **Russell 2000** (`index_id="russell2000"`): same pattern. Source: iShares IWM ETF holdings (free CSV from BlackRock product page). Add `russell2000` to the `IndexId` Literal in `app/schemas/generic_ranking.py`, bundle a snapshot at `data/universe/index_snapshots/russell2000.json`, and the existing `_load_index_snapshot()` + resolver dispatch handle the rest. No new tests beyond a couple of dispatch checks.
- **MSCI EAFE** (`index_id="eafe"`): same pattern. Source: iShares EFA ETF holdings. Adds international-developed coverage to the universe set.
- **Sector ETF peer groups as named universes**: the `etf_peer_group` universe kind already supports explicit symbol lists. Codifying common sector groupings (e.g. XLK/XLF/XLV/etc. clusters) as named static lists would reduce repeated user input.
- **Custom mandate universes** (e.g. dividend aristocrats, ESG screens): same `index_constituent` pattern via static snapshots from the relevant index ETF holdings.

Note for next agent: every entry above is intentionally LOW-PRIORITY relative to active product workflows. The bundled Russell 1000 sample is sufficient for development, demo, and testing; full ingestion only matters when the user actually runs production rankings against the full Russell 1000 set. Resist sunk-cost reasoning — adding more universes that nobody uses adds maintenance burden without product value.

- **Selection guardrails are not yet productized as a standalone surface**: the construction preflight already returns typed eligibility/readiness for the three supported ranking families, which is the minimum viable selection guardrail. Broader selection guardrails (e.g. per-factor coverage warnings, cross-factor agreement scores, confidence-aware suppression) are a future direction, not blocking.

### Planned slices

- `Shipped`: desktop recent discovery now uses generalized `/strategy-lab/ranking-artifacts/recent` with `artifact_kind=etf_ranking`, while ETF-native metadata remains temporary for peer-group filter options.
- `Shipped`: Workspace Candidate Idea now browses and opens persisted replacement ranking artifacts read-only through generalized recent plus generalized preflight/open, with fail-closed validation and ephemeral in-memory state only.
- `Shipped`: persisted ETF ranking artifacts can now hand off into persisted construction review through canonical construction preflight plus construction run, exposed from both ETF Ranking and Workspace Candidate Idea while remaining ETF-only in this slice.
- `Shipped`: persisted intent-bound ETF replacement ranking artifacts can now also hand off into persisted construction review through the same canonical construction preflight plus construction run seam, while remaining replacement-family-only in this slice.
- `Shipped`: construction preflight for the two supported ranking families now returns typed eligibility/readiness semantics, so desktop can distinguish supported-but-ineligible artifacts from malformed or unsupported artifact states before `Review In Construction`.
- `Shipped` (Phase 1, PR #2): generic_ranking artifact kind, UniverseSpec, versioned ScoreConfig with content-addressed digest, EligibilityRecord, CompositeScoreTrace, fail-closed validation, recent-index discovery, desktop Generic Ranking tab.
- `Shipped` (Phase 2, PR #3): index_constituent universe (S&P 500), 8 fundamental factor IDs (quality + value), FMP `get_ratios_ttm`/`get_key_metrics_ttm`/`get_sp500_constituents` methods, cross-kind catalog inclusion of generic_ranking, graceful degradation when fundamental factors requested without FMP key.
- Next: **construction eligibility expansion** — add `generic_ranking` to the construction preflight allowlist, expose `Review In Construction` from Generic Ranking results, surface generic_ranking in Workspace Candidate Idea browser. This closes the dead-end currently isolating Generic Ranking from the portfolio improvement workflow.

### Dependencies

- Depends on imported truth guardrails.
- Unlocks richer construction and optimizer methodology work.

### Evidence to keep aligned

- `docs/product/current-product-state.md`
- `docs/product/roadmap.md`
- `docs/product/technical-roadmap.md`
- `docs/contracts/etf-ranking-fields.md`
- ranking artifact and strategy-lab tests under `services/quant-engine/app/tests`

### Exit criteria

- Generalized ranking artifact discovery/open is the visible default desktop path for shipped ranking families.

## Epic 3. Construction and Optimizer Methodology Guard

### Objective

Deepen deterministic construction and constrained optimizer review on top of stronger upstream ranking contracts and explicit review-basis provenance.

### Shipped baseline

- Persisted construction engine, policy catalog, preview, and replay are shipped.
- Construction provenance, hard-constraint truth, weighting trace, and turnover diagnostics are shipped.
- Optimizer preview, handoff, replay, and methodology provenance are shipped.
- Desktop restore and review-basis handling were recently hardened.
- Desktop `Review In Construction` now consumes authoritative backend policy discovery for the shipped ranking-to-construction bridge.

### Target state

- Desktop uses authoritative backend construction policy discovery and stronger ranking-to-construction handoff.
- Optimizer review compares against stronger rule-based baselines under the same explicit provenance rules.

### Phase closeout status

- Closed for this phase / guardrail-complete.
- The shipped narrow boundary preserves artifact-backed ranking-to-construction handoff, backend-authoritative policy discovery, fixed launch-profile semantics, fail-closed lineage validation, explicit review basis, and hypothetical-only optimizer/construction truth separation.

### Future breadth gaps

- Canonical ranking-to-construction handoff is shipped for the narrow `ranking_artifact_review_handoff_v1` launch profile; broader eligibility and parameterization remain open.
- Policy and constraint breadth remain narrow.
- Ranking-entry portfolio lineage and policy parameterization are still intentionally narrow in the current desktop bridge.

### Planned slices

- `Shipped`: desktop ranking-to-construction review now uses authoritative backend `/construction/policies` discovery for policy selection and exposes required `max_position_weight` plus optional `min_position_weight` inputs while keeping the bridge parameter-light.
- `Shipped`: the broader Epic 3 launch boundary is now explicit and stabilized as `preflight -> typed handoff -> /construction/run -> persisted construction artifact review` for exactly two supported ranking families: `etf_ranking` and `intent_bound_etf_replacement_ranking`, with desktop fail-closed policy discovery and fixed `top_n = 2` launch semantics.
- `Shipped`: the existing Workspace artifact-backed ranking-to-construction launch browsers now also expose optional `max_turnover_weight` and optional `max_trade_intent_count`, with shared local validation, omission-on-blank request serialization, and no widening of policy authority, ranking-family support, or inline launch paths.
- `Shipped`: canonical launch context is now preserved and fail-closed across the full shipped ranking-to-construction review boundary, including ranking artifact id/schema/ranking lineage, current portfolio identity/timestamp, selected policy id/definition, and fixed `top_n` lineage through persisted construction artifact reopen.
- `Shipped`: backend policy discovery now stamps one canonical `ranking_artifact_review_handoff_v1` launch profile with explicit default/opt-in/excluded status, desktop consumes that metadata instead of hardcoded launch allowlists/defaults, and review surfaces read back the shipped `top_n = 2` plus required/optional hard-constraint boundary next to construction launch controls.
- Future breadth work: add configurable `top_n`, richer constraints, broader policy coverage, optional inverse-rank promotion if desired, broader ranking-family construction eligibility, and cleanup of narrow lineage assumptions.

### Dependencies

- Depends on Epic 2 generalization.

### Evidence to keep aligned

- `docs/product/current-product-state.md`
- `docs/product/technical-roadmap.md`
- `docs/contracts/backtest-fields.md`
- construction and optimizer tests under `services/quant-engine/app/tests`

### Exit criteria

- Supported construction and optimizer review workflows consume explicit upstream artifact/handoff boundaries and preserve review basis throughout.
- Broader ranking-family eligibility, policy breadth, configurable `top_n`, and richer constraints remain future work.

## Epic 4. Monitoring and Overlay Review Guard

### Objective

Extend narrow review-scoped monitoring into broader persisted discipline workflows without weakening current alert lifecycle or fail-closed review authority.

### Shipped baseline

- `benchmark_trend_overlay_v1` monitor-definition workflow is shipped.
- `data_quality_monitor_v1` is shipped as a distinct persisted data-quality monitor family.
- Latest-observation, recovered-review, active alert-episode, and timeline/history review surfaces are shipped.
- Workspace restore from persisted monitor review state was recently strengthened.

### Target state

- Monitoring grows into a broader discipline layer with more visible inbox/history workflows and more than one narrow monitor family.

### Future breadth gaps

- Monitor-family breadth is still narrow.
- Monitoring is still more review-scoped than ongoing discipline-system level.
- Factor drift, concentration drift, benchmark-relative drift, and volatility are not persisted monitor families.

### Planned slices

- `Shipped`: Workspace Compare now surfaces the backend-rooted active alert-episode inbox as a read-only `Active Alert Review Inbox`, loading persisted open episode rows directly from the existing inbox route and reopening timeline review only through persisted episode timeline handoff ids.
- `Shipped`: Workspace Compare now includes a definition-scoped `Alert Episode History` drill-in that loads bounded persisted episode records from the existing history route, surfaces truth/provenance/windowing metadata, and opens the existing timeline review through each row's persisted handoff ids.
- `Shipped`: Monitoring now includes a read-only `Monitoring Discipline Overview` for existing `benchmark_trend_overlay_v1` persisted definitions, sourced from catalog metadata only with fail-closed contract and lineage validation.
- `Shipped`: Monitoring now includes a read-only `Monitor Family Readiness Overview` that separates persisted `benchmark_trend_overlay_v1` and `data_quality_monitor_v1` review support from replay-derived signals, renders explicit decision/reason codes, gate breakdowns, evidence summaries, and provenance summaries, and lists persistence gates missing before any additional family could become persisted.
- `Shipped`: Integrated `data_quality_monitor_v1` persisted monitor family plus family-aware readback completion: backend create/evaluate/catalog/recent/observation/history/timeline/inbox/episodes and desktop readback now treat data quality as evidence-only input reliability, while benchmark trend preserves legacy benchmark-threshold semantics.
- No active slice; future breadth work must not implicitly widen monitor-family support.

### Dependencies

- Benefits from stronger upstream ranking, construction, and replay methodology boundaries.

### Evidence to keep aligned

- `docs/product/current-product-state.md`
- `docs/product/roadmap.md`
- `docs/product/technical-roadmap.md`
- `docs/contracts/backtest-fields.md`
- monitoring and route tests under `services/quant-engine/app/tests`

### Exit criteria

- Current phase is satisfied by persisted `benchmark_trend_overlay_v1` plus `data_quality_monitor_v1` review coverage, with no overclaim of continuous monitoring, scheduling, remediation, threshold management, or broader monitor-family support.

## Slice Update Log

### 2026-05-12 - Epic 3 breadth: max_sector_weight desktop input (milestone slice 3 of 3)

- Epic: `3. Construction and Optimizer Methodology Guard`
- Milestone: **Sector concentration constraint** — slice 3 of 3 (final). Milestone complete.
- Slice: surface the `max_sector_weight` hard constraint as an optional desktop input in the three Workspace construction browsers so it is user-reachable end-to-end. Status: shipped.
- Scope delivered:
  - **Shared validator** (`rankingConstructionMaxPositionWeight.ts`): `DEFAULT_RANKING_CONSTRUCTION_MAX_SECTOR_WEIGHT` (`''`), `MAX_RANKING_CONSTRUCTION_MAX_SECTOR_WEIGHT` (`1`), `RankingConstructionMaxSectorWeightValidation` type, `validateOptionalMaxSectorWeightInput` (decimal in `(0, 1]`, and `>= max_position_weight` invariant), wired into `validateRankingConstructionConstraintInputs` plus a standalone `validateRankingConstructionMaxSectorWeightInput`.
  - **Handoff runner** (`rankingArtifactConstructionHandoff.ts`): new optional `maxSectorWeight` param threaded into `hard_constraints.max_sector_weight` (omitted when blank).
  - **Three Workspace construction browsers** (`PersistedEtfRankingConstructionBrowser`, `PersistedReplacementRankingBrowser`, `PersistedGenericRankingConstructionBrowser`): optional `Max Sector Weight` input with state, validation, helper text, blocked-reason chaining, and request threading. ETF / replacement browsers note in helper text that their handoffs carry no sector labels (`not_evaluated`); the generic browser notes evaluation depends on ranked names carrying sector labels.
  - **Latent bug fixed in the same file**: `runRankingArtifactConstructionHandoff` previously hard-rejected `top_n != 2` (`'only supports top_n=2'`) and validated run lineage against the fixed constant — this silently disabled the configurable-`top_n` slice end-to-end (no test caught it; there is no dedicated handoff test and the browser tests never ran a non-2 handoff). It now accepts `top_n` in `[2, 20]` and checks `normalized_inputs.top_n` against the requested policy value.
- Guard impact: desktop stays thin — all validation mirrors backend bounds, no portfolio math added. No truth-class / trust-ladder / no-execution change. `backtest-fields.md` and `financial-methodology.md` updated.
- Tests/evidence: 2 new `PersistedGenericRankingConstructionBrowser` tests (max-sector-weight input validation incl. the `>= max_position_weight` invariant; non-default `top_n` + `max_sector_weight` threaded into the run request body). Full suite: backend `1277 passed`, frontend `530 passed`; `tsc --noEmit` clean.
- Milestone outcome: the sector-concentration constraint is now end-to-end — backend mechanism (slice 1), sector metadata threading (slice 2), desktop input (slice 3). A `generic_ranking` handoff with a sector-bearing universe now evaluates `max_sector_weight` from a user-set cap.

### 2026-05-12 - Epic 3 breadth: sector metadata threading (milestone slice 2 of 3)

- Epic: `3. Construction and Optimizer Methodology Guard`
- Milestone: **Sector concentration constraint** — slice 2 of 3.
- Slice: thread per-symbol sector metadata end-to-end so `generic_ranking` artifact-handoff construction runs can actually evaluate `max_sector_weight` (slice 1 shipped the constraint mechanism; without sector data it always withheld). Status: shipped.
- Scope delivered:
  - **Universe resolver** (`services/universe_resolver.py`): the three resolution paths (`_screen_equity`, `_resolve_index_constituents`, `_filter_by_profiles`) now also return a `symbol -> GICS sector` map, harvested from the screener / index-snapshot / profile rows they already iterate. `resolve()` retains it on the snapshot, scoped to evaluated members and dropping empty sectors.
  - **Schema** (`schemas/generic_ranking.py`): `UniverseSpecSnapshot.member_sectors` (`dict[str, str]`, default `{}`) and `GenericRankingRow.sector` (`str | None`). Both additive-optional — prior persisted `generic_ranking` artifacts still load.
  - **Ranking engine** (`services/generic_ranking_service.py`): stamps `GenericRankingRow.sector` from `universe_snapshot.member_sectors`.
  - **Construction handoff** (`construction_run_service.py`): `_build_ranked_candidate_from_generic_ranking_row` threads `row.sector` into `ConstructionRankedCandidateInput.sector`, so a `generic_ranking` handoff run now evaluates `max_sector_weight` (`pass`/`binding`/`fail`) instead of `not_evaluated` whenever the universe carried sectors.
  - **Desktop types** (`generic-ranking/types.ts`): `UniverseSpecSnapshot.member_sectors` and `GenericRankingRow.sector` mirrored for contract parity (read-only; no UI yet).
- Coverage scope: `etf_peer_group` / `custom_list` universes consult no sector source (rows carry no sector); `etf_ranking` / `intent_bound_etf_replacement_ranking` handoffs still carry no sector. Those paths keep evaluating `max_sector_weight` as `not_evaluated` — honest, not a regression.
- Guard impact: additive-optional schema, no artifact schema-version bump; no truth-class / trust-ladder / no-execution change. `financial-methodology.md`, `backtest-fields.md`, `generic-ranking-fields.md` updated in the same pass.
- Tests/evidence: 3 new resolver tests (`member_sectors` populated for index, empty for explicit-list, populated for sp500) + 1 new handoff test (sector threaded into ranked candidates). Full suite: backend `1277 passed`, frontend `528 passed`.
- Pre-existing issue flagged (not this slice): `apps/desktop/src/features/backtest/constructionPolicyCatalog.ts` has 2 `tsc` errors from the configurable-`top_n` slice — the TS `launch_top_n` type is still the literal `2`. `tsc` is not run by `run_all_tests.py`; spun off as a separate task.
- Next: milestone slice 3 — desktop `max_sector_weight` input in the 3 construction browsers + sector-evaluation rendering.

### 2026-05-12 - Epic 3 breadth: max_sector_weight constraint mechanism (milestone slice 1 of 3)

- Epic: `3. Construction and Optimizer Methodology Guard`
- Milestone: **Sector concentration constraint.** Investigation confirmed this is a multi-slice milestone, not a single slice: no ranking artifact carries per-symbol sector today, and `ConstructionRankedCandidateInput` had no sector field. Planned slices: (1) backend constraint mechanism — this slice; (2) thread sector metadata into ranking artifacts so artifact-handoff runs can evaluate it; (3) desktop `max_sector_weight` input + sector evaluation rendering.
- Slice: backend `max_sector_weight` optional hard constraint. Status: shipped.
- Scope delivered:
  - **Schema** (`services/quant-engine/app/schemas/construction.py`): optional `sector` on `ConstructionRankedCandidateInput` and `ConstructionSelectedName`; optional `max_sector_weight` (`gt=0, le=1`) on `ConstructionHardConstraints` with the request invariant `max_sector_weight >= max_position_weight`; `"max_sector_weight"` added to the `ConstructionConstraintEvaluation.constraint_id` literal; `max_sector_weight_constraint` capability on `ConstructionPolicyCatalogEntry`; a tolerant persisted-artifact validator block (old artifacts without the constraint still load).
  - **Engine** (`construction_run_service.py`): `_compute_max_selected_sector_weight` sums target weight per sector across selected names; a cap violation appends `SECTOR_CONCENTRATION_FAILURE_REASON` and makes the run infeasible (mirrors the turnover cap — no silent reshuffle). `_evaluate_constraints` emits a `max_sector_weight` evaluation in both feasible and infeasible branches; status is `not_evaluated` when the cap is unrequested OR any selected name lacks a sector label (fail-closed withholding, never assumed-satisfied).
  - **Catalog + route**: all three policies advertise `max_sector_weight_constraint = supported_optional`; `/construction/policies` gains a `max_sector_weight_constraint` filter.
- Guard impact:
  - methodology-meaningful: a new hard constraint. `docs/finance/financial-methodology.md` and `docs/contracts/backtest-fields.md` updated in the same pass.
  - fail-closed preserved: violated cap -> infeasible run with no persisted target weights; missing sector metadata -> `not_evaluated`, never a fabricated sector total.
  - additive-optional schema changes keep the 4 committed `construction_artifact_v1` artifacts valid; no schema-version bump.
- Tests/evidence:
  - 9 new tests in `test_construction_run_service.py` (not-requested, sector-metadata-absent withholding, pass, binding, fail/infeasible, cap-below-position rejection, out-of-range rejection).
  - Updated existing construction/route/replay tests for the new `sector` field and `max_sector_weight` constraint entry. Full backend suite: `1264 + 9 = 1273 passed`.
- Next: milestone slice 2 — thread per-symbol sector into `generic_ranking` artifacts (engine populates from screener/instrument data) and through the construction handoff builder, so artifact-handoff runs evaluate the cap instead of withholding it.

### 2026-05-12 - Testing flow cleanup: goldens freshness + frontend baseline (PR #7 + PR #8)

- Epic: cross-cutting infrastructure (not tied to a single product epic).
- Slice: harden the test workflow so bare `pytest` no longer produces ~40 spurious failures, and restore the frontend baseline to fully green.
- Status: shipped.
- Scope delivered:
  - **Goldens freshness fixture** (`services/quant-engine/app/tests/conftest.py`): autouse session-scope `_check_dashboard_goldens_freshness` regenerates the dashboard goldens text via the export script and compares to the committed `apps/desktop/src/test/dashboardGoldens.ts`. Failure mode is a fast actionable message naming the regen command. Bypass via `SKIP_GOLDEN_FRESHNESS_CHECK=1` for narrow runs that don't touch the dashboard surface. `source_path` strings are normalized before comparison so the check tolerates running pytest from a non-primary worktree.
  - **Goldens canonicalization** (`services/quant-engine/app/scripts/export_dashboard_goldens.py`): `_normalize_snapshot` now writes `Path(source_path).name` (basename) instead of the absolute path. Committed goldens are now stable across worktrees and machines. Extracted pure `render_dashboard_goldens_text(repo_root)` so the freshness fixture can call it without I/O.
  - **Epic 3 follow-up backend fixes that had been left uncommitted on the worktree**: additional sample ETF series (XLB/XLP/XLU/XLY US sector + IUFS/IUHC/VDST/VUAA/BTEC UCITS proxies) for strategy-lab peer-group tests, mock-prices conftest helper for FF2026 dashboard regression, and widened `top_n in [2, 20]` range tests in `test_routes.py`.
  - **`CLAUDE.md` Development Commands** flags `python scripts/run_all_tests.py` as the canonical entrypoint and explains the freshness fixture / bypass env var.
  - **`testing-triage` skill** gains a "Canonical entrypoint" section and a stale-goldens entry under backend failure patterns.
  - **Frontend baseline (PR #8)**: fixed 8 pre-existing failures — 5 DashboardPanel time-bombs (pinned `vi.setSystemTime('2026-04-15T00:00:00Z')` in `beforeEach`), 2 App.test fetch-count assertions (2 → 3 reflecting 3rd construction-browser surface from Epic 2 Workspace integration), 1 FF2026 cache-dependent assertion (switched to `accountId` + `statementPeriod` so the test stays cache-independent).
- Guard impact:
  - no methodology, schema, trust-state, or truth-class semantics changed.
  - the freshness fixture *strengthens* the guardrail "every UI metric maps to one engine formula and one code path" by catching backend-vs-golden drift before it can mask UI assertion drift.
  - the FF2026 assertion change keeps the same semantic (broker truth is restored correctly from persisted state) using fields that don't conflate broker truth with benchmark availability.
- Tests/evidence:
  - `python scripts/run_all_tests.py` -> backend `1264 passed`, frontend `528 / 528 passed`, "All tests passed."
  - Bare `pytest` from `services/quant-engine/` -> `1264 passed`. Confirmed the freshness fixture fires with an actionable failure message when goldens are stale.

### 2026-05-12 - Epic 3 breadth: configurable top_n at construction launch

- Epic: `3. Construction and Optimizer Methodology Guard`
- Slice: widen the construction-launch `top_n` parameter from a fixed scalar `2` to a configurable range `[2, 20]`. First Epic 3 breadth slice.
- Status: shipped.
- Scope delivered:
  - **Backend schema** (`services/quant-engine/app/schemas/construction.py`):
    - `ConstructionPolicyLaunchTopN` changed from `Literal[2]` to `Annotated[int, Field(ge=2, le=20)]`.
    - New module-level constants `CONSTRUCTION_POLICY_LAUNCH_TOP_N_MIN = 2` and `CONSTRUCTION_POLICY_LAUNCH_TOP_N_MAX = 20`.
    - Per-policy catalog entries still declare `launch_top_n=2` as the recommended default. Users opt into a wider value at request time via `ConstructionPolicyInput.top_n` — the value is now an independent runtime input, not a fixed launch profile constraint.
  - **Backend service** (`services/quant-engine/app/services/construction_run_service.py`):
    - Replaced the hard equality check `policy.top_n != 2` with a range check (`[MIN, MAX]`). Error message now reports the received value alongside the supported range.
    - Constants renamed from `RANKING_ARTIFACT_HANDOFF_LAUNCH_TOP_N` (scalar) to `_MIN`/`_MAX` (range).
  - **Backend route** (`services/quant-engine/app/api/routes/construction.py`):
    - The catalog filter allowlist for `launch_top_n` now enumerates the integer range [2..20] instead of reading off a `Literal` via `get_args`. HTTP 422 still rejects values outside the range (or non-integers) with explicit error text.
  - **Frontend constants + validators** (`apps/desktop/src/features/backtest/constructionPolicyCatalog.ts` and `rankingConstructionMaxPositionWeight.ts`):
    - Added `RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N_DEFAULT/_MIN/_MAX` constants. The legacy `RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N` symbol is kept as an alias for the default value (deprecation-friendly).
    - New `validateRankingConstructionTopNInput()` helper returning `{value, error}`.
    - `parseLaunchProfile` and `parseConstructionPolicyRow` validators now check the range instead of equality to 2. Cross-check between row-level and profile-level `launch_top_n` preserves the existing "policy row metadata is internally consistent" guard.
    - `buildConstructionPolicyRunInput` accepts any integer in the range; rejects non-integers and out-of-range values explicitly.
  - **Frontend UI** (3 construction browsers + Workspace shell):
    - `PersistedGenericRankingConstructionBrowser`, `PersistedEtfRankingConstructionBrowser`, `PersistedReplacementRankingBrowser` all gained a "Top N" number input that drives the construction handoff. Default value is `'2'` for backward-compat; user can pick any value in `[2, 20]`.
    - The Top N validation error blocks the "Review In Construction" CTA and surfaces in the per-row blocked-reason small text.
    - Helper text changed from "while the shipped ranking launch keeps top_n fixed at 2" to a clearer pairing note: "Pair with Top N so that max × top_n ≥ 1".
    - `EtfRankingPanel` (the legacy ETF Ranking tab) intentionally still uses `top_n=2` by default — surfacing a Top N input there is a deferred follow-up; the primary configurable-top_n path is through the Workspace browsers.
- Guard impact:
  - widens a launch parameter, not financial methodology. No factor scores, weighting formulas, or construction math changed — only the count of names selected at construction launch.
  - per-policy catalog metadata (`launch_top_n` in each policy row) remains at the recommended default of `2`. Catalog discovery filters still work the same way for that value. The widening is entirely at the user-input layer.
  - existing tests that asserted the strict `==2` boundary were updated to assert the new range: out-of-range values (1, 21, non-numeric) still fail closed; in-range values (3, 5, 10, 20) now succeed.
  - persisted construction artifacts continue to record `top_n` as part of `normalized_inputs`, so prior reproducibility properties are preserved.
- Tests/evidence:
  - Backend: 3 updated tests + 1 new test in `test_construction_run_service.py` covering range validation at both the handoff-builder and the catalog-filter layers.
  - Frontend: 1 updated test in `EtfRankingPanel.test.tsx` (now exercises out-of-range fixture) + 1 new test in `PersistedGenericRankingConstructionBrowser.test.tsx` covering default value, in-range, below-min, above-max, non-numeric input paths.
  - 520/527 frontend (same baseline as main, no regressions); construction subset clean.
- Next Epic 3 breadth candidates (deferred to subsequent slices):
  - **Risk-aware weighting policy** (e.g., `top_n_inverse_volatility_weight_v1`): requires construction engine to consume per-candidate factor scores (volatility) from the ranked artifact. Larger architectural change because today's construction policies are rank-aware but not factor-data-aware.
  - **Sector concentration constraint**: new optional `max_sector_weight` constraint requiring sector metadata per candidate.
  - **Surface Top N input in legacy ETF Ranking tab**: extend the configurable top_n control to the original ETF Ranking surface that bypasses the Workspace browsers.
  - **Promote `top_n_inverse_rank_weight_v1` from `excluded` to `opt_in`** in the launch profile so users can pick it explicitly (currently launchable policies are equal-weight + linear-rank-weight only).

### 2026-05-11 - Stabilize / cleanup pass

- Epic: cross-cutting infrastructure (not tied to a single product epic).
- Slice: post-Epic-2 stabilization sweep — branch rename, dependency hygiene, test isolation hardening, artifact-noise cleanup.
- Status: shipped.
- Scope delivered:
  - **Default branch renamed `master` → `main`** on GitHub via API rename. Local refs and tracking updated across worktrees. Zero code, doc, or config references to git-master existed (all hits in a `grep -i master` were unrelated: Mastercard, instrument-master data, factor-master-detail CSS class).
  - **Frontend dependency hygiene**: `@tauri-apps/plugin-dialog` and `@tauri-apps/plugin-fs` were declared in `apps/desktop/package.json` but not installed; a stale `node_modules/` was missing them. After `npm install`, the previously-blocked `App.test.tsx` suite now collects and runs — frontend pass count went from 389/394 → 520/527 (+131 tests previously failing to import).
  - **Test isolation hardened**: extended `services/quant-engine/app/tests/conftest.py` with an autouse fixture that monkeypatches `get_settings` for all four artifact-store modules (`etf_ranking_artifact_service`, `replacement_ranking_artifact_service`, `generic_ranking_artifact_service`, `optimizer_artifact_service`) to point at per-test `tmp_path_factory` directories. Explicit per-test `mocker.patch.object(...)` still overrides the fixture, so existing tests with their own paths keep working unchanged. Confirmed via full backend test run: `data/artifacts/` stays empty after running all 1262 tests.
  - **Test-noise cleanup**: removed 20 untracked test-generated artifact JSON files + 3 optimizer-handoff directories that had accumulated under `data/artifacts/etf-ranking-artifacts/`, `data/artifacts/generic-ranking-artifacts/`, and `data/artifacts/optimizer-handoffs/`. With the new conftest fixture, these won't reappear from future test runs.
- Guard impact:
  - the project's "artifacts are committed to git as auditable records" rule is preserved — user-generated artifacts from real ranking runs continue to be tracked. The cleanup removed only TEST-side-effect artifacts that leaked from route-layer tests, which were never authoritative.
  - branch rename has zero functional impact on the codebase; it is purely the GitHub default branch label.
  - the autouse fixture is non-destructive: existing test runs reproduce the same failure count (40 backend / 7 frontend) before and after the fixture extension. These failures are real but pre-existing test bugs (market-data unavailability, stale text matchers, etc.) — out of scope for a cleanup slice.
- Deferred to backlog:
  - **Dead `/strategy-lab/etf-ranking/artifacts/recent/metadata` test mocks** in `EtfRankingPanel.test.tsx` (17 instances), `App.test.tsx` (4 instances), and `BacktestWorkspacePanel.test.tsx` (1 instance) — desktop no longer calls that route, so these mock branches are never matched at runtime. Purely cosmetic; high-churn to remove. Defer until a future test-hygiene pass.
  - **Real test failures**: 40 backend failures (mostly in `test_strategy_lab.py`, `test_routes.py`, `test_portfolio_allocation_backtests.py`) and 7 frontend failures (5 in `DashboardPanel.test.tsx` for stale text matchers, 2 in `App.test.tsx` for monitoring handoff and Dashboard restore). These are real test bugs that need methodical per-test triage and fix, not stabilization-pass cleanup.
- Tests/evidence:
  - Backend after slice: 1222/1262 pass (40 pre-existing failures unchanged).
  - Frontend after slice: 520/527 pass (was 389/394 — +131 unblocked, same 7 real failures remain).
  - `data/artifacts/` verified empty after full backend run with the new conftest.

### 2026-05-11 - Epic 2 desktop ETF discovery fully migrated to generalized path

- Epic: `2. Ranking and selection methodology guard`
- Slice: remove the last ETF-native discovery call from the desktop and derive peer-group filter options client-side from the generalized cross-kind recent route.
- Status: shipped. **Closes Epic 2's last stated Open Gap.**
- Scope delivered:
  - Audit found the recent-runs discovery path (the main one) was already migrated in a prior slice. The only remaining ETF-native call was `loadRecentMetadata()` in `EtfRankingPanel.tsx`, hitting `/strategy-lab/etf-ranking/artifacts/recent/metadata` to populate the peer-group filter dropdown.
  - That call is now replaced with an unfiltered fetch against `/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking` followed by client-side dedup of the `effective_peer_group` values. Semantics are equivalent: both the legacy backend route and the new client logic dedup over the same `recent.jsonl` index — only the dedup location changed.
  - Result: zero ETF-native discovery calls remain on the desktop. All ETF Ranking discovery now flows through the generalized cross-kind path that already supports `etf_ranking`, `intent_bound_etf_replacement_ranking`, and `generic_ranking` artifact kinds.
- Guard impact:
  - Closes the Epic 2 Open Gap stated in this doc since 2026-05-06: "Desktop still leans on ETF-native recent discovery instead of the generalized ranking-artifact path."
  - Backend ETF-native `/recent/metadata` route is preserved for any external consumers but no longer on a desktop-blocking path. It can be deprecated in a future cleanup pass without affecting desktop behavior.
  - No behavior change for users — the peer-group filter dropdown still populates from the same underlying data (the ETF `recent.jsonl` index) with deterministic sort order.
- Tests/evidence:
  - 30/30 `EtfRankingPanel.test.tsx` tests pass unchanged. The legacy `/recent/metadata` mocks in those tests are now dead code (never matched) and can be cleaned up in a future test-hygiene pass.
  - 0 regressions in the broader frontend suite (389/394 — same 5 pre-existing `@tauri-apps/plugin-dialog` failures unrelated to this change).
- Epic 2 status after this slice: **functionally complete.** All stated Open Gaps are closed. Future breadth (additional index families, scripted full IWB ingestion, selection guardrails) is captured in the Future Universe Expansion deferred backlog under Epic 2's Open Gaps section.

### 2026-05-11 - Epic 2 generic_ranking Russell 1000 universe shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: extend the `index_constituent` universe family with Russell 1000 via static-snapshot resolution.
- Status: shipped.
- Scope delivered:
  - extended `IndexId` Literal in `app/schemas/generic_ranking.py` to include `russell1000` (was `sp500` only)
  - new `_load_index_snapshot()` loader in `app/services/universe_resolver.py` that reads versioned JSON snapshots from `data/universe/index_snapshots/<index_id>.json` with fail-closed validation: missing file, invalid JSON, schema_version mismatch, index_id field mismatch, malformed constituent rows all raise `IndexSnapshotError`
  - resolver `_resolve_index_constituents()` refactored to dispatch by `index_id`: `sp500` → live FMP `/stable/sp500-constituent`, `russell1000` → static snapshot loader; sector_include/sector_exclude filters apply identically across both paths
  - resolver degrades gracefully when the russell1000 snapshot file is unavailable: returns empty `evaluated_members` with a logged warning rather than raising — surfaces the trust state explicitly through the artifact instead of failing the request
  - bundled representative snapshot `data/universe/index_snapshots/russell1000.json`: 26 well-known large-cap names spanning 7 GICS sectors, with explicit provenance metadata (source = iShares IWB ETF holdings CSV, source_url, source_notes flagging it as a SAMPLE not the full membership)
  - desktop frontend extended: `IndexId` TS type now includes `russell1000`; `INDEX_LABELS` map renders human-readable labels with the resolution mode visible to the user (`S&P 500 (FMP live)`, `Russell 1000 (static snapshot)`)
  - 13 new backend tests covering schema validation, snapshot loader fail-closed paths, dispatch, sector filtering, and graceful degradation when the snapshot is missing
- Guard impact:
  - widens `index_constituent` from one to two index families without adding new live data sources or new infrastructure beyond a JSON snapshot loader
  - russell1000 path is intentionally static-snapshot-based (no FMP endpoint exists); reproducibility is preserved by `UniverseSpecSnapshot.evaluated_members` capturing the resolved members at run time, so persisted ranking artifacts remain reproducible even after the snapshot file is later refreshed in place
  - bundled snapshot is honest: explicit `source_notes` field documents that it is a representative sample, not the full ~1000 names; full ingestion of IWB CSV is intentionally deferred to a future slice
- Contracts changed:
  - additive only: `IndexId` Literal extended with `russell1000`; `UniverseSpec.index_id` accepts the new value
  - new file format: `data/universe/index_snapshots/<index_id>.json` with fixed `snapshot_schema_version: index_snapshot_v1` envelope
- Tests/evidence:
  - `services/quant-engine/app/tests/test_universe_resolver_russell1000.py` (13 tests)
  - 201/201 backend generic_ranking + construction tests still pass; 15/15 frontend generic-ranking tests pass
- Next slice candidates:
  - scripted ingestion of the full Russell 1000 from IWB ETF holdings CSV (replaces the bundled sample with the full membership)
  - additional index families (Russell 2000 via IWM holdings, MSCI EAFE via EFA holdings) using the same snapshot loader pattern
  - Epic 3 breadth: more construction policies + richer constraints

### 2026-05-11 - Epic 2 generic_ranking Workspace Candidate Idea browser shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: surface persisted `generic_ranking` artifacts inside the Workspace Candidate Idea section so the construction-eligibility seam becomes user-visible end-to-end.
- Status: shipped.
- Scope delivered:
  - new `PersistedGenericRankingConstructionBrowser` desktop component, modeled after `PersistedEtfRankingConstructionBrowser`, that:
    - lists recent generic ranking artifacts via `GET /api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking`
    - parses cross-kind catalog rows fail-closed: rejects unsupported discovery scope, non-`generic_ranking` rows, missing `generic_summary`, and malformed metadata
    - calls `POST /api/construction/ranking-artifacts/preflight/{artifact_id}` per row to compute construction readiness
    - exposes a single `Review In Construction` CTA per row that runs the canonical construction handoff via `runRankingArtifactConstructionHandoff` and dispatches the resulting persisted construction artifact id to `onOpenConstructionReview`
  - browser is mounted alongside the ETF and replacement browsers inside `PortfolioImprovementWorkspaceShell`'s Candidate Idea section so the Workspace's authoritative `current_portfolio` is supplied to the construction handoff
  - the standalone `Generic Ranking` desktop tab now shows an informational hand-off note pointing users to Workspace → Persisted Generic Ranking Construction with the artifact id surfaced for cross-tab reference
- Guard impact:
  - closes the Generic Ranking dead-end identified in the prior Construction Eligibility slice: a persisted `generic_ranking` artifact can now be reopened end-to-end through Workspace → Candidate Idea → Construction Review without leaving the desktop UI.
  - browser stays explicitly construction-only: it does not seed candidate drafts, mutate `PortfolioSnapshot`, or imply applied portfolio truth.
  - parsing remains fail-closed on malformed catalog state; ineligible artifacts surface the backend `eligibility.reason` and disable the CTA rather than silently fabricating eligibility.
- Contracts changed:
  - no backend contract changes.
  - desktop now consumes the existing `/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking` and `/construction/ranking-artifacts/preflight/{artifact_id}` routes through a new browser entry point.
- Tests/evidence:
  - `apps/desktop/src/features/backtest/PersistedGenericRankingConstructionBrowser.test.tsx` (7 tests)
  - 188/188 backend construction + generic_ranking tests still pass; 7/7 new browser tests pass; 0 regressions in the unrelated frontend suites
- Next slice: Epic 2 status moves from "Workspace browser integration is the next slice" to "broaden supported ranking families and selection guardrails or pivot to Epic 3 breadth (more construction policies + richer constraints)" — see Epic 2 Open Gaps for the broader future direction.

### 2026-05-10 - Epic 1 save-time local admission evidence matching shipped

- Epic: `1. Imported-portfolio truth and reconciliation guard`
- Slice: harden desktop-local import-admission review metadata saves by matching captured evidence against the current non-pass check.
- Status: shipped.
- Scope delivered:
  - save-time validation canonicalizes current check evidence and saved `evidence_summary`, including optional null/default fields, before comparison.
  - mismatched captured evidence is rejected, while stale or mismatched snapshot/admission-summary fingerprints remain accepted for stale-labeling only.
  - review metadata remains desktop-local and does not mutate admission decisions, trust labels, broker truth, imported values, or derived portfolio truth.
- Contracts changed:
  - desktop-local contract docs now state current-evidence save matching and non-blocking stale fingerprints.
- Tests/evidence:
  - `apps/desktop/src/app/portfolioWorkspaceStorage.test.ts`

### 2026-05-10 - Epic 1 runtime-load local admission metadata sanitization shipped

- Epic: `1. Imported-portfolio truth and reconciliation guard`
- Slice: validate and sanitize malformed desktop-local import-admission review metadata at runtime load/build and save boundaries.
- Status: shipped.
- Scope delivered:
  - desktop imported-source build/read boundaries return sanitized clones for local `ImportAdmissionReviewDispositionV1` maps on workspaces and imported nodes.
  - valid stale fingerprints are preserved for stale review labels, malformed records and pass-status evidence are dropped, and unknown extras are stripped by reconstructing the known local metadata shape.
  - read-time sanitization does not rewrite IndexedDB; save-time validation requires a current non-pass admission check and non-pass captured evidence.
- Guard impact:
  - keeps review metadata local-only and prevents malformed local records from mutating admission state, trust labels, broker truth, imported values, or derived portfolio truth.
- Contracts changed:
  - desktop-local contract docs now state runtime sanitization and non-mutating read behavior.
- Tests/evidence:
  - `apps/desktop/src/app/portfolioWorkspaceStorage.test.ts`
  - `apps/desktop/src/features/portfolio/DashboardPanel.test.tsx`

### 2026-05-10 - Epic 2 → Epic 3 generic_ranking construction eligibility shipped

- Epic: `2. Ranking and selection methodology guard` → `3. Construction and optimizer methodology guard` (cross-epic slice)
- Slice: extend the construction-eligibility allowlist to accept `generic_ranking` artifacts.
- Status: shipped (backend + TS contract validators).
- Scope delivered:
  - new `GenericRankingArtifactConstructionHandoff` schema (handoff_kind `generic_ranking_artifact_construction_handoff_v1`)
  - new `GenericRankingConstructionPreflightArtifact` schema; `ConstructionRankingArtifactPreflightArtifactUnion` discriminator extended
  - `ConstructionRankingArtifactHandoffKind` Literal extended with `generic_ranking_artifact_construction_handoff_v1`
  - `prepare_generic_ranking_artifact_for_construction()` + `build_construction_preflight_response_from_generic_ranking_artifact()` in `construction_run_service.py`
  - `_build_ranked_candidates_from_generic_ranking_artifact()` mapping `EligibilityRecord` → `ConstructionRankedCandidateInput`; surfaces `hard_filter_failures` joined as `exclusion_reason` on excluded rows
  - `preflight_generic_ranking_artifact_for_construction()` in `construction_ranking_handoff_service.py`
  - `POST /construction/ranking-artifacts/preflight/{artifact_id}` route now dispatches `generic_ranking` artifact-id prefix; previously raised `unsupported ranking artifact kind` fail-closed
  - `POST /construction/run` now accepts `generic_ranking_artifact_construction_handoff_v1` handoffs and validates lineage (artifact_id, schema_version, ranking_id, methodology_id, as_of_date) plus eligibility
  - error class hierarchy extended: `GenericRankingMissingFileError` → 404; other generic ranking persistence errors → 400
  - desktop `rankingArtifactConstructionHandoff.ts` validator and `types.ts` extended with `generic_ranking_artifact_construction_handoff_v1` handoff kind support
  - autouse pytest fixture refactored to use `tmp_path_factory` (avoids polluting per-test `tmp_path` for tests that assert it stays empty)
- Guard impact:
  - closes Epic 2's actual next-slice gap: `generic_ranking` artifacts can now flow into the persisted construction review path through the same canonical preflight + run boundary used by ETF and replacement ranking artifacts.
  - explicit two-then-three-kind allowlist remains; no silent generalization to arbitrary artifact families.
  - excluded rows surface `hard_filter_failures` rather than being silently dropped, preserving generic_ranking's per-instrument `EligibilityRecord` truth through the construction boundary.
  - Workspace Candidate Idea browser integration for `generic_ranking` is NOT in this slice; it remains a follow-up (the standalone `Generic Ranking` desktop tab is still the only UI entry point for now).
- Tests/evidence:
  - `services/quant-engine/app/tests/test_construction_generic_ranking_handoff.py` (10 tests)
  - all existing construction tests still pass (178/178 in the construction + generic_ranking subsets)
- Next slice: surface `Review In Construction` CTA on the Generic Ranking desktop tab and add `generic_ranking` to Workspace Candidate Idea browser, so the eligibility expansion becomes user-visible end-to-end.

### 2026-05-10 - Epic 2 generic_ranking platform Phase 1 shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: introduce `generic_ranking` artifact kind as the first non-ETF ranking family on the generalized platform.
- Status: shipped (PR #2).
- Scope delivered:
  - new Pydantic schemas: `GenericRankingRequest`, `GenericRankingArtifact`, `UniverseSpec`, versioned `ScoreConfig` with content-addressed `score_config_digest`, `EligibilityRecord` (hard_filter_failures + soft_filter_flags), `CompositeScoreTrace` (per-factor cross-sectional mean/std).
  - 11 supported factor IDs (price-bar based): momentum (1m/3m/6m/12m/blended), realized_volatility (126d/252d), downside_volatility_126d, max_drawdown (126d/252d), liquidity_60d.
  - 3 universe kinds: `etf_peer_group`, `custom_list`, `broad_equity_screen`/`sector_screen` (FMP `/stock-screener`).
  - 3 new routes: `POST /strategy-lab/ranking/run`, `GET /strategy-lab/ranking/artifacts/recent`, `GET /strategy-lab/ranking/artifacts/{artifact_id}`.
  - `RankingArtifactKind` registry extended with `generic_ranking` and discovery filter set.
  - Content-addressed artifact persistence with write-once + fail-closed integrity validation; recent.jsonl index.
  - Desktop: new `Generic Ranking` tab with universe spec form, score config preset selector (Momentum+Volatility, Pure Momentum), ranked results table with confidence badges and per-factor component scores, recent runs panel.
  - Contract docs: `docs/contracts/generic-ranking-fields.md` covering all 7 contract surfaces.
- Guard impact:
  - extends ranking platform beyond the ETF-only and intent-bound replacement families per Epic 2 target state.
  - keeps ETF/replacement routes and artifacts unchanged (zero backward-compat breakage).
  - Generic ranking artifacts NOT yet construction-eligible; `Generic Ranking` tab is currently a standalone surface with no Workspace handoff.
- Tests/evidence:
  - `services/quant-engine/app/tests/test_generic_ranking.py` (23 tests)
  - `apps/desktop/src/features/generic-ranking/GenericRankingRequestForm.test.tsx`
- Next slice: Phase 2 (factor + universe coverage expansion).

### 2026-05-10 - Epic 2 generic_ranking factor + universe + catalog expansion shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: extend generic_ranking with quality + value factors, S&P 500 universe, and cross-kind catalog inclusion.
- Status: shipped (PR #3).
- Scope delivered:
  - 8 new fundamental factor IDs:
    - quality (4): `quality_profitability` (Novy-Marx gross profitability w/ EBIT fallback), `quality_cash_generation` (OCF/assets w/ FCF fallback), `quality_accrual` (Sloan), `quality_leverage` (net leverage).
    - value (4): `value_earnings_yield` (Greenblatt EBIT/EV), `value_book_to_market` (1/PB), `value_fcf_yield`, `value_ev_ebitda_inverse`.
  - new universe kind `index_constituent` with `IndexId='sp500'` resolved live via FMP `/stable/sp500-constituent`; optional sector include/exclude filters.
  - FMP client methods added: `get_ratios_ttm()`, `get_key_metrics_ttm()`, `get_sp500_constituents()`.
  - cross-kind catalog (`/strategy-lab/ranking-artifacts/catalog` and `/recent`) now surfaces generic_ranking artifacts alongside ETF and replacement; new `RankingArtifactCatalogGenericSummary` schema; 7 mechanical changes in `RankingArtifactCatalogService`.
  - graceful degradation: when fundamentals requested without FMP key, service emits warning rather than failing; confidence drops to `partial`.
  - desktop: 3 new score config presets (Quality, Value, Quality+Value Composite), index_constituent universe option with index dropdown.
  - autouse pytest fixture isolates generic_ranking artifact store per test (prevents leakage into ETF catalog tests).
- Guard impact:
  - broadens factor and universe coverage on the generic_ranking surface only; ETF and replacement contracts unchanged.
  - Russell 1000 universe deferred (no FMP endpoint; needs IWB ETF holdings CSV ingestion).
  - sentiment factors deferred (needs Alpha Vantage client).
  - generic_ranking still not in construction-eligibility allowlist (next slice).
- Tests/evidence:
  - `services/quant-engine/app/tests/test_generic_ranking_phase2.py` (19 tests)
  - `services/quant-engine/app/tests/conftest.py` (test isolation fixture)
- Next slice: construction eligibility expansion — add `generic_ranking` to construction preflight allowlist + Workspace Candidate Idea browser + `Review In Construction` CTA.

### 2026-05-08 - Epic 4 persisted monitoring discipline overview shipped

- Epic: `4. Monitoring and overlay review guard`
- Slice: add a read-only Monitoring Discipline Overview inside the existing Monitoring panel for persisted `benchmark_trend_overlay_v1` definitions.
- Status: shipped.
- Scope delivered:
  - desktop Monitoring loads `GET /api/backtests/monitor-definitions/catalog?overlay_family=benchmark_trend&monitor_id=benchmark_trend_overlay_v1` and validates discovery contract, metadata truth, row provenance, monitor id, and overlay family fail-closed before computing counts.
  - the overview renders persisted-definition coverage, enabled count, latest-observation presence/freshness, lifecycle/review readiness, latest-state counts, latest-snapshot presence, and a compact recent definitions table from persisted metadata only.
  - missing latest observation or snapshot metadata remains explicit `absent`; desktop does not infer stale/recent state or trigger evaluation.
- Guard impact:
  - broadens monitoring visibility as a persisted discipline review while preserving the narrow `benchmark_trend_overlay_v1` family boundary and avoiding mutation, scheduling, live-state, remediation, or execution semantics.
- Contracts changed:
  - no backend contract changes.
  - desktop consumes the existing monitor-definition catalog route for a new read-only aggregate view.
- Tests/evidence:
  - `apps/desktop/src/features/backtest/MonitoringPanel.test.tsx`

### 2026-05-09 - Epic 4 monitor family readiness explainability shipped

- Epic: `4. Monitoring and overlay review guard`
- Slice: enhance the read-only Monitor Family Readiness Overview inside the existing Monitoring panel with decision-grade explainability and non-promotion gates.
- Status: shipped.
- Scope delivered:
  - desktop Monitoring now derives family-readiness rows from the existing persisted discipline overview state, replay-derived monitor evidence, and the active replay.
  - `benchmark_trend_overlay_v1` was the only persisted/review-supported family for this explainability slice when the validated catalog was ready with rows; empty, invalid, and unavailable catalog states showed distinct frontend-only reason codes.
  - persisted benchmark rows render backend catalog metadata truth, row provenance, monitor definition count, and monitor definition ids.
  - factor drift, concentration drift, benchmark-relative drift, volatility, and pre-persistence data-quality readouts remained replay-derived signal rows only, with explicit blocked reason codes and gate breakdowns for monitor definition artifact, thresholds, lineage/provenance, lifecycle metadata, review support decision, and replay evidence.
  - signal rows said evidence unavailable rather than readiness when replay diagnostics/watch-group evidence was unavailable.
- Guard impact:
  - broadened visibility into possible monitor-family breadth without persisting new definitions, creating state, launching review handoffs, adding thresholds, triggering evaluation, scheduling, remediation, mutation, or implying unsupported family support.
- Contracts changed:
  - no backend contract changes.
  - no new persisted monitor definitions or monitor families.
- Tests/evidence:
  - `apps/desktop/src/features/backtest/MonitoringPanel.test.tsx`

### 2026-05-09 - Epic 4 persisted data-quality monitor family shipped

- Epic: `4. Monitoring and overlay review guard`
- Slice: stabilize and complete exactly one additional persisted monitor family, `data_quality_monitor_v1`, as evidence-only input reliability monitoring with family-aware readback.
- Status: shipped.
- Scope delivered:
  - backend schemas, routes, and persistence support `data_quality_monitor_v1` as `monitor_family = data_quality`, separate from benchmark overlays, with `DATA_QUALITY` reserved for that family and rejected for benchmark trend.
  - create/evaluate/catalog/recent/observation/history/timeline/inbox/episodes flows persist and validate data-quality definition, latest observation, latest evaluation snapshot, append-only history, alert episode records, and evidence lineage.
  - data-quality outcomes are review-only `ok`, `degraded`, or `unavailable`; `threshold_breach` and `action_required` are rejected for the family.
  - desktop Monitoring and Workspace readback render data quality as evidence-only input reliability and benchmark trend as benchmark threshold review after fail-closed family/evidence validation; replay-derived factor/concentration/benchmark-relative/volatility signals are not persisted monitor families.
- Guard impact:
  - adds one narrow persisted monitor family without adding scheduler, daemon, threshold editor, remediation, trading, allocation advice, auto-promotion, factor drift, concentration drift, benchmark-relative drift, or volatility persistence.
- Contracts changed:
  - `MonitorDefinitionMonitorId` now includes `data_quality_monitor_v1`.
  - catalog/recent filters now include `monitor_family`.
  - data-quality policy, source-lineage, evidence, cause-code, observation, latest-snapshot, and history shapes are additive while preserving legacy benchmark-trend serialization compatibility.
- Tests/evidence:
  - `services/quant-engine/app/tests/test_routes.py`
  - `services/quant-engine/app/tests/test_portfolio_allocation_backtests.py`
  - `apps/desktop/src/features/backtest/MonitoringPanel.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`

### 2026-05-09 - Epic 4 phase closeout

- Epic: `4. Monitoring and overlay review guard`
- Status: docs/status-only closeout.
- Marked Epic 4 phase closed / stabilized for the current phase; shipped breadth includes persisted benchmark-trend and data-quality review families, while remaining monitoring and overlay work is future breadth expansion rather than closeout work.
- No code, behavior, contract, current-state, roadmap, technical-roadmap, or test changes beyond this roadmap closeout.

### 2026-05-08 - Epic 3 phase closeout

- Epic: `3. Construction and optimizer methodology guard`
- Status: docs-only phase closeout.
- Marked Epic 3 phase closed / guardrail-complete for the current phase while preserving construction and optimizer breadth expansion as future work.
- No code, test, contract, current-state, or technical-roadmap changes beyond this roadmap closeout.

### 2026-05-07 - Epic 3 ranking bridge stabilization follow-up

- Status: shipped slice stabilization
- Aligned docs, backend discovery, and desktop wording to the broader shipped ranking-to-construction bridge: backend-authoritative policy selection from `/construction/policies`, typed preflight/handoff launch semantics, and persisted construction artifact review.
- Tightened the launch boundary so desktop-compatible policy discovery now carries explicit `launch_top_n = 2`, desktop consumers fail closed on mismatched catalog rows, and backend handoff-backed construction rejects `policy.top_n != 2` for the shipped launch path.
- Kept the bridge intentionally parameter-light and review-only: `top_n = 2`, desktop surfaces only required `max_position_weight` plus optional `min_position_weight`, other optional constraints stay hidden, and supported ranking families remain limited to ETF and intent-bound replacement artifacts.

### 2026-05-08 - Epic 3 slice 3 shipped

- Epic: `3. Construction and optimizer methodology guard`
- Slice: expose optional `max_turnover_weight` and optional `max_trade_intent_count` on the shipped artifact-backed ranking-to-construction desktop bridge.
- Status: shipped.
- Scope delivered:
  - Workspace persisted ETF ranking and persisted replacement ranking construction browsers now expose optional `Max Turnover Weight` and `Max Trade Intent Count` beside the existing max/min position-weight inputs.
  - desktop uses one shared validation path across both browsers so blank optional fields omit from the request, `max_turnover_weight` accepts decimal values in `[0, 1]` including `0`, and `max_trade_intent_count` accepts whole numbers `>= 0` including `0`.
  - ranking-artifact construction handoff now serializes those two optional hard constraints only when the user supplies non-null values, while preserving the same backend-authoritative policy selection and fixed `top_n = 2` launch boundary.
- Guard impact:
  - broadens the visible hard-constraint surface only within the agreed artifact-backed desktop bridge and keeps construction review hypothetical, persisted-artifact-backed, and limited to the same two supported ranking families.
  - does not widen backend capability, policy families, ranking families, or inline ranked-universe launch paths.
- Contracts changed:
  - no backend contract changes.
  - desktop handoff now optionally serializes `hard_constraints.max_turnover_weight` and `hard_constraints.max_trade_intent_count` only when explicitly supplied.
- Tests/evidence:
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: broaden policy parameterization beyond the current fixed `top_n` and the currently exposed hard-constraint set.

### 2026-05-08 - Epic 3 slice 4 shipped

- Epic: `3. Construction and optimizer methodology guard`
- Slice: make `top_n_linear_rank_weight_v1` an explicit launch-compatible opt-in on the shipped artifact-backed ranking-to-construction desktop bridge while keeping equal-weight the only auto-selected default.
- Status: shipped.
- Scope delivered:
  - desktop ranking-to-construction policy pickers now surface only `top_n_equal_weight_v1` and `top_n_linear_rank_weight_v1` for the existing artifact-backed launch browsers and ETF Ranking recent-run handoff entry point.
  - equal-weight remains the only auto-selected default when backend discovery returns it; if not, desktop stays fail-closed until the user explicitly chooses the linear-rank alternative.
  - the narrow launch boundary remains unchanged: review-only/hypothetical artifact-backed semantics, same two supported ranking families, backend-owned policy discovery, fixed `top_n = 2`, and post-run lineage checks for `policy_id`, `policy_definition_id`, and normalized `top_n`.
- Guard impact:
  - narrows desktop launch-scope exposure without widening backend construction capability, persistence, replay, or catalog rows.
  - does not expose `top_n_inverse_rank_weight_v1` on desktop launch surfaces in this slice.
- Contracts changed:
  - no backend contract changes.
  - desktop launch compatibility now filters discovered policies down to the shipped opt-in set before rendering or accepting selection.
- Tests/evidence:
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`

### 2026-05-08 - Epic 3 slice 5 shipped

- Epic: `3. Construction and optimizer methodology guard`
- Slice: make the narrow ranking-artifact construction launch path canonical through explicit launch-profile metadata plus matching desktop readback.
- Status: shipped.
- Scope delivered:
  - backend `/construction/policies` rows now stamp one canonical `ranking_artifact_review_handoff_v1` launch profile with explicit `default` / `opt_in` / `excluded` policy status and explicit fixed `launch_top_n = 2`.
  - the canonical launch profile includes only `top_n_equal_weight_v1` as the single default and `top_n_linear_rank_weight_v1` as explicit opt-in; `top_n_inverse_rank_weight_v1` remains in the broader catalog but is explicitly excluded from the desktop launch profile.
  - desktop policy parsing now consumes launch-profile metadata fail-closed instead of relying on hardcoded launch-compatible policy ids or hardcoded default-policy selection.
  - ETF Ranking and Workspace persisted ranking browsers now show compact readback text for selected launch policy, default vs opt-in status, fixed `top_n = 2`, required `max_position_weight`, and optional `min_position_weight`, `max_turnover_weight`, and `max_trade_intent_count`.
- Guard impact:
  - makes the currently shipped ranking-to-construction launch boundary explicit without widening policy breadth, ranking-family breadth, request shape, or hard-constraint semantics.
  - blocks launch if catalog metadata is contradictory, incomplete, or no longer matches the canonical equal-weight-plus-linear-rank launch boundary.
- Contracts changed:
  - additive backend discovery metadata only: `/construction/policies` rows now include `launch_profile`.
  - desktop launch compatibility/default behavior is now derived from that backend metadata rather than hardcoded allowlists/defaults.
- Tests/evidence:
  - `services/quant-engine/app/tests/test_routes.py`
  - `services/quant-engine/app/tests/test_construction_run_service.py`
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`

### 2026-05-07 - Epic 3 slice 2 shipped

- Epic: `3. Construction and optimizer methodology guard`
- Slice: add optional `min_position_weight` to the shipped ranking-to-construction bridge while keeping policy authority and scope narrow.
- Status: shipped.
- Scope delivered:
  - desktop `Review In Construction` entry points for ETF ranking and persisted replacement ranking now expose optional `Min Position Weight` beside the existing max field.
  - blank `min_position_weight` is treated as not requested and omitted from the construction request shape.
  - desktop uses one shared validation path for required `max_position_weight` and optional `min_position_weight`, including the local `min <= max` guard.
  - ETF Ranking workspace session state now persists the min field alongside the existing max field; the two persisted browsers keep min in local component state only.
- Guard impact:
  - broadens the visible bridge only one notch while preserving backend-authoritative policy selection, fixed `top_n = 2`, review-only construction semantics, and the two-family ranking allowlist.
  - keeps deeper feasibility with the backend and continues to leave turnover and trade-intent constraints out of scope.
- Contracts changed:
  - no backend contract changes.
  - desktop handoff now optionally serializes `hard_constraints.min_position_weight` only when the user explicitly supplies it.
- Tests/evidence:
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: broaden policy parameterization beyond the current fixed `top_n`, position-weight constraints, and hidden optional-constraint bridge.

### 2026-05-06 - Baseline epic alignment established

- Status: shipped roadmap update
- Added this living epic roadmap to track the four active epics and future slice sequencing.
- Set current priority order to `Epic 2 -> Epic 3 -> Epic 4`, with `Epic 1` treated as the foundational guardrail.
- Recorded the current shipped baseline from product-state, roadmap, and technical-roadmap docs.
- Next slice: move desktop ranking recent discovery onto generalized ranking-artifact recent flow.

### 2026-05-06 - Epic 2 slice 1 shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: move desktop recent discovery onto generalized ranking-artifact recent flow for ETF ranking.
- Status: shipped.
- Scope delivered:
  - `EtfRankingPanel` recent-run listing now fetches generalized `/strategy-lab/ranking-artifacts/recent` with `artifact_kind=etf_ranking`.
  - Desktop keeps ETF-native `/strategy-lab/etf-ranking/artifacts/recent/metadata` only for peer-group filter options in this transitional slice.
  - Recent-run open remains on the existing generalized preflight/open handoff path.
- Guard impact:
  - strengthens the generalized ranking artifact discovery seam in visible desktop workflow without changing ranking methodology or widening supported artifact kinds.
- Contracts changed:
  - no backend contract changes.
  - desktop discovery consumer moved to the generalized recent contract for ETF rows.
- Tests/evidence:
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: add read-only browsing/opening of persisted replacement ranking artifacts through the same generalized flow.

### 2026-05-06 - Epic 2 slice 2 shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: add read-only browsing/opening of persisted replacement ranking artifacts through generalized ranking discovery/open.
- Status: shipped.
- Scope delivered:
  - Workspace `Candidate Idea` now includes a persisted replacement review browser backed by generalized `/strategy-lab/ranking-artifacts/recent` with `artifact_kind=intent_bound_etf_replacement_ranking`.
  - Desktop opens persisted replacement artifacts only through generalized preflight plus typed open handoff reuse.
  - Persisted replacement review renders read-only authoritative artifact context in Workspace without creating intent, mutating workflow state, widening storage, or launching replay.
  - Desktop validates discovery rows, preflight, open payload, and consumer handoff fail-closed before rendering persisted review state.
- Guard impact:
  - strengthens the generalized ranking artifact seam in visible Workspace review while keeping persisted replacement reopen explicitly context-only and non-promotable.
  - keeps `consumer_handoff` validation-only in this slice; no downstream actionability was added.
- Contracts changed:
  - no backend contract changes.
  - desktop now consumes generalized replacement recent/preflight/open contracts in Workspace Candidate Idea.
- Tests/evidence:
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
- Next slice: generalized ranking-to-construction handoff review path.

### 2026-05-06 - Epic 2 slice 3 shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: ETF ranking artifact to persisted construction review handoff through the canonical construction preflight/run path.
- Status: shipped.
- Scope delivered:
  - persisted ETF ranking artifacts now expose `Review In Construction` from `ETF Ranking`.
  - Workspace `Candidate Idea` now also exposes an ETF-only persisted ranking construction browser/action surface alongside the existing read-only replacement review surface.
  - both entry points route through canonical `/construction/ranking-artifacts/preflight/{artifact_id}` plus `/construction/run` and then reopen the returned persisted construction artifact through the existing artifact review flow.
  - desktop validates construction preflight contract identity and construction-run ranking lineage fail-closed before opening persisted construction review.
- Guard impact:
  - makes ranking-to-construction methodology visible through canonical persisted handoff review rather than ETF-local-only ranking inspection.
  - keeps this slice explicitly ETF-ranking-only for construction handoff; persisted replacement reviews remain read-only/context-only and do not imply construction eligibility.
- Contracts changed:
  - no backend contract changes.
  - desktop now consumes the shipped ETF construction ranking-artifact preflight/handoff boundary from both ETF Ranking and Workspace Candidate Idea.
- Tests/evidence:
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: broaden construction handoff beyond ETF ranking artifacts.

### 2026-05-06 - Epic 2 slice 4 shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: broaden persisted construction handoff from ETF ranking artifacts to intent-bound ETF replacement ranking artifacts.
- Status: shipped.
- Scope delivered:
  - backend construction preflight and construction run now support exactly two ranking-artifact handoff kinds: `etf_ranking` and `intent_bound_etf_replacement_ranking`.
  - persisted replacement ranking artifacts now expose `Review In Construction` from Workspace Candidate Idea while keeping their ranking review explicitly read-only until that action is invoked.
  - replacement construction handoff reuses the same persisted construction artifact review path already used by ETF ranking handoff.
  - desktop and backend both validate replacement construction preflight identity, selected-candidate lineage, and persisted construction ranking lineage fail-closed.
- Guard impact:
  - broadens ranking-to-construction review one artifact family further without pretending all ranking artifacts are construction-eligible.
  - keeps the construction seam on an explicit two-kind allowlist rather than silently generalizing to arbitrary ranking artifacts.
  - preserves replacement review as context-only unless the user explicitly launches the separate construction review handoff.
- Contracts changed:
  - backend construction preflight/handoff contracts now support the additive `intent_bound_etf_replacement_ranking` construction handoff kind alongside the shipped ETF handoff kind.
  - desktop now consumes the widened two-kind construction handoff seam through the shared ranking-artifact construction helper.
- Tests/evidence:
  - `services/quant-engine/app/tests/test_construction_run_service.py`
  - `services/quant-engine/app/tests/test_routes.py`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: broaden construction handoff beyond ETF and intent-bound replacement artifacts.

### 2026-05-06 - Epic 2 slice 5 shipped

- Epic: `2. Ranking and selection methodology guard`
- Slice: add explicit construction eligibility/readiness review for the two supported ranking families before construction launch.
- Status: shipped.
- Scope delivered:
  - backend construction preflight for `etf_ranking` and `intent_bound_etf_replacement_ranking` now returns additive typed `eligibility` plus optional `handoff` instead of treating all non-launchable cases as the same class.
  - desktop ETF and replacement construction browsers now surface construction-readiness state, disable `Review In Construction` when preflight says ineligible, and show canonical backend reason text.
  - unsupported families such as `cross_sectional_research_run` remain explicitly non-constructible; desktop shows only a static unsupported note and backend rejects construction preflight for that family fail-closed.
  - construction run still revalidates persisted artifact truth and lineage; preflight eligibility is a typed gate, not execution approval.
- Guard impact:
  - strengthens the selection-to-construction boundary by making construction-readiness explicit for the two supported ranking families rather than implicit in CTA behavior.

### 2026-05-07 - Epic 3 slice 1 shipped

- Epic: `3. Construction and optimizer methodology guard`
- Slice: stabilize the ranking-to-construction bridge around backend-authoritative policy selection plus one editable `max_position_weight` input.
- Status: shipped.
- Scope delivered:
  - desktop `Review In Construction` entry points for ETF ranking and persisted replacement ranking now load compatible construction policies from backend discovery instead of silently hardcoding `top_n_equal_weight_v1`.
  - desktop validates policy catalog rows fail-closed, auto-selects `top_n_equal_weight_v1` only when it is actually returned, and otherwise requires explicit user selection before construction launch.
  - desktop ranking-to-construction entry points now expose one shared editable `max_position_weight` input while still omitting other optional constraint knobs.
  - ranking-artifact construction handoff now requires caller-supplied selected policy and validates persisted construction run lineage for both ranking artifact provenance and requested policy provenance.
- Guard impact:
  - strengthens backend methodology authority in the visible ranking-to-construction workflow without widening supported ranking families, optimizer scope, or construction configuration breadth.
  - keeps the bridge explicitly review-only and parameter-light: fixed `top_n`, one editable `max_position_weight`, hidden optional constraints, and narrow portfolio lineage assumptions remain unchanged in this slice.
- Contracts changed:
  - no backend contract changes.
  - desktop now consumes `GET /construction/policies` as the authoritative source for construction policy identity on the ranking-to-construction bridge.
- Tests/evidence:
  - `apps/desktop/src/features/strategy-lab/EtfRankingPanel.test.tsx`
  - `apps/desktop/src/features/backtest/PortfolioImprovementWorkspaceShell.test.tsx`
  - `apps/desktop/src/app/App.test.tsx`
- Next slice: broaden policy parameterization beyond the current fixed `top_n`, single editable `max_position_weight`, and hidden optional-constraint bridge.

## Operational Update Rule

After every shipped slice or epic checkpoint:

1. update this file with status, delivered scope, and next slice
2. update `docs/product/current-product-state.md` if shipped behavior changed
3. update contracts or finance docs if methodology, trust semantics, or artifact boundaries changed
