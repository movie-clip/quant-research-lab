import type {
  ConstructionArtifactRunResponse,
  ConstructionPolicyRunInput,
  ConstructionRankingArtifactHandoff,
  ConstructionRankingArtifactPreflightResponse,
} from '../portfolio/types'
import {
  RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N,
  resolvePolicyDefinitionIdForPolicyId,
} from './constructionPolicyCatalog'

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

function assertValidConstructionRankingArtifactPreflight(
  payload: unknown,
  expectedArtifactId: string,
): ConstructionRankingArtifactPreflightResponse {
  if (!isObject(payload)) {
    throw new Error('Ranking artifact construction preflight returned a malformed payload')
  }
  const contractVersion = payload.contract_version
  if (contractVersion !== 'construction_ranking_artifact_preflight_v1') {
    throw new Error('Ranking artifact construction preflight returned an unsupported contract version')
  }
  const artifact = payload.artifact
  const eligibility = payload.eligibility
  const handoff = payload.handoff
  if (!isObject(artifact) || !isObject(eligibility)) {
    throw new Error('Ranking artifact construction preflight returned malformed artifact eligibility state')
  }
  if (!['etf_ranking', 'intent_bound_etf_replacement_ranking'].includes(String(artifact.artifact_kind))) {
    throw new Error('Ranking artifact construction preflight returned an unsupported artifact kind')
  }
  if (!['etf_ranking_artifact_v1', 'intent_bound_etf_replacement_ranking_artifact_v1'].includes(String(artifact.schema_version))) {
    throw new Error('Ranking artifact construction preflight returned an unsupported schema version')
  }
  if (typeof artifact.artifact_id !== 'string' || artifact.artifact_id !== expectedArtifactId) {
    throw new Error('Ranking artifact construction preflight returned a mismatched artifact identity')
  }
  if (typeof artifact.ranking_id !== 'string' || typeof artifact.methodology_id !== 'string' || typeof artifact.as_of_date !== 'string') {
    throw new Error('Ranking artifact construction preflight returned malformed artifact lineage')
  }
  if (typeof eligibility.eligible !== 'boolean') {
    throw new Error('Ranking artifact construction preflight returned malformed eligibility state')
  }
  if (eligibility.eligible) {
    if (eligibility.reason !== null) {
      throw new Error('Ranking artifact construction preflight returned malformed eligible reason state')
    }
    if (!isObject(handoff)) {
      throw new Error('Ranking artifact construction preflight returned malformed artifact handoff state')
    }
  } else {
    if (typeof eligibility.reason !== 'string' || !eligibility.reason.trim()) {
      throw new Error('Ranking artifact construction preflight returned malformed ineligibility reason')
    }
    if (handoff != null) {
      throw new Error('Ranking artifact construction preflight returned handoff for an ineligible artifact')
    }
    return payload as ConstructionRankingArtifactPreflightResponse
  }
  if (![
    'etf_ranking_artifact_construction_handoff_v1',
    'intent_bound_etf_replacement_ranking_artifact_construction_handoff_v1',
  ].includes(String(handoff.handoff_kind))) {
    throw new Error('Ranking artifact construction preflight returned an unsupported handoff kind')
  }
  if (handoff.artifact_kind !== artifact.artifact_kind || handoff.schema_version !== artifact.schema_version) {
    throw new Error('Ranking artifact construction preflight returned a mismatched handoff contract')
  }
  if (
    handoff.artifact_id !== artifact.artifact_id
    || handoff.ranking_id !== artifact.ranking_id
    || handoff.methodology_id !== artifact.methodology_id
    || handoff.as_of_date !== artifact.as_of_date
  ) {
    throw new Error('Ranking artifact construction preflight returned a mismatched handoff identity')
  }
  return payload as ConstructionRankingArtifactPreflightResponse
}

function assertConstructionRunMatchesHandoff(
  payload: unknown,
  handoff: ConstructionRankingArtifactHandoff,
  requestedCurrentPortfolio: {
    artifact_id: string
    as_of_timestamp: string
  },
  requestedPolicy: ConstructionPolicyRunInput,
): ConstructionArtifactRunResponse {
  if (!isObject(payload)) {
    throw new Error('Ranking artifact construction run returned a malformed payload')
  }
  if (payload.schema_version !== 'construction_artifact_v1') {
    throw new Error('Ranking artifact construction run returned an unsupported construction artifact schema version')
  }
  if (typeof payload.artifact_id !== 'string' || !payload.artifact_id.trim()) {
    throw new Error('Ranking artifact construction run returned a malformed construction artifact identity')
  }
  const normalizedInputs = payload.normalized_inputs
  if (!isObject(normalizedInputs)) {
    throw new Error('Ranking artifact construction run returned malformed lineage inputs')
  }
  if (normalizedInputs.ranked_universe_artifact_kind !== handoff.artifact_kind) {
    throw new Error('Ranking artifact construction run lineage returned a mismatched ranking artifact kind')
  }
  if (normalizedInputs.ranked_universe_artifact_schema_version !== handoff.schema_version) {
    throw new Error('Ranking artifact construction run lineage returned a mismatched ranking artifact schema version')
  }
  if (normalizedInputs.ranked_universe_artifact_id !== handoff.artifact_id) {
    throw new Error('Ranking artifact construction run lineage returned a mismatched ranking artifact identity')
  }
  if (normalizedInputs.ranking_id !== handoff.ranking_id) {
    throw new Error('Ranking artifact construction run lineage returned a mismatched ranking id')
  }
  if (normalizedInputs.ranking_methodology_id !== handoff.methodology_id) {
    throw new Error('Ranking artifact construction run lineage returned a mismatched ranking methodology id')
  }
  if (normalizedInputs.ranking_as_of_date !== handoff.as_of_date) {
    throw new Error('Ranking artifact construction run lineage returned a mismatched ranking as_of_date')
  }
  if (normalizedInputs.current_portfolio_artifact_id !== requestedCurrentPortfolio.artifact_id) {
    throw new Error('Ranking artifact construction run lineage returned a mismatched current portfolio identity')
  }
  if (normalizedInputs.current_portfolio_as_of_timestamp !== requestedCurrentPortfolio.as_of_timestamp) {
    throw new Error('Ranking artifact construction run lineage returned a mismatched current portfolio timestamp')
  }
  if (normalizedInputs.policy_id !== requestedPolicy.policy_id) {
    throw new Error('Ranking artifact construction run lineage returned a mismatched policy_id')
  }
  const expectedPolicyDefinitionId = resolvePolicyDefinitionIdForPolicyId(requestedPolicy.policy_id)
  if (!expectedPolicyDefinitionId) {
    throw new Error('Ranking artifact construction launch requested an unsupported policy_id')
  }
  if (normalizedInputs.policy_definition_id !== expectedPolicyDefinitionId) {
    throw new Error('Ranking artifact construction run lineage returned a mismatched policy_definition_id')
  }
  if (normalizedInputs.top_n !== RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N) {
    throw new Error('Ranking artifact construction run lineage returned unsupported top_n for launch boundary')
  }
  return payload as ConstructionArtifactRunResponse
}

export async function runRankingArtifactConstructionHandoff(params: {
  apiBase?: string
  artifactId: string
  maxPositionWeight: number
  minPositionWeight?: number | null
  maxTurnoverWeight?: number | null
  maxTradeIntentCount?: number | null
  currentPortfolio: {
    artifact_id: string
    as_of_timestamp: string
    weights: Array<{ symbol: string; weight: number }>
  }
  policy: ConstructionPolicyRunInput
}) {
  const apiBase = params.apiBase ?? '/api'
  if (params.policy.top_n !== RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N) {
    throw new Error('Ranking artifact construction launch only supports top_n=2')
  }
  const preflightResponse = await fetch(`${apiBase}/construction/ranking-artifacts/preflight/${encodeURIComponent(params.artifactId)}`, {
    method: 'POST',
  })
  const preflightPayload = await readJsonResponse<unknown>(preflightResponse, 'Ranking artifact construction preflight failed')
  const preflight = assertValidConstructionRankingArtifactPreflight(preflightPayload, params.artifactId)
  if (!preflight.eligibility.eligible || !preflight.handoff) {
    throw new Error(preflight.eligibility.reason ?? 'Ranking artifact construction preflight returned an ineligible artifact')
  }
  const runResponse = await fetch(`${apiBase}/construction/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      request_id: `desktop_ranking_artifact_handoff_${Date.now()}`,
      ranking_artifact_handoff: preflight.handoff,
      current_portfolio: params.currentPortfolio,
      policy: params.policy,
      hard_constraints: {
        full_investment: true,
        long_only: true,
        eligible_ranked_universe_only: true,
        max_position_weight: params.maxPositionWeight,
        ...(params.minPositionWeight != null ? { min_position_weight: params.minPositionWeight } : {}),
        ...(params.maxTurnoverWeight != null ? { max_turnover_weight: params.maxTurnoverWeight } : {}),
        ...(params.maxTradeIntentCount != null ? { max_trade_intent_count: params.maxTradeIntentCount } : {}),
      },
    }),
  })
  const runPayload = await readJsonResponse<unknown>(runResponse, 'Ranking artifact construction run failed')
  const run = assertConstructionRunMatchesHandoff(runPayload, preflight.handoff, params.currentPortfolio, params.policy)
  return { preflight, run }
}
