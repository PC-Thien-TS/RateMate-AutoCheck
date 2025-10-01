'use client';

import { useEffect, useMemo, useState, Suspense, FC, useReducer } from "react";
import { useSearchParams, useRouter } from 'next/navigation'; // eslint-disable-line
import SiteSwitcher from "../components/SiteSwitcher"; // eslint-disable-line

interface Session {
  id: string;
  project: string;
  kind: 'web' | 'mobile';
  test_type: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'canceled';
  created_at: string;
}

interface PaginatedSessions {
  items: Session[];
  total: number;
  limit: number;
  offset: number;
}

interface Job {
  id: string;
  status: Session['status'];
  kind: Session['kind'];
  payload: Record<string, any>;
  performance?: { performance_score?: number };
  security?: { counts?: { High?: number; Medium?: number; Low?: number } };
  artifact_urls?: {
    perf_html?: { presigned_url: string };
    zap_html?: { presigned_url: string };
  };
}

function useSessions(params: Record<string, string | number | undefined>) {
  const [data, setData] = useState<PaginatedSessions | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const query = useMemo(() => new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v !== undefined)) as Record<string, string>).toString(), [params]);
  useEffect(() => {
    setLoading(true); setError(null);
    fetch(`/api/proxy/api/sessions?${query}`)
      .then(async r => { if (!r.ok) throw new Error(await r.text().catch(()=>r.statusText)); return r.json(); })
      .then(setData)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, [query]);
  return { data, loading, error };
}
interface FiltersProps {
  filterState: FilterState;
  dispatch: import("react").Dispatch<FilterAction>;
  onApply: () => void; // eslint-disable-line
}

const Filters: FC<FiltersProps> = ({ filterState, dispatch, onApply }) => (
  <section style={{ marginBottom: 12, display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
    <SiteSwitcher />
    <label>Kind:
      <select value={filterState.kind} onChange={e => dispatch({ type: 'SET_KIND', payload: e.target.value })}>
        <option value="">(all)</option>
        <option value="web">web</option>
        <option value="mobile">mobile</option>
      </select>
    </label>
    <label>Status:
      <select value={filterState.status} onChange={e => dispatch({ type: 'SET_STATUS', payload: e.target.value })}>
        <option value="">(all)</option>
        <option value="queued">queued</option>
        <option value="running">running</option>
        <option value="completed">completed</option>
        <option value="failed">failed</option>
        <option value="canceled">canceled</option>
      </select>
    </label>
    <label>Type:
      <select value={filterState.testType} onChange={e => dispatch({ type: 'SET_TEST_TYPE', payload: e.target.value })}>
        <option value="">(all)</option>
        <option value="smoke">smoke</option>
        <option value="auto">auto</option>
        <option value="performance">performance</option>
        <option value="security">security</option>
        <option value="analyze">analyze</option>
      </select>
    </label>
    <label>Since: <input type="datetime-local" value={filterState.since} onChange={e => dispatch({ type: 'SET_SINCE', payload: e.target.value })} /></label>
    <label>Until: <input type="datetime-local" value={filterState.until} onChange={e => dispatch({ type: 'SET_UNTIL', payload: e.target.value })} /></label>
    <label>Limit: <input type="number" value={filterState.limit} onChange={e => dispatch({ type: 'SET_LIMIT', payload: parseInt(e.target.value || "20") })} style={{ width: 60 }} /></label>
    <button onClick={onApply}>Apply</button>
  </section>
);

type FilterState = {
  limit: number;
  kind: string;
  status: string;
  testType: string;
  since: string;
  until: string;
};

type FilterAction =
  | { type: 'SET_LIMIT'; payload: number }
  | { type: 'SET_KIND'; payload: string }
  | { type: 'SET_STATUS'; payload: string }
  | { type: 'SET_TEST_TYPE'; payload: string }
  | { type: 'SET_SINCE'; payload: string }
  | { type: 'SET_UNTIL'; payload: string };

const initialFilterState: FilterState = {
  limit: 20,
  kind: "",
  status: "",
  testType: "",
  since: "",
  until: "",
};

function filterReducer(state: FilterState, action: FilterAction): FilterState {
  switch (action.type) {
    case 'SET_LIMIT': return { ...state, limit: action.payload };
    case 'SET_KIND': return { ...state, kind: action.payload };
    case 'SET_STATUS': return { ...state, status: action.payload };
    case 'SET_TEST_TYPE': return { ...state, testType: action.payload };
    case 'SET_SINCE': return { ...state, since: action.payload };
    case 'SET_UNTIL': return { ...state, until: action.payload };
    default: return state;
  }
}

function HomeClient() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const project = searchParams.get('project') || "";

  const [offset, setOffset] = useState(0);
  const [filterState, dispatch] = useReducer(filterReducer, initialFilterState);

  const { data, loading, error } = useSessions({
    limit: filterState.limit,
    offset,
    project,
    kind: filterState.kind,
    status: filterState.status,
    test_type: filterState.testType,
    since: filterState.since ? new Date(filterState.since).toISOString() : undefined,
    until: filterState.until ? new Date(filterState.until).toISOString() : undefined
  });
  const [jobs, setJobs] = useState<Record<string, Job | null>>({});
  const [auto, setAuto] = useState(true);

  // Enrich with job status for perf/security/links; poll if any pending
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      if (!data?.items) return;
      const ids: string[] = data.items.map((s) => s.id);
      try {
        const entries = await Promise.all(ids.map(async (id) => {
          const res = await fetch(`/api/proxy/api/jobs/${id}`);
          if (!res.ok) return [id, null] as const;
          const j: Job = await res.json();
          return [id, j] as const;
        }));
        const map: Record<string, Job | null> = {};
        for (const [id, j] of entries) map[id] = j;
        setJobs(map);
        const hasPending = Object.values(map).some((j) => j && (j.status === 'queued' || j.status === 'running'));
        if (auto && hasPending) timer = setTimeout(load, 3000);
      } catch (e) { console.warn('Failed to poll job statuses:', e); }
    };
    load();
    return () => { if (timer) clearTimeout(timer); };
  }, [data, auto]);

  const rerun = async (id: string) => {
    try {
      const j = jobs[id];
      if (!j) return alert('No job payload');
      const payload = j.payload || {};
      const kind = (j.kind || 'web').toLowerCase();
      const path = kind === 'mobile' ? '/api/test/mobile' : '/api/test/web';
      const res = await fetch(`/api/proxy${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const js = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(js));
      router.push(`/sessions/${js.job_id}`);
    } catch (e: any) { alert('Re-run failed: ' + (e?.message || String(e))); }
  };

  const badge = (st:string) => {
    const color = st==='failed'?'#fff0f0': st==='completed'?'#f0fff0': st==='running'?'#fffbe6':'#f0f0f0';
    return (<span style={{ background: color, padding: '2px 6px', borderRadius: 4 }}>{st}</span>);
  };
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Filters filterState={filterState} dispatch={dispatch} onApply={() => setOffset(0)} />
        <label><input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} /> Auto-refresh</label>
      </div>

      {loading && <p>Loading…</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      <table cellPadding={6} border={1} style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr><th>ID</th><th>Project</th><th>Kind</th><th>Type</th><th>Status</th><th>Perf Score</th><th>ZAP Alerts</th><th>Reports</th><th>Created</th><th>Actions</th></tr>
        </thead>
        <tbody>
        {data?.items?.map((s: Session) => {
          const j = jobs[s.id];
          const status = j?.status || s.status;
          const perfScore = j?.performance?.performance_score;
          const zap = j?.security?.counts;
          const perfUrl = j?.artifact_urls?.perf_html?.presigned_url;
          const zapUrl = j?.artifact_urls?.zap_html?.presigned_url;
          return (
            <tr key={s.id}>
              <td><a href={`/sessions/${s.id}`}>{s.id.slice(0,8)}…</a></td>
              <td>{s.project || ''}</td>
              <td>{s.kind}</td>
              <td>{s.test_type}</td>
              <td>{badge(status as string)}</td>
              <td>{typeof perfScore==='number'? perfScore: ''}</td>
              <td>{zap? `H${zap.High||0}/M${zap.Medium||0}/L${zap.Low||0}`: ''}</td>
              <td>
                {perfUrl && <a href={perfUrl} target="_blank" rel="noreferrer">Perf</a>} {zapUrl && <a href={zapUrl} target="_blank" rel="noreferrer" style={{ marginLeft: 8 }}>ZAP</a>}
              </td>
              <td>{new Date(s.created_at).toLocaleString()}</td>
              <td><button onClick={()=>rerun(s.id)} disabled={!j?.payload}>Re-run</button></td>
            </tr>
          );
        })}
        </tbody>
      </table>

      <div style={{ marginTop: 12 }}>
        <button disabled={offset===0} onClick={()=> setOffset(Math.max(0, offset - filterState.limit))}>Prev</button>
        <span style={{ margin: '0 8px' }}>offset: {offset}</span>
        <button disabled={!data || offset + filterState.limit >= data.total} onClick={()=> setOffset(offset + filterState.limit)}>Next</button>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <HomeClient />
    </Suspense>
  );
}
