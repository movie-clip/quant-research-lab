import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { MonitoringResearchHandoff, PortfolioAllocationBacktestResponse } from '../portfolio/types'
import { BacktestWorkspacePanel } from './BacktestWorkspacePanel'

const replay: PortfolioAllocationBacktestResponse = {
  methodology: 'm',
  reference_result: null,
  candidate_result: {
    portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 2, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null,
    assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
    status: 'ok', instrument_metadata: [], starting_weights: [], ending_weights: [],
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
}

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
        savedProposals={[]}
        activeThesis={null}
        monitoringResearchHandoff={handoff}
        monitoringResearchHandoffDismissed={false}
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
        savedProposals={[]}
        activeThesis={null}
        onReviewInResearch={() => {}}
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

    expect(screen.getAllByText('Portfolio Research Workspace').length).toBeGreaterThan(0)
    expect(screen.queryByText('Portfolio improvement research')).toBeNull()
  })
})
