export type CaptureResult = {
  id: number;
  score: number | null;
  similarity_score: number | null;
  rerank_score: number | null;
  rank: number | null;
  timestamp: string;
  app_name: string;
  window_title: string | null;
  content: string;
  snippet: string;
  source_type: string;
  url: string | null;
  file_path: string | null;
  is_noise: number | null;
  is_pinned: number;
};

export type SearchResponse = {
  query: string;
  count: number;
  candidate_count: number;
  elapsed_ms: number;
  index_backend: string;
  reranker: string;
  results: CaptureResult[];
};

export type RecentResponse = {
  count: number;
  results: CaptureResult[];
};

export type StatsResponse = {
  database_path: string;
  total_captures: number;
  indexed_available: boolean;
  counts_by_app: Array<{ app_name: string; count: number }>;
  counts_by_source_type: Array<{ source_type: string; count: number }>;
  noise_counts: Array<{ is_noise: number | null; count: number }>;
  latest_capture_at: string | null;
  storage_bytes: number | null;
  protected_captures: number | null;
};

export type HealthResponse = {
  ok: boolean;
  api_key_enabled: boolean;
};

export type PrivacySettings = {
  blocked_apps: string[];
  blocked_domains: string[];
  excluded_path_fragments: string[];
};

export type StoragePolicy = {
  mode: string;
  auto_noise_enabled: boolean;
  min_text_chars: number;
  retention_days: number;
  noise_retention_hours: number;
  max_database_mb: number;
  keep_clicked: boolean;
  protect_keep_labels: boolean;
  noise_apps: string[];
  noise_domains: string[];
};

export type StorageStats = {
  database_bytes: number;
  index_bytes: number;
  log_bytes: number;
  total_bytes: number;
  total_captures: number;
  noise_captures: number;
  keep_captures: number;
  protected_captures: number;
  oldest_capture_at: string | null;
  latest_capture_at: string | null;
  policy: StoragePolicy;
};

export type CleanupResponse = {
  deleted_noise: number;
  deleted_old: number;
  deleted_duplicates: number;
  deleted_for_size: number;
  logs_rotated: number;
  index_removed: boolean;
  index_rebuilt: boolean;
  reclaimed_hint_bytes: number;
};

export type CollectionSummary = {
  id: string;
  name: string;
  description: string;
  count: number;
  latest_capture_at: string | null;
  captures: CaptureResult[];
};

export type CollectionsResponse = {
  count: number;
  collections: CollectionSummary[];
};

export type WeeklyDigest = {
  from_timestamp: string;
  to_timestamp: string;
  capture_count: number;
  keep_count: number;
  noise_count: number;
  pinned_count: number;
  opened_count: number;
  open_todo_count: number;
  top_apps: Array<{ app_name: string; count: number }>;
  top_sources: Array<{ source_type: string; count: number }>;
  collections: CollectionSummary[];
  pinned_captures: CaptureResult[];
  opened_captures: CaptureResult[];
};

export type TodoItem = {
  id: number;
  title: string;
  notes: string | null;
  status: 'open' | 'done';
  priority: number;
  due_at: string | null;
  source_capture_id: number | null;
  created_at: string;
  updated_at: string;
};

export type UserModelData = {
  status: 'ready' | 'no_model';
  summary: string;
  top_interests: string[];
  active_projects: string[];
  work_rhythm: string;
  knowledge_gaps: string[];
  generated_at: string | null;
  message?: string | null;
};

export type Belief = {
  topic: string;
  belief_type: 'interest' | 'knowledge' | 'gap' | 'pattern' | 'project';
  summary: string;
  confidence: number;
  depth: 'surface' | 'familiar' | 'intermediate' | 'deep' | null;
  times_reinforced: number;
  last_updated: string | null;
};

export type AbstractionRun = {
  id: number;
  started_at: string;
  finished_at: string | null;
  captures_read: number;
  beliefs_written: number;
  beliefs_updated: number;
  status: 'running' | 'complete' | 'failed';
  error: string | null;
};

export type AbstractionStatus = {
  ollama_running: boolean;
  model: string;
  running: boolean;
};

export type ClientConfig = {
  baseUrl: string;
  apiKey: string;
};

const jsonHeaders = (config: ClientConfig): HeadersInit => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (config.apiKey.trim()) {
    headers['X-MemoryOS-API-Key'] = config.apiKey.trim();
  }
  return headers;
};

async function request<T>(config: ClientConfig, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${config.baseUrl}${path}`, {
    ...init,
    headers: {
      ...jsonHeaders(config),
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      const text = await response.text();
      if (text) message = text;
    }
    throw new Error(message);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: (config: ClientConfig) => request<HealthResponse>(config, '/health'),
  stats: (config: ClientConfig) => request<StatsResponse>(config, '/stats'),
  recent: (config: ClientConfig, limit = 50, appName = '', sourceType = '') => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (appName) params.set('app_name', appName);
    if (sourceType) params.set('source_type', sourceType);
    return request<RecentResponse>(config, `/recent?${params.toString()}`);
  },
  search: (config: ClientConfig, query: string, topK = 10) =>
    request<SearchResponse>(config, '/search', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK }),
    }),
  refreshIndex: (config: ClientConfig, backend = 'auto') =>
    request<{ indexed_count: number; artifact_path: string; backend: string }>(config, '/refresh-index', {
      method: 'POST',
      body: JSON.stringify({ backend }),
    }),
  logClick: (config: ClientConfig, query: string, captureId: number, rank: number | null, dwellMs?: number) => {
    const params = new URLSearchParams({
      query,
      capture_id: String(captureId),
    });
    if (rank !== null) params.set('rank', String(rank));
    if (dwellMs !== undefined) params.set('dwell_ms', String(Math.max(0, Math.round(dwellMs))));
    return request<void>(config, `/click?${params.toString()}`, { method: 'POST' });
  },
  openCapture: (config: ClientConfig, captureId: number) =>
    request<{ opened: boolean; target: string }>(config, '/open', {
      method: 'POST',
      body: JSON.stringify({ capture_id: captureId }),
    }),
  labelNoise: (config: ClientConfig, captureId: number, isNoise: number | null) =>
    request<void>(config, `/captures/${captureId}/noise`, {
      method: 'PATCH',
      body: JSON.stringify({ is_noise: isNoise }),
    }),
  pinCapture: (config: ClientConfig, captureId: number, isPinned: boolean) =>
    request<void>(config, `/captures/${captureId}/pin`, {
      method: 'PATCH',
      body: JSON.stringify({ is_pinned: isPinned }),
    }),
  bulkLabelNoise: (config: ClientConfig, captureIds: number[], isNoise: number | null) =>
    request<{ updated_count: number }>(config, '/captures/noise/bulk', {
      method: 'PATCH',
      body: JSON.stringify({ capture_ids: captureIds, is_noise: isNoise }),
    }),
  privacy: (config: ClientConfig) => request<PrivacySettings>(config, '/privacy'),
  savePrivacy: (config: ClientConfig, settings: PrivacySettings) =>
    request<PrivacySettings>(config, '/privacy', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),
  storage: (config: ClientConfig) => request<StorageStats>(config, '/storage'),
  storagePolicy: (config: ClientConfig) => request<StoragePolicy>(config, '/storage-policy'),
  saveStoragePolicy: (config: ClientConfig, policy: StoragePolicy) =>
    request<StoragePolicy>(config, '/storage-policy', {
      method: 'PUT',
      body: JSON.stringify(policy),
    }),
  cleanup: (config: ClientConfig, rebuildIndex = false) =>
    request<CleanupResponse>(config, '/cleanup', {
      method: 'POST',
      body: JSON.stringify({
        delete_noise: true,
        delete_duplicates: true,
        apply_retention: true,
        enforce_size_cap: true,
        rotate_logs: true,
        rebuild_index: rebuildIndex,
        confirm: true,
      }),
    }),
  collections: (config: ClientConfig) => request<CollectionsResponse>(config, '/collections'),
  weeklyDigest: (config: ClientConfig) => request<WeeklyDigest>(config, '/digest/weekly'),
  todos: (config: ClientConfig, status = '') => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<{ count: number; todos: TodoItem[] }>(config, `/todos${suffix}`);
  },
  createTodo: (
    config: ClientConfig,
    body: { title: string; notes?: string; priority: number; due_at?: string; source_capture_id?: number },
  ) =>
    request<TodoItem>(config, '/todos', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateTodo: (
    config: ClientConfig,
    todoId: number,
    body: Partial<{ title: string; notes: string; status: 'open' | 'done'; priority: number; due_at: string; source_capture_id: number }>,
  ) =>
    request<TodoItem>(config, `/todos/${todoId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  deleteTodo: (config: ClientConfig, todoId: number) =>
    request<void>(config, `/todos/${todoId}?confirm=true`, { method: 'DELETE' }),
  userModel: (config: ClientConfig) => request<UserModelData>(config, '/user-model'),
  beliefs: (config: ClientConfig, beliefType = '', minConfidence = 0, limit = 100) => {
    const params = new URLSearchParams({ min_confidence: String(minConfidence), limit: String(limit) });
    if (beliefType) params.set('belief_type', beliefType);
    return request<{ count: number; beliefs: Belief[] }>(config, `/beliefs?${params.toString()}`);
  },
  deleteBelief: (config: ClientConfig, topic: string) =>
    request<void>(config, `/beliefs/${encodeURIComponent(topic)}?confirm=true`, { method: 'DELETE' }),
  runAbstraction: (config: ClientConfig) =>
    request<{ status: string; message: string }>(config, '/run-abstraction', { method: 'POST' }),
  abstractionRuns: (config: ClientConfig, limit = 10) =>
    request<{ count: number; runs: AbstractionRun[] }>(config, `/abstraction-runs?limit=${limit}`),
  abstractionStatus: (config: ClientConfig) => request<AbstractionStatus>(config, '/abstraction-status'),
  exportData: (config: ClientConfig) => request<unknown>(config, '/export'),
  forget: (
    config: ClientConfig,
    body: { from_timestamp?: string; to_timestamp?: string; app_name?: string; source_type?: string; confirm: boolean },
  ) =>
    request<{ deleted_count: number }>(config, '/forget', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};
