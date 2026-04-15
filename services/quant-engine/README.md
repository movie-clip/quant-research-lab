# Quant Engine

Local Python service for market data ingestion, portfolio truth, ranking, analytics, construction, replay, and monitoring.

## Responsibilities

- FMP client and caching
- dataset normalization
- broker statement import
- portfolio accounting and analytics
- ETF / instrument ranking
- construction and replay workflows
- monitoring and diagnostics
- LLM-safe portfolio explanation inputs

## Current Engine Direction

The backend now has explicit early boundaries for the long-term product shape:

- `app/importers/`
  - broker import pipelines for real portfolio data
- `app/domain/`
  - canonical ledger and portfolio accounting helpers
- `app/analytics/`
  - imported portfolio analytics, factors, diagnostics, and reconciliation
- `app/instruments/`
  - instrument master and metadata
- `app/datasets/`
  - local dataset catalog and sample/live history access
- `app/strategies/`
  - strategy and ranking research workflows
- `app/backtests/`
  - replay and backtest engines
- `app/overlay/`
  - overlay preview and later overlay engine workflows

The service should evolve into the deterministic backend for the quant research lab.

Priority backend directions:
- production-grade financial math
- ranking engine
- portfolio construction rules
- portfolio improvement comparison
- overlay and monitoring systems

## FMP Cache Strategy

The backend now prefers a local-first file cache for FMP responses rather than Redis.

- quote responses use a short TTL for freshness
- historical price responses use a longer TTL because they change slowly
- stale cached responses can be used as a fallback if the live API is temporarily unavailable
- cache namespaces are split into `quote`, `history`, and `fx`
- cache logs now emit hit, miss, store, and stale-fallback events

Why not Redis right now:

- this project is local-first and usually single-user
- Redis adds another service to install, run, and debug
- file cache works better for your current workflow where the same portfolio is analyzed repeatedly on one machine

Move to Redis later only if you need shared cache across multiple processes, users, or hosts.

### Cache Maintenance

Use the repo script from the workspace root:

```bash
python scripts/manage_cache.py list
python scripts/manage_cache.py clear
python scripts/manage_cache.py clear --namespace history
```
