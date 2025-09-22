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

  const Trend = ({label, values, color}:{label:string, values:number[], color:string}) => {
    const w=320, h=60; const max = Math.max(1, ...values);
    const pts = values.map((v,i)=> `${(i/(values.length-1||1))*w},${h - (v/max)*h}`).join(' ');
    return (
      <div style={{ marginRight: 20 }}>
        <div style={{ fontSize:12, marginBottom:4 }}>{label}</div>
        <svg width={w} height={h} style={{ background:'#111', border:'1px solid #333' }}>
          <polyline points={pts} fill="none" stroke={color} strokeWidth={2} />
        </svg>
      </div>
    );
  };

  const metricsArr = (name:string) => (data?.items||[])
    .map((r:any)=> r?.summary?.performance?.metrics?.[name])
    .filter((x:any)=> typeof x==='number');

  return (
    <div>
      <a href={`/sessions/${id}`}>← Back</a>
      <h2>Results for {id}</h2>
      {loading && <p>Loading…</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <div style={{ margin: '8px 0' }}>
        <button onClick={compare} disabled={selected.length!==2}>Compare selected</button>
      </div>
      {data?.items?.length>1 && (
        <div style={{ display:'flex', margin:'8px 0' }}>
          <Trend label='LCP(ms)' values={metricsArr('lcp') as number[]} color="#5cb85c" />
          <Trend label='CLS' values={metricsArr('cls') as number[]} color="#f0ad4e" />
          <Trend label='TTI(ms)' values={metricsArr('tti') as number[]} color="#d9534f" />
        </div>
      )}
      <table cellPadding={6} border={1} style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr><th></th><th>Result ID</th><th>Created</th><th>Perf</th><th>ZAP</th><th>Summary</th><th>Alerts</th></tr>
        </thead>
        <tbody>
          {data?.items?.map((r:any) => {
            const alerts = r?.summary?.security?.alerts || [];
            const perfScore = r?.summary?.performance?.performance_score;
            const counts = r?.summary?.security?.counts || {};
            return (
              <tr key={r.id}>
                <td><input type="checkbox" checked={selected.includes(r.id)} onChange={()=>toggle(r.id)} /></td>
                <td>{r.id}</td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td>{typeof perfScore==='number'? perfScore: ''}</td>
                <td>{`H${counts.High||0}/M${counts.Medium||0}/L${counts.Low||0}`}</td>
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
