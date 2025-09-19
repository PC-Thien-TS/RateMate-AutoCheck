"use client";

import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'dev-key';

export default function ResultsPage({ params }: { params: { id: string }}) {
  const id = params.id;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number[]>([]);

  useEffect(() => {
    setLoading(true); setError(null);
    fetch(`${API}/api/sessions/${id}/results?limit=50`, { headers: { 'x-api-key': API_KEY }})
      .then(r => r.json()).then(setData).catch(e=> setError(String(e))).finally(()=> setLoading(false));
  }, [id]);

  const toggle = (rid: number) => {
    setSelected(s => s.includes(rid) ? s.filter(x=>x!==rid) : [...s, rid].slice(0,2));
  };

  const compare = () => {
    if (selected.length !== 2) return alert('Select exactly 2 results to compare');
    const [l,r] = selected;
    window.location.href = `/sessions/${id}/diff?l=${l}&r=${r}`;
  };

  return (
    <div>
      <a href={`/sessions/${id}`}>← Back</a>
      <h2>Results for {id}</h2>
      {loading && <p>Loading…</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <div style={{ margin: '8px 0' }}>
        <button onClick={compare} disabled={selected.length!==2}>Compare selected</button>
      </div>
      <table cellPadding={6} border={1} style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr><th></th><th>Result ID</th><th>Created</th><th>Summary</th><th>Alerts</th></tr>
        </thead>
        <tbody>
          {data?.items?.map((r:any) => {
            const alerts = r?.summary?.security?.alerts || [];
            return (
              <tr key={r.id}>
                <td><input type="checkbox" checked={selected.includes(r.id)} onChange={()=>toggle(r.id)} /></td>
                <td>{r.id}</td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td><pre style={{ whiteSpace:'pre-wrap', maxWidth: '800px', overflow:'auto' }}>{JSON.stringify({ performance: r.summary?.performance?.performance_score, policy: r.summary?.policy }, null, 2)}</pre></td>
                <td>
                  <div>{alerts.length} alerts</div>
                  <a href={`${API}/api/results/${r.id}/alerts.csv`} target="_blank">CSV</a>
                  <span> | </span>
                  <a href={`${API}/api/results/${r.id}/alerts.json`} target="_blank">JSON</a>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
