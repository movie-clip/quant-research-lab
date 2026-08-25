import { afterEach, describe, expect, it, vi } from 'vitest'

import { createImportedBootstrapResponseFixture } from '../test/portfolioFixtures'
import { projectImportedBootstrap } from '../features/portfolio/importedBootstrapMapper'
import * as portfolioDb from './portfolioDb'
import * as portfolioWorkspaceStorage from './portfolioWorkspaceStorage'
import { buildPersistedImportedSource } from './portfolioWorkspaceStorage'
import type {
  ImportedHistoryContext,
  ImportedNodeSource,
  PortfolioNode,
  PortfolioWorkspace,
} from '../features/portfolio/workspaceTypes'

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

afterEach(() => {
  vi.restoreAllMocks()
})

// Minimal in-memory stand-in for IndexedDB, backing both `withStore` and
// `withStores` from a single shared map so a value written through one
// entry point (e.g. createWorkspaceFromImport's `withStores` transaction) is
// readable through the other (e.g. saveImportedSnapshotNode's `withStore`
// reads) — real cross-function flows in this module mix both. Reuse this
// rather than the narrower ad hoc store stubs used elsewhere in this file
// when a test needs more than one storage function to see the same data.
function createFakePortfolioDb() {
  const stores = new Map<string, Map<string, unknown>>()
  function storeFor(name: string) {
    if (!stores.has(name)) stores.set(name, new Map())
    return stores.get(name)!
  }
  function keyFor(value: unknown): string {
    const v = value as { id?: string; workspaceId?: string }
    return v.id ?? v.workspaceId ?? ''
  }
  function makeStoreApi(name: string) {
    const map = storeFor(name)
    return {
      get(key: string) {
        const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: map.get(key) }
        queueMicrotask(() => request.onsuccess?.())
        return request as unknown as IDBRequest
      },
      put(value: unknown) {
        map.set(keyFor(value), structuredClone(value))
        const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
        queueMicrotask(() => request.onsuccess?.())
        return request as unknown as IDBRequest
      },
      index(_indexName: string) {
        return {
          getAll(key: string) {
            const results = Array.from(map.values()).filter((v) => (v as { workspaceId?: string }).workspaceId === key)
            const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: results }
            queueMicrotask(() => request.onsuccess?.())
            return request as unknown as IDBRequest
          },
        }
      },
    } as unknown as IDBObjectStore
  }
  return {
    stores,
    install() {
      vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
        return new Promise((resolve, reject) => handler(makeStoreApi(storeName), resolve, reject))
      })
      vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
        const transaction = { objectStore: (name: string) => makeStoreApi(name) } as unknown as IDBTransaction
        return new Promise((resolve, reject) => handler(transaction, resolve, reject))
      })
    },
  }
}

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

  it('drops a legacy admissionReviewDispositions blob on read without rewriting storage', async () => {
    // A workspace saved before US-23.9 may carry an admissionReviewDispositions
    // blob in IndexedDB. After the removal the read path must simply not carry
    // the field forward (field absent, never throws, storage not rewritten).
    const legacyDisposition = {
      schema_version: 'import_admission_review_disposition_v1',
      check_id: 'nav_market_value_comparability',
      disposition: 'deferred',
      rationale: 'Legacy disposition blob from a pre-US-23.9 workspace.',
      reviewed_at: '2026-04-11T00:00:00Z',
      reviewer_label: 'local reviewer',
      snapshot_fingerprint: 'import_snapshot:legacy',
      admission_summary_fingerprint: 'import_admission_summary:legacy',
      evidence_summary: { status: 'warn', trust_impact: 'degraded', message: 'legacy', affected_fields: [], observed: null, comparison: null, delta: null, currency: null },
    }
    const legacySource = {
      ...buildPersistedImportedSource({
        importedFileNames: ['IB2025.pdf'],
        importedAt: '2026-04-10T00:00:00Z',
        importer: 'interactive_brokers',
        baseCurrency: 'USD',
        admissionSummary: createImportedBootstrapResponseFixture().admission_summary,
      }),
      admissionReviewDispositions: { [legacyDisposition.check_id]: legacyDisposition },
    } as unknown as ImportedNodeSource
    const storedWorkspace = {
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:00:00Z',
      rootNodeId: 'node-base',
      activeNodeId: 'node-base',
      source: legacySource,
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
      source: legacySource,
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

    // Field dropped on every read boundary; admissionSummary still round-trips.
    expect(workspace && !('kind' in workspace.source) ? 'admissionReviewDispositions' in workspace.source : true).toBe(false)
    expect(node?.source && 'admissionReviewDispositions' in node.source).toBe(false)
    expect(nodes[0].source && 'admissionReviewDispositions' in nodes[0].source).toBe(false)
    expect(workspace && !('kind' in workspace.source) ? workspace.source.admissionSummary?.checks : null).toHaveLength(4)
    // Read never rewrites storage and returns fresh clones.
    expect(workspace).not.toBe(storedWorkspace)
    expect(node).not.toBe(storedNode)
    expect(putSpy).not.toHaveBeenCalled()
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

  it('persists the 6-field exposure override verbatim from the analyze-upload response on replace-mode import', async () => {
    // Coverage point 1 (2026-08-24-sbio-still-unclassified-bug/T2): the fields
    // computed once at import time must survive into workspace.source
    // unchanged, so a later lossy runExposureEngine call never needs to be
    // trusted for them.
    createFakePortfolioDb().install()

    const bootstrap = createImportedBootstrapResponseFixture()
    const analysis = projectImportedBootstrap(bootstrap).workspace
    const created = await portfolioWorkspaceStorage.createWorkspaceFromImport({
      analysis,
      importedFileNames: ['IB2025.pdf'],
    })

    const source = created.workspace.source
    expect('importedExposureOverride' in source).toBe(true)
    expect(source.importedExposureOverride).toEqual({
      overview: analysis.overview,
      lookthrough: analysis.lookthrough,
      lookthrough_sector_exposure: analysis.lookthrough_sector_exposure,
      market_overlap: analysis.market_overlap,
      current_state_concentration: analysis.current_state_concentration,
      availability: analysis.availability,
    })
  })

  it('leaves importedExposureOverride undefined on an add_snapshot node even though the parent workspace carries one', async () => {
    // Coverage point 3 (structural half): saveImportedSnapshotNode is
    // deliberately unchanged by the T1 fix — its merged snapshot was never
    // computed by the fresh exposure_result at import time, so substituting
    // any of the 6 fields would render silently wrong totals for the combined
    // portfolio. This is the known, deliberately-unfixed gap, not a claim the
    // add_snapshot path is fixed.
    createFakePortfolioDb().install()

    const bootstrap = createImportedBootstrapResponseFixture()
    const analysis = projectImportedBootstrap(bootstrap).workspace
    const created = await portfolioWorkspaceStorage.createWorkspaceFromImport({
      analysis,
      importedFileNames: ['IB2025.pdf'],
    })
    expect(created.workspace.source.importedExposureOverride).toBeTruthy()

    const saved = await portfolioWorkspaceStorage.saveImportedSnapshotNode({
      workspaceId: created.workspace.id,
      parentNodeId: created.rootNode.id,
      portfolioSnapshot: created.draft.portfolioSnapshot,
      importedFileNames: ['IB2026.pdf'],
      name: 'IB 2026',
    })

    expect(saved.node.source && 'importedExposureOverride' in saved.node.source).toBe(false)
    expect(saved.node.source?.importedExposureOverride).toBeUndefined()
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
