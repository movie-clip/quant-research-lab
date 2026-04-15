import { describe, expect, it } from 'vitest'

import { createImportedBootstrapResponseFixture } from '../test/portfolioFixtures'
import { buildPersistedImportedSource } from './portfolioWorkspaceStorage'
import type { ImportedHistoryContext, PortfolioWorkspace } from '../features/portfolio/workspaceTypes'

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

    expect(cleanWorkspace.source.historySource.kind).toBe('imported_replay')
  })
})
