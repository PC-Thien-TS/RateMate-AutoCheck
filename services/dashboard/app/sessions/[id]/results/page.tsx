"use client";

import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'dev-key';
const S3_PUBLIC = process.env.NEXT_PUBLIC_S3_PUBLIC || 'http://localhost:9000';

function rewriteUrl(u?: string | null): string | undefined {
  if (!u) return u as any;
  try {
    const src = new URL(u);
    if (src.host.startsWith('minio:')) {
      const pub = new URL(S3_PUBLIC);
      src.host = pub.host;
      src.protocol = pub.protocol as any;
      return src.toString();
    }
    return u;
  } catch { return u; }
}

export default function ResultsPage({ params }: { params: { id: string }}) {
  const id = params.id;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number[]>([]);

  useEffect(() => {
    setLoading(true); setError(null);
    fetch(`${API}/api/sessions/${id}/results?limit=50&api_key=${encodeURIComponent(API_KEY)}`, { headers: { 'x-api-key': API_KEY }})
      .then(async r => { if (!r.ok) throw new Error(await r.text().catch(()=>r.statusText)); return r.json(); })
      .then(setData).catch(e=> setError(String(e))).finally(()=> setLoading(false));
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
            const cases: any[] = Array.isArray(r?.summary?.cases) ? r.summary.cases : [];
            const arts: Record<string, any> = (r?.summary?.artifact_urls || {}) as any;
            return (
              <tr key={r.id}>
                <td><input type="checkbox" checked={selected.includes(r.id)} onChange={()=>toggle(r.id)} /></td>
                <td>{r.id}</td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td>{typeof perfScore==='number'? perfScore: ''}</td>
                <td>{`H${counts.High||0}/M${counts.Medium||0}/L${counts.Low||0}`}</td>
                <td>
                  <pre style={{ whiteSpace:'pre-wrap', maxWidth: '800px', overflow:'auto' }}>{JSON.stringify({ performance: r.summary?.performance?.performance_score, policy: r.summary?.policy, cases: cases.length }, null, 2)}</pre>
                  {cases.length>0 && (
                    <details>
                      <summary>Cases ({cases.length})</summary>
                      <table cellPadding={8} border={1} style={{ marginTop: 6, borderCollapse:'collapse', width:'100%', background:'#fff', color:'#111' }}>
                        <thead>
                          <tr style={{ background:'#f5f5f5' }}>
                            <th>#</th>
                            <th>URL</th>
                            <th>Status</th>
                            <th>HTTP</th>
                            <th>Visual</th>
                            <th>Artifacts</th>
                          </tr>
                        </thead>
                        <tbody>
                          {cases.map((c:any, i:number) => {
                            const ok = !!c.passed;
                            const v = c.visual || {};
                            const sKey = `screenshot_${i+1}`;
                            const tKey = `trace_${i+1}`;
                            const sUrl = rewriteUrl(arts?.[sKey]?.presigned_url);
                            const tUrl = rewriteUrl(arts?.[tKey]?.presigned_url);
                            return (
                              <tr key={i} style={{ background: ok ? '#f6ffed' : '#fff2f0' }}>
                                <td>{i+1}</td>
                                <td style={{ maxWidth: 520, wordBreak:'break-all' }}>{c.url}</td>
                                <td>
                                  <span style={{ padding:'2px 8px', borderRadius:12, background: ok ? '#d9f7be' : '#ffccc7', color: ok ? '#135200' : '#a8071a', fontWeight:600 }}>{ok? 'passed':'failed'}</span>
                                </td>
                                <td>{c.status_code ?? ''}</td>
                                <td>{v.baseline_missing? 'baseline missing' : (typeof v.mismatch_pct==='number'? `${v.mismatch_pct}%` : '')}</td>
                                <td>
                                  {sUrl && (<a href={sUrl} target="_blank" rel="noreferrer">screenshot</a>)}
                                  {sUrl && tUrl && ' | '}
                                  {tUrl && (<a href={tUrl} target="_blank" rel="noreferrer">trace</a>)}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </details>
                  )}
                </td>
                <td>
                  <div>{alerts.length} alerts</div>
                  <a href={`${API}/api/results/${r.id}/alerts.csv?api_key=${encodeURIComponent(API_KEY)}`} target="_blank">CSV</a>
                  <span> | </span>
                  <a href={`${API}/api/results/${r.id}/alerts.json?api_key=${encodeURIComponent(API_KEY)}`} target="_blank">JSON</a>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
