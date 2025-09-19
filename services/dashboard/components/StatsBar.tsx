"use client";

import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'dev-key';

export default function StatsBar() {
  const [s, setS] = useState<any>(null);
  useEffect(() => {
    let t: any;
    const load = async () => {
      try {
        const r = await fetch(`${API}/api/stats`, { headers: { 'x-api-key': API_KEY } });
        if (r.ok) setS(await r.json());
      } catch (_) {}
      t = setTimeout(load, 5000);
    };
    load();
    return () => t && clearTimeout(t);
  }, []);
  if (!s) return null;
  const pill = (label:string, val:number, bg:string) => (
    <span style={{ background:bg, padding:'2px 6px', borderRadius:4, marginRight:6 }}>{label}:{val}</span>
  );
  return (
    <div style={{ margin:'8px 0' }}>
      {pill('queued', s.queued, '#f0f0f0')}
      {pill('started', s.started, '#fff7e6')}
      {pill('finished', s.finished, '#e6ffed')}
      {pill('failed', s.failed, '#ffe6e6')}
    </div>
  );
}

