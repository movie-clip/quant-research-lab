import type { BenchmarkStats, DashboardAnalysis, DashboardHistoryEngineResponse, DiagnosticsEngineResponse, DistributionEngineResponse, DistributionWindow, DrawdownEngineResponse, DrawdownWindow, DriftResult, ExposureAnalysis, ExposureEngineResponse, ExposureFactorModelResponse, FactorAttributionResponse, ImportedBaselineSource, ImportedDashboardSource, ImportedDiagnosticsSource, ImportedExposureSource, ImportedSnapshot, IntraCorrelationResult, MultiBenchmarkCorrelationResult, PortfolioBaselineView, ProvenanceResult, StressEngineResponse, CacheStats, CacheClearResult } from './types'
import type { ImportedHistoryContext, PortfolioSnapshot } from './workspaceTypes'
import type { ResolveDesktopApiUrlOptions } from '../../app/apiBase'
import { resolveDesktopApiUrl } from '../../app/apiBase'
import { DEFAULT_FACTOR_MODEL_METHODOLOGY } from './exposureFactorModel'

type SnapshotAnalysisRequest = {
  benchmark_symbol: string
  base_currency: string | null
  statement_period: string | null
  imported_at: string
  importer: string | null
  source_file_names: string[]
  positions: Array<{
    symbol: string
    market_value: number
    quantity: number | null
    currency: string | null
    sector: string | null
  }>
  cash_balances: Array<{
    currency: string
    amount: number
  }>
  /** US-30.5a: statement-implied FX rates ("EURUSD" → rate). Omitted when the
   *  snapshot has none (pre-US-30.2 persisted snapshots). */
  fx_rates?: Record<string, number>
}

type DashboardHistoryRequest = SnapshotAnalysisRequest & {
  history_context: EngineHistoryContextRequest
}

type EngineHistoryContextRequest = {
  benchmark_symbol: string
  statement_period: string | null
  imported_at: string | null
  importer: string | null
  source_file_names: string[]
  history_start_date: string | null
  history_end_date: string | null
}

function resolvePortfolioEngineUrl(path: string, options?: ResolveDesktopApiUrlOptions) {
  return resolveDesktopApiUrl(path, options)
}

function buildSnapshotAnalysisRequest(snapshot: PortfolioSnapshot): SnapshotAnalysisRequest {
  return {
    benchmark_symbol: snapshot.metadata.benchmarkSymbol ?? 'SPY',
    base_currency: snapshot.baseCurrency,
    statement_period: snapshot.importedMeta.statementPeriod,
    imported_at: snapshot.importedMeta.importedAt,
    importer: snapshot.importedMeta.importer,
    source_file_names: snapshot.importedMeta.sourceFileNames,
    positions: snapshot.positions.map((position) => ({
      symbol: position.symbol,
      market_value: position.marketValue,
      quantity: position.quantity ?? null,
      currency: position.currency ?? snapshot.baseCurrency,
      sector: position.sector ?? null,
    })),
    cash_balances: snapshot.cashBalances.map((balance) => ({
      currency: balance.currency,
      amount: balance.amount,
    })),
    // US-30.5a (audit F-7): every engine on the request path needs the
    // statement-implied rates so weight denominators sum in the base currency.
    // Absent on snapshots persisted before US-30.2 — the engine then carries
    // values unconverted and discloses it.
    ...(snapshot.fxRates ? { fx_rates: snapshot.fxRates } : {}),
  }
}

function buildHistoryContextRequest(historyContext: ImportedHistoryContext): EngineHistoryContextRequest {
  return {
    benchmark_symbol: historyContext.benchmarkSymbol,
    statement_period: historyContext.statementPeriod,
    imported_at: historyContext.importedAt,
    importer: historyContext.importer,
    source_file_names: historyContext.sourceFileNames,
    history_start_date: historyContext.historyStartDate,
    history_end_date: historyContext.historyEndDate,
  }
}

export async function runExposureEngine(snapshot: PortfolioSnapshot, apiUrlOptions?: ResolveDesktopApiUrlOptions): Promise<ExposureEngineResponse> {
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/exposure/run', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildSnapshotAnalysisRequest(snapshot)),
  })

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(payload?.detail ?? 'Exposure engine run failed')
  }

  return (await response.json()) as ExposureEngineResponse
}

export async function runDriftEngine(
  snapshot: PortfolioSnapshot,
  benchmarkSymbol: string,
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<DriftResult> {
  // `fx_rates` (US-30.2 / US-30.5a) comes from buildSnapshotAnalysisRequest.
  const requestBody = { ...buildSnapshotAnalysisRequest(snapshot), benchmark_symbol: benchmarkSymbol }
  // Debug log: confirm the adapter is reached and inspect the actual outgoing
  // payload. Removeable once drift-card "No drift data" issue is diagnosed.
  console.info('[drift] POST', {
    url: resolvePortfolioEngineUrl('/api/engines/drift/run', apiUrlOptions),
    positions: requestBody.positions.length,
    benchmark: benchmarkSymbol,
    imported_at: requestBody.imported_at,
    base_currency: requestBody.base_currency,
  })
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/drift/run', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody),
  })

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null
    const detail = payload?.detail ?? `HTTP ${response.status}`
    throw new Error(`Drift engine run failed: ${detail}`)
  }

  return (await response.json()) as DriftResult
}

export async function runDiagnosticsEngine(
  snapshot: PortfolioSnapshot,
  historyContext?: ImportedHistoryContext | null,
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<DiagnosticsEngineResponse> {
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/diagnostics/run', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...buildSnapshotAnalysisRequest(snapshot),
      history_context: historyContext ? buildHistoryContextRequest(historyContext) : null,
    }),
  })

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(payload?.detail ?? 'Diagnostics engine run failed')
  }

  return (await response.json()) as DiagnosticsEngineResponse
}

export async function runImportedDiagnosticsEngine(
  snapshot: ImportedDashboardSource['snapshot'],
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<DiagnosticsEngineResponse> {
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/diagnostics/run-imported', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(snapshot),
  })

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(payload?.detail ?? 'Imported diagnostics engine run failed')
  }

  return (await response.json()) as DiagnosticsEngineResponse
}

export async function runDashboardHistoryEngine(
  snapshot: PortfolioSnapshot,
  historyContext: ImportedHistoryContext,
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<DashboardHistoryEngineResponse> {
  const payload: DashboardHistoryRequest = {
    ...buildSnapshotAnalysisRequest(snapshot),
    history_context: buildHistoryContextRequest(historyContext),
  }

  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/dashboard-history/run', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(payload?.detail ?? 'Dashboard history engine run failed')
  }

  return (await response.json()) as DashboardHistoryEngineResponse
}

export async function runImportedDashboardHistory(
  snapshot: ImportedDashboardSource['snapshot'],
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<DashboardHistoryEngineResponse> {
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/dashboard-history/run-imported', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(snapshot),
  })

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(payload?.detail ?? 'Imported dashboard history engine run failed')
  }

  return (await response.json()) as DashboardHistoryEngineResponse
}

export function composeExposureView(exposure: ExposureEngineResponse, diagnostics: DiagnosticsEngineResponse): ExposureAnalysis {
  return {
    snapshot: exposure.snapshot,
    provenance: exposure.provenance,
    run_metadata: exposure.run_metadata,
    diagnostics_run_metadata: diagnostics.run_metadata,
    overview: exposure.overview,
    lookthrough: exposure.lookthrough,
    lookthrough_sector_exposure: exposure.lookthrough_sector_exposure,
    // US-30.5a (audit F-8): forward the currency-basis disclosure to the tab.
    fx_static_rate_currencies: exposure.fx_static_rate_currencies,
    fx_fallback_currencies: exposure.fx_fallback_currencies,
    market_overlap: exposure.market_overlap,
    current_state_concentration: exposure.current_state_concentration,
    risk_summary: diagnostics.risk_summary,
    rolling_risk: diagnostics.rolling_risk,
    relative_risk: diagnostics.relative_risk,
    volatility_regime: diagnostics.volatility_regime,
    factor_exposures: diagnostics.factor_exposures,
    model_reliability: diagnostics.model_reliability,
    factor_registry: diagnostics.factor_registry,
    factor_methodology: diagnostics.factor_methodology,
    statistical_factor_model: diagnostics.statistical_factor_model,
    stress_scenarios: diagnostics.stress_scenarios,
    benchmark: null,
    scenario_preview: null,
    exposure_availability: exposure.availability,
    availability: diagnostics.availability,
  }
}

export async function runAttributionEngine(
  snapshot: ImportedSnapshot,
  window: 20 | 60 | 252,
  benchmarkSymbol: string = 'SPY',
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<FactorAttributionResponse> {
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/attribution/run', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ snapshot, window, benchmark_symbol: benchmarkSymbol }),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(errorPayload?.detail ?? 'Attribution engine run failed')
  }

  return (await response.json()) as FactorAttributionResponse
}

export async function runMultiBenchmarkCorrelation(
  snapshot: ImportedSnapshot,
  lookbackDays: number = 252,
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<MultiBenchmarkCorrelationResult> {
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/correlation/multi', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ snapshot, lookback_days: lookbackDays }),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(errorPayload?.detail ?? 'Multi-benchmark correlation run failed')
  }

  return (await response.json()) as MultiBenchmarkCorrelationResult
}

/** Run the intra-portfolio correlation engine (Epic 17 — Exposure tab).
 *  Returns a holdings × holdings Pearson correlation matrix + summary stats
 *  over the requested lookback window. Synthetic-history trust. */
export async function runIntraCorrelationEngine(
  snapshot: ImportedSnapshot,
  lookbackDays: number = 60,
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<IntraCorrelationResult> {
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/correlation/intra', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ snapshot, lookback_days: lookbackDays }),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(errorPayload?.detail ?? 'Intra-portfolio correlation run failed')
  }

  return (await response.json()) as IntraCorrelationResult
}

/** Run the portfolio data-provenance engine (Epic 18 — Exposure tab).
 *  Returns which provider (FMP vs Yahoo Finance) priced each holding. */
export async function runProvenanceEngine(
  snapshot: ImportedSnapshot,
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<ProvenanceResult> {
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/provenance/run', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ snapshot }),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(errorPayload?.detail ?? 'Provenance run failed')
  }

  return (await response.json()) as ProvenanceResult
}

/** Read the local market-data cache footprint (Epic 20 — Cache control). */
export async function getCacheStats(
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<CacheStats> {
  const response = await fetch(resolvePortfolioEngineUrl('/api/cache/stats', apiUrlOptions), { method: 'GET' })
  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(errorPayload?.detail ?? 'Cache stats request failed')
  }
  return (await response.json()) as CacheStats
}

/** Clear the local market-data cache (all namespaces, or a single one). */
export async function clearCache(
  namespace?: string | null,
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<CacheClearResult> {
  const response = await fetch(resolvePortfolioEngineUrl('/api/cache/clear', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ namespace: namespace ?? null }),
  })
  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(errorPayload?.detail ?? 'Cache clear failed')
  }
  return (await response.json()) as CacheClearResult
}

/** Run the standalone drawdown analytics engine (Epic 13 — Risk tab).
 *  Returns the underwater curve + top-N episodes. `window` selects the
 *  lookback in trading days; `null` (or omitted) requests the maximum
 *  available history (capped by the engine at ~8 years).
 *  Per-field nullability is preserved on the unavailable path. */
export async function runDrawdownEngine(
  snapshot: PortfolioSnapshot,
  window: DrawdownWindow | null = null,
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<DrawdownEngineResponse> {
  const body: SnapshotAnalysisRequest & { window_trading_days?: DrawdownWindow } = {
    ...buildSnapshotAnalysisRequest(snapshot),
  }
  if (window !== null) {
    body.window_trading_days = window
  }
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/drawdown/run', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null
    const detail = errorPayload?.detail ?? `HTTP ${response.status}`
    throw new Error(`Drawdown engine run failed: ${detail}`)
  }

  return (await response.json()) as DrawdownEngineResponse
}

/** Run the standalone distribution / VaR analytics engine (Epic 13 — Risk tab).
 *  Returns daily return distribution + historical VaR_95 / VaR_99 / CVaR_95 +
 *  percentiles + distribution shape (mean / std / skew / excess kurt) +
 *  histogram. `window` defaults to 252 trading days. */
export async function runDistributionEngine(
  snapshot: PortfolioSnapshot,
  window: DistributionWindow = 252,
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<DistributionEngineResponse> {
  const body = {
    ...buildSnapshotAnalysisRequest(snapshot),
    window_trading_days: window,
  }
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/distribution/run', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null
    const detail = errorPayload?.detail ?? `HTTP ${response.status}`
    throw new Error(`Distribution engine run failed: ${detail}`)
  }

  return (await response.json()) as DistributionEngineResponse
}

/** Run the standalone stress-scenario engine (Epic 13 — Risk tab).
 *  Returns a list of scenario projections + engine-level trust. Per-scenario
 *  pcts may be null (status='unavailable') when the factor model could not
 *  be fit; in that case the wrapper trust is 'unavailable' and the UI must
 *  render an empty state, not zeroes. */
export async function runStressEngine(
  snapshot: PortfolioSnapshot,
  apiUrlOptions?: ResolveDesktopApiUrlOptions,
): Promise<StressEngineResponse> {
  const response = await fetch(resolvePortfolioEngineUrl('/api/engines/stress/run', apiUrlOptions), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildSnapshotAnalysisRequest(snapshot)),
  })

  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { detail?: string } | null
    const detail = errorPayload?.detail ?? `HTTP ${response.status}`
    throw new Error(`Stress engine run failed: ${detail}`)
  }

  return (await response.json()) as StressEngineResponse
}

export function composeDashboardAnalysisFromEngines(exposure: ExposureEngineResponse, diagnostics: DiagnosticsEngineResponse): DashboardAnalysis {
  return {
    snapshot: exposure.snapshot,
    overview: exposure.overview,
    source_status: null,
    run_metadata: null,
    daily_states: [],
    performance_series: [],
    range_metrics: null,
  }
}

export function composeDashboardAnalysisWithHistory(
  exposure: ExposureEngineResponse,
  history: DashboardHistoryEngineResponse,
): DashboardAnalysis {
  return {
    snapshot: exposure.snapshot,
    overview: exposure.overview,
    admission_summary: (exposure as { admission_summary?: DashboardAnalysis['admission_summary'] }).admission_summary ?? null,
    source_status: history.source_status ?? null,
    run_metadata: history.run_metadata,
    daily_states: history.daily_states,
    performance_series: history.performance_series,
    range_metrics: history.range_metrics ?? null,
  }
}

export function buildExposureFactorModel(result: Pick<ExposureAnalysis, 'benchmark' | 'factor_methodology' | 'factor_registry' | 'statistical_factor_model'>): ExposureFactorModelResponse {
  return {
    benchmark_symbol: result.statistical_factor_model.benchmark_symbol || result.benchmark?.symbol || 'SPY',
    methodology: result.factor_methodology || DEFAULT_FACTOR_MODEL_METHODOLOGY,
    factor_registry: result.factor_registry,
    statistical_factor_model: result.statistical_factor_model,
  }
}

export function buildPortfolioBaselineView(analysis: ImportedBaselineSource): PortfolioBaselineView {
  return {
    snapshot: analysis.snapshot,
    overview: analysis.overview,
  }
}
