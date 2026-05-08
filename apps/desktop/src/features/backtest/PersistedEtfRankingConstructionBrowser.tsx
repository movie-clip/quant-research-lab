import { useEffect, useMemo, useRef, useState } from 'react'

import {
  buildConstructionPolicyRunInput,
  RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N,
  useConstructionPolicyCatalog,
} from './constructionPolicyCatalog'
import {
  DEFAULT_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT,
  DEFAULT_RANKING_CONSTRUCTION_MIN_POSITION_WEIGHT,
  validateRankingConstructionPositionWeightInputs,
} from './rankingConstructionMaxPositionWeight'
import { runRankingArtifactConstructionHandoff } from './rankingArtifactConstructionHandoff'
import type {
  ConstructionRankingArtifactPreflightResponse,
  EtfRankingArtifactRecentRow,
} from '../portfolio/types'

type GeneralizedEtfRecentResponse = {
  items?: Array<{
    artifact_kind?: unknown
    artifact_id?: unknown
    ranking_id?: unknown
    methodology_id?: unknown
    as_of_date?: unknown
    ranking_basis_date?: unknown
    etf_summary?: {
      benchmark_symbol?: unknown
      lookback_months?: unknown
      effective_peer_group?: unknown
      universe_size?: unknown
      evaluated_universe_size?: unknown
      confidence?: unknown
    } | null
    replacement_summary?: unknown
  }>
  metadata?: {
    applied_filters?: {
      artifact_kind?: unknown
    }
  }
}

type RecentState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  items: EtfRankingArtifactRecentRow[]
  error: string | null
}

type HandoffState = {
  status: 'idle' | 'running' | 'error'
  targetArtifactId: string | null
  error: string | null
}

type ReadinessEntry = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  response: ConstructionRankingArtifactPreflightResponse | null
  error: string | null
}

type ReadinessState = Record<string, ReadinessEntry>

function parseEtfRecentRunsFromGeneralizedResponse(payload: GeneralizedEtfRecentResponse): EtfRankingArtifactRecentRow[] {
  if (payload.metadata?.applied_filters?.artifact_kind !== 'etf_ranking') {
    throw new Error('Recent ETF ranking runs returned unsupported discovery scope')
  }
  if (!Array.isArray(payload.items)) {
    throw new Error('Recent ETF ranking runs returned malformed discovery payload')
  }
  return payload.items.map((item) => {
    if (item.artifact_kind !== 'etf_ranking') {
      throw new Error('Recent ETF ranking runs returned non-ETF artifact rows')
    }
    if (item.replacement_summary != null || !item.etf_summary) {
      throw new Error('Recent ETF ranking runs returned malformed ETF summaries')
    }
    const summary = item.etf_summary
    if (
      typeof item.artifact_id !== 'string'
      || typeof item.ranking_id !== 'string'
      || typeof item.methodology_id !== 'string'
      || typeof item.as_of_date !== 'string'
      || typeof item.ranking_basis_date !== 'string'
      || typeof summary.benchmark_symbol !== 'string'
      || typeof summary.lookback_months !== 'number'
      || !(typeof summary.effective_peer_group === 'string' || summary.effective_peer_group === null)
      || typeof summary.universe_size !== 'number'
      || typeof summary.evaluated_universe_size !== 'number'
      || !['high', 'medium', 'low'].includes(String(summary.confidence))
    ) {
      throw new Error('Recent ETF ranking runs returned invalid ETF row metadata')
    }
    return {
      artifact_id: item.artifact_id,
      ranking_id: item.ranking_id,
      methodology_id: item.methodology_id,
      as_of_date: item.as_of_date,
      ranking_basis_date: item.ranking_basis_date,
      benchmark_symbol: summary.benchmark_symbol,
      lookback_months: summary.lookback_months,
      universe_size: summary.universe_size,
      evaluated_universe_size: summary.evaluated_universe_size,
      effective_peer_group: summary.effective_peer_group,
      confidence: summary.confidence as 'high' | 'medium' | 'low',
    }
  })
}

async function readJsonResponse<T>(response: Response, fallbackMessage: string) {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(typeof payload === 'object' && payload != null && 'detail' in payload && typeof payload.detail === 'string' ? payload.detail : fallbackMessage)
  }
  return payload as T
}

function policyNameForReview(policyId: string, policies: Array<{ policy_id: string; name: string }>) {
  return policies.find((policy) => policy.policy_id === policyId)?.name ?? policyId
}

export function PersistedEtfRankingConstructionBrowser({
  currentPortfolio,
  onOpenRankingReview,
  onOpenConstructionReview,
}: {
  currentPortfolio: {
    artifact_id: string
    as_of_timestamp: string
    weights: Array<{ symbol: string; weight: number }>
  } | null
  onOpenRankingReview: (artifactId: string) => void | Promise<void>
  onOpenConstructionReview: (constructionArtifactId: string) => void | Promise<void>
}) {
  const apiBase = '/api'
  const constructionPolicyCatalog = useConstructionPolicyCatalog(apiBase)
  const recentRequestOwnerRef = useRef(0)
  const actionRequestOwnerRef = useRef(0)
  const [recentState, setRecentState] = useState<RecentState>({ status: 'idle', items: [], error: null })
  const [handoffState, setHandoffState] = useState<HandoffState>({ status: 'idle', targetArtifactId: null, error: null })
  const [readinessState, setReadinessState] = useState<ReadinessState>({})
  const [selectedConstructionPolicyId, setSelectedConstructionPolicyId] = useState<string>('')
  const [constructionMaxPositionWeight, setConstructionMaxPositionWeight] = useState(DEFAULT_RANKING_CONSTRUCTION_MAX_POSITION_WEIGHT)
  const [constructionMinPositionWeight, setConstructionMinPositionWeight] = useState(DEFAULT_RANKING_CONSTRUCTION_MIN_POSITION_WEIGHT)
  const constructionPositionWeightValidation = useMemo(
    () => validateRankingConstructionPositionWeightInputs({
      maxPositionWeightInput: constructionMaxPositionWeight,
      minPositionWeightInput: constructionMinPositionWeight,
    }),
    [constructionMaxPositionWeight, constructionMinPositionWeight],
  )
  const constructionMaxPositionWeightValidation = constructionPositionWeightValidation.maxPositionWeight
  const constructionMinPositionWeightValidation = constructionPositionWeightValidation.minPositionWeight

  useEffect(() => {
    if (constructionPolicyCatalog.status !== 'ready') return
    setSelectedConstructionPolicyId((current) => {
      if (current && constructionPolicyCatalog.policies.some((policy) => policy.policy_id === current)) {
        return current
      }
      return constructionPolicyCatalog.defaultPolicyId ?? ''
    })
  }, [constructionPolicyCatalog.defaultPolicyId, constructionPolicyCatalog.policies, constructionPolicyCatalog.status])

  async function loadConstructionReadiness(artifactId: string) {
    setReadinessState((current) => ({
      ...current,
      [artifactId]: { status: 'loading', response: null, error: null },
    }))
    try {
      const response = await fetch(`${apiBase}/construction/ranking-artifacts/preflight/${encodeURIComponent(artifactId)}`, {
        method: 'POST',
      })
      const payload = await readJsonResponse<ConstructionRankingArtifactPreflightResponse>(response, 'ETF ranking construction readiness is unavailable')
      setReadinessState((current) => ({
        ...current,
        [artifactId]: { status: 'ready', response: payload, error: null },
      }))
    } catch (caught) {
      setReadinessState((current) => ({
        ...current,
        [artifactId]: { status: 'error', response: null, error: caught instanceof Error ? caught.message : 'ETF ranking construction readiness is unavailable' },
      }))
    }
  }

  async function loadRecentArtifacts() {
    const owner = recentRequestOwnerRef.current + 1
    recentRequestOwnerRef.current = owner
    setRecentState((current) => ({ ...current, status: 'loading', error: null }))
    try {
      const response = await fetch(`${apiBase}/strategy-lab/ranking-artifacts/recent?artifact_kind=etf_ranking`)
      const payload = await readJsonResponse<GeneralizedEtfRecentResponse>(response, 'Recent ETF ranking artifacts are unavailable')
      const items = parseEtfRecentRunsFromGeneralizedResponse(payload)
      if (recentRequestOwnerRef.current !== owner) return
      setRecentState({ status: 'ready', items, error: null })
      void Promise.all(items.map(async (item) => loadConstructionReadiness(item.artifact_id)))
    } catch (caught) {
      if (recentRequestOwnerRef.current !== owner) return
      setRecentState({ status: 'error', items: [], error: caught instanceof Error ? caught.message : 'Recent ETF ranking artifacts are unavailable' })
    }
  }

  useEffect(() => {
    void loadRecentArtifacts()
  }, [])

  async function reviewInConstruction(artifactId: string) {
    if (constructionMaxPositionWeightValidation.value == null) {
      setHandoffState({ status: 'error', targetArtifactId: artifactId, error: constructionMaxPositionWeightValidation.error })
      return
    }
    if (constructionMinPositionWeightValidation.error) {
      setHandoffState({ status: 'error', targetArtifactId: artifactId, error: constructionMinPositionWeightValidation.error })
      return
    }
    if (!currentPortfolio) {
      setHandoffState({ status: 'error', targetArtifactId: artifactId, error: 'Review In Construction requires an active workspace draft and current portfolio.' })
      return
    }
    const selectedPolicy = buildConstructionPolicyRunInput(
      selectedConstructionPolicyId,
      RANKING_ARTIFACT_CONSTRUCTION_LAUNCH_TOP_N,
    )
    if (!selectedPolicy) {
      setHandoffState({ status: 'error', targetArtifactId: artifactId, error: 'Review In Construction requires selecting a compatible construction policy.' })
      return
    }
    const owner = actionRequestOwnerRef.current + 1
    actionRequestOwnerRef.current = owner
    setHandoffState({ status: 'running', targetArtifactId: artifactId, error: null })
    try {
      const result = await runRankingArtifactConstructionHandoff({
        apiBase,
        artifactId,
        maxPositionWeight: constructionMaxPositionWeightValidation.value,
        minPositionWeight: constructionMinPositionWeightValidation.value,
        currentPortfolio,
        policy: selectedPolicy,
      })
      if (actionRequestOwnerRef.current !== owner) return
      await onOpenConstructionReview(result.run.artifact_id)
      if (actionRequestOwnerRef.current !== owner) return
      setHandoffState({ status: 'idle', targetArtifactId: null, error: null })
    } catch (caught) {
      if (actionRequestOwnerRef.current !== owner) return
      setHandoffState({ status: 'error', targetArtifactId: artifactId, error: caught instanceof Error ? caught.message : 'ETF ranking construction handoff failed' })
    }
  }

  return (
    <section className="dashboard-bottom-grid" data-testid="persisted-etf-ranking-construction-browser">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Persisted ETF Ranking Construction</p></div>
        <p className="helper">Compact ETF-only browser for reopening persisted ETF ranking reviews or handing them into construction.</p>
      </div>
      <div className="summary-card">
        <div className="split-grid compact-split-grid strategy-lab-config-grid">
          <label className="field-group">
            <span className="field-label">Construction Policy</span>
            <select className="path-input" value={selectedConstructionPolicyId} onChange={(event) => setSelectedConstructionPolicyId(event.target.value)} disabled={constructionPolicyCatalog.status === 'loading' || constructionPolicyCatalog.status === 'error'}>
              <option value="">Select compatible policy</option>
              {constructionPolicyCatalog.policies.map((policy) => <option key={policy.policy_id} value={policy.policy_id}>{policy.name}</option>)}
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Max Position Weight</span>
            <input aria-label="Max Position Weight" className="path-input" value={constructionMaxPositionWeight} onChange={(event) => setConstructionMaxPositionWeight(event.target.value)} />
            <p className="helper">Decimal weight only. Must stay between 0.5 and 1 while the shipped ranking launch keeps top_n fixed at 2.</p>
            {constructionMaxPositionWeightValidation.error ? <p className="helper">{constructionMaxPositionWeightValidation.error}</p> : null}
          </label>
          <label className="field-group">
            <span className="field-label">Min Position Weight (optional)</span>
            <input aria-label="Min Position Weight (optional)" className="path-input" value={constructionMinPositionWeight} onChange={(event) => setConstructionMinPositionWeight(event.target.value)} />
            <p className="helper">Leave blank to omit. If set, use a decimal greater than 0 and up to 0.5, and no higher than max.</p>
            {constructionMinPositionWeightValidation.error ? <p className="helper">{constructionMinPositionWeightValidation.error}</p> : null}
          </label>
          <div className="field-group">
            <span className="field-label">Policy Source</span>
            <p className="helper">Authoritative `/construction/policies` discovery defines the compatible review-only policy set and the fixed top_n=2 launch boundary.</p>
          </div>
        </div>
        <div className="dashboard-edit-actions dashboard-edit-actions-compact">
          <button className="secondary-button" onClick={() => void loadRecentArtifacts()} type="button" disabled={recentState.status === 'loading'}>
            {recentState.status === 'loading' ? 'Refreshing...' : 'Refresh ETF Rankings'}
          </button>
        </div>
        {constructionPolicyCatalog.status === 'loading' ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Loading construction policies.</p>
            <p className="helper">Requesting authoritative compatible policy discovery for review-only construction.</p>
          </div>
        ) : null}
        {constructionPolicyCatalog.status === 'error' ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Construction policies are unavailable.</p>
            <p className="helper">Review In Construction is blocked until authoritative policy discovery succeeds.</p>
            <p className="helper">{constructionPolicyCatalog.error}</p>
          </div>
        ) : null}
        {handoffState.error ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">ETF ranking construction handoff failed.</p>
            <p className="helper">The selected persisted ETF ranking could not be handed into construction review.</p>
            <p className="helper">{handoffState.error}</p>
          </div>
        ) : null}
        {recentState.status === 'loading' && !recentState.items.length ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Loading persisted ETF rankings.</p>
            <p className="helper">Reading recent ETF ranking artifacts from generalized discovery.</p>
          </div>
        ) : null}
        {recentState.status === 'error' ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Persisted ETF rankings are unavailable.</p>
            <p className="helper">The generalized recent discovery route did not return a usable ETF list.</p>
            <p className="helper">{recentState.error}</p>
          </div>
        ) : null}
        {recentState.status !== 'error' && recentState.items.length === 0 && recentState.status !== 'loading' ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">No persisted ETF rankings found.</p>
            <p className="helper">Persisted ETF ranking artifacts will appear here when generalized recent discovery finds them.</p>
          </div>
        ) : null}
        {recentState.items.length ? (
          <div className="factor-snapshot-table-wrap">
            <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-rank-grid-wide">
              <span>Basis Date</span>
              <span>Peer Group</span>
              <span>Benchmark</span>
              <span>Lookback</span>
              <span>Confidence</span>
              <span>Universe</span>
              <span>Evaluated</span>
              <span>Artifact</span>
              <span>Action</span>
            </div>
            {recentState.items.map((item) => {
              const isRunning = handoffState.status === 'running' && handoffState.targetArtifactId === item.artifact_id
              const readiness = readinessState[item.artifact_id]
               const ready = readiness?.response?.eligibility.eligible === true && readiness.response.handoff != null
               const policyBlockedReason = constructionMaxPositionWeightValidation.error
                   ?? constructionMinPositionWeightValidation.error
                   ?? (!currentPortfolio
                     ? 'Open a workspace with an authoritative current portfolio to review this ranking in construction'
                     : null)
                   ?? (constructionPolicyCatalog.status === 'error'
                     ? constructionPolicyCatalog.error ?? 'Construction policy catalog unavailable'
                     : constructionPolicyCatalog.status === 'loading'
                      ? 'Loading construction policies...'
                      : !selectedConstructionPolicyId
                        ? 'Select a compatible construction policy'
                        : null)
               const selectedPolicyLabel = selectedConstructionPolicyId
                 ? policyNameForReview(selectedConstructionPolicyId, constructionPolicyCatalog.policies)
                 : null
               const readinessLabel = readiness == null || readiness.status === 'loading'
                 ? 'Checking readiness...'
                 : readiness.status === 'error'
                   ? readiness.error ?? 'Construction readiness unavailable'
                   : ready
                     ? (selectedPolicyLabel ? `Ready for construction review with ${selectedPolicyLabel}` : 'Ready for construction review')
                     : readiness.response?.eligibility.reason ?? 'Construction ineligible'
              const reviewLabel = policyBlockedReason ?? readinessLabel
              return (
                <div className="risk-contrib-table-grid factor-shift-data-row strategy-lab-rank-grid-wide" key={item.artifact_id}>
                  <span>{item.ranking_basis_date}</span>
                  <span>{item.effective_peer_group ?? 'Unspecified'}</span>
                  <span>{item.benchmark_symbol}</span>
                  <span>{item.lookback_months}</span>
                  <span>{item.confidence}</span>
                  <span>{item.universe_size}</span>
                  <span>{item.evaluated_universe_size}</span>
                    <span>{item.artifact_id}</span>
                    <span className="strategy-ranking-symbol-cell">
                      <button className="secondary-button" onClick={() => void onOpenRankingReview(item.artifact_id)} type="button">Open Review</button>
                      <button className={`secondary-button${isRunning ? ' button-loading' : ''}`} onClick={() => void reviewInConstruction(item.artifact_id)} type="button" disabled={isRunning || !ready || policyBlockedReason != null} title={reviewLabel}>
                        {isRunning ? 'Opening...' : 'Review In Construction'}
                      </button>
                      <small>{reviewLabel}</small>
                    </span>
                  </div>
                )
            })}
          </div>
        ) : null}
      </div>
    </section>
  )
}
