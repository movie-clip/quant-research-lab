/**
 * US-46 at the point the user reads it: combined imports and re-derived saved workspaces, driven through
 * the real App, the real workspace storage (over the in-memory fake DB) and a route-based fetch mock.
 *
 * Only the ENGINE is mocked. Every figure asserted here reaches the UI or the next request from an
 * analyze-combined response, and the answers are chosen to differ from anything the client could derive
 * by summing (VUAA 77, not 80 or 160), so a return to client-side merging or to stale saved figures fails.
 *
 * Covers (frontend): US-46.1 AC 1-8, 10-12; US-46.3 AC 1, 5, 8, 11-15; US-46.4 AC 9, 11 (see the report map).
 */
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  IB_TRUTH,
  buildSavedWorkspace,
  combinedResponse,
  concatDistinctAccounts,
  doubledPortfolioSnapshot,
  esppAdmission,
  esppStatementSnapshot,
  FF_FABRICATED,
  ffLegacyStatementSnapshot,
  ibAdmission,
  ibOverview,
  ibPlusEsppAdmission,
  ibStatementSnapshot,
  portfolioSnapshotOf,
  sameAccountCombine,
  seedSavedWorkspace,
  type SavedNodeInput,
} from '../test/combinedImportFixtures'
import { createFakePortfolioDb } from '../test/fakePortfolioDb'
import { installFetchMock, jsonResponse, matchingFetchCalls, requestJsonBody, requestMethod, requestPathname, unhandledOrDrift } from '../test/fetchHarness'
import { createDiagnosticsEngineFixture, createExposureEngineFixture, createImportedDashboardHistoryFixture } from '../test/portfolioFixtures'
import type { CombinedImportBootstrapRequest, ImportAdmissionSummaryV1, ImportedBootstrapResponse, ImportedSnapshot } from '../features/portfolio/types'
import type { PortfolioNode } from '../features/portfolio/workspaceTypes'
import { App } from './App'

vi.mock('@tauri-apps/plugin-dialog', () => ({ open: vi.fn() }))
vi.mock('@tauri-apps/plugin-fs', () => ({ readFile: vi.fn() }))

afterEach(() => {
  cleanup()
  delete (window as Window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

// ── engine mock ──────────────────────────────────────────────────────────────────────────────────
type CombinedAnswer = ImportedBootstrapResponse | { status: number; detail: string }
type ExposureBody = {
  positions: Array<{ symbol: string; market_value: number; quantity: number | null; currency: string }>
  cash_balances: Array<{ currency: string; amount: number }>
}

function installEngine(opts: { analyzeUpload?: ImportedBootstrapResponse[]; analyzeCombined?: CombinedAnswer[] }) {
  let uploads = 0
  let combines = 0
  const fetchMock = installFetchMock(async (input, init) => {
    const pathname = requestPathname(input)
    const method = requestMethod(input, init)
    if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') {
      const list = opts.analyzeUpload ?? []
      if (!list.length) throw new Error('Unexpected analyze-upload call')
      const answer = list[Math.min(uploads, list.length - 1)]
      uploads += 1
      return jsonResponse(answer)
    }
    if (pathname === '/api/portfolios/import/analyze-combined' && method === 'POST') {
      const list = opts.analyzeCombined ?? []
      if (!list.length) throw new Error('Unexpected analyze-combined call')
      const answer = list[Math.min(combines, list.length - 1)]
      combines += 1
      return 'status' in answer ? jsonResponse({ detail: answer.detail }, answer.status) : jsonResponse(answer)
    }
    if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(createExposureEngineFixture())
    if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(createDiagnosticsEngineFixture())
    if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(createImportedDashboardHistoryFixture())
    return unhandledOrDrift(pathname, method)
  })
  return {
    fetchMock,
    combinedBodies: () => matchingFetchCalls(fetchMock, '/api/portfolios/import/analyze-combined', 'POST').map(([, init]) => requestJsonBody(init) as CombinedImportBootstrapRequest),
    exposureBodies: () => matchingFetchCalls(fetchMock, '/api/engines/exposure/run', 'POST').map(([, init]) => requestJsonBody(init) as ExposureBody),
    importedRunBodies: (path: string) => matchingFetchCalls(fetchMock, path, 'POST').map(([, init]) => requestJsonBody(init) as ImportedSnapshot),
  }
}

// ── flow helpers ─────────────────────────────────────────────────────────────────────────────────
function fileInput() {
  return document.querySelector('input[type="file"]') as HTMLInputElement
}

function pickFile(name: string) {
  const type = name.endsWith('.csv') ? 'text/csv' : 'application/pdf'
  fireEvent.change(fileInput(), { target: { files: [new File([name], name, { type, lastModified: 1 })] } })
}

async function importFirst(name: string) {
  pickFile(name)
  await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())
}

function addStatement(name: string) {
  fireEvent.click(screen.getByText('Add Statement'))
  pickFile(name)
}

async function openExposure() {
  fireEvent.click(screen.getByText('Exposure'))
  await screen.findByText('Import Admission Review')
}

function storedNodes(db: ReturnType<typeof createFakePortfolioDb>) {
  return Array.from(db.stores.get('portfolio_nodes')?.values() ?? []) as PortfolioNode[]
}

function admissionHeader() {
  return screen.getByText('Import Admission Review').parentElement as HTMLElement
}

function expectIbExposure(body: ExposureBody, vuaaQuantity = IB_TRUTH.vuaaQuantity) {
  expect(body.positions).toHaveLength(IB_TRUTH.positionCount)
  const vuaa = body.positions.find((position) => position.symbol === 'VUAA')
  expect(vuaa?.quantity).toBe(vuaaQuantity)
  const raw = body.positions.reduce((total, position) => total + position.market_value, 0)
  expect(Math.round(raw * 100) / 100).toBe(IB_TRUTH.rawMarketValue)
  const usd = body.cash_balances.find((balance) => balance.currency === 'USD')?.amount ?? NaN
  expect(Math.round(usd * 100) / 100).toBe(IB_TRUTH.usdCash)
  expect(body.cash_balances.find((balance) => balance.currency === 'EUR')?.amount).toBe(0)
  expect(body.cash_balances.find((balance) => balance.currency === 'GBP')?.amount).toBe(0)
}

const ibUpload = () => combinedResponse({ snapshot: ibStatementSnapshot(), admission: ibAdmission(), constituents: [] })
const esppUpload = () =>
  combinedResponse({ snapshot: esppStatementSnapshot(), admission: esppAdmission(), constituents: [] })

// ─────────────────────────────────────────────────────────────────────────────────────────────────
describe('add-statement flow through analyze-combined (US-46.1, US-46.3)', () => {
  it('IB2026 then IB2026: the Exposure inputs are IB2026 alone, and the request carried both constituents (US-46.1 AC 1-4, 6)', async () => {
    createFakePortfolioDb().install()
    const engine = installEngine({
      analyzeUpload: [ibUpload()],
      // the engine's answer for the same account twice: IB2026 alone, two statement records
      analyzeCombined: [combinedResponse({ snapshot: sameAccountCombine(ibStatementSnapshot(), ibStatementSnapshot()), admission: ibAdmission() })],
    })
    render(<App />)

    await importFirst('IB2026.csv')
    const exposureCallsBeforeAdd = engine.exposureBodies().length
    addStatement('IB2026.csv')

    await waitFor(() => expect(engine.combinedBodies()).toHaveLength(1))
    await waitFor(() => expect(engine.exposureBodies().length).toBeGreaterThan(exposureCallsBeforeAdd))

    // both constituents reached the engine; nothing was pre-merged on the client
    expect(engine.combinedBodies()[0].snapshots).toEqual([ibStatementSnapshot(), ibStatementSnapshot()])
    expect(engine.combinedBodies()[0].carried_admissions ?? []).toEqual([])
    // Exposure is computed over the engine's answer: 18 positions, VUAA 80 (not 160), 62,843.22, USD 146.07
    expectIbExposure(engine.exposureBodies()[engine.exposureBodies().length - 1])
    for (const body of engine.exposureBodies()) {
      expect(body.positions.find((position) => position.symbol === 'VUAA')?.quantity).not.toBe(160)
    }
  })

  it('IB2026 then ESPP2026: the Exposure tab reads degraded / degraded with each constituent, not admitted / verified (US-46.3 AC 1, 8)', async () => {
    const db = createFakePortfolioDb()
    db.install()
    const ib = ibStatementSnapshot()
    const espp = esppStatementSnapshot()
    const engine = installEngine({
      analyzeUpload: [ibUpload(), esppUpload()],
      analyzeCombined: [combinedResponse({ snapshot: concatDistinctAccounts(ib, espp), admission: ibPlusEsppAdmission() })],
    })
    render(<App />)

    await importFirst('IB2026.csv')
    addStatement('ESPP2026.pdf')
    await waitFor(() => expect(engine.combinedBodies()).toHaveLength(1))
    await waitFor(() => expect(storedNodes(db)).toHaveLength(2))
    await openExposure()

    const header = admissionHeader()
    expect(within(header).getByText('Decision: Degraded')).toBeTruthy()
    expect(within(header).getByText('Trust: Degraded')).toBeTruthy()
    expect(within(header).queryByText(/Admitted|Verified/)).toBeNull()
    // the ESPP statement's own label stays visible alongside the portfolio label
    const esppGroup = screen.getByRole('group', { name: /ESPP2026\.pdf/ })
    expect(within(esppGroup).getByText('Decision: Admitted')).toBeTruthy()
    expect(within(esppGroup).getByText('Trust: Verified')).toBeTruthy()
    expect(within(screen.getByRole('group', { name: /IB2026\.csv/ })).getByText('Decision: Degraded')).toBeTruthy()
    // distinct accounts: the engine's 19 lines (IB's 18 + MSFT) reach Exposure
    expect(engine.exposureBodies()[engine.exposureBodies().length - 1].positions).toHaveLength(IB_TRUTH.positionCount + 1)
  })

  it('shows what the engine returned even when it differs from any client-side sum (falsifier)', async () => {
    createFakePortfolioDb().install()
    const ib = ibStatementSnapshot()
    const espp = esppStatementSnapshot()
    // An answer nothing on the client could produce from [IB, ESPP]: VUAA 77 (client sums 80), an extra
    // line the engine chose to add, and a label the constituents alone do not give.
    const engineSnapshot = concatDistinctAccounts(ib, espp)
    engineSnapshot.positions = engineSnapshot.positions.map((position) => (position.symbol === 'VUAA' ? { ...position, quantity: 77 } : position))
    engineSnapshot.positions.push({ symbol: 'ENGINEONLY', quantity: 3, market_value: 123.45, currency: 'USD' })
    const engineAdmission: ImportAdmissionSummaryV1 = { ...ibPlusEsppAdmission(), decision: 'withheld', trust_level: 'unavailable' }
    const engine = installEngine({
      analyzeUpload: [ibUpload(), esppUpload()],
      analyzeCombined: [combinedResponse({ snapshot: engineSnapshot, admission: engineAdmission })],
    })
    render(<App />)

    await importFirst('IB2026.csv')
    const before = engine.exposureBodies().length
    addStatement('ESPP2026.pdf')
    await waitFor(() => expect(engine.combinedBodies()).toHaveLength(1))
    await waitFor(() => expect(engine.exposureBodies().length).toBeGreaterThan(before))

    // the request carried both constituents, unmerged
    expect(engine.combinedBodies()[0].snapshots).toEqual([ib, espp])
    // the UI inputs are the response, not a client sum
    const exposure = engine.exposureBodies()[engine.exposureBodies().length - 1]
    expect(exposure.positions.find((position) => position.symbol === 'VUAA')?.quantity).toBe(77)
    expect(exposure.positions.find((position) => position.symbol === 'ENGINEONLY')?.quantity).toBe(3)
    // withheld and unavailable are shown as delivered, neither lowered nor collapsed
    await openExposure()
    expect(within(admissionHeader()).getByText('Decision: Withheld')).toBeTruthy()
    expect(within(admissionHeader()).getByText('Trust: Unavailable')).toBeTruthy()
  })

  it.each([
    ['a base-currency mismatch', 'Cannot combine snapshots with differing base currencies'],
    ['a statement without an account identity', 'Cannot combine: a statement has no account identity'],
  ])('a refused combine (%s) saves nothing, keeps the prior portfolio and shows the server detail (US-46.1 AC 7, US-46.3 AC 11)', async (_label, detail) => {
    const db = createFakePortfolioDb()
    db.install()
    const engine = installEngine({
      analyzeUpload: [ibUpload(), esppUpload()],
      analyzeCombined: [{ status: 400, detail }],
    })
    render(<App />)

    await importFirst('IB2026.csv')
    const nodeWritesBefore = db.writes.filter((write) => write.store === 'portfolio_nodes').length
    const exposureBefore = engine.exposureBodies()[engine.exposureBodies().length - 1]
    addStatement('ESPP2026.pdf')

    await waitFor(() => expect(screen.getAllByText(detail).length).toBeGreaterThan(0))
    // no node, no state change, no new admission on any surface
    expect(storedNodes(db)).toHaveLength(1)
    expect(db.writes.filter((write) => write.store === 'portfolio_nodes')).toHaveLength(nodeWritesBefore)
    const [rootNode] = storedNodes(db)
    const savedState = Array.from(db.stores.get('workspace_state')?.values() ?? []) as Array<{ activeNodeId: string }>
    expect(savedState.map((state) => state.activeNodeId)).toEqual([rootNode.id])
    // the prior portfolio is still on screen, with its own admission and holdings
    expect(screen.getByText('Account overview')).toBeTruthy()
    await openExposure()
    expect(screen.queryByText(/Import Admission Review unavailable/)).toBeNull()
    expect(screen.queryByRole('group', { name: /ESPP2026\.pdf/ })).toBeNull()
    expect(exposureBefore.positions).toHaveLength(IB_TRUTH.positionCount)
  })

  it('a base with no stored statement history refuses the add with a disclosure and never calls the engine', async () => {
    const db = createFakePortfolioDb()
    db.install()
    const saved = buildSavedWorkspace({
      nodes: [
        {
          id: 'node-1',
          parentId: null,
          replaySnapshot: null,
          admission: ibAdmission(),
          portfolioSnapshot: portfolioSnapshotOf(ibStatementSnapshot(), ['IB2026.csv']),
          fileNames: ['IB2026.csv'],
          derivationVersion: 1,
        },
      ],
    })
    seedSavedWorkspace(db, saved)
    const engine = installEngine({ analyzeUpload: [esppUpload()], analyzeCombined: [combinedResponse({ snapshot: ibStatementSnapshot(), admission: ibAdmission() })] })
    render(<App />)
    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())

    addStatement('ESPP2026.pdf')

    await waitFor(() => expect(screen.getAllByText(/no stored statement history to add to/).length).toBeGreaterThan(0))
    expect(engine.combinedBodies()).toHaveLength(0)
    expect(storedNodes(db)).toHaveLength(1)
  })

  it.each([
    ['carries the base admission as evidence', ibAdmission(), [ibAdmission()]],
    ['carries nothing when the base recorded no admission', null, []],
  ])('a current-format base without stored constituents goes in as one input and %s', async (_label, baseAdmission, expectedCarried) => {
    const db = createFakePortfolioDb()
    db.install()
    const ib = ibStatementSnapshot()
    const espp = esppStatementSnapshot()
    seedSavedWorkspace(
      db,
      buildSavedWorkspace({
        nodes: [
          {
            id: 'node-1',
            parentId: null,
            replaySnapshot: ib,
            admission: baseAdmission,
            portfolioSnapshot: portfolioSnapshotOf(ib, ['IB2026.csv']),
            fileNames: ['IB2026.csv'],
            derivationVersion: 1,
          },
        ],
      }),
    )
    const engine = installEngine({
      analyzeUpload: [esppUpload()],
      analyzeCombined: [combinedResponse({ snapshot: concatDistinctAccounts(ib, espp), admission: ibPlusEsppAdmission() })],
    })
    render(<App />)
    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())

    addStatement('ESPP2026.pdf')

    await waitFor(() => expect(engine.combinedBodies()).toHaveLength(1))
    expect(engine.combinedBodies()[0].snapshots).toEqual([ib, espp])
    expect(engine.combinedBodies()[0].carried_admissions ?? []).toEqual(expectedCarried)
  })

  it('adds flat from the persisted constituents on every add: [IB, ESPP] then [IB, ESPP, IB], never the combined result', async () => {
    const db = createFakePortfolioDb()
    db.install()
    const ib = ibStatementSnapshot()
    const espp = esppStatementSnapshot()
    const firstCombined = concatDistinctAccounts(ib, espp)
    const secondCombined = sameAccountCombine(firstCombined, ib)
    const engine = installEngine({
      analyzeUpload: [ibUpload(), esppUpload(), ibUpload()],
      analyzeCombined: [
        combinedResponse({ snapshot: firstCombined, admission: ibPlusEsppAdmission() }),
        combinedResponse({ snapshot: secondCombined, admission: ibPlusEsppAdmission() }),
      ],
    })
    render(<App />)

    await importFirst('IB2026.csv')
    addStatement('ESPP2026.pdf')
    await waitFor(() => expect(engine.combinedBodies()).toHaveLength(1))
    await waitFor(() => expect(storedNodes(db)).toHaveLength(2))
    await waitFor(() => expect(screen.getByText('Add Statement')).toBeTruthy())
    addStatement('IB2026.csv')
    await waitFor(() => expect(engine.combinedBodies()).toHaveLength(2))

    const [first, second] = engine.combinedBodies()
    expect(first.snapshots).toEqual([ib, espp])
    expect(second.snapshots).toEqual([ib, espp, ib])
    expect(second.snapshots).not.toContainEqual(firstCombined)
    expect(second.carried_admissions ?? []).toEqual([])
    // the second add node persisted the flat list, stamped as built by analyze-combined
    await waitFor(() => expect(storedNodes(db)).toHaveLength(3))
    const tip = storedNodes(db).find((node) => node.source?.importedConstituents?.length === 3)
    expect(tip?.source?.importedConstituents).toEqual([ib, espp, ib])
    expect(tip?.source?.derivationVersion).toBe(1)
    expect(tip?.source?.historySource.importedHistorySnapshot).toEqual(secondCombined)
  })

  it('a first import of several files stores the per-file snapshots, so a later add is built from the same constituents (US-46.3 AC 5)', async () => {
    const db = createFakePortfolioDb()
    db.install()
    const ib = ibStatementSnapshot()
    const espp = esppStatementSnapshot()
    const later = ibStatementSnapshot()
    const engine = installEngine({
      analyzeUpload: [
        combinedResponse({ snapshot: concatDistinctAccounts(ib, espp), admission: ibPlusEsppAdmission(), constituents: [ib, espp] }),
        ibUpload(),
      ],
      analyzeCombined: [combinedResponse({ snapshot: sameAccountCombine(concatDistinctAccounts(ib, espp), later), admission: ibPlusEsppAdmission() })],
    })
    render(<App />)

    fireEvent.change(fileInput(), {
      target: {
        files: [
          new File(['ib'], 'IB2026.csv', { type: 'text/csv', lastModified: 1 }),
          new File(['espp'], 'ESPP2026.pdf', { type: 'application/pdf', lastModified: 2 }),
        ],
      },
    })
    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())
    addStatement('IB2026.csv')
    await waitFor(() => expect(engine.combinedBodies()).toHaveLength(1))

    expect(engine.combinedBodies()[0].snapshots).toEqual([ib, espp, later])
    expect(engine.combinedBodies()[0].carried_admissions ?? []).toEqual([])
    const workspaces = Array.from(db.stores.get('workspaces')?.values() ?? []) as Array<{ source: { importedConstituents?: ImportedSnapshot[]; derivationVersion?: number } }>
    expect(workspaces[0].source.importedConstituents).toEqual([ib, espp])
    expect(workspaces[0].source.derivationVersion).toBe(1)
  })
})

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// Saved workspaces in the pre-fix shape (D-5, D-7, D-11, D-12): re-derived through the engine on load.
// ─────────────────────────────────────────────────────────────────────────────────────────────────
const STORED_WORKSPACE_STORES = ['portfolio_nodes', 'workspaces', 'working_drafts']

function rootNode(overrides: Partial<SavedNodeInput> = {}): SavedNodeInput {
  const ib = ibStatementSnapshot()
  return {
    id: 'node-1',
    parentId: null,
    replaySnapshot: ib,
    admission: ibAdmission(),
    portfolioSnapshot: portfolioSnapshotOf(ib, ['IB2026.csv']),
    fileNames: ['IB2026.csv'],
    ...overrides,
  }
}

/** A workspace saved by the old add-statement path: IB2026 added onto IB2026, so the node's portfolio
 *  snapshot holds the client overlay's doubled figures (VUAA 160). */
function doubledIbWorkspace(overrides: { withDraft?: 'clean' | 'dirty' | null } = {}) {
  const ib = ibStatementSnapshot()
  return buildSavedWorkspace({
    nodes: [
      rootNode(),
      {
        id: 'node-2',
        parentId: 'node-1',
        replaySnapshot: sameAccountCombine(ib, ib),
        admission: ibAdmission(),
        portfolioSnapshot: doubledPortfolioSnapshot(portfolioSnapshotOf(ib, ['IB2026.csv'])),
        fileNames: ['IB2026.csv'],
      },
    ],
    draft: overrides.withDraft === undefined ? 'clean' : overrides.withDraft,
  })
}

function engineIb(): ImportedBootstrapResponse {
  return combinedResponse({ snapshot: ibStatementSnapshot(), admission: ibAdmission() })
}

describe('saved workspaces are re-derived on load (US-46.1 AC 10-12, US-46.3 AC 13-15, US-46.4 AC 11)', () => {
  it('opens a doubled IB + IB node showing IB2026 alone, and asks the engine once per node with the lineage evidence (AC 10)', async () => {
    const db = createFakePortfolioDb()
    db.install()
    seedSavedWorkspace(db, doubledIbWorkspace())
    const engine = installEngine({ analyzeCombined: [engineIb()] })

    render(<App />)
    await waitFor(() => expect(engine.exposureBodies().length).toBeGreaterThan(0))

    expectIbExposure(engine.exposureBodies()[engine.exposureBodies().length - 1])
    // the saved, doubled figure never reached the Exposure engine
    for (const body of engine.exposureBodies()) {
      expect(body.positions.find((position) => position.symbol === 'VUAA')?.quantity).not.toBe(160)
    }
    const ib = ibStatementSnapshot()
    const [rootCall, nodeCall] = engine.combinedBodies()
    expect(engine.combinedBodies()).toHaveLength(2)
    expect(rootCall.snapshots).toEqual([ib])
    expect(rootCall.carried_admissions ?? []).toEqual([])
    expect(nodeCall.snapshots).toEqual([sameAccountCombine(ib, ib)])
    expect(nodeCall.carried_admissions).toEqual([ibAdmission(), ibAdmission()])
  })

  it('shows the engine answer, not the saved figures, when they differ (falsifier)', async () => {
    const db = createFakePortfolioDb()
    db.install()
    seedSavedWorkspace(db, doubledIbWorkspace())
    const engineSnapshot = ibStatementSnapshot()
    engineSnapshot.positions = engineSnapshot.positions.map((position) => (position.symbol === 'VUAA' ? { ...position, quantity: 77 } : position))
    const engine = installEngine({ analyzeCombined: [combinedResponse({ snapshot: engineSnapshot, admission: ibAdmission() })] })

    render(<App />)
    await waitFor(() => expect(engine.exposureBodies().length).toBeGreaterThan(0))

    const last = engine.exposureBodies()[engine.exposureBodies().length - 1]
    expect(last.positions.find((position) => position.symbol === 'VUAA')?.quantity).toBe(77)
    expect(JSON.stringify(engine.exposureBodies())).not.toContain('"quantity":160')
  })

  it('is stable across repeated loads and writes nothing back (AC 11)', async () => {
    const db = createFakePortfolioDb()
    db.install()
    seedSavedWorkspace(db, doubledIbWorkspace())
    const engine = installEngine({ analyzeCombined: [engineIb()] })

    render(<App />)
    await waitFor(() => expect(engine.exposureBodies().length).toBeGreaterThan(0))
    const firstLoad = engine.exposureBodies()[engine.exposureBodies().length - 1]
    cleanup()

    const callsAfterFirst = engine.exposureBodies().length
    render(<App />)
    await waitFor(() => expect(engine.exposureBodies().length).toBeGreaterThan(callsAfterFirst))
    const secondLoad = engine.exposureBodies()[engine.exposureBodies().length - 1]
    cleanup()

    const callsAfterSecond = engine.exposureBodies().length
    render(<App />)
    await waitFor(() => expect(engine.exposureBodies().length).toBeGreaterThan(callsAfterSecond))
    const thirdLoad = engine.exposureBodies()[engine.exposureBodies().length - 1]

    expect(secondLoad).toEqual(firstLoad)
    expect(thirdLoad).toEqual(firstLoad)
    expectIbExposure(thirdLoad)
    // nothing stored was rewritten: the node, workspace and draft stores saw no write
    expect(db.writes.filter((write) => STORED_WORKSPACE_STORES.includes(write.store))).toEqual([])
    // and what is stored is still the legacy shape, so every load starts from the same input
    const stored = db.read<PortfolioNode>('portfolio_nodes', 'node-2')
    expect(stored?.source?.derivationVersion).toBeUndefined()
    expect(stored?.portfolioSnapshot?.positions.find((position) => position.symbol === 'VUAA')?.quantity).toBe(160)
  })

  it('opens an IB + ESPP node persisted as admitted / verified showing degraded / degraded with its constituents (US-46.3 AC 13, 14)', async () => {
    const db = createFakePortfolioDb()
    db.install()
    const ib = ibStatementSnapshot()
    const espp = esppStatementSnapshot()
    const combined = concatDistinctAccounts(ib, espp)
    seedSavedWorkspace(
      db,
      buildSavedWorkspace({
        nodes: [
          rootNode(),
          {
            id: 'node-2',
            parentId: 'node-1',
            replaySnapshot: combined,
            // the old path saved the LAST file's own label
            admission: esppAdmission(),
            portfolioSnapshot: portfolioSnapshotOf(combined, ['IB2026.csv', 'ESPP2026.pdf']),
            fileNames: ['IB2026.csv', 'ESPP2026.pdf'],
          },
        ],
      }),
    )
    const engine = installEngine({ analyzeCombined: [engineIb(), combinedResponse({ snapshot: combined, admission: ibPlusEsppAdmission() })] })

    render(<App />)
    await waitFor(() => expect(engine.exposureBodies().length).toBeGreaterThan(0))
    await openExposure()

    expect(within(admissionHeader()).getByText('Decision: Degraded')).toBeTruthy()
    expect(within(admissionHeader()).getByText('Trust: Degraded')).toBeTruthy()
    expect(within(admissionHeader()).queryByText(/Admitted|Verified/)).toBeNull()
    expect(screen.getByRole('group', { name: /IB2026\.csv/ })).toBeTruthy()
    expect(screen.getByRole('group', { name: /ESPP2026\.pdf/ })).toBeTruthy()
    // the persisted label was handed to the engine as evidence to carry, never displayed as the answer
    expect(engine.combinedBodies()[1].carried_admissions).toEqual([ibAdmission(), esppAdmission()])
  })

  it('opens a Freedom24 node saved with the fabricated 3,018.96 / 0.00 and shows the engine unavailable, with no client scrub (US-46.4 AC 11)', async () => {
    const db = createFakePortfolioDb()
    db.install()
    const legacyFf = ffLegacyStatementSnapshot()
    seedSavedWorkspace(
      db,
      buildSavedWorkspace({
        nodes: [rootNode({ replaySnapshot: legacyFf, portfolioSnapshot: portfolioSnapshotOf(legacyFf, ['FF2026.pdf']), fileNames: ['FF2026.pdf'] })],
      }),
    )
    const scrubbed = ffLegacyStatementSnapshot()
    scrubbed.positions = scrubbed.positions.map((position) => ({ ...position, cost_basis: null, unrealized_pnl: null }))
    const engineOverview = { ...ibOverview(), total_cost_basis: null, total_unrealized_pnl: null, cost_basis_trust: 'unavailable' as const }
    const engine = installEngine({ analyzeCombined: [combinedResponse({ snapshot: scrubbed, admission: ibAdmission(), overview: engineOverview })] })

    render(<App />)
    await waitFor(() => expect(engine.importedRunBodies('/api/engines/diagnostics/run-imported').length).toBeGreaterThan(0))

    // the saved fabricated values went to the engine as saved: only the engine may change them
    const sentVti = engine.combinedBodies()[0].snapshots[0].positions.find((position) => position.symbol === FF_FABRICATED.symbol)
    expect(sentVti).toMatchObject({ cost_basis: FF_FABRICATED.costBasis, unrealized_pnl: FF_FABRICATED.unrealizedPnl })
    // every later imported-history request carries the engine's null, never 3,018.96 / 0.00
    for (const path of ['/api/engines/diagnostics/run-imported', '/api/engines/dashboard-history/run-imported']) {
      for (const body of engine.importedRunBodies(path)) {
        const vti = body.positions.find((position) => position.symbol === FF_FABRICATED.symbol)
        expect(vti?.cost_basis).toBeNull()
        expect(vti?.unrealized_pnl).toBeNull()
      }
    }
    // and the stored copy is untouched (nothing written back)
    expect(db.writes.filter((write) => STORED_WORKSPACE_STORES.includes(write.store))).toEqual([])
  })

  it('does not call the engine for a current-format node (derivationVersion 1)', async () => {
    const db = createFakePortfolioDb()
    db.install()
    seedSavedWorkspace(db, buildSavedWorkspace({ nodes: [rootNode({ derivationVersion: 1 })] }))
    const engine = installEngine({ analyzeCombined: [engineIb()] })

    render(<App />)
    await waitFor(() => expect(engine.exposureBodies().length).toBeGreaterThan(0))

    expect(engine.combinedBodies()).toHaveLength(0)
  })

  it('shows the server detail, no holdings, no stale label and no Add Statement for a node the engine refuses (US-46.1 AC 12, US-46.3 AC 15)', async () => {
    const db = createFakePortfolioDb()
    db.install()
    const detail = "Cannot combine: the saved combined statement 'U8516450 + U8516450' repeats an account identifier"
    seedSavedWorkspace(db, doubledIbWorkspace())
    const engine = installEngine({ analyzeCombined: [engineIb(), { status: 400, detail }] })

    render(<App />)

    await waitFor(() => expect(screen.getAllByText(detail).length).toBeGreaterThan(0))
    // the doubled figures were never analysed as current
    for (const body of engine.exposureBodies()) {
      expect(body.positions.find((position) => position.symbol === 'VUAA')?.quantity).not.toBe(160)
    }
    expect(screen.queryByText('Add Statement')).toBeNull()
    fireEvent.click(screen.getByText('Exposure'))
    // no exposure analysis at all: the tab holds no holdings and, above all, no admission label
    await screen.findByText(/Import a portfolio from the Dashboard to review/)
    expect(screen.queryByText(/Decision: /)).toBeNull()
    expect(screen.queryByText('Import Admission Review')).toBeNull()
  })

  it.each([
    ['history-context only', 'history_context'],
    ['no stored history', 'none'],
  ])('shows the no-stored-statement disclosure for a legacy node with %s and never calls the engine (AC 12)', async (_label, _kind) => {
    const db = createFakePortfolioDb()
    db.install()
    seedSavedWorkspace(db, buildSavedWorkspace({ nodes: [rootNode({ replaySnapshot: null })] }))
    const engine = installEngine({ analyzeCombined: [engineIb()] })

    render(<App />)

    await waitFor(() => expect(screen.getAllByText(/no stored statement to recompute from/).length).toBeGreaterThan(0))
    expect(engine.combinedBodies()).toHaveLength(0)
    expect(engine.exposureBodies()).toHaveLength(0)
    expect(screen.queryByText('Add Statement')).toBeNull()
  })

  it('fails a node whose lineage lacks a recorded admission without asking the engine about it (AC 15)', async () => {
    const db = createFakePortfolioDb()
    db.install()
    const saved = doubledIbWorkspace()
    saved.nodes[1].source!.admissionSummary = null
    seedSavedWorkspace(db, saved)
    const engine = installEngine({ analyzeCombined: [engineIb()] })

    render(<App />)

    await waitFor(() => expect(screen.getAllByText(/no recorded admission review/).length).toBeGreaterThan(0))
    expect(engine.combinedBodies()).toHaveLength(1) // the root only
    expect(screen.queryByText('Add Statement')).toBeNull()
  })

  it('leaves a dirty working draft as the user saved it while re-deriving its base node', async () => {
    const db = createFakePortfolioDb()
    db.install()
    const saved = doubledIbWorkspace({ withDraft: 'dirty' })
    saved.draft!.portfolioSnapshot.positions = saved.draft!.portfolioSnapshot.positions.map((position) =>
      position.symbol === 'VUAA' ? { ...position, quantity: 999 } : position,
    )
    seedSavedWorkspace(db, saved)
    const engine = installEngine({ analyzeCombined: [engineIb()] })

    render(<App />)
    await waitFor(() => expect(engine.exposureBodies().length).toBeGreaterThan(0))
    fireEvent.click(screen.getByText('Exposure'))
    const snapshotSelect = (await screen.findByLabelText('Snapshot')) as HTMLSelectElement
    fireEvent.change(snapshotSelect, { target: { value: 'draft' } })

    // the draft branch analyses the user's own edit, not a copy re-cloned from the re-derived node
    await waitFor(() => {
      const bodies = engine.exposureBodies()
      expect(bodies[bodies.length - 1].positions.find((position) => position.symbol === 'VUAA')?.quantity).toBe(999)
    })
  })
})
