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
  const zapCounts = (x:any) => (x?.summary?.security?.counts || {}) as Record<string, number>;
  const alerts = (x:any): string[] => (x?.summary?.security?.alerts || []).map((a:any)=> `${a.risk}:${a.alert}|${a.url}`) as string[];

  const leftAlerts: Set<string> = new Set<string>(alerts(left));
  const rightAlerts: Set<string> = new Set<string>(alerts(right));
  const added: string[] = Array.from(rightAlerts).filter((x: string) => !leftAlerts.has(x));
  const removed: string[] = Array.from(leftAlerts).filter((x: string) => !rightAlerts.has(x));

  return (
    <div>
      <a href={`/sessions/${id}/results`}>← Back</a>
      <h2>Diff results {l} ↔ {r}</h2>
      {err && <p style={{ color: 'red' }}>{err}</p>}
      <div style={{ display:'flex', gap: 20 }}>
        <div style={{ flex:1 }}>
          <h3>Left (#{l})</h3>
          <pre>{JSON.stringify({ perf: perf(left), zap: zapCounts(left) }, null, 2)}</pre>
        </div>
        <div style={{ flex:1 }}>
          <h3>Right (#{r})</h3>
          <pre>{JSON.stringify({ perf: perf(right), zap: zapCounts(right) }, null, 2)}</pre>
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <h3>Alerts Added</h3>
        <ul>{added.map((x: string, i: number)=>(<li key={i}>{x}</li>))}</ul>
        <h3>Alerts Removed</h3>
        <ul>{removed.map((x: string, i: number)=>(<li key={i}>{x}</li>))}</ul>
      </div>
    </div>
  );
}
