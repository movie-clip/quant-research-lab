# MVP Data Flow

## 1. Ingestion

- fetch symbols, historical prices, fundamentals, and benchmark data from FMP
- cache raw responses only when useful for retries or parser debugging
- normalize all analysis-ready data into parquet
- query parquet through DuckDB for portfolio and backtest workloads

## 2. Portfolio Sources

The initial portfolio can come from:

- manual transaction entry
- imported Interactive Brokers statement

Both paths should end in the same normalized transaction model.

### Interactive Brokers PDF import

- desktop app currently imports statements through broker upload routes, with the long-term target being an import-engine-owned upload contract
- quant engine reads the local PDF and extracts account metadata, positions, trades, cash balances, dividends, taxes, fees, and deposits
- the importer returns a normalized snapshot with:
  - `statement`
  - `instruments`
  - `cash_balances`
  - `positions`
  - `ledger_entries`
- this snapshot becomes the starting point for creating an internal portfolio ledger
- during rapid development this flow stays in memory; no persistent DB write is required yet
- the current desktop app projects imported upload responses immediately into narrower dashboard, exposure, diagnostics, baseline, snapshot, and factor-model contracts
- benchmark prices can be fetched from FMP on demand for imported portfolios, still without persisting data yet

## 3. Portfolio State Build

- transactions and cash activity are converted into dated holdings
- holdings are joined with normalized price history
- the engine computes market value, weights, returns, cash, and benchmark-relative metrics

## 4. Backtesting

- the user defines universe, benchmark, rebalance frequency, model, and constraints
- the engine loads local price and factor data
- strategy logic creates target weights or signals
- the backtest layer simulates portfolio evolution and records metrics

## 5. UI Delivery

- desktop app persists snapshot-first workspace state locally and requests derived engine results for analytics views
- charts and tables consume normalized API responses, not raw FMP payloads
- assistant features consume the same normalized outputs for explanation

## 6. LLM Layer

- turns user intent into filters, constraints, and review prompts
- never bypasses deterministic optimization or backtest validation
- explains portfolio changes, exposures, and trade-offs in plain language
