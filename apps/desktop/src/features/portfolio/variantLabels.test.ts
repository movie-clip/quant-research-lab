/**
 * US-40.1 / T-40.1.2 (implementation), T-40.1.4 (this coverage) — AC1-AC3.
 *
 * The snapshot picker's option label for a persisted imported/base node must
 * disclose the date its underlying data was captured
 * (`node.portfolioSnapshot.importedMeta.importedAt`, truncated to
 * YYYY-MM-DD), not just the bare `"base"` string it showed before this
 * story. A variant/draft layered on top of a base must still carry that
 * date (AC2). A node with no import date anywhere in its ancestor chain
 * must render exactly as it did before this story — no placeholder, no
 * fabricated date (AC3).
 */
import { describe, expect, it } from 'vitest'

import { formatVariantNodeLabel, formatWorkingDraftLabel, resolveNodeImportDate } from './variantLabels'
import type { PortfolioNode, PortfolioSnapshot } from './workspaceTypes'

function snapshot(overrides: Partial<PortfolioSnapshot> = {}): PortfolioSnapshot {
  return {
    snapshotVersion: 1,
    baseCurrency: 'USD',
    importedMeta: {
      importer: 'interactive_brokers',
      statementPeriod: '2025-01-01 - 2025-12-31',
      importedAt: '2026-04-10T00:00:00Z',
      sourceFileNames: ['IB2025.pdf'],
    },
    positions: [],
    cashBalances: [],
    metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    ...overrides,
  }
}

function node(overrides: Partial<PortfolioNode> & { id: string }): PortfolioNode {
  return {
    workspaceId: 'workspace-1',
    parentId: null,
    kind: 'imported_base',
    name: 'Base Import',
    createdAt: '2026-04-10T00:00:00Z',
    changeSummary: { label: 'Base Import', changedPositionsCount: 0, changedSectorsCount: 0 },
    portfolioSnapshot: snapshot(),
    ...overrides,
  }
}

describe('variantLabels — freeze-date signal (AC1-AC3)', () => {
  it('AC1: a base node label includes its importedMeta.importedAt date, truncated to YYYY-MM-DD', () => {
    const baseNode = node({ id: 'node-1', kind: 'imported_base' })
    const label = formatVariantNodeLabel(baseNode, [baseNode])
    expect(label).toBe('base (2026-04-10)')
  })

  it('AC2: a variant node built on top of the base still carries the base import date', () => {
    const baseNode = node({ id: 'node-1', kind: 'imported_base' })
    const variantNode = node({
      id: 'node-2',
      parentId: 'node-1',
      kind: 'variant',
      name: 'Raise MSFT',
      // Variant carries its own portfolioSnapshot (as real variant nodes do),
      // inheriting the same importedMeta.importedAt the base has — this is
      // the "own snapshot has the date" path, not the ancestor-walk fallback.
      portfolioSnapshot: snapshot(),
    })
    const label = formatVariantNodeLabel(variantNode, [baseNode, variantNode])
    expect(label).toBe('base -> Raise MSFT (2026-04-10)')
  })

  it('AC2: resolveNodeImportDate falls back to walking the ancestor chain when a node has no snapshot of its own', () => {
    const baseNode = node({ id: 'node-1', kind: 'imported_base' })
    // A hypothetical node with no portfolioSnapshot of its own (the design
    // doc's defensive ancestor-walk case — no live path produces this today,
    // but the fallback exists and is testable in isolation).
    const noSnapshotVariant = node({
      id: 'node-2',
      parentId: 'node-1',
      kind: 'variant',
      name: 'No Own Snapshot',
      portfolioSnapshot: null,
    })
    const date = resolveNodeImportDate(noSnapshotVariant, [baseNode, noSnapshotVariant])
    expect(date).toBe('2026-04-10')
  })

  it('AC3: a node with no import date anywhere in its chain renders with no date suffix', () => {
    const noDateNode = node({
      id: 'node-1',
      kind: 'imported_base',
      portfolioSnapshot: null,
    })
    expect(resolveNodeImportDate(noDateNode, [noDateNode])).toBeNull()
    expect(formatVariantNodeLabel(noDateNode, [noDateNode])).toBe('base')
  })

  it('AC3: formatWorkingDraftLabel(null, nodes) still returns exactly "Working Draft · base"', () => {
    const baseNode = node({ id: 'node-1', kind: 'imported_base' })
    expect(formatWorkingDraftLabel(null, [baseNode])).toBe('Working Draft · base')
  })

  it('a working draft built on a dated base node still discloses that date', () => {
    const baseNode = node({ id: 'node-1', kind: 'imported_base' })
    expect(formatWorkingDraftLabel(baseNode, [baseNode])).toBe('Working Draft · base (2026-04-10)')
  })
})
