import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import { PersistedGenericRankingConstructionBrowser } from './PersistedGenericRankingConstructionBrowser'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function jsonResponse(payload: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(payload), {
    status: init.status ?? 200,
    headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
  })
}

function buildConstructionPoliciesResponse() {
  // The shipped catalog requires all three canonical policies with specific
  // launch profile statuses (one default, inverse-rank excluded, linear opt_in).
  return [
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
    {
      policy_id: 'top_n_inverse_rank_weight_v1',
      policy_definition_id: 'construction_policy_definition_top_n_inverse_rank_weight_v1',
      name: 'Top N Inverse Rank Weight v1',
      description: 'Inverse selected-order weighting.',
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
    {
      policy_id: 'top_n_linear_rank_weight_v1',
      policy_definition_id: 'construction_policy_definition_top_n_linear_rank_weight_v1',
      name: 'Top N Linear Rank Weight v1',
      description: 'Linear selected-order weighting.',
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
  ]
}

function buildGenericRecentResponse(items: unknown[] = [defaultGenericRow()]) {
  return {
    items,
    metadata: { applied_filters: { artifact_kind: 'generic_ranking' } },
  }
}

function defaultGenericRow() {
  return {
    artifact_kind: 'generic_ranking',
    artifact_id: 'generic_ranking_artifact_abc123',
    ranking_id: 'generic_ranking_engine_v1',
    methodology_id: 'generic_ranking_methodology_v1',
    as_of_date: '2026-05-01',
    ranking_basis_date: '2026-05-01',
    etf_summary: null,
    replacement_summary: null,
    generic_summary: {
      benchmark_symbol: 'SPY',
      lookback_months: 6,
      universe_id: 'sp500_quality_v1',
      universe_kind: 'index_constituent',
      score_config_id: 'quality_v1',
      evaluated_universe_size: 480,
      confidence: 'partial',
    },
  }
}

function buildPreflightEligibleResponse() {
  return {
    contract_version: 'construction_ranking_artifact_preflight_v1',
    artifact: {
      artifact_kind: 'generic_ranking',
      artifact_id: 'generic_ranking_artifact_abc123',
      schema_version: 'generic_ranking_artifact_v1',
      ranking_id: 'generic_ranking_engine_v1',
      methodology_id: 'generic_ranking_methodology_v1',
      as_of_date: '2026-05-01',
    },
    eligibility: { eligible: true, reason: null },
    handoff: {
      handoff_kind: 'generic_ranking_artifact_construction_handoff_v1',
      artifact_kind: 'generic_ranking',
      artifact_id: 'generic_ranking_artifact_abc123',
      schema_version: 'generic_ranking_artifact_v1',
      ranking_id: 'generic_ranking_engine_v1',
      methodology_id: 'generic_ranking_methodology_v1',
      as_of_date: '2026-05-01',
    },
  }
}

function buildConstructionRunResponse() {
  return {
    schema_version: 'construction_artifact_v1',
    artifact_id: 'construction_artifact_xyz789',
    normalized_inputs: {
      ranked_universe_artifact_kind: 'generic_ranking',
      ranked_universe_artifact_id: 'generic_ranking_artifact_abc123',
      ranked_universe_artifact_schema_version: 'generic_ranking_artifact_v1',
      ranking_id: 'generic_ranking_engine_v1',
      ranking_methodology_id: 'generic_ranking_methodology_v1',
      ranking_as_of_date: '2026-05-01',
      current_portfolio_artifact_id: 'workspace_current_portfolio_1',
      current_portfolio_as_of_timestamp: '2026-04-10T00:00:00Z',
      policy_id: 'top_n_equal_weight_v1',
      policy_definition_id: 'construction_policy_definition_top_n_equal_weight_v1',
      top_n: 2,
    },
  }
}

const sampleCurrentPortfolio = {
  artifact_id: 'workspace_current_portfolio_1',
  as_of_timestamp: '2026-04-10T00:00:00Z',
  weights: [
    { symbol: 'AAPL', weight: 0.5 },
    { symbol: 'MSFT', weight: 0.5 },
  ],
}


describe('PersistedGenericRankingConstructionBrowser', () => {
  it('renders the browser header even without persisted artifacts', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
      if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
        return jsonResponse(buildGenericRecentResponse([]))
      }
      if (url.includes('/api/construction/policies') && method === 'GET') {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`)
    })

    render(
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={sampleCurrentPortfolio}
        onOpenConstructionReview={vi.fn()}
      />,
    )

    await screen.findByText('Persisted Generic Ranking Construction')
    await screen.findByText('No persisted generic rankings found.')
  })

  it('lists recent generic ranking artifacts after generalized discovery', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
      if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
        return jsonResponse(buildGenericRecentResponse())
      }
      if (url.includes('/api/construction/policies') && method === 'GET') {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.includes('/api/construction/ranking-artifacts/preflight/generic_ranking_artifact_abc123') && method === 'POST') {
        return jsonResponse(buildPreflightEligibleResponse())
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`)
    })

    render(
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={sampleCurrentPortfolio}
        onOpenConstructionReview={vi.fn()}
      />,
    )

    await screen.findByText('sp500_quality_v1') // universe_id column
    expect(screen.getByText('Index')).toBeTruthy() // index_constituent mapped to readable label
    expect(screen.queryByText('quality_v1')).toBeNull() // score_config_id not shown
    expect(screen.queryByText('generic_ranking_artifact_abc123')).toBeNull() // artifact_id not shown
  })

  it('rejects malformed discovery scope (not generic_ranking)', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
      if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
        return jsonResponse({
          items: [],
          metadata: { applied_filters: { artifact_kind: 'etf_ranking' } }, // wrong scope
        })
      }
      if (url.includes('/api/construction/policies') && method === 'GET') {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`)
    })

    render(
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={sampleCurrentPortfolio}
        onOpenConstructionReview={vi.fn()}
      />,
    )

    await screen.findByText(/Recent generic ranking runs returned unsupported discovery scope/)
  })

  it('rejects rows with the wrong artifact_kind in items', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
      if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
        const row = defaultGenericRow()
        row.artifact_kind = 'etf_ranking' // wrong row kind despite scope claim
        return jsonResponse(buildGenericRecentResponse([row]))
      }
      if (url.includes('/api/construction/policies') && method === 'GET') {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`)
    })

    render(
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={sampleCurrentPortfolio}
        onOpenConstructionReview={vi.fn()}
      />,
    )

    await screen.findByText(/Recent generic ranking runs returned non-generic artifact rows/)
  })

  it('blocks Review In Construction when there is no current portfolio', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
      if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
        return jsonResponse(buildGenericRecentResponse())
      }
      if (url.includes('/api/construction/policies') && method === 'GET') {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.includes('/api/construction/ranking-artifacts/preflight/generic_ranking_artifact_abc123') && method === 'POST') {
        return jsonResponse(buildPreflightEligibleResponse())
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`)
    })

    render(
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={null}
        onOpenConstructionReview={vi.fn()}
      />,
    )

    const browser = await screen.findByTestId('persisted-generic-ranking-construction-browser')
    await within(browser).findByText('sp500_quality_v1')
    const button = within(browser).getByRole('button', { name: 'Review In Construction' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(button.title).toContain('Open a workspace with an authoritative current portfolio')
  })

  it('hands off to construction and invokes onOpenConstructionReview with the new construction artifact id', async () => {
    const onOpenConstructionReview = vi.fn()

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
      if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
        return jsonResponse(buildGenericRecentResponse())
      }
      if (url.includes('/api/construction/policies') && method === 'GET') {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.includes('/api/construction/ranking-artifacts/preflight/generic_ranking_artifact_abc123') && method === 'POST') {
        return jsonResponse(buildPreflightEligibleResponse())
      }
      if (url.includes('/api/construction/run') && method === 'POST') {
        return jsonResponse(buildConstructionRunResponse())
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`)
    })

    render(
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={sampleCurrentPortfolio}
        onOpenConstructionReview={onOpenConstructionReview}
      />,
    )

    const browser = await screen.findByTestId('persisted-generic-ranking-construction-browser')
    await within(browser).findByText('sp500_quality_v1')
    // Wait for readiness check to complete and policy catalog to settle
    await waitFor(() => {
      const button = within(browser).getByRole('button', { name: 'Review In Construction' }) as HTMLButtonElement
      expect(button.disabled).toBe(false)
    })

    fireEvent.click(within(browser).getByRole('button', { name: 'Review In Construction' }))
    await waitFor(() => expect(onOpenConstructionReview).toHaveBeenCalledWith('construction_artifact_xyz789'))
  })

  it('surfaces ineligible preflight reason without enabling the CTA', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
      if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
        return jsonResponse(buildGenericRecentResponse())
      }
      if (url.includes('/api/construction/policies') && method === 'GET') {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.includes('/api/construction/ranking-artifacts/preflight/generic_ranking_artifact_abc123') && method === 'POST') {
        return jsonResponse({
          contract_version: 'construction_ranking_artifact_preflight_v1',
          artifact: {
            artifact_kind: 'generic_ranking',
            artifact_id: 'generic_ranking_artifact_abc123',
            schema_version: 'generic_ranking_artifact_v1',
            ranking_id: 'generic_ranking_engine_v1',
            methodology_id: 'generic_ranking_methodology_v1',
            as_of_date: '2026-05-01',
          },
          eligibility: {
            eligible: false,
            reason: 'persisted generic ranking artifact has no eligible ranked candidates for construction',
          },
          handoff: null,
        })
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`)
    })

    render(
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={sampleCurrentPortfolio}
        onOpenConstructionReview={vi.fn()}
      />,
    )

    const browser = await screen.findByTestId('persisted-generic-ranking-construction-browser')
    await within(browser).findByText(/persisted generic ranking artifact has no eligible ranked candidates for construction/)
    const button = within(browser).getByRole('button', { name: 'Review In Construction' }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
  })

  it('exposes a Top N input that defaults to 2 and rejects out-of-range values', async () => {
    // Epic 3 breadth: configurable top_n input. Default is 2; in-range values are
    // accepted (2..20); below-min and above-max values surface a validation error
    // that blocks the Review In Construction CTA.
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
      if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
        return jsonResponse(buildGenericRecentResponse())
      }
      if (url.includes('/api/construction/policies') && method === 'GET') {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.includes('/api/construction/ranking-artifacts/preflight/generic_ranking_artifact_abc123') && method === 'POST') {
        return jsonResponse(buildPreflightEligibleResponse())
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`)
    })

    render(
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={sampleCurrentPortfolio}
        onOpenConstructionReview={vi.fn()}
      />,
    )

    const browser = await screen.findByTestId('persisted-generic-ranking-construction-browser')
    const topNInput = await within(browser).findByLabelText('Generic Top N') as HTMLInputElement
    expect(topNInput.value).toBe('2') // default

    // In-range value (3) — no validation error, button can be enabled (subject to other gates)
    fireEvent.change(topNInput, { target: { value: '3' } })
    await waitFor(() => expect(within(browser).queryByText(/Top N must be/)).toBeNull())

    // Below-min value (1) — surfaces validation error
    // The error text appears twice: once in the field helper, once in the table-row blocked-reason small.
    fireEvent.change(topNInput, { target: { value: '1' } })
    await waitFor(() => expect(within(browser).getAllByText(/Top N must be between 2 and 20/).length).toBeGreaterThan(0))
    expect(
      (within(browser).getByRole('button', { name: 'Review In Construction' }) as HTMLButtonElement).disabled,
    ).toBe(true)

    // Above-max value (21) — surfaces same error
    fireEvent.change(topNInput, { target: { value: '21' } })
    await waitFor(() => expect(within(browser).getAllByText(/Top N must be between 2 and 20/).length).toBeGreaterThan(0))

    // Non-numeric — surfaces a different error
    fireEvent.change(topNInput, { target: { value: 'xyz' } })
    await waitFor(() => expect(within(browser).getAllByText(/Top N must be a whole number/).length).toBeGreaterThan(0))
  })

  it('exposes an optional Max Sector Weight input that validates against max position weight', async () => {
    // Epic 3 breadth (milestone slice 3): optional max_sector_weight input.
    // Blank by default (omitted from the request); when set it must be a decimal
    // in (0, 1] and no lower than max position weight (default 0.60).
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
      if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
        return jsonResponse(buildGenericRecentResponse())
      }
      if (url.includes('/api/construction/policies') && method === 'GET') {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.includes('/api/construction/ranking-artifacts/preflight/generic_ranking_artifact_abc123') && method === 'POST') {
        return jsonResponse(buildPreflightEligibleResponse())
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`)
    })

    render(
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={sampleCurrentPortfolio}
        onOpenConstructionReview={vi.fn()}
      />,
    )

    const browser = await screen.findByTestId('persisted-generic-ranking-construction-browser')
    const sectorInput = await within(browser).findByLabelText('Generic Max Sector Weight (optional)') as HTMLInputElement
    expect(sectorInput.value).toBe('') // blank default — omitted from the request

    // Valid: 0.80 is >= max position weight (0.60) and <= 1 — no validation error.
    fireEvent.change(sectorInput, { target: { value: '0.80' } })
    await waitFor(() => expect(within(browser).queryByText(/Max sector weight/)).toBeNull())

    // Below max position weight (0.50 < 0.60) — surfaces the invariant error.
    fireEvent.change(sectorInput, { target: { value: '0.50' } })
    await waitFor(() => expect(
      within(browser).getAllByText(/Max sector weight must be greater than or equal to max position weight/).length,
    ).toBeGreaterThan(0))
    expect(
      (within(browser).getByRole('button', { name: 'Review In Construction' }) as HTMLButtonElement).disabled,
    ).toBe(true)

    // Above 1 — surfaces the upper-bound error.
    fireEvent.change(sectorInput, { target: { value: '1.5' } })
    await waitFor(() => expect(
      within(browser).getAllByText(/Max sector weight must be less than or equal to 1/).length,
    ).toBeGreaterThan(0))

    // Non-numeric — surfaces the format error.
    fireEvent.change(sectorInput, { target: { value: 'abc' } })
    await waitFor(() => expect(
      within(browser).getAllByText(/Enter a numeric max sector weight/).length,
    ).toBeGreaterThan(0))
  })

  it('sends a non-default top_n and max_sector_weight in the construction run request', async () => {
    // Verifies (a) the configurable-top_n handoff path works end-to-end for a
    // non-2 top_n (a latent bug fixed in this slice — the handoff runner
    // previously hard-rejected top_n != 2), and (b) max_sector_weight is
    // threaded into hard_constraints.
    const onOpenConstructionReview = vi.fn()
    let capturedRunBody: Record<string, unknown> | null = null

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
      if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
        return jsonResponse(buildGenericRecentResponse())
      }
      if (url.includes('/api/construction/policies') && method === 'GET') {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.includes('/api/construction/ranking-artifacts/preflight/generic_ranking_artifact_abc123') && method === 'POST') {
        return jsonResponse(buildPreflightEligibleResponse())
      }
      if (url.includes('/api/construction/run') && method === 'POST') {
        capturedRunBody = JSON.parse(String(init?.body)) as Record<string, unknown>
        const runResponse = buildConstructionRunResponse()
        // The run echoes back the requested top_n; the handoff lineage check
        // requires normalized_inputs.top_n === requested policy.top_n.
        runResponse.normalized_inputs.top_n = 5
        return jsonResponse(runResponse)
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`)
    })

    render(
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={sampleCurrentPortfolio}
        onOpenConstructionReview={onOpenConstructionReview}
      />,
    )

    const browser = await screen.findByTestId('persisted-generic-ranking-construction-browser')
    await within(browser).findByText('sp500_quality_v1')
    fireEvent.change(within(browser).getByLabelText('Generic Top N') as HTMLInputElement, { target: { value: '5' } })
    fireEvent.change(within(browser).getByLabelText('Generic Max Sector Weight (optional)') as HTMLInputElement, { target: { value: '0.80' } })
    await waitFor(() => {
      const button = within(browser).getByRole('button', { name: 'Review In Construction' }) as HTMLButtonElement
      expect(button.disabled).toBe(false)
    })

    fireEvent.click(within(browser).getByRole('button', { name: 'Review In Construction' }))
    await waitFor(() => expect(onOpenConstructionReview).toHaveBeenCalledWith('construction_artifact_xyz789'))

    expect(capturedRunBody).not.toBeNull()
    const policy = (capturedRunBody as Record<string, unknown>).policy as Record<string, unknown>
    const hardConstraints = (capturedRunBody as Record<string, unknown>).hard_constraints as Record<string, unknown>
    expect(policy.top_n).toBe(5)
    expect(hardConstraints.max_sector_weight).toBe(0.8)
  })

  it('renders plain-English column headers and hides internal identifiers', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url
      const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
      if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
        return jsonResponse(buildGenericRecentResponse())
      }
      if (url.includes('/api/construction/policies') && method === 'GET') {
        return jsonResponse(buildConstructionPoliciesResponse())
      }
      if (url.includes('/api/construction/ranking-artifacts/preflight/generic_ranking_artifact_abc123') && method === 'POST') {
        return jsonResponse(buildPreflightEligibleResponse())
      }
      throw new Error(`Unhandled fetch: ${method} ${url}`)
    })

    render(
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={sampleCurrentPortfolio}
        onOpenConstructionReview={vi.fn()}
      />,
    )

    const browser = await screen.findByTestId('persisted-generic-ranking-construction-browser')
    await within(browser).findByText('sp500_quality_v1')

    expect(within(browser).getByText('Ranked On')).toBeTruthy()
    expect(within(browser).getByText('Type')).toBeTruthy()
    expect(within(browser).getByText('# Ranked')).toBeTruthy()
    expect(within(browser).queryByText('Basis Date')).toBeNull()
    expect(within(browser).queryByText('Score Config')).toBeNull()
    expect(within(browser).queryByText('Artifact')).toBeNull()
  })

  it('maps universe_kind enum values to readable labels', async () => {
    const universeKindCases: Array<{ kind: string; label: string }> = [
      { kind: 'index_constituent', label: 'Index' },
      { kind: 'etf_peer_group', label: 'ETF Peer Group' },
      { kind: 'custom_list', label: 'Custom List' },
      { kind: 'broad_equity_screen', label: 'Screened' },
      { kind: 'sector_screen', label: 'Sector Screen' },
    ]

    for (const { kind, label } of universeKindCases) {
      cleanup()
      vi.restoreAllMocks()
      const base = defaultGenericRow()
      const row = { ...base, generic_summary: { ...base.generic_summary, universe_kind: kind } }

      vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
        const url = typeof input === 'string' ? input : (input as Request).url
        const method = init?.method ?? (input instanceof Request ? input.method : 'GET')
        if (url.includes('/api/strategy-lab/ranking-artifacts/recent?artifact_kind=generic_ranking') && method === 'GET') {
          return jsonResponse(buildGenericRecentResponse([row]))
        }
        if (url.includes('/api/construction/policies') && method === 'GET') {
          return jsonResponse(buildConstructionPoliciesResponse())
        }
        if (url.includes('/api/construction/ranking-artifacts/preflight/generic_ranking_artifact_abc123') && method === 'POST') {
          return jsonResponse(buildPreflightEligibleResponse())
        }
        throw new Error(`Unhandled fetch: ${method} ${url}`)
      })

      render(
        <PersistedGenericRankingConstructionBrowser
          currentPortfolio={sampleCurrentPortfolio}
          onOpenConstructionReview={vi.fn()}
        />,
      )

      const browser = await screen.findByTestId('persisted-generic-ranking-construction-browser')
      await within(browser).findByText('sp500_quality_v1')
      expect(within(browser).getByText(label)).toBeTruthy()
      expect(within(browser).queryByText(kind)).toBeNull()
    }
  })
})
