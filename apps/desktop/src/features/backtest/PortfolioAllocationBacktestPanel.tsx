import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { HypotheticalReplacementReplayResponse, PortfolioAllocationBacktestResponse, PortfolioBaselineView, PortfolioDiagnosticsComparisonRow, PortfolioDiagnosticsTopCallout } from '../portfolio/types'
import type { PortfolioSnapshot, ReplacementIntentDraftArtifact, VersionedProposalArtifact } from '../portfolio/workspaceTypes'

type AllocationWeightRow = {
  symbol: string
  target_weight: string
}

type Props = {
  result: PortfolioAllocationBacktestResponse | null
  onResult: (result: PortfolioAllocationBacktestResponse) => void
  analysis: PortfolioBaselineView | null
  draftSnapshot: PortfolioSnapshot | null
  replacementIntentDraft: ReplacementIntentDraftArtifact | null
  hypotheticalReplayResult: HypotheticalReplacementReplayResponse | null
  savedProposals: VersionedProposalArtifact[]
  onSaveProposal: () => void | Promise<void>
  onHypotheticalReplayResult: (result: HypotheticalReplacementReplayResponse) => void
}

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

type HypotheticalReplayPreflight = {
  overallStatus: PreflightStatus
  incumbentWeight: number | null
  checks: Array<{
    label: string
    status: PreflightStatus
    detail: string
  }>
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
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'n/a' : value.toFixed(digits)
}

function formatMoney(value: number | null | undefined) {
  return value == null ? 'n/a' : `$${value.toFixed(2)}`
}

function formatDateLabel(value: string | number | null | undefined) {
  if (typeof value !== 'string') return ''
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) return value
  return `${month}/${day}/${year.slice(2)}`
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
  if (value == null) return 'n/a'
  if (kind === 'money') return `${value > 0 ? '+' : ''}${formatMoney(value)}`
  if (kind === 'pct') return `${value > 0 ? '+' : ''}${formatPct(value)}`
  return `${value > 0 ? '+' : ''}${formatNumber(value, 2)}`
}

function metricDeltaTone(row: ComparisonMetricRow): DeltaTone {
  if (row.delta == null || row.delta === 0) return 'neutral'
  const betterWhenHigher = new Set(['total_return', 'annualized_return', 'max_drawdown', 'sharpe', 'sortino', 'excess_return', 'information_ratio'])
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
  if (!startDate || !endDate) return 'n/a'
  return `${startDate} -> ${endDate}`
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

function buildSummaryRows(replay: PortfolioAllocationBacktestResponse | null): ComparisonMetricRow[] {
  if (!replay?.reference_result) return []
  return [
    { key: 'total_return', label: 'Total Return', baseline: replay.reference_result.metrics.total_return_pct, candidate: replay.candidate_result.metrics.total_return_pct, delta: replay.comparison?.total_return_diff_pct ?? null, format: 'pct' },
    { key: 'annualized_return', label: 'Annualized Return', baseline: replay.reference_result.metrics.annualized_return_pct, candidate: replay.candidate_result.metrics.annualized_return_pct, delta: replay.comparison?.annualized_return_diff_pct ?? null, format: 'pct' },
    { key: 'annualized_volatility', label: 'Annualized Volatility', baseline: replay.reference_result.metrics.annualized_volatility_pct, candidate: replay.candidate_result.metrics.annualized_volatility_pct, delta: replay.comparison?.annualized_volatility_diff_pct ?? null, format: 'pct' },
    { key: 'downside_volatility', label: 'Downside Volatility', baseline: replay.reference_result.metrics.downside_volatility_pct, candidate: replay.candidate_result.metrics.downside_volatility_pct, delta: replay.comparison?.downside_volatility_diff_pct ?? null, format: 'pct' },
    { key: 'max_drawdown', label: 'Max Drawdown', baseline: replay.reference_result.metrics.max_drawdown_pct, candidate: replay.candidate_result.metrics.max_drawdown_pct, delta: replay.comparison?.max_drawdown_diff_pct ?? null, format: 'pct' },
    { key: 'sharpe', label: 'Sharpe Ratio', baseline: replay.reference_result.metrics.sharpe_ratio, candidate: replay.candidate_result.metrics.sharpe_ratio, delta: replay.comparison?.sharpe_diff ?? null, format: 'number' },
    { key: 'sortino', label: 'Sortino Ratio', baseline: replay.reference_result.metrics.sortino_ratio, candidate: replay.candidate_result.metrics.sortino_ratio, delta: replay.comparison?.sortino_diff ?? null, format: 'number' },
    { key: 'benchmark_return', label: 'Benchmark Return', baseline: replay.reference_result.metrics.benchmark_return_pct, candidate: replay.candidate_result.metrics.benchmark_return_pct, delta: 0, format: 'pct' },
    { key: 'excess_return', label: 'Excess Return', baseline: replay.reference_result.metrics.excess_return_pct, candidate: replay.candidate_result.metrics.excess_return_pct, delta: replay.comparison?.excess_return_diff_pct ?? null, format: 'pct' },
    { key: 'tracking_error', label: 'Tracking Error', baseline: replay.reference_result.metrics.tracking_error_pct, candidate: replay.candidate_result.metrics.tracking_error_pct, delta: replay.comparison?.tracking_error_diff_pct ?? null, format: 'pct' },
    { key: 'information_ratio', label: 'Information Ratio', baseline: replay.reference_result.metrics.information_ratio, candidate: replay.candidate_result.metrics.information_ratio, delta: replay.comparison?.information_ratio_diff ?? null, format: 'number' },
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
      key: 'volatility-drawdown',
      title: 'Volatility & Drawdown',
      helper: 'Review whether the hypothetical candidate changes the portfolio risk path under the shared replay window.',
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
  return selectionRule.replaceAll('_', ' ')
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

function buildHypotheticalReplayPreflight(draftSnapshot: PortfolioSnapshot | null, replacementIntentDraft: ReplacementIntentDraftArtifact | null): HypotheticalReplayPreflight {
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

  if (!draftSnapshot) {
    return {
      overallStatus: 'blocked',
      incumbentWeight: null,
      checks: [
        {
          label: 'Draft Snapshot',
          status: 'blocked',
          detail: 'A current draft snapshot is required so the backend can derive the replay basis.',
        },
      ],
    }
  }

  const positivePositions = draftSnapshot.positions.filter((position) => position.marketValue > 0)
  const totalPositiveMarketValue = positivePositions.reduce((sum, position) => sum + position.marketValue, 0)
  const incumbentPosition = positivePositions.find((position) => position.symbol === replacementIntentDraft.baseSymbol)
  const candidateAlreadyHeld = positivePositions.some((position) => position.symbol === replacementIntentDraft.candidateSymbol)
  const sameSymbol = replacementIntentDraft.baseSymbol === replacementIntentDraft.candidateSymbol
  const incumbentWeight = incumbentPosition && totalPositiveMarketValue > 0 ? incumbentPosition.marketValue / totalPositiveMarketValue : null

  const checks: HypotheticalReplayPreflight['checks'] = [
    {
      label: 'Replay Basis',
      status: positivePositions.length > 0 && totalPositiveMarketValue > 0 ? 'ready' : 'blocked',
      detail: positivePositions.length > 0 && totalPositiveMarketValue > 0
        ? `The draft snapshot contains ${positivePositions.length} positive-weight holdings that can seed the hypothetical replay basis.`
        : 'The draft snapshot does not contain positive-weight holdings, so the replay basis cannot be derived.',
    },
    {
      label: 'Incumbent Holding',
      status: incumbentPosition ? 'ready' : 'blocked',
      detail: incumbentPosition
        ? `${replacementIntentDraft.baseSymbol} is present in the draft basis at ${formatPct((incumbentWeight ?? 0) * 100)}.`
        : `${replacementIntentDraft.baseSymbol} is not available as a positive-weight holding in the current draft basis.`,
    },
    {
      label: 'Candidate Conflict',
      status: sameSymbol || candidateAlreadyHeld ? 'blocked' : 'ready',
      detail: sameSymbol
        ? 'The candidate symbol must differ from the incumbent symbol.'
        : candidateAlreadyHeld
          ? `${replacementIntentDraft.candidateSymbol} is already held in the current draft basis, so the MVP replay must reject it.`
          : `${replacementIntentDraft.candidateSymbol} is not already held in the current draft basis.`,
    },
    {
      label: 'Backend Validation',
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

function BacktestCurve({ result }: { result: PortfolioAllocationBacktestResponse }) {
  const chartData = useMemo(() => {
    const referenceByDate = new Map((result.reference_result?.equity_curve ?? []).map((point) => [point.date, point]))
    return result.candidate_result.equity_curve.map((point) => ({
      date: point.date,
      candidateEquity: point.equity,
      referenceEquity: referenceByDate.get(point.date)?.equity ?? null,
      candidateDrawdown: point.drawdown_pct,
      referenceDrawdown: referenceByDate.get(point.date)?.drawdown_pct ?? null,
    }))
  }, [result])

  return (
    <div className="split-grid dashboard-bottom-grid">
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
      <section>
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Replay Drawdown</p></div></div>
        <div className="line-chart-panel compact-chart-panel">
          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={220}>
            <LineChart data={chartData} margin={{ top: 18, right: 16, left: 8, bottom: 8 }}>
              <CartesianGrid stroke="rgba(70, 82, 98, 0.16)" strokeDasharray="3 3" />
              <ReferenceLine y={0} stroke="rgba(156, 169, 184, 0.34)" strokeDasharray="5 5" />
              <XAxis dataKey="date" tick={{ fill: '#748295', fontSize: 10 }} minTickGap={28} interval="preserveStartEnd" tickFormatter={formatDateLabel} />
              <YAxis tick={{ fill: '#748295', fontSize: 10 }} width={48} />
              <Tooltip formatter={(value) => formatPct(typeof value === 'number' ? value : null)} labelFormatter={formatTooltipLabel} />
              {result.reference_result ? <Line type="monotone" dataKey="referenceDrawdown" name="Baseline" stroke="#6c88a6" strokeWidth={1.8} dot={false} isAnimationActive={false} /> : null}
              <Line type="monotone" dataKey="candidateDrawdown" name="Candidate" stroke="#d85a51" strokeWidth={2.0} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
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
          <p className="summary-value">{activeReplay.candidate_diagnostics?.provenance.snapshot_basis ?? 'n/a'}</p>
          <p className="helper">Baseline diagnostics reflect the current portfolio basis. Candidate diagnostics reflect a hypothetical replacement-intent variant and have not been applied to holdings.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Historical Basis</p>
          <p className="summary-value">{activeReplay.candidate_diagnostics?.provenance.historical_basis ?? 'n/a'}</p>
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
      <div className="section-header-inline sector-list-header"><div><p className="panel-label">Before / After Diagnostics</p></div><p className="helper">{activeReplay.candidate_diagnostics?.provenance.note ?? 'Diagnostics compare synthetic replay snapshots against historical market-data inputs.'}</p></div>
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

function SavedProposalReadoutSection({ proposal }: { proposal: VersionedProposalArtifact }) {
  const proposalReplay = proposal.reviewSnapshot.replay
  const proposalSummaryRows = buildSummaryRows(proposalReplay)
  const proposalDeltaCallouts = buildReplayDeltaCallouts(proposalSummaryRows)
  const proposalDiagnosticsSections = diagnosticsSectionConfigs(proposalReplay)

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Saved Proposal Review</p></div>
        <p className="helper">This is a saved proposal artifact, not live portfolio truth. It preserves prior hypothetical replay outputs and lineage exactly as reviewed when saved, even if the current draft or portfolio state has changed.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card">
          <p className="stat-label">Proposal Artifact</p>
          <p className="summary-value">v{proposal.versionNumber}</p>
          <p className="helper">Immutable local record of a previously reviewed hypothetical proposal.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Lineage</p>
          <p className="summary-value">{proposal.sourceIntent.baseSymbol} -&gt; {proposal.sourceIntent.candidateSymbol}</p>
          <p className="helper">Shows how this proposal was derived, including ranking seed, replacement intent, and hypothetical replay context.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Proposal Basis</p>
          <p className="summary-value">{proposal.replayBasis.derivationBasis}</p>
          <p className="helper">Review the baseline and candidate basis captured when this proposal was saved. This surface does not depend on the current draft state.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Review State</p>
          <p className="summary-value">{proposal.reviewStatus}</p>
          <p className="helper">This proposal is saved for inspection only. It does not update holdings, confirm a decision, or reflect applied portfolio truth.</p>
        </div>
      </div>
      <div className="summary-card">
        <p className="panel-label">Proposal Lineage</p>
        <p className="helper">Workspace: {proposal.workspaceId} · Draft: {proposal.sourceDraftId} · Base node: {proposal.sourceBaseNodeId} · Saved at: {proposal.createdAt}</p>
        <p className="helper">Source: {proposal.reviewSnapshot.proposal.source} · Construction rule: {proposal.replayBasis.candidateConstructionRule}</p>
      </div>
      <div className="dashboard-summary compact-summary-grid backtest-workspace-summary">
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Benchmark</p><p className="summary-value">{proposal.replayBasis.benchmarkSymbol}</p></div>
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Replay Window</p><p className="summary-value">{formatReplayWindow(proposal.replayBasis.startDate, proposal.replayBasis.endDate)}</p></div>
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Replay Setup</p><p className="summary-value">{proposal.replayBasis.rebalanceFrequency}</p><p className="helper">{proposal.replayBasis.commissionBps} commission bps / {proposal.replayBasis.slippageBps} slippage bps</p></div>
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card"><p className="stat-label">Replay Status</p><p className="summary-value">{proposalReplay.candidate_result.status}</p><p className="helper">Snapshot of the saved hypothetical current-vs-candidate replay results captured with the proposal.</p></div>
      </div>
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
                <p className="summary-value">{topCallout?.label ?? 'n/a'}</p>
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

export function PortfolioAllocationBacktestPanel({ result, onResult, analysis, draftSnapshot, replacementIntentDraft, hypotheticalReplayResult, savedProposals, onSaveProposal, onHypotheticalReplayResult }: Props) {
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
  const [hypotheticalLoading, setHypotheticalLoading] = useState(false)
  const [hypotheticalError, setHypotheticalError] = useState<string | null>(null)
  const [showHypotheticalReplayConfirmation, setShowHypotheticalReplayConfirmation] = useState(false)
  const candidateWeightTotal = totalWeight(candidateWeights)
  const referenceWeightTotal = totalWeight(referenceWeights)
  const baselineRows = useMemo(() => deriveBaselineRows(analysis), [analysis])
  const hypotheticalPreflight = useMemo(() => buildHypotheticalReplayPreflight(draftSnapshot, replacementIntentDraft), [draftSnapshot, replacementIntentDraft])
  const latestSavedProposal = savedProposals[0] ?? null
  const importedPortfolioValue = analysis?.overview.total_market_value ?? null
  const importedPositionsCount = analysis?.snapshot.positions.length ?? 0

  useEffect(() => {
    if (!baselineRows.length) return
    setReferenceWeights((current) => (current.length === 1 && current[0]?.symbol === 'SPY' && current[0]?.target_weight === '1.00') ? baselineRows : current)
  }, [baselineRows])

  async function runHypotheticalReplayPreview() {
    if (!draftSnapshot || !replacementIntentDraft) return

    setHypotheticalLoading(true)
    setHypotheticalError(null)

    try {
      const response = await fetch(`${apiBase}/backtests/portfolio-allocation/replacement-intent-preview`, {
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
      onHypotheticalReplayResult((await response.json()) as HypotheticalReplacementReplayResponse)
      setShowHypotheticalReplayConfirmation(false)
    } catch (caughtError) {
      setHypotheticalError(caughtError instanceof Error ? caughtError.message : 'Hypothetical replay preview failed')
    } finally {
      setHypotheticalLoading(false)
    }
  }

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

  const activeReplay = hypotheticalReplayResult?.replay ?? result
  const summaryRows = buildSummaryRows(activeReplay)
  const replayDeltaCallouts = useMemo(() => buildReplayDeltaCallouts(summaryRows), [summaryRows])

  return (
    <section className="workspace-section">
      <p className="panel-label">Portfolio Improvement Workspace</p>
      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Hypothetical Replay</p></div></div>
        <p className="helper">Review this as a draft-only comparison built from one explicit replacement intent. Read the basis first, then compare baseline and candidate results.</p>
        {replacementIntentDraft ? (
          <>
            <div className="summary-card">
              <p className="panel-label">Replay Preflight</p>
              <p className="helper">Check the draft basis first so obvious MVP rejection cases are visible before you run the hypothetical replay.</p>
              <div className="dashboard-summary compact-summary-grid">
                <div className="summary-card">
                  <p className="stat-label">Preflight Status</p>
                  <p className={`summary-value ${preflightToneClass(hypotheticalPreflight.overallStatus)}`}>{hypotheticalPreflight.overallStatus === 'ready' ? 'Ready for backend validation' : 'Blocked before preview'}</p>
                </div>
                <div className="summary-card">
                  <p className="stat-label">Intent Pair</p>
                  <p className="summary-value">{replacementIntentDraft.baseSymbol} -&gt; {replacementIntentDraft.candidateSymbol}</p>
                </div>
                <div className="summary-card">
                  <p className="stat-label">Incumbent Starting Weight</p>
                  <p className="summary-value">{hypotheticalPreflight.incumbentWeight == null ? 'n/a' : formatPct(hypotheticalPreflight.incumbentWeight * 100)}</p>
                </div>
              </div>
              <div className="list-table">
                {hypotheticalPreflight.checks.map((check) => (
                  <div className="list-row list-row-wide" key={check.label}>
                    <span>{check.label}</span>
                    <span className={preflightToneClass(check.status)}>{check.status === 'ready' ? 'Ready' : check.status === 'blocked' ? 'Blocked' : 'Pending backend'}</span>
                    <span>{check.detail}</span>
                  </div>
                ))}
              </div>
            </div>
            {!hypotheticalReplayResult ? <p className="helper">No hypothetical replay has been run for this replacement intent yet.</p> : null}
            {!showHypotheticalReplayConfirmation ? (
              <div className="actions backtest-actions">
                <button className="secondary-button" disabled={hypotheticalPreflight.overallStatus === 'blocked'} type="button" onClick={() => setShowHypotheticalReplayConfirmation(true)}>Preview Hypothetical Replay</button>
                <p className="helper">Compare the current portfolio against a draft-only candidate built from this replacement intent.</p>
              </div>
            ) : (
              <div className="summary-card">
                <p className="panel-label">Preview hypothetical current-vs-candidate replay</p>
                <p className="helper">This creates a draft-only candidate portfolio by carrying the replacement intent into a hypothetical replay. It does not apply the replacement, endorse it, or run portfolio construction logic.</p>
                <div className="dashboard-summary compact-summary-grid">
                  <div className="summary-card"><p className="stat-label">Baseline</p><p className="summary-value">Current draft or imported portfolio state</p></div>
                  <div className="summary-card"><p className="stat-label">Hypothetical Candidate</p><p className="summary-value">Single incumbent-to-candidate replacement from the active replacement intent</p></div>
                  <div className="summary-card"><p className="stat-label">Intent Source</p><p className="summary-value">Replacement Intent from ETF Ranking seed</p></div>
                  <div className="summary-card"><p className="stat-label">Replay Basis</p><p className="summary-value">Hypothetical current-vs-candidate comparison</p></div>
                </div>
                <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
                  <button className="primary-button" type="button" disabled={hypotheticalLoading} onClick={() => void runHypotheticalReplayPreview()}>{hypotheticalLoading ? 'Running Preview...' : 'Run Preview'}</button>
                  <button className="secondary-button" type="button" onClick={() => setShowHypotheticalReplayConfirmation(false)}>Cancel</button>
                </div>
              </div>
            )}
            {hypotheticalError ? <p className="error">{hypotheticalError}</p> : null}
            {hypotheticalReplayResult ? (
              <>
                <div className="summary-card">
                  <p className="helper">Baseline: current portfolio basis</p>
                  <p className="helper">Candidate: hypothetical replacement-intent variant</p>
                  <p className="helper">Status: not applied to holdings</p>
                </div>
                <section>
                  <div className="section-header-inline sector-list-header"><div><p className="panel-label">Replay Decision Readout</p></div></div>
                  <p className="helper">Start here before reading the charts and tables. Confirm what this replay compares, what changed in the candidate, and what did not.</p>
                  <div className="dashboard-summary compact-summary-grid">
                    <div className="summary-card"><p className="stat-label">Replay Type</p><p className="summary-value">Hypothetical current-vs-candidate</p></div>
                    <div className="summary-card"><p className="stat-label">Intent Pair</p><p className="summary-value">{hypotheticalReplayResult.proposal.incumbent_symbol} -&gt; {hypotheticalReplayResult.proposal.candidate_symbol}</p></div>
                    <div className="summary-card"><p className="stat-label">Baseline Basis</p><p className="summary-value">Current draft or imported portfolio state</p></div>
                    <div className="summary-card"><p className="stat-label">Candidate Basis</p><p className="summary-value">Single replacement-intent variant</p></div>
                  </div>
                  <div className="dashboard-summary compact-summary-grid">
                    <div className="summary-card">
                      <p className="stat-label">What Changed</p>
                      <p className="helper">The candidate replay changes one thing only: it replaces {hypotheticalReplayResult.proposal.incumbent_symbol} with {hypotheticalReplayResult.proposal.candidate_symbol} inside a hypothetical draft-only portfolio variant.</p>
                    </div>
                    <div className="summary-card">
                      <p className="stat-label">What Did Not Change</p>
                      <p className="helper">No holdings have been updated. No construction, optimization, turnover repair, or execution logic has been applied.</p>
                    </div>
                  </div>
                </section>
                <div className="summary-card">
                  <p className="panel-label">Replay Metadata</p>
                  <p className="helper">Source: {hypotheticalReplayResult.proposal.source} · Draft: {hypotheticalReplayResult.proposal.draft_id} · Base node: {hypotheticalReplayResult.proposal.base_node_id}</p>
                  <p className="helper">Derivation: {hypotheticalReplayResult.derivation.baseline_basis} · {hypotheticalReplayResult.derivation.candidate_construction_rule}</p>
                  <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
                    <button className="primary-button" type="button" onClick={() => void onSaveProposal()}>Save Proposal v{savedProposals.length + 1}</button>
                    <p className="helper">Create an immutable reviewed proposal artifact from this hypothetical replay. It remains separate from portfolio truth and does not apply any holdings change.</p>
                  </div>
                </div>
                {latestSavedProposal ? (
                  <div className="summary-card">
                    <p className="panel-label">Latest Saved Proposal</p>
                    <div className="dashboard-summary compact-summary-grid">
                      <div className="summary-card"><p className="stat-label">Version</p><p className="summary-value">v{latestSavedProposal.versionNumber}</p></div>
                      <div className="summary-card"><p className="stat-label">Intent Pair</p><p className="summary-value">{latestSavedProposal.sourceIntent.baseSymbol} -&gt; {latestSavedProposal.sourceIntent.candidateSymbol}</p></div>
                      <div className="summary-card"><p className="stat-label">Replay Window</p><p className="summary-value">{formatReplayWindow(latestSavedProposal.replayBasis.startDate, latestSavedProposal.replayBasis.endDate)}</p></div>
                      <div className="summary-card"><p className="stat-label">Saved At</p><p className="summary-value">{latestSavedProposal.createdAt.slice(0, 10)}</p></div>
                    </div>
                    <p className="helper">Saved from draft {latestSavedProposal.sourceDraftId} / base node {latestSavedProposal.sourceBaseNodeId}. This proposal is a recorded review artifact and not an applied portfolio change.</p>
                  </div>
                ) : null}
                <div className="dashboard-summary compact-summary-grid backtest-workspace-summary">
                  <div className="summary-card metric-card metric-card-neutral backtest-summary-card">
                    <p className="stat-label">Replay Status</p>
                    <p className="summary-value">{activeReplay?.candidate_result.status ?? 'n/a'}</p>
                    <p className="helper">Candidate replay status under the shared implementation window</p>
                  </div>
                  <div className="summary-card metric-card metric-card-neutral backtest-summary-card">
                    <p className="stat-label">Benchmark</p>
                    <p className="summary-value">{activeReplay?.candidate_result.benchmark_symbol ?? 'n/a'}</p>
                    <p className="helper">Shared benchmark for baseline and candidate replay</p>
                  </div>
                  <div className="summary-card metric-card metric-card-neutral backtest-summary-card">
                    <p className="stat-label">Replay Window</p>
                    <p className="summary-value">{formatReplayWindow(activeReplay?.candidate_result.start_date, activeReplay?.candidate_result.end_date)}</p>
                    <p className="helper">Baseline and candidate are shown on the same replay window. Treat the candidate as a hypothetical test of the intent, not as an approved portfolio change.</p>
                  </div>
                  <div className="summary-card metric-card metric-card-neutral backtest-summary-card">
                    <p className="stat-label">Replay Setup</p>
                    <p className="summary-value">{activeReplay?.candidate_result.rebalance_frequency ?? 'n/a'}</p>
                    <p className="helper">{activeReplay ? `${activeReplay.candidate_result.commission_bps} commission bps / ${activeReplay.candidate_result.slippage_bps} slippage bps` : 'n/a'}</p>
                  </div>
                </div>
                <div className="split-grid dashboard-bottom-grid">
                  <section>
                    <div className="section-header-inline sector-list-header"><div><p className="panel-label">Baseline Weights</p></div></div>
                    <div className="list-table">{hypotheticalReplayResult.baseline_weights.map((row) => <div className="list-row" key={`baseline-weight-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div>
                  </section>
                  <section>
                    <div className="section-header-inline sector-list-header"><div><p className="panel-label">Candidate Weights</p></div></div>
                    <div className="list-table">{hypotheticalReplayResult.candidate_weights.map((row) => <div className="list-row" key={`candidate-weight-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div>
                  </section>
                </div>
                {hypotheticalReplayResult.warnings.length ? (
                  <div className="summary-card">
                    <p className="panel-label">Warnings</p>
                    {hypotheticalReplayResult.warnings.map((warning) => <p className="helper" key={warning}>{warning}</p>)}
                  </div>
                ) : null}
              </>
            ) : null}
          </>
        ) : (
          <p className="helper">An explicit replacement intent is required before a hypothetical replay can run.</p>
        )}
      </section>
      {latestSavedProposal ? <SavedProposalReadoutSection proposal={latestSavedProposal} /> : null}
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
          <button className="primary-button" disabled={loading} type="submit">{loading ? 'Running Portfolio Improvement Replay...' : 'Run Portfolio Improvement Replay'}</button>
          <p className="helper">Baseline and candidate weights should each sum to 1.00 when comparison is enabled.</p>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </form>

      {activeReplay ? (
        <>
          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Replay Summary</p></div><p className="helper">Baseline and candidate are shown on the same replay window. Treat the candidate as a hypothetical test of the intent, not as an approved portfolio change.</p></div>
            {summaryRows.length && replayDeltaCallouts.length ? (
              <div className="dashboard-summary compact-summary-grid">
                {replayDeltaCallouts.map((callout) => (
                  <div className="summary-card" key={callout.key}>
                    <p className="stat-label">{callout.label}</p>
                    <p className={`summary-value ${deltaToneClass(callout.tone)}`}>{callout.value}</p>
                    <p className="helper">{callout.rationale}</p>
                  </div>
                ))}
              </div>
            ) : null}
            {summaryRows.length ? <ComparisonTable rows={summaryRows} /> : <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">Run with baseline comparison enabled to view before/after replay metrics.</p></div>}
          </section>

          {hypotheticalReplayResult ? <DiagnosticsDeltaReviewSection activeReplay={activeReplay} /> : null}

          <BacktestCurve result={activeReplay} />

          {!hypotheticalReplayResult && activeReplay.diagnostics_comparison ? <StandardDiagnosticsComparisonSection activeReplay={activeReplay} /> : null}

          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Implementation Details</p></div><p className="helper">{activeReplay.candidate_result.status} / {activeReplay.candidate_result.assumptions.calendar_policy}</p></div>
            <div className="dashboard-summary compact-summary-grid">
              <div className="summary-card"><p className="stat-label">Price Basis</p><p className="summary-value">{activeReplay.candidate_result.assumptions.price_basis}</p></div>
              <div className="summary-card"><p className="stat-label">Execution Field</p><p className="summary-value">{activeReplay.candidate_result.assumptions.execution_price_field}</p></div>
              <div className="summary-card"><p className="stat-label">Execution Lag</p><p className="summary-value">{formatNumber(activeReplay.candidate_result.assumptions.execution_lag_days, 0)}</p></div>
              <div className="summary-card"><p className="stat-label">Tax Treatment</p><p className="summary-value">{activeReplay.candidate_result.assumptions.tax_treatment}</p></div>
              <div className="summary-card"><p className="stat-label">Fractional Shares</p><p className="summary-value">{activeReplay.candidate_result.assumptions.fractional_shares ? 'true' : 'false'}</p></div>
              <div className="summary-card"><p className="stat-label">Base Currency</p><p className="summary-value">{activeReplay.candidate_result.assumptions.investor_base_currency ?? 'n/a'}</p></div>
            </div>
          </section>

          <div className="split-grid dashboard-bottom-grid">
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Starting Weights</p></div></div>
              <div className="list-table">{activeReplay.candidate_result.starting_weights.map((row) => <div className="list-row" key={`starting-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div>
            </section>
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Ending Weights</p></div></div>
              <div className="list-table">{activeReplay.candidate_result.ending_weights.map((row) => <div className="list-row" key={`ending-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div>
            </section>
          </div>

          <div className="split-grid dashboard-bottom-grid">
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Instrument Metadata</p></div></div>
              <div className="list-table">{activeReplay.candidate_result.instrument_metadata.map((item) => <div className="list-row list-row-wide" key={`meta-${item.symbol}`}><span>{item.symbol}</span><span>{item.trading_currency ?? 'n/a'}</span><span>{item.instrument_base_currency ?? 'n/a'}</span><span>{item.currency_hedged == null ? 'n/a' : String(item.currency_hedged)}</span><span>{item.distribution_policy}</span></div>)}</div>
            </section>
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Rebalance Events</p></div></div>
              <div className="list-table">{activeReplay.candidate_result.rebalance_events.length ? activeReplay.candidate_result.rebalance_events.map((row) => <div className="list-row list-row-wide" key={`rebalance-${row.execution_date}`}><span>{row.decision_date}</span><span>{row.execution_date}</span><span>{formatPct(row.turnover_pct)}</span><span>{formatMoney(row.total_cost)}</span></div>) : <div className="list-row"><span>No rebalances</span><span>n/a</span></div>}</div>
            </section>
          </div>

          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Trade Log</p></div><p className="helper">Showing first 12 candidate trades.</p></div>
            <div className="list-table">{activeReplay.candidate_result.trades.slice(0, 12).map((trade, index) => <div className="list-row list-row-wide" key={`${trade.symbol}-${trade.date}-${index}`}><span>{trade.date}</span><span>{trade.action}</span><span>{trade.symbol}</span><span>{formatNumber(trade.quantity, 4)}</span><span>{formatMoney(trade.traded_notional)}</span><span>{formatMoney(trade.total_cost)}</span></div>)}</div>
          </section>

          {hypotheticalReplayResult ? <p className="helper">Use this surface to review whether the explicit replacement intent produces a meaningfully different hypothetical path under a shared window. It does not recommend the change or prove it should be applied.</p> : null}
        </>
      ) : null}
    </section>
  )
}
