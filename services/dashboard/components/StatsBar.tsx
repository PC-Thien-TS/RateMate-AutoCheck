"use client";

import { useEffect, useState } from 'react';

interface Stats {
  queued: number;
  started: number;
  finished: number;
  failed: number;
}

export default function StatsBar() {
  const [stats, setStats] = useState<Stats | null>(null);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {
        const res = await fetch(`/api/proxy/api/stats`);
        if (res.ok) {
          setStats(await res.json());
        }
      } catch (e) {
        console.warn('Failed to fetch stats', e);
      }
      timer = setTimeout(load, 5000);
    };
    load();
    return () => timer && clearTimeout(timer);
  }, []);
  if (!stats) return null;
  const pill = (label:string, val:number, bg:string) => (
    <span style={{ background:bg, padding:'2px 6px', borderRadius:4, marginRight:6 }}>{label}:{val}</span>
  );
  return (
    <div style={{ margin:'8px 0' }}>
      {pill('Queued', stats.queued, '#f0f0f0')}
      {pill('Running', stats.started, '#fff7e6')}
      {pill('Finished', stats.finished, '#e6ffed')}
      {pill('Failed', stats.failed, '#ffe6e6')}
    </div>
  );
}
