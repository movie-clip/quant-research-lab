import { useEffect, useMemo, useState } from 'react'

import type {
  ConstructionDiscoveredPolicy,
  ConstructionPolicyRunInput,
} from '../portfolio/types'

const DESKTOP_CONSTRUCTION_POLICY_FILTERS = {
  constraints: 'long_only_fully_invested_max_position_turnover',
  inputs: 'ranked_universe_and_current_portfolio',
  determinism: 'deterministic_rank_order',
  full_investment_constraint: 'required',
  long_only_constraint: 'required',
  eligible_ranked_universe_constraint: 'required',
  max_position_weight_constraint: 'required',
  min_position_weight_constraint: 'supported_optional',
  max_turnover_weight_constraint: 'supported_optional',
  max_trade_intent_count_constraint: 'supported_optional',
  ranked_universe_input: 'required',
  current_portfolio_input: 'required',
  launch_top_n: '2',
} as const

export const RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N = 2 as const

const SUPPORTED_POLICY_IDS = new Set([
  'top_n_equal_weight_v1',
  'top_n_inverse_rank_weight_v1',
  'top_n_linear_rank_weight_v1',
])

const SUPPORTED_POLICY_SPECS = {
  top_n_equal_weight_v1: {
    policy_definition_id: 'construction_policy_definition_top_n_equal_weight_v1',
    family: 'top_n_equal_weight',
    ranking_support: 'selection_only',
  },
  top_n_inverse_rank_weight_v1: {
    policy_definition_id: 'construction_policy_definition_top_n_inverse_rank_weight_v1',
    family: 'top_n_rank_weighted',
    ranking_support: 'inverse_selected_order_weighting',
  },
  top_n_linear_rank_weight_v1: {
    policy_definition_id: 'construction_policy_definition_top_n_linear_rank_weight_v1',
    family: 'top_n_rank_weighted',
    ranking_support: 'linear_selected_order_weighting',
  },
} as const

export function resolvePolicyDefinitionIdForPolicyId(policyId: string): string | null {
  return SUPPORTED_POLICY_SPECS[policyId as keyof typeof SUPPORTED_POLICY_SPECS]?.policy_definition_id ?? null
}

const SUPPORTED_RANKING_SUPPORT = new Set([
  'selection_only',
  'inverse_selected_order_weighting',
  'linear_selected_order_weighting',
])

const REQUIRED_SELECTION_RULE_IDS = ['eligible_only', 'take_top_n'] as const

type ConstructionPolicyCatalogState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  policies: ConstructionDiscoveredPolicy[]
  error: string | null
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value != null
}

async function readJsonResponse<T>(response: Response, fallbackMessage: string) {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(typeof payload === 'object' && payload != null && 'detail' in payload && typeof payload.detail === 'string' ? payload.detail : fallbackMessage)
  }
  return payload as T
}

function validateExactField<T extends string>(
  row: Record<string, unknown>,
  field: string,
  expected: T,
): T {
  const value = row[field]
  if (value !== expected) {
    throw new Error(`Construction policy catalog row has unsupported ${field}`)
  }
  return value as T
}

function parseConstructionPolicyRow(payload: unknown): ConstructionDiscoveredPolicy {
  if (!isObject(payload)) {
    throw new Error('Construction policy catalog returned a malformed row')
  }
  const policyId = payload.policy_id
  if (typeof policyId !== 'string' || !policyId.trim() || !SUPPORTED_POLICY_IDS.has(policyId)) {
    throw new Error('Construction policy catalog returned an unsupported policy_id')
  }
  const expectedPolicySpec = SUPPORTED_POLICY_SPECS[policyId as keyof typeof SUPPORTED_POLICY_SPECS]
  const policyDefinitionId = payload.policy_definition_id
  if (typeof policyDefinitionId !== 'string' || policyDefinitionId !== expectedPolicySpec.policy_definition_id) {
    throw new Error('Construction policy catalog returned an unsupported policy_definition_id')
  }
  const name = payload.name
  if (typeof name !== 'string' || !name.trim()) {
    throw new Error('Construction policy catalog returned a malformed policy name')
  }
  const description = payload.description
  if (typeof description !== 'string' || !description.trim()) {
    throw new Error('Construction policy catalog returned a malformed policy description')
  }
  const family = payload.family
  if (typeof family !== 'string') {
    throw new Error('Construction policy catalog returned an unsupported policy family')
  }
  const rankingSupport = payload.ranking_support
  if (typeof rankingSupport !== 'string') {
    throw new Error('Construction policy catalog returned an unsupported ranking_support')
  }
  if (family !== expectedPolicySpec.family) {
    throw new Error('Construction policy catalog returned an unsupported policy family')
  }
  if (!SUPPORTED_RANKING_SUPPORT.has(rankingSupport)) {
    throw new Error('Construction policy catalog returned an unsupported ranking_support')
  }
  if (rankingSupport !== expectedPolicySpec.ranking_support) {
    throw new Error('Construction policy catalog returned policy metadata inconsistent with policy_id')
  }
  if (!Array.isArray(payload.selection_rule_ids) || payload.selection_rule_ids.length !== REQUIRED_SELECTION_RULE_IDS.length) {
    throw new Error('Construction policy catalog returned malformed selection_rule_ids')
  }
  const selectionRuleIds = payload.selection_rule_ids.map((value) => {
    if (typeof value !== 'string' || !value.trim()) {
      throw new Error('Construction policy catalog returned malformed selection_rule_ids')
    }
    return value
  })
  if (selectionRuleIds.some((value, index) => value !== REQUIRED_SELECTION_RULE_IDS[index])) {
    throw new Error('Construction policy catalog returned unsupported selection_rule_ids')
  }
  if (payload.launch_top_n !== RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N) {
    throw new Error('Construction policy catalog returned an unsupported launch_top_n')
  }

  return {
    policy_id: policyId,
    policy_definition_id: policyDefinitionId,
    name,
    description,
    family,
    constraints: validateExactField(payload, 'constraints', DESKTOP_CONSTRUCTION_POLICY_FILTERS.constraints),
    inputs: validateExactField(payload, 'inputs', DESKTOP_CONSTRUCTION_POLICY_FILTERS.inputs),
    determinism: validateExactField(payload, 'determinism', DESKTOP_CONSTRUCTION_POLICY_FILTERS.determinism),
    ranking_support: rankingSupport as ConstructionDiscoveredPolicy['ranking_support'],
    full_investment_constraint: validateExactField(payload, 'full_investment_constraint', DESKTOP_CONSTRUCTION_POLICY_FILTERS.full_investment_constraint),
    long_only_constraint: validateExactField(payload, 'long_only_constraint', DESKTOP_CONSTRUCTION_POLICY_FILTERS.long_only_constraint),
    eligible_ranked_universe_constraint: validateExactField(payload, 'eligible_ranked_universe_constraint', DESKTOP_CONSTRUCTION_POLICY_FILTERS.eligible_ranked_universe_constraint),
    max_position_weight_constraint: validateExactField(payload, 'max_position_weight_constraint', DESKTOP_CONSTRUCTION_POLICY_FILTERS.max_position_weight_constraint),
    min_position_weight_constraint: validateExactField(payload, 'min_position_weight_constraint', DESKTOP_CONSTRUCTION_POLICY_FILTERS.min_position_weight_constraint),
    max_turnover_weight_constraint: validateExactField(payload, 'max_turnover_weight_constraint', DESKTOP_CONSTRUCTION_POLICY_FILTERS.max_turnover_weight_constraint),
    max_trade_intent_count_constraint: validateExactField(payload, 'max_trade_intent_count_constraint', DESKTOP_CONSTRUCTION_POLICY_FILTERS.max_trade_intent_count_constraint),
    ranked_universe_input: validateExactField(payload, 'ranked_universe_input', DESKTOP_CONSTRUCTION_POLICY_FILTERS.ranked_universe_input),
    current_portfolio_input: validateExactField(payload, 'current_portfolio_input', DESKTOP_CONSTRUCTION_POLICY_FILTERS.current_portfolio_input),
    launch_top_n: RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N,
    selection_rule_ids: selectionRuleIds,
  }
}

export function parseConstructionPolicyCatalog(payload: unknown): ConstructionDiscoveredPolicy[] {
  if (!Array.isArray(payload)) {
    throw new Error('Construction policy catalog returned a malformed payload')
  }
  const parsed = payload.map(parseConstructionPolicyRow)
  const seenPolicyIds = new Set<string>()
  const seenDefinitionIds = new Set<string>()
  for (const policy of parsed) {
    if (seenPolicyIds.has(policy.policy_id)) {
      throw new Error('Construction policy catalog returned duplicate policy_id rows')
    }
    if (seenDefinitionIds.has(policy.policy_definition_id)) {
      throw new Error('Construction policy catalog returned duplicate policy_definition_id rows')
    }
    seenPolicyIds.add(policy.policy_id)
    seenDefinitionIds.add(policy.policy_definition_id)
  }
  return parsed
}

export function buildConstructionPolicyCatalogUrl(apiBase = '/api') {
  const search = new URLSearchParams(DESKTOP_CONSTRUCTION_POLICY_FILTERS)
  return `${apiBase}/construction/policies?${search.toString()}`
}

export function useConstructionPolicyCatalog(apiBase = '/api') {
  const [state, setState] = useState<ConstructionPolicyCatalogState>({
    status: 'idle',
    policies: [],
    error: null,
  })

  useEffect(() => {
    let active = true
    setState({ status: 'loading', policies: [], error: null })
    void (async () => {
      try {
        const response = await fetch(buildConstructionPolicyCatalogUrl(apiBase))
        const payload = await readJsonResponse<unknown>(response, 'Construction policy catalog is unavailable')
        const policies = parseConstructionPolicyCatalog(payload)
        if (!active) return
        setState({ status: 'ready', policies, error: null })
      } catch (caught) {
        if (!active) return
        setState({ status: 'error', policies: [], error: caught instanceof Error ? caught.message : 'Construction policy catalog is unavailable' })
      }
    })()
    return () => {
      active = false
    }
  }, [apiBase])

  const defaultPolicyId = useMemo(() => (
    state.policies.some((policy) => policy.policy_id === 'top_n_equal_weight_v1')
      ? 'top_n_equal_weight_v1'
      : null
  ), [state.policies])

  return {
    ...state,
    defaultPolicyId,
  }
}

export function buildConstructionPolicyRunInput(policyId: string | null, topN: number): ConstructionPolicyRunInput | null {
  if (!policyId) return null
  if (topN !== RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N) {
    throw new Error('Ranking artifact construction launch only supports top_n=2')
  }
  return { policy_id: policyId, top_n: topN }
}
