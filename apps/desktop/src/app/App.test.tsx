import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture, createFf2026DiagnosticsEngineFixture, createFf2026ExposureEngineFixture, createIb2026DiagnosticsEngineFixture, createIb2026ExposureEngineFixture, createImportedBootstrapResponseFixture, createImportedDashboardHistoryFixture } from '../test/portfolioFixtures'
import {
  ff2026DashboardGolden,
  ff2026ImportedDashboardGoldenFixture,
  ib2026DashboardGolden,
  ib2026ImportedDashboardGoldenFixture,
} from '../test/dashboardGoldens'
import { App } from './App'
import * as portfolioWorkspaceStorage from './portfolioWorkspaceStorage'
import { mapImportedHistoryContextToWorkspace } from '../features/portfolio/importedBootstrapMapper'
import type { ConstructionArtifactReplayValidationResponse, HypotheticalReplayResponse, ImportedSnapshot, OptimizerHandoffReplayResponse, OptimizerHandoffValidationResponse, OptimizerPersistedArtifactReference, PortfolioAllocationBacktestResponse, PortfolioOverview } from '../features/portfolio/types'
import type { ImportedHistoryContext, ImportedNodeSource, PortfolioNode, PortfolioSnapshot, PortfolioWorkspace, ReplacementIntentDraftArtifact, WorkingDraft, WorkspaceState } from '../features/portfolio/workspaceTypes'

const exposurePayload = createExposureEngineFixture()
const diagnosticsPayload = createDiagnosticsEngineFixture()
const bootstrapPayload = createImportedBootstrapResponseFixture()
const dashboardHistoryPayload = createImportedDashboardHistoryFixture()

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function requestPathname(input: RequestInfo | URL) {
  const rawUrl = typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.toString()
      : input.url
  return new URL(rawUrl, 'http://localhost').pathname
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit) {
  if (init?.method) return init.method.toUpperCase()
  if (typeof input !== 'string' && !(input instanceof URL) && input.method) return input.method.toUpperCase()
  return 'GET'
}

function installFetchMock(handler: (input: RequestInfo | URL, init?: RequestInit) => Response | Promise<Response>) {
  return vi.stubGlobal('fetch', vi.fn(handler))
}

function cloneMutable<T>(value: unknown): T {
  return JSON.parse(JSON.stringify(value)) as T
}

const ib2026MutableSnapshot = cloneMutable<ImportedSnapshot>(ib2026ImportedDashboardGoldenFixture.snapshot)
const ff2026MutableSnapshot = cloneMutable<ImportedSnapshot>(ff2026ImportedDashboardGoldenFixture.snapshot)
const ib2026MutableOverview = cloneMutable<PortfolioOverview>(ib2026ImportedDashboardGoldenFixture.overview)
const ff2026MutableOverview = cloneMutable<PortfolioOverview>(ff2026ImportedDashboardGoldenFixture.overview)

const ib2026LoadedFiles = [...ib2026DashboardGolden.loadedFiles]
const ff2026LoadedFiles = [...ff2026DashboardGolden.loadedFiles]

const ib2026DashboardHistoryPayload = {
  performance_series: ib2026ImportedDashboardGoldenFixture.performance_series,
  daily_states: ib2026ImportedDashboardGoldenFixture.daily_states,
  source_status: ib2026ImportedDashboardGoldenFixture.source_status,
  benchmark: ib2026ImportedDashboardGoldenFixture.benchmark,
  range_metrics: ib2026ImportedDashboardGoldenFixture.range_metrics,
}
const ib2026ExposurePayload = createIb2026ExposureEngineFixture()
const ib2026DiagnosticsPayload = createIb2026DiagnosticsEngineFixture()
const ib2026BootstrapPayload = {
  snapshot: ib2026MutableSnapshot,
  overview: ib2026MutableOverview,
  risk_summary: ib2026ImportedDashboardGoldenFixture.risk_summary,
   history_context: {
     benchmark_symbol: 'SPY',
     statement_period: ib2026ImportedDashboardGoldenFixture.snapshot.statement.statement_period,
     imported_at: ib2026ImportedDashboardGoldenFixture.snapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
     importer: ib2026ImportedDashboardGoldenFixture.snapshot.statement.importer,
     source_file_names: ib2026LoadedFiles,
     history_start_date: ib2026ImportedDashboardGoldenFixture.daily_states[0]?.date ?? null,
     history_end_date: ib2026ImportedDashboardGoldenFixture.daily_states[ib2026ImportedDashboardGoldenFixture.daily_states.length - 1]?.date ?? null,
   },
}
const ff2026DashboardHistoryPayload = {
  performance_series: ff2026ImportedDashboardGoldenFixture.performance_series,
  daily_states: ff2026ImportedDashboardGoldenFixture.daily_states,
  source_status: ff2026ImportedDashboardGoldenFixture.source_status,
  benchmark: ff2026ImportedDashboardGoldenFixture.benchmark,
  range_metrics: ff2026ImportedDashboardGoldenFixture.range_metrics,
}
const ff2026ExposurePayload = createFf2026ExposureEngineFixture()
const ff2026DiagnosticsPayload = createFf2026DiagnosticsEngineFixture()
const ff2026BootstrapPayload = {
  snapshot: ff2026MutableSnapshot,
  overview: ff2026MutableOverview,
  risk_summary: ff2026ImportedDashboardGoldenFixture.risk_summary,
   history_context: {
     benchmark_symbol: 'SPY',
     statement_period: ff2026ImportedDashboardGoldenFixture.snapshot.statement.statement_period,
     imported_at: ff2026ImportedDashboardGoldenFixture.snapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
     importer: ff2026ImportedDashboardGoldenFixture.snapshot.statement.importer,
     source_file_names: ff2026LoadedFiles,
     history_start_date: ff2026ImportedDashboardGoldenFixture.daily_states[0]?.date ?? null,
     history_end_date: ff2026ImportedDashboardGoldenFixture.daily_states[ff2026ImportedDashboardGoldenFixture.daily_states.length - 1]?.date ?? null,
   },
}
const appendedExposurePayload = {
  ...exposurePayload,
  snapshot: {
    ...exposurePayload.snapshot,
    statement: {
      ...exposurePayload.snapshot.statement,
      statement_period: '2025-01-01 - 2026-04-08',
    },
    statements: [
      ...exposurePayload.snapshot.statements,
      {
        ...exposurePayload.snapshot.statements[0],
        statement_period: '2026-01-01 - 2026-04-08',
        source_path: 'C:\\docs\\IB2026.pdf',
        imported_at: '2026-04-10T00:05:00Z',
        page_count: 17,
      },
    ],
  },
}
const appendedDiagnosticsPayload = {
  ...diagnosticsPayload,
  snapshot: {
    ...diagnosticsPayload.snapshot,
    statement: {
      ...diagnosticsPayload.snapshot.statement,
      statement_period: '2025-01-01 - 2026-04-08',
    },
    statements: [
      ...diagnosticsPayload.snapshot.statements,
      {
        ...diagnosticsPayload.snapshot.statements[0],
        statement_period: '2026-01-01 - 2026-04-08',
        source_path: 'C:\\docs\\IB2026.pdf',
        imported_at: '2026-04-10T00:05:00Z',
        page_count: 17,
      },
    ],
  },
}

const allocationBacktestPayload: PortfolioAllocationBacktestResponse = {
  methodology: 'm',
  investor_economics_status: { status: 'available', reason: null },
  reference_result: {
    portfolio_name: 'Reference',
    benchmark_symbol: 'SPY',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    observation_count: 2,
    rebalance_frequency: 'monthly',
    commission_bps: 0,
    slippage_bps: 0,
    drift_tolerance_pct: null,
    assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
    status: 'ok',
    investor_economics_status: { status: 'available', reason: null },
    instrument_metadata: [],
    starting_weights: [],
    ending_weights: [],
    metrics: { total_return_pct: 0.5, annualized_return_pct: 0.5, annualized_volatility_pct: 10, downside_volatility_pct: 6, max_drawdown_pct: -4, sharpe_ratio: 0.4, sortino_ratio: 0.7, benchmark_return_pct: 1, excess_return_pct: -0.5, tracking_error_pct: 3, information_ratio: -0.1, beta_vs_benchmark: 1, correlation_vs_benchmark: 0.9, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
    equity_curve: [{ date: '2024-01-02', equity: 100000, cash: 0, gross_exposure: 100000, drawdown_pct: 0 }, { date: '2024-12-31', equity: 100500, cash: 0, gross_exposure: 100500, drawdown_pct: -4 }],
    rebalance_events: [],
    trades: [],
  },
  candidate_result: {
    portfolio_name: 'Candidate',
    benchmark_symbol: 'SPY',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    observation_count: 2,
    rebalance_frequency: 'monthly',
    commission_bps: 0,
    slippage_bps: 0,
    drift_tolerance_pct: null,
    assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
    status: 'ok',
    investor_economics_status: { status: 'available', reason: null },
    instrument_metadata: [],
    starting_weights: [],
    ending_weights: [],
    metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
    equity_curve: [{ date: '2024-01-02', equity: 100000, cash: 0, gross_exposure: 100000, drawdown_pct: 0 }, { date: '2024-12-31', equity: 101000, cash: 0, gross_exposure: 101000, drawdown_pct: -1 }],
    rebalance_events: [],
    trades: [],
  },
  comparison: { total_return_diff_pct: 0.5, annualized_return_diff_pct: 0.5, benchmark_return_diff_pct: 0, annualized_volatility_diff_pct: -1, downside_volatility_diff_pct: -1, max_drawdown_diff_pct: 1, sharpe_diff: 0.6, sortino_diff: 0.3, excess_return_diff_pct: 0.5, tracking_error_diff_pct: 1, information_ratio_diff: 0.1, beta_diff: -0.2, correlation_diff: -0.05, total_turnover_diff_pct: 0, total_cost_diff: 0 },
  reference_diagnostics: {
    provenance: { snapshot_basis: 'synthetic_replay_snapshot', historical_basis: 'market_data_history', note: 'Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.' },
    factor_snapshot: [{ key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 1, target_exposure: null, primary_mapping: null, alternative_mappings: [], ucits_examples: [], mapping_quality: 'high', description: 'broad market' }],
    volatility_snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: 10, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: 6, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: 3, current_drawdown_pct: -2, max_drawdown_pct: -4, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null },
    risk_contribution: null,
    stress_scenarios: [],
  },
  candidate_diagnostics: {
    provenance: { snapshot_basis: 'synthetic_replay_snapshot', historical_basis: 'market_data_history', note: 'Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.' },
    factor_snapshot: [{ key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 0.8, target_exposure: null, primary_mapping: null, alternative_mappings: [], ucits_examples: [], mapping_quality: 'high', description: 'broad market' }],
    volatility_snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: 9, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: 5, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: 4, current_drawdown_pct: -1.5, max_drawdown_pct: -3, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null },
    risk_contribution: null,
    stress_scenarios: [],
  },
  diagnostics_comparison: {
    factor_exposure_changes: [{ key: 'market', label: 'Market', baseline_value: 1, candidate_value: 0.8, delta_value: -0.2 }],
    top_factor_exposure_change: { key: 'market', label: 'Market', baseline_value: 1, candidate_value: 0.8, delta_value: -0.2, selection_rule: 'largest_absolute_delta', rationale: 'Largest valid factor exposure delta in this group (candidate - baseline).' },
    volatility_changes: [{ key: 'annualized_volatility', label: 'Annualized Volatility', baseline_value: 10, candidate_value: 9, delta_value: -1 }],
    top_volatility_change: { key: 'annualized_volatility', label: 'Annualized Volatility', baseline_value: 10, candidate_value: 9, delta_value: -1, selection_rule: 'fixed_priority', rationale: 'Selected by fixed priority order: max drawdown, then annualized volatility, then downside volatility.' },
    risk_contribution_changes: [],
    top_risk_contribution_change: null,
    concentration_changes: [{ key: 'factor_hhi', label: 'Factor HHI', baseline_value: 0.36, candidate_value: 0.2, delta_value: -0.16 }],
    top_concentration_change: { key: 'factor_hhi', label: 'Factor HHI', baseline_value: 0.36, candidate_value: 0.2, delta_value: -0.16, selection_rule: 'fixed_priority', rationale: 'Selected by fixed priority order: factor HHI, then top 1 position risk share.' },
    stress_scenario_changes: [],
    top_stress_scenario_change: null,
  },
}

const persistedSnapshot: PortfolioSnapshot = {
  snapshotVersion: 1,
  baseCurrency: 'USD',
  importedMeta: {
    importer: 'interactive_brokers',
    statementPeriod: '2025-01-01 - 2025-12-31',
    importedAt: '2026-04-10T00:00:00Z',
    sourceFileNames: ['IB2025.pdf'],
  },
  positions: [{ symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
  cashBalances: [{ currency: 'USD', amount: 1000 }],
  metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
}

const variantSnapshot: PortfolioSnapshot = {
  ...persistedSnapshot,
  importedMeta: {
    ...persistedSnapshot.importedMeta,
    statementPeriod: '2026-01-01 - 2026-04-10',
    sourceFileNames: ['IB2025.pdf', 'IB2026.pdf'],
  },
  positions: [{ symbol: 'AAPL', marketValue: 15000, quantity: 15, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
  cashBalances: [{ currency: 'USD', amount: 500 }],
}

const variantExposurePayload = {
  ...exposurePayload,
  snapshot: {
    ...exposurePayload.snapshot,
    statement: {
      ...exposurePayload.snapshot.statement,
      statement_period: '2026-01-01 - 2026-04-10',
    },
    statement_totals: {
      ...exposurePayload.snapshot.statement_totals,
      ending_nav: 15500,
      starting_nav: 14000,
    },
    positions: [{ symbol: 'AAPL', quantity: 15, market_value: 15000, currency: 'USD', as_of_date: '2026-04-10' }],
    cash_balances: [{ currency: 'USD', ending_cash: 500 }],
  },
  overview: {
    ...exposurePayload.overview,
    total_market_value: 15500,
  },
}

const variantDashboardHistoryPayload = {
  ...dashboardHistoryPayload,
  daily_states: [
    { ...dashboardHistoryPayload.daily_states[0], total_portfolio_value: 14000, external_cash_flow: 0 },
    { ...dashboardHistoryPayload.daily_states[dashboardHistoryPayload.daily_states.length - 1], total_portfolio_value: 15500, external_cash_flow: 0 },
  ],
  performance_series: [
    { ...dashboardHistoryPayload.performance_series[0], portfolio_value: 14000, benchmark_price: 100, portfolio_return_pct: 0, benchmark_return_pct: 0 },
    { ...dashboardHistoryPayload.performance_series[dashboardHistoryPayload.performance_series.length - 1], portfolio_value: 15500, benchmark_price: 105, portfolio_return_pct: 10.71, benchmark_return_pct: 5 },
  ],
}

function buildHistorySource(historyContext: ImportedHistoryContext | null, importedHistorySnapshot: ImportedSnapshot | null) {
  if (importedHistorySnapshot) {
    return {
      kind: 'imported_replay' as const,
      historyContext,
      importedHistorySnapshot,
    }
  }
  if (historyContext) {
    return {
      kind: 'history_context' as const,
      historyContext,
      importedHistorySnapshot: null,
    }
  }
  return {
    kind: 'none' as const,
    historyContext: null,
    importedHistorySnapshot: null,
  }
}

function buildImportedSource(input: {
  importedFileNames: string[]
  importedAt: string
  importer: ImportedNodeSource['importer']
  baseCurrency: string | null
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
}): ImportedNodeSource {
  return {
    importedFileNames: input.importedFileNames,
    importedAt: input.importedAt,
    importer: input.importer,
    baseCurrency: input.baseCurrency,
    historySource: buildHistorySource(input.historyContext ?? null, input.importedHistorySnapshot ?? null),
  }
}

function buildArtifactReviewSource(constructionArtifactId: string, openedAt: string) {
  return {
    kind: 'persisted_construction_artifact' as const,
    constructionArtifactId,
    openedAt,
    reviewBasis: {
      basisVersion: 1 as const,
      basisKind: 'persisted_construction_artifact_review' as const,
      constructionArtifactId,
      openedAt,
      benchmarkSymbol: 'SPY',
      baseCurrency: 'USD',
      replayWindow: {
        startDate: '2024-01-01',
        endDate: '2024-12-31',
      },
      baselineWeights: [{ symbol: 'AAPL', target_weight: 0.6 }],
      candidateWeights: [{ symbol: 'MSFT', target_weight: 0.6 }],
    },
  }
}

function buildOptimizerHandoffReviewSource(handoffReference: OptimizerPersistedArtifactReference, openedAt: string) {
  return {
    kind: 'persisted_optimizer_handoff' as const,
    handoffReference,
    openedAt,
    reviewBasis: {
      basisVersion: 1 as const,
      basisKind: 'persisted_optimizer_handoff_review' as const,
      handoffReference,
      openedAt,
      benchmarkSymbol: 'SPY',
      baseCurrency: 'USD',
      replayWindow: {
        startDate: '2024-01-01',
        endDate: '2024-12-31',
      },
      baselineWeights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
      candidateWeights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
    },
  }
}

function makeOptimizerHandoffReference(): OptimizerPersistedArtifactReference {
  return {
    reference_kind: 'optimizer_handoff_reference_v1',
    handoff_id: 'optimizer_handoff_123',
    artifact_id: 'optimizer_artifact_123',
    manifest_path: '/tmp/optimizer_handoff_123/manifest.json',
    artifact_path: '/tmp/optimizer_handoff_123/artifact.json',
  }
}

const ib2026HistoryContext = mapImportedHistoryContextToWorkspace(ib2026BootstrapPayload.history_context)
const ff2026HistoryContext = mapImportedHistoryContextToWorkspace(ff2026BootstrapPayload.history_context)

function mockImportedWorkspace(): { workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: WorkingDraft; workspaceState: WorkspaceState } {
  return {
    workspace: { id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) },
    rootNode: { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base' as const, name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 0, changedSectorsCount: 0, grossExposureDelta: 0, netCapitalDelta: 0 }, portfolioSnapshot: { snapshotVersion: 1, baseCurrency: 'USD', importedMeta: { importer: 'interactive_brokers', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', sourceFileNames: ['IB2025.pdf'] }, positions: [], cashBalances: [], metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] } } },
    draft: { id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: { snapshotVersion: 1, baseCurrency: 'USD', importedMeta: { importer: 'interactive_brokers', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', sourceFileNames: ['IB2025.pdf'] }, positions: [], cashBalances: [], metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] } } },
    workspaceState: { workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', lastOpenedAt: '2026-04-10T00:00:00Z' },
  }
}

function makeReplacementIntent(): ReplacementIntentDraftArtifact {
  return { kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1 }
}

function makeHypotheticalReplay(): HypotheticalReplayResponse {
  return {
    proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
    derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
    baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
    candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
    replay: allocationBacktestPayload,
    warnings: ['Candidate weights are derived from a single-symbol replacement intent and remain hypothetical replay inputs only.'],
  }
}

function makeFormedCandidateArtifact() {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    formation: {
      formation: { kind: 'single_replacement_candidate_formation', status: 'ok' },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1', cash_treatment: 'excluded_from_candidate_formation_basis', position_scope: 'positive_market_value_positions_only' },
      baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
      candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
      formation_summary: { incumbent_start_weight: 1, candidate_start_weight: 1, unchanged_positions_count: 0, baseline_positions_count: 1, candidate_positions_count: 1, starting_turnover_pct: 1 },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', candidate_truth_class: 'hypothetical_candidate_input_only', formation_truth_class: 'candidate_formation_derived', note: 'Candidate formation is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed.' },
      warnings: [],
      rejection_reason: null,
    },
  }
}

function makeConstructedCandidateArtifact() {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    constructionRuleId: 'same_weight_substitution_v1',
    construction: {
      construction: { kind: 'single_replacement_construction', status: 'ok', rule_id: 'same_weight_substitution_v1' },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      inputs: { baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], construction_rule: 'same_weight_substitution_v1', incumbent_start_weight: 1 },
      outputs: { candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }], starting_turnover_pct: 1, unchanged_positions_count: 0 },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', construction_basis: 'explicit_single_replacement_rule', cash_treatment: 'excluded_from_construction_basis', position_scope: 'positive_market_value_positions_only' },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', construction_truth_class: 'candidate_construction_derived', candidate_truth_class: 'hypothetical_candidate_input_only', note: 'Candidate construction is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed and no replay has been run.' },
      warnings: [],
      rejection_reason: null,
    },
  }
}

function makeConstructionConstraintValidationArtifact(status: 'ok' | 'blocked' | 'rejected' = 'ok') {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    constructionRuleId: 'same_weight_substitution_v1',
    validation: {
      validation: {
        kind: 'single_replacement_construction_constraint_validation',
        status,
        constraint_set_id: 'single_replacement_construction_constraints_v1',
      },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      construction: { kind: 'single_replacement_construction', status: 'ok', rule_id: 'same_weight_substitution_v1' },
      derivation: { validation_timing: 'post_construction_pre_replay', validation_basis: 'explicit_constraint_set', candidate_input_source: 'constructed_candidate_payload', constraint_set_id: 'single_replacement_construction_constraints_v1' },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', construction_truth_class: 'candidate_construction_derived', candidate_truth_class: 'hypothetical_candidate_input_only', constraint_validation_truth_class: 'constraint_validation_derived', note: 'Constraint validation remains review-only.' },
      evaluations: [
        { constraint_id: 'weight_sum_matches_rule', severity: 'hard_block', status: status === 'blocked' ? 'fail' : 'pass', message: status === 'blocked' ? 'Constraint failed.' : 'Constraint passed.', rationale: null, actual_value: status === 'blocked' ? 0.97 : 1, expected_value: 1, operator: '==' },
      ],
      blocking_constraint_ids: status === 'blocked' ? ['weight_sum_matches_rule'] : [],
      warnings: [],
      rejection_reason: status === 'rejected' ? 'constructed candidate could not be evaluated safely' : null,
    },
  }
}

function makeSelectedConstructionRuleArtifact(selectedRuleId: 'same_weight_substitution_v1' | 'fixed_split_50_50_substitution_v2' = 'same_weight_substitution_v1') {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    selectedRuleId,
  }
}

function makeConstructionArtifactReplayResponse() {
  return {
    construction_artifact_id: 'artifact-123',
    truth_separation: {
      baseline_truth: 'imported_portfolio_snapshot' as const,
      candidate_truth: 'hypothetical_construction_artifact' as const,
      candidate_applied: false as const,
      consumption_mode: 'explicit_reference_only' as const,
    },
    replay_provenance: {
      source: 'construction_artifact_reference' as const,
      construction_artifact_id: 'artifact-123',
      policy_id: 'policy-1',
      policy_definition_id: 'policy-def-1',
      ranked_universe_artifact_id: 'ranked-1',
      ranking_id: 'ranking-1',
      ranking_methodology_id: 'method-1',
      current_portfolio_artifact_id: 'portfolio-1',
      hard_constraints: {
        full_investment: true as const,
        long_only: true as const,
        eligible_ranked_universe_only: true as const,
        max_position_weight: 0.6,
        min_position_weight: null,
        max_turnover_weight: null,
        max_trade_intent_count: null,
      },
      baseline_input_source: 'normalized_inputs.current_portfolio_weights' as const,
      candidate_input_source: 'final_target_weights' as const,
      selection_rule_trace: {
        rule_ids: ['rule-1'],
        steps: [{
          rule_id: 'rule-1',
          rule_order: 1,
          input_candidate_symbols: ['AAPL'],
          output_candidate_symbols: ['MSFT'],
        }],
      },
      turnover_diagnostics_status: 'available' as const,
      turnover_diagnostics_v1: {
        diagnostics_version: 'construction_turnover_diagnostics_v1' as const,
        source: 'persisted_construction_artifact' as const,
        diagnostic_truth: 'artifact_backed_hypothetical_construction_diagnostics_only' as const,
        turnover_basis_method_version: 'half_l1_weight_delta_union_v1' as const,
        reported_value_status: 'computed' as const,
        reported_turnover_weight: 0.2,
        inclusion_flags: {
          uses_current_and_target_weight_union: true as const,
          includes_initiations: true as const,
          includes_exits: true as const,
          includes_zero_delta_positions_in_trade_intent_context: true as const,
          excludes_zero_delta_positions_from_reported_turnover_sum: true as const,
        },
        trade_intent_context: { source_field: 'trade_intents' as const, intent_count: 2 },
        feasibility_context: {
          artifact_status: 'feasible' as const,
          failure_reasons_field: 'failure_reasons' as const,
          turnover_failure_reason_present: false,
        },
        constraint_context: {
          constraint_id: 'max_turnover_weight' as const,
          requested: false,
          limit_weight: null,
          evaluation_status: 'not_evaluated' as const,
        },
        symbol_contributions: [
          {
            symbol: 'AAPL',
            action: 'hold' as const,
            current_weight: 0.5,
            target_weight: 0.5,
            delta_weight: 0,
            absolute_delta_weight: 0,
            turnover_contribution_weight: 0,
            contribution_fraction_of_reported_turnover: 0,
            included_in_reported_turnover: false,
          },
          {
            symbol: 'MSFT',
            action: 'initiate' as const,
            current_weight: 0,
            target_weight: 0.4,
            delta_weight: 0.4,
            absolute_delta_weight: 0.4,
            turnover_contribution_weight: 0.2,
            contribution_fraction_of_reported_turnover: 1,
            included_in_reported_turnover: true,
          },
        ],
      },
      weighting_trace_status: 'available' as const,
      weighting_trace_v1: {
        trace_version: 'weighting_trace_v1' as const,
        source: 'persisted_construction_artifact' as const,
        diagnostic_truth: 'artifact_backed_hypothetical_construction_diagnostics_only' as const,
        policy_id: 'policy-1',
        policy_definition_id: 'policy-def-1',
        stages: [],
        normalization: {
          normalization_source: 'raw_weight_numerator_to_seed_weight' as const,
          normalization_applied: false,
          input_metric_id: 'raw_weight_numerator' as const,
          output_metric_id: 'seed_weight' as const,
          raw_value_sum: null,
          normalized_value_sum: null,
          rounding_scale: null,
          normalization_method: 'not_applicable' as const,
          residual_reconciliation_symbol: null,
          residual_reconciliation_delta: null,
        },
        artifact_binding: {
          binding_status: 'final_target_weights_persisted' as const,
          final_target_weights_present: true,
        },
      },
    },
    baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }],
    candidate_weights: [{ symbol: 'MSFT', target_weight: 0.6 }],
    effective_replay_params: {
      benchmark_symbol: 'SPY' as const,
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      initial_capital: 100000,
      rebalance_frequency: 'monthly' as const,
      base_currency: 'USD',
      commission_bps: 0,
      slippage_bps: 0,
      drift_tolerance_pct: null,
      price_basis: 'adjusted_close' as const,
      execution_price_field: 'close' as const,
      execution_lag_days: 1,
      symbol_overrides: {},
    },
    replay: allocationBacktestPayload,
  }
}

function makeConstructionArtifactReplayValidationResponse(overrides: Partial<ConstructionArtifactReplayValidationResponse> = {}): ConstructionArtifactReplayValidationResponse {
  return {
    construction_artifact_id: 'artifact-123',
    effective_replay_params: {
      benchmark_symbol: 'SPY',
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      initial_capital: 100000,
      rebalance_frequency: 'monthly',
      base_currency: 'USD',
      commission_bps: 0,
      slippage_bps: 0,
      drift_tolerance_pct: null,
      price_basis: 'adjusted_close',
      execution_price_field: 'close',
      execution_lag_days: 1,
      symbol_overrides: {},
    },
    preview_handoff: {
      handoff_kind: 'construction_artifact_preview_handoff_v1',
      construction_artifact_id: 'artifact-123',
      effective_replay_params: {
        benchmark_symbol: 'SPY',
        start_date: '2024-01-01',
        end_date: '2024-12-31',
        initial_capital: 100000,
        rebalance_frequency: 'monthly',
        base_currency: 'USD',
        commission_bps: 0,
        slippage_bps: 0,
        drift_tolerance_pct: null,
        price_basis: 'adjusted_close',
        execution_price_field: 'close',
        execution_lag_days: 1,
        symbol_overrides: {},
      },
    },
    open_payload: null,
    ...overrides,
  }
}

function makeOptimizerHandoffValidationResponse(overrides: Partial<OptimizerHandoffValidationResponse> = {}): OptimizerHandoffValidationResponse {
  return {
    handoff_id: 'optimizer_handoff_123',
    artifact_id: 'optimizer_artifact_123',
    source_portfolio_snapshot_id: 'portfolio_snapshot_123',
    truth_separation: {
      source_truth: 'persisted_hypothetical_optimizer_handoff',
      holdings_truth: 'imported_portfolio_snapshot',
      optimizer_output_applied: false,
      consumption_mode: 'explicit_reference_only',
    },
    eligible_replay_window: {
      source: 'persisted_return_basis_attestation',
      benchmark_symbol: 'SPY',
      as_of_date: '2024-12-31',
      start_date: '2024-01-01',
      end_date: '2024-12-31',
    },
    provenance: {
      source: 'optimizer_handoff_reference',
      benchmark_id: 'benchmark_spy_demo_v1',
      benchmark_version: '2024-04-15',
      benchmark_symbol: 'SPY',
      objective: {
        objective_id: 'minimize_l2_distance_to_benchmark',
        benchmark_relative: true,
        description: 'Minimize squared distance to benchmark weights inside the hard-constraint set.',
        alpha_signal_id: null,
        requires_alpha_package: false,
      },
      replay_output_policy: {
        source: 'persisted_return_basis_attestation',
        section_trust: {
          benchmark_relative_path: 'degraded_unverified_return_basis',
          factor_model_path: 'degraded_unverified_return_basis',
          risk_contribution_path: 'degraded_unverified_return_basis',
        },
        eligible_families: [],
        withheld_families: ['benchmark_relative_volatility_outputs', 'factor_exposure_outputs'],
      },
      artifact_state: 'fresh',
      constraint_set_fingerprint: 'constraint-fingerprint-1',
    },
    validation_status: 'ok',
    evaluations: [],
    blocking_rule_ids: [],
    warnings: [],
    ...overrides,
  }
}

function makeOptimizerHandoffReplayResponse(): OptimizerHandoffReplayResponse {
  return {
    handoff_id: 'optimizer_handoff_123',
    artifact_id: 'optimizer_artifact_123',
    source_portfolio_snapshot_id: 'portfolio_snapshot_123',
    truth_separation: {
      baseline_truth: 'imported_portfolio_snapshot',
      candidate_truth: 'hypothetical_optimizer_handoff',
      candidate_applied: false,
      consumption_mode: 'explicit_reference_only',
    },
    replay_provenance: {
      source: 'optimizer_handoff_reference',
      benchmark_id: 'benchmark_spy_demo_v1',
      benchmark_version: '2024-04-15',
      benchmark_symbol: 'SPY',
      return_basis_attestation: {
        benchmark_symbol: 'SPY',
        as_of_date: '2024-12-31',
        history_start_date: '2024-01-01',
        history_end_date: '2024-12-31',
        factor_proxy_symbols: ['QQQ'],
        benchmark_return_basis_contract: 'unverified_adjusted_proxy',
        factor_return_basis_contract: 'unverified_adjusted_proxy',
        factor_basis_path: 'degraded_unverified_return_basis',
        section_trust: {
          benchmark_relative_path: 'degraded_unverified_return_basis',
          factor_model_path: 'degraded_unverified_return_basis',
          risk_contribution_path: 'degraded_unverified_return_basis',
        },
        evidence: {
          benchmark_history: { verification_status: 'unverified', economic_basis: 'adjusted_close_proxy', construction_method: 'vendor_adjusted_close', disqualifiers: [], fallbacks_used: [], source_price_field: 'adj_close' },
          factor_history: { verification_status: 'unverified', economic_basis: 'adjusted_close_proxy', construction_method: 'vendor_adjusted_close', disqualifiers: [], fallbacks_used: [], source_price_field: 'adj_close' },
        },
      },
      replay_output_policy: {
        source: 'persisted_return_basis_attestation',
        section_trust: {
          benchmark_relative_path: 'degraded_unverified_return_basis',
          factor_model_path: 'degraded_unverified_return_basis',
          risk_contribution_path: 'degraded_unverified_return_basis',
        },
        eligible_families: [],
        withheld_families: ['benchmark_relative_volatility_outputs', 'factor_exposure_outputs'],
      },
      artifact_state: 'fresh',
      optimizer_status: 'feasible',
      constraint_set_fingerprint: 'constraint-fingerprint-1',
    },
    optimizer_context: {
      objective: {
        objective_id: 'minimize_l2_distance_to_benchmark',
        benchmark_relative: true,
        description: 'Minimize squared distance to benchmark weights inside the hard-constraint set.',
        alpha_signal_id: null,
        requires_alpha_package: false,
      },
      penalty_ids: [],
      artifact_state: 'fresh',
      stale_inputs: [],
      degraded_inputs: [],
      reasons: [],
      run_summary: { engine_id: 'optimizer_engine_v1', solver_id: 'solver_v1', methodology_id: 'optimizer_methodology_v1' },
      diagnostics: { turnover: 0.2, active_share: 0.1 },
      binding_constraints: [],
      violated_constraints: [],
      benchmark_relative_attestations: [],
      binding_constraint_evaluations: [],
    },
    baseline_weights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
    candidate_weights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
    replay: allocationBacktestPayload,
  }
}

function makeEtfRankingPayload() {
  return {
    schema_version: 'etf_ranking_artifact_v1',
    artifact_id: 'etf_ranking_artifact_sector_1',
    ranking_id: 'etf_ranking_engine_v1',
    title: 'ETF Ranking Engine',
    as_of_date: '2026-04-15',
    benchmark_symbol: 'SPY',
    universe: ['IUFS', 'IUHC', 'VDST'],
    lookback_months: 6,
    price_basis: 'close',
    methodology: 'm',
    effective_peer_group: 'Sector UCITS ETF',
    effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 },
    source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' },
    warnings: { confidence: 'medium', warnings: ['Implementation-fit support is not complete across the ranked universe.'], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] },
    request: { peer_group: 'Sector UCITS ETF', universe: ['IUFS', 'IUHC', 'VDST'], benchmark_symbol: 'SPY', lookback_months: 6 },
    effective_inputs: {
      effective_peer_group: 'Sector UCITS ETF',
      effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 },
      requested_universe: ['IUFS', 'IUHC', 'VDST'],
      evaluated_universe: ['IUFS', 'IUHC'],
      excluded_symbols: [{ symbol: 'VDST', reason: 'instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF' }],
    },
    run_metadata: {
      ranking_id: 'etf_ranking_engine_v1',
      methodology_id: 'etf_ranking_methodology_v1',
      methodology: 'm',
      as_of_date: '2026-04-15',
      ranking_basis_date: '2026-04-15',
      price_basis: 'close',
      source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' },
      confidence: 'medium',
    },
    ranked_universe: [
      {
        rank: 1,
        symbol: 'IUFS',
        composite_score: 0.8123,
        instrument: { symbol: 'IUFS', name: 'iShares S&P 500 Financials Sector UCITS ETF', asset_class: 'etf', sector: 'Financials', category: 'Sector UCITS ETF', currency: 'USD' },
        component_scores: {
          momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 11.2, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 },
          benchmark_relative_strength: { label: 'Benchmark-relative strength', direction: 'higher_is_better', raw_value: 4.2, raw_unit: 'pct', normalized_score: 1, weight: 0.2, weighted_score: 0.2 },
          realized_volatility: { label: 'Realized volatility', direction: 'lower_is_better', raw_value: 14.4, raw_unit: 'pct', normalized_score: 0.7, weight: 0.15, weighted_score: 0.105 },
          max_drawdown: { label: 'Max drawdown', direction: 'lower_is_better', raw_value: 8.1, raw_unit: 'pct', normalized_score: 0.75, weight: 0.1, weighted_score: 0.075 },
          liquidity: { label: 'Median dollar volume', direction: 'higher_is_better', raw_value: 13.1, raw_unit: 'score', normalized_score: 0.8, weight: 0.1, weighted_score: 0.08 },
          implementation_fit: { label: 'Implementation fit', direction: 'higher_is_better', raw_value: 1, raw_unit: 'score', normalized_score: 1, weight: 0.05, weighted_score: 0.05 },
        },
      },
      {
        rank: 2,
        symbol: 'IUHC',
        composite_score: 0.7345,
        instrument: { symbol: 'IUHC', name: 'iShares S&P 500 Health Care Sector UCITS ETF', asset_class: 'etf', sector: 'Health Care', category: 'Sector UCITS ETF', currency: 'USD' },
        component_scores: {
          momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 9.8, raw_unit: 'pct', normalized_score: 0.8, weight: 0.3, weighted_score: 0.24 },
          benchmark_relative_strength: { label: 'Benchmark-relative strength', direction: 'higher_is_better', raw_value: 2.7, raw_unit: 'pct', normalized_score: 0.7, weight: 0.2, weighted_score: 0.14 },
          realized_volatility: { label: 'Realized volatility', direction: 'lower_is_better', raw_value: 15.8, raw_unit: 'pct', normalized_score: 0.6, weight: 0.15, weighted_score: 0.09 },
          max_drawdown: { label: 'Max drawdown', direction: 'lower_is_better', raw_value: 9.5, raw_unit: 'pct', normalized_score: 0.65, weight: 0.1, weighted_score: 0.065 },
          liquidity: { label: 'Median dollar volume', direction: 'higher_is_better', raw_value: 12.3, raw_unit: 'score', normalized_score: 0.7, weight: 0.1, weighted_score: 0.07 },
          implementation_fit: { label: 'Implementation fit', direction: 'higher_is_better', raw_value: 1, raw_unit: 'score', normalized_score: 1, weight: 0.05, weighted_score: 0.05 },
        },
      },
    ],
    excluded_symbols: [{ symbol: 'VDST', reason: 'instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF' }],
  }
}

function makeEtfRankingMetadataPayload() {
  return { available_effective_peer_groups: ['Sector UCITS ETF'] }
}

function makeEtfRankingRecentRunsPayload() {
  return []
}

function makeEtfRankingPreflightPayload(overrides: Record<string, unknown> = {}) {
  const artifact = makeEtfRankingPayload()
  return {
    contract_version: 'ranking_artifact_preflight_v1',
    artifact: {
      artifact_kind: 'etf_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
      ranking_id: artifact.ranking_id,
      methodology_id: artifact.run_metadata.methodology_id,
      as_of_date: artifact.run_metadata.as_of_date,
      ranking_basis_date: artifact.run_metadata.ranking_basis_date,
    },
    eligibility: {
      review_truth_basis: 'authoritative_persisted_ranking_artifact',
      review_scope: 'artifact_backed_review_only',
      open_supported: true,
      replay_eligible: true,
      consumer_handoff_supported: false,
      ineligibility_reason: null,
    },
    open_handoff: {
      handoff_kind: 'ranking_artifact_open_handoff_v1',
      artifact_kind: 'etf_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
    },
    ...overrides,
  }
}

function makeReplacementRankingPayload(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 'intent_bound_etf_replacement_ranking_artifact_v1',
    artifact_id: 'intent_bound_etf_replacement_ranking_artifact_sector_1',
    ranking_id: 'intent_bound_etf_replacement_ranking_engine_v1',
    methodology_id: 'intent_bound_etf_replacement_ranking_methodology_v1',
    basis_date: '2026-04-15',
    status: 'ok',
    request: {
      replacement_intent: {
        draft_id: 'draft-1',
        workspace_id: 'workspace-1',
        base_node_id: 'node-1',
        base_symbol: 'AAPL',
        candidate_symbol: 'IUFS',
        seed_ranking_id: 'etf_ranking_engine_v1',
        seed_methodology_id: 'etf_ranking_methodology_v1',
        seed_ranking_basis_date: '2026-04-15',
        peer_group: 'Sector UCITS ETF',
        benchmark_symbol: 'SPY',
        lookback_months: 6,
      },
      seed_context: {
        ranking_id: 'etf_ranking_engine_v1',
        methodology_id: 'etf_ranking_methodology_v1',
        ranking_basis_date: '2026-04-15',
        peer_group: 'Sector UCITS ETF',
        benchmark_symbol: 'SPY',
        lookback_months: 6,
        seeded_symbols: ['AAPL', 'IUFS'],
      },
      prefer_live_data: false,
      normalized_request: {
        base_symbol: 'AAPL',
        candidate_symbol: 'IUFS',
        seeded_symbols: ['AAPL', 'IUFS'],
        peer_group: 'Sector UCITS ETF',
        ranking_basis_date: '2026-04-15',
        benchmark_symbol: 'SPY',
        lookback_months: 6,
      },
    },
    request_context: {
      universe: ['AAPL', 'IUFS'],
      benchmark_symbol: 'SPY',
      lookback_months: 6,
      prefer_live_data: false,
      base_symbol: 'AAPL',
      candidate_symbol: 'IUFS',
      peer_group: 'Sector UCITS ETF',
      ranking_basis_date: '2026-04-15',
      seed_ranking_id: 'etf_ranking_engine_v1',
      seed_methodology_id: 'etf_ranking_methodology_v1',
    },
    submitted_request: {
      replacement_intent: {
        draft_id: 'draft-1',
        workspace_id: 'workspace-1',
        base_node_id: 'node-1',
        base_symbol: 'AAPL',
        candidate_symbol: 'IUFS',
        seed_ranking_id: 'etf_ranking_engine_v1',
        seed_methodology_id: 'etf_ranking_methodology_v1',
        seed_ranking_basis_date: '2026-04-15',
        peer_group: 'Sector UCITS ETF',
        benchmark_symbol: 'SPY',
        lookback_months: 6,
      },
      seed_context: {
        ranking_id: 'etf_ranking_engine_v1',
        methodology_id: 'etf_ranking_methodology_v1',
        ranking_basis_date: '2026-04-15',
        peer_group: 'Sector UCITS ETF',
        benchmark_symbol: 'SPY',
        lookback_months: 6,
        seeded_symbols: ['AAPL', 'IUFS'],
      },
      prefer_live_data: false,
    },
    normalized_request: {
      base_symbol: 'AAPL',
      candidate_symbol: 'IUFS',
      seeded_symbols: ['AAPL', 'IUFS'],
      peer_group: 'Sector UCITS ETF',
      ranking_basis_date: '2026-04-15',
      benchmark_symbol: 'SPY',
      lookback_months: 6,
    },
    effective_inputs: {
      benchmark_symbol: 'SPY',
      lookback_months: 6,
      price_basis: 'close',
      requested_universe: ['AAPL', 'IUFS'],
      evaluated_universe: ['IUFS'],
      base_symbol: 'AAPL',
      candidate_symbol: 'IUFS',
      peer_group: 'Sector UCITS ETF',
      ranking_basis_date: '2026-04-15',
    },
    request_hash: 'request-hash-1',
    run_metadata: {
      ranking_id: 'intent_bound_etf_replacement_ranking_engine_v1',
      methodology_id: 'intent_bound_etf_replacement_ranking_methodology_v1',
      methodology: 'm',
      as_of_date: '2026-04-15',
      ranking_basis_date: '2026-04-15',
      basis_date: '2026-04-15',
      request_hash: 'request-hash-1',
      price_basis: 'close',
      source_status: 'sample',
      tie_break_order: ['composite_score'],
      factor_weights: { momentum: 1 },
      confidence: 'medium',
    },
    eligible_count: 1,
    excluded_count: 1,
    ranked_candidates: [{
      symbol: 'IUFS',
      rank: 1,
      composite_score: 0.8123,
      raw_factors: {
        momentum_12_1: 11.2,
        momentum_6_1: 4.2,
        momentum_blended: 7.7,
        realized_volatility_126d: 14.4,
        max_drawdown_252d: 8.1,
        liquidity_60d: 13.1,
      },
      normalized_scores: {
        momentum: 1,
        realized_volatility: 0.7,
        max_drawdown: 0.75,
        liquidity: 0.8,
      },
      eligibility_status: 'eligible',
      exclusion_reason: null,
      basis_date: '2026-04-15',
      draft_id: 'draft-1',
      base_node_id: 'node-1',
      base_symbol: 'AAPL',
      seed_ranking_id: 'etf_ranking_engine_v1',
      seed_methodology_id: 'etf_ranking_methodology_v1',
    }],
    excluded_candidates: [{
      symbol: 'VDST',
      rank: null,
      composite_score: null,
      raw_factors: null,
      normalized_scores: null,
      eligibility_status: 'excluded',
      exclusion_reason: 'instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF',
      basis_date: '2026-04-15',
      draft_id: 'draft-1',
      base_node_id: 'node-1',
      base_symbol: 'AAPL',
      seed_ranking_id: 'etf_ranking_engine_v1',
      seed_methodology_id: 'etf_ranking_methodology_v1',
    }],
    warnings: [],
    unavailable_reason: null,
    lineage: {
      draft_id: 'draft-1',
      workspace_id: 'workspace-1',
      base_node_id: 'node-1',
      base_symbol: 'AAPL',
      candidate_symbol: 'IUFS',
      seed_ranking_id: 'etf_ranking_engine_v1',
      seed_methodology_id: 'etf_ranking_methodology_v1',
      seed_ranking_basis_date: '2026-04-15',
      peer_group: 'Sector UCITS ETF',
      benchmark_symbol: 'SPY',
      lookback_months: 6,
    },
    ...overrides,
  }
}

function makeReplacementRankingPreflightPayload(overrides: Record<string, unknown> = {}) {
  const artifact = makeReplacementRankingPayload()
  return {
    contract_version: 'ranking_artifact_preflight_v1',
    artifact: {
      artifact_kind: 'intent_bound_etf_replacement_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
      ranking_id: artifact.ranking_id,
      methodology_id: artifact.run_metadata.methodology_id,
      as_of_date: artifact.run_metadata.as_of_date,
      ranking_basis_date: artifact.run_metadata.ranking_basis_date,
    },
    eligibility: {
      review_truth_basis: 'authoritative_persisted_ranking_artifact',
      review_scope: 'artifact_backed_review_only',
      open_supported: true,
      replay_eligible: true,
      consumer_handoff_supported: true,
      ineligibility_reason: null,
    },
    open_handoff: {
      handoff_kind: 'ranking_artifact_open_handoff_v1',
      artifact_kind: 'intent_bound_etf_replacement_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
    },
    ...overrides,
  }
}

function makeReplacementRankingOpenPayload(overrides: Record<string, unknown> = {}) {
  const artifact = makeReplacementRankingPayload()
  const preflight = makeReplacementRankingPreflightPayload()
  return {
    contract_version: 'ranking_artifact_open_v1',
    open_handoff: preflight.open_handoff,
    review_payload_kind: 'intent_bound_etf_replacement_ranking_review_payload_v1',
    review_payload: {
      review_payload_kind: 'intent_bound_etf_replacement_ranking_review_payload_v1',
      review_truth_basis: 'authoritative_persisted_ranking_artifact',
      review_scope: 'artifact_backed_review_only',
      artifact_kind: 'intent_bound_etf_replacement_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
      artifact,
    },
    consumer_handoff: {
      contract_version: 'intent_bound_etf_replacement_ranking_consumer_contract_v1',
      handoff_kind: 'intent_bound_etf_replacement_ranking_consumer_handoff_v1',
      artifact_kind: 'intent_bound_etf_replacement_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
      ranking_id: artifact.ranking_id,
      methodology_id: artifact.methodology_id,
      basis_date: artifact.basis_date,
      draft_id: artifact.lineage.draft_id,
      workspace_id: artifact.lineage.workspace_id,
      base_node_id: artifact.lineage.base_node_id,
      base_symbol: artifact.lineage.base_symbol,
      candidate_symbol: artifact.lineage.candidate_symbol,
      seed_ranking_id: artifact.lineage.seed_ranking_id,
      seed_methodology_id: artifact.lineage.seed_methodology_id,
      seed_ranking_basis_date: artifact.lineage.seed_ranking_basis_date,
      peer_group: artifact.lineage.peer_group,
      benchmark_symbol: artifact.lineage.benchmark_symbol,
      lookback_months: artifact.lineage.lookback_months,
      eligible_count: artifact.eligible_count,
      excluded_count: artifact.excluded_count,
      selected_candidate: {
        symbol: 'IUFS',
        rank: 1,
        composite_score: 0.8123,
        basis_date: '2026-04-15',
        draft_id: 'draft-1',
        base_node_id: 'node-1',
        base_symbol: 'AAPL',
        seed_ranking_id: 'etf_ranking_engine_v1',
        seed_methodology_id: 'etf_ranking_methodology_v1',
      },
    },
    ...overrides,
  }
}

function assertReplacementContractState(preflight: Record<string, any>, openPayload?: Record<string, any>) {
  const eligibility = preflight.eligibility
  if (preflight.artifact.artifact_kind !== 'intent_bound_etf_replacement_ranking') {
    throw new Error('Replacement contract fixture must use replacement artifact kind')
  }
  if (eligibility.open_supported !== eligibility.replay_eligible) {
    throw new Error('Replacement preflight eligibility must keep open_supported and replay_eligible aligned')
  }
  if (eligibility.consumer_handoff_supported !== eligibility.open_supported) {
    throw new Error('replacement ranking preflight must keep consumer_handoff_supported aligned with open_supported')
  }
  if (!eligibility.open_supported) {
    if (eligibility.ineligibility_reason == null) {
      throw new Error('Replacement preflight must fail closed with ineligibility_reason')
    }
    if (openPayload) {
      throw new Error('Ineligible replacement preflight must not carry an open payload fixture')
    }
    return
  }
  if (eligibility.ineligibility_reason != null) {
    throw new Error('Eligible replacement preflight must not carry ineligibility_reason')
  }
  if (!openPayload) {
    throw new Error('Eligible replacement preflight must provide an open payload fixture')
  }
  if (openPayload.review_payload.artifact_kind !== 'intent_bound_etf_replacement_ranking') {
    throw new Error('Replacement open payload must keep replacement artifact kind')
  }
  const hasConsumerHandoff = 'consumer_handoff' in openPayload
  if (eligibility.consumer_handoff_supported !== hasConsumerHandoff) {
    throw new Error('Replacement open payload consumer_handoff presence must match preflight support state')
  }
}

function makeEtfRankingOpenPayload(overrides: Record<string, unknown> = {}) {
  const artifact = makeEtfRankingPayload()
  const preflight = makeEtfRankingPreflightPayload()
  return {
    contract_version: 'ranking_artifact_open_v1',
    open_handoff: preflight.open_handoff,
    review_payload_kind: 'etf_ranking_review_payload_v1',
    review_payload: {
      review_payload_kind: 'etf_ranking_review_payload_v1',
      review_truth_basis: 'authoritative_persisted_ranking_artifact',
      review_scope: 'artifact_backed_review_only',
      artifact_kind: 'etf_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
      artifact,
    },
    ...overrides,
  }
}

function sectorPositionsByName(overview: PortfolioOverview): Record<string, Array<{ symbol: string; market_value: number; weight: number }>> {
  return overview.sector_position_breakdown
}

function mockSavedVariantNode() {
  return {
    id: 'node-2',
    workspaceId: 'workspace-1',
    parentId: 'node-1',
    kind: 'variant' as const,
    name: 'Raise MSFT',
    createdAt: '2026-04-10T00:10:00Z',
    changeSummary: { label: 'Raise MSFT', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: 0, netCapitalDelta: 0 },
    portfolioSnapshot: variantSnapshot,
  }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('adds a new imported snapshot node from Dashboard Add Statement', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const importedWorkspace = mockImportedWorkspace()
    const importedSnapshotNode: PortfolioNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026-04-08',
      createdAt: '2026-04-10T00:05:00Z',
      changeSummary: { label: 'IB 2026-04-08', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: 0, netCapitalDelta: 0 },
      portfolioSnapshot: persistedSnapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ['IB2026.pdf'], importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-08', importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-08' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
      },
    }
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([importedWorkspace.rootNode, importedSnapshotNode])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    const saveImportedSnapshotNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveImportedSnapshotNode').mockResolvedValue({
      node: importedSnapshotNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2', updatedAt: '2026-04-10T00:05:00Z' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:05:00Z' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({
        ...importedWorkspace.draft,
        baseNodeId: 'node-2',
        updatedAt: '2026-04-10T00:05:00Z',
      } satisfies WorkingDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const addSnapshotBootstrapPayload = {
      ...bootstrapPayload,
      snapshot: {
        ...bootstrapPayload.snapshot,
        statement: { ...bootstrapPayload.snapshot.statement, statement_period: '2026-01-01 - 2026-04-08' },
        statements: [{ ...bootstrapPayload.snapshot.statements[0], statement_period: '2026-01-01 - 2026-04-08', source_path: 'C:\\docs\\IB2026.pdf', imported_at: '2026-04-10T00:05:00Z', page_count: 17 }],
        positions: bootstrapPayload.snapshot.positions.map((position) => ({ ...position, as_of_date: '2026-04-08' })),
      },
      history_context: { ...bootstrapPayload.history_context, statement_period: '2026-01-01 - 2026-04-08', source_file_names: ['IB2026.pdf'], history_end_date: '2026-04-08' },
    }

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(addSnapshotBootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...appendedExposurePayload, snapshot: { ...appendedExposurePayload.snapshot, statement: { ...appendedExposurePayload.snapshot.statement, statement_period: '2026-01-01 - 2026-04-08' }, statements: [{ ...appendedExposurePayload.snapshot.statements[1], statement_period: '2026-01-01 - 2026-04-08', source_path: 'C:\\docs\\IB2026.pdf' }] } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...appendedDiagnosticsPayload, snapshot: { ...appendedDiagnosticsPayload.snapshot, statement: { ...appendedDiagnosticsPayload.snapshot.statement, statement_period: '2026-01-01 - 2026-04-08' }, statements: [{ ...appendedDiagnosticsPayload.snapshot.statements[1], statement_period: '2026-01-01 - 2026-04-08', source_path: 'C:\\docs\\IB2026.pdf' }] } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    const file2026 = new File(['2026'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })

    fireEvent.change(input, { target: { files: [file2025] } })
    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    await waitFor(() => expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy())

    fireEvent.click(screen.getByText('Add Statement'))
    fireEvent.change(input, { target: { files: [file2026] } })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))

    const appendAnalyzeBody = fetchMock.mock.calls[4]?.[1]?.body as FormData
    const uploadedFiles = appendAnalyzeBody.getAll('statement_files') as File[]
    expect(uploadedFiles.map((file) => file.name)).toEqual(['IB2026.pdf'])
    expect(saveImportedSnapshotNodeSpy).toHaveBeenCalledWith(expect.objectContaining({ workspaceId: 'workspace-1', parentNodeId: 'node-1', importedFileNames: ['IB2026.pdf'], name: 'IB 2026-04-08' }))
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.portfolioSnapshot.importedMeta.sourceFileNames).toContain('IB2026.pdf')
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.portfolioSnapshot.positions.some((position: { symbol: string }) => position.symbol === 'AAPL')).toBe(true)
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.historyContext?.sourceFileNames).toEqual(['IB2025.pdf', 'IB2026.pdf'])
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.historyContext?.historyEndDate).toBe('2026-04-08')
    await waitFor(() => expect(saveImportedSnapshotNodeSpy).toHaveBeenCalled())
  })

  it('shows the separate ETF Ranking tab', async () => {
    render(<App />)

    fireEvent.click(screen.getByText('ETF Ranking'))

    await waitFor(() => expect(screen.getByText('ETF ranking workspace')).toBeTruthy())
  })

  it('shows the strategy lab research artifact consumer workspace', async () => {
    installFetchMock(async (input) => {
      const pathname = requestPathname(input)
      if (pathname === '/api/strategy-lab/cross-sectional-research/recent') {
        return jsonResponse({
          items: [],
          applied_filters: {
            artifact_kind: null,
            schema_version: null,
            methodology_id: null,
            dataset_version: null,
            universe_definition: null,
            benchmark_symbol: null,
            rebalance_date: null,
            as_of_date: null,
            holdout_start_date: null,
          },
          metadata: {
            contract_version: 'cross_sectional_research_discovery_v1',
            metadata_truth: 'authoritative_persisted_artifact_metadata',
            recent_order_basis: 'persisted_artifact.persisted_at_then_artifact_id',
            supported_filters: ['artifact_kind', 'schema_version', 'methodology_id', 'dataset_version', 'universe_definition', 'benchmark_symbol', 'rebalance_date', 'as_of_date', 'holdout_start_date'],
            methodology_metadata_v1_semantics: 'descriptive_only',
            status_metadata_v1_semantics: 'descriptive_only',
            provenance_metadata_v1_semantics: 'descriptive_only',
            applied_filters: {
              artifact_kind: null,
              schema_version: null,
              methodology_id: null,
              dataset_version: null,
              universe_definition: null,
              benchmark_symbol: null,
              rebalance_date: null,
              as_of_date: null,
              holdout_start_date: null,
            },
          },
        })
      }
      throw new Error(`Unhandled fetch ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByText('Strategy Lab'))

    await waitFor(() => expect(screen.getByText('ETF cross-sectional momentum')).toBeTruthy())
    fireEvent.click(screen.getByText('Load Research Artifacts'))
    await waitFor(() => expect(screen.getByText('No persisted research artifacts found.')).toBeTruthy())
  })

  it('shows trend and risk overlays above diagnostics on the diagnostics tab', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } })))

    render(<App />)

    fireEvent.click(screen.getByText('Dashboard'))
    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())

    fireEvent.click(screen.getByText('Diagnostics'))

    await waitFor(() => expect(screen.getAllByText('Overlay analysis').length).toBeGreaterThan(0))
    expect(screen.getByText('Trend / Risk Overlays')).toBeTruthy()
    await waitFor(() => expect(screen.getByText('Factor and risk diagnostics')).toBeTruthy())
  })

  it('refreshes dashboard allocation and cards after adding a statement snapshot', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const importedWorkspace = mockImportedWorkspace()
    const addedSnapshot = {
      ...persistedSnapshot,
      importedMeta: {
        ...persistedSnapshot.importedMeta,
        statementPeriod: '2026-01-01 - 2026-04-08',
        sourceFileNames: ['IB2025.pdf', 'FF2026.pdf'],
      },
      positions: [
        { symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' as const },
        { symbol: 'JPM', marketValue: 5000, quantity: 20, currency: 'USD', sector: 'Financials', sourceType: 'equity' as const },
      ],
      cashBalances: [{ currency: 'USD', amount: 1200 }],
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'FF 2026-04-08',
      createdAt: '2026-04-10T00:05:00Z',
      changeSummary: { label: 'FF 2026-04-08', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: addedSnapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ['FF2026.pdf'], importedAt: '2026-04-10T00:05:00Z', importer: 'freedom24', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-08', importedAt: '2026-04-10T00:05:00Z', importer: 'freedom24', sourceFileNames: ['IB2025.pdf', 'FF2026.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2026-04-08' }, importedHistorySnapshot: null }),
      },
    }
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([importedWorkspace.rootNode, importedSnapshotNode])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveImportedSnapshotNode').mockResolvedValue({
      node: importedSnapshotNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2', updatedAt: '2026-04-10T00:05:00Z' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:05:00Z' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({
        ...importedWorkspace.draft,
        baseNodeId: 'node-2',
        portfolioSnapshot: addedSnapshot,
        updatedAt: '2026-04-10T00:05:00Z',
      })
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const ffBootstrapPayload = {
      ...bootstrapPayload,
      snapshot: {
        ...bootstrapPayload.snapshot,
        statement: { ...bootstrapPayload.snapshot.statement, importer: 'freedom24', statement_period: '2026-01-01 - 2026-04-08' },
        statements: [{ ...bootstrapPayload.snapshot.statements[0], importer: 'freedom24', source_path: 'C:\\docs\\FF2026.pdf', statement_period: '2026-01-01 - 2026-04-08', imported_at: '2026-04-10T00:05:00Z' }],
        positions: [
          { ...bootstrapPayload.snapshot.positions[0], symbol: 'JPM', market_value: 5000, quantity: 20, as_of_date: '2026-04-08' },
        ],
      },
      history_context: {
        ...bootstrapPayload.history_context,
        importer: 'freedom24',
        statement_period: '2026-01-01 - 2026-04-08',
        source_file_names: ['FF2026.pdf'],
        history_end_date: '2026-04-08',
      },
    }

    const ffExposurePayload = {
      ...exposurePayload,
      snapshot: {
        ...exposurePayload.snapshot,
        statement: { ...exposurePayload.snapshot.statement, importer: 'freedom24', statement_period: '2026-01-01 - 2026-04-08' },
        statements: [{ ...exposurePayload.snapshot.statements[0], importer: 'freedom24', source_path: 'C:\\docs\\FF2026.pdf', statement_period: '2026-01-01 - 2026-04-08' }],
        positions: [
          { ...exposurePayload.snapshot.positions[0], symbol: 'AAPL', market_value: 10000, quantity: 10 },
          { ...exposurePayload.snapshot.positions[0], symbol: 'JPM', market_value: 5000, quantity: 20 },
        ],
      },
      overview: {
        ...exposurePayload.overview,
        total_market_value: 15000,
        sector_allocation: [
          { sector: 'Technology', market_value: 10000, weight: 2 / 3 },
          { sector: 'Financials', market_value: 5000, weight: 1 / 3 },
        ],
        sector_position_breakdown: {
          Technology: [{ symbol: 'AAPL', market_value: 10000, weight: 2 / 3 }],
          Financials: [{ symbol: 'JPM', market_value: 5000, weight: 1 / 3 }],
        },
      },
    }

    const unavailableHistoryPayload = { performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ffBootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ffExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(unavailableHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const ibFile = new File(['ib'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    const ffFile = new File(['ff'], 'FF2026.pdf', { type: 'application/pdf', lastModified: 2 })

    fireEvent.change(input, { target: { files: [ibFile] } })
    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    expect(screen.getByText('Project summary')).toBeTruthy()

    fireEvent.click(screen.getByText('Add Statement'))
    fireEvent.change(input, { target: { files: [ffFile] } })

    await waitFor(() => expect(screen.getByText('Loaded file: FF2026.pdf')).toBeTruthy())
    await waitFor(() => expect(screen.getByText('Performance history is unavailable for this import.')).toBeTruthy())
    expect(screen.getByText('Technology')).toBeTruthy()
    expect(screen.getByText('Financials')).toBeTruthy()
    expect(screen.getByDisplayValue('AAPL')).toBeTruthy()
    fireEvent.click(screen.getByText('Financials'))
    expect(screen.getByDisplayValue('JPM')).toBeTruthy()
  })

  it('restores persisted import state on startup', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByText('Dashboard'))
    await waitFor(() => expect(screen.getByText('Restored on launch')).toBeTruthy())
    expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy()
  })

  it('opens persisted construction artifact review from query param on startup', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeConstructionArtifactReplayValidationResponse()))
        .mockResolvedValueOnce(jsonResponse(makeConstructionArtifactReplayResponse()))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(createWorkspaceSpy).toHaveBeenCalledWith(expect.objectContaining({ constructionArtifactId: 'artifact-123' })))
      await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
      expect(createWorkspaceSpy).toHaveBeenCalledTimes(1)
      expect(fetchMock).toHaveBeenCalledTimes(2)
      expect(requestPathname(fetchMock.mock.calls[0]?.[0] as RequestInfo | URL)).toBe('/api/backtests/portfolio-allocation/construction-artifact-validation')
      expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body ?? '{}'))).toEqual({ construction_artifact_id: 'artifact-123' })
      expect(requestPathname(fetchMock.mock.calls[1]?.[0] as RequestInfo | URL)).toBe('/api/backtests/portfolio-allocation/construction-artifact-preview')
      expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body ?? '{}'))).toEqual(makeConstructionArtifactReplayValidationResponse().preview_handoff)
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted construction artifact open when preview handoff kind is unsupported', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(makeConstructionArtifactReplayValidationResponse({
        preview_handoff: {
          ...makeConstructionArtifactReplayValidationResponse().preview_handoff,
          handoff_kind: 'construction_artifact_preview_handoff_v0',
        } as unknown as ConstructionArtifactReplayValidationResponse['preview_handoff'],
      })))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
      fireEvent.click(screen.getByText('Dashboard'))
      await waitFor(() => expect(screen.getByText('Unable to open persisted construction artifact review: unsupported preview handoff kind')).toBeTruthy())
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted construction artifact open when preview handoff artifact mismatches query artifact', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(makeConstructionArtifactReplayValidationResponse({
        preview_handoff: {
          ...makeConstructionArtifactReplayValidationResponse().preview_handoff,
          construction_artifact_id: 'artifact-other',
        },
      })))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
      fireEvent.click(screen.getByText('Dashboard'))
      await waitFor(() => expect(screen.getByText('Unable to open persisted construction artifact review: preview handoff artifact mismatch')).toBeTruthy())
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted construction artifact open when preflight validation fails', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ detail: 'validation failed' }, 400))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
      fireEvent.click(screen.getByText('Dashboard'))
      await waitFor(() => expect(screen.getByText('validation failed')).toBeTruthy())
      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(requestPathname(fetchMock.mock.calls[0]?.[0] as RequestInfo | URL)).toBe('/api/backtests/portfolio-allocation/construction-artifact-validation')
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted construction artifact open when preview fails after preflight succeeds', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeConstructionArtifactReplayValidationResponse()))
        .mockResolvedValueOnce(jsonResponse({ detail: 'preview failed' }, 400))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
      fireEvent.click(screen.getByText('Dashboard'))
      await waitFor(() => expect(screen.getByText('preview failed')).toBeTruthy())
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted construction artifact open when preview handoff is missing', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({
        ...makeConstructionArtifactReplayValidationResponse(),
        preview_handoff: undefined,
      }))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
      fireEvent.click(screen.getByText('Dashboard'))
      await waitFor(() => expect(screen.getByText('Unable to open persisted construction artifact review: validation response missing preview handoff')).toBeTruthy())
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('restores persisted construction artifact review state on startup', async () => {
    const replay = makeConstructionArtifactReplayResponse()
    const workspace = {
      id: 'workspace-artifact',
      name: 'Construction Artifact artifact-123',
      createdAt: '2026-04-23T00:00:00Z',
      updatedAt: '2026-04-23T00:00:00Z',
      rootNodeId: 'node-artifact',
      activeNodeId: 'node-artifact',
      source: buildArtifactReviewSource('artifact-123', '2026-04-23T00:00:00Z'),
    }
    const node = {
      id: 'node-artifact',
      workspaceId: 'workspace-artifact',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-23T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: {
        basisVersion: 1 as const,
        basisKind: 'persisted_construction_artifact_review' as const,
        constructionArtifactId: 'artifact-123',
        openedAt: '2026-04-23T00:00:00Z',
        benchmarkSymbol: 'SPY',
        baseCurrency: 'USD',
        replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
        baselineWeights: [{ symbol: 'AAPL', target_weight: 0.6 }],
        candidateWeights: [{ symbol: 'MSFT', target_weight: 0.6 }],
      },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-artifact', activeNodeId: 'node-artifact', activeDraftId: null, selectedExposureSnapshotId: 'node-artifact', lastOpenedAt: '2026-04-23T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedConstructionArtifactWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-artifact', constructionArtifactId: 'artifact-123', openedAt: '2026-04-23T00:00:00Z', replay })

    render(<App />)

    await waitFor(() => expect(screen.getByTestId('persisted-construction-artifact-banner')).toBeTruthy())
    expect(screen.getAllByText('artifact-123').length).toBeGreaterThan(0)
    expect(screen.queryByText('Proposal')).toBeNull()
    expect(screen.getByText('Review basis: artifact-123')).toBeTruthy()
  })

  it('opens persisted optimizer handoff review from query param on startup', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff').mockResolvedValue({
        workspace: {
          id: 'workspace-optimizer',
          name: 'Optimizer Handoff optimizer_handoff_123',
          createdAt: '2026-04-24T00:00:00Z',
          updatedAt: '2026-04-24T00:00:00Z',
          rootNodeId: 'node-optimizer',
          activeNodeId: 'node-optimizer',
          source: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
        } as PortfolioWorkspace,
        rootNode: {
          id: 'node-optimizer',
          workspaceId: 'workspace-optimizer',
          parentId: null,
          kind: 'artifact_review_basis',
          name: 'Artifact Review Basis',
          createdAt: '2026-04-24T00:00:00Z',
          changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
          portfolioSnapshot: null,
          artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
        } as PortfolioNode,
        draft: null,
        workspaceState: {
          workspaceId: 'workspace-optimizer',
          activeNodeId: 'node-optimizer',
          activeDraftId: null,
          selectedExposureSnapshotId: 'node-optimizer',
          lastOpenedAt: '2026-04-24T00:00:00Z',
        },
        review: {
          workspaceId: 'workspace-optimizer',
          handoffReference,
          openedAt: '2026-04-24T00:00:00Z',
          validation: makeOptimizerHandoffValidationResponse(),
          replay: makeOptimizerHandoffReplayResponse(),
        },
      })
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse()))
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffReplayResponse()))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(createWorkspaceSpy).toHaveBeenCalledWith(expect.objectContaining({ handoffReference })))
      await waitFor(() => expect(screen.getByTestId('persisted-construction-artifact-banner')).toBeTruthy())
      expect(requestPathname(fetchMock.mock.calls[0]?.[0] as RequestInfo | URL)).toBe('/api/backtests/portfolio-allocation/optimizer-handoff/constraints')
      expect(requestPathname(fetchMock.mock.calls[1]?.[0] as RequestInfo | URL)).toBe('/api/backtests/portfolio-allocation/optimizer-handoff-preview')
      expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy()
      expect(screen.getByText('This workspace reopens a hypothetical artifact-backed optimizer review by persisted handoff reference while keeping replay review surfaces intact.')).toBeTruthy()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when validation is blocked', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse({ validation_status: 'blocked', blocking_rule_ids: ['persisted_payload_accessible'] }))))

      render(<App />)

      fireEvent.click(screen.getByText('Dashboard'))
      await waitFor(() => expect(screen.getByText('Unable to open persisted optimizer handoff review: validation blocked')).toBeTruthy())
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when validation handoff mismatches query reference', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse({ handoff_id: 'optimizer_handoff_other' }))))

      render(<App />)

      fireEvent.click(screen.getByText('Dashboard'))
      await waitFor(() => expect(screen.getByText('Unable to open persisted optimizer handoff review: validation handoff mismatch')).toBeTruthy())
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when validation artifact mismatches query reference', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse({ artifact_id: 'optimizer_artifact_other' }))))

      render(<App />)

      fireEvent.click(screen.getByText('Dashboard'))
      await waitFor(() => expect(screen.getByText('Unable to open persisted optimizer handoff review: validation artifact mismatch')).toBeTruthy())
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('allows persisted optimizer handoff open when validation omits artifact id', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff').mockResolvedValue({
        workspace: {
          id: 'workspace-optimizer',
          name: 'Optimizer Handoff optimizer_handoff_123',
          createdAt: '2026-04-24T00:00:00Z',
          updatedAt: '2026-04-24T00:00:00Z',
          rootNodeId: 'node-optimizer',
          activeNodeId: 'node-optimizer',
          source: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
        } as PortfolioWorkspace,
        rootNode: {
          id: 'node-optimizer',
          workspaceId: 'workspace-optimizer',
          parentId: null,
          kind: 'artifact_review_basis',
          name: 'Artifact Review Basis',
          createdAt: '2026-04-24T00:00:00Z',
          changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
          portfolioSnapshot: null,
          artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
        } as PortfolioNode,
        draft: null,
        workspaceState: { workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' },
        review: {
          workspaceId: 'workspace-optimizer',
          handoffReference,
          openedAt: '2026-04-24T00:00:00Z',
          validation: makeOptimizerHandoffValidationResponse({ artifact_id: null }),
          replay: makeOptimizerHandoffReplayResponse(),
        },
      })
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse({ artifact_id: null })))
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffReplayResponse()))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(createWorkspaceSpy).toHaveBeenCalled())
      expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when replay artifact mismatches query reference', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse()))
        .mockResolvedValueOnce(jsonResponse({ ...makeOptimizerHandoffReplayResponse(), artifact_id: 'optimizer_artifact_other' }))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      fireEvent.click(screen.getByText('Dashboard'))
      await waitFor(() => expect(screen.getByText('Unable to open persisted optimizer handoff review: replay artifact mismatch')).toBeTruthy())
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when replay omits the canonical objective block', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse()))
        .mockResolvedValueOnce(jsonResponse({
          ...makeOptimizerHandoffReplayResponse(),
          optimizer_context: {
            ...makeOptimizerHandoffReplayResponse().optimizer_context!,
            objective: null,
          },
        }))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      fireEvent.click(screen.getByText('Dashboard'))
      await waitFor(() => expect(screen.getByText('Unable to open persisted optimizer handoff review: replay optimizer objective missing')).toBeTruthy())
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('restores persisted optimizer handoff review state on startup', async () => {
    const handoffReference = makeOptimizerHandoffReference()
    const replay = makeOptimizerHandoffReplayResponse()
    const validation = makeOptimizerHandoffValidationResponse()
    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
    }
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'normalizeLegacyPersistedOptimizerHandoffWorkspaceCache').mockResolvedValue({
      workspace: workspace as PortfolioWorkspace,
      node: {
        ...node,
        artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
      } as PortfolioNode,
      review: { workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedOptimizerHandoffWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay })

    render(<App />)

    await waitFor(() => expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy())
    expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy()
    expect(screen.getByText('Optimizer Handoff Review Replay')).toBeTruthy()
  })

  it('fails closed when restored persisted optimizer workspace is missing its authoritative persisted review row', async () => {
    const handoffReference = makeOptimizerHandoffReference()
    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
    }
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    const normalizeSpy = vi.spyOn(portfolioWorkspaceStorage, 'normalizeLegacyPersistedOptimizerHandoffWorkspaceCache')
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedOptimizerHandoffWorkspaceReview').mockResolvedValue(null)

    render(<App />)

    fireEvent.click(screen.getByText('Dashboard'))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace: persisted optimizer handoff review is missing')).toBeTruthy())
    expect(normalizeSpy).not.toHaveBeenCalled()
  })

  it('fails closed when restored persisted optimizer workspace source conflicts with handoffReference identity', async () => {
    const handoffReference = makeOptimizerHandoffReference()
    const validation = makeOptimizerHandoffValidationResponse()
    const replay = makeOptimizerHandoffReplayResponse()
    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: {
        ...buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
        handoffId: 'optimizer_handoff_other',
      },
    }
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedOptimizerHandoffWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay })

    render(<App />)

    fireEvent.click(screen.getByText('Dashboard'))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace')).toBeTruthy())
  })

  it('fails closed when restored persisted optimizer workspace has a malformed cached reviewBasis envelope', async () => {
    const handoffReference = makeOptimizerHandoffReference()
    const validation = makeOptimizerHandoffValidationResponse()
    const replay = makeOptimizerHandoffReplayResponse()
    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: {
        ...buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
        reviewBasis: {
          ...buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
          basisKind: 'persisted_construction_artifact_review',
        },
      },
    }
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedOptimizerHandoffWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay })

    render(<App />)

    fireEvent.click(screen.getByText('Dashboard'))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace')).toBeTruthy())
  })

  it('restores persisted optimizer handoff review state when cached reviewBasis is missing as a documented legacy case', async () => {
    const handoffReference = makeOptimizerHandoffReference()
    const replay = makeOptimizerHandoffReplayResponse()
    const validation = makeOptimizerHandoffValidationResponse()
    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: {
        kind: 'persisted_optimizer_handoff' as const,
        handoffReference,
        openedAt: '2026-04-24T00:00:00Z',
      },
    }
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: null,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'normalizeLegacyPersistedOptimizerHandoffWorkspaceCache').mockResolvedValue({
      workspace: {
        ...workspace,
        source: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
      } as PortfolioWorkspace,
      node: {
        ...node,
        artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
      } as PortfolioNode,
      review: { workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedOptimizerHandoffWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay })

    render(<App />)

    await waitFor(() => expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy())
    expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy()
    expect(screen.getByText('Optimizer Handoff Review Replay')).toBeTruthy()
  })

  it('normalizes legacy cached artifact review workspaces during restore', async () => {
    const replay = makeConstructionArtifactReplayResponse()
    const workspace = {
      id: 'workspace-artifact',
      name: 'Construction Artifact artifact-123',
      createdAt: '2026-04-23T00:00:00Z',
      updatedAt: '2026-04-23T00:00:00Z',
      rootNodeId: 'node-artifact',
      activeNodeId: 'node-artifact',
      source: {
        kind: 'persisted_construction_artifact' as const,
        constructionArtifactId: 'artifact-123',
        openedAt: '2026-04-23T00:00:00Z',
      },
    }
    const node = {
      id: 'node-artifact',
      workspaceId: 'workspace-artifact',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-23T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: {
        basisVersion: 1 as const,
        basisKind: 'persisted_construction_artifact_review' as const,
        constructionArtifactId: 'artifact-123',
        openedAt: '2026-04-23T00:00:00Z',
        benchmarkSymbol: 'SPY',
        baseCurrency: 'USD',
        replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
        baselineWeights: [{ symbol: 'AAPL', target_weight: 0.6 }],
        candidateWeights: [{ symbol: 'MSFT', target_weight: 0.6 }],
      },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-artifact', activeNodeId: 'node-artifact', activeDraftId: null, selectedExposureSnapshotId: 'node-artifact', lastOpenedAt: '2026-04-23T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedConstructionArtifactWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-artifact', constructionArtifactId: 'artifact-123', openedAt: '2026-04-23T00:00:00Z', replay })
    const normalizeSpy = vi.spyOn(portfolioWorkspaceStorage, 'normalizeLegacyPersistedConstructionArtifactWorkspaceCache').mockResolvedValue({
      workspace: {
        ...workspace,
        source: buildArtifactReviewSource('artifact-123', '2026-04-23T00:00:00Z'),
      },
      node: {
        id: 'node-artifact',
        workspaceId: 'workspace-artifact',
        parentId: null,
        kind: 'artifact_review_basis' as const,
        name: 'Artifact Review Basis',
        createdAt: '2026-04-23T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
        artifactReviewBasis: buildArtifactReviewSource('artifact-123', '2026-04-23T00:00:00Z').reviewBasis,
      },
      review: { workspaceId: 'workspace-artifact', constructionArtifactId: 'artifact-123', openedAt: '2026-04-23T00:00:00Z', replay },
    })

    render(<App />)

    await waitFor(() => expect(normalizeSpy).toHaveBeenCalled())
    expect(screen.getByTestId('persisted-construction-artifact-banner')).toBeTruthy()
  })

  it('restores IB2026 dashboard values consistently from persisted imported state', async () => {
    const snapshot = {
      snapshotVersion: 1 as const,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers' as const,
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: ib2026MutableOverview.sector_allocation.flatMap((sector) =>
        (sectorPositionsByName(ib2026MutableOverview)[sector.sector] ?? []).map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector: sector.sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'IB 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 }, portfolioSnapshot: snapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-14T00:00:00Z', updatedAt: '2026-04-14T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'IB 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 }, portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-14T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026ExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026DiagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026DashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByText('Dashboard'))
    await waitFor(() => expect(screen.getByText('Restored on launch')).toBeTruthy())
    expect(screen.getByText(ib2026DashboardGolden.loadedFileLabel)).toBeTruthy()
    expect(screen.getByText(`Portfolio value: ${ib2026DashboardGolden.portfolioValue}`)).toBeTruthy()
    expect(screen.getByText('Technology')).toBeTruthy()
    fireEvent.click(screen.getByText('Technology'))
    expect(screen.getByDisplayValue('SXRV')).toBeTruthy()
    expect(screen.getByDisplayValue(ib2026DashboardGolden.sxrvValue)).toBeTruthy()
  })

  it('restores FF2026 dashboard values consistently from persisted imported state', async () => {
    const snapshot = {
      snapshotVersion: 1 as const,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'freedom24' as const,
        statementPeriod: ff2026MutableSnapshot.statement.statement_period,
        importedAt: ff2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ff2026LoadedFiles,
      },
      positions: ff2026MutableOverview.sector_allocation.flatMap((sector) =>
        (sectorPositionsByName(ff2026MutableOverview)[sector.sector] ?? []).map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector: sector.sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ff2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'FF 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'FF 2026', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 3018.96, netCapitalDelta: 3018.96 }, portfolioSnapshot: snapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-14T00:00:00Z', updatedAt: '2026-04-14T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ff2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'freedom24', baseCurrency: 'USD', historyContext: ff2026HistoryContext, importedHistorySnapshot: ff2026BootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'FF 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'FF 2026', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 3018.96, netCapitalDelta: 3018.96 }, portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-14T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(ff2026ExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ff2026DiagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ff2026DashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByText('Dashboard'))
    await waitFor(() => expect(screen.getByText('Restored on launch')).toBeTruthy())
    expect(screen.getByText(ff2026DashboardGolden.loadedFileLabel)).toBeTruthy()
    expect(screen.getByText(`Portfolio value: ${ff2026DashboardGolden.portfolioValue}`)).toBeTruthy()
    fireEvent.click(screen.getAllByText('All')[0])
    expect(screen.getByText('Broad Market')).toBeTruthy()
    fireEvent.click(screen.getByText('Broad Market'))
    expect(screen.getByDisplayValue('VTI')).toBeTruthy()
    expect(screen.getByDisplayValue(ff2026DashboardGolden.vtiValue)).toBeTruthy()
  })

  it('clears restored import state and persisted session', async () => {
    const clearSpy = vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const saveRankingArtifactSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByText('Dashboard'))
    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())
    fireEvent.click(screen.getByText('Clear Imported Session'))

    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())
    expect(clearSpy).toHaveBeenCalled()
    expect(screen.queryByText('Clear Imported Session')).toBeNull()
  })

  it('passes imported bootstrap data into the backtest workspace', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(mockImportedWorkspace())
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(allocationBacktestPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })

    await waitFor(() => expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))

    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())
    expect(screen.getByText('Current Import')).toBeTruthy()
    expect(screen.getAllByText('$50000.00').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByText('Run Portfolio Improvement Replay'))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))
  })

  it('opens Workspace from Monitoring with a dismissible handoff banner', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(mockImportedWorkspace())
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(allocationBacktestPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })

    await waitFor(() => expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())

    fireEvent.click(screen.getByText('Run Portfolio Improvement Replay'))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))

    fireEvent.click(screen.getByRole('button', { name: 'Review In Workspace' }))

    await waitFor(() => expect(screen.getByTestId('monitoring-research-handoff-banner')).toBeTruthy())
    expect(screen.getByText('Monitoring context')).toBeTruthy()
    expect(screen.getByText(/Context:/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    await waitFor(() => expect(screen.queryByTestId('monitoring-research-handoff-banner')).toBeNull())
  })

  it('keeps generic strategy backtests in the dedicated Backtest tab', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        run_id: 'run-1:book_trend_breakout',
        config: {
          strategy: { strategy_id: 'book_trend_breakout', name: 'Book Trend Breakout', description: null, timeframe: 'daily', side: 'long_only', universe: ['ES', 'NQ', 'CL'], parameters: [], tags: [] },
          benchmark_symbol: 'SPY',
          start_date: '2024-01-01',
          end_date: '2024-12-31',
          initial_capital: 100000,
          base_currency: 'USD',
          slippage_bps: 0,
          commission_per_contract: 0,
          rebalance_frequency: 'monthly',
          use_continuous_contracts: false,
          continuous_series: null,
        },
        dataset_info: { ES: { symbol: 'ES', timeframe: 'daily', source: 'fmp', continuous: false, ready: true } },
        trades: [],
        positions: [],
        equity_curve: [],
        total_return_pct: 1,
        annualized_return_pct: 1,
        max_drawdown_pct: -1,
        sharpe_ratio: 1,
        overlay_preview: null,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByText('Backtest'))

    await waitFor(() => expect(screen.getByText('Generic strategy backtests')).toBeTruthy())
    expect(screen.queryByText('Project summary')).toBeNull()
    expect(screen.queryByText('Monitoring')).toBeNull()

    fireEvent.click(screen.getByText('Run Backtest'))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  })

  it('seeds an ETF ranking candidate into draft review without mutating the portfolio snapshot', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const saveRankingArtifactSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/strategy-lab/etf-ranking' && method === 'POST') return jsonResponse(makeEtfRankingPayload())
      if (pathname === '/api/strategy-lab/etf-ranking/artifacts/recent/metadata' && method === 'GET') return jsonResponse(makeEtfRankingMetadataPayload())
      if (pathname === '/api/strategy-lab/etf-ranking/artifacts/recent' && method === 'GET') return jsonResponse(makeEtfRankingRecentRunsPayload())
      if (pathname === '/api/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1' && method === 'POST') return jsonResponse(makeEtfRankingPreflightPayload())
      if (pathname === '/api/strategy-lab/ranking-artifacts/open' && method === 'POST') return jsonResponse(makeEtfRankingOpenPayload())
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByText('ETF Ranking'))
    fireEvent.click(screen.getByText('Run ETF Ranking'))
    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())

    fireEvent.click(screen.getAllByText('Seed Candidate Draft')[0])
    fireEvent.change(screen.getByLabelText('Incumbent ETF'), { target: { value: 'AAPL' } })
    fireEvent.click(screen.getByText('Create Draft'))

    await waitFor(() => expect(screen.getByText('Seeded Candidate Review')).toBeTruthy())
        expect(saveRankingArtifactSpy).toHaveBeenCalledTimes(1)
    expect(saveRankingArtifactSpy.mock.calls[0]?.[0]).toMatchObject({
      kind: 'intent_bound_seeded_etf_replacement_ranking',
      draftId: 'draft-1',
      workspaceId: 'workspace-1',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
      candidateRank: 1,
      rankingId: 'etf_ranking_engine_v1',
      openHandoff: {
        handoff_kind: 'ranking_artifact_open_handoff_v1',
        artifact_kind: 'etf_ranking',
        artifact_id: 'etf_ranking_artifact_sector_1',
        schema_version: 'etf_ranking_artifact_v1',
      },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Seeded Candidate Review')).toBeTruthy())
    expect(screen.getByText('Ranked Review')).toBeTruthy()
    expect(screen.getByText('Excluded Symbols')).toBeTruthy()
    expect(screen.getByText('VDST')).toBeTruthy()
    expect(screen.getByText('Base: AAPL · Candidate: IUFS · Rank #1')).toBeTruthy()
  })

  it('restores a persisted ETF ranking candidate annotation for the active draft', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-15T00:00:00Z',
        baseSymbol: 'AAPL',
        candidateSymbol: 'IUFS',
        candidateRank: 1,
        peerGroup: 'Sector UCITS ETF',
        benchmarkSymbol: 'SPY',
        lookbackMonths: 6,
        rankingId: 'etf_ranking_engine_v1',
        methodologyId: 'etf_ranking_methodology_v1',
        rankingBasisDate: '2026-04-15',
        confidence: 'medium',
        holdingsSupport: 'mixed',
        requestUniverse: ['AAPL', 'IUFS'],
        evaluatedUniverse: ['IUFS'],
        warningCount: 1,
        excludedSymbolsCount: 0,
      },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue({
      kind: 'intent_bound_seeded_etf_replacement_ranking',
      source: 'etf_ranking',
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      selectedAt: '2026-04-15T00:00:00Z',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
      candidateRank: 1,
      rankingId: 'etf_ranking_engine_v1',
      methodologyId: 'etf_ranking_methodology_v1',
      rankingBasisDate: '2026-04-15',
      openHandoff: {
        handoff_kind: 'ranking_artifact_open_handoff_v1',
        artifact_kind: 'etf_ranking',
        artifact_id: 'etf_ranking_artifact_sector_1',
        schema_version: 'etf_ranking_artifact_v1',
      },
      benchmarkSymbol: 'SPY',
      lookbackMonths: 6,
      peerGroup: 'Sector UCITS ETF',
      confidence: 'medium',
      holdingsSupport: 'mixed',
      requestUniverse: ['AAPL', 'IUFS'],
      evaluatedUniverse: ['IUFS'],
      warnings: ['Implementation-fit support is not complete across the ranked universe.'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF' }],
      selectedCandidate: {
        symbol: 'IUFS',
        rank: 1,
        compositeScore: 0.8123,
        instrument: {
          name: 'ETF',
          assetClass: 'etf',
          sector: 'Financials',
          category: 'Sector UCITS ETF',
          currency: 'USD',
        },
      },
      topCandidate: null,
      runnerUpCandidate: null,
    })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
        fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Ranked Review')).toBeTruthy())
    expect(screen.getByText('Seeded Candidate Review')).toBeTruthy()
    expect(screen.getByText('Base: AAPL · Candidate: IUFS · Rank #1')).toBeTruthy()
    expect(screen.getByText('VDST')).toBeTruthy()
  })

  it('fails closed when restored seeded ranking cache is missing canonical open handoff', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getIntentBoundSeededEtfReplacementRankingDraft').mockRejectedValue(new Error('Persisted seeded ranking review cache is missing or invalid open handoff'))
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByText('Dashboard'))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace')).toBeTruthy())
  })

  it('keeps replacement contract fixtures aligned for supported, unsupported, and fail-closed states', () => {
    const supportedPreflight = makeReplacementRankingPreflightPayload()
    const supportedOpen = makeReplacementRankingOpenPayload()
    const ineligiblePreflight = makeReplacementRankingPreflightPayload({
      eligibility: {
        review_truth_basis: 'authoritative_persisted_ranking_artifact',
        review_scope: 'artifact_backed_review_only',
        open_supported: false,
        replay_eligible: false,
        consumer_handoff_supported: false,
        ineligibility_reason: 'replacement ranking artifact is unreplayable',
      },
    })

    expect(() => assertReplacementContractState(supportedPreflight, supportedOpen)).not.toThrow()
    expect(() => assertReplacementContractState(ineligiblePreflight)).not.toThrow()

    expect(() => assertReplacementContractState(makeReplacementRankingPreflightPayload({
      eligibility: {
        review_truth_basis: 'authoritative_persisted_ranking_artifact',
        review_scope: 'artifact_backed_review_only',
        open_supported: true,
        replay_eligible: true,
        consumer_handoff_supported: false,
        ineligibility_reason: null,
      },
    }), supportedOpen)).toThrow('replacement ranking preflight must keep consumer_handoff_supported aligned with open_supported')

    expect(() => assertReplacementContractState(makeReplacementRankingPreflightPayload({
      eligibility: {
        review_truth_basis: 'authoritative_persisted_ranking_artifact',
        review_scope: 'artifact_backed_review_only',
        open_supported: false,
        replay_eligible: true,
        consumer_handoff_supported: false,
        ineligibility_reason: 'ambiguous replacement state',
      },
    }))).toThrow('Replacement preflight eligibility must keep open_supported and replay_eligible aligned')

    expect(() => assertReplacementContractState(makeReplacementRankingPreflightPayload({
      eligibility: {
        review_truth_basis: 'authoritative_persisted_ranking_artifact',
        review_scope: 'artifact_backed_review_only',
        open_supported: false,
        replay_eligible: false,
        consumer_handoff_supported: false,
        ineligibility_reason: null,
      },
    }))).toThrow('Replacement preflight must fail closed with ineligibility_reason')
  })

  it('promotes a seed into a persisted replacement intent and restores it for the same draft', async () => {
    const restoredReplacementIntent = {
      kind: 'etf_replacement_intent' as const,
      source: 'candidate_seed' as const,
      createdAt: '2026-04-15T00:05:00Z',
      draftId: 'draft-1',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-1',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
      seededFromDraftId: 'draft-1',
      seedRankingId: 'etf_ranking_engine_v1',
      seedMethodologyId: 'etf_ranking_methodology_v1',
      seedRankingBasisDate: '2026-04-15',
      peerGroup: 'Sector UCITS ETF',
      benchmarkSymbol: 'SPY',
      lookbackMonths: 6,
      confidence: 'medium' as const,
      holdingsSupport: 'mixed' as const,
      warningCount: 1,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-15T00:00:00Z',
        baseSymbol: 'AAPL',
        candidateSymbol: 'IUFS',
        candidateRank: 1,
        peerGroup: 'Sector UCITS ETF',
        benchmarkSymbol: 'SPY',
        lookbackMonths: 6,
        rankingId: 'etf_ranking_engine_v1',
        methodologyId: 'etf_ranking_methodology_v1',
        rankingBasisDate: '2026-04-15',
        confidence: 'medium',
        holdingsSupport: 'mixed',
        requestUniverse: ['AAPL', 'IUFS'],
        evaluatedUniverse: ['IUFS'],
        warningCount: 1,
        excludedSymbolsCount: 0,
      },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValue(restoredReplacementIntent)
    const saveReplacementIntentSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveReplacementIntentDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
        fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('Promote to Replacement Intent').length).toBeGreaterThan(0))
    fireEvent.click(screen.getByRole('button', { name: 'Promote to Replacement Intent' }))
    expect(screen.getByText('Create replacement intent')).toBeTruthy()
    fireEvent.click(screen.getByText('Create Intent'))

    expect(saveReplacementIntentSpy).toHaveBeenCalledTimes(1)
    expect(saveReplacementIntentSpy.mock.calls[0]?.[0]).toMatchObject({
      kind: 'etf_replacement_intent',
      source: 'candidate_seed',
      draftId: 'draft-1',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
      seededFromDraftId: 'draft-1',
      seedRankingId: 'etf_ranking_engine_v1',
      seedMethodologyId: 'etf_ranking_methodology_v1',
    })

    cleanup()
    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
        fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Replacement Intent')).toBeTruthy())
    expect(screen.getByText('Draft intent')).toBeTruthy()
    expect(screen.getByText('Draft intent only. This handoff does not change holdings.')).toBeTruthy()
  })

  it('opens the workspace from the replacement intent hypothetical replay action', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(makeReplacementIntent())
    vi.spyOn(portfolioWorkspaceStorage, 'getIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue({
      kind: 'intent_bound_seeded_etf_replacement_ranking',
      source: 'etf_ranking',
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      selectedAt: '2026-04-15T00:00:00Z',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
      candidateRank: 1,
      rankingId: 'etf_ranking_engine_v1',
      methodologyId: 'etf_ranking_methodology_v1',
      rankingBasisDate: '2026-04-15',
      openHandoff: {
        handoff_kind: 'ranking_artifact_open_handoff_v1',
        artifact_kind: 'etf_ranking',
        artifact_id: 'etf_ranking_artifact_sector_1',
        schema_version: 'etf_ranking_artifact_v1',
      },
      benchmarkSymbol: 'SPY',
      lookbackMonths: 6,
      peerGroup: 'Sector UCITS ETF',
      confidence: 'medium',
      holdingsSupport: 'mixed',
      requestUniverse: ['AAPL', 'IUFS'],
      evaluatedUniverse: ['IUFS'],
      warnings: [],
      excludedSymbols: [],
      selectedCandidate: {
        symbol: 'IUFS',
        rank: 1,
        compositeScore: 0.8123,
        instrument: {
          name: 'ETF',
          assetClass: 'etf',
          sector: 'Financials',
          category: 'Sector UCITS ETF',
          currency: 'USD',
        },
      },
      topCandidate: null,
      runnerUpCandidate: null,
    })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
        fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Preview Hypothetical Replay' }).length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByRole('button', { name: 'Preview Hypothetical Replay' })[0])
    expect(screen.getAllByText('Hypothetical Replay').length).toBeGreaterThan(0)
  })

  it('falls back to current seed and replay behavior when ranking artifact persistence is unavailable', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'saveIntentBoundSeededEtfReplacementRankingDraft').mockRejectedValue(new Error('IndexedDB unavailable'))
    const saveReplacementIntentSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveReplacementIntentDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/strategy-lab/etf-ranking' && method === 'POST') return jsonResponse(makeEtfRankingPayload())
      if (pathname === '/api/strategy-lab/etf-ranking/artifacts/recent/metadata' && method === 'GET') return jsonResponse(makeEtfRankingMetadataPayload())
      if (pathname === '/api/strategy-lab/etf-ranking/artifacts/recent' && method === 'GET') return jsonResponse(makeEtfRankingRecentRunsPayload())
      if (pathname === '/api/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1' && method === 'POST') return jsonResponse(makeEtfRankingPreflightPayload())
      if (pathname === '/api/strategy-lab/ranking-artifacts/open' && method === 'POST') return jsonResponse(makeEtfRankingOpenPayload())
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByText('ETF Ranking'))
    fireEvent.click(screen.getByText('Run ETF Ranking'))
    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())
    fireEvent.click(screen.getAllByText('Seed Candidate Draft')[0])
    fireEvent.change(screen.getByLabelText('Incumbent ETF'), { target: { value: 'AAPL' } })
    fireEvent.click(screen.getByText('Create Draft'))

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
        fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Promote to Replacement Intent' }).length).toBeGreaterThan(0))
    fireEvent.click(screen.getByRole('button', { name: 'Promote to Replacement Intent' }))
    fireEvent.click(screen.getByText('Create Intent'))
    expect(saveReplacementIntentSpy).toHaveBeenCalledTimes(1)
  })

  it('persists and restores a hypothetical replay for the same draft intent', async () => {
    const replacementIntent = makeReplacementIntent()
    const hypotheticalReplay = makeHypotheticalReplay()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      replay: hypotheticalReplay,
    })
    vi.spyOn(portfolioWorkspaceStorage, 'saveHypotheticalReplacementReplayDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Replacement Intent')).toBeTruthy())
    expect(screen.getByText('Portfolio Improvement Decision Summary')).toBeTruthy()
    expect(screen.getAllByText('Candidate Formation').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Construction Rule').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Construction Constraints').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Formed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Constructed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Pass').length).toBeGreaterThan(0)
    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    await waitFor(() => expect(screen.getAllByText('Replay Decision Readout').length).toBeGreaterThan(0))
    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getByText('Replacement Intent')).toBeTruthy()
    expect(screen.getByText('Replay Decision Readout')).toBeTruthy()
    expect(screen.getAllByText('Diagnostics Change').length).toBeGreaterThan(0)
  })

  it('saves a reviewed hypothetical replay as a versioned proposal artifact', async () => {
    const replacementIntent = makeReplacementIntent()
    const hypotheticalReplay = makeHypotheticalReplay()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      replay: hypotheticalReplay,
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([])
    const saveProposalSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveProposalArtifact').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Replacement Intent')).toBeTruthy())
    await waitFor(() => expect(screen.getAllByText('Save Proposal v1').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByText('Save Proposal v1')[0])

    await waitFor(() => expect(saveProposalSpy).toHaveBeenCalledTimes(1))
    expect(saveProposalSpy.mock.calls[0]?.[0]).toMatchObject({
      kind: 'single_replacement_hypothetical_replay_proposal',
      workspaceId: 'workspace-1',
      sourceDraftId: 'draft-1',
      sourceBaseNodeId: 'node-1',
      versionNumber: 1,
      savedFrom: 'desktop_hypothetical_replay_review',
      reviewStatus: 'recorded',
      replayBasis: {
        candidateConstructionRule: 'same_weight_substitution_v1',
        replayProvenance: {
          construction_rule_id: 'same_weight_substitution_v1',
          candidate_input_source: 'replacement_intent_preview',
          upstream_ids: {
            draft_id: 'draft-1',
            workspace_id: 'workspace-1',
            base_node_id: 'node-1',
          },
          seed_ranking_id: 'etf_ranking_engine_v1',
          seed_methodology_id: 'etf_ranking_methodology_v1',
          constraint_validation: {
            supplied: false,
            validation_status: null,
            constraint_set_id: null,
          },
        },
      },
    })
    expect(screen.getAllByText('Saved Proposal Review').length).toBeGreaterThan(0)
    expect(screen.getAllByText('v1').length).toBeGreaterThan(0)
    expect(screen.getByText('Latest Saved Artifact')).toBeTruthy()
    expect(screen.getByText('Recorded v1')).toBeTruthy()
    expect(screen.getAllByText('Viewing For Review').length).toBeGreaterThan(0)
  })

  it('fails before persisting a contradictory saved proposal artifact', async () => {
    const replacementIntent = makeReplacementIntent()
    const hypotheticalReplay = makeHypotheticalReplay()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      replay: hypotheticalReplay,
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'buildSavedProposalArtifact').mockImplementation(() => {
      throw new Error('Saved proposal replayProvenance construction_rule_id does not match reviewSnapshot replay_provenance')
    })
    const saveProposalSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveProposalArtifact').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('Save Proposal v1').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByText('Save Proposal v1')[0])

    await waitFor(() => expect(saveProposalSpy).not.toHaveBeenCalled())
    expect(screen.getByText('Saved proposal replayProvenance construction_rule_id does not match reviewSnapshot replay_provenance')).toBeTruthy()
  })

  it('restores formed candidate state for the active draft before replay review', async () => {
    const replacementIntent = makeReplacementIntent()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('Construction Rule').length).toBeGreaterThan(0))
    expect(screen.getAllByText('candidate_formation_derived').length).toBeGreaterThan(0)
    expect(screen.getAllByText('candidate_construction_derived').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Formed Candidate').length).toBeGreaterThan(0)
  })

  it('restores the selected construction rule for the active draft and marks mismatched construction stale', async () => {
    const replacementIntent = makeReplacementIntent()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact('fixed_split_50_50_substitution_v2'))
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('fixed_split_50_50_substitution_v2').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Stale').length).toBeGreaterThan(0)
  })

  it('restores construction constraint validation for the active draft and blocks replay when validation is blocked', async () => {
    const replacementIntent = makeReplacementIntent()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact('blocked') as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('Construction Constraints').length).toBeGreaterThan(0))
    expect(screen.getByText('Constraint validation blocked replay with 1 hard-block result.')).toBeTruthy()
    expect(screen.getByText('Hypothetical replay remains unavailable until the current constructed candidate passes construction constraints.')).toBeTruthy()
  })

  it('restores saved proposal review UI without needing live draft replay state', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([{ id: 'proposal-1', kind: 'single_replacement_hypothetical_replay_proposal', schemaVersion: 1, createdAt: '2026-04-16T00:00:00Z', workspaceId: 'workspace-1', sourceDraftId: 'draft-1', sourceBaseNodeId: 'node-1', proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z', versionNumber: 1, savedFrom: 'desktop_hypothetical_replay_review', reviewStatus: 'recorded', sourceIntent: { kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1 }, replayBasis: { benchmarkSymbol: 'SPY', startDate: '2024-01-01', endDate: '2024-12-31', rebalanceFrequency: 'monthly', commissionBps: 0, slippageBps: 0, derivationBasis: 'draft_snapshot_positions_normalized', candidateConstructionRule: 'same_weight_substitution_v1', replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } } }, reviewSnapshot: { proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' }, derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } }, baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }], replay: allocationBacktestPayload, warnings: ['Candidate weights are derived from a single-symbol replacement intent and remain hypothetical replay inputs only.'] } }])
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('Saved Proposal Review').length).toBeGreaterThan(0))
    expect(screen.getByText('Latest Saved Artifact')).toBeTruthy()
    expect(screen.getAllByText('Proposal Lineage').length).toBeGreaterThan(0)
    expect(screen.getAllByText('This proposal is a saved review snapshot, not applied holdings, candidate truth, or live draft state.').length).toBeGreaterThan(0)
  })

  it('reopens an older saved proposal inside the shell in review-only mode', async () => {
    const latestProposal = { id: 'proposal-2', kind: 'single_replacement_hypothetical_replay_proposal', schemaVersion: 1, createdAt: '2026-04-17T00:00:00Z', workspaceId: 'workspace-1', sourceDraftId: 'draft-1', sourceBaseNodeId: 'node-1', proposalFamilyId: 'etf_replacement_intent:AAPL:IUIT:2026-04-17T00:00:00Z', versionNumber: 2, savedFrom: 'desktop_hypothetical_replay_review', reviewStatus: 'recorded', sourceIntent: { kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUIT', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1 }, replayBasis: { benchmarkSymbol: 'SPY', startDate: '2024-01-01', endDate: '2024-12-31', rebalanceFrequency: 'monthly', commissionBps: 0, slippageBps: 0, derivationBasis: 'draft_snapshot_positions_normalized', candidateConstructionRule: 'same_weight_substitution_v1', replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } } }, reviewSnapshot: { proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUIT', draft_id: 'draft-1', base_node_id: 'node-1' }, derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } }, baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], candidate_weights: [{ symbol: 'IUIT', target_weight: 1 }], replay: allocationBacktestPayload, warnings: [] } }
    const olderProposal = { id: 'proposal-1', kind: 'single_replacement_hypothetical_replay_proposal', schemaVersion: 1, createdAt: '2026-04-16T00:00:00Z', workspaceId: 'workspace-1', sourceDraftId: 'draft-1', sourceBaseNodeId: 'node-1', proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-16T00:00:00Z', versionNumber: 1, savedFrom: 'desktop_hypothetical_replay_review', reviewStatus: 'recorded', sourceIntent: { kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1 }, replayBasis: { benchmarkSymbol: 'SPY', startDate: '2024-01-01', endDate: '2024-12-31', rebalanceFrequency: 'monthly', commissionBps: 0, slippageBps: 0, derivationBasis: 'draft_snapshot_positions_normalized', candidateConstructionRule: 'same_weight_substitution_v1', replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } } }, reviewSnapshot: { proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' }, derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } }, baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }], replay: allocationBacktestPayload, warnings: [] } }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([olderProposal as any, latestProposal as any])
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Latest Saved Artifact')).toBeTruthy())
    expect(screen.getAllByText('AAPL -> IUIT').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: 'Reopen In Workspace' }))

    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Saved Proposal Review').length).toBeGreaterThan(0)
  })

  it('promotes a saved proposal into a restored active thesis and clears it', async () => {
    const latestProposal = { id: 'proposal-2', kind: 'single_replacement_hypothetical_replay_proposal', schemaVersion: 1, createdAt: '2026-04-17T00:00:00Z', workspaceId: 'workspace-1', sourceDraftId: 'draft-1', sourceBaseNodeId: 'node-1', proposalFamilyId: 'etf_replacement_intent:AAPL:IUIT:2026-04-17T00:00:00Z', versionNumber: 2, savedFrom: 'desktop_hypothetical_replay_review', reviewStatus: 'recorded', sourceIntent: { kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUIT', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1 }, replayBasis: { benchmarkSymbol: 'SPY', startDate: '2024-01-01', endDate: '2024-12-31', rebalanceFrequency: 'monthly', commissionBps: 0, slippageBps: 0, derivationBasis: 'draft_snapshot_positions_normalized', candidateConstructionRule: 'same_weight_substitution_v1', replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } } }, reviewSnapshot: { proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUIT', draft_id: 'draft-1', base_node_id: 'node-1' }, derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } }, baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], candidate_weights: [{ symbol: 'IUIT', target_weight: 1 }], replay: allocationBacktestPayload, warnings: [] } }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([latestProposal as any])
    vi.spyOn(portfolioWorkspaceStorage, 'getActiveThesis').mockResolvedValue({ workspaceId: 'workspace-1', promotedAt: '2026-04-17T12:00:00Z', sourceProposalId: 'proposal-2', thesisProposal: latestProposal as any })
    const saveActiveThesisSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveActiveThesis').mockResolvedValue()
    const deleteActiveThesisSpy = vi.spyOn(portfolioWorkspaceStorage, 'deleteActiveThesis').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Active Thesis')).toBeTruthy())
    expect(screen.getAllByText('v2 · AAPL -> IUIT').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByTestId('saved-proposal-promote-proposal-2'))
    await waitFor(() => expect(saveActiveThesisSpy).toHaveBeenCalledTimes(1))
    expect(saveActiveThesisSpy.mock.calls[0]?.[0]).toMatchObject({ workspaceId: 'workspace-1', sourceProposalId: 'proposal-2' })

    fireEvent.click(screen.getByTestId('clear-active-thesis'))
    await waitFor(() => expect(deleteActiveThesisSpy).toHaveBeenCalledWith('workspace-1'))
  })

  it('does not restore an active thesis when the embedded saved proposal artifact is contradictory', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'getActiveThesis').mockRejectedValue(new Error('Saved proposal replayProvenance seed_methodology_id does not match reviewSnapshot replay_provenance'))
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.queryByText('Active Thesis')).toBeNull())
  })

  it('clears stale candidate annotation state when the restored draft has no saved annotation', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    expect(screen.queryByText('Seeded Candidate Review')).toBeNull()
  })

  it('does not propagate candidate annotation when switching active nodes', async () => {
    const variantNode = mockSavedVariantNode()
    const cleanVariantDraft = { id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: persistedSnapshot }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return variantNode
      return { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
      .mockResolvedValueOnce(cleanVariantDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft')
      .mockResolvedValueOnce({
        workspaceId: 'workspace-1',
        draftId: 'draft-1',
        baseNodeId: 'node-1',
        seed: {
          kind: 'etf_replacement_candidate',
          source: 'etf_ranking',
          seededAt: '2026-04-15T00:00:00Z',
          baseSymbol: 'AAPL',
          candidateSymbol: 'IUFS',
          candidateRank: 1,
          peerGroup: 'Sector UCITS ETF',
          benchmarkSymbol: 'SPY',
          lookbackMonths: 6,
          rankingId: 'etf_ranking_engine_v1',
          methodologyId: 'etf_ranking_methodology_v1',
          rankingBasisDate: '2026-04-15',
          confidence: 'medium',
          holdingsSupport: 'mixed',
          requestUniverse: ['AAPL', 'IUFS'],
          evaluatedUniverse: ['IUFS'],
          warningCount: 1,
          excludedSymbolsCount: 0,
        },
      })
      .mockResolvedValueOnce(null)
    const persistActiveNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'setActiveNode').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(variantExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    fireEvent.click(screen.getAllByRole('button', { name: 'Open' }).find((button) => !button.hasAttribute('disabled')) as HTMLButtonElement)

    await waitFor(() => expect(persistActiveNodeSpy).toHaveBeenCalledWith({ workspaceId: 'workspace-1', nodeId: 'node-2', createDraftFromNode: true }))
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.queryByText('Seeded Candidate Review')).toBeNull())
  })

  it('does not propagate candidate annotation after saving a variant', async () => {
    const importedWorkspace = mockImportedWorkspace()
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(null)
    vi.spyOn(portfolioWorkspaceStorage, 'saveVariantFromDraft').mockResolvedValue({
      node: variantNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return variantNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({
      ...importedWorkspace.draft,
      baseNodeId: 'node-2',
      status: 'clean',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockImplementation(async () => [importedWorkspace.rootNode, variantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:10:00Z' })
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') return jsonResponse(bootstrapPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run-imported' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/strategy-lab/etf-ranking' && method === 'POST') return jsonResponse(makeEtfRankingPayload())
      if (pathname === '/api/strategy-lab/etf-ranking/artifacts/recent/metadata' && method === 'GET') return jsonResponse(makeEtfRankingMetadataPayload())
      if (pathname === '/api/strategy-lab/etf-ranking/artifacts/recent' && method === 'GET') return jsonResponse(makeEtfRankingRecentRunsPayload())
      if (pathname === '/api/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1' && method === 'POST') return jsonResponse(makeEtfRankingPreflightPayload())
      if (pathname === '/api/strategy-lab/ranking-artifacts/open' && method === 'POST') return jsonResponse(makeEtfRankingOpenPayload())
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })

    await waitFor(() => expect(screen.getByText('Project summary')).toBeTruthy())
    fireEvent.click(screen.getByText('ETF Ranking'))
    fireEvent.click(screen.getByText('Run ETF Ranking'))
    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())
    fireEvent.click(screen.getAllByText('Seed Candidate Draft')[0])
    fireEvent.change(screen.getByLabelText('Incumbent ETF'), { target: { value: 'AAPL' } })
    fireEvent.click(screen.getByText('Create Draft'))
    await waitFor(() => expect(screen.getByText('Seeded Candidate Review')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    fireEvent.change(screen.getByPlaceholderText('Variant name'), { target: { value: 'Raise MSFT' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Variant' }))

    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.queryByText('Seeded Candidate Review')).toBeNull())
  })

  it('uses fresh-draft discard flow so annotations do not survive discard', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
      .mockResolvedValueOnce({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:05:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft')
      .mockResolvedValueOnce({
        workspaceId: 'workspace-1',
        draftId: 'draft-1',
        baseNodeId: 'node-1',
        seed: {
          kind: 'etf_replacement_candidate',
          source: 'etf_ranking',
          seededAt: '2026-04-15T00:00:00Z',
          baseSymbol: 'AAPL',
          candidateSymbol: 'IUFS',
          candidateRank: 1,
          peerGroup: 'Sector UCITS ETF',
          benchmarkSymbol: 'SPY',
          lookbackMonths: 6,
          rankingId: 'etf_ranking_engine_v1',
          methodologyId: 'etf_ranking_methodology_v1',
          rankingBasisDate: '2026-04-15',
          confidence: 'medium',
          holdingsSupport: 'mixed',
          requestUniverse: ['AAPL', 'IUFS'],
          evaluatedUniverse: ['IUFS'],
          warningCount: 1,
          excludedSymbolsCount: 0,
        },
      })
      .mockResolvedValueOnce(null)
    const persistActiveNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'setActiveNode').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:05:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Discard draft' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Discard draft' }))

    await waitFor(() => expect(persistActiveNodeSpy).toHaveBeenCalledWith({ workspaceId: 'workspace-1', nodeId: 'node-1', createDraftFromNode: true }))
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.queryByText('Seeded Candidate Review')).toBeNull())
  })

  it('resets the local workspace database from the dashboard', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const resetSpy = vi.spyOn(portfolioWorkspaceStorage, 'resetLocalPortfolioDatabase').mockResolvedValue()

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Reset Local DB')).toBeTruthy())
    fireEvent.click(screen.getByText('Reset Local DB'))

    await waitFor(() => expect(resetSpy).toHaveBeenCalled())
    expect(screen.getByText('Import Portfolio')).toBeTruthy()
  })

  it('keeps exposure and dashboard views usable after importing a portfolio', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(mockImportedWorkspace())
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2026 = new File(['2026'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })
    fireEvent.change(input, { target: { files: [file2026] } })

    await waitFor(() => expect(screen.getByText('Project summary')).toBeTruthy())
    expect(screen.getByLabelText('Sector allocation pie chart')).toBeTruthy()
    expect(screen.getByText('Saved Variants')).toBeTruthy()
    expect(screen.getByText(/^base · active$/)).toBeTruthy()

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByText('Risk Path')).toBeTruthy())
    expect(screen.getByText('Actual Exposure')).toBeTruthy()

    fireEvent.click(screen.getByText('Dashboard'))
    await waitFor(() => expect(screen.getByLabelText('Sector allocation pie chart')).toBeTruthy())
  })

  it('saves a draft as a child variant and shows it in the variant list', async () => {
    const importedWorkspace = mockImportedWorkspace()
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'saveVariantFromDraft').mockResolvedValue({
      node: variantNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return variantNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({
      ...importedWorkspace.draft,
      baseNodeId: 'node-2',
      status: 'clean',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockImplementation(async () => [importedWorkspace.rootNode, variantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:10:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })

    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())

    const variantNameInput = screen.getByPlaceholderText('Variant name')
    fireEvent.change(variantNameInput, { target: { value: 'Raise MSFT' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Variant' }))

    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    const variantRow = screen.getByText((content) => content.includes('Raise MSFT') && content.includes('active'))
    expect(variantRow).toBeTruthy()
  })

  it('opens a saved variant by creating a clean working draft from that node', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })

    const variantNode = mockSavedVariantNode()
    const cleanVariantDraft = {
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-2',
      updatedAt: '2026-04-10T00:12:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: persistedSnapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:00:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return variantNode
      return { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(cleanVariantDraft)
    const persistActiveNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'setActiveNode').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(variantExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    fireEvent.click(screen.getAllByRole('button', { name: 'Open' }).find((button) => !button.hasAttribute('disabled')) as HTMLButtonElement)

    await waitFor(() => expect(persistActiveNodeSpy).toHaveBeenCalledWith({ workspaceId: 'workspace-1', nodeId: 'node-2', createDraftFromNode: true }))
    expect(screen.getByLabelText('Sector allocation pie chart')).toBeTruthy()
    expect(screen.getByText('Project summary')).toBeTruthy()
    expect(screen.getByText('Performance history is unavailable for this import.')).toBeTruthy()
    expect(screen.getByText((content) => content.includes('2026-01-01 - 2026-04-10'))).toBeTruthy()
  })

  it('switches from a variant back to the imported base and restores imported dashboard history', async () => {
    const baseNode = { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base' as const, name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
    const variantNode = mockSavedVariantNode()
    const variantDraft = { id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: persistedSnapshot }
    const baseDraft = { id: 'draft-3', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:13:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: persistedSnapshot }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-2',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([baseNode, variantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-1' ? baseNode : variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce(variantDraft)
      .mockResolvedValueOnce(baseDraft)
    const persistActiveNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'setActiveNode').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:13:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:13:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    expect(screen.getByText('Performance history is unavailable for this import.')).toBeTruthy()

    fireEvent.click(screen.getAllByRole('button', { name: 'Open' }).find((button) => !button.hasAttribute('disabled')) as HTMLButtonElement)

    await waitFor(() => expect(persistActiveNodeSpy).toHaveBeenCalledWith({ workspaceId: 'workspace-1', nodeId: 'node-1', createDraftFromNode: true }))
    await waitFor(() => expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy())
    expect(screen.getByText('Project summary')).toBeTruthy()
  })

  it('opens an IB2026 imported snapshot node and keeps canonical dashboard values aligned', async () => {
    const baseSnapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: '2025-01-01 - 2025-12-31',
        importedAt: '2026-04-10T00:00:00Z',
        sourceFileNames: ['IB2025.pdf'],
      },
      positions: [{ symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
      cashBalances: [{ currency: 'USD', amount: 1000 }],
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const ib2026Snapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
        positions.map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026',
      createdAt: '2026-04-14T00:00:00Z',
      changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
      portfolioSnapshot: ib2026Snapshot,
      source: buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
    }
    const cleanImportedDraft = {
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-2',
      updatedAt: '2026-04-14T00:00:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: ib2026Snapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-14T00:00:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-12-31' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: baseSnapshot },
      importedSnapshotNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      return { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: baseSnapshot }
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: baseSnapshot })
      .mockResolvedValueOnce(cleanImportedDraft)
    const persistActiveNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'setActiveNode').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026ExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026DiagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026DashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    fireEvent.click(screen.getAllByRole('button', { name: 'Open' }).find((button) => !button.hasAttribute('disabled')) as HTMLButtonElement)

    await waitFor(() => expect(persistActiveNodeSpy).toHaveBeenCalledWith({ workspaceId: 'workspace-1', nodeId: 'node-2', createDraftFromNode: true }))
    expect(screen.getByText(ib2026DashboardGolden.loadedFileLabel)).toBeTruthy()
    expect(screen.getByText(`Portfolio value: ${ib2026DashboardGolden.portfolioValue}`)).toBeTruthy()
    expect(screen.getByText((content) => content.includes(ib2026DashboardGolden.statementPeriod))).toBeTruthy()
    fireEvent.click(screen.getByText('Technology'))
    expect(screen.getByDisplayValue('SXRV')).toBeTruthy()
    expect(screen.getByDisplayValue(ib2026DashboardGolden.sxrvValue)).toBeTruthy()
  })

  it('restores a child variant under an imported IB2026 snapshot with unavailable dashboard history', async () => {
    const baseSnapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: '2025-01-01 - 2025-12-31',
        importedAt: '2026-04-10T00:00:00Z',
        sourceFileNames: ['IB2025.pdf'],
      },
      positions: [{ symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
      cashBalances: [{ currency: 'USD', amount: 1000 }],
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const ib2026Snapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
        positions.map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector,
          sourceType: 'equity' as const,
        }))),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026',
      createdAt: '2026-04-14T00:00:00Z',
      changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
      portfolioSnapshot: ib2026Snapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
      },
    }
    const variantFromImportedSnapshot: PortfolioSnapshot = {
      ...ib2026Snapshot,
      positions: ib2026Snapshot.positions.map((position, index) => index === 0 ? { ...position, marketValue: position.marketValue + 5000 } : position),
    }
    const importedVariantNode = {
      id: 'node-3',
      workspaceId: 'workspace-1',
      parentId: 'node-2',
      kind: 'variant' as const,
      name: 'Raise SXRV',
      createdAt: '2026-04-14T00:10:00Z',
      changeSummary: { label: 'Raise SXRV', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: variantFromImportedSnapshot,
    }
    const importedDraft = {
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-2',
      updatedAt: '2026-04-14T00:00:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: ib2026Snapshot,
    }
    const variantDraft = {
      id: 'draft-3',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-3',
      updatedAt: '2026-04-14T00:10:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: variantFromImportedSnapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:10:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-14T00:10:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-3',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-12-31' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: baseSnapshot },
      importedSnapshotNode,
      importedVariantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(importedVariantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(variantDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:10:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026ExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026DiagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Loaded file: IB2026.pdf')).toBeTruthy())
    expect(screen.queryByText(ib2026DashboardGolden.portfolioValue)).toBeNull()
    expect(screen.queryByText(`Portfolio value: ${ib2026DashboardGolden.portfolioValue}`)).toBeNull()
  })

  it('shows base and child variant lineage consistently after reload', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-2',
      source: buildImportedSource({ importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    expect(screen.getByText(/^base$/)).toBeTruthy()
    expect(screen.getByText(/base -> Raise MSFT/)).toBeTruthy()

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    expect(screen.getByText('Working Draft · base -> Raise MSFT')).toBeTruthy()
  })

  it('reuses imported diagnostics when selecting the base snapshot in Exposure after reload', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-2',
      source: buildImportedSource({ importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-1'
      ? { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
      : variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-1' } })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))
    expect(fetchMock.mock.calls[4]?.[0]).toBe('/api/engines/diagnostics/run-imported')
  })

  it('uses history-aware snapshot diagnostics for saved variants in Exposure', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-2',
      source: buildImportedSource({ importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'node-2', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-2' } })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))
    expect(fetchMock.mock.calls[4]?.[0]).toBe('/api/engines/diagnostics/run')
    expect(String(fetchMock.mock.calls[4]?.[1]?.body)).toContain('history_context')
  })

  it('uses snapshot-history diagnostics instead of imported replay for a child variant under an imported snapshot', async () => {
    const baseNode = {
      id: 'node-1',
      workspaceId: 'workspace-1',
      parentId: null,
      kind: 'imported_base' as const,
      name: 'Base Import',
      createdAt: '2026-04-10T00:00:00Z',
      changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 },
      portfolioSnapshot: persistedSnapshot,
    }
    const importedSnapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
        positions.map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026',
      createdAt: '2026-04-14T00:00:00Z',
      changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
      portfolioSnapshot: importedSnapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
      },
    }
    const importedVariantSnapshot: PortfolioSnapshot = {
      ...importedSnapshot,
      positions: importedSnapshot.positions.map((position, index) => index === 0 ? { ...position, marketValue: position.marketValue + 5000 } : position),
    }
    const importedVariantNode = {
      id: 'node-3',
      workspaceId: 'workspace-1',
      parentId: 'node-2',
      kind: 'variant' as const,
      name: 'Raise SXRV',
      createdAt: '2026-04-14T00:10:00Z',
      changeSummary: { label: 'Raise SXRV', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: importedVariantSnapshot,
    }
    const variantDraft = {
      id: 'draft-3',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-3',
      updatedAt: '2026-04-14T00:10:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: importedVariantSnapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:10:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-14T00:10:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-3',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-12-31' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([baseNode, importedSnapshotNode, importedVariantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      if (nodeId === 'node-3') return importedVariantNode
      return baseNode
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(variantDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'node-3', lastOpenedAt: '2026-04-14T00:10:00Z' })

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026ExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026DiagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026ExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026DiagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-3' } })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))
    expect(fetchMock.mock.calls[4]?.[0]).toBe('/api/engines/diagnostics/run')
    expect(String(fetchMock.mock.calls[4]?.[1]?.body)).toContain('history_context')
    expect(fetchMock.mock.calls.slice(0, 5).some((call) => call[0] === '/api/engines/diagnostics/run-imported')).toBe(false)
  })
})
