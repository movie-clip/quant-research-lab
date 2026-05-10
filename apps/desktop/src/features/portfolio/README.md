# Portfolio Feature

Owns portfolio intelligence views, holdings tables, allocation charts, imported account workflows, and decision-grade portfolio diagnostics.

Current contract split:

- `DashboardPanel` consumes `DashboardAnalysis`
- `ExposurePanel` consumes `ExposureAnalysis`
- `DiagnosticsPanel` consumes `DiagnosticsEngineResponse`
- portfolio improvement baseline seeding consumes `PortfolioBaselineView`
- imported upload responses should be projected into narrower import-specific contracts as early as possible
- `ImportAdmissionSummaryV1` is read-only evidence from imported bootstrap responses; the Dashboard may display it but must not treat it as a workspace-creation gate or trust upgrade
- `ImportAdmissionReviewDispositionV1` is optional desktop-local metadata for non-pass checks only; save-time validation must match current evidence, and runtime sanitization must not rewrite IndexedDB on read
- accuracy inventories live in `docs/contracts/dashboard-fields.md`, `docs/contracts/exposure-fields.md`, and `docs/contracts/import-admission-fields.md`

Quant-lab direction for this feature:
- current portfolio truth and intelligence
- benchmark-relative analysis
- factor and risk diagnostics
- portfolio improvement inputs and baseline views
