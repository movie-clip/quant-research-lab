# Epic Roadmap

*Living execution snapshot. Updated: 2026-07-18 (Epic 31 — Ledger Replay Correctness **active** (US-31.1 audit done; F-1..F-3 open, blocks tech-debt US-24.9); Epic 30 — Exposure Improvements **complete** (all 8 stories done, closed 2026-07-16; created from the verified drift-panel findings F-1..F-6, extended by the US-30.4 audit's F-7..F-10; calculations-first); Epic 29 — Chart First-Render Reliability **complete** (salvaged from a parallel session, renumbered from its "Epic 27"); Epic 28 — IBKR CSV Importer & Statement-Refresh Resilience **complete** (all 3 stories done 2026-07-07); Epic 27 — Financial Calculation Correctness **complete** (all 9 stories done, findings F1–F13 resolved); Epic 25 — Dashboard Performance & Risk Summary complete; Epic 24 — Codebase Improvement active; Epic 26 — Currency Exposure & Risk backlog (research brief only); Epic 23 — dead-code cleanup & codebase review complete; Epics 13/18/19/20/21/22 complete).*

---

## Completed Epic: Epic 31 — Ledger Replay Correctness

**PRD:** [`docs/product/prd/epic-31-ledger-replay-correctness.md`](product/prd/epic-31-ledger-replay-correctness.md)

Created 2026-07-18 from a defect found while scoping tech-debt US-24.9: the
**imported ledger-replay** path — the truth class the product presents as
broker truth — publishes a **fabricated −36.34% single-day return** on the
committed IB2026 portfolio, inflating its annualised volatility **+79%**
(36.05% → 64.55%). Root-caused to one causal chain, reproduced against the
**frozen** golden market data (deterministic, network-free): price histories
are fetched only for *current* holdings while the replay reconstructs *opening*
positions (**11 of 38 priced on day 1**, opening MV $14,582 vs ~$50,116); the
`base_cash = starting_nav − opening_positions_value` anchor then absorbs the
**$35,534** error as a cash plug that rides the whole window; and the terminal
reconciliation snaps it out on the final day, where the return series reads the
accounting correction as performance.

The impact map (PRD) shows the policy gates do **not** contain it: the Exposure
rolling correlation & beta chart, the risk summary's beta/correlation/volatility,
and the factor model are all **surfaced and corrupted**; only the relative-return
and drawdown families are gated to `null`.

| Story | Title | Status |
|---|---|---|
| US-31.1 | Findings-first audit of the imported ledger replay (F-1..F-3 + impact map) | Done |
| US-31.2 | Fix F-1: price history for the full reconstructed symbol set | Done |
| US-31.3 | Fix F-2/F-3: stop cash absorbing valuation error; never publish a reconciliation adjustment as a return | Done |
| US-31.4 | Fix F-5: stop the bare-symbol fallback substituting a different security | Done |
| US-31.5 | Fix F-4: convert each replayed holding by its fund currency | Done |

**Closed 2026-08-04** — all five findings (F-1..F-5) resolved. The imported
ledger-replay path reconciles to the broker statement (terminal market value
within $1.35 of `stock_total`), and the one irreducible gap — a period-start NAV
vs window-start valuation — is measured and disclosed rather than absorbed.
**Unblocks tech-debt US-24.9** (ledger-path cash de-dilution), which can now be
built on a trustworthy series.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-08-04 | US-31.3 | **Fixed F-2/F-3 — the last Epic 31 findings; epic closed.** With F-1/F-4/F-5 cleared, the remaining drift was purely cash, and re-measuring root-caused F-2 to a **date mismatch** rather than a valuation error: `base_cash = starting_nav − opening_positions_value` subtracts a **window-start** market value (2026-01-08, $49,124.79) from a **period-start** NAV (2026-01-01, $52,381.12), so five trading days of market movement are plugged into cash. The residual is **−$1,196.61 at the anchor and −$1,196.61 at the terminal state — identical to the cent**, proving the in-window flows are correct and isolating the anchor. The replay *cannot* value the period-start date (no prices exist before the window), so per the owner's **fail-closed + disclose** decision the residual is measured and surfaced, never fabricated: new `ReplayCashAnchor` (basis / `nav_as_of` / `window_start` / residual / trust) reports `statement_nav_date_mismatch` + **`degraded`**, and can only claim `verified` when the dates align AND the residual is within the new named `REPLAY_RECONCILIATION_TOLERANCE`. **F-3:** the terminal reconciliation still snaps to the statement's ending NAV (that IS the broker's number) but now records `reconciliation_adjustment` (+$1,197.88), and the affected day's return is **WITHHELD** — surfaced via `withheld_return_dates` + a stated reason, so the gap is visible rather than silent. The predicate lives on `DailyPortfolioState.return_is_publishable` so all **three** return builders (`performance.py`, `risk.py`, `attribution.py`) share it and cannot drift — the US-31.2 "one shared chain" lesson. Annualised volatility **23.63% → 23.32%** (the day is excluded outright, not recomputed un-reconciled: its value was overwritten, so no trustworthy return exists for it). **Measurement trap caught and pinned:** the statement-implied opening cash must use **FX-converted** flows — the raw `cash_effect` sum is currency-mixed (−$271.23 vs −$2,459.29 converted, implying $2,264.88 instead of the correct $4,452.94); a dedicated test rejects the raw basis. `dashboardGoldens.ts` diff is **purely additive** — the new field on 209 states with **zero value changes** (verified line-by-line); `golden_market_data.json` byte-identical, no re-capture. All five audit pins in `test_ledger_replay_audit.py` inverted from "KNOWN WRONG" to assert-resolved. +10 backend tests. 600 backend (+10) + 285 frontend green; tsc + dead-code gate clean. **Epic 31 closed; US-24.9 unblocked.** |
| 2026-07-25 | US-31.5 | **Fixed F-4: the replay now converts each holding by its fund currency, and the terminal market value reconciles to the statement.** Every replay call site passed `fx_history={}`, carrying EUR/GBP values unconverted (US-27.8 fallback). The obvious fix — convert by `position.currency` — is **4.3× worse** (the audit's trap): the provider's *quote* currency varies per resolved line and is not the broker listing (DEFS listed EUR but `DEFS.L` quotes USD; `SXRV.DE` quotes EUR; `SEMI.L` quotes GBP). **Key finding:** the **InstrumentRegistry** currency equals the observed quote basis for every priced holding (0 mismatches across 19) — it was hand-curated to the fund currency (US-24.2/18.3), so it is the reliable conversion basis; `snapshot.instruments[].currency` is `None` on the CSV path. New `valuation_currency` in `PortfolioStateEngine` selects the **fund currency** (new `symbol_fund_currencies` param, from the registry) for market-priced values and keeps the **position currency** for statement-anchored values (LQQ — the anchor is the statement close, in the listing currency). New shared `build_replay_currency_context` resolves the fund-currency map + a static per-date `fx_history` from the statement's own implied rates (US-28.1 broker truth, the US-30.2 pattern); both replay callers (`dashboard_history_engine`, `diagnostics_engine`) use it. **Result:** IB2026 terminal market value **$61,239.88** vs the statement `stock_total` **$61,238.53** ($1.35 residual, 0.002%), and `run_metadata.fx_fallback_currencies` **empties** for EUR/GBP (genuinely converted, not carried). The remaining terminal reconciliation gap is now almost entirely the F-2 cash plug (~$1,092), leaving US-31.3 a clean number. **Conversion-only** — `golden_market_data.json` byte-identical (no `--capture`, no FMP key); the `dashboardGoldens.ts` diff is confined to the five EUR/GBP holdings (SEMI/SXRV/LQQ + since-sold DFND/ACOMO) and dependent daily totals; every USD series + identity/weight/sector/cost/ledger/ISIN/cash family byte-identical. Fail-closed preserved (AC6): no statement rates → carried unconverted + disclosed, exactly as US-27.8. +7 backend tests (5 engine + 2 disclosure); the F-4 audit pin flipped to assert-resolved. 590 backend (+5 net) + 285 frontend green; tsc + dead-code gate clean. |
| 2026-07-25 | US-31.4 | **Fixed F-5: the bare-symbol fallback no longer substitutes a different security for SEMI.** `SEMI`'s resolution rule carried a bare `"SEMI"` fallback; when the held LSE UCITS line `SEMI.L` (iShares MSCI Global Semiconductors, GBP, ISIN IE000I8KRLL9) was unavailable on the FMP plan it fell through to the **US-listed `SEMI`** — a different security quoting 40.58 vs the held 17.998 GBP, overstating a 4.4% holding by **+$2,506.93** (the largest single term in the replay's terminal MV drift, and a series that also fed correlation/beta/factor loadings/risk contribution). Removed the bare candidate from `quote/history/holdings_candidates` in `app/core/symbols.py`, leaving `("SEMI.L",)` — mirroring the existing **CIBR** and **DFND** wrong-fund guards exactly; the US line stays reachable only as a labeled proxy (`SOXX`/`SMH` unchanged). With the bare candidate gone the yfinance secondary provider returns the correct `SEMI.L` GBP line, so SEMI's replayed terminal value is now **$2,699.70** (150 × 17.998, correct fund) — it moved out of the F-5 wrong-instrument bucket into the F-4 unconverted-GBP bucket that **US-31.5** owns. **Side effect on F-3:** with SEMI corrected the engine slightly under-values terminal MV, so the reconciliation now snaps **up** (+2.77% vs +0.89% un-reconciled) — the fabricated adjustment flipped sign, confirming US-31.3 must land last. Deliberate golden re-capture (the stale wrong-SEMI FMP cache cleared first): the `dashboardGoldens.ts` diff is **SEMI-only** — SEMI's per-day `market_price`/`market_value` and the dependent daily `total_market_value`/`total_portfolio_value`/`return_pct`; statement-identity, weight, sector, cost-basis, ledger-count, ISIN and cash-by-currency families byte-identical, every non-SEMI position series unchanged. +3 `test_market_data.py` guard tests; the F-5 audit pin flipped to assert-resolved and the F-4 pin extended to cover SEMI (now a clean GBP conversion case). No schema/formula/contract change. 583 backend (+3) + 285 frontend green; tsc + dead-code gate clean. |
| 2026-07-24 | — | **Findings-first audit while re-scoping US-31.3 — two new findings (F-4, F-5), no fixes.** Re-measuring F-2/F-3 on merged main showed the terminal reconciliation gap (**$2,229.11**) is only ~half F-2: cash drift **$1,092.20** vs terminal market-value drift **$1,139.53**. The MV half decomposes **exactly** across three symbols — **SEMI +$2,506.93**, **SXRV −$1,077.45**, **LQQ −$291.30** — so **the net gap badly understates the true error** ($2.5k of wrong-instrument overstatement masked by $1.37k of opposite-signed FX understatement); anything judging replay health by the net figure draws the wrong conclusion. **F-5 (High):** `resolve_symbol_candidates("SEMI")` = `['SEMI.L','SEMI']`; SEMI.L is unavailable on the current FMP plan (402), so resolution falls through to the **bare US-listed `SEMI`** — confirmed via `last_fetch_meta.resolved_symbol` — quoting 40.58 against the held LSE UCITS line's 17.998 GBP (2.2547×) on a 4.4% position. Same collision class the registry already documents for **CIBR** (hard-pinned to `['CIBR.L']`); SEMI is unguarded. Blast radius exceeds the replay — the substituted series feeds rolling correlation, beta, factor loadings, risk contribution and intra-correlation. **F-4 (High):** the replay carries everything unconverted (`fx_history={}` at every call site), but the obvious fix is **unsafe** — applying the statement's own broker-truth rates by `position.currency` makes drift **4.3× worse** ($1,139.53 → $4,951.06), because the provider's quote currency varies per resolved line: `DEFS.L` quotes **USD** for an **EUR** position (error exactly $0.00 today — converting would double-count) while `SXRV.DE` quotes **EUR** (conversion required). Both are EUR positions, so the cases are indistinguishable from the snapshot alone; no per-symbol quote currency exists anywhere in the pipeline. Recorded an examined-and-found-correct list too (19 of 20 holdings resolve to the intended venue line; all 13 USD holdings ratio exactly 1.0000; LQQ's anchor and US-31.2's unpriced disclosure both behaving). Two reproduction pins added to `test_ledger_replay_audit.py` (network-free). **US-31.3 re-rated Critical → High and re-ordered behind US-31.4/31.5** — its adjustment is ~50% MV error, so fixing the cash plug first would pin a tolerance against a number the other two then move (the US-31.2 sequencing lesson). Audit-only: no production code touched, goldens byte-identical. |
| 2026-07-24 | US-31.2 | **Fixed F-1: the ledger replay now prices every position it reconstructs — and that alone removes most of F-3.** New `replay_symbol_universe(snapshot)` derives the fetch set from the SAME BUY/SELL scan that builds `opening_positions` (the US-30.1 "one shared chain" lesson), so the symbols fetched can never drift from the symbols valued. **Scoping correction:** the PRD's "38" is the count of non-zero *opening* positions, not the set needing prices — the universe is **63** (38 opening ∪ **16 bought AND sold entirely inside the window**, which appear in neither the opening nor the ending set yet are held on interior days, ∪ 9 opened in-window and still held). Both ledger-replay callers (`dashboard_history_engine`, `diagnostics_engine`) fetch it **separately** from `symbol_price_histories`, which still feeds the return-basis evidence and the downstream fan-out on the current-holdings basis those consumers are specified against; the synthetic branch is untouched (AC3 negative-pinned). **Two latent traps that the wider fetch armed, both closed:** (1) `_effective_valuation_dates` scored an unknown symbol `weight_by_symbol.get(symbol, 1.0)` — harmless only because since-sold symbols had no history to reach `first_covered`; they are now excluded from the truncation reference set (they have no current weight to evaluate), else any one with mid-window coverage would truncate the replay for every holding; (2) `fallback_prices` is keyed on current positions, so an unfetchable since-sold symbol contributed 0 in silence — new `unpriced_replay_symbols` disclosure on `DashboardHistoryRunMetadata` (TS + contract row mirrored). **Results (frozen data, network-free):** day-one opening MV **$14,582.03 → $49,024.04** vs implied $50,116.24 (70.9% short → 2.2%; residual is LQQ's US-27.7 statement-close anchor); opening-cash drift **$35,534.21 → $1,097.18 (−96.9%)**, confirming F-1 as the dominant term of the F-2 plug (AC8's falsification check). **F-3 materially re-scoped:** the fabricated terminal return fell **−36.34% → −2.56%** and its annualised-volatility inflation **+79% (36.21%→64.82%) → +1.1% (23.65%→23.91%)** — US-31.3 is still required on principle (guardrail #3: never publish an accounting adjustment as a return) but is no longer Critical in magnitude. **FF2026 caught the same defect on a second statement:** opening SCHD 28 / VWO 4 were unpriced, inflating start_value to 39% above the broker's own `starting_nav`, which fabricated a **−23.86%** period loss; corrected to **+3.75%** (2960.00 → 3071.00), with the US-27.2 chaining invariant Π(1+mᵢ)−1 still matching exactly. Goldens + `golden_market_data.json` re-captured **deliberately** (23 → 68 series) and itemized per family: market_value/market_price/portfolio_value/cash/return series moved; **statement-identity, ledger-count, weight, sector, cost-basis, ISIN and cash-by-currency families byte-identical**. Four `test_analytics.py` fixtures converted from ordered `side_effect` lists to a symbol-keyed dispatch (US-21.5: call order/count is not the contract). 578 backend (+13) + 285 frontend green; tsc + dead-code gate clean. |
| 2026-07-18 | US-31.1 | **Opened Epic 31 from a defect found while scoping US-24.9 — findings-first, no fixes.** Recorded **F-1..F-3** as one causal chain with `file:line` evidence, every number reproduced against the **frozen** `golden_market_data.json` (deterministic, network-free — not a local-cache artifact): **F-1 (Critical)** market data is fetched for *current* holdings only (`[p.symbol for p in snapshot.positions]`) while `build_daily_states` reconstructs *opening* positions by rolling back BUY/SELL — 38 opening symbols vs 20 current, leaving **27 of 38 unpriced on day 1** and opening MV at **$14,582.03** vs implied **$50,116.24**. **F-2 (Critical)** `base_cash = starting_nav − opening_positions_value` makes cash a **plug**: the $35,534.21 undervaluation is absorbed into opening cash ($37,799.09 vs implied $2,264.88) and rides every daily state, with no disclosure and no fail-closed — the same structural defect Epic 30 F-1 fixed only for the *no-ledger* path. **F-3 (High)** `_reconcile_terminal_state_to_statement_totals` corrects the whole drift on the final day, so the return series reads it as performance: last-day return **−36.34%** with reconciliation vs **+0.57%** without; annualised volatility **36.05% → 64.55% (+79%)** from that one day, contaminating every rolling window touching 2026-06-30. Added an **impact map**: the policy gates do *not* contain the defect — the Exposure rolling correlation/beta chart, risk-summary beta/correlation/volatility and the factor model are **surfaced and corrupted**; only the relative-return and drawdown families are gated to `null`. Also recorded an examined-and-found-correct list (synthetic path unaffected; `external_cash_flow` scope correct; no ledger entry type dropped by `snapshot_to_ledger`; `portfolio_proof` already builds with `apply_terminal_reconciliation=False`). Tech-debt **US-24.9** annotated as **blocked by Epic 31**. Audit-only: no production code touched, `dashboardGoldens.ts` byte-identical. |

---

## Completed Epic: Epic 30 — Exposure Improvements

**PRD:** [`docs/product/prd/epic-30-exposure-improvements.md`](product/prd/epic-30-exposure-improvements.md)

Created 2026-07-08 from an owner bug report: the vs-Market drift panel showed
no chart until a benchmark change, then impossible window returns
(−6226.32% 3M). All four reported numbers reproduced exactly and root-caused
(PRD findings F-1..F-6, findings-first per the Epic 27 discipline): the
drift request path carries no statement_totals/ledger, so
`PortfolioStateEngine` anchors cash at `0 − opening_positions_value`
(≈ −$62.6k) and the TWR chain divides by near-zero fabricated portfolio
values, compounding through impossible (≤ −100%) daily returns while labeled
`trust="synthetic"` with a false "broker-ledger replay" note; zero-coverage
LQQ silently omitted; panel requires a dropdown interaction to fetch at all.
Six stories: verified drift fixes first (US-30.1..30.3), then a
findings-first audit of every remaining Exposure calculation surface
(US-30.4/30.5), UI polish last (US-30.6). **Calculations must be accurate —
that is the epic's bar.** Stories authored via `write-story` on pickup.
*Closed 2026-07-16 with eight stories — the audit's four findings (F-7..F-10)
split US-30.5 into 30.5a/b/c.*

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-30.1 | Fix the drift valuation basis (fail-closed TWR, honest anchor) | Done |
| US-30.2 | Drift coverage + FX disclosure | Done |
| US-30.3 | Exposure-tab first-render reliability | Done |
| US-30.4 | Findings-first audit of remaining Exposure calculations | Done |
| US-30.5a | Fix F-7 + F-8: base-currency weights + FX disclosure | Done |
| US-30.5b | Fix F-9: min-observation gate on per-position beta | Done |
| US-30.5c | Fix F-10: provenance-selected return basis (cash excluded on synthetic surfaces) | Done |
| US-30.6 | Exposure UI polish — Concentration Pack → CardShell + audit coverage | Done |

---

## Completed Epic: Epic 29 — Chart First-Render Reliability

**PRD:** [`docs/product/prd/epic-29-chart-first-render-reliability.md`](product/prd/epic-29-chart-first-render-reliability.md)

### Goal

Fix charts (Dashboard's Performance & Benchmark / Rolling Factor Analysis;
Exposure's Rolling Correlation / Factor Return Attribution and others)
rendering as an empty area right after a portfolio import, requiring a page
reload to appear. Root-caused via live browser reproduction to a Recharts
`ResponsiveContainer` measurement race in the shared `ChartShell` primitive.
*(Authored in a parallel session as "Epic 27"; renumbered to Epic 29 at merge
on 2026-07-07 to resolve the collision with Epic 27 — Financial Calculation
Correctness.)*

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-29.1 | Defer ChartShell's chart mount by one tick | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-07-16 | US-30.6 | **Exposure UI polish (Epic 30 close) — the Concentration Pack is now a landmarked card, and its host file is under the design-system audit.** A findings-first audit against the `ui-polish` DoD found the tab **already meets the baseline** (all 5 audit tests green; every card on `CardShell`; every self-fetching card has Loading/Error; both correlation surfaces carry the ▲▲/▲/•/▼/▼▼ glyph so colour is never the sole encoder) — so the story was re-scoped from a broad sweep to the **one real gap** `ui-polish` explicitly defers: the **Concentration Pack** (largest Exposure surface, inline in `ExposurePanel.tsx`) was three raw `<section>`s with **no landmark**, and sat **outside the audited surface**. Migrated the outer block onto `<CardShell title="Concentration Pack">` (layout classes preserved via `className` passthrough — `.compact-chart-panel` is intentionally empty, so **zero layout change**), gave the "Top Positions"/"Top Sectors" subsections `aria-labelledby` names, and added `ExposurePanel.tsx` to `ALL_CARD_FILES` (no-hex / no-px / single-source-`"Synthetic"` coverage). **Truth-class integrity held (guardrail #2):** the pack is snapshot analytics (broker-truth composition), **not** synthetic history, so it renders **no** `Synthetic` badge — its `Basis`/`Scope`/`Availability` status strip (available/partial/withheld, which don't map to TrustBadge's two types) is unchanged. No backend/schema/methodology/contract change; `dashboardGoldens.ts` untouched. Frontend +3 (region landmark, named subsections, no-Synthetic/withheld regression); `ExposurePanel` now audited. tsc + dead-code gate clean. **Epic 30 closed.** |
| 2026-07-15 | US-30.5c | **Fixed F-10 with a scoping correction: the portfolio-return basis is now provenance-selected, cash excluded on synthetic surfaces.** The audit's owner decision ("exclude cash") taken literally — market-value chain everywhere — is **unsafe**: on the imported ledger-replay path (146 BUY/SELL entries in the IB2026 window) a plain `MV_t/MV_{t−1}` reads a BUY as a gain, the F-1 fabrication class (reproduced: **+37.23% on the 2026-06-19 trade day**). Resolved by the same provenance rule §Indexed Return Series uses for drift: a new `ReturnBasis` (`"portfolio_value" | "market_value"`) parameter, defaulting to the cash-flow-neutral TWR, is set from `provenance.historical_basis` — **synthetic** paths (`market_data_history`, plus the always-synthetic attribution / multi-benchmark-correlation / stress engines) use the cash-excluded market-value chain `MV_t/MV_{t−1}−1`; the **imported ledger-replay** path keeps the trade-safe TWR. This removed a prior *internal* split — VaR (`distribution_engine`) and drawdown (`drawdown_engine`) already derived their synthetic returns from `total_market_value`, while correlation/beta/attribution/factor/stress read the cash-inclusive TWR; they now agree. Threaded through `build_portfolio_risk_summary` / `build_rolling_risk_series` / `build_relative_risk_summary` / `build_statistical_factor_model` / `build_volatility_regime_payload` (risk.py) + `build_factor_attribution` (attribution.py), all safe-by-default (opt-in `"market_value"` is greppable — the F-4 lesson). **`dashboardGoldens.ts` byte-identical** (generated from the imported/ledger path, which is unchanged — AC8). Methodology §Rolling Pearson Correlation rewritten to the provenance-selected basis + cross-ref §Indexed Return Series (resolving the doc-vs-doc contradiction US-30.4 flagged). Ledger-path cash de-dilution (needs a per-day trade-flow field on `DailyPortfolioState`) deferred → tech-debt **US-24.9**. 565 backend (+7) green; tsc + dead-code gate clean. |
| 2026-07-08 | US-30.5b | **Fixed F-9: per-position risk statistics gate on the 20-observation floor.** A published per-position beta, correlation, or annualised volatility now requires ≥ `MIN_DAILY_OBSERVATIONS` (20) overlapping daily returns (methodology §Beta: "len < 20 → null"); below the floor it is **null**, never a confident number from a handful of days, while weight/market-value/risk-share still render. `risk.py` now imports `MIN_DAILY_OBSERVATIONS` from `core/constants.py` (the "never imported by risk.py" gap the audit noted). **Finding wording corrected** (F-3 precedent): the function the audit named — `build_position_risk_contributions` — is orphaned (one test caller, on no response schema), so the gate also covers the *live* surface with the same defect, `_build_position_risk_contributions`'s per-position `volatility` (fed the Risk Summary card at len≥2). The covariance-matrix cells keep their pairwise ≥2 floor deliberately (US-27.3 intermediate inputs; reliability disclosed via `observation_count`). **Behaviour-neutral for the committed portfolio** — every IB2026 position clears the 60-day window's 20-obs floor, so `dashboardGoldens.ts` is **byte-identical** (the gate only nulls genuinely under-powered positions). Methodology gains §Risk Contribution and Concentration → "Per-position minimum-observation rule". 551 backend (+3) + frontend unchanged green; tsc + dead-code gate clean. F-10 → US-30.5c. |
| 2026-07-08 | US-30.5a | **Fixed F-7 (Critical) + F-8: every Exposure weight now sums in the base currency, and the tab says so.** New `analytics/currency.py` (`convert_to_base` / `position_base_market_values` / `total_base_market_value` / `snapshot_fx_disclosure`) converts each position with the statement's own implied rates before it enters ANY denominator. All seven weight sites converted: `overview.py` (totals, top positions, sector allocation + breakdown, cost basis, unrealized P/L), `exposure_engine.py` (portfolio total, concentration/HHI), `risk.py` (position risk contributions, look-through effective value + sector exposure, risk-share weights), `intra_correlation_engine.py` (DR/ENB weights). **The arbiter test**: converted total = **$61,238.53** = the statement's own `stock_total` to the cent (raw mixed sum was $58,588.76). Weights corrected — SEMI 4.61%→5.85%, SXRV 12.93%→14.13%, VDST 20.19%→19.31%, VUAA 19.73%→18.87%; position HHI 0.11536→0.11272. F-8: `ExposureResult` gains `fx_static_rate_currencies` + `fx_fallback_currencies` (exactly one tier per non-base currency, base in neither) and the Exposure tab renders both helper notes; a currency with no rate is **carried unconverted, never dropped and never 1:1** (US-27.8 precedent). Plumbing: `fx_rates` moved up from `DriftEngineRequest` to the shared `PortfolioEngineRequest` (drift unchanged), the request-path snapshot builder materialises `statement_totals` **only when rates are supplied** (so `statement_totals=None` and byte-identical behaviour without them — US-30.1's cash anchor and terminal reconciliation both guard on other fields, verified), and `buildSnapshotAnalysisRequest` now sends `fx_rates` for every engine. **`dashboardGoldens.ts` regenerated deliberately** — diff is exactly 71 lines across `weight` / `market_value` / `unrealized_pnl` / `total_market_value` / `total_cost_basis` / `total_unrealized_pnl`; **zero** return-series, correlation, beta, or statement-identity fields changed (verified per-family). Methodology gains §Risk Contribution and Concentration → "Base-currency weighting rule"; `exposure-fields.md` gains the matching contract rule. 548 backend (+12) + 282 frontend (+5) green; `npx tsc --noEmit` clean; dead-code gate clean. F-9 → US-30.5b, F-10 → US-30.5c (owner decided: exclude cash). |
| 2026-07-08 | US-30.4 | **Findings-first audit of the rest of the Exposure tab (Epic 30) — four new findings, no fixes.** Audit-only story (zero code touched; goldens byte-identical). **F-7 (Critical): every Exposure weight denominator raw-sums market values across currencies** — `sum(position.market_value)` mixes EUR/GBP/USD with no FX conversion anywhere in the exposure path. Reproduced on IB2026.csv: raw $58,588.76 vs FX-converted $61,238.53, and the converted figure reproduces the statement's own stock total to the cent — so the statement is the arbiter, not a modelling preference (4.33% understatement). SEMI +1.24pp, SXRV +1.20pp, VDST −0.87pp, VUAA −0.85pp; position HHI off −2.29%. Hits overview totals, exposure engine, concentration/HHI, position risk contributions, look-through sector exposure, market overlap, and the intra-correlation DR/ENB weights. **F-8 (High): no Exposure card discloses that degradation** — the drift panel got the three-tier disclosure in US-30.2, the rest render a confident `Synthetic` badge over currency-mixed weights (the F-2 lesson repeating). **F-9 (Medium): per-position beta/correlation published from as few as 2 overlapping observations** — `build_position_risk_contributions` never gates on `MIN_DAILY_OBSERVATIONS`, contradicting methodology §Beta's "len < 20 → null"; `risk.py` never imports the constant (the *rolling* series is correctly gated). **F-10 (Medium): two incompatible portfolio-return bases** — drift uses the market-value chain (US-30.1), rolling corr/beta + attribution + multi-benchmark use the TWR chain on `total_portfolio_value` (market value **+ cash**); cash dilutes the series (scale 0.9805 → beta understated ~1.95%; correlation is scale-invariant). Also a doc-vs-doc contradiction: §Indexed Return Series vs §Rolling Pearson Correlation now specify different bases. Recorded an **"examined and found correct"** list too (correlation.py min-obs gates, rolling-window gating, zero-variance guards, Factor Drift Summary, look-through math) so a future reader knows the audit covered them. US-30.5 scope pinned to F-7..F-10 in the PRD. Full suite green; `dashboardGoldens.ts` byte-identical (proof the audit changed no behaviour). |
| 2026-07-08 | US-30.3 | **Exposure-tab first-render reliability (Epic 30 F-4/F-5) — the blank-chart-until-dropdown bug is fixed by construction.** F-4: `DriftBenchmarkPanel` converted to the project's self-fetching pattern (`FactorAttributionCard`/`BenchmarkCorrelationTable`) — takes a `snapshot` prop, owns `useEffect([snapshot, benchmark])` with `idle`/`loading`/`error`/`done` + a cancellation flag; fed App's reactive `dashboardSnapshot` (the workspace `PortfolioSnapshot` carrying US-30.2 `fxRates`), so `runDriftEngine(PortfolioSnapshot, benchmark)` and every US-30.2 fx test are untouched. Root cause was `analyzeRestoredSnapshot` never calling `runDriftEngine` (one of three parallel analyze paths); self-fetch makes the omission structurally impossible and net-removes App state (`driftResult`/`driftError`/`driftBenchmark`/`handleDriftBenchmarkChange`/`driftPromise`/`lastAnalyzedSnapshotRef`). F-5: the "Since Import" window now anchors at the statement-period START (`_since_import_anchor`, fallback `imported_at`, then fail-closed) instead of the import timestamp (≈ today, which left it perpetually `unavailable`). Panel now surfaces loading + backend-error states itself (no silent "No drift data"). Backend +3 (anchor unit trio + e2e availability), frontend drift-panel test rewritten for self-fetch (+5 net: mount-fetch, dropdown re-fetch, loading, error-detail, stale-result discard). Methodology §Indexed Return Series + `correlation-fields.md` + `current-product-state.md` note the anchor + self-fetch. 536 backend (+3) + 277 frontend (+6) green; `npx tsc --noEmit` clean; goldens untouched. |
| 2026-07-08 | US-30.2 | **Drift coverage + FX disclosure (Epic 30 F-3/F-6) — every degraded input is now visible.** Three-tier FX disclosure on `DriftResult`: `fx_static_rate_currencies` (converted at the statement's implied period-end rate — US-28.1 `statement_totals.fx_rates`, broker truth, applied static across the window), `fx_fallback_currencies` (carried unconverted, US-27.8), `statement_anchored_symbols` (held symbols with zero in-window price history, valued flat at the statement close — the F-3 wording correction: they were flat-anchored, not omitted). A currency lands in exactly one FX tier. `DriftEngineRequest.fx_rates` added (schema-first + TS mirror + contract rows); `PortfolioStateEngine` records `statement_anchored_symbols`; `run_drift_engine` builds a static per-date `fx_history` from the request rates and splits the tiers. Statement-implied rates flow end-to-end: imported `statement_totals.fx_rates` → new optional `PortfolioSnapshot.fxRates` (backward-compatible with persisted v1 snapshots) → `runDriftEngine` request → engine. Panel gains two helper notes (static-rate + anchored), ui-polish-clean (no hand-rolled badge labels). A static rate scales single-currency levels but not that currency's own returns — pinned, and disclosed as static rather than passed off as fully converted (guardrail #3). Methodology §FX Conversion Fallback Disclosure gains the static-rate + anchored tiers; PRD F-3 wording corrected. 534 backend (+8) + 271 frontend (+6) green; `npx tsc --noEmit` clean; goldens untouched (AC6 byte-identical when `fx_rates` absent). |
| 2026-07-08 | US-30.1 | **Fixed the drift valuation basis (Epic 30 F-1/F-2) — the −6226% is gone.** The drift engine now chooses its basis by what the snapshot carries: with ledger entries, the US-27.8 cash-flow-neutral TWR chain (deposit-neutrality pins unchanged); without (the request path — today's only caller), the market-value chain of current holdings — the synthetic convention its badge already claimed. One shared `_compound_chain` feeds both the window cards and the indexed chart, so they can never disagree (pinned on both bases). Fail-closed rule: a ≤ −100% daily return (impossible long-only) withholds the window (`trust="unavailable"`, degradation note, null spread) and the chart's whole portfolio line — never clamped, never compounded. `PortfolioStateEngine` cash anchor: with no `starting_nav`, `base_cash` now sums the snapshot's real `cash_balances` (was `0 − opening_value` ≈ −$62.6k, the F-1 root cause); totals-present path byte-identical. Basis notes truthful per path end-to-end (backend `_basis_note` + panel tooltip repeats the engine note; hardcoded "broker-ledger replay" claim removed — a design-system audit catch forced the tooltip fallback to not hand-roll the badge label). Live reproduction rerun: 1M +0.01 / 3M +5.32 / 6M +2.51 / 12M +11.34 vs SPY (statement's own Jan–Jun TWR +1.25%), chart final index 111.34 ≡ 12M card. Methodology §Indexed Return Series rewritten (per-path basis + fail-closed + cash-anchor rules); correlation-fields drift rows updated. 526 backend (+9) + 265 frontend (+1) green; goldens untouched. |
| 2026-07-07 | US-28.3 | **Statement-refresh resilience: truths centralized, swap failure-surface pinned. Epic 28 fully closed.** New `app/tests/statement_truths.py` — the single source for every IB2026.csv statement-truth pin (identity, position/instrument/ledger counts, pinned rows, totals, implied FX, sector examples, absent symbols), each named with the statement period; `diff_statement_truths(snapshot)` compares a snapshot against all pins, every mismatch line naming the workflow doc. `test_statement_matches_truths_module` is the one test that fails on a refresh. Audit + conversion: UCITS sector/sold-symbol pins, exposure account + top-overweights, route account pins, and the period pin now reference the truths module; the variant-diagnostics perturbation switched from the sold symbol DFND (a silent no-op since 2026-06) to the largest position (true invariant); `test_importer.py`'s IB2026.pdf pins classified frozen-legacy-fixture scope (never refreshed) and left inline by design. New `test_statement_refresh.py` swap-simulation meta-test: a mutated fixture (AMZN qty 10→12 + brand-new NEWX position/instrument) surfaces diffs ONLY for the touched pin families, zero diffs for untouched ones, every line self-documenting, registry-coverage step asserted. Workflow documented in `refresh_statement.py` + new `testing-architecture.md` "Statement refresh workflow" section (replace CSV → refresh script → truths module → registry → commit set). Behaviour-neutral: goldens byte-identical. 517 backend (+3) + 264 frontend tests green; tsc + dead-code gate clean. |
| 2026-07-07 | US-28.2 | **CSV wired end-to-end; golden pipeline keys off `docs/IB2026.csv`.** Backend: `statement_importer.import_statement` routes `.csv` → IBKR CSV importer (preview → import; non-IBKR CSV rejected with the preview's ValueError; unsupported suffix message now "Only PDF or CSV..."); PDF chain untouched. Desktop: file input accepts `text/csv`, Tauri picker filter "Broker Statements" (pdf+csv), per-extension MIME on upload, PDF-specific copy made format-neutral. Golden pipeline: `export_dashboard_goldens` prefers `IB2026.csv` (PDF names remain fallbacks) — goldens regenerated **deterministically from the existing frozen fixture, no live FMP re-capture needed** (the committed PDF had already been refreshed to the same Jan–Jun window and identical position set). Goldens diff per-family: statement identity (`source_path`/`detected_format: "csv"`/normalized ISO period/`page_count: null`), ledger amounts at CSV precision (penny-level rounding vs PDF text), +1 recovered SELL (GOOG 2026-04-13) the PDF regex path silently dropped, downstream portfolio-value/return recomputation. Statement-truth pin catalogue for US-28.3: exactly ONE backend pin broke (`test_analytics` period-format assertion `January 1, 2026 -` → `2026-01-01 -`) + 4 frontend copy pins (deliberate copy change); everything else self-healed through the goldens. IB2026-consuming tests moved to `STATEMENT_2026_CSV_PATH` (analytics/exposure/routes/registry-ISIN). `refresh_statement.py` docs cover CSV; `--check` passes. `importers/README.md` + `dashboard-fields.md` provenance rows updated. 514 backend (+4) + 264 frontend (+2) tests green; `npx tsc --noEmit` clean. |
| 2026-07-07 | US-28.1 | **IBKR Activity-Statement CSV importer (backend).** New `app/importers/interactive_brokers_csv.py`: parses `docs/IB2026.csv` (utf-8-sig BOM, stdlib `csv`, per-section column headers with mid-file `Trades` Header-restatement support, quoted thousands, `--` missing-cell sentinel) into the unchanged `ImportedPortfolioSnapshot` contract — statement identity (U8516450 / USD / normalized `2026-01-01 - 2026-06-30` / `detected_format="csv"`), Change-in-NAV totals + TWR, 20 per-currency positions (16 USD / 3 EUR / 1 GBP), 180 ledger entries (BUY/SELL/DIVIDEND/WITHHOLDING_TAX/INTEREST/FEE/DEPOSIT), per-currency cash balances, 65 instruments with ISIN from `Security ID`. Fail-safe per record (US-24.4/24.8 discipline; 4 mutation regressions). Reconciliation: `_statement_stock_total_in_base` generalized to per-currency `fx_rates` conversion (PDF behavior preserved; CSV supplies **implied rates from the statement's own Open Positions totals** — EUR/GBP now reconcile exactly), and the erroneous "Credit Interest" withholding exclusion removed (IBKR's own totals include it, verified 2023–2026; 2024/2025 PDF statements now fully reconcile, regression-pinned on CSV + 2025 PDF). CSV snapshot's reconciliation summary passes end-to-end. Methodology: Importer resilience rule + reconciliation rule extended. 510 backend (+21) + 262 frontend tests green; `npx tsc --noEmit` clean; goldens untouched (no dashboard surface). Wiring into route/UI/goldens is US-28.2. |
| 2026-07-04 | US-29.1 | **Fixed charts rendering blank after import until a page reload.** User-reported bug, reproduced live in a browser (simulated a real PDF import against a running backend). Root cause: Recharts' `ResponsiveContainer` measures its container synchronously on mount; racing a same-commit DOM insertion of several other new cards (exactly what happens when import resolves and multiple cards flip from `EmptyState` to populated together) can yield a degenerate `-1,-1` measurement, and `ResizeObserver` only fires on a subsequent size *change* — never to self-correct a bad first read — so the chart can stay blank until something else (a reload) forces a fresh measurement. **First fix attempt (deferring the chart mount by one `requestAnimationFrame` tick) was verified insufficient** by re-reproducing live: `requestAnimationFrame` is paused while `document.hidden` is `true`, which is exactly the state during/after Tauri's native file-picker dialog (used for import) blurs the webview. Corrected to `setTimeout(fn, 0)` (fires regardless of visibility, since layout is computed independent of paint) and re-verified: Dashboard's Performance & Benchmark chart and Exposure's Rolling Correlation / Factor Return Attribution charts all rendered with real, populated SVG paths on the first render after import, confirmed via direct DOM/SVG inspection with `document.hidden` still `true`. Fix confined entirely to the shared `ChartShell.tsx` primitive — no per-chart-file changes. +2 `ChartShell.test.tsx` tests; full `run_all_tests.py` green; tsc clean; goldens untouched (frontend-only). *(Renumbered from "Epic 27/US-27.1" on 2026-07-07 — authored in a parallel session, collided with Epic 27 — Financial Calculation Correctness; merged unchanged.)* |

---

## Completed Epic: Epic 28 — IBKR CSV Importer & Statement-Refresh Resilience

**PRD:** [`docs/product/prd/epic-28-ibkr-csv-importer.md`](product/prd/epic-28-ibkr-csv-importer.md)

Created 2026-07-05 from the owner's actual workflow: the IB statement file is
replaced with a fresh broker export every few weeks, so exact-number pins
break on every refresh — and the fragile PDF regex parsing (hardened twice in
Epic 24) re-parses a *layout* when IBKR ships the same statement as a
machine-readable CSV. `docs/IB2026.csv` (Activity Statement, 2026-01-01 →
2026-06-30, 22 sections, utf-8-sig) is committed as the real statement to
build against. Three stories: **US-28.1** a fail-safe
`interactive_brokers_csv.py` importer producing the unchanged snapshot
contract (per-currency Open Positions, ISIN from Financial Instrument
Information, reconciles against its own Change-in-NAV totals); **US-28.2**
remove the three `.pdf` gates (statement_importer suffix check, App.tsx
picker filter + accept attr), key the golden pipeline off the CSV, one
deliberate `refresh_statement.py` regeneration (window moves Jan–Apr →
Jan–Jun; needs FMP key + registry entries for new symbols), legacy 2022–2025
PDFs keep working; **US-28.3** classify statement-truth vs structural
assertions, centralize the truths into one module per side, prove via a
swap-simulation meta-test that a statement refresh fails only the documented
pin set, and document the one-command workflow.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-28.1 | IBKR Activity-Statement CSV importer (backend) | Done |
| US-28.2 | Wire CSV end-to-end: detection, upload UI, golden pipeline on IB2026.csv | Done |
| US-28.3 | Statement-refresh resilience: centralize statement-truth pins + document the workflow | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-07-05 | — | Epic created ("switch the IB parser from PDF to the CSV export; fix whatever a periodic statement refresh breaks"). Verified against the real `docs/IB2026.csv`: IBKR's `Section,Header|Data` framing with per-section column headers covers everything the PDF regexes reconstruct, at full precision, plus data the PDF path lacks (per-currency EUR/GBP/USD Open Positions, `Security ID` ISINs, Conids). Confirmed the three `.pdf` gates (`statement_importer.import_statement`, App.tsx selection filter, `<input accept>`), the golden pipeline's `IB2026.pdf` keying (`export_dashboard_goldens.py`, `_statement_fixtures.py`), and that the upload route is already suffix-agnostic. Noted the statement-window move (PDF Jan–Apr vs CSV Jan–Jun) makes the US-28.2 golden regeneration the epic's main scheduled cost. PRD + 3 stories authored; `docs/IB2026.csv` committed; no code changed. |

---

## Completed Epic: Epic 27 — Financial Calculation Correctness

**PRD:** [`docs/product/prd/epic-27-financial-calculation-correctness.md`](product/prd/epic-27-financial-calculation-correctness.md)

Created 2026-07-05 from a full financial-calculations audit of the analytics +
engine layer against `financial-methodology.md` (findings recorded first, no
fixes applied during the audit — the PRD's F1–F13 table is the canonical
record). **13 findings**: 4 confirmed math bugs shown to the researcher today
(Information Ratio under-stated ~√252×; dashboard monthly returns drop every
month-boundary day; dashboard max drawdown measured on raw
cash-flow-contaminated value; covariance cells can pair returns from different
dates), 6 guardrail violations (stress projections zero-fill missing loadings;
factor risk-share denominator diverges from the doc; collinear factors kept
raw instead of nulled; synthetic history flat back-fills before a symbol's
first quote; missing FX rates silently convert 1:1; drift-window returns
aren't cash-flow-neutral), and 3 low-severity consistency gaps. 9 stories
authored (US-27.1–27.9); recommended order 27.1 → 27.2 → 27.3 (small,
wrong-number-today fixes) before the behaviour-aware valuation changes
(27.7/27.8) that will shift goldens.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-27.1 | Fix the Information Ratio annualization | Done |
| US-27.2 | Fix dashboard monthly-return chaining + max-drawdown basis | Done |
| US-27.3 | Fix covariance-matrix date alignment | Done |
| US-27.4 | Stress scenarios: null semantics for missing loadings | Done |
| US-27.5 | Reconcile the factor risk-share denominator | Done |
| US-27.6 | Null collinear factors in per-window orthogonalization | Done |
| US-27.7 | Stop flat back-filling synthetic history before first quote | Done |
| US-27.8 | Surface FX-fallback trust + fix drift-window return basis | Done |
| US-27.9 | Low-severity tail (fabricated 0.0 points, stdev conventions, DR/return basis) | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-07-05 | US-27.9 | **Low-severity tail (audit F11–F13) — closes Epic 27.** F11: `build_true_performance_series` no longer fabricates plausible-looking `0.0` cumulative-return points — an unverified return basis suppresses the series with explicit nulls, and a mid-series zero-prior-value day is a null point with the chain resuming (only the verified series' first point is a genuine 0.0 anchor); the two existing "refuses" tests flipped from pinning the fabricated 0.0 to pinning None, +2 new tests (verified anchor; −100% collapse day then null). `dashboardGoldens.ts` regenerated deliberately: the diff is EXACTLY 197 × `portfolio_return_pct: 0.0 → null`, nothing else. F12: stdev denominator conventions DOCUMENTED (decision: not standardized — ratios invariant, each module internally consistent, standardizing would churn every golden for sub-percent display differences): `risk.py` sample (N−1) vs `correlation.py`/`distribution.py` population (N); new methodology subsection. F13a: the Diversification Ratio's σᵢ now computed over the same COMPLETE-CASE date set as σ_p (hand-built regression: ragged coverage gave DR ≈ 0.916 < 1 pre-fix, exactly 1.0 now). F13b: `row["price"]` basis verified empirically against the frozen capture of real provider data — Yahoo rows have `price = adjClose` exactly (max diff 0.0 across 9 symbols); FMP light standard-path rows carry no `adjClose` (basis adjusted-indicated via the US-21.4 re-adjustment churn but unverifiable from row shape → correctly classified `unverified_close_only`); recorded in §Market Data Basis with a call-site rule. All 13 PRD findings now Resolved/Documented. 489 backend + 260 frontend + dead-code gate green; tsc clean. |
| 2026-07-05 | US-27.8 | **Surfaced FX-fallback trust + fixed the drift-window return basis (audit F9 + F10).** F9: `PortfolioStateEngine.to_base_currency` silently returned the raw value when no FX rate was available (EUR treated as USD), and every caller passes `fx_history={}` — the engine now RECORDS the currencies that required conversion with no rate (`fx_fallback_currencies`, exposed via the new `build_daily_portfolio_states_with_fx_disclosure`), values stay carried-unconverted (the only honest number held), and the disclosure flows to `DriftResult.fx_fallback_currencies` (rendered as a drift-panel helper note) + `DashboardHistoryRunMetadata.fx_fallback_currencies`. AC5 decision recorded: explicit permanent degradation over wiring real FX — `get_fx_history` has zero callers and unverified FMP symbol resolution; wiring it is Epic 26 scope. F10: drift `_portfolio_return` was `last/first` on raw market value (a deposit read as return — latent on today's request path, which carries no ledger, but contract-wrong); now the compounded cash-flow-neutral TWR chain, and `daily_series` is TWR-indexed (AC4 decision — a deposit no longer draws a fake move against the benchmark price line); the basis note + TrustBadge tooltip corrected from the false "current holdings applied to historical prices" claim to "Broker-ledger replay: compounded time-weighted return (cash-flow-neutral)". +6 pytest (deposit-fixture 0.0 vs pre-fix +100%, exact no-flow pin 6.09, TWR-indexed chart, basis note, EUR disclosure e2e + unit conversion/recording) + 2 vitest (drift panel FX note / no-note) in a new `DriftBenchmarkPanel.test.tsx`. Methodology: §Indexed Return Series rewritten (TWR portfolio line + drift window basis) + new §FX Conversion Fallback Disclosure; `correlation-fields.md` drift rows + `dashboard-fields.md` run-metadata inventory updated. Goldens untouched (run_metadata is not golden-serialized — verified). 486 backend + 260 frontend + dead-code gate green; tsc clean. |
| 2026-07-05 | US-27.7 | **Stopped flat back-filling synthetic history before a symbol's first quote (audit F8).** Both daily-state builders fabricated prices: the synthetic builder back-filled each symbol's first quote flat across leading dates AND flat-filled the statement close for symbols with no fetched history at all; the broker replay back-filled the first fetched quote. Fabricated zero returns understated vol/VaR/drawdown and distorted correlations. **Option B implemented** (per the story's recommendation): the effective window starts at the latest first-quote across MATERIAL holdings (new shared `SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT = 0.01` policy constant in `core/constants.py`); zero-coverage holdings and sub-de-minimis late-listers are EXCLUDED (never mid-window entries); interior gaps keep the carry-to-next-quote convention (documented); the broker path may seed carry from a real pre-window quote and keeps the statement-close anchor ONLY for zero-history symbols (broker-truth-adjacent, e.g. unpriceable UCITS). New `SyntheticHistoryCoverage` disclosure (`requested/effective_start_date`, `limiting_symbol`, `excluded_symbols`) emitted by the stress/drawdown/distribution/multi-correlation/attribution engines and rendered as a helper note in all five cards (TS mirrored). Floors apply to the EFFECTIVE window — truncation below `MIN_DAILY_OBSERVATIONS` → unavailable WITH coverage attached. +11 pytest (`test_synthetic_history_coverage.py`: truncation/limiting-symbol, de-minimis exclusion, zero-coverage exclusion, interior-gap carry, hand-verifiable vol-understatement regression, broker truncation/pre-window seed/statement anchor, engine passthrough, below-floor fail-closed) + 5 vitest (coverageNote unit + stress-card rendering). Methodology gained §Synthetic History Coverage Rule; risk/correlation/attribution contract docs updated. **Goldens verified as a no-op** — every committed-statement symbol has full frozen coverage, so the regeneration step changed nothing (`dashboardGoldens.ts` untouched). 481 backend + 258 frontend + dead-code gate green; tsc clean. |
| 2026-07-05 | US-27.6 | **Nulled exactly-collinear factors in per-window orthogonalization (audit F7).** `_orthogonalize_factors_window` re-inserted the RAW series when a factor's Gram-Schmidt residual was ~0, letting the ridge split the loading arbitrarily between the collinear pair and residualizing later factors against the raw (not orthogonalized) series — the methodology edge case says skip-with-null. The factor is now DROPPED from the window design matrix (loading None for that date) and reported via `dropped_factor_labels`; later factors orthogonalize against survivors only. **Root-cause bonus:** the drop branch was effectively dead because the *projection* solve used ridge λ=1e-5, leaving an exact duplicate with a ~λ/S residual (≈2.7e-4) that never hit the 1e-12 floor — the projection now uses λ=0, exactly matching the doc's Gram-Schmidt step (ridge stays in the final OLS only); the 1e-12 floor became the named `ORTHOGONALIZATION_ZERO_RESIDUAL_THRESHOLD`. `attribution.py` skips dates with dropped factors per its documented edge case. +4 tests (duplicate → None + Market carries the full 2.0 loading vs the pre-fix ~1/1 split; later-factor orthogonalization vs survivors; orthogonalizer unit test; attribution full-duplication → unavailable). Two degenerate test fixtures that fed IDENTICAL rows to every factor proxy were fixed with distinct sine dynamics (they were exercising exactly the bug this story fixes). 470 backend + 253 frontend + dead-code gate green; tsc clean; goldens untouched. |
| 2026-07-05 | US-27.5 | **Reconciled the factor risk-share denominator with the methodology (audit F6).** `build_risk_contribution_breakdown` computed the doc's `variance_contribution / factor_total_variance` shares inside `_build_factor_risk_contributions`, then **overwrote** every factor `risk_share` with `/ total_variance_raw` (factor + specific) — factor shares summed to `factor_risk_share_total` (< 1) and `factor_hhi`/top-N were built over the rescaled values, contradicting §Risk share. Kept the DOCUMENTED convention (denominator matches the decomposition; non-null factor shares sum to 1; the share-of-total view stays exposed via `factor_risk_share_total` + `specific_risk_share`, which partition total variance) and removed the compute-then-overwrite. Updated the existing breakdown consistency test to the doc convention (Σ shares ≈ 1, share-of-total partition, HHI-over-consistent-shares) and added a hand-computed two-factor pin (`_build_factor_risk_contributions` with SPY/QQQ fixture: shares 0.5676 + 0.4324 = 1.0 exactly; pre-fix code divided by total_variance_raw). Methodology §Risk share gained the denominator-convention block; `diagnostics-fields.md` concentration section documents the two non-cross-comparable share families. No golden pins these values — goldens untouched. 466 backend + 253 frontend + dead-code gate green; tsc clean. |
| 2026-07-05 | US-27.4 | **Stress scenarios: null semantics for missing loadings (audit F5).** `build_stress_scenarios` zero-filled any shocked factor whose latest loading was unavailable (`(loading or 0.0) × shock`) — a 9-of-12-loadings projection rendered identically to a complete one. Decision: **Option B (partial)** — strict per-scenario nulling would blank the card exactly when history is thin and it's most needed. Each scenario now sums the AVAILABLE loadings only and carries `status="partial"` + `missing_factors=[labels]` (schema + TS mirror); all-shocked-loadings-missing → `status="unavailable"`, null estimate; `is None` checks so a genuine 0.0 loading is a real value, never listed as missing. `StressScenariosCard` renders a "Partial estimate — computed without X, Y (loading unavailable)" helper note per partial row (text, not color-only). The US-24.2 stress pin test passes **unedited** (its single-Market fixture now reports `partial`, same numbers). +3 pytest (partial hand-computed −16.0, genuine-zero → ok, all-missing → unavailable) + 1 vitest (partial note, exactly one). Methodology §Stress Scenarios gained the missing-loading rule; `risk-fields.md` rows + trust table updated. 465 backend + 253 frontend + dead-code gate green; tsc clean; goldens untouched. |
| 2026-07-05 | US-27.3 | **Fixed covariance-matrix date alignment (audit F4).** `_compute_covariance_matrix` in `risk.py` filtered each symbol's return list to its own coverage independently — two symbols missing *different* dates but the same count were zipped misaligned, silently pairing returns from different calendar days (downstream: factor/position variance contributions, risk shares, top-N concentration, both HHIs). Every cell now uses the pair's intersected date set (window ∩ left ∩ right), the same pairwise-drop discipline as `analytics/correlation.py`; < 2 common observations → None. +3 hand-computed tests: the misalignment regression (intersection gives +0.0002 where the pre-fix zip produced −0.0006 — a sign flip), a full-coverage behaviour-neutral pin (diagonal = sample variance), and the below-floor → None case. Methodology §Risk share gained the date-alignment convention sentence. Behaviour-neutral for full-coverage inputs — `dashboardGoldens.ts` untouched. 462 backend + 252 frontend + dead-code gate green; tsc clean. |
| 2026-07-05 | US-27.2 | **Fixed dashboard monthly-return chaining + max-drawdown basis (audit F3 + F2).** `_compute_contribution_adjusted_monthly_returns` now buckets each cash-flow-neutral daily return into its **end date's** month with the baseline carried across month boundaries — the old per-month grouping reset the baseline each month, dropping every month-boundary return so Π(1+mᵢ) ≠ period TWR (FF2026 proof: old months compounded to −24.8% vs the actual −23.86%; corrected months chain exactly). A month with no computable return now emits no entry (never a fabricated 0.0%). `_compute_max_drawdown` now builds the compounded return index (reusing `_build_wealth_index`/`_build_drawdown_from_return_index` from `risk.py`, anchored at 100 on the range's first state date) instead of walking raw `portfolio_value` — a same-day deposit no longer masks a real drawdown (fixture: −10% was reported as 0.0) and a withdrawal no longer fabricates one (fixture: 0.0 was reported as −50%). Withholding gates untouched. +6 pytest (chaining property, boundary regression, boundary-flow neutrality, deposit-mask, withdrawal-fabricate, first-day-decline parity); FF2026 golden constant + its test-local mirror re-pinned to the corrected convention with a chaining sanity note; `dashboardGoldens.ts` regenerated deliberately (diff reviewed field-by-field — only monthly_returns/returnPct shifted; the ib2026 1M-range May +75.99% verified to chain exactly to that range's own +19.21% summary, a sparse-series/synthetic-anchor artifact documented in the new methodology edge case). Methodology gained §Monthly Returns + §Dashboard range max drawdown; `dashboard-fields.md` monthly-cells row updated. 459 backend + 252 frontend + dead-code gate green; tsc clean. |
| 2026-07-05 | US-27.1 | **Fixed the Information Ratio annualization (audit finding F1).** `build_relative_risk_summary` in `risk.py` computed `mean_active × √252 / TE_annualized` — algebraically the *daily* IR, under-stating the displayed value by √252 ≈ 15.87×. Now `mean_active × VOLATILITY_ANNUALIZATION_DAYS (252) / tracking_error`, exactly the methodology §Information Ratio form (daily IR × √252). Edge cases (no pairs / TE=0 → null) unchanged and still covered by the four pre-existing null-path assertions. Added `test_build_relative_risk_summary_information_ratio_is_annualized_exact_value` — a hand-derived fixture (expected 18.71) that the pre-fix code fails at 1.18, closing the null/not-null test gap the audit flagged. Verified no golden or fixture embeds an IR value (`dashboardGoldens.ts` untouched); contract docs (`diagnostics-fields.md`/`dashboard-fields.md`/`exposure-fields.md`) defer the formula to the methodology section — no edit needed; methodology doc already correct, unchanged. 453 backend + 252 frontend + dead-code gate green; tsc clean. |
| 2026-07-05 | — | Epic created from a "check all financial calculations" audit. Every formula in `app/analytics/*` + the engine services + `dashboard_history_engine.py` + `engine/portfolio_state.py` was read against `financial-methodology.md`. Also recorded what was **checked and found correct** (Modified Dietz, VaR/CVaR + invariant, percentiles/moments/histogram, wealth index/underwater/episodes + decomposition reconciliation, attribution identity + NaN guards, correlation-matrix null semantics, ENB, active share, exposure HHIs, tracking error, β/ρ/R²) so future audits don't re-litigate. Notable pattern: none of the 13 findings were test-caught because the suite asserts null/not-null rather than numeric values at exactly these spots — every Epic 27 story therefore requires exact-value or property pins. PRD + 9 stories authored; no code changed. |

---

## Backlog Epic: Epic 26 — Currency Exposure & Risk

**PRD:** [`docs/product/prd/epic-26-currency-exposure-and-risk.md`](product/prd/epic-26-currency-exposure-and-risk.md)

Research brief only — not yet ticketed. A project-wide review found the
project has no view of portfolio currency exposure despite already importing
`ImportedPosition.currency`/`ImportedStatement.base_currency` on every
statement. `financial-methodology.md` gained a §Currency Exposure section
(snapshot weight-by-currency formula, ready to implement) and a
§Currency Risk Contribution subsection (historical FX-return decomposition,
explicitly documented as **not** ready — the interaction-term and portfolio-
variance-decomposition questions are open, and
`MarketDataService.get_fx_history` — which exists but has zero callers today
— needs empirical verification before any engine work begins). Run
`write-story` against the PRD's US-26.1 when this epic is picked up.
*Validity re-check 2026-07-08: premise verified current and strengthened —
US-28.1's statement-implied FX rates give US-26.1 a broker-truth conversion
basis with zero market-data calls; see the PRD header note.*

---

## Completed Epic: Epic 25 — Dashboard Performance & Risk Summary

**PRD:** [`docs/product/prd/epic-25-dashboard-performance-risk-summary.md`](product/prd/epic-25-dashboard-performance-risk-summary.md)

### Goal

Restore the Dashboard tab's performance/risk surface that `dashboard-fields.md`
and `current-product-state.md` describe but `DashboardPanel.tsx` no longer
renders (removed piecemeal across several undocumented refactors, per git
history — `bc4ff4d`/`195dc70`/`e0254d6`/`df5d478`). The backend
(`DashboardHistoryResult`, `DiagnosticsResult`) already computes every field
needed: no schema/engine change, frontend-only restoration + a docs
reconciliation pass.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-25.1 | Performance & benchmark comparison card | Done |
| US-25.2 | Monthly returns grid card | Done |
| US-25.3 | Risk metrics card (volatility, drawdown, concentration) | Done |
| US-25.4 | Docs close-out | Done |
| US-25.5 | Information Ratio on the Risk Summary card | Done |

Recommended build order: 25.1 → 25.2 → 25.3 → 25.4 (docs last). US-25.5 was
added afterward from a separate quant-research pass and picked up as an
Epic 25 addendum since it extends the same US-25.3 card.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-07-04 | US-25.5 | **Information Ratio on the Risk Summary card.** A `quant-research` pass on "what risk-adjusted return metrics are missing" found `RelativeRiskSummary.information_ratio`/`.active_return_pct` were **already fully computed** in `risk.py` and already flowing into `DiagnosticsResult.relative_risk` — contract-documented, but with no `financial-methodology.md` section and no UI consumer anywhere (the same "computed but never surfaced" pattern as the rest of Epic 25). Added a §Information Ratio methodology section (Grinold & Kahn 2000; Goodwin 1998 citations) that explicitly distinguishes the IR's annualized-mean-daily active return from the schema's separate compounded `active_return_pct`. Added two rows to `RiskSummaryCard.tsx` (US-25.3) reading the already-fetched `diagnosticsAnalysis.relative_risk` — no new fetch, prop, or schema change. The two rows are omitted (not `n/a`) when `tracking_error_pct` is null, since they're mathematically dependent on it. Frontend + docs only. +3 `DashboardPanel.test.tsx` tests (32 total); full `run_all_tests.py` green; tsc clean; goldens untouched. |
| 2026-07-04 | US-25.4 | **Epic 25 docs close-out — closes the epic.** Corrected this story's own premise during implementation: `money_weighted_return_pct` is **Modified Dietz**, not IRR/XIRR, implemented in `app/analytics/performance.py` (not `app/analytics/portfolio.py` as originally assumed) — added §Money-Weighted Return to `financial-methodology.md` with the correct formula, edge cases, and Dietz (1966) + GIPS citations. Fleshed out §Risk Contribution and Concentration with the risk-share, top-N risk-share, and HHI formulas (Herfindahl 1950 / Hirschman 1964 citations), explicitly distinguishing the risk-contribution HHI from the separate current-state holdings HHI in `exposure_engine.py`. **Caught a real scale bug while cross-checking the methodology against the implementation:** `risk.py`'s `top_*_risk_share` fields are 0-1 fractions, but `RiskSummaryCard.tsx` (US-25.3) was rendering them with a bare `%` suffix (~100x too small); fixed with a dedicated `formatShareAsPct` formatter and corrected the test fixture. Rewrote `dashboard-fields.md`'s Field Inventory/Provider-Chain/Accuracy-Rules sections wholesale (the prior version described `draftSnapshot`/Allocation-Overview/`capitalChartData` helpers that no longer exist anywhere in the codebase — confirmed by grep) and `current-product-state.md`'s Dashboard bullet list (dropped the unsubstantiated "Sharpe-equivalent" line; no Sharpe ratio exists anywhere in the codebase). Docs-only + one bugfix; full `run_all_tests.py` green; `dashboardGoldens.ts` untouched. |
| 2026-07-04 | US-25.3 | **Risk metrics card (volatility, drawdown, concentration).** New `RiskSummaryCard.tsx` on the Dashboard tab, sourced from the already-fetched `DiagnosticsResult` (`volatility_summary`, `drawdown_summary`, `risk_concentration_summary`) — deliberately not `DashboardHistoryResult.max_drawdown_pct`, which stays behind the investor-economics withholding policy. Threaded `diagnosticsAnalysis` (already held in `App.tsx` state) into `DashboardPanel` as a new prop. Trust shown as a plain-text label following `run_metadata.section_trust.risk_contribution_path`. **Hardening found by the full suite, not the story's own tests:** `App.test.tsx` exercises a real case where `diagnosticsAnalysis` is present but its `volatility_summary`/`drawdown_summary`/`risk_concentration_summary` sub-objects are absent — the card crashed on first render; fixed to fail closed to the EmptyState instead of trusting `availability` alone, with a dedicated regression test. Frontend-only, no backend/schema change. +6 `DashboardPanel.test.tsx` tests (31 total in the file); 249 frontend green; tsc clean; full `run_all_tests.py` (incl. dead-code gate) green; `dashboardGoldens.ts` untouched. |
| 2026-07-04 | US-25.2 | **Monthly returns grid card.** New `MonthlyReturnsGrid.tsx` on the Dashboard tab: one cell per `range_metrics[selectedRange].monthly_returns[]` entry, signed `+X.XX%`/`−X.XX%` formatting (color + sign, never color-only), whole-card EmptyState when `monthly_returns_reliable = false` or `range_metrics` is absent. Refactored the shared range-selection state up from `PerformanceBenchmarkCard` (US-25.1) into `DashboardPanel`, which now renders one `WindowSelector` driving both cards so they can never show mismatched ranges. Frontend-only, no backend/schema change. +4 `DashboardPanel.test.tsx` tests (20 total in the file); 243 frontend green; tsc clean; full `run_all_tests.py` (incl. dead-code gate) green; `dashboardGoldens.ts` untouched. |
| 2026-07-04 | US-25.1 | **Performance & benchmark comparison card.** New `PerformanceBenchmarkCard.tsx` on the Dashboard tab: indexed portfolio-vs-benchmark line chart (base 100, reuses the `IndexedReturnChart`/`normalizePerformanceSeries` rebasing convention) + a summary strip (Portfolio Value, Time-Weighted Return, Money-Weighted Return, Net Contributions) sourced from the already-computed `range_metrics[selectedRange].summary`; a range selector switches both without any new fetch (data already present in `result`). Trust reflected as a plain-text return-basis label per path (`return_basis_contract`), not the shared `TrustBadge` primitive — that primitive's synthetic/unavailable vocabulary doesn't fit dashboard-history's verified/price-return/unverified-proxy ladder (documented in the story's Notes). Deliberately never reads `max_drawdown_pct` (withheld investor-economics field; that's US-25.3's diagnostics-sourced card). Frontend-only, no backend/schema change. +6 `DashboardPanel.test.tsx` tests; 239 frontend green; tsc clean; full `run_all_tests.py` (incl. dead-code gate) green; `dashboardGoldens.ts` untouched. |
| 2026-07-04 | — | Epic created from a project-wide review that found `DashboardPanel.tsx` renders only 3 cards (Rolling Factor Analysis, Sector composition, Benchmark Positioning) while two contract docs still describe a performance chart, monthly returns grid, risk metrics, and investor-economics status as shipped. Confirmed via grep + git log that the backend fields are fully live/tested/golden-pinned and the gap is UI-only, accumulated across several past refactors rather than one regression. PRD + 4 stories authored. |

---

## Completed Epic: Epic 23 — Dead-Code Cleanup & Codebase Review

**PRD:** [`docs/product/prd/epic-23-dead-code-cleanup-and-review.md`](product/prd/epic-23-dead-code-cleanup-and-review.md)

### Goal

A safe, comprehensive, per-area sweep that removes confirmed-dead code across the
whole project (one reviewable area per story, full suite green after each, zero
behaviour change), stands up a dead-code detection floor (tooling + tsconfig
flags), and **catalogs** hardcodes / anti-patterns into `docs/tech-debt-register.md`
to seed a follow-up improvement epic (Epic 24). Deletions + tooling + docs only —
no behaviour change, no smell fixes (those are Epic 24).

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-23.1 | Detection tooling + tech-debt register + removal protocol | Done |
| US-23.2 | Backend sweep — analytics, schemas, domain, instruments | Done |
| US-23.3 | Backend sweep — services, routes, clients, core, importers | Done |
| US-23.4 | Frontend sweep — app & features | Done |
| US-23.5 | Contract & schema↔type↔docs drift reconciliation | Done |
| US-23.6 | Tests, fixtures & golden-pipeline hygiene | Done |
| US-23.7 | Scripts, tooling & docs reconciliation | Done |
| US-23.8 | Enforce the dead-code floor in the canonical test gate | Done |
| US-23.9 | Remove the unused disposition plumbing (cross-seam) | Done |

Recommended build order: 23.1 → 23.5 → 23.2 → 23.3 → 23.4 → 23.6 → 23.7 → 23.8.
(23.1 stands up the tooling/register; 23.5 settles cross-seam contracts before
deletions; 23.7 reconciles docs + hands the register to Epic 24; **23.8 last** —
wires `knip`/`ruff`/`vulture` zero-findings enforcement into `run_all_tests.py`
once the baseline is clean, so dead code can't re-accumulate and no future
cleanup epic is needed. ESLint deliberately not adopted — `tsc` + `knip` cover
the dead-code goal; ESLint's in-file `no-unused-vars` is redundant with `tsc`.)

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-19 | US-23.8 | **Epic 23 tail — the dead-code detection floor is now an enforced gate, and Epic 23 is Completed.** `scripts/run_all_tests.py` gained two gate steps: `npx tsc --noEmit` and `python scripts/detect_deadcode.py --strict` (ruff + vulture + knip, zero-findings) — so any newly-introduced dead code or in-file unused local fails the suite. **Baseline cleaned to green:** `knip.json` set `ignoreExportsUsedInFile: true` (so a flagged export is used *nowhere*, not merely over-exported) — collapsing 74 findings to 5 genuinely-dead exports, which were removed (the dead `buildExposureFactorModelResponse` duplicate + its `ImportedExposureFactorModelSource` type, the unused `buildImportedExposureView`/`buildImportedDashboardView`/`buildImportedDiagnosticsView` adapter views, `hashPortfolioSnapshot`); plus 4 vulture-100% test-dead items (an unreachable-after-return method, two unused lambda params, one signature-match `auto_adjust` kwarg → reasoned `vulture_allowlist.py` entry). **Enforcement proven (AC4):** a scratch unused export was shown to fail the gate, then removed. **Documented (AC6)** in `CLAUDE.md` + `testing-architecture.md` (how to read a failure; reasoned-allowlist policy). Full suite + both gate steps green; goldens untouched; `git status` clean. No app behaviour change — tooling only. |
| 2026-06-19 | US-23.7 | Epic 23 reconciliation close-out (the enforcement gate US-23.8 is the tail that flips the epic to Completed). **scripts/** swept — `ruff` + `vulture` clean, no dead code (CLI entry points are live by design). **Docs reconciled** to the leaner tree: removed the stale live-state references to the US-23.9-removed disposition subsystem from `system-architecture.md`, `dashboard-fields.md`, and `financial-methodology.md` (contract `import-admission-fields.md` was already reconciled in US-23.9); contract docs confirmed free of the removed `MarketOverlapConstituent` schema + US-23.4 dead types. **Register consolidated** into a prioritized "Epic 24 backlog" (severity × effort, grouped to proposed stories). **Epic 24 — Codebase Improvement PRD seeded** (`docs/product/prd/epic-24-codebase-improvement.md`, Backlog) with a 7-story list led by the two hardcoded-year latent bugs. **Epic 23 removal totals (US-23.1–23.7):** 7 unimported files deleted + the cross-seam disposition subsystem; ~1,550 lines of dead/duplicate code removed across 36 services/apps files (gross deletions; net is smaller — insertions are mostly the US-23.9 persistence-test rewrite + reasoned `# noqa`); detectors now clean on all backend trees (`ruff`/`vulture`) with knip down to over-exported-but-live only. Full suite green throughout; goldens untouched; no methodology change. |
| 2026-06-19 | US-23.6 | Test-suite hygiene sweep (backend pytest + frontend vitest). **Removed:** backend — 12 `F401` unused imports across 8 test files + 3 `F841` dead locals (`test_analytics.py` `snapshot`/`price_histories`, `test_drawdown_analytics.py` `top_returns`); frontend — `DashboardPerformanceChart.tsx` (no production importer) together with its **vacuous** App.test.tsx suspense scaffolding (the `vi.hoisted` mock + `vi.mock` + reset + suspense test — confirmed it could not exercise a real suspense boundary since App never renders the component), plus 4 dead leaf fixture factories (`createIb2026/Ff2026ImportedDashboardFixture`, `createImportedBaselineFixture`, `createDiagnosticsFixture`). The 4 over-exported-but-live fixtures were kept. **AC1 decision:** the ~10 hand-rolled snapshot builders were NOT wholesale-migrated to `fixtures.py` — many return route-payload dicts vs the shared model builder, so migration is deferred to Epic 24 with a recorded reason. **AC5 catalog:** fixture-duplication + a coverage gap (`test_build_portfolio_risk_summary_and_position_contributions` never calls `build_position_risk_contributions`) recorded. Golden invariants intact; `git status` clean after `run_all_tests.py`; 233 desktop + backend green; tsc clean. |
| 2026-06-19 | US-23.3 | Backend wiring-tier dead-code sweep (`services/` + `api/` + `clients/` + `core/` + `importers/`). **Removal (AC1):** the dead **duplicate** `allow_exact_slice_benchmark_return_output` computation in `dashboard_history_engine.py` — investigated and confirmed dead (its result was discarded; the live benchmark-output gating is the per-range call → `_compute_visible_summary`; withholding logic unchanged). Output-neutral; drops a wasted call per dashboard run. The 3 Freedom24 `F841` locals (`isin`/`realized_pnl`/`account`) were checked against the schema and **kept under reasoned `# noqa: F841`** (parsed-but-dropped: `isin` is a real `ImportedInstrument.isin` coverage gap, `realized_pnl` is unmodeled, `account` is benign) rather than deleted — evidence preserved. `vulture --min-confidence 80` finds no dead routes/methods/classes; every registered route still passes the US-21.3 route-table check. **AC4 catalog (16 wiring smells → Epic 24):** the fragile positional Freedom24 PDF parser (~50 fixed-offset reads), `fmp.py` hardcoded `timeout=30.0` + hardcoded `etf-holder` v3 URL bypassing settings `base_url`, the `"SPY"` default benchmark duplicated across ≥4 engines, the `99.0` coverage threshold, the `ceil(window*1.6)+30` lookback heuristic duplicated across 3 engines, and `_MIN_OBSERVATIONS=20` triplication; `core/` noted as exemplary settings-driven config (no findings). Full suite green; goldens untouched; no methodology change. |
| 2026-06-19 | US-23.2 | Backend dead-code sweep of the pure-logic core (`analytics/` + `schemas/` + `domain/` + `instruments/`) — closed out. Dead-code removal (AC1–AC3) was landed in a prior pass (5 F401 unused imports across `attribution.py`/`risk.py`/`reconciliation.py`; the dead full-period OLS block + discarded `alpha_annualized`/`specific_risk`/`collinearity_warnings` locals + orphaned `_orthogonalize_factor_series`; the dead `top_shared` market-overlap build + `MarketOverlapConstituent` schema; the `target`/`portfolio_names` locals — all output-neutral, methodology cross-checked). This pass **confirmed** the four modules are now `ruff F401/F811/F841`-clean and `vulture --min-confidence 80`-clean, and completed **AC4**: an exhaustive hardcode/anti-pattern catalog (24 findings → Epic 24), headlined by two **hardcoded calendar-year `2025` latent bugs** (`activity.py:24`, `reconciliation.py:24` silently drop non-2025 ledger entries), hardcoded broker-section strings in `domain/ledger.py`, and the inline mapping-score weight/threshold clusters in `risk.py`. No code change this pass; full suite green; goldens untouched; no methodology edit (proof of behaviour-neutrality). |
| 2026-06-19 | US-23.9 | Removed the never-wired `ImportAdmissionReviewDispositionV1` disposition plumbing across the seam (carved from US-23.4, gated by the workspace round-trip tests). **FE** (`portfolioWorkspaceStorage.ts`): dropped the disposition save fn, `assertValidImportAdmissionReviewDispositionForSave`, the 8 sanitize/canonicalize/match helpers, the whole fingerprint subsystem (`canonicalizeForFingerprint`/`buildDeterministicImportAdmissionFingerprint`/`buildImportSnapshotFingerprint`/`buildImportAdmissionSummaryFingerprint`), the now-dead `isPlainRecord`/`isNonEmptyString`, the type aliases, and `admissionReviewDispositions` handling in `buildPersistedImportedSource`+`sanitizeImportedNodeSource`. Removed `ImportAdmissionReviewDispositionV1`+`ImportAdmissionCheckEvidenceSummaryV1` (`types.ts`) and the `admissionReviewDispositions` field+import (`workspaceTypes.ts`). **BE** (`import_bootstrap.py`): dropped `ImportAdmissionReviewDispositionV1`+`ImportAdmissionReviewEvidenceSummaryV1`+the `ImportAdmissionReviewDisposition` enum+`ImportAdmissionReviewEvidenceStatus` alias+the now-unused `field_validator` import. **Persisted-state safety**: a pre-US-23.9 workspace's `admissionReviewDispositions` blob is dropped on read (field absent, no throw, storage not rewritten) — proven by a new round-trip regression. Removed the ~14 disposition/fingerprint test blocks + 3 BE disposition tests; `import-admission-fields.md` reconciled (disposition subsystem → "Removed" note). 234 frontend green (added 1, net −13 blocks); backend `test_import_admission.py` 17 green; ruff/knip clean, no new vulture findings; tsc clean; goldens untouched. |
| 2026-06-17 | US-23.4 | Frontend dead-code sweep — closed out. Removed the confirmed-dead set (6 unimported files: `featureFlags`/`portfolioState`/`CurrentFactorSnapshotCard`/`SectorDonutCard`/`historyTruth`/`investorEconomics`; 5 dead types; `getPortfolioDatabaseName`) — knip 7→1 files, 65→60 types, 22→21 exports. Resolved `features/market-data` + `features/settings` as intentional README-only placeholders (not dead). Recorded the over-exported live types, 7 suspected-unused CSS tokens (kept — design-scale/indirect-ref risk), and "no FE anti-patterns of note" in the register. **Carved out** the two heavy/entangled remainders to their own slices: the disposition plumbing → **US-23.9** (per the 2026-06-17 stability decision — ~250-line persistence+test+schema change gated by the workspace round-trip tests), and `DashboardPerformanceChart` (test-coupled) → **US-23.6**. Suite green; tsc clean; goldens untouched. |
| 2026-06-12 | US-23.5 | Contract & schema↔type↔docs drift reconciliation (sequenced before the deletion sweeps). Triaged the US-23.1 detector baseline into the register: of knip's 81 flagged exports/types, **only 10 are truly dead** (5 FE-orphan types `ActivityPoint`/`CanonicalLedgerRecord`/`ReconciliationCheck`/`DiagnosticsPayload`/`ExposureEnginePayload` + 5 unused fixture/db helpers) and 7 whole unimported files; the other **71 are live in-file mirrors merely over-exported** (not deletable — `export` keyword unnecessary; re-run knip iteratively as the 10 are removed). Three-way audit (Pydantic schemas ↔ `types.ts` ↔ `docs/contracts/*`) found **no type-level drift** — every doc-referenced identifier resolves to a live schema/TS type or a UI-component/prose word; no stale rows, no dangling types, so contract docs are accurate as-is and **no reconciliation edits were needed**. Confirmed none of the deletion candidates cross a documented seam (safe for US-23.4). Flagged the canonical cross-seam dead case — the `ImportAdmissionReviewDispositionV1` disposition plumbing — with coordinated owners (FE US-23.4 + BE US-23.2). Register/docs only; suite green, tsc clean, goldens untouched. |
| 2026-06-12 | US-23.1 | Dead-code detection floor + tech-debt register. Python: `ruff` (`ruff.toml`, unused rules F401/F811/F841) + `vulture` (`vulture_allowlist.py` for dynamic-use FPs — Pydantic `__context` etc.), declared in new `requirements-dev.txt`. TypeScript: `knip` devDependency + minimal `knip.json` (auto-detects Vite/Vitest entries). New `scripts/detect_deadcode.py` runs all three (informational; `--strict` = the US-23.8 gate mode). New `docs/tech-debt-register.md` (category schema + per-entry fields + the "confirmed dead" removal protocol + the captured baseline as the per-area worklist). Documented in CLAUDE.md + testing-architecture.md (incl. why ESLint is not adopted — redundant with tsc). **Baseline captured**: ruff 29 (17×F401, 12×F841), vulture (FactorRiskContribution + test items), knip **7 unused files / 22 unused exports / 65 unused types** — triaged to US-23.2/23.3/23.4/23.6. `tsconfig noUnusedLocals/noUnusedParameters` **staged** (enabling surfaces ~20 in-file violations inside not-yet-deleted dead files; turned on in US-23.8). Tooling/config/docs only — no app code; 242 frontend + backend green; tsc clean; goldens untouched. |
| 2026-06-12 | — | Epic created from a "clean dead code + review the whole project" request, after the US-22.2 review surfaced never-consumed disposition plumbing and a survey found **no dead-code tooling** (no ruff/vulture/knip/ts-prune/eslint) and no `noUnusedLocals`. Per-area story breakdown (tooling+register, backend×2, frontend, contracts, tests, scripts-docs) so nothing is missed; dual deliverable per story — remove dead code AND catalog hardcodes/anti-patterns into a tech-debt register feeding a follow-up Epic 24. Tail story US-23.8 added per request: enforce the detectors (`knip`+`ruff`+`vulture`, zero-findings) in `run_all_tests.py` once the baseline is clean, so dead code can't re-accumulate and no future cleanup epic is needed (researched: ESLint not adopted — redundant with `tsc` for the dead-code goal). PRD + 8 stories authored. |

---

## Active Epic: Epic 24 — Codebase Improvement

**PRD:** [`docs/product/prd/epic-24-codebase-improvement.md`](product/prd/epic-24-codebase-improvement.md)

Seeded by Epic 23 (US-23.7) from the consolidated "Epic 24 backlog" in
`docs/tech-debt-register.md`. Fixes the catalogued hardcodes / magic numbers /
fragile coupling / latent bugs as deliberate, reviewed, **behaviour-aware**
changes (the complement to Epic 23's deletions). Every change keeps the
deterministic suite green and updates methodology / contract docs when a
surfaced value becomes a named, documented constant.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-24.1 | Fix hardcoded-year ledger filters (latent bugs) | Done |
| US-24.2 | Extract the risk-model scoring rubric & thresholds | Done |
| US-24.3 | De-duplicate shared analytics constants | Done |
| US-24.4 | Harden importer parsing (Freedom24) + extract hardcodes | Done |
| US-24.5 | Decouple broker sections from the domain (+ two silent misclassifications) | Done |
| US-24.6 | Market-data client config hygiene — escaped URL + timeout | Done |
| US-24.7 | Reconcile minor hardcodes + de-export + test smells | Backlog |
| US-24.8 | Harden the IBKR importer parsing (fail-safe) | Done |
| US-24.9 | Cash de-dilution on the imported ledger-replay return series | Done |
| US-24.10 | Stop unpriced-symbol cash events fabricating investor-performance returns | Done |
| US-24.11 | Render the replay disclosures the engine already computes | Done |

Recommended order: US-24.1 first (highest-impact latent bugs, low effort), then
US-24.2/24.3 (the analytics-constant work), then US-24.4/24.5/24.6, with US-24.7
the low-severity tail. Stories are authored via `write-story` as each is picked up.
US-24.8 (the deferred US-24.4 importer-hardening follow-up) was picked up out of
order alongside a broader codebase review.
*Validity re-check 2026-07-08: US-24.5 still valid (strengthened — the US-28.1
CSV importer is a third producer coupled to `domain/ledger.py`'s section
strings); US-24.6 valid verbatim; US-24.7 downgraded to Low — its EURUSD item
was resolved incidentally by US-28.1 and the de-export motivation is obsolete
(knip gate uses `ignoreExportsUsedInFile`); see the tech-debt register rows.*
*US-24.9 was logged by US-30.5c and renumbered from 24.8 by US-24.6 (the
original number collided with the shipped IBKR-importer story); US-31.1 then
marked it **blocked** — refining the ledger-path return basis is meaningless
while Epic 31's F-1..F-3 corrupt the series itself.*

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-08-09 | US-24.5 | **A refactor row that turned out to be a live correctness defect on two of three brokers.** Re-validating before touching anything (Epic 24 discipline) showed `domain/ledger.py` derived `broker_evidence` and `cash_movement_classification` by matching **broker display strings inline** — a vocabulary drawn entirely from IBKR statements. Any importer whose statement named a section differently fell through to `"unknown"`, silently. **F-1:** Freedom24 calls its trade section `"Transactions"`, so **all 3 FF2026 trades** were unclassified. **F-2 (worse):** ESPP emits `"Employee Stock Purchase Summary"` for both the payroll DEPOSIT and the BUY — and since `external_capital_flow` is exactly how `portfolio_proof._cash_flow_witnesses` recognises investor contributions, the deposit was reported **`not_observed`** while the statement stated it plainly. IB2026 classified all **204** entries cleanly, which is why this survived: the primary fixture never exercised it. **Fix:** a **section-role registry** resolving `(label, entry_type) → semantic role`. `source_section` stays **provenance** — no importer is made to relabel its broker's vocabulary to satisfy a downstream matcher — and a label may hold several roles (the one ESPP section carries both the contribution and the purchase), exactly as the pre-existing IBKR aliases already required. `unknown` remains reachable for genuinely unrecognised sections; defaulting an unknown label to a role would fabricate provenance. **The actual deliverable is the guard:** an AST scan over every importer asserts each `source_section` literal resolves to a registered role, so the next broker fails the suite rather than degrading output in production — the fix for the *class*, not just today's two symptoms. **Result:** FF2026 and ESPP2026 both classify with **zero** `unknown`; IB2026's 204-entry distribution is **unchanged**; `dashboardGoldens.ts` byte-identical (no engine output moved). **Register correction:** the row's second item was stale — `LedgerEntryType` has been a shared `Literal` in `app/schemas/imports.py` for some time, imported by the domain and both IBKR importers, so there was no pseudo-enum to extract; and its **Med** rating understated a High defect. +22 backend tests (20 registry/domain incl. a 14-case unchanged-pairing table, 2 fixture-level). 646 backend (+22) + 294 frontend green; tsc + dead-code gate clean. |
| 2026-08-09 | US-24.11 | **The engine's honesty finally reaches the screen.** Five replay disclosures — `fx_fallback_currencies` (US-27.8), `unpriced_replay_symbols` (US-31.2), `replay_cash_anchor` + `withheld_return_dates` (US-31.3) and `trade_price_anchored_symbols` (US-24.10) — were computed, schema'd, contract-documented and golden-pinned, but `DashboardPanel.tsx` rendered **no** `run_metadata` at all (grep: zero occurrences). On the committed IB2026 portfolio that meant a performance chart, TWR, monthly returns and max drawdown presented over a **degraded** cash anchor (`statement_nav_date_mismatch`, −$1,196.61 residual) with one return day withheld and LQQ flat-anchored — with nothing on screen saying so, contradicting CLAUDE.md's own "trust levels rendered visibly" convention and guardrail #3. New `ReplayDisclosuresCard` on `CardShell` renders one prose note per present degradation, each stating what was degraded **and what it affects** (the `DriftBenchmarkPanel` bar), placed directly above the surfaces they affect. **Renders nothing on a clean run** — no empty card and deliberately no "all good" banner, since absence of a warning is not a claim the engine made; the cash anchor appears only when its trust is not `verified`. **No Synthetic badge** (AC5): the imported replay is broker truth that has been degraded, a different truth class, and `TrustBadge` only speaks `Synthetic`/`Unavailable` — labelling it would be a precise-looking claim that is wrong (guardrail #2), so the nuance lives in prose; pinned by a regression test. `withheld` renders with the engine's own reason string, never collapsed into `unavailable`. Frontend-only — `run_metadata` was already on `DashboardAnalysis`, so no plumbing, no schema, no backend, and `dashboardGoldens.ts` is **byte-identical**. Card added to the design-system audit's `ALL_CARD_FILES` (no-hex / no-px / single-source-`Synthetic`). +9 frontend tests (7 card, 2 panel). 624 backend + 294 frontend (+9) green; tsc + dead-code gate clean. |
| 2026-08-09 | US-24.10 | **Killed a live fabrication in the investor-performance series — and found a second one while doing it.** A symbol with no market history and no statement close was valued at **$0**, yet its trades moved real cash, so `total_portfolio_value` stepped with no offsetting position and the cash-inclusive TWR published the step as performance. On IB2026 this produced the window's **two largest days**, both pure fabrication: **−7.90%** (2026-04-08, buying $5,092.82 of BTEC/IUFS/IUHC) and **+9.61%** (2026-04-27, selling IUFS/IUHC for $5,341.92). Same guardrail-#3 class as Epic 31 F-3. **Owner decision** (four options put forward): value them at the **last broker execution price** — the statement already records one for every trade, so it needs no market data and is deterministic. New **third valuation tier**, precedence `market history → statement close → trade price`, **never inverted** (a nearer-in-time trade must not outrank a statement close, or every currently-held anchored symbol would re-value and regress US-27.7/US-30.2 — pinned in both directions). **Forward-carry only**: before a symbol's first observed trade it stays unvalued and disclosed, because reaching backwards fabricates a price for a date the broker never produced one. Converted from the **trade's settle currency** (not the US-31.5 fund currency — a trade price is quoted where it executed); no rate → carried unconverted and disclosed. Disclosed as `trade_price_anchored_symbols`, mutually exclusive with the other two tiers. **Second fabrication class, found by this story's own new test and fixed in the same pass:** US-24.9 gated `trade_flow` on "is this symbol valued today", which breaks once these symbols have a valuation — (a) selling a symbol first observed by that very sale (never in yesterday's market value), and (b) a **same-day round trip** in a new symbol: **2026-06-11 IITU** is bought and fully sold before any close, so it is in **no** day's market value, and counting its $1,443.00 leg produced **−3.45%** against an expected −0.36%. A per-direction predicate fixed (a) but not (b); both fall out of one rule computed from the **built state** — a leg counts only if the symbol is priced in today's market value or was priced in the previous day's — which also subsumes US-24.9's original unpriced case. Three special cases collapsed into one rule. **Measured (frozen data, network-free):** TWR 2026-04-08 **−7.90% → +2.54%**, 2026-04-27 **+9.61% → −0.12%**; max daily TWR **9.61% → 2.76%**; TWR annualised volatility **23.32% → 14.72%**; `unpriced_replay_symbols` **empties**; LQQ keeps its statement-close anchor; terminal market value **unchanged** at $61,239.88 ($1.35 from `stock_total` — reconciliation not degraded). **The AC9 tripwire is now clean:** with the fabricated days gone the trade-neutral chain tracks a cash-de-diluted TWR to within **0.0537% on every one of the 117 days** — no exclusions, where US-24.9 needed two. Goldens regenerated deliberately; the diff is confined to `market_value`/`market_price` (the three newly-valued symbols), the dependent daily totals, `trade_flow` and 5 return points — statement-identity, weight, sector, cost-basis, ledger-count, ISIN and cash-by-currency families **byte-identical**; `golden_market_data.json` untouched (no re-capture). Methodology §Synthetic History Coverage Rule gains the three-tier precedence ladder, the no-back-fill rule and the trade-leg neutralisation rule, with IFRS 13 / GIPS citations. **Scope correction:** T-24.10.3 (a frontend disclosure note) was **not built** — its premise was false, `DashboardPanel.tsx` renders no `run_metadata` at all, so shipping one note would have made the newest, mildest disclosure the only visible one while the more severe siblings stayed hidden; logged as **US-24.11**. +9 net backend tests (6 engine, 4 new IB2026 pins, 3 US-24.9 pins restated, 1 superseded). 624 backend (+9) + 285 frontend green; tsc + dead-code gate clean. |
| 2026-08-09 | US-24.9 | **Closed the last open ledger-replay accuracy row — and the measurement tripwire caught two fabrications on the way.** New `DailyPortfolioState.trade_flow` (net base-currency market value moved INTO the holdings by a day's BUY/SELL entries, FX-converted per entry — the raw currency-mixed sum is explicitly rejected, the US-31.3 trap) plus a third `ReturnBasis`, **`market_value_trade_neutral`**: `r_t = (MV_t − trade_flow_t)/MV_{t−1} − 1`. The imported ledger-replay path's RISK statistics (beta / correlation / volatility / relative risk / volatility regime / factor model) now exclude the account's cash sleeve **without** reading a BUY as a gain — the two properties US-30.5c could not have at once, which is why it deferred this. The **investor-performance** family (Dashboard performance series, TWR, money-weighted return, monthly returns, max drawdown) deliberately keeps the cash-inclusive TWR: cash is part of what the investor earned. One predicate, mirrored in `risk.py` and `attribution.py`, so the two chains cannot drift (the US-31.2 lesson). **Scoping correction:** the register's "~3% cash" is the *terminal* weight — the **median is 5.60%** (range −1.91% .. 17.53%). **AC9 tripwire fired twice, neither absorbed.** (1) *A fabrication in this story's own first cut:* counting trades in **unpriced** symbols neutralises a leg that never entered market value — selling the unpriced IUFS + IUHC ($5,341.92) on IB2026 2026-04-27 produced **+9.43%** on a day the priced book moved **+0.02%**. Fixed by gating `trade_flow` on a new side-effect-free `is_valued(symbol, day)` predicate; pinned on both a synthetic GHOST symbol and the real 2026-04-27 / 2026-04-08 pair. (2) *A pre-existing defect this story does NOT fix:* the same unpriced symbols corrupt the **cash-inclusive TWR** it deliberately leaves alone — their market value is $0 but their trades move real cash, so `PV` steps with no offsetting position and the TWR publishes it as performance: **−7.90% on 2026-04-08** and **+9.61% on 2026-04-27**, both pure fabrication. Logged as **US-24.10 (High)** rather than quietly absorbed; the new basis is structurally immune (it works purely in priced-market-value space), which is exactly how the defect surfaced. **Measured de-dilution, like-for-like** (those two contaminated days excluded): annualised volatility **14.54% → 15.47%**, ×1.064 against the cash-weight prediction ×1.059 — explained. The *headline* figures move much further (vol 23.32% → 15.86%, beta 0.552 → 0.860, correlation 0.343 → 0.787, r² 0.118 → 0.619, max daily 9.61% → 2.95%) because finding (2)'s two fabricated days dominated the old series — accuracy, not a change in portfolio risk. **The US-30.5c guard held:** a blanket market-value chain here would report vol **41.43%** and a **+17.19%** trade day. `dashboardGoldens.ts` diff is **purely additive** — 209 insertions, **zero deletions**, the new field on 209 states with no value changes (so the performance/TWR/monthly-return family is byte-identical, AC6 proven mechanically); `golden_market_data.json` untouched, no re-capture. Methodology §Rolling Pearson Correlation's "deferred to the tech-debt register" paragraph replaced by the shipped three-basis rule + Bacon/GIPS citations. +15 backend tests (6 engine, 6 analytics, 3 IB2026 audit pins); the US-30.5c imported-path pin inverted to the new basis with a negative pin on the naive chain. 615 backend (+15) + 285 frontend green; tsc + dead-code gate clean. |
| 2026-07-17 | US-24.6 | **Closed the last hole in "all market data flows through the configured client."** Re-validated the register row first (Epic 24 discipline): two of its three items were real, one was a misread. **The actual defect —** `get_etf_holders` built an **absolute** `https://financialmodelingprep.com/api/v3/etf-holder/{symbol}` inline (`fmp.py:183`), the single call bypassing `settings.fmp_base_url`, so pointing `FMP_BASE_URL` at a proxy, mock or recorded fixture silently failed to redirect it. **The subtlety that shaped the fix:** that endpoint lives on the **legacy v3** API while `fmp_base_url` is `/stable`, so reusing `fmp_base_url` would have 404'd — the fix adds a *separate* `fmp_legacy_base_url` (default `…/api/v3`, preserving the exact live URL). No vendor-host literal remains in `fmp.py`. **Also fixed:** `timeout=30.0` → `fmp_request_timeout_seconds` (the last non-configurable transport knob). **Deliberately preserved:** `get_etf_holders`'s **cache identifier** still serialises the v3 *path* and is independent of the now-configurable host — changing it would have invalidated every cached holdings entry (16 local) and broken in-flight coalescing; regression-pinned. **Scoping correction:** the register's third item, `:248` screener `limit=500`, is **not** debt — it is a caller-overridable keyword default (correct API design) with no in-app callers; promoting it to settings would add config surface nothing sets. Left unchanged, recorded why. Behaviour-neutral at defaults; goldens untouched; +4 backend tests; dead-code gate clean. **Also corrected a numbering collision this session introduced:** the deferred ledger-path cash de-dilution item logged by US-30.5c was filed as "US-24.8", which already belongs to the shipped IBKR-importer story — renumbered to **US-24.9** across the register, roadmap, PRD and story index. |
| 2026-07-04 | US-24.8 | **Hardened the IBKR importer parsing (fail-safe).** Investigation corrected this story's original two-importer premise: `interactive_brokers.py` and `espp.py` are already regex-`match()`-guarded (unlike Freedom24's raw offset walk), so the real gap was narrower — a captured numeric/date group can match the shape but fail the subsequent `float()`/`datetime.strptime()` conversion, with no guard between that and `import_statement`. Fixed in `interactive_brokers.py`: `_parse_statement_totals`'s per-field loop (+ TWR/EURUSD parses), `_parse_period_end_date` (catches `ValueError`, returns `None` so the existing `2025-12-31` fallback applies), and the record-append blocks in `_parse_trades`/`_parse_simple_cash_section`/`_parse_deposits_and_withdrawals` now degrade one field/record instead of raising. **`espp.py` investigated and left unchanged** — every numeric regex group there uses the strict `[\d,]+\.\d+` shape, which cannot capture a value `float()` will reject, so there was no reachable failure to guard (confirmed by trying to construct one and failing). Behaviour-neutral for valid statements (IB2026 golden import unchanged). +3 `test_importer.py` tests. Methodology "Importer resilience rule" extended to both importers + the ESPP investigation note; tech-debt register row marked Resolved (IBKR) / Investigated-not-needed (ESPP). Full suite + dead-code gate green; tsc clean; goldens untouched. |
| 2026-06-24 | US-24.4 | **Hardened the Freedom24 importer + extracted its format hardcodes.** Investigation first **corrected the register's premise**: the "Freedom24 ISIN data gap" was a misread — `_parse_instruments` already flows ISIN to `ImportedInstrument.isin` (now pinned by an FF2026 assertion); the `_parse_positions` `isin` copy was dead offset-walk code. Made all 5 positional parsers **fail-safe** — a malformed/non-numeric record is skipped and parsing continues (a layout drift → partial snapshot surfaced by reconciliation, never a crash or fabricated/zero row). Extracted the inline format hardcodes (currency whitelist / `.US` suffix / default currency / the magic page indices) to named constants; removed the 3 dead parsed-but-dropped locals (`isin`/`realized_pnl`/`account`, now documented offset comments). **Behaviour-neutral for valid statements** — the FF2026.pdf golden-master test is byte-identical (+ a new ISIN + constants pin + a malformed-input degradation test). `realized_pnl` stays unmodeled (schema change deferred). Methodology gained an "Importer resilience rule"; register rows corrected/Resolved. Full suite + dead-code gate green; goldens untouched. |
| 2026-06-24 | US-24.3 | **De-duplicated the three copy-pasted analytics defaults** into a single `app/core/constants.py` (the lowest layer, so `schemas` can import it without a cycle): `lookback_calendar_days(window)` (= `ceil(window*1.6)+30`), `MIN_DAILY_OBSERVATIONS` (= `20`), `DEFAULT_BENCHMARK_SYMBOL` (= `"SPY"`). Replaced the duplicate `_lookback_calendar_days` in **6** engines (attribution / correlation / distribution / drawdown / stress / provenance + intra-correlation — two more consumers than the original catalog noted), the flat `_MIN_OBSERVATIONS=20` across the distribution/correlation/drawdown/intra engines + the `analytics/distribution.py`/`analytics/correlation.py` modules, and ~10 `"SPY"` defaults (3 schema field defaults + the engine `or "SPY"` fallbacks). **Behaviour-neutral** — values unchanged, `dashboardGoldens.ts` untouched, full suite + dead-code gate green; the distinct `WINDOW_MIN_OBSERVATIONS` (OLS buffer) and `attribution.min_observations=window` were deliberately **not** merged. Added 3 shared-module tests; methodology doc + register updated. |
| 2026-06-19 | US-24.2 | **Extracted the risk-model scoring rubric & thresholds into named, documented constants** (behaviour-neutral). Lifted the factor→UCITS mapping-quality composite/sub-weights, hard-cap ceilings + reasons, `_mapping_match_label` thresholds, the `_mapping_quality_score`/`_cost_fit_score` quality maps, the volatility-regime percentile cutoffs, and the factor-model `FACTOR_MODEL_MIN_SHARED_OBSERVATIONS` floor into a documented `# ── Factor-mapping scoring rubric ──` constants block in `risk.py`; plus `BENCHMARK_HOLDINGS_VERIFIED_COVERAGE_PCT` in `exposure_engine.py`. Each constant carries a one-line rationale ("heuristic, no academic basis" where applicable — **no fabricated citations**). **Pin-tests-first discipline:** added 6 exact-value golden-master tests (`test_analytics.py`) capturing the *current* score_pcts/labels/hard-caps/regime-cutoffs/stress-projections/min-history before the extraction, so a transposed weight fails loudly. Behaviour-neutral — `dashboardGoldens.ts` untouched; 141 analytics+exposure tests green; full suite + dead-code gate green; tsc clean. The leaf per-token `_*_score` rubric literals stay inline (deferred, low value). Methodology doc + register updated. |
| 2026-06-19 | US-24.1 | **Fixed the two hardcoded calendar-year `2025` latent bugs** (the register's only High-severity entries). Removed `if entry.date.year != 2025` from `analytics/activity.py` `build_activity_series` (which silently dropped every non-2025 ledger entry → empty activity for 2026+ statements) and `and candidate.date.year == 2025` from `analytics/reconciliation.py` `_negative_withholding_total` (which reconciled non-2025 withholding against `0`). Removal — not "derive the year" — because the snapshot ledger is already period-scoped and the sibling reconciliation actuals (dividends/fees/interest/deposits) never year-filtered; the `%Y-%m` bucketing handles any span. **Behaviour-neutral for 2025** (all-2025 fixtures → identical output; `dashboardGoldens.ts` untouched). Added 4 `test_analytics.py` regressions (2026 non-empty activity, 2025-unchanged pin, 2026 withholding reconciles, multi-year span). Methodology doc gained a "Statement reconciliation & activity scoping" rule; register rows marked Resolved. Full suite + dead-code gate green; tsc clean. |

---

## Completed Epic: Epic 22 — Import Admission Review UI

**PRD:** [`docs/product/prd/epic-22-import-admission-review-ui.md`](product/prd/epic-22-import-admission-review-ui.md)

### Goal

Give the Import Admission Review (overall decision + trust level + per-check
results) a visible home in the UI. The summary is already computed, delivered,
and persisted as workspace `admissionSummary` — but never rendered (only the
identity-mismatch slice leaks through the Data Sources panel). Render it from
existing state; no backend change.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-22.1 | Import Admission Review card | Done |
| US-22.2 | Admission review disposition workflow | Won't do (2026-06-12) |

US-22.2 reviewed and **closed as not needed** (2026-06-12): the disposition
schema models an enterprise review/sign-off (reviewer label, required rationale,
accepted-exception / needs-correction / deferred states) on a single-user,
local-first personal tool. Persistence + sanitization + evidence-matching for
dispositions already exist in the workspace storage layer but have **no producer
and no consumer** — nothing records a disposition and nothing displays/acts on
one. US-22.1 already delivers the actual value (visibility into why an import is
degraded/withheld); a formal sign-off workflow is speculative (no demonstrated
need) and changes no number or analytic. Epic 22 is therefore complete with
US-22.1 alone. (If acknowledgement value ever becomes real, a lightweight
"dismiss this warning" — no reviewer/rationale ceremony — is the right shape,
not the full schema. The unused disposition plumbing is a candidate for a
separate dead-code cleanup.)

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-12 | US-22.1 | Import Admission Review card — the admission summary now has a visible home. New `ImportAdmissionReviewCard.tsx` (Exposure tab, beside Data Sources): renders the persisted workspace `admissionSummary` (`ImportAdmissionSummaryV1`) — decision (admitted/degraded/withheld) + trust-level badges, then one row per check (residual-cash, NAV, position-MV, symbol identity, description-consistency, ISIN-consistency) with status (✓ Pass / ⚠ Warn / ✗ Fail / — Unavailable — symbol prefix so status isn't colour-only), message, and observed/comparison/signed-delta+currency evidence + affected fields. Presentational only (persisted-import truth class) — no fetch/recompute, survives reload; null summary → explicit unavailable state, never a fabricated all-clear. Threaded the active import source's `admissionSummary` from App.tsx through a new optional `ExposurePanel` prop. Added `--color-status-warn` design token (amber caution, distinct from error/disabled) and registered the card in the design-system audit set. Frontend-only; no backend/schema/goldens change. +7 vitest tests; 242 frontend + backend green; tsc + audit clean. |

---

## Completed Epic: Epic 21 — Testing Strategy & Architecture Hardening

**PRD:** [`docs/product/prd/epic-21-testing-strategy-hardening.md`](product/prd/epic-21-testing-strategy-hardening.md)

### Goal

Make "green" mean green: zero live-network tests (kill the standing "4 known
failures"), a generic JSON-strict response-integrity property test (generalizing
the 2026-06-10 NaN-500 fix), one shared fixtures module instead of ~7 duplicated
mock helpers, deterministic goldens, additive-tolerant assertions, and a faster
parallel suite.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-21.1 | Deterministic suite — no live network in tests | Done |
| US-21.2 | Shared test-fixtures module | Done |
| US-21.3 | Engine response-integrity property test | Done |
| US-21.4 | Golden pipeline determinism | Done |
| US-21.5 | Assertion conventions + suite speed | Done |

Recommended build order: 21.1 → 21.2 → 21.3 → 21.4 → 21.5.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-11 | US-21.5 | Assertion conventions + suite speed — **closes Epic 21**. (1) `write-tests/SKILL.md` gained an "Assertion conventions" section: assert membership/superset (`expected.items() <= actual.items()`) for intentionally-extensible structures (reserve `==` for closed contracts); pin an implicit default in exactly one dedicated test and capture-and-delta elsewhere. Both rules cite their real Epic-21 breakages (`vendor`/`last_fetch_meta`; admission check; 60d→20d window). (2) Converted the brittle spots: five `last_fetch_meta` exact-dict assertions (`test_market_data.py`) + the import-admission check dict (`test_import_admission.py`) → `.items() <=` superset; drawdown/VaR click-refetch tests capture the default dynamically and assert the delta (VaR gained a dedicated default test); rolling-correlation "insufficient history" selects 20d explicitly. (3) `pytest-xdist` added to `requirements.txt`; `run_all_tests.py` backend step now `-n auto`. **Backend wall-time 135.0s → 39.9s (~70% reduction, 16 cores)** — well past the ≥40% target; network guard + frozen-goldens determinism intact under parallel. (Drift-noise console-cleanup slice landed earlier as `1c7154f`.) 414 backend + 232 frontend green. |
| 2026-06-11 | US-21.4 | Golden pipeline determinism — the dashboard goldens no longer depend on the live FMP cache. Discovered the root churn: `render_dashboard_goldens_text` drove `run_imported_dashboard_history`, which built a live `MarketDataService` and pulled benchmark + per-symbol histories whose *adjusted closes re-adjust over time* (dividends/splits) — so the goldens differed per machine and per fetch, and bare `pytest` needed a warm cache or `SKIP_GOLDEN_FRESHNESS_CHECK=1`. Fix: (1) added a keyword-only `market_data` injection seam to `run_imported_dashboard_history` (production callers unchanged → live service). (2) New `app/scripts/frozen_market_data.py`: `FrozenMarketData` replays a committed JSON fixture and **raises `FrozenMarketDataMiss`** on an absent (symbol, window) — a stale fixture fails loudly instead of degrading to a wrong "unavailable" golden; `RecordingMarketData` wraps a real service to (re)capture. (3) New committed fixture `app/scripts/golden_market_data.json` (24 series + SPY verified-benchmark meta), captured once via the new `export_dashboard_goldens --capture` mode. (4) `render_dashboard_goldens_text` now defaults to the frozen provider → deterministic, network-free; the conftest freshness fixture inherits this (no env var, no warm cache needed). Goldens regenerated once from the frozen capture (one-time content shift from adjusted-price drift; frontend vitest goldens stay green because expected values + fixture regenerate together). +4 `test_golden_pipeline_determinism.py` tests. **414 backend + 232 frontend green offline with zero env vars**; `git status` clean after `run_all_tests.py`. |
| 2026-06-10 | US-21.3 | Engine response-integrity property test. New `test_engine_response_integrity.py`: (1) parametrized strict-JSON check over **8 engine routes** (stress, drawdown, distribution, drift, attribution, correlation/multi, correlation/intra, provenance) — each driven by a standard fixtures portfolio with its own per-engine `MarketDataService` mock; a 200 is the property (starlette's encoder raises on NaN/inf, which WAS both 2026-06-10 bugs). (2) **Self-policing coverage check**: introspects the FastAPI route table — any new `POST /engines/*` route must be parametrized or explicitly waived with a reason (waivers: exposure / diagnostics / dashboard-history, golden-pinned heavier contracts; stale waivers also fail). risk.py audit found the same NaN leak as attribution (`round(coefficients[...])` passes NaN into rolling loadings/R²/residual-vol) → fail-closed isfinite→None guard in `_build_rolling_factor_loadings` + NaN-injection regression in `test_analytics.py`; methodology §Statistical Factor Model gained the degenerate-window→null-never-NaN edge-case rule. +10 tests. 410 backend pass, fully green. |
| 2026-06-10 | US-21.2 | Shared test-fixtures module. New `app/tests/fixtures.py` (+ `app/tests/__init__.py` making the dir a package): `imported_snapshot()` / `position()` (the 422-proof `ImportedPortfolioSnapshot` shape, round-trip-validated against the real schema), `price_rows()` / `price_rows_from_returns()`, and `install_market_data_mock(mocker, target_module, …)` (engine-module-targeted MarketDataService mock with real `last_fetch_meta`). Migrated the three dict-based duplicate sets (`test_correlation_engine`, `test_intra_correlation_engine`, `test_provenance_engine`) to thin wrappers over the shared module; behaviour + counts unchanged. +3 `test_fixtures.py` tests; write-tests skill gained the mandatory-fixtures section. |
| 2026-06-10 | US-21.1 | Deterministic suite landed — **first fully-green backend run (397 passed, 0 failed) since Epic 17**. (1) New conftest autouse fixture `_mock_risk_engines_market_data` mocks `MarketDataService` in the stress / drawdown / distribution engines with the existing deterministic synthetic rows — the 4 "real portfolio" tests now pass offline with original assertions intact. (2) New `pytest.ini`: `pytest-socket` guard (`--disable-socket --allow-hosts=127.0.0.1,::1 --allow-unix-socket`) blocks any real network connection — a test that forgets to mock fails loudly with `SocketConnectBlockedError`; loopback (in-process TestClient / Windows asyncio socketpairs) and file I/O unaffected. `live_data` marker registered and **deselected** by default (`-m "not live_data"`). `pytest-socket` added to requirements. +3 guard tests (`test_network_guard.py`: external blocked, marker deselection pinned, loopback+file-I/O pass). write-tests skill gained a "No live network in tests" policy section. Test-layer only — no production code change. |
| 2026-06-10 | — | Epic created from a testing-architecture review prompted by the attribution NaN-500 (a bug class no test guarded) and by recurring friction in Epics 16–20: 4 live-FMP tests failing offline for weeks, goldens churn requiring `git checkout` before commits, exact-set assertions breaking twice on additive changes, fixture duplication across ~7 files, 10 frontend tests pinned to an implicit default. PRD authored with five-story plan; US-21.1 (deterministic suite + network guard) authored and ticketed. |

---

## Completed Epic: Epic 20 — Market-Data Cache Efficiency & Control

**PRD:** [`docs/product/prd/epic-20-market-data-cache-efficiency.md`](product/prd/epic-20-market-data-cache-efficiency.md)

### Goal

Cut FMP overuse and latency by making the **local** cache smarter (range
normalization, in-memory layer, parallel fetch) and giving the user cache
visibility + a clear button. No Redis (local-first desktop; wouldn't fix the
core redundant-range issue).

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-20.1 | Cache stats + clear (route + UI) | Done |
| US-20.2 | History range normalization (FMP-call reduction) | Done |
| US-20.3 | In-memory layer + parallel fetch (latency) | Done |

Recommended build order: 20.1 → 20.2 → 20.3.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-11 | US-20.3 | In-memory layer + parallel fetch — the latency win; **closes Epic 20**. (A) `JsonFileCache` gained a process-level in-memory memo (`_MEMORY_CACHE`, lock-guarded, keyed by `(absolute_path, mtime_ns)` → parsed envelope): repeated reads of the same cache file across an analysis's ~7 engines skip the disk read + `json.loads` after the first; self-invalidating on any write (mtime bump), shared across the separate per-engine `JsonFileCache` instances, and cleared per-test by an autouse `_clear_cache_memory` fixture for determinism. (B) `MarketDataService.get_historical_prices_for_symbols` now fetches symbols concurrently via a bounded `ThreadPoolExecutor` (`max_workers=min(8, n)`); the lazy `_yfinance()` build is lock-guarded; per-symbol `last_fetch_meta` writes are race-free; result dict is reassembled in deterministic canonical-symbol order. Pure performance — bytes/TTL/trust/`last_fetch_meta` unchanged; goldens untouched (`FrozenMarketData` bypasses the seam). Measured: repeated read of a ~500KB payload **737ms → 11ms (~65× on the read path)**; 12-symbol fetch at 50ms I/O each **600ms → 102ms (~6×)**. +9 tests (6 `test_cache.py`, 3 `test_market_data.py`); hardened the pre-existing `max_age=0` stale test to a deterministic past-`fetched_at` (the memo made the 0-second boundary timing-flaky). 430 backend + 232 frontend green under `-n auto`; tsc clean; `git status` clean. |
| 2026-06-11 | US-20.2 | History range normalization — the FMP-call reduction. `MarketDataService` now widens every history request to a deterministic calendar-year-quantized superset range (`_canonical_history_range`), fetches that one range (so all requests in the same year-span share a single FMP cache key / call), then slices rows back to the caller's exact window (`_slice_price_rows`). Applied to `get_historical_prices` (FMP candidates + yfinance fallback + proxy + FX + `…_for_symbols`) and the verified-benchmark direct path (`get_direct_verified_benchmark_history`). Output is byte-identical to a direct `(from,to)` fetch — slicing is exact. No schema/methodology/trust change; `last_fetch_meta` unchanged. +8 `test_market_data.py` tests (quantization, slicing, shared-cache-key on overlapping windows, direct-window equivalence, empty-window fail-closed, yfinance-fallback slicing, benchmark canonical sharing + meta parity); 2 benchmark tests + 1 intra-correlation NaN-seam test updated (the latter anchored its synthetic bars to `date.today()` so they land in the engine's requested window — slicing now correctly enforces the window). Goldens untouched (`FrozenMarketData` bypasses the seam). 422 backend + 232 frontend green; tsc clean; `git status` clean after `run_all_tests.py`. |
| 2026-06-10 | hotfix | **Critical: attribution 500 (NaN not JSON-compliant).** A degenerate rolling window made the OLS solve return a non-finite beta → NaN contributions that silently passed the reconciliation check (NaN comparisons are always False) and broke JSON serialization (`ValueError: Out of range float values are not JSON compliant: nan`) → `POST /engines/attribution/run` 500. Surfaced after the attribution time-span widening (more windows → more degenerate ones). Fix in `analytics/attribution.py`: skip any date whose computed `r_p`, residual, betas, f* or contributions are non-finite (fail-closed — omit, never emit NaN). +1 regression test (injects a NaN beta; asserts `json.dumps(..., allow_nan=False)` succeeds). |
| 2026-06-05 | — | Epic created from a cache review. Found the dominant FMP-overuse cause is date-range fragmentation (each engine fetches overlapping ranges → distinct cache keys), plus no in-memory layer, sequential fetches, and no cache route/UI. Decision: enhance the local file cache (range-normalization + memo + parallel + control surface); **no Redis** (local-first; doesn't fix the range issue). Three-story plan; US-20.1 (stats + clear) authored first to also provide the observability used to validate 20.2/20.3. |

---

## Completed Epic: Epic 19 — Instrument Identity Integrity

**PRD:** [`docs/product/prd/epic-19-instrument-identity-integrity.md`](product/prd/epic-19-instrument-identity-integrity.md)

### Goal

Detect and surface ticker→fund mislabels (like the `DFND` case) by cross-checking
the registry's fund name against the broker statement's own description, instead
of silently trusting the registry.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-19.1 | Instrument description-consistency check | Done |
| US-19.2 | ISIN-keyed registry identity | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-11 | US-19.2 | ISIN-keyed registry identity — **closes Epic 19**. The registry's instrument definitions gained an optional `isin`, seeded with **authoritative values extracted from the committed real statements** for the 16 registry-known UCITS/identity-sensitive lines (e.g. `DFND → IE000U9ODG19` iShares Global Aerospace & Defence — distinct from the portfolio's own `DFNS → IE000YYE6WK5` VanEck Defense, the exact near-miss pair). `detect_instrument_identity_mismatches` now checks ISIN evidence first (definitive ISO 6166 equality, normalized) alongside the US-19.1 description heuristic; `InstrumentIdentityMismatch` gained `kind` (`description`/`isin`) + `statement_isin`/`expected_isin` (TS + contract doc mirrored). Evidence-gated: holdings lacking an ISIN on either side are skipped — absent evidence is never a pass or a failure. Surfaced through both channels: new `instrument_isin_registry_consistency` admission check (`warn`/`degraded`, flag-only) and the Data Sources panel (renders both ISINs). New `test_registry_isin_integrity.py` guard pins registry-seed ⇄ statement agreement (a typo'd seed fails the suite) and proves zero false positives on re-importing the real statements. +9 backend, +3 frontend tests; the analyze-snapshot route's exact check-set assertion converted to superset per the US-21.5 convention. 439 backend + 235 frontend green; tsc clean. |
| 2026-06-05 | US-19.1 | Instrument description-consistency check. New pure detector `app/services/instrument_identity.py` (`detect_instrument_identity_mismatches`) flags registry-known holdings whose broker description is **identity-disjoint** from the registry fund name (conservative token comparison; catches different-issuer mislabels, ignores formatting/share-class noise). Surfaced two ways: a new `instrument_description_registry_consistency` Import Admission check (`warn`/`degraded`), and — because the admission summary isn't rendered today — a visible "⚠ Possible identity mismatch" line on the Exposure **Data Sources panel** (`ProvenanceResult.identity_warnings`, computed in `provenance_engine`). Schema + TS `InstrumentIdentityMismatch`. Flag only — never auto-corrects. +6 detector + 3 admission + 2 engine + 2 panel tests; 2 pre-existing exact-check-set assertions (clean-pass, analyze-snapshot route) updated for the additive check. 227 frontend + backend green (only the 4 pre-existing FMP-offline failures remain); `npx tsc --noEmit` clean; audit 5/5. |
| 2026-06-05 | — | Epic created after the `DFND` mislabel (registry said "VanEck Defense"; user's holding is iShares Global Aerospace & Defence). PRD authored; description-consistency flag chosen over ISIN (providers don't return ISINs for these EU funds). Grounding found the Import Admission Review summary is computed/persisted but not rendered, so US-19.1 surfaces the flag on the visible Data Sources panel (US-18.2) in addition to the persisted admission check. |

---

## Completed Epic: Epic 18 — Secondary Market-Data Provider

**PRD:** [`docs/product/prd/epic-18-secondary-market-data-provider.md`](product/prd/epic-18-secondary-market-data-provider.md)

### Goal

Add **yfinance as a fallback market-data provider** behind `MarketDataService`
(FMP first, Yahoo when FMP returns 402/empty) so European UCITS ETFs stop being
excluded from history-based analytics — with an explicit, **visible data-provenance**
dimension (`fmp` vs `yfinance`) per the traceability guardrail. Verified POC:
7 of 10 currently-excluded UCITS tickers resolve immediately via Yahoo with
adjusted-close data.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-18.1 | yfinance fallback provider + data provenance | Done |
| US-18.2 | Portfolio-level data-sources indicator (one Exposure panel) | Done |
| US-18.3 | Defense-ETF Yahoo symbol mapping (DFND/DEFS/IDFN) | Done |
| US-18.4 | Sanitize non-finite price rows (bugfix) | Done |

Recommended build order: 18.1 → 18.2 → 18.3. **Epic 18 complete** (+ US-18.4 bugfix follow-up).

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-10 | US-18.4 | **Critical bugfix: correlation 500s from NaN price bars.** Cache scan found 38 `history_yf` entries with `price: NaN` (2026-06-09 bars for the Yahoo-sourced UCITS) — pandas encodes missing bars as `float('nan')`, which passed `YFinanceClient`'s `is None` check; downstream, `pearson()`'s variance guard passes NaN, so `/engines/correlation/{intra,multi}` 500'd on JSON encode. Two-layer fix: (1) `yfinance_client._fetch` skips non-finite bars at the source; (2) new `MarketDataService._sanitize_price_rows` drops absent/non-finite-price rows on **every** history return path (FMP loop, yfinance fallback, direct-benchmark) — sanitization runs *before* the truthiness check so an all-bad result falls through to the next candidate/provider, and the 38 already-cached poisoned entries are neutralized without a cache clear. +5 tests incl. a route-level regression through the REAL MarketDataService asserting 200. 390 backend pass (only the 4 known offline failures, US-21.1's target). Backend-only. |
| 2026-06-05 | UX fix | **Factor Return Attribution time-span bug + 20d default.** The attribution engine fetched only `_lookback_calendar_days(window)` of history, so the 20d chart spanned just ~2 months (the rolling window was wrongly controlling the *displayed* range). Fixed `attribution_engine.py` to fetch a fixed display span (`ATTRIBUTION_DISPLAY_TRADING_DAYS=252`) **plus** the window, so every window shows the same ~1-year cumulative series; the window now only sets each rolling estimate's length. +1 engine test (mock respects the date range; pins the 20d series spans the full range). Separately, made **20d the default** window on all 20/60/252 charts (FactorAttributionCard, RollingCorrelationChart, FactorDriftSummaryCard, IntraCorrelationHeatmap); updated the affected component tests. 225 frontend + 369 backend pass (only the 4 pre-existing FMP-offline failures remain); `npx tsc --noEmit` clean. |
| 2026-06-05 | US-18.3 (fix 2) | Added missing exchange-suffix candidates for two more UCITS holdings the user still saw excluded: `ICOM` → `("ICOM.L","ICOM")` (iShares Diversified Commodity Swap UCITS ETF, LSE/USD) and `VDST` → `("VDST.L","VDST")` (Vanguard U.S. Treasury 0-1 Year Bond UCITS ETF, LSE/USD) — both verified by yfinance `longName`+currency. Their rules previously had only the bare ticker (404 on both providers). Existing ICOM proxy-fallback test updated for the new candidate order; +1 resolution test. Backend resolution tests green. |
| 2026-06-05 | US-18.3 (fix) | **Correction:** the registry mislabeled `DFND` as "VanEck Defense UCITS ETF"; the user confirmed their `DFND` is the **iShares Global Aerospace & Defence UCITS ETF (LSE, GBP)** = `DFND.L`. US-18.3's original mapping was inverted accordingly: `DFND` → `("DFND.L","DFND")` (the iShares A&D fund); the VanEck lines (`DFNS.L`/`DFEN.DE`/`DFNG.L`) are now the *excluded* wrong-fund symbols. Registry display name fixed to "iShares Global Aerospace & Defence UCITS ETF"; guard test inverted; fmp-data skill table corrected. Lesson: verify ticker→fund identity against the broker statement (ISIN/name), not just the registry label. Backend green (resolution tests pass). |
| 2026-06-05 | US-18.2 | Portfolio-level data-sources indicator. New `app/schemas/provenance.py` + `app/services/provenance_engine.py` + `POST /engines/provenance/run`: probes a short window per holding and reads `MarketDataService.last_fetch_meta` vendor to group holdings into FMP (primary) / Yahoo (secondary) / unpriced — provider identity is window-independent so the probe is cheap (cached). New self-fetching `DataSourcesPanel` on the Exposure tab renders the grouping once at the portfolio level (design decision: single indicator over per-card markers; the intra card keeps its inline marker). TS types + `runProvenanceEngine` adapter; panel added to the design-system audit set. New `docs/contracts/provenance-fields.md`; system-architecture + current-product-state updated. Provenance is a **source label, not a trust claim**. +5 backend (4 engine + 1 route) + 5 frontend (4 panel + 1 adapter); 225 frontend + 367 backend pass (only the 4 pre-existing FMP-offline failures remain); `npx tsc --noEmit` clean; audit 5/5; goldens untouched. **Epic 18 complete.** |
| 2026-06-05 | US-18.3 | Defense-ETF Yahoo symbol mapping. Investigation (yfinance `longName`) showed only `DFND` was a real gap and carried a correctness trap: `DFND.L` is **iShares Global Aerospace & Defence UCITS ETF**, a *different* fund — while the `DFND` rule had only the bare (404ing) `DFND` candidate. Fixed the `DFND` `SymbolResolutionRule` to the real VanEck Defense lines `("DFNS.L","DFEN.DE","DFNG.L","DFND")` (USD first; never `DFND.L`), proxies `ITA/PPA` preserved. `DEFS` (`DEFS.L`) and `IDFN` (`IDFN.L`) were already correct via US-18.1 — the earlier "3 deferred" was a probe artifact (2024 date range predating the 2024/25 fund launches). +3 backend resolution tests incl. a wrong-fund guard pinning that no `DFND` candidate list ever contains `DFND.L`. fmp-data skill UCITS table updated. No methodology/contract/frontend change. Backend green (only the 4 pre-existing FMP-offline failures remain). |
| 2026-06-05 | US-18.1 | yfinance fallback provider + data provenance. New `app/clients/yfinance_client.py` (`YFinanceClient.get_historical_price_light` → FMP-shaped rows with `adjClose`; lazy yfinance import; JsonFileCache namespace `history_yf` incl. negative caching; all errors → `[]`). `MarketDataService.get_historical_prices` gains a yfinance fallback after the FMP candidate loop (same suffixed candidates, never proxies), recording `last_fetch_meta[...]['vendor']` ∈ {`fmp`,`yfinance`}; FMP-first path byte-for-byte unchanged. `IntraCorrelationResult` + TS gained `yahoo_sourced_symbols`; the engine populates it from `last_fetch_meta`; `IntraCorrelationHeatmap` renders a visible "◆ N holdings via Yahoo Finance (secondary source): …" marker. `yfinance` added to `requirements.txt`. New autouse conftest fixture disables the fallback by default so no test hits the network; 5 pre-existing `test_market_data.py` proxy assertions updated for the additive `vendor` key. Docs: system-architecture gained a "Market-data providers and data provenance" subsection; `intra-correlation-fields.md` + current-product-state updated. +11 backend (5 yfinance client + 4 MDS fallback + 2 engine provenance) + 2 frontend; 220 frontend + 359 backend pass (only the 4 pre-existing FMP-dependent stress/drawdown/distribution tests fail offline — unrelated); `npx tsc --noEmit` clean; audit 5/5; goldens untouched. Recovers 7/10 of the user's excluded UCITS ETFs; the 3 defense ETFs (DFND/DEFS/IDFN) are US-18.3. |
| 2026-06-05 | — | Epic created after a user hit "10 holdings excluded: insufficient history" (all European UCITS ETFs FMP's plan 402s). yfinance POC confirmed Yahoo serves the suffixed symbols (VUAA.L, SXRV.DE, …) with adjusted close. PRD authored; three-story plan (fallback provider + provenance → broaden badges → defense-ETF symbol mapping). US-18.1 authored and ticketed. |

---

## Completed Epic: Epic 17 — Intra-Portfolio Correlation

**PRD:** [`docs/product/prd/epic-17-intra-portfolio-correlation.md`](product/prd/epic-17-intra-portfolio-correlation.md)

### Goal

Answer "what is actually diversifying me?" on the Exposure tab with a holdings ×
holdings Pearson correlation heatmap (selectable 20d/60d/252d window) plus
diversification summary stats — reusing the existing synthetic-history machinery
and `pearson()` helper. No new data provider.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-17.1 | Pairwise correlation matrix engine + heatmap | Done |
| US-17.2 | Diversification summary metrics (DR + ENB; introduces numpy) | Done |
| ~~US-17.3~~ | ~~Docs, contracts, roadmap close-out~~ | **Cancelled** (docs reconciled per-story via update-docs) |

Recommended build order: 17.1 → 17.2.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-05 | US-17.2 | Diversification summary metrics added to the Intra-Portfolio Correlation card. `analytics/correlation.py` gained `population_stdev()`, `diversification_ratio()` (Choueifaty & Coignard 2008, pure-Python), and `effective_number_of_bets()` (Meucci 2009, numpy `eigvalsh` imported lazily; null when matrix incomplete / <2 holdings / non-PSD). `intra_correlation_engine.py` computes current-weight-renormalised weights, per-holding σᵢ, and σ_p from the **constant-weight** synthetic portfolio return series `Σwᵢrᵢ` (coherent DR denominator, guarantees DR≥1; deviates from the story's `_build_synthetic_snapshot_history_states` hint for self-consistency with the displayed top-N universe) → populates `diversification_ratio` + `effective_number_of_bets` on `IntraCorrelationResult`. Schema + TS mirror extended; `IntraCorrelationHeatmap` summary strip gained "Diversification Ratio" (2-dp) and "Effective number of bets" (1-dp), each "Unavailable" when null. numpy added to `requirements.txt`. Contract + methodology reconciled (ENB no longer "later story"; σ_p constant-weight definition). +8 backend (6 analytics + 2 engine; route field-presence folded into the existing shape test) + 3 frontend; 218 frontend + 348 backend pass (the 4 pre-existing FMP-dependent stress/drawdown/distribution failures persist — unrelated); `npx tsc --noEmit` clean; audit 5/5; goldens reverted. **Epic 17 complete.** |
| 2026-06-05 | US-17.1 | Pairwise correlation matrix engine + heatmap landed on the Exposure tab. Extended `analytics/correlation.py` with `pairwise_correlation_matrix()` (reuses `pearson()`; symmetric, diagonal 1.0, null below 20-overlap / zero-variance) + `average_pairwise_correlation()`. New `services/intra_correlation_engine.py` (reuses `_returns_from_price_series` + `_lookback_calendar_days`; per-symbol returns over the SPY grid; cash/non-priceable/no-history holdings excluded → `excluded_symbols`; weight-ranked, top-15 cap; most/least pair). New `POST /engines/correlation/intra` on the existing correlation router; new `schemas/intra_correlation.py`. Frontend: TS types + `runIntraCorrelationEngine` adapter; new `IntraCorrelationHeatmap` card (color-blind-safe heatmap — numeric ρ + ▲▲/▲/•/▼/▼▼ glyph over `--color-corr-*`; muted diagonal; "n/a" null cells; summary strip; excluded caption; Synthetic badge; EmptyState), added to the design-system audit set and wired into `ExposurePanel`. Contract `docs/contracts/intra-correlation-fields.md`. +14 backend (6 analytics + 6 engine + 2 route) + 10 frontend (9 card + 1 adapter); 215 frontend green; `npx tsc --noEmit` clean; audit 5/5; goldens reverted. (Pre-existing FMP-dependent stress/drawdown/distribution "real portfolio" tests fail in the offline sandbox — confirmed identical on base, unrelated to this story.) DR + ENB remain US-17.2. |
| 2026-06-05 | — | Epic created from a `quant-research` brief (intra-portfolio correlation). Methodology extended with §Intra-Portfolio Correlation (pairwise Pearson matrix reusing `pearson()`; average pairwise correlation; Diversification Ratio — Choueifaty & Coignard 2008; Effective Number of Bets — Meucci 2009; Markowitz 1952 grounding; numpy approved for the ENB eigendecomposition). PRD authored; three-story plan. US-17.1 authored and ticketed (schema → analytics → service+route → types/adapter → heatmap card → docs). |

---

## Completed Epic: Epic 16 — Factor Drift Visualization

**PRD:** [`docs/product/prd/epic-16-factor-drift-visualization.md`](product/prd/epic-16-factor-drift-visualization.md)

### Goal

Answer "how have my factor exposures *moved*?" on the Exposure tab with a
compact, ranked **Factor Drift Summary** card — per-factor delta (latest
loading − reference loading) over a selectable rolling window, reusing the
rolling loadings the engine already computes. Net-new value, no new backend.
This ships the delta-indicator card parked during Epic 15.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-16.1 | Factor Drift Summary card | Done |

Single-story epic (quick-win follow-up).

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-04 | US-16.1 | Factor Drift Summary card landed on the Exposure tab. New `FactorDriftSummaryCard.tsx` (frontend-only — derives the factor model from the Exposure `result` via `buildExposureFactorModel`, no backend): for the selected window it computes per-factor `drift = β_k(latest) − β_k(reference)` over the trimmed `rolling_loadings_<window>` series, ranks factors by `|drift|` desc (ties by label), and renders divergent magnitude bars (positive right of a zero baseline, negative left) with a signed value + ▲/▼ marker so direction survives color-blindness. Factors null at the reference/latest endpoints are excluded (never 0-imputed); fails closed to an EmptyState when the window has insufficient history. Uses Epic 12 primitives (`CardShell`/`TrustBadge`/`WindowSelector`/`EmptyState`) + factor-palette + value tokens (no hex/px); added to the `designSystem.audit.test.ts` scanned set (5/5 audit green). Wired into `ExposurePanel` after the factor attribution card. Methodology §Statistical Factor Model gained a `### Factor Loading Drift` subsection (Ferson & Schadt 1996; Jagannathan & Wang 1996); new `docs/contracts/factor-drift-fields.md`. **Incidental fix**: annotated `decomposedPayload()` return type in `DrawdownAnalyticsCard.test.tsx` to repair a pre-existing (Epic 15) `tsc` narrowing error unrelated to this story. +8 vitest (ranking, delta = latest−reference, null-endpoint exclusion, window re-rank, two EmptyState paths, badge tooltip, color-blind signal). 205 frontend (+8) green; backend unchanged (330); `npx tsc --noEmit` clean; no dashboardGoldens regen. **Epic 16 fully closed.** |
| 2026-06-04 | — | Epic created from the Epic 15 parked backlog candidate ("complementary Factor Drift Summary delta-indicator card"). PRD authored; single frontend-only story (`FactorDriftSummaryCard` on the Exposure tab; ranked per-factor `latest − reference` drift bars; 20d/60d/252d window; Synthetic trust badge; methodology §Factor Loading Drift + `factor-drift-fields.md` contract at close-out). |

---

## Completed Epic: Epic 15 — Position-Level Analytics

**PRD:** [`docs/product/prd/epic-15-position-level-analytics.md`](product/prd/epic-15-position-level-analytics.md)

### Goal

Answer "which positions drove that?" for every Risk-tab metric by
decomposing drawdown episodes into per-position contributions
(arithmetic Brinson under synthetic-history convention) AND
visualize the existing rolling factor loadings on the Exposure tab
so researchers can see how their factor mix has drifted over time.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-15.1 | Drawdown decomposition engine + schema | Done |
| US-15.2 | Drawdown card "Contributors" drawer | Done |
| ~~US-15.3~~ | ~~Factor loading drift chart~~ | **Cancelled** (existing card covers it) |
| US-15.4 | Epic 15 docs close-out | Done |

Recommended build order: 15.1 → 15.2 → 15.3 → 15.4.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-01 | — | Epic created. `quant-research` brief covering arithmetic Brinson-style position decomposition (Brinson Hood Beebower 1986; Goldberg & Mahmoud 2017 §3); methodology extended with `### Drawdown episode decomposition` subsection under §Wealth Index and Drawdown; PRD authored; four-story plan (decomposition engine → drawer UI → factor drift chart → docs close-out). |
| 2026-06-04 | US-15.4 | Epic 15 docs close-out. Extended `docs/contracts/risk-fields.md` with the decomposition fields: 4 new rows on `DrawdownEpisode` (`top_contributors`, `other_contribution_pct`, `decomposition_residual_pct`, `decomposition_trust`); new `EpisodeContributor` field table; "Decomposition trust state semantics" + "Decomposition edge cases" subsections; new "Example response (with decomposition)" snippet showing both synthetic and partial trust variants with realistic 2022 + 2023 drawdown episode JSON. Methodology subsection `### Drawdown episode decomposition` verified against shipped `decompose_drawdown_episode(daily_states, episode, top_n=5)` in `app/analytics/drawdown.py` — function signature, `Implementation:` path, and reconciliation invariant text all match. `current-product-state.md` Risk-tab Drawdown bullet extended with the Contributors drawer description. **Epic 15 fully closed**: 3 Done (US-15.1, US-15.2, US-15.4) + 1 Cancelled (US-15.3 — existing `RollingFactorLoadingsCard` on Dashboard tab already covered the factor-drift use case). 330 backend + 197 frontend stay green (no code changes); `npx tsc --noEmit` clean; no dashboardGoldens regen. |
| 2026-06-04 | US-15.2 | Drawdown card "Contributors" drawer landed. `DrawdownAnalyticsCard`'s episodes table gained a leftmost expand-toggle column; clicking a row reveals a sibling drawer `<tr>` (colSpan=7) with the per-episode contributors sub-table (Symbol / Weight @ Peak / Return / Contribution). Single-open semantics: clicking another row swaps focus. New `ContributorsDrawer` sub-component formats per-cell sign-coloured tabular-nums via design tokens (no hex, no px). "Other" aggregate row renders when `\|other_contribution_pct\| >= 0.01`; "Residual (unexplained)" row renders when `\|residual_pct\| > 0.05` (floating-point noise threshold); both hidden below thresholds. Partial-trust caption ("Partial: N.N% unexplained (some positions missing price history).") appears above the sub-table when `decomposition_trust='partial'`. Toggle disabled (with descriptive aria-label + tooltip) when `decomposition_trust='unavailable'` or `top_contributors=null`. Responsive: `.drawdown-contributor-secondary` CSS class hides Weight + Return columns below 520px viewport (new `@media` rule in `styles.css`). +6 vitest pinning toggle render, expand/collapse, swap-focus, partial caption, disabled state, Other/Residual visibility thresholds. 330 backend + 197 frontend (+6) green; `npx tsc --noEmit` clean; design-system audit 5/5 green; no dashboardGoldens regen. |
| 2026-06-01 | US-15.1 | Drawdown decomposition engine landed. New `decompose_drawdown_episode(daily_states, episode, top_n=5)` in `app/analytics/drawdown.py` implements arithmetic Brinson-style attribution under the synthetic-history convention: `contribution_pct = (V_i(t_peak) / V_p(t_peak)) × (p_i(t_trough) / p_i(t_peak) − 1) × 100`. Iterates `state.positions` only — cash naturally contributes 0 per methodology Contract rule. New `EpisodeContributor` schema + 4 nullable-default fields on `DrawdownEpisode` (`top_contributors`, `other_contribution_pct`, `decomposition_residual_pct`, `decomposition_trust ∈ {'synthetic','partial','unavailable'}`). Wire-up in `drawdown_engine.run_drawdown_engine` decomposes each top-N episode via `model_copy(update=...)`. Reconciliation invariant `|magnitude − (sum_top + other + residual)| < 1e-9` enforced as defensive ValueError post-condition. TS mirror types added (`EpisodeContributor`, `DrawdownDecompositionTrust`, extended `DrawdownEpisode`); all nullable so existing fixtures stay valid. +9 backend tests (7 analytics + 2 engine); 330 backend (+9) + 191 frontend green; `npx tsc --noEmit` clean; no dashboardGoldens regen. |

---

## Completed Epic: Epic 14 — Post-Epic-13 Bug Sweep

**PRD:** [`docs/product/prd/epic-14-post-epic-13-bug-sweep.md`](product/prd/epic-14-post-epic-13-bug-sweep.md)

### Goal

Sweep three independent bugs that surfaced from running the
shipped Epic 13 product: overlay symbol-collision in
"Add Statement", DrawdownAnalyticsCard missing smart-default
window fallback, and Freedom24 unknown-symbol "Other" sector
mis-classification.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-14.1 | Fix overlay symbol collision (sum, don't replace) | Done |
| US-14.2 | DrawdownAnalyticsCard smart-default window fallback | Done |
| US-14.3 | Freedom24 FMP company-profile enrichment for unknown symbols | Done |

Recommended build order: 14.1 → 14.2 → 14.3.

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-06-01 | — | Epic created from post-Epic-13 user-feedback bug sweep. PRD authored; three-story plan (overlay collision → drawdown smart-default → Freedom24 FMP enrichment). |
| 2026-06-01 | US-14.3 | New `app/services/instrument_enrichment.py` with `enrich_imported_instruments(snapshot, market_data)`. Fast-path skips symbols in static `INSTRUMENT_DEFINITIONS` (no FMP call). Slow-path: for unknown symbols with bare-ticker descriptions, calls `MarketDataService.get_company_profile` and populates `description` (= FMP `companyName`) + `instrument_type` (= `"ETF"` when `isEtf=True`, else `"STOCK"`). Asymmetric `instrument_type` rule: FMP can upgrade STOCK→ETF but a non-empty parser declaration always wins. Fail-graceful on FMP `None` or any exception. Wired into Freedom24 parser's `import_statement` with an outer try/except so any FMP failure leaves the import flow intact. Existing description-based `classify_imported_instrument` fallback in `InstrumentRegistry` consumes the enriched description and produces correct sectors (e.g. "Vanguard Total Stock Market ETF" → Broad Market) — verified by a round-trip test. +11 backend pytest (7 enrichment unit + 3 Freedom24 integration + 1 registry round-trip). 321 backend (+11) + 191 frontend tests green; `npx tsc --noEmit` clean; dashboardGoldens.ts unchanged (bundled fixtures use known-registry tickers). **Epic 14 fully closed.** |
| 2026-06-01 | US-14.2 | `DrawdownAnalyticsCard` now auto-falls-back through the window cascade (1260 → 756 → 252 → Max) when the engine returns `trust='unavailable'`, so portfolios with shorter FMP history render on first load instead of forcing the user to manually click each window. New `hasUserOverriddenWindow` state preserves user intent — once they click a WindowSelector button, that window is fetched single-shot regardless of result (no cascade). Snapshot change resets the override flag. Cascade respects existing `let cancelled = false` cleanup so mid-cascade snapshot changes abort cleanly. Network errors stop the cascade (failure isn't window-specific). The displayed window in WindowSelector is derived from `response.window_trading_days` when cascade lands on a different window — avoids re-triggering the effect on `setSelectedWindow`. +4 new vitest pinning: auto-fallback 1260→756 on unavailable; full 4-window exhaustion → EmptyState; user click disables further cascade; happy path doesn't over-fetch. Existing 9 DrawdownAnalyticsCard tests stay green; existing unavailable test updated from `mockResolvedValue` to `mockImplementation` (cascade triggers multiple fetches; Web Response bodies are single-use). 310 backend + 191 frontend (+4) green; `npx tsc --noEmit` clean. |
| 2026-06-01 | US-14.1 | `overlayImportedSnapshot` (in `apps/desktop/src/features/portfolio/portfolioSnapshot.ts`) now SUMS `marketValue` + `quantity` when a symbol appears in both base and imported statements (was REPLACE — silently lost the base statement's dollars on any ticker overlap). Parallel fix for cash balances: sum amounts when the same currency appears in both. Quantity null-handling preserves fail-closed semantics: both-null stays null (no fabricated 0); one-null treats null as 0 in the sum. Two existing US-10.2 overlay tests that accidentally pinned the REPLACE behaviour (`does not duplicate symbols when the same symbol appears in two overlays` and the 3-broker USD cash assertion) updated to assert the SUM, with inline US-14.1 comments. +6 new vitest pinning marketValue sum, quantity sum, both null-cases, sector preservation, and cash-balance sum. 310 backend + 187 frontend (+6) green; `npx tsc --noEmit` clean. No retroactive remediation for users who already overlaid overlapping statements — fix applies to future imports only; they'd need to re-import. |

---

## Completed Epic: Epic 13 — Risk Analytics Tab

**PRD:** [`docs/product/prd/epic-13-risk-analytics-tab.md`](product/prd/epic-13-risk-analytics-tab.md)

### Goal

Add a third tab, **Risk**, alongside Dashboard + Exposure, surfacing three
synthetic-history risk views: stress scenarios (factor-shock projection),
drawdown analytics (underwater curve + top-N episodes with recovery times),
and VaR / distribution analysis (histogram + percentile / tail-risk / shape
table). Two of the three engines already exist in `analytics/risk.py` but
are not surfaced; VaR is new methodology.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-13.1 | Risk tab + Stress Scenarios card | Done |
| US-13.2 | Drawdown Analytics card | Done |
| US-13.3 | VaR & Distribution card | Done |
| US-13.4 | UI density polish + trust-state + a11y verification | Done |
| US-13.5 | Docs close-out | Done |

Stories must be built in order (13.1 → 13.2 → 13.3 → 13.4 → 13.5).

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-31 | — | Epic created. `quant-research` brief covering Stress + Drawdown + VaR; methodology extended with §Value-at-Risk and Distribution + drawdown episode identification under §Wealth Index and Drawdown; PRD authored; five-story plan (Stress + tab plumbing → Drawdown → VaR → polish → close-out). |
| 2026-06-01 | US-13.1 | Third nav tab **Risk** wired into `App.tsx` (tab union + `appTabs` array + lazy-loaded panel). New `RiskPanel` mirrors `ExposurePanel` shell with `.risk-shell-stack` flex-column wrapper. New `StressScenariosCard` (3 scenario rows, sorted by abs magnitude desc, horizontal magnitude bar, color-coded pct, `Synthetic` TrustBadge, EmptyState on `trust='unavailable'`). Backend: `app/schemas/stress.py` (`StressEngineRequest` + `StressEngineResponse` wrapper), `app/services/stress_engine.py` (reuses `build_statistical_factor_model` + `build_stress_scenarios`; surfaces `trust='unavailable'` when factor model empty), `app/api/routes/stress.py` (`POST /engines/stress/run`). 268 backend (+5) + 155 frontend (+13) tests green; `npx tsc --noEmit` clean; design-system audit 5/5 green. |
| 2026-06-01 | US-13.2 | Second Risk-tab card: **DrawdownAnalyticsCard** with underwater curve (Recharts AreaChart fill = `--color-value-negative`) and top-5 episodes table (Peak / Trough / Recovery / Magnitude / Duration / Underwater; "Still underwater" italic for `recovery_date=null`). 4-option `WindowSelector` (252d / 756d / 1260d / Max). Self-fetching card with internal `[snapshot, window]` re-fetch. Backend: new `app/analytics/drawdown.py` (pure functions implementing the methodology §Drawdown episode identification greedy forward-walk algorithm), `app/schemas/drawdown.py`, `app/services/drawdown_engine.py` (reuses `_build_synthetic_snapshot_history_states` + `_build_wealth_index`; fails closed when < 20 obs), `app/api/routes/drawdown.py` (`POST /engines/drawdown/run`). `RiskPanel` extended to render both cards in the stack. RiskPanel tests refactored to URL-routed `vi.fn().mockImplementation` so concurrent card mounts work cleanly. 280 backend (+12) + 167 frontend (+12) tests green; `npx tsc --noEmit` clean; design-system audit 5/5 green. |
| 2026-06-01 | US-13.5 | Epic 13 docs close-out. New contract doc `docs/contracts/risk-fields.md` (450 lines) covering all three Risk-tab response shapes (Stress / Drawdown / VaR & Distribution): trust-class preamble, per-field tables (Backend type / TS mirror / UI surface / Nullability / Methodology ref), edge cases, example happy + unavailable JSON per engine. `financial-methodology.md` `Implementation:` subsections for §Stress Scenarios, §Drawdown episode identification, §Value-at-Risk and Distribution updated to cite shipped paths (`analytics/{stress→risk,drawdown,distribution}.py`, `services/{stress,drawdown,distribution}_engine.py`, `api/routes/{stress,drawdown,distribution}.py`) — removed "added in Epic 13" placeholder language. `current-product-state.md` updated: tab count "two → three"; new Risk section with three card bullets; route list expanded with `/engines/{stress,drawdown,distribution}` (now 12 route modules total); analytics module list updated. `CLAUDE.md` updated: "Product: three tabs" + tab table gains Risk row; doc-map adds `risk-fields.md` row; repo-layout `api/routes/`, `analytics/`, `services/` paths list expanded; Active PRD pointer flipped to Epic 13. **Epic 13 fully closed.** 294 backend + 181 frontend stay green; `npx tsc --noEmit` clean. |
| 2026-06-01 | US-13.4 | Density + a11y polish pass on the Risk tab. `RiskPanel` header rewritten from the bulky `<h2 className="panel-label">Risk Analytics</h2>` pattern to ExposurePanel's two-tier hierarchy (`<p className="panel-label">Risk</p>` + plain `<h2>Stress, drawdown, and tail-risk views</h2>`) so the page header no longer competes with the first card's title. `VarDistributionCard` `SectionHeader` slimmed: dropped `textTransform: uppercase` + `letterSpacing: 0.05em` + tightened top margin to `var(--space-sm)` so the three sections read as quiet group labels instead of loud chapter breaks. Trust-tooltip wording aligned across the two history-based cards (Drawdown + VaR/Distribution) — both now open with `"Synthetic: computed from current holdings × historical prices."` followed by a card-specific qualifier; Stress keeps its distinct factor-shock phrasing. Cross-card a11y audit confirmed all three cards inherit CardShell `role="region"` + `aria-labelledby`, both charts have descriptive `ChartShell` ariaLabels, both WindowSelectors pass `ariaLabelFn`, no color-only signal encoding. 2 new density-pin vitest (`risk_panel_header_uses_two_tier_hierarchy_not_bulky_h2`, `section_headers_render_compactly_without_uppercase_or_wide_letter_spacing`). 294 backend + 181 frontend (+2) green; `npx tsc --noEmit` clean; design-system audit 5/5 green. |
| 2026-06-01 | US-13.3 | Third Risk-tab card: **VarDistributionCard** with daily return histogram (Recharts BarChart; loss-tail bars `--color-value-negative`, rest muted; VaR-95 + Mean reference lines) and percentile / tail-risk / distribution-shape table (5/10/50/90/95 percentiles; VaR 95 / CVaR 95 / VaR 99; Mean / Std / Skew / Kurtosis-excess). 3-option `WindowSelector` (60d / 252d / 504d, default 252; no Max — VaR is window-pinned for interpretability). Backend: new `app/analytics/distribution.py` (pure-Python NIST-linear quantile, historical VaR, CVaR/Expected Shortfall, Fisher-Pearson skewness + excess kurtosis, 30-bin auto-fit histogram — no numpy / scipy), `app/schemas/distribution.py`, `app/services/distribution_engine.py` (enforces CVaR≥VaR coherence invariant; raises on violation per Acerbi & Tasche 2002 methodology contract), `app/api/routes/distribution.py` (`POST /engines/distribution/run`). VaR may be negative (no loss days in window) — surfaced as-is per methodology Contract rule; UI styles muted instead of red. `RiskPanel` extended to render all three cards in the stack. URL-routed `makeRoutedFetch` test helper extended for distribution. 294 backend (+14) + 179 frontend (+12) tests green; `npx tsc --noEmit` clean; design-system audit 5/5 green. |

---

## Completed Epic: Epic 12 — UI Polish & Design System

**PRD:** [`docs/product/prd/epic-12-ui-polish-design-system.md`](product/prd/epic-12-ui-polish-design-system.md)

### Goal

Turn the four new Exposure cards (drift, indexed return, rolling correlation,
factor attribution, multi-benchmark correlation) into a production-ready
surface backed by a small design system: tokens, shared primitive components,
accessibility baseline, and a `ui-polish` skill that lets the next analytics
card slot in consistently.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-12.1 | Design tokens + apply to the four Exposure cards | Done |
| US-12.2 | Primitive components + refactor cards | Done |
| US-12.3 | Accessibility + Recharts defaults (ChartShell) | Done |
| US-12.4 | `ui-polish` skill + Epic 12 close-out | Done |

Stories must be built in order (12.1 → 12.2 → 12.3 → 12.4).

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-28 | — | Epic created from UX pass over Epic 9/11 cards; PRD authored; four-story plan (tokens → primitives → a11y → skill) |
| 2026-05-28 | US-12.1 | Design tokens (`:root` block: 60+ tokens covering text/surface/border/correlation-sign/factor palette/spacing/typography/radius/border-widths); canonical `.attribution-trust-badge` CSS rule; refactored 5 card files to consume tokens; fixed RollingCorrelationChart dual-axis text overlap (YAxis width 44→64, margin right 56→72); audit regression test (`designSystem.audit.test.ts`, 3 tests) enforces no-hex / no-px in inline styles. 263 backend + 109 frontend green; `npx tsc --noEmit` clean. |
| 2026-05-28 | US-12.2 | Primitive components extracted: `<CardShell>`, `<TrustBadge>`, `<WindowSelector>` (generic), `<EmptyState>`, `<LoadingState>`, `<ErrorState>` at `apps/desktop/src/app/primitives/`; refactored 5 cards to import + use primitives (deleted ~70 lines of duplicated JSX across them); audit test grew 3→4 tests (added "Synthetic" single-source-of-truth check + import-based badge check). New token: `--color-error` / `--color-error-border`. 263 backend + 132 frontend green (+23 frontend); `npx tsc --noEmit` clean. |
| 2026-05-29 | US-12.3 | Chart defaults primitive (`chartDefaults.ts` + `ChartShell.tsx`) + accessibility pass. 3 chart files refactored to use `<ChartShell>` + spread `defaultChartGrid`/`defaultAxisTickStyle`/etc. `CardShell` adds `role="region"` + `aria-labelledby` (via `useId`). `BenchmarkCorrelationTable` ρ column gains sign-symbol prefix (▲▲/▲/•/▼/▼▼) — color no longer sole encoder. `WindowSelector` buttons get `.window-selector-btn:focus-visible` outline. Audit grew 4→5 tests. 263 backend + 142 frontend green (+10 frontend); `npx tsc --noEmit` clean. |
| 2026-05-29 | US-12.4 | `ui-polish` skill authored at `.claude/skills/ui-polish/SKILL.md` (token + primitive + chart-defaults + a11y reference; canonical card pattern code block). New contract doc `docs/contracts/ui-design-system.md` (full token + primitive + audit inventory). `build-story` skill updated to auto-delegate UI slice to ui-polish. `CLAUDE.md` doc map + skills section updated (ui-polish now 8th project skill). Epic 12 closed; no code changes. 263 backend + 142 frontend green; `npx tsc --noEmit` clean. |

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

## Completed Epic: Epic 10 — Multi-broker Import Correctness

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

## Completed Epic: Epic 9 — Portfolio Correlation & Co-movement Analysis

**PRD:** [`docs/product/prd/epic-9-correlation-analysis.md`](product/prd/epic-9-correlation-analysis.md)

### Goal

Give the portfolio researcher a quantitative view of how their portfolio
co-moves with major market indexes — a day-by-day indexed return chart, a
rolling correlation & beta chart (20d/60d/252d Pearson ρ and β), and a
multi-benchmark snapshot table (ρ, β, R² vs SPY/QQQ/GLD/IEF/VT) — all in
the Exposure tab.

### Story snapshot

| Story | Title | Status |
|---|---|---|
| US-9.1 | Indexed return time-series chart | Done |
| US-9.2 | Rolling correlation and beta chart | Done |
| US-9.3 | Multi-benchmark correlation matrix | Done |
| US-9.4 | Fix rolling factor loadings methodology | Done |
| US-9.5 | Docs, contracts, roadmap close-out | Done |
| US-9.6 | Multi-benchmark correlation follow-ups | Done |

### Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-05-26 | US-9.4 | Fixed rolling factor model: per-window Gram-Schmidt orthogonalization replaces global GS; Market loading blowup (−4.60) eliminated; 221 backend + 98 frontend tests green |
| 2026-05-28 | — | Epic activated from Parked; US-9.2 revised to frontend-only (rolling_risk fields already computed); US-9.5 added for docs close-out |
| 2026-05-28 | US-9.1 | `DriftBenchmarkPanel` + `IndexedReturnChart` added to Exposure tab; drift engine wired in App.tsx; 5 new frontend tests; 97 frontend + 239 backend tests green |
| 2026-05-28 | US-9.2 | `RollingCorrelationChart` added to Exposure tab (bottom); dual-axis ρ + β chart with 20d/60d/252d window selector; 5 new frontend tests; 102 frontend + 239 backend tests green |
| 2026-05-28 | US-9.3 | `analytics/correlation.py` (pearson/beta/r_squared) + `schemas/correlation.py` + `services/correlation_engine.py` + `POST /engines/correlation/multi` route + `BenchmarkCorrelationTable` in Exposure tab — 22 backend tests green (261 total); 5 frontend tests green (107 total); `npx tsc --noEmit` clean |
| 2026-05-28 | US-9.5 | `docs/contracts/correlation-fields.md` created; `financial-methodology.md` window values corrected (20/60/252); roadmap and story files updated; Epic 9 fully closed |
| 2026-05-28 | US-9.6 | Follow-ups from verify-story on US-9.3: pinned sort + trust-indicator contracts (2 new backend pytest + 2 new frontend vitest); added §Multi-Benchmark Correlation umbrella section to methodology doc; updated `correlation-fields.md` to document opacity-not-column trust rendering — 263 backend + 109 frontend green; npx tsc clean |

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
