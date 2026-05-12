import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { EtfRankingPanel } from './EtfRankingPanel'

const authoritativeCurrentPortfolio = {
  artifact_id: 'workspace_current_portfolio_1',
  as_of_timestamp: '2026-04-10T00:00:00Z',
  weights: [
    { symbol: 'VUAA', weight: 0.6 },
    { symbol: 'IWDA', weight: 0.4 },
  ],
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

type RankingArtifactFixture = ReturnType<typeof buildRankingArtifact>
type RankingArtifactPreflightFixture = ReturnType<typeof buildPreflightResponse>
type RankingArtifactOpenFixture = ReturnType<typeof buildOpenResponse>

function buildConstructionPoliciesResponse(policyIds: string[] = ['top_n_equal_weight_v1', 'top_n_inverse_rank_weight_v1', 'top_n_linear_rank_weight_v1']) {
  const catalog = {
    top_n_equal_weight_v1: {
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
    top_n_inverse_rank_weight_v1: {
      policy_id: 'top_n_inverse_rank_weight_v1',
      policy_definition_id: 'construction_policy_definition_top_n_inverse_rank_weight_v1',
      name: 'Top N Inverse Rank Weight v1',
      description: 'Select eligible top-ranked names and weight them by inverse selected-order rank.',
      family: 'top_n_rank_weighted',
      constraints: 'long_only_fully_invested_max_position_turnover',
      inputs: 'ranked_universe_and_current_portfolio',
      determinism: 'deterministic_rank_order',
      ranking_support: 'inverse_selected_order_weighting',
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
        policy_status: 'excluded',
        launch_top_n: 2,
      },
    },
    top_n_linear_rank_weight_v1: {
      policy_id: 'top_n_linear_rank_weight_v1',
      policy_definition_id: 'construction_policy_definition_top_n_linear_rank_weight_v1',
      name: 'Top N Linear Rank Weight v1',
      description: 'Select eligible top-ranked names and weight them by selected-order linear rank numerators N..1.',
      family: 'top_n_rank_weighted',
      constraints: 'long_only_fully_invested_max_position_turnover',
      inputs: 'ranked_universe_and_current_portfolio',
      determinism: 'deterministic_rank_order',
      ranking_support: 'linear_selected_order_weighting',
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
        policy_status: 'opt_in',
        launch_top_n: 2,
      },
    },
  } as const

  return policyIds.map((policyId) => catalog[policyId as keyof typeof catalog])
}

function buildGeneralizedRecentResponse(runs: Array<Record<string, unknown>>, appliedFilters: Record<string, unknown> = { artifact_kind: 'etf_ranking' }) {
  return {
    items: runs.map((run) => ({
      artifact_kind: 'etf_ranking',
      schema_version: 'etf_ranking_artifact_v1',
      metadata: {
        metadata_truth: 'authoritative_persisted_metadata',
        metadata_provenance: 'persisted_artifact_body',
        matched_metadata_provenance: 'persisted_artifact_body',
        recency_same_day_provenance: 'etf_recent_index',
      },
      etf_summary: {
        benchmark_symbol: run.benchmark_symbol,
        lookback_months: run.lookback_months,
        effective_peer_group: run.effective_peer_group,
        universe_size: run.universe_size,
        evaluated_universe_size: run.evaluated_universe_size,
        confidence: run.confidence,
      },
      replacement_summary: null,
      ...run,
    })),
    metadata: {
      contract_version: 'ranking_artifact_discovery_v1',
      metadata_truth: 'authoritative_persisted_metadata',
      supported_metadata_provenance: ['persisted_artifact_body', 'persisted_etf_recent_index'],
      supported_artifact_kinds: ['etf_ranking', 'intent_bound_etf_replacement_ranking'],
      artifact_kind_registry_version: 'ranking_artifact_kind_registry_v1',
      supported_filters: ['artifact_kind', 'effective_peer_group'],
      artifact_kind_registry: [],
      applied_filters: appliedFilters,
    },
  }
}

function buildRankingArtifact(overrides: Record<string, unknown> = {}) {
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
    ...overrides,
  }
}

function buildPreflightResponse(artifact: Record<string, unknown>, overrides: Record<string, unknown> = {}) {
  const typedArtifact = artifact as ReturnType<typeof buildRankingArtifact>
  return {
    contract_version: 'ranking_artifact_preflight_v1',
    artifact: {
      artifact_kind: 'etf_ranking',
      artifact_id: typedArtifact.artifact_id,
      schema_version: 'etf_ranking_artifact_v1',
      ranking_id: typedArtifact.ranking_id,
      methodology_id: typedArtifact.run_metadata.methodology_id,
      as_of_date: typedArtifact.run_metadata.as_of_date,
      ranking_basis_date: typedArtifact.run_metadata.ranking_basis_date,
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
      artifact_id: typedArtifact.artifact_id,
      schema_version: 'etf_ranking_artifact_v1',
    },
    ...overrides,
  }
}

function buildOpenResponse(
  artifact: RankingArtifactFixture,
  preflight: RankingArtifactPreflightFixture = buildPreflightResponse(artifact),
  overrides: Record<string, unknown> = {},
) {
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
      schema_version: 'etf_ranking_artifact_v1',
      artifact,
    },
    ...overrides,
  }
}

function installFetchRouter(options: {
  metadata?: { available_effective_peer_groups: string[] }
  constructionPolicies?: Array<Record<string, unknown>>
  recentRuns?: Array<Record<string, unknown>>
  recentArtifact?: RankingArtifactFixture
  recentArtifactPreflight?: RankingArtifactPreflightFixture
  recentArtifactOpen?: RankingArtifactOpenFixture
  runArtifact?: RankingArtifactFixture
  recentMetadataStatus?: number
  constructionPoliciesStatus?: number
  recentRunsStatus?: number
  runStatus?: number
  artifactPreflightStatus?: number
  artifactOpenStatus?: number
  runErrorBody?: unknown
  constructionPoliciesErrorBody?: unknown
  artifactPreflightErrorBody?: unknown
  artifactOpenErrorBody?: unknown
}) {
  const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.includes('/construction/policies')) {
      return jsonResponse(options.constructionPoliciesErrorBody ?? options.constructionPolicies ?? buildConstructionPoliciesResponse(), options.constructionPoliciesStatus ?? 200)
    }
    if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
      return jsonResponse(options.metadata ?? { available_effective_peer_groups: ['Sector UCITS ETF'] }, options.recentMetadataStatus ?? 200)
    }
    if (url.includes('/strategy-lab/ranking-artifacts/recent')) {
      const appliedFilters: Record<string, unknown> = { artifact_kind: 'etf_ranking' }
      const peerGroup = new URL(url, 'https://example.test').searchParams.get('effective_peer_group')
      if (peerGroup) appliedFilters.effective_peer_group = peerGroup
      return jsonResponse(buildGeneralizedRecentResponse(options.recentRuns ?? [], appliedFilters), options.recentRunsStatus ?? 200)
    }
    if (url.includes('/strategy-lab/ranking-artifacts/preflight/')) {
      const artifact = options.recentArtifact ?? buildRankingArtifact()
      return jsonResponse(
        options.artifactPreflightErrorBody ?? options.recentArtifactPreflight ?? buildPreflightResponse(artifact),
        options.artifactPreflightStatus ?? 200,
      )
    }
    if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST') {
      const artifact = options.recentArtifact ?? buildRankingArtifact()
      const preflight = options.recentArtifactPreflight ?? buildPreflightResponse(artifact)
      return jsonResponse(
        options.artifactOpenErrorBody ?? options.recentArtifactOpen ?? buildOpenResponse(artifact, preflight),
        options.artifactOpenStatus ?? 200,
      )
    }
    if (url.endsWith('/strategy-lab/etf-ranking') && (init?.method ?? 'GET') === 'POST') {
      return jsonResponse(options.runErrorBody ?? options.runArtifact ?? buildRankingArtifact(), options.runStatus ?? 200)
    }
    throw new Error(`Unhandled fetch: ${url}`)
  })

  return fetchSpy
}

function buildRecentRun(overrides: Record<string, unknown> = {}) {
  return {
    artifact_id: 'etf_ranking_artifact_sector_1',
    ranking_id: 'etf_ranking_engine_v1',
    methodology_id: 'etf_ranking_methodology_v1',
    as_of_date: '2026-04-15',
    ranking_basis_date: '2026-04-15',
    benchmark_symbol: 'SPY',
    lookback_months: 6,
    universe_size: 3,
    evaluated_universe_size: 2,
    effective_peer_group: 'Sector UCITS ETF',
    confidence: 'medium',
    ...overrides,
  }
}

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('EtfRankingPanel', () => {
  it('renders a stable pre-run empty state', () => {
    installFetchRouter({ recentRuns: [] })

    render(<EtfRankingPanel />)

    expect(screen.getByText('Rank same-mandate ETF substitutes and review whether the current holding has a stronger replacement candidate.')).toBeTruthy()
    expect(screen.getByText('Run a ranking pass to review ETF peer-group results.')).toBeTruthy()
    expect(screen.getByText('Compare same-mandate substitutes before carrying one into a draft review.')).toBeTruthy()
    expect(screen.getByText('Recent Runs')).toBeTruthy()
    expect(screen.getByText('Benchmark')).toBeTruthy()
    expect(screen.getByText('Lookback (months)')).toBeTruthy()
    expect(screen.queryByText('What This Tool Does')).toBeNull()
    expect(screen.queryByText('How To Read It')).toBeNull()
    expect(screen.queryByText('Before You Run')).toBeNull()
    expect(screen.queryByText('Portfolio Fit')).toBeNull()
  })

  it('renders ranking results with peer-group, warnings, and exclusions', async () => {
    const fetchSpy = installFetchRouter({
      recentRuns: [buildRecentRun()],
      runArtifact: buildRankingArtifact(),
    })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} />)

    fireEvent.click(screen.getByText('Run ETF Ranking'))

    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())
    const runCall = fetchSpy.mock.calls.find(([, init]) => String(init?.method) === 'POST')
    const payload = JSON.parse(String(runCall?.[1]?.body)) as { peer_group: string }
    expect(payload.peer_group).toBe('Sector UCITS ETF')
    const headings = [
      'Replacement Decision',
      'Portfolio Fit',
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
    expect(screen.getByText('Portfolio Fit')).toBeTruthy()
    expect(screen.getByText('Use ranking to check whether the same mandate has a stronger ETF implementation.')).toBeTruthy()
    expect(screen.getByText('Review confidence, metadata gaps, and warnings before treating the ranking as decision-grade.')).toBeTruthy()
    expect(screen.getByText('Highest-ranked eligible substitute in this run')).toBeTruthy()
    expect(screen.getByText('Second choice to compare before acting')).toBeTruthy()
    expect(screen.getByText('Check trust before considering a switch')).toBeTruthy()
    expect(screen.getByText("Composite score using the engine's effective component weights")).toBeTruthy()
    expect(screen.getByText('Peer Group: Sector UCITS ETF')).toBeTruthy()
    expect(screen.getByText('Confidence: medium')).toBeTruthy()
    expect(screen.getByText('Holdings Support: mixed')).toBeTruthy()
    expect(screen.getByText('Source: Fresh Run')).toBeTruthy()
    expect(screen.getByText('Artifact: etf_ranking_artifact_sector_1')).toBeTruthy()
    expect(screen.getAllByText('IUFS').length).toBeGreaterThan(0)
    expect(screen.getAllByText('IUHC').length).toBeGreaterThan(0)
    expect(screen.getAllByText('0.8123').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Seed Candidate Draft').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Carry into draft review.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Blended').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Lower better').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Implementation').length).toBeGreaterThan(0)
    expect(screen.getByText('Implementation-fit support is not complete across the ranked universe.')).toBeTruthy()
    expect(screen.getByText('VDST')).toBeTruthy()
    expect(screen.getByText('Portfolio Use Note')).toBeTruthy()
    expect(screen.getByText('Ranking stays review-only until you carry a candidate into a draft.')).toBeTruthy()
    expect(screen.queryByText(/take action/i)).toBeNull()
  })

  it('prefers grouped metadata over request and run metadata paths when both exist', async () => {
    installFetchRouter({
      runArtifact: buildRankingArtifact({
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
      }),
    })

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

    installFetchRouter({ runArtifact: buildRankingArtifact() })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} onSeedCandidateDraft={onSeedCandidateDraft} />)

    fireEvent.click(screen.getByText('Run ETF Ranking'))

    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())
    fireEvent.click(screen.getAllByText('Seed Candidate Draft')[0])

    expect(screen.getByText('Create candidate improvement draft')).toBeTruthy()
    expect(screen.getByText('Carry the selected ETF and ranking context into a draft review.')).toBeTruthy()
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
      },
    })
    expect(screen.getByText('Candidate draft created for review.')).toBeTruthy()
  })

  it('blocks confirm when incumbent equals selected candidate', async () => {
    const onSeedCandidateDraft = vi.fn()

    installFetchRouter({
      runArtifact: buildRankingArtifact({
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
      }),
    })

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
    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return Promise.resolve(jsonResponse(buildConstructionPoliciesResponse()))
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return Promise.resolve(jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] }))
      }
      if (url.includes('/strategy-lab/ranking-artifacts/recent')) {
        return Promise.resolve(jsonResponse(buildGeneralizedRecentResponse([])))
      }
      if (url.endsWith('/strategy-lab/etf-ranking') && (init?.method ?? 'GET') === 'POST') {
        return new Promise<Response>((resolve) => {
          resolveFetch = resolve
        })
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} />)

    const runButton = screen.getByText('Run ETF Ranking') as HTMLButtonElement
    fireEvent.click(runButton)

    await waitFor(() => expect((screen.getByText('Running...') as HTMLButtonElement).className.includes('button-loading')).toBe(true))

    resolveFetch(jsonResponse(buildRankingArtifact({
      universe: ['IUFS', 'IUHC'],
      request: { peer_group: 'Sector UCITS ETF', universe: ['IUFS', 'IUHC'], benchmark_symbol: 'SPY', lookback_months: 6 },
      effective_inputs: { effective_peer_group: 'Sector UCITS ETF', effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 }, requested_universe: ['IUFS', 'IUHC'], evaluated_universe: ['IUFS', 'IUHC'], excluded_symbols: [] },
      warnings: { confidence: 'medium', warnings: [], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] },
      ranked_universe: [{ rank: 1, symbol: 'IUFS', composite_score: 0.8123, instrument: { symbol: 'IUFS', name: 'ETF', asset_class: 'etf', sector: 'Financials', category: 'Sector UCITS ETF', currency: 'USD' }, component_scores: { momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 11.2, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 } } }],
      excluded_symbols: [],
    })))

    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())
    fireEvent.click(screen.getByText('Seed Candidate Draft'))

    const createDraftButton = screen.getByText('Create Draft') as HTMLButtonElement
    expect(createDraftButton.disabled).toBe(true)
    expect(createDraftButton.className.includes('button-loading')).toBe(false)
  })

  it('renders a structured error state when the ranking request fails', async () => {
    installFetchRouter({ runStatus: 400, runErrorBody: { detail: 'lookback_months must be at least 1' } })

    render(<EtfRankingPanel />)

    fireEvent.change(screen.getByLabelText('Lookback (months)'), { target: { value: '0' } })
    fireEvent.click(screen.getByText('Run ETF Ranking'))

    await waitFor(() => expect(screen.getByText('ETF ranking failed.')).toBeTruthy())
    expect(screen.getByText('The request did not return a usable ranking payload.')).toBeTruthy()
    expect(screen.getByText('lookback_months must be at least 1')).toBeTruthy()
  })

  it('loads recent runs from discovery metadata, filters them, and reuses the ranking view', async () => {
    const sectorRun = buildRecentRun()
    const bondRun = buildRecentRun({ artifact_id: 'etf_ranking_artifact_bond_1', effective_peer_group: 'Bond UCITS ETF', confidence: 'high', benchmark_symbol: 'AGG' })
    const bondArtifact = buildRankingArtifact({
      artifact_id: 'etf_ranking_artifact_bond_1',
      benchmark_symbol: 'AGG',
      effective_peer_group: 'Bond UCITS ETF',
      request: { peer_group: 'Bond UCITS ETF', universe: ['VDST'], benchmark_symbol: 'AGG', lookback_months: 6 },
      effective_inputs: { effective_peer_group: 'Bond UCITS ETF', effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 }, requested_universe: ['VDST'], evaluated_universe: ['VDST'], excluded_symbols: [] },
      run_metadata: { ranking_id: 'etf_ranking_engine_v1', methodology_id: 'etf_ranking_methodology_v1', methodology: 'm', as_of_date: '2026-04-15', ranking_basis_date: '2026-04-15', price_basis: 'close', source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' }, confidence: 'high' },
      warnings: { confidence: 'high', warnings: [], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] },
      ranked_universe: [{ rank: 1, symbol: 'VDST', composite_score: 0.8444, instrument: { symbol: 'VDST', name: 'ETF', asset_class: 'etf', sector: 'Fixed Income', category: 'Bond UCITS ETF', currency: 'USD' }, component_scores: { momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 5.5, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 } } }],
      excluded_symbols: [],
    })

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF', 'Bond UCITS ETF'] })
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return jsonResponse(buildGeneralizedRecentResponse([sectorRun, bondRun]))
      }
      if (url.includes('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking&effective_peer_group=Bond+UCITS+ETF')) {
        return jsonResponse(buildGeneralizedRecentResponse([bondRun], { artifact_kind: 'etf_ranking', effective_peer_group: 'Bond UCITS ETF' }))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_bond_1') && (init?.method ?? 'GET') === 'POST') {
        return jsonResponse(buildPreflightResponse(bondArtifact))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST') {
        return jsonResponse(buildOpenResponse(bondArtifact, buildPreflightResponse(bondArtifact)))
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} />)

    await waitFor(() => expect(screen.getAllByText('Load Run').length).toBe(2))
    expect(screen.getByText('All peer groups')).toBeTruthy()
    expect(screen.getByText('etf_ranking_artifact_sector_1')).toBeTruthy()
    expect(screen.getByText('etf_ranking_artifact_bond_1')).toBeTruthy()

    fireEvent.change(screen.getByLabelText('Peer Group Filter'), { target: { value: 'Bond UCITS ETF' } })

    await waitFor(() => expect(screen.queryByText('etf_ranking_artifact_sector_1')).toBeNull())
    expect(screen.getByText('etf_ranking_artifact_bond_1')).toBeTruthy()

    await waitFor(() => expect(screen.getAllByText('Load Run').length).toBe(1))
    fireEvent.click(screen.getByText('Load Run'))

    await waitFor(() => expect(screen.getByText('Source: Recent Artifact')).toBeTruthy())
    expect(screen.getByText('Artifact: etf_ranking_artifact_bond_1')).toBeTruthy()
    expect(screen.getByText('Peer Group: Bond UCITS ETF')).toBeTruthy()
    expect(screen.getByText('Confidence: high')).toBeTruthy()
    expect(screen.getByText('Open a workspace with an authoritative current portfolio to review this ranking in construction')).toBeTruthy()
    expect(fetchSpy).toHaveBeenCalled()
  })

  it('offers Review In Construction for persisted ETF rankings and routes the handoff without inline ranked_universe', async () => {
    const onReviewInConstruction = vi.fn()
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] })
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return jsonResponse(buildGeneralizedRecentResponse([buildRecentRun()]))
      }
      if (url.endsWith('/construction/ranking-artifacts/preflight/etf_ranking_artifact_sector_1') && (init?.method ?? 'GET') === 'POST') {
        return jsonResponse({
          contract_version: 'construction_ranking_artifact_preflight_v1',
          artifact: {
            artifact_kind: 'etf_ranking',
            artifact_id: 'etf_ranking_artifact_sector_1',
            schema_version: 'etf_ranking_artifact_v1',
            ranking_id: 'etf_ranking_engine_v1',
            methodology_id: 'etf_ranking_methodology_v1',
            as_of_date: '2026-04-15',
          },
          eligibility: {
            eligible: true,
            reason: null,
          },
          handoff: {
            handoff_kind: 'etf_ranking_artifact_construction_handoff_v1',
            artifact_kind: 'etf_ranking',
            artifact_id: 'etf_ranking_artifact_sector_1',
            schema_version: 'etf_ranking_artifact_v1',
            ranking_id: 'etf_ranking_engine_v1',
            methodology_id: 'etf_ranking_methodology_v1',
            as_of_date: '2026-04-15',
          },
        })
      }
      if (url.endsWith('/construction/run') && (init?.method ?? 'GET') === 'POST') {
        const body = JSON.parse(String(init?.body ?? '{}'))
        expect(body.ranked_universe).toBeUndefined()
        expect(body.policy).toEqual({ policy_id: 'top_n_equal_weight_v1', top_n: 2 })
        expect(body.hard_constraints).toEqual({
          full_investment: true,
          long_only: true,
          eligible_ranked_universe_only: true,
          max_position_weight: 0.6,
          min_position_weight: 0.2,
        })
        expect(body.ranking_artifact_handoff).toEqual({
          handoff_kind: 'etf_ranking_artifact_construction_handoff_v1',
          artifact_kind: 'etf_ranking',
          artifact_id: 'etf_ranking_artifact_sector_1',
          schema_version: 'etf_ranking_artifact_v1',
          ranking_id: 'etf_ranking_engine_v1',
          methodology_id: 'etf_ranking_methodology_v1',
          as_of_date: '2026-04-15',
        })
        return jsonResponse({
          schema_version: 'construction_artifact_v1',
          artifact_id: 'construction_artifact_123',
          normalized_inputs: {
            ranked_universe_artifact_kind: 'etf_ranking',
            ranked_universe_artifact_id: 'etf_ranking_artifact_sector_1',
            ranked_universe_artifact_schema_version: 'etf_ranking_artifact_v1',
            ranking_id: 'etf_ranking_engine_v1',
            ranking_methodology_id: 'etf_ranking_methodology_v1',
            ranking_as_of_date: '2026-04-15',
            current_portfolio_artifact_id: 'workspace_current_portfolio_1',
            current_portfolio_as_of_timestamp: '2026-04-10T00:00:00Z',
            policy_id: 'top_n_equal_weight_v1',
            policy_definition_id: 'construction_policy_definition_top_n_equal_weight_v1',
            top_n: 2,
          },
        })
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} currentPortfolio={authoritativeCurrentPortfolio} onReviewInConstruction={onReviewInConstruction} />)

    fireEvent.change(screen.getByLabelText('Min Position Weight (optional)'), { target: { value: '0.2' } })
    await waitFor(() => expect(screen.getByText('Review In Construction')).toBeTruthy())
    fireEvent.click(screen.getByText('Review In Construction'))

    await waitFor(() => expect(onReviewInConstruction).toHaveBeenCalledWith(expect.objectContaining({
      rankingArtifactId: 'etf_ranking_artifact_sector_1',
      run: expect.objectContaining({ artifact_id: 'construction_artifact_123' }),
    })))
    expect(fetchSpy).toHaveBeenCalled()
  })

  it('passes an edited max position weight into Review In Construction', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] })
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return jsonResponse(buildGeneralizedRecentResponse([buildRecentRun()]))
      }
      if (url.endsWith('/construction/ranking-artifacts/preflight/etf_ranking_artifact_sector_1') && (init?.method ?? 'GET') === 'POST') {
        return jsonResponse({
          contract_version: 'construction_ranking_artifact_preflight_v1',
          artifact: {
            artifact_kind: 'etf_ranking',
            artifact_id: 'etf_ranking_artifact_sector_1',
            schema_version: 'etf_ranking_artifact_v1',
            ranking_id: 'etf_ranking_engine_v1',
            methodology_id: 'etf_ranking_methodology_v1',
            as_of_date: '2026-04-15',
          },
          eligibility: {
            eligible: true,
            reason: null,
          },
          handoff: {
            handoff_kind: 'etf_ranking_artifact_construction_handoff_v1',
            artifact_kind: 'etf_ranking',
            artifact_id: 'etf_ranking_artifact_sector_1',
            schema_version: 'etf_ranking_artifact_v1',
            ranking_id: 'etf_ranking_engine_v1',
            methodology_id: 'etf_ranking_methodology_v1',
            as_of_date: '2026-04-15',
          },
        })
      }
      if (url.endsWith('/construction/run') && (init?.method ?? 'GET') === 'POST') {
        const body = JSON.parse(String(init?.body ?? '{}'))
        expect(body.hard_constraints).toEqual({
          full_investment: true,
          long_only: true,
          eligible_ranked_universe_only: true,
          max_position_weight: 0.75,
          min_position_weight: 0.25,
        })
        return jsonResponse({
          schema_version: 'construction_artifact_v1',
          artifact_id: 'construction_artifact_123',
          normalized_inputs: {
            ranked_universe_artifact_kind: 'etf_ranking',
            ranked_universe_artifact_id: 'etf_ranking_artifact_sector_1',
            ranked_universe_artifact_schema_version: 'etf_ranking_artifact_v1',
            ranking_id: 'etf_ranking_engine_v1',
            ranking_methodology_id: 'etf_ranking_methodology_v1',
            ranking_as_of_date: '2026-04-15',
            current_portfolio_artifact_id: 'workspace_current_portfolio_1',
            current_portfolio_as_of_timestamp: '2026-04-10T00:00:00Z',
            policy_id: 'top_n_equal_weight_v1',
            policy_definition_id: 'construction_policy_definition_top_n_equal_weight_v1',
            top_n: 2,
          },
        })
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} currentPortfolio={authoritativeCurrentPortfolio} />)

    fireEvent.change(screen.getByLabelText('Max Position Weight'), { target: { value: '0.75' } })
    fireEvent.change(screen.getByLabelText('Min Position Weight (optional)'), { target: { value: '0.25' } })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Review In Construction' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Review In Construction' }))

    await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining('/construction/run'),
      expect.objectContaining({ method: 'POST' }),
    ))
  })

  it('blocks Review In Construction locally when no active workspace draft is available', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] })
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return jsonResponse(buildGeneralizedRecentResponse([buildRecentRun()]))
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel />)

    await waitFor(() => expect(screen.getByText('Review In Construction')).toBeTruthy())
    expect(screen.getByText('Open a workspace with an authoritative current portfolio to review this ranking in construction')).toBeTruthy()
  })

  it('blocks Review In Construction locally when max position weight is blank or out of range', async () => {
    installFetchRouter({ recentRuns: [buildRecentRun()] })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} />)

    const maxPositionWeightInput = await screen.findByLabelText('Max Position Weight')
    const reviewButton = screen.getByRole('button', { name: 'Review In Construction' }) as HTMLButtonElement

    fireEvent.change(maxPositionWeightInput, { target: { value: '' } })
    await waitFor(() => expect(reviewButton.disabled).toBe(true))
    expect(screen.getAllByText('Enter a max position weight as a decimal between 0.5 and 1.').length).toBeGreaterThan(0)

    fireEvent.change(maxPositionWeightInput, { target: { value: '1.1' } })
    await waitFor(() => expect(reviewButton.disabled).toBe(true))
    expect(screen.getAllByText('Max position weight must be between 0.5 and 1.').length).toBeGreaterThan(0)
  })

  it('omits min position weight when left blank and blocks invalid local min values', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] })
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return jsonResponse(buildGeneralizedRecentResponse([buildRecentRun()]))
      }
      if (url.endsWith('/construction/ranking-artifacts/preflight/etf_ranking_artifact_sector_1') && (init?.method ?? 'GET') === 'POST') {
        return jsonResponse({
          contract_version: 'construction_ranking_artifact_preflight_v1',
          artifact: {
            artifact_kind: 'etf_ranking',
            artifact_id: 'etf_ranking_artifact_sector_1',
            schema_version: 'etf_ranking_artifact_v1',
            ranking_id: 'etf_ranking_engine_v1',
            methodology_id: 'etf_ranking_methodology_v1',
            as_of_date: '2026-04-15',
          },
          eligibility: {
            eligible: true,
            reason: null,
          },
          handoff: {
            handoff_kind: 'etf_ranking_artifact_construction_handoff_v1',
            artifact_kind: 'etf_ranking',
            artifact_id: 'etf_ranking_artifact_sector_1',
            schema_version: 'etf_ranking_artifact_v1',
            ranking_id: 'etf_ranking_engine_v1',
            methodology_id: 'etf_ranking_methodology_v1',
            as_of_date: '2026-04-15',
          },
        })
      }
      if (url.endsWith('/construction/run') && (init?.method ?? 'GET') === 'POST') {
        const body = JSON.parse(String(init?.body ?? '{}'))
        expect(body.hard_constraints).toEqual({
          full_investment: true,
          long_only: true,
          eligible_ranked_universe_only: true,
          max_position_weight: 0.6,
        })
        return jsonResponse({
          schema_version: 'construction_artifact_v1',
          artifact_id: 'construction_artifact_123',
          normalized_inputs: {
            ranked_universe_artifact_kind: 'etf_ranking',
            ranked_universe_artifact_id: 'etf_ranking_artifact_sector_1',
            ranked_universe_artifact_schema_version: 'etf_ranking_artifact_v1',
            ranking_id: 'etf_ranking_engine_v1',
            ranking_methodology_id: 'etf_ranking_methodology_v1',
            ranking_as_of_date: '2026-04-15',
            current_portfolio_artifact_id: 'workspace_current_portfolio_1',
            current_portfolio_as_of_timestamp: '2026-04-10T00:00:00Z',
            policy_id: 'top_n_equal_weight_v1',
            policy_definition_id: 'construction_policy_definition_top_n_equal_weight_v1',
            top_n: 2,
          },
        })
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} currentPortfolio={authoritativeCurrentPortfolio} />)

    const reviewButton = await screen.findByRole('button', { name: 'Review In Construction' }) as HTMLButtonElement
    fireEvent.change(screen.getByLabelText('Min Position Weight (optional)'), { target: { value: '0.7' } })
    await waitFor(() => expect(reviewButton.disabled).toBe(true))
    expect(screen.getAllByText('Min position weight must be less than or equal to 0.5.').length).toBeGreaterThan(0)

    fireEvent.change(screen.getByLabelText('Min Position Weight (optional)'), { target: { value: '' } })
    await waitFor(() => expect(reviewButton.disabled).toBe(false))
    fireEvent.click(reviewButton)

    await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining('/construction/run'),
      expect.objectContaining({ method: 'POST' }),
    ))
  })

  it('surfaces only equal-weight and linear-rank launch policies', async () => {
    installFetchRouter({ recentRuns: [buildRecentRun()] })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} currentPortfolio={authoritativeCurrentPortfolio} />)

    const policySelect = await screen.findByLabelText('Construction Policy')
    expect(screen.getByRole('option', { name: 'Top N Equal Weight v1' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'Top N Linear Rank Weight v1' })).toBeTruthy()
    expect(screen.queryByRole('option', { name: 'Top N Inverse Rank Weight v1' })).toBeNull()
    expect((policySelect as HTMLSelectElement).value).toBe('top_n_equal_weight_v1')
    expect(screen.getAllByText('Top N Equal Weight v1 (default); fixed top_n=2; requires max_position_weight; optional min_position_weight, max_turnover_weight, max_trade_intent_count').length).toBeGreaterThan(0)
  })

  it('fails closed when equal weight is not discovered in the canonical launch profile', async () => {
    installFetchRouter({
      recentRuns: [buildRecentRun()],
      constructionPolicies: buildConstructionPoliciesResponse(['top_n_inverse_rank_weight_v1', 'top_n_linear_rank_weight_v1']),
    })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} currentPortfolio={authoritativeCurrentPortfolio} />)

    await waitFor(() => expect(screen.getByText('Construction policies are unavailable.')).toBeTruthy())
    expect(screen.getAllByText('Construction policy catalog must define exactly one default launch policy').length).toBeGreaterThan(0)
  })

  it('fails closed when construction policy discovery returns an out-of-range launch_top_n', async () => {
    // Epic 3 breadth: launch_top_n widened to range [2, 20]. Use a below-min value
    // (1) to trigger the rejection; previously 3 was rejected but that's now in range.
    installFetchRouter({
      recentRuns: [buildRecentRun()],
      constructionPolicies: buildConstructionPoliciesResponse().map((policy) => ({
        ...policy,
        launch_top_n: policy.policy_id === 'top_n_equal_weight_v1' ? 1 : policy.launch_top_n,
      })),
    })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} />)

    await waitFor(() => expect(screen.getByText('Construction policies are unavailable.')).toBeTruthy())
    // The fixture sets the OUTER row's launch_top_n to 1 (not launch_profile.launch_top_n),
    // so the outer-row validator fires first with: "Construction policy catalog returned an unsupported launch_top_n"
    expect(screen.getAllByText('Construction policy catalog returned an unsupported launch_top_n').length).toBeGreaterThan(0)
  })

  it('fails closed when construction policy discovery returns policy-status metadata inconsistent with policy identity', async () => {
    installFetchRouter({
      recentRuns: [buildRecentRun()],
      constructionPolicies: buildConstructionPoliciesResponse().map((policy) => ({
        ...policy,
        launch_profile: {
          ...policy.launch_profile,
          policy_status: policy.policy_id === 'top_n_linear_rank_weight_v1' ? 'default' : policy.launch_profile.policy_status,
        },
      })),
    })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} />)

    await waitFor(() => expect(screen.getByText('Construction policies are unavailable.')).toBeTruthy())
    expect(screen.getAllByText('Construction policy catalog returned policy metadata inconsistent with launch_profile.policy_status').length).toBeGreaterThan(0)
  })

  it('opens a requested persisted ETF ranking artifact on entry', async () => {
    const preflight = buildPreflightResponse(buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_recent_open' }))
    const open = buildOpenResponse(buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_recent_open' }), preflight)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] })
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return jsonResponse(buildGeneralizedRecentResponse([buildRecentRun({ artifact_id: 'etf_ranking_artifact_recent_open' })]))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_recent_open') && (init?.method ?? 'GET') === 'POST') {
        return jsonResponse(preflight)
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST') {
        return jsonResponse(open)
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })
    const onConsumeRequestedRecentArtifactId = vi.fn()

    render(<EtfRankingPanel requestedRecentArtifactId="etf_ranking_artifact_recent_open" onConsumeRequestedRecentArtifactId={onConsumeRequestedRecentArtifactId} />)

    await waitFor(() => expect(screen.getByText('Source: Recent Artifact')).toBeTruthy())
    expect(onConsumeRequestedRecentArtifactId).toHaveBeenCalledTimes(1)
  })

  it('opens recent artifacts through preflight handoff and typed open payload', async () => {
    const recentArtifact = buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_recent_open' })
    const preflight = buildPreflightResponse(recentArtifact)
    const open = buildOpenResponse(recentArtifact, preflight)
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] })
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return jsonResponse(buildGeneralizedRecentResponse([buildRecentRun({ artifact_id: 'etf_ranking_artifact_recent_open' })]))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_recent_open') && (init?.method ?? 'GET') === 'POST') {
        return jsonResponse(preflight)
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST') {
        expect(JSON.parse(String(init?.body))).toEqual(preflight.open_handoff)
        return jsonResponse(open)
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel />)

    await waitFor(() => expect(screen.getByText('Load Run')).toBeTruthy())
    fireEvent.click(screen.getByText('Load Run'))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_recent_open')).toBeTruthy())
    expect(fetchSpy).toHaveBeenCalled()
  })

  it('fails closed when recent artifact open returns unsupported review payload kind', async () => {
    const recentArtifact = buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_bad_open' })
    const preflight = buildPreflightResponse(recentArtifact)
    installFetchRouter({
      recentRuns: [buildRecentRun({ artifact_id: 'etf_ranking_artifact_bad_open' })],
      recentArtifact: recentArtifact,
      recentArtifactPreflight: preflight,
      recentArtifactOpen: buildOpenResponse(recentArtifact, preflight, {
        review_payload_kind: 'intent_bound_etf_replacement_ranking_review_payload_v1',
        review_payload: {
          review_payload_kind: 'intent_bound_etf_replacement_ranking_review_payload_v1',
          review_truth_basis: 'authoritative_persisted_ranking_artifact',
          review_scope: 'artifact_backed_review_only',
          artifact_kind: 'intent_bound_etf_replacement_ranking',
          artifact_id: recentArtifact.artifact_id,
          schema_version: 'intent_bound_etf_replacement_ranking_artifact_v1',
          artifact: {},
        },
      }),
    })

    render(<EtfRankingPanel />)

    await waitFor(() => expect(screen.getByText('Load Run')).toBeTruthy())
    fireEvent.click(screen.getByText('Load Run'))

    await waitFor(() => expect(screen.getByText('Recent artifact load failed.')).toBeTruthy())
    expect(screen.getByText('Ranking artifact open returned unsupported review payload kind intent_bound_etf_replacement_ranking_review_payload_v1')).toBeTruthy()
  })

  it('fails closed when recent artifact open payload identity mismatches preflight', async () => {
    const recentArtifact = buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_mismatch' })
    const preflight = buildPreflightResponse(recentArtifact)
    installFetchRouter({
      recentRuns: [buildRecentRun({ artifact_id: 'etf_ranking_artifact_mismatch' })],
      recentArtifact: recentArtifact,
      recentArtifactPreflight: preflight,
      recentArtifactOpen: buildOpenResponse(
        buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_other' }),
        preflight,
      ),
    })

    render(<EtfRankingPanel />)

    await waitFor(() => expect(screen.getByText('Load Run')).toBeTruthy())
    fireEvent.click(screen.getByText('Load Run'))

    await waitFor(() => expect(screen.getByText('Recent artifact load failed.')).toBeTruthy())
    expect(screen.getByText('Ranking artifact open review payload identity does not match preflight')).toBeTruthy()
  })

  it('seeds a draft from a loaded recent artifact the same way as a fresh run', async () => {
    const onSeedCandidateDraft = vi.fn()

    installFetchRouter({
      recentRuns: [buildRecentRun()],
      recentArtifact: buildRankingArtifact(),
    })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} onSeedCandidateDraft={onSeedCandidateDraft} />)

    await waitFor(() => expect(screen.getByText('Load Run')).toBeTruthy())
    fireEvent.click(screen.getByText('Load Run'))

    await waitFor(() => expect(screen.getByText('Source: Recent Artifact')).toBeTruthy())
    fireEvent.click(screen.getAllByText('Seed Candidate Draft')[0])
    fireEvent.change(screen.getByLabelText('Incumbent ETF'), { target: { value: 'VUAA' } })
    fireEvent.click(screen.getByText('Create Draft'))

    expect(onSeedCandidateDraft).toHaveBeenCalledTimes(1)
    expect(onSeedCandidateDraft.mock.calls[0]?.[0]).toMatchObject({
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        baseSymbol: 'VUAA',
        candidateSymbol: 'IUFS',
        rankingId: 'etf_ranking_engine_v1',
      },
      rankingArtifact: {
        kind: 'intent_bound_seeded_etf_replacement_ranking',
        source: 'etf_ranking',
        baseSymbol: 'VUAA',
        candidateSymbol: 'IUFS',
        rankingId: 'etf_ranking_engine_v1',
        openHandoff: {
          handoff_kind: 'ranking_artifact_open_handoff_v1',
          artifact_kind: 'etf_ranking',
          artifact_id: 'etf_ranking_artifact_sector_1',
          schema_version: 'etf_ranking_artifact_v1',
        },
      },
    })
  })

  it('keeps the newest fresh run when two runs resolve out of order', async () => {
    const runRequests: Array<ReturnType<typeof createDeferred<Response>>> = []

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return Promise.resolve(jsonResponse(buildConstructionPoliciesResponse()))
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return Promise.resolve(jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] }))
      }
      if (url.includes('/strategy-lab/ranking-artifacts/recent')) {
        return Promise.resolve(jsonResponse([]))
      }
      if (url.endsWith('/strategy-lab/etf-ranking') && (init?.method ?? 'GET') === 'POST') {
        const request = createDeferred<Response>()
        runRequests.push(request)
        return request.promise
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel />)

    const runButton = screen.getByText('Run ETF Ranking')
    await act(async () => {
      fireEvent.click(runButton)
      fireEvent.click(runButton)
    })

    await waitFor(() => expect(runRequests).toHaveLength(2))

    runRequests[1]?.resolve(jsonResponse(buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_second_run', effective_peer_group: 'Broad Market UCITS ETF', request: { peer_group: 'Broad Market UCITS ETF', universe: ['VUAA'], benchmark_symbol: 'SPY', lookback_months: 6 }, effective_inputs: { effective_peer_group: 'Broad Market UCITS ETF', effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 }, requested_universe: ['VUAA'], evaluated_universe: ['VUAA'], excluded_symbols: [] }, warnings: { confidence: 'high', warnings: [], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] }, run_metadata: { ranking_id: 'etf_ranking_engine_v1', methodology_id: 'etf_ranking_methodology_v1', methodology: 'm', as_of_date: '2026-04-15', ranking_basis_date: '2026-04-15', price_basis: 'close', source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'complete' }, confidence: 'high' }, ranked_universe: [{ rank: 1, symbol: 'VUAA', composite_score: 0.9555, instrument: { symbol: 'VUAA', name: 'ETF', asset_class: 'etf', sector: 'Broad Market', category: 'Broad Market UCITS ETF', currency: 'USD' }, component_scores: { momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 12.3, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 } } }], excluded_symbols: [] })))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_second_run')).toBeTruthy())
    expect(screen.getByText('Source: Fresh Run')).toBeTruthy()
    expect(screen.getByText('Peer Group: Broad Market UCITS ETF')).toBeTruthy()

    runRequests[0]?.resolve(jsonResponse(buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_first_run' })))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_second_run')).toBeTruthy())
    expect(screen.queryByText('Artifact: etf_ranking_artifact_first_run')).toBeNull()
  })

  it('keeps the newest artifact load when a stale run fails later and clears seed confirmation immediately', async () => {
    const onSeedCandidateDraft = vi.fn()
    let runCount = 0
    const firstRunResponse = jsonResponse(buildRankingArtifact())
    const runRequest = createDeferred<Response>()
    const artifactRequest = createDeferred<Response>()
    const bondArtifact = buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_bond_1', benchmark_symbol: 'AGG', effective_peer_group: 'Bond UCITS ETF', request: { peer_group: 'Bond UCITS ETF', universe: ['VDST'], benchmark_symbol: 'AGG', lookback_months: 6 }, effective_inputs: { effective_peer_group: 'Bond UCITS ETF', effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 }, requested_universe: ['VDST'], evaluated_universe: ['VDST'], excluded_symbols: [] }, warnings: { confidence: 'high', warnings: [], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] }, run_metadata: { ranking_id: 'etf_ranking_engine_v1', methodology_id: 'etf_ranking_methodology_v1', methodology: 'm', as_of_date: '2026-04-15', ranking_basis_date: '2026-04-15', price_basis: 'close', source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' }, confidence: 'high' }, ranked_universe: [{ rank: 1, symbol: 'VDST', composite_score: 0.8444, instrument: { symbol: 'VDST', name: 'ETF', asset_class: 'etf', sector: 'Fixed Income', category: 'Bond UCITS ETF', currency: 'USD' }, component_scores: { momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 5.5, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 } } }], excluded_symbols: [] })

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return Promise.resolve(jsonResponse(buildConstructionPoliciesResponse()))
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return Promise.resolve(jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF', 'Bond UCITS ETF'] }))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return Promise.resolve(jsonResponse(buildGeneralizedRecentResponse([buildRecentRun({ artifact_id: 'etf_ranking_artifact_bond_1', effective_peer_group: 'Bond UCITS ETF', benchmark_symbol: 'AGG', confidence: 'high' })])))
      }
      if (url.endsWith('/strategy-lab/etf-ranking') && (init?.method ?? 'GET') === 'POST') {
        runCount += 1
        if (runCount === 1) return Promise.resolve(firstRunResponse)
        return runRequest.promise
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_bond_1') && (init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonResponse(buildPreflightResponse(bondArtifact)))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST') {
        return artifactRequest.promise
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel draftSymbols={['VUAA', 'IWDA']} onSeedCandidateDraft={onSeedCandidateDraft} />)

    fireEvent.click(screen.getByText('Run ETF Ranking'))
    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_sector_1')).toBeTruthy())

    fireEvent.click(screen.getAllByText('Seed Candidate Draft')[0])
    fireEvent.change(screen.getByLabelText('Incumbent ETF'), { target: { value: 'VUAA' } })
    fireEvent.click(screen.getByText('Create Draft'))
    expect(screen.getByText('Candidate draft created for review.')).toBeTruthy()

    fireEvent.click(screen.getByText('Run ETF Ranking'))

    expect(screen.queryByText('Candidate draft created for review.')).toBeNull()
    expect(screen.getByText('Artifact: etf_ranking_artifact_sector_1')).toBeTruthy()

    await waitFor(() => expect(screen.getByText('Load Run')).toBeTruthy())
    fireEvent.click(screen.getByText('Load Run'))

    artifactRequest.resolve(jsonResponse(buildOpenResponse(bondArtifact, buildPreflightResponse(bondArtifact))))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_bond_1')).toBeTruthy())
    expect(screen.getByText('Source: Recent Artifact')).toBeTruthy()

    runRequest.resolve(jsonResponse({ detail: 'stale run failure' }, 400))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_bond_1')).toBeTruthy())
    expect(screen.queryByText('ETF ranking failed.')).toBeNull()
    expect(screen.queryByText('stale run failure')).toBeNull()
  })

  it('keeps the newest fresh run when a stale artifact resolves later', async () => {
    const artifactRequest = createDeferred<Response>()
    const runRequest = createDeferred<Response>()
    const sectorArtifact = buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_sector_1' })

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return Promise.resolve(jsonResponse(buildConstructionPoliciesResponse()))
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return Promise.resolve(jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] }))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return Promise.resolve(jsonResponse(buildGeneralizedRecentResponse([buildRecentRun()])))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1') && (init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonResponse(buildPreflightResponse(sectorArtifact)))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST') {
        return artifactRequest.promise
      }
      if (url.endsWith('/strategy-lab/etf-ranking') && (init?.method ?? 'GET') === 'POST') {
        return runRequest.promise
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel />)

    await waitFor(() => expect(screen.getAllByText('Load Run').length).toBe(1))
    fireEvent.click(screen.getAllByText('Load Run')[0])
    fireEvent.click(screen.getByText('Run ETF Ranking'))

    runRequest.resolve(jsonResponse(buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_fresh_run', effective_peer_group: 'Commodity UCITS ETF', request: { peer_group: 'Commodity UCITS ETF', universe: ['GLD'], benchmark_symbol: 'GLD', lookback_months: 6 }, effective_inputs: { effective_peer_group: 'Commodity UCITS ETF', effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 }, requested_universe: ['GLD'], evaluated_universe: ['GLD'], excluded_symbols: [] }, warnings: { confidence: 'medium', warnings: [], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] }, ranked_universe: [{ rank: 1, symbol: 'GLD', composite_score: 0.8111, instrument: { symbol: 'GLD', name: 'ETF', asset_class: 'etf', sector: 'Commodity', category: 'Commodity UCITS ETF', currency: 'USD' }, component_scores: { momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 7.7, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 } } }], excluded_symbols: [] })))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_fresh_run')).toBeTruthy())
    expect(screen.getByText('Source: Fresh Run')).toBeTruthy()

    artifactRequest.resolve(jsonResponse(buildOpenResponse(sectorArtifact, buildPreflightResponse(sectorArtifact))))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_fresh_run')).toBeTruthy())
    expect(screen.queryByText('Source: Recent Artifact')).toBeNull()
  })

  it('keeps the newest artifact load when an older artifact fails later', async () => {
    const firstArtifactRequest = createDeferred<Response>()
    const secondArtifactRequest = createDeferred<Response>()
    const sectorArtifact = buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_sector_1' })
    const bondArtifact = buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_bond_1', benchmark_symbol: 'AGG', effective_peer_group: 'Bond UCITS ETF', request: { peer_group: 'Bond UCITS ETF', universe: ['VDST'], benchmark_symbol: 'AGG', lookback_months: 6 }, effective_inputs: { effective_peer_group: 'Bond UCITS ETF', effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 }, requested_universe: ['VDST'], evaluated_universe: ['VDST'], excluded_symbols: [] }, warnings: { confidence: 'high', warnings: [], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] }, run_metadata: { ranking_id: 'etf_ranking_engine_v1', methodology_id: 'etf_ranking_methodology_v1', methodology: 'm', as_of_date: '2026-04-15', ranking_basis_date: '2026-04-15', price_basis: 'close', source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' }, confidence: 'high' }, ranked_universe: [{ rank: 1, symbol: 'VDST', composite_score: 0.8444, instrument: { symbol: 'VDST', name: 'ETF', asset_class: 'etf', sector: 'Fixed Income', category: 'Bond UCITS ETF', currency: 'USD' }, component_scores: { momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 5.5, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 } } }], excluded_symbols: [] })

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return Promise.resolve(jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF', 'Bond UCITS ETF'] }))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return Promise.resolve(jsonResponse(buildGeneralizedRecentResponse([
          buildRecentRun({ artifact_id: 'etf_ranking_artifact_sector_1' }),
          buildRecentRun({ artifact_id: 'etf_ranking_artifact_bond_1', effective_peer_group: 'Bond UCITS ETF', benchmark_symbol: 'AGG', confidence: 'high' }),
        ])))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1') && (init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonResponse(buildPreflightResponse(sectorArtifact)))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_bond_1') && (init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonResponse(buildPreflightResponse(bondArtifact)))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST' && String(init?.body).includes('etf_ranking_artifact_sector_1')) {
        return firstArtifactRequest.promise
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST' && String(init?.body).includes('etf_ranking_artifact_bond_1')) {
        return secondArtifactRequest.promise
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel />)

    const initialLoadButtons = await screen.findAllByRole('button', { name: 'Load Run' })
    fireEvent.click(initialLoadButtons[0])
    fireEvent.click(initialLoadButtons[1])

    secondArtifactRequest.resolve(jsonResponse(buildOpenResponse(bondArtifact, buildPreflightResponse(bondArtifact))))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_bond_1')).toBeTruthy())
    expect(screen.getByText('Source: Recent Artifact')).toBeTruthy()

    firstArtifactRequest.resolve(jsonResponse({ detail: 'stale artifact failure' }, 404))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_bond_1')).toBeTruthy())
    expect(screen.queryByText('Recent artifact load failed.')).toBeNull()
    expect(screen.queryByText('stale artifact failure')).toBeNull()
  })

  it('ignores a stale failed run after a newer run succeeds', async () => {
    const runRequests: Array<ReturnType<typeof createDeferred<Response>>> = []

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return Promise.resolve(jsonResponse(buildConstructionPoliciesResponse()))
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return Promise.resolve(jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] }))
      }
      if (url.includes('/strategy-lab/ranking-artifacts/recent')) {
        return Promise.resolve(jsonResponse([]))
      }
      if (url.endsWith('/strategy-lab/etf-ranking') && (init?.method ?? 'GET') === 'POST') {
        const request = createDeferred<Response>()
        runRequests.push(request)
        return request.promise
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel />)

    const runButton = screen.getByText('Run ETF Ranking')
    await act(async () => {
      fireEvent.click(runButton)
      fireEvent.click(runButton)
    })

    await waitFor(() => expect(runRequests).toHaveLength(2))

    runRequests[1]?.resolve(jsonResponse(buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_second_run_success' })))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_second_run_success')).toBeTruthy())

    runRequests[0]?.resolve(jsonResponse({ detail: 'older run failed' }, 400))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_second_run_success')).toBeTruthy())
    expect(screen.queryByText('ETF ranking failed.')).toBeNull()
    expect(screen.queryByText('older run failed')).toBeNull()
  })

  it('keeps the newest artifact result when a stale run resolves later', async () => {
    const runRequest = createDeferred<Response>()
    const artifactRequest = createDeferred<Response>()
    const sectorArtifact = buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_sector_1' })

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return Promise.resolve(jsonResponse(buildConstructionPoliciesResponse()))
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return Promise.resolve(jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF', 'Bond UCITS ETF'] }))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return Promise.resolve(jsonResponse(buildGeneralizedRecentResponse([buildRecentRun(), buildRecentRun({ artifact_id: 'etf_ranking_artifact_bond_1', effective_peer_group: 'Bond UCITS ETF', benchmark_symbol: 'AGG', confidence: 'high' })])))
      }
      if (url.endsWith('/strategy-lab/etf-ranking') && (init?.method ?? 'GET') === 'POST') {
        return runRequest.promise
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1') && (init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonResponse(buildPreflightResponse(sectorArtifact)))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST') {
        return artifactRequest.promise
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel />)

    fireEvent.click(screen.getByText('Run ETF Ranking'))
    await waitFor(() => expect(screen.getAllByText('Load Run').length).toBe(2))
    fireEvent.click(screen.getAllByText('Load Run')[0])

    artifactRequest.resolve(jsonResponse(buildOpenResponse(sectorArtifact, buildPreflightResponse(sectorArtifact))))

    await waitFor(() => expect(screen.getByText('Source: Recent Artifact')).toBeTruthy())

    runRequest.resolve(jsonResponse(buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_stale_run_success', effective_peer_group: 'Commodity UCITS ETF', request: { peer_group: 'Commodity UCITS ETF', universe: ['GLD'], benchmark_symbol: 'GLD', lookback_months: 6 }, effective_inputs: { effective_peer_group: 'Commodity UCITS ETF', effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 }, requested_universe: ['GLD'], evaluated_universe: ['GLD'], excluded_symbols: [] }, warnings: { confidence: 'medium', warnings: [], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] }, ranked_universe: [{ rank: 1, symbol: 'GLD', composite_score: 0.8111, instrument: { symbol: 'GLD', name: 'ETF', asset_class: 'etf', sector: 'Commodity', category: 'Commodity UCITS ETF', currency: 'USD' }, component_scores: { momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 7.7, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 } } }], excluded_symbols: [] })))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_sector_1')).toBeTruthy())
    expect(screen.getByText('Source: Recent Artifact')).toBeTruthy()
    expect(screen.queryByText('Artifact: etf_ranking_artifact_stale_run_success')).toBeNull()
  })

  it('keeps the newest fresh run when a stale artifact fails later', async () => {
    const artifactRequest = createDeferred<Response>()
    const runRequest = createDeferred<Response>()
    const sectorArtifact = buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_sector_1' })

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return Promise.resolve(jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF'] }))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return Promise.resolve(jsonResponse(buildGeneralizedRecentResponse([buildRecentRun()])))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1') && (init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonResponse(buildPreflightResponse(sectorArtifact)))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST') {
        return artifactRequest.promise
      }
      if (url.endsWith('/strategy-lab/etf-ranking') && (init?.method ?? 'GET') === 'POST') {
        return runRequest.promise
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel />)

    await waitFor(() => expect(screen.getByText('Load Run')).toBeTruthy())
    fireEvent.click(screen.getByText('Load Run'))
    fireEvent.click(screen.getByText('Run ETF Ranking'))

    runRequest.resolve(jsonResponse(buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_fresh_run_after_stale_artifact' })))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_fresh_run_after_stale_artifact')).toBeTruthy())
    expect(screen.getByText('Source: Fresh Run')).toBeTruthy()

    artifactRequest.resolve(jsonResponse({ detail: 'older artifact failed' }, 404))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_fresh_run_after_stale_artifact')).toBeTruthy())
    expect(screen.queryByText('Recent artifact load failed.')).toBeNull()
    expect(screen.queryByText('older artifact failed')).toBeNull()
  })

  it('keeps the newest artifact result when an older artifact resolves later', async () => {
    const firstArtifactRequest = createDeferred<Response>()
    const secondArtifactRequest = createDeferred<Response>()
    const sectorArtifact = buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_sector_1' })
    const bondArtifact = buildRankingArtifact({ artifact_id: 'etf_ranking_artifact_bond_1', benchmark_symbol: 'AGG', effective_peer_group: 'Bond UCITS ETF', request: { peer_group: 'Bond UCITS ETF', universe: ['VDST'], benchmark_symbol: 'AGG', lookback_months: 6 }, effective_inputs: { effective_peer_group: 'Bond UCITS ETF', effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 }, requested_universe: ['VDST'], evaluated_universe: ['VDST'], excluded_symbols: [] }, warnings: { confidence: 'high', warnings: [], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] }, run_metadata: { ranking_id: 'etf_ranking_engine_v1', methodology_id: 'etf_ranking_methodology_v1', methodology: 'm', as_of_date: '2026-04-15', ranking_basis_date: '2026-04-15', price_basis: 'close', source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' }, confidence: 'high' }, ranked_universe: [{ rank: 1, symbol: 'VDST', composite_score: 0.8444, instrument: { symbol: 'VDST', name: 'ETF', asset_class: 'etf', sector: 'Fixed Income', category: 'Bond UCITS ETF', currency: 'USD' }, component_scores: { momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 5.5, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 } } }], excluded_symbols: [] })

    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input)
      if (url.includes('/construction/policies')) {
        return Promise.resolve(jsonResponse(buildConstructionPoliciesResponse()))
      }
      if (url.endsWith('/strategy-lab/etf-ranking/artifacts/recent/metadata')) {
        return Promise.resolve(jsonResponse({ available_effective_peer_groups: ['Sector UCITS ETF', 'Bond UCITS ETF'] }))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking')) {
        return Promise.resolve(jsonResponse(buildGeneralizedRecentResponse([
          buildRecentRun({ artifact_id: 'etf_ranking_artifact_sector_1' }),
          buildRecentRun({ artifact_id: 'etf_ranking_artifact_bond_1', effective_peer_group: 'Bond UCITS ETF', benchmark_symbol: 'AGG', confidence: 'high' }),
        ])))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1') && (init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonResponse(buildPreflightResponse(sectorArtifact)))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_bond_1') && (init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonResponse(buildPreflightResponse(bondArtifact)))
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST' && String(init?.body).includes('etf_ranking_artifact_sector_1')) {
        return firstArtifactRequest.promise
      }
      if (url.endsWith('/strategy-lab/ranking-artifacts/open') && (init?.method ?? 'GET') === 'POST' && String(init?.body).includes('etf_ranking_artifact_bond_1')) {
        return secondArtifactRequest.promise
      }
      throw new Error(`Unhandled fetch: ${url}`)
    })

    render(<EtfRankingPanel />)

    const initialLoadButtons = await screen.findAllByRole('button', { name: 'Load Run' })
    fireEvent.click(initialLoadButtons[0])
    fireEvent.click(initialLoadButtons[1])

    secondArtifactRequest.resolve(jsonResponse(buildOpenResponse(bondArtifact, buildPreflightResponse(bondArtifact))))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_bond_1')).toBeTruthy())

    firstArtifactRequest.resolve(jsonResponse(buildOpenResponse(sectorArtifact, buildPreflightResponse(sectorArtifact))))

    await waitFor(() => expect(screen.getByText('Artifact: etf_ranking_artifact_bond_1')).toBeTruthy())
    expect(screen.queryByText('Artifact: etf_ranking_artifact_sector_1')).toBeNull()
  })
})
