import { useMemo, useState } from 'react'

import type {
  AllocationBacktestComparison,
  HypotheticalReplayResponse,
  PortfolioAllocationBacktestResponse,
  PortfolioDiagnosticsComparisonRow,
  PortfolioDiagnosticsSnapshot,
  PortfolioDiagnosticsTopCallout,
} from '../portfolio/types'
import { formatReplayHistoricalBasisLabel } from '../portfolio/historyTruth'

type MonitorTone = 'hot' | 'warm' | 'cool' | 'neutral'

type MonitorItem = {
  key: string
  title: string
  currentStatus: string
  recentChange: string
  severity: 'High' | 'Medium' | 'Low'
  confidence: 'High' | 'Medium' | 'Low'
  provenance: string
  tone: MonitorTone
  detail: string[]
}

type MonitorCallout = {
  key: string
  label: string
  value: string
  helper: string
  tone: MonitorTone
}

function formatPct(value: number | null | undefined) {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatSignedPct(value: number | null | undefined) {
  if (value == null) return 'n/a'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'n/a' : value.toFixed(digits)
}

function formatSignedNumber(value: number | null | undefined, digits = 2) {
  if (value == null) return 'n/a'
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}`
}

function cardClass(tone: MonitorTone) {
  return `summary-card metric-card metric-card-${tone}`
}

function rowToneClass(tone: MonitorTone) {
  if (tone === 'hot') return 'negative-text'
  if (tone === 'warm') return 'neutral-text'
  if (tone === 'cool') return 'positive-text'
  return 'neutral-text'
}

function selectionRuleLabel(value: string) {
  if (value === 'largest_absolute_delta') return 'largest absolute delta'
  if (value === 'fixed_priority') return 'fixed priority rule'
  return value.replace(/_/g, ' ')
}

function comparisonValue(row: PortfolioDiagnosticsComparisonRow | PortfolioDiagnosticsTopCallout) {
  if (row.key.includes('hhi') || row.key.includes('beta') || row.key.includes('correlation')) {
    return formatSignedNumber(row.delta_value)
  }
  return formatSignedPct(row.delta_value)
}

function magnitude(value: number | null | undefined) {
  return Math.abs(value ?? 0)
}

function toneFromMagnitude(value: number | null | undefined, highThreshold: number, mediumThreshold: number): MonitorTone {
  const absolute = magnitude(value)
  if (absolute >= highThreshold) return 'hot'
  if (absolute >= mediumThreshold) return 'warm'
  if (absolute > 0) return 'cool'
  return 'neutral'
}

function confidenceFromReplay(activeReplay: PortfolioAllocationBacktestResponse, diagnosticsReady: boolean): 'High' | 'Medium' | 'Low' {
  if (activeReplay.candidate_result.status === 'degraded' || activeReplay.reference_result?.status === 'degraded') return 'Low'
  if (!diagnosticsReady) return 'Medium'
  return activeReplay.reference_result ? 'High' : 'Medium'
}

function monitorFromCallout(
  key: string,
  title: string,
  row: PortfolioDiagnosticsTopCallout | null,
  provenance: string,
  diagnosticsConfidence: 'High' | 'Medium' | 'Low',
  unavailableGuidance: string,
): MonitorItem {
  if (!row) {
    return {
      key,
      title,
      currentStatus: 'Unavailable',
      recentChange: 'n/a',
      severity: 'Low',
      confidence: 'Low',
      provenance,
      tone: 'neutral',
      detail: [unavailableGuidance],
    }
  }

  const tone = toneFromMagnitude(row.delta_value, 0.2, 0.08)
  return {
    key,
    title,
    currentStatus: row.label,
    recentChange: comparisonValue(row),
    severity: tone === 'hot' ? 'High' : tone === 'warm' ? 'Medium' : 'Low',
    confidence: diagnosticsConfidence,
    provenance,
    tone,
    detail: [
      `Baseline ${formatNumber(row.baseline_value)} vs candidate ${formatNumber(row.candidate_value)}.`,
      `Selection rule: ${selectionRuleLabel(row.selection_rule)}.`,
      row.rationale,
    ],
  }
}

function dataQualityMonitor(
  activeReplay: PortfolioAllocationBacktestResponse,
  candidateDiagnostics: PortfolioDiagnosticsSnapshot | null,
  referenceDiagnostics: PortfolioDiagnosticsSnapshot | null,
): MonitorItem {
  const degradedVariants = [activeReplay.reference_result?.status, activeReplay.candidate_result.status].filter((status) => status === 'degraded').length
  const missingDiagnostics = [referenceDiagnostics, candidateDiagnostics].filter((snapshot) => snapshot == null).length
  const comparisonReady = Boolean(activeReplay.diagnostics_comparison)
  const tone = degradedVariants > 0 ? 'hot' : missingDiagnostics > 0 || !comparisonReady ? 'warm' : 'cool'

  return {
    key: 'data-quality',
    title: 'Data Quality',
    currentStatus: degradedVariants > 0 ? 'Degraded' : missingDiagnostics > 0 || !comparisonReady ? 'Partial' : 'Stable',
    recentChange: degradedVariants > 0 ? `${degradedVariants} degraded replay variant${degradedVariants > 1 ? 's' : ''}` : missingDiagnostics > 0 ? `${missingDiagnostics} diagnostics snapshot missing` : 'No degradation flag',
    severity: tone === 'hot' ? 'High' : tone === 'warm' ? 'Medium' : 'Low',
    confidence: tone === 'hot' ? 'Low' : tone === 'warm' ? 'Medium' : 'High',
    provenance: candidateDiagnostics?.provenance.note ?? referenceDiagnostics?.provenance.note ?? 'Replay status and diagnostics availability are backend-authored.',
    tone,
    detail: [
      `Candidate replay status: ${activeReplay.candidate_result.status}.`,
      `Reference replay status: ${activeReplay.reference_result?.status ?? 'not provided'}.`,
      comparisonReady ? 'Diagnostics comparison is available for monitoring review.' : 'Diagnostics comparison is unavailable for this replay state.',
    ],
  }
}

function benchmarkRelativeMonitor(
  comparison: AllocationBacktestComparison | null,
  activeReplay: PortfolioAllocationBacktestResponse,
  provenance: string,
  diagnosticsConfidence: 'High' | 'Medium' | 'Low',
): MonitorItem {
  const tone = toneFromMagnitude(comparison?.tracking_error_diff_pct, 2.5, 1)

  return {
    key: 'benchmark-relative',
    title: 'Benchmark-Relative Drift',
    currentStatus: `TE ${formatPct(activeReplay.candidate_result.metrics.tracking_error_pct)} / Beta ${formatNumber(activeReplay.candidate_result.metrics.beta_vs_benchmark)}`,
    recentChange: `TE ${formatSignedPct(comparison?.tracking_error_diff_pct ?? null)} / Beta ${formatSignedNumber(comparison?.beta_diff ?? null)}`,
    severity: tone === 'hot' ? 'High' : tone === 'warm' ? 'Medium' : 'Low',
    confidence: diagnosticsConfidence,
    provenance,
    tone,
    detail: [
      `Candidate correlation vs benchmark: ${formatNumber(activeReplay.candidate_result.metrics.correlation_vs_benchmark)}.`,
      `Active return: ${formatSignedPct(activeReplay.candidate_result.metrics.excess_return_pct)}.`,
      'Benchmark-relative watch uses shared replay metrics rather than frontend-derived scoring.',
    ],
  }
}

function volatilityMonitor(
  row: PortfolioDiagnosticsTopCallout | null,
  candidateDiagnostics: PortfolioDiagnosticsSnapshot | null,
  provenance: string,
  diagnosticsConfidence: 'High' | 'Medium' | 'Low',
): MonitorItem {
  const snapshot = candidateDiagnostics?.volatility_snapshot ?? null
  const tone = toneFromMagnitude(row?.delta_value ?? snapshot?.tracking_error_252d ?? null, 3, 1)

  return {
    key: 'volatility',
    title: 'Volatility / Regime',
    currentStatus: `Vol ${formatPct(snapshot?.realized_vol_252d)} / Drawdown ${formatPct(snapshot?.current_drawdown_pct)}`,
    recentChange: row ? `${row.label} ${comparisonValue(row)}` : `Tracking error 252d ${formatPct(snapshot?.tracking_error_252d)}`,
    severity: tone === 'hot' ? 'High' : tone === 'warm' ? 'Medium' : 'Low',
    confidence: diagnosticsConfidence,
    provenance,
    tone,
    detail: [
      `Max drawdown snapshot: ${formatPct(snapshot?.max_drawdown_pct)}.`,
      `Downside volatility: ${formatPct(snapshot?.downside_vol_252d)}.`,
      row?.rationale ?? 'Replay diagnostics expose volatility and drawdown directly; a separate replay regime label is not available in v1.',
    ],
  }
}

function buildMonitors(activeReplay: PortfolioAllocationBacktestResponse, hypotheticalReplayResult: HypotheticalReplayResponse | null) {
  const diagnostics = activeReplay.diagnostics_comparison
  const candidateDiagnostics = activeReplay.candidate_diagnostics ?? null
  const referenceDiagnostics = activeReplay.reference_diagnostics ?? null
  const historyTruthLabel = formatReplayHistoricalBasisLabel(
    candidateDiagnostics?.provenance.historical_basis ?? referenceDiagnostics?.provenance.historical_basis ?? null,
  )
  const provenanceNote = candidateDiagnostics?.provenance.note ?? referenceDiagnostics?.provenance.note ?? 'Replay diagnostics provenance is unavailable for this watch surface.'
  const provenance = `${historyTruthLabel}. ${provenanceNote}`
  const diagnosticsReady = Boolean(diagnostics && candidateDiagnostics)
  const diagnosticsConfidence = confidenceFromReplay(activeReplay, diagnosticsReady)

  const monitors: MonitorItem[] = [
    monitorFromCallout('factor-drift', 'Factor Drift', diagnostics?.top_factor_exposure_change ?? null, provenance, diagnosticsConfidence, 'No factor-drift callout is available for the current replay state.'),
    monitorFromCallout('concentration-drift', 'Concentration Drift', diagnostics?.top_concentration_change ?? null, provenance, diagnosticsConfidence, 'No concentration-drift callout is available for the current replay state.'),
    benchmarkRelativeMonitor(activeReplay.comparison, activeReplay, provenance, diagnosticsConfidence),
    volatilityMonitor(diagnostics?.top_volatility_change ?? null, candidateDiagnostics, provenance, diagnosticsConfidence),
    dataQualityMonitor(activeReplay, candidateDiagnostics, referenceDiagnostics),
  ]

  const topCallouts: MonitorCallout[] = [
    diagnostics?.top_factor_exposure_change ? {
      key: 'top-factor-callout',
      label: 'Top Factor Callout',
      value: `${diagnostics.top_factor_exposure_change.label} ${comparisonValue(diagnostics.top_factor_exposure_change)}`,
      helper: diagnostics.top_factor_exposure_change.rationale,
      tone: toneFromMagnitude(diagnostics.top_factor_exposure_change.delta_value, 0.2, 0.08),
    } : null,
    diagnostics?.top_concentration_change ? {
      key: 'top-concentration-callout',
      label: 'Top Concentration Callout',
      value: `${diagnostics.top_concentration_change.label} ${comparisonValue(diagnostics.top_concentration_change)}`,
      helper: diagnostics.top_concentration_change.rationale,
      tone: toneFromMagnitude(diagnostics.top_concentration_change.delta_value, 0.2, 0.08),
    } : null,
    diagnostics?.top_volatility_change ? {
      key: 'top-volatility-callout',
      label: 'Top Volatility Callout',
      value: `${diagnostics.top_volatility_change.label} ${comparisonValue(diagnostics.top_volatility_change)}`,
      helper: diagnostics.top_volatility_change.rationale,
      tone: toneFromMagnitude(diagnostics.top_volatility_change.delta_value, 3, 1),
    } : null,
    {
      key: 'data-quality-callout',
      label: 'Data Quality',
      value: monitors.find((item) => item.key === 'data-quality')?.currentStatus ?? 'n/a',
      helper: monitors.find((item) => item.key === 'data-quality')?.recentChange ?? 'n/a',
      tone: monitors.find((item) => item.key === 'data-quality')?.tone ?? 'neutral',
    },
  ].filter((item): item is MonitorCallout => item != null)

  const contextNote = hypotheticalReplayResult
    ? `Monitoring reflects the active hypothetical replay for ${hypotheticalReplayResult.proposal.incumbent_symbol} -> ${hypotheticalReplayResult.proposal.candidate_symbol}.`
    : 'Monitoring reflects the latest shared replay evidence available in Research.'

  return {
    monitors,
    topCallouts,
    contextNote,
    provenance,
    diagnosticsConfidence,
  }
}

export function MonitoringPanel({
  result,
  hypotheticalReplayResult,
}: {
  result: PortfolioAllocationBacktestResponse | null
  hypotheticalReplayResult: HypotheticalReplayResponse | null
}) {
  const activeReplay = hypotheticalReplayResult ? ('replay' in hypotheticalReplayResult ? hypotheticalReplayResult.replay : hypotheticalReplayResult.overlay_replay) : result
  const monitoringState = useMemo(() => activeReplay ? buildMonitors(activeReplay, hypotheticalReplayResult) : null, [activeReplay, hypotheticalReplayResult])
  const [selectedKey, setSelectedKey] = useState<string>('factor-drift')

  const selectedMonitor = monitoringState?.monitors.find((item) => item.key === selectedKey) ?? monitoringState?.monitors[0] ?? null

  if (!activeReplay || !monitoringState) {
    return (
      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Monitoring</p></div>
          <p className="helper">Compact watch surface for replay-state changes, severity, confidence, and provenance.</p>
        </div>
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Monitoring is waiting for replay evidence.</p>
          <p className="helper">Run a portfolio improvement replay or restore a saved replay review to populate the first monitoring surface.</p>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-bottom-grid monitoring-panel-shell" data-testid="monitoring-panel">
      <div className="section-header-inline sector-list-header">
        <div>
          <p className="panel-label">Monitoring</p>
          <h3>Research watch surface</h3>
        </div>
        <p className="helper">Review and watch the most important replay changes first. This surface stays analytical and does not trigger notifications or actions.</p>
      </div>

      <div className="summary-card monitoring-context-card">
        <p className="stat-label">Current Context</p>
        <p className="helper">{monitoringState.contextNote}</p>
        <div className="tab-bar dashboard-meta-row-quant diagnostics-provenance-strip">
          <span className="backtest-source-badge">Candidate {activeReplay.candidate_result.status}</span>
          <span className="backtest-source-badge">Diagnostics confidence {monitoringState.diagnosticsConfidence}</span>
          <span className="backtest-source-badge">Reference {activeReplay.reference_result?.status ?? 'not provided'}</span>
        </div>
      </div>

      <div className="dashboard-summary compact-summary-grid monitoring-callout-grid">
        {monitoringState.topCallouts.map((callout) => (
          <div className={cardClass(callout.tone)} key={callout.key}>
            <p className="stat-label">{callout.label}</p>
            <p className="summary-value">{callout.value}</p>
            <p className="helper">{callout.helper}</p>
          </div>
        ))}
      </div>

      <div className="monitoring-grid">
        <section className="monitoring-list-card">
          <div className="section-header-inline sector-list-header">
            <div><p className="panel-label">Watch Groups</p></div>
            <p className="helper">Current status, recent change, severity, confidence, and provenance stay explicit.</p>
          </div>
          <div className="list-table">
            <div className="list-row list-row-wide">
              <span>Group</span>
              <span>Status</span>
              <span>Recent Change</span>
              <span>Severity</span>
              <span>Confidence</span>
            </div>
            {monitoringState.monitors.map((item) => (
              <button className={`list-row list-row-wide list-row-button${selectedMonitor?.key === item.key ? ' active' : ''}`} key={item.key} onClick={() => setSelectedKey(item.key)} type="button">
                <span>{item.title}</span>
                <span className={rowToneClass(item.tone)}>{item.currentStatus}</span>
                <span>{item.recentChange}</span>
                <span className={rowToneClass(item.tone)}>{item.severity}</span>
                <span>{item.confidence}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="monitoring-detail-card">
          <div className="section-header-inline sector-list-header">
            <div><p className="panel-label">Detail</p></div>
            <p className="helper">Drill into one watch group at a time without broadening into a feed or recommendation layer.</p>
          </div>
          {selectedMonitor ? (
            <div className={cardClass(selectedMonitor.tone)}>
              <p className="stat-label">{selectedMonitor.title}</p>
              <p className="summary-value">{selectedMonitor.currentStatus}</p>
              <p className="helper">Recent change: {selectedMonitor.recentChange}</p>
              <p className="helper">Severity {selectedMonitor.severity} · Confidence {selectedMonitor.confidence}</p>
              <p className="helper">Provenance: {selectedMonitor.provenance}</p>
              <div className="monitoring-detail-list">
                {selectedMonitor.detail.map((item) => (
                  <p className="helper monitoring-detail-item" key={item}>{item}</p>
                ))}
              </div>
            </div>
          ) : (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">No monitoring detail is available.</p>
              <p className="helper">The current replay did not expose enough diagnostics detail for a watch-group drilldown.</p>
            </div>
          )}
        </section>
      </div>
    </section>
  )
}
