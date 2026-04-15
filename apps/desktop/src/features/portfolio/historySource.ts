import type { ImportedHistoryContext, ImportedHistorySource, ImportedNodeSource } from './workspaceTypes'
import type { ImportedSnapshot } from './types'

export function buildImportedHistorySource(input: {
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
}): ImportedHistorySource {
  if (input.importedHistorySnapshot) {
    return {
      kind: 'imported_replay',
      historyContext: input.historyContext ?? null,
      importedHistorySnapshot: input.importedHistorySnapshot,
    }
  }
  if (input.historyContext) {
    return {
      kind: 'history_context',
      historyContext: input.historyContext,
      importedHistorySnapshot: null,
    }
  }
  return {
    kind: 'none',
    historyContext: null,
    importedHistorySnapshot: null,
  }
}

export function canUseImportedReplay(source: Pick<ImportedNodeSource, 'historySource'> | null | undefined) {
  return source?.historySource.kind === 'imported_replay'
}

export function collapseToHistoryContextSource(source: Pick<ImportedNodeSource, 'historySource'> | null | undefined): ImportedHistorySource {
  return source?.historySource.historyContext
    ? {
        kind: 'history_context',
        historyContext: source.historySource.historyContext,
        importedHistorySnapshot: null,
      }
    : {
        kind: 'none',
        historyContext: null,
        importedHistorySnapshot: null,
      }
}

export function resolveEffectiveHistorySource(
  effectiveSource: Pick<ImportedNodeSource, 'historySource'> | null | undefined,
  directSource: Pick<ImportedNodeSource, 'historySource'> | null | undefined,
): ImportedHistorySource {
  if (directSource && canUseImportedReplay(directSource)) {
    return directSource.historySource
  }
  return collapseToHistoryContextSource(effectiveSource)
}
