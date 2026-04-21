import type { DashboardAnalysis, DashboardHistoryEngineResponse, DiagnosticsEngineResponse, ExposureAnalysis, ExposureEngineResponse, ExposureFactorModelResponse, ImportedBaselineSource, ImportedDashboardSource, ImportedDiagnosticsSource, ImportedExposureSource, PortfolioBaselineView } from './types'
import type { ImportedHistoryContext, PortfolioSnapshot } from './workspaceTypes'
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

export async function runExposureEngine(snapshot: PortfolioSnapshot): Promise<ExposureEngineResponse> {
  const response = await fetch('/api/engines/exposure/run', {
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

export async function runDiagnosticsEngine(snapshot: PortfolioSnapshot, historyContext?: ImportedHistoryContext | null): Promise<DiagnosticsEngineResponse> {
  const response = await fetch('/api/engines/diagnostics/run', {
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

export async function runImportedDiagnosticsEngine(snapshot: ImportedDashboardSource['snapshot']): Promise<DiagnosticsEngineResponse> {
  const response = await fetch('/api/engines/diagnostics/run-imported', {
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

export async function runDashboardHistoryEngine(snapshot: PortfolioSnapshot, historyContext: ImportedHistoryContext): Promise<DashboardHistoryEngineResponse> {
  const payload: DashboardHistoryRequest = {
    ...buildSnapshotAnalysisRequest(snapshot),
    history_context: buildHistoryContextRequest(historyContext),
  }

  const response = await fetch('/api/engines/dashboard-history/run', {
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

export async function runImportedDashboardHistory(snapshot: ImportedDashboardSource['snapshot']): Promise<DashboardHistoryEngineResponse> {
  const response = await fetch('/api/engines/dashboard-history/run-imported', {
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

export function buildImportedExposureView(analysis: ImportedExposureSource): ExposureAnalysis {
  return {
    snapshot: analysis.snapshot,
    provenance: analysis.provenance ?? null,
    run_metadata: analysis.run_metadata ?? null,
    diagnostics_run_metadata: analysis.diagnostics_run_metadata ?? null,
    overview: analysis.overview,
    lookthrough: analysis.lookthrough,
    lookthrough_sector_exposure: analysis.lookthrough_sector_exposure,
    market_overlap: analysis.market_overlap,
    current_state_concentration: analysis.current_state_concentration,
    risk_summary: analysis.risk_summary,
    rolling_risk: analysis.rolling_risk,
    relative_risk: analysis.relative_risk,
    volatility_regime: analysis.volatility_regime,
    factor_exposures: analysis.factor_exposures,
    model_reliability: analysis.model_reliability,
    factor_registry: analysis.factor_registry,
    factor_methodology: analysis.factor_methodology,
    statistical_factor_model: analysis.statistical_factor_model,
    stress_scenarios: analysis.stress_scenarios,
    benchmark: analysis.benchmark,
    scenario_preview: analysis.scenario_preview ?? null,
    exposure_availability: analysis.exposure_availability ?? null,
    availability: analysis.availability ?? null,
  }
}

export function buildImportedDashboardView(analysis: ImportedDashboardSource): DashboardAnalysis {
  return {
    snapshot: analysis.snapshot,
    overview: analysis.overview,
    performance_series: analysis.performance_series,
    daily_states: analysis.daily_states,
    source_status: analysis.source_status ?? null,
    run_metadata: analysis.run_metadata ?? null,
    range_metrics: analysis.range_metrics ?? null,
  }
}

export function buildPortfolioBaselineView(analysis: ImportedBaselineSource): PortfolioBaselineView {
  return {
    snapshot: analysis.snapshot,
    overview: analysis.overview,
  }
}

export function buildImportedDiagnosticsView(analysis: ImportedDiagnosticsSource): DiagnosticsEngineResponse {
  return {
    snapshot: analysis.snapshot,
    provenance: analysis.provenance,
    drawdown_summary: analysis.drawdown_summary,
    volatility_summary: analysis.volatility_summary,
    risk_concentration_summary: analysis.risk_concentration_summary,
    risk_summary: analysis.risk_summary,
    rolling_risk: analysis.rolling_risk,
    relative_risk: analysis.relative_risk,
    volatility_regime: analysis.volatility_regime,
    factor_exposures: analysis.factor_exposures,
    factor_shift_diagnostics: analysis.factor_shift_diagnostics,
    risk_contribution_breakdown: analysis.risk_contribution_breakdown,
    model_reliability: analysis.model_reliability,
    factor_registry: analysis.factor_registry,
    factor_methodology: analysis.factor_methodology,
    statistical_factor_model: analysis.statistical_factor_model,
    stress_scenarios: analysis.stress_scenarios,
    run_metadata: analysis.run_metadata,
    availability: analysis.availability,
  }
}
