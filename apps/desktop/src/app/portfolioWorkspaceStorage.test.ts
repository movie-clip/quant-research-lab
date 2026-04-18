import { describe, expect, it, vi } from 'vitest'

import { createImportedBootstrapResponseFixture } from '../test/portfolioFixtures'
import * as portfolioDb from './portfolioDb'
import * as portfolioWorkspaceStorage from './portfolioWorkspaceStorage'
import { buildPersistedImportedSource } from './portfolioWorkspaceStorage'
import type { ImportedHistoryContext, PortfolioWorkspace } from '../features/portfolio/workspaceTypes'

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

    expect(cleanWorkspace.source.historySource.kind).toBe('imported_replay')
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
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1' },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
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
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1' },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
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
          candidateConstructionRule: 'same_weight_substitution_v1',
        },
        reviewSnapshot: {
          proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
          derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1' },
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
          candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
          replay: {
            methodology: 'm',
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
        candidateConstructionRule: 'same_weight_substitution_v1',
      },
      reviewSnapshot: {
        proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1' },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
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
          candidateConstructionRule: 'same_weight_substitution_v1',
        },
        reviewSnapshot: {
          proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
          derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1' },
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
          candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
          replay: {
            methodology: 'm',
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
          candidateConstructionRule: 'same_weight_substitution_v1',
        },
        reviewSnapshot: {
          proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
          derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1' },
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
          candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
          replay: {
            methodology: 'm',
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
})
