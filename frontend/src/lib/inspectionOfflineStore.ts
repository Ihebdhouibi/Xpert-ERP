/**
 * IndexedDB-backed store for offline inspection results.
 *
 * Results are written locally on every tap; synced to the server when online.
 * Conflict resolution (last-write-wins) is enforced server-side via written_at.
 */

export interface PendingResult {
  inspectionId: string
  itemId: string
  status: string
  notes: string | null
  mediaIds: string[]
  writtenAt: string   // ISO-8601
  synced: boolean
}

const DB_NAME = 'xpert-erp-inspections'
const DB_VERSION = 1
const STORE = 'pending_results'

let _db: IDBDatabase | null = null

function openDB(): Promise<IDBDatabase> {
  if (_db) return Promise.resolve(_db)
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = (e) => {
      const db = (e.target as IDBOpenDBRequest).result
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, {
          keyPath: ['inspectionId', 'itemId'],
        })
        store.createIndex('by_inspection', 'inspectionId', { unique: false })
      }
    }
    req.onsuccess = () => {
      _db = req.result
      resolve(req.result)
    }
    req.onerror = () => reject(req.error)
  })
}

function cursorAll(
  db: IDBDatabase,
  indexName: string,
  keyRange: IDBKeyRange
): Promise<PendingResult[]> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const idx = tx.objectStore(STORE).index(indexName)
    const req = idx.getAll(keyRange)
    req.onsuccess = () => resolve(req.result as PendingResult[])
    req.onerror = () => reject(req.error)
  })
}

export const inspectionOfflineStore = {
  /** Upsert a result locally (call on every status change). */
  async saveResult(result: PendingResult): Promise<void> {
    const db = await openDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.objectStore(STORE).put(result)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  },

  /** Return all un-synced results for an inspection. */
  async getPending(inspectionId: string): Promise<PendingResult[]> {
    const db = await openDB()
    const all = await cursorAll(
      db,
      'by_inspection',
      IDBKeyRange.only(inspectionId)
    )
    return all.filter((r) => !r.synced)
  },

  /** Return all stored results for an inspection (synced + pending). */
  async getAll(inspectionId: string): Promise<PendingResult[]> {
    const db = await openDB()
    return cursorAll(db, 'by_inspection', IDBKeyRange.only(inspectionId))
  },

  /** Mark a specific item as synced. */
  async markSynced(inspectionId: string, itemId: string): Promise<void> {
    const db = await openDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const req = store.get([inspectionId, itemId])
      req.onsuccess = () => {
        const record = req.result as PendingResult | undefined
        if (record) {
          record.synced = true
          store.put(record)
        }
      }
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  },

  /** Delete all synced records for an inspection (cleanup after sync). */
  async clearSynced(inspectionId: string): Promise<void> {
    const db = await openDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      const store = tx.objectStore(STORE)
      const idx = store.index('by_inspection')
      const req = idx.openCursor(IDBKeyRange.only(inspectionId))
      req.onsuccess = (e) => {
        const cursor = (e.target as IDBRequest<IDBCursorWithValue | null>).result
        if (cursor) {
          if ((cursor.value as PendingResult).synced) cursor.delete()
          cursor.continue()
        }
      }
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  },
}
