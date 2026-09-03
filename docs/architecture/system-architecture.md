# Quant Research Lab Architecture

This document explains the current architectural seams and the normalized direction.

For the canonical shipped-state inventory, use `docs/product/current-product-state.md`.

## System Boundaries

The project is split into a desktop application and a local quant engine.

- `apps/desktop`
  - workflow UI, workspace state, review flows, visualization, and local artifact persistence
- `services/quant-engine`
  - deterministic finance and quant engines for portfolio import and for snapshot / synthetic-history analytics — exposure, diagnostics, dashboard history, drift, attribution, correlation, currency risk, stress, drawdown, distribution, and provenance

The desktop app should treat the quant engine as the source of truth for portfolio calculations.

Import admission has a narrower split: the quant engine emits read-only `ImportAdmissionSummaryV1` evidence in imported bootstrap responses. The summary never mutates broker truth, admission state, trust level, imported values, derived portfolio truth, or workspace creation. (The never-wired `ImportAdmissionReviewDispositionV1` reviewer-disposition plumbing was removed in US-23.9 — no producer, no consumer; see `docs/contracts/import-admission-fields.md`.)

## Core Architecture Rules

- deterministic outputs over hidden heuristics
- explicit methodology and policy ids
- explicit truth separation across imported broker truth, snapshot analytics, synthetic history, and persisted import artifacts
- fail-closed loading for malformed or contradictory persisted import artifacts
- thin frontend; no duplicate finance engine in UI code

## Current Implemented Backend Seams

### Registered routers

The engine registers 15 routers (`services/quant-engine/app/api/main.py`):
- `health` — GET /health; liveness probe
- `imports` — POST /portfolios/import/{interactive-brokers, combine-snapshots, interactive-brokers/analyze, interactive-brokers/analyze-upload, interactive-brokers/analyze-snapshot}; IBKR statement + snapshot import, bootstrap analytics
- `exposure` — POST /engines/exposure/run -> ExposureResult
- `diagnostics` — POST /engines/diagnostics/{run, run-imported} -> DiagnosticsResult
- `dashboard_history` — POST /engines/dashboard-history/{run, run-imported} -> DashboardHistoryResult
- `drift` — POST /engines/drift/run -> DriftResult
- `attribution` — POST /engines/attribution/run -> FactorAttributionResponse
- `correlation` — POST /engines/correlation/{multi, intra} -> MultiBenchmarkCorrelationResult / IntraCorrelationResult
- `stress` — POST /engines/stress/run -> StressEngineResponse
- `drawdown` — POST /engines/drawdown/run -> DrawdownEngineResponse
- `distribution` — POST /engines/distribution/run -> DistributionEngineResponse
- `provenance` — POST /engines/provenance/run -> ProvenanceResult
- `currency_risk` — POST /engines/currency-risk/run -> CurrencyRiskResult
- `market_data` — GET /market-data/{quote-short, historical-price-light}; FMP / yfinance passthrough
- `cache` — GET /cache/stats, POST /cache/clear; FMP cache admin

Grouped by role:

- **Import** — `imports` ingests Interactive Brokers statements and combined snapshots and returns bootstrap analytics.
- **Analytics engines** — `exposure`, `diagnostics`, `dashboard_history`, `drift`, `attribution`, `correlation`, `stress`, `drawdown`, `distribution`, `provenance`, and `currency_risk` each run one deterministic snapshot-analytics or synthetic-history computation over a `PortfolioSnapshot` plus optional history context, and return a derived result with explicit trust metadata.
- **Infrastructure** — `health` is a liveness probe; `market_data` is a thin passthrough to the market-data seam; `cache` administers the FMP cache.

### Service layer

Each engine route is a thin wrapper over one service under
`services/quant-engine/app/services/`. Every file named here exists in that
directory today:

- Per-engine services: `exposure_engine.py`, `diagnostics_engine.py`, `dashboard_history_engine.py`, `drift_engine.py`, `attribution_engine.py`, `correlation_engine.py`, `intra_correlation_engine.py`, `stress_engine.py`, `drawdown_engine.py`, `distribution_engine.py`, `provenance_engine.py`, `currency_risk_engine.py`.
- Import path: `import_engine.py`, `import_engine_composer.py`, `statement_importer.py`, `import_admission.py`, `portfolio_snapshot_builder.py`, `history_context_builder.py`.
- Market data: `market_data.py` (`MarketDataService`).
- Cache: `cache_admin.py`.
- Shared / supporting: `benchmark_service.py`, `holdings_history.py`, `instrument_enrichment.py`, `instrument_identity.py`, `portfolio_proof.py`, `synthetic_history.py` (Synthetic History truth-class reconstruction — `build_synthetic_snapshot_history_states` / `..._with_coverage`, consumed by the diagnostics, attribution, correlation, distribution, drawdown and stress engines; extracted from `diagnostics_engine.py` in US-43.1).

Analytics layer (`services/quant-engine/app/analytics/`): `analytics/factor_model.py` holds the statistical factor-model internals — the factor-definition vocabulary (`FactorDefinition`, `DEFAULT_FACTOR_DEFINITIONS`, the proxy/key maps), `ROLLING_RIDGE_FLOOR`, the per-window Gram-Schmidt orthogonalisation and the ridge-OLS fit, plus their linear-algebra primitives. Extracted from `analytics/risk.py` in US-43.2 as a leaf module (it imports nothing from `risk.py`). Transitional shape: `risk.py` imports these names back, and `build_statistical_factor_model` (the response-shaping entry point) is still owned by `risk.py`; consumers `attribution.py`, `attribution_engine.py`, `stress_engine.py` and `diagnostics_engine.py` now import factor symbols from `analytics.factor_model`. The `ReturnBasis` execution-basis literal moved to `schemas/return_basis.py` in the same story.

Docs should describe these as the real current boundaries until they are split further.

## Truth Classes and Trust Semantics

The project uses explicit truth classes when reasoning about financial outputs:

- `broker-truth historical diagnostics`
- `snapshot current-state analytics`
- `synthetic snapshot-history diagnostics`
- `persisted import artifacts` (content-addressed, immutable)

These must remain visibly distinct in both payloads and UI.

Architecture-level trust rule:

- `verified_*` states mean the contract can claim the documented trust level for that path
- `degraded_*` states mean the engine may still compute useful outputs, but the contract must explicitly downgrade trust and suppress stronger claims
- `withheld` means broader evidence exists but investor-economics output is intentionally suppressed pending stronger return-basis justification
- `unavailable` means the required source inputs or trustworthy path do not exist at all

Docs and UI must not collapse `withheld` into generic `unavailable`.

### Market-data providers and data provenance

Market data is served behind a single seam, `MarketDataService`
(`app/services/market_data.py`), which resolves each symbol to ordered
candidates and tries providers in priority order:

1. **FMP (primary)** — `FmpClient`. Covers US-listed equities/ETFs. Returns
   HTTP 402 for European exchange-listed symbols (`.L`, `.DE`, …).
2. **Yahoo Finance (secondary/fallback)** — `YFinanceClient`, tried only when
   FMP returns nothing for a candidate (US-18.1). Recovers European UCITS ETFs
   (`VUAA.L`, `SXRV.DE`, …) with adjusted-close history.

`MarketDataService.last_fetch_meta[symbol]['vendor']` records which provider
satisfied each symbol (`'fmp'` | `'yfinance'`). The FMP-first path is unchanged
when FMP has data; yfinance is never a proxy substitute (it fetches the *real*
holding from a second source).

**Failure classes at the seam (US-35.1):** the seam distinguishes *"there is no
data for this symbol"* from *"this machine could not ask"*, because only the
first is a fact about the portfolio.

| Failure | Scope | Behaviour |
|---|---|---|
| 404, unresolvable symbol, delisted | that symbol | negative-cached, returns `[]` — the caller degrades to `unavailable` |
| 402/403 (plan entitlement) | that symbol | negative-cached, returns `[]` — the yfinance fallback then serves UCITS listings |
| **401, or no API key configured** | **every symbol** | raises `MarketDataAuthError`; **never cached** |

A configuration failure cannot be represented as an absence of data. It used to
be: a 401 was negative-cached as `[]` and immediately re-read by the
stale-fallback branch, so the error was swallowed, every engine degraded to
`unavailable` perfectly correctly, and nothing reported the real cause — for
`fmp_history_cache_ttl_seconds` (86400) at a time, surviving a corrected key.

`MarketDataService` still catches `Exception` broadly at every call site, and
those catches are load-bearing: symbol resolution tries `VUAA.L` → `VUAA` → a US
proxy and expects most candidates to fail. They re-raise `MarketDataAuthError`
specifically and swallow everything else exactly as before, so a per-symbol
failure stays per-symbol.

**Row sanitization rule (US-18.4):** rows with an absent or non-finite `price`
(NaN/inf — e.g. a Yahoo/pandas missing bar) never leave the seam:
`MarketDataService` filters them on every history return path, and the yfinance
client additionally skips non-finite bars at the source. A non-finite bar is
"no data for that date" — dropped, never zero-filled or interpolated. This also
neutralizes already-cached poisoned entries.

**History range normalization (US-20.2):** because each engine computes its own
lookback, the same symbol's history is requested over many overlapping `(from,
to)` windows — each a distinct FMP cache key, the dominant source of FMP
overuse. `MarketDataService` widens every history request to a canonical,
deterministic superset range quantized to calendar-year boundaries
(`_canonical_history_range`), fetches that one range (so all requests in the same
year-span share a single cache key / FMP call), then slices the rows back to the
caller's exact window (`_slice_price_rows`). The bars an engine receives are
byte-identical to a direct `(from, to)` fetch — slicing is exact, not
approximate. Applies to `get_historical_prices` (and `…_for_symbols`, FX, proxy
fallback, yfinance fallback) and the verified-benchmark direct path. Goldens and
engine unit tests are unaffected (they replace `MarketDataService` wholesale —
`FrozenMarketData` for goldens, conftest mocks for engines).

**In-memory layer + parallel fetch (US-20.3):** two latency optimizations over
the same seam. (1) `JsonFileCache` keeps a process-level in-memory memo (keyed by
absolute path + file mtime) of the parsed cache envelope, so repeated reads of
the same file across an analysis's engines skip the disk read + `json.loads`
after the first; it self-invalidates on any write (mtime change), is shared
across the separate per-engine cache instances, and is cleared per-test by an
autouse fixture for determinism. (2) `get_historical_prices_for_symbols` fetches
symbols concurrently via a bounded `ThreadPoolExecutor`. Both are pure
performance — identical bytes, TTL/stale semantics, `last_fetch_meta`, and trust
ladder; no on-disk format change.

**Data provenance is a distinct dimension from return-basis trust.** Yahoo data
carries adjusted close, so its return-basis is `verified_adjusted_close` — the
same class as FMP — but the *source* differs. Per the traceability guardrail,
provenance must be **surfaced, never hidden**: engine responses that include
yfinance-sourced holdings carry that fact (e.g. `IntraCorrelationResult.yahoo_sourced_symbols`)
and the UI shows a visible "via Yahoo Finance (secondary source)" marker.
(The `.claude/skills/fmp-data` skill is the multi-provider reference.)

A dedicated `POST /engines/provenance/run` engine (`provenance_engine.py`,
US-18.2) reports per-holding provenance for the whole portfolio (FMP / yfinance
/ unavailable) by a short probe of `last_fetch_meta` vendor; the Exposure tab's
"Data sources" panel renders it once at the portfolio level rather than
repeating a marker on every card. Provenance is a **source label, not a
return-basis trust claim** — it never asserts `verified`/`synthetic` for the
analytics.

Instrument identity (Epic 19): `app/services/instrument_identity.py`
cross-checks each registry-known holding's broker-statement evidence against the
registry mapping, with two complementary evidence classes:

- **Description heuristic (US-19.1):** flags when the statement description and
  the registry fund name share zero significant tokens (conservative —
  formatting/share-class noise never fires).
- **ISIN, definitive (US-19.2):** the registry stores an authoritative `isin`
  per instrument, **sourced from the committed real statements** (16
  UCITS/identity-sensitive lines seeded); a normalized statement-ISIN ≠
  expected-ISIN is an exact ISO 6166 identity violation — it catches mislabels
  the token heuristic misses (e.g. two different "Defense" funds).
  Evidence-gated: holdings lacking an ISIN on either side are skipped — absent
  evidence is never a pass or a failure. `test_registry_isin_integrity.py` pins
  registry-seed ⇄ statement agreement so a typo'd seed fails the suite.

Mismatches are emitted both as Import Admission checks
(`instrument_description_registry_consistency`,
`instrument_isin_registry_consistency` — `warn`/`degraded`) and (for
visibility) in the provenance result rendered by the Data Sources panel, with
`kind` + both ISINs as evidence. Flag only — never auto-corrects the registry
or remaps the symbol.

## API Boundary

Current API direction:

- local workspace persistence is snapshot-first
- engine outputs are derived runtime artifacts
- the frontend may persist `PortfolioSnapshot` and workspace metadata locally, but it must not persist derived analytics as portfolio truth

**Accepted tradeoff — unauthenticated local file-read (import routes).**
`services/quant-engine/app/api/routes/imports.py`'s
`InteractiveBrokersImportRequest.statement_path` / `statement_paths` accept
any filesystem path the caller supplies, and `_resolve_statement_paths` only
checks that the path exists — it is not restricted to an app-owned directory.
The FastAPI server itself has no authentication layer. This is a **deliberate,
accepted tradeoff, not an unnoticed defect**: the product is local-first and
single-user by design (see "What the product is" in the project profile), the
engine never places trades or moves money (guardrail 5), and CORS is
restricted to the app's own dev origins
(`http://localhost:5173`, `http://127.0.0.1:5173` — not a wildcard, per
`app/api/main.py`). Revisit this note if the engine is ever exposed beyond
localhost or gains multi-user scope — at that point the tradeoff's premise no
longer holds.

## Data Flow

### Portfolio import and analytics

1. import broker statements or transactions
2. normalize into domain transactions, balances, and positions
3. build `PortfolioSnapshot` plus optional history context
4. persist snapshot as local truth in the desktop workspace model
5. call dedicated engines (exposure, diagnostics, dashboard-history, drift, attribution, correlation, currency-risk, stress, drawdown, distribution, provenance) as appropriate
6. send derived outputs to the UI with explicit provenance and trust metadata

Import admission evidence is finite-only for numeric observed, comparison, and delta fields. Non-finite imported numeric inputs degrade to unavailable evidence rather than serializing `NaN` or `Infinity`. Desktop read/build paths may return sanitized clones of local review metadata without rewriting IndexedDB; save paths must match captured evidence against the current non-pass check evidence.

Every engine reads from the persisted `PortfolioSnapshot` plus optional history context; there is no persisted-artifact, ranking, construction, optimizer-handoff, or replay flow.

## Desktop Workspace Model

The desktop app follows a local-first workspace structure:

- `PortfolioWorkspace`
- `PortfolioNode`
- `WorkingDraft`
- `PortfolioSnapshot`

Saved portfolio variants are immutable child nodes. Engine outputs are recalculated or restored as derived views and are not the persisted truth of the workspace.

Persisted snapshots and workspace references should remain lineage-aware and fail closed when internal contradictions are provable.

## Documentation Rule

If a financially meaningful formula, methodology, truth-class assumption, trust semantic, or persisted-artifact provenance rule changes, update:
- `docs/finance/financial-methodology.md`
- the relevant field inventory document
- tests that lock the behavior
