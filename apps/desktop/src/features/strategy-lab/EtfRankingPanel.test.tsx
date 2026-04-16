import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { EtfRankingPanel } from './EtfRankingPanel'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('EtfRankingPanel', () => {
  it('renders a stable pre-run empty state', () => {
    render(<EtfRankingPanel />)

    expect(screen.getByText('Compare a current ETF against same-mandate substitutes, rank the eligible options on momentum, path risk, liquidity, and implementation fit, and review whether a stronger replacement candidate exists without turning the tool into a hype screener.')).toBeTruthy()
    expect(screen.getByText('Run a ranking pass to review ETF peer-group results.')).toBeTruthy()
    expect(screen.getByText('This workspace is read-only. It helps you compare same-mandate substitutes before making a separate portfolio decision elsewhere.')).toBeTruthy()
    expect(screen.getByText('What This Tool Does')).toBeTruthy()
    expect(screen.getByText('How To Read It')).toBeTruthy()
    expect(screen.getByText('Before You Run')).toBeTruthy()
    expect(screen.getByText('Benchmark')).toBeTruthy()
    expect(screen.getByText('Lookback (months)')).toBeTruthy()
    expect(screen.getByText('Include the incumbent ETF you currently hold, plus realistic replacement candidates.')).toBeTruthy()
    expect(screen.queryByText('How This Can Improve The Portfolio')).toBeNull()
  })

  it('renders ranking results with peer-group, warnings, and exclusions', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
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
        warnings: {
          confidence: 'medium',
          warnings: ['Implementation-fit support is not complete across the ranked universe.'],
          unknown_metadata_symbols: [],
          peer_group_unclassified_symbols: [],
        },
        request: {
          peer_group: 'Sector UCITS ETF',
          universe: ['IUFS', 'IUHC', 'VDST'],
          benchmark_symbol: 'SPY',
          lookback_months: 6,
        },
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
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} />)

    fireEvent.click(screen.getByText('Run ETF Ranking'))

    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())
    const payload = JSON.parse(String(fetchSpy.mock.calls[0]?.[1]?.body)) as { peer_group: string }
    expect(payload.peer_group).toBe('Sector UCITS ETF')
    const headings = [
      'Replacement Decision',
      'How This Can Improve The Portfolio',
      'Trust Checks',
      'Why #1 Beats #2',
      'Ranked Universe',
      'Excluded Symbols',
      'Portfolio Use Note',
    ].map((text) => screen.getByText(text))
    expect(headings[0].compareDocumentPosition(headings[1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(headings[1].compareDocumentPosition(headings[2]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(headings[2].compareDocumentPosition(headings[3]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(headings[3].compareDocumentPosition(headings[4]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(headings[4].compareDocumentPosition(headings[5]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByText('Top Pick')).toBeTruthy()
    expect(screen.getByText('Runner-Up')).toBeTruthy()
    expect(screen.getByText('Start here to see whether the top-ranked ETF looks like a credible substitute, not an automatic switch.')).toBeTruthy()
    expect(screen.getByText('How This Can Improve The Portfolio')).toBeTruthy()
    expect(screen.getByText('This tool can improve the portfolio by improving the ETF vehicle inside the same mandate. It helps you check whether the current ETF could be replaced by a stronger implementation of the same job, without changing exposure or allocation.')).toBeTruthy()
    expect(screen.getByText('Review confidence, metadata gaps, and warnings before treating the ranking as decision-grade.')).toBeTruthy()
    expect(screen.getByText('Highest-ranked eligible substitute in this run')).toBeTruthy()
    expect(screen.getByText('Second choice to compare before acting')).toBeTruthy()
    expect(screen.getByText('Check trust before considering a switch')).toBeTruthy()
    expect(screen.getByText("Composite score using the engine's effective component weights")).toBeTruthy()
    expect(screen.getByText('Peer Group: Sector UCITS ETF')).toBeTruthy()
    expect(screen.getByText('Confidence: medium')).toBeTruthy()
    expect(screen.getByText('Holdings Support: mixed')).toBeTruthy()
    expect(screen.getAllByText('IUFS').length).toBeGreaterThan(0)
    expect(screen.getAllByText('IUHC').length).toBeGreaterThan(0)
    expect(screen.getAllByText('0.8123').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Seed Candidate Draft').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Carry this ETF into a draft portfolio-improvement review without implying a switch.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Blended').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Lower better').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Implementation').length).toBeGreaterThan(0)
    expect(screen.getByText('Implementation-fit support is not complete across the ranked universe.')).toBeTruthy()
    expect(screen.getByText('VDST')).toBeTruthy()
    expect(screen.getByText('Portfolio Use Note')).toBeTruthy()
    expect(screen.queryByText(/take action/i)).toBeNull()
  })

  it('prefers grouped metadata over legacy top-level metadata when both exist', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        ranking_id: 'etf_ranking_engine_v1',
        title: 'ETF Ranking Engine',
        as_of_date: '2026-04-15',
        benchmark_symbol: 'SPY',
        universe: ['IUFS', 'IUHC', 'VDST'],
        lookback_months: 6,
        price_basis: 'close',
        methodology: 'legacy-methodology',
        effective_peer_group: 'Legacy Peer Group',
        effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 },
        source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' },
        warnings: {
          confidence: 'low',
          warnings: ['Legacy warning'],
          unknown_metadata_symbols: [],
          peer_group_unclassified_symbols: [],
        },
        request: {
          peer_group: 'Grouped Request Peer Group',
          universe: ['IUFS', 'IUHC', 'VDST'],
          benchmark_symbol: 'SPY',
          lookback_months: 6,
        },
        effective_inputs: {
          effective_peer_group: 'Grouped Effective Peer Group',
          effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 },
          requested_universe: ['IUFS', 'IUHC', 'VDST'],
          evaluated_universe: ['IUFS', 'IUHC'],
          excluded_symbols: [{ symbol: 'GROUPED', reason: 'Grouped exclusion reason' }],
        },
        run_metadata: {
          ranking_id: 'etf_ranking_engine_v1',
          methodology_id: 'etf_ranking_methodology_v1',
          methodology: 'grouped-methodology',
          as_of_date: '2026-04-15',
          ranking_basis_date: '2026-04-15',
          price_basis: 'close',
          source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'unavailable' },
          confidence: 'high',
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
        excluded_symbols: [{ symbol: 'LEGACY', reason: 'Legacy exclusion reason' }],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<EtfRankingPanel draftSymbols={['VUAA']} />)

    fireEvent.click(screen.getByText('Run ETF Ranking'))

    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())
    expect(screen.getByText('Peer Group: Grouped Effective Peer Group')).toBeTruthy()
    expect(screen.getByText('Confidence: high')).toBeTruthy()
    expect(screen.getByText('Holdings Support: unavailable')).toBeTruthy()
    expect(screen.getByText('Grouped exclusion reason')).toBeTruthy()
    expect(screen.queryByText('Legacy exclusion reason')).toBeNull()
  })

  it('creates a candidate improvement draft only after explicit incumbent selection', async () => {
    const onSeedCandidateDraft = vi.fn()

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
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
        warnings: {
          confidence: 'medium',
          warnings: ['Implementation-fit support is not complete across the ranked universe.'],
          unknown_metadata_symbols: [],
          peer_group_unclassified_symbols: [],
        },
        request: {
          peer_group: 'Sector UCITS ETF',
          universe: ['IUFS', 'IUHC', 'VDST'],
          benchmark_symbol: 'SPY',
          lookback_months: 6,
        },
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
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} onSeedCandidateDraft={onSeedCandidateDraft} />)

    fireEvent.click(screen.getByText('Run ETF Ranking'))

    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())
    fireEvent.click(screen.getAllByText('Seed Candidate Draft')[0])

    expect(screen.getByText('Create candidate improvement draft')).toBeTruthy()
    expect(screen.getByText('This carries the selected ETF and its ranking context into a draft review. It does not recommend a switch, change allocations, or execute anything.')).toBeTruthy()
    expect(screen.getAllByText('Selected ETF').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Source').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Peer Group').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Benchmark').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Lookback').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Confidence').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Warnings').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Exclusions').length).toBeGreaterThan(0)

    const createDraftButton = screen.getByText('Create Draft') as HTMLButtonElement
    expect(createDraftButton.disabled).toBe(true)
    expect(createDraftButton.className.includes('button-loading')).toBe(false)

    fireEvent.change(screen.getByLabelText('Incumbent ETF'), { target: { value: 'VUAA' } })
    expect(createDraftButton.disabled).toBe(false)
    fireEvent.click(createDraftButton)

    expect(onSeedCandidateDraft).toHaveBeenCalledTimes(1)
    expect(onSeedCandidateDraft.mock.calls[0]?.[0]).toMatchObject({
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
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
        requestUniverse: ['IUFS', 'IUHC', 'VDST'],
        evaluatedUniverse: ['IUFS', 'IUHC'],
        warningCount: 1,
        excludedSymbolsCount: 1,
      },
      rankingArtifact: {
        kind: 'intent_bound_seeded_etf_replacement_ranking',
        source: 'etf_ranking',
        baseSymbol: 'VUAA',
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
      },
    })
    expect(screen.getByText('Candidate draft created. Review it before making any portfolio decision.')).toBeTruthy()
  })

  it('blocks confirm when incumbent equals selected candidate', async () => {
    const onSeedCandidateDraft = vi.fn()

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        ranking_id: 'etf_ranking_engine_v1',
        title: 'ETF Ranking Engine',
        as_of_date: '2026-04-15',
        benchmark_symbol: 'SPY',
        universe: ['IUFS', 'IUHC'],
        lookback_months: 6,
        price_basis: 'close',
        methodology: 'm',
        effective_peer_group: 'Sector UCITS ETF',
        effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 },
        source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' },
        warnings: { confidence: 'medium', warnings: [], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] },
        request: { peer_group: 'Sector UCITS ETF', universe: ['IUFS', 'IUHC'], benchmark_symbol: 'SPY', lookback_months: 6 },
        effective_inputs: { effective_peer_group: 'Sector UCITS ETF', effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 }, requested_universe: ['IUFS', 'IUHC'], evaluated_universe: ['IUFS', 'IUHC'], excluded_symbols: [] },
        run_metadata: { ranking_id: 'etf_ranking_engine_v1', methodology_id: 'etf_ranking_methodology_v1', methodology: 'm', as_of_date: '2026-04-15', ranking_basis_date: '2026-04-15', price_basis: 'close', source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' }, confidence: 'medium' },
        ranked_universe: [{ rank: 1, symbol: 'IUFS', composite_score: 0.8123, instrument: { symbol: 'IUFS', name: 'ETF', asset_class: 'etf', sector: 'Financials', category: 'Sector UCITS ETF', currency: 'USD' }, component_scores: { momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 11.2, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 } } }],
        excluded_symbols: [],
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<EtfRankingPanel draftSymbols={['IUFS']} onSeedCandidateDraft={onSeedCandidateDraft} />)

    fireEvent.click(screen.getByText('Run ETF Ranking'))
    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())
    fireEvent.click(screen.getByText('Seed Candidate Draft'))
    fireEvent.change(screen.getByLabelText('Incumbent ETF'), { target: { value: 'IUFS' } })

    expect(screen.getByText('Incumbent and candidate must be different symbols.')).toBeTruthy()
    expect((screen.getByText('Create Draft') as HTMLButtonElement).disabled).toBe(true)
    expect(onSeedCandidateDraft).not.toHaveBeenCalled()
  })

  it('marks Run ETF Ranking as loading-only while Create Draft stays validation-disabled', async () => {
    let resolveFetch!: (value: Response | PromiseLike<Response>) => void
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise<Response>((resolve) => {
      resolveFetch = resolve
    }))

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} />)

    const runButton = screen.getByText('Run ETF Ranking') as HTMLButtonElement
    fireEvent.click(runButton)

    await waitFor(() => expect((screen.getByText('Running...') as HTMLButtonElement).className.includes('button-loading')).toBe(true))

    resolveFetch(new Response(JSON.stringify({
      ranking_id: 'etf_ranking_engine_v1',
      title: 'ETF Ranking Engine',
      as_of_date: '2026-04-15',
      benchmark_symbol: 'SPY',
      universe: ['IUFS', 'IUHC'],
      lookback_months: 6,
      price_basis: 'close',
      methodology: 'm',
      effective_peer_group: 'Sector UCITS ETF',
      effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 },
      source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' },
      warnings: { confidence: 'medium', warnings: [], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] },
      request: { peer_group: 'Sector UCITS ETF', universe: ['IUFS', 'IUHC'], benchmark_symbol: 'SPY', lookback_months: 6 },
      effective_inputs: { effective_peer_group: 'Sector UCITS ETF', effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 }, requested_universe: ['IUFS', 'IUHC'], evaluated_universe: ['IUFS', 'IUHC'], excluded_symbols: [] },
      run_metadata: { ranking_id: 'etf_ranking_engine_v1', methodology_id: 'etf_ranking_methodology_v1', methodology: 'm', as_of_date: '2026-04-15', ranking_basis_date: '2026-04-15', price_basis: 'close', source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' }, confidence: 'medium' },
      ranked_universe: [{ rank: 1, symbol: 'IUFS', composite_score: 0.8123, instrument: { symbol: 'IUFS', name: 'ETF', asset_class: 'etf', sector: 'Financials', category: 'Sector UCITS ETF', currency: 'USD' }, component_scores: { momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 11.2, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 } } }],
      excluded_symbols: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())
    fireEvent.click(screen.getByText('Seed Candidate Draft'))

    const createDraftButton = screen.getByText('Create Draft') as HTMLButtonElement
    expect(createDraftButton.disabled).toBe(true)
    expect(createDraftButton.className.includes('button-loading')).toBe(false)
  })

  it('renders a structured error state when the ranking request fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'lookback_months must be at least 1' }), { status: 400, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<EtfRankingPanel />)

    fireEvent.change(screen.getByLabelText('Lookback (months)'), { target: { value: '0' } })
    fireEvent.click(screen.getByText('Run ETF Ranking'))

    await waitFor(() => expect(screen.getByText('ETF ranking failed.')).toBeTruthy())
    expect(screen.getByText('The request did not return a usable ranking payload.')).toBeTruthy()
    expect(screen.getByText('lookback_months must be at least 1')).toBeTruthy()
  })
})
