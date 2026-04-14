# Financial Accuracy Review

This note traces the current import-to-analytics pipeline and documents what is used to calculate each portfolio view. The goal is to establish what is financially solid today, what is approximation-heavy, and where correctness risks remain.

## 1. End-to-End Flow

### Frontend import flow

Entry point: `apps/desktop/src/app/App.tsx`

1. User selects one or more PDF files in the Dashboard import flow.
2. Frontend sends uploaded files to `/api/portfolios/import/interactive-brokers/analyze-upload`.
3. Frontend projects the upload response into narrower imported dashboard, exposure, diagnostics, baseline, snapshot, and factor-model contracts.
4. Snapshot-first workspace state is persisted locally and derived views are rendered from those narrower contracts.

Important consequence:
- Exposure reuses the imported factor-model slice directly, which removes a prior stale-state / split-pipeline risk.

### Backend import orchestration

Entry point: `services/quant-engine/app/services/statement_importer.py`

Importer detection order for PDFs:
1. Interactive Brokers
2. Freedom24
3. ESPP

If multiple files are imported, `combine_imported_snapshots(...)` merges them into one synthetic combined snapshot.

### Analysis orchestration

Entry point: `services/quant-engine/app/services/import_engine.py`

Current pipeline:
1. Import / combine statements into `ImportedPortfolioSnapshot`
2. Derive analysis window from statement periods or transaction/position dates
3. Fetch market data:
   - benchmark history (`SPY`, hardcoded)
   - latest quotes for current positions
   - historical prices for traded symbols
   - factor proxy histories
   - FX history for non-base-currency positions
4. Reconstruct daily portfolio states via `PortfolioStateEngine`
5. Derive performance, risk, lookthrough, factor exposures, diagnostics, and stress output

## 2. Parsing Layer

### Supported statement formats

- `interactive_brokers`
- `freedom24`
- `espp`
- `multi_broker` synthetic combined snapshot

### Parsing objective

Each parser maps source statements into the common import schema:
- `ImportedStatement`
- `ImportedStatementTotals`
- `ImportedInstrument`
- `ImportedPosition`
- `ImportedCashBalance`
- `ImportedLedgerEntry`

This abstraction is good and should remain the main boundary.

### Financial accuracy status of parsers

#### Interactive Brokers
- strongest parser
- supports positions, cash, ledger, statement totals
- used as the main reference-quality source

#### Freedom24
- functional, but page-layout fragile
- recently fixed to correctly parse split dates and commissions from `FF2026.pdf`
- still relies on page-number/row-shape assumptions rather than semantic table extraction

#### ESPP
- intentionally simplified to integrate as:
  - `MSFT` position
  - USD cash balance
  - minimal ledger (`DEPOSIT`, `BUY`, `WITHHOLDING_TAX`, `DIVIDEND`)
- this is correct as an integration strategy, but not a full brokerage-ledger reconstruction
- it should be treated as a holdings-style account statement, not a full transactional broker report

## 3. Combined Snapshot Semantics

Entry point: `services/quant-engine/app/services/statement_importer.py`

Current behavior:
- statements are merged chronologically
- base currency must match
- account ids are combined into a synthetic account label
- terminal positions and cash are merged per latest snapshot per account
- statement totals are merged so combined `ending_nav` = combined `cash_total + stock_total`

This is materially better than the old behavior that used only the latest snapshot's positions/cash.

Remaining semantic caveat:
- the result is still one synthetic portfolio across accounts, not separate sleeves with separate NAV paths

## 4. Ledger Construction

Entry point: `services/quant-engine/app/domain/ledger.py`

Current model:
- imported ledger entries are converted into normalized `LedgerRecord`s
- `cash_effect = net_amount or 0.0`
- position-affecting entries are only `BUY` / `SELL`
- external flows are only `DEPOSIT` / `WITHDRAWAL`

Strengths:
- simple and auditable
- good enough for time-weighted performance if ledger entries are well parsed

Risks:
- parsers must get sign conventions exactly right
- dividends, taxes, fees, and internal cash movements must be normalized consistently
- some statement types do not provide complete enough ledger detail to fully reconstruct path-accurate state

## 5. Daily Portfolio State Reconstruction

Entry point: `services/quant-engine/app/engine/portfolio_state.py`

Current methodology:
1. Determine ending positions from snapshot
2. Infer opening positions by reversing buys/sells:
   - opening = ending + sells - buys
3. Use `statement_totals.starting_nav` as initial portfolio value
4. Compute opening positions value at first valuation date
5. Back out implied base cash:
   - `base_cash = starting_nav - opening_positions_value`
6. Roll forward daily through ledger entries and prices

Strengths:
- coherent framework for reconstructing a time series from static statement snapshots + ledger
- cash-flow-neutral return math downstream is conceptually correct if the state path is correct

Major accuracy risks:
- this is a reverse-engineered state path, not broker-native daily NAV history
- if opening positions are incomplete or price history is missing for traded symbols, implied cash can become wrong
- if parsers emit incomplete deposit/buy semantics, early cash and return history distort sharply
- combined multi-account histories are especially approximation-heavy because accounts are merged into one synthetic path

Specific current issue:
- reconstruction can still diverge from statement ending NAV even after recent fixes
- dashboard now prefers statement ending NAV for the headline card when reconstruction disagrees materially
- this is a useful guardrail, but it also proves the reconstructed path is not always fully accurate

## 6. Performance Methodology

Entry point: `services/quant-engine/app/analytics/performance.py`

### What is financially correct

- time-weighted daily return formula:
  - `((current_value - external_cash_flow) / previous_value) - 1`
- compounded return series from daily TWR is conceptually right
- drawdown built from compounded wealth index is correct in principle
- money-weighted return approximation is consistent with a simple weighted-flow estimator

### What performance depends on

Performance is only as good as:
- daily reconstructed portfolio values
- external cash flow tagging
- symbol price history completeness
- FX conversions

### Accuracy assessment

- methodology is good
- reconstructed inputs are still the weak link

## 7. Dashboard Calculations

Primary files:
- `apps/desktop/src/features/portfolio/DashboardPanel.tsx`
- `services/quant-engine/app/analytics/overview.py`

### Overview / Allocation

Uses current snapshot positions and current snapshot cash balances.

This is generally robust because it is statement-terminal rather than path-reconstructed.

### Performance chart

Uses backend `performance_series` derived from reconstructed `daily_states`.

Recent improvement:
- `All` range normalization now anchors from the first non-zero portfolio point rather than the first visible point

### Headline `Portfolio Value`

Now prefers statement ending NAV when reconstructed terminal NAV diverges materially.

This is the right current safeguard.

## 8. Lookthrough / Sector / Exposure Calculations

Primary files:
- `services/quant-engine/app/analytics/risk.py`
- `services/quant-engine/app/instruments/registry.py`
- `services/quant-engine/app/core/symbols.py`

### Lookthrough exposure

Method:
- if a holding is classified as ETF, fetch holdings and decompose by constituent weights
- otherwise keep the security as a direct constituent

This is structurally reasonable.

Risks:
- ETF classification must be correct
- ticker resolution / proxy mapping must be correct
- missing holdings data pushes positions into uncovered / direct buckets

### Sector exposure

Method:
- sector is taken from instrument registry metadata if available
- otherwise inferred from proxy/source heuristics

This is useful operationally, but not fully robust.

Accuracy risk:
- sector classification still mixes curated registry entries and heuristic fallbacks

### Simplified factor exposures row

`build_factor_exposures(...)` produces:
- Market = `risk_summary.portfolio_beta`
- SPY Overlap = lookthrough overlap vs benchmark holdings
- Growth Tilt = Technology + Communication Services + Consumer Discretionary sector weights
- Health Care / Defense / Commodities / Fixed Income from lookthrough sector weights

This block is intuitive and mostly holdings-based.

Important note:
- `Growth Tilt` is not the same thing as the regression `Growth (QQQ)` loading
- users can easily confuse the two

## 9. Statistical Factor Model

Primary file:
- `services/quant-engine/app/analytics/risk.py`

Current methodology:
- portfolio return series derived from reconstructed daily states
- factor proxy returns from US ETF proxies
- factor series are orthogonalized
- rolling factor loadings computed for 20d / 60d / 252d windows
- current snapshot uses latest 60d loading

What is strong:
- explicit rolling windows
- explicit model reliability block exists now
- collinearity diagnostics exist

What is weak:
- factor model stability is often poor
- loadings can become financially unintuitive because:
  - returns are reconstructed, not native account returns
  - factor set is highly collinear
  - orthogonalization makes coefficients harder to interpret economically
  - short or mixed-history imports amplify instability

Example symptom:
- negative `Growth (QQQ)` loading even when holdings look growth-heavy

Current recommendation:
- treat regression factor outputs as diagnostic / secondary when `model_reliability.confidence = low`
- prioritize holdings-based exposure summaries in those cases

## 10. Risk Summary / Relative Risk / Volatility

Primary file:
- `services/quant-engine/app/analytics/risk.py`

These use reconstructed daily returns and aligned benchmark returns.

Financially correct in formula:
- beta
- correlation
- volatility
- tracking error
- drawdown

Accuracy caveat:
- again depends on reconstructed state quality

If state reconstruction is noisy, all downstream risk metrics can become economically implausible.

## 11. Risk Contribution / Diagnostics

Primary file:
- `services/quant-engine/app/analytics/risk.py`

Recent improvements:
- factor contribution now uses covariance-based factor variance math, not diagonal-only approximation
- model reliability is first-class

Strengths:
- mathematically improved vs prior version

Risks:
- still depends on unstable factor model inputs
- risk contribution can be numerically precise while economically misleading if factor loadings are unreliable

## 12. Accuracy Findings

### Strongest parts today

- statement-terminal holdings / cash / allocation overview
- benchmark-aligned performance formulas in principle
- covariance-based diagnostics framework in principle
- symbol resolution system is much better than before
- mixed-broker terminal merge now correctly combines current holdings and cash

### Weak / approximation-heavy parts today

- reconstructed daily portfolio path
- multi-account synthetic time series
- ESPP path reconstruction from year-end report format
- regression factor model interpretation under low confidence
- some ETF / sector classification still depends on manual mapping and heuristics

## 13. Concrete Correctness Risks To Fix Next

1. Separate terminal snapshot truth from reconstructed historical path more explicitly
   - current headline value fix is only a UI guardrail

2. Build account-sleeve-aware reconstruction for mixed-broker imports
   - reconstruct each account separately, then aggregate daily

3. Improve ESPP historical semantics
   - year-end ESPP reports should probably contribute terminal holdings and limited cash semantics, but not imply full-year path confidence

4. Add reliability gating in Exposure
   - if factor model confidence is low, demote or suppress regression loadings visually

5. Reduce heuristic classification
   - move symbol aliases, proxies, asset semantics, and sector/category metadata into one richer registry

6. Add statement-vs-reconstruction reconciliation diagnostics
   - compare terminal reconstructed NAV to statement ending NAV
   - compare terminal reconstructed cash to statement cash balances
   - compare terminal reconstructed positions to statement positions

7. Review deposit semantics in non-broker parsers
   - especially ESPP, where payroll funding is inferred rather than explicitly ledger-proven

## 14. Proposed Standard For “Financially Correct” Going Forward

For each metric, define the acceptable data source priority:

- `Holdings / Allocation / Cash`:
  1. statement-terminal parser output
  2. never reconstructed if statement data exists

- `Portfolio Value headline`:
  1. statement ending NAV if available
  2. reconstructed NAV only as fallback

- `Performance / Return path`:
  1. reconstructed path from complete transactional statements
  2. downgraded-confidence output for holdings-style statements (like ESPP year-end reports)

- `Lookthrough / Sector exposure`:
  1. holdings-based decomposition
  2. registry-based classification
  3. heuristic inference only as fallback

- `Regression factor model`:
  1. show only with explicit reliability tier
  2. de-emphasize or suppress when confidence is low

- `Risk contribution`:
  1. allowed only when model reliability is acceptable
  2. otherwise show limited / degraded diagnostic state

## 15. Bottom Line

The project is strongest today as a local portfolio snapshot / allocation / benchmark-relative workstation.

It is directionally good for professional diagnostics, but not yet fully financially reliable in every path-dependent metric because too much depends on reconstructed daily state from incomplete or heterogeneous statements.

The main architectural win already exists:
- all parsers normalize into one schema

The next accuracy step should be:
- make statement truth, reconstruction confidence, and model reliability explicit everywhere they matter.
