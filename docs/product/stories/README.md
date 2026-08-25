# User Stories

One file per user story. A story is a vertical slice of user value, not a
technical feature. Delivery model: see [`../prd/README.md`](../prd/README.md).

## Naming

`US-<epic>.<n>-<slug>.md` — e.g. `US-3.1-inverse-volatility-weighting-policy.md`.

## Lifecycle

| Status | Meaning |
|---|---|
| **Backlog** | Story defined (statement + acceptance criteria + rough test plan). Not yet ticketed. |
| **Next phase** | Pulled into the active phase and broken into ordered tickets. |
| **In progress** | An agent is delivering it via the `build-story` skill. |
| **Done** | Every acceptance criterion met, full test plan passing, docs updated. |

## Index

### Epic 40 — Snapshot Trust & Fidelity Follow-Through (complete)

PRD: none — see `US-40.1`/`US-40.2` for the full delivery record (close-out scope excluded `docs/product/prd/`)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-40.1](US-40.1-snapshot-trust-signal-completeness.md) | The researcher can tell when a snapshot's trust signals reflect frozen import data, not a live recomputation | Doc-only contract note + permanent regression test retiring `run_metadata.source_status.*`/`.confidence` as a trust source (`docs/contracts/exposure-fields.md`, `runMetadataTrustSourceGuard.test.ts`); snapshot-picker labels now disclose a node's import/capture date (`variantLabels.ts`); housekeeping fold-in: `RecordingMarketData` gains 2 delegate methods, dead `market_data` param and the `_build_exposure_source_status`/`_build_exposure_availability` duplication routed to `tech-debt-register.md` | Done |
| [US-40.2](US-40.2-add-snapshot-preserves-imported-history.md) | Adding a new snapshot to a portfolio no longer discards its imported history | Backend — new `CombineImportedSnapshotsRequest` schema + `POST /portfolios/import/combine-snapshots` route, reusing `combine_imported_snapshots` verbatim (no new merge logic). Frontend — `App.tsx`'s `add_snapshot` branch calls the new route and preserves combined history instead of passing `null`; degrades via the existing `importError` channel on an incompatible combine | Done |

Two-story epic. Stories are structurally independent (no shared function). US-40.1 sequenced first as a soft dependency only, not a build-order constraint.

---

### Epic 39 — Direct-Held ETF Sector Classification (complete)

PRD: [`prd/epic-39-direct-held-etf-sector-classification.md`](../prd/epic-39-direct-held-etf-sector-classification.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-39.1](US-39.1-direct-held-etf-sector-classification.md) | Direct-held ETF sector classification stops relying on keyword-substring matching | Backend — deletes the keyword-substring `sector` matcher (and its silent `"Broad Market"` default) from `instruments/registry.py`'s direct-held ETF branch; replaces with identity-gated dynamic classification (new `etf_sector_resolution.py`: ISIN gate → 55% dominance threshold on `/stable/etf/sector-weightings` → shared taxonomy map, else "Unclassified"); new SBIO `SymbolResolutionRule` prevents a proven live ticker-collision; `category` derivation unaffected | Done |

Single-story epic. No build-order constraints.

---

### Epic 38 — Sector-Classification Follow-Through: ETF Look-Through & Diagnostic Integrity (complete)

PRD: [`prd/epic-38-sector-classification-follow-through.md`](../prd/epic-38-sector-classification-follow-through.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-38.1](US-38.1-etf-lookthrough-sector-classification.md) | ETF look-through sector exposure stops guessing and stops silently landing on "Other" | Backend — deletes the two hardcoded ETF-ticker-keyword → sector proxy functions and the ungated live `get_company_profile` fallback in `analytics/risk.py`; replaces with a static-registry-or-"Unclassified" rule (per-source-slice attribution preserved, "Unclassified" exempt from the `MIN_SECTOR_WEIGHT` suppression filter); curates eight companion ETF tickers (`XLF`/`XLV`/`IBB`/`ITA`/`PPA`/`BIL`/`VGSH`/`DBC`) into `INSTRUMENT_DEFINITIONS` | Done |
| [US-38.2](US-38.2-market-data-cache-diagnostic-accuracy.md) | Market-data cache diagnostics report the truth, and the cache-key formula has one home | Backend — extends US-37.2's real-hit/miss cache-flag fix from `get_company_profile` to the remaining five `MarketDataService` methods / six call sites; consolidates the cache-key formula into `FmpClient.build_cache_identifier`/`is_cached`, one formula for `fmp.py` itself and `market_data.py`'s pre-check helper | Done |

Two-story epic. Stories are structurally independent (disjoint files, disjoint concerns). No build-order constraints.

---

### Epic 37 — Dynamic Equity Sector Classification (complete)

PRD: [`prd/epic-37-dynamic-equity-sector-classification.md`](../prd/epic-37-dynamic-equity-sector-classification.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-37.1](US-37.1-dynamic-equity-sector-classification.md) | Dynamic, identity-gated sector classification for equities outside the static registry | Backend — identity-gated FMP resolution (static registry → FMP + ISIN-match → no classification) for equities outside `INSTRUMENT_DEFINITIONS`, an 11-entry sector-taxonomy normalization table, fail-safe FMP-failure handling, and an honest, disclosed `"Unclassified"` bucket (never `"Other"`) for equities nothing resolves. ETF look-through constituent classification (F-B) explicitly out of scope | Done |
| [US-37.2](US-37.2-sector-classification-followups.md) | Sector-classification follow-ups — taxonomy normalization, cache-flag accuracy, test-fixture consolidation | Backend — case/whitespace-insensitive taxonomy lookup in `resolve_equity_sector` (narrows only what counts as unmapped, never widens what counts as mapped); `MarketDataService.get_company_profile`'s `cached` diagnostic now reflects true per-symbol cache hit/miss instead of hardcoded `True`. Test — shared `FakeMarketData` fixture in `app/tests/fixtures.py` replacing three hand-duplicated local fakes. ETF look-through, both epic-24 tech-debt rows, and the same `cached: True` shape in other `MarketDataService` methods explicitly out of scope | Done |

Two-story epic (US-37.2 is a follow-up story to US-37.1, filed under the same epic). No build-order constraints.

---

### Epic 36 — Findings-First Doc & Gate Hygiene (complete)

PRD: [`prd/epic-36-findings-first-doc-and-gate-hygiene.md`](../prd/epic-36-findings-first-doc-and-gate-hygiene.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-36.1](US-36.1-blocked-commit-stays-blocked.md) | A blocked commit stays blocked, regardless of which tool issued it | F-R1: the `.claude/.last-test-pass` freshness gate was wired only to the Bash-matched `PreToolUse` hook — a PowerShell-issued `git commit` bypassed it silently, while `CLAUDE.md`/`project.md` falsely claimed a git-level hook already closed the gap. Real git-level `pre-commit` hook via `core.hooksPath`, self-wired by `run_all_tests.py`, tool-independent by construction | Done |
| [US-36.2](US-36.2-dependency-vulnerability-scan.md) | CI flags a newly-vulnerable pinned dependency instead of staying silent forever | F-R3: nothing scanned the pinned backend / locked frontend dependency sets for known vulnerabilities. New `pip-audit`/`npm audit` scan tooling plus a separate, scheduled, network-permitted GitHub Actions workflow — deliberately not folded into the network-free `run_all_tests.py`/CI gate | Done |
| [US-36.3](US-36.3-docs-match-the-repo.md) | The docs an agent is told to trust for "what's shipped" actually match the repo | F-R5/F-R6/F-R7/F-R8 bundled: stale cache-CLI doc, undercounted route inventory (+ new mechanical check), stale Epic 24 PRD status header, undocumented accepted security tradeoff. Also retires `docs/product/review-2026-08-20-findings.md` as superseded | Done |

### Epic 35 — Market-Data Failure Honesty (active)

PRD: [`prd/epic-35-market-data-cache-resilience.md`](../prd/epic-35-market-data-cache-resilience.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-35.1](US-35.1-auth-failure-is-not-missing-data.md) | Stop returning an auth failure as if it were missing data | F-1: a 401 is negative-cached as `[]` and immediately re-read as "stale", so the error is swallowed — a wrong key produces an empty Dashboard, not an error, and persists for 24h. Verified empirically. The fix must cross two layers: `MarketDataService` catches `Exception` at eight call sites, and those catches are load-bearing for symbol resolution, so a per-symbol failure must keep degrading while a config failure propagates | Done |
| [US-35.2](US-35.2-clearable-cache-namespaces.md) | Make every cache namespace clearable and inspectable | F-2: `list` printed `history_yf`, `holdings` and more; `clear --namespace` accepted a hand-written four-item list, so most were unnameable. Choices are now derived from disk, a partial clear says what it left behind, and a typo is rejected instead of reporting `Removed 0`. **The claimed prefix collision did not exist** — matching was already exact, so that AC became a guard against introducing one | Done |
| [US-35.3](US-35.3-capture-refuses-to-degrade.md) | Refuse to overwrite the golden capture with a degraded one | F-3: the capture wrote whatever it recorded and printed the count — it overwrote 73 series with 21 and reported success. Now compares against the committed fixture and refuses, naming what changed. Catches the sharpest case: a benchmark **present with zero rows**, which any "is SPY there?" check would pass | Done |

### Epic 34 — An Answerable Dashboard: Reachable Trust States (active)

PRD: [`prd/epic-34-answerable-dashboard-and-reachable-trust.md`](../prd/epic-34-answerable-dashboard-and-reachable-trust.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| US-34.1 | Findings-first audit of the withheld Dashboard surface | Audit-only, recorded in the PRD: F-1 `portfolio_path="unavailable"` is a hardcoded literal; F-1a five of eight hard proof disqualifiers are structural properties of replaying a statement and can never clear, so TWR / benchmark / excess / max-drawdown are `null` in all five ranges on every run while the statement's own TWR (4.77%) sits imported; F-2 the cash anchor can never be `verified` (period start vs replay window start); F-3 a withheld holding's magnitude (~3.2% of the book) is never disclosed; F-4 two of six withheld days carry $5.13/$25.09 flows; F-5 the terminal day never has a return; F-6 the benchmark return is null although 148 SPY closes are returned. Includes the examined-and-correct list — Exposure and Risk are healthy | Done |
| [US-34.2](US-34.2-publish-replay-derived-twr.md) | Publish the replay's TWR under an explicit `replay_derived` trust state | F-1/F-1a: a real classification instead of the hardcoded literal, and a rung below `verified_total_return` so a reconstructed-replay return is published labelled rather than withheld. Discloses what the withheld days cost it (1.80pp). Surfaced three hidden defects: every window reported the same return, windowed ranges were anchored at the series start, and MWR carries the reconciliation adjustment (→ F-7). The strict admission gate is untouched | Done |
| [US-34.3](US-34.3-anchor-opening-cash-on-statement.md) | Anchor opening cash on the statement's own starting cash | F-2 + most of F-5: the derived `starting_nav − opening_positions_value` anchor mixes two differently-dated terms, so it is `degraded` on every run of every statement. The broker reports its opening cash directly ($4,672.04 vs the derived $3,252.74) — residual −$1,377.59 → +$46.69, terminal adjustment +$1,366.17 → −$53.13. Trust follows the source, so the standing warning finally clears | Done |
| [US-34.4](US-34.4-disclose-withheld-holding-value.md) | Say what a withheld holding was worth, and stop withholding immaterial days | F-3 + F-4: bound the withheld position from the broker's own cash movements (LQQ: at least $2,130.62, ~3.4% of the book, across 26 held days) — no price or quantity needed, since the quantity is the untrusted thing; and switch the unbacked-cash guard from a flat $1.00 to a share of portfolio value, recovering two days that distort nothing (0.0085% and 0.0400% against a 2.77% smallest material day) | Done |
| [US-34.5](US-34.5-publish-benchmark-return-on-stated-basis.md) | Publish the benchmark and excess return on a stated basis | F-6: 148 SPY closes are drawn on the chart with `benchmark_return_pct` null on every one. Publishes +11.75% and a −11.21pp excess, labelled `price_return_only`, with the dividend bias quantified (~0.7pp, always flattering the portfolio). Surfaced **F-9** and **F-10**. Parked on **F-10** and shipped 2026-08-17 once the owner retired the anti-derivation rule for the benchmark leg — the withheld figures were already derivable from the response's own published prices, so the rule removed the label, not the information | Done |
| [US-34.6](US-34.6-mwr-excludes-reconciliation-adjustment.md) | Stop the money-weighted return and investment gain from publishing the reconciliation adjustment | F-7, found by US-34.2: both read the reconciled terminal value, so both republished the accounting entry US-31.3 withholds from the TWR. IB2026 MWR 5.30% → 2.95%, gain $3,080.88 → $1,714.71; levels keep the broker's ending NAV. Surfaced F-8 | Done |
| [US-34.9](US-34.9-source-adjusted-closes-for-verified-benchmark.md) | Source adjusted closes so the verified benchmark rung can fire | F-9: the verified rung needed `adjClose` from an endpoint that returns none, so it was unreachable by construction and its tests passed only on hand-written rows. Joins FMP's `full` and `dividend-adjusted` responses for the benchmark only. SPY now publishes **+12.35%** on `verified_total_return` (was +11.75% price-basis) and the excess moves to **−11.92pp**. Surfaced **F-13** (the FMP skill asserted the inverse of the data), **F-14** (FMP's newest-first row order was a second, silent disqualifier that briefly published *nothing*), and **F-15** (the fallback provider valued holdings at adjusted prices). The re-capture also brought real terminal-day quotes: VUAA and SEMI now match the broker exactly | Done |
| [US-34.7](US-34.7-correct-the-drawdown-price-basis-claim.md) | Correct the drawdown price-basis claim, and disclose where it is real | **F-11**: the justification US-34.2 left on the gate is false for the Dashboard — that path chains `portfolio_value` over the replay, where dividends arrive as ledger cash ($125.72 gross / $107.79 net, verified in the states), so it is already total-return-like. The gate is actually closed because `drawdown_family` is withheld (blocked on F-10). **F-12**: the exposure is real on the Risk tab's synthetic path (flat cash, no ledger) but bounded at ~0.006% here — only PYPL is both held and paying. Publishes nothing new; goldens byte-identical | Done |
| [US-34.8](US-34.8-publish-terminal-day-return.md) | Publish the terminal day's return, corrected rather than withheld | F-8, found by US-34.6: US-31.3 withheld the reconciled day because its value was overwritten and no un-overwritten one existed; `market_derived_terminal_value` now supplies it. **Not a relaxation** — computing the return with the adjustment removed satisfies F-3's requirement more exactly than blanking the day did. Closes the last TWR/MWR disagreement on FF2026 (0.12% vs 0.51% → both 0.51%). Found that `risk.py` holds a second copy of the daily-return formula | Done |

Recommended order: US-34.2, US-34.6, US-34.3, US-34.4, US-34.8, US-34.7 and US-34.5 (done); US-34.9 is complete, including the FMP re-capture.

---

### Epic 33 — Corporate Actions & Replay Quantity Integrity (complete)

PRD: [`prd/epic-33-corporate-actions-replay-integrity.md`](../prd/epic-33-corporate-actions-replay-integrity.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| US-33.1 | Findings-first audit of corporate-action handling in the replay | Audit-only, recorded in the PRD: F-1 the roll-back sums quantities across a share split (LQQ ~200:1, 218× price range in its own ledger → phantom 199-unit opening); F-2 US-24.10's trade-price anchor values those phantom units at the stale pre-split €1,457.78 = $336,543, inflating MV ~8× for three months and volatility to 737.84%; F-3 the valuation-tier exclusivity claim is false per-symbol. Includes the examined-and-correct list — the new tickers were tested and eliminated | Done |
| [US-33.2](US-33.2-fail-closed-split-inconsistent-quantities.md) | Fail closed on split-inconsistent reconstructed quantities | Detect the share-unit discontinuity, withhold and disclose rather than value a phantom position; add the trade-price anchor's discontinuity guard, and withhold the return on days its cash moves with no position behind it | Done |
| [US-33.3](US-33.3-correct-valuation-tier-exclusivity-claim.md) | Correct the valuation-tier exclusivity claim | F-3: the tiers are exclusive per (symbol, **day**), not per symbol — the disclosure lists are unions over the window, so a holding that predates its own first trade is legitimately in two. Corrects US-24.10's AC5 + 5 doc/comment sites and adds the counter-example test the original claim never had | Done |
| [US-33.4](US-33.4-adopt-2026-08-11-statement.md) | Adopt the 2026-08-11 statement as the golden fixture | Re-measures the replay pins against the fixed engine, re-homes 5 structural tests that were wrongly pinning statement truths, derives the importer/refresh anchors instead of pasting CSV rows, corrects a settled-cash over-assertion, and regenerates the goldens. Found and fixed the unbacked-cash fabrication via US-24.9's tripwire | Done |

---

### Epic 32 — Project Hygiene & Agent-Facing Doc Accuracy (active)

PRD: [`prd/epic-32-project-hygiene-and-agent-docs.md`](../prd/epic-32-project-hygiene-and-agent-docs.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-32.1](US-32.1-fix-agent-facing-paths.md) | Fix the agent-facing instructions that point at files that do not exist | F-3/F-4: CLAUDE.md told every implementer to register routes in `app/main.py` (never existed; it is `app/api/main.py`) and the `write-story` module table named three phantom analytics modules while omitting eight real ones. Both fixed, plus `test_docs_paths.py` so the drift cannot return — it verifies claims in **both** directions and has no opt-out. The scan immediately found two more instances, including a goldens heuristic inside `verify-story` itself that pointed at a module which has never existed | Done |
| [US-32.2](US-32.2-risk-tab-design-system-audit.md) | Bring the Risk-tab cards under the design-system audit | F-5: all three Risk-tab cards were absent from `ALL_CARD_FILES`, so the no-hex / no-px / single-source-`Synthetic` gate covered two tabs of a three-tab product. Adding them surfaced two real violations (badge tooltips restating the label `TrustBadge` already renders), fixed rather than waived. Coverage proven by injecting a hex+px literal and watching the suite fail | Done |
| [US-32.3](US-32.3-refresh-status-surfaces.md) | Refresh the status surfaces so "where are we?" is answerable | F-6/F-7/F-8: the roadmap still read *Epic 31 active* four epics later, and CLAUDE.md pointed at Epic 13's PRD as "most recent". **The story had itself gone stale** — its AC1 example named Epic 26 — so the intent was implemented against today's truth and the drift recorded. Closes Epic 34 and Epic 32; makes the epic pointer defer to the roadmap so it degrades gracefully; stops `build-story` instructing an unconditional push | Done |

---

### Epic 31 — Ledger Replay Correctness (complete)

PRD: [`prd/epic-31-ledger-replay-correctness.md`](../prd/epic-31-ledger-replay-correctness.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-31.1](US-31.1-ledger-replay-audit.md) | Findings-first audit of the imported ledger replay | Audit-only (no code): records F-1..F-3 as one causal chain with file:line evidence, reproduced against the frozen golden market data — price history fetched for current holdings only while the replay reconstructs opening positions (11/38 priced on day 1), the `starting_nav − opening_value` cash anchor absorbing the $35,534 error as a plug, and the terminal reconciliation publishing that correction as a −36.34% single-day return (+79% volatility). Includes the surfaced-vs-gated impact map. Blocks tech-debt US-24.9 | Done |
| [US-31.2](US-31.2-ledger-replay-opening-symbol-coverage.md) | Price the full reconstructed symbol set on the ledger-replay path | Backend — fixes F-1: one shared pure function derives the replay symbol universe (current holdings ∪ every BUY/SELL symbol, 63 vs 20 for IB2026) and both ledger-replay callers fetch it; closes the `_effective_valuation_dates` default-weight-1.0 trap that the wider fetch set would otherwise arm; discloses residual unpriced opening positions on the run metadata. Deliberate `golden_market_data.json` re-capture + itemized goldens diff. Opening MV $14,582 → $49,024; cash plug −96.9%; F-3 re-scoped (−36.34% → −2.56%). F-2/F-3 stay untouched (US-31.3) | Done |
| [US-31.4](US-31.4-remove-semi-bare-symbol-fallback.md) | Stop the bare-symbol fallback substituting a different security for SEMI | Backend — fixes F-5: removes the bare `SEMI` candidate so resolution no longer falls through from the unavailable held line (`SEMI.L`, iShares MSCI Global Semiconductors UCITS, GBP) to a different US-listed fund (40.58 vs the held 17.998 GBP, +$2,506.93 on IB2026). Mirrors the CIBR/DFND wrong-fund guards in `app/core/symbols.py`; yfinance then returns the correct `SEMI.L` line. Deliberate golden re-capture. Residual GBP-unconverted value is F-4/US-31.5. | Done |
| [US-31.5](US-31.5-per-symbol-quote-currency-conversion.md) | Convert each replayed holding by its fund currency, not the broker listing | Backend — fixes F-4: the replay converts each holding's market value by its **fund currency** (InstrumentRegistry, = the resolved line's quote currency; 0 mismatches on IB2026) using the statement's implied rates, not `position.currency` (a blanket listing-currency conversion is 4.3× worse — DEFS.L quotes USD for an EUR listing). Statement-anchored holdings keep the position currency. Terminal MV reconciles to the statement `stock_total` ($61,239.88 vs $61,238.53, $1.35 residual). No re-capture (conversion-only); `golden_market_data.json` untouched. Leaves F-2 cash plug for US-31.3. | Done |
| [US-31.3](US-31.3-cash-anchor-and-terminal-reconciliation.md) | Stop cash absorbing valuation error, and never publish a reconciliation adjustment as a return | Backend — fixes F-2/F-3, the last Epic 31 findings. Root-caused F-2 to a **date mismatch**: `base_cash = starting_nav − opening_positions_value` subtracts a window-start (2026-01-08) market value from a period-start (2026-01-01) NAV, plugging ~$1,192 into cash — constant across the window, so in-window flows are correct. Owner decision: **fail-closed + disclose** — a `replay_cash_anchor` disclosure (basis/dates/residual/trust) plus a recorded `reconciliation_adjustment`, and **no return is published for the adjusted terminal day** (the fabricated +2.95% disappears). Vol 23.63% → 23.32%. Closes Epic 31; unblocks US-24.9. | Done |

---

### Epic 29 — Chart First-Render Reliability (complete)

PRD: [`prd/epic-29-chart-first-render-reliability.md`](../prd/epic-29-chart-first-render-reliability.md)
(renumbered from a parallel session's "Epic 27" at merge, 2026-07-07)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-29.1](US-29.1-defer-chartshell-mount-one-frame.md) | Defer ChartShell's chart mount by one tick | `setTimeout(fn, 0)` mount deferral in the shared `ChartShell` primitive — fixes Recharts' `ResponsiveContainer` degenerate first measurement when import flips several cards at once (rAF variant proven insufficient under Tauri's hidden-webview state) | Done |

---

### Epic 28 — IBKR CSV Importer & Statement-Refresh Resilience (backlog)

PRD: [`prd/epic-28-ibkr-csv-importer.md`](../prd/epic-28-ibkr-csv-importer.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-30.2](US-30.2-drift-coverage-fx-disclosure.md) | Drift coverage + FX disclosure — statement-anchored symbols, implied rates | Disclose flat statement-anchored (zero-coverage) holdings on DriftResult (PRD F-3, wording corrected: anchored, not omitted); carry US-28.1 statement-implied FX through workspace snapshot → request → engine with a three-tier FX disclosure (static-rate / fallback / anchored) (F-6) | Done |
| [US-30.3](US-30.3-exposure-first-render.md) | Exposure first-render reliability — self-fetching drift panel + Since-Import anchor | Convert the drift panel to the self-fetching pattern so the chart renders on Exposure-tab open with no dropdown interaction (F-4); anchor the "Since Import" window to the statement-period start instead of the import timestamp (F-5) | Done |
| [US-30.4](US-30.4-exposure-calculation-audit.md) | Findings-first audit of the remaining Exposure calculations | Audit-only (no code): verified every Exposure calculation surface against the methodology and recorded PRD findings F-7..F-10 with file:line evidence and reproduced numbers — currency-mixed weight denominators (Critical), missing FX disclosure, ungated per-position beta, two incompatible portfolio-return bases | Done |
| [US-30.5a](US-30.5a-exposure-fx-weights.md) | FX-convert every Exposure weight + disclose the currency basis | Fix PRD F-7 (Critical: every Exposure weight denominator raw-sums EUR/GBP/USD) by converting with the statement's implied rates, and F-8 (no card disclosed the degradation). Regenerates dashboardGoldens.ts deliberately | Done |
| [US-30.6](US-30.6-concentration-pack-cardshell.md) | Migrate the Concentration Pack onto CardShell + bring it under the design-system audit | Epic 30 close. Findings-first audit showed the tab already meets the ui-polish baseline; re-scoped to the deferred gap — the Concentration Pack (largest Exposure surface) was raw `<section>`s with no landmark and outside the audited surface. Wrapped in CardShell (region landmark), named its subsections, added ExposurePanel.tsx to ALL_CARD_FILES. No Synthetic badge (snapshot analytics); zero layout change; goldens untouched | Done |
| [US-30.5c](US-30.5c-return-basis.md) | Provenance-selected return basis — cash-excluded market-value chain for synthetic series | Fix PRD F-10: synthetic surfaces (rolling correlation/beta, factor attribution, factor model, stress, multi-benchmark) move onto the cash-excluded market-value chain; the imported ledger-replay path keeps the trade-safe TWR (avoiding the F-1 fabrication a blanket swap would reintroduce). Goldens byte-identical; ledger-path de-dilution deferred to tech-debt US-24.9 | Done |
| [US-30.5b](US-30.5b-position-beta-min-observations.md) | Gate per-position risk statistics on the minimum observation floor | Fix PRD F-9: withhold per-position beta/correlation/volatility until a holding has ≥ MIN_DAILY_OBSERVATIONS (20) return observations (methodology §Beta). Behaviour-neutral for the committed portfolio; goldens byte-identical | Done |
| [US-30.1](US-30.1-drift-valuation-basis.md) | Fix the drift valuation basis — honest anchor, fail-closed TWR, truthful note | Drift no-ledger path switches to the synthetic market-value chain (PRD F-1); ≤ −100% daily returns fail closed instead of compounding (F-2); basis notes made truthful per path; PortfolioStateEngine cash anchored from real cash_balances when starting_nav absent | Done |
| [US-28.1](US-28.1-ibkr-csv-importer-backend.md) | IBKR Activity-Statement CSV importer (backend) | New `interactive_brokers_csv.py` parsing `docs/IB2026.csv` (22 sections, utf-8-sig, stdlib csv) into the unchanged snapshot contract; fail-safe per record; reconciles against its own Change-in-NAV totals | Done |
| [US-28.2](US-28.2-wire-csv-end-to-end.md) | Wire CSV end-to-end: detection, upload UI, golden pipeline on IB2026.csv | Remove the three `.pdf` gates (statement_importer, App.tsx filter + accept attr); goldens key off IB2026.csv (Jan–Jun window — one deliberate `refresh_statement.py` regeneration); legacy PDFs unchanged | Done |
| [US-28.3](US-28.3-statement-refresh-resilience.md) | Statement-refresh resilience: centralize statement-truth pins + document the workflow | Classify statement-truth vs structural assertions; one truths module per side; swap-simulation meta-test; refresh workflow documented | Done |

Recommended build order: 28.1 → 28.2 → 28.3.

---

### Epic 27 — Financial Calculation Correctness (complete)

PRD: [`prd/epic-27-financial-calculation-correctness.md`](../prd/epic-27-financial-calculation-correctness.md)
(the PRD's audit-findings table F1–F13 is the canonical record; each story cites its findings)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-27.1](US-27.1-fix-information-ratio-annualization.md) | Fix the Information Ratio annualization | `build_relative_risk_summary` computes the daily IR (√252 off vs the documented `mean×252/TE`); exact-value pin test | Done |
| [US-27.2](US-27.2-fix-dashboard-monthly-returns-and-max-drawdown.md) | Fix dashboard monthly-return chaining + max-drawdown basis | Month-boundary returns are dropped (Π(1+mᵢ) ≠ TWR); max drawdown uses raw portfolio value instead of the wealth index | Done |
| [US-27.3](US-27.3-fix-covariance-matrix-date-alignment.md) | Fix covariance-matrix date alignment | `_compute_covariance_matrix` can zip returns from different dates when two symbols miss different days; pairwise date intersection | Done |
| [US-27.4](US-27.4-stress-scenario-null-semantics.md) | Stress scenarios: null semantics for missing loadings | `(loading or 0.0)` zero-fills missing factor loadings into projections; explicit partial/unavailable semantics instead | Done |
| [US-27.5](US-27.5-reconcile-factor-risk-share-denominator.md) | Reconcile the factor risk-share denominator | Code overwrites the doc's `variance/factor_total_variance` shares with `/total_variance_raw`; one convention, doc = code | Done |
| [US-27.6](US-27.6-null-collinear-factors-in-window-orthogonalization.md) | Null collinear factors in per-window orthogonalization | Collinear factor is kept raw → arbitrary ridge-split loadings + broken later-factor orthogonalization; doc says skip-with-null | Done |
| [US-27.7](US-27.7-stop-flat-backfill-synthetic-history.md) | Stop flat back-filling synthetic history before first quote | `first_price` back-fill fabricates zero returns → understated vol/VaR/drawdown; coverage disclosure instead | Done |
| [US-27.8](US-27.8-fx-fallback-trust-and-drift-return-basis.md) | Surface FX-fallback trust + fix drift-window return basis | Missing FX rate silently converts 1:1 (drift always passes `fx_history={}`); drift return uses raw market value, not TWR | Done |
| [US-27.9](US-27.9-low-severity-consistency-tail.md) | Low-severity tail | Fabricated 0.0 performance points → null; stdev-convention documentation; DR self-consistency + FMP `price` basis verification | Done |

Recommended build order: 27.1 → 27.2 → 27.3 → 27.4/27.5/27.6 → 27.7 → 27.8 → 27.9.

---

### Epic 25 — Dashboard Performance & Risk Summary (complete)

PRD: [`prd/epic-25-dashboard-performance-risk-summary.md`](../prd/epic-25-dashboard-performance-risk-summary.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-25.1](US-25.1-dashboard-performance-benchmark-card.md) | Performance & benchmark comparison card | TWR index chart vs benchmark + summary strip (Portfolio Value/TWR/MWR/Net Contributions), sourced from existing `range_metrics`/`performance_series` | Done |
| [US-25.2](US-25.2-dashboard-monthly-returns-grid.md) | Monthly returns grid card | Grid from `range_metrics[*].monthly_returns`; whole-card hide when `monthly_returns_reliable = false` | Done |
| [US-25.3](US-25.3-dashboard-risk-metrics-card.md) | Risk metrics card (volatility, drawdown, concentration) | Sourced from the already-fetched `DiagnosticsResult`, not the withheld dashboard-history path | Done |
| [US-25.4](US-25.4-epic-25-docs-closeout.md) | Docs close-out | Reconcile `dashboard-fields.md` + `current-product-state.md`; backfill HHI + Modified-Dietz formula sections in `financial-methodology.md` | Done |
| [US-25.5](US-25.5-information-ratio-risk-summary-card.md) | Information Ratio on the Risk Summary card | Surface the already-computed `relative_risk.{information_ratio,active_return_pct}` (found unrendered during a project review); backfill the methodology section | Done |

Recommended build order: 25.1 → 25.2 → 25.3 → 25.4.

---

### Epic 26 — Currency Exposure & Risk (active)

PRD: [`prd/epic-26-currency-exposure-and-risk.md`](../prd/epic-26-currency-exposure-and-risk.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-26.1](US-26.1-currency-exposure-by-weight.md) | Currency exposure by weight (snapshot) | New `analytics/currency_exposure.py` + Exposure-tab card: per-currency weight, non-base total, explicit `unclassified` bucket. Corrects two defects in the research brief's formula — the denominator must be **base-currency converted** (the brief's raw sum is the F-7 Critical defect US-30.5a fixed) and the null-currency rule was self-contradictory. Snapshot analytics, zero new market-data calls. A third correction emerged in build: the brief's "unclassified" bucket is unreachable (schema-required currency) and the real fabrication is upstream in the request-path builder — logged as US-26.3 | Done |
| [US-26.2](US-26.2-currency-risk-contribution.md) | Currency risk contribution (historical) | Decomposes each non-base holding's base-currency return into **local / FX / interaction** legs (an exact identity, not an approximation) and splits portfolio variance by component covariance into three shares summing to exactly 1.0. Dedicated route + self-fetching card (60d/252d, `Synthetic` badge) — **not** the exposure engine, which fetches no history. Both prior blockers cleared by the research brief. Measured on IB2026: securities 96.70% / currency 3.31% / interaction −0.013%, summing to exactly 1.0 | Done |

---

### Epic 24 — Codebase Improvement (active)

PRD: [`prd/epic-24-codebase-improvement.md`](../prd/epic-24-codebase-improvement.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-24.1](US-24.1-fix-hardcoded-year-ledger-filters.md) | Fix the hardcoded calendar-year ledger filters (latent bugs) | Remove the `year == 2025` filters in `activity.py` / `reconciliation.py` so non-2025 statements work; 2025 goldens unchanged | Done |
| [US-24.2](US-24.2-extract-risk-model-rubric-constants.md) | Extract the risk-model scoring rubric & thresholds into named constants | Lift `risk.py` mapping-score weights / hard-caps / thresholds / regime cutoffs + the coverage threshold into documented constants; behaviour-neutral (goldens unchanged) | Done |
| [US-24.3](US-24.3-dedupe-shared-analytics-constants.md) | De-duplicate the shared analytics constants & lookback helper | One shared `app/core/constants.py` for `lookback_calendar_days` / `MIN_DAILY_OBSERVATIONS` / `DEFAULT_BENCHMARK_SYMBOL`; behaviour-neutral (goldens unchanged) | Done |
| [US-24.4](US-24.4-harden-freedom24-importer-parsing.md) | Harden the Freedom24 importer parsing + extract its hardcodes | Fail-safe positional parsing (skip malformed → no crash); extract format hardcodes to named constants; correct the (non-real) ISIN-gap; FF2026 fixture pinned | Done |
| [US-24.8](US-24.8-harden-ibkr-espp-importer-parsing.md) | Harden the IBKR importer parsing (fail-safe) | Deferred US-24.4 follow-up: guard post-match numeric/date conversions in `interactive_brokers.py` so a malformed field degrades instead of crashing the whole import; `espp.py` investigated and found not to need it | Done |
| [US-24.6](US-24.6-fmp-client-transport-config.md) | Make the FMP client's transport config configurable (escaped URL + timeout) | Closes the one call that bypassed `fmp_base_url`: `get_etf_holders` hardcoded an absolute vendor URL, so a proxy/mock could not redirect it. Adds a *separate* `fmp_legacy_base_url` (the endpoint is legacy-v3, not `/stable`, so reusing `fmp_base_url` would 404) + `fmp_request_timeout_seconds`; cache identity deliberately preserved. Scoping correction: screener `limit=500` is an overridable default, not debt | Done |
| [US-24.9](US-24.9-ledger-replay-cash-de-dilution.md) | Cash de-dilution on the imported ledger-replay return series | Unblocked by Epic 31. Adds a per-day `trade_flow` to `DailyPortfolioState` and a third `ReturnBasis` — the trade-neutral market-value chain `(MV_t − trade_flow_t)/MV_{t−1} − 1` — so the imported path's beta / correlation / volatility / factor model exclude the ~3% cash sleeve without reintroducing the +37.23% trade-day fabrication a plain market-value chain causes. Investor-performance surfaces (TWR, monthly returns, max drawdown) deliberately unchanged | Done |
| [US-24.10](US-24.10-trade-price-anchor-for-unpriced-holdings.md) | Stop unpriced-symbol cash events fabricating investor-performance returns | Found by US-24.9. Symbols with no price history and no statement close are valued at **$0**, so trading them steps `total_portfolio_value` by the full cash amount and the TWR publishes it as performance (IB2026: **−7.90%** on 2026-04-08, **+9.61%** on 2026-04-27 — the window's two largest moves, both pure fabrication). Owner decision: value them at the **last broker trade price** from the statement's own ledger, forward-carry only (no back-fill, US-27.7), as a third precedence tier below history and statement close, disclosed as a flat-priced segment | Done |
| [US-24.11](US-24.11-render-replay-disclosures.md) | Render the replay disclosures the engine already computes | Frontend-only. All five dashboard-history replay disclosures (FX fallback, unpriced symbols, cash anchor, withheld return dates, trade-price anchoring) were computed, schema'd and contract-documented but `DashboardPanel.tsx` rendered **no** `run_metadata` at all — so a researcher saw a confident chart built on a `degraded` cash anchor with a withheld day and no indication. New `ReplayDisclosuresCard` on CardShell, one prose note per present degradation, renders nothing on a clean run, no Synthetic badge (broker truth, not synthetic history). Goldens byte-identical | Done |
| [US-24.5](US-24.5-decouple-broker-sections-from-domain.md) | Decouple broker statement sections from the domain (and fix the two silent misclassifications it caused) | Re-validating the register row found the coupling was **already producing wrong output**: `domain/ledger.py` matched broker display strings inline, so Freedom24 trades (`"Transactions"`) and ESPP contributions + purchases (`"Employee Stock Purchase Summary"`) all classified as `unknown` — leaving the proof system reporting an ESPP payroll deposit as `not_observed`. New section-role registry resolves (label, entry_type) → role; `source_section` stays provenance; an AST-based guard test fails the suite if any importer emits an unregistered label. IBKR byte-identical; goldens untouched | Done |
| [US-24.7](US-24.7-minor-hardcodes-and-orphaned-risk-path.md) | Name the unnamed financial tolerances, and delete the orphaned risk-contribution path the methodology cites | Epic 24's low-severity tail, re-validated item by item. **F-1:** the public `build_position_risk_contributions` had no production caller, yet `financial-methodology.md` named it as the source of per-position beta/correlation — the doc pointed at a code path that never ran (guardrail #1). Deleted with the response model only it used; doc corrected to the live path. **F-2:** the `0.25` reconciliation pass threshold and the `0.01` proof terminal-match tolerance are now named constants with rationales (incl. why they differ 100x). Three scoping corrections recorded rather than built. Goldens byte-identical | Done |

---

### Epic 23 — Dead-Code Cleanup & Codebase Review (complete)

PRD: [`prd/epic-23-dead-code-cleanup-and-review.md`](../prd/epic-23-dead-code-cleanup-and-review.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-23.1](US-23.1-detection-tooling-and-register.md) | Detection tooling + tech-debt register + removal protocol | Dev-only dead-code tooling (vulture/ruff, knip, `noUnusedLocals` staged) + `docs/tech-debt-register.md` + removal protocol | Done |
| [US-23.2](US-23.2-backend-sweep-analytics-schemas-domain.md) | Backend sweep — analytics, schemas, domain, instruments | Remove confirmed-dead pure-logic code; catalog smells; no formula change | Done |
| [US-23.3](US-23.3-backend-sweep-services-routes-clients.md) | Backend sweep — services, routes, clients, core, importers | Remove dead wiring/routes/clients; catalog smells; routes stay reachable | Done |
| [US-23.4](US-23.4-frontend-sweep-app-and-features.md) | Frontend sweep — app & features | Remove dead files/types/helpers; catalog smells (disposition → US-23.9; DashboardPerformanceChart → US-23.6) | Done |
| [US-23.5](US-23.5-contract-schema-type-docs-drift.md) | Contract & schema↔type↔docs drift reconciliation | Three-way audit + reconcile drift so deletions don't break a documented seam | Done |
| [US-23.6](US-23.6-tests-fixtures-golden-hygiene.md) | Tests, fixtures & golden-pipeline hygiene | Migrate to shared fixtures, remove dead/skip tests; keep guard + goldens invariants | Done |
| [US-23.7](US-23.7-scripts-docs-reconciliation-closeout.md) | Scripts, tooling & docs reconciliation | Sweep `scripts/`; reconcile docs; consolidate register → seed Epic 24 | Done |
| [US-23.8](US-23.8-enforce-dead-code-gate.md) | Enforce the dead-code floor in the canonical test gate | Wire knip + ruff + vulture zero-findings into `run_all_tests.py` (the tail; no ESLint) so dead code can't re-accumulate | Done |
| [US-23.9](US-23.9-remove-disposition-plumbing.md) | Remove the unused disposition plumbing (cross-seam) | Carved from US-23.4: remove the no-producer/no-consumer disposition subsystem (FE persistence + BE schema), gated by the workspace round-trip tests | Done |

---

### Epic 22 — Import Admission Review UI (completed)

PRD: [`prd/epic-22-import-admission-review-ui.md`](../prd/epic-22-import-admission-review-ui.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-22.1](US-22.1-import-admission-review-card.md) | Import Admission Review card | Render the persisted `admissionSummary` (decision + trust + per-check rows) as an Exposure-tab card — frontend-only | Done |
| US-22.2 | Admission review disposition workflow | Record a disposition per flagged check (accept-exception/needs-correction/deferred) with rationale | Won't do — not needed for a single-user local-first tool (2026-06-12) |

---

### Epic 21 — Testing Strategy & Architecture Hardening (completed)

PRD: [`prd/epic-21-testing-strategy-hardening.md`](../prd/epic-21-testing-strategy-hardening.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-21.1](US-21.1-deterministic-test-suite.md) | Deterministic suite — no live network in tests | Mock the 4 FMP-dependent "real portfolio" tests + autouse network guard with `live_data` marker | Done |
| [US-21.2](US-21.2-shared-test-fixtures.md) | Shared test-fixtures module | `app/tests/fixtures.py` (snapshot builders + market-data mock installer); migrate the 3 dict-based duplicate sets | Done |
| [US-21.3](US-21.3-response-integrity-property-test.md) | Engine response-integrity property test | Parametrized JSON-strict check over 8 engine routes + self-policing route-table coverage; `risk.py` non-finite audit | Done |
| [US-21.4](US-21.4-golden-pipeline-determinism.md) | Golden pipeline determinism | Goldens from a committed frozen fixture set — no live FMP, no env var, no per-machine churn | Done |
| [US-21.5](US-21.5-assertion-conventions-suite-speed.md) | Assertion conventions + suite speed | Additive-tolerant assertion rules in write-tests skill; pytest-xdist parallel run | Done |

Recommended build order: 21.1 → 21.2 → 21.3 → 21.4 → 21.5.

---

### Epic 20 — Market-Data Cache Efficiency & Control (completed)

PRD: [`prd/epic-20-market-data-cache-efficiency.md`](../prd/epic-20-market-data-cache-efficiency.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-20.1](US-20.1-cache-stats-and-clear.md) | Cache stats + clear (route + UI) | `GET /cache/stats` + `POST /cache/clear`; Market-data cache card on the Exposure tab | Done |
| [US-20.2](US-20.2-history-range-normalization.md) | History range normalization | One widened superset fetch per symbol, sliced per request — the FMP-call reduction | Done |
| [US-20.3](US-20.3-in-memory-layer-parallel-fetch.md) | In-memory layer + parallel fetch | Process memo over the file cache + parallel multi-symbol fetch | Done |

Recommended build order: 20.1 → 20.2 → 20.3.

---

### Epic 19 — Instrument Identity Integrity (completed)

PRD: [`prd/epic-19-instrument-identity-integrity.md`](../prd/epic-19-instrument-identity-integrity.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-19.1](US-19.1-instrument-description-consistency.md) | Instrument description-consistency check | Backend detector + admission check + Data Sources panel warning for ticker↔description mismatches | Done |
| [US-19.2](US-19.2-isin-keyed-registry-identity.md) | ISIN-keyed registry identity | Statement-sourced ISIN seeds in the registry + definitive ISIN-mismatch detection | Done |

Recommended build order: 19.1 → 19.2.

---

### Epic 18 — Secondary Market-Data Provider (complete)

PRD: [`prd/epic-18-secondary-market-data-provider.md`](../prd/epic-18-secondary-market-data-provider.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-18.1](US-18.1-yfinance-fallback-provider.md) | yfinance fallback provider + data provenance | Backend — `YFinanceClient` + `MarketDataService` fallback + provenance; provenance marker on the Intra-Portfolio Correlation card | Done |
| [US-18.2](US-18.2-portfolio-provenance-indicator.md) | Portfolio-level data-sources indicator | One Exposure-tab "Data sources" panel (FMP vs Yahoo vs unpriced) via a dedicated provenance engine | Done |
| [US-18.3](US-18.3-defense-etf-symbol-mapping.md) | Defense-ETF Yahoo symbol mapping | `DFND` → real VanEck Defense lines (not the look-alike `DFND.L`); DEFS/IDFN already correct | Done |
| [US-18.4](US-18.4-sanitize-nonfinite-price-rows.md) | Sanitize non-finite price rows (bugfix) | Yahoo NaN bars skipped at the client + seam-level row sanitization in `MarketDataService` (fixes correlation 500s) | Done |

Recommended build order: 18.1 → 18.2 → 18.3.

---

### Epic 17 — Intra-Portfolio Correlation (complete)

PRD: [`prd/epic-17-intra-portfolio-correlation.md`](../prd/epic-17-intra-portfolio-correlation.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-17.1](US-17.1-pairwise-correlation-heatmap.md) | Pairwise correlation matrix engine + heatmap | Full-stack — `pairwise_correlation_matrix()` + `average_pairwise_correlation()` in `analytics/correlation.py`; `intra_correlation_engine.py`; `POST /engines/correlation/intra`; `IntraCorrelationHeatmap` card on the Exposure tab | Done |
| [US-17.2](US-17.2-diversification-summary-metrics.md) | Diversification summary metrics | Full-stack — `diversification_ratio()` + `effective_number_of_bets()` (numpy) in `analytics/correlation.py`; engine wiring; summary-strip additions on `IntraCorrelationHeatmap` | Done |
| ~~US-17.3~~ | ~~Docs, contracts, roadmap close-out~~ | Cancelled — docs reconciled per-story via update-docs | Cancelled |

Recommended build order: 17.1 → 17.2.

---

### Epic 16 — Factor Drift Visualization (complete)

PRD: [`prd/epic-16-factor-drift-visualization.md`](../prd/epic-16-factor-drift-visualization.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-16.1](US-16.1-factor-drift-summary-card.md) | Factor Drift Summary card | Frontend-only — `FactorDriftSummaryCard` on the Exposure tab: ranked per-factor delta (latest − reference) bars, 20d/60d/252d window, Synthetic badge, unavailable state | Done |

Single-story epic (quick-win follow-up). No build-order constraints.

---

### Epic 15 — Position-Level Analytics (complete)

PRD: [`prd/epic-15-position-level-analytics.md`](../prd/epic-15-position-level-analytics.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-15.1](US-15.1-drawdown-decomposition-engine.md) | Drawdown decomposition engine + schema | Backend — `decompose_drawdown_episode()` in `analytics/drawdown.py`; extend `DrawdownEpisode` Pydantic schema; wire into `drawdown_engine` | Done |
| [US-15.2](US-15.2-drawdown-contributors-drawer.md) | Drawdown card "Contributors" drawer | Frontend — expandable per-episode drawer in `DrawdownAnalyticsCard.tsx` | Done |
| ~~US-15.3~~ | ~~Factor loading drift chart~~ | **Cancelled 2026-06-04**: existing `RollingFactorLoadingsCard` on Dashboard tab already covers the use case | Cancelled |
| [US-15.4](US-15.4-epic-15-docs-closeout.md) | Epic 15 docs close-out | Docs — `risk-fields.md` decomposition fields, methodology verify, current-product-state Risk-tab extension | Done |

Recommended build order: 15.1 → 15.2 → 15.3 → 15.4.

---

### Epic 14 — Post-Epic-13 Bug Sweep (complete)

PRD: [`prd/epic-14-post-epic-13-bug-sweep.md`](../prd/epic-14-post-epic-13-bug-sweep.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-14.1](US-14.1-fix-overlay-symbol-collision.md) | Fix overlay symbol collision (sum, don't replace) | Frontend — `overlayImportedSnapshot` in `portfolioSnapshot.ts` | Done |
| [US-14.2](US-14.2-drawdown-smart-default-window.md) | DrawdownAnalyticsCard smart-default window fallback | Frontend — cycle 1260→756→252→Max on `trust='unavailable'` | Done |
| [US-14.3](US-14.3-freedom24-fmp-enrichment.md) | Freedom24 FMP company-profile enrichment for unknown symbols | Backend — new shared `enrich_imported_instruments` helper + Freedom24 parser wire-up | Done |

Recommended build order: 14.1 → 14.2 → 14.3.

---

### Epic 13 — Risk Analytics Tab (complete)

PRD: [`prd/epic-13-risk-analytics-tab.md`](../prd/epic-13-risk-analytics-tab.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-13.1](US-13.1-risk-tab-and-stress-card.md) | Risk tab + Stress Scenarios card | Full-stack — `App.tsx` tab union extended + `RiskPanel.tsx` scaffold + `StressScenariosCard.tsx` + `POST /engines/stress/run` route + service | Done |
| [US-13.2](US-13.2-drawdown-analytics-card.md) | Drawdown Analytics card | Full-stack — `analytics/drawdown.py` (episode identification) + `POST /engines/drawdown/run` + `DrawdownAnalyticsCard.tsx` (underwater curve + top-N table) | Done |
| [US-13.3](US-13.3-var-distribution-card.md) | VaR & Distribution card | Full-stack — `analytics/distribution.py` + `POST /engines/distribution/run` + `VarDistributionCard.tsx` (histogram + percentile/tail/shape table) | Done |
| [US-13.4](US-13.4-risk-tab-polish-and-a11y.md) | UI density polish + trust-state + a11y verification | Frontend — RiskPanel header rewrite, VarDistributionCard section header slim-down, cross-card audit, density tests | Done |
| [US-13.5](US-13.5-epic-13-docs-closeout.md) | Docs close-out | Docs — `risk-fields.md`, methodology verification, roadmap, `current-product-state.md`, `CLAUDE.md` | Done |

Stories must be built in order (13.1 → 13.2 → 13.3 → 13.4 → 13.5).

---

### Epic 12 — UI Polish & Design System (complete)

PRD: [`prd/epic-12-ui-polish-design-system.md`](../prd/epic-12-ui-polish-design-system.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-12.1](US-12.1-design-tokens-and-card-polish.md) | Design tokens + apply to the four Exposure cards | Frontend — `styles.css` :root tokens + refactor 5 card files + fix rolling-correlation axis overlap + audit test | Done |
| [US-12.2](US-12.2-primitive-components.md) | Primitive components + refactor cards | Frontend — `<CardShell>`, `<WindowSelector>`, `<TrustBadge>`, `<EmptyState>`, `<LoadingState>`, `<ErrorState>` + refactor 5 cards | Done |
| [US-12.3](US-12.3-accessibility-and-chart-defaults.md) | Accessibility + Recharts defaults (ChartShell) | Frontend — ARIA, focus-visible, color-blind-safe, `<ChartShell>` wrapper + contrast audit | Done |
| [US-12.4](US-12.4-ui-polish-skill-and-closeout.md) | `ui-polish` skill + Epic 12 close-out | `.claude/skills/ui-polish/SKILL.md` + `docs/contracts/ui-design-system.md` + roadmap close | Done |

Stories must be built in order (12.1 → 12.2 → 12.3 → 12.4).

---

### Epic 11 — Factor Return Attribution (complete)

PRD: [`prd/epic-11-factor-return-attribution.md`](../prd/epic-11-factor-return-attribution.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-11.1](US-11.1-attribution-engine-endpoint.md) | Attribution engine + endpoint | Backend — analytics function, Pydantic schema, FastAPI route, pytest | Done |
| [US-11.2](US-11.2-attribution-card-chart-table.md) | Attribution card (chart + table) | Frontend — FactorAttributionCard, vitest | Done |
| [US-11.3](US-11.3-attribution-docs-closeout.md) | Docs, contracts, roadmap close-out | Docs — attribution-fields.md, methodology verification, slice log | Done |

Stories must be built in order (11.1 → 11.2 → 11.3). US-11.2 depends on the endpoint from US-11.1.

---

### Epic 10 — Multi-broker Import Correctness (complete)

PRD: [`prd/epic-10-multi-broker-import-correctness.md`](../prd/epic-10-multi-broker-import-correctness.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-10.1](US-10.1-three-broker-combine-tests.md) | 3-way combine and API-level import tests | Backend pytest — combine + import_statements + analytics | Done |
| [US-10.2](US-10.2-add-statement-overlay-tests.md) | Sequential add-statement overlay tests | Frontend vitest — overlayImportedSnapshot 3-step flow | Done |

---

### Epic 9 — Portfolio Correlation & Co-movement Analysis (complete)

PRD: [`prd/epic-9-correlation-analysis.md`](../prd/epic-9-correlation-analysis.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-9.1](US-9.1-indexed-return-chart.md) | Indexed return time-series chart | Frontend — chart of existing `daily_series` data (no backend work) | Done |
| [US-9.2](US-9.2-rolling-correlation-chart.md) | Rolling correlation and beta chart | Frontend — chart of existing `rolling_risk` data (no backend work) | Done |
| [US-9.3](US-9.3-multi-benchmark-correlation-matrix.md) | Multi-benchmark correlation matrix | Full-stack — new `correlation.py` analytics + `POST /engines/correlation/multi` + frontend table | Done |
| [US-9.4](US-9.4-fix-rolling-factor-loadings-methodology.md) | Fix rolling factor loadings methodology | Backend bugfix — per-window orthogonalization + ridge floor | Done |
| [US-9.5](US-9.5-correlation-docs-closeout.md) | Docs, contracts, roadmap close-out | Docs — `correlation-fields.md`, methodology verification, slice log | Done |
| [US-9.6](US-9.6-correlation-followups.md) | Multi-benchmark correlation follow-ups | Tests + docs — sort regression, trust-indicator pinning, umbrella methodology section | Done |

Stories must be built in order (9.1 → 9.2 → 9.3 → 9.5). US-9.4 is a Done bugfix independent of 9.1–9.3.

---

### Epic 8 — Reset to Analysis Core (complete)

PRD: [`prd/epic-8-reset-to-analysis-core.md`](../prd/epic-8-reset-to-analysis-core.md)

| Story | Title | Scope | Status |
|---|---|---|---|
| [US-8.1](US-8.1-remove-workflow-tabs.md) | Remove workflow tabs from navigation | Frontend — nav only | Done |
| [US-8.2](US-8.2-strip-backtest-frontend.md) | Strip Workspace and Monitoring frontend | Frontend — features/backtest/ | Done |
| [US-8.3](US-8.3-strip-ranking-optimizer-frontend.md) | Strip ranking and optimizer frontend | Frontend — features/strategy-lab/, features/generic-ranking/, features/optimizer/ | Done |
| [US-8.4](US-8.4-strip-app-state.md) | Strip App.tsx workflow state and storage | Frontend — App.tsx, workspace storage | Done |
| [US-8.5](US-8.5-strip-ranking-construction-optimizer-backend.md) | Remove ranking, construction, and optimizer backend | Backend — routes, services, schemas | Done |
| [US-8.6](US-8.6-strip-backtest-monitoring-backend.md) | Remove backtest and monitoring backend | Backend — routes, services, schemas | Done |
| [US-8.7](US-8.7-prune-portfolio-feature-dir.md) | Prune portfolio feature directory | Frontend — features/portfolio/ dead code | Done |
| [US-8.8](US-8.8-reset-docs-and-contracts.md) | Reset docs and contracts | Docs — contracts, PRDs, roadmap | Done |
| [US-8.9](US-8.9-add-drift-vs-benchmark.md) | Add portfolio drift vs index benchmarks | Backend + Frontend — new Exposure feature | Done |

Stories must be built in order (8.1 → 8.2 → ... → 8.9). Each leaves a compilable, test-green codebase. Story 8.9 (the one additive story) goes last.

---

### Epic 5 — Usable Core Flow (complete — superseded by Epic 8 pivot)

| Story | Title | Status |
|---|---|---|
| [US-5.1](US-5.1-fix-app-navigation-order.md) | Fix app navigation order | Done |
| [US-5.2](US-5.2-workspace-candidate-ux.md) | Make Workspace candidate selection self-explanatory | Done |
| [US-5.3](US-5.3-fix-review-in-construction.md) | Fix "Review in Construction" end-to-end | Done |
| [US-5.4](US-5.4-clear-replay-comparison-output.md) | Clear replay comparison output | Done |

### Epic 3 — Construction & Optimizer Methodology (cancelled — features removed in Epic 8)

| Story | Title | Status |
|---|---|---|
| [US-3.1](US-3.1-inverse-volatility-weighting-policy.md) | Risk-aware (inverse-volatility) weighting policy | Cancelled |
| [US-3.2](US-3.2-inverse-rank-weight-opt-in.md) | Make inverse-rank-weight selectable at launch | Cancelled |
| [US-3.3](US-3.3-top-n-in-etf-ranking-tab.md) | Set Top N directly in the ETF Ranking tab | Cancelled |

To implement a story, invoke the `build-story` skill and point it at the file.
To author a new story from a feature idea, invoke the `write-story` skill.
