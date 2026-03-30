/**
 * 用户本地文档数据库（IndexedDB）
 * 文档只存储在浏览器中，不上传至服务端。
 */

const DB_NAME = 'codex_local';
const DB_VERSION = 1;
const STORE = 'documents';

export interface LocalChunk {
  text: string;
  embedding: number[];
  index: number;
}

export interface LocalDocument {
  id: string;
  title: string;
  fileType: string;
  fileSize: number;
  createdAt: string;
  chunkCount: number;
  chunks: LocalChunk[];
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = (e.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id' });
      }
    };
    req.onsuccess = (e) => resolve((e.target as IDBOpenDBRequest).result);
    req.onerror = () => reject(req.error);
  });
}

export async function saveLocalDoc(doc: LocalDocument): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(doc);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function listLocalDocs(): Promise<Omit<LocalDocument, 'chunks'>[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => {
      const docs = (req.result as LocalDocument[]).map(({ chunks: _c, ...rest }) => rest);
      resolve(docs.sort((a, b) => b.createdAt.localeCompare(a.createdAt)));
    };
    req.onerror = () => reject(req.error);
  });
}

export async function deleteLocalDoc(id: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

function cosineSim(a: number[], b: number[]): number {
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  return dot / (Math.sqrt(na) * Math.sqrt(nb) + 1e-9);
}

export async function searchLocalDocs(queryEmbedding: number[], topK = 5): Promise<string[]> {
  const db = await openDb();
  const allDocs: LocalDocument[] = await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });

  const scored: { text: string; score: number }[] = [];
  for (const doc of allDocs) {
    for (const chunk of doc.chunks || []) {
      scored.push({
        text: `[来源：${doc.title}]\n${chunk.text}`,
        score: cosineSim(queryEmbedding, chunk.embedding),
      });
    }
  }

  return scored
    .sort((a, b) => b.score - a.score)
    .slice(0, topK)
    .map((s) => s.text);
}

/** 将文本按 chunkSize 切块，相邻块有 overlap 重叠 */
export function chunkText(text: string, chunkSize = 800, overlap = 100): string[] {
  const chunks: string[] = [];
  let i = 0;
  while (i < text.length) {
    chunks.push(text.slice(i, i + chunkSize));
    i += chunkSize - overlap;
    if (i + overlap >= text.length) break;
  }
  if (chunks.length === 0 && text.trim()) chunks.push(text);
  return chunks;
}
