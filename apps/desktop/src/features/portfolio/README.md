# Portfolio Feature

Owns portfolio views, holdings tables, allocation charts, transaction history, and imported account workflows.

Current contract split:

- `DashboardPanel` consumes `DashboardAnalysis`
- `ExposurePanel` consumes `ExposureAnalysis`
- `DiagnosticsPanel` consumes `DiagnosticsEngineResponse`
- portfolio improvement baseline seeding consumes `PortfolioBaselineAnalysis`
- imported upload responses should be projected into narrower import-specific contracts as early as possible
