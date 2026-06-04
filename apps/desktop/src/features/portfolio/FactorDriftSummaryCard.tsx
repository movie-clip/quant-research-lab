/**
 * FactorDriftSummaryCard — Exposure tab (Epic 16 / US-16.1).
 *
 * Ranked, delta-indicator view of how each factor loading has moved over a
 * selectable rolling window: drift_k = β_k(latest) − β_k(reference), where both
 * loadings come from the same `rolling_loadings_<window>` series the engine
 * already computes and `reference` is the first date after leading-null
 * trimming. Factors are ranked by |drift| descending and rendered as divergent
 * magnitude bars (positive right of the baseline, negative left).
 *
 * Methodology: see §Factor Loading Drift (under §Statistical Factor Model) in
 * financial-methodology.md. Trust: synthetic — loadings are reconstructed from
 * current holdings × historical factor-proxy prices. This card performs no
 * regression; it takes a first difference of two engine-computed loadings (a
 * presentation-layer rebasing). When the selected window has insufficient
 * history it surfaces an EmptyState — never zeros, never fabricated rows.
 *
 * T-16.1.1 decision: the small series/coverage helpers below are reimplemented
 * locally rather than extracted from RollingFactorLoadingsCard. The duplication
 * is a few lines each and a local copy keeps that component (and its tests)
 * untouched.
 */
import { useMemo, useState } from 'react'

import type { ExposureAnalysis, ExposureFactorModelResponse, StatisticalFactorModel } from './types'
import { buildExposureFactorModel } from './portfolioAnalysisAdapter'

import { CardShell } from '../../app/primitives/CardShell'
import { EmptyState } from '../../app/primitives/EmptyState'
import { TrustBadge } from '../../app/primitives/TrustBadge'
import { WindowSelector } from '../../app/primitives/WindowSelector'

type DriftWindow = 20 | 60 | 252
const WINDOW_OPTIONS: DriftWindow[] = [20, 60, 252]

/** Same default factor set the Dashboard trend chart shows, so the two cards
 *  stay visually consistent. */
const DEFAULT_VISIBLE_FACTORS = ['market', 'growth', 'value', 'small_cap', 'technology', 'financials']

const SYNTHETIC_TOOLTIP =
  'Factor loadings are reconstructed from current holdings × historical factor-proxy prices. Drift is the change in loading over the selected window.'

type RollingSeries = StatisticalFactorModel['rolling_loadings_60d']
type DriftRow = {
  key: string
  label: string
  reference: number
  latest: number
  delta: number
}

function getRollingSeries(model: ExposureFactorModelResponse, window: DriftWindow): RollingSeries {
  if (window === 20) return model.statistical_factor_model.rolling_loadings_20d ?? []
  if (window === 252) return model.statistical_factor_model.rolling_loadings_252d ?? []
  return model.statistical_factor_model.rolling_loadings_60d ?? []
}

function getWindowObservations(model: ExposureFactorModelResponse, window: DriftWindow): number {
  return (model.statistical_factor_model.windows ?? []).find((w) => w.window_days === window)?.observations ?? 0
}

/** Drop leading rows where every visible factor is null — the window hasn't
 *  filled yet for any of them. */
function trimLeadingNullPoints(data: RollingSeries, keys: string[]): RollingSeries {
  const firstIndex = data.findIndex((point) => keys.some((key) => (point as unknown as Record<string, number | null | undefined>)[key] != null))
  if (firstIndex < 0) return []
  return firstIndex > 0 ? data.slice(firstIndex) : data
}

function readLoading(point: RollingSeries[number] | undefined, key: string): number | null {
  if (!point) return null
  const value = (point as unknown as Record<string, number | null | undefined>)[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function formatLoading(value: number): string {
  return value.toFixed(2)
}

/** Signed, fixed-precision delta using a true minus sign for negatives. */
function formatDelta(delta: number): string {
  if (delta > 0) return `+${delta.toFixed(2)}`
  if (delta < 0) return `−${Math.abs(delta).toFixed(2)}`
  return '0.00'
}

/** Non-color direction marker (color-blind safety, AC4). */
function directionArrow(delta: number): string {
  if (delta > 0) return '▲'
  if (delta < 0) return '▼'
  return '•'
}

function deltaColor(delta: number): string {
  if (delta > 0) return 'var(--color-value-positive)'
  if (delta < 0) return 'var(--color-value-negative)'
  return 'var(--color-text-muted)'
}

function factorColorVar(key: string): string {
  return `var(--color-factor-${key.replace(/_/g, '-')}, var(--color-factor-default))`
}

function formatDateLabel(value: string | null | undefined): string {
  if (typeof value !== 'string') return ''
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) return value
  return `${month}/${day}/${year.slice(2)}`
}

function DriftBarRow({ row, maxAbs }: { row: DriftRow; maxAbs: number }) {
  const color = deltaColor(row.delta)
  const widthPct = maxAbs === 0 ? 0 : (Math.abs(row.delta) / maxAbs) * 100

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1.3fr) auto minmax(0, 2fr) auto',
        gap: 'var(--space-md)',
        alignItems: 'center',
        padding: 'var(--space-sm) 0',
        borderBottom: 'var(--border-thin) solid var(--color-border-subtle)',
      }}
    >
      <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', minWidth: 0 }}>
        <span
          aria-hidden="true"
          style={{
            width: 'var(--space-sm)',
            height: 'var(--space-sm)',
            borderRadius: 'var(--radius-sm)',
            background: factorColorVar(row.key),
            flexShrink: 0,
          }}
        />
        <span
          style={{
            fontSize: 'var(--font-body-sm)',
            color: 'var(--color-text-primary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {row.label}
        </span>
      </span>

      <span
        style={{
          fontSize: 'var(--font-caption)',
          color: 'var(--color-text-muted)',
          fontVariantNumeric: 'tabular-nums',
          whiteSpace: 'nowrap',
        }}
      >
        {formatLoading(row.reference)} → {formatLoading(row.latest)}
      </span>

      {/* Divergent magnitude bar — centered on a zero baseline. Negative drift
          extends left of center, positive right of center. Direction is encoded
          by side (and the signed value + arrow), not color alone. */}
      <span aria-hidden="true" style={{ display: 'flex', alignItems: 'center' }}>
        <span style={{ flex: 1, display: 'flex', justifyContent: 'flex-end' }}>
          {row.delta < 0 ? (
            <span style={{ width: `${widthPct}%`, height: 'var(--space-sm)', background: color, borderRadius: 'var(--radius-sm)' }} />
          ) : null}
        </span>
        <span style={{ width: 'var(--border-medium)', height: 'var(--space-md)', background: 'var(--color-border-strong)' }} />
        <span style={{ flex: 1, display: 'flex', justifyContent: 'flex-start' }}>
          {row.delta > 0 ? (
            <span style={{ width: `${widthPct}%`, height: 'var(--space-sm)', background: color, borderRadius: 'var(--radius-sm)' }} />
          ) : null}
        </span>
      </span>

      <span
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'flex-end',
          gap: 'var(--space-xs)',
          color,
          fontVariantNumeric: 'tabular-nums',
          fontWeight: 600,
          whiteSpace: 'nowrap',
        }}
      >
        <span aria-hidden="true" style={{ fontSize: 'var(--font-caption)' }}>{directionArrow(row.delta)}</span>
        <span style={{ fontSize: 'var(--font-body-sm)' }}>{formatDelta(row.delta)}</span>
      </span>
    </div>
  )
}

export function FactorDriftSummaryCard({ result }: { result: ExposureAnalysis | null }) {
  const [window, setWindow] = useState<DriftWindow>(60)

  const factorModel = useMemo(() => (result ? buildExposureFactorModel(result) : null), [result])
  const registryByKey = useMemo(
    () => Object.fromEntries((factorModel?.factor_registry ?? []).map((f) => [f.key, f])),
    [factorModel],
  )

  const visibleKeys = useMemo(
    () => DEFAULT_VISIBLE_FACTORS.filter((key) => registryByKey[key]),
    [registryByKey],
  )

  const trimmed = useMemo(() => {
    if (!factorModel) return [] as RollingSeries
    return trimLeadingNullPoints(getRollingSeries(factorModel, window), visibleKeys)
  }, [factorModel, window, visibleKeys])

  const rows = useMemo<DriftRow[]>(() => {
    if (!trimmed.length) return []
    const reference = trimmed[0]
    const latest = trimmed[trimmed.length - 1]
    const computed: DriftRow[] = []
    for (const key of visibleKeys) {
      const ref = readLoading(reference, key)
      const last = readLoading(latest, key)
      if (ref == null || last == null) continue
      computed.push({ key, label: registryByKey[key]?.label ?? key, reference: ref, latest: last, delta: last - ref })
    }
    return computed.sort((a, b) => {
      const diff = Math.abs(b.delta) - Math.abs(a.delta)
      return diff !== 0 ? diff : a.label.localeCompare(b.label)
    })
  }, [trimmed, visibleKeys, registryByKey])

  // No registry at all → the factor model isn't available on this snapshot;
  // render nothing (matches the Dashboard trend chart's behaviour).
  if (!factorModel || !visibleKeys.length) return null

  const maxAbs = rows.reduce((acc, r) => Math.max(acc, Math.abs(r.delta)), 0)
  const observations = getWindowObservations(factorModel, window)

  return (
    <CardShell
      title="Factor Drift Summary"
      badge={<TrustBadge type="synthetic" tooltip={SYNTHETIC_TOOLTIP} />}
      actions={
        <WindowSelector<DriftWindow>
          options={WINDOW_OPTIONS}
          value={window}
          onChange={setWindow}
          labelFn={(w) => `${w}d`}
        />
      }
    >
      {rows.length ? (
        <div>
          <p className="helper" style={{ margin: '0 0 var(--space-sm) 0' }}>
            {`Latest vs start of window · ${observations} observations · ${formatDateLabel(trimmed[0]?.date)} → ${formatDateLabel(trimmed[trimmed.length - 1]?.date)}`}
          </p>
          {rows.map((row) => (
            <DriftBarRow key={row.key} row={row} maxAbs={maxAbs} />
          ))}
        </div>
      ) : (
        <EmptyState
          title={`Not enough history for ${window}d factor drift.`}
          detail={`This view needs a filled ${window}d rolling window. Available observations: ${observations}`}
        />
      )}
    </CardShell>
  )
}
