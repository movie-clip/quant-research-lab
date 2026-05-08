import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture, createFf2026DiagnosticsEngineFixture, createFf2026ExposureEngineFixture, createIb2026DiagnosticsEngineFixture, createIb2026ExposureEngineFixture, createImportedBootstrapResponseFixture, createImportedDashboardHistoryFixture } from '../test/portfolioFixtures'
import {
  ff2026DashboardGolden,
  ff2026ImportedDashboardGoldenFixture,
  ib2026DashboardGolden,
  ib2026ImportedDashboardGoldenFixture,
} from '../test/dashboardGoldens'
import { App, assertMonitorDefinitionActiveAlertEpisodeInboxResponse, assertMonitorDefinitionAlertEpisodeHistoryResponse, loadMonitorDefinitionAlertReviewTimeline, loadMonitorDefinitionRecoveredAlertReviewQueue, openAlertHistoryReviewFromTimelineRow, openLatestObservationFromTimelineRow, reopenRecoveredAlertReviewRow } from './App'
import * as portfolioWorkspaceStorage from './portfolioWorkspaceStorage'
import { mapImportedHistoryContextToWorkspace } from '../features/portfolio/importedBootstrapMapper'
import type { ConstructionArtifactReplayValidationResponse, EtfRankingArtifactRecentRow, HypotheticalReplayResponse, ImportedSnapshot, OptimizerHandoffReplayResponse, OptimizerHandoffValidationResponse, OptimizerPersistedArtifactReference, PortfolioAllocationBacktestResponse, PortfolioOverview } from '../features/portfolio/types'
import type { MonitorDefinitionAlertReviewTimelineResponse } from '../features/portfolio/types'
import type { ImportedHistoryContext, ImportedNodeSource, PortfolioNode, PortfolioSnapshot, PortfolioWorkspace, ReplacementIntentDraftArtifact, ReviewSnapshotArtifact, SavedProposalReviewSnapshotPMSummaryMirror, VersionedProposalArtifact, WorkingDraft, WorkspaceState } from '../features/portfolio/workspaceTypes'

const dashboardPerformanceChartMock = vi.hoisted(() => ({
  shouldSuspend: false,
  suspensePromise: new Promise<never>(() => {}),
}))

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: vi.fn(),
}))

vi.mock('@tauri-apps/plugin-fs', () => ({
  readFile: vi.fn(),
}))

vi.mock('../features/portfolio/DashboardPerformanceChart', () => ({
  DashboardPerformanceChart: () => {
    if (dashboardPerformanceChartMock.shouldSuspend) {
      throw dashboardPerformanceChartMock.suspensePromise
    }
    return null
  },
}))

async function importTauriPlugins() {
  const [{ open }, { readFile }] = await Promise.all([
    import('@tauri-apps/plugin-dialog'),
    import('@tauri-apps/plugin-fs'),
  ])

  return {
    open: vi.mocked(open),
    readFile: vi.mocked(readFile),
  }
}

function installTauriRuntime() {
  Object.defineProperty(window, '__TAURI_INTERNALS__', {
    value: {},
    configurable: true,
  })
}

const exposurePayload = createExposureEngineFixture()
const diagnosticsPayload = createDiagnosticsEngineFixture()
const bootstrapPayload = createImportedBootstrapResponseFixture()
const dashboardHistoryPayload = createImportedDashboardHistoryFixture()

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function requestUrl(input: RequestInfo | URL) {
  const rawUrl = typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.toString()
      : input.url
  return new URL(rawUrl, 'http://localhost')
}

function requestPathname(input: RequestInfo | URL) {
  return requestUrl(input).pathname
}

function requestSearchParam(input: RequestInfo | URL, key: string) {
  return requestUrl(input).searchParams.get(key)
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit) {
  if (init?.method) return init.method.toUpperCase()
  if (typeof input !== 'string' && !(input instanceof URL) && input.method) return input.method.toUpperCase()
  return 'GET'
}

function requestJsonBody(init?: RequestInit) {
  return JSON.parse(typeof init?.body === 'string' ? init.body : String(init?.body ?? '{}'))
}

function matchingFetchCalls(fetchMock: { mock: { calls: ReadonlyArray<ReadonlyArray<unknown>> } }, pathname: string, method?: string) {
  return fetchMock.mock.calls.filter((call) => {
    const input = call[0] as RequestInfo | URL
    const init = call[1] as RequestInit | undefined
    return requestPathname(input) === pathname
      && (method == null || requestMethod(input, init) === method.toUpperCase())
  }) as Array<[RequestInfo | URL, RequestInit | undefined]>
}

function installFetchMock(handler: (input: RequestInfo | URL, init?: RequestInit) => Response | Promise<Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    try {
      return await handler(input, init)
    } catch (error) {
      if (
        requestPathname(input) === '/api/strategy-lab/ranking-artifacts/recent'
        && requestMethod(input, init) === 'GET'
        && requestSearchParam(input, 'artifact_kind') === 'intent_bound_etf_replacement_ranking'
      ) {
        return jsonResponse(makeReplacementRankingRecentDiscoveryPayload())
      }
      if (requestPathname(input) === '/api/construction/policies' && requestMethod(input, init) === 'GET') {
        return jsonResponse(makeConstructionPoliciesResponse())
      }
      if (requestPathname(input) === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && requestMethod(input, init) === 'GET') {
        return jsonResponse({ items: [], metadata: { contract_version: 'monitor_definition_recovered_alert_review_queue_v1', provenance: 'persisted_latest_observation_with_latest_snapshot_and_prior_alert_history_lineage', row_provenance: 'persisted_monitor_definition_observation_artifact_with_latest_snapshot_and_prior_alert_history_lineage', ordering: 'newest_first_evaluated_at_then_monitor_definition_id_then_observation_id', returned_limit: 20, total_queue_rows: 0 } })
      }
      throw error
    }
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function reopenDetailedReviewIfNeeded() {
  await waitFor(() => {
    expect(
      screen.queryByRole('heading', { name: 'Portfolio Research Workspace' })
      ?? screen.queryByRole('button', { name: 'Workspace' })
      ?? screen.queryByRole('button', { name: 'Open detailed review' })
      ?? screen.queryByText('Detailed review')
      ?? screen.queryByText('Detailed review unavailable here'),
    ).toBeTruthy()
  })

  if (
    screen.queryByRole('heading', { name: 'Portfolio Research Workspace' })
    || screen.queryByRole('button', { name: 'Workspace' })?.getAttribute('aria-current') === 'page'
  ) {
    return
  }

  const button = screen.queryByRole('button', { name: 'Open detailed review' })
  if (button) {
    fireEvent.click(button)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page'))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
  }
}

async function expandSupportLayer() {
  await waitFor(() => expect(screen.getByRole('button', { name: /support layer/i })).toBeTruthy())

  const toggle = screen.getByRole('button', { name: /support layer/i })
  if (toggle.getAttribute('aria-expanded') !== 'true') {
    fireEvent.click(toggle)
  }

  await waitFor(() => expect(screen.getByRole('button', { name: /support layer/i }).getAttribute('aria-expanded')).toBe('true'))
}

async function expandDraftToolLayer() {
  await waitFor(() => expect(screen.getByRole('button', { name: /draft\/tool layer/i })).toBeTruthy())

  const toggle = screen.getByRole('button', { name: /draft\/tool layer/i })
  if (toggle.getAttribute('aria-expanded') !== 'true') {
    fireEvent.click(toggle)
  }

  await waitFor(() => expect(screen.getByRole('button', { name: /draft\/tool layer/i }).getAttribute('aria-expanded')).toBe('true'))
}

function makeLatestObservationInboxPayload(overrides: Record<string, unknown> = {}) {
  const row = {
    monitor_definition_id: 'monitor_definition_abc12345def67890',
    monitor_definition_fingerprint: 'f'.repeat(64),
    monitor_definition_schema_version: 'monitor_definition_artifact_v1',
    observation_id: 'monitor_definition_observation_abc12345',
    monitor_id: 'benchmark_trend_overlay_v1',
    benchmark_symbol: 'SPY',
    review_scope: 'current_portfolio_truth_only',
    evaluation_mode: 'review_only_observation_evaluation',
    evaluated_at: '2026-04-21T09:30:00Z',
    observation_status: 'threshold_breach',
    cause_code: null,
    alert_classification: 'action_required',
    hysteresis_transition: 'open',
    recency_status: 'recent',
    reason: 'current portfolio truth breaches canonical overlay thresholds',
    open_handoff: {
      handoff_kind: 'monitor_definition_observation_open_handoff_v1',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      observation_id: 'monitor_definition_observation_abc12345',
      monitor_id: 'benchmark_trend_overlay_v1',
      benchmark_symbol: 'SPY',
    },
    metadata: {
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      row_provenance: 'persisted_monitor_definition_observation_artifact',
    },
  }
  return {
    items: [row],
    metadata: {
      contract_version: 'monitor_definition_latest_observation_alert_inbox_v1',
      provenance: 'authoritative_persisted_monitor_definition_observations_only',
      row_provenance: 'persisted_monitor_definition_observation_artifact',
      source_precedence: 'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry',
      ordering: 'newest_first_evaluated_at',
      returned_limit: 20,
    },
    ...overrides,
  }
}

function makeAlertHistoryQueuePayload(overrides: Record<string, unknown> = {}) {
  const row = {
    monitor_definition_id: 'monitor_definition_abc12345def67890',
    monitor_definition_fingerprint: 'f'.repeat(64),
    monitor_definition_schema_version: 'monitor_definition_artifact_v1',
    history_entry_id: 'monitor_definition_history_entry_abc12345',
    monitor_id: 'benchmark_trend_overlay_v1',
    benchmark_symbol: 'SPY',
    review_scope: 'current_portfolio_truth_only',
    evaluation_mode: 'review_only_observation_evaluation',
    evaluated_at: '2026-04-21T09:30:00Z',
    outcome_status: 'threshold_breach',
    cause_code: null,
    significance_status: 'action_required',
    hysteresis_transition: 'open',
    review_support_status: 'review_supported',
    latest_for_monitor_definition: true,
    reason: 'current portfolio truth breaches canonical overlay thresholds',
    review_handoff: {
      handoff_kind: 'monitor_definition_evaluation_history_review_handoff_v1',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      history_entry_id: 'monitor_definition_history_entry_abc12345',
      monitor_id: 'benchmark_trend_overlay_v1',
      benchmark_symbol: 'SPY',
    },
    metadata: {
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      row_provenance: 'persisted_monitor_definition_evaluation_history_entry_with_latest_snapshot_precedence',
    },
  }
  return {
    items: [row],
    metadata: {
      contract_version: 'monitor_definition_alert_history_queue_v1',
      provenance: 'persisted_monitor_definitions_with_canonical_latest_snapshot_and_evaluation_history',
      row_provenance: 'persisted_monitor_definition_evaluation_history_entry_with_latest_snapshot_precedence',
      source_precedence: 'persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries',
      ordering: 'newest_first_evaluated_at_then_latest_snapshot_precedence_then_monitor_definition_id_then_history_entry_id',
      returned_limit: 20,
      total_queue_rows: 1,
    },
    ...overrides,
  }
}

function makeAlertReviewTimelinePayload(overrides: Record<string, unknown> = {}) {
  return {
    items: [
      {
        ...makeLatestObservationInboxPayload().items[0],
        event_kind: 'latest_observation_event' as const,
        event_semantics: 'observation_rooted' as const,
        thresholds: makeObservationOpenPayload().thresholds,
        benchmark_observation: makeObservationOpenPayload().benchmark_observation,
        portfolio_observation: makeObservationOpenPayload().portfolio_observation,
        active_observation: makeObservationOpenPayload().active_observation,
        metadata: {
          metadata_truth: 'authoritative_persisted_artifact_metadata',
          row_provenance: 'persisted_monitor_definition_observation_artifact',
        },
      },
      {
        ...makeAlertHistoryQueuePayload().items[0],
        event_kind: 'evaluation_history_event' as const,
        event_semantics: 'history_entry_rooted' as const,
        thresholds: makeEvaluationHistoryEntryPayload().item.thresholds,
        benchmark_observation: makeEvaluationHistoryEntryPayload().item.benchmark_observation,
        portfolio_observation: makeEvaluationHistoryEntryPayload().item.portfolio_observation,
        active_observation: makeEvaluationHistoryEntryPayload().item.active_observation,
        metadata: {
          metadata_truth: 'authoritative_persisted_artifact_metadata',
          row_provenance: 'persisted_monitor_definition_evaluation_history_entry',
        },
      },
    ],
    metadata: {
      contract_version: 'monitor_definition_alert_review_timeline_v1',
      provenance: 'canonical_latest_observation_artifact_and_append_only_evaluation_history_entries',
      ordering: 'newest_first_evaluated_at_then_observation_event_then_history_entry_id',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      monitor_definition_fingerprint: 'f'.repeat(64),
      monitor_definition_schema_version: 'monitor_definition_artifact_v1',
      observation_row_provenance: 'persisted_monitor_definition_observation_artifact',
      history_row_provenance: 'persisted_monitor_definition_evaluation_history_entry',
      source_precedence: 'persisted_observation_artifact_then_persisted_evaluation_history_entries_then_persisted_latest_alert_episode_projection',
      latest_alert_episode: {
        contract_version: 'monitor_definition_alert_episode_v1',
        monitor_definition_id: 'monitor_definition_abc12345def67890',
        episode_id: 'monitor_definition_alert_episode_abc12345def67890',
        episode_status: 'active',
        started_at: '2026-04-21T09:30:00Z',
        ended_at: null,
        hysteresis_transition: 'open',
        source_precedence: 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation',
        latest_contributing_observation: {
          observation_id: 'monitor_definition_observation_abc12345',
          evaluated_at: '2026-04-21T09:30:00Z',
          observation_status: 'threshold_breach',
          cause_code: null,
          alert_classification: 'action_required',
        },
        recovery_basis: null,
      },
      total_rows: 2,
      observation_rows: 1,
      history_rows: 1,
    },
    ...overrides,
  } as MonitorDefinitionAlertReviewTimelineResponse
}

function makeRecoveredAlertReviewQueuePayload(overrides: Record<string, unknown> = {}) {
  const row = {
    monitor_definition_id: 'monitor_definition_abc12345def67890',
    monitor_definition_fingerprint: 'f'.repeat(64),
    monitor_definition_schema_version: 'monitor_definition_artifact_v1',
    observation_id: 'monitor_definition_observation_abc12345',
    latest_history_entry_id: 'monitor_definition_history_entry_latest_info',
    monitor_id: 'benchmark_trend_overlay_v1',
    benchmark_symbol: 'SPY',
    review_scope: 'current_portfolio_truth_only',
    evaluation_mode: 'review_only_observation_evaluation',
    evaluated_at: '2026-04-21T09:30:00Z',
    observation_status: 'ok',
    cause_code: null,
    alert_classification: 'informational',
    hysteresis_transition: 'recover',
    recency_status: 'recent',
    reason: 'latest persisted observation recovered to informational state',
    alert_episode: {
      contract_version: 'monitor_definition_alert_episode_v1',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      episode_id: 'monitor_definition_alert_episode_abc12345def67890',
      episode_status: 'recovered',
      started_at: '2026-04-20T09:30:00Z',
      ended_at: '2026-04-21T09:30:00Z',
      hysteresis_transition: 'recover',
      source_precedence: 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation',
      latest_contributing_observation: {
        observation_id: 'monitor_definition_observation_abc12345',
        evaluated_at: '2026-04-21T09:30:00Z',
        observation_status: 'ok',
        cause_code: null,
        alert_classification: 'informational',
      },
      recovery_basis: {
        recovered_from_history_entry_id: 'monitor_definition_history_entry_alert',
        recovered_from_evaluated_at: '2026-04-20T09:30:00Z',
        recovered_from_outcome_status: 'threshold_breach',
        recovered_from_cause_code: null,
        recovered_from_significance_status: 'action_required',
      },
    },
    recovered_from: {
      history_entry_id: 'monitor_definition_history_entry_alert',
      evaluated_at: '2026-04-20T09:30:00Z',
      outcome_status: 'threshold_breach',
      cause_code: null,
      significance_status: 'action_required',
      reason: 'prior persisted alert state',
    },
    timeline_handoff: {
      handoff_kind: 'monitor_definition_alert_review_timeline_open_handoff_v1',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      selected_event_kind: 'latest_observation_event',
      observation_id: 'monitor_definition_observation_abc12345',
      monitor_id: 'benchmark_trend_overlay_v1',
      benchmark_symbol: 'SPY',
    },
    metadata: {
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      row_provenance: 'persisted_monitor_definition_observation_artifact_with_latest_snapshot_and_prior_alert_history_lineage',
    },
  }
  return {
    items: [row],
    metadata: {
      contract_version: 'monitor_definition_recovered_alert_review_queue_v1',
      provenance: 'persisted_latest_observation_with_latest_snapshot_and_prior_alert_history_lineage',
      row_provenance: 'persisted_monitor_definition_observation_artifact_with_latest_snapshot_and_prior_alert_history_lineage',
      source_precedence: 'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries',
      ordering: 'newest_first_evaluated_at_then_monitor_definition_id_then_observation_id',
      returned_limit: 20,
      total_queue_rows: 1,
    },
    ...overrides,
  }
}

function makeAlertEpisodeHistoryPayload(overrides: Record<string, unknown> = {}) {
  return {
    items: [
      {
        schema_version: 'monitor_definition_alert_episode_record_v1',
        episode_id: 'monitor_definition_alert_episode_latest',
        monitor_definition_id: 'monitor_definition_abc12345def67890',
        monitor_definition_fingerprint: 'f'.repeat(64),
        monitor_definition_schema_version: 'monitor_definition_artifact_v1',
        monitor_id: 'benchmark_trend_overlay_v1',
        benchmark_symbol: 'SPY',
        lifecycle_status: 'recovered',
        latest_for_monitor_definition: true,
        started_at: '2026-04-20T09:30:00Z',
        ended_at: '2026-04-21T09:30:00Z',
        latest_event_at: '2026-04-21T09:30:00Z',
        hysteresis_transition: 'recover',
        source_precedence: 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation',
        latest_contributing_observation: {
          observation_id: 'monitor_definition_observation_abc12345',
          evaluated_at: '2026-04-21T09:30:00Z',
          observation_status: 'ok',
          cause_code: null,
          alert_classification: 'informational',
        },
        recovery_basis: {
          recovered_from_history_entry_id: 'monitor_definition_history_entry_abc12345',
          recovered_from_evaluated_at: '2026-04-20T09:30:00Z',
          recovered_from_outcome_status: 'threshold_breach',
          recovered_from_cause_code: null,
          recovered_from_significance_status: 'action_required',
        },
        terminal_history_entry_id: 'monitor_definition_history_entry_latest_info',
        timeline_handoff: {
          handoff_kind: 'monitor_definition_alert_episode_history_timeline_handoff_v1',
          monitor_definition_id: 'monitor_definition_abc12345def67890',
          selected_event_kind: 'latest_observation_event',
          observation_id: 'monitor_definition_observation_abc12345',
          history_entry_id: null,
          monitor_id: 'benchmark_trend_overlay_v1',
          benchmark_symbol: 'SPY',
        },
        metadata: {
          history_truth: 'authoritative_persisted_monitor_definition_alert_episode_history',
          row_provenance: 'persisted_monitor_definition_alert_episode_record',
        },
      },
      {
        schema_version: 'monitor_definition_alert_episode_record_v1',
        episode_id: 'monitor_definition_alert_episode_closed',
        monitor_definition_id: 'monitor_definition_abc12345def67890',
        monitor_definition_fingerprint: 'f'.repeat(64),
        monitor_definition_schema_version: 'monitor_definition_artifact_v1',
        monitor_id: 'benchmark_trend_overlay_v1',
        benchmark_symbol: 'SPY',
        lifecycle_status: 'closed',
        latest_for_monitor_definition: false,
        started_at: '2026-04-18T09:30:00Z',
        ended_at: '2026-04-19T09:30:00Z',
        latest_event_at: '2026-04-19T09:30:00Z',
        hysteresis_transition: 'recover',
        source_precedence: 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation',
        latest_contributing_observation: {
          observation_id: 'monitor_definition_observation_closed',
          evaluated_at: '2026-04-19T09:30:00Z',
          observation_status: 'threshold_breach',
          cause_code: null,
          alert_classification: 'action_required',
        },
        recovery_basis: {
          recovered_from_history_entry_id: 'monitor_definition_history_entry_closed',
          recovered_from_evaluated_at: '2026-04-19T09:30:00Z',
          recovered_from_outcome_status: 'threshold_breach',
          recovered_from_cause_code: null,
          recovered_from_significance_status: 'action_required',
        },
        terminal_history_entry_id: 'monitor_definition_history_entry_closed',
        timeline_handoff: {
          handoff_kind: 'monitor_definition_alert_episode_history_timeline_handoff_v1',
          monitor_definition_id: 'monitor_definition_abc12345def67890',
          selected_event_kind: 'evaluation_history_event',
          observation_id: null,
          history_entry_id: 'monitor_definition_history_entry_closed',
          monitor_id: 'benchmark_trend_overlay_v1',
          benchmark_symbol: 'SPY',
        },
        metadata: {
          history_truth: 'authoritative_persisted_monitor_definition_alert_episode_history',
          row_provenance: 'persisted_monitor_definition_alert_episode_record',
        },
      },
    ],
    metadata: {
      contract_version: 'monitor_definition_alert_episode_history_v1',
      history_truth: 'authoritative_persisted_monitor_definition_alert_episode_history',
      row_provenance: 'persisted_monitor_definition_alert_episode_record',
      source_precedence: 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation',
      ordering: 'newest_first_latest_event_at_then_episode_id',
      windowing: 'before_episode_id_exclusive',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      monitor_definition_fingerprint: 'f'.repeat(64),
      monitor_definition_schema_version: 'monitor_definition_artifact_v1',
      returned_limit: 20,
      requested_before_episode_id: null,
      next_before_episode_id: null,
      total_episodes: 2,
    },
    ...overrides,
  }
}

function makeActiveAlertEpisodeInboxPayload(overrides: Record<string, unknown> = {}) {
  return {
    items: [
      {
        review_scope: 'current_portfolio_truth_only',
        evaluation_mode: 'review_only_observation_evaluation',
        alert_episode: {
          ...makeAlertEpisodeHistoryPayload().items[0],
          lifecycle_status: 'open',
          latest_for_monitor_definition: true,
          ended_at: null,
          recovery_basis: null,
          hysteresis_transition: 'remain_open',
          source_precedence: 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation',
          latest_contributing_observation: {
            observation_id: 'monitor_definition_observation_abc12345',
            evaluated_at: '2026-04-21T09:30:00Z',
            observation_status: 'threshold_breach',
            cause_code: null,
            alert_classification: 'action_required',
          },
          timeline_handoff: {
            handoff_kind: 'monitor_definition_alert_episode_history_timeline_handoff_v1',
            monitor_definition_id: 'monitor_definition_abc12345def67890',
            selected_event_kind: 'latest_observation_event',
            observation_id: 'monitor_definition_observation_abc12345',
            history_entry_id: null,
            monitor_id: 'benchmark_trend_overlay_v1',
            benchmark_symbol: 'SPY',
          },
        },
        metadata: {
          metadata_truth: 'authoritative_persisted_artifact_metadata',
          row_provenance: 'persisted_monitor_definition_alert_episode_record',
        },
      },
    ],
    metadata: {
      contract_version: 'monitor_definition_active_alert_episode_inbox_v1',
      provenance: 'authoritative_persisted_monitor_definition_alert_episode_records_only',
      row_provenance: 'persisted_monitor_definition_alert_episode_record',
      source_precedence: 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation',
      ordering: 'newest_first_latest_event_at_then_monitor_definition_id_then_episode_id',
      windowing: 'before_episode_id_exclusive',
      returned_limit: 20,
      requested_before_episode_id: null,
      next_before_episode_id: null,
      total_active_episodes: 1,
    },
    ...overrides,
  }
}

function makeEvaluationHistoryEntryPayload(overrides: Record<string, unknown> = {}) {
  return {
    item: {
      schema_version: 'monitor_definition_evaluation_history_entry_v1',
      history_entry_id: 'monitor_definition_history_entry_abc12345',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      monitor_definition_fingerprint: 'f'.repeat(64),
      monitor_definition_schema_version: 'monitor_definition_artifact_v1',
      monitor_id: 'benchmark_trend_overlay_v1',
      benchmark_symbol: 'SPY',
      evaluation_mode: 'review_only_observation_evaluation',
      evaluated_at: '2026-04-21T09:30:00Z',
      observation_status: 'threshold_breach',
      cause_code: null,
      significance_status: 'action_required',
      hysteresis_transition: 'open',
      source_precedence: 'persisted_evaluation_history_entry_only',
      reason: 'current portfolio truth breaches canonical overlay thresholds',
      thresholds: {
        minimum_confirmation_count: 2,
        risk_on_min_risky_weight: 0.95,
        risk_on_max_cash_weight: 0.05,
        risk_reduced_max_risky_weight: 0.35,
        risk_reduced_min_cash_weight: 0.65,
      },
      benchmark_observation: {
        overlay_id: 'benchmark_trend_overlay_v1',
        status: 'risk_reduced',
        as_of_month_end: '2024-12-31',
        benchmark_symbol: 'SPY',
        signal_basis: '10_month_sma_month_end',
        confirmation_count: 2,
        rule_version: 'v1',
        source_lineage: {
          source_kind: 'benchmark_overlay_signal',
          source_id: 'overlay-signal-2024-12-31',
          observed_at: '2025-01-02T09:30:00Z',
        },
      },
      portfolio_observation: {
        total_portfolio_value: 685,
        risky_value: 35,
        cash_value: 650,
        risky_weight: 0.05109489,
        cash_weight: 0.94890511,
        position_count: 2,
        source_lineage: {
          truth_basis: 'imported_portfolio_snapshot',
          importer: 'interactive_brokers',
          imported_at: '2024-04-15T09:30:00Z',
          statement_period: '2024-04',
          source_paths: ['IB2024.pdf'],
        },
      },
      active_observation: {
        required_overlay_status: 'risk_reduced',
        threshold_evaluation_performed: true,
        required_min_risky_weight: null,
        required_max_risky_weight: 0.35,
        required_min_cash_weight: 0.65,
        required_max_cash_weight: null,
        actual_risky_weight: 0.05109489,
        actual_cash_weight: 0.94890511,
        risky_weight_gap: -0.29890511,
        cash_weight_gap: 0.29890511,
        triggered_thresholds: [],
      },
      metadata: {
        history_truth: 'authoritative_persisted_monitor_definition_evaluation_history',
        row_provenance: 'persisted_monitor_definition_evaluation_history_entry',
      },
    },
    metadata: {
      contract_version: 'monitor_definition_evaluation_history_v1',
      history_truth: 'authoritative_persisted_monitor_definition_evaluation_history',
      row_provenance: 'persisted_monitor_definition_evaluation_history_entry',
      source_precedence: 'persisted_evaluation_history_entry_only',
      inspection_order: 'newest_first_evaluated_at',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      monitor_definition_fingerprint: 'f'.repeat(64),
      monitor_definition_schema_version: 'monitor_definition_artifact_v1',
      returned_limit: 20,
      total_entries: 1,
      retrieved_history_entry_id: 'monitor_definition_history_entry_abc12345',
    },
    ...overrides,
  }
}

function makeObservationOpenPayload(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 'monitor_definition_observation_artifact_v1',
    observation_id: 'monitor_definition_observation_abc12345',
    monitor_definition_id: 'monitor_definition_abc12345def67890',
    monitor_definition_fingerprint: 'f'.repeat(64),
    monitor_definition_schema_version: 'monitor_definition_artifact_v1',
    monitor_id: 'benchmark_trend_overlay_v1',
    benchmark_symbol: 'SPY',
    evaluation_mode: 'review_only_observation_evaluation',
    evaluated_at: '2026-04-21T09:30:00Z',
    observation_status: 'threshold_breach',
    cause_code: null,
    alert_classification: 'action_required',
    hysteresis_transition: 'open',
    source_precedence: 'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry',
    reason: 'current portfolio truth breaches canonical overlay thresholds',
    thresholds: {
      minimum_confirmation_count: 2,
      risk_on_min_risky_weight: 0.95,
      risk_on_max_cash_weight: 0.05,
      risk_reduced_max_risky_weight: 0.35,
      risk_reduced_min_cash_weight: 0.65,
    },
    benchmark_observation: {
      overlay_id: 'benchmark_trend_overlay_v1',
      status: 'risk_reduced',
      as_of_month_end: '2024-12-31',
      benchmark_symbol: 'SPY',
      signal_basis: '10_month_sma_month_end',
      confirmation_count: 2,
      rule_version: 'v1',
      source_lineage: {
        source_kind: 'benchmark_overlay_signal',
        source_id: 'overlay-signal-2024-12-31',
        observed_at: '2025-01-02T09:30:00Z',
      },
    },
    portfolio_observation: {
      total_portfolio_value: 685,
      risky_value: 35,
      cash_value: 650,
      risky_weight: 0.05109489,
      cash_weight: 0.94890511,
      position_count: 2,
      source_lineage: {
        truth_basis: 'imported_portfolio_snapshot',
        importer: 'interactive_brokers',
        imported_at: '2024-04-15T09:30:00Z',
        statement_period: '2024-04',
        source_paths: ['IB2024.pdf'],
      },
    },
    active_observation: {
      required_overlay_status: 'risk_reduced',
      threshold_evaluation_performed: true,
      required_min_risky_weight: null,
      required_max_risky_weight: 0.35,
      required_min_cash_weight: 0.65,
      required_max_cash_weight: null,
      actual_risky_weight: 0.05109489,
      actual_cash_weight: 0.94890511,
      risky_weight_gap: -0.29890511,
      cash_weight_gap: 0.29890511,
      triggered_thresholds: [],
    },
    ...overrides,
  }
}

function installWorkspaceReviewFetchMock(reviewSnapshotArtifact?: ReviewSnapshotArtifact) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const pathname = requestPathname(input)
    const method = requestMethod(input, init)
    if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
    if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
    if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
    if (reviewSnapshotArtifact && pathname === '/api/backtests/review-snapshots' && method === 'POST') return jsonResponse(reviewSnapshotArtifact)
    throw new Error(`Unhandled fetch: ${method} ${pathname}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function makeReviewSnapshotFamilyReviewResponse(anchorProposal: VersionedProposalArtifact, siblings: VersionedProposalArtifact[]) {
  return {
    review_kind: 'review_snapshot_family_review',
    family_key: {
      workspace_id: anchorProposal.workspaceId,
      source_draft_id: anchorProposal.sourceDraftId,
      source_base_node_id: anchorProposal.sourceBaseNodeId,
      proposal_family_id: anchorProposal.proposalFamilyId,
      source_kind: 'hypothetical_replacement_replay',
    },
    provenance: 'persisted_review_snapshot_artifacts_only',
    compare_selection_policy: 'exactly_two_distinct_family_siblings',
    anchor: {
      identity: {
        artifact_id: anchorProposal.reviewSnapshotArtifactId,
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        fingerprint: `fingerprint-${anchorProposal.versionNumber}`,
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      open_handoff: anchorProposal.proposalCapture.open_handoff,
      lineage: anchorProposal.proposalCapture.lineage,
      pm_summary: anchorProposal.reviewSnapshotPMSummary,
      comparison_eligibility: {
        eligible: siblings.length > 1,
        reason: siblings.length > 1 ? 'compatible_family_sibling_available' : 'no_compatible_family_sibling',
        compatible_sibling_artifact_ids: siblings
          .filter((proposal) => proposal.reviewSnapshotArtifactId !== anchorProposal.reviewSnapshotArtifactId)
          .map((proposal) => proposal.reviewSnapshotArtifactId),
      },
    },
    siblings: siblings.map((proposal) => ({
      identity: {
        artifact_id: proposal.reviewSnapshotArtifactId,
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        fingerprint: `fingerprint-${proposal.versionNumber}`,
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      open_handoff: proposal.proposalCapture.open_handoff,
      lineage: proposal.proposalCapture.lineage,
      pm_summary: proposal.reviewSnapshotPMSummary,
      comparison_eligibility: {
        eligible: siblings.length > 1,
        reason: siblings.length > 1 ? 'compatible_family_sibling_available' : 'no_compatible_family_sibling',
        compatible_sibling_artifact_ids: siblings
          .filter((item) => item.reviewSnapshotArtifactId !== proposal.reviewSnapshotArtifactId)
          .map((item) => item.reviewSnapshotArtifactId),
      },
    })),
  }
}

function makeReviewSnapshotFamilyInboxResponse(proposals: VersionedProposalArtifact[]) {
  const latestByFamily = new Map<string, VersionedProposalArtifact[]>()
  proposals.forEach((proposal) => {
    const current = latestByFamily.get(proposal.proposalFamilyId) ?? []
    latestByFamily.set(proposal.proposalFamilyId, [...current, proposal])
  })
  const rows = [...latestByFamily.values()]
    .map((familyProposals) => [...familyProposals].sort((left, right) => right.versionNumber - left.versionNumber || new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()))
    .sort((left, right) => new Date(right[0]!.createdAt).getTime() - new Date(left[0]!.createdAt).getTime())
    .map((familyProposals) => {
      const latest = familyProposals[0]!
      return {
        family_key: {
          workspace_id: latest.workspaceId,
          source_draft_id: latest.sourceDraftId,
          source_base_node_id: latest.sourceBaseNodeId,
          proposal_family_id: latest.proposalFamilyId,
          source_kind: 'hypothetical_replacement_replay',
        },
        latest_identity: {
          artifact_id: latest.reviewSnapshotArtifactId,
          artifact_kind: 'portfolio_review_snapshot',
          schema_version: 'review_snapshot_artifact_v1',
          fingerprint: `fingerprint-${latest.versionNumber}`,
          consumer_kind: 'saved_hypothetical_replay_proposal',
        },
        lineage: latest.proposalCapture.lineage,
        proposal_capture: latest.proposalCapture,
        pm_summary: latest.reviewSnapshotPMSummary,
        sibling_count: familyProposals.length,
        compare_readiness: {
          ready: familyProposals.length > 1,
          reason: familyProposals.length > 1 ? 'compatible_family_pair_available' : 'no_compatible_family_pair',
          compatible_pair_count: familyProposals.length > 1 ? 1 : 0,
        },
        latest_saved_at: latest.createdAt,
        latest_order_provenance: 'persisted_artifact_file_mtime',
      }
    })
  return {
    inbox_kind: 'review_snapshot_family_inbox',
    workspace_id: proposals[0]?.workspaceId ?? 'workspace-1',
    provenance: 'persisted_review_snapshot_artifacts_only',
    rows,
  }
}

function installSavedProposalWorkspaceFetchMock({
  familyInboxPayload,
  familyReviewPayloads,
  openPayloads = {},
}: {
  familyInboxPayload: unknown
  familyReviewPayloads: Record<string, unknown>
  openPayloads?: Record<string, unknown>
}) {
  return installFetchMock(async (input, init) => {
    const pathname = requestPathname(input)
    const method = requestMethod(input, init)
    if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
    if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
    if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
    if (pathname === '/api/backtests/review-snapshots/family-inbox' && method === 'POST') {
      return jsonResponse(familyInboxPayload)
    }
    if (pathname === '/api/backtests/review-snapshots/family-review' && method === 'POST') {
      const artifactId = requestJsonBody(init).handoff?.artifact_id
      const payload = artifactId ? familyReviewPayloads[artifactId] : undefined
      if (payload) return jsonResponse(payload)
    }
    if (pathname === '/api/backtests/review-snapshots/open' && method === 'POST') {
      const artifactId = requestJsonBody(init).artifact_id
      const payload = artifactId ? openPayloads[artifactId] : undefined
      if (payload) return jsonResponse(payload)
    }
    throw new Error(`Unhandled fetch: ${method} ${pathname}`)
  })
}

function cloneMutable<T>(value: unknown): T {
  return JSON.parse(JSON.stringify(value)) as T
}

const ib2026MutableSnapshot = cloneMutable<ImportedSnapshot>(ib2026ImportedDashboardGoldenFixture.snapshot)
const ff2026MutableSnapshot = cloneMutable<ImportedSnapshot>(ff2026ImportedDashboardGoldenFixture.snapshot)
const ib2026MutableOverview = cloneMutable<PortfolioOverview>(ib2026ImportedDashboardGoldenFixture.overview)
const ff2026MutableOverview = cloneMutable<PortfolioOverview>(ff2026ImportedDashboardGoldenFixture.overview)

const ib2026LoadedFiles = [...ib2026DashboardGolden.loadedFiles]
const ff2026LoadedFiles = [...ff2026DashboardGolden.loadedFiles]
const ib2026ImportedDailyStates = ib2026ImportedDashboardGoldenFixture.daily_states as Array<{ date: string }>
const ff2026ImportedDailyStates = ff2026ImportedDashboardGoldenFixture.daily_states as Array<{ date: string }>

const ib2026DashboardHistoryPayload = {
  performance_series: ib2026ImportedDashboardGoldenFixture.performance_series,
  daily_states: ib2026ImportedDashboardGoldenFixture.daily_states,
  source_status: ib2026ImportedDashboardGoldenFixture.source_status,
  benchmark: ib2026ImportedDashboardGoldenFixture.benchmark,
  range_metrics: ib2026ImportedDashboardGoldenFixture.range_metrics,
}
const ib2026ExposurePayload = createIb2026ExposureEngineFixture()
const ib2026DiagnosticsPayload = createIb2026DiagnosticsEngineFixture()
const ib2026BootstrapPayload = {
  snapshot: ib2026MutableSnapshot,
  overview: ib2026MutableOverview,
  risk_summary: ib2026ImportedDashboardGoldenFixture.risk_summary,
   history_context: {
     benchmark_symbol: 'SPY',
     statement_period: ib2026ImportedDashboardGoldenFixture.snapshot.statement.statement_period,
     imported_at: ib2026ImportedDashboardGoldenFixture.snapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
     importer: ib2026ImportedDashboardGoldenFixture.snapshot.statement.importer,
     source_file_names: ib2026LoadedFiles,
      history_start_date: ib2026ImportedDailyStates[0]?.date ?? null,
      history_end_date: ib2026ImportedDailyStates[ib2026ImportedDailyStates.length - 1]?.date ?? null,
   },
}
const ff2026DashboardHistoryPayload = {
  performance_series: ff2026ImportedDashboardGoldenFixture.performance_series,
  daily_states: ff2026ImportedDashboardGoldenFixture.daily_states,
  source_status: ff2026ImportedDashboardGoldenFixture.source_status,
  benchmark: ff2026ImportedDashboardGoldenFixture.benchmark,
  range_metrics: ff2026ImportedDashboardGoldenFixture.range_metrics,
}
const ff2026ExposurePayload = createFf2026ExposureEngineFixture()
const ff2026DiagnosticsPayload = createFf2026DiagnosticsEngineFixture()
const ff2026BootstrapPayload = {
  snapshot: ff2026MutableSnapshot,
  overview: ff2026MutableOverview,
  risk_summary: ff2026ImportedDashboardGoldenFixture.risk_summary,
   history_context: {
     benchmark_symbol: 'SPY',
     statement_period: ff2026ImportedDashboardGoldenFixture.snapshot.statement.statement_period,
     imported_at: ff2026ImportedDashboardGoldenFixture.snapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
     importer: ff2026ImportedDashboardGoldenFixture.snapshot.statement.importer,
     source_file_names: ff2026LoadedFiles,
      history_start_date: ff2026ImportedDailyStates[0]?.date ?? null,
      history_end_date: ff2026ImportedDailyStates[ff2026ImportedDailyStates.length - 1]?.date ?? null,
   },
}
const appendedExposurePayload = {
  ...exposurePayload,
  snapshot: {
    ...exposurePayload.snapshot,
    statement: {
      ...exposurePayload.snapshot.statement,
      statement_period: '2025-01-01 - 2026-04-08',
    },
    statements: [
      ...exposurePayload.snapshot.statements,
      {
        ...exposurePayload.snapshot.statements[0],
        statement_period: '2026-01-01 - 2026-04-08',
        source_path: 'C:\\docs\\IB2026.pdf',
        imported_at: '2026-04-10T00:05:00Z',
        page_count: 17,
      },
    ],
  },
}
const appendedDiagnosticsPayload = {
  ...diagnosticsPayload,
  snapshot: {
    ...diagnosticsPayload.snapshot,
    statement: {
      ...diagnosticsPayload.snapshot.statement,
      statement_period: '2025-01-01 - 2026-04-08',
    },
    statements: [
      ...diagnosticsPayload.snapshot.statements,
      {
        ...diagnosticsPayload.snapshot.statements[0],
        statement_period: '2026-01-01 - 2026-04-08',
        source_path: 'C:\\docs\\IB2026.pdf',
        imported_at: '2026-04-10T00:05:00Z',
        page_count: 17,
      },
    ],
  },
}

const allocationBacktestPayload: PortfolioAllocationBacktestResponse = {
  methodology: 'm',
  methodology_provenance: {
    provenance_version: 1,
    source: 'portfolio_allocation_backtest_engine',
    methodology_truth: 'review_only_replay_methodology',
    assumptions_truth: 'review_only_replay_assumptions',
    analytics_truth: 'hypothetical_replay_analytics_only',
    review_scope: 'workspace_review_context_only',
  },
  investor_economics_status: { status: 'available', reason: null },
  reference_result: {
    portfolio_name: 'Reference',
    benchmark_symbol: 'SPY',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    observation_count: 2,
    rebalance_frequency: 'monthly',
    commission_bps: 0,
    slippage_bps: 0,
    drift_tolerance_pct: null,
    assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
    status: 'ok',
    investor_economics_status: { status: 'available', reason: null },
    instrument_metadata: [],
    starting_weights: [],
    ending_weights: [],
    metrics: { total_return_pct: 0.5, annualized_return_pct: 0.5, annualized_volatility_pct: 10, downside_volatility_pct: 6, max_drawdown_pct: -4, sharpe_ratio: 0.4, sortino_ratio: 0.7, benchmark_return_pct: 1, excess_return_pct: -0.5, tracking_error_pct: 3, information_ratio: -0.1, beta_vs_benchmark: 1, correlation_vs_benchmark: 0.9, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
    equity_curve: [{ date: '2024-01-02', equity: 100000, cash: 0, gross_exposure: 100000, drawdown_pct: 0 }, { date: '2024-12-31', equity: 100500, cash: 0, gross_exposure: 100500, drawdown_pct: -4 }],
    rebalance_events: [],
    trades: [],
  },
  candidate_result: {
    portfolio_name: 'Candidate',
    benchmark_symbol: 'SPY',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    observation_count: 2,
    rebalance_frequency: 'monthly',
    commission_bps: 0,
    slippage_bps: 0,
    drift_tolerance_pct: null,
    assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
    status: 'ok',
    investor_economics_status: { status: 'available', reason: null },
    instrument_metadata: [],
    starting_weights: [],
    ending_weights: [],
    metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
    equity_curve: [{ date: '2024-01-02', equity: 100000, cash: 0, gross_exposure: 100000, drawdown_pct: 0 }, { date: '2024-12-31', equity: 101000, cash: 0, gross_exposure: 101000, drawdown_pct: -1 }],
    rebalance_events: [],
    trades: [],
  },
  comparison: { total_return_diff_pct: 0.5, annualized_return_diff_pct: 0.5, benchmark_return_diff_pct: 0, annualized_volatility_diff_pct: -1, downside_volatility_diff_pct: -1, max_drawdown_diff_pct: 1, sharpe_diff: 0.6, sortino_diff: 0.3, excess_return_diff_pct: 0.5, tracking_error_diff_pct: 1, information_ratio_diff: 0.1, beta_diff: -0.2, correlation_diff: -0.05, total_turnover_diff_pct: 0, total_cost_diff: 0 },
  reference_diagnostics: {
    provenance: { snapshot_basis: 'synthetic_replay_snapshot', historical_basis: 'market_data_history', note: 'Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.' },
    factor_snapshot: [{ key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 1, target_exposure: null, primary_mapping: null, alternative_mappings: [], ucits_examples: [], mapping_quality: 'high', description: 'broad market' }],
    volatility_snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: 10, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: 6, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: 3, current_drawdown_pct: -2, max_drawdown_pct: -4, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null },
    risk_contribution: null,
    stress_scenarios: [],
  },
  candidate_diagnostics: {
    provenance: { snapshot_basis: 'synthetic_replay_snapshot', historical_basis: 'market_data_history', note: 'Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.' },
    factor_snapshot: [{ key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 0.8, target_exposure: null, primary_mapping: null, alternative_mappings: [], ucits_examples: [], mapping_quality: 'high', description: 'broad market' }],
    volatility_snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: 9, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: 5, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: 4, current_drawdown_pct: -1.5, max_drawdown_pct: -3, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null },
    risk_contribution: null,
    stress_scenarios: [],
  },
  diagnostics_comparison: {
    factor_exposure_changes: [{ key: 'market', label: 'Market', baseline_value: 1, candidate_value: 0.8, delta_value: -0.2 }],
    top_factor_exposure_change: { key: 'market', label: 'Market', baseline_value: 1, candidate_value: 0.8, delta_value: -0.2, selection_rule: 'largest_absolute_delta', rationale: 'Largest valid factor exposure delta in this group (candidate - baseline).' },
    volatility_changes: [{ key: 'annualized_volatility', label: 'Annualized Volatility', baseline_value: 10, candidate_value: 9, delta_value: -1 }],
    top_volatility_change: { key: 'annualized_volatility', label: 'Annualized Volatility', baseline_value: 10, candidate_value: 9, delta_value: -1, selection_rule: 'fixed_priority', rationale: 'Selected by fixed priority order: max drawdown, then annualized volatility, then downside volatility.' },
    risk_contribution_changes: [],
    top_risk_contribution_change: null,
    concentration_changes: [{ key: 'factor_hhi', label: 'Factor HHI', baseline_value: 0.36, candidate_value: 0.2, delta_value: -0.16 }],
    top_concentration_change: { key: 'factor_hhi', label: 'Factor HHI', baseline_value: 0.36, candidate_value: 0.2, delta_value: -0.16, selection_rule: 'fixed_priority', rationale: 'Selected by fixed priority order: factor HHI, then top 1 position risk share.' },
    stress_scenario_changes: [],
    top_stress_scenario_change: null,
  },
}

const persistedSnapshot: PortfolioSnapshot = {
  snapshotVersion: 1,
  baseCurrency: 'USD',
  importedMeta: {
    importer: 'interactive_brokers',
    statementPeriod: '2025-01-01 - 2025-12-31',
    importedAt: '2026-04-10T00:00:00Z',
    sourceFileNames: ['IB2025.pdf'],
  },
  positions: [{ symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
  cashBalances: [{ currency: 'USD', amount: 1000 }],
  metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
}

const variantSnapshot: PortfolioSnapshot = {
  ...persistedSnapshot,
  importedMeta: {
    ...persistedSnapshot.importedMeta,
    statementPeriod: '2026-01-01 - 2026-04-10',
    sourceFileNames: ['IB2025.pdf', 'IB2026.pdf'],
  },
  positions: [{ symbol: 'AAPL', marketValue: 15000, quantity: 15, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
  cashBalances: [{ currency: 'USD', amount: 500 }],
}

const variantExposurePayload = {
  ...exposurePayload,
  snapshot: {
    ...exposurePayload.snapshot,
    statement: {
      ...exposurePayload.snapshot.statement,
      statement_period: '2026-01-01 - 2026-04-10',
    },
    statement_totals: {
      ...exposurePayload.snapshot.statement_totals,
      ending_nav: 15500,
      starting_nav: 14000,
    },
    positions: [{ symbol: 'AAPL', quantity: 15, market_value: 15000, currency: 'USD', as_of_date: '2026-04-10' }],
    cash_balances: [{ currency: 'USD', ending_cash: 500 }],
  },
  overview: {
    ...exposurePayload.overview,
    total_market_value: 15500,
  },
}

const variantDashboardHistoryPayload = {
  ...dashboardHistoryPayload,
  daily_states: [
    { ...dashboardHistoryPayload.daily_states[0], total_portfolio_value: 14000, external_cash_flow: 0 },
    { ...dashboardHistoryPayload.daily_states[dashboardHistoryPayload.daily_states.length - 1], total_portfolio_value: 15500, external_cash_flow: 0 },
  ],
  performance_series: [
    { ...dashboardHistoryPayload.performance_series[0], portfolio_value: 14000, benchmark_price: 100, portfolio_return_pct: 0, benchmark_return_pct: 0 },
    { ...dashboardHistoryPayload.performance_series[dashboardHistoryPayload.performance_series.length - 1], portfolio_value: 15500, benchmark_price: 105, portfolio_return_pct: 10.71, benchmark_return_pct: 5 },
  ],
}

function buildHistorySource(historyContext: ImportedHistoryContext | null, importedHistorySnapshot: ImportedSnapshot | null) {
  if (importedHistorySnapshot) {
    return {
      kind: 'imported_replay' as const,
      historyContext,
      importedHistorySnapshot,
    }
  }
  if (historyContext) {
    return {
      kind: 'history_context' as const,
      historyContext,
      importedHistorySnapshot: null,
    }
  }
  return {
    kind: 'none' as const,
    historyContext: null,
    importedHistorySnapshot: null,
  }
}

function buildImportedSource(input: {
  importedFileNames: string[]
  importedAt: string
  importer: ImportedNodeSource['importer']
  baseCurrency: string | null
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
}): ImportedNodeSource {
  return {
    importedFileNames: input.importedFileNames,
    importedAt: input.importedAt,
    importer: input.importer,
    baseCurrency: input.baseCurrency,
    historySource: buildHistorySource(input.historyContext ?? null, input.importedHistorySnapshot ?? null),
  }
}

function buildArtifactReviewSource(constructionArtifactId: string, openedAt: string) {
  return {
    kind: 'persisted_construction_artifact' as const,
    constructionArtifactId,
    openedAt,
    reviewBasis: {
      basisVersion: 1 as const,
      basisKind: 'persisted_construction_artifact_review' as const,
      reviewScope: 'workspace_review_only' as const,
      canonicalSource: 'typed_preview_handoff' as const,
      basisProvenanceLabel: 'artifact_backed_review_basis' as const,
      portfolioTruth: 'imported_portfolio_snapshot' as const,
      candidateTruth: 'hypothetical_construction_artifact' as const,
      constructionArtifactId,
      previewHandoff: makeConstructionArtifactReplayValidationResponse().preview_handoff,
      launchContext: makeConstructionArtifactReplayResponse().review_basis.launch_context,
      openedAt,
      benchmarkSymbol: 'SPY',
      baseCurrency: 'USD',
      replayWindow: {
        startDate: '2024-01-01',
        endDate: '2024-12-31',
      },
      baselineWeights: [{ symbol: 'AAPL', target_weight: 0.6 }],
      candidateWeights: [{ symbol: 'MSFT', target_weight: 0.6 }],
    },
  }
}

function buildOptimizerHandoffReviewSource(handoffReference: OptimizerPersistedArtifactReference, openedAt: string) {
  return {
    kind: 'persisted_optimizer_handoff' as const,
    handoffReference,
    openedAt,
    reviewBasis: {
      basisVersion: 1 as const,
      basisKind: 'persisted_optimizer_handoff_review' as const,
      reviewScope: 'workspace_review_only' as const,
      canonicalSource: 'persisted_handoff_reference' as const,
      basisProvenanceLabel: 'artifact_backed_review_basis' as const,
      portfolioTruth: 'imported_portfolio_snapshot' as const,
      candidateTruth: 'hypothetical_optimizer_handoff' as const,
      handoffReference,
      openedAt,
      benchmarkSymbol: 'SPY',
      baseCurrency: 'USD',
      replayWindow: {
        startDate: '2024-01-01',
        endDate: '2024-12-31',
      },
      baselineWeights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
      candidateWeights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
    },
  }
}

function makeOptimizerHandoffReference(): OptimizerPersistedArtifactReference {
  return {
    reference_kind: 'optimizer_handoff_reference_v1',
    handoff_id: 'optimizer_handoff_123',
    artifact_id: 'optimizer_artifact_123',
    manifest_path: '/tmp/optimizer_handoff_123/manifest.json',
    artifact_path: '/tmp/optimizer_handoff_123/artifact.json',
  }
}

const ib2026HistoryContext = mapImportedHistoryContextToWorkspace(ib2026BootstrapPayload.history_context)
const ff2026HistoryContext = mapImportedHistoryContextToWorkspace(ff2026BootstrapPayload.history_context)

function mockImportedWorkspace(): { workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: WorkingDraft; workspaceState: WorkspaceState } {
  return {
    workspace: { id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) },
    rootNode: { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base' as const, name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
    draft: { id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: persistedSnapshot },
    workspaceState: { workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' },
  }
}

function mockImportedWorkspaceRestore(importedWorkspace: { workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: WorkingDraft }) {
  vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(importedWorkspace.workspace)
  vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(importedWorkspace.rootNode)
  vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(importedWorkspace.draft)
}

function setupAppendedImportedStartupRestoreCase(overrides?: {
  persistedActiveDraftId?: string
  restoredDraft?: WorkingDraft | null
}) {
  const importedWorkspace = mockImportedWorkspace()
  const restoredSnapshot: PortfolioSnapshot = {
    snapshotVersion: 1,
    baseCurrency: 'USD',
    importedMeta: {
      importer: 'interactive_brokers',
      statementPeriod: ib2026MutableSnapshot.statement.statement_period,
      importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
      sourceFileNames: ib2026LoadedFiles,
    },
    positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
      positions.map((position) => ({
        symbol: position.symbol,
        marketValue: position.market_value,
        quantity: null,
        currency: 'USD',
        sector,
        sourceType: 'equity' as const,
      })),
    ),
    cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
    metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
  }
  const restoredImportedSnapshotNode: PortfolioNode = {
    id: 'node-2',
    workspaceId: 'workspace-1',
    parentId: 'node-1',
    kind: 'imported_snapshot',
    name: 'IB 2026',
    createdAt: '2026-04-14T00:00:00Z',
    changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
    portfolioSnapshot: restoredSnapshot,
    source: buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
  }

  vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({
    workspaceId: 'workspace-1',
    activeNodeId: 'node-2',
    activeDraftId: overrides?.persistedActiveDraftId ?? 'draft-2',
    selectedExposureSnapshotId: 'draft',
    lastOpenedAt: '2026-04-14T00:00:00Z',
  })
  vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([importedWorkspace.rootNode, restoredImportedSnapshotNode])
  vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
    ...importedWorkspace.workspace,
    activeNodeId: 'node-2',
    updatedAt: '2026-04-14T00:00:00Z',
  })
  vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
    if (nodeId === 'node-2') return restoredImportedSnapshotNode
    if (nodeId === 'node-1') return importedWorkspace.rootNode
    return null
  })
  vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(overrides?.restoredDraft ?? null)

  installFetchMock(async (input, init) => {
    const pathname = requestPathname(input)
    const method = requestMethod(input, init)
    if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
    if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
    if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
    throw new Error(`Unhandled fetch: ${method} ${pathname}`)
  })

  return { importedWorkspace, restoredImportedSnapshotNode, restoredSnapshot }
}

function makeReplacementIntent(): ReplacementIntentDraftArtifact {
  return { kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1 }
}

function makeHypotheticalReplay(): HypotheticalReplayResponse {
  return {
    proposal: { source: 'draft_replacement_intent', proposal_source: { proposal_source_version: 1, proposal_source_kind: 'draft_replacement_intent_review_only', proposal_truth: 'review_only_hypothetical_proposal', portfolio_truth: 'draft_snapshot_not_applied', review_scope: 'proposal_review_context_only' }, incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
    derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
    baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
    candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
    replay: allocationBacktestPayload,
    warnings: ['Candidate weights are derived from a single-symbol replacement intent and remain hypothetical replay inputs only.'],
  }
}

function makeFormedCandidateArtifact() {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    formation: {
      formation: { kind: 'single_replacement_candidate_formation', status: 'ok' },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1', cash_treatment: 'excluded_from_candidate_formation_basis', position_scope: 'positive_market_value_positions_only' },
      baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
      candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
      formation_summary: { incumbent_start_weight: 1, candidate_start_weight: 1, unchanged_positions_count: 0, baseline_positions_count: 1, candidate_positions_count: 1, starting_turnover_pct: 1 },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', candidate_truth_class: 'hypothetical_candidate_input_only', formation_truth_class: 'candidate_formation_derived', note: 'Candidate formation is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed.' },
      warnings: [],
      rejection_reason: null,
    },
  }
}

function makeConstructedCandidateArtifact() {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    constructionRuleId: 'same_weight_substitution_v1',
    construction: {
      construction: { kind: 'single_replacement_construction', status: 'ok', rule_id: 'same_weight_substitution_v1' },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      inputs: { baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], construction_rule: 'same_weight_substitution_v1', incumbent_start_weight: 1 },
      outputs: { candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }], starting_turnover_pct: 1, unchanged_positions_count: 0 },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', construction_basis: 'explicit_single_replacement_rule', cash_treatment: 'excluded_from_construction_basis', position_scope: 'positive_market_value_positions_only' },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', construction_truth_class: 'candidate_construction_derived', candidate_truth_class: 'hypothetical_candidate_input_only', note: 'Candidate construction is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed and no replay has been run.' },
      warnings: [],
      rejection_reason: null,
    },
  }
}

function makeConstructionConstraintValidationArtifact(status: 'ok' | 'blocked' | 'rejected' = 'ok') {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    constructionRuleId: 'same_weight_substitution_v1',
    validation: {
      validation: {
        kind: 'single_replacement_construction_constraint_validation',
        status,
        constraint_set_id: 'single_replacement_construction_constraints_v1',
      },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      construction: { kind: 'single_replacement_construction', status: 'ok', rule_id: 'same_weight_substitution_v1' },
      derivation: { validation_timing: 'post_construction_pre_replay', validation_basis: 'explicit_constraint_set', candidate_input_source: 'constructed_candidate_payload', constraint_set_id: 'single_replacement_construction_constraints_v1' },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', construction_truth_class: 'candidate_construction_derived', candidate_truth_class: 'hypothetical_candidate_input_only', constraint_validation_truth_class: 'constraint_validation_derived', note: 'Constraint validation remains review-only.' },
      evaluations: [
        { constraint_id: 'weight_sum_matches_rule', severity: 'hard_block', status: status === 'blocked' ? 'fail' : 'pass', message: status === 'blocked' ? 'Constraint failed.' : 'Constraint passed.', rationale: null, actual_value: status === 'blocked' ? 0.97 : 1, expected_value: 1, operator: '==' },
      ],
      blocking_constraint_ids: status === 'blocked' ? ['weight_sum_matches_rule'] : [],
      warnings: [],
      rejection_reason: status === 'rejected' ? 'constructed candidate could not be evaluated safely' : null,
    },
  }
}

function makeSelectedConstructionRuleArtifact(selectedRuleId: 'same_weight_substitution_v1' | 'fixed_split_50_50_substitution_v2' = 'same_weight_substitution_v1') {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    selectedRuleId,
  }
}

function makeConstructionArtifactReplayResponse() {
  return {
    construction_artifact_id: 'artifact-123',
    truth_separation: {
      baseline_truth: 'imported_portfolio_snapshot' as const,
      candidate_truth: 'hypothetical_construction_artifact' as const,
      candidate_applied: false as const,
      consumption_mode: 'explicit_reference_only' as const,
    },
    review_basis: {
      basis_version: 1 as const,
      basis_kind: 'persisted_construction_artifact_review' as const,
      review_scope: 'workspace_review_only' as const,
      canonical_source: 'typed_preview_handoff' as const,
      basis_provenance_label: 'artifact_backed_review_basis' as const,
      portfolio_truth: 'imported_portfolio_snapshot' as const,
      candidate_truth: 'hypothetical_construction_artifact' as const,
      construction_artifact_id: 'artifact-123',
      preview_handoff: makeConstructionArtifactReplayValidationResponse().preview_handoff,
      launch_context: {
        construction_artifact_id: 'artifact-123',
        ranked_universe_artifact_id: 'ranked-1',
        ranked_universe_artifact_schema_version: 'etf_ranking_artifact_v1',
        ranking_id: 'ranking-1',
        ranking_methodology_id: 'method-1',
        ranking_as_of_date: '2026-04-23',
        current_portfolio_artifact_id: 'portfolio-1',
        current_portfolio_as_of_timestamp: '2026-04-23T09:30:00Z',
        policy_id: 'policy-1',
        policy_definition_id: 'policy-def-1',
        top_n: 2,
      },
      benchmark_symbol: 'SPY',
      base_currency: 'USD',
      replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
      baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }],
      candidate_weights: [{ symbol: 'MSFT', target_weight: 0.6 }],
    },
    replay_provenance: {
      source: 'construction_artifact_reference' as const,
      construction_artifact_id: 'artifact-123',
      policy_id: 'policy-1',
      policy_definition_id: 'policy-def-1',
      ranked_universe_artifact_id: 'ranked-1',
      ranked_universe_artifact_schema_version: 'etf_ranking_artifact_v1',
      ranking_id: 'ranking-1',
      ranking_methodology_id: 'method-1',
      ranking_as_of_date: '2026-04-23',
      current_portfolio_artifact_id: 'portfolio-1',
      current_portfolio_as_of_timestamp: '2026-04-23T09:30:00Z',
      top_n: 2,
      hard_constraints: {
        full_investment: true as const,
        long_only: true as const,
        eligible_ranked_universe_only: true as const,
        max_position_weight: 0.6,
        min_position_weight: null,
        max_turnover_weight: null,
        max_trade_intent_count: null,
      },
      baseline_input_source: 'normalized_inputs.current_portfolio_weights' as const,
      candidate_input_source: 'final_target_weights' as const,
      selection_rule_trace: {
        rule_ids: ['rule-1'],
        steps: [{
          rule_id: 'rule-1',
          rule_order: 1,
          input_candidate_symbols: ['AAPL'],
          output_candidate_symbols: ['MSFT'],
        }],
      },
      turnover_diagnostics_status: 'available' as const,
      turnover_diagnostics_v1: {
        diagnostics_version: 'construction_turnover_diagnostics_v1' as const,
        source: 'persisted_construction_artifact' as const,
        diagnostic_truth: 'artifact_backed_hypothetical_construction_diagnostics_only' as const,
        turnover_basis_method_version: 'half_l1_weight_delta_union_v1' as const,
        reported_value_status: 'computed' as const,
        reported_turnover_weight: 0.2,
        inclusion_flags: {
          uses_current_and_target_weight_union: true as const,
          includes_initiations: true as const,
          includes_exits: true as const,
          includes_zero_delta_positions_in_trade_intent_context: true as const,
          excludes_zero_delta_positions_from_reported_turnover_sum: true as const,
        },
        trade_intent_context: { source_field: 'trade_intents' as const, intent_count: 2 },
        feasibility_context: {
          artifact_status: 'feasible' as const,
          failure_reasons_field: 'failure_reasons' as const,
          turnover_failure_reason_present: false,
        },
        constraint_context: {
          constraint_id: 'max_turnover_weight' as const,
          requested: false,
          limit_weight: null,
          evaluation_status: 'not_evaluated' as const,
        },
        symbol_contributions: [
          {
            symbol: 'AAPL',
            action: 'hold' as const,
            current_weight: 0.5,
            target_weight: 0.5,
            delta_weight: 0,
            absolute_delta_weight: 0,
            turnover_contribution_weight: 0,
            contribution_fraction_of_reported_turnover: 0,
            included_in_reported_turnover: false,
          },
          {
            symbol: 'MSFT',
            action: 'initiate' as const,
            current_weight: 0,
            target_weight: 0.4,
            delta_weight: 0.4,
            absolute_delta_weight: 0.4,
            turnover_contribution_weight: 0.2,
            contribution_fraction_of_reported_turnover: 1,
            included_in_reported_turnover: true,
          },
        ],
      },
      weighting_trace_status: 'available' as const,
      weighting_trace_v1: {
        trace_version: 'weighting_trace_v1' as const,
        source: 'persisted_construction_artifact' as const,
        diagnostic_truth: 'artifact_backed_hypothetical_construction_diagnostics_only' as const,
        policy_id: 'policy-1',
        policy_definition_id: 'policy-def-1',
        stages: [],
        normalization: {
          normalization_source: 'raw_weight_numerator_to_seed_weight' as const,
          normalization_applied: false,
          input_metric_id: 'raw_weight_numerator' as const,
          output_metric_id: 'seed_weight' as const,
          raw_value_sum: null,
          normalized_value_sum: null,
          rounding_scale: null,
          normalization_method: 'not_applicable' as const,
          residual_reconciliation_symbol: null,
          residual_reconciliation_delta: null,
        },
        artifact_binding: {
          binding_status: 'final_target_weights_persisted' as const,
          final_target_weights_present: true,
        },
      },
    },
    baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }],
    candidate_weights: [{ symbol: 'MSFT', target_weight: 0.6 }],
    effective_replay_params: {
      benchmark_symbol: 'SPY' as const,
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      initial_capital: 100000,
      rebalance_frequency: 'monthly' as const,
      base_currency: 'USD',
      commission_bps: 0,
      slippage_bps: 0,
      drift_tolerance_pct: null,
      price_basis: 'adjusted_close' as const,
      execution_price_field: 'close' as const,
      execution_lag_days: 1,
      symbol_overrides: {},
    },
    replay: allocationBacktestPayload,
  }
}

function makeConstructionArtifactReplayValidationResponse(overrides: Partial<ConstructionArtifactReplayValidationResponse> = {}): ConstructionArtifactReplayValidationResponse {
  return {
    construction_artifact_id: 'artifact-123',
    effective_replay_params: {
      benchmark_symbol: 'SPY',
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      initial_capital: 100000,
      rebalance_frequency: 'monthly',
      base_currency: 'USD',
      commission_bps: 0,
      slippage_bps: 0,
      drift_tolerance_pct: null,
      price_basis: 'adjusted_close',
      execution_price_field: 'close',
      execution_lag_days: 1,
      symbol_overrides: {},
    },
    preview_handoff: {
      handoff_kind: 'construction_artifact_preview_handoff_v1',
      construction_artifact_id: 'artifact-123',
      effective_replay_params: {
        benchmark_symbol: 'SPY',
        start_date: '2024-01-01',
        end_date: '2024-12-31',
        initial_capital: 100000,
        rebalance_frequency: 'monthly',
        base_currency: 'USD',
        commission_bps: 0,
        slippage_bps: 0,
        drift_tolerance_pct: null,
        price_basis: 'adjusted_close',
        execution_price_field: 'close',
        execution_lag_days: 1,
        symbol_overrides: {},
      },
    },
    open_payload: null,
    ...overrides,
  }
}

function makeOptimizerHandoffValidationResponse(overrides: Partial<OptimizerHandoffValidationResponse> = {}): OptimizerHandoffValidationResponse {
  return {
    handoff_id: 'optimizer_handoff_123',
    artifact_id: 'optimizer_artifact_123',
    source_portfolio_snapshot_id: 'portfolio_snapshot_123',
    truth_separation: {
      source_truth: 'persisted_hypothetical_optimizer_handoff',
      holdings_truth: 'imported_portfolio_snapshot',
      optimizer_output_applied: false,
      consumption_mode: 'explicit_reference_only',
    },
    eligible_replay_window: {
      source: 'persisted_return_basis_attestation',
      benchmark_symbol: 'SPY',
      as_of_date: '2024-12-31',
      start_date: '2024-01-01',
      end_date: '2024-12-31',
    },
    replay_handoff: {
      handoff_kind: 'optimizer_handoff_replay_handoff_v1',
      handoff_reference: makeOptimizerHandoffReference(),
      effective_replay_params: {
        start_date: '2024-01-01',
        end_date: '2024-12-31',
        initial_capital: 100000,
        rebalance_frequency: 'monthly',
        base_currency: 'USD',
        commission_bps: 0,
        slippage_bps: 0,
        drift_tolerance_pct: null,
        price_basis: 'adjusted_close',
        execution_price_field: 'close',
        execution_lag_days: 1,
        symbol_overrides: {},
      },
    },
    provenance: {
      source: 'optimizer_handoff_reference',
      benchmark_id: 'benchmark_spy_demo_v1',
      benchmark_version: '2024-04-15',
      benchmark_symbol: 'SPY',
      objective: {
        objective_id: 'minimize_l2_distance_to_benchmark',
        benchmark_relative: true,
        description: 'Minimize squared distance to benchmark weights inside the hard-constraint set.',
        alpha_signal_id: null,
        requires_alpha_package: false,
      },
      replay_output_policy: {
        source: 'persisted_return_basis_attestation',
        section_trust: {
          benchmark_relative_path: 'degraded_unverified_return_basis',
          factor_model_path: 'degraded_unverified_return_basis',
          risk_contribution_path: 'degraded_unverified_return_basis',
        },
        eligible_families: [],
        withheld_families: ['benchmark_relative_volatility_outputs', 'factor_exposure_outputs'],
      },
      artifact_state: 'fresh',
      constraint_set_fingerprint: 'constraint-fingerprint-1',
    },
    validation_status: 'ok',
    evaluations: [],
    blocking_rule_ids: [],
    warnings: [],
    ...overrides,
  }
}

function makeOptimizerHandoffReplayResponse(): OptimizerHandoffReplayResponse {
  return {
    handoff_id: 'optimizer_handoff_123',
    artifact_id: 'optimizer_artifact_123',
    source_portfolio_snapshot_id: 'portfolio_snapshot_123',
    truth_separation: {
      baseline_truth: 'imported_portfolio_snapshot',
      candidate_truth: 'hypothetical_optimizer_handoff',
      candidate_applied: false,
      consumption_mode: 'explicit_reference_only',
    },
    review_basis: {
      basis_version: 1,
      basis_kind: 'persisted_optimizer_handoff_review',
      review_scope: 'workspace_review_only',
      canonical_source: 'persisted_handoff_reference',
      basis_provenance_label: 'artifact_backed_review_basis',
      portfolio_truth: 'imported_portfolio_snapshot',
      candidate_truth: 'hypothetical_optimizer_handoff',
      handoff_reference: makeOptimizerHandoffReference(),
      benchmark_symbol: 'SPY',
      base_currency: 'USD',
      replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
      baseline_weights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
      candidate_weights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
    },
    replay_provenance: {
      source: 'optimizer_handoff_reference',
      benchmark_id: 'benchmark_spy_demo_v1',
      benchmark_version: '2024-04-15',
      benchmark_symbol: 'SPY',
      return_basis_attestation: {
        benchmark_symbol: 'SPY',
        as_of_date: '2024-12-31',
        history_start_date: '2024-01-01',
        history_end_date: '2024-12-31',
        factor_proxy_symbols: ['QQQ'],
        benchmark_return_basis_contract: 'unverified_adjusted_proxy',
        factor_return_basis_contract: 'unverified_adjusted_proxy',
        factor_basis_path: 'degraded_unverified_return_basis',
        section_trust: {
          benchmark_relative_path: 'degraded_unverified_return_basis',
          factor_model_path: 'degraded_unverified_return_basis',
          risk_contribution_path: 'degraded_unverified_return_basis',
        },
        evidence: {
          benchmark_history: { verification_status: 'unverified', economic_basis: 'adjusted_close_proxy', construction_method: 'vendor_adjusted_close', disqualifiers: [], fallbacks_used: [], source_price_field: 'adj_close' },
          factor_history: { verification_status: 'unverified', economic_basis: 'adjusted_close_proxy', construction_method: 'vendor_adjusted_close', disqualifiers: [], fallbacks_used: [], source_price_field: 'adj_close' },
        },
      },
      replay_output_policy: {
        source: 'persisted_return_basis_attestation',
        section_trust: {
          benchmark_relative_path: 'degraded_unverified_return_basis',
          factor_model_path: 'degraded_unverified_return_basis',
          risk_contribution_path: 'degraded_unverified_return_basis',
        },
        eligible_families: [],
        withheld_families: ['benchmark_relative_volatility_outputs', 'factor_exposure_outputs'],
      },
      artifact_state: 'fresh',
      optimizer_status: 'feasible',
      constraint_set_fingerprint: 'constraint-fingerprint-1',
    },
    optimizer_context: {
      objective: {
        objective_id: 'minimize_l2_distance_to_benchmark',
        benchmark_relative: true,
        description: 'Minimize squared distance to benchmark weights inside the hard-constraint set.',
        alpha_signal_id: null,
        requires_alpha_package: false,
      },
      penalty_ids: [],
      artifact_state: 'fresh',
      stale_inputs: [],
      degraded_inputs: [],
      reasons: [],
      run_summary: { engine_id: 'optimizer_engine_v1', solver_id: 'solver_v1', methodology_id: 'optimizer_methodology_v1' },
      diagnostics: { turnover: 0.2, active_share: 0.1 },
      binding_constraints: [],
      violated_constraints: [],
      benchmark_relative_attestations: [],
      binding_constraint_evaluations: [],
    },
    baseline_weights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
    candidate_weights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
    replay: allocationBacktestPayload,
  }
}

function makeEtfRankingPayload() {
  return {
    schema_version: 'etf_ranking_artifact_v1',
    artifact_id: 'etf_ranking_artifact_sector_1',
    ranking_id: 'etf_ranking_engine_v1',
    title: 'ETF Ranking Engine',
    as_of_date: '2026-04-15',
    benchmark_symbol: 'SPY',
    universe: ['IUFS', 'IUHC', 'VDST'],
    lookback_months: 6,
    price_basis: 'close',
    methodology: 'm',
    effective_peer_group: 'Sector UCITS ETF',
    effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 },
    source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' },
    warnings: { confidence: 'medium', warnings: ['Implementation-fit support is not complete across the ranked universe.'], unknown_metadata_symbols: [], peer_group_unclassified_symbols: [] },
    request: { peer_group: 'Sector UCITS ETF', universe: ['IUFS', 'IUHC', 'VDST'], benchmark_symbol: 'SPY', lookback_months: 6 },
    effective_inputs: {
      effective_peer_group: 'Sector UCITS ETF',
      effective_component_weights: { momentum: 0.3, benchmark_relative_strength: 0.2, realized_volatility: 0.15, downside_volatility: 0.1, max_drawdown: 0.1, liquidity: 0.1, implementation_fit: 0.05 },
      requested_universe: ['IUFS', 'IUHC', 'VDST'],
      evaluated_universe: ['IUFS', 'IUHC'],
      excluded_symbols: [{ symbol: 'VDST', reason: 'instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF' }],
    },
    run_metadata: {
      ranking_id: 'etf_ranking_engine_v1',
      methodology_id: 'etf_ranking_methodology_v1',
      methodology: 'm',
      as_of_date: '2026-04-15',
      ranking_basis_date: '2026-04-15',
      price_basis: 'close',
      source_status: { price_history: 'sample', benchmark_history: 'sample', holdings_support: 'mixed' },
      confidence: 'medium',
    },
    ranked_universe: [
      {
        rank: 1,
        symbol: 'IUFS',
        composite_score: 0.8123,
        instrument: { symbol: 'IUFS', name: 'iShares S&P 500 Financials Sector UCITS ETF', asset_class: 'etf', sector: 'Financials', category: 'Sector UCITS ETF', currency: 'USD' },
        component_scores: {
          momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 11.2, raw_unit: 'pct', normalized_score: 1, weight: 0.3, weighted_score: 0.3 },
          benchmark_relative_strength: { label: 'Benchmark-relative strength', direction: 'higher_is_better', raw_value: 4.2, raw_unit: 'pct', normalized_score: 1, weight: 0.2, weighted_score: 0.2 },
          realized_volatility: { label: 'Realized volatility', direction: 'lower_is_better', raw_value: 14.4, raw_unit: 'pct', normalized_score: 0.7, weight: 0.15, weighted_score: 0.105 },
          max_drawdown: { label: 'Max drawdown', direction: 'lower_is_better', raw_value: 8.1, raw_unit: 'pct', normalized_score: 0.75, weight: 0.1, weighted_score: 0.075 },
          liquidity: { label: 'Median dollar volume', direction: 'higher_is_better', raw_value: 13.1, raw_unit: 'score', normalized_score: 0.8, weight: 0.1, weighted_score: 0.08 },
          implementation_fit: { label: 'Implementation fit', direction: 'higher_is_better', raw_value: 1, raw_unit: 'score', normalized_score: 1, weight: 0.05, weighted_score: 0.05 },
        },
      },
      {
        rank: 2,
        symbol: 'IUHC',
        composite_score: 0.7345,
        instrument: { symbol: 'IUHC', name: 'iShares S&P 500 Health Care Sector UCITS ETF', asset_class: 'etf', sector: 'Health Care', category: 'Sector UCITS ETF', currency: 'USD' },
        component_scores: {
          momentum: { label: 'Blended momentum', direction: 'higher_is_better', raw_value: 9.8, raw_unit: 'pct', normalized_score: 0.8, weight: 0.3, weighted_score: 0.24 },
          benchmark_relative_strength: { label: 'Benchmark-relative strength', direction: 'higher_is_better', raw_value: 2.7, raw_unit: 'pct', normalized_score: 0.7, weight: 0.2, weighted_score: 0.14 },
          realized_volatility: { label: 'Realized volatility', direction: 'lower_is_better', raw_value: 15.8, raw_unit: 'pct', normalized_score: 0.6, weight: 0.15, weighted_score: 0.09 },
          max_drawdown: { label: 'Max drawdown', direction: 'lower_is_better', raw_value: 9.5, raw_unit: 'pct', normalized_score: 0.65, weight: 0.1, weighted_score: 0.065 },
          liquidity: { label: 'Median dollar volume', direction: 'higher_is_better', raw_value: 12.3, raw_unit: 'score', normalized_score: 0.7, weight: 0.1, weighted_score: 0.07 },
          implementation_fit: { label: 'Implementation fit', direction: 'higher_is_better', raw_value: 1, raw_unit: 'score', normalized_score: 1, weight: 0.05, weighted_score: 0.05 },
        },
      },
    ],
    excluded_symbols: [{ symbol: 'VDST', reason: 'instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF' }],
  }
}

function makeEtfRankingMetadataPayload() {
  return { available_effective_peer_groups: ['Sector UCITS ETF'] }
}

function makeEtfRankingRecentRunsPayload(): EtfRankingArtifactRecentRow[] {
  return []
}

function makeReplacementRankingRecentDiscoveryPayload() {
  return {
    items: [],
    metadata: {
      applied_filters: {
        artifact_kind: 'intent_bound_etf_replacement_ranking',
      },
    },
  }
}

function makeConstructionPoliciesResponse(policyIds: string[] = ['top_n_equal_weight_v1', 'top_n_inverse_rank_weight_v1', 'top_n_linear_rank_weight_v1']) {
  const catalog = {
    top_n_equal_weight_v1: {
      policy_id: 'top_n_equal_weight_v1',
      policy_definition_id: 'construction_policy_definition_top_n_equal_weight_v1',
      name: 'Top N Equal Weight v1',
      description: 'Select eligible top-ranked names and assign equal target weights.',
      family: 'top_n_equal_weight',
      constraints: 'long_only_fully_invested_max_position_turnover',
      inputs: 'ranked_universe_and_current_portfolio',
      determinism: 'deterministic_rank_order',
      ranking_support: 'selection_only',
      full_investment_constraint: 'required',
      long_only_constraint: 'required',
      eligible_ranked_universe_constraint: 'required',
      max_position_weight_constraint: 'required',
      min_position_weight_constraint: 'supported_optional',
      max_turnover_weight_constraint: 'supported_optional',
      max_trade_intent_count_constraint: 'supported_optional',
      ranked_universe_input: 'required',
      current_portfolio_input: 'required',
      launch_top_n: 2,
      selection_rule_ids: ['eligible_only', 'take_top_n'],
    },
    top_n_inverse_rank_weight_v1: {
      policy_id: 'top_n_inverse_rank_weight_v1',
      policy_definition_id: 'construction_policy_definition_top_n_inverse_rank_weight_v1',
      name: 'Top N Inverse Rank Weight v1',
      description: 'Select eligible top-ranked names and weight them by inverse selected-order rank.',
      family: 'top_n_rank_weighted',
      constraints: 'long_only_fully_invested_max_position_turnover',
      inputs: 'ranked_universe_and_current_portfolio',
      determinism: 'deterministic_rank_order',
      ranking_support: 'inverse_selected_order_weighting',
      full_investment_constraint: 'required',
      long_only_constraint: 'required',
      eligible_ranked_universe_constraint: 'required',
      max_position_weight_constraint: 'required',
      min_position_weight_constraint: 'supported_optional',
      max_turnover_weight_constraint: 'supported_optional',
      max_trade_intent_count_constraint: 'supported_optional',
      ranked_universe_input: 'required',
      current_portfolio_input: 'required',
      launch_top_n: 2,
      selection_rule_ids: ['eligible_only', 'take_top_n'],
    },
    top_n_linear_rank_weight_v1: {
      policy_id: 'top_n_linear_rank_weight_v1',
      policy_definition_id: 'construction_policy_definition_top_n_linear_rank_weight_v1',
      name: 'Top N Linear Rank Weight v1',
      description: 'Select eligible top-ranked names and weight them by selected-order linear rank numerators N..1.',
      family: 'top_n_rank_weighted',
      constraints: 'long_only_fully_invested_max_position_turnover',
      inputs: 'ranked_universe_and_current_portfolio',
      determinism: 'deterministic_rank_order',
      ranking_support: 'linear_selected_order_weighting',
      full_investment_constraint: 'required',
      long_only_constraint: 'required',
      eligible_ranked_universe_constraint: 'required',
      max_position_weight_constraint: 'required',
      min_position_weight_constraint: 'supported_optional',
      max_turnover_weight_constraint: 'supported_optional',
      max_trade_intent_count_constraint: 'supported_optional',
      ranked_universe_input: 'required',
      current_portfolio_input: 'required',
      launch_top_n: 2,
      selection_rule_ids: ['eligible_only', 'take_top_n'],
    },
  } as const

  return policyIds.map((policyId) => catalog[policyId as keyof typeof catalog])
}

function makeConstructionRankingArtifactPreflightResponse() {
  return {
    contract_version: 'construction_ranking_artifact_preflight_v1' as const,
    artifact: {
      artifact_kind: 'etf_ranking' as const,
      artifact_id: 'etf_ranking_artifact_sector_1',
      schema_version: 'etf_ranking_artifact_v1' as const,
      ranking_id: 'etf_ranking_engine_v1',
      methodology_id: 'etf_ranking_methodology_v1',
      as_of_date: '2026-04-15',
    },
    eligibility: {
      eligible: true as const,
      reason: null,
    },
    handoff: {
      handoff_kind: 'etf_ranking_artifact_construction_handoff_v1' as const,
      artifact_kind: 'etf_ranking' as const,
      artifact_id: 'etf_ranking_artifact_sector_1',
      schema_version: 'etf_ranking_artifact_v1' as const,
      ranking_id: 'etf_ranking_engine_v1',
      methodology_id: 'etf_ranking_methodology_v1',
      as_of_date: '2026-04-15',
    },
  }
}

function makeReplacementConstructionRankingArtifactPreflightResponse() {
  return {
    contract_version: 'construction_ranking_artifact_preflight_v1' as const,
    artifact: {
      artifact_kind: 'intent_bound_etf_replacement_ranking' as const,
      artifact_id: 'intent_bound_etf_replacement_ranking_artifact_sector_1',
      schema_version: 'intent_bound_etf_replacement_ranking_artifact_v1' as const,
      ranking_id: 'intent_bound_etf_replacement_ranking_engine_v1',
      methodology_id: 'intent_bound_etf_replacement_ranking_methodology_v1',
      as_of_date: '2026-04-15',
    },
    eligibility: {
      eligible: true as const,
      reason: null,
    },
    handoff: {
      handoff_kind: 'intent_bound_etf_replacement_ranking_artifact_construction_handoff_v1' as const,
      artifact_kind: 'intent_bound_etf_replacement_ranking' as const,
      artifact_id: 'intent_bound_etf_replacement_ranking_artifact_sector_1',
      schema_version: 'intent_bound_etf_replacement_ranking_artifact_v1' as const,
      ranking_id: 'intent_bound_etf_replacement_ranking_engine_v1',
      methodology_id: 'intent_bound_etf_replacement_ranking_methodology_v1',
      as_of_date: '2026-04-15',
    },
  }
}

function makeConstructionRunArtifactResponse(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 'construction_artifact_v1' as const,
    artifact_id: 'construction_artifact_456',
    normalized_inputs: {
      ranked_universe_artifact_kind: 'etf_ranking',
      ranked_universe_artifact_id: 'etf_ranking_artifact_sector_1',
      ranked_universe_artifact_schema_version: 'etf_ranking_artifact_v1',
      ranking_id: 'etf_ranking_engine_v1',
      ranking_methodology_id: 'etf_ranking_methodology_v1',
      ranking_as_of_date: '2026-04-15',
      current_portfolio_artifact_id: 'workspace_current_portfolio_1',
      current_portfolio_as_of_timestamp: '2026-04-10T00:00:00Z',
      policy_id: 'top_n_equal_weight_v1',
      policy_definition_id: 'construction_policy_definition_top_n_equal_weight_v1',
      top_n: 2,
    },
    ...overrides,
  }
}

function makeEtfRankingPreflightPayload(overrides: Record<string, unknown> = {}) {
  const artifact = makeEtfRankingPayload()
  return {
    contract_version: 'ranking_artifact_preflight_v1',
    artifact: {
      artifact_kind: 'etf_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
      ranking_id: artifact.ranking_id,
      methodology_id: artifact.run_metadata.methodology_id,
      as_of_date: artifact.run_metadata.as_of_date,
      ranking_basis_date: artifact.run_metadata.ranking_basis_date,
    },
    eligibility: {
      review_truth_basis: 'authoritative_persisted_ranking_artifact',
      review_scope: 'artifact_backed_review_only',
      open_supported: true,
      replay_eligible: true,
      consumer_handoff_supported: false,
      ineligibility_reason: null,
    },
    open_handoff: {
      handoff_kind: 'ranking_artifact_open_handoff_v1',
      artifact_kind: 'etf_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
    },
    ...overrides,
  }
}

function makeSavedProposalArtifact(input?: {
  id?: string
  createdAt?: string
  versionNumber?: number
  candidateSymbol?: string
  proposalFamilyId?: string
  reviewSnapshotArtifactId?: string
}): VersionedProposalArtifact {
  const candidateSymbol = input?.candidateSymbol ?? 'IUFS'
  const createdAt = input?.createdAt ?? '2026-04-16T00:00:00Z'
  const versionNumber = input?.versionNumber ?? 1
  const reviewSnapshot = cloneMutable<HypotheticalReplayResponse>(makeHypotheticalReplay())

  reviewSnapshot.proposal = {
    ...reviewSnapshot.proposal,
    candidate_symbol: candidateSymbol,
    proposal_source: { ...reviewSnapshot.proposal.proposal_source! },
  }

  const proposal = {
    id: input?.id ?? `proposal-${versionNumber}`,
    kind: 'single_replacement_hypothetical_replay_proposal',
    schemaVersion: 1,
    createdAt,
    workspaceId: 'workspace-1',
    sourceDraftId: 'draft-1',
    sourceBaseNodeId: 'node-1',
    proposalFamilyId: input?.proposalFamilyId ?? `etf_replacement_intent:AAPL:${candidateSymbol}:${createdAt}`,
    versionNumber,
    savedFrom: 'desktop_hypothetical_replay_review',
    reviewStatus: 'recorded',
    sourceIntent: {
      ...makeReplacementIntent(),
      candidateSymbol,
    },
    proposalCapture: {
      capture_version: 1,
      capture_kind: 'workspace_review_saved_proposal',
      open_handoff: {
        handoff_kind: 'review_snapshot_open_handoff_v1',
        artifact_id: input?.reviewSnapshotArtifactId ?? `review_snapshot_${versionNumber}`,
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      lineage: {
        workspace_id: 'workspace-1',
        source_draft_id: 'draft-1',
        source_base_node_id: 'node-1',
        proposal_family_id: input?.proposalFamilyId ?? `etf_replacement_intent:AAPL:${candidateSymbol}:${createdAt}`,
        proposal_id: input?.id ?? `proposal-${versionNumber}`,
        version_number: versionNumber,
        source_kind: 'hypothetical_replacement_replay',
      },
      proposal: {
        source: reviewSnapshot.proposal.source,
        proposal_source: reviewSnapshot.proposal.proposal_source!,
        incumbent_symbol: reviewSnapshot.proposal.incumbent_symbol,
        candidate_symbol: reviewSnapshot.proposal.candidate_symbol,
      },
      replay_type: 'replay' in reviewSnapshot ? 'standard' : 'overlay_aware',
      replay_provenance: cloneMutable(reviewSnapshot.replay_provenance),
      review_basis: {
        benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
        benchmark_symbol: 'SPY',
        replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
        rebalance_frequency: 'monthly',
        commission_bps: 0,
        slippage_bps: 0,
        derivation_basis: 'draft_snapshot_positions_normalized',
        candidate_construction_rule: 'same_weight_substitution_v1',
      },
    },
    proposalSource: {
      proposalSourceVersion: 1,
      proposalSourceKind: 'draft_replacement_intent_review_only',
      proposalTruth: 'review_only_hypothetical_proposal',
      portfolioTruth: 'draft_snapshot_not_applied',
      reviewScope: 'proposal_review_context_only',
    },
    reviewSnapshotArtifactId: input?.reviewSnapshotArtifactId ?? `review_snapshot_${versionNumber}`,
    replayBasis: {
      benchmarkSymbol: 'SPY',
      startDate: '2024-01-01',
      endDate: '2024-12-31',
      rebalanceFrequency: 'monthly',
      commissionBps: 0,
      slippageBps: 0,
      derivationBasis: 'draft_snapshot_positions_normalized',
      candidateConstructionRule: 'same_weight_substitution_v1',
      replayProvenance: cloneMutable(makeHypotheticalReplay().replay_provenance),
    },
    reviewSnapshot,
  } as VersionedProposalArtifact

  return {
    ...proposal,
    reviewSnapshotPMSummary: makeReviewSnapshotArtifactFromProposal(proposal).pm_summary as SavedProposalReviewSnapshotPMSummaryMirror,
  }
}

function makeReviewSnapshotArtifactFromProposal(proposal: VersionedProposalArtifact): ReviewSnapshotArtifact {
  const effectiveReplay = 'replay' in proposal.reviewSnapshot ? proposal.reviewSnapshot.replay : proposal.reviewSnapshot.overlay_replay
  const methodologyProvenance = effectiveReplay.methodology_provenance!
  const pmSummary: SavedProposalReviewSnapshotPMSummaryMirror = {
    pm_summary_version: 1,
    role: 'saved_proposal',
    provenance: {
      source: 'persisted_review_snapshot_artifact',
      artifact_kind: 'portfolio_review_snapshot',
      schema_version: 'review_snapshot_artifact_v1',
      consumer_kind: 'saved_hypothetical_replay_proposal',
      lineage: {
        workspace_id: proposal.workspaceId,
        source_draft_id: proposal.sourceDraftId,
        source_base_node_id: proposal.sourceBaseNodeId,
        proposal_family_id: proposal.proposalFamilyId,
        proposal_id: proposal.id,
        version_number: proposal.versionNumber,
        source_kind: 'hypothetical_replacement_replay',
      },
      proposal_source: proposal.reviewSnapshot.proposal.proposal_source!,
      replay_provenance: proposal.replayBasis.replayProvenance,
    },
    truth_labels: {
      proposal_truth: 'review_only_hypothetical_proposal',
      portfolio_truth: 'draft_snapshot_not_applied',
      analytics_truth: 'hypothetical_replay_analytics_only',
      review_scope: 'proposal_review_context_only',
    },
    replay_type: 'replay' in proposal.reviewSnapshot ? 'standard' : 'overlay_aware',
    replay_status: effectiveReplay.candidate_result.status,
    investor_economics_status: effectiveReplay.investor_economics_status,
    review_basis: {
      benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
      benchmark_symbol: proposal.replayBasis.benchmarkSymbol,
      replay_window: { start_date: proposal.replayBasis.startDate, end_date: proposal.replayBasis.endDate },
      rebalance_frequency: proposal.replayBasis.rebalanceFrequency,
      commission_bps: proposal.replayBasis.commissionBps,
      slippage_bps: proposal.replayBasis.slippageBps,
      derivation_basis: proposal.replayBasis.derivationBasis,
      candidate_construction_rule: proposal.replayBasis.candidateConstructionRule,
    },
    methodology: {
      methodology: effectiveReplay.methodology,
      methodology_provenance: methodologyProvenance,
    },
    assumptions: effectiveReplay.candidate_result.assumptions,
    analytics_summary: {
      candidate_analytics: {
        methodology: effectiveReplay.methodology,
        methodology_provenance: methodologyProvenance,
        assumptions: effectiveReplay.candidate_result.assumptions,
        benchmark_symbol: proposal.replayBasis.benchmarkSymbol,
        benchmark_return_pct: 1,
        total_return_pct: 1,
        annualized_return_pct: 1,
        annualized_volatility_pct: 1,
        downside_volatility_pct: 1,
        max_drawdown_pct: -1,
        sharpe_ratio: 1,
        sortino_ratio: 1,
        excess_return_pct: 0,
        tracking_error_pct: 1,
        information_ratio: 0,
        beta_vs_benchmark: 1,
        correlation_vs_benchmark: 1,
        total_turnover_pct: 0,
        total_cost_paid: 0,
      },
      baseline_analytics: null,
      analytics_comparison: null,
    },
    diagnostics_summary: {
      diagnostics_available: false,
      top_factor_exposure_change: null,
      top_volatility_change: null,
      top_risk_contribution_change: null,
      top_concentration_change: null,
      top_stress_scenario_change: null,
    },
  }

  return {
    identity: {
      artifact_id: proposal.reviewSnapshotArtifactId!,
      artifact_kind: 'portfolio_review_snapshot',
      schema_version: 'review_snapshot_artifact_v1',
      fingerprint: 'f'.repeat(64),
      consumer_kind: 'saved_hypothetical_replay_proposal',
    },
    lineage: {
      workspace_id: proposal.workspaceId,
      source_draft_id: proposal.sourceDraftId,
      source_base_node_id: proposal.sourceBaseNodeId,
      proposal_family_id: proposal.proposalFamilyId,
      proposal_id: proposal.id,
      version_number: proposal.versionNumber,
      source_kind: 'hypothetical_replacement_replay',
    },
    review_basis: {
      benchmark_symbol: proposal.replayBasis.benchmarkSymbol,
      start_date: proposal.replayBasis.startDate,
      end_date: proposal.replayBasis.endDate,
      rebalance_frequency: proposal.replayBasis.rebalanceFrequency,
      commission_bps: proposal.replayBasis.commissionBps,
      slippage_bps: proposal.replayBasis.slippageBps,
      derivation_basis: proposal.replayBasis.derivationBasis,
      candidate_construction_rule: proposal.replayBasis.candidateConstructionRule,
      replay_provenance: proposal.replayBasis.replayProvenance,
    },
    truth_labels: {
      proposal_truth: 'review_only_hypothetical_proposal',
      portfolio_truth: 'draft_snapshot_not_applied',
      analytics_truth: 'hypothetical_replay_analytics_only',
      review_scope: 'proposal_review_context_only',
    },
    compact_summary: {
      replay_type: 'replay' in proposal.reviewSnapshot ? 'standard' : 'overlay_aware',
      replay_status: effectiveReplay.candidate_result.status,
      investor_economics_status: effectiveReplay.investor_economics_status,
      candidate_analytics: {
        methodology: effectiveReplay.methodology,
        methodology_provenance: methodologyProvenance,
        assumptions: effectiveReplay.candidate_result.assumptions,
        benchmark_symbol: proposal.replayBasis.benchmarkSymbol,
        benchmark_return_pct: 1,
        total_return_pct: 1,
        annualized_return_pct: 1,
        annualized_volatility_pct: 1,
        downside_volatility_pct: 1,
        max_drawdown_pct: -1,
        sharpe_ratio: 1,
        sortino_ratio: 1,
        excess_return_pct: 0,
        tracking_error_pct: 1,
        information_ratio: 0,
        beta_vs_benchmark: 1,
        correlation_vs_benchmark: 1,
        total_turnover_pct: 0,
        total_cost_paid: 0,
      },
      baseline_analytics: null,
      analytics_comparison: null,
      diagnostics_summary: {
        diagnostics_available: false,
        top_factor_exposure_change: null,
        top_volatility_change: null,
        top_risk_contribution_change: null,
        top_concentration_change: null,
        top_stress_scenario_change: null,
      },
    },
    proposal_capture: proposal.proposalCapture,
    pm_summary: pmSummary as unknown as ReviewSnapshotArtifact['pm_summary'],
    source_payload: {
      replay_type: 'replay' in proposal.reviewSnapshot ? 'standard' : 'overlay_aware',
      replay: 'replay' in proposal.reviewSnapshot ? proposal.reviewSnapshot : null,
      overlay_replay: 'overlay_replay' in proposal.reviewSnapshot ? proposal.reviewSnapshot : null,
    },
  }
}

function makeReplacementRankingPayload(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 'intent_bound_etf_replacement_ranking_artifact_v1',
    artifact_id: 'intent_bound_etf_replacement_ranking_artifact_sector_1',
    ranking_id: 'intent_bound_etf_replacement_ranking_engine_v1',
    methodology_id: 'intent_bound_etf_replacement_ranking_methodology_v1',
    basis_date: '2026-04-15',
    status: 'ok',
    request: {
      replacement_intent: {
        draft_id: 'draft-1',
        workspace_id: 'workspace-1',
        base_node_id: 'node-1',
        base_symbol: 'AAPL',
        candidate_symbol: 'IUFS',
        seed_ranking_id: 'etf_ranking_engine_v1',
        seed_methodology_id: 'etf_ranking_methodology_v1',
        seed_ranking_basis_date: '2026-04-15',
        peer_group: 'Sector UCITS ETF',
        benchmark_symbol: 'SPY',
        lookback_months: 6,
      },
      seed_context: {
        ranking_id: 'etf_ranking_engine_v1',
        methodology_id: 'etf_ranking_methodology_v1',
        ranking_basis_date: '2026-04-15',
        peer_group: 'Sector UCITS ETF',
        benchmark_symbol: 'SPY',
        lookback_months: 6,
        seeded_symbols: ['AAPL', 'IUFS'],
      },
      prefer_live_data: false,
      normalized_request: {
        base_symbol: 'AAPL',
        candidate_symbol: 'IUFS',
        seeded_symbols: ['AAPL', 'IUFS'],
        peer_group: 'Sector UCITS ETF',
        ranking_basis_date: '2026-04-15',
        benchmark_symbol: 'SPY',
        lookback_months: 6,
      },
    },
    request_context: {
      universe: ['AAPL', 'IUFS'],
      benchmark_symbol: 'SPY',
      lookback_months: 6,
      prefer_live_data: false,
      base_symbol: 'AAPL',
      candidate_symbol: 'IUFS',
      peer_group: 'Sector UCITS ETF',
      ranking_basis_date: '2026-04-15',
      seed_ranking_id: 'etf_ranking_engine_v1',
      seed_methodology_id: 'etf_ranking_methodology_v1',
    },
    submitted_request: {
      replacement_intent: {
        draft_id: 'draft-1',
        workspace_id: 'workspace-1',
        base_node_id: 'node-1',
        base_symbol: 'AAPL',
        candidate_symbol: 'IUFS',
        seed_ranking_id: 'etf_ranking_engine_v1',
        seed_methodology_id: 'etf_ranking_methodology_v1',
        seed_ranking_basis_date: '2026-04-15',
        peer_group: 'Sector UCITS ETF',
        benchmark_symbol: 'SPY',
        lookback_months: 6,
      },
      seed_context: {
        ranking_id: 'etf_ranking_engine_v1',
        methodology_id: 'etf_ranking_methodology_v1',
        ranking_basis_date: '2026-04-15',
        peer_group: 'Sector UCITS ETF',
        benchmark_symbol: 'SPY',
        lookback_months: 6,
        seeded_symbols: ['AAPL', 'IUFS'],
      },
      prefer_live_data: false,
    },
    normalized_request: {
      base_symbol: 'AAPL',
      candidate_symbol: 'IUFS',
      seeded_symbols: ['AAPL', 'IUFS'],
      peer_group: 'Sector UCITS ETF',
      ranking_basis_date: '2026-04-15',
      benchmark_symbol: 'SPY',
      lookback_months: 6,
    },
    effective_inputs: {
      benchmark_symbol: 'SPY',
      lookback_months: 6,
      price_basis: 'close',
      requested_universe: ['AAPL', 'IUFS'],
      evaluated_universe: ['IUFS'],
      base_symbol: 'AAPL',
      candidate_symbol: 'IUFS',
      peer_group: 'Sector UCITS ETF',
      ranking_basis_date: '2026-04-15',
    },
    request_hash: 'request-hash-1',
    run_metadata: {
      ranking_id: 'intent_bound_etf_replacement_ranking_engine_v1',
      methodology_id: 'intent_bound_etf_replacement_ranking_methodology_v1',
      methodology: 'm',
      as_of_date: '2026-04-15',
      ranking_basis_date: '2026-04-15',
      basis_date: '2026-04-15',
      request_hash: 'request-hash-1',
      price_basis: 'close',
      source_status: 'sample',
      tie_break_order: ['composite_score'],
      factor_weights: { momentum: 1 },
      confidence: 'medium',
    },
    eligible_count: 1,
    excluded_count: 1,
    ranked_candidates: [{
      symbol: 'IUFS',
      rank: 1,
      composite_score: 0.8123,
      raw_factors: {
        momentum_12_1: 11.2,
        momentum_6_1: 4.2,
        momentum_blended: 7.7,
        realized_volatility_126d: 14.4,
        max_drawdown_252d: 8.1,
        liquidity_60d: 13.1,
      },
      normalized_scores: {
        momentum: 1,
        realized_volatility: 0.7,
        max_drawdown: 0.75,
        liquidity: 0.8,
      },
      eligibility_status: 'eligible',
      exclusion_reason: null,
      basis_date: '2026-04-15',
      draft_id: 'draft-1',
      base_node_id: 'node-1',
      base_symbol: 'AAPL',
      seed_ranking_id: 'etf_ranking_engine_v1',
      seed_methodology_id: 'etf_ranking_methodology_v1',
    }],
    excluded_candidates: [{
      symbol: 'VDST',
      rank: null,
      composite_score: null,
      raw_factors: null,
      normalized_scores: null,
      eligibility_status: 'excluded',
      exclusion_reason: 'instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF',
      basis_date: '2026-04-15',
      draft_id: 'draft-1',
      base_node_id: 'node-1',
      base_symbol: 'AAPL',
      seed_ranking_id: 'etf_ranking_engine_v1',
      seed_methodology_id: 'etf_ranking_methodology_v1',
    }],
    warnings: [],
    unavailable_reason: null,
    lineage: {
      draft_id: 'draft-1',
      workspace_id: 'workspace-1',
      base_node_id: 'node-1',
      base_symbol: 'AAPL',
      candidate_symbol: 'IUFS',
      seed_ranking_id: 'etf_ranking_engine_v1',
      seed_methodology_id: 'etf_ranking_methodology_v1',
      seed_ranking_basis_date: '2026-04-15',
      peer_group: 'Sector UCITS ETF',
      benchmark_symbol: 'SPY',
      lookback_months: 6,
    },
    ...overrides,
  }
}

function makeReplacementRankingPreflightPayload(overrides: Record<string, unknown> = {}) {
  const artifact = makeReplacementRankingPayload()
  return {
    contract_version: 'ranking_artifact_preflight_v1',
    artifact: {
      artifact_kind: 'intent_bound_etf_replacement_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
      ranking_id: artifact.ranking_id,
      methodology_id: artifact.run_metadata.methodology_id,
      as_of_date: artifact.run_metadata.as_of_date,
      ranking_basis_date: artifact.run_metadata.ranking_basis_date,
    },
    eligibility: {
      review_truth_basis: 'authoritative_persisted_ranking_artifact',
      review_scope: 'artifact_backed_review_only',
      open_supported: true,
      replay_eligible: true,
      consumer_handoff_supported: true,
      ineligibility_reason: null,
    },
    open_handoff: {
      handoff_kind: 'ranking_artifact_open_handoff_v1',
      artifact_kind: 'intent_bound_etf_replacement_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
    },
    ...overrides,
  }
}

function makeReplacementRankingOpenPayload(overrides: Record<string, unknown> = {}) {
  const artifact = makeReplacementRankingPayload()
  const preflight = makeReplacementRankingPreflightPayload()
  return {
    contract_version: 'ranking_artifact_open_v1',
    open_handoff: preflight.open_handoff,
    review_payload_kind: 'intent_bound_etf_replacement_ranking_review_payload_v1',
    review_payload: {
      review_payload_kind: 'intent_bound_etf_replacement_ranking_review_payload_v1',
      review_truth_basis: 'authoritative_persisted_ranking_artifact',
      review_scope: 'artifact_backed_review_only',
      artifact_kind: 'intent_bound_etf_replacement_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
      artifact,
    },
    consumer_handoff: {
      contract_version: 'intent_bound_etf_replacement_ranking_consumer_contract_v1',
      handoff_kind: 'intent_bound_etf_replacement_ranking_consumer_handoff_v1',
      artifact_kind: 'intent_bound_etf_replacement_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
      ranking_id: artifact.ranking_id,
      methodology_id: artifact.methodology_id,
      basis_date: artifact.basis_date,
      draft_id: artifact.lineage.draft_id,
      workspace_id: artifact.lineage.workspace_id,
      base_node_id: artifact.lineage.base_node_id,
      base_symbol: artifact.lineage.base_symbol,
      candidate_symbol: artifact.lineage.candidate_symbol,
      seed_ranking_id: artifact.lineage.seed_ranking_id,
      seed_methodology_id: artifact.lineage.seed_methodology_id,
      seed_ranking_basis_date: artifact.lineage.seed_ranking_basis_date,
      peer_group: artifact.lineage.peer_group,
      benchmark_symbol: artifact.lineage.benchmark_symbol,
      lookback_months: artifact.lineage.lookback_months,
      eligible_count: artifact.eligible_count,
      excluded_count: artifact.excluded_count,
      selected_candidate: {
        symbol: 'IUFS',
        rank: 1,
        composite_score: 0.8123,
        basis_date: '2026-04-15',
        draft_id: 'draft-1',
        base_node_id: 'node-1',
        base_symbol: 'AAPL',
        seed_ranking_id: 'etf_ranking_engine_v1',
        seed_methodology_id: 'etf_ranking_methodology_v1',
      },
    },
    ...overrides,
  }
}

function buildReplacementRecentResponse(runs: Array<Record<string, unknown>>) {
  return {
    items: runs.map((run) => ({
      artifact_kind: 'intent_bound_etf_replacement_ranking',
      artifact_id: run.artifact_id,
      ranking_id: run.ranking_id,
      methodology_id: run.methodology_id,
      as_of_date: run.as_of_date,
      ranking_basis_date: run.ranking_basis_date,
      etf_summary: null,
      replacement_summary: {
        basis_date: run.basis_date,
        status: run.status,
        base_symbol: run.base_symbol,
        candidate_symbol: run.candidate_symbol,
        peer_group: run.peer_group,
        eligible_count: run.eligible_count,
        excluded_count: run.excluded_count,
        confidence: run.confidence,
      },
    })),
    metadata: { applied_filters: { artifact_kind: 'intent_bound_etf_replacement_ranking' } },
  }
}

function buildReplacementRecentRun(overrides: Record<string, unknown> = {}) {
  return {
    artifact_id: 'intent_bound_etf_replacement_ranking_artifact_sector_1',
    ranking_id: 'intent_bound_etf_replacement_ranking_engine_v1',
    methodology_id: 'intent_bound_etf_replacement_ranking_methodology_v1',
    as_of_date: '2026-04-15',
    ranking_basis_date: '2026-04-15',
    basis_date: '2026-04-15',
    status: 'ok',
    base_symbol: 'AAPL',
    candidate_symbol: 'IUFS',
    peer_group: 'Sector UCITS ETF',
    eligible_count: 1,
    excluded_count: 1,
    confidence: 'medium',
    ...overrides,
  }
}

function assertReplacementContractState(preflight: Record<string, any>, openPayload?: Record<string, any>) {
  const eligibility = preflight.eligibility
  if (preflight.artifact.artifact_kind !== 'intent_bound_etf_replacement_ranking') {
    throw new Error('Replacement contract fixture must use replacement artifact kind')
  }
  if (eligibility.open_supported !== eligibility.replay_eligible) {
    throw new Error('Replacement preflight eligibility must keep open_supported and replay_eligible aligned')
  }
  if (eligibility.consumer_handoff_supported !== eligibility.open_supported) {
    throw new Error('replacement ranking preflight must keep consumer_handoff_supported aligned with open_supported')
  }
  if (!eligibility.open_supported) {
    if (eligibility.ineligibility_reason == null) {
      throw new Error('Replacement preflight must fail closed with ineligibility_reason')
    }
    if (openPayload) {
      throw new Error('Ineligible replacement preflight must not carry an open payload fixture')
    }
    return
  }
  if (eligibility.ineligibility_reason != null) {
    throw new Error('Eligible replacement preflight must not carry ineligibility_reason')
  }
  if (!openPayload) {
    throw new Error('Eligible replacement preflight must provide an open payload fixture')
  }
  if (openPayload.review_payload.artifact_kind !== 'intent_bound_etf_replacement_ranking') {
    throw new Error('Replacement open payload must keep replacement artifact kind')
  }
  const hasConsumerHandoff = 'consumer_handoff' in openPayload
  if (eligibility.consumer_handoff_supported !== hasConsumerHandoff) {
    throw new Error('Replacement open payload consumer_handoff presence must match preflight support state')
  }
}

function makeEtfRankingOpenPayload(overrides: Record<string, unknown> = {}) {
  const artifact = makeEtfRankingPayload()
  const preflight = makeEtfRankingPreflightPayload()
  return {
    contract_version: 'ranking_artifact_open_v1',
    open_handoff: preflight.open_handoff,
    review_payload_kind: 'etf_ranking_review_payload_v1',
    review_payload: {
      review_payload_kind: 'etf_ranking_review_payload_v1',
      review_truth_basis: 'authoritative_persisted_ranking_artifact',
      review_scope: 'artifact_backed_review_only',
      artifact_kind: 'etf_ranking',
      artifact_id: artifact.artifact_id,
      schema_version: artifact.schema_version,
      artifact,
    },
    ...overrides,
  }
}

function sectorPositionsByName(overview: PortfolioOverview): Record<string, Array<{ symbol: string; market_value: number; weight: number }>> {
  return overview.sector_position_breakdown
}

function mockSavedVariantNode() {
  return {
    id: 'node-2',
    workspaceId: 'workspace-1',
    parentId: 'node-1',
    kind: 'variant' as const,
    name: 'Raise MSFT',
    createdAt: '2026-04-10T00:10:00Z',
    changeSummary: { label: 'Raise MSFT', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: 0, netCapitalDelta: 0 },
    portfolioSnapshot: variantSnapshot,
  }
}

afterEach(() => {
  cleanup()
  delete (window as Window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__
  delete (window as Window & { __TAURI__?: unknown }).__TAURI__
  dashboardPerformanceChartMock.shouldSuspend = false
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('App', () => {
  beforeEach(() => {
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([])
  })

  it('loads the authoritative timeline from monitoring handoff and opens persisted observation review by timeline ids only', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse(makeRecoveredAlertReviewQueuePayload())
      if (pathname === '/api/backtests/monitor-definitions/recent' && method === 'GET') return jsonResponse({ items: [{ monitor_definition_id: 'monitor_definition_abc12345def67890', monitor_id: 'benchmark_trend_overlay_v1' }], metadata: {} })
      if (pathname === '/api/backtests/portfolio-allocation' && method === 'POST') return jsonResponse(allocationBacktestPayload)
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/alert-review-timeline' && method === 'GET') return jsonResponse(makeAlertReviewTimelinePayload())
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/observation' && method === 'GET') return jsonResponse(makeObservationOpenPayload())
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })
    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())
    fireEvent.click(screen.getByText('Run Portfolio Improvement Replay'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Review In Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Review In Workspace' }))
    await waitFor(() => expect(screen.getByText('Opened by timeline ids only: monitor_definition_abc12345def67890 · monitor_definition_observation_abc12345')).toBeTruthy())
    expect(fetchMock).not.toHaveBeenCalledWith('/api/backtests/monitor-definitions/latest-observation-alert-inbox?limit=20')
    expect(fetchMock).toHaveBeenCalledWith('/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/observation')
    expect(fetchMock).toHaveBeenCalledWith('/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/alert-review-timeline')
  })

  it('fails closed when persisted observation open payload mismatches the selected timeline row', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse(makeRecoveredAlertReviewQueuePayload())
      if (pathname === '/api/backtests/monitor-definitions/recent' && method === 'GET') return jsonResponse({ items: [{ monitor_definition_id: 'monitor_definition_abc12345def67890', monitor_id: 'benchmark_trend_overlay_v1' }], metadata: {} })
      if (pathname === '/api/backtests/portfolio-allocation' && method === 'POST') return jsonResponse(allocationBacktestPayload)
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/alert-review-timeline' && method === 'GET') return jsonResponse(makeAlertReviewTimelinePayload())
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/observation' && method === 'GET') return jsonResponse(makeObservationOpenPayload({ observation_id: 'monitor_definition_observation_other' }))
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })
    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())
    fireEvent.click(screen.getByText('Run Portfolio Improvement Replay'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Review In Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Review In Workspace' }))
    await waitFor(() => expect(screen.getByText('Unable to open timeline observation review: persisted observation observation_id does not match selected timeline observation event')).toBeTruthy())
  })

  it('loads the authoritative timeline from monitoring handoff and opens persisted history review by timeline ids only', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse(makeRecoveredAlertReviewQueuePayload())
      if (pathname === '/api/backtests/monitor-definitions/recent' && method === 'GET') return jsonResponse({ items: [{ monitor_definition_id: 'monitor_definition_abc12345def67890', monitor_id: 'benchmark_trend_overlay_v1' }], metadata: {} })
      if (pathname === '/api/backtests/portfolio-allocation' && method === 'POST') return jsonResponse(allocationBacktestPayload)
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/alert-review-timeline' && method === 'GET') return jsonResponse(makeAlertReviewTimelinePayload())
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/evaluation-history/monitor_definition_history_entry_abc12345' && method === 'GET') return jsonResponse(makeEvaluationHistoryEntryPayload())
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })
    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())
    fireEvent.click(screen.getByText('Run Portfolio Improvement Replay'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Review In Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Review In Workspace' }))
    await waitFor(() => expect(screen.getByText('Open history review')).toBeTruthy())
    fireEvent.click(screen.getByText('Open history review'))
    await waitFor(() => expect(screen.getByText('Opened by timeline ids only: monitor_definition_abc12345def67890 · monitor_definition_history_entry_abc12345')).toBeTruthy())
    expect(fetchMock).toHaveBeenCalledWith('/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/evaluation-history/monitor_definition_history_entry_abc12345')
  })

  it('fails closed when persisted history open payload mismatches the selected timeline row', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse(makeRecoveredAlertReviewQueuePayload())
      if (pathname === '/api/backtests/monitor-definitions/recent' && method === 'GET') return jsonResponse({ items: [{ monitor_definition_id: 'monitor_definition_abc12345def67890', monitor_id: 'benchmark_trend_overlay_v1' }], metadata: {} })
      if (pathname === '/api/backtests/portfolio-allocation' && method === 'POST') return jsonResponse(allocationBacktestPayload)
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/alert-review-timeline' && method === 'GET') return jsonResponse(makeAlertReviewTimelinePayload())
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/evaluation-history/monitor_definition_history_entry_abc12345' && method === 'GET') return jsonResponse(makeEvaluationHistoryEntryPayload({ item: { ...makeEvaluationHistoryEntryPayload().item, history_entry_id: 'monitor_definition_history_entry_other' } }))
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })
    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())
    fireEvent.click(screen.getByText('Run Portfolio Improvement Replay'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Review In Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Review In Workspace' }))
    await waitFor(() => expect(screen.getByText('Open history review')).toBeTruthy())
    fireEvent.click(screen.getByText('Open history review'))
    await waitFor(() => expect(screen.getByText('Unable to open timeline history review: persisted history entry history_entry_id does not match selected timeline history event')).toBeTruthy())
  })

  it('loads the shipped alert review timeline payload directly and reopens both review surfaces by authoritative ids only', async () => {
    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/alert-review-timeline' && method === 'GET') return jsonResponse(makeAlertReviewTimelinePayload())
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/observation' && method === 'GET') return jsonResponse(makeObservationOpenPayload())
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/evaluation-history/monitor_definition_history_entry_abc12345' && method === 'GET') return jsonResponse(makeEvaluationHistoryEntryPayload())
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    const timeline = await loadMonitorDefinitionAlertReviewTimeline('monitor_definition_abc12345def67890')
    expect(timeline).toEqual(makeAlertReviewTimelinePayload())
    const observationRow = timeline.items[0] as Parameters<typeof openLatestObservationFromTimelineRow>[0]
    const historyRow = timeline.items[1] as Parameters<typeof openAlertHistoryReviewFromTimelineRow>[0]
    expect(observationRow.open_handoff.observation_id).toBe('monitor_definition_observation_abc12345')
    expect(historyRow.review_handoff.history_entry_id).toBe('monitor_definition_history_entry_abc12345')

    const observationSetState = vi.fn()
    await openLatestObservationFromTimelineRow(observationRow, observationSetState)
    expect(fetchMock).toHaveBeenCalledWith('/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/observation')

    const historySetState = vi.fn()
    await openAlertHistoryReviewFromTimelineRow(historyRow, historySetState)
    expect(fetchMock).toHaveBeenCalledWith('/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/evaluation-history/monitor_definition_history_entry_abc12345')
  })

  it('fails closed on unsupported alert episode contract state in timeline payloads', async () => {
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/alert-review-timeline' && method === 'GET') {
        return jsonResponse(makeAlertReviewTimelinePayload({
          metadata: Object.assign({}, makeAlertReviewTimelinePayload().metadata, {
            latest_alert_episode: Object.assign({}, makeAlertReviewTimelinePayload().metadata.latest_alert_episode, {
              episode_status: 'unsupported',
            }),
          }),
        }))
      }
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    await expect(loadMonitorDefinitionAlertReviewTimeline('monitor_definition_abc12345def67890')).rejects.toThrow(
      'alert review timeline latest_alert_episode episode_status is unsupported',
    )
  })

  it('loads the shipped recovered queue payload directly and reopens the authoritative timeline by persisted ids only', async () => {
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse(makeRecoveredAlertReviewQueuePayload())
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    const queue = await loadMonitorDefinitionRecoveredAlertReviewQueue()
    expect(queue).toEqual(makeRecoveredAlertReviewQueuePayload())

    const beginNavigation = vi.fn().mockResolvedValue(undefined)
    await reopenRecoveredAlertReviewRow(queue.items[0]!, beginNavigation)

    expect(beginNavigation).toHaveBeenCalledWith({
      monitorDefinitionId: 'monitor_definition_abc12345def67890',
      selectedEvent: {
        eventKind: 'latest_observation_event',
        observationId: 'monitor_definition_observation_abc12345',
      },
    })
  })

  it('fails closed on unsupported alert episode contract state in recovered queue payloads', async () => {
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') {
        return jsonResponse(makeRecoveredAlertReviewQueuePayload({
          items: [{
            ...makeRecoveredAlertReviewQueuePayload().items[0],
            alert_episode: {
              ...makeRecoveredAlertReviewQueuePayload().items[0].alert_episode,
              episode_status: 'active',
            },
          }],
        }))
      }
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    await expect(loadMonitorDefinitionRecoveredAlertReviewQueue()).rejects.toThrow(
      'recovered alert review queue row alert_episode episode_status is unsupported',
    )
  })

  it('accepts the shipped alert episode history payload directly for definition-scoped drill-in discovery', () => {
    const payload = makeAlertEpisodeHistoryPayload()
    expect(() => assertMonitorDefinitionAlertEpisodeHistoryResponse(payload, 'monitor_definition_abc12345def67890')).not.toThrow()
    expect(payload.items[0].timeline_handoff.selected_event_kind).toBe('latest_observation_event')
    expect(payload.items[1].timeline_handoff.selected_event_kind).toBe('evaluation_history_event')
  })

  it('accepts the shipped active alert episode inbox payload directly for discovery-only open episode rows', () => {
    const payload = makeActiveAlertEpisodeInboxPayload()
    expect(() => assertMonitorDefinitionActiveAlertEpisodeInboxResponse(payload)).not.toThrow()
    expect(payload.items[0].alert_episode.timeline_handoff.selected_event_kind).toBe('latest_observation_event')
    expect(payload.items[0].alert_episode.latest_contributing_observation.observation_id).toBe('monitor_definition_observation_abc12345')
  })

  it('fails closed on unsupported active alert episode inbox contract state', () => {
    const payload = makeActiveAlertEpisodeInboxPayload({
      items: [{
        ...makeActiveAlertEpisodeInboxPayload().items[0],
        alert_episode: {
          ...makeActiveAlertEpisodeInboxPayload().items[0].alert_episode,
          lifecycle_status: 'recovered',
        },
      }],
    })

    expect(() => assertMonitorDefinitionActiveAlertEpisodeInboxResponse(payload)).toThrow(
      'active alert episode inbox row alert_episode lifecycle_status is unsupported',
    )
  })

  it('fails closed on unsupported alert episode history contract state', () => {
    const payload = makeAlertEpisodeHistoryPayload({
      items: [{
        ...makeAlertEpisodeHistoryPayload().items[0],
        lifecycle_status: 'unsupported',
      }],
    })

    expect(() => assertMonitorDefinitionAlertEpisodeHistoryResponse(payload, 'monitor_definition_abc12345def67890')).toThrow(
      'alert episode history row lifecycle_status is unsupported',
    )
  })

  it('renders the recovered queue from backend payloads and reopens the definition-scoped timeline by authoritative ids', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse(makeRecoveredAlertReviewQueuePayload())
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/alert-review-timeline' && method === 'GET') return jsonResponse(makeAlertReviewTimelinePayload())
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/observation' && method === 'GET') return jsonResponse(makeObservationOpenPayload())
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Recovered Alert Review Queue')).toBeTruthy())
    await waitFor(() => expect(screen.getByRole('button', { name: 'Reopen timeline review' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Reopen timeline review' }))

    await waitFor(() => expect(screen.getByText('Opened by timeline ids only: monitor_definition_abc12345def67890 · monitor_definition_observation_abc12345')).toBeTruthy())
    expect(fetchMock).toHaveBeenCalledWith('/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/alert-review-timeline')
    expect(fetchMock).toHaveBeenCalledWith('/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/observation')
  })

  it('restores cached definition-scoped review state from the authoritative timeline payload', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({
      workspaceId: 'workspace-1',
      activeNodeId: 'node-1',
      activeDraftId: 'draft-1',
      selectedExposureSnapshotId: 'draft',
        monitorDefinitionAlertReview: {
          source: 'definition_scoped_alert_review_timeline',
          monitorDefinitionId: 'monitor_definition_abc12345def67890',
          openedAt: '2026-04-10T00:00:00Z',
        selectedEvent: {
          eventKind: 'latest_observation_event',
          observationId: 'monitor_definition_observation_abc12345',
        },
        cachedTimeline: makeAlertReviewTimelinePayload(),
      },
      lastOpenedAt: '2026-04-10T00:00:00Z',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/observation' && method === 'GET') return jsonResponse(makeObservationOpenPayload())
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Opened by timeline ids only: monitor_definition_abc12345def67890 · monitor_definition_observation_abc12345')).toBeTruthy())
  })

  it('fails closed when definition-scoped alert review restore cannot build the exposure factor model', async () => {
    const malformedDiagnosticsPayload = {
      ...diagnosticsPayload,
      statistical_factor_model: undefined,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({
      workspaceId: 'workspace-1',
      activeNodeId: 'node-1',
      activeDraftId: 'draft-1',
      selectedExposureSnapshotId: 'draft',
      monitorDefinitionAlertReview: {
        source: 'definition_scoped_alert_review_timeline',
        monitorDefinitionId: 'monitor_definition_abc12345def67890',
        openedAt: '2026-04-10T00:00:00Z',
        selectedEvent: {
          eventKind: 'latest_observation_event',
          observationId: 'monitor_definition_observation_abc12345',
        },
        cachedTimeline: makeAlertReviewTimelinePayload(),
      },
      lastOpenedAt: '2026-04-10T00:00:00Z',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/observation' && method === 'GET') return jsonResponse(makeObservationOpenPayload())
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(malformedDiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    await waitFor(() => expect(screen.getByText((content) => content.includes('Unable to restore previous portfolio workspace: definition-scoped alert review analytics require authoritative exposure inputs'))).toBeTruthy())
    expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(0)
    expect(matchingFetchCalls(fetchMock, '/api/engines/dashboard-history/run', 'POST')).toHaveLength(0)
  })

  it('fails closed when definition-scoped alert review restore receives invalid imported diagnostics inputs', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({
      workspaceId: 'workspace-1',
      activeNodeId: 'node-1',
      activeDraftId: 'draft-1',
      selectedExposureSnapshotId: 'draft',
      monitorDefinitionAlertReview: {
        source: 'definition_scoped_alert_review_timeline',
        monitorDefinitionId: 'monitor_definition_abc12345def67890',
        openedAt: '2026-04-10T00:00:00Z',
        selectedEvent: {
          eventKind: 'latest_observation_event',
          observationId: 'monitor_definition_observation_abc12345',
        },
        cachedTimeline: makeAlertReviewTimelinePayload(),
      },
      lastOpenedAt: '2026-04-10T00:00:00Z',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/observation' && method === 'GET') return jsonResponse(makeObservationOpenPayload())
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse({ detail: 'authoritative imported diagnostics payload is malformed' }, 422)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    await waitFor(() => expect(screen.getByText((content) => content.includes('Unable to restore previous portfolio workspace: definition-scoped alert review analytics require authoritative imported diagnostics and dashboard history inputs; authoritative imported diagnostics payload is malformed'))).toBeTruthy())
    expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(0)
    expect(matchingFetchCalls(fetchMock, '/api/engines/dashboard-history/run', 'POST')).toHaveLength(0)
  })

  it('fails closed when definition-scoped alert review restore receives invalid imported dashboard history inputs', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({
      workspaceId: 'workspace-1',
      activeNodeId: 'node-1',
      activeDraftId: 'draft-1',
      selectedExposureSnapshotId: 'draft',
      monitorDefinitionAlertReview: {
        source: 'definition_scoped_alert_review_timeline',
        monitorDefinitionId: 'monitor_definition_abc12345def67890',
        openedAt: '2026-04-10T00:00:00Z',
        selectedEvent: {
          eventKind: 'latest_observation_event',
          observationId: 'monitor_definition_observation_abc12345',
        },
        cachedTimeline: makeAlertReviewTimelinePayload(),
      },
      lastOpenedAt: '2026-04-10T00:00:00Z',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/monitor_definition_abc12345def67890/observation' && method === 'GET') return jsonResponse(makeObservationOpenPayload())
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse({ detail: 'authoritative imported dashboard history payload is malformed' }, 422)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    await waitFor(() => expect(screen.getByText((content) => content.includes('Unable to restore previous portfolio workspace: definition-scoped alert review analytics require authoritative imported diagnostics and dashboard history inputs; authoritative imported dashboard history payload is malformed'))).toBeTruthy())
    expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(0)
    expect(matchingFetchCalls(fetchMock, '/api/engines/dashboard-history/run', 'POST')).toHaveLength(0)
  })

  it('preserves generic analytics fallback behavior outside definition-scoped alert review restore', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({
      workspaceId: 'workspace-1',
      activeNodeId: 'node-1',
      activeDraftId: 'draft-1',
      selectedExposureSnapshotId: 'draft',
      lastOpenedAt: '2026-04-10T00:00:00Z',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse({ detail: 'authoritative imported diagnostics payload is malformed' }, 422)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse({ detail: 'authoritative imported dashboard history payload is malformed' }, 422)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    expect(screen.queryByText(/^Unable to restore previous portfolio workspace/)).toBeNull()
    expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run-imported', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/engines/dashboard-history/run-imported', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/engines/dashboard-history/run', 'POST')).toHaveLength(1)
  })

  it('fails closed when the monitoring handoff reaches workspace without a monitor definition id', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    const importedWorkspace = mockImportedWorkspace()
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    mockImportedWorkspaceRestore(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') return jsonResponse(bootstrapPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/backtests/monitor-definitions/recent' && method === 'GET') return jsonResponse({ items: [] })
      if (pathname === '/api/backtests/portfolio-allocation' && method === 'POST') return jsonResponse(allocationBacktestPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })

    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())
    fireEvent.click(screen.getByText('Run Portfolio Improvement Replay'))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Review In Workspace' })).toBeNull())
    expect(matchingFetchCalls(fetchMock, '/api/backtests/monitor-definitions/recovered-alert-review-queue', 'GET')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/backtests/portfolio-allocation', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/backtests/monitor-definitions/recent', 'GET')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/strategy-lab/ranking-artifacts/recent', 'GET')).toHaveLength(2)
  })

  it('adds a new imported snapshot node from Dashboard Add Statement', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const importedWorkspace = mockImportedWorkspace()
    mockImportedWorkspaceRestore(importedWorkspace)
    const importedSnapshotNode: PortfolioNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026-04-08',
      createdAt: '2026-04-10T00:05:00Z',
      changeSummary: { label: 'IB 2026-04-08', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: 0, netCapitalDelta: 0 },
      portfolioSnapshot: persistedSnapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ['IB2026.pdf'], importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-08', importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-08' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
      },
    }
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([importedWorkspace.rootNode, importedSnapshotNode])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    const saveImportedSnapshotNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveImportedSnapshotNode').mockResolvedValue({
      node: importedSnapshotNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2', updatedAt: '2026-04-10T00:05:00Z' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:05:00Z' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({
        ...importedWorkspace.draft,
        baseNodeId: 'node-2',
        updatedAt: '2026-04-10T00:05:00Z',
      } satisfies WorkingDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const addSnapshotBootstrapPayload = {
      ...bootstrapPayload,
      snapshot: {
        ...bootstrapPayload.snapshot,
        statement: { ...bootstrapPayload.snapshot.statement, statement_period: '2026-01-01 - 2026-04-08' },
        statements: [{ ...bootstrapPayload.snapshot.statements[0], statement_period: '2026-01-01 - 2026-04-08', source_path: 'C:\\docs\\IB2026.pdf', imported_at: '2026-04-10T00:05:00Z', page_count: 17 }],
        positions: bootstrapPayload.snapshot.positions.map((position) => ({ ...position, as_of_date: '2026-04-08' })),
      },
      history_context: { ...bootstrapPayload.history_context, statement_period: '2026-01-01 - 2026-04-08', source_file_names: ['IB2026.pdf'], history_end_date: '2026-04-08' },
    }

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(addSnapshotBootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...appendedExposurePayload, snapshot: { ...appendedExposurePayload.snapshot, statement: { ...appendedExposurePayload.snapshot.statement, statement_period: '2026-01-01 - 2026-04-08' }, statements: [{ ...appendedExposurePayload.snapshot.statements[1], statement_period: '2026-01-01 - 2026-04-08', source_path: 'C:\\docs\\IB2026.pdf' }] } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...appendedDiagnosticsPayload, snapshot: { ...appendedDiagnosticsPayload.snapshot, statement: { ...appendedDiagnosticsPayload.snapshot.statement, statement_period: '2026-01-01 - 2026-04-08' }, statements: [{ ...appendedDiagnosticsPayload.snapshot.statements[1], statement_period: '2026-01-01 - 2026-04-08', source_path: 'C:\\docs\\IB2026.pdf' }] } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    const file2026 = new File(['2026'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })

    fireEvent.change(input, { target: { files: [file2025] } })
    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())

    fireEvent.click(screen.getByText('Add Statement'))
    fireEvent.change(input, { target: { files: [file2026] } })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))

    const appendAnalyzeBody = fetchMock.mock.calls[4]?.[1]?.body as FormData
    const uploadedFiles = appendAnalyzeBody.getAll('statement_files') as File[]
    expect(uploadedFiles.map((file) => file.name)).toEqual(['IB2026.pdf'])
    expect(saveImportedSnapshotNodeSpy).toHaveBeenCalledWith(expect.objectContaining({ workspaceId: 'workspace-1', parentNodeId: 'node-1', importedFileNames: ['IB2026.pdf'], name: 'IB 2026-04-08' }))
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.portfolioSnapshot.importedMeta.sourceFileNames).toContain('IB2026.pdf')
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.portfolioSnapshot.positions.some((position: { symbol: string }) => position.symbol === 'AAPL')).toBe(true)
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.historyContext?.sourceFileNames).toEqual(['IB2025.pdf', 'IB2026.pdf'])
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.historyContext?.historyEndDate).toBe('2026-04-08')
    await waitFor(() => expect(saveImportedSnapshotNodeSpy).toHaveBeenCalled())
  })

  it('restores appended snapshot from persisted state', async () => {
    const importedWorkspace = mockImportedWorkspace()
    const restoredSnapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
        positions.map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const restoredImportedSnapshotNode: PortfolioNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot',
      name: 'IB 2026',
      createdAt: '2026-04-14T00:00:00Z',
      changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
      portfolioSnapshot: restoredSnapshot,
      source: buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
    }
    const restoredDraft: WorkingDraft = {
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-2',
      updatedAt: '2026-04-14T00:00:00Z',
      name: 'Working Draft',
      status: 'clean',
      portfolioSnapshot: restoredSnapshot,
    }
    const restoredWorkspaceState: WorkspaceState = {
      workspaceId: 'workspace-1',
      activeNodeId: 'node-2',
      activeDraftId: 'draft-2',
      selectedExposureSnapshotId: 'draft',
      lastOpenedAt: '2026-04-14T00:00:00Z',
    }
    const transientAppendBootstrapPayload = {
      ...bootstrapPayload,
      snapshot: {
        ...bootstrapPayload.snapshot,
        statement: { ...bootstrapPayload.snapshot.statement, importer: 'freedom24', statement_period: '2026-01-01 - 2026-04-08' },
        statements: [{ ...bootstrapPayload.snapshot.statements[0], importer: 'freedom24', source_path: 'C:\\docs\\FF2026.pdf', statement_period: '2026-01-01 - 2026-04-08', imported_at: '2026-04-10T00:05:00Z' }],
        positions: [
          { ...bootstrapPayload.snapshot.positions[0], symbol: 'JPM', market_value: 5000, quantity: 20, as_of_date: '2026-04-08' },
        ],
      },
      history_context: {
        ...bootstrapPayload.history_context,
        importer: 'freedom24',
        statement_period: '2026-01-01 - 2026-04-08',
        source_file_names: ['FF2026.pdf'],
        history_end_date: '2026-04-08',
      },
    }
    const transientAppendExposurePayload = {
      ...exposurePayload,
      snapshot: {
        ...exposurePayload.snapshot,
        statement: { ...exposurePayload.snapshot.statement, importer: 'freedom24', statement_period: '2026-01-01 - 2026-04-08' },
        statements: [{ ...exposurePayload.snapshot.statements[0], importer: 'freedom24', source_path: 'C:\\docs\\FF2026.pdf', statement_period: '2026-01-01 - 2026-04-08' }],
        positions: [
          { ...exposurePayload.snapshot.positions[0], symbol: 'AAPL', market_value: 10000, quantity: 10 },
          { ...exposurePayload.snapshot.positions[0], symbol: 'JPM', market_value: 5000, quantity: 20 },
        ],
      },
      overview: {
        ...exposurePayload.overview,
        total_market_value: 15000,
        sector_allocation: [
          { sector: 'Technology', market_value: 10000, weight: 2 / 3 },
          { sector: 'Financials', market_value: 5000, weight: 1 / 3 },
        ],
        sector_position_breakdown: {
          Technology: [{ symbol: 'AAPL', market_value: 10000, weight: 2 / 3 }],
          Financials: [{ symbol: 'JPM', market_value: 5000, weight: 1 / 3 }],
        },
      },
    }
    const unavailableHistoryPayload = { performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }

    let restorePhase = false
    let appendedNodePersisted = false
    let appendDraftLookupCount = 0

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockImplementation(async () => (restorePhase ? restoredWorkspaceState : null))
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockImplementation(async () => (restorePhase || appendedNodePersisted ? [importedWorkspace.rootNode, restoredImportedSnapshotNode] : []))
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockImplementation(async () => (restorePhase
      ? { ...importedWorkspace.workspace, activeNodeId: 'node-2', updatedAt: '2026-04-14T00:00:00Z' }
      : importedWorkspace.workspace))
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return restoredImportedSnapshotNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockImplementation(async () => {
      if (restorePhase) return restoredDraft
      appendDraftLookupCount += 1
      return appendDraftLookupCount === 1 ? null : restoredDraft
    })
    const saveImportedSnapshotNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveImportedSnapshotNode').mockImplementation(async () => {
      appendedNodePersisted = true
      return {
        node: restoredImportedSnapshotNode,
        workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2', updatedAt: '2026-04-14T00:00:00Z' },
        workspaceState: restoredWorkspaceState,
      }
    })
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue(restoredWorkspaceState)

    let importedHistoryRunCount = 0
    let exposureRunCount = 0
    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') {
        const uploadedFiles = ((init?.body as FormData | undefined)?.getAll('statement_files') ?? []) as File[]
        if (uploadedFiles.some((file) => file.name === 'IB2025.pdf')) return jsonResponse(bootstrapPayload)
        if (uploadedFiles.some((file) => file.name === 'FF2026.pdf')) return jsonResponse(transientAppendBootstrapPayload)
      }
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') {
        return jsonResponse(restorePhase ? ib2026DiagnosticsPayload : diagnosticsPayload)
      }
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') {
        if (restorePhase) return jsonResponse(ib2026DashboardHistoryPayload)
        importedHistoryRunCount += 1
        return jsonResponse(importedHistoryRunCount === 1 ? dashboardHistoryPayload : unavailableHistoryPayload)
      }
      if (pathname === '/api/engines/exposure/run' && method === 'POST') {
        if (restorePhase) return jsonResponse(ib2026ExposurePayload)
        exposureRunCount += 1
        return jsonResponse(exposureRunCount === 1 ? exposurePayload : transientAppendExposurePayload)
      }
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    const firstRender = render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const baseFile = new File(['ib'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    const appendFile = new File(['ff'], 'FF2026.pdf', { type: 'application/pdf', lastModified: 2 })

    fireEvent.change(input, { target: { files: [baseFile] } })
    await waitFor(() => expect(screen.getByText('Open detailed review')).toBeTruthy())

    fireEvent.click(screen.getByText('Add Statement'))
    fireEvent.change(input, { target: { files: [appendFile] } })

    await waitFor(() => expect(saveImportedSnapshotNodeSpy).toHaveBeenCalled())
    expect(saveImportedSnapshotNodeSpy).toHaveBeenCalledWith(expect.objectContaining({ workspaceId: 'workspace-1', parentNodeId: 'node-1', importedFileNames: ['FF2026.pdf'] }))
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.portfolioSnapshot.importedMeta.sourceFileNames).toContain('FF2026.pdf')
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.portfolioSnapshot.positions.some((position: { symbol: string }) => position.symbol === 'JPM')).toBe(true)

    firstRender.unmount()
    restorePhase = true

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Open detailed review')).toBeTruthy())
    expect(fetchMock).toHaveBeenCalled()
    expect(screen.getByText((content) => content.includes(ib2026DashboardGolden.statementPeriod))).toBeTruthy()
    expect(screen.queryByText('Loaded file: FF2026.pdf')).toBeNull()
    expect(screen.getByText('$62875.19')).toBeTruthy()
    expect(screen.queryByDisplayValue('JPM')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())
  })

  it('uses the Tauri picker path and preserves PDF multipart metadata', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    const createWorkspaceFromImportSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(mockImportedWorkspace())
    const getWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(mockImportedWorkspace().workspace)
    const getNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(mockImportedWorkspace().rootNode)
    const getDraftSpy = vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(mockImportedWorkspace().draft)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') return jsonResponse(bootstrapPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(diagnosticsPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Import Portfolio')).toBeTruthy())

    installTauriRuntime()
    const { open, readFile } = await importTauriPlugins()
    open.mockResolvedValue('D:\\brokerage\\IB2026.pdf')
    readFile.mockResolvedValue(new Uint8Array([50, 48, 50, 54]))

    fireEvent.click(screen.getByText('Import Portfolio'))

    await waitFor(() => expect(createWorkspaceFromImportSpy).toHaveBeenCalledWith(expect.objectContaining({ importedFileNames: ['IB2026.pdf'] })))
    await waitFor(() => expect(getWorkspaceSpy).toHaveBeenCalledWith('workspace-1'))
    expect(getNodeSpy).toHaveBeenCalledWith('node-1')
    expect(getDraftSpy).toHaveBeenCalledWith('workspace-1')

    expect(open).toHaveBeenCalledWith({
      multiple: true,
      directory: false,
      filters: [{ name: 'PDF Statements', extensions: ['pdf'] }],
    })
    expect(readFile).toHaveBeenCalledWith('D:\\brokerage\\IB2026.pdf')
    const analyzeBody = matchingFetchCalls(fetchMock, '/api/portfolios/import/interactive-brokers/analyze-upload', 'POST')[0]?.[1]?.body as FormData
    const uploadedFiles = analyzeBody.getAll('statement_files') as File[]
    expect(uploadedFiles).toHaveLength(1)
    expect(uploadedFiles[0]).toMatchObject({ name: 'IB2026.pdf', type: 'application/pdf' })
  })

  it('fails closed when the Tauri file bridge reads an empty PDF', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const fetchMock = vi.spyOn(globalThis, 'fetch')

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Import Portfolio')).toBeTruthy())

    installTauriRuntime()
    const { open, readFile } = await importTauriPlugins()
    open.mockResolvedValue('D:\\brokerage\\IB2026.pdf')
    readFile.mockResolvedValue(new Uint8Array())

    fireEvent.click(screen.getByText('Import Portfolio'))

    await waitFor(() => expect(screen.getAllByText('Tauri import failed: could not read "IB2026.pdf" because the selected PDF was empty').length).toBeGreaterThan(0))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('maps Tauri analyze-upload network failures to a Tauri import error', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') {
        throw new TypeError('Failed to fetch')
      }
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Import Portfolio')).toBeTruthy())

    installTauriRuntime()
    const { open, readFile } = await importTauriPlugins()
    open.mockResolvedValue('D:\\brokerage\\IB2026.pdf')
    readFile.mockResolvedValue(new Uint8Array([50, 48, 50, 54]))

    fireEvent.click(screen.getByText('Import Portfolio'))

    await waitFor(() => expect(screen.getAllByText('Tauri import failed: unable to reach the local import service while analyzing the selected PDF files').length).toBeGreaterThan(0))
    expect(matchingFetchCalls(fetchMock, '/api/portfolios/import/interactive-brokers/analyze-upload', 'POST')).toHaveLength(1)
  })

  it('times out Tauri analyze-upload requests with a Tauri import error', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const originalSetTimeout = window.setTimeout.bind(window)
    vi.spyOn(window, 'setTimeout').mockImplementation(((handler: TimerHandler, timeout?: number, ...args: unknown[]) => {
      const effectiveTimeout = timeout === 30_000 ? 0 : timeout
      return originalSetTimeout(handler, effectiveTimeout, ...args)
    }) as typeof window.setTimeout)

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') {
        if (init?.signal?.aborted) {
          throw new DOMException('Aborted', 'AbortError')
        }
        return await new Promise<Response>((_, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
        })
      }
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Import Portfolio')).toBeTruthy())

    installTauriRuntime()
    const { open, readFile } = await importTauriPlugins()
    open.mockResolvedValue('D:\\brokerage\\IB2026.pdf')
    readFile.mockResolvedValue(new Uint8Array([50, 48, 50, 54]))

    fireEvent.click(screen.getByText('Import Portfolio'))

    await waitFor(() => expect(screen.getAllByText('Tauri import failed: the local import service timed out while analyzing the selected PDF files').length).toBeGreaterThan(0))
  })

  it('routes the ETF Ranking compatibility tab into the workspace-owned session and keeps Workspace active', async () => {
    const importedWorkspace = mockImportedWorkspace()
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(importedWorkspace.workspaceState)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([importedWorkspace.rootNode])
    mockImportedWorkspaceRestore(importedWorkspace)

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'ETF Ranking' }))

    await waitFor(() => expect(screen.getByText('Embedded ETF Ranking')).toBeTruthy())
    expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page')
  })

  it('shows a no-workspace message for compatibility research entrypoints without firing tool requests', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Backtest' }))
    await waitFor(() => expect(screen.getByTestId('workspace-empty-state')).toBeTruthy())
    expect(screen.getByText('No active workspace is open.')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Strategy Lab' }))
    await waitFor(() => expect(screen.getByTestId('workspace-empty-state')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'ETF Ranking' }))
    await waitFor(() => expect(screen.getByTestId('workspace-empty-state')).toBeTruthy())

    expect(screen.queryByTestId('workspace-research-intent-empty-state')).toBeNull()
    expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page')
    expect(fetchMock).toHaveBeenCalledTimes(0)
  })

  it('routes dashboard detailed review to the generic workspace empty state without backend requests when no workspace exists', async () => {
    vi.resetModules()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    try {
      const mockedDashboardAnalysis = {
        performance_series: [{ date: '2024-01-02', equity: 100000 }],
        daily_states: [],
        source_status: { performance_history: 'available', monthly_returns: 'available' },
      }

      vi.doMock('react', async () => {
        const actualReact = await vi.importActual<typeof import('react')>('react')
        let stateCallCount = 0

        return {
          ...actualReact,
          useEffect: vi.fn(),
          useState: <T,>(initial: T | (() => T)) => {
            const resolvedInitial = typeof initial === 'function'
              ? (initial as () => T)()
              : initial
            const hookIndex = stateCallCount % 39
            stateCallCount += 1

            if (hookIndex === 1) return actualReact.useState(mockedDashboardAnalysis as T)
            if (hookIndex === 18) return actualReact.useState(false as T)
            if (hookIndex === 37) return actualReact.useState('backtest' as T)
            return actualReact.useState(resolvedInitial)
          },
        }
      })

      vi.doMock('../features/portfolio/DashboardPanel', () => ({
        DashboardPanel: ({ onOpenDetailedReview }: { onOpenDetailedReview?: () => void }) => (
          <button type="button" onClick={onOpenDetailedReview}>Open detailed review</button>
        ),
      }))

      const { App: IsolatedApp } = await import('./App')

      render(<IsolatedApp />)

      fireEvent.click(screen.getByRole('button', { name: 'Open detailed review' }))

      await waitFor(() => expect(screen.getByTestId('workspace-empty-state')).toBeTruthy())
      expect(screen.queryByTestId('workspace-research-intent-empty-state')).toBeNull()
      expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page')
      expect(fetchMock).toHaveBeenCalledTimes(0)
    } finally {
      vi.doUnmock('react')
      vi.doUnmock('../features/portfolio/DashboardPanel')
      vi.resetModules()
    }
  })

  it('keeps Strategy Lab reachable from the Workspace research tools', async () => {
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/strategy-lab/cross-sectional-research/recent') {
        return jsonResponse({
          items: [],
          applied_filters: {
            artifact_kind: null,
            schema_version: null,
            methodology_id: null,
            dataset_version: null,
            universe_definition: null,
            benchmark_symbol: null,
            rebalance_date: null,
            as_of_date: null,
            holdout_start_date: null,
          },
          metadata: {
            contract_version: 'cross_sectional_research_discovery_v1',
            metadata_truth: 'authoritative_persisted_artifact_metadata',
            recent_order_basis: 'persisted_artifact.persisted_at_then_artifact_id',
            supported_filters: ['artifact_kind', 'schema_version', 'methodology_id', 'dataset_version', 'universe_definition', 'benchmark_symbol', 'rebalance_date', 'as_of_date', 'holdout_start_date'],
            methodology_metadata_v1_semantics: 'descriptive_only',
            status_metadata_v1_semantics: 'descriptive_only',
            provenance_metadata_v1_semantics: 'descriptive_only',
            applied_filters: {
              artifact_kind: null,
              schema_version: null,
              methodology_id: null,
              dataset_version: null,
              universe_definition: null,
              benchmark_symbol: null,
              rebalance_date: null,
              as_of_date: null,
              holdout_start_date: null,
            },
          },
        })
      }
      throw new Error(`Unhandled fetch ${pathname}`)
    })

    const importedWorkspace = mockImportedWorkspace()
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(importedWorkspace.workspaceState)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([importedWorkspace.rootNode])
    mockImportedWorkspaceRestore(importedWorkspace)

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Open Strategy Lab' }))

    await waitFor(() => expect(screen.getByText('Embedded Strategy Lab')).toBeTruthy())
    expect(screen.getByText('ETF cross-sectional momentum')).toBeTruthy()
  })

  it('shows trend and risk overlays above diagnostics on the diagnostics tab', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } })))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())

    fireEvent.click(screen.getByText('Diagnostics'))

    await waitFor(() => expect(screen.getAllByText('Overlay analysis').length).toBeGreaterThan(0))
    expect(screen.getByText('Trend / Risk Overlays')).toBeTruthy()
    await waitFor(() => expect(screen.getByText('Factor and risk diagnostics')).toBeTruthy())
  })

  it('refreshes dashboard allocation and cards after adding a statement snapshot', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const importedWorkspace = mockImportedWorkspace()
    mockImportedWorkspaceRestore(importedWorkspace)
    const addedSnapshot = {
      ...persistedSnapshot,
      importedMeta: {
        ...persistedSnapshot.importedMeta,
        statementPeriod: '2026-01-01 - 2026-04-08',
        sourceFileNames: ['IB2025.pdf', 'FF2026.pdf'],
      },
      positions: [
        { symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' as const },
        { symbol: 'JPM', marketValue: 5000, quantity: 20, currency: 'USD', sector: 'Financials', sourceType: 'equity' as const },
      ],
      cashBalances: [{ currency: 'USD', amount: 1200 }],
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'FF 2026-04-08',
      createdAt: '2026-04-10T00:05:00Z',
      changeSummary: { label: 'FF 2026-04-08', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: addedSnapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ['FF2026.pdf'], importedAt: '2026-04-10T00:05:00Z', importer: 'freedom24', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-08', importedAt: '2026-04-10T00:05:00Z', importer: 'freedom24', sourceFileNames: ['IB2025.pdf', 'FF2026.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2026-04-08' }, importedHistorySnapshot: null }),
      },
    }
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([importedWorkspace.rootNode, importedSnapshotNode])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveImportedSnapshotNode').mockResolvedValue({
      node: importedSnapshotNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2', updatedAt: '2026-04-10T00:05:00Z' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:05:00Z' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({
        ...importedWorkspace.draft,
        baseNodeId: 'node-2',
        portfolioSnapshot: addedSnapshot,
        updatedAt: '2026-04-10T00:05:00Z',
      })
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const ffBootstrapPayload = {
      ...bootstrapPayload,
      snapshot: {
        ...bootstrapPayload.snapshot,
        statement: { ...bootstrapPayload.snapshot.statement, importer: 'freedom24', statement_period: '2026-01-01 - 2026-04-08' },
        statements: [{ ...bootstrapPayload.snapshot.statements[0], importer: 'freedom24', source_path: 'C:\\docs\\FF2026.pdf', statement_period: '2026-01-01 - 2026-04-08', imported_at: '2026-04-10T00:05:00Z' }],
        positions: [
          { ...bootstrapPayload.snapshot.positions[0], symbol: 'JPM', market_value: 5000, quantity: 20, as_of_date: '2026-04-08' },
        ],
      },
      history_context: {
        ...bootstrapPayload.history_context,
        importer: 'freedom24',
        statement_period: '2026-01-01 - 2026-04-08',
        source_file_names: ['FF2026.pdf'],
        history_end_date: '2026-04-08',
      },
    }

    const ffExposurePayload = {
      ...exposurePayload,
      snapshot: {
        ...exposurePayload.snapshot,
        statement: { ...exposurePayload.snapshot.statement, importer: 'freedom24', statement_period: '2026-01-01 - 2026-04-08' },
        statements: [{ ...exposurePayload.snapshot.statements[0], importer: 'freedom24', source_path: 'C:\\docs\\FF2026.pdf', statement_period: '2026-01-01 - 2026-04-08' }],
        positions: [
          { ...exposurePayload.snapshot.positions[0], symbol: 'AAPL', market_value: 10000, quantity: 10 },
          { ...exposurePayload.snapshot.positions[0], symbol: 'JPM', market_value: 5000, quantity: 20 },
        ],
      },
      overview: {
        ...exposurePayload.overview,
        total_market_value: 15000,
        sector_allocation: [
          { sector: 'Technology', market_value: 10000, weight: 2 / 3 },
          { sector: 'Financials', market_value: 5000, weight: 1 / 3 },
        ],
        sector_position_breakdown: {
          Technology: [{ symbol: 'AAPL', market_value: 10000, weight: 2 / 3 }],
          Financials: [{ symbol: 'JPM', market_value: 5000, weight: 1 / 3 }],
        },
      },
    }

    const unavailableHistoryPayload = { performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ffBootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(unavailableHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ffExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const ibFile = new File(['ib'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    const ffFile = new File(['ff'], 'FF2026.pdf', { type: 'application/pdf', lastModified: 2 })

    fireEvent.change(input, { target: { files: [ibFile] } })
    await waitFor(() => expect(screen.getByText('Open detailed review')).toBeTruthy())
    expect(screen.getByText('Open detailed review')).toBeTruthy()

    fireEvent.click(screen.getByText('Add Statement'))
    fireEvent.change(input, { target: { files: [ffFile] } })

    await waitFor(() => expect(screen.getByText('2026-01-01 - 2026-04-08')).toBeTruthy())
    expect(screen.getAllByText('Loaded file: FF2026.pdf').length).toBeGreaterThan(0)
    expect(screen.queryByText('$15000.00')).toBeNull()
    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Open detailed review' })).toBeTruthy()
  })

  it('restores imported startup draft to Dashboard first and preserves Workspace navigation', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())
    expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy()
    expect(screen.getByText('Restored on launch')).toBeTruthy()
    expect(screen.queryByText('Monitoring')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())
    expect(matchingFetchCalls(fetchMock, '/api/engines/exposure/run', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/engines/dashboard-history/run', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/strategy-lab/ranking-artifacts/recent', 'GET')).toHaveLength(2)
  })

  it('opens persisted construction artifact review from query param on startup', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeConstructionArtifactReplayValidationResponse()))
        .mockResolvedValueOnce(jsonResponse(makeConstructionArtifactReplayResponse()))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(createWorkspaceSpy).toHaveBeenCalledWith(expect.objectContaining({ constructionArtifactId: 'artifact-123' })))
      fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
      expect(createWorkspaceSpy).toHaveBeenCalledTimes(1)
      expect(fetchMock).toHaveBeenCalledTimes(2)
      expect(requestPathname(fetchMock.mock.calls[0]?.[0] as RequestInfo | URL)).toBe('/api/backtests/portfolio-allocation/construction-artifact-validation')
      expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body ?? '{}'))).toEqual({ construction_artifact_id: 'artifact-123' })
      expect(requestPathname(fetchMock.mock.calls[1]?.[0] as RequestInfo | URL)).toBe('/api/backtests/portfolio-allocation/construction-artifact-preview')
      expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body ?? '{}'))).toEqual(makeConstructionArtifactReplayValidationResponse().preview_handoff)
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted construction artifact open when preview handoff kind is unsupported', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(makeConstructionArtifactReplayValidationResponse({
        preview_handoff: {
          ...makeConstructionArtifactReplayValidationResponse().preview_handoff,
          handoff_kind: 'construction_artifact_preview_handoff_v0',
        } as unknown as ConstructionArtifactReplayValidationResponse['preview_handoff'],
      })))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('Unable to open persisted construction artifact review: unsupported preview handoff kind').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted construction artifact open when preview handoff artifact mismatches query artifact', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse(makeConstructionArtifactReplayValidationResponse({
        preview_handoff: {
          ...makeConstructionArtifactReplayValidationResponse().preview_handoff,
          construction_artifact_id: 'artifact-other',
        },
      })))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('Unable to open persisted construction artifact review: preview handoff artifact mismatch').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted construction artifact open when preflight validation fails', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ detail: 'validation failed' }, 400))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('validation failed').length).toBeGreaterThan(0))
      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(requestPathname(fetchMock.mock.calls[0]?.[0] as RequestInfo | URL)).toBe('/api/backtests/portfolio-allocation/construction-artifact-validation')
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted construction artifact open when preview fails after preflight succeeds', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeConstructionArtifactReplayValidationResponse()))
        .mockResolvedValueOnce(jsonResponse({ detail: 'preview failed' }, 400))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('preview failed').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted construction artifact open when preview handoff is missing', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({
        ...makeConstructionArtifactReplayValidationResponse(),
        preview_handoff: undefined,
      }))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('Unable to open persisted construction artifact review: validation response missing preview handoff').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted construction artifact open when preview response launch lineage mismatches review basis', async () => {
    const originalLocation = globalThis.location
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: '?construction_artifact_id=artifact-123' },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeConstructionArtifactReplayValidationResponse()))
        .mockResolvedValueOnce(jsonResponse({
          ...makeConstructionArtifactReplayResponse(),
          review_basis: {
            ...makeConstructionArtifactReplayResponse().review_basis,
            launch_context: {
              ...makeConstructionArtifactReplayResponse().review_basis.launch_context,
              top_n: 3,
            },
          },
        }))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('Unable to open persisted construction artifact review: launch lineage mismatch between review basis and replay provenance').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('restores persisted construction artifact review state on startup', async () => {
    const replay = makeConstructionArtifactReplayResponse()
    const workspace = {
      id: 'workspace-artifact',
      name: 'Construction Artifact artifact-123',
      createdAt: '2026-04-23T00:00:00Z',
      updatedAt: '2026-04-23T00:00:00Z',
      rootNodeId: 'node-artifact',
      activeNodeId: 'node-artifact',
      source: buildArtifactReviewSource('artifact-123', '2026-04-23T00:00:00Z'),
    }
    const node = {
      id: 'node-artifact',
      workspaceId: 'workspace-artifact',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-23T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: {
        basisVersion: 1 as const,
        basisKind: 'persisted_construction_artifact_review' as const,
        reviewScope: 'workspace_review_only' as const,
        canonicalSource: 'typed_preview_handoff' as const,
        basisProvenanceLabel: 'artifact_backed_review_basis' as const,
        portfolioTruth: 'imported_portfolio_snapshot' as const,
        candidateTruth: 'hypothetical_construction_artifact' as const,
        constructionArtifactId: 'artifact-123',
        previewHandoff: makeConstructionArtifactReplayValidationResponse().preview_handoff,
        launchContext: makeConstructionArtifactReplayResponse().review_basis.launch_context,
        openedAt: '2026-04-23T00:00:00Z',
        benchmarkSymbol: 'SPY',
        baseCurrency: 'USD',
        replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
        baselineWeights: [{ symbol: 'AAPL', target_weight: 0.6 }],
        candidateWeights: [{ symbol: 'MSFT', target_weight: 0.6 }],
      },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-artifact', activeNodeId: 'node-artifact', activeDraftId: null, selectedExposureSnapshotId: 'node-artifact', lastOpenedAt: '2026-04-23T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedConstructionArtifactWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-artifact', constructionArtifactId: 'artifact-123', openedAt: '2026-04-23T00:00:00Z', replay })

    render(<App />)

    await waitFor(() => expect(screen.getByTestId('persisted-construction-artifact-banner')).toBeTruthy())
    expect(screen.getAllByText('artifact-123').length).toBeGreaterThan(0)
    expect(screen.queryByText('Proposal')).toBeNull()
    expect(screen.getByText('Review basis: artifact-123')).toBeTruthy()
  })

  it('fails closed when persisted construction artifact review is missing on startup restore', async () => {
    const workspace = {
      id: 'workspace-artifact',
      name: 'Construction Artifact artifact-123',
      createdAt: '2026-04-23T00:00:00Z',
      updatedAt: '2026-04-23T00:00:00Z',
      rootNodeId: 'node-artifact',
      activeNodeId: 'node-artifact',
      source: buildArtifactReviewSource('artifact-123', '2026-04-23T00:00:00Z'),
    }
    const node = {
      id: 'node-artifact',
      workspaceId: 'workspace-artifact',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-23T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: buildArtifactReviewSource('artifact-123', '2026-04-23T00:00:00Z').reviewBasis,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-artifact', activeNodeId: 'node-artifact', activeDraftId: null, selectedExposureSnapshotId: 'node-artifact', lastOpenedAt: '2026-04-23T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedConstructionArtifactWorkspaceReview').mockResolvedValue(null)

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getAllByText('Unable to restore previous portfolio workspace: persisted construction artifact review is missing').length).toBeGreaterThan(0))
  })

  it('opens persisted optimizer handoff review from query param on startup', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff').mockResolvedValue({
        workspace: {
          id: 'workspace-optimizer',
          name: 'Optimizer Handoff optimizer_handoff_123',
          createdAt: '2026-04-24T00:00:00Z',
          updatedAt: '2026-04-24T00:00:00Z',
          rootNodeId: 'node-optimizer',
          activeNodeId: 'node-optimizer',
          source: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
        } as PortfolioWorkspace,
        rootNode: {
          id: 'node-optimizer',
          workspaceId: 'workspace-optimizer',
          parentId: null,
          kind: 'artifact_review_basis',
          name: 'Artifact Review Basis',
          createdAt: '2026-04-24T00:00:00Z',
          changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
          portfolioSnapshot: null,
          artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
        } as PortfolioNode,
        draft: null,
        workspaceState: {
          workspaceId: 'workspace-optimizer',
          activeNodeId: 'node-optimizer',
          activeDraftId: null,
          selectedExposureSnapshotId: 'node-optimizer',
          lastOpenedAt: '2026-04-24T00:00:00Z',
        },
        review: {
          workspaceId: 'workspace-optimizer',
          handoffReference,
          openedAt: '2026-04-24T00:00:00Z',
          validation: makeOptimizerHandoffValidationResponse(),
          replay: makeOptimizerHandoffReplayResponse(),
        },
      })
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse()))
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffReplayResponse()))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(createWorkspaceSpy).toHaveBeenCalledWith(expect.objectContaining({ handoffReference })))
      await waitFor(() => expect(screen.getByTestId('persisted-construction-artifact-banner')).toBeTruthy())
      expect(requestPathname(fetchMock.mock.calls[0]?.[0] as RequestInfo | URL)).toBe('/api/backtests/portfolio-allocation/optimizer-handoff/constraints')
      expect(requestPathname(fetchMock.mock.calls[1]?.[0] as RequestInfo | URL)).toBe('/api/backtests/portfolio-allocation/optimizer-handoff-preview')
      expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body ?? '{}'))).toEqual(makeOptimizerHandoffValidationResponse().replay_handoff)
      expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy()
      expect(screen.getByText('This workspace reopens a hypothetical artifact-backed optimizer review by persisted handoff reference while keeping replay review surfaces intact.')).toBeTruthy()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when validation replay handoff is missing', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse({ replay_handoff: undefined }))))

      render(<App />)

      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('Unable to open persisted optimizer handoff review: validation response missing replay handoff').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when validation replay handoff reference mismatches query reference', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse({
        replay_handoff: {
          ...makeOptimizerHandoffValidationResponse().replay_handoff!,
          handoff_reference: {
            ...handoffReference,
            artifact_id: 'optimizer_artifact_other',
          },
        },
      }))))

      render(<App />)

      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('Unable to open persisted optimizer handoff review: replay handoff reference mismatch').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when validation is blocked', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse({ validation_status: 'blocked', blocking_rule_ids: ['persisted_payload_accessible'] }))))

      render(<App />)

      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('Unable to open persisted optimizer handoff review: validation blocked').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when validation handoff mismatches query reference', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse({ handoff_id: 'optimizer_handoff_other' }))))

      render(<App />)

      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('Unable to open persisted optimizer handoff review: validation handoff mismatch').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when validation artifact mismatches query reference', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse({ artifact_id: 'optimizer_artifact_other' }))))

      render(<App />)

      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('Unable to open persisted optimizer handoff review: validation artifact mismatch').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('allows persisted optimizer handoff open when validation omits artifact id', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff').mockResolvedValue({
        workspace: {
          id: 'workspace-optimizer',
          name: 'Optimizer Handoff optimizer_handoff_123',
          createdAt: '2026-04-24T00:00:00Z',
          updatedAt: '2026-04-24T00:00:00Z',
          rootNodeId: 'node-optimizer',
          activeNodeId: 'node-optimizer',
          source: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
        } as PortfolioWorkspace,
        rootNode: {
          id: 'node-optimizer',
          workspaceId: 'workspace-optimizer',
          parentId: null,
          kind: 'artifact_review_basis',
          name: 'Artifact Review Basis',
          createdAt: '2026-04-24T00:00:00Z',
          changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
          portfolioSnapshot: null,
          artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
        } as PortfolioNode,
        draft: null,
        workspaceState: { workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' },
        review: {
          workspaceId: 'workspace-optimizer',
          handoffReference,
          openedAt: '2026-04-24T00:00:00Z',
          validation: makeOptimizerHandoffValidationResponse({ artifact_id: null }),
          replay: makeOptimizerHandoffReplayResponse(),
        },
      })
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse({ artifact_id: null })))
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffReplayResponse()))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      await waitFor(() => expect(createWorkspaceSpy).toHaveBeenCalled())
      expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when replay artifact mismatches query reference', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse()))
        .mockResolvedValueOnce(jsonResponse({ ...makeOptimizerHandoffReplayResponse(), artifact_id: 'optimizer_artifact_other' }))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('Unable to open persisted optimizer handoff review: replay artifact mismatch').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('stops persisted optimizer handoff open when replay omits the canonical objective block', async () => {
    const originalLocation = globalThis.location
    const handoffReference = makeOptimizerHandoffReference()
    try {
      Object.defineProperty(globalThis, 'location', {
        value: { ...originalLocation, search: `?optimizer_handoff_reference=${encodeURIComponent(JSON.stringify(handoffReference))}` },
        configurable: true,
      })

      vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
      const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedOptimizerHandoff')
      const fetchMock = vi.fn()
        .mockResolvedValueOnce(jsonResponse(makeOptimizerHandoffValidationResponse()))
        .mockResolvedValueOnce(jsonResponse({
          ...makeOptimizerHandoffReplayResponse(),
          optimizer_context: {
            ...makeOptimizerHandoffReplayResponse().optimizer_context!,
            objective: null,
          },
        }))
      vi.stubGlobal('fetch', fetchMock)

      render(<App />)

      fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
      await waitFor(() => expect(screen.getAllByText('Unable to open persisted optimizer handoff review: replay optimizer objective missing').length).toBeGreaterThan(0))
      expect(createWorkspaceSpy).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(globalThis, 'location', { value: originalLocation, configurable: true })
    }
  })

  it('restores persisted optimizer handoff review state on startup', async () => {
    const handoffReference = makeOptimizerHandoffReference()
    const replay = makeOptimizerHandoffReplayResponse()
    const validation = makeOptimizerHandoffValidationResponse()
    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
    }
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'normalizeLegacyPersistedOptimizerHandoffWorkspaceCache').mockResolvedValue({
      workspace: workspace as PortfolioWorkspace,
      node: {
        ...node,
        artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
      } as PortfolioNode,
      review: { workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedOptimizerHandoffWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay })

    render(<App />)

    await waitFor(() => expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy())
    expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy()
    expect(screen.getByText('Optimizer Handoff Review Replay')).toBeTruthy()
  })

  it('fails closed when restored persisted optimizer workspace is missing its authoritative persisted review row', async () => {
    const handoffReference = makeOptimizerHandoffReference()
    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
    }
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    const normalizeSpy = vi.spyOn(portfolioWorkspaceStorage, 'normalizeLegacyPersistedOptimizerHandoffWorkspaceCache')
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedOptimizerHandoffWorkspaceReview').mockResolvedValue(null)

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getAllByText('Unable to restore previous portfolio workspace: persisted optimizer handoff review is missing').length).toBeGreaterThan(0))
    expect(normalizeSpy).not.toHaveBeenCalled()
  })

  it('fails closed when restored persisted optimizer workspace source conflicts with handoffReference identity', async () => {
    const handoffReference = makeOptimizerHandoffReference()
    const validation = makeOptimizerHandoffValidationResponse()
    const replay = makeOptimizerHandoffReplayResponse()
    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: {
        ...buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
        handoffId: 'optimizer_handoff_other',
      },
    }
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedOptimizerHandoffWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace')).toBeTruthy())
  })

  it('fails closed when restored persisted optimizer workspace has a malformed cached reviewBasis envelope', async () => {
    const handoffReference = makeOptimizerHandoffReference()
    const validation = makeOptimizerHandoffValidationResponse()
    const replay = makeOptimizerHandoffReplayResponse()
    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: {
        ...buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
        reviewBasis: {
          ...buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
          basisKind: 'persisted_construction_artifact_review',
        },
      },
    }
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedOptimizerHandoffWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace')).toBeTruthy())
  })

  it('restores persisted optimizer handoff review state when cached reviewBasis is missing as a documented legacy case', async () => {
    const handoffReference = makeOptimizerHandoffReference()
    const replay = makeOptimizerHandoffReplayResponse()
    const validation = makeOptimizerHandoffValidationResponse()
    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: {
        kind: 'persisted_optimizer_handoff' as const,
        handoffReference,
        openedAt: '2026-04-24T00:00:00Z',
      },
    }
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: null,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-optimizer', activeNodeId: 'node-optimizer', activeDraftId: null, selectedExposureSnapshotId: 'node-optimizer', lastOpenedAt: '2026-04-24T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'normalizeLegacyPersistedOptimizerHandoffWorkspaceCache').mockResolvedValue({
      workspace: {
        ...workspace,
        source: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z'),
      } as PortfolioWorkspace,
      node: {
        ...node,
        artifactReviewBasis: buildOptimizerHandoffReviewSource(handoffReference, '2026-04-24T00:00:00Z').reviewBasis,
      } as PortfolioNode,
      review: { workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedOptimizerHandoffWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-optimizer', handoffReference, openedAt: '2026-04-24T00:00:00Z', validation, replay })

    render(<App />)

    await waitFor(() => expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy())
    expect(screen.getByText('Review basis: optimizer_handoff_123')).toBeTruthy()
    expect(screen.getByText('Optimizer Handoff Review Replay')).toBeTruthy()
  })

  it('normalizes legacy cached artifact review workspaces during restore', async () => {
    const replay = makeConstructionArtifactReplayResponse()
    const workspace = {
      id: 'workspace-artifact',
      name: 'Construction Artifact artifact-123',
      createdAt: '2026-04-23T00:00:00Z',
      updatedAt: '2026-04-23T00:00:00Z',
      rootNodeId: 'node-artifact',
      activeNodeId: 'node-artifact',
      source: {
        kind: 'persisted_construction_artifact' as const,
        constructionArtifactId: 'artifact-123',
        openedAt: '2026-04-23T00:00:00Z',
      },
    }
    const node = {
      id: 'node-artifact',
      workspaceId: 'workspace-artifact',
      parentId: null,
      kind: 'artifact_review_basis' as const,
      name: 'Artifact Review Basis',
      createdAt: '2026-04-23T00:00:00Z',
      changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
        artifactReviewBasis: {
          basisVersion: 1 as const,
          basisKind: 'persisted_construction_artifact_review' as const,
          reviewScope: 'workspace_review_only' as const,
          canonicalSource: 'typed_preview_handoff' as const,
          basisProvenanceLabel: 'artifact_backed_review_basis' as const,
          portfolioTruth: 'imported_portfolio_snapshot' as const,
          candidateTruth: 'hypothetical_construction_artifact' as const,
          constructionArtifactId: 'artifact-123',
          previewHandoff: makeConstructionArtifactReplayValidationResponse().preview_handoff,
          openedAt: '2026-04-23T00:00:00Z',
          benchmarkSymbol: 'SPY',
        baseCurrency: 'USD',
        replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
        baselineWeights: [{ symbol: 'AAPL', target_weight: 0.6 }],
        candidateWeights: [{ symbol: 'MSFT', target_weight: 0.6 }],
      },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-artifact', activeNodeId: 'node-artifact', activeDraftId: null, selectedExposureSnapshotId: 'node-artifact', lastOpenedAt: '2026-04-23T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace as PortfolioWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([node as PortfolioNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(node as PortfolioNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getPersistedConstructionArtifactWorkspaceReview').mockResolvedValue({ workspaceId: 'workspace-artifact', constructionArtifactId: 'artifact-123', openedAt: '2026-04-23T00:00:00Z', replay })
    const normalizeSpy = vi.spyOn(portfolioWorkspaceStorage, 'normalizeLegacyPersistedConstructionArtifactWorkspaceCache').mockResolvedValue({
      workspace: {
        ...workspace,
        source: buildArtifactReviewSource('artifact-123', '2026-04-23T00:00:00Z'),
      },
      node: {
        id: 'node-artifact',
        workspaceId: 'workspace-artifact',
        parentId: null,
        kind: 'artifact_review_basis' as const,
        name: 'Artifact Review Basis',
        createdAt: '2026-04-23T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
        artifactReviewBasis: buildArtifactReviewSource('artifact-123', '2026-04-23T00:00:00Z').reviewBasis,
      },
      review: { workspaceId: 'workspace-artifact', constructionArtifactId: 'artifact-123', openedAt: '2026-04-23T00:00:00Z', replay },
    })

    render(<App />)

    await waitFor(() => expect(normalizeSpy).toHaveBeenCalled())
    expect(screen.getByTestId('persisted-construction-artifact-banner')).toBeTruthy()
  })

  it('restores IB2026 dashboard values consistently from persisted imported state', async () => {
    const snapshot = {
      snapshotVersion: 1 as const,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers' as const,
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: ib2026MutableOverview.sector_allocation.flatMap((sector) =>
        (sectorPositionsByName(ib2026MutableOverview)[sector.sector] ?? []).map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector: sector.sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'IB 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 }, portfolioSnapshot: snapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-14T00:00:00Z', updatedAt: '2026-04-14T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'IB 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 }, portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-14T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026DiagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026DashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026ExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('$62875.19')).toBeTruthy())
    const ib2026DetailedReviewButton = screen.queryByRole('button', { name: 'Open detailed review' })
    if (ib2026DetailedReviewButton) {
      fireEvent.click(ib2026DetailedReviewButton)
      await waitFor(() => expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page'))
    }
    expect(screen.queryByRole('button', { name: 'Open detailed review' })).toBeNull()
    await waitFor(() => expect(screen.getByText('Portfolio Research Workspace')).toBeTruthy())
  })

  it('opens persisted construction artifact review from ETF ranking construction handoff in workspace candidate idea', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const createWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromPersistedConstructionArtifact')

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/strategy-lab/ranking-artifacts/recent' && method === 'GET' && requestSearchParam(input, 'artifact_kind') === 'etf_ranking') {
        return jsonResponse({
          items: [{
            artifact_kind: 'etf_ranking',
            artifact_id: 'etf_ranking_artifact_sector_1',
            ranking_id: 'etf_ranking_engine_v1',
            methodology_id: 'etf_ranking_methodology_v1',
            as_of_date: '2026-04-15',
            ranking_basis_date: '2026-04-15',
            etf_summary: {
              benchmark_symbol: 'SPY',
              lookback_months: 6,
              effective_peer_group: 'Sector UCITS ETF',
              universe_size: 3,
              evaluated_universe_size: 2,
              confidence: 'medium',
            },
            replacement_summary: null,
          }],
          metadata: { applied_filters: { artifact_kind: 'etf_ranking' } },
        })
      }
      if (pathname === '/api/strategy-lab/ranking-artifacts/recent' && method === 'GET' && requestSearchParam(input, 'artifact_kind') === 'intent_bound_etf_replacement_ranking') {
        return jsonResponse(buildReplacementRecentResponse([buildReplacementRecentRun()]))
      }
      if (pathname === '/api/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1' && method === 'POST') {
        return jsonResponse(makeEtfRankingPreflightPayload())
      }
      if (pathname === '/api/strategy-lab/ranking-artifacts/preflight/intent_bound_etf_replacement_ranking_artifact_sector_1' && method === 'POST') {
        return jsonResponse(makeReplacementRankingPreflightPayload())
      }
      if (pathname === '/api/strategy-lab/ranking-artifacts/open' && method === 'POST') {
        const body = requestJsonBody(init)
        if (body?.artifact_kind === 'intent_bound_etf_replacement_ranking') {
          return jsonResponse(makeReplacementRankingOpenPayload())
        }
        return jsonResponse(makeEtfRankingOpenPayload())
      }
      if (pathname === '/api/construction/policies' && method === 'GET') {
        return jsonResponse(makeConstructionPoliciesResponse())
      }
      if (pathname === '/api/construction/ranking-artifacts/preflight/etf_ranking_artifact_sector_1' && method === 'POST') {
        return jsonResponse(makeConstructionRankingArtifactPreflightResponse())
      }
      if (pathname === '/api/construction/ranking-artifacts/preflight/intent_bound_etf_replacement_ranking_artifact_sector_1' && method === 'POST') {
        return jsonResponse(makeReplacementConstructionRankingArtifactPreflightResponse())
      }
      if (pathname === '/api/construction/run' && method === 'POST') {
        expect(requestJsonBody(init).ranked_universe).toBeUndefined()
        expect(requestJsonBody(init).policy).toEqual({ policy_id: 'top_n_equal_weight_v1', top_n: 2 })
        expect(requestJsonBody(init).hard_constraints).toEqual({
          full_investment: true,
          long_only: true,
          eligible_ranked_universe_only: true,
          max_position_weight: 0.6,
          min_position_weight: 0.2,
          max_turnover_weight: 0.1,
          max_trade_intent_count: 3,
        })
        const handoff = requestJsonBody(init).ranking_artifact_handoff
        expect([
          makeConstructionRankingArtifactPreflightResponse().handoff,
          makeReplacementConstructionRankingArtifactPreflightResponse().handoff,
        ]).toContainEqual(handoff)
        if (handoff?.artifact_kind === 'intent_bound_etf_replacement_ranking') {
          return jsonResponse(makeConstructionRunArtifactResponse({
            artifact_id: 'construction_artifact_789',
            normalized_inputs: {
              ranked_universe_artifact_kind: 'intent_bound_etf_replacement_ranking',
              ranked_universe_artifact_id: 'intent_bound_etf_replacement_ranking_artifact_sector_1',
              ranked_universe_artifact_schema_version: 'intent_bound_etf_replacement_ranking_artifact_v1',
              ranking_id: 'intent_bound_etf_replacement_ranking_engine_v1',
              ranking_methodology_id: 'intent_bound_etf_replacement_ranking_methodology_v1',
              ranking_as_of_date: '2026-04-15',
              current_portfolio_artifact_id: 'workspace_current_portfolio_1',
              current_portfolio_as_of_timestamp: '2026-04-10T00:00:00Z',
              top_n: 2,
              policy_id: 'top_n_equal_weight_v1',
              policy_definition_id: 'construction_policy_definition_top_n_equal_weight_v1',
            },
          }))
        }
        return jsonResponse(makeConstructionRunArtifactResponse())
      }
      if (pathname === '/api/backtests/portfolio-allocation/construction-artifact-validation' && method === 'POST') {
        const constructionArtifactId = requestJsonBody(init).construction_artifact_id
        return jsonResponse(makeConstructionArtifactReplayValidationResponse({ construction_artifact_id: constructionArtifactId, preview_handoff: { ...makeConstructionArtifactReplayValidationResponse().preview_handoff, construction_artifact_id: constructionArtifactId } }))
      }
      if (pathname === '/api/backtests/portfolio-allocation/construction-artifact-preview' && method === 'POST') {
        const constructionArtifactId = requestJsonBody(init).construction_artifact_id
        return jsonResponse({
          ...makeConstructionArtifactReplayResponse(),
          construction_artifact_id: constructionArtifactId,
          review_basis: {
            ...makeConstructionArtifactReplayResponse().review_basis,
            construction_artifact_id: constructionArtifactId,
            preview_handoff: { ...makeConstructionArtifactReplayValidationResponse().preview_handoff, construction_artifact_id: constructionArtifactId },
            launch_context: {
              ...makeConstructionArtifactReplayResponse().review_basis.launch_context,
              construction_artifact_id: constructionArtifactId,
            },
          },
          replay_provenance: {
            ...makeConstructionArtifactReplayResponse().replay_provenance,
            construction_artifact_id: constructionArtifactId,
          },
        })
      }
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [], metadata: { contract_version: 'monitor_definition_recovered_alert_review_queue_v1', provenance: 'persisted_latest_observation_with_latest_snapshot_and_prior_alert_history_lineage', row_provenance: 'persisted_monitor_definition_observation_artifact_with_latest_snapshot_and_prior_alert_history_lineage', ordering: 'newest_first_evaluated_at_then_monitor_definition_id_then_observation_id', returned_limit: 20, total_queue_rows: 0 } })
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    await reopenDetailedReviewIfNeeded()
    await screen.findByText('Persisted ETF Ranking Construction')
    await screen.findAllByText('Ready for construction review with Top N Equal Weight v1')
    const etfBrowser = screen.getByTestId('persisted-etf-ranking-construction-browser')
    fireEvent.change(within(etfBrowser).getByLabelText('Min Position Weight (optional)'), { target: { value: '0.2' } })
    fireEvent.change(within(etfBrowser).getByLabelText('Max Turnover Weight (optional)'), { target: { value: '0.1' } })
    fireEvent.change(within(etfBrowser).getByLabelText('Max Trade Intent Count (optional)'), { target: { value: '3' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Open Review' })[0]!)
    await waitFor(() => expect(screen.getByText('Embedded ETF Ranking')).toBeTruthy())
    await waitFor(() => expect(screen.getByText('Source: Recent Artifact')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Back To Workspace' }))
    await screen.findByText('Persisted ETF Ranking Construction')
    fireEvent.change(within(screen.getByTestId('persisted-etf-ranking-construction-browser')).getByLabelText('Min Position Weight (optional)'), { target: { value: '0.2' } })
    fireEvent.change(within(screen.getByTestId('persisted-etf-ranking-construction-browser')).getByLabelText('Max Turnover Weight (optional)'), { target: { value: '0.1' } })
    fireEvent.change(within(screen.getByTestId('persisted-etf-ranking-construction-browser')).getByLabelText('Max Trade Intent Count (optional)'), { target: { value: '3' } })
    fireEvent.click(within(screen.getByTestId('persisted-etf-ranking-construction-browser')).getByRole('button', { name: 'Review In Construction' }))

    await waitFor(() => expect(createWorkspaceSpy).toHaveBeenCalledWith(expect.objectContaining({ constructionArtifactId: 'construction_artifact_456' })))
    expect(matchingFetchCalls(fetchMock, '/api/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/strategy-lab/ranking-artifacts/open', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/construction/ranking-artifacts/preflight/etf_ranking_artifact_sector_1', 'POST')).toHaveLength(3)
    expect(matchingFetchCalls(fetchMock, '/api/construction/run', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/backtests/portfolio-allocation/construction-artifact-validation', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/backtests/portfolio-allocation/construction-artifact-preview', 'POST')).toHaveLength(1)
  })

  it('restores FF2026 dashboard values consistently from persisted imported state', async () => {
    const snapshot = {
      snapshotVersion: 1 as const,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'freedom24' as const,
        statementPeriod: ff2026MutableSnapshot.statement.statement_period,
        importedAt: ff2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ff2026LoadedFiles,
      },
      positions: ff2026MutableOverview.sector_allocation.flatMap((sector) =>
        (sectorPositionsByName(ff2026MutableOverview)[sector.sector] ?? []).map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector: sector.sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ff2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'FF 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'FF 2026', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 3018.96, netCapitalDelta: 3018.96 }, portfolioSnapshot: snapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-14T00:00:00Z', updatedAt: '2026-04-14T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ff2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'freedom24', baseCurrency: 'USD', historyContext: ff2026HistoryContext, importedHistorySnapshot: ff2026BootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'FF 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'FF 2026', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 3018.96, netCapitalDelta: 3018.96 }, portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-14T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(ff2026DiagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ff2026DashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ff2026ExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText(ff2026DashboardGolden.portfolioValue)).toBeTruthy())
    const ff2026DetailedReviewButton = screen.queryByRole('button', { name: 'Open detailed review' })
    if (ff2026DetailedReviewButton) {
      fireEvent.click(ff2026DetailedReviewButton)
      await waitFor(() => expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page'))
    }
    expect(screen.queryByRole('button', { name: 'Open detailed review' })).toBeNull()
    await waitFor(() => expect(screen.getByText('Portfolio Research Workspace')).toBeTruthy())
  })

  it('clears restored import state and persisted session', async () => {
    const clearSpy = vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const saveRankingArtifactSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Clear Imported Session' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    fireEvent.click(screen.getByRole('button', { name: 'Clear Imported Session' }))

    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())
    expect(clearSpy).toHaveBeenCalled()
    expect(screen.queryByText('Clear Imported Session')).toBeNull()
  })

  it('passes imported bootstrap data into the backtest workspace', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    const importedWorkspace = mockImportedWorkspace()
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    mockImportedWorkspaceRestore(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') return jsonResponse(bootstrapPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/backtests/monitor-definitions/recent' && method === 'GET') return jsonResponse({ items: [{ monitor_definition_id: 'monitor_definition_abc12345def67890', monitor_id: 'benchmark_trend_overlay_v1' }], metadata: {} })
      if (pathname === '/api/backtests/portfolio-allocation' && method === 'POST') return jsonResponse(allocationBacktestPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })

    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))

    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())
    expect(screen.getByText('Current Import')).toBeTruthy()
    expect(screen.getAllByText('$50000.00').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByText('Run Portfolio Improvement Replay'))
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/backtests/portfolio-allocation', 'POST')).toHaveLength(1))
  })

  it('opens Workspace from Monitoring with a dismissible handoff banner', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    const importedWorkspace = mockImportedWorkspace()
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    mockImportedWorkspaceRestore(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') return jsonResponse(bootstrapPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/backtests/monitor-definitions/recent' && method === 'GET') return jsonResponse({ items: [{ monitor_definition_id: 'monitor_definition_abc12345def67890', monitor_id: 'benchmark_trend_overlay_v1' }], metadata: {} })
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if (pathname === '/api/backtests/portfolio-allocation' && method === 'POST') return jsonResponse(allocationBacktestPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })

    await waitFor(() => expect(screen.getByText('Open detailed review')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())

    fireEvent.click(screen.getByText('Run Portfolio Improvement Replay'))
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/backtests/portfolio-allocation', 'POST')).toHaveLength(1))

    fireEvent.click(screen.getByRole('button', { name: 'Review In Workspace' }))

    await waitFor(() => expect(screen.getByTestId('monitoring-research-handoff-banner')).toBeTruthy())
    expect(screen.getByText('Monitoring context')).toBeTruthy()
    expect(screen.getByText(/Context:/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    await waitFor(() => expect(screen.queryByTestId('monitoring-research-handoff-banner')).toBeNull())
  })

  it('keeps generic strategy backtests reachable from the Workspace research tools', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        run_id: 'run-1:book_trend_breakout',
        config: {
          strategy: { strategy_id: 'book_trend_breakout', name: 'Book Trend Breakout', description: null, timeframe: 'daily', side: 'long_only', universe: ['ES', 'NQ', 'CL'], parameters: [], tags: [] },
          benchmark_symbol: 'SPY',
          start_date: '2024-01-01',
          end_date: '2024-12-31',
          initial_capital: 100000,
          base_currency: 'USD',
          slippage_bps: 0,
          commission_per_contract: 0,
          rebalance_frequency: 'monthly',
          use_continuous_contracts: false,
          continuous_series: null,
        },
        dataset_info: { ES: { symbol: 'ES', timeframe: 'daily', source: 'fmp', continuous: false, ready: true } },
        trades: [],
        positions: [],
        equity_curve: [],
        total_return_pct: 1,
        annualized_return_pct: 1,
        max_drawdown_pct: -1,
        sharpe_ratio: 1,
        overlay_preview: null,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    const importedWorkspace = mockImportedWorkspace()
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(importedWorkspace.workspaceState)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([importedWorkspace.rootNode])
    mockImportedWorkspaceRestore(importedWorkspace)

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Open Backtest' }))

    await waitFor(() => expect(screen.getByText('Embedded Backtest')).toBeTruthy())
    expect(screen.getByText('Generic strategy backtests')).toBeTruthy()
    expect(screen.queryByText('Project summary')).toBeNull()
    expect(screen.queryByText('Monitoring')).toBeNull()

    fireEvent.click(screen.getByText('Run Backtest'))

    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/backtests/run', 'POST')).toHaveLength(1))
  })

  it('preserves workspace-owned backtest state when re-entering through the compatibility tab', async () => {
    const importedWorkspace = mockImportedWorkspace()
    mockImportedWorkspaceRestore(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({
      workspaceId: importedWorkspace.workspace.id,
      activeNodeId: importedWorkspace.rootNode.id,
      activeDraftId: importedWorkspace.draft.id,
      selectedExposureSnapshotId: 'draft',
      lastOpenedAt: '2026-04-10T00:00:00Z',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([importedWorkspace.rootNode])

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/backtests/run' && method === 'POST') {
        return jsonResponse({
          run_id: 'run-1:book_trend_breakout',
          config: {
            strategy: { strategy_id: 'book_trend_breakout', name: 'Book Trend Breakout', description: null, timeframe: 'daily', side: 'long_only', universe: ['ES'], parameters: [], tags: [] },
            benchmark_symbol: 'SPY',
            start_date: '2024-01-01',
            end_date: '2024-12-31',
            initial_capital: 100000,
            base_currency: 'USD',
            slippage_bps: 0,
            commission_per_contract: 0,
            rebalance_frequency: 'monthly',
            use_continuous_contracts: false,
            continuous_series: null,
          },
          dataset_info: { ES: { symbol: 'ES', timeframe: 'daily', source: 'fmp', continuous: false, ready: true } },
          trades: [],
          positions: [],
          equity_curve: [],
          total_return_pct: 1,
          annualized_return_pct: 1,
          max_drawdown_pct: -1,
          sharpe_ratio: 1,
          overlay_preview: null,
        })
      }
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Open Backtest' }))
    await waitFor(() => expect(screen.getByText('Embedded Backtest')).toBeTruthy())

    fireEvent.change(screen.getAllByDisplayValue('ES,NQ,CL')[0]!, { target: { value: 'YM' } })
    await waitFor(() => expect(screen.getByDisplayValue('YM')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByTestId('workspace-section-research-tools')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Backtest' }))
    await waitFor(() => expect(screen.getAllByDisplayValue('YM').length).toBeGreaterThan(0))
    expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page')

    expect(
      fetchMock.mock.calls.filter(([input, init]) => (
        requestPathname(input) === '/api/backtests/run' && requestMethod(input, init) === 'POST'
      )),
    ).toHaveLength(0)
  })

  it('preserves workspace-owned ETF ranking state when re-entering through the compatibility tab', async () => {
    const importedWorkspace = mockImportedWorkspace()
    mockImportedWorkspaceRestore(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({
      workspaceId: importedWorkspace.workspace.id,
      activeNodeId: importedWorkspace.rootNode.id,
      activeDraftId: importedWorkspace.draft.id,
      selectedExposureSnapshotId: 'draft',
      lastOpenedAt: '2026-04-10T00:00:00Z',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([importedWorkspace.rootNode])

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/strategy-lab/etf-ranking/artifacts/recent/metadata' && method === 'GET') return jsonResponse(makeEtfRankingMetadataPayload())
      if (pathname === '/api/strategy-lab/ranking-artifacts/recent' && method === 'GET') return jsonResponse({
        items: makeEtfRankingRecentRunsPayload().map((run) => ({
          artifact_kind: 'etf_ranking',
          schema_version: 'etf_ranking_artifact_v1',
          metadata: {
            metadata_truth: 'authoritative_persisted_metadata',
            metadata_provenance: 'persisted_artifact_body',
            matched_metadata_provenance: 'persisted_artifact_body',
            recency_same_day_provenance: 'etf_recent_index',
          },
          etf_summary: {
            benchmark_symbol: run.benchmark_symbol,
            lookback_months: run.lookback_months,
            effective_peer_group: run.effective_peer_group,
            universe_size: run.universe_size,
            evaluated_universe_size: run.evaluated_universe_size,
            confidence: run.confidence,
          },
          replacement_summary: null,
          ...run,
        })),
        metadata: {
          contract_version: 'ranking_artifact_discovery_v1',
          metadata_truth: 'authoritative_persisted_metadata',
          supported_metadata_provenance: ['persisted_artifact_body', 'persisted_etf_recent_index'],
          supported_artifact_kinds: ['etf_ranking', 'intent_bound_etf_replacement_ranking'],
          artifact_kind_registry_version: 'ranking_artifact_kind_registry_v1',
          supported_filters: ['artifact_kind', 'effective_peer_group'],
          artifact_kind_registry: [],
          applied_filters: { artifact_kind: 'etf_ranking' },
        },
      })
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Open ETF Ranking' }))
    await waitFor(() => expect(screen.getByText('Embedded ETF Ranking')).toBeTruthy())

    fireEvent.change(screen.getAllByDisplayValue('IUFS,IUHC,VDST,VUAA')[0]!, { target: { value: 'AAA,BBB' } })
    await waitFor(() => expect(screen.getByDisplayValue('AAA,BBB')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByTestId('workspace-section-research-tools')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'ETF Ranking' }))
    await waitFor(() => expect(screen.getAllByDisplayValue('AAA,BBB').length).toBeGreaterThan(0))
    expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page')
  })

  it('seeds an ETF ranking candidate into draft review without mutating the portfolio snapshot', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const saveRankingArtifactSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/strategy-lab/etf-ranking' && method === 'POST') return jsonResponse(makeEtfRankingPayload())
      if (pathname === '/api/strategy-lab/etf-ranking/artifacts/recent/metadata' && method === 'GET') return jsonResponse(makeEtfRankingMetadataPayload())
      if (pathname === '/api/strategy-lab/ranking-artifacts/recent' && method === 'GET') return jsonResponse({
        items: makeEtfRankingRecentRunsPayload().map((run) => ({
          artifact_kind: 'etf_ranking',
          schema_version: 'etf_ranking_artifact_v1',
          metadata: {
            metadata_truth: 'authoritative_persisted_metadata',
            metadata_provenance: 'persisted_artifact_body',
            matched_metadata_provenance: 'persisted_artifact_body',
            recency_same_day_provenance: 'etf_recent_index',
          },
          etf_summary: {
            benchmark_symbol: run.benchmark_symbol,
            lookback_months: run.lookback_months,
            effective_peer_group: run.effective_peer_group,
            universe_size: run.universe_size,
            evaluated_universe_size: run.evaluated_universe_size,
            confidence: run.confidence,
          },
          replacement_summary: null,
          ...run,
        })),
        metadata: {
          contract_version: 'ranking_artifact_discovery_v1',
          metadata_truth: 'authoritative_persisted_metadata',
          supported_metadata_provenance: ['persisted_artifact_body', 'persisted_etf_recent_index'],
          supported_artifact_kinds: ['etf_ranking', 'intent_bound_etf_replacement_ranking'],
          artifact_kind_registry_version: 'ranking_artifact_kind_registry_v1',
          supported_filters: ['artifact_kind', 'effective_peer_group'],
          artifact_kind_registry: [],
          applied_filters: { artifact_kind: 'etf_ranking' },
        },
      })
      if (pathname === '/api/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1' && method === 'POST') return jsonResponse(makeEtfRankingPreflightPayload())
      if (pathname === '/api/strategy-lab/ranking-artifacts/open' && method === 'POST') return jsonResponse(makeEtfRankingOpenPayload())
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'ETF Ranking' }))
    await waitFor(() => expect(screen.getByText('Embedded ETF Ranking')).toBeTruthy())
    fireEvent.click(screen.getByText('Run ETF Ranking'))
    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())

    fireEvent.click(screen.getAllByText('Seed Candidate Draft')[0])
    fireEvent.change(screen.getByLabelText('Incumbent ETF'), { target: { value: 'AAPL' } })
    fireEvent.click(screen.getByText('Create Draft'))

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Seeded Candidate Review')).toBeTruthy())
        expect(saveRankingArtifactSpy).toHaveBeenCalledTimes(1)
    expect(saveRankingArtifactSpy.mock.calls[0]?.[0]).toMatchObject({
      kind: 'intent_bound_seeded_etf_replacement_ranking',
      draftId: 'draft-1',
      workspaceId: 'workspace-1',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
      candidateRank: 1,
      rankingId: 'etf_ranking_engine_v1',
      openHandoff: {
        handoff_kind: 'ranking_artifact_open_handoff_v1',
        artifact_kind: 'etf_ranking',
        artifact_id: 'etf_ranking_artifact_sector_1',
        schema_version: 'etf_ranking_artifact_v1',
      },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Seeded Candidate Review')).toBeTruthy())
    expect(screen.getByText('Ranked Review')).toBeTruthy()
    expect(screen.getByText('Excluded Symbols')).toBeTruthy()
    expect(screen.getByText('VDST')).toBeTruthy()
    expect(screen.getByText('Base: AAPL · Candidate: IUFS · Rank #1')).toBeTruthy()
  })

  it('restores a persisted ETF ranking candidate annotation for the active draft', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-15T00:00:00Z',
        baseSymbol: 'AAPL',
        candidateSymbol: 'IUFS',
        candidateRank: 1,
        peerGroup: 'Sector UCITS ETF',
        benchmarkSymbol: 'SPY',
        lookbackMonths: 6,
        rankingId: 'etf_ranking_engine_v1',
        methodologyId: 'etf_ranking_methodology_v1',
        rankingBasisDate: '2026-04-15',
        confidence: 'medium',
        holdingsSupport: 'mixed',
        requestUniverse: ['AAPL', 'IUFS'],
        evaluatedUniverse: ['IUFS'],
        warningCount: 1,
        excludedSymbolsCount: 0,
      },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue({
      kind: 'intent_bound_seeded_etf_replacement_ranking',
      source: 'etf_ranking',
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      selectedAt: '2026-04-15T00:00:00Z',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
      candidateRank: 1,
      rankingId: 'etf_ranking_engine_v1',
      methodologyId: 'etf_ranking_methodology_v1',
      rankingBasisDate: '2026-04-15',
      openHandoff: {
        handoff_kind: 'ranking_artifact_open_handoff_v1',
        artifact_kind: 'etf_ranking',
        artifact_id: 'etf_ranking_artifact_sector_1',
        schema_version: 'etf_ranking_artifact_v1',
      },
      benchmarkSymbol: 'SPY',
      lookbackMonths: 6,
      peerGroup: 'Sector UCITS ETF',
      confidence: 'medium',
      holdingsSupport: 'mixed',
      requestUniverse: ['AAPL', 'IUFS'],
      evaluatedUniverse: ['IUFS'],
      warnings: ['Implementation-fit support is not complete across the ranked universe.'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF' }],
      selectedCandidate: {
        symbol: 'IUFS',
        rank: 1,
        compositeScore: 0.8123,
        instrument: {
          name: 'ETF',
          assetClass: 'etf',
          sector: 'Financials',
          category: 'Sector UCITS ETF',
          currency: 'USD',
        },
      },
      topCandidate: null,
      runnerUpCandidate: null,
    })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    await waitFor(() => expect(screen.getByText('Ranked Review')).toBeTruthy())
    expect(screen.getByText('Seeded Candidate Review')).toBeTruthy()
    expect(screen.getByText('Base: AAPL · Candidate: IUFS · Rank #1')).toBeTruthy()
    expect(screen.getByText('VDST')).toBeTruthy()
  })

  it('fails closed when restored seeded ranking cache is missing canonical open handoff', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getIntentBoundSeededEtfReplacementRankingDraft').mockRejectedValue(new Error('Persisted seeded ranking review cache is missing or invalid open handoff'))
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace')).toBeTruthy())
  })

  it('fails closed when startup restore targets appended imported node draft but persisted draft is missing', async () => {
    setupAppendedImportedStartupRestoreCase()

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace: persisted draft selected on startup is missing')).toBeTruthy())
  })

  it('fails closed when authoritative nodes omit the restored active node even if a startup draft points back to it', async () => {
    const { importedWorkspace, restoredSnapshot } = setupAppendedImportedStartupRestoreCase()
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-2',
      updatedAt: '2026-04-14T00:00:00Z',
      name: 'Working Draft',
      status: 'clean',
      portfolioSnapshot: restoredSnapshot,
    })
    vi.mocked(portfolioWorkspaceStorage.getWorkspaceNodes).mockResolvedValue([
      {
        id: 'node-1',
        workspaceId: 'workspace-1',
        parentId: null,
        kind: 'imported_base',
        name: 'Base Import',
        createdAt: '2026-04-10T00:00:00Z',
        changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 },
        portfolioSnapshot: persistedSnapshot,
      },
    ])

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace: persisted startup node is missing from authoritative workspace state')).toBeTruthy())
    expect(importedWorkspace.workspace.id).toBe('workspace-1')
  })

  it('fails closed when startup restore selected snapshot targets appended imported node omitted from authoritative workspace nodes', async () => {
    const importedWorkspace = mockImportedWorkspace()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({
      workspaceId: 'workspace-1',
      activeNodeId: 'node-1',
      activeDraftId: 'draft-1',
      selectedExposureSnapshotId: 'node-2',
      lastOpenedAt: '2026-04-14T00:00:00Z',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([importedWorkspace.rootNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(importedWorkspace.workspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(importedWorkspace.rootNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(importedWorkspace.draft)
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace: persisted startup selected snapshot is missing from authoritative workspace state')).toBeTruthy())
  })

  it('fails closed when startup restore cannot read authoritative appended imported workspace nodes', async () => {
    const { restoredSnapshot } = setupAppendedImportedStartupRestoreCase()
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-2',
      updatedAt: '2026-04-14T00:00:00Z',
      name: 'Working Draft',
      status: 'clean',
      portfolioSnapshot: restoredSnapshot,
    })
    vi.mocked(portfolioWorkspaceStorage.getWorkspaceNodes).mockRejectedValue(new Error('IndexedDB unavailable'))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace: authoritative workspace nodes are unavailable on startup')).toBeTruthy())
  })

  it('restores appended imported startup draft when persisted draft matches restored appended node', async () => {
    const { restoredSnapshot, restoredImportedSnapshotNode } = setupAppendedImportedStartupRestoreCase()
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: restoredImportedSnapshotNode.id,
      updatedAt: '2026-04-14T00:00:00Z',
      name: 'Working Draft',
      status: 'clean',
      portfolioSnapshot: restoredSnapshot,
    })

    render(<App />)

    await waitFor(() => expect(screen.getByText('Open detailed review')).toBeTruthy())
    expect(screen.getByText('Clear Imported Session')).toBeTruthy()
    expect(screen.queryByText('Monitoring')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Open detailed review' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page'))
    expect(screen.queryByRole('button', { name: 'Open detailed review' })).toBeNull()
    await waitFor(() => expect(screen.getByText('Portfolio Research Workspace')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Monitoring')).toBeTruthy())
    expect(screen.queryByText('Unable to restore previous portfolio workspace: persisted draft selected on startup is missing')).toBeNull()
  })

  it('fails closed when startup restore targets appended imported node draft but persisted draft id mismatches active draft id', async () => {
    const { restoredSnapshot } = setupAppendedImportedStartupRestoreCase()
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({
      id: 'draft-mismatch',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-2',
      updatedAt: '2026-04-14T00:00:00Z',
      name: 'Working Draft',
      status: 'clean',
      portfolioSnapshot: restoredSnapshot,
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace: persisted draft selected on startup is missing')).toBeTruthy())
  })

  it('fails closed when startup restore targets appended imported node draft but persisted draft base node does not resolve to restored appended node', async () => {
    const { restoredSnapshot } = setupAppendedImportedStartupRestoreCase()
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-1',
      updatedAt: '2026-04-14T00:00:00Z',
      name: 'Working Draft',
      status: 'clean',
      portfolioSnapshot: restoredSnapshot,
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace: persisted draft selected on startup is missing')).toBeTruthy())
  })

  it('fails closed when startup restore targets appended imported node draft and authoritative nodes omit the mismatched draft base node', async () => {
    const { restoredImportedSnapshotNode, restoredSnapshot } = setupAppendedImportedStartupRestoreCase()
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-1',
      updatedAt: '2026-04-14T00:00:00Z',
      name: 'Working Draft',
      status: 'clean',
      portfolioSnapshot: restoredSnapshot,
    })
    vi.mocked(portfolioWorkspaceStorage.getWorkspaceNodes).mockResolvedValue([restoredImportedSnapshotNode])

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to restore previous portfolio workspace: persisted draft selected on startup is missing')).toBeTruthy())
  })

  it('fails closed when proposal artifact restore throws during workspace reopen', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockRejectedValue(new Error('IndexedDB unavailable'))
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to reopen saved proposal: indexedDB unavailable')).toBeTruthy())
    expect(screen.queryByText('Latest Saved Artifact')).toBeNull()
    expect(screen.queryByText('No saved proposal artifact yet.')).toBeNull()
  })

  it('fails closed when restored proposal artifacts deserialize but violate contract during workspace reopen', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockRejectedValue(new Error('Saved proposal is missing authoritative proposalSource'))
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Unable to reopen saved proposal: saved proposal is missing authoritative proposalSource')).toBeTruthy())
    expect(screen.queryByText('Latest Saved Artifact')).toBeNull()
    expect(screen.queryByText('No saved proposal artifact yet.')).toBeNull()
  })

  it('keeps replacement contract fixtures aligned for supported, unsupported, and fail-closed states', () => {
    const supportedPreflight = makeReplacementRankingPreflightPayload()
    const supportedOpen = makeReplacementRankingOpenPayload()
    const ineligiblePreflight = makeReplacementRankingPreflightPayload({
      eligibility: {
        review_truth_basis: 'authoritative_persisted_ranking_artifact',
        review_scope: 'artifact_backed_review_only',
        open_supported: false,
        replay_eligible: false,
        consumer_handoff_supported: false,
        ineligibility_reason: 'replacement ranking artifact is unreplayable',
      },
    })

    expect(() => assertReplacementContractState(supportedPreflight, supportedOpen)).not.toThrow()
    expect(() => assertReplacementContractState(ineligiblePreflight)).not.toThrow()

    expect(() => assertReplacementContractState(makeReplacementRankingPreflightPayload({
      eligibility: {
        review_truth_basis: 'authoritative_persisted_ranking_artifact',
        review_scope: 'artifact_backed_review_only',
        open_supported: true,
        replay_eligible: true,
        consumer_handoff_supported: false,
        ineligibility_reason: null,
      },
    }), supportedOpen)).toThrow('replacement ranking preflight must keep consumer_handoff_supported aligned with open_supported')

    expect(() => assertReplacementContractState(makeReplacementRankingPreflightPayload({
      eligibility: {
        review_truth_basis: 'authoritative_persisted_ranking_artifact',
        review_scope: 'artifact_backed_review_only',
        open_supported: false,
        replay_eligible: true,
        consumer_handoff_supported: false,
        ineligibility_reason: 'ambiguous replacement state',
      },
    }))).toThrow('Replacement preflight eligibility must keep open_supported and replay_eligible aligned')

    expect(() => assertReplacementContractState(makeReplacementRankingPreflightPayload({
      eligibility: {
        review_truth_basis: 'authoritative_persisted_ranking_artifact',
        review_scope: 'artifact_backed_review_only',
        open_supported: false,
        replay_eligible: false,
        consumer_handoff_supported: false,
        ineligibility_reason: null,
      },
    }))).toThrow('Replacement preflight must fail closed with ineligibility_reason')
  })

  it('promotes a seed into a persisted replacement intent and restores it for the same draft', async () => {
    const restoredReplacementIntent = {
      kind: 'etf_replacement_intent' as const,
      source: 'candidate_seed' as const,
      createdAt: '2026-04-15T00:05:00Z',
      draftId: 'draft-1',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-1',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
      seededFromDraftId: 'draft-1',
      seedRankingId: 'etf_ranking_engine_v1',
      seedMethodologyId: 'etf_ranking_methodology_v1',
      seedRankingBasisDate: '2026-04-15',
      peerGroup: 'Sector UCITS ETF',
      benchmarkSymbol: 'SPY',
      lookbackMonths: 6,
      confidence: 'medium' as const,
      holdingsSupport: 'mixed' as const,
      warningCount: 1,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-15T00:00:00Z',
        baseSymbol: 'AAPL',
        candidateSymbol: 'IUFS',
        candidateRank: 1,
        peerGroup: 'Sector UCITS ETF',
        benchmarkSymbol: 'SPY',
        lookbackMonths: 6,
        rankingId: 'etf_ranking_engine_v1',
        methodologyId: 'etf_ranking_methodology_v1',
        rankingBasisDate: '2026-04-15',
        confidence: 'medium',
        holdingsSupport: 'mixed',
        requestUniverse: ['AAPL', 'IUFS'],
        evaluatedUniverse: ['IUFS'],
        warningCount: 1,
        excludedSymbolsCount: 0,
      },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValue(restoredReplacementIntent)
    const saveReplacementIntentSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveReplacementIntentDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    await waitFor(() => expect(screen.getAllByText('Promote to Replacement Intent').length).toBeGreaterThan(0))
    fireEvent.click(screen.getByRole('button', { name: 'Promote to Replacement Intent' }))
    expect(screen.getByText('Create replacement intent')).toBeTruthy()
    fireEvent.click(screen.getByText('Create Intent'))

    expect(saveReplacementIntentSpy).toHaveBeenCalledTimes(1)
    expect(saveReplacementIntentSpy.mock.calls[0]?.[0]).toMatchObject({
      kind: 'etf_replacement_intent',
      source: 'candidate_seed',
      draftId: 'draft-1',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
      seededFromDraftId: 'draft-1',
      seedRankingId: 'etf_ranking_engine_v1',
      seedMethodologyId: 'etf_ranking_methodology_v1',
    })

    cleanup()
    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
        fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Replacement Intent')).toBeTruthy())
    expect(screen.getByText('Draft intent')).toBeTruthy()
    expect(screen.getByText('Draft intent only. This handoff does not change holdings.')).toBeTruthy()
  })

  it('opens the workspace from the replacement intent hypothetical replay action', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(makeReplacementIntent())
    vi.spyOn(portfolioWorkspaceStorage, 'getIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue({
      kind: 'intent_bound_seeded_etf_replacement_ranking',
      source: 'etf_ranking',
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      selectedAt: '2026-04-15T00:00:00Z',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
      candidateRank: 1,
      rankingId: 'etf_ranking_engine_v1',
      methodologyId: 'etf_ranking_methodology_v1',
      rankingBasisDate: '2026-04-15',
      openHandoff: {
        handoff_kind: 'ranking_artifact_open_handoff_v1',
        artifact_kind: 'etf_ranking',
        artifact_id: 'etf_ranking_artifact_sector_1',
        schema_version: 'etf_ranking_artifact_v1',
      },
      benchmarkSymbol: 'SPY',
      lookbackMonths: 6,
      peerGroup: 'Sector UCITS ETF',
      confidence: 'medium',
      holdingsSupport: 'mixed',
      requestUniverse: ['AAPL', 'IUFS'],
      evaluatedUniverse: ['IUFS'],
      warnings: [],
      excludedSymbols: [],
      selectedCandidate: {
        symbol: 'IUFS',
        rank: 1,
        compositeScore: 0.8123,
        instrument: {
          name: 'ETF',
          assetClass: 'etf',
          sector: 'Financials',
          category: 'Sector UCITS ETF',
          currency: 'USD',
        },
      },
      topCandidate: null,
      runnerUpCandidate: null,
    })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
        fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Preview Hypothetical Replay' }).length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByRole('button', { name: 'Preview Hypothetical Replay' })[0])
    expect(screen.getAllByText('Hypothetical Replay').length).toBeGreaterThan(0)
  })

  it('falls back to current seed and replay behavior when ranking artifact persistence is unavailable', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'saveIntentBoundSeededEtfReplacementRankingDraft').mockRejectedValue(new Error('IndexedDB unavailable'))
    const saveReplacementIntentSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveReplacementIntentDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/strategy-lab/etf-ranking' && method === 'POST') return jsonResponse(makeEtfRankingPayload())
      if (pathname === '/api/strategy-lab/etf-ranking/artifacts/recent/metadata' && method === 'GET') return jsonResponse(makeEtfRankingMetadataPayload())
      if (pathname === '/api/strategy-lab/ranking-artifacts/recent' && method === 'GET') return jsonResponse({
        items: makeEtfRankingRecentRunsPayload().map((run) => ({
          artifact_kind: 'etf_ranking',
          schema_version: 'etf_ranking_artifact_v1',
          metadata: {
            metadata_truth: 'authoritative_persisted_metadata',
            metadata_provenance: 'persisted_artifact_body',
            matched_metadata_provenance: 'persisted_artifact_body',
            recency_same_day_provenance: 'etf_recent_index',
          },
          etf_summary: {
            benchmark_symbol: run.benchmark_symbol,
            lookback_months: run.lookback_months,
            effective_peer_group: run.effective_peer_group,
            universe_size: run.universe_size,
            evaluated_universe_size: run.evaluated_universe_size,
            confidence: run.confidence,
          },
          replacement_summary: null,
          ...run,
        })),
        metadata: {
          contract_version: 'ranking_artifact_discovery_v1',
          metadata_truth: 'authoritative_persisted_metadata',
          supported_metadata_provenance: ['persisted_artifact_body', 'persisted_etf_recent_index'],
          supported_artifact_kinds: ['etf_ranking', 'intent_bound_etf_replacement_ranking'],
          artifact_kind_registry_version: 'ranking_artifact_kind_registry_v1',
          supported_filters: ['artifact_kind', 'effective_peer_group'],
          artifact_kind_registry: [],
          applied_filters: { artifact_kind: 'etf_ranking' },
        },
      })
      if (pathname === '/api/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_sector_1' && method === 'POST') return jsonResponse(makeEtfRankingPreflightPayload())
      if (pathname === '/api/strategy-lab/ranking-artifacts/open' && method === 'POST') return jsonResponse(makeEtfRankingOpenPayload())
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'ETF Ranking' }))
    await waitFor(() => expect(screen.getByText('Embedded ETF Ranking')).toBeTruthy())
    fireEvent.click(screen.getByText('Run ETF Ranking'))
    await waitFor(() => expect(screen.getByText('Ranked Universe')).toBeTruthy())
    fireEvent.click(screen.getAllByText('Seed Candidate Draft')[0])
    fireEvent.change(screen.getByLabelText('Incumbent ETF'), { target: { value: 'AAPL' } })
    fireEvent.click(screen.getByText('Create Draft'))

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
        fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Promote to Replacement Intent' }).length).toBeGreaterThan(0))
    fireEvent.click(screen.getByRole('button', { name: 'Promote to Replacement Intent' }))
    fireEvent.click(screen.getByText('Create Intent'))
    expect(saveReplacementIntentSpy).toHaveBeenCalledTimes(1)
  })

  it('persists and restores a hypothetical replay for the same draft intent', async () => {
    const replacementIntent = makeReplacementIntent()
    const hypotheticalReplay = makeHypotheticalReplay()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      replay: hypotheticalReplay,
    })
    vi.spyOn(portfolioWorkspaceStorage, 'saveHypotheticalReplacementReplayDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Replacement Intent')).toBeTruthy())
    expect(screen.getByText('Workflow Spine')).toBeTruthy()
    expect(screen.getAllByText('Candidate Formation').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Construction Rule').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Construction Constraints').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Formed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Constructed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Pass').length).toBeGreaterThan(0)
    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    await waitFor(() => expect(screen.getAllByText('Replay Decision Readout').length).toBeGreaterThan(0))
    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getByText('Replacement Intent')).toBeTruthy()
    expect(screen.getByText('Replay Decision Readout')).toBeTruthy()
    expect(screen.getAllByText('Diagnostics Change').length).toBeGreaterThan(0)
  })

  it('saves a reviewed hypothetical replay as a versioned proposal artifact', async () => {
    const replacementIntent = makeReplacementIntent()
    const hypotheticalReplay = makeHypotheticalReplay()
    const authoritativeSavedProposal = makeSavedProposalArtifact({
      id: 'proposal-save-test',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      reviewSnapshotArtifactId: 'review_snapshot_1234567890abcdef',
    })
    const authoritativeReviewSnapshotArtifact = makeReviewSnapshotArtifactFromProposal(authoritativeSavedProposal)

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      replay: hypotheticalReplay,
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([])
    const fetchMock = installWorkspaceReviewFetchMock(authoritativeReviewSnapshotArtifact)
    const saveProposalSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveProposalArtifact').mockResolvedValue()
    const saveReviewSnapshotArtifactSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveReviewSnapshotArtifact').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Replacement Intent')).toBeTruthy())
    await waitFor(() => expect(screen.getAllByText('Save Proposal v1').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByText('Save Proposal v1')[0])

    await waitFor(() => expect(saveProposalSpy).toHaveBeenCalledTimes(1))
    expect(saveReviewSnapshotArtifactSpy).toHaveBeenCalledTimes(1)
    expect(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots', 'POST')).toHaveLength(1)
    expect(saveReviewSnapshotArtifactSpy.mock.calls[0]?.[0]).toEqual({
      id: authoritativeSavedProposal.id,
      workspaceId: authoritativeSavedProposal.workspaceId,
      reviewSnapshotArtifactId: authoritativeReviewSnapshotArtifact.identity.artifact_id,
      artifact: authoritativeReviewSnapshotArtifact,
    })
    expect(saveReviewSnapshotArtifactSpy.mock.invocationCallOrder[0]).toBeLessThan(saveProposalSpy.mock.invocationCallOrder[0] ?? Number.POSITIVE_INFINITY)
    expect(saveProposalSpy.mock.calls[0]?.[0]).toEqual({
      ...authoritativeSavedProposal,
      proposalCapture: expect.objectContaining({
        capture_kind: 'workspace_review_saved_proposal',
        open_handoff: expect.objectContaining({
          artifact_id: authoritativeReviewSnapshotArtifact.identity.artifact_id,
        }),
      }),
      reviewSnapshotPMSummary: expect.any(Object),
      createdAt: expect.any(String),
    })
    expect(screen.getAllByText('Saved Proposal Review').length).toBeGreaterThan(0)
    expect(screen.getAllByText('v1').length).toBeGreaterThan(0)
    expect(screen.getByText('Latest Saved Artifact')).toBeTruthy()
    expect(screen.getByText('An immutable proposal artifact has been recorded for this workflow. Nothing else is needed right now. Next up: saved-proposal reopen, comparison, or thesis-promotion review.')).toBeTruthy()
    expect(screen.getAllByText('Viewing For Review').length).toBeGreaterThan(0)
  })

  it('fails before persisting a contradictory saved proposal artifact', async () => {
    const replacementIntent = makeReplacementIntent()
    const hypotheticalReplay = makeHypotheticalReplay()
    const authoritativeSavedProposal = makeSavedProposalArtifact({
      id: 'proposal-save-test',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      reviewSnapshotArtifactId: 'review_snapshot_1234567890abcdef',
    })
    const authoritativeReviewSnapshotArtifact = makeReviewSnapshotArtifactFromProposal(authoritativeSavedProposal)

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      replay: hypotheticalReplay,
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'buildSavedProposalArtifact').mockImplementation(() => {
      throw new Error('Saved proposal replayProvenance construction_rule_id does not match reviewSnapshot replay_provenance')
    })
    const saveReviewSnapshotArtifactSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveReviewSnapshotArtifact').mockResolvedValue()
    const saveProposalSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveProposalArtifact').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    const fetchMock = installWorkspaceReviewFetchMock(authoritativeReviewSnapshotArtifact)

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('Save Proposal v1').length).toBeGreaterThan(0))
    fireEvent.click(screen.getAllByText('Save Proposal v1')[0])

    await waitFor(() => expect(saveProposalSpy).not.toHaveBeenCalled())
    expect(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots', 'POST')).toHaveLength(1)
    expect(saveReviewSnapshotArtifactSpy).not.toHaveBeenCalled()
    expect(screen.getByText('Saved proposal replayProvenance construction_rule_id does not match reviewSnapshot replay_provenance')).toBeTruthy()
  })

  it('fails reopen when saved proposal proposalCapture handoff contradicts the open response', async () => {
    const authoritativeProposal = makeSavedProposalArtifact()
    const authoritativeArtifact = makeReviewSnapshotArtifactFromProposal(authoritativeProposal)
    const proposal = {
      ...authoritativeProposal,
      proposalCapture: {
        ...authoritativeProposal.proposalCapture,
        open_handoff: {
          ...authoritativeProposal.proposalCapture.open_handoff,
          reopen_local_mirror: 'contradictory_cached_copy',
        },
      },
    } as VersionedProposalArtifact
    const buildReviewSnapshotOpenHandoffFromProposalSpy = vi
      .spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal')
      .mockResolvedValue(authoritativeArtifact.proposal_capture.open_handoff)
    const familyReviewPayload = makeReviewSnapshotFamilyReviewResponse(proposal, [proposal])
    const familyInboxPayload = makeReviewSnapshotFamilyInboxResponse([proposal])

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([proposal])
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    const fetchMock = installSavedProposalWorkspaceFetchMock({
      familyInboxPayload,
      familyReviewPayloads: {
        [proposal.reviewSnapshotArtifactId!]: familyReviewPayload,
      },
      openPayloads: {
        [proposal.reviewSnapshotArtifactId!]: {
          handoff: authoritativeArtifact.proposal_capture.open_handoff,
          artifact: authoritativeArtifact,
          pm_summary: authoritativeArtifact.pm_summary,
          replay_payload: authoritativeArtifact.source_payload,
        },
      },
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Latest Saved Artifact')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Viewing For Review' }))

    await waitFor(() => expect(buildReviewSnapshotOpenHandoffFromProposalSpy).toHaveBeenCalledWith(proposal))
    expect(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots/family-review', 'POST')).toHaveLength(1)
    expect(requestJsonBody(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots/family-review', 'POST')[0]?.[1])).toEqual({
      handoff: authoritativeArtifact.proposal_capture.open_handoff,
    })
    expect(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots/open', 'POST')).toHaveLength(1)
    expect(requestJsonBody(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots/open', 'POST')[0]?.[1])).toEqual(authoritativeArtifact.proposal_capture.open_handoff)
    await waitFor(() => expect(screen.getByText('Unable to reopen saved proposal: saved proposal proposalCapture open_handoff contradicts review snapshot open handoff')).toBeTruthy())
    expect(screen.queryByText('IndexedDB unavailable')).toBeNull()
  })

  it('fails reopen when saved proposal is missing authoritative proposalCapture', async () => {
    const proposal = {
      ...makeSavedProposalArtifact(),
      proposalCapture: undefined,
    } as unknown as VersionedProposalArtifact

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([proposal])
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))

    await waitFor(() => expect(screen.getByText('Unable to reopen saved proposal: saved proposal proposalCapture is missing')).toBeTruthy())
    expect(screen.queryByText('Latest Saved Artifact')).toBeNull()
  })

  it('restores formed candidate state for the active draft before replay review', async () => {
    const replacementIntent = makeReplacementIntent()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('Construction Rule').length).toBeGreaterThan(0))
    expect(screen.getAllByText('candidate_formation_derived').length).toBeGreaterThan(0)
    expect(screen.getAllByText('candidate_construction_derived').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Formed Candidate').length).toBeGreaterThan(0)
  })

  it('restores the selected construction rule for the active draft and marks mismatched construction stale', async () => {
    const replacementIntent = makeReplacementIntent()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact('fixed_split_50_50_substitution_v2'))
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('fixed_split_50_50_substitution_v2').length).toBeGreaterThan(0))
    expect(screen.getAllByText('Stale').length).toBeGreaterThan(0)
  })

  it('restores construction constraint validation for the active draft and blocks replay when validation is blocked', async () => {
    const replacementIntent = makeReplacementIntent()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(replacementIntent)
    vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue(makeFormedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue(makeConstructedCandidateArtifact() as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(makeConstructionConstraintValidationArtifact('blocked') as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('Construction Constraints').length).toBeGreaterThan(0))
    expect(screen.getByText('Constraint validation blocked the current constructed candidate, so replay remains unavailable. Missing now: a constraint-compliant construction handoff. Unlocks next: the hypothetical replay once constraints pass.')).toBeTruthy()
    expect(screen.getByText('Hypothetical replay cannot run yet. Missing now: passed construction constraints. Unlocks next: the hypothetical replay once constraint validation passes.')).toBeTruthy()
  })

  it('restores saved proposal review UI without needing live draft replay state', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([
      makeSavedProposalArtifact({
        id: 'proposal-1',
        createdAt: '2026-04-16T00:00:00Z',
        versionNumber: 1,
        candidateSymbol: 'IUFS',
        proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      }) as any,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('Saved Proposal Review').length).toBeGreaterThan(0))
    expect(screen.getByText('Latest Saved Artifact')).toBeTruthy()
    expect(screen.getAllByText('Proposal Lineage').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Proposal source: draft_replacement_intent_review_only/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('This proposal is a saved review snapshot, not applied holdings, candidate truth, or live draft state.').length).toBeGreaterThan(0)
  })

  it('restores saved proposal proposalSource display from legacy dual-omission hydration without using draft or replay cache state', async () => {
    const legacyPersistedProposal = makeSavedProposalArtifact({
      id: 'proposal-1',
      createdAt: '2026-04-16T00:00:00Z',
      versionNumber: 1,
      candidateSymbol: 'IUFS',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
    })
    delete (legacyPersistedProposal as { proposalSource?: unknown }).proposalSource
    delete (legacyPersistedProposal.reviewSnapshot.proposal as { proposal_source?: unknown }).proposal_source
    delete (legacyPersistedProposal.proposalCapture.proposal as { proposal_source?: unknown }).proposal_source

    const hydratedLegacyProposal = makeSavedProposalArtifact({
      id: 'proposal-1',
      createdAt: '2026-04-16T00:00:00Z',
      versionNumber: 1,
      candidateSymbol: 'IUFS',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
    })
    hydratedLegacyProposal.proposalCapture.proposal.proposal_source = {
      proposal_source_version: 1,
      proposal_source_kind: 'draft_replacement_intent_review_only',
      proposal_truth: 'review_only_hypothetical_proposal',
      portfolio_truth: 'draft_snapshot_not_applied',
      review_scope: 'proposal_review_context_only',
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue({ kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2099-01-01T00:00:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'ZZZZ', seededFromDraftId: 'draft-1', seedRankingId: 'other-seed', seedMethodologyId: 'other-method', seedRankingBasisDate: '2099-01-01', peerGroup: 'Other', benchmarkSymbol: 'QQQ', lookbackMonths: 3, confidence: 'low', holdingsSupport: 'mixed', warningCount: 9 } as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue({ draftId: 'draft-1', snapshotHash: 'stale', replay: { proposal: { proposal_source: { proposal_source_version: 1, proposal_source_kind: 'draft_replacement_intent_review_only', proposal_truth: 'review_only_hypothetical_proposal', portfolio_truth: 'draft_snapshot_not_applied', review_scope: 'proposal_review_context_only' } } } } as any)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockImplementation(async () => {
      expect(legacyPersistedProposal.proposalSource).toBeUndefined()
      expect(legacyPersistedProposal.reviewSnapshot.proposal.proposal_source).toBeUndefined()
      return [hydratedLegacyProposal as any]
    })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(makeReviewSnapshotArtifactFromProposal(makeSavedProposalArtifact({ id: 'proposal-save-test', candidateSymbol: 'IUFS', proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z' }))), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(makeReviewSnapshotArtifactFromProposal(makeSavedProposalArtifact({ id: 'proposal-save-test', candidateSymbol: 'IUFS', proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z' }))), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(makeReviewSnapshotArtifactFromProposal(makeSavedProposalArtifact({ id: 'proposal-save-test', candidateSymbol: 'IUFS', proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z' }))), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getAllByText('Saved Proposal Review').length).toBeGreaterThan(0))
    expect(screen.getAllByText(/Proposal source: draft_replacement_intent_review_only/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/Proposal source: .*review_only_hypothetical_proposal.*review_only_hypothetical_proposal/)).toBeNull()
  })

  it('reopens an older saved proposal inside the shell in review-only mode', async () => {
    const latestProposal = makeSavedProposalArtifact({
      id: 'proposal-2',
      createdAt: '2026-04-17T00:00:00Z',
      versionNumber: 2,
      candidateSymbol: 'IUIT',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUIT:2026-04-17T00:00:00Z',
    })
    const olderProposal = makeSavedProposalArtifact({
      id: 'proposal-1',
      createdAt: '2026-04-16T00:00:00Z',
      versionNumber: 1,
      candidateSymbol: 'IUFS',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUIT:2026-04-17T00:00:00Z',
    })
    const olderArtifact = makeReviewSnapshotArtifactFromProposal(olderProposal)
    const familyInboxPayload = makeReviewSnapshotFamilyInboxResponse([latestProposal, olderProposal])
    const latestFamilyReview = makeReviewSnapshotFamilyReviewResponse(latestProposal, [latestProposal, olderProposal])
    const olderFamilyReview = makeReviewSnapshotFamilyReviewResponse(olderProposal, [latestProposal, olderProposal])

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([olderProposal as any, latestProposal as any])
    const buildOpenHandoffSpy = vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockResolvedValue({
      handoff_kind: 'review_snapshot_open_handoff_v1',
      artifact_id: olderProposal.reviewSnapshotArtifactId!,
      artifact_kind: 'portfolio_review_snapshot',
      schema_version: 'review_snapshot_artifact_v1',
      consumer_kind: 'saved_hypothetical_replay_proposal',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    const fetchMock = installSavedProposalWorkspaceFetchMock({
      familyInboxPayload,
      familyReviewPayloads: {
        [latestProposal.reviewSnapshotArtifactId!]: latestFamilyReview,
        [olderProposal.reviewSnapshotArtifactId!]: olderFamilyReview,
      },
      openPayloads: {
        [olderProposal.reviewSnapshotArtifactId!]: {
          handoff: {
            handoff_kind: 'review_snapshot_open_handoff_v1',
            artifact_id: olderProposal.reviewSnapshotArtifactId,
            artifact_kind: 'portfolio_review_snapshot',
            schema_version: 'review_snapshot_artifact_v1',
            consumer_kind: 'saved_hypothetical_replay_proposal',
          },
          artifact: olderArtifact,
          pm_summary: olderArtifact.pm_summary,
          replay_payload: olderArtifact.source_payload,
        },
      },
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Latest Saved Artifact')).toBeTruthy())
    expect(screen.getAllByText('AAPL -> IUIT').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: 'Reopen In Workspace' }))

    await waitFor(() => expect(buildOpenHandoffSpy).toHaveBeenCalledWith(olderProposal))
    expect(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots/family-inbox', 'POST')).toHaveLength(2)
    expect(requestJsonBody(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots/family-inbox', 'POST')[0]?.[1])).toEqual({
      workspace_id: olderProposal.workspaceId,
    })
    expect(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots/family-review', 'POST')).toHaveLength(2)
    expect(requestJsonBody(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots/open', 'POST')[0]?.[1])).toEqual(olderProposal.proposalCapture.open_handoff)
    expect(screen.getAllByText('Saved Proposal Review').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Proposal source: draft_replacement_intent_review_only/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('This proposal is a saved review snapshot, not applied holdings, candidate truth, or live draft state.').length).toBeGreaterThan(0)
  })

  it('renders the PM-first saved proposal family inbox from persisted artifacts only', async () => {
    const latestProposal = makeSavedProposalArtifact({
      id: 'proposal-2',
      createdAt: '2026-04-17T00:00:00Z',
      versionNumber: 2,
      candidateSymbol: 'IUFS',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-17T00:00:00Z',
    })
    const olderProposal = makeSavedProposalArtifact({
      id: 'proposal-1',
      createdAt: '2026-04-16T00:00:00Z',
      versionNumber: 1,
      candidateSymbol: 'IUFS',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-17T00:00:00Z',
    })
    const separateFamily = makeSavedProposalArtifact({
      id: 'proposal-3',
      createdAt: '2026-04-15T00:00:00Z',
      versionNumber: 1,
      candidateSymbol: 'IUIT',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUIT:2026-04-15T00:00:00Z',
    })
    const familyInboxPayload = makeReviewSnapshotFamilyInboxResponse([olderProposal, latestProposal, separateFamily])
    const latestFamilyReview = makeReviewSnapshotFamilyReviewResponse(latestProposal, [latestProposal, olderProposal])
    const separateFamilyReview = makeReviewSnapshotFamilyReviewResponse(separateFamily, [separateFamily])

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([olderProposal as any, latestProposal as any, separateFamily as any])
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    const fetchMock = installSavedProposalWorkspaceFetchMock({
      familyInboxPayload,
      familyReviewPayloads: {
        [latestProposal.reviewSnapshotArtifactId!]: latestFamilyReview,
        [separateFamily.reviewSnapshotArtifactId!]: separateFamilyReview,
      },
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))

    await waitFor(() => expect(screen.getByText('Saved Proposal Family Inbox')).toBeTruthy())
    expect(screen.getAllByText('Saved Proposal Family Inbox').length).toBeGreaterThan(0)
    expect(screen.getByText('Persisted families: 2 · provenance: persisted_review_snapshot_artifacts_only')).toBeTruthy()
    expect(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots/family-inbox', 'POST')).toHaveLength(1)
    expect(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots/open', 'POST')).toHaveLength(0)
  })

  it('uses persisted pm_summary as the saved proposal reopen authority even when the local mirror differs', async () => {
    const proposal = makeSavedProposalArtifact()
    proposal.reviewSnapshotPMSummary = {
      ...proposal.reviewSnapshotPMSummary,
      review_basis: {
        ...proposal.reviewSnapshotPMSummary.review_basis,
        benchmark_symbol: 'QQQ',
      },
    }
    const artifact = makeReviewSnapshotArtifactFromProposal(makeSavedProposalArtifact())

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([proposal as any])
    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockResolvedValue({
      handoff_kind: 'review_snapshot_open_handoff_v1',
      artifact_id: proposal.reviewSnapshotArtifactId,
      artifact_kind: 'portfolio_review_snapshot',
      schema_version: 'review_snapshot_artifact_v1',
      consumer_kind: 'saved_hypothetical_replay_proposal',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        handoff: {
          handoff_kind: 'review_snapshot_open_handoff_v1',
          artifact_id: proposal.reviewSnapshotArtifactId,
          artifact_kind: 'portfolio_review_snapshot',
          schema_version: 'review_snapshot_artifact_v1',
          consumer_kind: 'saved_hypothetical_replay_proposal',
        },
        artifact,
        pm_summary: artifact.pm_summary,
        replay_payload: artifact.source_payload,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Latest Saved Artifact')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Viewing For Review' }))

    await waitFor(() => expect(screen.getByText(/Methodology: m/)).toBeTruthy())
    expect(screen.getByText(/benchmark separation: explicit_per_snapshot_benchmark_fields/)).toBeTruthy()
  })

  it('fails reopen clearly when local cached summary conflicts with persisted pm_summary', async () => {
    const proposal = makeSavedProposalArtifact()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([proposal as any])
    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockRejectedValue(new Error('Saved proposal cached reviewSnapshotPMSummary does not match persisted review snapshot artifact pm_summary'))
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Latest Saved Artifact')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Viewing For Review' }))

    await waitFor(() => expect(screen.getByText('Saved proposal cached reviewSnapshotPMSummary does not match persisted review snapshot artifact pm_summary')).toBeTruthy())
    expect(matchingFetchCalls(fetchMock, '/api/backtests/review-snapshots/open', 'POST')).toHaveLength(0)
  })

  it('fails closed when reopen response handoff kind is unsupported', async () => {
    const proposal = makeSavedProposalArtifact()
    const artifact = makeReviewSnapshotArtifactFromProposal(proposal)
    const familyReviewPayload = makeReviewSnapshotFamilyReviewResponse(proposal, [proposal])
    const familyInboxPayload = makeReviewSnapshotFamilyInboxResponse([proposal])

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([proposal as any])
    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockResolvedValue({
      handoff_kind: 'review_snapshot_open_handoff_v1',
      artifact_id: proposal.reviewSnapshotArtifactId!,
      artifact_kind: 'portfolio_review_snapshot',
      schema_version: 'review_snapshot_artifact_v1',
      consumer_kind: 'saved_hypothetical_replay_proposal',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    installSavedProposalWorkspaceFetchMock({
      familyInboxPayload,
      familyReviewPayloads: {
        [proposal.reviewSnapshotArtifactId!]: familyReviewPayload,
      },
      openPayloads: {
        [proposal.reviewSnapshotArtifactId!]: {
          handoff: {
            handoff_kind: 'review_snapshot_open_handoff_v0',
            artifact_id: proposal.reviewSnapshotArtifactId,
            artifact_kind: 'portfolio_review_snapshot',
            schema_version: 'review_snapshot_artifact_v1',
            consumer_kind: 'saved_hypothetical_replay_proposal',
          },
          artifact,
          pm_summary: artifact.pm_summary,
          replay_payload: artifact.source_payload,
        },
      },
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Latest Saved Artifact')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Viewing For Review' }))

    await waitFor(() => expect(screen.getByText('Review snapshot open response handoff has unsupported handoff kind')).toBeTruthy())
  })

  it('fails closed when stored reopen handoff builder returns unsupported kind', async () => {
    const proposal = makeSavedProposalArtifact()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([proposal as any])
    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockResolvedValue({
      handoff_kind: 'review_snapshot_open_handoff_v0',
      artifact_id: proposal.reviewSnapshotArtifactId!,
      artifact_kind: 'portfolio_review_snapshot',
      schema_version: 'review_snapshot_artifact_v1',
      consumer_kind: 'saved_hypothetical_replay_proposal',
    } as any)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Latest Saved Artifact')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Viewing For Review' }))

    await waitFor(() => expect(screen.getByText('Unable to reopen saved proposal: unsupported review snapshot open handoff kind')).toBeTruthy())
  })

  it('fails closed when reopen response contradicts persisted artifact identity', async () => {
    const proposal = makeSavedProposalArtifact()
    const artifact = makeReviewSnapshotArtifactFromProposal(proposal)
    const familyReviewPayload = makeReviewSnapshotFamilyReviewResponse(proposal, [proposal])
    const familyInboxPayload = makeReviewSnapshotFamilyInboxResponse([proposal])
    const contradictoryArtifact = {
      ...artifact,
      identity: {
        ...artifact.identity,
        artifact_id: 'review_snapshot_other',
      },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([proposal as any])
    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockResolvedValue({
      handoff_kind: 'review_snapshot_open_handoff_v1',
      artifact_id: proposal.reviewSnapshotArtifactId!,
      artifact_kind: 'portfolio_review_snapshot',
      schema_version: 'review_snapshot_artifact_v1',
      consumer_kind: 'saved_hypothetical_replay_proposal',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    installSavedProposalWorkspaceFetchMock({
      familyInboxPayload,
      familyReviewPayloads: {
        [proposal.reviewSnapshotArtifactId!]: familyReviewPayload,
      },
      openPayloads: {
        [proposal.reviewSnapshotArtifactId!]: {
          handoff: {
            handoff_kind: 'review_snapshot_open_handoff_v1',
            artifact_id: proposal.reviewSnapshotArtifactId,
            artifact_kind: 'portfolio_review_snapshot',
            schema_version: 'review_snapshot_artifact_v1',
            consumer_kind: 'saved_hypothetical_replay_proposal',
          },
          artifact: contradictoryArtifact,
          pm_summary: artifact.pm_summary,
          replay_payload: artifact.source_payload,
        },
      },
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Latest Saved Artifact')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Viewing For Review' }))

    await waitFor(() => expect(screen.getByText('Review snapshot open response handoff artifact_id does not match persisted artifact identity')).toBeTruthy())
  })

  it('promotes a saved proposal into a restored active thesis and clears it', async () => {
    const latestProposal = makeSavedProposalArtifact({
      id: 'proposal-2',
      createdAt: '2026-04-17T00:00:00Z',
      versionNumber: 2,
      candidateSymbol: 'IUIT',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUIT:2026-04-17T00:00:00Z',
    })

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([latestProposal as any])
    vi.spyOn(portfolioWorkspaceStorage, 'getActiveThesis').mockResolvedValue({ workspaceId: 'workspace-1', promotedAt: '2026-04-17T12:00:00Z', sourceProposalId: 'proposal-2', thesisProposal: latestProposal as any })
    const saveActiveThesisSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveActiveThesis').mockResolvedValue()
    const deleteActiveThesisSpy = vi.spyOn(portfolioWorkspaceStorage, 'deleteActiveThesis').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByText('Active Thesis')).toBeTruthy())
    expect(screen.getAllByText('v2 · AAPL -> IUIT').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByTestId('saved-proposal-promote-proposal-2'))
    await waitFor(() => expect(saveActiveThesisSpy).toHaveBeenCalledTimes(1))
    expect(saveActiveThesisSpy.mock.calls[0]?.[0]).toMatchObject({ workspaceId: 'workspace-1', sourceProposalId: 'proposal-2' })

    fireEvent.click(screen.getByTestId('clear-active-thesis'))
    await waitFor(() => expect(deleteActiveThesisSpy).toHaveBeenCalledWith('workspace-1'))
  })

  it('does not restore an active thesis when the embedded saved proposal artifact is contradictory', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue(makeSelectedConstructionRuleArtifact())
    vi.spyOn(portfolioWorkspaceStorage, 'getReplacementIntentDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getConstructionConstraintValidationArtifact').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'getActiveThesis').mockRejectedValue(new Error('Saved proposal replayProvenance seed_methodology_id does not match reviewSnapshot replay_provenance'))
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.queryByText('Active Thesis')).toBeNull())
  })

  it('clears stale candidate annotation state when the restored draft has no saved annotation', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    expect(screen.queryByText('Seeded Candidate Review')).toBeNull()
  })

  it('does not propagate candidate annotation when a saved variant is the restored active node', async () => {
    const variantNode = mockSavedVariantNode()
    const cleanVariantDraft = { id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: persistedSnapshot }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-2',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return variantNode
      return { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(cleanVariantDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(variantExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    expect(screen.queryByText('Seeded Candidate Review')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Detailed review unavailable here')).toBeTruthy())
  })

  it('does not propagate candidate annotation when reopening a clean variant workspace', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:10:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:10:00Z', rootNodeId: 'node-1', activeNodeId: 'node-2', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }, variantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-2' ? variantNode : null)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:10:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: variantSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:10:00Z' })
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(variantExposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null })
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    expect(screen.queryByText('Seeded Candidate Review')).toBeNull()
  })

  it('treats detailed review handoff as workspace-only navigation for clean imported drafts', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Open detailed review')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Open detailed review' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page'))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    expect(screen.queryByRole('button', { name: 'Discard draft' })).toBeNull()
    expect(screen.queryByText('Detailed review')).toBeNull()
  })

  it('resets the local workspace database from the dashboard', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const resetSpy = vi.spyOn(portfolioWorkspaceStorage, 'resetLocalPortfolioDatabase').mockResolvedValue()

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Reset Local DB')).toBeTruthy())
    fireEvent.click(screen.getByText('Reset Local DB'))

    await waitFor(() => expect(resetSpy).toHaveBeenCalled())
    expect(screen.getByText('Import Portfolio')).toBeTruthy()
  })

  it('keeps the dashboard tab landing-only after importing a portfolio', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const importedWorkspace = mockImportedWorkspace()
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    mockImportedWorkspaceRestore(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2026 = new File(['2026'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })
    fireEvent.change(input, { target: { files: [file2026] } })

    await waitFor(() => expect(screen.getByText('Trusted Portfolio Snapshot')).toBeTruthy())
    expect(screen.queryByText('Project summary')).toBeNull()
    expect(screen.queryByText('Saved Variants')).toBeNull()
    expect(screen.queryByText(/^base · active$/)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Open' })).toBeNull()
    expect(screen.queryByText('Detailed review')).toBeNull()
    expect(screen.queryByRole('button', { name: /support layer/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /draft\/tool layer/i })).toBeNull()

    expect(screen.getByRole('button', { name: 'Replace Import' })).toBeTruthy()

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByText('Look-Through Summary')).toBeTruthy())
    expect(screen.getByText('Concentration Pack')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Trusted Portfolio Snapshot')).toBeTruthy())
    expect(screen.getByRole('button', { name: 'Open detailed review' })).toBeTruthy()
    expect(screen.queryByText('Detailed review')).toBeNull()
    expect(screen.queryByText('Saved Variants')).toBeNull()
  })

  it('keeps the dashboard handoff shell unchanged across import replacement and reset paths', async () => {
    const importedWorkspace = mockImportedWorkspace()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    mockImportedWorkspaceRestore(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'resetLocalPortfolioDatabase').mockResolvedValue()

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const firstFile = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    const replacementFile = new File(['2026'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })

    fireEvent.change(input, { target: { files: [firstFile] } })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Open detailed review' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Open detailed review' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page'))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Replace Import' })).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Replace Import' }))
    fireEvent.change(input, { target: { files: [replacementFile] } })

    await waitFor(() => expect(screen.getByRole('button', { name: 'Open detailed review' })).toBeTruthy())
    expect(screen.queryByText('Saved Variants')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Replace Import' })).toBeTruthy()
    expect(screen.queryByText('Detailed review')).toBeNull()

    expect(screen.getByRole('button', { name: 'Open detailed review' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Reset Local DB' }))

    await waitFor(() => expect(screen.getByText('Import Portfolio')).toBeTruthy())
    expect(screen.queryByText('Saved Variants')).toBeNull()
  })

  it('routes import to dashboard then workspace through the detailed-review handoff', async () => {
    const importedWorkspace = mockImportedWorkspace()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    mockImportedWorkspaceRestore(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })

    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => expect(screen.getByText('Trusted Portfolio Snapshot')).toBeTruthy())
    expect(screen.getByRole('button', { name: 'Dashboard' }).getAttribute('aria-current')).toBe('page')
    fireEvent.click(screen.getByRole('button', { name: 'Open detailed review' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page'))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
  })

  it('routes imported drafts to Workspace without legacy variant controls', async () => {
    const importedWorkspace = mockImportedWorkspace()
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    mockImportedWorkspaceRestore(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()
    const saveVariantFromDraftSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveVariantFromDraft').mockResolvedValue({
      node: variantNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return variantNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({
      ...importedWorkspace.draft,
      baseNodeId: 'node-2',
      status: 'clean',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockImplementation(async () => [importedWorkspace.rootNode, variantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:10:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })

    await waitFor(() => expect(screen.getByText('Open detailed review')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Open detailed review' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())

    expect(screen.queryByPlaceholderText('Variant name')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Save Variant' })).toBeNull()
    expect(screen.queryByText('Saved Variants')).toBeNull()
    expect(saveVariantFromDraftSpy).not.toHaveBeenCalled()
  })

  it('shows saved variant lineage in Exposure without legacy open controls', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })

    const variantNode = mockSavedVariantNode()
    const baseDraft = {
      id: 'draft-1',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-1',
      updatedAt: '2026-04-10T00:00:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: persistedSnapshot,
    }
    const cleanVariantDraft = {
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-2',
      updatedAt: '2026-04-10T00:12:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: persistedSnapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:00:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return variantNode
      return { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce(baseDraft)
      .mockResolvedValueOnce(cleanVariantDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })

    let exposureCallCount = 0
    let historyCallCount = 0
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') {
        historyCallCount += 1
        return jsonResponse(historyCallCount === 1
          ? dashboardHistoryPayload
          : { performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null })
      }
      if (pathname === '/api/engines/exposure/run' && method === 'POST') {
        exposureCallCount += 1
        return jsonResponse(exposureCallCount === 1 ? exposurePayload : variantExposurePayload)
      }
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Open detailed review')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Open detailed review' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    expect(screen.queryByRole('button', { name: 'Open' })).toBeNull()

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    expect(screen.getByRole('option', { name: 'Working Draft · base' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'base' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'base -> Raise MSFT' })).toBeTruthy()
  })

  it('restores an imported snapshot workspace and keeps the dashboard handoff eligible', async () => {
    const baseNode = { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base' as const, name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026',
      createdAt: '2026-04-14T00:00:00Z',
      changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
      portfolioSnapshot: variantSnapshot,
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf', 'IB2026.pdf'], importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
    }
    const baseDraft = { id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: persistedSnapshot }
    const importedDraft = { id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-14T00:00:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: variantSnapshot }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-14T00:00:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-2',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([baseNode, importedSnapshotNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-2' ? importedSnapshotNode : baseNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(importedDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(variantDashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Open detailed review' })).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    expect(screen.getByText('Review Basis')).toBeTruthy()
  })

  it('switches from a variant back to the imported base and restores imported dashboard history', async () => {
    const baseNode = { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base' as const, name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
    const variantNode = mockSavedVariantNode()
    const variantDraft = { id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: persistedSnapshot }
    const baseDraft = { id: 'draft-3', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:13:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: persistedSnapshot }

    let activeNodeId: 'node-1' | 'node-2' = 'node-1'
    const workspaceStateForActiveNode = () => activeNodeId === 'node-1'
      ? { workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:13:00Z' }
      : { workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'node-2', lastOpenedAt: '2026-04-10T00:12:00Z' }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockImplementation(async () => workspaceStateForActiveNode())
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockImplementation(async () => ({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId,
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    }))
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([baseNode, variantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-1' ? baseNode : variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockImplementation(async () => activeNodeId === 'node-1' ? baseDraft : variantDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockImplementation(async () => ({ ...workspaceStateForActiveNode(), selectedExposureSnapshotId: activeNodeId }))

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null })
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    const firstRender = render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Open detailed review')).toBeTruthy())
    fireEvent.click(screen.getByRole('button', { name: 'Open detailed review' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page'))
    await waitFor(() => expect(screen.getByText('Portfolio Research Workspace')).toBeTruthy())

    firstRender.unmount()
    activeNodeId = 'node-2'

    const secondRender = render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Detailed review unavailable here')).toBeTruthy())
    expect(screen.getByText('Imported snapshot not active here')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Open detailed review' })).toBeNull()

    secondRender.unmount()
    activeNodeId = 'node-1'

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Open detailed review')).toBeTruthy())
    expect(screen.getAllByText((content) => content.includes('2025-01-01 - 2025-12-31')).length).toBeGreaterThan(0)
    expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Open detailed review' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Workspace' }).getAttribute('aria-current')).toBe('page'))
    expect(screen.queryByRole('button', { name: 'Open detailed review' })).toBeNull()
    await waitFor(() => expect(screen.getByText('Portfolio Research Workspace')).toBeTruthy())
  })

  it('keeps the dashboard shell rendered while the chart subtree suspends without showing dashboard loading copy', async () => {
    dashboardPerformanceChartMock.shouldSuspend = true

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(diagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse(makeRecoveredAlertReviewQueuePayload())
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))

    await waitFor(() => expect(screen.getByText('Trusted Portfolio Snapshot')).toBeTruthy())
    expect(screen.getByText('Open detailed review')).toBeTruthy()
    expect(screen.queryByText('Portfolio vs SPY path for the selected range')).toBeNull()
    expect(screen.queryByText('Loading dashboard...')).toBeNull()
  })


  it('restores an IB2026 imported snapshot workspace and keeps dashboard handoff semantics', async () => {
    const baseSnapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: '2025-01-01 - 2025-12-31',
        importedAt: '2026-04-10T00:00:00Z',
        sourceFileNames: ['IB2025.pdf'],
      },
      positions: [{ symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
      cashBalances: [{ currency: 'USD', amount: 1000 }],
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const ib2026Snapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
        positions.map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026',
      createdAt: '2026-04-14T00:00:00Z',
      changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
      portfolioSnapshot: ib2026Snapshot,
      source: buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
    }
    const cleanImportedDraft = {
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-2',
      updatedAt: '2026-04-14T00:00:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: ib2026Snapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-14T00:00:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-2',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-12-31' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: baseSnapshot },
      importedSnapshotNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      return { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: baseSnapshot }
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(cleanImportedDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if (pathname === '/api/engines/exposure/run-imported' && method === 'POST') return jsonResponse(ib2026ExposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(ib2026DiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(ib2026DashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    expect(screen.getByText('Review Basis')).toBeTruthy()
    expect(screen.getAllByText((content) => content.includes(ib2026DashboardGolden.statementPeriod)).length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getAllByText('Unable to restore previous portfolio workspace').length).toBeGreaterThan(0))
  })

  it('restores a child variant under an imported IB2026 snapshot with Dashboard fail-closed', async () => {
    const baseSnapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: '2025-01-01 - 2025-12-31',
        importedAt: '2026-04-10T00:00:00Z',
        sourceFileNames: ['IB2025.pdf'],
      },
      positions: [{ symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
      cashBalances: [{ currency: 'USD', amount: 1000 }],
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const ib2026Snapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
        positions.map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector,
          sourceType: 'equity' as const,
        }))),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026',
      createdAt: '2026-04-14T00:00:00Z',
      changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
      portfolioSnapshot: ib2026Snapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
      },
    }
    const variantFromImportedSnapshot: PortfolioSnapshot = {
      ...ib2026Snapshot,
      positions: ib2026Snapshot.positions.map((position, index) => index === 0 ? { ...position, marketValue: position.marketValue + 5000 } : position),
    }
    const importedVariantNode = {
      id: 'node-3',
      workspaceId: 'workspace-1',
      parentId: 'node-2',
      kind: 'variant' as const,
      name: 'Raise SXRV',
      createdAt: '2026-04-14T00:10:00Z',
      changeSummary: { label: 'Raise SXRV', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: variantFromImportedSnapshot,
    }
    const importedDraft = {
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-2',
      updatedAt: '2026-04-14T00:00:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: ib2026Snapshot,
    }
    const variantDraft = {
      id: 'draft-3',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-3',
      updatedAt: '2026-04-14T00:10:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: variantFromImportedSnapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'node-3', lastOpenedAt: '2026-04-14T00:10:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-14T00:10:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-3',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-12-31' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: baseSnapshot },
      importedSnapshotNode,
      importedVariantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-3') return importedVariantNode
      if (nodeId === 'node-2') return importedSnapshotNode
      return { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: baseSnapshot }
    })
    void importedDraft
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(variantDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:10:00Z' })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(ib2026ExposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(ib2026DiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(ib2026DashboardHistoryPayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(ib2026DiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null })
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Detailed review unavailable here')).toBeTruthy())
    expect(screen.getByText('Imported snapshot not active here')).toBeTruthy()
    expect(screen.getByText('Loaded file: IB2026.pdf')).toBeTruthy()
    expect(screen.queryByText(ib2026DashboardGolden.portfolioValue)).toBeNull()
    expect(screen.queryByText(`Portfolio value: ${ib2026DashboardGolden.portfolioValue}`)).toBeNull()
  })

  it('shows base and child variant lineage in Exposure snapshot options', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-2'
      ? variantNode
      : { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
      .mockResolvedValueOnce({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const persistActiveNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'setActiveNode').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    expect(screen.getByRole('option', { name: 'Working Draft · base' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'base' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'base -> Raise MSFT' })).toBeTruthy()
  })

  it('reuses imported diagnostics when selecting the base snapshot in Exposure after reload', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-1'
      ? { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
      : variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
      .mockResolvedValueOnce({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-2' } })
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(1))
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-1' } })

    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run-imported', 'POST').length).toBeGreaterThanOrEqual(2))
    expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(1)
  })

  it('shows an Exposure header exit CTA after selecting a draft and returns to the imported base snapshot', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-1'
      ? { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
      : variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const setSelectedExposureSnapshotSpy = vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'draft' } })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Return to imported snapshot' })).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Return to imported snapshot' }))

    await waitFor(() => expect(setSelectedExposureSnapshotSpy).toHaveBeenLastCalledWith({ workspaceId: 'workspace-1', snapshotId: 'node-1' }))
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run-imported', 'POST').length).toBeGreaterThanOrEqual(2))
  })

  it('uses history-aware snapshot diagnostics for saved variants in Exposure', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-2'
      ? variantNode
      : { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
      .mockResolvedValueOnce({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'node-2', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-2' } })

    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(1))
    expect(String(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')[0]?.[1]?.body)).toContain('history_context')
  })

  it('returns a saved variant selection to the nearest imported ancestor without changing active workspace state', async () => {
    const baseNode = {
      id: 'node-1',
      workspaceId: 'workspace-1',
      parentId: null,
      kind: 'imported_base' as const,
      name: 'Base Import',
      createdAt: '2026-04-10T00:00:00Z',
      changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 },
      portfolioSnapshot: persistedSnapshot,
    }
    const importedSnapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
        positions.map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026',
      createdAt: '2026-04-14T00:00:00Z',
      changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
      portfolioSnapshot: importedSnapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
      },
    }
    const importedVariantSnapshot: PortfolioSnapshot = {
      ...importedSnapshot,
      positions: importedSnapshot.positions.map((position, index) => index === 0 ? { ...position, marketValue: position.marketValue + 5000 } : position),
    }
    const importedVariantNode = {
      id: 'node-3',
      workspaceId: 'workspace-1',
      parentId: 'node-2',
      kind: 'variant' as const,
      name: 'Raise SXRV',
      createdAt: '2026-04-14T00:10:00Z',
      changeSummary: { label: 'Raise SXRV', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: importedVariantSnapshot,
    }
    const variantDraft = {
      id: 'draft-3',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-3',
      updatedAt: '2026-04-14T00:10:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: importedVariantSnapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'node-2', lastOpenedAt: '2026-04-14T00:10:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-14T00:10:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-3',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-12-31' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([baseNode, importedSnapshotNode, importedVariantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      if (nodeId === 'node-3') return importedVariantNode
      return baseNode
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(variantDraft)
    const setActiveNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'setActiveNode').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'node-3', lastOpenedAt: '2026-04-14T00:10:00Z' })
    const setSelectedExposureSnapshotSpy = vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockImplementation(async ({ snapshotId }) => ({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: snapshotId, lastOpenedAt: '2026-04-14T00:10:00Z' }))

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(ib2026ExposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(ib2026DiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(ib2026DashboardHistoryPayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(ib2026DiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null })
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())

    const variantDiagnosticsCallsBeforeSelection = matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST').length
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-3' } })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Return to imported snapshot' })).toBeTruthy())
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST').length).toBeGreaterThan(variantDiagnosticsCallsBeforeSelection))

    fireEvent.click(screen.getByRole('button', { name: 'Return to imported snapshot' }))

    await waitFor(() => expect(setSelectedExposureSnapshotSpy).toHaveBeenLastCalledWith({ workspaceId: 'workspace-1', snapshotId: 'node-2' }))
    await waitFor(() => expect((screen.getByLabelText('Snapshot') as HTMLSelectElement).value).toBe('node-2'))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Return to imported snapshot' })).toBeNull())
    expect(setActiveNodeSpy).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Detailed review unavailable here')).toBeTruthy())
    expect(screen.getByText('Imported snapshot not active here')).toBeTruthy()
  })

  it('uses snapshot-history diagnostics instead of imported replay for a child variant under an imported snapshot', async () => {
    const baseNode = {
      id: 'node-1',
      workspaceId: 'workspace-1',
      parentId: null,
      kind: 'imported_base' as const,
      name: 'Base Import',
      createdAt: '2026-04-10T00:00:00Z',
      changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 },
      portfolioSnapshot: persistedSnapshot,
    }
    const importedSnapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
        positions.map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026',
      createdAt: '2026-04-14T00:00:00Z',
      changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
      portfolioSnapshot: importedSnapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
      },
    }
    const importedVariantSnapshot: PortfolioSnapshot = {
      ...importedSnapshot,
      positions: importedSnapshot.positions.map((position, index) => index === 0 ? { ...position, marketValue: position.marketValue + 5000 } : position),
    }
    const importedVariantNode = {
      id: 'node-3',
      workspaceId: 'workspace-1',
      parentId: 'node-2',
      kind: 'variant' as const,
      name: 'Raise SXRV',
      createdAt: '2026-04-14T00:10:00Z',
      changeSummary: { label: 'Raise SXRV', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: importedVariantSnapshot,
    }
    const variantDraft = {
      id: 'draft-3',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-3',
      updatedAt: '2026-04-14T00:10:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: importedVariantSnapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'node-3', lastOpenedAt: '2026-04-14T00:10:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-14T00:10:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-3',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-12-31' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([baseNode, importedSnapshotNode, importedVariantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      if (nodeId === 'node-3') return importedVariantNode
      return baseNode
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(variantDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'node-3', lastOpenedAt: '2026-04-14T00:10:00Z' })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(ib2026ExposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(ib2026DiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(ib2026DashboardHistoryPayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(ib2026DiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null })
      throw new Error(`Unhandled fetch: ${method} ${pathname}`)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Portfolio Research Workspace' })).toBeTruthy())
    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-2' } })
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run-imported', 'POST')).toHaveLength(1))
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-3' } })

    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run-imported', 'POST')).toHaveLength(1))
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(2))
    expect(String(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')[1]?.[1]?.body)).toContain('history_context')
  })
})
