import { afterEach, describe, expect, it, vi } from 'vitest'

import { createImportedBootstrapResponseFixture } from '../test/portfolioFixtures'
import * as portfolioDb from './portfolioDb'
import * as portfolioWorkspaceStorage from './portfolioWorkspaceStorage'
import { buildPersistedImportedSource } from './portfolioWorkspaceStorage'
import type { ConstructionArtifactReplayResponse, OptimizerHandoffReplayResponse, OptimizerHandoffValidationResponse, OptimizerPersistedArtifactReference } from '../features/portfolio/types'
import type { ImportedHistoryContext, PersistedOptimizerHandoffWorkspaceReview, PortfolioNode, PortfolioWorkspace } from '../features/portfolio/workspaceTypes'

function expectPersistedOptimizerHandoffSource(value: PortfolioWorkspace['source']) {
  expect('kind' in value && value.kind === 'persisted_optimizer_handoff').toBe(true)
  if (!('kind' in value) || value.kind !== 'persisted_optimizer_handoff') {
    throw new Error('Expected persisted optimizer handoff workspace source in test fixture')
  }
  return value
}

const availableInvestorEconomicsStatus = { status: 'available' as const, reason: null }

const importedSnapshot = createImportedBootstrapResponseFixture().snapshot

function createHistoryContext(): ImportedHistoryContext {
  return {
    benchmarkSymbol: 'SPY',
    statementPeriod: '2025-01-01 - 2025-12-31',
    importedAt: '2026-04-10T00:00:00Z',
    importer: 'interactive_brokers',
    sourceFileNames: ['IB2025.pdf'],
    historyStartDate: '2025-01-02',
    historyEndDate: '2025-03-03',
  }
}

function createConstructionArtifactReplayResponse(): ConstructionArtifactReplayResponse {
  return {
    construction_artifact_id: 'artifact-123',
    truth_separation: {
      baseline_truth: 'imported_portfolio_snapshot',
      candidate_truth: 'hypothetical_construction_artifact',
      candidate_applied: false,
      consumption_mode: 'explicit_reference_only',
    },
    replay_provenance: {
      source: 'construction_artifact_reference',
      construction_artifact_id: 'artifact-123',
      policy_id: 'policy-1',
      policy_definition_id: 'policy-def-1',
      ranked_universe_artifact_id: 'ranked-1',
      ranking_id: 'ranking-1',
      ranking_methodology_id: 'method-1',
      current_portfolio_artifact_id: 'portfolio-1',
      hard_constraints: {
        full_investment: true,
        long_only: true,
        eligible_ranked_universe_only: true,
        max_position_weight: 0.6,
        min_position_weight: null,
        max_turnover_weight: null,
        max_trade_intent_count: null,
      },
      baseline_input_source: 'normalized_inputs.current_portfolio_weights',
      candidate_input_source: 'final_target_weights',
      selection_rule_trace: {
        rule_ids: ['rule-1'],
        steps: [
          {
            rule_id: 'rule-1',
            rule_order: 1,
            input_candidate_symbols: ['AAPL'],
            output_candidate_symbols: ['MSFT'],
          },
        ],
      },
      turnover_diagnostics_status: 'unavailable_legacy_artifact',
      turnover_diagnostics_v1: null,
      weighting_trace_status: 'unavailable_legacy_artifact',
      weighting_trace_v1: null,
    },
    baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }],
    candidate_weights: [{ symbol: 'MSFT', target_weight: 0.6 }],
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
    replay: {
      methodology: 'm',
      investor_economics_status: { status: 'available', reason: null },
      reference_result: null,
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
        equity_curve: [],
        rebalance_events: [],
        trades: [],
      },
      comparison: null,
      reference_diagnostics: null,
      candidate_diagnostics: null,
      diagnostics_comparison: null,
    },
  }
}

function createOptimizerHandoffReference(): OptimizerPersistedArtifactReference {
  return {
    reference_kind: 'optimizer_handoff_reference_v1',
    handoff_id: 'optimizer_handoff_123',
    artifact_id: 'optimizer_artifact_123',
    manifest_path: '/tmp/optimizer_handoff_123/manifest.json',
    artifact_path: '/tmp/optimizer_handoff_123/artifact.json',
  }
}

function createOptimizerHandoffValidationResponse(): OptimizerHandoffValidationResponse {
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
  }
}

function createOptimizerHandoffReplayResponse(): OptimizerHandoffReplayResponse {
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
    replay: createConstructionArtifactReplayResponse().replay,
  }
}

function createPersistedOptimizerHandoffWorkspaceReview(overrides: Partial<PersistedOptimizerHandoffWorkspaceReview> = {}): PersistedOptimizerHandoffWorkspaceReview {
  return {
    workspaceId: 'workspace-optimizer',
    handoffReference: createOptimizerHandoffReference(),
    openedAt: '2026-04-24T00:00:00Z',
    validation: createOptimizerHandoffValidationResponse(),
    replay: createOptimizerHandoffReplayResponse(),
    ...overrides,
  }
}

function createOptimizerHandoffWorkspaceReviewBasisFixture() {
  return {
    basisVersion: 1 as const,
    basisKind: 'persisted_optimizer_handoff_review' as const,
    handoffReference: createOptimizerHandoffReference(),
    openedAt: '2026-04-24T00:00:00Z',
    benchmarkSymbol: 'SPY',
    baseCurrency: 'USD',
    replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
    baselineWeights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
    candidateWeights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
  }
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('portfolioWorkspaceStorage', () => {
  it('builds persisted sources with historySource only', () => {
    const persistedSource = buildPersistedImportedSource({
      importedFileNames: ['IB2025.pdf'],
      importedAt: '2026-04-10T00:00:00Z',
      importer: 'interactive_brokers',
      baseCurrency: 'USD',
      historyContext: createHistoryContext(),
      importedHistorySnapshot: importedSnapshot,
    })

    expect(persistedSource).toEqual({
      importedFileNames: ['IB2025.pdf'],
      importedAt: '2026-04-10T00:00:00Z',
      importer: 'interactive_brokers',
      baseCurrency: 'USD',
      historySource: {
        kind: 'imported_replay',
        historyContext: createHistoryContext(),
        importedHistorySnapshot: importedSnapshot,
      },
    })
    expect('historyContext' in persistedSource).toBe(false)
    expect('importedHistorySnapshot' in persistedSource).toBe(false)
  })

  it('embeds current-format persisted sources inside workspaces', () => {
    const cleanWorkspace: PortfolioWorkspace = {
      id: 'workspace-clean',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:00:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildPersistedImportedSource({
        importedFileNames: ['IB2025.pdf'],
        importedAt: '2026-04-10T00:00:00Z',
        importer: 'interactive_brokers',
        baseCurrency: 'USD',
        historyContext: createHistoryContext(),
        importedHistorySnapshot: importedSnapshot,
      }),
    }

    expect('historySource' in cleanWorkspace.source && cleanWorkspace.source.historySource.kind).toBe('imported_replay')
  })

  it('creates and restores persisted construction artifact workspace reviews', async () => {
    const replay = createConstructionArtifactReplayResponse()
    const persisted = new Map<string, unknown>()
    const withStoresSpy = vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) persisted.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })
    const withStoreSpy = vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      if (storeName === portfolioDb.persistedConstructionArtifactReviewStoreName) {
        const store = {
          get(key: string) {
            const request = { ...requestTemplate, result: persisted.get(`${storeName}:${key}`) }
            queueMicrotask(() => request.onsuccess?.())
            return request
          },
        } as unknown as IDBObjectStore
        return new Promise((resolve, reject) => handler(store, resolve, reject))
      }
      return Promise.resolve(null as never)
    })

    const created = await portfolioWorkspaceStorage.createWorkspaceFromPersistedConstructionArtifact({
      constructionArtifactId: 'artifact-123',
      openedAt: '2026-04-23T00:00:00Z',
      replay,
    })

    expect(created.workspace.source).toEqual({
      kind: 'persisted_construction_artifact',
      constructionArtifactId: 'artifact-123',
      openedAt: '2026-04-23T00:00:00Z',
      reviewBasis: {
        basisVersion: 1,
        basisKind: 'persisted_construction_artifact_review',
        constructionArtifactId: 'artifact-123',
        openedAt: '2026-04-23T00:00:00Z',
        benchmarkSymbol: 'SPY',
        baseCurrency: 'USD',
        replayWindow: {
          startDate: '2024-01-01',
          endDate: '2024-12-31',
        },
        baselineWeights: [{ symbol: 'AAPL', target_weight: 0.6 }],
        candidateWeights: [{ symbol: 'MSFT', target_weight: 0.6 }],
      },
    })
    expect(created.draft).toBeNull()
    expect(created.rootNode.name).toBe('Artifact Review Basis')
    expect(created.rootNode.kind).toBe('artifact_review_basis')
    expect(created.rootNode.portfolioSnapshot).toBeNull()
    expect(created.rootNode.artifactReviewBasis).toMatchObject({
      constructionArtifactId: 'artifact-123',
      basisKind: 'persisted_construction_artifact_review',
    })
    expect(created.review).toMatchObject({
      workspaceId: created.workspace.id,
      constructionArtifactId: 'artifact-123',
      replay,
    })

    await expect(portfolioWorkspaceStorage.getPersistedConstructionArtifactWorkspaceReview(created.workspace.id)).resolves.toMatchObject({
      workspaceId: created.workspace.id,
      constructionArtifactId: 'artifact-123',
      replay,
    })
    expect(withStoresSpy).toHaveBeenCalled()
    expect(withStoreSpy).toHaveBeenCalled()
  })

  it('hydrates effective replay params for older cached construction artifact reviews', async () => {
    const legacyReplay = createConstructionArtifactReplayResponse()
    delete (legacyReplay as { effective_replay_params?: unknown }).effective_replay_params
    const review = {
      workspaceId: 'workspace-artifact',
      constructionArtifactId: 'artifact-123',
      openedAt: '2026-04-23T00:00:00Z',
      replay: legacyReplay,
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      const store = {
        get(_key: string) {
          const request = { ...requestTemplate, result: storeName === portfolioDb.persistedConstructionArtifactReviewStoreName ? review : undefined }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getPersistedConstructionArtifactWorkspaceReview('workspace-artifact')).resolves.toMatchObject({
      replay: {
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
    })
  })

  it('uses current-contract construction artifact fixtures with max_trade_intent_count', () => {
    expect(createConstructionArtifactReplayResponse().replay_provenance.hard_constraints).toMatchObject({
      max_trade_intent_count: null,
    })
  })

  it('normalizes legacy cached artifact review workspaces to review-basis records', async () => {
    const review = {
      workspaceId: 'workspace-artifact',
      constructionArtifactId: 'artifact-123',
      openedAt: '2026-04-23T00:00:00Z',
      replay: createConstructionArtifactReplayResponse(),
    }
    const writes = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string }).id
              if (key) writes.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })

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
    } satisfies PortfolioWorkspace
    const node = {
      id: 'node-artifact',
      workspaceId: 'workspace-artifact',
      parentId: null,
      kind: 'imported_base' as const,
      name: 'Construction Artifact Review',
      createdAt: '2026-04-23T00:00:00Z',
      changeSummary: { label: 'Construction Artifact Review', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: {
        snapshotVersion: 1 as const,
        baseCurrency: 'USD',
        importedMeta: { importer: null, statementPeriod: '2024-01-01 - 2024-12-31', importedAt: '2026-04-23T00:00:00Z', sourceFileNames: ['artifact-123'] },
        positions: [{ symbol: 'AAPL', marketValue: 0.6, quantity: null, currency: null, sector: null, sourceType: 'other' as const }],
        cashBalances: [],
        metadata: { benchmarkSymbol: 'SPY', notes: null, tags: ['persisted_construction_artifact_review'] },
      },
    } satisfies PortfolioNode

    const normalized = await portfolioWorkspaceStorage.normalizeLegacyPersistedConstructionArtifactWorkspaceCache({ workspace, node, review })

    expect(normalized.workspace.source).toMatchObject({
      kind: 'persisted_construction_artifact',
      reviewBasis: {
        basisKind: 'persisted_construction_artifact_review',
      },
    })
    expect(normalized.node).toMatchObject({
      kind: 'artifact_review_basis',
      name: 'Artifact Review Basis',
      portfolioSnapshot: null,
    })
    expect(writes.get(`${portfolioDb.workspaceStoreName}:workspace-artifact`)).toBeTruthy()
    expect(writes.get(`${portfolioDb.portfolioNodeStoreName}:node-artifact`)).toBeTruthy()
  })

  it('creates and restores persisted optimizer handoff workspace reviews', async () => {
    const validation = createOptimizerHandoffValidationResponse()
    const replay = createOptimizerHandoffReplayResponse()
    const handoffReference = createOptimizerHandoffReference()
    const persisted = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) persisted.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })
    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      if (storeName === portfolioDb.persistedOptimizerHandoffReviewStoreName) {
        const store = {
          get(key: string) {
            const request = { ...requestTemplate, result: persisted.get(`${storeName}:${key}`) }
            queueMicrotask(() => request.onsuccess?.())
            return request
          },
        } as unknown as IDBObjectStore
        return new Promise((resolve, reject) => handler(store, resolve, reject))
      }
      return Promise.resolve(null as never)
    })

    const created = await portfolioWorkspaceStorage.createWorkspaceFromPersistedOptimizerHandoff({ handoffReference, validation, replay, openedAt: '2026-04-24T00:00:00Z' })

    expect(created.workspace.source).toMatchObject({
      kind: 'persisted_optimizer_handoff',
      handoffReference,
      reviewBasis: {
        basisKind: 'persisted_optimizer_handoff_review',
        handoffReference,
      },
    })
    expect('handoffId' in created.workspace.source).toBe(false)
    expect('artifactId' in created.workspace.source).toBe(false)
    const createdWorkspaceSource = expectPersistedOptimizerHandoffSource(created.workspace.source)
    if (createdWorkspaceSource.reviewBasis) {
      expect('handoffId' in createdWorkspaceSource.reviewBasis).toBe(false)
      expect('artifactId' in createdWorkspaceSource.reviewBasis).toBe(false)
    }
    expect(created.rootNode.kind).toBe('artifact_review_basis')
    expect(created.rootNode.portfolioSnapshot).toBeNull()
    expect(created.review.validation.validation_status).toBe('ok')
    expect('handoffId' in created.review).toBe(false)
    expect('artifactId' in created.review).toBe(false)
    await expect(portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview(created.workspace.id)).resolves.toMatchObject({
      workspaceId: created.workspace.id,
      handoffReference,
      validation: { validation_status: 'ok' },
      replay: { handoff_id: 'optimizer_handoff_123' },
    })
    const persistedReview = persisted.get(`${portfolioDb.persistedOptimizerHandoffReviewStoreName}:${created.workspace.id}`) as Record<string, unknown>
    expect(persistedReview).toBeTruthy()
    expect('handoffId' in persistedReview).toBe(false)
    expect('artifactId' in persistedReview).toBe(false)
  })

  it('uses the same canonical optimizer handoff contract across create and save writes', async () => {
    const persisted = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) persisted.set(`${name}:${key}`, structuredClone(value))
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })
    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const store = {
        put(value: unknown) {
          const key = (value as { workspaceId?: string }).workspaceId
          if (key) persisted.set(`${storeName}:${key}`, structuredClone(value))
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    const created = await portfolioWorkspaceStorage.createWorkspaceFromPersistedOptimizerHandoff({
      handoffReference: createOptimizerHandoffReference(),
      validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: null },
      replay: createOptimizerHandoffReplayResponse(),
      openedAt: '2026-04-24T00:00:00Z',
    })
    const createdPersistedReview = structuredClone(
      persisted.get(`${portfolioDb.persistedOptimizerHandoffReviewStoreName}:${created.workspace.id}`),
    )

    await portfolioWorkspaceStorage.savePersistedOptimizerHandoffWorkspaceReview({
      ...created.review,
      validation: { ...created.review.validation, artifact_id: null },
      handoffId: created.review.handoffReference.handoff_id,
      artifactId: created.review.handoffReference.artifact_id,
    } as PersistedOptimizerHandoffWorkspaceReview)

    expect(persisted.get(`${portfolioDb.persistedOptimizerHandoffReviewStoreName}:${created.workspace.id}`)).toEqual(createdPersistedReview)
    expect(createdPersistedReview).toEqual({
      workspaceId: created.workspace.id,
      handoffReference: createOptimizerHandoffReference(),
      openedAt: '2026-04-24T00:00:00Z',
      validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: null },
      replay: createOptimizerHandoffReplayResponse(),
    })
  })

  it('repairs legacy optimizer handoff cache identities at load time only', async () => {
    const legacyReview = {
      workspaceId: 'workspace-optimizer',
      handoffId: 'optimizer_handoff_123',
      artifactId: 'optimizer_artifact_123',
      handoffReference: createOptimizerHandoffReference(),
      openedAt: '2026-04-24T00:00:00Z',
      validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: null },
      replay: createOptimizerHandoffReplayResponse(),
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: legacyReview as unknown }
      const store = {
        get(_key: string) {
          const request = { ...requestTemplate }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview('workspace-optimizer')).resolves.toMatchObject({
      handoffReference: { handoff_id: 'optimizer_handoff_123', artifact_id: 'optimizer_artifact_123' },
      validation: { artifact_id: null },
    })
    const restored = await portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview('workspace-optimizer')
    expect(restored).toBeTruthy()
    expect(restored && 'handoffId' in restored).toBe(false)
    expect(restored && 'artifactId' in restored).toBe(false)
  })

  it('fails closed when persisted optimizer handoff cache is missing a valid canonical handoff reference', async () => {
    const badReview = {
      workspaceId: 'workspace-optimizer',
      handoffReference: {
        reference_kind: 'optimizer_handoff_reference_v1',
        handoff_id: 'optimizer_handoff_123',
        artifact_id: '',
        manifest_path: '/tmp/optimizer_handoff_123/manifest.json',
        artifact_path: '/tmp/optimizer_handoff_123/artifact.json',
      },
      openedAt: '2026-04-24T00:00:00Z',
      validation: createOptimizerHandoffValidationResponse(),
      replay: createOptimizerHandoffReplayResponse(),
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badReview as unknown }
      const store = {
        get(_key: string) {
          const request = { ...requestTemplate }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview('workspace-optimizer')).rejects.toThrow(
      'Persisted optimizer handoff review cache is missing or invalid handoff reference',
    )
  })

  it('fails closed when persisted optimizer handoff cache replay identity mismatches the reference', async () => {
    const badReview = {
      workspaceId: 'workspace-optimizer',
      handoffReference: createOptimizerHandoffReference(),
      openedAt: '2026-04-24T00:00:00Z',
      validation: createOptimizerHandoffValidationResponse(),
      replay: { ...createOptimizerHandoffReplayResponse(), handoff_id: 'optimizer_handoff_other' },
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badReview as unknown }
      const store = {
        get(_key: string) {
          const request = { ...requestTemplate }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview('workspace-optimizer')).rejects.toThrow(
      'Persisted optimizer handoff review cache is inconsistent with replay identity',
    )
  })

  it('fails closed before saving optimizer handoff reviews when validation artifact identity mismatches', async () => {
    const persisted = new Map<string, unknown>()
    const withStoreSpy = vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const store = {
        put(value: unknown) {
          const key = (value as { workspaceId?: string }).workspaceId
          if (key) persisted.set(`${storeName}:${key}`, value)
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.savePersistedOptimizerHandoffWorkspaceReview(
      createPersistedOptimizerHandoffWorkspaceReview({
        validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: 'optimizer_artifact_other' },
      }),
    )).rejects.toThrow('Persisted optimizer handoff review cache is inconsistent with validation artifact identity')

    expect(withStoreSpy).not.toHaveBeenCalled()
    expect(persisted.size).toBe(0)
  })

  it('fails closed when persisted optimizer handoff cache is missing the canonical replay objective', async () => {
    const badReview = {
      workspaceId: 'workspace-optimizer',
      handoffReference: createOptimizerHandoffReference(),
      openedAt: '2026-04-24T00:00:00Z',
      validation: createOptimizerHandoffValidationResponse(),
      replay: {
        ...createOptimizerHandoffReplayResponse(),
        optimizer_context: {
          ...createOptimizerHandoffReplayResponse().optimizer_context!,
          objective: null,
        },
      },
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badReview as unknown }
      const store = {
        get(_key: string) {
          const request = { ...requestTemplate }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview('workspace-optimizer')).rejects.toThrow(
      'Persisted optimizer handoff review cache is missing replay optimizer objective',
    )
  })

  it('fails closed before creating optimizer handoff workspaces when replay identity mismatches', async () => {
    const persisted = new Map<string, unknown>()
    const withStoresSpy = vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) persisted.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.createWorkspaceFromPersistedOptimizerHandoff({
      handoffReference: createOptimizerHandoffReference(),
      validation: createOptimizerHandoffValidationResponse(),
      replay: { ...createOptimizerHandoffReplayResponse(), handoff_id: 'optimizer_handoff_other' },
      openedAt: '2026-04-24T00:00:00Z',
    })).rejects.toThrow('Persisted optimizer handoff review cache is inconsistent with replay identity')

    expect(withStoresSpy).not.toHaveBeenCalled()
    expect(persisted.size).toBe(0)
  })

  it('normalizes legacy cached optimizer handoff workspaces to handoff-centric review records', async () => {
    const review = {
      workspaceId: 'workspace-optimizer',
      handoffId: 'optimizer_handoff_123',
      artifactId: 'optimizer_artifact_123',
      handoffReference: createOptimizerHandoffReference(),
      openedAt: '2026-04-24T00:00:00Z',
      validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: null },
      replay: createOptimizerHandoffReplayResponse(),
    }
    const writes = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) writes.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })

    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: {
        kind: 'persisted_optimizer_handoff' as const,
        handoffId: 'optimizer_handoff_123',
        artifactId: 'optimizer_artifact_123',
        handoffReference: createOptimizerHandoffReference(),
        openedAt: '2026-04-24T00:00:00Z',
        reviewBasis: {
          basisVersion: 1 as const,
          basisKind: 'persisted_optimizer_handoff_review' as const,
          handoffId: 'optimizer_handoff_123',
          artifactId: 'optimizer_artifact_123',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          benchmarkSymbol: 'SPY',
          baseCurrency: 'USD',
          replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
          baselineWeights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
          candidateWeights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
        },
      },
    } as unknown as PortfolioWorkspace
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'imported_base' as const,
      name: 'Optimizer Handoff Review',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Optimizer Handoff Review', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: {
        basisVersion: 1 as const,
        basisKind: 'persisted_optimizer_handoff_review' as const,
        handoffId: 'optimizer_handoff_123',
        artifactId: 'optimizer_artifact_123',
        handoffReference: createOptimizerHandoffReference(),
        openedAt: '2026-04-24T00:00:00Z',
        benchmarkSymbol: 'SPY',
        baseCurrency: 'USD',
        replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
        baselineWeights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
        candidateWeights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
      },
    } as unknown as PortfolioNode

    const normalized = await portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({ workspace, node, review })

    expect(normalized.workspace.source).toMatchObject({
      kind: 'persisted_optimizer_handoff',
      handoffReference: { handoff_id: 'optimizer_handoff_123', artifact_id: 'optimizer_artifact_123' },
      reviewBasis: {
        basisKind: 'persisted_optimizer_handoff_review',
        handoffReference: { handoff_id: 'optimizer_handoff_123', artifact_id: 'optimizer_artifact_123' },
      },
    })
    expect(normalized.node).toMatchObject({
      kind: 'artifact_review_basis',
      name: 'Artifact Review Basis',
      portfolioSnapshot: null,
      artifactReviewBasis: {
        basisKind: 'persisted_optimizer_handoff_review',
        handoffReference: { handoff_id: 'optimizer_handoff_123', artifact_id: 'optimizer_artifact_123' },
      },
    })
    expect(normalized.review).toMatchObject({
      handoffReference: { handoff_id: 'optimizer_handoff_123', artifact_id: 'optimizer_artifact_123' },
    })
    expect('handoffId' in normalized.workspace.source).toBe(false)
    expect('artifactId' in normalized.workspace.source).toBe(false)
    const normalizedWorkspaceSource = expectPersistedOptimizerHandoffSource(normalized.workspace.source)
    if (normalizedWorkspaceSource.reviewBasis) {
      expect('handoffId' in normalizedWorkspaceSource.reviewBasis).toBe(false)
      expect('artifactId' in normalizedWorkspaceSource.reviewBasis).toBe(false)
    }
    expect(normalized.node.artifactReviewBasis && 'handoffId' in normalized.node.artifactReviewBasis).toBe(false)
    expect(normalized.node.artifactReviewBasis && 'artifactId' in normalized.node.artifactReviewBasis).toBe(false)
    expect(writes.get(`${portfolioDb.workspaceStoreName}:workspace-optimizer`)).toBeTruthy()
    expect(writes.get(`${portfolioDb.portfolioNodeStoreName}:workspace-optimizer`)).toBeTruthy()
  })

  it('repairs missing optimizer handoff reviewBasis but only for documented legacy cache cases', async () => {
    const review = createPersistedOptimizerHandoffWorkspaceReview({
      validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: null },
    })
    const writes = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) writes.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })

    const normalized = await portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
        artifactReviewBasis: null,
      } as unknown as PortfolioNode,
      review,
    })

    expect(normalized.workspace.source).toMatchObject({
      kind: 'persisted_optimizer_handoff',
      reviewBasis: {
        basisKind: 'persisted_optimizer_handoff_review',
        handoffReference: createOptimizerHandoffReference(),
      },
    })
    expect(normalized.node.artifactReviewBasis).toMatchObject({
      basisKind: 'persisted_optimizer_handoff_review',
      handoffReference: createOptimizerHandoffReference(),
    })
    expect(writes.get(`${portfolioDb.workspaceStoreName}:workspace-optimizer`)).toBeTruthy()
    expect(writes.get(`${portfolioDb.portfolioNodeStoreName}:workspace-optimizer`)).toBeTruthy()
  })

  it('fails closed when present optimizer workspace reviewBasis has the wrong basis kind', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          reviewBasis: {
            ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
            basisKind: 'persisted_construction_artifact_review',
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff workspace review basis has unsupported basis kind')
  })

  it('fails closed when present optimizer workspace reviewBasis has the wrong basis version', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          reviewBasis: {
            ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
            basisVersion: 2,
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff workspace review basis has unsupported basis version')
  })

  it('fails closed when present optimizer workspace reviewBasis has an invalid handoff reference', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          reviewBasis: {
            ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
            handoffReference: {
              ...createOptimizerHandoffReference(),
              artifact_id: '',
            },
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff workspace review basis is missing or invalid handoff reference')
  })

  it('fails closed when present optimizer workspace reviewBasis mixes canonical and partial legacy identity fields', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          reviewBasis: {
            ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
            handoffId: 'optimizer_handoff_123',
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff workspace review basis has partial legacy identity fields')
  })

  it('fails closed when present optimizer workspace reviewBasis conflicts with canonical persisted review data', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          reviewBasis: {
            ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
            benchmarkSymbol: 'QQQ',
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff workspace review basis conflicts with canonical persisted review')
  })

  it('fails closed when present optimizer node reviewBasis conflicts with canonical persisted review data', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
        artifactReviewBasis: {
          ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
          candidateWeights: [{ symbol: 'DDD', target_weight: 0.2 }],
        },
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff node review basis conflicts with canonical persisted review')
  })

  it('fails closed when legacy optimizer workspace source identity conflicts with the handoff reference', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffId: 'optimizer_handoff_other',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
        },
      } as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as PortfolioNode,
      review: {
        workspaceId: 'workspace-optimizer',
        handoffReference: createOptimizerHandoffReference(),
        openedAt: '2026-04-24T00:00:00Z',
        validation: createOptimizerHandoffValidationResponse(),
        replay: createOptimizerHandoffReplayResponse(),
      },
    })).rejects.toThrow('Persisted optimizer handoff workspace source has partial legacy identity fields')
  })

  it('persists and overwrites candidate improvement draft annotations by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveCandidateImprovementDraft').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft')
      .mockResolvedValueOnce({
        workspaceId: 'workspace-1',
        draftId: 'draft-1',
        baseNodeId: 'node-1',
        seed: {
          kind: 'etf_replacement_candidate',
          source: 'etf_ranking',
          seededAt: '2026-04-16T00:00:00Z',
          baseSymbol: 'IWDA',
          candidateSymbol: 'IUHC',
          candidateRank: 2,
          peerGroup: 'Sector UCITS ETF',
          benchmarkSymbol: 'SPY',
          lookbackMonths: 6,
          rankingId: 'etf_ranking_engine_v1',
          methodologyId: 'etf_ranking_methodology_v1',
          rankingBasisDate: '2026-04-16',
          confidence: 'high',
          holdingsSupport: 'sample',
          requestUniverse: ['IWDA', 'IUHC'],
          evaluatedUniverse: ['IUHC'],
          warningCount: 0,
          excludedSymbolsCount: 1,
        },
      })

    await portfolioWorkspaceStorage.saveCandidateImprovementDraft({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-15T00:00:00Z',
        baseSymbol: 'VUAA',
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
        requestUniverse: ['VUAA', 'IUFS'],
        evaluatedUniverse: ['IUFS'],
        warningCount: 1,
        excludedSymbolsCount: 0,
      },
    })

    await portfolioWorkspaceStorage.saveCandidateImprovementDraft({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-16T00:00:00Z',
        baseSymbol: 'IWDA',
        candidateSymbol: 'IUHC',
        candidateRank: 2,
        peerGroup: 'Sector UCITS ETF',
        benchmarkSymbol: 'SPY',
        lookbackMonths: 6,
        rankingId: 'etf_ranking_engine_v1',
        methodologyId: 'etf_ranking_methodology_v1',
        rankingBasisDate: '2026-04-16',
        confidence: 'high',
        holdingsSupport: 'sample',
        requestUniverse: ['IWDA', 'IUHC'],
        evaluatedUniverse: ['IUHC'],
        warningCount: 0,
        excludedSymbolsCount: 1,
      },
    })

    expect(saveSpy).toHaveBeenCalledTimes(2)
    expect(await portfolioWorkspaceStorage.getCandidateImprovementDraft('draft-1')).toMatchObject({
      draftId: 'draft-1',
      seed: {
        baseSymbol: 'IWDA',
        candidateSymbol: 'IUHC',
        candidateRank: 2,
        confidence: 'high',
      },
    })
  })

  it('deletes and clears candidate improvement draft annotations separately from portfolio truth', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveCandidateImprovementDraft').mockResolvedValue()
    const deleteSpy = vi.spyOn(portfolioWorkspaceStorage, 'deleteCandidateImprovementDraft').mockResolvedValue()
    const clearSpy = vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(null)

    await portfolioWorkspaceStorage.saveCandidateImprovementDraft({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-15T00:00:00Z',
        baseSymbol: 'VUAA',
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
        requestUniverse: ['VUAA', 'IUFS'],
        evaluatedUniverse: ['IUFS'],
        warningCount: 1,
        excludedSymbolsCount: 0,
      },
    })

    await portfolioWorkspaceStorage.deleteCandidateImprovementDraft('draft-1')
    expect(deleteSpy).toHaveBeenCalledWith('draft-1')
    expect(await portfolioWorkspaceStorage.getCandidateImprovementDraft('draft-1')).toBeNull()

    await portfolioWorkspaceStorage.saveCandidateImprovementDraft({
      workspaceId: 'workspace-1',
      draftId: 'draft-2',
      baseNodeId: 'node-2',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-15T00:00:00Z',
        baseSymbol: 'VUAA',
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
        requestUniverse: ['VUAA', 'IUFS'],
        evaluatedUniverse: ['IUFS'],
        warningCount: 1,
        excludedSymbolsCount: 0,
      },
    })

    await portfolioWorkspaceStorage.clearPortfolioWorkspaceState()
    expect(clearSpy).toHaveBeenCalled()
    expect(saveSpy).toHaveBeenCalledTimes(2)
    expect(await portfolioWorkspaceStorage.getCandidateImprovementDraft('draft-2')).toBeNull()
  })

  it('clears candidate improvement draft annotation when recreating a fresh draft from a node', async () => {
    const getNodeSpy = vi.spyOn(portfolioDb, 'withStore').mockImplementation((storeName) => {
      if (storeName === portfolioDb.portfolioNodeStoreName) {
        return Promise.resolve({
          id: 'node-1',
          workspaceId: 'workspace-1',
          parentId: null,
          kind: 'imported_base',
          name: 'Base Import',
          createdAt: '2026-04-10T00:00:00Z',
          changeSummary: {
            label: 'Base Import',
            changedPositionsCount: 1,
            changedSectorsCount: 1,
            grossExposureDelta: 10000,
            netCapitalDelta: 10000,
          },
          portfolioSnapshot: {
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
          },
        })
      }
      if (storeName === portfolioDb.workingDraftStoreName) {
        return Promise.resolve({
          id: 'draft-1',
          workspaceId: 'workspace-1',
          baseNodeId: 'node-legacy',
          updatedAt: '2026-04-10T00:00:00Z',
          name: 'Working Draft',
          status: 'dirty',
          portfolioSnapshot: {
            snapshotVersion: 1,
            baseCurrency: 'USD',
            importedMeta: {
              importer: 'interactive_brokers',
              statementPeriod: '2025-01-01 - 2025-12-31',
              importedAt: '2026-04-10T00:00:00Z',
              sourceFileNames: ['IB2025.pdf'],
            },
            positions: [{ symbol: 'MSFT', marketValue: 9000, quantity: 9, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
            cashBalances: [{ currency: 'USD', amount: 500 }],
            metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
          },
        })
      }
      return Promise.resolve(undefined)
    })
    const draft = await portfolioWorkspaceStorage.createDraftFromNode({ workspaceId: 'workspace-1', baseNodeId: 'node-1' })

    expect(getNodeSpy).toHaveBeenCalled()
    expect(getNodeSpy.mock.calls.some((call) => call[0] === portfolioDb.candidateImprovementDraftStoreName && call[1] === 'readwrite')).toBe(true)
    expect(draft).toMatchObject({
      id: 'draft-1',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-1',
      status: 'clean',
    })
  })

  it('persists and restores intent-bound seeded ETF replacement ranking artifacts by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue({
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
      warnings: ['warning'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'excluded' }],
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

    await portfolioWorkspaceStorage.saveIntentBoundSeededEtfReplacementRankingDraft({
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
      warnings: ['warning'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'excluded' }],
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

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).toMatchObject({
      draftId: 'draft-1',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
    })
    expect(getSpy).toHaveBeenCalledWith('draft-1')
  })

  it('uses the same canonical seeded ranking contract across save and restore', async () => {
    const persisted = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const store = {
        put(value: unknown) {
          const key = (value as { draftId?: string }).draftId
          if (key) persisted.set(`${storeName}:${key}`, structuredClone(value))
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
        get(key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: persisted.get(`${storeName}:${key}`) }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await portfolioWorkspaceStorage.saveIntentBoundSeededEtfReplacementRankingDraft({
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
      warnings: ['warning'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'excluded' }],
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

    expect(persisted.get(`${portfolioDb.intentBoundSeededEtfReplacementRankingDraftStoreName}:draft-1`)).toEqual({
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
      warnings: ['warning'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'excluded' }],
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

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).resolves.toMatchObject({
      openHandoff: {
        handoff_kind: 'ranking_artifact_open_handoff_v1',
        artifact_kind: 'etf_ranking',
        artifact_id: 'etf_ranking_artifact_sector_1',
        schema_version: 'etf_ranking_artifact_v1',
      },
    })
  })

  it('hydrates only documented seeded ranking legacy omissions at load time', async () => {
    const legacyDraft = {
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
      warnings: ['warning'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'excluded' }],
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: legacyDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).resolves.toMatchObject({
      openHandoff: {
        artifact_id: 'etf_ranking_artifact_sector_1',
        artifact_kind: 'etf_ranking',
        schema_version: 'etf_ranking_artifact_v1',
      },
    })
  })

  it('allows documented legacy seeded ranking cache reads that omit mirrored artifact identity fields', async () => {
    const badDraft = {
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).resolves.toMatchObject({
      openHandoff: {
        artifact_id: 'etf_ranking_artifact_sector_1',
        artifact_kind: 'etf_ranking',
        schema_version: 'etf_ranking_artifact_v1',
      },
    })
  })

  it('fails closed when seeded ranking cache is missing a valid typed open handoff', async () => {
    const badDraft = {
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).rejects.toThrow(
      'Persisted seeded ranking review cache is missing or invalid open handoff',
    )
  })

  it('fails closed when seeded ranking cache has unsupported open handoff kind', async () => {
    const badDraft = {
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
        handoff_kind: 'ranking_artifact_open_handoff_v2',
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).rejects.toThrow(
      'Persisted seeded ranking review cache has unsupported open handoff kind',
    )
  })

  it('fails closed when seeded ranking cache has unsupported open handoff schema version', async () => {
    const badDraft = {
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
        schema_version: 'intent_bound_etf_replacement_ranking_artifact_v1',
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).rejects.toThrow(
      'Persisted seeded ranking review cache has unsupported open handoff schema version',
    )
  })

  it('fails closed when seeded ranking cache has contradictory present legacy mirrored fields', async () => {
    const badDraft = {
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
      artifactId: 'etf_ranking_artifact_sector_1',
      artifactKind: 'intent_bound_etf_replacement_ranking',
      schemaVersion: 'intent_bound_etf_replacement_ranking_artifact_v1',
      openHandoff: {
        handoff_kind: 'ranking_artifact_open_handoff_v1',
        artifact_kind: 'etf_ranking',
        artifact_id: 'etf_ranking_artifact_sector_1',
        schema_version: 'etf_ranking_artifact_v1',
      },
      reviewPayloadKind: 'intent_bound_etf_replacement_ranking_review_payload_v1',
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).rejects.toThrow(
      'Persisted seeded ranking review cache conflicts with open handoff artifact kind',
    )
  })

  it('fails closed when seeded ranking cache carries unsupported consumer handoff state', async () => {
    const badDraft = {
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
      consumerHandoff: {
        handoff_kind: 'intent_bound_etf_replacement_ranking_consumer_handoff_v1',
      },
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).rejects.toThrow(
      'Persisted seeded ranking review cache has unsupported consumer handoff state',
    )
  })

  it('fails closed when saving seeded ranking cache with contradictory present review payload state', async () => {
    const withStoreSpy = vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        put(_value: unknown) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.saveIntentBoundSeededEtfReplacementRankingDraft({
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
    })).resolves.toBeUndefined()

    expect(withStoreSpy).toHaveBeenCalledOnce()
  })

  it('persists hypothetical replay drafts by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveHypotheticalReplacementReplayDraft').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      replay: {
        proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
          investor_economics_status: availableInvestorEconomicsStatus,
          reference_result: null,
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
            investor_economics_status: availableInvestorEconomicsStatus,
            instrument_metadata: [],
            starting_weights: [],
            ending_weights: [],
            metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
            equity_curve: [],
            rebalance_events: [],
            trades: [],
          },
          comparison: null,
          reference_diagnostics: null,
          candidate_diagnostics: null,
          diagnostics_comparison: null,
        },
        warnings: ['Candidate weights are derived from a single-symbol replacement intent and remain hypothetical replay inputs only.'],
      },
    })

    await portfolioWorkspaceStorage.saveHypotheticalReplacementReplayDraft({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      replay: {
        proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
          investor_economics_status: availableInvestorEconomicsStatus,
          reference_result: null,
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
            investor_economics_status: availableInvestorEconomicsStatus,
            instrument_metadata: [],
            starting_weights: [],
            ending_weights: [],
            metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
            equity_curve: [],
            rebalance_events: [],
            trades: [],
          },
          comparison: null,
          reference_diagnostics: null,
          candidate_diagnostics: null,
          diagnostics_comparison: null,
        },
        warnings: ['Candidate weights are derived from a single-symbol replacement intent and remain hypothetical replay inputs only.'],
      },
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getHypotheticalReplacementReplayDraft('draft-1')).toMatchObject({
      draftId: 'draft-1',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
    })
    expect(getSpy).toHaveBeenCalledWith('draft-1')
  })

  it('persists formed candidate artifacts by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveFormedCandidateArtifact').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      formation: {
        formation: { kind: 'single_replacement_candidate_formation', status: 'ok' },
        proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'single_symbol_weight_substitution', cash_treatment: 'excluded_from_candidate_formation_basis', position_scope: 'positive_market_value_positions_only' },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        formation_summary: { incumbent_start_weight: 1, candidate_start_weight: 1, unchanged_positions_count: 0, baseline_positions_count: 1, candidate_positions_count: 1, starting_turnover_pct: 1 },
        truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', candidate_truth_class: 'hypothetical_candidate_input_only', formation_truth_class: 'candidate_formation_derived', note: 'Candidate formation is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed.' },
        warnings: [],
        rejection_reason: null,
      },
    })

    await portfolioWorkspaceStorage.saveFormedCandidateArtifact({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      formation: {
        formation: { kind: 'single_replacement_candidate_formation', status: 'ok' },
        proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'single_symbol_weight_substitution', cash_treatment: 'excluded_from_candidate_formation_basis', position_scope: 'positive_market_value_positions_only' },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        formation_summary: { incumbent_start_weight: 1, candidate_start_weight: 1, unchanged_positions_count: 0, baseline_positions_count: 1, candidate_positions_count: 1, starting_turnover_pct: 1 },
        truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', candidate_truth_class: 'hypothetical_candidate_input_only', formation_truth_class: 'candidate_formation_derived', note: 'Candidate formation is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed.' },
        warnings: [],
        rejection_reason: null,
      },
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getFormedCandidateArtifact('draft-1')).toMatchObject({
      draftId: 'draft-1',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
    })
    expect(getSpy).toHaveBeenCalledWith('draft-1')
  })

  it('persists constructed candidate artifacts by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveConstructedCandidateArtifact').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue({
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
    })

    await portfolioWorkspaceStorage.saveConstructedCandidateArtifact({
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
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getConstructedCandidateArtifact('draft-1')).toMatchObject({
      draftId: 'draft-1',
      replacementIntentBaseSymbol: 'AAPL',
      constructionRuleId: 'same_weight_substitution_v1',
    })
    expect(getSpy).toHaveBeenCalledWith('draft-1')
  })

  it('persists selected construction rule by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveSelectedConstructionRule').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      selectedRuleId: 'fixed_split_50_50_substitution_v2',
    })

    await portfolioWorkspaceStorage.saveSelectedConstructionRule({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      selectedRuleId: 'fixed_split_50_50_substitution_v2',
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getSelectedConstructionRule('draft-1')).toMatchObject({
      draftId: 'draft-1',
      selectedRuleId: 'fixed_split_50_50_substitution_v2',
    })
    expect(getSpy).toHaveBeenCalledWith('draft-1')
  })

  it('persists proposal artifacts by workspace id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveProposalArtifact').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([
      {
        id: 'proposal-1',
        kind: 'single_replacement_hypothetical_replay_proposal',
        schemaVersion: 1,
        createdAt: '2026-04-16T00:00:00Z',
        workspaceId: 'workspace-1',
        sourceDraftId: 'draft-1',
        sourceBaseNodeId: 'node-1',
        proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
        versionNumber: 1,
        savedFrom: 'desktop_hypothetical_replay_review',
        reviewStatus: 'recorded',
        sourceIntent: {
          kind: 'etf_replacement_intent',
          source: 'candidate_seed',
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
          confidence: 'medium',
          holdingsSupport: 'mixed',
          warningCount: 1,
        },
        replayBasis: {
          benchmarkSymbol: 'SPY',
          startDate: '2024-01-01',
          endDate: '2024-12-31',
          rebalanceFrequency: 'monthly',
          commissionBps: 0,
          slippageBps: 0,
          derivationBasis: 'draft_snapshot_positions_normalized',
          candidateConstructionRule: 'same_weight_substitution_v1', replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        },
        reviewSnapshot: {
          proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
          derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
          candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
          replay: {
            methodology: 'm',
            investor_economics_status: availableInvestorEconomicsStatus,
            reference_result: null,
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
              investor_economics_status: availableInvestorEconomicsStatus,
              instrument_metadata: [],
              starting_weights: [],
              ending_weights: [],
              metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
              equity_curve: [],
              rebalance_events: [],
              trades: [],
            },
            comparison: null,
            reference_diagnostics: null,
            candidate_diagnostics: null,
            diagnostics_comparison: null,
          },
          warnings: ['Candidate weights are derived from a single-symbol replacement intent and remain hypothetical replay inputs only.'],
        },
      },
    ])

    await portfolioWorkspaceStorage.saveProposalArtifact({
      id: 'proposal-1',
      kind: 'single_replacement_hypothetical_replay_proposal',
      schemaVersion: 1,
      createdAt: '2026-04-16T00:00:00Z',
      workspaceId: 'workspace-1',
      sourceDraftId: 'draft-1',
      sourceBaseNodeId: 'node-1',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      versionNumber: 1,
      savedFrom: 'desktop_hypothetical_replay_review',
      reviewStatus: 'recorded',
      sourceIntent: {
        kind: 'etf_replacement_intent',
        source: 'candidate_seed',
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
        confidence: 'medium',
        holdingsSupport: 'mixed',
        warningCount: 1,
      },
      replayBasis: {
        benchmarkSymbol: 'SPY',
        startDate: '2024-01-01',
        endDate: '2024-12-31',
        rebalanceFrequency: 'monthly',
        commissionBps: 0,
        slippageBps: 0,
        derivationBasis: 'draft_snapshot_positions_normalized',
        candidateConstructionRule: 'same_weight_substitution_v1', replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
      },
      reviewSnapshot: {
        proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
          investor_economics_status: availableInvestorEconomicsStatus,
          reference_result: null,
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
            investor_economics_status: availableInvestorEconomicsStatus,
            instrument_metadata: [],
            starting_weights: [],
            ending_weights: [],
            metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
            equity_curve: [],
            rebalance_events: [],
            trades: [],
          },
          comparison: null,
          reference_diagnostics: null,
          candidate_diagnostics: null,
          diagnostics_comparison: null,
        },
        warnings: ['Candidate weights are derived from a single-symbol replacement intent and remain hypothetical replay inputs only.'],
      },
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getWorkspaceProposalArtifacts('workspace-1')).toMatchObject([{ id: 'proposal-1', versionNumber: 1 }])
    expect(getSpy).toHaveBeenCalledWith('workspace-1')
  })

  it('rejects contradictory proposal artifacts before saving', async () => {
    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactIntegrity({
      id: 'proposal-1',
      kind: 'single_replacement_hypothetical_replay_proposal',
      schemaVersion: 1,
      createdAt: '2026-04-16T00:00:00Z',
      workspaceId: 'workspace-1',
      sourceDraftId: 'draft-1',
      sourceBaseNodeId: 'node-1',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      versionNumber: 1,
      savedFrom: 'desktop_hypothetical_replay_review',
      reviewStatus: 'recorded',
      sourceIntent: {
        kind: 'etf_replacement_intent',
        source: 'candidate_seed',
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
        confidence: 'medium',
        holdingsSupport: 'mixed',
        warningCount: 1,
      },
      replayBasis: {
        benchmarkSymbol: 'SPY',
        startDate: '2024-01-01',
        endDate: '2024-12-31',
        rebalanceFrequency: 'monthly',
        commissionBps: 0,
        slippageBps: 0,
        derivationBasis: 'draft_snapshot_positions_normalized',
        candidateConstructionRule: 'same_weight_substitution_v1',
        replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
      },
      reviewSnapshot: {
        proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'fixed_split_50_50_substitution_v2' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
          investor_economics_status: availableInvestorEconomicsStatus,
          reference_result: null,
          candidate_result: {
            portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 2, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null,
            assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
            status: 'ok', investor_economics_status: availableInvestorEconomicsStatus, instrument_metadata: [], starting_weights: [], ending_weights: [], metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 }, equity_curve: [], rebalance_events: [], trades: [],
          },
          comparison: null,
          reference_diagnostics: null,
          candidate_diagnostics: null,
          diagnostics_comparison: null,
        },
        warnings: [],
      },
    } as any)).toThrow('Saved proposal candidateConstructionRule does not match reviewSnapshot derivation')
  })

  it('fails deterministically when loading contradictory proposal artifacts', async () => {
    const valid = {
      id: 'proposal-1',
      kind: 'single_replacement_hypothetical_replay_proposal',
      schemaVersion: 1,
      createdAt: '2026-04-16T00:00:00Z',
      workspaceId: 'workspace-1',
      sourceDraftId: 'draft-1',
      sourceBaseNodeId: 'node-1',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      versionNumber: 1,
      savedFrom: 'desktop_hypothetical_replay_review',
      reviewStatus: 'recorded',
      sourceIntent: {
        kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1,
      },
      replayBasis: {
        benchmarkSymbol: 'SPY', startDate: '2024-01-01', endDate: '2024-12-31', rebalanceFrequency: 'monthly', commissionBps: 0, slippageBps: 0, derivationBasis: 'draft_snapshot_positions_normalized',
        candidateConstructionRule: 'same_weight_substitution_v1',
        replayProvenance: { candidate_input_source: 'constructed_candidate_payload', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
      },
      reviewSnapshot: {
        proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' },
        replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm', reference_result: null,
          candidate_result: {
            portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 2, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null,
            assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
            status: 'ok', investor_economics_status: availableInvestorEconomicsStatus, instrument_metadata: [], starting_weights: [], ending_weights: [], metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 }, equity_curve: [], rebalance_events: [], trades: [],
          }, comparison: null, reference_diagnostics: null, candidate_diagnostics: null, diagnostics_comparison: null,
        },
        warnings: [],
      },
    }

    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactIntegrity({
      ...valid,
      replayBasis: {
        ...valid.replayBasis,
        replayProvenance: { ...valid.replayBasis.replayProvenance, candidate_input_source: 'constructed_candidate_payload' },
      },
    } as any)).toThrow('Saved proposal replayProvenance candidate_input_source does not match reviewSnapshot replay_provenance')
  })

  it('persists active thesis by workspace id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveActiveThesis').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getActiveThesis').mockResolvedValue({
      workspaceId: 'workspace-1',
      promotedAt: '2026-04-17T00:00:00Z',
      sourceProposalId: 'proposal-1',
      thesisProposal: {
        id: 'proposal-1',
        kind: 'single_replacement_hypothetical_replay_proposal',
        schemaVersion: 1,
        createdAt: '2026-04-16T00:00:00Z',
        workspaceId: 'workspace-1',
        sourceDraftId: 'draft-1',
        sourceBaseNodeId: 'node-1',
        proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
        versionNumber: 1,
        savedFrom: 'desktop_hypothetical_replay_review',
        reviewStatus: 'recorded',
        sourceIntent: {
          kind: 'etf_replacement_intent',
          source: 'candidate_seed',
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
          confidence: 'medium',
          holdingsSupport: 'mixed',
          warningCount: 1,
        },
        replayBasis: {
          benchmarkSymbol: 'SPY',
          startDate: '2024-01-01',
          endDate: '2024-12-31',
          rebalanceFrequency: 'monthly',
          commissionBps: 0,
          slippageBps: 0,
          derivationBasis: 'draft_snapshot_positions_normalized',
          candidateConstructionRule: 'same_weight_substitution_v1', replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        },
        reviewSnapshot: {
          proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
          derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
          candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
          investor_economics_status: availableInvestorEconomicsStatus,
          reference_result: null,
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
              investor_economics_status: availableInvestorEconomicsStatus,
              instrument_metadata: [],
              starting_weights: [],
              ending_weights: [],
              metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
              equity_curve: [],
              rebalance_events: [],
              trades: [],
            },
            comparison: null,
            reference_diagnostics: null,
            candidate_diagnostics: null,
            diagnostics_comparison: null,
          },
          warnings: [],
        },
      },
    })

    await portfolioWorkspaceStorage.saveActiveThesis({
      workspaceId: 'workspace-1',
      promotedAt: '2026-04-17T00:00:00Z',
      sourceProposalId: 'proposal-1',
      thesisProposal: {
        id: 'proposal-1',
        kind: 'single_replacement_hypothetical_replay_proposal',
        schemaVersion: 1,
        createdAt: '2026-04-16T00:00:00Z',
        workspaceId: 'workspace-1',
        sourceDraftId: 'draft-1',
        sourceBaseNodeId: 'node-1',
        proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
        versionNumber: 1,
        savedFrom: 'desktop_hypothetical_replay_review',
        reviewStatus: 'recorded',
        sourceIntent: {
          kind: 'etf_replacement_intent',
          source: 'candidate_seed',
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
          confidence: 'medium',
          holdingsSupport: 'mixed',
          warningCount: 1,
        },
        replayBasis: {
          benchmarkSymbol: 'SPY',
          startDate: '2024-01-01',
          endDate: '2024-12-31',
          rebalanceFrequency: 'monthly',
          commissionBps: 0,
          slippageBps: 0,
          derivationBasis: 'draft_snapshot_positions_normalized',
          candidateConstructionRule: 'same_weight_substitution_v1', replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        },
        reviewSnapshot: {
          proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
          derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
          candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
          replay: {
            methodology: 'm',
            investor_economics_status: availableInvestorEconomicsStatus,
            reference_result: null,
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
              investor_economics_status: availableInvestorEconomicsStatus,
              instrument_metadata: [],
              starting_weights: [],
              ending_weights: [],
              metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
              equity_curve: [],
              rebalance_events: [],
              trades: [],
            },
            comparison: null,
            reference_diagnostics: null,
            candidate_diagnostics: null,
            diagnostics_comparison: null,
          },
          warnings: [],
        },
      },
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getActiveThesis('workspace-1')).toMatchObject({ workspaceId: 'workspace-1', sourceProposalId: 'proposal-1' })
    expect(getSpy).toHaveBeenCalledWith('workspace-1')
  })

  it('rejects contradictory active thesis artifacts before saving', async () => {
    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactIntegrity({
        id: 'proposal-1',
        kind: 'single_replacement_hypothetical_replay_proposal',
        schemaVersion: 1,
        createdAt: '2026-04-16T00:00:00Z',
        workspaceId: 'workspace-1',
        sourceDraftId: 'draft-1',
        sourceBaseNodeId: 'node-1',
        proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
        versionNumber: 1,
        savedFrom: 'desktop_hypothetical_replay_review',
        reviewStatus: 'recorded',
        sourceIntent: {
          kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1,
        },
        replayBasis: {
          benchmarkSymbol: 'SPY', startDate: '2024-01-01', endDate: '2024-12-31', rebalanceFrequency: 'monthly', commissionBps: 0, slippageBps: 0, derivationBasis: 'draft_snapshot_positions_normalized',
          candidateConstructionRule: 'same_weight_substitution_v1',
          replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: true, validation_status: null, constraint_set_id: null } },
        },
        reviewSnapshot: {
          proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
          derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' },
          replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
          replay: {
            methodology: 'm', investor_economics_status: availableInvestorEconomicsStatus, reference_result: null,
            candidate_result: {
              portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 2, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null,
              assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
              status: 'ok', investor_economics_status: availableInvestorEconomicsStatus, instrument_metadata: [], starting_weights: [], ending_weights: [], metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 }, equity_curve: [], rebalance_events: [], trades: [],
            }, comparison: null, reference_diagnostics: null, candidate_diagnostics: null, diagnostics_comparison: null,
        },
        warnings: [],
      },
    } as any)).toThrow('Saved proposal replayProvenance constraint_validation.supplied does not match reviewSnapshot replay_provenance')
  })

  it('fails deterministically when loading contradictory active thesis artifacts', async () => {
    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactIntegrity({
      id: 'proposal-1',
      kind: 'single_replacement_hypothetical_replay_proposal',
      schemaVersion: 1,
      createdAt: '2026-04-16T00:00:00Z',
      workspaceId: 'workspace-1',
      sourceDraftId: 'draft-1',
      sourceBaseNodeId: 'node-1',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      versionNumber: 1,
      savedFrom: 'desktop_hypothetical_replay_review',
      reviewStatus: 'recorded',
      sourceIntent: {
        kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1,
      },
      replayBasis: {
        benchmarkSymbol: 'SPY', startDate: '2024-01-01', endDate: '2024-12-31', rebalanceFrequency: 'monthly', commissionBps: 0, slippageBps: 0, derivationBasis: 'draft_snapshot_positions_normalized', candidateConstructionRule: 'same_weight_substitution_v1',
        replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'mismatched_methodology', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
      },
      reviewSnapshot: {
        proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' },
        replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm', investor_economics_status: availableInvestorEconomicsStatus, reference_result: null,
          candidate_result: {
            portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 2, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null,
            assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
              status: 'ok', investor_economics_status: availableInvestorEconomicsStatus, instrument_metadata: [], starting_weights: [], ending_weights: [], metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 }, equity_curve: [], rebalance_events: [], trades: [],
          }, comparison: null, reference_diagnostics: null, candidate_diagnostics: null, diagnostics_comparison: null,
        },
        warnings: [],
      },
    } as any)).toThrow('Saved proposal replayProvenance seed_methodology_id does not match reviewSnapshot replay_provenance')
  })
})
