const DB_NAME = 'fda-workspace';
const DB_VERSION = 1;

export interface Session {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

export interface StoredQueryDetail {
  id: string;
  tool: string;
  dataSource: string;
  args: Record<string, unknown>;
  status: 'pending' | 'complete' | 'error';
  resultSummary?: string;
  timestamp: number;
}

export interface StoredMessage {
  id: string;
  sessionId: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  meta?: {
    tokens?: number;
    cost?: number;
    model?: string;
    thinkingContent?: string;
  };
  structuredData?: Record<string, unknown>;
  queryDetails?: StoredQueryDetail[];
}

export interface Artifact {
  id: string;
  sessionId: string;
  messageId: string;
  type: 'recalls' | 'events' | 'clearances' | 'approvals' | 'classifications' | 'registrations' | 'devices';
  label: string;
  rowCount: number;
  data: unknown[];
  createdAt: string;
}

let dbPromise: Promise<IDBDatabase> | null = null;

function openDB(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise;

  dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;

      if (!db.objectStoreNames.contains('sessions')) {
        const sessionsStore = db.createObjectStore('sessions', { keyPath: 'id' });
        sessionsStore.createIndex('updatedAt', 'updatedAt', { unique: false });
      }

      if (!db.objectStoreNames.contains('messages')) {
        const messagesStore = db.createObjectStore('messages', { keyPath: 'id' });
        messagesStore.createIndex('sessionId', 'sessionId', { unique: false });
        messagesStore.createIndex('sessionTimestamp', ['sessionId', 'timestamp'], { unique: false });
      }

      if (!db.objectStoreNames.contains('artifacts')) {
        const artifactsStore = db.createObjectStore('artifacts', { keyPath: 'id' });
        artifactsStore.createIndex('sessionId', 'sessionId', { unique: false });
      }
    };
  });

  return dbPromise;
}

export async function saveSession(session: Session): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('sessions', 'readwrite');
    tx.objectStore('sessions').put(session);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getSession(id: string): Promise<Session | undefined> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('sessions', 'readonly');
    const request = tx.objectStore('sessions').get(id);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function listSessions(): Promise<Session[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('sessions', 'readonly');
    const index = tx.objectStore('sessions').index('updatedAt');
    const request = index.openCursor(null, 'prev');
    const sessions: Session[] = [];

    request.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
      if (cursor) {
        sessions.push(cursor.value);
        cursor.continue();
      } else {
        resolve(sessions);
      }
    };
    request.onerror = () => reject(request.error);
  });
}

export async function deleteSession(id: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(['sessions', 'messages', 'artifacts'], 'readwrite');

    tx.objectStore('sessions').delete(id);

    const messagesIndex = tx.objectStore('messages').index('sessionId');
    const messagesRequest = messagesIndex.openCursor(IDBKeyRange.only(id));
    messagesRequest.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };

    const artifactsIndex = tx.objectStore('artifacts').index('sessionId');
    const artifactsRequest = artifactsIndex.openCursor(IDBKeyRange.only(id));
    artifactsRequest.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };

    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function saveMessage(message: StoredMessage): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('messages', 'readwrite');
    tx.objectStore('messages').put(message);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getMessages(sessionId: string): Promise<StoredMessage[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('messages', 'readonly');
    const index = tx.objectStore('messages').index('sessionTimestamp');
    const range = IDBKeyRange.bound([sessionId, ''], [sessionId, '\uffff']);
    const request = index.openCursor(range);
    const messages: StoredMessage[] = [];

    request.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
      if (cursor) {
        messages.push(cursor.value);
        cursor.continue();
      } else {
        resolve(messages);
      }
    };
    request.onerror = () => reject(request.error);
  });
}

export async function saveArtifact(artifact: Artifact): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('artifacts', 'readwrite');
    tx.objectStore('artifacts').put(artifact);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getArtifacts(sessionId: string): Promise<Artifact[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('artifacts', 'readonly');
    const index = tx.objectStore('artifacts').index('sessionId');
    const request = index.getAll(IDBKeyRange.only(sessionId));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function clearAllData(): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(['sessions', 'messages', 'artifacts'], 'readwrite');
    tx.objectStore('sessions').clear();
    tx.objectStore('messages').clear();
    tx.objectStore('artifacts').clear();
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export function exportArtifactToCSV(artifact: Artifact): string {
  if (!artifact.data || artifact.data.length === 0) return '';

  const rows = artifact.data as Record<string, unknown>[];
  const headers = Object.keys(rows[0]);

  const csvRows = [
    headers.join(','),
    ...rows.map(row =>
      headers.map(header => {
        const val = row[header];
        const str = val === null || val === undefined ? '' : String(val);
        return str.includes(',') || str.includes('"') || str.includes('\n')
          ? `"${str.replace(/"/g, '""')}"`
          : str;
      }).join(',')
    )
  ];

  return csvRows.join('\n');
}

export function downloadCSV(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
