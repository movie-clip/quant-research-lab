# Portfolio Feature

Owns portfolio intelligence views, holdings tables, allocation charts, imported account workflows, and decision-grade portfolio diagnostics.

Current contract split:

- `DashboardPanel` consumes `DashboardAnalysis`
- `ExposurePanel` consumes `ExposureAnalysis`
- `DiagnosticsPanel` consumes `DiagnosticsEngineResponse`
- portfolio improvement baseline seeding consumes `PortfolioBaselineView`
- imported upload responses should be projected into narrower import-specific contracts as early as possible
- accuracy inventories live in `docs/dashboard-field-inventory.md` and `docs/exposure-field-inventory.md`

Quant-lab direction for this feature:
- current portfolio truth and intelligence
- benchmark-relative analysis
- factor and risk diagnostics
- portfolio improvement inputs and baseline views
