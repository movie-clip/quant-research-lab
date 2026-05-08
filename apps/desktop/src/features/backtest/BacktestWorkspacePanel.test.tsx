import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { MonitoringResearchHandoff, PortfolioAllocationBacktestResponse } from '../portfolio/types'
import type { MonitorDefinitionAlertReviewSessionState } from '../portfolio/workspaceTypes'
import { BacktestWorkspacePanel } from './BacktestWorkspacePanel'

const authoritativeDraftSnapshot = {
  snapshotVersion: 1,
  importedMeta: {
    importer: 'interactive_brokers',
    statementPeriod: '2025',
    importedAt: '2026-04-10T00:00:00Z',
    sourceFileNames: ['IB2025.pdf'],
  },
  positions: [
    { symbol: 'AAPL', marketValue: 60000 },
    { symbol: 'MSFT', marketValue: 40000 },
  ],
  cashBalances: [],
  metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
} as any

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const replay: PortfolioAllocationBacktestResponse = {
  methodology: 'm',
  investor_economics_status: { status: 'available', reason: null },
  reference_result: null,
  candidate_result: {
    portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 2, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null,
    assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
    status: 'ok', investor_economics_status: { status: 'available', reason: null }, instrument_metadata: [], starting_weights: [], ending_weights: [],
    metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
    equity_curve: [], rebalance_events: [], trades: [],
  },
  comparison: null,
  reference_diagnostics: null,
  candidate_diagnostics: null,
  diagnostics_comparison: null,
}

const handoff: MonitoringResearchHandoff = {
  version: 1,
  source: 'monitoring',
  monitorKey: 'factor-drift',
  monitorTitle: 'Factor Drift',
  researchTarget: 'diagnostics_change',
  contextLabel: 'Market',
  replayContext: 'AAPL -> IUFS',
  monitorDefinitionReview: {
    source: 'definition_scoped_alert_review_entrypoint',
    monitorDefinitionId: 'monitor_definition_abc12345def67890',
  },
}

const monitorDefinitionAlertReviewSession: MonitorDefinitionAlertReviewSessionState = {
  navigation: {
    monitorDefinitionId: 'monitor_definition_abc12345def67890',
    selectedEvent: null,
  },
  timeline: null,
  timelineStatus: 'idle',
  timelineError: null,
  latestObservation: { status: 'idle', row: null, observation: null, error: null },
  alertHistory: { status: 'idle', row: null, entry: null, error: null },
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('BacktestWorkspacePanel', () => {
  it('renders a slim monitoring-origin banner with dismiss action', () => {
    const onDismiss = vi.fn()

    render(
      <BacktestWorkspacePanel
        allocationBacktestResult={replay}
        onAllocationBacktestResult={() => {}}
        analysis={null}
        draftSnapshot={null}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        hypotheticalReplayResult={null}
        workspaceSource={null}
        persistedConstructionArtifactReview={null}
        persistedOptimizerHandoffReview={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={() => {}}
        openedSavedProposalArtifactId={null}
        monitoringResearchHandoff={handoff}
        monitoringResearchHandoffDismissed={false}
        monitorDefinitionAlertReviewSession={monitorDefinitionAlertReviewSession}
        onDismissMonitoringResearchHandoff={onDismiss}
        onReviewInResearch={() => {}}
        onSaveProposal={() => {}}
        onPromoteProposalToThesis={() => {}}
        onClearActiveThesis={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
        onOpenPersistedConstructionArtifactReview={() => {}}
        workspaceId="workspace-1"
        workspaceShellActivationKey={0}
      />,
    )

    expect(screen.getByTestId('monitoring-research-handoff-banner')).toBeTruthy()
    expect(screen.getByText('Monitoring context')).toBeTruthy()
    expect(screen.getByText(/Factor Drift · Diagnostics Change/)).toBeTruthy()
    expect(screen.getByText('Context: Market')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))

    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('frames the route as the portfolio research workspace', () => {
    render(
      <BacktestWorkspacePanel
        allocationBacktestResult={replay}
        onAllocationBacktestResult={() => {}}
        analysis={null}
        draftSnapshot={null}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        hypotheticalReplayResult={null}
        workspaceSource={null}
        persistedConstructionArtifactReview={null}
        persistedOptimizerHandoffReview={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={() => {}}
        openedSavedProposalArtifactId={null}
        monitorDefinitionAlertReviewSession={monitorDefinitionAlertReviewSession}
        onReviewInResearch={() => {}}
        onSaveProposal={() => {}}
        onPromoteProposalToThesis={() => {}}
        onClearActiveThesis={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
        onOpenPersistedConstructionArtifactReview={() => {}}
        workspaceId="workspace-1"
        workspaceShellActivationKey={0}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy()
    expect(screen.queryByText('Portfolio improvement research')).toBeNull()
  })

  it('renders the workspace route and embedded sessions without requiring shell-only wrappers', () => {
    render(
      <BacktestWorkspacePanel
        allocationBacktestResult={replay}
        onAllocationBacktestResult={() => {}}
        analysis={null}
        draftSnapshot={null}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        hypotheticalReplayResult={null}
        workspaceSource={null}
        persistedConstructionArtifactReview={null}
        persistedOptimizerHandoffReview={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={() => {}}
        openedSavedProposalArtifactId={null}
        monitorDefinitionAlertReviewSession={monitorDefinitionAlertReviewSession}
        onReviewInResearch={() => {}}
        onSaveProposal={() => {}}
        onPromoteProposalToThesis={() => {}}
        onClearActiveThesis={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
        onOpenPersistedConstructionArtifactReview={() => {}}
        workspaceId="workspace-1"
        workspaceShellActivationKey={0}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Open Backtest' }))

    expect(screen.getByTestId('workspace-owned-research-session')).toBeTruthy()
  })

  it('shows blocked construction review when embedded ETF ranking policy discovery is unavailable', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return jsonResponse([
          {
            policy_id: 'top_n_equal_weight_v1',
            policy_definition_id: 'construction_policy_definition_top_n_equal_weight_v1',
            name: 'Top N Equal Weight v1',
            description: 'Select eligible top-ranked names and assign equal target weights.',
            family: 'top_n_equal_weight',
            constraints: 'long_only_fully_invested_max_position_turnover',
            inputs: 'ranked_universe_and_current_portfolio',
            determinism: 'deterministic_rank_order',
            ranking_support: 'selection_only',
            full_investment_constraint: 'required',
            long_only_constraint: 'required',
            eligible_ranked_universe_constraint: 'required',
            max_position_weight_constraint: 'required',
            min_position_weight_constraint: 'supported_optional',
            max_turnover_weight_constraint: 'supported_optional',
            max_trade_intent_count_constraint: 'supported_optional',
            ranked_universe_input: 'required',
            current_portfolio_input: 'required',
            launch_top_n: 2,
            selection_rule_ids: ['eligible_only', 'take_top_n'],
            launch_profile: {
              profile_id: 'ranking_artifact_review_handoff_v1',
              profile_kind: 'ranking_artifact_review_handoff',
              policy_status: 'default',
              launch_top_n: 2,
            },
          },
        ])
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] })
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return jsonResponse({
          items: [{
            artifact_kind: 'etf_ranking',
            artifact_id: 'etf_ranking_artifact_sector_1',
            ranking_id: 'etf_ranking_engine_v1',
            methodology_id: 'etf_ranking_methodology_v1',
            as_of_date: '2026-04-15',
            ranking_basis_date: '2026-04-15',
            etf_summary: {
              benchmark_symbol: 'SPY',
              lookback_months: 6,
              effective_peer_group: 'Sector UCITS ETF',
              universe_size: 3,
              evaluated_universe_size: 2,
              confidence: 'medium',
            },
            replacement_summary: null,
          }],
          metadata: { applied_filters: { artifact_kind: 'etf_ranking' } },
        })
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(
      <BacktestWorkspacePanel
        allocationBacktestResult={replay}
        onAllocationBacktestResult={() => {}}
        analysis={null}
        draftSnapshot={authoritativeDraftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        hypotheticalReplayResult={null}
        workspaceSource={null}
        persistedConstructionArtifactReview={null}
        persistedOptimizerHandoffReview={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={() => {}}
        openedSavedProposalArtifactId={null}
        monitorDefinitionAlertReviewSession={monitorDefinitionAlertReviewSession}
        onReviewInResearch={() => {}}
        onSaveProposal={() => {}}
        onPromoteProposalToThesis={() => {}}
        onClearActiveThesis={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
        onOpenPersistedConstructionArtifactReview={() => {}}
        workspaceId="workspace-1"
        workspaceShellActivationKey={0}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Open ETF Ranking' }))

    expect(await screen.findByText('Construction policies are unavailable.')).toBeTruthy()
    expect(screen.getByText('Review In Construction is blocked until authoritative policy discovery succeeds.')).toBeTruthy()
  })

  it('offers workspace-owned entrypoints for deeper research tools', () => {
    render(
      <BacktestWorkspacePanel
        allocationBacktestResult={replay}
        onAllocationBacktestResult={() => {}}
        analysis={null}
        draftSnapshot={null}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        hypotheticalReplayResult={null}
        workspaceSource={null}
        persistedConstructionArtifactReview={null}
        persistedOptimizerHandoffReview={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={() => {}}
        openedSavedProposalArtifactId={null}
        monitorDefinitionAlertReviewSession={monitorDefinitionAlertReviewSession}
        onReviewInResearch={() => {}}
        onSaveProposal={() => {}}
        onPromoteProposalToThesis={() => {}}
        onClearActiveThesis={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
        onOpenPersistedConstructionArtifactReview={() => {}}
        workspaceId="workspace-1"
        workspaceShellActivationKey={0}
      />,
    )

    expect(screen.getAllByTestId('workspace-section-research-tools')).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'Open Backtest' }))

    expect(screen.getByTestId('workspace-owned-research-session')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Back To Workspace' })).toBeTruthy()
    expect(screen.queryByTestId('workspace-section-research-tools')).toBeNull()
  })

  it('opens a requested compatibility-tab research intent inside the active workspace and consumes it', () => {
    const onConsumeRequestedResearchTool = vi.fn()

    render(
      <BacktestWorkspacePanel
        allocationBacktestResult={replay}
        onAllocationBacktestResult={() => {}}
        analysis={null}
        draftSnapshot={null}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        hypotheticalReplayResult={null}
        workspaceSource={null}
        persistedConstructionArtifactReview={null}
        persistedOptimizerHandoffReview={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={() => {}}
        openedSavedProposalArtifactId={null}
        monitorDefinitionAlertReviewSession={monitorDefinitionAlertReviewSession}
        onReviewInResearch={() => {}}
        onSaveProposal={() => {}}
        onPromoteProposalToThesis={() => {}}
        onClearActiveThesis={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
        onOpenPersistedConstructionArtifactReview={() => {}}
        workspaceId="workspace-1"
        requestedResearchTool="strategy_lab"
        onConsumeRequestedResearchTool={onConsumeRequestedResearchTool}
        workspaceShellActivationKey={0}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Embedded Strategy Lab' })).toBeTruthy()
    expect(onConsumeRequestedResearchTool).toHaveBeenCalledTimes(1)
  })

  it('shows requested-tool no-workspace copy without opening a synthetic workspace', () => {
    render(
      <BacktestWorkspacePanel
        allocationBacktestResult={replay}
        onAllocationBacktestResult={() => {}}
        analysis={null}
        draftSnapshot={null}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        hypotheticalReplayResult={null}
        workspaceSource={null}
        persistedConstructionArtifactReview={null}
        persistedOptimizerHandoffReview={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={() => {}}
        openedSavedProposalArtifactId={null}
        monitorDefinitionAlertReviewSession={monitorDefinitionAlertReviewSession}
        onReviewInResearch={() => {}}
        onSaveProposal={() => {}}
        onPromoteProposalToThesis={() => {}}
        onClearActiveThesis={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
        onOpenPersistedConstructionArtifactReview={() => {}}
        requestedResearchTool="backtest"
      />,
    )

    expect(screen.getByTestId('workspace-research-intent-empty-state')).toBeTruthy()
    expect(screen.getByText('No active workspace is open for Backtest.')).toBeTruthy()
    expect(screen.queryByTestId('workspace-owned-research-session')).toBeNull()
  })

  it('persists embedded research session state while moving in and out of workspace-owned tools', () => {
    render(
      <BacktestWorkspacePanel
        allocationBacktestResult={replay}
        onAllocationBacktestResult={() => {}}
        analysis={null}
        draftSnapshot={null}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        hypotheticalReplayResult={null}
        workspaceSource={null}
        persistedConstructionArtifactReview={null}
        persistedOptimizerHandoffReview={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={() => {}}
        openedSavedProposalArtifactId={null}
        monitorDefinitionAlertReviewSession={monitorDefinitionAlertReviewSession}
        onReviewInResearch={() => {}}
        onSaveProposal={() => {}}
        onPromoteProposalToThesis={() => {}}
        onClearActiveThesis={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
        onOpenPersistedConstructionArtifactReview={() => {}}
        workspaceId="workspace-1"
        workspaceShellActivationKey={0}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Open Backtest' }))
    fireEvent.change(screen.getByDisplayValue('ES,NQ,CL'), { target: { value: 'RTY' } })
    fireEvent.click(screen.getByRole('button', { name: 'Back To Workspace' }))

    expect(screen.getByTestId('workspace-section-research-tools')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Open Backtest' }))

    expect(screen.getByDisplayValue('RTY')).toBeTruthy()
  })
})
