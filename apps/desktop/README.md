# Desktop App

Tauri desktop shell with a React and TypeScript frontend.

## Responsibilities

- portfolio intelligence dashboards
- holdings, overlap, factor, and risk views
- ranking, construction, and replay workflows
- broker statement import workflows
- LLM-assisted review and workflow support

The desktop app should remain thin on finance logic and delegate calculations to the quant engine.

## Current Frontend Direction

- local portfolio editing is workspace-based and snapshot-first
- `PortfolioSnapshot` is the persisted truth for imported bases, saved variants, and working drafts
- dashboard, exposure, diagnostics, and backtest baseline flows now use narrower contracts instead of a single broad imported-analysis UI object
- if historical diagnostics require missing history context, the app should show unavailable rather than infer them from a static snapshot
- the frontend should evolve toward a quant-research-lab workflow built around ranking, construction, replay, and portfolio improvement
