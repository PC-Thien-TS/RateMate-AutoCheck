'use client';

import { useEffect, useMemo, useState, Suspense } from "react";
import { useSearchParams } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev-key";

function useSessions(params: Record<string, string | number>) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const query = useMemo(() => new URLSearchParams(params as any).toString(), [params]);
  useEffect(() => {
    setLoading(true); setError(null);
    fetch(`${API}/api/sessions?${query}&api_key=${encodeURIComponent(API_KEY)}`, { headers: { 'x-api-key': API_KEY } })
      .then(async r => { if (!r.ok) throw new Error(await r.text().catch(()=>r.statusText)); return r.json(); })
      .then(setData)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, [query]);
  return { data, loading, error };
}

function HomeClient() {
  const searchParams = useSearchParams();
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [project, setProject] = useState(searchParams.get('project') || "");
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [testType, setTestType] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const { data, loading, error } = useSessions({ limit, offset, project, kind, status, test_type: testType, since, until });
  const [jobs, setJobs] = useState<Record<string, any>>({});
  const [auto, setAuto] = useState(true);

  useEffect(() => {
    // Update project from URL if it changes
    setProject(searchParams.get('project') || '');
  }, [searchParams]);

  // Enrich with job status for perf/security/links; poll if any pending
  useEffect(() => {
    let timer: any;
    const load = async () => {
      if (!data?.items) return;
      const ids: string[] = data.items.map((s: any) => s.id);
      try {
        const entries = await Promise.all(ids.map(async (id) => {
          const res = await fetch(`${API}/api/jobs/${id}?api_key=${encodeURIComponent(API_KEY)}`, { headers: { 'x-api-key': API_KEY } });
          if (!res.ok) return [id, null] as const;
          const j = await res.json();
          return [id, j] as const;
        }));
        const map: Record<string, any> = {};
        for (const [id, j] of entries) map[id] = j;
        setJobs(map);
        const hasPending = Object.values(map).some((j: any) => j && (j.status === 'queued' || j.status === 'running'));
        if (auto && hasPending) timer = setTimeout(load, 3000);
      } catch (_) {}
    };
    load();
    return () => { if (timer) clearTimeout(timer); };
  }, [JSON.stringify(data?.items), auto]);

  const rerun = async (id: string) => {
    try {
      const j = jobs[id];
      if (!j) return alert('No job payload');
      const payload = j.payload || {};
      const kind = (j.kind || 'web').toLowerCase();
      const path = kind === 'mobile' ? '/api/test/mobile' : '/api/test/web';
      const res = await fetch(`${API}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY }, body: JSON.stringify(payload) });
      const js = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(js));
      window.location.href = `/sessions/${js.job_id}`;
    } catch (e: any) { alert('Re-run failed: ' + (e?.message || String(e))); }
  };

  return (
    <div>
      <section style={{ marginBottom: 12 }}>
        <label>Kind: 
          <select value={kind} onChange={e=>setKind(e.target.value)}>
            <option value="">(all)</option>
            <option value="web">web</option>
            <option value="mobile">mobile</option>
          </select>
        </label>
        <label style={{ marginLeft: 12 }}>Status: 
          <select value={status} onChange={e=>setStatus(e.target.value)}>
            <option value="">(all)</option>
            <option value="queued">queued</option>
            <option value="running">running</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
            <option value="canceled">canceled</option>
          </select>
        </label>
        <label style={{ marginLeft: 12 }}>Type: 
          <select value={testType} onChange={e=>setTestType(e.target.value)}>
            <option value="">(all)</option>
            <option value="smoke">smoke</option>
            <option value="auto">auto</option>
            <option value="performance">performance</option>
            <option value="security">security</option>
            <option value="analyze">analyze</option>
          </select>
        </label>
        <label style={{ marginLeft: 12 }}>Since: <input type="datetime-local" value={since} onChange={e=>setSince(e.target.value)} /></label>
        <label style={{ marginLeft: 12 }}>Until: <input type="datetime-local" value={until} onChange={e=>setUntil(e.target.value)} /></label>
        <label style={{ marginLeft: 12 }}>Limit: <input type="number" value={limit} onChange={e=>setLimit(parseInt(e.target.value||"20"))} style={{ width: 60 }} /></label>
        <button onClick={() => setOffset(0)} style={{ marginLeft: 12 }}>Apply</button>
        <label style={{ marginLeft: 12 }}><input type="checkbox" checked={auto} onChange={e=>setAuto(e.target.checked)} /> Auto-refresh</label>
      </section>

      {loading && <p>Loading…</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      <table cellPadding={6} border={1} style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr><th>ID</th><th>Project</th><th>Kind</th><th>Type</th><th>Status</th><th>Perf</th><th>ZAP</th><th>Reports</th><th>Created</th><th>Actions</th></tr>
        </thead>
        <tbody>
        {data?.items?.map((s: any) => {
          const j = jobs[s.id];
          const status = j?.status || s.status;
          const badge = (st:string) => {
            const color = st==='failed'?'#fff0f0': st==='completed'?'#f0fff0': st==='running'?'#fffbe6':'#f0f0f0';
            return (<span style={{ background: color, padding: '2px 6px', borderRadius: 4 }}>{st}</span>);
          };
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
              <td>{badge(status)}</td>
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
        <button disabled={offset===0} onClick={()=> setOffset(Math.max(0, offset - limit))}>Prev</button>
        <span style={{ margin: '0 8px' }}>offset: {offset}</span>
        <button onClick={()=> setOffset(offset + limit)}>Next</button>
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
