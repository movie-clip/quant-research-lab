const databaseName = 'portfolio-workstation'
const databaseVersion = 8

export const appStateStoreName = 'app-state'
export const workspaceStoreName = 'workspaces'
export const portfolioNodeStoreName = 'portfolio_nodes'
export const workingDraftStoreName = 'working_drafts'
export const workspaceStateStoreName = 'workspace_state'
export const candidateImprovementDraftStoreName = 'candidate_improvement_drafts'
export const intentBoundSeededEtfReplacementRankingDraftStoreName = 'intent_bound_seeded_etf_replacement_ranking_drafts'
export const replacementIntentDraftStoreName = 'replacement_intent_drafts'
export const hypotheticalReplacementReplayDraftStoreName = 'hypothetical_replacement_replay_drafts'
export const versionedProposalStoreName = 'versioned_proposals'

let databasePromise: Promise<IDBDatabase> | null = null
let openDatabaseHandle: IDBDatabase | null = null

export function getPortfolioDatabaseName() {
  return databaseName
}

export function getIndexedDb() {
  return globalThis.indexedDB
}

export function openPortfolioDatabase() {
  if (!getIndexedDb()) {
    return Promise.reject(new Error('IndexedDB unavailable'))
  }

  if (!databasePromise) {
    databasePromise = new Promise((resolve, reject) => {
      const request = getIndexedDb().open(databaseName, databaseVersion)

      request.onupgradeneeded = (event) => {
        const database = request.result
        const oldVersion = event.oldVersion

        if (request.transaction && oldVersion < 3) {
          const storeNames = [
            appStateStoreName,
            workspaceStoreName,
            portfolioNodeStoreName,
            workingDraftStoreName,
            workspaceStateStoreName,
            candidateImprovementDraftStoreName,
            intentBoundSeededEtfReplacementRankingDraftStoreName,
            replacementIntentDraftStoreName,
            hypotheticalReplacementReplayDraftStoreName,
            versionedProposalStoreName,
          ]

          for (const storeName of storeNames) {
            if (database.objectStoreNames.contains(storeName)) {
              database.deleteObjectStore(storeName)
            }
          }
        }

        if (!database.objectStoreNames.contains(appStateStoreName)) {
          database.createObjectStore(appStateStoreName, { keyPath: 'id' })
        }
        if (!database.objectStoreNames.contains(workspaceStoreName)) {
          database.createObjectStore(workspaceStoreName, { keyPath: 'id' })
        }
        if (!database.objectStoreNames.contains(portfolioNodeStoreName)) {
          const store = database.createObjectStore(portfolioNodeStoreName, { keyPath: 'id' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
          store.createIndex('parentId', 'parentId', { unique: false })
        }
        if (!database.objectStoreNames.contains(workingDraftStoreName)) {
          const store = database.createObjectStore(workingDraftStoreName, { keyPath: 'id' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(workspaceStateStoreName)) {
          database.createObjectStore(workspaceStateStoreName, { keyPath: 'workspaceId' })
        }
        if (!database.objectStoreNames.contains(candidateImprovementDraftStoreName)) {
          const store = database.createObjectStore(candidateImprovementDraftStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(intentBoundSeededEtfReplacementRankingDraftStoreName)) {
          const store = database.createObjectStore(intentBoundSeededEtfReplacementRankingDraftStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(replacementIntentDraftStoreName)) {
          const store = database.createObjectStore(replacementIntentDraftStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(hypotheticalReplacementReplayDraftStoreName)) {
          const store = database.createObjectStore(hypotheticalReplacementReplayDraftStoreName, { keyPath: 'draftId' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
        if (!database.objectStoreNames.contains(versionedProposalStoreName)) {
          const store = database.createObjectStore(versionedProposalStoreName, { keyPath: 'id' })
          store.createIndex('workspaceId', 'workspaceId', { unique: false })
        }
      }

      request.onsuccess = () => {
        openDatabaseHandle = request.result
        openDatabaseHandle.onclose = () => {
          if (openDatabaseHandle === request.result) {
            openDatabaseHandle = null
          }
        }
        resolve(request.result)
      }
      request.onerror = () => reject(request.error ?? new Error('Failed to open IndexedDB'))
    })
  }

  return databasePromise
}

export function deletePortfolioDatabase() {
  if (!getIndexedDb()) {
    return Promise.reject(new Error('IndexedDB unavailable'))
  }

  if (openDatabaseHandle) {
    openDatabaseHandle.close()
    openDatabaseHandle = null
  }

  databasePromise = null

  return new Promise<void>((resolve, reject) => {
    const request = getIndexedDb().deleteDatabase(databaseName)
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error ?? new Error('Failed to delete IndexedDB database'))
    request.onblocked = () => reject(new Error('IndexedDB deletion blocked by an open connection'))
  })
}

export function withStore<T>(storeName: string, mode: IDBTransactionMode, handler: (store: IDBObjectStore, resolve: (value: T) => void, reject: (reason?: unknown) => void) => void) {
  return openPortfolioDatabase().then((database) => new Promise<T>((resolve, reject) => {
    const transaction = database.transaction(storeName, mode)
    const store = transaction.objectStore(storeName)

    transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB transaction failed'))
    handler(store, resolve, reject)
  }))
}

export function withStores<T>(storeNames: string[], mode: IDBTransactionMode, handler: (transaction: IDBTransaction, resolve: (value: T) => void, reject: (reason?: unknown) => void) => void) {
  return openPortfolioDatabase().then((database) => new Promise<T>((resolve, reject) => {
    const transaction = database.transaction(storeNames, mode)
    transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB transaction failed'))
    handler(transaction, resolve, reject)
  }))
}
