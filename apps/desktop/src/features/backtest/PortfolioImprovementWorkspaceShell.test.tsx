import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PortfolioImprovementWorkspaceShell } from './PortfolioImprovementWorkspaceShell'

const noOp = () => {}

function textContentOf(testId: string) {
  const matches = screen.getAllByTestId(testId)
  return matches[matches.length - 1]?.textContent ?? ''
}

function clickCompareFor(proposalId: string) {
  const matches = screen.getAllByTestId(`saved-proposal-compare-${proposalId}`)
  fireEvent.click(matches[matches.length - 1])
}

function latestByTestId(testId: string) {
  const matches = screen.getAllByTestId(testId)
  return matches[matches.length - 1]
}

function textContentOfIn(root: HTMLElement, testId: string) {
  const matches = within(root).getAllByTestId(testId)
  return matches[matches.length - 1]?.textContent ?? ''
}

function clickCompareForIn(root: HTMLElement, proposalId: string) {
  const matches = within(root).getAllByTestId(`saved-proposal-compare-${proposalId}`)
  fireEvent.click(matches[matches.length - 1])
}

function latestByTestIdIn(root: HTMLElement, testId: string) {
  const matches = within(root).getAllByTestId(testId)
  return matches[matches.length - 1]
}

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
      candidateConstructionRule: 'same_weight_substitution_v1',
    },
    reviewSnapshot: {
      proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: candidateSymbol, draft_id: 'draft-1', base_node_id: 'node-1' },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' },
      replay_provenance: {
        candidate_input_source: 'replacement_intent_preview',
        construction_rule_id: 'same_weight_substitution_v1',
        upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' },
        seed_ranking_id: 'etf_ranking_engine_v1',
        seed_methodology_id: 'etf_ranking_methodology_v1',
      },
      baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }],
      candidate_weights: [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: candidateSymbol, target_weight: 0.6 }],
      replay: makeReplay(),
      warnings: [],
    },
  } as any
}

function makeFormedCandidate(status: 'ok' | 'rejected' = 'ok') {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    formation: {
      formation: { kind: 'single_replacement_candidate_formation', status },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'single_symbol_weight_substitution', cash_treatment: 'excluded_from_candidate_formation_basis', position_scope: 'positive_market_value_positions_only' },
      baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }],
      candidate_weights: status === 'ok' ? [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: 'IUFS', target_weight: 0.6 }] : [],
      formation_summary: { incumbent_start_weight: 0.6, candidate_start_weight: status === 'ok' ? 0.6 : null, unchanged_positions_count: status === 'ok' ? 1 : 0, baseline_positions_count: status === 'ok' ? 2 : 0, candidate_positions_count: status === 'ok' ? 2 : 0, starting_turnover_pct: status === 'ok' ? 0.6 : null },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', candidate_truth_class: 'hypothetical_candidate_input_only', formation_truth_class: 'candidate_formation_derived', note: 'Candidate formation is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed.' },
      warnings: [],
      rejection_reason: status === 'rejected' ? 'replacement intent candidate is already held in draft snapshot: IUFS' : null,
    },
  } as any
}

function makeConstructedCandidate(status: 'ok' | 'rejected' = 'ok') {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    constructionRuleId: 'same_weight_substitution_v1',
    construction: {
      construction: { kind: 'single_replacement_construction', status, rule_id: 'same_weight_substitution_v1' },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      inputs: { baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }], construction_rule: 'same_weight_substitution_v1', incumbent_start_weight: 0.6 },
      outputs: { candidate_weights: status === 'ok' ? [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: 'IUFS', target_weight: 0.6 }] : [], starting_turnover_pct: status === 'ok' ? 0.6 : null, unchanged_positions_count: status === 'ok' ? 1 : 0 },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', construction_basis: 'explicit_single_replacement_rule', cash_treatment: 'excluded_from_construction_basis', position_scope: 'positive_market_value_positions_only' },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', construction_truth_class: 'candidate_construction_derived', candidate_truth_class: 'hypothetical_candidate_input_only', note: 'Candidate construction is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed and no replay has been run.' },
      warnings: [],
      rejection_reason: status === 'rejected' ? 'replacement intent candidate is already held in draft snapshot: IUFS' : null,
    },
  } as any
}

function makeConstraintValidation(status: 'ok' | 'blocked' | 'rejected' = 'ok') {
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
  } as any
}

function makeActiveThesis(versionNumber = 1, candidateSymbol = 'IUFS') {
  const thesisProposal = makeSavedProposal(versionNumber, '2026-04-17T00:00:00Z', candidateSymbol)
  return {
    workspaceId: 'workspace-1',
    promotedAt: '2026-04-17T12:00:00Z',
    sourceProposalId: thesisProposal.id,
    thesisProposal,
  } as any
}

function renderShell(overrides: Record<string, any> = {}) {
  return render(
    <PortfolioImprovementWorkspaceShell
      analysis={analysis}
      draftSnapshot={draftSnapshot}
      candidateImprovementDraft={null}
      intentBoundSeededEtfReplacementRankingDraft={null}
      replacementIntentDraft={null}
      formedCandidateArtifact={null}
      constructedCandidateArtifact={null}
      constructionConstraintValidationArtifact={null}
      selectedConstructionRuleId="same_weight_substitution_v1"
      allocationBacktestResult={null}
      hypotheticalReplayResult={null}
      savedProposals={[]}
      activeThesis={null}
      onPromoteProposalToThesis={noOp}
      onClearActiveThesis={noOp}
      onSaveProposal={noOp}
      onHypotheticalReplayResult={noOp}
      onFormedCandidateArtifact={noOp}
      onConstructedCandidateArtifact={noOp}
      onConstructionConstraintValidationArtifact={noOp}
      onSelectedConstructionRuleChange={noOp}
      {...overrides}
    />,
  )
}

describe('PortfolioImprovementWorkspaceShell', () => {
  it('shows an explicit decision summary when no candidate exists yet', () => {
    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getByText('Portfolio Improvement Decision Summary')).toBeTruthy()
    expect(screen.getByText('Not selected')).toBeTruthy()
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)
    expect(screen.getAllByText('No artifact').length).toBeGreaterThan(0)
    expect(screen.getByText('Current review state only.')).toBeTruthy()
  })

  it('shows partial decision summary state when candidate exists but replay has not run', () => {
    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={{ workspaceId: 'workspace-1', draftId: 'draft-1', baseNodeId: 'node-1', seed: { kind: 'etf_replacement_candidate', source: 'etf_ranking', seededAt: '2026-04-15T00:00:00Z', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', candidateRank: 1, peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, rankingId: 'etf_ranking_engine_v1', methodologyId: 'etf_ranking_methodology_v1', rankingBasisDate: '2026-04-15', confidence: 'medium', holdingsSupport: 'mixed', requestUniverse: ['AAPL', 'IUFS'], evaluatedUniverse: ['IUFS'], warningCount: 1, excludedSymbolsCount: 0 } }}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)
    expect(screen.getByText('Hypothetical replay cannot run until the selected candidate is promoted into an explicit replacement intent.')).toBeTruthy()
  })

  it('renders workspace sections in the approved order', () => {
    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={{ workspaceId: 'workspace-1', draftId: 'draft-1', baseNodeId: 'node-1', seed: { kind: 'etf_replacement_candidate', source: 'etf_ranking', seededAt: '2026-04-15T00:00:00Z', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', candidateRank: 1, peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, rankingId: 'etf_ranking_engine_v1', methodologyId: 'etf_ranking_methodology_v1', rankingBasisDate: '2026-04-15', confidence: 'medium', holdingsSupport: 'mixed', requestUniverse: ['AAPL', 'IUFS'], evaluatedUniverse: ['IUFS'], warningCount: 1, excludedSymbolsCount: 0 } }}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Overview').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Portfolio Research Workspace').length).toBeGreaterThan(0)
    expect(screen.queryByText('Workflow / Analysis Guide')).toBeNull()
    expect(screen.queryByText('Workflow Readiness')).toBeNull()
    expect(screen.queryByText('Section Status Guidance')).toBeNull()

    const overviewMatches = screen.getAllByText('Overview')
    const currentMatches = screen.getAllByText('Current Portfolio')
    const candidateMatches = screen.getAllByText('Candidate')
    const compareMatches = screen.getAllByText('Compare')
    const proposalMatches = screen.getAllByText('Proposal')

    const overview = overviewMatches[overviewMatches.length - 1] as HTMLElement
    const current = currentMatches[currentMatches.length - 1] as HTMLElement
    const candidate = candidateMatches[candidateMatches.length - 1] as HTMLElement
    const compare = compareMatches[compareMatches.length - 1] as HTMLElement
    const proposal = proposalMatches[proposalMatches.length - 1] as HTMLElement

    expect(overview.compareDocumentPosition(current) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(current.compareDocumentPosition(candidate) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(candidate.compareDocumentPosition(compare) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(compare.compareDocumentPosition(proposal) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('owns the shell-level replay, diagnostics, and proposal framing', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Hypothetical Replay').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Diagnostics Change').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Saved Proposal').length).toBeGreaterThan(0)
    expect(screen.getAllByText('No saved proposal artifact yet.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)
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
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={savedProposal.reviewSnapshot}
        savedProposals={[savedProposal]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Recorded').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Construction Constraints').length).toBeGreaterThan(0)
    expect(screen.getAllByText('An immutable proposal artifact has been recorded for this workflow.').length).toBeGreaterThan(0)
    expect(screen.getByText('Replay lineage: direct preview replay · same-weight substitution')).toBeTruthy()
  })

  it('shows constructed candidate replay lineage with the actual construction rule', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')
    const constructedReplay = {
      ...savedProposal.reviewSnapshot,
      derivation: {
        baseline_basis: 'draft_snapshot_positions_normalized',
        candidate_construction_rule: 'fixed_split_50_50_substitution_v2',
      },
      replay_provenance: {
        candidate_input_source: 'constructed_candidate_payload',
        construction_rule_id: 'fixed_split_50_50_substitution_v2',
        upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' },
        seed_ranking_id: 'etf_ranking_engine_v1',
        seed_methodology_id: 'etf_ranking_methodology_v1',
      },
    }

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={savedProposal.sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={{ ...makeConstructedCandidate(), constructionRuleId: 'fixed_split_50_50_substitution_v2' }}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="fixed_split_50_50_substitution_v2"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={constructedReplay}
        savedProposals={[savedProposal]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getByText('Replay lineage: constructed candidate replay · fixed split 50/50')).toBeTruthy()
  })

  it('renders explicit candidate formation state between candidate idea and replay', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    const candidateMatches = screen.getAllByText('Candidate')
    const formationMatches = screen.getAllByText('Candidate Formation')
    const constructionMatches = screen.getAllByText('Construction Rule')
    const replayMatches = screen.getAllByText('Hypothetical Replay')
    const candidate = candidateMatches[candidateMatches.length - 1] as HTMLElement
    const formation = formationMatches[formationMatches.length - 1] as HTMLElement
    const construction = constructionMatches[constructionMatches.length - 1] as HTMLElement
    const replay = replayMatches[replayMatches.length - 1] as HTMLElement

    expect(candidate.compareDocumentPosition(formation) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(formation.compareDocumentPosition(construction) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(construction.compareDocumentPosition(replay) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getAllByText('Formed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Constructed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Pass').length).toBeGreaterThan(0)
    expect(screen.getAllByText('candidate_formation_derived').length).toBeGreaterThan(0)
    expect(screen.getAllByText('candidate_construction_derived').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Truth provenance: .*constraint_validation_derived/).length).toBeGreaterThan(0)
  })

  it('shows explicit candidate formation rejection state', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate('rejected')}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onSaveProposal={() => {}}
        onPromoteProposalToThesis={() => {}}
        onClearActiveThesis={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Rejected').length).toBeGreaterThan(0)
    expect(screen.getByText('Formation rejected: replacement intent candidate is already held in draft snapshot: IUFS')).toBeTruthy()
    expect(screen.getAllByText('replacement intent candidate is already held in draft snapshot: IUFS').length).toBeGreaterThan(0)
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
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={{ ...makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').reviewSnapshot, replay: replayWithDiagnostics }}
        savedProposals={[]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Formed').length).toBeGreaterThan(0)
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
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={savedProposal.reviewSnapshot}
        savedProposals={[savedProposal]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Recorded v1').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Recorded Apr/).length).toBeGreaterThan(0)
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
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[olderProposal, latestProposal]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Latest Saved Artifact').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/v2 .* AAPL/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Latest .* Apr/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Saved artifact .* Apr/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('AAPL -> IUIT').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: 'Reopen In Workspace' }))

    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: 'Viewing For Review' }).length).toBeGreaterThan(0)
  })

  it('opens a read-only saved proposal comparison for exactly two selected artifacts', () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[olderProposal, latestProposal]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    const ui = within(container)

    clickCompareForIn(container, 'proposal-2')
    expect(textContentOfIn(container, 'saved-proposal-comparison-status')).toContain('Choose one more saved proposal to open the comparison surface.')
    clickCompareForIn(container, 'proposal-1')

    expect(latestByTestIdIn(container, 'saved-proposal-comparison-view')).toBeTruthy()
    expect(ui.getByText('2 of 2 selected')).toBeTruthy()
    expect(ui.getByText('Key Differences')).toBeTruthy()
    expect(ui.getByRole('button', { name: 'Swap sides' })).toBeTruthy()
    expect(ui.getByRole('button', { name: 'Open full proposal v2' })).toBeTruthy()
    expect(ui.getByRole('button', { name: 'Open full proposal v1' })).toBeTruthy()
  })

  it('shows comparison ineligible state when fewer than two saved proposals exist', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={savedProposal.sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={savedProposal.reviewSnapshot}
        savedProposals={[savedProposal]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(textContentOfIn(container, 'saved-proposal-comparison-status')).toContain('Comparison is unavailable until at least two saved proposal artifacts exist.')
    expect(within(container).queryByTestId('saved-proposal-comparison-view')).toBeNull()
  })

  it('swaps sides and opens a full proposal from comparison mode', () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[olderProposal, latestProposal]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    const ui = within(container)

    clickCompareForIn(container, 'proposal-2')
    clickCompareForIn(container, 'proposal-1')
    const comparisonView = latestByTestIdIn(container, 'saved-proposal-comparison-view')
    expect(comparisonView).toBeTruthy()
    expect(within(comparisonView).getAllByText('v2 · AAPL -> IUIT').length).toBeGreaterThan(0)

    fireEvent.click(ui.getByRole('button', { name: 'Swap sides' }))
    expect(within(latestByTestIdIn(container, 'saved-proposal-comparison-view')).getAllByText('v1 · AAPL -> IUFS').length).toBeGreaterThan(0)

    fireEvent.click(ui.getByRole('button', { name: 'Open full proposal v2' }))
    expect(ui.getAllByText('AAPL -> IUIT').length).toBeGreaterThan(0)
    expect(ui.getAllByRole('button', { name: 'Viewing For Review' }).length).toBeGreaterThan(0)
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
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onCreateReplacementIntent={onCreateReplacementIntent}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Promote to Replacement Intent' }))
    fireEvent.click(screen.getByRole('button', { name: 'Create Intent' }))
    expect(onCreateReplacementIntent).toHaveBeenCalledTimes(1)
  })

  it('marks construction stale when the selected rule differs from the saved artifact rule', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="fixed_split_50_50_substitution_v2"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Stale').length).toBeGreaterThan(0)
    expect(screen.getByText('The existing construction artifact was built with same_weight_substitution_v1 and must be rerun for fixed_split_50_50_substitution_v2.')).toBeTruthy()
    expect(screen.getAllByText('fixed_split_50_50_substitution_v2').length).toBeGreaterThan(0)
  })

  it('shows blocked construction constraints before replay can run', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation('blocked')}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Construction Constraints').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)
    expect(screen.getByText('Constraint validation blocked replay with 1 hard-block result.')).toBeTruthy()
    expect(screen.getByText('Hypothetical replay remains unavailable until the current constructed candidate passes construction constraints.')).toBeTruthy()
  })

  it('shortens rejected constraint copy in the decision summary', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation('rejected')}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getByText('Constraint validation rejected replay input: constructed candidate could not be evaluated safely')).toBeTruthy()
  })

  it('shows active thesis state and marks the promoted proposal row', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    const { container } = renderShell({
      savedProposals: [savedProposal],
      activeThesis: makeActiveThesis(1, 'IUFS'),
    })

    const ui = within(container)

    expect(ui.getAllByText('Active Thesis').length).toBeGreaterThan(0)
    expect(ui.getAllByText('v1 · AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(ui.getByTestId('saved-proposal-status-proposal-1').textContent).toContain('active thesis')
    expect(ui.getByTestId('saved-proposal-status-proposal-1').textContent).toContain('active thesis')
  })

  it('promotes and clears the active thesis from saved proposal actions', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')
    const onPromoteProposalToThesis = vi.fn()
    const onClearActiveThesis = vi.fn()

    const { container } = renderShell({
      savedProposals: [savedProposal],
      onPromoteProposalToThesis,
      onClearActiveThesis,
      activeThesis: makeActiveThesis(1, 'IUFS'),
    })

    const ui = within(container)

    const promoteButtons = ui.getAllByTestId('saved-proposal-promote-proposal-1')

    fireEvent.click(promoteButtons[promoteButtons.length - 1] as HTMLElement)
    expect(onPromoteProposalToThesis).toHaveBeenCalledWith('proposal-1')

    fireEvent.click(ui.getByTestId('clear-active-thesis'))
    expect(onClearActiveThesis).toHaveBeenCalledTimes(1)
  })
})
