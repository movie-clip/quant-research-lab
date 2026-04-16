import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PortfolioImprovementWorkspaceShell } from './PortfolioImprovementWorkspaceShell'

const analysis = {
  snapshot: { statement: { importer: 'interactive_brokers', account_id: 'U1', base_currency: 'USD', statement_period: '2025', page_count: 1 }, positions: [{ symbol: 'AAPL', market_value: 60000 }, { symbol: 'MSFT', market_value: 40000 }] },
  overview: { total_market_value: 100000 },
  risk_summary: { benchmark_symbol: 'SPY' },
} as any

const draftSnapshot = {
  snapshotVersion: 1,
  baseCurrency: 'USD',
  importedMeta: { importer: 'interactive_brokers', statementPeriod: '2025', importedAt: '2026-04-10T00:00:00Z', sourceFileNames: ['IB2025.pdf'] },
  positions: [{ symbol: 'AAPL', marketValue: 60000 }, { symbol: 'MSFT', marketValue: 40000 }],
  cashBalances: [],
  metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
} as any

function makeReplay() {
  return {
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
      assumptions: {
        price_basis: 'adjusted_close',
        execution_price_field: 'close',
        execution_lag_days: 1,
        calendar_policy: 'intersection_common_dates',
        fractional_shares: true,
        long_only: true,
        leverage_allowed: false,
        tax_treatment: 'pre_tax',
        investor_base_currency: 'USD',
      },
      status: 'ok',
      instrument_metadata: [],
      starting_weights: [],
      ending_weights: [],
      metrics: {
        total_return_pct: 1,
        annualized_return_pct: 1,
        annualized_volatility_pct: 1,
        downside_volatility_pct: 1,
        max_drawdown_pct: -1,
        sharpe_ratio: 1,
        sortino_ratio: 1,
        benchmark_return_pct: 1,
        excess_return_pct: 0,
        tracking_error_pct: 1,
        information_ratio: 0,
        beta_vs_benchmark: 1,
        correlation_vs_benchmark: 1,
        total_turnover_pct: 0,
        turnover_events_count: 0,
        total_cost_paid: 0,
      },
      equity_curve: [
        { date: '2024-01-02', equity: 100000, cash: 0, gross_exposure: 100000, drawdown_pct: 0 },
        { date: '2024-12-31', equity: 101000, cash: 0, gross_exposure: 101000, drawdown_pct: -1 },
      ],
      rebalance_events: [],
      trades: [],
    },
    comparison: null,
    reference_diagnostics: null,
    candidate_diagnostics: null,
    diagnostics_comparison: null,
  }
}

function makeSavedProposal(versionNumber: number, createdAt: string, candidateSymbol: string) {
  return {
    id: `proposal-${versionNumber}`,
    kind: 'single_replacement_hypothetical_replay_proposal',
    schemaVersion: 1,
    createdAt,
    workspaceId: 'workspace-1',
    sourceDraftId: 'draft-1',
    sourceBaseNodeId: 'node-1',
    proposalFamilyId: `etf_replacement_intent:AAPL:${candidateSymbol}:${createdAt}`,
    versionNumber,
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
      candidateSymbol,
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
      candidateConstructionRule: 'single_symbol_weight_substitution',
    },
    reviewSnapshot: {
      proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: candidateSymbol, draft_id: 'draft-1', base_node_id: 'node-1' },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'single_symbol_weight_substitution' },
      baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }],
      candidate_weights: [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: candidateSymbol, target_weight: 0.6 }],
      replay: makeReplay(),
      warnings: [],
    },
  } as any
}

describe('PortfolioImprovementWorkspaceShell', () => {
  it('shows an explicit decision summary when no candidate exists yet', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
      />,
    )

    expect(screen.getByText('Portfolio Improvement Decision Summary')).toBeTruthy()
    expect(screen.getByText('Not selected')).toBeTruthy()
    expect(screen.getByText('Unavailable')).toBeTruthy()
    expect(screen.getAllByText('No artifact').length).toBeGreaterThan(0)
    expect(screen.getByText('Shell-owned decision summary. This synthesizes current workflow review state only; it does not recommend, approve, or apply any portfolio change.')).toBeTruthy()
  })

  it('shows partial decision summary state when candidate exists but replay has not run', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={{ workspaceId: 'workspace-1', draftId: 'draft-1', baseNodeId: 'node-1', seed: { kind: 'etf_replacement_candidate', source: 'etf_ranking', seededAt: '2026-04-15T00:00:00Z', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', candidateRank: 1, peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, rankingId: 'etf_ranking_engine_v1', methodologyId: 'etf_ranking_methodology_v1', rankingBasisDate: '2026-04-15', confidence: 'medium', holdingsSupport: 'mixed', requestUniverse: ['AAPL', 'IUFS'], evaluatedUniverse: ['IUFS'], warningCount: 1, excludedSymbolsCount: 0 } }}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
      />,
    )

    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getByText('Blocked')).toBeTruthy()
    expect(screen.getByText('Hypothetical replay cannot run until the selected candidate is promoted into an explicit replacement intent.')).toBeTruthy()
  })

  it('renders workflow sections in the approved order', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={{ workspaceId: 'workspace-1', draftId: 'draft-1', baseNodeId: 'node-1', seed: { kind: 'etf_replacement_candidate', source: 'etf_ranking', seededAt: '2026-04-15T00:00:00Z', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', candidateRank: 1, peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, rankingId: 'etf_ranking_engine_v1', methodologyId: 'etf_ranking_methodology_v1', rankingBasisDate: '2026-04-15', confidence: 'medium', holdingsSupport: 'mixed', requestUniverse: ['AAPL', 'IUFS'], evaluatedUniverse: ['IUFS'], warningCount: 1, excludedSymbolsCount: 0 } }}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
      />,
    )

    expect(screen.getAllByText('Workflow Readiness').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Section Status Guidance').length).toBeGreaterThan(0)

    const currentMatches = screen.getAllByText('Current Portfolio')
    const candidateMatches = screen.getAllByText('Candidate Idea')
    const replayMatches = screen.getAllByText('Hypothetical Replay')
    const diagnosticsMatches = screen.getAllByText('Diagnostics Change')
    const proposalMatches = screen.getAllByText('Saved Proposal')

    const current = currentMatches[currentMatches.length - 1] as HTMLElement
    const candidate = candidateMatches[candidateMatches.length - 1] as HTMLElement
    const replay = replayMatches[replayMatches.length - 1] as HTMLElement
    const diagnostics = diagnosticsMatches[diagnosticsMatches.length - 1] as HTMLElement
    const proposal = proposalMatches[proposalMatches.length - 1] as HTMLElement

    expect(current.compareDocumentPosition(candidate) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(candidate.compareDocumentPosition(replay) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(replay.compareDocumentPosition(diagnostics) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(diagnostics.compareDocumentPosition(proposal) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('owns the shell-level replay, diagnostics, and proposal framing', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
      />,
    )

    expect(screen.getAllByText('Hypothetical Replay').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Diagnostics Change').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Saved Proposal').length).toBeGreaterThan(0)
    expect(screen.getAllByText('No saved proposal artifact yet.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Shell-owned workflow guidance. Use this strip to see what is ready now and which section needs attention next.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Read the workflow top-to-bottom. Each section stays shell-owned and describes its current role in the improvement review.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Ready Sections').length).toBeGreaterThan(0)
    expect(screen.getAllByText('blocked').length).toBeGreaterThan(0)
  })

  it('updates readiness guidance when replay and saved proposal state exist', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={savedProposal.sourceIntent}
        allocationBacktestResult={null}
        hypotheticalReplayResult={savedProposal.reviewSnapshot}
        savedProposals={[savedProposal]}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
      />,
    )

    expect(screen.getAllByText('recorded').length).toBeGreaterThan(0)
    expect(screen.getAllByText('An immutable proposal artifact has been recorded for this workflow.').length).toBeGreaterThan(0)
  })

  it('summarizes replay and diagnostics state without presenting a recommendation', () => {
    const replayWithDiagnostics = {
      ...makeReplay(),
      comparison: {
        total_return_diff_pct: 2.5,
        annualized_return_diff_pct: 1.5,
        annualized_volatility_diff_pct: -0.5,
        downside_volatility_diff_pct: -0.4,
        max_drawdown_diff_pct: 0.3,
        sharpe_diff: 0.2,
        sortino_diff: 0.2,
        excess_return_diff_pct: 1.1,
        tracking_error_diff_pct: 0.2,
        information_ratio_diff: 0.1,
        beta_diff: 0,
        correlation_diff: 0,
        total_turnover_diff_pct: 0,
        total_cost_diff: 0,
      },
      diagnostics_comparison: {
        concentration_changes: [],
        top_concentration_change: { key: 'position_hhi', label: 'Position HHI', baseline_value: 0.4, candidate_value: 0.35, delta_value: -0.05, selection_rule: 'largest_absolute_delta', rationale: 'candidate modestly reduces concentration' },
        factor_exposure_changes: [],
        top_factor_exposure_change: null,
        volatility_changes: [],
        top_volatility_change: null,
        risk_contribution_changes: [],
        top_risk_contribution_change: null,
        stress_scenario_changes: [],
        top_stress_scenario_change: null,
      },
    } as any

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        allocationBacktestResult={null}
        hypotheticalReplayResult={{ ...makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').reviewSnapshot, replay: replayWithDiagnostics }}
        savedProposals={[]}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
      />,
    )

    expect(screen.getAllByText('ok').length).toBeGreaterThan(0)
    expect(screen.getByText('Total return delta +2.50% versus baseline under the shared replay window.')).toBeTruthy()
    expect(screen.getAllByText('Position HHI').length).toBeGreaterThan(0)
    expect(screen.getByText('Concentration shows -0.05. candidate modestly reduces concentration')).toBeTruthy()
  })

  it('summarizes recorded proposal state when an artifact exists', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={savedProposal.sourceIntent}
        allocationBacktestResult={null}
        hypotheticalReplayResult={savedProposal.reviewSnapshot}
        savedProposals={[savedProposal]}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
      />,
    )

    expect(screen.getAllByText('Recorded v1').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Latest immutable artifact captures AAPL -> IUFS for review only.').length).toBeGreaterThan(0)
  })

  it('shows newest-first saved proposal index and reopens an older artifact for review only', () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[olderProposal, latestProposal]}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
      />,
    )

    expect(screen.getAllByText('Latest Saved Artifact').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/v2 .* AAPL/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Latest .* Apr/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Saved artifact .* Apr/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Review-only proposal view').length).toBeGreaterThan(0)
    expect(screen.getAllByText('You are reopening an immutable saved artifact for review inside the workspace shell. This does not apply, edit, approve, or otherwise mutate portfolio truth.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('AAPL -> IUIT').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: 'Reopen In Workspace' }))

    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: 'Viewing For Review' }).length).toBeGreaterThan(0)
  })

  it('keeps candidate idea actions inside the shell and promotes to replacement intent', () => {
    const onCreateReplacementIntent = vi.fn()

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={{ workspaceId: 'workspace-1', draftId: 'draft-1', baseNodeId: 'node-1', seed: { kind: 'etf_replacement_candidate', source: 'etf_ranking', seededAt: '2026-04-15T00:00:00Z', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', candidateRank: 1, peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, rankingId: 'etf_ranking_engine_v1', methodologyId: 'etf_ranking_methodology_v1', rankingBasisDate: '2026-04-15', confidence: 'medium', holdingsSupport: 'mixed', requestUniverse: ['AAPL', 'IUFS'], evaluatedUniverse: ['IUFS'], warningCount: 1, excludedSymbolsCount: 0 } }}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        onCreateReplacementIntent={onCreateReplacementIntent}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Promote to Replacement Intent' }))
    fireEvent.click(screen.getByRole('button', { name: 'Create Intent' }))
    expect(onCreateReplacementIntent).toHaveBeenCalledTimes(1)
  })
})
