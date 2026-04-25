import {
  Activity,
  BarChart3,
  BrainCircuit,
  CalendarDays,
  Check,
  Clock3,
  Circle,
  ClipboardList,
  Database,
  ExternalLink,
  FileText,
  Filter,
  Gauge,
  HardDrive,
  Layers3,
  Loader2,
  Pin,
  PinOff,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Shield,
  ShieldCheck,
  Tag,
  Trash2,
  UserRound,
  X,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  api,
  CaptureResult,
  ClientConfig,
  CollectionSummary,
  PrivacySettings,
  SearchResponse,
  StatsResponse,
  StoragePolicy,
  StorageStats,
  TodoItem,
  WeeklyDigest,
} from './api';
import UserModel from './UserModel';

type Tab = 'home' | 'search' | 'recent' | 'you' | 'collections' | 'digest' | 'todo' | 'label' | 'stats' | 'settings';

const DEFAULT_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8765';

const tabs: Array<{ id: Tab; label: string; icon: typeof Search }> = [
  { id: 'home', label: 'Home', icon: BrainCircuit },
  { id: 'search', label: 'Search', icon: Search },
  { id: 'recent', label: 'Recent', icon: FileText },
  { id: 'you', label: 'You', icon: UserRound },
  { id: 'collections', label: 'Collections', icon: Layers3 },
  { id: 'digest', label: 'Digest', icon: CalendarDays },
  { id: 'todo', label: 'Todo', icon: ClipboardList },
  { id: 'label', label: 'Label', icon: Tag },
  { id: 'stats', label: 'Stats', icon: BarChart3 },
  { id: 'settings', label: 'Settings', icon: Settings },
];

function loadConfig(): ClientConfig {
  return {
    baseUrl: localStorage.getItem('memoryos.baseUrl') || DEFAULT_BASE_URL,
    apiKey: localStorage.getItem('memoryos.apiKey') || '',
  };
}

function saveConfig(config: ClientConfig) {
  localStorage.setItem('memoryos.baseUrl', config.baseUrl);
  localStorage.setItem('memoryos.apiKey', config.apiKey);
}

function formatTime(value: string | null) {
  if (!value) return 'None';
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function formatBytes(value: number | null | undefined) {
  if (!value) return '0 MB';
  const units = ['B', 'KB', 'MB', 'GB'];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function relativeTime(value: string | null) {
  if (!value) return 'unknown time';
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['year', 60 * 60 * 24 * 365],
    ['month', 60 * 60 * 24 * 30],
    ['week', 60 * 60 * 24 * 7],
    ['day', 60 * 60 * 24],
    ['hour', 60 * 60],
    ['minute', 60],
  ];
  for (const [unit, seconds] of units) {
    if (Math.abs(diffSeconds) >= seconds || unit === 'minute') {
      return formatter.format(Math.round(diffSeconds / seconds), unit);
    }
  }
  return 'just now';
}

function sourceLabel(capture: CaptureResult) {
  return [capture.app_name, capture.source_type, relativeTime(capture.timestamp)].join(' / ');
}

function openCapture(capture: CaptureResult) {
  if (capture.url) {
    window.open(capture.url, '_blank', 'noopener,noreferrer');
    return;
  }
  if (capture.file_path) {
    window.open(`file://${capture.file_path}`, '_blank', 'noopener,noreferrer');
  }
}

function labelText(value: number | null) {
  if (value === 0) return 'Keep';
  if (value === 1) return 'Noise';
  return 'Unlabeled';
}

export function App() {
  const [config, setConfig] = useState<ClientConfig>(loadConfig);
  const [tab, setTab] = useState<Tab>('home');
  const [health, setHealth] = useState<'online' | 'offline' | 'checking'>('checking');
  const [healthKey, setHealthKey] = useState(false);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  const checkHealth = async () => {
    setHealth('checking');
    try {
      const response = await api.health(config);
      setHealth(response.ok ? 'online' : 'offline');
      setHealthKey(response.api_key_enabled);
    } catch {
      setHealth('offline');
      setHealthKey(false);
    }
  };

  const loadStats = async () => {
    try {
      setStats(await api.stats(config));
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    saveConfig(config);
  }, [config]);

  useEffect(() => {
    void checkHealth();
    void loadStats();
  }, [config.baseUrl, config.apiKey]);

  const statusClass =
    health === 'online' ? 'text-moss' : health === 'offline' ? 'text-rust' : 'text-signal';

  return (
    <main className="min-h-screen bg-[#f2f4f6] text-ink">
      <header className="app-header">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <div className="brain-logo">
              <BrainCircuit size={24} />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-normal">MemoryOS</h1>
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Circle size={9} className={statusClass} fill="currentColor" />
                <span>{health}</span>
                {healthKey && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">key</span>}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button className="icon-button" onClick={checkHealth} title="Refresh backend status" type="button">
              <RefreshCw size={17} />
            </button>
            <button className="command-button" onClick={() => setTab('settings')} type="button">
              <Settings size={16} />
              Settings
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-4 px-4 py-4 lg:grid-cols-[220px_1fr]">
        <nav className="h-fit border-b border-line bg-white p-2 lg:sticky lg:top-4 lg:border">
          <div className="grid grid-cols-3 gap-1 sm:grid-cols-6 lg:grid-cols-1">
            {tabs.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={`nav-tab ${tab === item.id ? 'nav-tab-active' : ''}`}
                  onClick={() => setTab(item.id)}
                  type="button"
                >
                  <Icon size={17} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </nav>

        <section className="min-w-0">
          {error && (
            <div className="mb-4 flex items-center justify-between border border-rust/30 bg-[#fff7f3] px-3 py-2 text-sm text-rust">
              <span>{error}</span>
              <button className="icon-button-small" onClick={() => setError('')} title="Dismiss" type="button">
                <X size={14} />
              </button>
            </div>
          )}
          {toast && (
            <div className="mb-4 flex items-center justify-between border border-moss/30 bg-[#f2fbf7] px-3 py-2 text-sm text-moss">
              <span>{toast}</span>
              <button className="icon-button-small" onClick={() => setToast('')} title="Dismiss" type="button">
                <X size={14} />
              </button>
            </div>
          )}

          {tab === 'home' && (
            <HomeView
              health={health}
              stats={stats}
              onNavigate={setTab}
              onRefresh={() => {
                void checkHealth();
                void loadStats();
              }}
            />
          )}
          {tab === 'search' && <SearchView config={config} onError={setError} />}
          {tab === 'recent' && <RecentView config={config} onError={setError} />}
          {tab === 'you' && <UserModel config={config} onError={setError} onToast={setToast} />}
          {tab === 'collections' && <CollectionsView config={config} onError={setError} />}
          {tab === 'digest' && <DigestView config={config} onError={setError} />}
          {tab === 'todo' && <TodoView config={config} onError={setError} onToast={setToast} />}
          {tab === 'label' && <LabelView config={config} onError={setError} onToast={setToast} />}
          {tab === 'stats' && (
            <StatsView config={config} stats={stats} onStats={setStats} onError={setError} onToast={setToast} />
          )}
          {tab === 'settings' && (
            <SettingsView
              config={config}
              onConfig={setConfig}
              onHealth={checkHealth}
              apiKeyEnabled={healthKey}
              onError={setError}
              onToast={setToast}
            />
          )}
        </section>
      </div>
    </main>
  );
}

function HomeView({
  health,
  stats,
  onNavigate,
  onRefresh,
}: {
  health: 'online' | 'offline' | 'checking';
  stats: StatsResponse | null;
  onNavigate: (tab: Tab) => void;
  onRefresh: () => void;
}) {
  const keepCount = stats?.noise_counts.find((item) => item.is_noise === 0)?.count || 0;
  const noiseCount = stats?.noise_counts.find((item) => item.is_noise === 1)?.count || 0;
  const unlabeledCount = stats?.noise_counts.find((item) => item.is_noise === null)?.count || 0;
  const statusTone = health === 'online' ? 'ready' : health === 'checking' ? 'checking' : 'offline';

  return (
    <div className="space-y-4">
      <section className="home-hero">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <div className="brain-logo brain-logo-large">
              <BrainCircuit size={36} />
            </div>
            <div>
              <div className="text-sm font-medium text-slate-600">Local memory console</div>
              <h2 className="text-3xl font-semibold tracking-normal text-ink">MemoryOS</h2>
            </div>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <HomeMetric label="Backend" value={health} icon={Gauge} tone={statusTone} />
            <HomeMetric label="Captures" value={stats?.total_captures ?? 0} icon={Database} tone="neutral" />
            <HomeMetric label="Protected" value={stats?.protected_captures ?? 0} icon={ShieldCheck} tone="safe" />
            <HomeMetric label="Storage" value={formatBytes(stats?.storage_bytes)} icon={HardDrive} tone="warm" />
          </div>
        </div>
        <div className="home-actions">
          <button className="command-button primary" onClick={() => onNavigate('search')} type="button">
            <Search size={16} />
            Search Memory
          </button>
          <button className="command-button" onClick={() => onNavigate('recent')} type="button">
            <Clock3 size={16} />
            Recent
          </button>
          <button className="command-button" onClick={onRefresh} type="button">
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="surface">
          <div className="surface-title">Today</div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <Badge label="Keep" value={keepCount} />
            <Badge label="Noise" value={noiseCount} />
            <Badge label="Unlabeled" value={unlabeledCount} />
          </div>
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            <button className="home-link" onClick={() => onNavigate('label')} type="button">
              <Check size={17} />
              Review labels
            </button>
            <button className="home-link" onClick={() => onNavigate('collections')} type="button">
              <Layers3 size={17} />
              Smart collections
            </button>
            <button className="home-link" onClick={() => onNavigate('you')} type="button">
              <UserRound size={17} />
              User model
            </button>
            <button className="home-link" onClick={() => onNavigate('digest')} type="button">
              <CalendarDays size={17} />
              Weekly digest
            </button>
            <button className="home-link" onClick={() => onNavigate('todo')} type="button">
              <ClipboardList size={17} />
              Todo list
            </button>
            <button className="home-link" onClick={() => onNavigate('stats')} type="button">
              <BarChart3 size={17} />
              View stats
            </button>
            <button className="home-link" onClick={() => onNavigate('settings')} type="button">
              <Shield size={17} />
              Storage policy
            </button>
          </div>
        </section>

        <section className="surface">
          <div className="surface-title">System</div>
          <div className="mt-4 space-y-3 text-sm text-slate-700">
            <SystemRow label="Index" value={stats?.indexed_available ? 'Ready' : 'Missing'} />
            <SystemRow label="Latest" value={relativeTime(stats?.latest_capture_at || null)} />
            <SystemRow label="Disk" value={formatBytes(stats?.storage_bytes)} />
            <SystemRow label="Protected" value={`${stats?.protected_captures ?? 0} captures`} />
          </div>
        </section>
      </div>
    </div>
  );
}

function HomeMetric({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: string | number;
  icon: typeof Database;
  tone: 'ready' | 'checking' | 'offline' | 'neutral' | 'safe' | 'warm';
}) {
  return (
    <div className={`home-metric home-metric-${tone}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-slate-600">{label}</span>
        <Icon size={18} />
      </div>
      <div className="mt-3 truncate text-2xl font-semibold capitalize">{value}</div>
    </div>
  );
}

function SystemRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line pb-2 last:border-b-0 last:pb-0">
      <span className="text-slate-500">{label}</span>
      <span className="truncate font-medium text-ink">{value}</span>
    </div>
  );
}

function SearchView({ config, onError }: { config: ClientConfig; onError: (value: string) => void }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<CaptureResult[]>([]);
  const [searchMeta, setSearchMeta] = useState<SearchResponse | null>(null);
  const [resultsLoadedAt, setResultsLoadedAt] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setSearchMeta(null);
      setResultsLoadedAt(null);
      return;
    }
    const handle = window.setTimeout(async () => {
      setLoading(true);
      try {
        const response = await api.search(config, trimmed, 10);
        setResults(response.results);
        setSearchMeta(response);
        setResultsLoadedAt(Date.now());
        onError('');
      } catch (err) {
        onError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => window.clearTimeout(handle);
  }, [query, config.baseUrl, config.apiKey]);

  return (
    <div className="space-y-4">
      <div className="toolbar">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
          <input
            className="search-input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search your memory..."
          />
        </div>
        {loading && <Loader2 className="animate-spin text-signal" size={20} />}
      </div>
      {searchMeta && (
        <div className="flex flex-wrap gap-2 text-xs text-slate-600">
          <span className="status-pill">{searchMeta.index_backend}</span>
          <span className="status-pill">{searchMeta.reranker} reranker</span>
          <span className="status-pill">{searchMeta.candidate_count} candidates</span>
          <span className="status-pill">{searchMeta.elapsed_ms.toFixed(1)} ms</span>
        </div>
      )}
      {query.trim() ? (
        <ResultList config={config} query={query} results={results} resultsLoadedAt={resultsLoadedAt} onError={onError} />
      ) : (
        <EmptyState label="Type a query to search" />
      )}
    </div>
  );
}

function RecentView({ config, onError }: { config: ClientConfig; onError: (value: string) => void }) {
  const [results, setResults] = useState<CaptureResult[]>([]);
  const [appName, setAppName] = useState('');
  const [sourceType, setSourceType] = useState('');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const response = await api.recent(config, 75, appName, sourceType);
      setResults(response.results);
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [config.baseUrl, config.apiKey]);

  return (
    <div className="space-y-4">
      <div className="toolbar">
        <Filter size={18} className="text-slate-500" />
        <input className="compact-input" value={appName} onChange={(e) => setAppName(e.target.value)} placeholder="App" />
        <select className="compact-input" value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
          <option value="">All sources</option>
          <option value="accessibility">Accessibility</option>
          <option value="browser">Browser</option>
          <option value="file">File</option>
          <option value="screenshot">Screenshot</option>
        </select>
        <button className="command-button" onClick={load} type="button">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          Refresh
        </button>
      </div>
      <ResultList config={config} query="" results={results} onError={onError} />
    </div>
  );
}

function CollectionsView({ config, onError }: { config: ClientConfig; onError: (value: string) => void }) {
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const response = await api.collections(config);
      setCollections(response.collections);
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [config.baseUrl, config.apiKey]);

  return (
    <div className="space-y-4">
      <div className="toolbar">
        <Layers3 size={18} className="text-slate-500" />
        <div className="min-w-0 flex-1 text-sm text-slate-700">Smart collections are built from pinned captures, topics, apps, domains, and source types.</div>
        <button className="command-button" onClick={load} type="button">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          Refresh
        </button>
      </div>
      <div className="grid gap-4">
        {collections.map((collection) => (
          <section className="surface" key={collection.id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="surface-title">{collection.name}</div>
                <div className="mt-1 text-sm text-slate-600">{collection.description}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="status-pill">{collection.count} captures</span>
                <span className="status-pill">{relativeTime(collection.latest_capture_at)}</span>
              </div>
            </div>
            <div className="mt-3 space-y-3">
              {collection.captures.map((capture) => (
                <CaptureCard key={capture.id} capture={capture} />
              ))}
            </div>
          </section>
        ))}
        {!collections.length && <EmptyState label="No smart collections yet" />}
      </div>
    </div>
  );
}

function DigestView({ config, onError }: { config: ClientConfig; onError: (value: string) => void }) {
  const [digest, setDigest] = useState<WeeklyDigest | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setDigest(await api.weeklyDigest(config));
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [config.baseUrl, config.apiKey]);

  return (
    <div className="space-y-4">
      <div className="toolbar">
        <CalendarDays size={18} className="text-slate-500" />
        <div className="min-w-0 flex-1 text-sm text-slate-700">
          {digest ? `${formatTime(digest.from_timestamp)} to ${formatTime(digest.to_timestamp)}` : 'Weekly memory digest'}
        </div>
        <button className="command-button" onClick={load} type="button">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          Refresh
        </button>
      </div>
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Metric label="Captures" value={digest?.capture_count ?? 0} icon={Database} />
        <Metric label="Keep" value={digest?.keep_count ?? 0} icon={Check} />
        <Metric label="Noise" value={digest?.noise_count ?? 0} icon={X} />
        <Metric label="Pinned" value={digest?.pinned_count ?? 0} icon={Pin} />
        <Metric label="Opened" value={digest?.opened_count ?? 0} icon={ExternalLink} />
        <Metric label="Todos" value={digest?.open_todo_count ?? 0} icon={ClipboardList} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Breakdown title="Top Apps" rows={digest?.top_apps || []} labelKey="app_name" />
        <Breakdown title="Sources" rows={digest?.top_sources || []} labelKey="source_type" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="surface">
          <div className="surface-title">Pinned Highlights</div>
          <div className="mt-3 space-y-3">
            {(digest?.pinned_captures || []).map((capture) => (
              <CaptureCard key={capture.id} capture={capture} />
            ))}
            {digest && !digest.pinned_captures.length && <div className="text-sm text-slate-500">No pinned captures yet.</div>}
          </div>
        </section>
        <section className="surface">
          <div className="surface-title">Opened From Search</div>
          <div className="mt-3 space-y-3">
            {(digest?.opened_captures || []).map((capture) => (
              <CaptureCard key={capture.id} capture={capture} />
            ))}
            {digest && !digest.opened_captures.length && <div className="text-sm text-slate-500">No opened search results this week.</div>}
          </div>
        </section>
      </div>
      <section className="surface">
        <div className="surface-title">Active Collections</div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {(digest?.collections || []).map((collection) => (
            <div className="border border-line bg-panel p-3" key={collection.id}>
              <div className="font-medium text-ink">{collection.name}</div>
              <div className="mt-1 text-sm text-slate-600">{collection.count} captures</div>
            </div>
          ))}
          {digest && !digest.collections.length && <div className="text-sm text-slate-500">No collection activity yet.</div>}
        </div>
      </section>
    </div>
  );
}

function TodoView({
  config,
  onError,
  onToast,
}: {
  config: ClientConfig;
  onError: (value: string) => void;
  onToast: (value: string) => void;
}) {
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [title, setTitle] = useState('');
  const [notes, setNotes] = useState('');
  const [priority, setPriority] = useState(2);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const response = await api.todos(config);
      setTodos(response.todos);
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const addTodo = async () => {
    if (!title.trim()) return;
    try {
      const created = await api.createTodo(config, {
        title: title.trim(),
        notes: notes.trim() || undefined,
        priority,
      });
      setTodos((items) => [created, ...items]);
      setTitle('');
      setNotes('');
      setPriority(2);
      onToast('Todo added');
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  const toggleTodo = async (todo: TodoItem) => {
    try {
      const updated = await api.updateTodo(config, todo.id, {
        status: todo.status === 'open' ? 'done' : 'open',
      });
      setTodos((items) => items.map((item) => (item.id === todo.id ? updated : item)));
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  const removeTodo = async (todo: TodoItem) => {
    if (!window.confirm(`Delete todo "${todo.title}"?`)) return;
    try {
      await api.deleteTodo(config, todo.id);
      setTodos((items) => items.filter((item) => item.id !== todo.id));
      onToast('Todo deleted');
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    void load();
  }, [config.baseUrl, config.apiKey]);

  const openTodos = todos.filter((todo) => todo.status === 'open');
  const doneTodos = todos.filter((todo) => todo.status === 'done');

  return (
    <div className="space-y-4">
      <section className="surface">
        <div className="surface-title">Add Todo</div>
        <div className="mt-4 grid gap-3">
          <input className="settings-input" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Task title" />
          <textarea className="settings-area" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Notes" />
          <div className="flex flex-wrap gap-2">
            <select className="compact-input" value={priority} onChange={(event) => setPriority(Number(event.target.value))}>
              <option value={1}>High priority</option>
              <option value={2}>Normal priority</option>
              <option value={3}>Low priority</option>
            </select>
            <button className="command-button primary" onClick={addTodo} type="button">
              <Plus size={16} />
              Add Todo
            </button>
            <button className="command-button" onClick={load} type="button">
              {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Refresh
            </button>
          </div>
        </div>
      </section>

      <section className="surface">
        <div className="surface-title">Open</div>
        <div className="mt-3 space-y-2">
          {openTodos.map((todo) => (
            <TodoRow key={todo.id} todo={todo} onToggle={toggleTodo} onDelete={removeTodo} />
          ))}
          {!openTodos.length && <div className="text-sm text-slate-500">No open todos.</div>}
        </div>
      </section>

      <section className="surface">
        <div className="surface-title">Done</div>
        <div className="mt-3 space-y-2">
          {doneTodos.map((todo) => (
            <TodoRow key={todo.id} todo={todo} onToggle={toggleTodo} onDelete={removeTodo} />
          ))}
          {!doneTodos.length && <div className="text-sm text-slate-500">No completed todos.</div>}
        </div>
      </section>
    </div>
  );
}

function TodoRow({
  todo,
  onToggle,
  onDelete,
}: {
  todo: TodoItem;
  onToggle: (todo: TodoItem) => void;
  onDelete: (todo: TodoItem) => void;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border border-line bg-white p-3">
      <div className="min-w-0 flex-1">
        <div className={`font-medium ${todo.status === 'done' ? 'text-slate-500 line-through' : 'text-ink'}`}>{todo.title}</div>
        {todo.notes && <div className="mt-1 text-sm text-slate-600">{todo.notes}</div>}
        <div className="mt-2 flex flex-wrap gap-2">
          <span className="status-pill">Priority {todo.priority}</span>
          <span className="status-pill">{todo.status}</span>
        </div>
      </div>
      <div className="flex gap-2">
        <button className="command-button" onClick={() => onToggle(todo)} type="button">
          <Check size={16} />
          {todo.status === 'open' ? 'Done' : 'Reopen'}
        </button>
        <button className="command-button danger" onClick={() => onDelete(todo)} type="button">
          <Trash2 size={16} />
          Delete
        </button>
      </div>
    </div>
  );
}

function LabelView({
  config,
  onError,
  onToast,
}: {
  config: ClientConfig;
  onError: (value: string) => void;
  onToast: (value: string) => void;
}) {
  const [captures, setCaptures] = useState<CaptureResult[]>([]);
  const [labelFilter, setLabelFilter] = useState<'unlabeled' | 'all' | 'keep' | 'noise'>('unlabeled');
  const [appFilter, setAppFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const response = await api.recent(config, 200);
      setCaptures(response.results);
      setSelectedIds(new Set());
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const visibleCaptures = useMemo(
    () =>
      captures.filter((capture) => {
        if (labelFilter === 'unlabeled' && capture.is_noise !== null) return false;
        if (labelFilter === 'keep' && capture.is_noise !== 0) return false;
        if (labelFilter === 'noise' && capture.is_noise !== 1) return false;
        if (appFilter && capture.app_name !== appFilter) return false;
        if (sourceFilter && capture.source_type !== sourceFilter) return false;
        return true;
      }),
    [captures, labelFilter, appFilter, sourceFilter],
  );

  const appOptions = useMemo(
    () => Array.from(new Set(captures.map((capture) => capture.app_name))).sort(),
    [captures],
  );
  const sourceOptions = useMemo(
    () => Array.from(new Set(captures.map((capture) => capture.source_type))).sort(),
    [captures],
  );

  const selectedVisibleIds = useMemo(
    () => visibleCaptures.map((capture) => capture.id).filter((id) => selectedIds.has(id)),
    [visibleCaptures, selectedIds],
  );

  const targetIds = selectedVisibleIds.length ? selectedVisibleIds : visibleCaptures.map((capture) => capture.id);
  const actionScope = selectedVisibleIds.length ? 'selected' : 'visible';

  const setVisibleSelection = (checked: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      visibleCaptures.forEach((capture) => {
        if (checked) {
          next.add(capture.id);
        } else {
          next.delete(capture.id);
        }
      });
      return next;
    });
  };

  const toggleSelection = (captureId: number, checked: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(captureId);
      } else {
        next.delete(captureId);
      }
      return next;
    });
  };

  const labelBatch = async (value: number | null) => {
    if (!targetIds.length) return;
    setSaving(true);
    try {
      const response = await api.bulkLabelNoise(config, targetIds, value);
      const updated = new Set(targetIds);
      setCaptures((items) => items.map((item) => (updated.has(item.id) ? { ...item, is_noise: value } : item)));
      setSelectedIds(new Set());
      onToast(`${labelText(value)} applied to ${response.updated_count} ${actionScope} captures`);
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    void load();
  }, [config.baseUrl, config.apiKey]);

  return (
    <div className="space-y-4">
      <div className="toolbar">
        <select
          className="compact-input"
          value={labelFilter}
          onChange={(e) => setLabelFilter(e.target.value as 'unlabeled' | 'all' | 'keep' | 'noise')}
        >
          <option value="unlabeled">Unlabeled</option>
          <option value="all">All captures</option>
          <option value="keep">Keep</option>
          <option value="noise">Noise</option>
        </select>
        <select className="compact-input" value={appFilter} onChange={(e) => setAppFilter(e.target.value)}>
          <option value="">All apps</option>
          {appOptions.map((appName) => (
            <option key={appName} value={appName}>
              {appName}
            </option>
          ))}
        </select>
        <select className="compact-input" value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
          <option value="">All sources</option>
          {sourceOptions.map((source) => (
            <option key={source} value={source}>
              {source}
            </option>
          ))}
        </select>
        <button className="command-button" onClick={load} type="button">
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          Refresh
        </button>
      </div>
      <div className="toolbar">
        <label className="selection-control">
          <input
            checked={visibleCaptures.length > 0 && selectedVisibleIds.length === visibleCaptures.length}
            onChange={(event) => setVisibleSelection(event.target.checked)}
            type="checkbox"
          />
          <span>{selectedVisibleIds.length || visibleCaptures.length} queued</span>
        </label>
        <button className="label-button keep" disabled={saving || !targetIds.length} onClick={() => labelBatch(0)} type="button">
          <Check size={16} />
          Keep {actionScope}
        </button>
        <button className="label-button noise" disabled={saving || !targetIds.length} onClick={() => labelBatch(1)} type="button">
          <X size={16} />
          Noise {actionScope}
        </button>
        <button className="label-button clear" disabled={saving || !targetIds.length} onClick={() => labelBatch(null)} type="button">
          {saving ? <Loader2 size={15} className="animate-spin" /> : <Circle size={15} />}
          Clear {actionScope}
        </button>
      </div>
      <div className="space-y-3">
        {visibleCaptures.map((capture) => (
          <CaptureCard key={capture.id} capture={capture}>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <label className="selection-control">
                <input
                  checked={selectedIds.has(capture.id)}
                  onChange={(event) => toggleSelection(capture.id, event.target.checked)}
                  type="checkbox"
                />
                <span>Select</span>
              </label>
              <span className="status-pill">{labelText(capture.is_noise)}</span>
            </div>
          </CaptureCard>
        ))}
        {!visibleCaptures.length && <EmptyState label="No captures" />}
      </div>
    </div>
  );
}

function StatsView({
  config,
  stats,
  onStats,
  onError,
  onToast,
}: {
  config: ClientConfig;
  stats: StatsResponse | null;
  onStats: (value: StatsResponse) => void;
  onError: (value: string) => void;
  onToast: (value: string) => void;
}) {
  const [refreshing, setRefreshing] = useState(false);

  const loadStats = async () => {
    try {
      onStats(await api.stats(config));
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  const refreshIndex = async () => {
    setRefreshing(true);
    try {
      const response = await api.refreshIndex(config, 'auto');
      onToast(`Indexed ${response.indexed_count} captures with ${response.backend}`);
      await loadStats();
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadStats();
  }, [config.baseUrl, config.apiKey]);

  const keepCount = useMemo(() => stats?.noise_counts.find((item) => item.is_noise === 0)?.count || 0, [stats]);
  const noiseCount = useMemo(() => stats?.noise_counts.find((item) => item.is_noise === 1)?.count || 0, [stats]);
  const unlabeledCount = useMemo(() => stats?.noise_counts.find((item) => item.is_noise === null)?.count || 0, [stats]);

  return (
    <div className="space-y-4">
      <div className="toolbar">
        <button className="command-button" onClick={loadStats} type="button">
          <RefreshCw size={16} />
          Refresh
        </button>
        <button className="command-button primary" onClick={refreshIndex} type="button">
          {refreshing ? <Loader2 size={16} className="animate-spin" /> : <HardDrive size={16} />}
          Reindex
        </button>
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Captures" value={stats?.total_captures ?? 0} icon={Database} />
        <Metric label="Indexed" value={stats?.indexed_available ? 'Yes' : 'No'} icon={Activity} />
        <Metric label="Keep" value={keepCount} icon={Check} />
        <Metric label="Storage" value={formatBytes(stats?.storage_bytes)} icon={HardDrive} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Breakdown title="Apps" rows={stats?.counts_by_app || []} labelKey="app_name" />
        <Breakdown title="Sources" rows={stats?.counts_by_source_type || []} labelKey="source_type" />
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="surface">
          <div className="surface-title">Labels</div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
            <Badge label="Keep" value={keepCount} />
            <Badge label="Noise" value={noiseCount} />
            <Badge label="Unlabeled" value={unlabeledCount} />
          </div>
          <div className="mt-2 text-sm text-slate-600">Protected: {stats?.protected_captures ?? 0}</div>
        </div>
        <div className="surface">
          <div className="surface-title">Database</div>
          <div className="mt-3 break-all text-sm text-slate-700">{stats?.database_path || 'None'}</div>
          <div className="mt-2 text-sm text-slate-600">Latest: {formatTime(stats?.latest_capture_at || null)}</div>
        </div>
      </div>
    </div>
  );
}

function SettingsView({
  config,
  onConfig,
  onHealth,
  apiKeyEnabled,
  onError,
  onToast,
}: {
  config: ClientConfig;
  onConfig: (value: ClientConfig) => void;
  onHealth: () => void;
  apiKeyEnabled: boolean;
  onError: (value: string) => void;
  onToast: (value: string) => void;
}) {
  const [privacy, setPrivacy] = useState<PrivacySettings>({
    blocked_apps: [],
    blocked_domains: [],
    excluded_path_fragments: [],
  });
  const [storage, setStorage] = useState<StorageStats | null>(null);
  const [policy, setPolicy] = useState<StoragePolicy>({
    mode: 'balanced',
    auto_noise_enabled: true,
    min_text_chars: 180,
    retention_days: 30,
    noise_retention_hours: 24,
    max_database_mb: 1024,
    keep_clicked: true,
    protect_keep_labels: true,
    noise_apps: [],
    noise_domains: [],
  });
  const [forgetHours, setForgetHours] = useState('24');
  const [forgetSource, setForgetSource] = useState('');

  const loadPrivacy = async () => {
    try {
      setPrivacy(await api.privacy(config));
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  const loadStorage = async () => {
    try {
      const response = await api.storage(config);
      setStorage(response);
      setPolicy(response.policy);
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    void loadPrivacy();
    void loadStorage();
  }, [config.baseUrl, config.apiKey]);

  const savePrivacy = async () => {
    try {
      await api.savePrivacy(config, privacy);
      onToast('Privacy settings saved');
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  const saveStorage = async () => {
    try {
      const saved = await api.saveStoragePolicy(config, policy);
      setPolicy(saved);
      await loadStorage();
      onToast('Storage policy saved');
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  const cleanupStorage = async (rebuildIndex = false) => {
    try {
      const result = await api.cleanup(config, rebuildIndex);
      await loadStorage();
      onToast(
        `Deleted ${result.deleted_noise + result.deleted_old + result.deleted_duplicates + result.deleted_for_size} captures`,
      );
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  const exportData = async () => {
    try {
      const data = await api.exportData(config);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `memoryos-export-${new Date().toISOString().slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      onToast('Export ready');
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  const forgetCaptures = async () => {
    const hours = Math.max(1, Number(forgetHours) || 24);
    const from = new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
    try {
      const result = await api.forget(config, {
        from_timestamp: from,
        source_type: forgetSource || undefined,
        confirm: true,
      });
      onToast(`Deleted ${result.deleted_count} captures`);
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  const listValue = (items: string[]) => items.join('\n');
  const updateList = (key: keyof PrivacySettings, value: string) => {
    setPrivacy({
      ...privacy,
      [key]: value
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean),
    });
  };

  const updatePolicyList = (key: 'noise_apps' | 'noise_domains', value: string) => {
    setPolicy({
      ...policy,
      [key]: value
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean),
    });
  };

  return (
    <div className="space-y-4">
      <div className="surface">
        <div className="surface-title">Backend</div>
        <div className="mt-4 grid gap-3">
          <label className="field-label">
            URL
            <input
              className="settings-input"
              value={config.baseUrl}
              onChange={(event) => onConfig({ ...config, baseUrl: event.target.value })}
            />
          </label>
          <label className="field-label">
            API Key
            <input
              className="settings-input"
              value={config.apiKey}
              onChange={(event) => onConfig({ ...config, apiKey: event.target.value })}
              type="password"
            />
          </label>
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Shield size={16} />
            <span>{apiKeyEnabled ? 'Enabled' : 'Disabled'}</span>
          </div>
          <button className="command-button w-fit" onClick={onHealth} type="button">
            <RefreshCw size={16} />
            Check
          </button>
        </div>
      </div>
      <div className="surface">
        <div className="surface-title">Privacy</div>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <label className="field-label">
            Blocked Apps
            <textarea
              className="settings-area"
              value={listValue(privacy.blocked_apps)}
              onChange={(event) => updateList('blocked_apps', event.target.value)}
            />
          </label>
          <label className="field-label">
            Blocked Domains
            <textarea
              className="settings-area"
              value={listValue(privacy.blocked_domains)}
              onChange={(event) => updateList('blocked_domains', event.target.value)}
            />
          </label>
          <label className="field-label">
            Excluded Paths
            <textarea
              className="settings-area"
              value={listValue(privacy.excluded_path_fragments)}
              onChange={(event) => updateList('excluded_path_fragments', event.target.value)}
            />
          </label>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button className="command-button" onClick={savePrivacy} type="button">
            <Check size={16} />
            Save
          </button>
          <button className="command-button" onClick={loadPrivacy} type="button">
            <RefreshCw size={16} />
            Reload
          </button>
        </div>
      </div>
      <div className="surface">
        <div className="surface-title">Storage</div>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <Badge label="Total" value={storage?.total_captures ?? 0} />
          <Badge label="Noise" value={storage?.noise_captures ?? 0} />
          <Badge label="Protected" value={storage?.protected_captures ?? 0} />
          <div className="border border-line bg-panel px-3 py-2">
            <div className="text-xs text-slate-500">Disk</div>
            <div className="mt-1 text-lg font-semibold">{formatBytes(storage?.total_bytes)}</div>
          </div>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <div className="border border-line bg-panel px-3 py-2 text-sm">
            <div className="text-xs text-slate-500">Database</div>
            <div className="mt-1 font-medium">{formatBytes(storage?.database_bytes)}</div>
          </div>
          <div className="border border-line bg-panel px-3 py-2 text-sm">
            <div className="text-xs text-slate-500">Index</div>
            <div className="mt-1 font-medium">{formatBytes(storage?.index_bytes)}</div>
          </div>
          <div className="border border-line bg-panel px-3 py-2 text-sm">
            <div className="text-xs text-slate-500">Logs</div>
            <div className="mt-1 font-medium">{formatBytes(storage?.log_bytes)}</div>
          </div>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-4">
          <label className="field-label">
            Mode
            <select className="settings-input" value={policy.mode} onChange={(event) => setPolicy({ ...policy, mode: event.target.value })}>
              <option value="light">Light</option>
              <option value="balanced">Balanced</option>
              <option value="deep">Deep memory</option>
              <option value="archive">Archive</option>
            </select>
          </label>
          <label className="field-label">
            Retention Days
            <input
              className="settings-input"
              value={policy.retention_days}
              onChange={(event) => setPolicy({ ...policy, retention_days: Number(event.target.value) || 30 })}
              type="number"
            />
          </label>
          <label className="field-label">
            Noise Hours
            <input
              className="settings-input"
              value={policy.noise_retention_hours}
              onChange={(event) => setPolicy({ ...policy, noise_retention_hours: Number(event.target.value) || 24 })}
              type="number"
            />
          </label>
          <label className="field-label">
            Max DB MB
            <input
              className="settings-input"
              value={policy.max_database_mb}
              onChange={(event) => setPolicy({ ...policy, max_database_mb: Number(event.target.value) || 1024 })}
              type="number"
            />
          </label>
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <label className="field-label">
            Noise Apps
            <textarea
              className="settings-area"
              value={policy.noise_apps.join('\n')}
              onChange={(event) => updatePolicyList('noise_apps', event.target.value)}
            />
          </label>
          <label className="field-label">
            Noise Domains
            <textarea
              className="settings-area"
              value={policy.noise_domains.join('\n')}
              onChange={(event) => updatePolicyList('noise_domains', event.target.value)}
            />
          </label>
        </div>
        <div className="mt-3 flex flex-wrap gap-3 text-sm text-slate-700">
          <label className="selection-control">
            <input
              checked={policy.auto_noise_enabled}
              onChange={(event) => setPolicy({ ...policy, auto_noise_enabled: event.target.checked })}
              type="checkbox"
            />
            <span>Auto-noise</span>
          </label>
          <label className="selection-control">
            <input
              checked={policy.keep_clicked}
              onChange={(event) => setPolicy({ ...policy, keep_clicked: event.target.checked })}
              type="checkbox"
            />
            <span>Protect clicked</span>
          </label>
          <label className="selection-control">
            <input
              checked={policy.protect_keep_labels}
              onChange={(event) => setPolicy({ ...policy, protect_keep_labels: event.target.checked })}
              type="checkbox"
            />
            <span>Protect keep labels</span>
          </label>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button className="command-button" onClick={saveStorage} type="button">
            <Check size={16} />
            Save Policy
          </button>
          <button className="command-button" onClick={loadStorage} type="button">
            <RefreshCw size={16} />
            Refresh Storage
          </button>
          <button className="command-button danger" onClick={() => cleanupStorage(false)} type="button">
            <X size={16} />
            Clean Up
          </button>
          <button className="command-button danger" onClick={() => cleanupStorage(true)} type="button">
            <HardDrive size={16} />
            Clean + Reindex
          </button>
        </div>
      </div>
      <div className="surface">
        <div className="surface-title">Data Controls</div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="command-button" onClick={exportData} type="button">
            <ExternalLink size={16} />
            Export JSON
          </button>
          <input
            className="compact-input"
            value={forgetHours}
            onChange={(event) => setForgetHours(event.target.value)}
            inputMode="numeric"
            aria-label="Forget hours"
          />
          <select className="compact-input" value={forgetSource} onChange={(event) => setForgetSource(event.target.value)}>
            <option value="">All sources</option>
            <option value="accessibility">Accessibility</option>
            <option value="browser">Browser</option>
            <option value="file">File</option>
            <option value="screenshot">Screenshot</option>
          </select>
          <button className="command-button danger" onClick={forgetCaptures} type="button">
            <X size={16} />
            Forget Hours
          </button>
        </div>
      </div>
    </div>
  );
}

function ResultList({
  config,
  query,
  results,
  resultsLoadedAt,
  onError,
}: {
  config: ClientConfig;
  query: string;
  results: CaptureResult[];
  resultsLoadedAt?: number | null;
  onError: (value: string) => void;
}) {
  const [localPins, setLocalPins] = useState<Record<number, boolean>>({});

  useEffect(() => {
    const next: Record<number, boolean> = {};
    results.forEach((capture) => {
      next[capture.id] = Boolean(capture.is_pinned);
    });
    setLocalPins(next);
  }, [results]);

  const handleOpen = async (capture: CaptureResult) => {
    const dwellMs = resultsLoadedAt ? Date.now() - resultsLoadedAt : undefined;
    let openedByBackend = false;
    if (capture.url || capture.file_path) {
      try {
        await api.openCapture(config, capture.id);
        openedByBackend = true;
      } catch (err) {
        onError(err instanceof Error ? err.message : String(err));
      }
    }
    if (query.trim()) {
      try {
        await api.logClick(config, query.trim(), capture.id, capture.rank, dwellMs);
      } catch (err) {
        onError(err instanceof Error ? err.message : String(err));
      }
    }
    if (!openedByBackend) {
      openCapture(capture);
    }
  };

  const handlePin = async (capture: CaptureResult) => {
    const next = !(localPins[capture.id] ?? Boolean(capture.is_pinned));
    try {
      await api.pinCapture(config, capture.id, next);
      setLocalPins((current) => ({ ...current, [capture.id]: next }));
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  if (!results.length) return <EmptyState label="No results" />;

  return (
    <div className="space-y-3">
      {results.map((capture) => (
        <CaptureCard key={capture.id} capture={capture} pinned={localPins[capture.id] ?? Boolean(capture.is_pinned)}>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button className="command-button" onClick={() => handlePin(capture)} type="button">
              {(localPins[capture.id] ?? Boolean(capture.is_pinned)) ? <PinOff size={16} /> : <Pin size={16} />}
              {(localPins[capture.id] ?? Boolean(capture.is_pinned)) ? 'Unpin' : 'Pin'}
            </button>
            {(capture.url || capture.file_path) && (
              <button className="command-button" onClick={() => handleOpen(capture)} type="button">
                <ExternalLink size={16} />
                Open
              </button>
            )}
            <span className="status-pill">{labelText(capture.is_noise)}</span>
            {capture.similarity_score !== null && <span className="status-pill">Similarity {capture.similarity_score.toFixed(3)}</span>}
            {capture.rerank_score !== null && <span className="status-pill">Rank {capture.rerank_score.toFixed(3)}</span>}
          </div>
        </CaptureCard>
      ))}
    </div>
  );
}

function CaptureCard({
  capture,
  pinned,
  children,
}: {
  capture: CaptureResult;
  pinned?: boolean;
  children?: ReactNode;
}) {
  const isPinned = pinned ?? Boolean(capture.is_pinned);
  return (
    <article className="capture-card">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold">
            {capture.window_title || capture.url || capture.file_path || `Capture ${capture.id}`}
          </h2>
          <div className="mt-1 text-sm text-slate-600">{sourceLabel(capture)}</div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {isPinned && (
            <span className="status-pill">
              <Pin size={13} />
              Pinned
            </span>
          )}
          <div className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">#{capture.id}</div>
        </div>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-800">{capture.snippet}</p>
      {children}
    </article>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex min-h-[180px] items-center justify-center border border-dashed border-line bg-white text-sm text-slate-500">
      {label}
    </div>
  );
}

function Metric({ label, value, icon: Icon }: { label: string; value: string | number; icon: typeof Database }) {
  return (
    <div className="surface">
      <div className="flex items-center justify-between">
        <div className="text-sm text-slate-600">{label}</div>
        <Icon size={17} className="text-signal" />
      </div>
      <div className="mt-3 text-2xl font-semibold">{value}</div>
    </div>
  );
}

function Breakdown({
  title,
  rows,
  labelKey,
}: {
  title: string;
  rows: Array<Record<string, string | number>>;
  labelKey: string;
}) {
  return (
    <div className="surface">
      <div className="surface-title">{title}</div>
      <div className="mt-3 divide-y divide-line">
        {rows.map((row) => (
          <div key={String(row[labelKey])} className="flex items-center justify-between gap-4 py-2 text-sm">
            <span className="truncate text-slate-700">{row[labelKey]}</span>
            <span className="font-medium">{row.count}</span>
          </div>
        ))}
        {!rows.length && <div className="py-2 text-sm text-slate-500">None</div>}
      </div>
    </div>
  );
}

function Badge({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-line bg-panel px-3 py-2">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}
