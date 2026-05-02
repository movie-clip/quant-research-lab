import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { createDiagnosticsFixture } from '../../test/portfolioFixtures'
import type { MonitorDefinitionCatalogResponse } from './types'
import { TrendRiskOverlaysPanel } from './TrendRiskOverlaysPanel'

afterEach(() => {
  cleanup()
})

describe('TrendRiskOverlaysPanel', () => {
  it('deserializes monitor-definition catalog discovery metadata with explicit absent latest-snapshot semantics', () => {
    const payload: MonitorDefinitionCatalogResponse = {
      items: [
        {
          monitor_definition_id: 'monitor-1',
          monitor_id: 'benchmark_trend_overlay_v1',
          benchmark_symbol: 'QQQ',
          schema_version: 'monitor_definition_artifact_v1',
          fingerprint: 'fp-1',
          review_scope: 'current_portfolio_truth_only',
          evaluation_mode: 'review_only_observation_evaluation',
          observation_statuses: ['ok', 'degraded'],
          thresholds: {
            minimum_confirmation_count: 2,
            risk_on_min_risky_weight: 0.75,
            risk_on_max_cash_weight: 0.25,
            risk_reduced_max_risky_weight: 0.45,
            risk_reduced_min_cash_weight: 0.55,
          },
          source_lineage_requirements: {
            benchmark_source_kind: 'benchmark_overlay_signal',
            portfolio_truth_basis: 'imported_portfolio_snapshot',
            required_portfolio_statement_fields: ['positions'],
            required_benchmark_observation_fields: ['status'],
          },
          metadata: {
            metadata_truth: 'authoritative_persisted_artifact_metadata',
            row_provenance: 'persisted_monitor_definition_artifact',
            status: {
              lifecycle: {
                overlay_family: 'benchmark_trend',
                review_support_status: 'review_supported',
                lifecycle_status: 'enabled',
              },
              status_source_precedence: 'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot',
              latest_observation_status: 'absent',
              latest_observation: null,
              latest_evaluation_snapshot_status: 'absent',
              latest_evaluation_snapshot: null,
            },
          },
        },
      ],
      metadata: {
        contract_version: 'monitor_definition_discovery_v1',
        metadata_truth: 'authoritative_persisted_artifact_metadata',
        row_provenance: 'persisted_monitor_definition_artifact',
        supported_monitor_ids: ['benchmark_trend_overlay_v1'],
        supported_overlay_families: ['benchmark_trend'],
        applied_filters: {
          overlay_family: null,
          monitor_id: 'benchmark_trend_overlay_v1',
          review_support_status: null,
          lifecycle_status: null,
          latest_observation_status: null,
          latest_observation_observation_status: null,
          latest_observation_alert_classification: null,
          latest_observation_cause_code: null,
          latest_observation_recency: null,
          latest_evaluation_snapshot_status: 'absent',
          latest_evaluation_snapshot_cause_code: null,
          latest_evaluation_snapshot_recency: null,
        },
      },
    }

    expect(Object.keys(payload.items[0].metadata)).toEqual([
      'metadata_truth',
      'row_provenance',
      'status',
    ])
    expect(payload.items[0].metadata.status.lifecycle).toEqual({
      overlay_family: 'benchmark_trend',
      review_support_status: 'review_supported',
      lifecycle_status: 'enabled',
    })
    expect(payload.items[0].metadata.status.latest_evaluation_snapshot_status).toBe('absent')
    expect(payload.items[0].metadata.status.latest_observation_status).toBe('absent')
    expect(payload.items[0].metadata.status.latest_observation).toBeNull()
    expect(payload.items[0].metadata.status.latest_evaluation_snapshot).toBeNull()
    expect(payload.metadata).toEqual({
      contract_version: 'monitor_definition_discovery_v1',
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      row_provenance: 'persisted_monitor_definition_artifact',
      supported_monitor_ids: ['benchmark_trend_overlay_v1'],
      supported_overlay_families: ['benchmark_trend'],
      applied_filters: {
        overlay_family: null,
        monitor_id: 'benchmark_trend_overlay_v1',
        review_support_status: null,
        lifecycle_status: null,
        latest_observation_status: null,
        latest_observation_observation_status: null,
        latest_observation_alert_classification: null,
        latest_observation_cause_code: null,
        latest_observation_recency: null,
        latest_evaluation_snapshot_status: 'absent',
        latest_evaluation_snapshot_cause_code: null,
        latest_evaluation_snapshot_recency: null,
      },
    })
  })

  it('renders top-line regime, component states, explanation drivers, and recent context', () => {
    const result = createDiagnosticsFixture()

    render(<TrendRiskOverlaysPanel result={result} />)

    expect(screen.getByTestId('trend-risk-overlays-panel')).toBeTruthy()
    expect(screen.getByText('Overlay analysis')).toBeTruthy()
    expect(screen.getByText('Top-Line Regime')).toBeTruthy()
    expect(screen.getByText('Component Status')).toBeTruthy()
    expect(screen.getByText('Explanation Drivers')).toBeTruthy()
    expect(screen.getByText('Recent Context')).toBeTruthy()
    expect(screen.getByText('Metadata & Caveats')).toBeTruthy()
    expect(screen.getByText('Status Live')).toBeTruthy()
    expect(screen.getByText('Synthetic snapshot-history')).toBeTruthy()
    expect(screen.getAllByText('Regime normal').length).toBeGreaterThan(0)
  })

  it('shows explicit unavailable state messaging when historical diagnostics are missing', () => {
    const result = {
      ...createDiagnosticsFixture(),
      availability: {
        historical_sections_available: false,
        history_context_required: true,
        note: 'Overlay analysis requires imported history context.',
        status: 'unavailable' as const,
      },
    }

    render(<TrendRiskOverlaysPanel result={result} />)

    expect(screen.getByText('Status Unavailable')).toBeTruthy()
    expect(screen.getByText('Overlay analysis requires imported history context.')).toBeTruthy()
    expect(screen.getByText('Recent overlay history is unavailable.')).toBeTruthy()
  })

  it('shows waiting state without diagnostics input', () => {
    render(<TrendRiskOverlaysPanel result={null} />)

    expect(screen.getByText('Overlay diagnostics are waiting for a portfolio.')).toBeTruthy()
    expect(screen.getByText('Import a portfolio from the Dashboard to inspect trend and risk overlays.')).toBeTruthy()
  })
})
