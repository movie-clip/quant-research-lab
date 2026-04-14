# Desktop App

Tauri desktop shell with a React and TypeScript frontend.

## Responsibilities

- portfolio dashboards
- holdings and allocation views
- backtest builder and results
- Interactive Brokers statement upload
- LLM-assisted portfolio review

The desktop app should remain thin on finance logic and delegate calculations to the quant engine.

## Current Portfolio Frontend Direction

- local portfolio editing is workspace-based and snapshot-first
- `PortfolioSnapshot` is the persisted truth for imported bases, saved variants, and working drafts
- dashboard, exposure, diagnostics, and backtest baseline flows now use narrower contracts instead of a single broad imported-analysis UI object
- if historical diagnostics require missing history context, the app should show unavailable rather than infer them from a static snapshot
