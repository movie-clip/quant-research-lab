import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { StrategyLabPanel } from './StrategyLabPanel'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('StrategyLabPanel', () => {
  function cloneValue<T>(value: T): T {
    return JSON.parse(JSON.stringify(value)) as T
  }

  const researchRecentPayload = {
    items: [
      {
        artifact_id: 'cross_sectional_research_artifact_abcd1234abcd1234',
        fingerprint: 'a'.repeat(64),
        methodology_id: 'alpha_quality_v1',
        methodology_metadata_v1: {
          methodology_family_id: 'cross_sectional_research_family_v1',
          methodology_family_version: 'v1',
          active_methodology_id: 'alpha_quality_v1',
          active_methodology_version: 'v1',
          alpha_package_version: 'alpha_quality_v1',
          alpha_methodology_id: 'alpha_quality_v1_methodology',
          alpha_input_contract_id: 'alpha_quality_v1_pit_fundamentals_v1',
          score_basis: 'optimizer_alpha_package.final_score',
          benchmark_role: 'descriptive_reference_only',
          partition_rule: 'effective_date_before_holdout_start_else_holdout',
          output_shape: 'compact_summary_only',
          component_signal_ids: ['profitability', 'cash_generation', 'accrual_quality', 'leverage_discipline'],
        },
        status_metadata_v1: {
          artifact_status: 'degraded',
          diagnostics_status: 'invalid',
          coverage_status: 'partial',
        },
        provenance_metadata_v1: {
          input_source_kind: 'replay_snapshot_input',
          replay_provenance_status: 'present',
          benchmark_source_kind: 'request_benchmark_reference',
          alpha_source_kind: 'optimizer_alpha_package',
        },
        dataset_version: 'alpha_quality_dataset_demo_v2',
        universe_definition: 'us_large_cap_demo_v1',
        benchmark_symbol: 'SPY',
        recent_order_persisted_at: '2026-04-25T09:30:00Z',
        recent_order_artifact_id: 'cross_sectional_research_artifact_abcd1234abcd1234',
        rebalance_date: '2024-04-15',
        as_of_date: '2024-04-15',
        holdout_start_date: '2024-01-01',
        universe_size: 3,
        walk_forward_sample_count: 2,
        holdout_sample_count: 1,
      },
    ],
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
      methodology_family_id: null,
      methodology_family_version: null,
      active_methodology_version: null,
      alpha_package_version: null,
      alpha_methodology_id: null,
      alpha_input_contract_id: null,
      score_basis: null,
      benchmark_role: null,
      partition_rule: null,
      output_shape: null,
      artifact_status: null,
      diagnostics_status: null,
      coverage_status: null,
      input_source_kind: null,
      replay_provenance_status: null,
      benchmark_source_kind: null,
      alpha_source_kind: null,
    },
    metadata: {
      contract_version: 'cross_sectional_research_discovery_v1',
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      recent_order_basis: 'persisted_artifact.persisted_at_then_artifact_id',
      supported_filters: ['artifact_kind', 'schema_version', 'methodology_id', 'dataset_version', 'universe_definition', 'benchmark_symbol', 'rebalance_date', 'as_of_date', 'holdout_start_date', 'methodology_family_id', 'methodology_family_version', 'active_methodology_version', 'alpha_package_version', 'alpha_methodology_id', 'alpha_input_contract_id', 'score_basis', 'benchmark_role', 'partition_rule', 'output_shape', 'artifact_status', 'diagnostics_status', 'coverage_status', 'input_source_kind', 'replay_provenance_status', 'benchmark_source_kind', 'alpha_source_kind'],
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
        methodology_family_id: null,
        methodology_family_version: null,
        active_methodology_version: null,
        alpha_package_version: null,
        alpha_methodology_id: null,
        alpha_input_contract_id: null,
        score_basis: null,
        benchmark_role: null,
        partition_rule: null,
        output_shape: null,
        artifact_status: null,
        diagnostics_status: null,
        coverage_status: null,
        input_source_kind: null,
        replay_provenance_status: null,
        benchmark_source_kind: null,
        alpha_source_kind: null,
      },
    },
  }

  const researchReloadPayload = {
    contract_version: 'cross_sectional_research_reload_v1',
    requested_artifact_id: 'cross_sectional_research_artifact_abcd1234abcd1234',
    artifact_id: 'cross_sectional_research_artifact_abcd1234abcd1234',
    artifact_kind: 'cross_sectional_research_run',
    schema_version: 'cross_sectional_research_artifact_v1',
    artifact: {
      schema_version: 'cross_sectional_research_artifact_v1',
      artifact_kind: 'cross_sectional_research_run',
      artifact_id: 'cross_sectional_research_artifact_abcd1234abcd1234',
      fingerprint: 'a'.repeat(64),
      run_id: 'cross_sectional_research_alpha_quality_v1_2024-04-15_SPY',
      persisted_at: '2026-04-25T09:30:00Z',
      methodology_id: 'alpha_quality_v1',
      request: {
        methodology_id: 'alpha_quality_v1',
        rebalance_date: '2024-04-15',
        as_of_date: '2024-04-15',
        holdout_start_date: '2024-01-01',
        dataset_version: 'alpha_quality_dataset_demo_v2',
        universe_definition: 'us_large_cap_demo_v1',
        benchmark: {
          benchmark_symbol: 'SPY',
          benchmark_name: 'SPDR S&P 500 ETF Trust',
          benchmark_kind: 'etf_proxy',
        },
        universe_symbols: ['AAA', 'BBB', 'CCC'],
        fundamental_snapshots: [
          { symbol: 'AAA', statement_date: '2023-12-31', period_type: 'annual', total_revenue: 1000 },
          { symbol: 'BBB', statement_date: '2023-12-31', period_type: 'annual', total_revenue: 950 },
          { symbol: 'CCC', statement_date: '2023-12-31', period_type: 'annual', total_revenue: 700 },
        ],
        source_name: 'research_replay_input',
        replay_id: 'replay-123',
        top_ranked_count: 2,
      },
      methodology: 'Cross-sectional research family v1',
      methodology_metadata_v1: researchRecentPayload.items[0].methodology_metadata_v1,
      status_metadata_v1: researchRecentPayload.items[0].status_metadata_v1,
      provenance_metadata_v1: researchRecentPayload.items[0].provenance_metadata_v1,
      assumptions: ['Outputs are hypothetical research artifacts only.'],
      dataset_version: 'alpha_quality_dataset_demo_v2',
      universe_definition: 'us_large_cap_demo_v1',
      benchmark: {
        benchmark_symbol: 'SPY',
        benchmark_name: 'SPDR S&P 500 ETF Trust',
        benchmark_kind: 'etf_proxy',
      },
      walk_forward_summary: {
        split_label: 'walk_forward',
        sample_count: 2,
        universe_size: 3,
        coverage_ratio: 0.666667,
        complete_coverage_ratio: 0.666667,
        mean_score: 0.44,
        median_score: 0.44,
        positive_score_share: 1,
        top_ranked_symbols: ['AAA', 'BBB'],
        effective_start_date: '2023-12-31',
        effective_end_date: '2023-12-31',
        provenance: {
          alpha_package_id: 'alpha_quality_package_1',
          alpha_package_version: 'alpha_quality_v1',
          alpha_methodology_id: 'alpha_quality_v1_methodology',
          input_digest: 'digest-1',
          source_name: 'research_replay_input',
          as_of_date: '2024-04-15',
          rebalance_date: '2024-04-15',
          holdout_start_date: '2024-01-01',
          benchmark_symbol: 'SPY',
          benchmark_kind: 'etf_proxy',
          partition_rule: 'Rows with effective_date before holdout_start_date belong to walk_forward; rows on or after holdout_start_date belong to holdout.',
        },
      },
      holdout_summary: {
        split_label: 'holdout',
        sample_count: 1,
        universe_size: 3,
        coverage_ratio: 0.333333,
        complete_coverage_ratio: 0.333333,
        mean_score: 0.22,
        median_score: 0.22,
        positive_score_share: 1,
        top_ranked_symbols: ['CCC'],
        effective_start_date: '2024-01-15',
        effective_end_date: '2024-01-15',
        provenance: {
          alpha_package_id: 'alpha_quality_package_1',
          alpha_package_version: 'alpha_quality_v1',
          alpha_methodology_id: 'alpha_quality_v1_methodology',
          input_digest: 'digest-1',
          source_name: 'research_replay_input',
          as_of_date: '2024-04-15',
          rebalance_date: '2024-04-15',
          holdout_start_date: '2024-01-01',
          benchmark_symbol: 'SPY',
          benchmark_kind: 'etf_proxy',
          partition_rule: 'Rows with effective_date before holdout_start_date belong to walk_forward; rows on or after holdout_start_date belong to holdout.',
        },
      },
      provenance: {
        source_name: 'research_replay_input',
        replay_id: 'replay-123',
        input_digest: 'digest-1',
        alpha_input_contract_id: 'alpha_quality_v1_pit_fundamentals_v1',
        point_in_time_only: true,
        alpha_package_id: 'alpha_quality_package_1',
        alpha_package_version: 'alpha_quality_v1',
        alpha_diagnostics_status: 'invalid',
        coverage_ratio: 0.666667,
        complete_coverage_ratio: 0.666667,
        missing_snapshot_symbols: ['CCC'],
        stale_symbols: [],
        lag_blocked_symbols: [],
        fallback_symbols: ['CCC'],
      },
    },
  }

  it('combines ETF universe presets like a mask', () => {
    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByRole('button', { name: /Broad ETF Rotation/i }))
    fireEvent.click(screen.getByText('Growth vs Value'))

    expect(screen.getByDisplayValue('XLK,XLF,XLV,XLE,XLI,QQQ,IWM,SPY')).toBeTruthy()
  })

  it('renders the strategy result after running the ETF rotation prototype', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLK', 'XLF', 'XLV', 'XLE', 'XLI', 'QQQ', 'IWM'],
        start_date: '2020-01-02',
        end_date: '2024-12-02',
        rebalance_frequency: 'monthly',
        lookback_months: 3,
        top_n: 3,
        methodology: 'm',
        investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
        source_status: {
          price_history: 'live',
          leader_internals: 'mixed',
          holdings_snapshot_counts: { XLK: 2 },
          dated_holdings_symbols: ['XLK'],
          sample_fallback_symbols: ['XLF'],
        },
        current_rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [
          { date: '2024-03-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
          { date: '2024-06-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
          { date: '2024-09-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
          { date: '2024-12-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] },
        ],
        etf_internals_history: {
          XLK: [
            { date: '2024-03-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
            { date: '2024-06-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
            { date: '2024-09-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
            { date: '2024-12-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] },
          ],
        },
        observations: [
          { date: '2024-03-02', rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-04-02', rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-06-02', rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-09-02', rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-12-02', rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
        ],
        equity_curve: [{ date: '2024-12-02', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 28.4, average_volume_participation_ratio: 1.12 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Run ETF Rotation Prototype'))

    await waitFor(() => expect(screen.getByText('Leadership Heatmap')).toBeTruthy())
    const payload = JSON.parse(String(fetchSpy.mock.calls[0]?.[1]?.body)) as { lookback_months: number; prefer_live_data?: boolean }
    const heatmap = screen.getByTestId('strategy-heatmap')
    const leaderHeatmap = screen.getByTestId('strategy-leader-heatmap')
    expect(payload.lookback_months).toBe(12)
    expect(payload.prefer_live_data).toBe(true)
    expect(screen.queryByText('Prototype the book-faithful ETF rotation workflow: rank ETFs by trailing momentum, hold the top sleeves equally, and replay multi-year trend leadership for slower-moving investors and big-trend traders.')).toBeNull()
    expect(within(heatmap).getAllByText('Q1 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q2 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q3 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q4 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).queryByText('04/24')).toBeNull()
    expect(screen.queryByText('2024-04-02')).toBeNull()
    expect(screen.getByText('Investor Economics')).toBeTruthy()
    expect(screen.getByText('Withheld')).toBeTruthy()
    expect(screen.getByText('Withheld until Strategy Lab has verified investor total-return equivalence.')).toBeTruthy()
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0)
    expect(screen.getByText('Volume Participation')).toBeTruthy()
    expect(screen.getByText('Price History')).toBeTruthy()
    expect(screen.getAllByText('Leader Internals').length).toBeGreaterThan(0)
    expect(screen.getByText('Live FMP')).toBeTruthy()
    expect(screen.getByText('Mixed live + sample')).toBeTruthy()
    expect(screen.getByText('XLK 2')).toBeTruthy()
    expect(screen.getByText('Sample fallback: XLF')).toBeTruthy()
    expect(screen.getByText('Leader Relative Heatmap')).toBeTruthy()
    expect(within(leaderHeatmap).getAllByText('XLK').length).toBeGreaterThan(0)
    expect(within(leaderHeatmap).getAllByText('0.0').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Leader Internals').length).toBeGreaterThan(0)
    expect(screen.getByText('Constituent Mini Heatmap')).toBeTruthy()
    expect(screen.getByText('Selected ETF history: XLK')).toBeTruthy()
    expect(screen.getByText('Selected ETF history')).toBeTruthy()
    expect(screen.getByText('Actual leaders only')).toBeTruthy()
    expect(screen.queryByText('Top Contributors')).toBeNull()
    expect(screen.queryByText('Lagging Contributors')).toBeNull()
    const constituentHeatmap = screen.getByTestId('strategy-constituent-heatmap')
    expect(screen.getByText('Contribution')).toBeTruthy()
    expect(screen.getByText('Lookback Price Change')).toBeTruthy()
    fireEvent.mouseEnter(screen.getByRole('button', { name: /Q3 2024/i }))
    expect(within(constituentHeatmap).getAllByText('Q3 2024').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).getAllByText('7.9').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/snapshot/i).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByText('Lookback Price Change'))
    expect(within(constituentHeatmap).getAllByText('33.1').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByText('Contribution'))
    expect(within(constituentHeatmap).getAllByText('7.9').length).toBeGreaterThan(0)
    expect(screen.getByText('Show details')).toBeTruthy()
    fireEvent.click(screen.getByText('Show details'))
    expect(screen.getByText('XLK Constituents')).toBeTruthy()
    expect(screen.getByText('Top Contributors')).toBeTruthy()
    expect(screen.getByText('Lagging Contributors')).toBeTruthy()
    expect(screen.getByText('Current Rankings')).toBeTruthy()
    expect(screen.getByText('Rebalance History')).toBeTruthy()
    expect(screen.getByText('Checkpoint investor-performance fields are intentionally withheld until Strategy Lab meets the verified investor total-return equivalence contract.')).toBeTruthy()
    expect(screen.getByText('2024-03-02')).toBeTruthy()
    expect(screen.getByText('2024-06-02')).toBeTruthy()
    expect(screen.getAllByText('XLK').length).toBeGreaterThan(0)
    expect(screen.queryByText('Rotation Equity')).toBeNull()
    expect(screen.queryByText('Rotation Drawdown')).toBeNull()
  })

  it('uses signal lookback as the visible quarterly range', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLK'],
        start_date: '2020-01-02',
        end_date: '2024-12-02',
        rebalance_frequency: 'monthly',
        lookback_months: 12,
        top_n: 1,
        methodology: 'm',
        investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
        source_status: {
          price_history: 'live',
          leader_internals: 'live-dated',
          holdings_snapshot_counts: { XLK: 3 },
          dated_holdings_symbols: ['XLK'],
          sample_fallback_symbols: [],
        },
        current_rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [
          { date: '2023-03-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
          { date: '2023-06-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
          { date: '2023-09-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-09-02', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
          { date: '2023-12-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-12-02', constituents: [{ symbol: 'AVGO', name: 'Broadcom', weight: 0.23, trailing_return_pct: 19.4, weighted_contribution_pct: 4.46 }] },
          { date: '2024-03-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
          { date: '2024-06-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
          { date: '2024-09-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
          { date: '2024-12-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] },
        ],
        etf_internals_history: {
          XLK: [
            { date: '2023-03-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
            { date: '2023-06-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
            { date: '2023-09-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-09-02', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
            { date: '2023-12-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-12-02', constituents: [{ symbol: 'AVGO', name: 'Broadcom', weight: 0.23, trailing_return_pct: 19.4, weighted_contribution_pct: 4.46 }] },
            { date: '2024-03-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
            { date: '2024-06-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
            { date: '2024-09-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
            { date: '2024-12-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] },
          ],
        },
        observations: [
          { date: '2023-03-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2023-06-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2023-09-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2023-12-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-03-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-06-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-09-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-12-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
        ],
        equity_curve: [{ date: '2024-12-02', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 28.4, average_volume_participation_ratio: 1.12 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.change(screen.getByLabelText('Signal Lookback'), { target: { value: '16' } })
    fireEvent.click(screen.getByText('Run ETF Rotation Prototype'))

    await waitFor(() => expect(screen.getByText('Leadership Heatmap')).toBeTruthy())

    const heatmap = screen.getByTestId('strategy-heatmap')
    expect(within(heatmap).getAllByText('Q1 2023').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q2 2023').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q3 2023').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q4 2023').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q1 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q2 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q3 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q4 2024').length).toBeGreaterThan(0)
  })

  it('shows selected ETF constituent history across all visible quarters even when it only leads at the selected checkpoint', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLF', 'XLE', 'XLK', 'XLI'],
        start_date: '2025-03-31',
        end_date: '2026-03-31',
        rebalance_frequency: 'monthly',
        lookback_months: 12,
        top_n: 1,
        methodology: 'm',
        investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
        source_status: { price_history: 'live', leader_internals: 'live-dated', holdings_snapshot_counts: { XLE: 1 }, dated_holdings_symbols: ['XLE'], sample_fallback_symbols: [] },
        current_rankings: [{ symbol: 'XLE', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLE', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [{ date: '2026-03-31', leader_symbol: 'XLE', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'XOM', name: 'Exxon', weight: 0.3, trailing_return_pct: 33.0, weighted_contribution_pct: 9.9 }] }],
        etf_internals_history: {
          XLE: [
            { date: '2025-06-30', etf_symbol: 'XLE', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'XOM', name: 'Exxon', weight: 0.3, trailing_return_pct: 10.0, weighted_contribution_pct: 3.0 }] },
            { date: '2025-09-30', etf_symbol: 'XLE', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'XOM', name: 'Exxon', weight: 0.3, trailing_return_pct: 12.0, weighted_contribution_pct: 3.6 }] },
            { date: '2025-12-31', etf_symbol: 'XLE', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'XOM', name: 'Exxon', weight: 0.3, trailing_return_pct: 18.0, weighted_contribution_pct: 5.4 }] },
            { date: '2026-03-31', etf_symbol: 'XLE', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'XOM', name: 'Exxon', weight: 0.3, trailing_return_pct: 33.0, weighted_contribution_pct: 9.9 }] },
          ],
        },
        observations: [
          { date: '2025-06-30', rankings: [{ symbol: 'XLF', target_weight: 1, score: 0.2, trailing_return_pct: 20, average_volume: 1000000 }, { symbol: 'XLE', target_weight: 0, score: 0.1, trailing_return_pct: 10, average_volume: 1000000 }], holdings: [{ symbol: 'XLF', target_weight: 1, score: 0.2, trailing_return_pct: 20, average_volume: 1000000 }], leader: 'XLF', leader_score: 0.2, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2025-09-30', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.21, trailing_return_pct: 21, average_volume: 1000000 }, { symbol: 'XLE', target_weight: 0, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.21, trailing_return_pct: 21, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.21, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2025-12-31', rankings: [{ symbol: 'XLI', target_weight: 1, score: 0.22, trailing_return_pct: 22, average_volume: 1000000 }, { symbol: 'XLE', target_weight: 0, score: 0.18, trailing_return_pct: 18, average_volume: 1000000 }], holdings: [{ symbol: 'XLI', target_weight: 1, score: 0.22, trailing_return_pct: 22, average_volume: 1000000 }], leader: 'XLI', leader_score: 0.22, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2026-03-31', rankings: [{ symbol: 'XLE', target_weight: 1, score: 0.33, trailing_return_pct: 33, average_volume: 1000000 }, { symbol: 'XLI', target_weight: 0, score: 0.25, trailing_return_pct: 25, average_volume: 1000000 }], holdings: [{ symbol: 'XLE', target_weight: 1, score: 0.33, trailing_return_pct: 33, average_volume: 1000000 }], leader: 'XLE', leader_score: 0.33, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
        ],
        equity_curve: [{ date: '2026-03-31', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 20, average_volume_participation_ratio: 1.1 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Run ETF Rotation Prototype'))
    await waitFor(() => expect(screen.getByText('Leadership Heatmap')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: /Q1 2026/i }))

    const constituentHeatmap = screen.getByTestId('strategy-constituent-heatmap')
    expect(within(constituentHeatmap).getAllByText('XOM').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).getAllByText('3.0').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).getAllByText('3.6').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).getAllByText('5.4').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).getAllByText('9.9').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByText('Actual leaders only'))
    expect(within(constituentHeatmap).queryByText('3.0')).toBeNull()
    expect(within(constituentHeatmap).queryByText('3.6')).toBeNull()
    expect(within(constituentHeatmap).queryByText('5.4')).toBeNull()
    expect(within(constituentHeatmap).getAllByText('9.9').length).toBeGreaterThan(0)
  })

  it('keeps quarterly trailing-return cells aligned with the selected ETF history', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLK', 'XLF', 'XLE', 'XLI'],
        start_date: '2025-03-31',
        end_date: '2025-12-31',
        rebalance_frequency: 'monthly',
        lookback_months: 12,
        top_n: 1,
        methodology: 'm',
        investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
        source_status: { price_history: 'live', leader_internals: 'live-dated', holdings_snapshot_counts: { XLK: 1 }, dated_holdings_symbols: ['XLK'], sample_fallback_symbols: [] },
        current_rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [
          { date: '2025-06-30', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.15, trailing_return_pct: 27.89, weighted_contribution_pct: 4.27 }] },
        ],
        etf_internals_history: {
          XLK: [
            { date: '2025-03-31', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.15, trailing_return_pct: 19.94, weighted_contribution_pct: 3.05 }] },
            { date: '2025-06-30', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.15, trailing_return_pct: 27.89, weighted_contribution_pct: 4.27 }] },
            { date: '2025-09-30', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.15, trailing_return_pct: 53.64, weighted_contribution_pct: 8.21 }] },
            { date: '2025-12-31', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.15, trailing_return_pct: 38.88, weighted_contribution_pct: 5.95 }] },
          ],
        },
        observations: [
          { date: '2025-03-31', rankings: [{ symbol: 'XLF', target_weight: 1, score: 0.2, trailing_return_pct: 20, average_volume: 1000000 }, { symbol: 'XLK', target_weight: 0, score: 0.19, trailing_return_pct: 19, average_volume: 1000000 }], holdings: [{ symbol: 'XLF', target_weight: 1, score: 0.2, trailing_return_pct: 20, average_volume: 1000000 }], leader: 'XLF', leader_score: 0.2, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2025-06-30', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.28, trailing_return_pct: 28, average_volume: 1000000 }, { symbol: 'XLF', target_weight: 0, score: 0.22, trailing_return_pct: 22, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.28, trailing_return_pct: 28, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.28, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2025-09-30', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.54, trailing_return_pct: 54, average_volume: 1000000 }, { symbol: 'XLI', target_weight: 0, score: 0.3, trailing_return_pct: 30, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.54, trailing_return_pct: 54, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.54, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2025-12-31', rankings: [{ symbol: 'XLE', target_weight: 1, score: 0.4, trailing_return_pct: 40, average_volume: 1000000 }, { symbol: 'XLK', target_weight: 0, score: 0.39, trailing_return_pct: 39, average_volume: 1000000 }], holdings: [{ symbol: 'XLE', target_weight: 1, score: 0.4, trailing_return_pct: 40, average_volume: 1000000 }], leader: 'XLE', leader_score: 0.4, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
        ],
        equity_curve: [{ date: '2025-12-31', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 20, average_volume_participation_ratio: 1.1 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Run ETF Rotation Prototype'))
    await waitFor(() => expect(screen.getByText('Leadership Heatmap')).toBeTruthy())

    fireEvent.mouseEnter(screen.getByRole('button', { name: /Q2 2025/i }))
    fireEvent.click(screen.getByText('Lookback Price Change'))

    const constituentHeatmap = screen.getByTestId('strategy-constituent-heatmap')
    expect(within(constituentHeatmap).getAllByText('27.9').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).queryByText('942.1')).toBeNull()
  })

  it('refreshes holdings snapshots and reruns the strategy', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLK'],
        start_date: '2020-01-02',
        end_date: '2024-12-02',
        rebalance_frequency: 'monthly',
        lookback_months: 12,
        top_n: 1,
        methodology: 'm',
        investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
        source_status: { price_history: 'live', leader_internals: 'live-dated', holdings_snapshot_counts: { XLK: 1 }, dated_holdings_symbols: ['XLK'], sample_fallback_symbols: [] },
        current_rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [{ date: '2024-12-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] }],
        etf_internals_history: { XLK: [{ date: '2024-12-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] }] },
        observations: [{ date: '2024-12-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 }],
        equity_curve: [{ date: '2024-12-02', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 28.4, average_volume_participation_ratio: 1.12 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ refreshed: [{ symbol: 'XLK', resolved_symbol: 'XLK', rows: 76, snapshots: 1 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLK'],
        start_date: '2020-01-02',
        end_date: '2024-12-02',
        rebalance_frequency: 'monthly',
        lookback_months: 12,
        top_n: 1,
        methodology: 'm',
        investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
        source_status: { price_history: 'live', leader_internals: 'live-dated', holdings_snapshot_counts: { XLK: 2 }, dated_holdings_symbols: ['XLK'], sample_fallback_symbols: [] },
        current_rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [{ date: '2024-12-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] }],
        etf_internals_history: { XLK: [{ date: '2024-12-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] }] },
        observations: [{ date: '2024-12-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 }],
        equity_curve: [{ date: '2024-12-02', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 28.4, average_volume_participation_ratio: 1.12 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Run ETF Rotation Prototype'))
    await waitFor(() => expect(screen.getByText('Refresh holdings snapshots')).toBeTruthy())
    fireEvent.click(screen.getByText('Refresh holdings snapshots'))

    await waitFor(() => expect(screen.getByText('XLK 2')).toBeTruthy())
    expect(fetchSpy).toHaveBeenCalledTimes(3)
  })

  it('loads persisted research artifacts and renders backend-owned research state without local reinterpretation', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/strategy-lab/cross-sectional-research/recent')) {
        return Promise.resolve(new Response(JSON.stringify(researchRecentPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      if (url.includes('/strategy-lab/cross-sectional-research/artifacts/cross_sectional_research_artifact_abcd1234abcd1234')) {
        return Promise.resolve(new Response(JSON.stringify(researchReloadPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      throw new Error(`Unexpected fetch ${url}`)
    })

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))

    await waitFor(() => expect(screen.getByTestId('research-artifact-list')).toBeTruthy())
    expect(screen.getByText('Degraded')).toBeTruthy()
    expect(screen.getByText('Coverage partial')).toBeTruthy()
    expect(screen.getByText('alpha_quality_dataset_demo_v2')).toBeTruthy()

    fireEvent.click(screen.getByText('Open Artifact'))

    await waitFor(() => expect(screen.getByTestId('research-artifact-detail')).toBeTruthy())
    const detail = screen.getByTestId('research-artifact-detail')
    expect(screen.getByText('Research Status')).toBeTruthy()
    expect(detail.textContent).toContain('Replay provenance present')
    expect(within(detail).getByText('replay_snapshot_input')).toBeTruthy()
    expect(within(detail).getByText('invalid')).toBeTruthy()
    expect(within(detail).getByText('cross_sectional_research_run')).toBeTruthy()
    expect(fetchSpy).toHaveBeenCalledTimes(2)
  })

  it('sends additive backend-owned research metadata filters through the shipped recent contract', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/strategy-lab/cross-sectional-research/recent')) {
        return Promise.resolve(new Response(JSON.stringify(researchRecentPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      throw new Error(`Unexpected fetch ${url}`)
    })

    render(<StrategyLabPanel />)

    fireEvent.change(screen.getByLabelText('Artifact Status'), { target: { value: 'degraded' } })
    fireEvent.change(screen.getByLabelText('Input Source'), { target: { value: 'replay_snapshot_input' } })
    fireEvent.change(screen.getByLabelText('Score Basis'), { target: { value: 'optimizer_alpha_package.final_score' } })
    fireEvent.click(screen.getByText('Load Research Artifacts'))

    await waitFor(() => expect(screen.getByTestId('research-artifact-list')).toBeTruthy())

    const requestUrl = String(fetchSpy.mock.calls[0]?.[0])
    expect(requestUrl).toContain('artifact_status=degraded')
    expect(requestUrl).toContain('input_source_kind=replay_snapshot_input')
    expect(requestUrl).toContain('score_basis=optimizer_alpha_package.final_score')
  })

  it('fails closed on research reload identity mismatch', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/strategy-lab/cross-sectional-research/recent')) {
        return Promise.resolve(new Response(JSON.stringify(researchRecentPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      if (url.includes('/strategy-lab/cross-sectional-research/artifacts/cross_sectional_research_artifact_abcd1234abcd1234')) {
        return Promise.resolve(new Response(JSON.stringify({
          ...researchReloadPayload,
          artifact_id: 'cross_sectional_research_artifact_wrong',
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      throw new Error(`Unexpected fetch ${url}`)
    })

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))
    await waitFor(() => expect(screen.getByTestId('research-artifact-list')).toBeTruthy())

    fireEvent.click(screen.getByText('Open Artifact'))

    await waitFor(() => expect(screen.getByText('Research artifact response identity mismatch')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-detail')).toBeNull()
  })

  it('fails closed on malformed research recent metadata objects', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        ...researchRecentPayload,
        items: [{
          ...researchRecentPayload.items[0],
          recent_order_artifact_id: 'cross_sectional_research_artifact_other',
        }],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))

    await waitFor(() => expect(screen.getByText('Research recent row identity mismatch')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-list')).toBeNull()
  })

  it('fails closed on invalid research recent literal values', async () => {
    const invalidPayload = cloneValue(researchRecentPayload)
    invalidPayload.items[0].status_metadata_v1.artifact_status = 'bad_status'

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(invalidPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))

    await waitFor(() => expect(screen.getByText('cross-sectional research recent response.items[0].status_metadata_v1.artifact_status must be one of: complete, degraded, unknown, unsupported')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-list')).toBeNull()
  })

  it('fails closed on invalid research recent methodology ids', async () => {
    const invalidPayload = cloneValue(researchRecentPayload)
    invalidPayload.items[0].methodology_id = 'alpha_quality_v2'

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(invalidPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))

    await waitFor(() => expect(screen.getByText('cross-sectional research recent response.items[0].methodology_id must be one of: alpha_quality_v1')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-list')).toBeNull()
  })

  it('fails closed on null research recent methodology ids', async () => {
    const invalidPayload = cloneValue(researchRecentPayload) as any
    invalidPayload.items[0].methodology_id = null

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(invalidPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))

    await waitFor(() => expect(screen.getByText('cross-sectional research recent response.items[0].methodology_id must be a string')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-list')).toBeNull()
  })

  it('fails closed on unsupported research metadata semantics values', async () => {
    const invalidPayload = cloneValue(researchRecentPayload)
    invalidPayload.metadata.methodology_metadata_v1_semantics = 'advisory_only'

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(invalidPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))

    await waitFor(() => expect(screen.getByText('cross-sectional research recent response.metadata.methodology_metadata_v1_semantics must be one of: descriptive_only')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-list')).toBeNull()
  })

  it('fails the whole recent parse when one nested row field is invalid', async () => {
    const mixedPayload = cloneValue(researchRecentPayload)
    mixedPayload.items.push({
      ...cloneValue(researchRecentPayload.items[0]),
      artifact_id: 'cross_sectional_research_artifact_ffff1234abcd1234',
      recent_order_artifact_id: 'cross_sectional_research_artifact_ffff1234abcd1234',
      provenance_metadata_v1: {
        ...cloneValue(researchRecentPayload.items[0].provenance_metadata_v1),
        alpha_source_kind: 'bad_alpha_source',
      },
    })

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(mixedPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))

    await waitFor(() => expect(screen.getByText('cross-sectional research recent response.items[1].provenance_metadata_v1.alpha_source_kind must be one of: optimizer_alpha_package, unknown, unsupported')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-list')).toBeNull()
    expect(screen.queryByText('cross_sectional_research_artifact_abcd1234abcd1234')).toBeNull()
  })

  it('fails closed on missing reload metadata fields instead of deriving desktop fallbacks', async () => {
    const invalidReloadPayload = cloneValue(researchReloadPayload) as any
    delete invalidReloadPayload.artifact.status_metadata_v1
    delete invalidReloadPayload.artifact.provenance_metadata_v1

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/strategy-lab/cross-sectional-research/recent')) {
        return Promise.resolve(new Response(JSON.stringify(researchRecentPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      if (url.includes('/strategy-lab/cross-sectional-research/artifacts/cross_sectional_research_artifact_abcd1234abcd1234')) {
        return Promise.resolve(new Response(JSON.stringify(invalidReloadPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      throw new Error(`Unexpected fetch ${url}`)
    })

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))
    await waitFor(() => expect(screen.getByTestId('research-artifact-list')).toBeTruthy())

    fireEvent.click(screen.getByText('Open Artifact'))

    await waitFor(() => expect(screen.getByText('cross-sectional research artifact.status_metadata_v1 must be an object')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-detail')).toBeNull()
  })

  it('renders backend-hydrated legacy reload metadata when the backend supplies canonical fields', async () => {
    const hydratedReloadPayload = cloneValue(researchReloadPayload)
    hydratedReloadPayload.artifact.status_metadata_v1 = {
      artifact_status: 'complete',
      diagnostics_status: 'ok',
      coverage_status: 'complete',
    }
    hydratedReloadPayload.artifact.provenance_metadata_v1 = {
      input_source_kind: 'direct_snapshot_input',
      replay_provenance_status: 'absent',
      benchmark_source_kind: 'request_benchmark_reference',
      alpha_source_kind: 'optimizer_alpha_package',
    }

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/strategy-lab/cross-sectional-research/recent')) {
        return Promise.resolve(new Response(JSON.stringify(researchRecentPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      if (url.includes('/strategy-lab/cross-sectional-research/artifacts/cross_sectional_research_artifact_abcd1234abcd1234')) {
        return Promise.resolve(new Response(JSON.stringify(hydratedReloadPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      throw new Error(`Unexpected fetch ${url}`)
    })

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))
    await waitFor(() => expect(screen.getByTestId('research-artifact-list')).toBeTruthy())

    fireEvent.click(screen.getByText('Open Artifact'))

    await waitFor(() => expect(screen.getByTestId('research-artifact-detail')).toBeTruthy())
    const detail = screen.getByTestId('research-artifact-detail')
    expect(within(detail).getByText('Complete')).toBeTruthy()
    expect(detail.textContent).toContain('Coverage complete')
    expect(detail.textContent).toContain('Replay provenance absent')
    expect(within(detail).getByText('direct_snapshot_input')).toBeTruthy()
    expect(within(detail).getByText('ok')).toBeTruthy()
  })

  it('fails closed on malformed present reload metadata fields', async () => {
    const invalidReloadPayload = cloneValue(researchReloadPayload)
    invalidReloadPayload.artifact.provenance_metadata_v1.replay_provenance_status = 'maybe_present'

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/strategy-lab/cross-sectional-research/recent')) {
        return Promise.resolve(new Response(JSON.stringify(researchRecentPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      if (url.includes('/strategy-lab/cross-sectional-research/artifacts/cross_sectional_research_artifact_abcd1234abcd1234')) {
        return Promise.resolve(new Response(JSON.stringify(invalidReloadPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      throw new Error(`Unexpected fetch ${url}`)
    })

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))
    await waitFor(() => expect(screen.getByTestId('research-artifact-list')).toBeTruthy())

    fireEvent.click(screen.getByText('Open Artifact'))

    await waitFor(() => expect(screen.getByText('cross-sectional research artifact.provenance_metadata_v1.replay_provenance_status must be one of: present, absent, unknown, unsupported')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-detail')).toBeNull()
  })

  it('fails closed on malformed fundamental snapshot entries during reload', async () => {
    const invalidReloadPayload = cloneValue(researchReloadPayload) as any
    invalidReloadPayload.artifact.request.fundamental_snapshots[0] = 'bad-snapshot'

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/strategy-lab/cross-sectional-research/recent')) {
        return Promise.resolve(new Response(JSON.stringify(researchRecentPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      if (url.includes('/strategy-lab/cross-sectional-research/artifacts/cross_sectional_research_artifact_abcd1234abcd1234')) {
        return Promise.resolve(new Response(JSON.stringify(invalidReloadPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      throw new Error(`Unexpected fetch ${url}`)
    })

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))
    await waitFor(() => expect(screen.getByTestId('research-artifact-list')).toBeTruthy())

    fireEvent.click(screen.getByText('Open Artifact'))

    await waitFor(() => expect(screen.getByText('cross-sectional research artifact.request.fundamental_snapshots[0] must be an object')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-detail')).toBeNull()
  })

  it('fails closed on partial fundamental snapshot objects during reload', async () => {
    const invalidReloadPayload = cloneValue(researchReloadPayload) as any
    delete invalidReloadPayload.artifact.request.fundamental_snapshots[0].statement_date

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/strategy-lab/cross-sectional-research/recent')) {
        return Promise.resolve(new Response(JSON.stringify(researchRecentPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      if (url.includes('/strategy-lab/cross-sectional-research/artifacts/cross_sectional_research_artifact_abcd1234abcd1234')) {
        return Promise.resolve(new Response(JSON.stringify(invalidReloadPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      throw new Error(`Unexpected fetch ${url}`)
    })

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))
    await waitFor(() => expect(screen.getByTestId('research-artifact-list')).toBeTruthy())

    fireEvent.click(screen.getByText('Open Artifact'))

    await waitFor(() => expect(screen.getByText('cross-sectional research artifact.request.fundamental_snapshots[0].statement_date must be a string')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-detail')).toBeNull()
  })

  it('fails closed on invalid fundamental snapshot literal values during reload', async () => {
    const invalidReloadPayload = cloneValue(researchReloadPayload)
    invalidReloadPayload.artifact.request.fundamental_snapshots[0].period_type = 'semiannual'

    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      if (url.includes('/strategy-lab/cross-sectional-research/recent')) {
        return Promise.resolve(new Response(JSON.stringify(researchRecentPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      if (url.includes('/strategy-lab/cross-sectional-research/artifacts/cross_sectional_research_artifact_abcd1234abcd1234')) {
        return Promise.resolve(new Response(JSON.stringify(invalidReloadPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      throw new Error(`Unexpected fetch ${url}`)
    })

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Load Research Artifacts'))
    await waitFor(() => expect(screen.getByTestId('research-artifact-list')).toBeTruthy())

    fireEvent.click(screen.getByText('Open Artifact'))

    await waitFor(() => expect(screen.getByText('cross-sectional research artifact.request.fundamental_snapshots[0].period_type must be one of: quarterly, annual')).toBeTruthy())
    expect(screen.queryByTestId('research-artifact-detail')).toBeNull()
  })
})
