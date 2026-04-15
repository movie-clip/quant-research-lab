import { useMemo, useState } from 'react'

import type { DiagnosticsEngineResponse } from './types'

type ShiftCategoryFilter = 'all' | 'market' | 'style' | 'sector' | 'macro'

function formatPct(value: number | null | undefined) {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'n/a' : value.toFixed(digits)
}

function formatSignedNumber(value: number | null | undefined, digits = 2) {
  if (value == null) return 'n/a'
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}`
}

function getShiftFlags(snapshot: DiagnosticsEngineResponse['factor_shift_diagnostics']['snapshots'][number]) {
  return [
    snapshot.shift_flag_20d ? 'S20' : null,
    snapshot.shift_flag_60d ? 'S60' : null,
    snapshot.stability_flag ? 'STAB' : null,
    snapshot.collinearity_flag ? 'COL' : null,
    snapshot.volatility_flag ? 'VOL' : null,
  ].filter((item): item is string => item != null)
}

function diagnosticsHistoryBasisLabel(result: DiagnosticsEngineResponse) {
  if (result.provenance.historical_basis === 'imported_portfolio_history') return 'Imported portfolio history'
  if (result.provenance.historical_basis === 'market_data_history') return 'Synthetic snapshot-history'
  return 'History unavailable'
}

function diagnosticsStatusLabel(result: DiagnosticsEngineResponse) {
  return result.availability.historical_sections_available ? 'Historical sections live' : 'Historical sections unavailable'
}

function diagnosticsLead() {
  return 'Review provenance and decision-grade signals before drilling into deeper factor and risk detail.'
}

export function DiagnosticsPanel({ result }: { result: DiagnosticsEngineResponse | null }) {
  const [shiftCategoryFilter, setShiftCategoryFilter] = useState<ShiftCategoryFilter>('all')
  const [shiftSortMode, setShiftSortMode] = useState<'absolute_20d' | 'absolute_60d'>('absolute_20d')
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const [factorRiskSortMode, setFactorRiskSortMode] = useState<'risk_share' | 'variance_contribution'>('risk_share')
  const [positionRiskSortMode, setPositionRiskSortMode] = useState<'risk_share' | 'component_contribution'>('risk_share')

  const shiftSnapshots = result?.factor_shift_diagnostics.snapshots ?? []
  const factorContributions = result?.risk_contribution_breakdown.factor_contributions ?? []
  const positionContributions = result?.risk_contribution_breakdown.position_contributions ?? []

  const filteredShiftSnapshots = useMemo(() => {
    const filtered = shiftSnapshots.filter((item) => {
      if (shiftCategoryFilter !== 'all' && item.category !== shiftCategoryFilter) return false
      if (!flaggedOnly) return true
      return getShiftFlags(item).length > 0
    })
    return [...filtered].sort((left, right) => {
      const leftValue = shiftSortMode === 'absolute_60d' ? left.abs_change_60d ?? -1 : left.abs_change_20d ?? -1
      const rightValue = shiftSortMode === 'absolute_60d' ? right.abs_change_60d ?? -1 : right.abs_change_20d ?? -1
      return rightValue - leftValue
    })
  }, [flaggedOnly, shiftCategoryFilter, shiftSnapshots, shiftSortMode])

  const sortedFactorContributions = useMemo(() => {
    return [...factorContributions].sort((left, right) => {
      const leftValue = factorRiskSortMode === 'variance_contribution' ? left.variance_contribution ?? -1 : left.risk_share ?? -1
      const rightValue = factorRiskSortMode === 'variance_contribution' ? right.variance_contribution ?? -1 : right.risk_share ?? -1
      return rightValue - leftValue
    })
  }, [factorContributions, factorRiskSortMode])

  const sortedPositionContributions = useMemo(() => {
    return [...positionContributions].sort((left, right) => {
      const leftValue = positionRiskSortMode === 'component_contribution' ? left.component_contribution ?? -1 : left.risk_share ?? -1
      const rightValue = positionRiskSortMode === 'component_contribution' ? right.component_contribution ?? -1 : right.risk_share ?? -1
      return rightValue - leftValue
    })
  }, [positionContributions, positionRiskSortMode])

  if (!result) {
    return (
      <article className="panel">
        <p className="panel-label">Diagnostics</p>
        <h2>Factor and risk diagnostics</h2>
        <p className="lead compact-lead">{diagnosticsLead()}</p>
        <p className="lead compact-lead">Import a portfolio from the Dashboard to inspect current risk diagnostics.</p>
      </article>
    )
  }

  if (!result.availability.historical_sections_available) {
    return (
      <article className="panel">
        <p className="panel-label">Diagnostics</p>
        <h2>Factor and risk diagnostics</h2>
        <p className="lead compact-lead">{diagnosticsLead()}</p>
        <div className="tab-bar" style={{ justifyContent: 'flex-start', margin: '8px 0 0' }}>
          <span className="backtest-source-badge">{diagnosticsHistoryBasisLabel(result)}</span>
          <span className="backtest-source-badge">{diagnosticsStatusLabel(result)}</span>
        </div>
        <p className="helper">{result.provenance.note}</p>
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Historical diagnostics unavailable for this snapshot.</p>
          <p className="helper">{result.availability.note ?? 'This view requires imported portfolio history context and is not approximated from a snapshot alone.'}</p>
          <p className="helper">Historical diagnostics are not approximated when history context is missing.</p>
        </div>
      </article>
    )
  }

  return (
    <article className="panel">
      <p className="panel-label">Diagnostics</p>
      <h2>Factor and risk diagnostics</h2>
      <p className="lead compact-lead">{diagnosticsLead()}</p>
      <div className="tab-bar" style={{ justifyContent: 'flex-start', margin: '8px 0 0' }}>
        <span className="backtest-source-badge">{diagnosticsHistoryBasisLabel(result)}</span>
        <span className="backtest-source-badge">{diagnosticsStatusLabel(result)}</span>
      </div>
      <p className="helper">{result.provenance.note}</p>
      {result.availability.note ? <p className="helper">{result.availability.note}</p> : null}

      <section className="dashboard-bottom-grid" data-testid="diagnostics-decision-readout">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Decision Readout</p></div>
          <p className="helper">Top-line diagnostics surfaced directly from authoritative backend provenance and summary outputs.</p>
        </div>
        <div className="dashboard-summary compact-summary-grid">
          <div className="summary-card"><p className="stat-label">History Basis</p><p className="summary-value">{diagnosticsHistoryBasisLabel(result)}</p></div>
          <div className="summary-card"><p className="stat-label">Historical Status</p><p className="summary-value">{diagnosticsStatusLabel(result)}</p></div>
          <div className="summary-card"><p className="stat-label">Model Confidence</p><p className="summary-value">{result.model_reliability.confidence}</p></div>
          <div className="summary-card"><p className="stat-label">Current Drawdown</p><p className="summary-value">{formatPct(result.drawdown_summary.current_drawdown_pct)}</p></div>
          <div className="summary-card"><p className="stat-label">Top 3 Factor Risk Share</p><p className="summary-value">{formatPct(result.risk_concentration_summary.top_3_factor_risk_share != null ? result.risk_concentration_summary.top_3_factor_risk_share * 100 : null)}</p></div>
          <div className="summary-card"><p className="stat-label">Top 5 Position Risk Share</p><p className="summary-value">{formatPct(result.risk_concentration_summary.top_5_position_risk_share != null ? result.risk_concentration_summary.top_5_position_risk_share * 100 : null)}</p></div>
        </div>
      </section>

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Risk Concentration</p></div><p className="helper">Concentration of factor and position risk within the historical diagnostics window.</p></div>
        <div className="dashboard-summary compact-summary-grid">
          <div className="summary-card"><p className="stat-label">Top 1 Factor Risk Share</p><p className="summary-value">{formatPct(result.risk_concentration_summary.top_1_factor_risk_share != null ? result.risk_concentration_summary.top_1_factor_risk_share * 100 : null)}</p></div>
          <div className="summary-card"><p className="stat-label">Top 3 Factor Risk Share</p><p className="summary-value">{formatPct(result.risk_concentration_summary.top_3_factor_risk_share != null ? result.risk_concentration_summary.top_3_factor_risk_share * 100 : null)}</p></div>
          <div className="summary-card"><p className="stat-label">Top 1 Position Risk Share</p><p className="summary-value">{formatPct(result.risk_concentration_summary.top_1_position_risk_share != null ? result.risk_concentration_summary.top_1_position_risk_share * 100 : null)}</p></div>
          <div className="summary-card"><p className="stat-label">Top 5 Position Risk Share</p><p className="summary-value">{formatPct(result.risk_concentration_summary.top_5_position_risk_share != null ? result.risk_concentration_summary.top_5_position_risk_share * 100 : null)}</p></div>
          <div className="summary-card"><p className="stat-label">Factor HHI</p><p className="summary-value">{formatNumber(result.risk_concentration_summary.factor_hhi, 4)}</p></div>
          <div className="summary-card"><p className="stat-label">Position HHI</p><p className="summary-value">{formatNumber(result.risk_concentration_summary.position_hhi, 4)}</p></div>
        </div>
      </section>

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Model Reliability</p></div><p className="helper">Backend model fit and stability for the current diagnostics window; interpret it alongside provenance and availability.</p></div>
        <div className="dashboard-summary compact-summary-grid">
          <div className="summary-card"><p className="stat-label">R-Squared</p><p className="summary-value">{formatNumber(result.model_reliability.r_squared, 4)}</p></div>
          <div className="summary-card"><p className="stat-label">Residual Volatility</p><p className="summary-value">{formatPct(result.model_reliability.residual_volatility)}</p></div>
          <div className="summary-card"><p className="stat-label">Collinearity Pairs</p><p className="summary-value">{formatNumber(result.model_reliability.collinearity_pair_count, 0)}</p></div>
          <div className="summary-card"><p className="stat-label">Max Abs Correlation</p><p className="summary-value">{formatNumber(result.model_reliability.max_abs_factor_correlation, 4)}</p></div>
          <div className="summary-card"><p className="stat-label">Factors Used</p><p className="summary-value">{formatNumber(result.model_reliability.factor_count_used, 0)}</p></div>
          <div className="summary-card"><p className="stat-label">Missing Factors</p><p className="summary-value">{formatNumber(result.model_reliability.missing_factor_count, 0)}</p></div>
          <div className="summary-card"><p className="stat-label">Stability Score</p><p className="summary-value">{formatNumber(result.model_reliability.stability_score, 4)}</p></div>
          <div className="summary-card"><p className="stat-label">Confidence</p><p className="summary-value">{result.model_reliability.confidence}</p></div>
        </div>
      </section>

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Historical Summary</p></div>
          <p className="helper">History-derived summary only; current-state holdings concentration is tracked separately.</p>
        </div>
        <div className="dashboard-summary compact-summary-grid">
          <div className="summary-card"><p className="stat-label">Current Drawdown</p><p className="summary-value">{formatPct(result.drawdown_summary.current_drawdown_pct)}</p></div>
          <div className="summary-card"><p className="stat-label">Max Drawdown</p><p className="summary-value">{formatPct(result.drawdown_summary.max_drawdown_pct)}</p></div>
          <div className="summary-card"><p className="stat-label">Portfolio Volatility</p><p className="summary-value">{formatPct(result.volatility_summary.portfolio_volatility_pct)}</p></div>
          <div className="summary-card"><p className="stat-label">Benchmark Volatility</p><p className="summary-value">{formatPct(result.volatility_summary.benchmark_volatility_pct)}</p></div>
          <div className="summary-card"><p className="stat-label">Downside Volatility</p><p className="summary-value">{formatPct(result.volatility_summary.downside_volatility_pct)}</p></div>
          <div className="summary-card"><p className="stat-label">Tracking Error</p><p className="summary-value">{formatPct(result.volatility_summary.tracking_error_pct)}</p></div>
          <div className="summary-card"><p className="stat-label">Factor HHI</p><p className="summary-value">{formatNumber(result.risk_concentration_summary.factor_hhi, 4)}</p></div>
          <div className="summary-card"><p className="stat-label">Position HHI</p><p className="summary-value">{formatNumber(result.risk_concentration_summary.position_hhi, 4)}</p></div>
        </div>
      </section>

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Risk Contribution</p></div><p className="helper">Variance decomposition from the backend diagnostics window. {result.risk_contribution_breakdown.window_days}d / {result.risk_contribution_breakdown.observation_count} obs / {result.risk_contribution_breakdown.status}</p></div>
        <div className="dashboard-summary compact-summary-grid">
          <div className="summary-card"><p className="stat-label">Factor Total Variance</p><p className="summary-value">{formatNumber(result.risk_contribution_breakdown.factor_total_variance, 4)}</p></div>
          <div className="summary-card"><p className="stat-label">Specific Variance</p><p className="summary-value">{formatNumber(result.risk_contribution_breakdown.specific_variance, 4)}</p></div>
          <div className="summary-card"><p className="stat-label">Total Variance</p><p className="summary-value">{formatNumber(result.risk_contribution_breakdown.total_variance, 4)}</p></div>
          <div className="summary-card"><p className="stat-label">Factor Risk Share</p><p className="summary-value">{formatPct(result.risk_contribution_breakdown.factor_risk_share_total != null ? result.risk_contribution_breakdown.factor_risk_share_total * 100 : null)}</p></div>
          <div className="summary-card"><p className="stat-label">Specific Risk Share</p><p className="summary-value">{formatPct(result.risk_contribution_breakdown.specific_risk_share != null ? result.risk_contribution_breakdown.specific_risk_share * 100 : null)}</p></div>
          <div className="summary-card"><p className="stat-label">Residual Volatility</p><p className="summary-value">{formatPct(result.risk_contribution_breakdown.residual_volatility)}</p></div>
        </div>
      </section>

      <div className="split-grid dashboard-bottom-grid">
        <section>
          <div className="section-header-inline sector-list-header"><div><p className="panel-label">Factor Contributions</p></div><p className="helper">Factor-level share of modeled portfolio risk for the current historical window.</p><div className="toggle-group" aria-label="Factor contribution sort mode"><button className={`toggle-chip${factorRiskSortMode === 'risk_share' ? ' active' : ''}`} onClick={() => setFactorRiskSortMode('risk_share')} type="button">Risk Share</button><button className={`toggle-chip${factorRiskSortMode === 'variance_contribution' ? ' active' : ''}`} onClick={() => setFactorRiskSortMode('variance_contribution')} type="button">Variance</button></div></div>
          <div className="factor-snapshot-table-wrap">
            <div className="risk-contrib-table-grid factor-snapshot-header-row">
              <span>Factor</span>
              <span>Proxy</span>
              <span>Loading</span>
              <span>Factor Vol</span>
              <span>Variance Contribution</span>
              <span>Risk Share</span>
            </div>
            {sortedFactorContributions.length ? sortedFactorContributions.map((item) => (
              <div className="risk-contrib-table-grid factor-shift-data-row" key={`factor-risk-${item.key}`}>
                <span className="factor-snapshot-primary">{item.label}</span>
                <span>{item.us_proxy}</span>
                <span>{formatNumber(item.loading, 2)}</span>
                <span>{formatPct(item.factor_volatility)}</span>
                <span>{formatNumber(item.variance_contribution, 4)}</span>
                <span>{formatPct(item.risk_share != null ? item.risk_share * 100 : null)}</span>
              </div>
            )) : <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">No factor risk contributions available.</p></div>}
          </div>
        </section>
        <section>
          <div className="section-header-inline sector-list-header"><div><p className="panel-label">Position Contributions</p></div><p className="helper">Position-level share of modeled portfolio risk for the current historical window.</p><div className="toggle-group" aria-label="Position contribution sort mode"><button className={`toggle-chip${positionRiskSortMode === 'risk_share' ? ' active' : ''}`} onClick={() => setPositionRiskSortMode('risk_share')} type="button">Risk Share</button><button className={`toggle-chip${positionRiskSortMode === 'component_contribution' ? ' active' : ''}`} onClick={() => setPositionRiskSortMode('component_contribution')} type="button">Component</button></div></div>
          <div className="factor-snapshot-table-wrap">
            <div className="risk-position-table-grid factor-snapshot-header-row">
              <span>Symbol</span>
              <span>Weight</span>
              <span>Volatility</span>
              <span>Marginal</span>
              <span>Component</span>
              <span>Risk Share</span>
            </div>
            {sortedPositionContributions.length ? sortedPositionContributions.map((item) => (
              <div className="risk-position-table-grid factor-shift-data-row" key={`position-risk-${item.symbol}`}>
                <span className="factor-snapshot-primary">{item.symbol}</span>
                <span>{formatPct(item.weight * 100)}</span>
                <span>{formatPct(item.volatility)}</span>
                <span>{formatNumber(item.marginal_contribution, 4)}</span>
                <span>{formatNumber(item.component_contribution, 4)}</span>
                <span>{formatPct(item.risk_share != null ? item.risk_share * 100 : null)}</span>
              </div>
            )) : <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">No position risk contributions available.</p></div>}
          </div>
        </section>
      </div>

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Factor Change Monitor</p></div>
          <p className="helper">Window-to-window loading shifts from the backend model; flags remain explicit when stability is weaker.</p>
          <div className="chart-controls">
            <div className="toggle-group" aria-label="Shift sort mode">
              <button className={`toggle-chip${shiftSortMode === 'absolute_20d' ? ' active' : ''}`} onClick={() => setShiftSortMode('absolute_20d')} type="button">Abs 20d</button>
              <button className={`toggle-chip${shiftSortMode === 'absolute_60d' ? ' active' : ''}`} onClick={() => setShiftSortMode('absolute_60d')} type="button">Abs 60d</button>
            </div>
            <div className="toggle-group" aria-label="Shift category filter">
              <button className={`toggle-chip${shiftCategoryFilter === 'all' ? ' active' : ''}`} onClick={() => setShiftCategoryFilter('all')} type="button">All</button>
              <button className={`toggle-chip${shiftCategoryFilter === 'market' ? ' active' : ''}`} onClick={() => setShiftCategoryFilter('market')} type="button">Market</button>
              <button className={`toggle-chip${shiftCategoryFilter === 'style' ? ' active' : ''}`} onClick={() => setShiftCategoryFilter('style')} type="button">Style</button>
              <button className={`toggle-chip${shiftCategoryFilter === 'sector' ? ' active' : ''}`} onClick={() => setShiftCategoryFilter('sector')} type="button">Sector</button>
              <button className={`toggle-chip${shiftCategoryFilter === 'macro' ? ' active' : ''}`} onClick={() => setShiftCategoryFilter('macro')} type="button">Macro</button>
            </div>
            <div className="toggle-group" aria-label="Shift flagged filter">
              <button className={`toggle-chip${flaggedOnly ? ' active' : ''}`} onClick={() => setFlaggedOnly((value) => !value)} type="button">Flagged only</button>
            </div>
          </div>
        </div>
        <div className="factor-snapshot-table-wrap">
          <div className="factor-shift-table-grid factor-snapshot-header-row">
            <span>Factor</span>
            <span>Proxy</span>
            <span>Category</span>
            <span>20d Loading</span>
            <span>60d Loading</span>
            <span>252d Loading</span>
            <span>20d Change</span>
            <span>60d Change</span>
            <span>Gap 20/60</span>
            <span>Gap 60/252</span>
            <span>Confidence</span>
            <span>Flags</span>
          </div>
          {filteredShiftSnapshots.length ? filteredShiftSnapshots.map((snapshot) => (
            <div className="factor-shift-table-grid factor-shift-data-row" key={`shift-${snapshot.key}`}>
              <span className="factor-snapshot-primary">{snapshot.label}</span>
              <span>{snapshot.us_proxy}</span>
              <span>{snapshot.category}</span>
              <span>{formatNumber(snapshot.current_loading_20d, 2)}</span>
              <span>{formatNumber(snapshot.current_loading_60d, 2)}</span>
              <span>{formatNumber(snapshot.current_loading_252d, 2)}</span>
              <span>{formatSignedNumber(snapshot.change_20d, 2)}</span>
              <span>{formatSignedNumber(snapshot.change_60d, 2)}</span>
              <span>{formatNumber(snapshot.stability_gap_20d_60d, 2)}</span>
              <span>{formatNumber(snapshot.stability_gap_60d_252d, 2)}</span>
              <span>{snapshot.confidence}</span>
              <span className="factor-shift-flags">{getShiftFlags(snapshot).length ? getShiftFlags(snapshot).map((flag) => <span className="flag-chip" key={`${snapshot.key}-${flag}`}>{flag}</span>) : 'n/a'}</span>
            </div>
          )) : <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">No factor shifts match the current filters.</p></div>}
        </div>
      </section>
    </article>
  )
}
