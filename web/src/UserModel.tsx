import { BrainCircuit, Play, RefreshCw, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { api, AbstractionRun, AbstractionStatus, Belief, ClientConfig, UserModelData } from './api';

const beliefTypes = ['all', 'interest', 'knowledge', 'gap', 'pattern', 'project'];

const typeClass: Record<string, string> = {
  interest: 'border-l-signal',
  knowledge: 'border-l-moss',
  gap: 'border-l-rust',
  pattern: 'border-l-indigo-500',
  project: 'border-l-amber-600',
};

function formatDate(value: string | null) {
  if (!value) return 'never';
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function confidenceLabel(value: number) {
  return `${Math.round(value * 100)}% confidence`;
}

export default function UserModel({
  config,
  onError,
  onToast,
}: {
  config: ClientConfig;
  onError: (value: string) => void;
  onToast: (value: string) => void;
}) {
  const [model, setModel] = useState<UserModelData | null>(null);
  const [beliefs, setBeliefs] = useState<Belief[]>([]);
  const [runs, setRuns] = useState<AbstractionRun[]>([]);
  const [status, setStatus] = useState<AbstractionStatus | null>(null);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [modelResponse, beliefsResponse, runsResponse, statusResponse] = await Promise.all([
        api.userModel(config),
        api.beliefs(config, '', 0, 100),
        api.abstractionRuns(config, 8),
        api.abstractionStatus(config),
      ]);
      setModel(modelResponse.status === 'no_model' ? null : modelResponse);
      setBeliefs(beliefsResponse.beliefs);
      setRuns(runsResponse.runs);
      setStatus(statusResponse);
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

  const filteredBeliefs = useMemo(
    () => (filter === 'all' ? beliefs : beliefs.filter((belief) => belief.belief_type === filter)),
    [beliefs, filter],
  );

  const runNow = async () => {
    setRunning(true);
    try {
      const response = await api.runAbstraction(config);
      onToast(response.message);
      onError('');
      window.setTimeout(() => {
        void load();
        setRunning(false);
      }, 8000);
    } catch (err) {
      setRunning(false);
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  const removeBelief = async (belief: Belief) => {
    if (!window.confirm(`Delete belief "${belief.topic}"?`)) return;
    try {
      await api.deleteBelief(config, belief.topic);
      setBeliefs((items) => items.filter((item) => item.topic !== belief.topic));
      onToast('Belief deleted');
      onError('');
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="space-y-4">
      <section className="surface">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="surface-title">You</div>
            <div className="mt-1 text-sm text-slate-600">Local user model built from recent non-noise captures.</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className={`status-pill ${status?.ollama_running ? 'text-moss' : 'text-rust'}`}>
              Ollama {status?.ollama_running ? 'online' : 'offline'}
            </span>
            <span className="status-pill">{status?.model || 'mistral'}</span>
            <button className="command-button" onClick={load} type="button">
              <RefreshCw size={16} />
              Refresh
            </button>
            <button className="command-button primary" disabled={running || status?.running} onClick={runNow} type="button">
              <Play size={16} />
              {running || status?.running ? 'Running' : 'Run Now'}
            </button>
          </div>
        </div>
      </section>

      {loading && <div className="surface text-sm text-slate-600">Loading user model...</div>}

      {!loading && !model && !beliefs.length && (
        <section className="surface border-dashed text-center">
          <BrainCircuit className="mx-auto text-slate-400" size={34} />
          <div className="mt-3 font-medium text-ink">No user model yet</div>
          <div className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">
            Start Ollama locally, make sure the `mistral` model is available, then run abstraction. The backend will store
            beliefs and a summary locally in SQLite.
          </div>
          <code className="mt-3 inline-block border border-line bg-panel px-3 py-2 text-xs text-slate-700">ollama serve</code>
        </section>
      )}

      {model && (
        <section className="surface">
          <div className="text-base font-medium text-ink">Current Model</div>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-700">{model.summary}</p>
          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <ModelList title="Top Interests" items={model.top_interests} />
            <ModelList title="Active Projects" items={model.active_projects} />
            <ModelList title="Knowledge Gaps" items={model.knowledge_gaps} />
          </div>
          {model.work_rhythm && <div className="mt-4 text-sm text-slate-600">{model.work_rhythm}</div>}
          <div className="mt-3 text-xs text-slate-500">Updated {formatDate(model.generated_at)}</div>
        </section>
      )}

      <section className="surface">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="surface-title">Beliefs</div>
          <div className="flex flex-wrap gap-2">
            {beliefTypes.map((type) => (
              <button
                className={`label-button clear ${filter === type ? 'border-ink bg-ink text-white hover:bg-slate-800' : ''}`}
                key={type}
                onClick={() => setFilter(type)}
                type="button"
              >
                {type}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-4 space-y-3">
          {filteredBeliefs.map((belief) => (
            <article className={`border border-line border-l-4 bg-white p-3 ${typeClass[belief.belief_type] || 'border-l-line'}`} key={belief.topic}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="truncate text-sm font-semibold text-ink">{belief.topic}</h3>
                    <span className="status-pill">{belief.belief_type}</span>
                    <span className="status-pill">{belief.depth || 'surface'}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{belief.summary}</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span>{confidenceLabel(belief.confidence)}</span>
                    <span>reinforced {belief.times_reinforced}x</span>
                    <span>updated {formatDate(belief.last_updated)}</span>
                  </div>
                </div>
                <button className="icon-button" onClick={() => removeBelief(belief)} title="Delete belief" type="button">
                  <Trash2 size={15} />
                </button>
              </div>
            </article>
          ))}
          {!filteredBeliefs.length && <div className="text-sm text-slate-500">No beliefs for this filter.</div>}
        </div>
      </section>

      <section className="surface">
        <div className="surface-title">Abstraction Runs</div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead className="border-b border-line text-xs uppercase text-slate-500">
              <tr>
                <th className="py-2 pr-3">Started</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Captures</th>
                <th className="py-2 pr-3">Written</th>
                <th className="py-2 pr-3">Updated</th>
                <th className="py-2 pr-3">Error</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr className="border-b border-line last:border-b-0" key={run.id}>
                  <td className="py-2 pr-3">{formatDate(run.started_at)}</td>
                  <td className="py-2 pr-3">{run.status}</td>
                  <td className="py-2 pr-3">{run.captures_read}</td>
                  <td className="py-2 pr-3">{run.beliefs_written}</td>
                  <td className="py-2 pr-3">{run.beliefs_updated}</td>
                  <td className="max-w-xs truncate py-2 pr-3 text-rust">{run.error || ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!runs.length && <div className="mt-3 text-sm text-slate-500">No abstraction runs yet.</div>}
        </div>
      </section>
    </div>
  );
}

function ModelList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase text-slate-500">{title}</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {items.map((item) => (
          <span className="status-pill" key={item}>
            {item}
          </span>
        ))}
        {!items.length && <span className="text-sm text-slate-500">None yet</span>}
      </div>
    </div>
  );
}
