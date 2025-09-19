"use client";

import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'dev-key';

export default function DiffPage({ params, searchParams }: { params: { id: string }, searchParams: any }) {
  const id = params.id;
  const l = parseInt(searchParams?.l || '0', 10);
  const r = parseInt(searchParams?.r || '0', 10);
  const [left, setLeft] = useState<any>(null);
  const [right, setRight] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setErr(null);
        const [a, b] = await Promise.all([
          fetch(`${API}/api/results/${l}`, { headers: { 'x-api-key': API_KEY }}).then(r=>r.json()),
          fetch(`${API}/api/results/${r}`, { headers: { 'x-api-key': API_KEY }}).then(r=>r.json()),
        ]);
        setLeft(a); setRight(b);
      } catch (e: any) { setErr(String(e)); }
    };
    if (l && r) load();
  }, [l, r]);

  const perf = (x:any) => x?.summary?.performance?.performance_score as number | undefined;
  const perfMetrics = (x:any) => (x?.summary?.performance?.metrics || x?.summary?.metrics || {}) as any;
  const zapCounts = (x:any) => (x?.summary?.security?.counts || {}) as Record<string, number>;
  const alerts = (x:any): string[] => (x?.summary?.security?.alerts || []).map((a:any)=> `${a.risk}:${a.alert}|${a.url}`) as string[];

  const leftAlerts: Set<string> = new Set<string>(alerts(left));
  const rightAlerts: Set<string> = new Set<string>(alerts(right));
  const added: string[] = Array.from(rightAlerts).filter((x: string) => !leftAlerts.has(x));
  const removed: string[] = Array.from(leftAlerts).filter((x: string) => !rightAlerts.has(x));

  const Bar = ({label, value, max, good, warn}:{label:string, value:number|undefined, max:number, good:number, warn:number}) => {
    const v = typeof value==='number' ? Math.min(value, max) : 0;
    const pct = typeof value==='number' ? Math.round((v/max)*100) : 0;
    const color = typeof value!=='number' ? '#888' : (value<=good? '#28a745' : (value<=warn? '#ffc107' : '#dc3545'));
    return (
      <div style={{ marginBottom:6 }}>
        <div style={{ fontSize:12, marginBottom:2 }}>{label}: {value ?? 'n/a'}</div>
        <div style={{ background:'#333', width:'100%', height:8, borderRadius:4 }}>
          <div style={{ width:`${pct}%`, height:8, background:color, borderRadius:4 }} />
        </div>
      </div>
    );
  };

  const Badge = ({text, kind}:{text:string, kind:'ok'|'warn'|'bad'|'info'}) => {
    const bg = kind==='ok'? '#e6ffed' : kind==='warn'? '#fff7e6' : kind==='bad'? '#ffe6e6' : '#e6f0ff';
    const color = kind==='ok'? '#237804' : kind==='warn'? '#ad6800' : kind==='bad'? '#a8071a' : '#1d39c4';
    return <span style={{ background:bg, color, padding:'2px 6px', borderRadius:4, marginRight:6 }}>{text}</span>;
  };

  return (
    <div>
      <a href={`/sessions/${id}/results`}>← Back</a>
      <h2>Diff results {l} ↔ {r}</h2>
      {err && <p style={{ color: 'red' }}>{err}</p>}
      <div style={{ display:'flex', gap: 20 }}>
        <div style={{ flex:1 }}>
          <h3>Left (#{l})</h3>
          <div style={{ marginBottom:8 }}>
            <Badge text={`Perf: ${perf(left) ?? 'n/a'}`} kind={typeof perf(left)==='number' ? (perf(left)!>=80? 'ok':'warn') : 'info'} />
            {(() => { const z=zapCounts(left); const k=(z as any); return (<>
              <Badge text={`ZAP H${k?.High||0}`} kind={(k?.High||0)>0?'bad':'ok'} />
              <Badge text={`M${k?.Medium||0}`} kind={(k?.Medium||0)>0?'warn':'ok'} />
            </>); })()}
          </div>
          {(() => { const m=perfMetrics(left); return (
            <div>
              <Bar label='LCP(ms)' value={m.lcp} max={4000} good={2500} warn={4000} />
              <Bar label='CLS' value={m.cls} max={0.4} good={0.1} warn={0.25} />
              <Bar label='TTI(ms)' value={m.tti} max={8000} good={5000} warn={8000} />
            </div>
          ); })()}
        </div>
        <div style={{ flex:1 }}>
          <h3>Right (#{r})</h3>
          <div style={{ marginBottom:8 }}>
            <Badge text={`Perf: ${perf(right) ?? 'n/a'}`} kind={typeof perf(right)==='number' ? (perf(right)!>=80? 'ok':'warn') : 'info'} />
            {(() => { const z=zapCounts(right); const k=(z as any); return (<>
              <Badge text={`ZAP H${k?.High||0}`} kind={(k?.High||0)>0?'bad':'ok'} />
              <Badge text={`M${k?.Medium||0}`} kind={(k?.Medium||0)>0?'warn':'ok'} />
            </>); })()}
          </div>
          {(() => { const m=perfMetrics(right); return (
            <div>
              <Bar label='LCP(ms)' value={m.lcp} max={4000} good={2500} warn={4000} />
              <Bar label='CLS' value={m.cls} max={0.4} good={0.1} warn={0.25} />
              <Bar label='TTI(ms)' value={m.tti} max={8000} good={5000} warn={8000} />
            </div>
          ); })()}
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <h3>Alerts Added</h3>
        <ul>{added.map((x: string, i: number)=>(<li key={i}><Badge text='ADDED' kind='bad' /> {x}</li>))}</ul>
        <h3>Alerts Removed</h3>
        <ul>{removed.map((x: string, i: number)=>(<li key={i}><Badge text='REMOVED' kind='ok' /> {x}</li>))}</ul>
      </div>
    </div>
  );
}
