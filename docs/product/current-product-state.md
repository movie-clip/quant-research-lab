# Current Product State

Quant Research Lab is a local-first portfolio analytics application. It imports
broker statements into a desktop-local workspace and calculates deterministic
portfolio analytics through a local FastAPI engine. It is decision support only:
it never executes trades or moves money.

## Shipped surface

### Dashboard

- Import or append Interactive Brokers PDF/CSV statements.
- Performance and benchmark comparison for selectable periods.
- Time-weighted return, benchmark return, excess return, monthly returns, and
  a risk summary when their individual trust rules permit publication.
- Replay disclosures for degraded broker-replay inputs, including withheld
  values, cash anchors, carried trade-price valuations, and FX limitations.

### Exposure

- Holdings, asset-class, concentration, sector, and benchmark positioning.
- ETF look-through and identity-gated sector classification.
- Currency exposure, currency-risk contribution, factor analysis, drift, and
  benchmark/intra-portfolio correlation.

### Risk

- Stress scenarios, drawdown analytics, and return distribution/VaR views.

## Data and trust model

- **Broker truth** is imported positions, balances, and ledger activity.
- **Snapshot analytics** describe the imported/current portfolio state.
- **Synthetic history** reconstructs historical behavior from current holdings
  and market data; it is not broker-replayed performance.
- **Persisted imports** are desktop-local snapshots and related metadata.

All financially meaningful outputs preserve this distinction and use the trust
ladder `verified > degraded > withheld > unavailable`. `withheld` is a deliberate
refusal to publish an unsupported metric, not a synonym for missing data.

## Important boundaries

- The desktop persists snapshots and workspace metadata locally. Analytics are
  runtime-derived views and are not persisted as portfolio truth.
- Market data uses FMP first and Yahoo Finance as an explicit secondary source;
  source provenance remains visible to the user.
- The local import API deliberately accepts a user-selected filesystem path and
  has no authentication. This is acceptable only while the engine remains a
  localhost, single-user application; revisit before any remote or multi-user
  deployment.
- Ranking, construction, optimizer, backtesting, and monitoring workflows are
  not current product surfaces.

## Known limitations

- Some investor-economics and drawdown outputs remain withheld when replay or
  return-basis evidence is insufficient.
- Synthetic-history analytics are evidence-limited by available market, FX, and
  dividend data.
- Currency-less positions supplied through the generic request path can be
  incorrectly assigned a currency; see the technical-debt register before
  extending that API.

For formulas and detailed output semantics, read the financial methodology and
the relevant field contract before changing analytics.

## Backend route inventory

The engine exposes these current HTTP route modules. This list is mechanically
checked against `services/quant-engine/app/api/routes/`.

15 route modules:
- `attribution.py` — factor-return attribution
- `cache.py` — cache statistics and clearing
- `correlation.py` — benchmark and intra-portfolio correlation
- `currency_risk.py` — currency risk contribution
- `dashboard_history.py` — dashboard history from snapshot or imported replay
- `diagnostics.py` — portfolio diagnostics from snapshot or imported replay
- `distribution.py` — return distribution and VaR analytics
- `drawdown.py` — drawdown analytics
- `drift.py` — portfolio drift versus a benchmark
- `exposure.py` — holdings, sector, factor, and concentration exposure
- `health.py` — liveness check
- `imports.py` — statement import, upload, bootstrap analysis, and combination
- `market_data.py` — lightweight quote and historical-price access
- `provenance.py` — market-data provenance
- `stress.py` — factor-shock stress scenarios
