"use client";

import { useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev-key";

function useSessions(params: Record<string, string | number>) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const query = useMemo(() => new URLSearchParams(params as any).toString(), [params]);
  useEffect(() => {
    setLoading(true); setError(null);
    fetch(`${API}/api/sessions?${query}`, { headers: { 'x-api-key': API_KEY } })
      .then(r => r.json())
      .then(setData)
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, [query]);
  return { data, loading, error };
}

export default function Home() {
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [project, setProject] = useState("");
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const { data, loading, error } = useSessions({ limit, offset, project, kind, status });

  return (
    <div>
      <section style={{ marginBottom: 12 }}>
        <label>Project: <input value={project} onChange={e=>setProject(e.target.value)} /></label>
        <label style={{ marginLeft: 12 }}>Kind: <input placeholder="web/mobile" value={kind} onChange={e=>setKind(e.target.value)} /></label>
        <label style={{ marginLeft: 12 }}>Status: <input placeholder="completed/failed" value={status} onChange={e=>setStatus(e.target.value)} /></label>
        <label style={{ marginLeft: 12 }}>Limit: <input type="number" value={limit} onChange={e=>setLimit(parseInt(e.target.value||"20"))} style={{ width: 60 }} /></label>
        <button onClick={() => setOffset(0)} style={{ marginLeft: 12 }}>Apply</button>
      </section>

      {loading && <p>Loading…</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      <table cellPadding={6} border={1} style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr><th>ID</th><th>Project</th><th>Kind</th><th>Type</th><th>Status</th><th>Created</th></tr>
        </thead>
        <tbody>
        {data?.items?.map((s: any) => (
          <tr key={s.id}>
            <td><a href={`/sessions/${s.id}`}>{s.id.slice(0,8)}…</a></td>
            <td>{s.project || ''}</td>
            <td>{s.kind}</td>
            <td>{s.test_type}</td>
            <td>{s.status}</td>
            <td>{new Date(s.created_at).toLocaleString()}</td>
          </tr>
        ))}
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

