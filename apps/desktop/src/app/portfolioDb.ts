const databaseName = 'portfolio-workstation'
const databaseVersion = 18

export const appStateStoreName = 'app-state'
export const workspaceStoreName = 'workspaces'
export const portfolioNodeStoreName = 'portfolio_nodes'
export const workingDraftStoreName = 'working_drafts'
export const workspaceStateStoreName = 'workspace_state'

// Store names for removed workflow features — kept here only to delete them on upgrade
const _legacyStoreNames = [
  'candidate_improvement_drafts',
  'intent_bound_seeded_etf_replacement_ranking_drafts',
  'replacement_intent_drafts',
  'formed_candidate_drafts',
  'constructed_candidate_drafts',
  'construction_constraint_validation_drafts',
  'selected_construction_rule_drafts',
  'hypothetical_replacement_replay_drafts',
  'versioned_proposals',
  'active_thesis',
  'persisted_construction_artifact_reviews',
  'persisted_optimizer_handoff_reviews',
  'review_snapshot_artifacts',
]

let databasePromise: Promise<IDBDatabase> | null = null
let openDatabaseHandle: IDBDatabase | null = null

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

        // v3 migration: clean up very-old store names that were renamed
        if (request.transaction && oldVersion < 3) {
          const storeNames = [
            appStateStoreName,
            workspaceStoreName,
            portfolioNodeStoreName,
            workingDraftStoreName,
            workspaceStateStoreName,
            ..._legacyStoreNames,
          ]

          for (const storeName of storeNames) {
            if (database.objectStoreNames.contains(storeName)) {
              database.deleteObjectStore(storeName)
            }
          }
        }

        // v18 migration: remove workflow stores no longer used after Epic 8
        if (request.transaction && oldVersion < 18) {
          for (const storeName of _legacyStoreNames) {
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
