// KONTACT API Client
// All endpoints proxied to same origin

// ============================================================
//  Types
// ============================================================

export interface UploadResponse {
  batch_id: string;
  files: { filename: string; status: string }[];
  message: string;
}

export interface FolderUploadResponse {
  batch_id: string;
  files_found: number;
  message: string;
}

export interface QueueItem {
  id: string;
  filename: string;
  status: string;
  batch_id: string;
  created_at: string;
  error?: string;
}

export interface QueueResponse {
  items: QueueItem[];
  total: number;
}

export interface BatchInfo {
  batch_id: string;
  total: number;
  pending: number;
  completed: number;
  failed: number;
  created_at: string;
}

export interface BatchesResponse {
  batches: BatchInfo[];
}

export interface PendingResponse {
  items: QueueItem[];
  total: number;
}

export interface ProcessResponse {
  processed: number;
  failed: number;
  message: string;
}

export interface SearchResult {
  id: string;
  filename: string;
  score: number;
  metadata: Record<string, unknown>;
  snippet?: string;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

export interface DataItem {
  id: string;
  filename: string;
  folder?: string;
  metadata: Record<string, unknown>;
  extracted_at: string;
}

export interface DataResponse {
  items: DataItem[];
  total: number;
}

export interface StatsResponse {
  total_files: number;
  total_processed: number;
  total_pending: number;
  total_failed: number;
  total_indexed: number;
  storage_used?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface ChatResponse {
  answer: string;
  session_id: string;
  sources?: { filename: string; score: number }[];
}

export interface ChatSession {
  session_id: string;
  title: string;
  created_at: string;
  message_count: number;
}

export interface ChatSessionsResponse {
  sessions: ChatSession[];
}

export interface ChatHistoryResponse {
  session_id: string;
  messages: ChatMessage[];
}

export interface ExportResponse {
  data: unknown[];
  total: number;
}

export interface IndexResponse {
  indexed: number;
  message: string;
}

export interface ApiError {
  detail: string;
  status: number;
}

// ============================================================
//  Helper
// ============================================================

class KontactApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'KontactApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {})
  };

  // Don't set Content-Type for FormData (browser sets boundary automatically)
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, {
    ...options,
    headers
  });

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const err = await res.json();
      detail = err.detail || err.message || detail;
    } catch {
      // response body wasn't JSON
    }
    throw new KontactApiError(res.status, detail);
  }

  // Handle empty responses (204 No Content)
  if (res.status === 204) {
    return {} as T;
  }

  return res.json();
}

function qs(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(
    (entry): entry is [string, string] => entry[1] !== undefined
  );
  if (entries.length === 0) return '';
  return '?' + new URLSearchParams(entries).toString();
}

// ============================================================
//  Upload
// ============================================================

/** Upload files via FormData */
export async function upload(files: File[], batchName?: string): Promise<UploadResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  if (batchName) {
    formData.append('batch_id', batchName);
  }
  return request<UploadResponse>('/api/upload', {
    method: 'POST',
    body: formData
  });
}

/** Alias for backward compat */
export const uploadFiles = upload;

/** Upload from a server-side folder path */
export async function uploadFolder(folderPath: string): Promise<FolderUploadResponse> {
  return request<FolderUploadResponse>(
    `/api/upload/folder?folder_path=${encodeURIComponent(folderPath)}`,
    { method: 'POST' }
  );
}

// ============================================================
//  Queue
// ============================================================

/** Get queue items, optionally filtered by batch_id */
export async function getQueue(batchId?: string): Promise<QueueResponse> {
  return request<QueueResponse>(`/api/queue${qs({ batch_id: batchId })}`);
}

/** Get all batches */
export async function getBatches(): Promise<BatchesResponse> {
  return request<BatchesResponse>('/api/queue/batches');
}

/** Get pending items, optionally filtered by batch_id */
export async function getPending(batchId?: string): Promise<PendingResponse> {
  return request<PendingResponse>(`/api/queue/pending${qs({ batch_id: batchId })}`);
}

// ============================================================
//  Processing
// ============================================================

/** Process queued items (foreground) */
export async function processQueue(batchId?: string): Promise<ProcessResponse> {
  return request<ProcessResponse>(`/api/process${qs({ batch_id: batchId })}`, {
    method: 'POST'
  });
}

/** Process queued items (background) */
export async function processBackground(batchId?: string): Promise<ProcessResponse> {
  return request<ProcessResponse>(`/api/process/background${qs({ batch_id: batchId })}`, {
    method: 'POST'
  });
}

// ============================================================
//  Search
// ============================================================

/** Keyword search */
export async function search(query: string): Promise<SearchResponse> {
  return request<SearchResponse>(`/api/search?q=${encodeURIComponent(query)}`);
}

/** Semantic / vector search */
export async function semanticSearch(query: string): Promise<SearchResponse> {
  return request<SearchResponse>(`/api/search/semantic?q=${encodeURIComponent(query)}`);
}

// ============================================================
//  Data
// ============================================================

/** Get extracted data, optionally filtered by folder */
export async function getData(folder?: string): Promise<DataResponse> {
  return request<DataResponse>(`/api/data${qs({ folder })}`);
}

/** Get system stats */
export async function getStats(): Promise<StatsResponse> {
  return request<StatsResponse>('/api/stats');
}

// ============================================================
//  Chat
// ============================================================

/** Send a chat message */
export async function sendChat(
  question: string,
  sessionId?: string
): Promise<ChatResponse> {
  return request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({
      question,
      session_id: sessionId
    })
  });
}

/** Get all chat sessions */
export async function getChatSessions(): Promise<ChatSessionsResponse> {
  return request<ChatSessionsResponse>('/api/chat/sessions');
}

/** Get chat history for a session */
export async function getChatHistory(sessionId: string): Promise<ChatHistoryResponse> {
  return request<ChatHistoryResponse>(`/api/chat/history/${encodeURIComponent(sessionId)}`);
}

/** Delete a chat session */
export async function deleteChatSession(sessionId: string): Promise<void> {
  await request<Record<string, never>>(`/api/chat/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE'
  });
}

// ============================================================
//  Export
// ============================================================

/** Export data as JSON */
export async function exportJson(): Promise<ExportResponse> {
  return request<ExportResponse>('/api/export/json');
}

/** Export data as CSV (returns blob URL) */
export async function exportCsv(): Promise<string> {
  const res = await fetch('/api/export/csv');
  if (!res.ok) {
    throw new KontactApiError(res.status, 'Export failed');
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// ============================================================
//  Index
// ============================================================

/** Trigger re-indexing */
export async function reindex(): Promise<IndexResponse> {
  return request<IndexResponse>('/api/index', {
    method: 'POST'
  });
}
