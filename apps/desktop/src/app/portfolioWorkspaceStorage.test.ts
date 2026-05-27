import { afterEach, describe, expect, it, vi } from 'vitest'

import { createImportedBootstrapResponseFixture } from '../test/portfolioFixtures'
import { projectImportedBootstrap } from '../features/portfolio/importedBootstrapMapper'
import * as portfolioDb from './portfolioDb'
import * as portfolioWorkspaceStorage from './portfolioWorkspaceStorage'
import { buildImportAdmissionSummaryFingerprint, buildImportSnapshotFingerprint, buildPersistedImportedSource } from './portfolioWorkspaceStorage'
import type { ImportAdmissionReviewDispositionV1 } from '../features/portfolio/types'
import type {
  ImportedHistoryContext,
  PortfolioNode,
  PortfolioWorkspace,
} from '../features/portfolio/workspaceTypes'

type AdmissionReviewDisposition = NonNullable<ReturnType<typeof buildPersistedImportedSource>['admissionReviewDispositions']>[string]

const importedSnapshot = createImportedBootstrapResponseFixture().snapshot

function createHistoryContext(): ImportedHistoryContext {
  return {
    benchmarkSymbol: 'SPY',
    statementPeriod: '2025-01-01 - 2025-12-31',
    importedAt: '2026-04-10T00:00:00Z',
    importer: 'interactive_brokers',
    sourceFileNames: ['IB2025.pdf'],
    historyStartDate: '2025-01-02',
    historyEndDate: '2025-03-03',
  }
}

function createAdmissionReviewDisposition(overrides: Partial<AdmissionReviewDisposition> = {}): AdmissionReviewDisposition {
  const check = createImportedBootstrapResponseFixture().admission_summary.checks.find((candidate) => candidate.status !== 'pass') ?? createImportedBootstrapResponseFixture().admission_summary.checks[0]
  return {
    schema_version: 'import_admission_review_disposition_v1',
    check_id: check.check_id,
    disposition: 'deferred',
    rationale: 'Waiting for corrected broker statement export.',
    reviewed_at: '2026-04-11T00:00:00Z',
    reviewer_label: 'local reviewer',
    snapshot_fingerprint: 'import_snapshot:one',
    admission_summary_fingerprint: 'import_admission_summary:one',
    evidence_summary: {
      status: check.status === 'pass' ? 'warn' : check.status,
      trust_impact: check.trust_impact,
      message: check.message,
      affected_fields: check.affected_fields ?? [],
      observed: check.observed ?? null,
      comparison: check.comparison ?? null,
      delta: check.delta ?? null,
      currency: check.currency ?? null,
    },
    ...overrides,
  } as ImportAdmissionReviewDispositionV1
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('portfolioWorkspaceStorage', () => {
  it('builds persisted sources with historySource only', () => {
    const persistedSource = buildPersistedImportedSource({
      importedFileNames: ['IB2025.pdf'],
      importedAt: '2026-04-10T00:00:00Z',
      importer: 'interactive_brokers',
      baseCurrency: 'USD',
      historyContext: createHistoryContext(),
      importedHistorySnapshot: importedSnapshot,
    })

    expect(persistedSource).toEqual({
      importedFileNames: ['IB2025.pdf'],
      importedAt: '2026-04-10T00:00:00Z',
      importer: 'interactive_brokers',
      baseCurrency: 'USD',
      historySource: {
        kind: 'imported_replay',
        historyContext: createHistoryContext(),
        importedHistorySnapshot: importedSnapshot,
      },
    })
    expect('historyContext' in persistedSource).toBe(false)
    expect('importedHistorySnapshot' in persistedSource).toBe(false)
  })

  it('persists import admission summary with imported source metadata', () => {
    const bootstrap = createImportedBootstrapResponseFixture()
    const admissionSummary = bootstrap.admission_summary

    const persistedSource = buildPersistedImportedSource({
      importedFileNames: ['IB2025.pdf'],
      importedAt: '2026-04-10T00:00:00Z',
      importer: 'interactive_brokers',
      baseCurrency: 'USD',
      admissionSummary,
    })

    expect(persistedSource.admissionSummary).toEqual(admissionSummary)
    expect(persistedSource.admissionSummary?.checks).toHaveLength(4)
  })

  it('persists import admission review dispositions separate from admission summary', () => {
    const bootstrap = createImportedBootstrapResponseFixture()
    const admissionSummary = bootstrap.admission_summary
    const check = admissionSummary.checks.find((candidate) => candidate.status !== 'pass') ?? admissionSummary.checks[0]
    if (check.status === 'pass') throw new Error('expected non-pass admission check fixture')
    const disposition = {
      schema_version: 'import_admission_review_disposition_v1' as const,
      check_id: check.check_id,
      disposition: 'deferred' as const,
      rationale: 'Waiting for corrected broker statement export.',
      reviewed_at: '2026-04-11T00:00:00Z',
      reviewer_label: 'local reviewer',
      snapshot_fingerprint: 'import_snapshot:one',
      admission_summary_fingerprint: 'import_admission_summary:one',
      evidence_summary: {
        status: check.status,
        trust_impact: check.trust_impact,
        message: check.message,
        affected_fields: check.affected_fields ?? [],
        observed: check.observed ?? null,
        comparison: check.comparison ?? null,
        delta: check.delta ?? null,
        currency: check.currency ?? null,
      },
    }

    const persistedSource = buildPersistedImportedSource({
      importedFileNames: ['IB2025.pdf'],
      importedAt: '2026-04-10T00:00:00Z',
      importer: 'interactive_brokers',
      baseCurrency: 'USD',
      admissionSummary,
      admissionReviewDispositions: { [disposition.check_id]: disposition },
    })

    expect(persistedSource.admissionSummary).toEqual(admissionSummary)
    expect(persistedSource.admissionReviewDispositions?.[check.check_id]).toEqual(disposition)
    expect(persistedSource.admissionSummary?.decision).toBe('degraded')
    expect(persistedSource.admissionSummary?.trust_level).toBe('degraded')
  })

  it('sanitizes local import admission review metadata at persisted-source build boundaries', () => {
    const validDisposition = createAdmissionReviewDisposition({
      snapshot_fingerprint: 'import_snapshot:stale-but-valid',
      admission_summary_fingerprint: 'import_admission_summary:stale-but-valid',
    })
    const persistedSource = buildPersistedImportedSource({
      importedFileNames: ['IB2025.pdf'],
      importedAt: '2026-04-10T00:00:00Z',
      importer: 'interactive_brokers',
      baseCurrency: 'USD',
      admissionSummary: createImportedBootstrapResponseFixture().admission_summary,
      admissionReviewDispositions: {
        [validDisposition.check_id]: {
          ...validDisposition,
          unknown_top_level: 'dropped',
          evidence_summary: {
            ...validDisposition.evidence_summary,
            unknown_nested: 'dropped',
          },
        } as unknown as AdmissionReviewDisposition,
        malformed_record: {
          ...validDisposition,
          check_id: 'malformed_record',
          rationale: '',
        },
        pass_status_evidence: {
          ...validDisposition,
          check_id: 'pass_status_evidence',
          evidence_summary: { ...validDisposition.evidence_summary, status: 'pass' },
        } as unknown as AdmissionReviewDisposition,
      },
    })

    expect(persistedSource.admissionReviewDispositions).toEqual({
      [validDisposition.check_id]: validDisposition,
    })
    expect(persistedSource.admissionReviewDispositions?.[validDisposition.check_id].snapshot_fingerprint).toBe('import_snapshot:stale-but-valid')
    expect('unknown_top_level' in (persistedSource.admissionReviewDispositions?.[validDisposition.check_id] as unknown as Record<string, unknown>)).toBe(false)
    expect('unknown_nested' in (persistedSource.admissionReviewDispositions?.[validDisposition.check_id].evidence_summary as unknown as Record<string, unknown>)).toBe(false)
  })

  it('drops local import admission review metadata with non-finite numeric evidence', () => {
    const validDisposition = createAdmissionReviewDisposition()
    const withNonFiniteObserved = {
      ...validDisposition,
      check_id: 'non_finite_observed',
      evidence_summary: {
        ...validDisposition.evidence_summary,
        observed: { label: 'parsed_cash_balances', value: Number.NaN },
      },
    } as unknown as AdmissionReviewDisposition
    const withNonFiniteComparison = {
      ...validDisposition,
      check_id: 'non_finite_comparison',
      evidence_summary: {
        ...validDisposition.evidence_summary,
        comparison: { label: 'statement_cash_total', value: Number.POSITIVE_INFINITY },
      },
    } as unknown as AdmissionReviewDisposition
    const withNonFiniteDelta = {
      ...validDisposition,
      check_id: 'non_finite_delta',
      evidence_summary: {
        ...validDisposition.evidence_summary,
        delta: Number.NEGATIVE_INFINITY,
      },
    } as unknown as AdmissionReviewDisposition

    const persistedSource = buildPersistedImportedSource({
      importedFileNames: ['IB2025.pdf'],
      importedAt: '2026-04-10T00:00:00Z',
      importer: 'interactive_brokers',
      baseCurrency: 'USD',
      admissionSummary: createImportedBootstrapResponseFixture().admission_summary,
      admissionReviewDispositions: {
        [validDisposition.check_id]: validDisposition,
        non_finite_observed: withNonFiniteObserved,
        non_finite_comparison: withNonFiniteComparison,
        non_finite_delta: withNonFiniteDelta,
      },
    })

    expect(persistedSource.admissionReviewDispositions).toEqual({
      [validDisposition.check_id]: validDisposition,
    })
  })

  it('returns sanitized imported metadata clones on workspace and node read boundaries without rewriting storage', async () => {
    const validDisposition = createAdmissionReviewDisposition({ snapshot_fingerprint: 'import_snapshot:old' })
    const dirtyDisposition = {
      ...validDisposition,
      extra: 'drop-me',
      evidence_summary: { ...validDisposition.evidence_summary, extra: 'drop-me-too' },
    } as unknown as AdmissionReviewDisposition
    const source = buildPersistedImportedSource({
      importedFileNames: ['IB2025.pdf'],
      importedAt: '2026-04-10T00:00:00Z',
      importer: 'interactive_brokers',
      baseCurrency: 'USD',
      admissionSummary: createImportedBootstrapResponseFixture().admission_summary,
      admissionReviewDispositions: { [validDisposition.check_id]: dirtyDisposition },
    })
    const storedWorkspace = {
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:00:00Z',
      rootNodeId: 'node-base',
      activeNodeId: 'node-base',
      source: {
        ...source,
        admissionReviewDispositions: { [validDisposition.check_id]: dirtyDisposition },
      },
    } satisfies PortfolioWorkspace
    const storedNode: PortfolioNode = {
      id: 'node-imported',
      workspaceId: 'workspace-1',
      parentId: null,
      kind: 'imported_snapshot',
      name: 'Imported Snapshot',
      createdAt: '2026-04-10T00:00:00Z',
      changeSummary: { label: 'Imported Snapshot', changedPositionsCount: 0, changedSectorsCount: 0 },
      portfolioSnapshot: null,
      source: storedWorkspace.source,
    }
    const putSpy = vi.fn()
    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const store = {
        get(key: string) {
          const result = storeName === portfolioDb.workspaceStoreName && key === 'workspace-1'
            ? storedWorkspace
            : storeName === portfolioDb.portfolioNodeStoreName && key === 'node-imported'
              ? storedNode
              : undefined
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
        index() {
          return {
            getAll(_key: string) {
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: [storedNode] }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
        put: putSpy,
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    const workspace = await portfolioWorkspaceStorage.getWorkspace('workspace-1')
    const node = await portfolioWorkspaceStorage.getNode('node-imported')
    const nodes = await portfolioWorkspaceStorage.getWorkspaceNodes('workspace-1')

    expect(workspace && !('kind' in workspace.source) ? workspace.source.admissionReviewDispositions?.[validDisposition.check_id] : null).toEqual(validDisposition)
    expect(node?.source?.admissionReviewDispositions?.[validDisposition.check_id]).toEqual(validDisposition)
    expect(nodes[0].source?.admissionReviewDispositions?.[validDisposition.check_id]).toEqual(validDisposition)
    expect(workspace).not.toBe(storedWorkspace)
    expect(node).not.toBe(storedNode)
    expect(putSpy).not.toHaveBeenCalled()
  })

  it('rejects saving import admission review metadata directly on variant nodes', async () => {
    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      const store = {
        get(key: string) {
          const result = storeName === portfolioDb.workspaceStoreName
            ? {
                id: 'workspace-1',
                name: 'Portfolio Workspace',
                createdAt: '2026-04-10T00:00:00Z',
                updatedAt: '2026-04-10T00:00:00Z',
                rootNodeId: 'node-base',
                activeNodeId: 'node-variant',
                source: buildPersistedImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD' }),
              }
            : key === 'node-variant'
              ? {
                  id: 'node-variant',
                  workspaceId: 'workspace-1',
                  parentId: 'node-base',
                  kind: 'variant',
                  name: 'Variant',
                  createdAt: '2026-04-11T00:00:00Z',
                  changeSummary: { label: 'Variant', changedPositionsCount: 0, changedSectorsCount: 0 },
                  portfolioSnapshot: null,
                }
              : undefined
          const request = { ...requestTemplate, result }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.saveImportAdmissionReviewDisposition({
      workspaceId: 'workspace-1',
      nodeId: 'node-variant',
      disposition: {
        schema_version: 'import_admission_review_disposition_v1',
        check_id: 'nav_market_value_comparability',
        disposition: 'deferred',
        rationale: 'Review metadata must stay anchored to imported source nodes.',
        reviewed_at: '2026-04-11T00:00:00Z',
        reviewer_label: 'local reviewer',
        snapshot_fingerprint: 'import_snapshot:one',
        admission_summary_fingerprint: 'import_admission_summary:one',
        evidence_summary: { status: 'warn', trust_impact: 'degraded', message: 'warning', affected_fields: [], observed: null, comparison: null, delta: null, currency: null },
      },
    })).rejects.toThrow('Import admission review metadata can only be saved on imported source nodes')
  })

  it('rejects saving import admission review metadata on a node outside the supplied workspace', async () => {
    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      const store = {
        get(key: string) {
          const result = storeName === portfolioDb.workspaceStoreName
            ? {
                id: 'workspace-1',
                name: 'Portfolio Workspace',
                createdAt: '2026-04-10T00:00:00Z',
                updatedAt: '2026-04-10T00:00:00Z',
                rootNodeId: 'node-base',
                activeNodeId: 'node-base',
                source: buildPersistedImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD' }),
              }
            : key === 'node-other-workspace'
              ? {
                  id: 'node-other-workspace',
                  workspaceId: 'workspace-2',
                  parentId: null,
                  kind: 'imported_snapshot',
                  name: 'Other Workspace Import',
                  createdAt: '2026-04-11T00:00:00Z',
                  changeSummary: { label: 'Other Workspace Import', changedPositionsCount: 0, changedSectorsCount: 0 },
                  portfolioSnapshot: null,
                  source: buildPersistedImportedSource({ importedFileNames: ['IB2026.pdf'], importedAt: '2026-04-11T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD' }),
                }
              : undefined
          const request = { ...requestTemplate, result }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.saveImportAdmissionReviewDisposition({
      workspaceId: 'workspace-1',
      nodeId: 'node-other-workspace',
      disposition: {
        schema_version: 'import_admission_review_disposition_v1',
        check_id: 'nav_market_value_comparability',
        disposition: 'deferred',
        rationale: 'Cross-workspace review metadata must be rejected.',
        reviewed_at: '2026-04-11T00:00:00Z',
        reviewer_label: 'local reviewer',
        snapshot_fingerprint: 'import_snapshot:one',
        admission_summary_fingerprint: 'import_admission_summary:one',
        evidence_summary: { status: 'warn', trust_impact: 'degraded', message: 'warning', affected_fields: [], observed: null, comparison: null, delta: null, currency: null },
      },
    })).rejects.toThrow('Import admission review metadata target node does not belong to supplied workspace')
  })

  it('validates saved import admission review metadata against non-pass admission evidence only', async () => {
    const admissionSummary = createImportedBootstrapResponseFixture().admission_summary
    const nonPassCheck = admissionSummary.checks.find((check) => check.status !== 'pass') ?? admissionSummary.checks[0]
    if (nonPassCheck.status === 'pass') throw new Error('expected non-pass admission check fixture')
    const workspace: PortfolioWorkspace = {
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:00:00Z',
      rootNodeId: 'node-base',
      activeNodeId: 'node-base',
      source: buildPersistedImportedSource({
        importedFileNames: ['IB2025.pdf'],
        importedAt: '2026-04-10T00:00:00Z',
        importer: 'interactive_brokers',
        baseCurrency: 'USD',
        admissionSummary,
      }),
    }
    const savedValues: unknown[] = []
    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: storeName === portfolioDb.workspaceStoreName ? workspace : undefined }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
        put(value: unknown) {
          savedValues.push(value)
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.saveImportAdmissionReviewDisposition({
      workspaceId: 'workspace-1',
      disposition: createAdmissionReviewDisposition({
        check_id: 'missing_check',
      }),
    })).rejects.toThrow('Import admission review metadata must reference an admission check')
    await expect(portfolioWorkspaceStorage.saveImportAdmissionReviewDisposition({
      workspaceId: 'workspace-1',
      disposition: createAdmissionReviewDisposition({
        check_id: nonPassCheck.check_id,
        evidence_summary: { status: 'pass', trust_impact: 'none', message: 'pass evidence should not persist', affected_fields: [] } as unknown as AdmissionReviewDisposition['evidence_summary'],
      }),
    })).rejects.toThrow('Import admission review metadata is malformed')
    await expect(portfolioWorkspaceStorage.saveImportAdmissionReviewDisposition({
      workspaceId: 'workspace-1',
      disposition: createAdmissionReviewDisposition({
        check_id: nonPassCheck.check_id,
        evidence_summary: {
          status: nonPassCheck.status,
          trust_impact: nonPassCheck.trust_impact,
          message: 'stale evidence from a previous admission check run',
          affected_fields: nonPassCheck.affected_fields ?? [],
          observed: nonPassCheck.observed ?? null,
          comparison: nonPassCheck.comparison ?? null,
          delta: nonPassCheck.delta ?? null,
          currency: nonPassCheck.currency ?? null,
        },
      }),
    })).rejects.toThrow('Import admission review metadata evidence must match current admission check evidence')
    expect(savedValues).toHaveLength(0)

    await portfolioWorkspaceStorage.saveImportAdmissionReviewDisposition({
      workspaceId: 'workspace-1',
      disposition: createAdmissionReviewDisposition({
        check_id: nonPassCheck.check_id,
        snapshot_fingerprint: 'import_snapshot:stale-but-valid',
        admission_summary_fingerprint: 'import_admission_summary:stale-but-valid',
      }),
    })

    expect(savedValues).toHaveLength(1)
    expect((savedValues[0] as PortfolioWorkspace).source).toMatchObject({
      admissionSummary: {
        decision: admissionSummary.decision,
        trust_level: admissionSummary.trust_level,
      },
      admissionReviewDispositions: {
        [nonPassCheck.check_id]: {
          check_id: nonPassCheck.check_id,
          snapshot_fingerprint: 'import_snapshot:stale-but-valid',
          admission_summary_fingerprint: 'import_admission_summary:stale-but-valid',
        },
      },
    })
    expect((savedValues[0] as PortfolioWorkspace).source).toMatchObject(workspace.source)
  })

  it('accepts saved admission evidence with omitted optional null defaults', async () => {
    const baseAdmissionSummary = createImportedBootstrapResponseFixture().admission_summary
    const nonPassCheck = {
      ...baseAdmissionSummary.checks[0],
      status: 'warn' as const,
      observed: null,
      comparison: null,
      delta: null,
      currency: null,
    }
    const admissionSummary = {
      ...baseAdmissionSummary,
      checks: [nonPassCheck, ...baseAdmissionSummary.checks.slice(1)],
    }
    const workspace: PortfolioWorkspace = {
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:00:00Z',
      rootNodeId: 'node-base',
      activeNodeId: 'node-base',
      source: buildPersistedImportedSource({
        importedFileNames: ['IB2025.pdf'],
        importedAt: '2026-04-10T00:00:00Z',
        importer: 'interactive_brokers',
        baseCurrency: 'USD',
        admissionSummary,
      }),
    }
    const savedValues: unknown[] = []
    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: storeName === portfolioDb.workspaceStoreName ? workspace : undefined }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
        put(value: unknown) {
          savedValues.push(value)
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await portfolioWorkspaceStorage.saveImportAdmissionReviewDisposition({
      workspaceId: 'workspace-1',
      disposition: createAdmissionReviewDisposition({
        check_id: nonPassCheck.check_id,
        evidence_summary: {
          status: nonPassCheck.status,
          trust_impact: nonPassCheck.trust_impact,
          message: nonPassCheck.message,
          affected_fields: nonPassCheck.affected_fields ?? [],
        },
      }),
    })

    expect(savedValues).toHaveLength(1)
    expect((savedValues[0] as PortfolioWorkspace).source).toMatchObject({
      admissionSummary: { decision: admissionSummary.decision, trust_level: admissionSummary.trust_level },
      admissionReviewDispositions: {
        [nonPassCheck.check_id]: {
          evidence_summary: {
            status: nonPassCheck.status,
            trust_impact: nonPassCheck.trust_impact,
            message: nonPassCheck.message,
            affected_fields: nonPassCheck.affected_fields ?? [],
          },
        },
      },
    })
  })

  it('builds deterministic import admission fingerprints independent of key order', () => {
    const left = buildImportAdmissionSummaryFingerprint({
      schema_version: 'import_admission_summary_v1',
      decision: 'degraded',
      trust_level: 'degraded',
      checks: [],
      provenance: { importer: null, statement_ids: [], source_names: [], generated_at: '2026-04-10T00:00:00Z', tolerance_policy: 'policy' },
    })
    const right = buildImportAdmissionSummaryFingerprint({
      trust_level: 'degraded',
      decision: 'degraded',
      schema_version: 'import_admission_summary_v1',
      provenance: { tolerance_policy: 'policy', generated_at: '2026-04-10T00:00:00Z', source_names: [], statement_ids: [], importer: null },
      checks: [],
    })
    const snapshotFingerprint = buildImportSnapshotFingerprint({
      portfolioSnapshot: null,
      importedSource: buildPersistedImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD' }),
    })

    expect(left).toEqual(right)
    expect(snapshotFingerprint).toContain('import_snapshot:')
  })

  it('embeds current-format persisted sources inside workspaces', () => {
    const cleanWorkspace: PortfolioWorkspace = {
      id: 'workspace-clean',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:00:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildPersistedImportedSource({
        importedFileNames: ['IB2025.pdf'],
        importedAt: '2026-04-10T00:00:00Z',
        importer: 'interactive_brokers',
        baseCurrency: 'USD',
        historyContext: createHistoryContext(),
        importedHistorySnapshot: importedSnapshot,
      }),
    }

    expect('historySource' in cleanWorkspace.source && cleanWorkspace.source.historySource.kind).toBe('imported_replay')
  })

  it('creates imported workspaces with dashboard-first startup selection', async () => {
    const persisted = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) persisted.set(`${name}:${key}`, structuredClone(value))
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })

    const bootstrap = createImportedBootstrapResponseFixture()
    const created = await portfolioWorkspaceStorage.createWorkspaceFromImport({
      analysis: projectImportedBootstrap(bootstrap).workspace,
      importedFileNames: ['IB2025.pdf'],
      historyContext: createHistoryContext(),
      importedHistorySnapshot: importedSnapshot,
    })

    expect(created.workspaceState.activeDraftId).toBe(created.draft.id)
    expect(created.workspaceState.selectedExposureSnapshotId).toBe(created.rootNode.id)
    expect(!('kind' in created.workspace.source) && created.workspace.source.admissionSummary).toEqual(bootstrap.admission_summary)
  })

  it('clears candidate improvement draft annotation when recreating a fresh draft from a node', async () => {
    const getNodeSpy = vi.spyOn(portfolioDb, 'withStore').mockImplementation((storeName) => {
      if (storeName === portfolioDb.portfolioNodeStoreName) {
        return Promise.resolve({
          id: 'node-1',
          workspaceId: 'workspace-1',
          parentId: null,
          kind: 'imported_base',
          name: 'Base Import',
          createdAt: '2026-04-10T00:00:00Z',
          changeSummary: {
            label: 'Base Import',
            changedPositionsCount: 1,
            changedSectorsCount: 1,
            grossExposureDelta: 10000,
            netCapitalDelta: 10000,
          },
          portfolioSnapshot: {
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
          },
        })
      }
      if (storeName === portfolioDb.workingDraftStoreName) {
        return Promise.resolve({
          id: 'draft-1',
          workspaceId: 'workspace-1',
          baseNodeId: 'node-legacy',
          updatedAt: '2026-04-10T00:00:00Z',
          name: 'Working Draft',
          status: 'dirty',
          portfolioSnapshot: {
            snapshotVersion: 1,
            baseCurrency: 'USD',
            importedMeta: {
              importer: 'interactive_brokers',
              statementPeriod: '2025-01-01 - 2025-12-31',
              importedAt: '2026-04-10T00:00:00Z',
              sourceFileNames: ['IB2025.pdf'],
            },
            positions: [{ symbol: 'MSFT', marketValue: 9000, quantity: 9, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
            cashBalances: [{ currency: 'USD', amount: 500 }],
            metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
          },
        })
      }
      return Promise.resolve(undefined)
    })
    const draft = await portfolioWorkspaceStorage.createDraftFromNode({ workspaceId: 'workspace-1', baseNodeId: 'node-1' })

    expect(getNodeSpy).toHaveBeenCalled()
    expect(draft).toMatchObject({
      id: 'draft-1',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-1',
      status: 'clean',
    })
  })
})
