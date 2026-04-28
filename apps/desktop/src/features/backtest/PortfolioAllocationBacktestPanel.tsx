import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { assertSavedProposalArtifactIntegrity, assertSavedProposalArtifactProposalSourceIntegrity } from '../../app/portfolioWorkspaceStorage'
import { investorEconomicsBaseReason } from '../portfolio/investorEconomics'
import type { CandidateConstructionRuleInput, ConstructionArtifactReplayResponse, HypotheticalReplayResponse, OptimizerHandoffReplayResponse, OptimizerObjective, OverlayApplicationSummary, OverlayAwareHypotheticalReplayResponse, OverlayStateInput, PortfolioAllocationBacktestResponse, PortfolioBaselineView, PortfolioDiagnosticsComparisonRow, PortfolioDiagnosticsTopCallout, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionConstraintSetInput, SingleReplacementConstructionConstraintValidationResponse, SingleReplacementConstructionRuleId } from '../portfolio/types'
import type { ConstructionConstraintValidationArtifact, ConstructedCandidateArtifact, FormedCandidateArtifact, PersistedConstructionArtifactWorkspaceReview, PersistedOptimizerHandoffWorkspaceReview, PortfolioSnapshot, PortfolioWorkspaceSource, ReplacementIntentDraftArtifact, VersionedProposalArtifact } from '../portfolio/workspaceTypes'
import { formatReplayHistoricalBasisLabel, formatSnapshotBasisLabel } from '../portfolio/historyTruth'

type AllocationWeightRow = {
  symbol: string
  target_weight: string
}

type Props = {
  result: PortfolioAllocationBacktestResponse | null
  onResult: (result: PortfolioAllocationBacktestResponse) => void
  analysis: PortfolioBaselineView | null
}

type HypotheticalReplaySectionProps = {
  result: PortfolioAllocationBacktestResponse | null
  draftSnapshot: PortfolioSnapshot | null
  replacementIntentDraft: ReplacementIntentDraftArtifact | null
  formedCandidateArtifact: FormedCandidateArtifact | null
  constructedCandidateArtifact: ConstructedCandidateArtifact | null
  constructionConstraintValidationArtifact: ConstructionConstraintValidationArtifact | null
  selectedConstructionRuleId: SingleReplacementConstructionRuleId
  hypotheticalReplayResult: HypotheticalReplayResponse | null
  savedProposalCount: number
  onSaveProposal: () => void | Promise<void>
  onHypotheticalReplayResult: (result: HypotheticalReplayResponse) => void
  workspaceSource?: PortfolioWorkspaceSource | null
  persistedConstructionArtifactReview?: PersistedConstructionArtifactWorkspaceReview | null
  persistedOptimizerHandoffReview?: PersistedOptimizerHandoffWorkspaceReview | null
}

type ReplayBasisMode = 'standard' | 'overlay_aware'

type ComparisonMetricRow = {
  key: string
  label: string
  baseline: number | null
  candidate: number | null
  delta: number | null
  format: 'pct' | 'number' | 'money'
}

type DeltaCallout = {
  key: string
  label: string
  value: string
  tone: DeltaTone
  rationale: string
}

type DeltaTone = 'positive' | 'negative' | 'neutral'

type PreflightStatus = 'ready' | 'blocked' | 'pending'

type ConstraintReviewStatus = 'pass' | 'blocked' | 'rejected' | 'pending'

const constructionConstraintSet: SingleReplacementConstructionConstraintSetInput = {
  constraint_set_id: 'single_replacement_construction_constraints_v1',
}

type HypotheticalReplayPreflight = {
  overallStatus: PreflightStatus
  incumbentWeight: number | null
  checks: Array<{
    label: string
    status: PreflightStatus
    detail: string
  }>
}

type CandidateFormationSectionProps = {
  draftSnapshot: PortfolioSnapshot | null
  replacementIntentDraft: ReplacementIntentDraftArtifact | null
  formedCandidateArtifact: FormedCandidateArtifact | null
  onFormedCandidateArtifact: (result: SingleReplacementCandidateFormationResponse) => void
}

type ConstructionRuleSectionProps = {
  draftSnapshot: PortfolioSnapshot | null
  replacementIntentDraft: ReplacementIntentDraftArtifact | null
  formedCandidateArtifact: FormedCandidateArtifact | null
  constructedCandidateArtifact: ConstructedCandidateArtifact | null
  constructionConstraintValidationArtifact: ConstructionConstraintValidationArtifact | null
  selectedConstructionRuleId: SingleReplacementConstructionRuleId
  onConstructedCandidateArtifact: (result: SingleReplacementCandidateConstructionResponse) => void
  onConstructionConstraintValidationArtifact: (result: SingleReplacementConstructionConstraintValidationResponse) => void
  onSelectedConstructionRuleChange: (ruleId: SingleReplacementConstructionRuleId) => void
}

const constructionRuleOptions: Array<{ id: SingleReplacementConstructionRuleId; label: string; helper: string }> = [
  {
    id: 'same_weight_substitution_v1',
    label: 'Same weight substitution v1',
    helper: 'Backend constructs a single replacement using the incumbent starting weight.',
  },
  {
    id: 'fixed_split_50_50_substitution_v2',
    label: 'Fixed split 50/50 substitution v2',
    helper: 'Backend constructs a review-only split between the incumbent and the candidate.',
  },
]

function formatCandidateFormationStatus(status: 'ok' | 'rejected' | null | undefined) {
  if (status === 'ok') return 'Formed'
  if (status === 'rejected') return 'Rejected'
  return 'Not formed'
}

function formatConstructionStatus(status: 'ok' | 'rejected' | null | undefined) {
  if (status === 'ok') return 'Constructed'
  if (status === 'rejected') return 'Rejected'
  return 'Not constructed'
}

type DiagnosticsSectionConfig = {
  key: string
  title: string
  helper: string
  rows: PortfolioDiagnosticsComparisonRow[]
  topCallout: PortfolioDiagnosticsTopCallout | null
}

type DiagnosticsTopCallout = {
  label: string
  baseline: string
  candidate: string
  delta: string
  selectionRule: string
  rationale: string
}

function formatPct(value: number | null | undefined) {
  return value == null ? 'N/A' : `${value.toFixed(2)}%`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'N/A' : value.toFixed(digits)
}

function formatMoney(value: number | null | undefined) {
  return value == null ? 'N/A' : `$${value.toFixed(2)}`
}

function formatDateLabel(value: string | number | null | undefined) {
  if (typeof value !== 'string') return ''
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) return value
  return `${month}/${day}/${year.slice(2)}`
}

function formatWeightPct(value: number | null | undefined) {
  return value == null ? 'N/A' : `${(value * 100).toFixed(2)}%`
}

function isOverlayAwareReplayResponse(value: HypotheticalReplayResponse | null | undefined): value is OverlayAwareHypotheticalReplayResponse {
  return Boolean(value && 'overlay_replay' in value)
}

function activeReplayFromHypothetical(result: HypotheticalReplayResponse | null | undefined) {
  if (!result) return null
  return isOverlayAwareReplayResponse(result) ? result.overlay_replay : result.replay
}

function formatReplayCandidateInputSourceLabel(value: HypotheticalReplayResponse['replay_provenance']['candidate_input_source']) {
  return value === 'constructed_candidate_payload' ? 'constructed candidate replay' : 'direct preview replay'
}

function formatReplayConstructionRuleLabel(value: HypotheticalReplayResponse['replay_provenance']['construction_rule_id']) {
  return value === 'fixed_split_50_50_substitution_v2' ? 'fixed split 50/50' : 'same-weight substitution'
}

function formatReplayConstraintValidationLabel(value: HypotheticalReplayResponse['replay_provenance']['constraint_validation']) {
  if (!value.supplied) return 'validation not supplied'
  if (value.validation_status === 'blocked') return 'validated blocked'
  if (value.validation_status === 'rejected') return 'validated rejected'
  return 'validated ok'
}

function formatReplayLineageHelper(result: HypotheticalReplayResponse) {
  return `Replay lineage: ${formatReplayCandidateInputSourceLabel(result.replay_provenance.candidate_input_source)} · ${formatReplayConstructionRuleLabel(result.replay_provenance.construction_rule_id)} · ${formatReplayConstraintValidationLabel(result.replay_provenance.constraint_validation)}`
}

function standardReplayFromHypothetical(result: HypotheticalReplayResponse | null | undefined) {
  if (!result) return null
  return isOverlayAwareReplayResponse(result) ? result.base_replay : result.replay
}

function defaultOverlayState(benchmarkSymbol: string): OverlayStateInput {
  return {
    overlay_id: 'benchmark_trend_overlay_v1',
    status: 'risk_reduced',
    as_of_month_end: '2024-12-31',
    benchmark_symbol: benchmarkSymbol,
    signal_basis: '10_month_sma_month_end',
    confirmation_count: 2,
    rule_version: 'v1',
  }
}

function formatTooltipLabel(label: unknown) {
  return typeof label === 'string' || typeof label === 'number' ? formatDateLabel(label) : ''
}

function parseWeightRows(rows: AllocationWeightRow[]) {
  return rows
    .map((row) => ({ symbol: row.symbol.trim().toUpperCase(), target_weight: Number(row.target_weight) }))
    .filter((row) => row.symbol.length > 0)
}

function totalWeight(rows: AllocationWeightRow[]) {
  return parseWeightRows(rows).reduce((sum, row) => sum + row.target_weight, 0)
}

function formatComparisonValue(value: number | null, kind: ComparisonMetricRow['format']) {
  if (kind === 'money') return formatMoney(value)
  if (kind === 'pct') return formatPct(value)
  return formatNumber(value, 2)
}

function formatSignedComparisonValue(value: number | null, kind: ComparisonMetricRow['format']) {
  if (value == null) return 'N/A'
  if (kind === 'money') return `${value > 0 ? '+' : ''}${formatMoney(value)}`
  if (kind === 'pct') return `${value > 0 ? '+' : ''}${formatPct(value)}`
  return `${value > 0 ? '+' : ''}${formatNumber(value, 2)}`
}

function metricDeltaTone(row: ComparisonMetricRow): DeltaTone {
  if (row.delta == null || row.delta === 0) return 'neutral'
  const betterWhenHigher = new Set(['excess_return', 'information_ratio'])
  const betterWhenLower = new Set(['annualized_volatility', 'downside_volatility', 'tracking_error', 'turnover', 'cost'])
  if (betterWhenHigher.has(row.key)) return row.delta > 0 ? 'positive' : 'negative'
  if (betterWhenLower.has(row.key)) return row.delta < 0 ? 'positive' : 'negative'
  return row.delta > 0 ? 'positive' : 'negative'
}

function deltaToneClass(tone: DeltaTone) {
  if (tone === 'positive') return 'positive-text'
  if (tone === 'negative') return 'negative-text'
  return 'neutral-text'
}

function preflightToneClass(status: PreflightStatus) {
  if (status === 'ready') return 'positive-text'
  if (status === 'blocked') return 'negative-text'
  return 'neutral-text'
}

function totalTone(total: number, enabled = true): DeltaTone {
  if (!enabled) return 'neutral'
  if (Math.abs(total - 1) <= 0.01) return 'positive'
  if (Math.abs(total - 1) <= 0.03) return 'neutral'
  return 'negative'
}

function sectionCardClass(kind: 'baseline' | 'candidate') {
  return `backtest-allocation-card ${kind === 'baseline' ? 'backtest-allocation-card-baseline' : 'backtest-allocation-card-candidate'}`
}

function formatReplayWindow(startDate: string | null | undefined, endDate: string | null | undefined) {
  if (!startDate || !endDate) return 'N/A'
  return `${startDate} -> ${endDate}`
}

function formatOptimizerObjectiveLabel(objective: OptimizerObjective) {
  const objectiveId: string = objective.objective_id
  if (objectiveId === 'maximize_alpha_quality_v1') return 'maximize alpha quality v1'
  if (objectiveId === 'minimize_l2_distance_to_benchmark') return 'minimize benchmark distance'
  return objectiveId.replace(/_/g, ' ')
}

function formatOptimizerObjectiveDetails(objective: OptimizerObjective) {
  if (objective.objective_id === 'maximize_alpha_quality_v1') {
    return `Alpha signal: ${objective.alpha_signal_id ?? 'n/a'} · requires alpha package: ${objective.requires_alpha_package ? 'yes' : 'no'}`
  }
  return `Benchmark-relative: ${String(objective.benchmark_relative)} · requires alpha package: ${objective.requires_alpha_package ? 'yes' : 'no'}`
}

function replayHistoryTruthLabel(replay: PortfolioAllocationBacktestResponse) {
  return formatReplayHistoricalBasisLabel(
    replay.candidate_diagnostics?.provenance.historical_basis ?? replay.reference_diagnostics?.provenance.historical_basis ?? null,
  )
}

function replaySnapshotBasisLabel(replay: PortfolioAllocationBacktestResponse) {
  return formatSnapshotBasisLabel(
    replay.candidate_diagnostics?.provenance.snapshot_basis ?? replay.reference_diagnostics?.provenance.snapshot_basis ?? null,
  )
}

function diagnosticsValueKind(key: string): ComparisonMetricRow['format'] {
  if (key.includes('hhi') || key.includes('beta') || key.includes('correlation')) return 'number'
  return 'pct'
}

function buildReplayDeltaCallouts(rows: ComparisonMetricRow[]) {
  const ranked = rows
    .filter((row) => row.delta != null && row.delta !== 0)
    .map((row) => ({ row, tone: metricDeltaTone(row), magnitude: Math.abs(row.delta ?? 0) }))
    .sort((left, right) => right.magnitude - left.magnitude)
    .slice(0, 3)

  return ranked.map<DeltaCallout>(({ row, tone }) => ({
    key: row.key,
    label: row.label,
    value: formatSignedComparisonValue(row.delta, row.format),
    tone,
    rationale: tone === 'positive'
      ? 'candidate improves this metric relative to baseline'
      : tone === 'negative'
        ? 'candidate worsens this metric relative to baseline'
        : 'candidate is effectively unchanged on this metric',
  }))
}

function buildReplayMetricRefusalLine(replay: PortfolioAllocationBacktestResponse | null) {
  if (!investorEconomicsBaseReason(replay?.investor_economics_status)) return null

  return 'When replay/backtest investor total-return equivalence is unverified, suppress all user-facing investor-economics metrics and any derived or comparative views from that basis, including drawdown surfaces, Sharpe, Sortino, benchmark-relative deltas, and monitoring callouts; emit only null/withheld semantics, never numeric fallbacks or zero-equivalent UI states.'
}

function buildSummaryRows(replay: PortfolioAllocationBacktestResponse | null): ComparisonMetricRow[] {
  if (!replay?.reference_result) return []
  return [
    { key: 'annualized_volatility', label: 'Annualized Volatility', baseline: replay.reference_result.metrics.annualized_volatility_pct, candidate: replay.candidate_result.metrics.annualized_volatility_pct, delta: replay.comparison?.annualized_volatility_diff_pct ?? null, format: 'pct' },
    { key: 'downside_volatility', label: 'Downside Volatility', baseline: replay.reference_result.metrics.downside_volatility_pct, candidate: replay.candidate_result.metrics.downside_volatility_pct, delta: replay.comparison?.downside_volatility_diff_pct ?? null, format: 'pct' },
    { key: 'tracking_error', label: 'Tracking Error', baseline: replay.reference_result.metrics.tracking_error_pct, candidate: replay.candidate_result.metrics.tracking_error_pct, delta: replay.comparison?.tracking_error_diff_pct ?? null, format: 'pct' },
    { key: 'beta', label: 'Beta vs Benchmark', baseline: replay.reference_result.metrics.beta_vs_benchmark, candidate: replay.candidate_result.metrics.beta_vs_benchmark, delta: replay.comparison?.beta_diff ?? null, format: 'number' },
    { key: 'correlation', label: 'Correlation vs Benchmark', baseline: replay.reference_result.metrics.correlation_vs_benchmark, candidate: replay.candidate_result.metrics.correlation_vs_benchmark, delta: replay.comparison?.correlation_diff ?? null, format: 'number' },
    { key: 'turnover', label: 'Total Turnover', baseline: replay.reference_result.metrics.total_turnover_pct, candidate: replay.candidate_result.metrics.total_turnover_pct, delta: replay.comparison?.total_turnover_diff_pct ?? null, format: 'pct' },
    { key: 'cost', label: 'Total Cost Paid', baseline: replay.reference_result.metrics.total_cost_paid, candidate: replay.candidate_result.metrics.total_cost_paid, delta: replay.comparison?.total_cost_diff ?? null, format: 'money' },
  ]
}

function diagnosticsSectionConfigs(activeReplay: PortfolioAllocationBacktestResponse | null): DiagnosticsSectionConfig[] {
  if (!activeReplay?.diagnostics_comparison) return []

  return [
    {
      key: 'concentration',
      title: 'Concentration',
      helper: 'Review whether the hypothetical replacement changes how concentrated portfolio risk remains across positions or factors.',
      rows: activeReplay.diagnostics_comparison.concentration_changes,
      topCallout: activeReplay.diagnostics_comparison.top_concentration_change,
    },
    {
      key: 'factor-exposure',
      title: 'Factor Exposure',
      helper: 'Review how the candidate variant shifts portfolio exposure relative to the current baseline. Read this as hypothetical exposure change, not a target allocation decision.',
      rows: activeReplay.diagnostics_comparison.factor_exposure_changes,
      topCallout: activeReplay.diagnostics_comparison.top_factor_exposure_change,
    },
    {
      key: 'volatility-shape',
      title: 'Volatility Shape',
      helper: 'Review allowed replay risk-shape metrics under the shared window without inferring investor-return or drawdown conclusions.',
      rows: activeReplay.diagnostics_comparison.volatility_changes,
      topCallout: activeReplay.diagnostics_comparison.top_volatility_change,
    },
    {
      key: 'risk-contribution',
      title: 'Risk Contribution',
      helper: 'Review what drives portfolio risk in the baseline versus the hypothetical candidate. Use this to inspect attribution, not to infer a recommendation.',
      rows: activeReplay.diagnostics_comparison.risk_contribution_changes,
      topCallout: activeReplay.diagnostics_comparison.top_risk_contribution_change,
    },
    {
      key: 'stress-scenario',
      title: 'Stress / Scenario',
      helper: 'Review how baseline and candidate behave under the same scenario assumptions. Treat this as hypothetical comparison only.',
      rows: activeReplay.diagnostics_comparison.stress_scenario_changes,
      topCallout: activeReplay.diagnostics_comparison.top_stress_scenario_change,
    },
  ]
}

function buildDiagnosticsTopCallout(row: PortfolioDiagnosticsTopCallout | null): DiagnosticsTopCallout | null {
  if (!row) return null
  const format = diagnosticsValueKind(row.key)
  return {
    label: row.label,
    baseline: formatComparisonValue(row.baseline_value, format),
    candidate: formatComparisonValue(row.candidate_value, format),
    delta: formatSignedComparisonValue(row.delta_value, format),
    selectionRule: row.selection_rule,
    rationale: row.rationale,
  }
}

function formatSelectionRuleLabel(selectionRule: string) {
  if (selectionRule === 'largest_absolute_delta') return 'largest absolute delta'
  if (selectionRule === 'fixed_priority') return 'fixed priority rule'
  return selectionRule.replace(/_/g, ' ')
}

function normalizeRows(rows: AllocationWeightRow[]) {
  const parsed = parseWeightRows(rows)
  const total = parsed.reduce((sum, row) => sum + row.target_weight, 0)
  if (!parsed.length || total === 0) return rows
  return parsed.map((row) => ({ symbol: row.symbol, target_weight: (row.target_weight / total).toFixed(4) }))
}

function deriveBaselineRows(analysis: PortfolioBaselineView | null): AllocationWeightRow[] {
  if (!analysis?.snapshot.positions?.length) return []
  const total = analysis.snapshot.positions.reduce((sum, position) => sum + position.market_value, 0)
  if (!total) return []
  return analysis.snapshot.positions
    .map((position) => ({ symbol: position.symbol, target_weight: (position.market_value / total).toFixed(4), market_value: position.market_value }))
    .sort((left, right) => right.market_value - left.market_value)
    .map(({ symbol, target_weight }) => ({ symbol, target_weight }))
}

function buildHypotheticalReplayPreflight(replacementIntentDraft: ReplacementIntentDraftArtifact | null, constructedCandidateArtifact: ConstructedCandidateArtifact | null, selectedConstructionRuleId: SingleReplacementConstructionRuleId): HypotheticalReplayPreflight {
  if (!replacementIntentDraft) {
    return {
      overallStatus: 'blocked',
      incumbentWeight: null,
      checks: [
        {
          label: 'Replacement Intent',
          status: 'blocked',
          detail: 'An explicit replacement intent must exist before a hypothetical replay can run.',
        },
      ],
    }
  }

  if (!constructedCandidateArtifact) {
    return {
      overallStatus: 'blocked',
      incumbentWeight: null,
      checks: [
        {
          label: 'Construction Rule',
          status: 'blocked',
          detail: 'A constructed candidate review artifact must exist before hypothetical replay can run.',
        },
      ],
    }
  }

  const matchesIntent = constructedCandidateArtifact.replacementIntentCreatedAt === replacementIntentDraft.createdAt
    && constructedCandidateArtifact.replacementIntentBaseSymbol === replacementIntentDraft.baseSymbol
    && constructedCandidateArtifact.replacementIntentCandidateSymbol === replacementIntentDraft.candidateSymbol
  const matchesRule = constructedCandidateArtifact.constructionRuleId === selectedConstructionRuleId
    && constructedCandidateArtifact.construction.construction.rule_id === selectedConstructionRuleId
  const construction = constructedCandidateArtifact.construction
  const incumbentWeight = construction.inputs.incumbent_start_weight

  const checks: HypotheticalReplayPreflight['checks'] = [
    {
      label: 'Construction Artifact',
      status: construction.construction.status === 'ok' ? 'ready' : 'blocked',
      detail: construction.construction.status === 'ok'
        ? `The construction artifact supplies ${construction.outputs.candidate_weights.length} candidate weights for review-only replay handoff.`
        : `Construction rule was rejected: ${construction.rejection_reason ?? 'unknown rejection reason'}.`,
    },
    {
      label: 'Intent Match',
      status: matchesIntent ? 'ready' : 'blocked',
      detail: matchesIntent
        ? `The construction artifact matches ${replacementIntentDraft.baseSymbol} -> ${replacementIntentDraft.candidateSymbol}.`
        : 'The construction artifact is stale and no longer matches the active replacement intent.',
    },
    {
      label: 'Selected Rule',
      status: matchesRule ? 'ready' : 'blocked',
      detail: matchesRule
        ? `The construction artifact matches the selected rule ${selectedConstructionRuleId}.`
        : `The selected rule is ${selectedConstructionRuleId}, but the saved construction artifact was built for ${constructedCandidateArtifact.constructionRuleId}.`,
    },
    {
      label: 'Replay Validation',
      status: 'pending',
      detail: 'The backend still has to confirm candidate history coverage and sufficient common replay dates before a preview can succeed.',
    },
  ]

  return {
    overallStatus: checks.some((check) => check.status === 'blocked') ? 'blocked' : 'ready',
    incumbentWeight,
    checks,
  }
}

function formatConstraintStatusLabel(status: ConstraintReviewStatus) {
  if (status === 'pass') return 'Pass'
  if (status === 'blocked') return 'Blocked'
  if (status === 'rejected') return 'Rejected'
  return 'Pending'
}

function constraintStatusToneClass(status: ConstraintReviewStatus) {
  if (status === 'pass') return 'positive-text'
  if (status === 'blocked' || status === 'rejected') return 'negative-text'
  return 'neutral-text'
}

function formatConstraintSeverityLabel(severity: 'hard_block' | 'warning') {
  return severity === 'warning' ? 'Warning' : 'Hard block'
}

function constraintSeverityToneClass(severity: 'hard_block' | 'warning', status: 'pass' | 'fail' | 'not_applicable') {
  if (severity === 'warning') return 'neutral-text'
  if (status === 'fail') return 'negative-text'
  return 'neutral-text'
}

function formatConstraintValue(value: number | string | null | undefined) {
  if (value == null) return 'n/a'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(4)
  return value
}

function summarizeConstraintValidation(validation: SingleReplacementConstructionConstraintValidationResponse | null): {
  reviewStatus: ConstraintReviewStatus
  hardBlockCount: number
  warningCount: number
  passCount: number
  constraintCount: number
  statusDetail: string
} {
  if (!validation) {
    return {
      reviewStatus: 'pending',
      hardBlockCount: 0,
      warningCount: 0,
      passCount: 0,
      constraintCount: 0,
      statusDetail: 'Constraint validation has not been run for the current construction output yet.',
    }
  }

  const hardBlockCount = validation.blocking_constraint_ids.length
  const warningCount = validation.evaluations.filter((item) => item.severity === 'warning').length
  const passCount = validation.evaluations.filter((item) => item.status === 'pass').length
  const constraintCount = validation.evaluations.length
  const reviewStatus: ConstraintReviewStatus = validation.validation.status === 'ok'
    ? 'pass'
    : validation.validation.status === 'blocked'
      ? 'blocked'
      : 'rejected'

  const statusDetail = validation.validation.status === 'ok'
    ? 'The constructed candidate passed the locked backend constraint set and can be handed into replay review.'
    : validation.validation.status === 'blocked'
      ? `The constructed candidate failed ${hardBlockCount} hard-block constraint${hardBlockCount === 1 ? '' : 's'} and replay remains unavailable.`
      : validation.rejection_reason ?? 'The constructed candidate could not be evaluated safely, so replay remains unavailable.'

  return { reviewStatus, hardBlockCount, warningCount, passCount, constraintCount, statusDetail }
}

export function CandidateFormationSection({ draftSnapshot, replacementIntentDraft, formedCandidateArtifact, onFormedCandidateArtifact }: CandidateFormationSectionProps) {
  const apiBase = useMemo(() => '/api', [])
  const [formationLoading, setFormationLoading] = useState(false)
  const [formationError, setFormationError] = useState<string | null>(null)

  const formationMatchesIntent = Boolean(
    replacementIntentDraft
    && formedCandidateArtifact
    && formedCandidateArtifact.replacementIntentCreatedAt === replacementIntentDraft.createdAt
    && formedCandidateArtifact.replacementIntentBaseSymbol === replacementIntentDraft.baseSymbol
    && formedCandidateArtifact.replacementIntentCandidateSymbol === replacementIntentDraft.candidateSymbol,
  )

  const activeFormation = formationMatchesIntent ? formedCandidateArtifact?.formation ?? null : null
  const staleFormation = Boolean(formedCandidateArtifact && !formationMatchesIntent)

  async function runCandidateFormation() {
    if (!draftSnapshot || !replacementIntentDraft) return

    setFormationLoading(true)
    setFormationError(null)

    try {
      const response = await fetch(`${apiBase}/backtests/candidate-formation/replacement-intent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          snapshot: {
            snapshot_version: draftSnapshot.snapshotVersion,
            base_currency: draftSnapshot.baseCurrency,
            imported_meta: {
              importer: draftSnapshot.importedMeta.importer,
              statement_period: draftSnapshot.importedMeta.statementPeriod,
              imported_at: draftSnapshot.importedMeta.importedAt,
              source_file_names: draftSnapshot.importedMeta.sourceFileNames,
            },
            positions: draftSnapshot.positions.map((position) => ({
              symbol: position.symbol,
              market_value: position.marketValue,
              quantity: position.quantity ?? null,
              currency: position.currency ?? null,
              sector: position.sector ?? null,
              name: position.name ?? null,
              source_type: position.sourceType ?? null,
            })),
            cash_balances: draftSnapshot.cashBalances.map((balance) => ({ currency: balance.currency, amount: balance.amount })),
          },
          replacement_intent: {
            kind: replacementIntentDraft.kind,
            source: replacementIntentDraft.source,
            created_at: replacementIntentDraft.createdAt,
            draft_id: replacementIntentDraft.draftId,
            workspace_id: replacementIntentDraft.workspaceId,
            base_node_id: replacementIntentDraft.baseNodeId,
            base_symbol: replacementIntentDraft.baseSymbol,
            candidate_symbol: replacementIntentDraft.candidateSymbol,
            seeded_from_draft_id: replacementIntentDraft.seededFromDraftId,
            seed_ranking_id: replacementIntentDraft.seedRankingId,
            seed_methodology_id: replacementIntentDraft.seedMethodologyId,
            seed_ranking_basis_date: replacementIntentDraft.seedRankingBasisDate,
            peer_group: replacementIntentDraft.peerGroup,
            benchmark_symbol: replacementIntentDraft.benchmarkSymbol,
            lookback_months: replacementIntentDraft.lookbackMonths,
            confidence: replacementIntentDraft.confidence,
            holdings_support: replacementIntentDraft.holdingsSupport,
            warning_count: replacementIntentDraft.warningCount,
          },
        }),
      })
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Candidate formation failed')
      }
      onFormedCandidateArtifact((await response.json()) as SingleReplacementCandidateFormationResponse)
    } catch (caughtError) {
      setFormationError(caughtError instanceof Error ? caughtError.message : 'Candidate formation failed')
    } finally {
      setFormationLoading(false)
    }
  }

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header"><div><p className="panel-label">Candidate Formation</p></div><p className="helper">Truth class: candidate-formation-derived review input only. This step forms a single-replacement hypothetical candidate before replay and does not apply holdings.</p></div>
      {!replacementIntentDraft ? (
        <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">No explicit replacement intent is available for candidate formation yet.</p><p className="helper">Create a replacement intent first. Candidate formation remains review-only and does not imply an applied portfolio change.</p></div>
      ) : (
        <>
          <div className="dashboard-summary compact-summary-grid">
            <div className="summary-card"><p className="stat-label">Intent Pair</p><p className="summary-value">{replacementIntentDraft.baseSymbol} -&gt; {replacementIntentDraft.candidateSymbol}</p><p className="helper">Formation uses the active replacement intent only.</p></div>
            <div className="summary-card"><p className="stat-label">Formation Status</p><p className={`summary-value ${staleFormation ? 'negative-text' : activeFormation?.formation.status === 'ok' ? 'positive-text' : activeFormation?.formation.status === 'rejected' ? 'negative-text' : 'neutral-text'}`}>{staleFormation ? 'stale' : formatCandidateFormationStatus(activeFormation?.formation.status)}</p><p className="helper">{staleFormation ? 'A previous formed candidate no longer matches the active replacement intent.' : activeFormation?.rejection_reason ?? 'No formed candidate artifact exists yet for this intent.'}</p></div>
            <div className="summary-card"><p className="stat-label">Truth Provenance</p><p className="summary-value">{activeFormation?.truth_provenance.formation_truth_class ?? 'n/a'}</p><p className="helper">{activeFormation?.truth_provenance.note ?? 'Formed candidate output remains a review-only derived object.'}</p></div>
            <div className="summary-card"><p className="stat-label">Starting Turnover</p><p className="summary-value">{formatWeightPct(activeFormation?.formation_summary.starting_turnover_pct ?? null)}</p><p className="helper">Candidate formation reports the incumbent weight handed into the hypothetical replacement.</p></div>
          </div>
          {activeFormation ? (
            <div className="summary-card">
              <p className="panel-label">Formation Provenance</p>
              <p className="helper">Source: {activeFormation.proposal.source} · Draft: {activeFormation.proposal.draft_id ?? 'n/a'} · Base node: {activeFormation.proposal.base_node_id ?? 'n/a'}</p>
              <p className="helper">Derivation: {activeFormation.derivation.baseline_basis} · {activeFormation.derivation.candidate_construction_rule} · {activeFormation.derivation.position_scope}</p>
              <p className="helper">Cash treatment: {activeFormation.derivation.cash_treatment}</p>
            </div>
          ) : null}
          {activeFormation?.warnings.length ? <div className="summary-card"><p className="panel-label">Formation Warnings</p>{activeFormation.warnings.map((warning) => <p className="helper" key={warning}>{warning}</p>)}</div> : null}
          {activeFormation ? <div className="split-grid dashboard-bottom-grid"><section><div className="section-header-inline sector-list-header"><div><p className="panel-label">Formation Baseline</p></div></div><div className="list-table">{activeFormation.baseline_weights.map((row) => <div className="list-row" key={`formation-baseline-${row.symbol}`}><span>{row.symbol}</span><span>{formatWeightPct(row.target_weight)}</span></div>)}</div></section><section><div className="section-header-inline sector-list-header"><div><p className="panel-label">Formed Candidate</p></div></div><div className="list-table">{activeFormation.candidate_weights.map((row) => <div className="list-row" key={`formation-candidate-${row.symbol}`}><span>{row.symbol}</span><span>{formatWeightPct(row.target_weight)}</span></div>)}</div></section></div> : null}
          <div className="actions backtest-actions"><button className="secondary-button" type="button" disabled={formationLoading} onClick={() => void runCandidateFormation()}>{formationLoading ? 'Forming Candidate...' : activeFormation ? 'Rebuild Candidate Formation' : 'Form Candidate For Replay'}</button><p className="helper">Form a review-only hypothetical candidate from the explicit replacement intent before replay.</p></div>
          {formationError ? <p className="error">{formationError}</p> : null}
        </>
      )}
    </section>
  )
}

export function ConstructionRuleSection({ draftSnapshot, replacementIntentDraft, formedCandidateArtifact, constructedCandidateArtifact, constructionConstraintValidationArtifact, selectedConstructionRuleId, onConstructedCandidateArtifact, onConstructionConstraintValidationArtifact, onSelectedConstructionRuleChange }: ConstructionRuleSectionProps) {
  const apiBase = useMemo(() => '/api', [])
  const [constructionLoading, setConstructionLoading] = useState(false)
  const [constraintValidationLoading, setConstraintValidationLoading] = useState(false)
  const [constructionError, setConstructionError] = useState<string | null>(null)
  const [constraintValidationError, setConstraintValidationError] = useState<string | null>(null)

  const formationMatchesIntent = Boolean(
    replacementIntentDraft
    && formedCandidateArtifact
    && formedCandidateArtifact.replacementIntentCreatedAt === replacementIntentDraft.createdAt
    && formedCandidateArtifact.replacementIntentBaseSymbol === replacementIntentDraft.baseSymbol
    && formedCandidateArtifact.replacementIntentCandidateSymbol === replacementIntentDraft.candidateSymbol,
  )
  const activeFormation = formationMatchesIntent ? formedCandidateArtifact?.formation ?? null : null
  const validFormation = Boolean(activeFormation && activeFormation.formation.status === 'ok')

  const constructionMatchesIntent = Boolean(
    replacementIntentDraft
    && constructedCandidateArtifact
    && constructedCandidateArtifact.replacementIntentCreatedAt === replacementIntentDraft.createdAt
    && constructedCandidateArtifact.replacementIntentBaseSymbol === replacementIntentDraft.baseSymbol
    && constructedCandidateArtifact.replacementIntentCandidateSymbol === replacementIntentDraft.candidateSymbol,
  )
  const activeConstruction = constructionMatchesIntent ? constructedCandidateArtifact?.construction ?? null : null
  const staleConstruction = Boolean(constructedCandidateArtifact && !constructionMatchesIntent)
  const constructionMatchesRule = Boolean(
    constructedCandidateArtifact
    && constructedCandidateArtifact.constructionRuleId === selectedConstructionRuleId
    && constructedCandidateArtifact.construction.construction.rule_id === selectedConstructionRuleId,
  )
  const activeConstructionForSelection = constructionMatchesIntent && constructionMatchesRule ? constructedCandidateArtifact?.construction ?? null : null
  const staleConstructionForSelectedRule = Boolean(constructedCandidateArtifact && constructionMatchesIntent && !constructionMatchesRule)
  const constraintValidationMatchesIntent = Boolean(
    replacementIntentDraft
    && constructionConstraintValidationArtifact
    && constructionConstraintValidationArtifact.replacementIntentCreatedAt === replacementIntentDraft.createdAt
    && constructionConstraintValidationArtifact.replacementIntentBaseSymbol === replacementIntentDraft.baseSymbol
    && constructionConstraintValidationArtifact.replacementIntentCandidateSymbol === replacementIntentDraft.candidateSymbol,
  )
  const constraintValidationMatchesRule = Boolean(
    constructionConstraintValidationArtifact
    && constructionConstraintValidationArtifact.constructionRuleId === selectedConstructionRuleId,
  )
  const activeConstraintValidation = constraintValidationMatchesIntent && constraintValidationMatchesRule
    ? constructionConstraintValidationArtifact?.validation ?? null
    : null
  const staleConstraintValidation = Boolean(
    constructionConstraintValidationArtifact
    && (!constraintValidationMatchesIntent || !constraintValidationMatchesRule),
  )
  const constraintSummary = summarizeConstraintValidation(activeConstraintValidation)
  const constructionRule: CandidateConstructionRuleInput = { rule_id: selectedConstructionRuleId }
  const selectedRuleOption = constructionRuleOptions.find((option) => option.id === selectedConstructionRuleId) ?? constructionRuleOptions[0]

  async function runConstructionRule() {
    if (!draftSnapshot || !replacementIntentDraft || !validFormation) return

    setConstructionLoading(true)
    setConstructionError(null)

    try {
      const response = await fetch(`${apiBase}/backtests/candidate-construction/replacement-intent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          snapshot: {
            snapshot_version: draftSnapshot.snapshotVersion,
            base_currency: draftSnapshot.baseCurrency,
            imported_meta: {
              importer: draftSnapshot.importedMeta.importer,
              statement_period: draftSnapshot.importedMeta.statementPeriod,
              imported_at: draftSnapshot.importedMeta.importedAt,
              source_file_names: draftSnapshot.importedMeta.sourceFileNames,
            },
            positions: draftSnapshot.positions.map((position) => ({
              symbol: position.symbol,
              market_value: position.marketValue,
              quantity: position.quantity ?? null,
              currency: position.currency ?? null,
              sector: position.sector ?? null,
              name: position.name ?? null,
              source_type: position.sourceType ?? null,
            })),
            cash_balances: draftSnapshot.cashBalances.map((balance) => ({ currency: balance.currency, amount: balance.amount })),
          },
          replacement_intent: {
            kind: replacementIntentDraft.kind,
            source: replacementIntentDraft.source,
            created_at: replacementIntentDraft.createdAt,
            draft_id: replacementIntentDraft.draftId,
            workspace_id: replacementIntentDraft.workspaceId,
            base_node_id: replacementIntentDraft.baseNodeId,
            base_symbol: replacementIntentDraft.baseSymbol,
            candidate_symbol: replacementIntentDraft.candidateSymbol,
            seeded_from_draft_id: replacementIntentDraft.seededFromDraftId,
            seed_ranking_id: replacementIntentDraft.seedRankingId,
            seed_methodology_id: replacementIntentDraft.seedMethodologyId,
            seed_ranking_basis_date: replacementIntentDraft.seedRankingBasisDate,
            peer_group: replacementIntentDraft.peerGroup,
            benchmark_symbol: replacementIntentDraft.benchmarkSymbol,
            lookback_months: replacementIntentDraft.lookbackMonths,
            confidence: replacementIntentDraft.confidence,
            holdings_support: replacementIntentDraft.holdingsSupport,
            warning_count: replacementIntentDraft.warningCount,
          },
          construction_rule: constructionRule,
        }),
      })
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Candidate construction failed')
      }
      onConstructedCandidateArtifact((await response.json()) as SingleReplacementCandidateConstructionResponse)
    } catch (caughtError) {
      setConstructionError(caughtError instanceof Error ? caughtError.message : 'Candidate construction failed')
    } finally {
      setConstructionLoading(false)
    }
  }

  async function runConstructionConstraintValidation() {
    if (!activeConstructionForSelection) return

    setConstraintValidationLoading(true)
    setConstraintValidationError(null)

    try {
      const response = await fetch(`${apiBase}/backtests/candidate-construction/replacement-intent/constraints`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          constructed_candidate: activeConstructionForSelection,
          constraint_set: constructionConstraintSet,
        }),
      })
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Construction constraint validation failed')
      }
      onConstructionConstraintValidationArtifact((await response.json()) as SingleReplacementConstructionConstraintValidationResponse)
    } catch (caughtError) {
      setConstraintValidationError(caughtError instanceof Error ? caughtError.message : 'Construction constraint validation failed')
    } finally {
      setConstraintValidationLoading(false)
    }
  }

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header"><div><p className="panel-label">Construction Rule</p></div><p className="helper">Truth class: candidate-construction-derived review input only. This step applies one explicit construction rule before replay and does not apply holdings.</p></div>
      {!replacementIntentDraft ? (
        <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">No explicit replacement intent is available for construction yet.</p><p className="helper">Create a replacement intent first. Construction remains review-only and separate from portfolio truth.</p></div>
      ) : !validFormation ? (
        <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">A valid formed candidate is required before construction can run.</p><p className="helper">Candidate formation must produce a current review-only artifact before the construction rule can build replay input.</p></div>
      ) : (
        <>
          <div className="dashboard-summary compact-summary-grid">
            <div className="summary-card"><p className="stat-label">Intent Pair</p><p className="summary-value">{replacementIntentDraft.baseSymbol} -&gt; {replacementIntentDraft.candidateSymbol}</p><p className="helper">Construction uses the active replacement intent only.</p></div>
            <div className="summary-card"><p className="stat-label">Selected Rule</p><p className="summary-value">{selectedConstructionRuleId}</p><p className="helper">{selectedRuleOption.helper}</p></div>
            <div className="summary-card"><p className="stat-label">Construction Status</p><p className={`summary-value ${staleConstruction || staleConstructionForSelectedRule ? 'negative-text' : activeConstructionForSelection?.construction.status === 'ok' ? 'positive-text' : activeConstructionForSelection?.construction.status === 'rejected' ? 'negative-text' : 'neutral-text'}`}>{staleConstruction || staleConstructionForSelectedRule ? 'Stale' : formatConstructionStatus(activeConstructionForSelection?.construction.status)}</p><p className="helper">{staleConstruction ? 'A previous construction artifact no longer matches the active replacement intent.' : staleConstructionForSelectedRule ? `The saved construction artifact was built with ${constructedCandidateArtifact?.constructionRuleId ?? 'another rule'}. Rerun construction for ${selectedConstructionRuleId}.` : activeConstructionForSelection?.rejection_reason ?? 'No construction artifact exists yet for this selected rule.'}</p></div>
            <div className="summary-card"><p className="stat-label">Truth Provenance</p><p className="summary-value">{activeConstructionForSelection?.truth_provenance.construction_truth_class ?? 'n/a'}</p><p className="helper">{activeConstructionForSelection?.truth_provenance.note ?? 'Construction output remains a review-only derived object.'}</p></div>
          </div>
          <div className="summary-card">
            <p className="panel-label">Rule Selection</p>
            <div className="split-grid compact-split-grid">
              <label className="field-group">
                <span className="field-label">Construction Rule</span>
                <select className="path-input" value={selectedConstructionRuleId} onChange={(event) => onSelectedConstructionRuleChange(event.target.value as SingleReplacementConstructionRuleId)}>
                  {constructionRuleOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
                </select>
              </label>
            </div>
            <p className="helper">Choose one locked backend-authored rule for review-only construction. Changing the rule makes earlier construction output stale until rerun.</p>
          </div>
          {activeConstructionForSelection ? (
            <div className="summary-card">
              <p className="panel-label">Construction Provenance</p>
              <p className="helper">Source: {activeConstructionForSelection.proposal.source} · Draft: {activeConstructionForSelection.proposal.draft_id ?? 'n/a'} · Base node: {activeConstructionForSelection.proposal.base_node_id ?? 'n/a'}</p>
              <p className="helper">Rule: {activeConstructionForSelection.inputs.construction_rule} · Basis: {activeConstructionForSelection.derivation.baseline_basis} · {activeConstructionForSelection.derivation.construction_basis}</p>
              <p className="helper">Cash treatment: {activeConstructionForSelection.derivation.cash_treatment} · Position scope: {activeConstructionForSelection.derivation.position_scope}</p>
              {activeConstructionForSelection.outputs.candidate_added_weight != null || activeConstructionForSelection.outputs.incumbent_remaining_weight != null ? <p className="helper">Candidate added weight: {formatWeightPct(activeConstructionForSelection.outputs.candidate_added_weight)} · Incumbent remaining weight: {formatWeightPct(activeConstructionForSelection.outputs.incumbent_remaining_weight)}</p> : null}
            </div>
          ) : null}
          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Construction Constraints</p></div><p className="helper">Truth class: constraint-validation-derived review state only. This step validates the constructed candidate after construction and before replay.</p></div>
            {!activeConstructionForSelection ? (
              <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">A current constructed candidate is required before constraint validation can run.</p><p className="helper">Construction constraints evaluate the explicit constructed candidate only and do not create a replay or mutate holdings.</p></div>
            ) : (
              <>
                <div className="dashboard-summary compact-summary-grid">
                  <div className="summary-card"><p className="stat-label">Validation Status</p><p className={`summary-value ${staleConstraintValidation ? 'negative-text' : constraintStatusToneClass(constraintSummary.reviewStatus)}`}>{staleConstraintValidation ? 'Stale' : formatConstraintStatusLabel(constraintSummary.reviewStatus)}</p><p className="helper">{staleConstraintValidation ? 'The saved constraint validation no longer matches the active construction output or selected rule.' : constraintSummary.statusDetail}</p></div>
                  <div className="summary-card"><p className="stat-label">Constraint Set</p><p className="summary-value">single_replacement_construction_constraints_v1</p><p className="helper">Backend-authored locked constraint set for this workflow step.</p></div>
                  <div className="summary-card"><p className="stat-label">Hard Blocks</p><p className="summary-value">{activeConstraintValidation ? String(constraintSummary.hardBlockCount) : 'n/a'}</p><p className="helper">Blocking failures keep replay unavailable.</p></div>
                  <div className="summary-card"><p className="stat-label">Constraint Results</p><p className="summary-value">{activeConstraintValidation ? `${constraintSummary.passCount}/${constraintSummary.constraintCount}` : 'n/a'}</p><p className="helper">Passing checks out of total evaluated constraints.</p></div>
                </div>
                {activeConstraintValidation ? (
                  <div className="summary-card">
                    <p className="panel-label">Validation Summary</p>
                    <p className="helper">Validation timing: {activeConstraintValidation.derivation.validation_timing} · Basis: {activeConstraintValidation.derivation.validation_basis}</p>
                    <p className="helper">Candidate input source: {activeConstraintValidation.derivation.candidate_input_source} · Truth provenance: {activeConstraintValidation.truth_provenance.constraint_validation_truth_class}</p>
                    <p className="helper">{activeConstraintValidation.truth_provenance.note}</p>
                    {activeConstraintValidation.rejection_reason ? <p className="helper">Rejection reason: {activeConstraintValidation.rejection_reason}</p> : null}
                    {activeConstraintValidation.blocking_constraint_ids.length ? <p className="helper">Blocking constraint ids: {activeConstraintValidation.blocking_constraint_ids.join(', ')}</p> : null}
                  </div>
                ) : null}
                {activeConstraintValidation?.warnings.length ? <div className="summary-card"><p className="panel-label">Validation Warnings</p>{activeConstraintValidation.warnings.map((warning) => <p className="helper" key={warning}>{warning}</p>)}</div> : null}
                {activeConstraintValidation ? (
                  <div className="list-table">
                    <div className="list-row list-row-wide">
                      <span>Constraint</span>
                      <span>Status</span>
                      <span>Severity</span>
                      <span>Result</span>
                    </div>
                    {activeConstraintValidation.evaluations.map((evaluation) => (
                      <div className="list-row list-row-wide" key={evaluation.constraint_id}>
                        <span>{evaluation.constraint_id}</span>
                        <span className={evaluation.status === 'pass' ? 'positive-text' : evaluation.status === 'fail' ? 'negative-text' : 'neutral-text'}>{evaluation.status}</span>
                        <span className={constraintSeverityToneClass(evaluation.severity, evaluation.status)}>{formatConstraintSeverityLabel(evaluation.severity)}</span>
                        <span>
                          {evaluation.message}
                          <br />
                          actual {formatConstraintValue(evaluation.actual_value)} · expected {formatConstraintValue(evaluation.expected_value)}{evaluation.operator ? ` · ${evaluation.operator}` : ''}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : null}
                <div className="actions backtest-actions"><button className="secondary-button" type="button" disabled={constraintValidationLoading} onClick={() => void runConstructionConstraintValidation()}>{constraintValidationLoading ? 'Validating Constraints...' : activeConstraintValidation ? 'Re-run Construction Constraints' : 'Validate Construction Constraints'}</button><p className="helper">Run locked backend validation for the current constructed candidate before replay.</p></div>
                {constraintValidationError ? <p className="error">{constraintValidationError}</p> : null}
              </>
            )}
          </section>
          {activeConstructionForSelection?.warnings.length ? <div className="summary-card"><p className="panel-label">Construction Warnings</p>{activeConstructionForSelection.warnings.map((warning) => <p className="helper" key={warning}>{warning}</p>)}</div> : null}
          {activeConstructionForSelection ? <div className="split-grid dashboard-bottom-grid"><section><div className="section-header-inline sector-list-header"><div><p className="panel-label">Construction Baseline</p></div></div><div className="list-table">{activeConstructionForSelection.inputs.baseline_weights.map((row) => <div className="list-row" key={`construction-baseline-${row.symbol}`}><span>{row.symbol}</span><span>{formatWeightPct(row.target_weight)}</span></div>)}</div></section><section><div className="section-header-inline sector-list-header"><div><p className="panel-label">Constructed Candidate</p></div></div><div className="list-table">{activeConstructionForSelection.outputs.candidate_weights.map((row) => <div className="list-row" key={`construction-candidate-${row.symbol}`}><span>{row.symbol}</span><span>{formatWeightPct(row.target_weight)}</span></div>)}</div></section></div> : null}
          <div className="actions backtest-actions"><button className="secondary-button" type="button" disabled={constructionLoading} onClick={() => void runConstructionRule()}>{constructionLoading ? 'Constructing Candidate...' : activeConstructionForSelection ? 'Rebuild Construction Rule' : 'Construct Candidate For Replay'}</button><p className="helper">Build a review-only constructed candidate from one explicit rule before replay.</p></div>
          {constructionError ? <p className="error">{constructionError}</p> : null}
        </>
      )}
    </section>
  )
}

function BacktestCurve({ result }: { result: PortfolioAllocationBacktestResponse }) {
  const chartData = useMemo(() => {
    const referenceByDate = new Map((result.reference_result?.equity_curve ?? []).map((point) => [point.date, point]))
    return result.candidate_result.equity_curve.map((point) => ({
      date: point.date,
      candidateEquity: point.equity,
      referenceEquity: referenceByDate.get(point.date)?.equity ?? null,
    }))
  }, [result])

  return (
    <section>
      <div className="section-header-inline sector-list-header"><div><p className="panel-label">Replay Equity</p></div></div>
      <div className="line-chart-panel compact-chart-panel">
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={220}>
          <AreaChart data={chartData} margin={{ top: 18, right: 16, left: 8, bottom: 8 }}>
            <defs>
              <linearGradient id="allocationCandidateFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#d85a51" stopOpacity={0.24} />
                <stop offset="100%" stopColor="#d85a51" stopOpacity={0.03} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(70, 82, 98, 0.16)" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: '#748295', fontSize: 10 }} minTickGap={28} interval="preserveStartEnd" tickFormatter={formatDateLabel} />
            <YAxis tick={{ fill: '#748295', fontSize: 10 }} width={56} tickFormatter={(value) => `$${Number(value).toFixed(0)}`} />
            <Tooltip formatter={(value) => formatMoney(typeof value === 'number' ? value : null)} labelFormatter={formatTooltipLabel} />
            {result.reference_result ? <Line type="monotone" dataKey="referenceEquity" name="Baseline" stroke="#6c88a6" strokeWidth={1.8} dot={false} isAnimationActive={false} /> : null}
            <Area type="monotone" dataKey="candidateEquity" name="Candidate" stroke="#d85a51" fill="url(#allocationCandidateFill)" strokeWidth={2.2} dot={false} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

function ComparisonTable({ rows }: { rows: ComparisonMetricRow[] }) {
  return (
    <div className="factor-snapshot-table-wrap">
      <div className="risk-contrib-table-grid factor-snapshot-header-row">
        <span>Metric</span>
        <span>Baseline</span>
        <span>Candidate</span>
        <span>Delta</span>
      </div>
      {rows.map((row) => (
        <div className={`risk-contrib-table-grid factor-shift-data-row comparison-data-row comparison-tone-${metricDeltaTone(row)}`} key={row.key}>
          <span className="factor-snapshot-primary">{row.label}</span>
          <span>{formatComparisonValue(row.baseline, row.format)}</span>
          <span>{formatComparisonValue(row.candidate, row.format)}</span>
          <span className={deltaToneClass(metricDeltaTone(row))}>{formatSignedComparisonValue(row.delta, row.format)}</span>
        </div>
      ))}
    </div>
  )
}

function DiagnosticsDeltaReviewSection({ activeReplay }: { activeReplay: PortfolioAllocationBacktestResponse }) {
  const sections = diagnosticsSectionConfigs(activeReplay)
  const diagnosticsStatus = activeReplay.candidate_result.status === 'degraded' || activeReplay.reference_result?.status === 'degraded'
    ? 'degraded'
    : activeReplay.diagnostics_comparison
      ? 'ok'
      : 'unavailable'

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Hypothetical Replay Diagnostics Delta Review</p></div>
        <p className="helper">Use this section to compare how the hypothetical replacement changes portfolio diagnostics under a shared replay basis. Read it as draft-only review support, not as approval, execution, or proof that the change should be made.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card">
          <p className="stat-label">Delta Meaning</p>
          <p className="summary-value">Candidate - baseline</p>
          <p className="helper">Every diagnostics delta in this section is shown as candidate minus baseline.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Diagnostics Status</p>
          <p className={`summary-value ${diagnosticsStatus === 'degraded' ? 'negative-text' : diagnosticsStatus === 'ok' ? 'positive-text' : 'neutral-text'}`}>{diagnosticsStatus}</p>
          <p className="helper">{diagnosticsStatus === 'degraded' ? 'Available with degradation. Interpret this comparison cautiously because one or both replay variants have limited diagnostics support.' : diagnosticsStatus === 'ok' ? 'Diagnostics comparison is available for both replay variants under the shared hypothetical review.' : 'Unavailable for this hypothetical review. The required diagnostics inputs were not available for one or both replay variants.'}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Snapshot Basis</p>
          <p className="summary-value">{replaySnapshotBasisLabel(activeReplay)}</p>
          <p className="helper">Baseline diagnostics reflect the current portfolio basis. Candidate diagnostics reflect a hypothetical replacement-intent variant and have not been applied to holdings.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">History Truth Class</p>
          <p className="summary-value">{replayHistoryTruthLabel(activeReplay)}</p>
          <p className="helper">{activeReplay.candidate_diagnostics?.provenance.note ?? 'Diagnostics compare replay-derived snapshots against historical market-data inputs when available.'}</p>
        </div>
      </div>
      {sections.length ? sections.map((section) => (
        <section key={section.key}>
          {(() => {
            const topCallout = buildDiagnosticsTopCallout(section.topCallout)
            return (
              <>
          <div className="section-header-inline sector-list-header">
            <div><p className="panel-label">{section.title}</p></div>
            <p className="helper">{section.helper}</p>
          </div>
          {topCallout ? (
            <div className="summary-card">
              <p className="stat-label">Most salient change in this group</p>
              <p className="summary-value">{topCallout.label}</p>
              <p className="helper">Selection rule: {formatSelectionRuleLabel(topCallout.selectionRule)}</p>
              <p className="helper">{topCallout.rationale}</p>
              <div className="list-table">
                <div className="list-row list-row-wide">
                  <span>Baseline</span>
                  <span>Candidate</span>
                  <span>Delta</span>
                </div>
                <div className="list-row list-row-wide">
                  <span>{topCallout.baseline}</span>
                  <span>{topCallout.candidate}</span>
                  <span>{topCallout.delta}</span>
                </div>
              </div>
            </div>
          ) : null}
          {section.rows.length ? <ComparisonTable rows={section.rows.map((row) => ({
            key: row.key,
            label: row.label,
            baseline: row.baseline_value,
            candidate: row.candidate_value,
            delta: row.delta_value,
            format: diagnosticsValueKind(row.key),
          }))} /> : <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">Unavailable for this hypothetical review. The required diagnostics inputs were not available for one or both replay variants.</p></div>}
              </>
            )
          })()}
        </section>
      )) : <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">Unavailable for this hypothetical review. The required diagnostics inputs were not available for one or both replay variants.</p></div>}
    </section>
  )
}

function StandardDiagnosticsComparisonSection({ activeReplay }: { activeReplay: PortfolioAllocationBacktestResponse }) {
  const sections = diagnosticsSectionConfigs(activeReplay)

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header"><div><p className="panel-label">Before / After Diagnostics</p></div><p className="helper">{activeReplay.candidate_diagnostics?.provenance.note ?? 'Diagnostics compare synthetic replay snapshots against historical market-data inputs.'} {replayHistoryTruthLabel(activeReplay)}.</p></div>
      {sections.map((section) => {
        const topCallout = buildDiagnosticsTopCallout(section.topCallout)

        return (
          <section key={section.key}>
            <div className="section-header-inline sector-list-header">
              <div><p className="panel-label">{section.title} Change</p></div>
              <p className="helper">{section.helper}</p>
            </div>
            {topCallout ? (
              <div className="summary-card">
                <p className="stat-label">Most salient change in this group</p>
                <p className="summary-value">{topCallout.label}</p>
                <p className="helper">Selection rule: {formatSelectionRuleLabel(topCallout.selectionRule)}</p>
                <p className="helper">{topCallout.rationale}</p>
                <div className="list-table">
                  <div className="list-row list-row-wide">
                    <span>Baseline</span>
                    <span>Candidate</span>
                    <span>Delta</span>
                  </div>
                  <div className="list-row list-row-wide">
                    <span>{topCallout.baseline}</span>
                    <span>{topCallout.candidate}</span>
                    <span>{topCallout.delta}</span>
                  </div>
                </div>
              </div>
            ) : null}
            {section.rows.length ? <ComparisonTable rows={section.rows.map((row) => ({
              key: row.key,
              label: row.label,
              baseline: row.baseline_value,
              candidate: row.candidate_value,
              delta: row.delta_value,
              format: diagnosticsValueKind(row.key),
            }))} /> : <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">Unavailable for this comparison. The required diagnostics inputs were not available for one or both replay variants.</p></div>}
          </section>
        )
      })}
    </section>
  )
}

export function SavedProposalReadoutSection({ proposal }: { proposal: VersionedProposalArtifact }) {
  const proposalReplay = activeReplayFromHypothetical(proposal.reviewSnapshot)
  if (!proposalReplay) return null
  if (!proposal.reviewSnapshotArtifactId) {
    throw new Error('Saved proposal is missing authoritative reviewSnapshotArtifactId')
  }
  if (!proposal.reviewSnapshotPMSummary) {
    throw new Error('Saved proposal is missing authoritative reviewSnapshotPMSummary mirror')
  }
  const canonicalProposal = assertSavedProposalArtifactIntegrity(proposal)
  const proposalSource = assertSavedProposalArtifactProposalSourceIntegrity(canonicalProposal).proposalSource
  const proposalSummaryRows = buildSummaryRows(proposalReplay)
  const proposalDeltaCallouts = buildReplayDeltaCallouts(proposalSummaryRows)
  const proposalDiagnosticsSections = diagnosticsSectionConfigs(proposalReplay)
  const proposalPMSummary = canonicalProposal.reviewSnapshotPMSummary
  const proposalCapture = canonicalProposal.proposalCapture

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Saved Proposal Review</p></div>
        <p className="helper">This is a saved proposal artifact, not live portfolio truth. It preserves prior hypothetical replay outputs and lineage exactly as reviewed when saved, even if the current draft or portfolio state has changed.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card">
          <p className="stat-label">Proposal Artifact</p>
          <p className="summary-value">v{canonicalProposal.versionNumber}</p>
          <p className="helper">Immutable local record of a previously reviewed hypothetical proposal.</p>
          <p className="helper">Review snapshot artifact: {canonicalProposal.reviewSnapshotArtifactId}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Lineage</p>
          <p className="summary-value">{proposalCapture.proposal.incumbent_symbol} -&gt; {proposalCapture.proposal.candidate_symbol}</p>
          <p className="helper">Shows how this proposal was derived, including ranking seed, replacement intent, and hypothetical replay context.</p>
          <p className="helper">Proposal source: {proposalSource.proposalSourceKind} · proposal truth: {proposalSource.proposalTruth} · portfolio truth: {proposalSource.portfolioTruth}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Proposal Basis</p>
          <p className="summary-value">{proposalCapture.review_basis.derivation_basis}</p>
          <p className="helper">Review-only basis captured from the persisted review snapshot artifact. This surface does not depend on current draft, live replay cache, or imported snapshot reconstruction.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Review State</p>
          <p className="summary-value">{canonicalProposal.reviewStatus}</p>
          <p className="helper">This proposal is saved for inspection only. It does not update holdings, confirm a decision, or reflect applied portfolio truth.</p>
        </div>
      </div>
      <div className="summary-card">
        <p className="panel-label">Proposal Lineage</p>
        <p className="helper">Workspace: {canonicalProposal.workspaceId} · Draft: {canonicalProposal.sourceDraftId} · Base node: {canonicalProposal.sourceBaseNodeId} · Saved at: {canonicalProposal.createdAt}</p>
        <p className="helper">Source: {proposalCapture.proposal.source} · Construction rule: {proposalCapture.review_basis.candidate_construction_rule}</p>
        <p className="helper">{formatReplayLineageHelper(canonicalProposal.reviewSnapshot)}</p>
      </div>
      <div className="summary-card">
        <p className="panel-label">Canonical PM Summary</p>
        <p className="helper">Role: {proposalPMSummary?.role ?? 'saved_proposal'} · provenance: {proposalPMSummary?.provenance.source ?? 'persisted_review_snapshot_artifact'} · benchmark separation: {proposalPMSummary?.review_basis.benchmark_separation ?? 'explicit_per_snapshot_benchmark_fields'}</p>
        <p className="helper">Methodology: {proposalPMSummary?.methodology.methodology ?? proposalReplay.methodology} · methodology truth: {proposalPMSummary?.methodology.methodology_provenance.methodology_truth ?? proposalReplay.methodology_provenance?.methodology_truth ?? 'n/a'} · assumptions truth: {proposalPMSummary?.methodology.methodology_provenance.assumptions_truth ?? proposalReplay.methodology_provenance?.assumptions_truth ?? 'n/a'}</p>
        <p className="helper">Analytics truth: {proposalPMSummary?.truth_labels.analytics_truth ?? proposalReplay.methodology_provenance?.analytics_truth ?? 'n/a'} · replay type: {proposalPMSummary?.replay_type ?? ('replay' in proposal.reviewSnapshot ? 'standard' : 'overlay_aware')} · diagnostics available: {proposalPMSummary?.diagnostics_summary.diagnostics_available ? 'yes' : 'no'}</p>
      </div>
      <div className="dashboard-summary compact-summary-grid backtest-workspace-summary">
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Benchmark</p><p className="summary-value">{proposalCapture.review_basis.benchmark_symbol}</p></div>
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Replay Window</p><p className="summary-value">{formatReplayWindow(proposalCapture.review_basis.replay_window.start_date, proposalCapture.review_basis.replay_window.end_date)}</p></div>
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Replay Setup</p><p className="summary-value">{proposalCapture.review_basis.rebalance_frequency}</p><p className="helper">{proposalCapture.review_basis.commission_bps} commission bps / {proposalCapture.review_basis.slippage_bps} slippage bps</p></div>
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Replay Status</p><p className="summary-value">{proposalReplay?.candidate_result.status ?? 'N/A'}</p><p className="helper">Snapshot of the saved hypothetical current-vs-candidate replay results captured with the proposal.</p></div>
      </div>
      {'overlay_application' in canonicalProposal.reviewSnapshot ? <div className="dashboard-summary compact-summary-grid backtest-workspace-summary"><div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Overlay State</p><p className="summary-value">{canonicalProposal.reviewSnapshot.overlay_application.overlay_status}</p><p className="helper">As of {canonicalProposal.reviewSnapshot.overlay_application.as_of_month_end}</p></div><div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Cash Residual</p><p className="summary-value">{formatWeightPct(canonicalProposal.reviewSnapshot.overlay_application.cash_residual_weight)}</p><p className="helper">Stored with the saved overlay-aware replay</p></div></div> : null}
      {proposalDeltaCallouts.length ? (
        <div className="dashboard-summary compact-summary-grid">
          {proposalDeltaCallouts.map((callout) => (
            <div className="summary-card" key={`proposal-callout-${callout.key}`}>
              <p className="stat-label">{callout.label}</p>
              <p className={`summary-value ${deltaToneClass(callout.tone)}`}>{callout.value}</p>
              <p className="helper">Replay Summary</p>
            </div>
          ))}
        </div>
      ) : null}
      {proposalDiagnosticsSections.length ? (
        <div className="dashboard-summary compact-summary-grid">
          {proposalDiagnosticsSections.map((section) => {
            const topCallout = buildDiagnosticsTopCallout(section.topCallout)
            return (
              <div className="summary-card" key={`proposal-diagnostics-${section.key}`}>
                <p className="stat-label">{section.title}</p>
                <p className="summary-value">{topCallout?.label ?? 'N/A'}</p>
                <p className="helper">Diagnostics Delta Summary</p>
              </div>
            )
          })}
        </div>
      ) : null}
      <div className="summary-card">
        <p className="panel-label">Review State</p>
        <p className="helper">This proposal is a saved review snapshot, not applied holdings, candidate truth, or live draft state.</p>
      </div>
    </section>
  )
}

export function PersistedConstructionArtifactReviewSection({ review }: { review: PersistedConstructionArtifactWorkspaceReview }) {
  const replay = review.replay.replay
  const summaryRows = buildSummaryRows(replay)
  const replayDeltaCallouts = buildReplayDeltaCallouts(summaryRows)

  return (
    <section className="dashboard-bottom-grid" data-testid="persisted-construction-artifact-review">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Artifact Review Replay</p></div>
        <p className="helper">Read-only replay review reopened from a persisted construction artifact review basis.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card">
          <p className="stat-label">Review Basis Id</p>
          <p className="summary-value">{review.constructionArtifactId}</p>
          <p className="helper">Canonical source: {review.reviewBasisSource?.canonical_source ?? review.replay.review_basis.canonical_source} · provenance: {review.reviewBasisSource?.basis_provenance_label ?? review.replay.review_basis.basis_provenance_label}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Truth Separation</p>
          <p className="summary-value">{review.replay.truth_separation.candidate_truth}</p>
          <p className="helper">Baseline {review.replay.truth_separation.baseline_truth} · candidate applied {String(review.replay.truth_separation.candidate_applied)}.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Consumption Mode</p>
          <p className="summary-value">{review.replay.truth_separation.consumption_mode}</p>
          <p className="helper">Review uses the artifact review replay path only.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Replay Status</p>
          <p className="summary-value">{replay.candidate_result.status}</p>
          <p className="helper">{formatReplayWindow(replay.candidate_result.start_date, replay.candidate_result.end_date)}</p>
        </div>
      </div>
      <div className="summary-card">
        <p className="panel-label">Replay Provenance</p>
        <p className="helper">Source: {review.replay.replay_provenance.source} · Policy: {review.replay.replay_provenance.policy_id} · Definition: {review.replay.replay_provenance.policy_definition_id}</p>
        <p className="helper">Ranking artifact: {review.replay.replay_provenance.ranked_universe_artifact_id ?? 'n/a'} · Ranking id: {review.replay.replay_provenance.ranking_id ?? 'n/a'} · Methodology: {review.replay.replay_provenance.ranking_methodology_id ?? 'n/a'}</p>
        <p className="helper">Current portfolio artifact: {review.replay.replay_provenance.current_portfolio_artifact_id ?? 'n/a'} · Baseline input: {review.replay.replay_provenance.baseline_input_source} · Candidate input: {review.replay.replay_provenance.candidate_input_source}</p>
        <p className="helper">Methodology provenance: {review.replay.replay.methodology_provenance.methodology_truth} · assumptions: {review.replay.replay.methodology_provenance.assumptions_truth} · analytics: {review.replay.replay.methodology_provenance.analytics_truth}</p>
      </div>
      <div className="summary-card">
        <p className="panel-label">Selection Rule Trace</p>
        <div className="list-table">
          <div className="list-row list-row-wide">
            <span>Rule</span>
            <span>Order</span>
            <span>Input</span>
            <span>Output</span>
          </div>
          {review.replay.replay_provenance.selection_rule_trace.steps.map((step) => (
            <div className="list-row list-row-wide" key={`${step.rule_id}-${step.rule_order}`}>
              <span>{step.rule_id}</span>
              <span>{step.rule_order}</span>
              <span>{step.input_candidate_symbols.join(', ') || 'n/a'}</span>
              <span>{step.output_candidate_symbols.join(', ') || 'n/a'}</span>
            </div>
          ))}
        </div>
      </div>
      {replayDeltaCallouts.length ? (
        <div className="dashboard-summary compact-summary-grid">
          {replayDeltaCallouts.map((callout) => (
            <div className="summary-card" key={`artifact-callout-${callout.key}`}>
              <p className="stat-label">{callout.label}</p>
              <p className={`summary-value ${deltaToneClass(callout.tone)}`}>{callout.value}</p>
              <p className="helper">Replay summary</p>
            </div>
          ))}
        </div>
      ) : null}
      {summaryRows.length ? <ComparisonTable rows={summaryRows} /> : null}
      <div className="split-grid dashboard-bottom-grid">
        <section>
          <div className="section-header-inline sector-list-header"><div><p className="panel-label">Baseline Weights</p></div></div>
          <div className="list-table">{review.replay.baseline_weights.map((row) => <div className="list-row" key={`artifact-baseline-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div>
        </section>
        <section>
          <div className="section-header-inline sector-list-header"><div><p className="panel-label">Candidate Weights</p></div></div>
          <div className="list-table">{review.replay.candidate_weights.map((row) => <div className="list-row" key={`artifact-candidate-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div>
        </section>
      </div>
    </section>
  )
}

export function PersistedOptimizerHandoffReviewSection({ review }: { review: PersistedOptimizerHandoffWorkspaceReview }) {
  const replay = review.replay.replay
  const summaryRows = buildSummaryRows(replay)
  const replayDeltaCallouts = buildReplayDeltaCallouts(summaryRows)
  const outputPolicy = review.replay.replay_provenance.replay_output_policy

  if (review.replay.optimizer_context && !review.replay.optimizer_context.objective) {
    throw new Error('Persisted optimizer handoff review is missing replay optimizer objective')
  }

  return (
    <section className="dashboard-bottom-grid" data-testid="persisted-optimizer-handoff-review">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Optimizer Handoff Review Replay</p></div>
        <p className="helper">Read-only replay review reopened by persisted optimizer handoff reference, with the artifact kept as backing lineage only.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card">
          <p className="stat-label">Review Basis Id</p>
          <p className="summary-value">{review.handoffReference.handoff_id}</p>
          <p className="helper">Canonical source: {review.reviewBasisSource?.canonical_source ?? review.replay.review_basis.canonical_source} · provenance: {review.reviewBasisSource?.basis_provenance_label ?? review.replay.review_basis.basis_provenance_label}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Artifact Lineage Id</p>
          <p className="summary-value">{review.handoffReference.artifact_id}</p>
          <p className="helper">Artifact-backed lineage and integrity reference only.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Truth Separation</p>
          <p className="summary-value">{review.replay.truth_separation.candidate_truth}</p>
          <p className="helper">Baseline {review.replay.truth_separation.baseline_truth} · candidate applied {String(review.replay.truth_separation.candidate_applied)}.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Replay Status</p>
          <p className="summary-value">{replay.candidate_result.status}</p>
          <p className="helper">{formatReplayWindow(replay.candidate_result.start_date, replay.candidate_result.end_date)}</p>
        </div>
      </div>
      <div className="summary-card">
        <p className="panel-label">Review Framing</p>
        <p className="helper">Truth class: optimizer-handoff-derived hypothetical evidence only. Review this as persisted optimizer output, not imported or applied portfolio truth.</p>
        <p className="helper">Validation status: {review.validation.validation_status} · consumption mode: {review.validation.truth_separation.consumption_mode} · reopen identity: {review.handoffReference.handoff_id}</p>
      </div>
      <div className="summary-card">
        <p className="panel-label">Replay Provenance</p>
        <p className="helper">Source: {review.replay.replay_provenance.source} · Benchmark: {review.replay.replay_provenance.benchmark_symbol} · Constraint fingerprint: {review.replay.replay_provenance.constraint_set_fingerprint}</p>
        <p className="helper">Artifact state: {review.replay.replay_provenance.artifact_state} · Optimizer status: {review.replay.replay_provenance.optimizer_status}</p>
        <p className="helper">Methodology provenance: {review.replay.replay.methodology_provenance.methodology_truth} · assumptions: {review.replay.replay.methodology_provenance.assumptions_truth} · analytics: {review.replay.replay.methodology_provenance.analytics_truth}</p>
      </div>
      <div className="summary-card">
        <p className="panel-label">Replay Output Policy</p>
        <p className="helper">Benchmark-relative path: {outputPolicy.section_trust.benchmark_relative_path} · factor path: {outputPolicy.section_trust.factor_model_path} · risk path: {outputPolicy.section_trust.risk_contribution_path}</p>
        <p className="helper">Eligible families: {outputPolicy.eligible_families.join(', ') || 'none'} · withheld families: {outputPolicy.withheld_families.join(', ') || 'none'}</p>
      </div>
      <div className="summary-card">
        <p className="panel-label">Return Basis Attestation</p>
        <p className="helper">Benchmark symbol: {review.replay.replay_provenance.return_basis_attestation.benchmark_symbol} · attested window: {formatReplayWindow(review.replay.replay_provenance.return_basis_attestation.history_start_date, review.replay.replay_provenance.return_basis_attestation.history_end_date)}</p>
        <p className="helper">Benchmark contract: {review.replay.replay_provenance.return_basis_attestation.benchmark_return_basis_contract} · factor contract: {review.replay.replay_provenance.return_basis_attestation.factor_return_basis_contract}</p>
      </div>
      {review.replay.optimizer_context ? (
        <div className="summary-card">
          <p className="panel-label">Optimizer Context</p>
          <p className="helper">Objective: {formatOptimizerObjectiveLabel(review.replay.optimizer_context.objective)} · solver: {review.replay.optimizer_context.run_summary.solver_id} · methodology: {review.replay.optimizer_context.run_summary.methodology_id}</p>
          <p className="helper">{review.replay.optimizer_context.objective.description ?? 'Canonical objective description unavailable.'}</p>
          <p className="helper">{formatOptimizerObjectiveDetails(review.replay.optimizer_context.objective)}</p>
          <p className="helper">Reasons: {review.replay.optimizer_context.reasons.join(', ') || 'none'} · stale inputs: {review.replay.optimizer_context.stale_inputs.join(', ') || 'none'} · degraded inputs: {review.replay.optimizer_context.degraded_inputs.join(', ') || 'none'}</p>
        </div>
      ) : null}
      {replayDeltaCallouts.length ? (
        <div className="dashboard-summary compact-summary-grid">
          {replayDeltaCallouts.map((callout) => (
            <div className="summary-card" key={`optimizer-handoff-callout-${callout.key}`}>
              <p className="stat-label">{callout.label}</p>
              <p className={`summary-value ${deltaToneClass(callout.tone)}`}>{callout.value}</p>
              <p className="helper">Replay summary</p>
            </div>
          ))}
        </div>
      ) : null}
      {summaryRows.length ? <ComparisonTable rows={summaryRows} /> : null}
      <div className="split-grid dashboard-bottom-grid">
        <section>
          <div className="section-header-inline sector-list-header"><div><p className="panel-label">Baseline Weights</p></div></div>
          <div className="list-table">{review.replay.baseline_weights.map((row) => <div className="list-row" key={`optimizer-handoff-baseline-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div>
        </section>
        <section>
          <div className="section-header-inline sector-list-header"><div><p className="panel-label">Candidate Weights</p></div></div>
          <div className="list-table">{review.replay.candidate_weights.map((row) => <div className="list-row" key={`optimizer-handoff-candidate-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div>
        </section>
      </div>
    </section>
  )
}

export function DiagnosticsChangeSection({ result, hypotheticalReplayResult }: { result: PortfolioAllocationBacktestResponse | null; hypotheticalReplayResult: HypotheticalReplayResponse | null }) {
  const activeReplay = activeReplayFromHypothetical(hypotheticalReplayResult) ?? result

  if (!activeReplay) return null
  if (hypotheticalReplayResult) return <DiagnosticsDeltaReviewSection activeReplay={activeReplay} />
  if (activeReplay.diagnostics_comparison) return <StandardDiagnosticsComparisonSection activeReplay={activeReplay} />

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Diagnostics Change</p></div>
        <p className="helper">Truth class: replay-derived hypothetical diagnostics only. Diagnostics comparison is not available for the current replay state.</p>
      </div>
      <div className="empty-state-panel compact-empty-state">
        <p className="empty-state-title">No diagnostics change view is available yet.</p>
        <p className="helper">Run a replay with diagnostics support to inspect before/after diagnostics change.</p>
      </div>
    </section>
  )
}

export function HypotheticalReplaySection({ result, draftSnapshot, replacementIntentDraft, formedCandidateArtifact, constructedCandidateArtifact, constructionConstraintValidationArtifact, selectedConstructionRuleId, hypotheticalReplayResult, savedProposalCount, onSaveProposal, onHypotheticalReplayResult, workspaceSource = null, persistedConstructionArtifactReview = null, persistedOptimizerHandoffReview = null }: HypotheticalReplaySectionProps) {
  const apiBase = useMemo(() => '/api', [])
  const isPersistedConstructionArtifactMode = Boolean(workspaceSource && 'kind' in workspaceSource && workspaceSource.kind === 'persisted_construction_artifact')
  const isPersistedOptimizerHandoffMode = Boolean(workspaceSource && 'kind' in workspaceSource && workspaceSource.kind === 'persisted_optimizer_handoff')
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [initialCapital, setInitialCapital] = useState('100000')
  const [rebalanceFrequency, setRebalanceFrequency] = useState<'none' | 'monthly' | 'quarterly'>('monthly')
  const [commissionBps, setCommissionBps] = useState('0')
  const [slippageBps, setSlippageBps] = useState('0')
  const [driftTolerancePct, setDriftTolerancePct] = useState('')
  const [replayBasisMode, setReplayBasisMode] = useState<ReplayBasisMode>('standard')
  const [overlayStatus, setOverlayStatus] = useState<OverlayStateInput['status']>('risk_reduced')
  const [overlayAsOfMonthEnd, setOverlayAsOfMonthEnd] = useState('2024-12-31')
  const [overlayConfirmationCount, setOverlayConfirmationCount] = useState('2')
  const [overlayRuleVersion, setOverlayRuleVersion] = useState('v1')
  const [hypotheticalLoading, setHypotheticalLoading] = useState(false)
  const [hypotheticalError, setHypotheticalError] = useState<string | null>(null)
  const [showHypotheticalReplayConfirmation, setShowHypotheticalReplayConfirmation] = useState(false)
  const hypotheticalPreflight = useMemo(() => buildHypotheticalReplayPreflight(replacementIntentDraft, constructedCandidateArtifact, selectedConstructionRuleId), [replacementIntentDraft, constructedCandidateArtifact, selectedConstructionRuleId])
  const constraintValidationMatchesIntent = Boolean(
    replacementIntentDraft
    && constructionConstraintValidationArtifact
    && constructionConstraintValidationArtifact.replacementIntentCreatedAt === replacementIntentDraft.createdAt
    && constructionConstraintValidationArtifact.replacementIntentBaseSymbol === replacementIntentDraft.baseSymbol
    && constructionConstraintValidationArtifact.replacementIntentCandidateSymbol === replacementIntentDraft.candidateSymbol,
  )
  const constraintValidationMatchesRule = Boolean(
    constructionConstraintValidationArtifact
    && constructionConstraintValidationArtifact.constructionRuleId === selectedConstructionRuleId,
  )
  const activeConstraintValidation = constraintValidationMatchesIntent && constraintValidationMatchesRule
    ? constructionConstraintValidationArtifact?.validation ?? null
    : null
  const replayConstraintStatus = activeConstraintValidation?.validation.status ?? 'blocked'
  const replayConstraintReady = replayConstraintStatus === 'ok'
  const activeReplay = activeReplayFromHypothetical(hypotheticalReplayResult) ?? result
  const baselineReplay = standardReplayFromHypothetical(hypotheticalReplayResult)
  const summaryRows = buildSummaryRows(activeReplay)
  const replayDeltaCallouts = useMemo(() => buildReplayDeltaCallouts(summaryRows), [summaryRows])
  const replayMetricRefusalLine = buildReplayMetricRefusalLine(activeReplay)
  const overlayState = useMemo<OverlayStateInput | null>(() => {
    if (!replacementIntentDraft || replayBasisMode !== 'overlay_aware') return null
    return {
      ...defaultOverlayState(replacementIntentDraft.benchmarkSymbol),
      status: overlayStatus,
      as_of_month_end: overlayAsOfMonthEnd,
      confirmation_count: Number(overlayConfirmationCount) || 0,
      rule_version: overlayRuleVersion || 'v1',
    }
  }, [overlayAsOfMonthEnd, overlayConfirmationCount, overlayRuleVersion, overlayStatus, replayBasisMode, replacementIntentDraft])

  async function runHypotheticalReplayPreview() {
    if (!draftSnapshot || !replacementIntentDraft || !constructedCandidateArtifact || !activeConstraintValidation || activeConstraintValidation.validation.status !== 'ok') return

    setHypotheticalLoading(true)
    setHypotheticalError(null)

    try {
      const isOverlayAware = replayBasisMode === 'overlay_aware'
      const response = await fetch(`${apiBase}${isOverlayAware ? '/backtests/portfolio-allocation/replacement-intent-overlay-preview' : '/backtests/portfolio-allocation/replacement-intent-preview'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          snapshot: {
            snapshot_version: draftSnapshot.snapshotVersion,
            base_currency: draftSnapshot.baseCurrency,
            imported_meta: {
              importer: draftSnapshot.importedMeta.importer,
              statement_period: draftSnapshot.importedMeta.statementPeriod,
              imported_at: draftSnapshot.importedMeta.importedAt,
              source_file_names: draftSnapshot.importedMeta.sourceFileNames,
            },
            positions: draftSnapshot.positions.map((position) => ({
              symbol: position.symbol,
              market_value: position.marketValue,
              quantity: position.quantity ?? null,
              currency: position.currency ?? null,
              sector: position.sector ?? null,
              name: position.name ?? null,
              source_type: position.sourceType ?? null,
            })),
            cash_balances: draftSnapshot.cashBalances.map((balance) => ({ currency: balance.currency, amount: balance.amount })),
          },
          replacement_intent: {
            kind: replacementIntentDraft.kind,
            source: replacementIntentDraft.source,
            created_at: replacementIntentDraft.createdAt,
            draft_id: replacementIntentDraft.draftId,
            workspace_id: replacementIntentDraft.workspaceId,
            base_node_id: replacementIntentDraft.baseNodeId,
            base_symbol: replacementIntentDraft.baseSymbol,
            candidate_symbol: replacementIntentDraft.candidateSymbol,
            seeded_from_draft_id: replacementIntentDraft.seededFromDraftId,
            seed_ranking_id: replacementIntentDraft.seedRankingId,
            seed_methodology_id: replacementIntentDraft.seedMethodologyId,
            seed_ranking_basis_date: replacementIntentDraft.seedRankingBasisDate,
            peer_group: replacementIntentDraft.peerGroup,
            benchmark_symbol: replacementIntentDraft.benchmarkSymbol,
            lookback_months: replacementIntentDraft.lookbackMonths,
            confidence: replacementIntentDraft.confidence,
            holdings_support: replacementIntentDraft.holdingsSupport,
            warning_count: replacementIntentDraft.warningCount,
          },
          constructed_candidate: constructedCandidateArtifact.construction,
          constraint_validation: activeConstraintValidation,
          ...(isOverlayAware ? { overlay_state: overlayState } : {}),
          benchmark_symbol: replacementIntentDraft.benchmarkSymbol,
          start_date: startDate,
          end_date: endDate,
          initial_capital: Number(initialCapital),
          rebalance_frequency: rebalanceFrequency,
          commission_bps: Number(commissionBps) || 0,
          slippage_bps: Number(slippageBps) || 0,
          drift_tolerance_pct: driftTolerancePct ? Number(driftTolerancePct) : null,
          base_currency: draftSnapshot.baseCurrency ?? 'USD',
          price_basis: 'adjusted_close',
          execution_price_field: 'close',
          execution_lag_days: 1,
        }),
      })
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Hypothetical replay preview failed')
      }
      onHypotheticalReplayResult((await response.json()) as HypotheticalReplayResponse)
      setShowHypotheticalReplayConfirmation(false)
    } catch (caughtError) {
      setHypotheticalError(caughtError instanceof Error ? caughtError.message : 'Hypothetical replay preview failed')
    } finally {
      setHypotheticalLoading(false)
    }
  }

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header"><div><p className="panel-label">Hypothetical Replay</p></div><p className="helper">Truth class: replay-derived hypothetical evidence only. Review this as a draft-only comparison built from one explicit construction output handoff.</p></div>
      {isPersistedConstructionArtifactMode && persistedConstructionArtifactReview ? (
        <PersistedConstructionArtifactReviewSection review={persistedConstructionArtifactReview} />
      ) : null}
      {isPersistedOptimizerHandoffMode && persistedOptimizerHandoffReview ? (
        <PersistedOptimizerHandoffReviewSection review={persistedOptimizerHandoffReview} />
      ) : null}
      {isPersistedConstructionArtifactMode || isPersistedOptimizerHandoffMode ? null : replacementIntentDraft ? (
        <>
            <div className="summary-card">
              <p className="panel-label">Replay Preflight</p>
              <p className="helper">Check the construction output handoff first so replay only runs from explicit review input.</p>
              <div className="dashboard-summary compact-summary-grid">
                <div className="summary-card"><p className="stat-label">Preflight Status</p><p className={`summary-value ${preflightToneClass(hypotheticalPreflight.overallStatus)}`}>{hypotheticalPreflight.overallStatus === 'ready' ? 'Ready for backend validation' : 'Blocked before preview'}</p></div>
                <div className="summary-card"><p className="stat-label">Intent Pair</p><p className="summary-value">{replacementIntentDraft.baseSymbol} -&gt; {replacementIntentDraft.candidateSymbol}</p></div>
                <div className="summary-card"><p className="stat-label">Incumbent Starting Weight</p><p className="summary-value">{hypotheticalPreflight.incumbentWeight == null ? 'n/a' : formatPct(hypotheticalPreflight.incumbentWeight * 100)}</p></div>
                <div className="summary-card"><p className="stat-label">Construction Constraints</p><p className={`summary-value ${replayConstraintReady ? 'positive-text' : 'negative-text'}`}>{replayConstraintReady ? 'Pass' : activeConstraintValidation?.validation.status === 'rejected' ? 'Rejected' : 'Blocked'}</p><p className="helper">{!activeConstraintValidation ? 'Run construction constraints before replay.' : activeConstraintValidation.validation.status === 'ok' ? 'Constraint validation passed for the current construction output.' : activeConstraintValidation.rejection_reason ?? 'Constraint validation did not pass, so replay remains unavailable.'}</p></div>
              </div>
              <div className="list-table">{hypotheticalPreflight.checks.map((check) => <div className="list-row list-row-wide" key={check.label}><span>{check.label}</span><span className={preflightToneClass(check.status)}>{check.status === 'ready' ? 'Ready' : check.status === 'blocked' ? 'Blocked' : 'Pending backend'}</span><span>{check.detail}</span></div>)}</div>
            </div>
          {!hypotheticalReplayResult ? <p className="helper">No hypothetical replay has been run for this replacement intent yet.</p> : null}
          {!showHypotheticalReplayConfirmation ? (
            <div className="actions backtest-actions"><button className="secondary-button" disabled={hypotheticalPreflight.overallStatus === 'blocked' || !replayConstraintReady} type="button" onClick={() => setShowHypotheticalReplayConfirmation(true)}>Preview Hypothetical Replay</button><p className="helper">Use replay to validate the explicit construction output under a shared portfolio basis. Replay stays unavailable until construction constraints pass.</p></div>
          ) : (
            <div className="summary-card">
              <p className="panel-label">Preview hypothetical current-vs-candidate replay</p>
              <p className="helper">This creates a draft-only replay from the explicit construction artifact. It does not apply the replacement, endorse it, or run broader construction logic.</p>
              <div className="dashboard-summary compact-summary-grid"><div className="summary-card"><p className="stat-label">Baseline</p><p className="summary-value">Current draft or imported portfolio state</p></div><div className="summary-card"><p className="stat-label">Hypothetical Candidate</p><p className="summary-value">Single constructed candidate from one explicit rule</p></div><div className="summary-card"><p className="stat-label">Intent Source</p><p className="summary-value">Replacement intent with explicit construction output</p></div><div className="summary-card"><p className="stat-label">Replay Basis</p><p className="summary-value">{replayBasisMode === 'overlay_aware' ? 'Overlay-aware hypothetical replay' : 'Hypothetical current-vs-candidate comparison'}</p></div></div>
              <div className="summary-card">
                <p className="panel-label">Replay Basis Selection</p>
                <p className="helper">Choose one explicit replay basis. Standard replay remains available as the fallback path.</p>
                <div className="list-table">
                  <label className="list-row list-row-wide">
                    <span>Standard replay</span>
                    <span>Current-vs-candidate hypothetical comparison without overlay scaling.</span>
                    <span><input checked={replayBasisMode === 'standard'} name="replay-basis-mode" onChange={() => setReplayBasisMode('standard')} type="radio" /></span>
                  </label>
                  <label className="list-row list-row-wide">
                    <span>Overlay-aware replay</span>
                    <span>Uses the selected overlay review state for the hypothetical candidate only and carries cash residual explicitly.</span>
                    <span><input checked={replayBasisMode === 'overlay_aware'} name="replay-basis-mode" onChange={() => setReplayBasisMode('overlay_aware')} type="radio" /></span>
                  </label>
                </div>
              </div>
              {replayBasisMode === 'overlay_aware' ? (
                <div className="summary-card">
                  <p className="panel-label">Overlay State</p>
                  <p className="helper">Overlay-aware replay requires an explicit replayable overlay state. This remains hypothetical candidate framing only.</p>
                  <div className="dashboard-summary compact-summary-grid">
                    <div className="summary-card"><p className="stat-label">Overlay Id</p><p className="summary-value">benchmark_trend_overlay_v1</p></div>
                    <div className="summary-card"><p className="stat-label">Signal Basis</p><p className="summary-value">10_month_sma_month_end</p></div>
                    <div className="summary-card"><p className="stat-label">Candidate Framing</p><p className="summary-value">Overlay applies to candidate only</p></div>
                    <div className="summary-card"><p className="stat-label">Cash Residual</p><p className="summary-value">Backend-derived from overlay state</p></div>
                  </div>
                  <div className="split-grid compact-split-grid"><label className="field-group"><span className="field-label">Overlay Status</span><select className="path-input" value={overlayStatus} onChange={(event) => setOverlayStatus(event.target.value as OverlayStateInput['status'])}><option value="risk_reduced">risk_reduced</option><option value="risk_on">risk_on</option><option value="unconfirmed">unconfirmed</option><option value="unavailable">unavailable</option></select><span className="helper">Unconfirmed or unavailable overlay states keep this replay hypothetical and may limit interpretation quality.</span></label><label className="field-group"><span className="field-label">As Of Month End</span><input className="path-input" type="date" value={overlayAsOfMonthEnd} onChange={(event) => setOverlayAsOfMonthEnd(event.target.value)} /></label></div>
                  <div className="split-grid compact-split-grid"><label className="field-group"><span className="field-label">Confirmation Count</span><input className="path-input" inputMode="numeric" value={overlayConfirmationCount} onChange={(event) => setOverlayConfirmationCount(event.target.value)} /></label><label className="field-group"><span className="field-label">Rule Version</span><input className="path-input" value={overlayRuleVersion} onChange={(event) => setOverlayRuleVersion(event.target.value)} /></label></div>
                  <p className="helper">Overlay-aware replay preserves standard hypothetical semantics. It does not imply execution, approval, or a standalone overlay workflow.</p>
                </div>
              ) : null}
              <div className="split-grid compact-split-grid"><label className="field-group"><span className="field-label">Start Date</span><input className="path-input" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label><label className="field-group"><span className="field-label">End Date</span><input className="path-input" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label></div>
              <div className="split-grid compact-split-grid"><label className="field-group"><span className="field-label">Initial Capital</span><input className="path-input" inputMode="decimal" value={initialCapital} onChange={(event) => setInitialCapital(event.target.value)} /></label><label className="field-group"><span className="field-label">Rebalance Frequency</span><select className="path-input" value={rebalanceFrequency} onChange={(event) => setRebalanceFrequency(event.target.value as 'none' | 'monthly' | 'quarterly')}><option value="none">None</option><option value="monthly">Monthly</option><option value="quarterly">Quarterly</option></select></label></div>
              <div className="split-grid compact-split-grid"><label className="field-group"><span className="field-label">Commission Bps</span><input className="path-input" inputMode="decimal" value={commissionBps} onChange={(event) => setCommissionBps(event.target.value)} /></label><label className="field-group"><span className="field-label">Slippage Bps</span><input className="path-input" inputMode="decimal" value={slippageBps} onChange={(event) => setSlippageBps(event.target.value)} /></label></div>
              <label className="field-group"><span className="field-label">Drift Tolerance Pct</span><input className="path-input" inputMode="decimal" value={driftTolerancePct} onChange={(event) => setDriftTolerancePct(event.target.value)} placeholder="Optional" /></label>
              <div className="actions dashboard-edit-actions dashboard-edit-actions-compact"><button className={`primary-button${hypotheticalLoading ? ' button-loading' : ''}`} type="button" disabled={hypotheticalLoading} onClick={() => void runHypotheticalReplayPreview()}>{hypotheticalLoading ? 'Running Preview...' : 'Run Preview'}</button><button className="secondary-button" type="button" onClick={() => setShowHypotheticalReplayConfirmation(false)}>Cancel</button></div>
            </div>
          )}
          {hypotheticalError ? <p className="error">Replay preview failed: {hypotheticalError}</p> : null}
          {hypotheticalReplayResult ? (
            <>
              <div className="summary-card"><p className="helper">Baseline: current portfolio basis</p><p className="helper">Candidate: hypothetical replacement-intent variant</p><p className="helper">Status: not applied to holdings</p></div>
              <section><div className="section-header-inline sector-list-header"><div><p className="panel-label">Replay Decision Readout</p></div></div><p className="helper">Start here before reading the charts and tables. Confirm what this replay compares, what changed in the candidate, and what did not.</p><div className="dashboard-summary compact-summary-grid"><div className="summary-card"><p className="stat-label">Replay Type</p><p className="summary-value">{isOverlayAwareReplayResponse(hypotheticalReplayResult) ? 'Overlay-aware hypothetical replay' : 'Hypothetical current-vs-candidate'}</p></div><div className="summary-card"><p className="stat-label">Intent Pair</p><p className="summary-value">{hypotheticalReplayResult.proposal.incumbent_symbol} -&gt; {hypotheticalReplayResult.proposal.candidate_symbol}</p></div><div className="summary-card"><p className="stat-label">Baseline Basis</p><p className="summary-value">Current draft or imported portfolio state</p></div><div className="summary-card"><p className="stat-label">Candidate Basis</p><p className="summary-value">{isOverlayAwareReplayResponse(hypotheticalReplayResult) ? 'Single replacement-intent variant with overlay-aware candidate scaling' : 'Single replacement-intent variant'}</p></div></div><div className="dashboard-summary compact-summary-grid"><div className="summary-card"><p className="stat-label">What Changed</p><p className="helper">{isOverlayAwareReplayResponse(hypotheticalReplayResult) ? `The candidate replay first replaces ${hypotheticalReplayResult.proposal.incumbent_symbol} with ${hypotheticalReplayResult.proposal.candidate_symbol}, then applies the selected overlay state to the hypothetical candidate only.` : `The candidate replay changes one thing only: it replaces ${hypotheticalReplayResult.proposal.incumbent_symbol} with ${hypotheticalReplayResult.proposal.candidate_symbol} inside a hypothetical draft-only portfolio variant.`}</p></div><div className="summary-card"><p className="stat-label">What Did Not Change</p><p className="helper">No holdings have been updated. No construction, optimization, turnover repair, or execution logic has been applied.</p></div></div></section>
              <div className="summary-card"><p className="panel-label">Replay Metadata</p><p className="helper">Source: {hypotheticalReplayResult.proposal.source} · Draft: {hypotheticalReplayResult.proposal.draft_id} · Base node: {hypotheticalReplayResult.proposal.base_node_id}</p><p className="helper">Derivation: {hypotheticalReplayResult.derivation.baseline_basis} · {hypotheticalReplayResult.derivation.candidate_construction_rule}</p>{isOverlayAwareReplayResponse(hypotheticalReplayResult) ? <p className="helper">Overlay basis: {hypotheticalReplayResult.overlay_application.overlay_id} · {hypotheticalReplayResult.overlay_application.overlay_status} · Cash residual {formatWeightPct(hypotheticalReplayResult.overlay_application.cash_residual_weight)}</p> : null}<div className="actions dashboard-edit-actions dashboard-edit-actions-compact"><button className="primary-button" type="button" onClick={() => void onSaveProposal()}>Save Proposal v{savedProposalCount + 1}</button><p className="helper">Create an immutable reviewed proposal artifact from this hypothetical replay. It remains separate from portfolio truth and does not apply any holdings change.</p></div></div>
              <div className="dashboard-summary compact-summary-grid backtest-workspace-summary"><div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Replay Status</p><p className="summary-value">{activeReplay?.candidate_result.status ?? 'N/A'}</p><p className="helper">Candidate replay status under the shared implementation window</p></div><div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Benchmark</p><p className="summary-value">{activeReplay?.candidate_result.benchmark_symbol ?? 'N/A'}</p><p className="helper">Shared benchmark for baseline and candidate replay</p></div><div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Replay Window</p><p className="summary-value">{formatReplayWindow(activeReplay?.candidate_result.start_date, activeReplay?.candidate_result.end_date)}</p><p className="helper">Baseline and candidate are shown on the same replay window. Treat the candidate as a hypothetical test of the intent, not as an approved portfolio change.</p></div><div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Replay Setup</p><p className="summary-value">{activeReplay?.candidate_result.rebalance_frequency ?? 'N/A'}</p><p className="helper">{activeReplay ? `${activeReplay.candidate_result.commission_bps} commission bps / ${activeReplay.candidate_result.slippage_bps} slippage bps` : 'N/A'}</p></div></div>
              {isOverlayAwareReplayResponse(hypotheticalReplayResult) ? <div className="dashboard-summary compact-summary-grid backtest-workspace-summary"><div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Overlay State</p><p className="summary-value">{hypotheticalReplayResult.overlay_application.overlay_status}</p><p className="helper">As of {hypotheticalReplayResult.overlay_application.as_of_month_end}</p></div><div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Overlay Basis</p><p className="summary-value">{hypotheticalReplayResult.overlay_application.overlay_id}</p><p className="helper">Candidate-only application: {hypotheticalReplayResult.overlay_application.applied_to_candidate_only ? 'yes' : 'no'}</p></div><div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Risky Weight Scale</p><p className="summary-value">{formatWeightPct(hypotheticalReplayResult.overlay_application.risky_weight_scale)}</p><p className="helper">Backend-authored overlay scaling</p></div><div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Cash Residual</p><p className="summary-value">{formatWeightPct(hypotheticalReplayResult.overlay_application.cash_residual_weight)}</p><p className="helper">Residual held as hypothetical cash only</p></div></div> : null}
              <section className="dashboard-bottom-grid"><div className="section-header-inline sector-list-header"><div><p className="panel-label">Replay Summary</p></div><p className="helper">Baseline and candidate are shown on the same replay window. Treat the candidate as a hypothetical test of the intent, not as an approved portfolio change.</p></div>{replayMetricRefusalLine ? <p className="helper">{replayMetricRefusalLine}</p> : null}{summaryRows.length && replayDeltaCallouts.length ? <div className="dashboard-summary compact-summary-grid">{replayDeltaCallouts.map((callout) => <div className="summary-card" key={callout.key}><p className="stat-label">{callout.label}</p><p className={`summary-value ${deltaToneClass(callout.tone)}`}>{callout.value}</p><p className="helper">{callout.rationale}</p></div>)}</div> : null}{summaryRows.length ? <ComparisonTable rows={summaryRows} /> : <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">Run with baseline comparison enabled to view before/after replay metrics.</p></div>}</section>
              {activeReplay ? <BacktestCurve result={activeReplay} /> : null}
              {isOverlayAwareReplayResponse(hypotheticalReplayResult) ? <div className="split-grid dashboard-bottom-grid"><section><div className="section-header-inline sector-list-header"><div><p className="panel-label">Baseline Weights</p></div></div><div className="list-table">{hypotheticalReplayResult.baseline_weights.map((row) => <div className="list-row" key={`baseline-weight-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div></section><section><div className="section-header-inline sector-list-header"><div><p className="panel-label">Candidate Pre-Overlay</p></div></div><div className="list-table">{hypotheticalReplayResult.candidate_weights_pre_overlay.map((row) => <div className="list-row" key={`candidate-pre-weight-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div></section></div> : <div className="split-grid dashboard-bottom-grid"><section><div className="section-header-inline sector-list-header"><div><p className="panel-label">Baseline Weights</p></div></div><div className="list-table">{hypotheticalReplayResult.baseline_weights.map((row) => <div className="list-row" key={`baseline-weight-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div></section><section><div className="section-header-inline sector-list-header"><div><p className="panel-label">Candidate Weights</p></div></div><div className="list-table">{hypotheticalReplayResult.candidate_weights.map((row) => <div className="list-row" key={`candidate-weight-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div></section></div>}
              {isOverlayAwareReplayResponse(hypotheticalReplayResult) ? <section className="dashboard-bottom-grid"><div className="section-header-inline sector-list-header"><div><p className="panel-label">Candidate Post-Overlay</p></div></div><div className="list-table">{hypotheticalReplayResult.candidate_weights_post_overlay.map((row) => <div className="list-row" key={`candidate-post-weight-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div></section> : null}
              {hypotheticalReplayResult.warnings.length ? <div className="summary-card"><p className="panel-label">Warnings</p>{hypotheticalReplayResult.warnings.map((warning) => <p className="helper" key={warning}>{warning}</p>)}</div> : null}
              <p className="helper">Use this surface to review whether the explicit replacement intent produces a meaningfully different hypothetical path under a shared window. It does not recommend the change or prove it should be applied.</p>
            </>
          ) : null}
        </>
      ) : isPersistedConstructionArtifactMode || isPersistedOptimizerHandoffMode ? null : (
        <p className="helper">An explicit replacement intent is required before a hypothetical replay can run.</p>
      )}
    </section>
  )
}

export function PortfolioAllocationBacktestPanel({ result, onResult, analysis }: Props) {
  const apiBase = useMemo(() => '/api', [])
  const [portfolioName, setPortfolioName] = useState('Candidate')
  const [benchmarkSymbol, setBenchmarkSymbol] = useState('SPY')
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [initialCapital, setInitialCapital] = useState('100000')
  const [rebalanceFrequency, setRebalanceFrequency] = useState<'none' | 'monthly' | 'quarterly'>('monthly')
  const [commissionBps, setCommissionBps] = useState('0')
  const [slippageBps, setSlippageBps] = useState('0')
  const [driftTolerancePct, setDriftTolerancePct] = useState('')
  const [candidateWeights, setCandidateWeights] = useState<AllocationWeightRow[]>([{ symbol: 'SPY', target_weight: '0.60' }, { symbol: 'TLT', target_weight: '0.40' }])
  const [referenceWeights, setReferenceWeights] = useState<AllocationWeightRow[]>([{ symbol: 'SPY', target_weight: '1.00' }])
  const [includeReference, setIncludeReference] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const candidateWeightTotal = totalWeight(candidateWeights)
  const referenceWeightTotal = totalWeight(referenceWeights)
  const baselineRows = useMemo(() => deriveBaselineRows(analysis), [analysis])
  const importedPortfolioValue = analysis?.overview.total_market_value ?? null
  const importedPositionsCount = analysis?.snapshot.positions.length ?? 0

  useEffect(() => {
    if (!baselineRows.length) return
    setReferenceWeights((current) => (current.length === 1 && current[0]?.symbol === 'SPY' && current[0]?.target_weight === '1.00') ? baselineRows : current)
  }, [baselineRows])

  function updateWeightRow(kind: 'candidate' | 'reference', index: number, key: keyof AllocationWeightRow, value: string) {
    const setter = kind === 'candidate' ? setCandidateWeights : setReferenceWeights
    setter((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row))
  }

  function addWeightRow(kind: 'candidate' | 'reference') {
    const setter = kind === 'candidate' ? setCandidateWeights : setReferenceWeights
    setter((current) => [...current, { symbol: '', target_weight: '' }])
  }

  function removeWeightRow(kind: 'candidate' | 'reference', index: number) {
    const setter = kind === 'candidate' ? setCandidateWeights : setReferenceWeights
    setter((current) => current.filter((_, rowIndex) => rowIndex !== index))
  }

  async function runAllocationBacktest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const capital = Number(initialCapital)
    const candidate = parseWeightRows(candidateWeights)
    const reference = parseWeightRows(referenceWeights)
    if (!candidate.length) {
      setError('Enter at least one candidate weight.')
      return
    }
    if (candidate.some((row) => !Number.isFinite(row.target_weight) || row.target_weight < 0)) {
      setError('Candidate weights must be non-negative numbers.')
      return
    }
    if (Math.abs(candidateWeightTotal - 1) > 0.01) {
      setError('Candidate weights must sum to approximately 1.0.')
      return
    }
    if (includeReference) {
      if (!reference.length) {
        setError('Enter at least one baseline weight or disable comparison.')
        return
      }
      if (reference.some((row) => !Number.isFinite(row.target_weight) || row.target_weight < 0)) {
        setError('Baseline weights must be non-negative numbers.')
        return
      }
      if (Math.abs(referenceWeightTotal - 1) > 0.01) {
        setError('Baseline weights must sum to approximately 1.0.')
        return
      }
    }
    if (endDate < startDate) {
      setError('End date must be on or after start date.')
      return
    }
    if (!Number.isFinite(capital) || capital <= 0) {
      setError('Initial capital must be a positive number.')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${apiBase}/backtests/portfolio-allocation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          portfolio_name: portfolioName,
          weights: candidate,
          reference_weights: includeReference ? reference : null,
          benchmark_symbol: benchmarkSymbol,
          start_date: startDate,
          end_date: endDate,
          initial_capital: capital,
          rebalance_frequency: rebalanceFrequency,
          commission_bps: Number(commissionBps) || 0,
          slippage_bps: Number(slippageBps) || 0,
          drift_tolerance_pct: driftTolerancePct ? Number(driftTolerancePct) : null,
          price_basis: 'adjusted_close',
          execution_price_field: 'close',
          execution_lag_days: 1,
          base_currency: 'USD',
        }),
      })
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Portfolio improvement replay failed')
      }
      onResult((await response.json()) as PortfolioAllocationBacktestResponse)
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Portfolio improvement replay failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="workspace-section">
      <div className="dashboard-summary compact-summary-grid backtest-workspace-summary">
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card">
          <p className="stat-label">Current Import</p>
          <p className="summary-value">{formatMoney(importedPortfolioValue)}</p>
          <p className="helper">{analysis ? `${importedPositionsCount} imported holdings ready for baseline seeding` : 'Import a portfolio to seed the baseline automatically'}</p>
        </div>
        <div className={`summary-card metric-card backtest-summary-card ${totalTone(referenceWeightTotal, includeReference) === 'positive' ? 'metric-card-cool' : totalTone(referenceWeightTotal, includeReference) === 'negative' ? 'metric-card-hot' : 'metric-card-neutral'}`}>
          <p className="stat-label">Baseline Total</p>
          <p className={`summary-value ${deltaToneClass(totalTone(referenceWeightTotal, includeReference))}`}>{formatNumber(referenceWeightTotal, 2)}</p>
          <p className="helper">{includeReference ? `${referenceWeights.length} rows / comparison enabled` : 'Comparison disabled'}</p>
        </div>
        <div className={`summary-card metric-card backtest-summary-card ${totalTone(candidateWeightTotal) === 'positive' ? 'metric-card-cool' : totalTone(candidateWeightTotal) === 'negative' ? 'metric-card-hot' : 'metric-card-neutral'}`}>
          <p className="stat-label">Candidate Total</p>
          <p className={`summary-value ${deltaToneClass(totalTone(candidateWeightTotal))}`}>{formatNumber(candidateWeightTotal, 2)}</p>
          <p className="helper">{candidateWeights.length} rows / target should be 1.00</p>
        </div>
        <div className="summary-card metric-card metric-card-warm backtest-summary-card">
          <p className="stat-label">Replay Setup</p>
          <p className="summary-value">{rebalanceFrequency}</p>
          <p className="helper">{benchmarkSymbol} benchmark / {formatMoney(Number(initialCapital) || null)} initial capital</p>
        </div>
      </div>

      {result ? (
        <div className="summary-card">
          <p className="panel-label">Replay Engine Status</p>
          <p className="helper">The lower-level builder has a completed replay result available for shell-owned review surfaces.</p>
          <div className="dashboard-summary compact-summary-grid">
            <div className="summary-card"><p className="stat-label">Candidate Status</p><p className="summary-value">{result.candidate_result.status}</p></div>
            <div className="summary-card"><p className="stat-label">Benchmark</p><p className="summary-value">{result.candidate_result.benchmark_symbol}</p></div>
            <div className="summary-card"><p className="stat-label">Replay Window</p><p className="summary-value">{formatReplayWindow(result.candidate_result.start_date, result.candidate_result.end_date)}</p></div>
            <div className="summary-card"><p className="stat-label">Comparison</p><p className="summary-value">{result.reference_result ? 'enabled' : 'disabled'}</p></div>
          </div>
        </div>
      ) : null}

      <form className="import-form" onSubmit={runAllocationBacktest}>
        <div className="split-grid compact-split-grid backtest-config-grid">
          <label className="field-group">
            <span className="field-label">Portfolio Name</span>
            <input className="path-input" value={portfolioName} onChange={(event) => setPortfolioName(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Benchmark Symbol</span>
            <input className="path-input" value={benchmarkSymbol} onChange={(event) => setBenchmarkSymbol(event.target.value.toUpperCase())} />
          </label>
        </div>
        <div className="split-grid compact-split-grid">
          <label className="field-group">
            <span className="field-label">Start Date</span>
            <input className="path-input" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">End Date</span>
            <input className="path-input" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          </label>
        </div>
        <div className="split-grid compact-split-grid">
          <label className="field-group">
            <span className="field-label">Initial Capital</span>
            <input className="path-input" inputMode="decimal" value={initialCapital} onChange={(event) => setInitialCapital(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Rebalance Frequency</span>
            <select className="path-input" value={rebalanceFrequency} onChange={(event) => setRebalanceFrequency(event.target.value as 'none' | 'monthly' | 'quarterly')}>
              <option value="none">None</option>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
            </select>
          </label>
        </div>
        <div className="split-grid compact-split-grid">
          <label className="field-group">
            <span className="field-label">Commission Bps</span>
            <input className="path-input" inputMode="decimal" value={commissionBps} onChange={(event) => setCommissionBps(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Slippage Bps</span>
            <input className="path-input" inputMode="decimal" value={slippageBps} onChange={(event) => setSlippageBps(event.target.value)} />
          </label>
        </div>
        <label className="field-group">
          <span className="field-label">Drift Tolerance Pct</span>
          <input className="path-input" inputMode="decimal" value={driftTolerancePct} onChange={(event) => setDriftTolerancePct(event.target.value)} placeholder="Optional" />
        </label>

        <div className="split-grid dashboard-bottom-grid">
          <section className={sectionCardClass('baseline')}>
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Baseline Portfolio</p></div><div className="toggle-group"><p className={`helper ${deltaToneClass(totalTone(referenceWeightTotal, includeReference))}`}>Total {formatNumber(referenceWeightTotal, 2)}</p><button className={`toggle-chip${includeReference ? ' active' : ''}`} onClick={() => setIncludeReference((value) => !value)} type="button">Compare</button><button className="toggle-chip" onClick={() => setReferenceWeights(baselineRows)} type="button">Use Current Portfolio</button><button className="toggle-chip" disabled={!includeReference} onClick={() => addWeightRow('reference')} type="button">Add Row</button></div></div>
            <p className="helper backtest-section-helper">Use the imported book as the before-state or define a custom baseline sleeve.</p>
            <div className="factor-snapshot-table-wrap">
              {referenceWeights.map((row, index) => (
                <div className="allocation-weight-row" key={`reference-${index}`}>
                  <input aria-label={`reference-symbol-${index}`} className="path-input" disabled={!includeReference} value={row.symbol} onChange={(event) => updateWeightRow('reference', index, 'symbol', event.target.value)} placeholder="Symbol" />
                  <input aria-label={`reference-weight-${index}`} className="path-input" disabled={!includeReference} value={row.target_weight} onChange={(event) => updateWeightRow('reference', index, 'target_weight', event.target.value)} placeholder="1.00" />
                  <span className={`allocation-weight-badge ${deltaToneClass(totalTone(Number(row.target_weight) || 0, includeReference))}`}>{formatPct((Number(row.target_weight) || 0) * 100)}</span>
                  <button className="toggle-chip" disabled={!includeReference} onClick={() => removeWeightRow('reference', index)} type="button">Remove</button>
                </div>
              ))}
            </div>
          </section>
          <section className={sectionCardClass('candidate')}>
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Candidate Portfolio Builder</p></div><div className="toggle-group"><p className={`helper ${deltaToneClass(totalTone(candidateWeightTotal))}`}>Total {formatNumber(candidateWeightTotal, 2)}</p><button className="toggle-chip" onClick={() => setCandidateWeights(referenceWeights)} type="button">Copy Baseline to Candidate</button><button className="toggle-chip" onClick={() => setCandidateWeights(normalizeRows(candidateWeights))} type="button">Normalize</button><button className="toggle-chip" onClick={() => setCandidateWeights([])} type="button">Clear</button><button className="toggle-chip" onClick={() => addWeightRow('candidate')} type="button">Add Row</button></div></div>
            <p className="helper backtest-section-helper">Build the after-state and keep the total close to 1.00 before running the replay.</p>
            <div className="factor-snapshot-table-wrap">
              {candidateWeights.map((row, index) => (
                <div className="allocation-weight-row" key={`candidate-${index}`}>
                  <input aria-label={`candidate-symbol-${index}`} className="path-input" value={row.symbol} onChange={(event) => updateWeightRow('candidate', index, 'symbol', event.target.value)} placeholder="Symbol" />
                  <input aria-label={`candidate-weight-${index}`} className="path-input" value={row.target_weight} onChange={(event) => updateWeightRow('candidate', index, 'target_weight', event.target.value)} placeholder="0.50" />
                  <span className={`allocation-weight-badge ${deltaToneClass(totalTone(Number(row.target_weight) || 0))}`}>{formatPct((Number(row.target_weight) || 0) * 100)}</span>
                  <button className="toggle-chip" onClick={() => removeWeightRow('candidate', index)} type="button">Remove</button>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div className="actions backtest-actions">
          <button className={`primary-button${loading ? ' button-loading' : ''}`} disabled={loading} type="submit">{loading ? 'Running Portfolio Improvement Replay...' : 'Run Portfolio Improvement Replay'}</button>
          <p className="helper">Baseline and candidate weights should each sum to 1.00 when comparison is enabled.</p>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </form>
    </section>
  )
}
