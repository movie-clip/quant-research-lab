/**
 * Saved-node re-derive (US-46.1 AC 10-12, US-46.3 AC 13-15, US-46.4 AC 11; decisions D-5, D-7, D-11, D-12).
 *
 * The engine is the only source of every figure and label these tests read back, so the mock answers
 * with values that differ from anything stored (VUAA 77, not the stored 80 or the doubled 160): a
 * regression that keeps saved figures, sums on the client or scrubs on the client cannot pass.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  IB_TRUTH,
  buildSavedWorkspace,
  cloneJson,
  combinedResponse,
  doubledPortfolioSnapshot,
  esppAdmission,
  esppStatementSnapshot,
  FF_FABRICATED,
  ffLegacyStatementSnapshot,
  ibAdmission,
  ibPlusEsppAdmission,
  ibStatementSnapshot,
  portfolioSnapshotOf,
  sameAccountCombine,
  type SavedNodeInput,
} from '../test/combinedImportFixtures'
import type { CombinedImportBootstrapRequest, ImportedBootstrapResponse, ImportedSnapshot } from '../features/portfolio/types'
import { rederiveSavedNodes } from './rederiveSavedNodes'

afterEach(() => {
  vi.unstubAllGlobals()
})

type EngineCall = CombinedImportBootstrapRequest

/** Stubs fetch for analyze-combined only; each call gets the next response (or the last one). A
 *  function entry decides per request; a number entry is an HTTP error with `detail`. */
function stubAnalyzeCombined(
  responses: Array<ImportedBootstrapResponse | { status: number; detail: string } | ((request: EngineCall) => ImportedBootstrapResponse | { status: number; detail: string })>,
) {
  const calls: EngineCall[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
      if (!url.endsWith('/api/portfolios/import/analyze-combined')) throw new Error(`Unhandled fetch: ${url}`)
      const request = JSON.parse(String(init?.body)) as EngineCall
      calls.push(request)
      const entry = responses[Math.min(calls.length - 1, responses.length - 1)]
      const answer = typeof entry === 'function' ? entry(request) : entry
      if ('status' in answer) {
        return new Response(JSON.stringify({ detail: answer.detail }), { status: answer.status, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify(answer), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }),
  )
  return calls
}

function ibNode(id: string, parentId: string | null, overrides: Partial<SavedNodeInput> = {}): SavedNodeInput {
  const ib = ibStatementSnapshot()
  return {
    id,
    parentId,
    replaySnapshot: ib,
    admission: ibAdmission(),
    portfolioSnapshot: portfolioSnapshotOf(ib, ['IB2026.csv']),
    fileNames: ['IB2026.csv'],
    ...overrides,
  }
}

/** What the engine answers when IB2026 is analysed: one line of VUAA quantity 77 marks the answer as the engine's. */
function engineIbAnswer(vuaaQuantity = 77): ImportedBootstrapResponse {
  const ib = ibStatementSnapshot()
  ib.positions = ib.positions.map((position) => (position.symbol === 'VUAA' ? { ...position, quantity: vuaaQuantity } : position))
  return combinedResponse({ snapshot: ib, admission: ibAdmission() })
}

async function rederive(saved: ReturnType<typeof buildSavedWorkspace>, options: { isActive?: () => boolean } = {}) {
  const activeNode = saved.nodes[saved.nodes.length - 1]
  return rederiveSavedNodes({
    workspace: saved.workspace,
    nodes: saved.nodes,
    activeNode,
    draft: saved.draft,
    ...options,
  })
}

function vuaaOf(node: { portfolioSnapshot: { positions: Array<{ symbol: string; quantity?: number | null }> } | null }) {
  return node.portfolioSnapshot?.positions.find((position) => position.symbol === 'VUAA')?.quantity
}

describe('rederiveSavedNodes: which nodes are re-derived', () => {
  it('leaves a node stamped derivationVersion 1 alone and never calls the engine', async () => {
    const calls = stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null, { derivationVersion: 1 })] })

    const result = await rederive(saved)

    expect(calls).toHaveLength(0)
    expect(result.workspace).toBe(saved.workspace)
    expect(result.nodes).toBe(saved.nodes)
    expect(result.draft).toBe(saved.draft)
    expect(result.importError).toBeNull()
  })

  it('re-derives a node with no derivationVersion (legacy) and leaves a stamped sibling in the same workspace alone', async () => {
    const calls = stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({
      nodes: [ibNode('node-1', null, { derivationVersion: 1 }), ibNode('node-2', 'node-1')],
    })

    const result = await rederive(saved)

    expect(calls).toHaveLength(1)
    expect(vuaaOf(result.nodes[0])).toBe(IB_TRUTH.vuaaQuantity)
    expect(vuaaOf(result.nodes[1])).toBe(77)
  })

  it('does not touch a variant node', async () => {
    stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null)] })
    const variant = {
      ...saved.nodes[0],
      id: 'node-v',
      parentId: 'node-1',
      kind: 'variant' as const,
      portfolioSnapshot: doubledPortfolioSnapshot(saved.nodes[0].portfolioSnapshot!),
    }
    saved.nodes.push(variant)

    const result = await rederive(saved)

    expect(result.nodes.find((node) => node.id === 'node-v')).toBe(variant)
  })
})

describe('rederiveSavedNodes: request shape (D-11)', () => {
  it('sends the root as one stored snapshot with no carried admissions', async () => {
    const calls = stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null)] })

    await rederive(saved)

    expect(calls).toHaveLength(1)
    expect(calls[0].snapshots).toEqual([ibStatementSnapshot()])
    expect(calls[0].carried_admissions ?? []).toEqual([])
  })

  it('derives ancestors first and carries the persisted admissions root..node for an add node', async () => {
    const calls = stubAnalyzeCombined([engineIbAnswer()])
    const rootAdmission = ibAdmission()
    const middleAdmission = esppAdmission()
    const tipAdmission = ibPlusEsppAdmission()
    const stored = ibStatementSnapshot()
    const saved = buildSavedWorkspace({
      nodes: [
        ibNode('node-1', null, { admission: rootAdmission }),
        ibNode('node-2', 'node-1', { admission: middleAdmission }),
        ibNode('node-3', 'node-2', { admission: tipAdmission, replaySnapshot: sameAccountCombine(stored, stored) }),
      ],
    })

    await rederive(saved)

    expect(calls).toHaveLength(3)
    // root first, no lineage to carry
    expect(calls[0].carried_admissions ?? []).toEqual([])
    // each add node: one stored snapshot, the lineage admissions root..node in order
    expect(calls[1].snapshots).toHaveLength(1)
    expect(calls[1].carried_admissions).toEqual([rootAdmission, middleAdmission])
    expect(calls[2].snapshots).toEqual([sameAccountCombine(stored, stored)])
    expect(calls[2].carried_admissions).toEqual([rootAdmission, middleAdmission, tipAdmission])
  })

  it('sends the stored fabricated Freedom24 cost basis as saved: the client does not scrub, the engine does (D-12)', async () => {
    const calls = stubAnalyzeCombined([combinedResponse({ snapshot: ibStatementSnapshot(), admission: ibAdmission() })])
    const saved = buildSavedWorkspace({
      nodes: [ibNode('node-1', null, { replaySnapshot: ffLegacyStatementSnapshot() })],
    })

    await rederive(saved)

    const sentVti = calls[0].snapshots[0].positions.find((position) => position.symbol === FF_FABRICATED.symbol)
    expect(sentVti).toMatchObject({ cost_basis: 3018.96, unrealized_pnl: 0 })
  })
})

describe('rederiveSavedNodes: the engine answer replaces the saved figures (US-46.1 AC 10, US-46.4 AC 11)', () => {
  it('shows the engine positions, not the doubled saved ones, on a doubled IB + IB node', async () => {
    const ib = ibStatementSnapshot()
    stubAnalyzeCombined([engineIbAnswer(77)])
    const saved = buildSavedWorkspace({
      nodes: [
        ibNode('node-1', null),
        ibNode('node-2', 'node-1', {
          replaySnapshot: sameAccountCombine(ib, ib),
          portfolioSnapshot: doubledPortfolioSnapshot(portfolioSnapshotOf(ib, ['IB2026.csv'])),
        }),
      ],
    })
    expect(vuaaOf(saved.nodes[1])).toBe(160) // the saved, doubled figure

    const result = await rederive(saved)

    const tip = result.nodes[1]
    expect(vuaaOf(tip)).toBe(77)
    expect(tip.portfolioSnapshot?.positions).toHaveLength(IB_TRUTH.positionCount)
    expect(result.activeNode).toEqual(tip)
    // the node's stored replay snapshot is the engine's answer, in memory
    const source = tip.source!
    expect(source.historySource.importedHistorySnapshot?.positions.find((p) => p.symbol === 'VUAA')?.quantity).toBe(77)
  })

  it('keeps the node file names and import time when it rebuilds the portfolio snapshot', async () => {
    stubAnalyzeCombined([engineIbAnswer()])
    const ib = ibStatementSnapshot()
    const original = portfolioSnapshotOf(ib, ['IB2026.csv', 'ESPP2026.pdf'])
    original.importedMeta.importedAt = '2026-05-05T12:00:00Z'
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null, { portfolioSnapshot: original })] })

    const result = await rederive(saved)

    expect(result.nodes[0].portfolioSnapshot?.importedMeta).toMatchObject({
      sourceFileNames: ['IB2026.csv', 'ESPP2026.pdf'],
      importedAt: '2026-05-05T12:00:00Z',
    })
  })

  it('replaces a persisted admitted / verified label on an IB + ESPP node with the engine roll-up (US-46.3 AC 13)', async () => {
    const stale = esppAdmission() // the old path saved the last file only
    const calls = stubAnalyzeCombined([
      combinedResponse({ snapshot: ibStatementSnapshot(), admission: ibAdmission() }),
      combinedResponse({ snapshot: ibStatementSnapshot(), admission: ibPlusEsppAdmission() }),
    ])
    const saved = buildSavedWorkspace({
      nodes: [ibNode('node-1', null), ibNode('node-2', 'node-1', { admission: stale })],
    })
    expect(saved.nodes[1].source?.admissionSummary).toMatchObject({ decision: 'admitted', trust_level: 'verified' })

    const result = await rederive(saved)

    const admission = result.nodes[1].source?.admissionSummary
    expect(admission).toMatchObject({ decision: 'degraded', trust_level: 'degraded' })
    expect(admission?.rollup?.constituents.map((constituent) => constituent.source_names)).toEqual([['IB2026.csv'], ['ESPP2026.pdf']])
    // the engine was given the stale per-node evidence to carry, never asked to trust it
    expect(calls[1].carried_admissions).toEqual([ibAdmission(), stale])
  })

  it('shows the engine null for a fabricated Freedom24 cost basis (US-46.4 AC 11)', async () => {
    const scrubbed = ffLegacyStatementSnapshot()
    scrubbed.positions = scrubbed.positions.map((position) => ({ ...position, cost_basis: null, unrealized_pnl: null }))
    stubAnalyzeCombined([combinedResponse({ snapshot: scrubbed, admission: ibAdmission() })])
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null, { replaySnapshot: ffLegacyStatementSnapshot() })] })

    const result = await rederive(saved)

    const vti = result.workspace.source.historySource.importedHistorySnapshot?.positions.find((position) => position.symbol === 'VTI')
    expect(vti?.cost_basis).toBeNull()
    expect(vti?.unrealized_pnl).toBeNull()
    const stored = result.workspace.source.historySource.importedHistorySnapshot
    expect(stored?.positions.every((position) => position.cost_basis == null && position.unrealized_pnl == null)).toBe(true)
  })

  it('replaces the root exposure override with the engine response and clears a stale override on an add node', async () => {
    const stale = { ...ibAdmission() }
    const answer = engineIbAnswer()
    stubAnalyzeCombined([answer])
    const saved = buildSavedWorkspace({
      nodes: [ibNode('node-1', null, { admission: stale }), ibNode('node-2', 'node-1')],
    })
    saved.workspace.source.importedExposureOverride = { overview: { stale: true } } as never
    saved.nodes[1].source!.importedExposureOverride = { overview: { stale: true } } as never

    const result = await rederive(saved)

    expect(result.workspace.source.importedExposureOverride?.overview).toEqual(answer.overview)
    expect(result.nodes[1].source?.importedExposureOverride).toBeNull()
  })
})

describe('rederiveSavedNodes: a node that cannot be re-derived shows nothing stale (AC 12, AC 15)', () => {
  it('nulls snapshot, admission and override and reports the server detail when the engine refuses', async () => {
    stubAnalyzeCombined([
      engineIbAnswer(),
      { status: 400, detail: "Cannot combine: the saved combined statement 'U8516450 + U8516450' repeats an account identifier" },
    ])
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null), ibNode('node-2', 'node-1')] })
    saved.nodes[1].source!.importedExposureOverride = { overview: {} } as never

    const result = await rederive(saved)

    const tip = result.nodes[1]
    expect(tip.portfolioSnapshot).toBeNull()
    expect(tip.source?.admissionSummary).toBeNull()
    expect(tip.source?.importedExposureOverride).toBeNull()
    expect(result.importError).toBe("Cannot combine: the saved combined statement 'U8516450 + U8516450' repeats an account identifier")
    // the healthy ancestor is still re-derived
    expect(vuaaOf(result.nodes[0])).toBe(77)
  })

  it('fails a node whose lineage holds a null admission without calling the engine for it', async () => {
    const calls = stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({
      nodes: [ibNode('node-1', null), ibNode('node-2', 'node-1', { admission: null })],
    })

    const result = await rederive(saved)

    expect(calls).toHaveLength(1) // the root only
    expect(result.nodes[1].portfolioSnapshot).toBeNull()
    expect(result.importError).toMatch(/no recorded admission review/)
  })

  it('fails an add node whose ROOT has a null admission, though the root itself re-derives (its lineage is empty)', async () => {
    const calls = stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({
      nodes: [ibNode('node-1', null, { admission: null }), ibNode('node-2', 'node-1')],
    })

    const result = await rederive(saved)

    expect(calls).toHaveLength(1) // the root only; the add node is never sent
    expect(vuaaOf(result.nodes[0])).toBe(77)
    expect(result.nodes[1].portfolioSnapshot).toBeNull()
    expect(result.nodes[1].source?.admissionSummary).toBeNull()
  })

  it.each([
    ['history_context only', null],
    ['no history at all', null],
  ])('fails a node with %s (no stored statement) without calling the engine', async (_label, replaySnapshot) => {
    const calls = stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null, { replaySnapshot: replaySnapshot as ImportedSnapshot | null })] })

    const result = await rederive(saved)

    expect(calls).toHaveLength(0)
    expect(result.nodes[0].portfolioSnapshot).toBeNull()
    expect(result.workspace.source.admissionSummary).toBeNull()
    expect(result.importError).toMatch(/no stored statement/)
  })

  it('reports one message once when several nodes fail the same way, and joins distinct messages', async () => {
    stubAnalyzeCombined([
      engineIbAnswer(),
      { status: 400, detail: 'first refusal' },
      { status: 400, detail: 'first refusal' },
      { status: 400, detail: 'second refusal' },
    ])
    const saved = buildSavedWorkspace({
      nodes: [ibNode('node-1', null), ibNode('node-2', 'node-1'), ibNode('node-3', 'node-2'), ibNode('node-4', 'node-3')],
    })

    const result = await rederive(saved)

    expect(result.importError).toBe('first refusal; second refusal')
  })
})

describe('rederiveSavedNodes: working draft', () => {
  it('re-clones a clean draft from the re-derived node', async () => {
    const ib = ibStatementSnapshot()
    stubAnalyzeCombined([engineIbAnswer(), engineIbAnswer(77)])
    const saved = buildSavedWorkspace({
      nodes: [
        ibNode('node-1', null),
        ibNode('node-2', 'node-1', { portfolioSnapshot: doubledPortfolioSnapshot(portfolioSnapshotOf(ib, ['IB2026.csv'])) }),
      ],
      draft: 'clean',
    })
    expect(vuaaOf({ portfolioSnapshot: saved.draft!.portfolioSnapshot })).toBe(160)

    const result = await rederive(saved)

    expect(vuaaOf({ portfolioSnapshot: result.draft!.portfolioSnapshot })).toBe(77)
    expect(result.draft!.status).toBe('clean')
  })

  it('drops a clean draft whose base node could not be re-derived', async () => {
    stubAnalyzeCombined([{ status: 400, detail: 'refused' }])
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null)], draft: 'clean' })

    const result = await rederive(saved)

    expect(result.draft).toBeNull()
  })

  it('leaves a dirty draft alone: it carries the user edits', async () => {
    stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null)], draft: 'dirty' })
    const before = cloneJson(saved.draft)

    const result = await rederive(saved)

    expect(result.draft).toBe(saved.draft)
    expect(result.draft).toEqual(before)
  })
})

describe('rederiveSavedNodes: stability and side effects (US-46.1 AC 11)', () => {
  it('gives identical figures on every load and never mutates what was stored', async () => {
    const ib = ibStatementSnapshot()
    stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({
      nodes: [ibNode('node-1', null), ibNode('node-2', 'node-1', { portfolioSnapshot: doubledPortfolioSnapshot(portfolioSnapshotOf(ib, ['IB2026.csv'])) })],
    })
    const storedBefore = cloneJson(saved)

    const first = await rederive(saved)
    const second = await rederive(saved)
    // a third load starts from what is STORED again (nothing was written back), not from the first result
    const third = await rederive(saved)

    expect(second).toEqual(first)
    expect(third).toEqual(first)
    expect(vuaaOf(first.nodes[1])).toBe(77)
    expect(cloneJson(saved)).toEqual(storedBefore)
  })

  it('does not double a node again when it is fed its own output', async () => {
    // Feeding a result back in models a load-save-load cycle if write-back ever appeared: the second
    // pass must not change the figures because the engine, not the client, owns the merge.
    stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null)] })

    const first = await rederive(saved)
    const stamped = buildSavedWorkspace({ nodes: [ibNode('node-1', null, { derivationVersion: 1 })] })
    stamped.nodes = first.nodes
    stamped.workspace = { ...first.workspace, source: { ...first.workspace.source, derivationVersion: 1 } }
    const second = await rederive(stamped)

    expect(vuaaOf(second.nodes[0])).toBe(77)
  })

  it('returns the inputs untouched when the caller has moved on before the engine answered', async () => {
    stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null)] })

    const result = await rederive(saved, { isActive: () => false })

    expect(result.workspace).toBe(saved.workspace)
    expect(result.nodes).toBe(saved.nodes)
    expect(result.importError).toBeNull()
  })

  it('makes exactly one engine call per legacy node, regardless of how often the tree is read', async () => {
    const calls = stubAnalyzeCombined([engineIbAnswer()])
    const saved = buildSavedWorkspace({ nodes: [ibNode('node-1', null), ibNode('node-2', 'node-1')] })

    await rederive(saved)

    expect(calls).toHaveLength(2)
  })
})

describe('rederiveSavedNodes: IB then ESPP fixtures stay distinct nodes', () => {
  it('does not merge constituents on the client: an ESPP add node is sent as its stored snapshot only', async () => {
    const calls = stubAnalyzeCombined([engineIbAnswer()])
    const espp = esppStatementSnapshot()
    const saved = buildSavedWorkspace({
      nodes: [ibNode('node-1', null), ibNode('node-2', 'node-1', { replaySnapshot: espp, admission: esppAdmission() })],
    })

    await rederive(saved)

    expect(calls[1].snapshots).toEqual([espp])
  })
})
