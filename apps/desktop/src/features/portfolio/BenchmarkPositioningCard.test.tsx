import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { ExposureAnalysis } from './types'
import { BenchmarkPositioningCard } from './BenchmarkPositioningCard'

afterEach(cleanup)

/**
 * CR-1 (2026-08-24-sbio-still-unclassified-bug, quant-audit Finding 1):
 * getBenchmarkTrust must derive the badge entirely from the frozen
 * `exposure_availability` fields. Before this fix it also read the live
 * `run_metadata.source_status.benchmark_holdings`, which — after T1 taught the
 * app to persist/replay a frozen `exposure_availability` for imported base
 * snapshots — could be of a different vintage than `availability` and
 * `market_overlap`, producing a badge that overstated the actual basis of the
 * numbers shown beside it. These tests pin `run_metadata` to a value that
 * actively disagrees with `availability` and assert the badge follows
 * `availability` alone.
 */
function analysis(overrides: {
  overlapStatus?: 'live' | 'partial' | 'unavailable'
  overlapConfidence?: 'high' | 'medium' | 'low'
  staleBenchmarkHoldings?: 'verified' | 'degraded' | 'unavailable'
} = {}): ExposureAnalysis {
  const {
    overlapStatus = 'live',
    overlapConfidence = 'high',
    staleBenchmarkHoldings = 'unavailable',
  } = overrides
  return {
    exposure_availability: {
      lookthrough_status: 'live',
      lookthrough_confidence: 'high',
      benchmark_overlap_status: overlapStatus,
      benchmark_overlap_confidence: overlapConfidence,
      note: null,
    },
    // Deliberately stale/unrelated to `exposure_availability` above — this is
    // the live field a persisted base-import snapshot never re-freezes.
    run_metadata: {
      source_status: {
        lookthrough_resolution: 'live',
        benchmark_holdings: staleBenchmarkHoldings,
      },
      reproducibility: {
        benchmark_symbol: 'SPY',
      },
    },
    market_overlap: {
      benchmark_symbol: 'SPY',
      overlap_weight: 0.62,
      active_share: 0.38,
      portfolio_in_benchmark_weight: 0.62,
      benchmark_covered_weight: 0.85,
      top_overweights: [],
      top_underweights: [],
    },
  } as unknown as ExposureAnalysis
}

describe('BenchmarkPositioningCard getBenchmarkTrust — single-vintage derivation', () => {
  it('reads "verified" from a high-confidence frozen availability even when live run_metadata disagrees', () => {
    render(
      <BenchmarkPositioningCard
        exposureResult={analysis({
          overlapStatus: 'live',
          overlapConfidence: 'high',
          // Live run_metadata claims the benchmark holdings are unavailable —
          // must not downgrade a verified frozen badge.
          staleBenchmarkHoldings: 'unavailable',
        })}
      />,
    )

    const text = screen.getByLabelText('Benchmark Positioning').textContent ?? ''
    expect(text).toContain('Positioning available versus SPY.')
  })

  it('reads "degraded" from a medium-confidence frozen availability even when live run_metadata claims verified', () => {
    render(
      <BenchmarkPositioningCard
        exposureResult={analysis({
          overlapStatus: 'live',
          overlapConfidence: 'medium',
          // Live run_metadata claims the benchmark holdings are verified —
          // must not upgrade a degraded frozen badge. This is the exact
          // scenario from the quant-audit's Finding 1 walkthrough: 85%
          // coverage at import time (degraded, frozen) vs >=99% coverage on a
          // later live render (verified, unfrozen).
          staleBenchmarkHoldings: 'verified',
        })}
      />,
    )

    const text = screen.getByLabelText('Benchmark Positioning').textContent ?? ''
    expect(text).toContain('Positioning degraded versus SPY.')
    expect(text).not.toContain('Positioning available versus SPY.')
  })

  it('reads "partial" from availability alone, short-circuiting before any run_metadata read', () => {
    render(
      <BenchmarkPositioningCard
        exposureResult={analysis({
          overlapStatus: 'partial',
          overlapConfidence: 'medium',
          staleBenchmarkHoldings: 'verified',
        })}
      />,
    )

    const text = screen.getByLabelText('Benchmark Positioning').textContent ?? ''
    expect(text).toContain('Positioning partial versus SPY.')
  })

  it('reads "unavailable" from availability alone when overlap status is unavailable', () => {
    render(
      <BenchmarkPositioningCard
        exposureResult={analysis({
          overlapStatus: 'unavailable',
          overlapConfidence: 'low',
          staleBenchmarkHoldings: 'verified',
        })}
      />,
    )

    const text = screen.getByLabelText('Benchmark Positioning').textContent ?? ''
    expect(text).toContain('Benchmark-relative positioning unavailable for this snapshot.')
  })
})
