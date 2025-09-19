"use client";

import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function KeysAdmin() {
  const [token, setToken] = useState('');
  const [items, setItems] = useState<any[]>([]);
  const [name, setName] = useState('pipeline');
  const [project, setProject] = useState('');
  const [rate, setRate] = useState(60);
  const [created, setCreated] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    setErr(null);
    try {
      const res = await fetch(`${API}/api/admin/keys`, { headers: { 'x-admin-token': token }});
      if (!res.ok) throw new Error(await res.text());
      const js = await res.json();
      setItems(js.items || []);
    } catch (e: any) { setErr(e?.message || String(e)); }
  };

  const createKey = async () => {
    setErr(null); setCreated(null);
    try {
      const res = await fetch(`${API}/api/admin/keys`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-admin-token': token }, body: JSON.stringify({ name, project, rate_limit_per_min: rate }) });
      const js = await res.json();
      if (!res.ok) throw new Error(js?.detail || JSON.stringify(js));
      setCreated(js.api_key);
      await load();
    } catch (e: any) { setErr(e?.message || String(e)); }
  };

  return (
    <div>
      <a href="/">← Back</a>
      <h2>Admin · API Keys</h2>
      <div style={{ marginBottom: 10 }}>
        <label>Admin Token: <input type="password" value={token} onChange={e=>setToken(e.target.value)} /></label>
        <button onClick={load} style={{ marginLeft: 8 }}>Load</button>
      </div>
      {err && <p style={{ color:'red' }}>{err}</p>}
      <div style={{ margin:'12px 0', padding:10, border:'1px solid #444' }}>
        <h3>Create</h3>
        <label>Name: <input value={name} onChange={e=>setName(e.target.value)} /></label>
        <label style={{ marginLeft:8 }}>Project: <input value={project} onChange={e=>setProject(e.target.value)} /></label>
        <label style={{ marginLeft:8 }}>Rate/min: <input type="number" value={rate} onChange={e=>setRate(parseInt(e.target.value||'60'))} style={{ width: 80 }} /></label>
        <button onClick={createKey} style={{ marginLeft:8 }}>Create</button>
        {created && <div style={{ marginTop:8 }}>API Key (copy now): <code>{created}</code></div>}
      </div>
      <table cellPadding={6} border={1} style={{ borderCollapse:'collapse', width:'100%' }}>
        <thead><tr><th>ID</th><th>Name</th><th>Project</th><th>Rate/min</th><th>Active</th><th>Created</th></tr></thead>
        <tbody>
          {items.map((k:any) => (
            <tr key={k.id}>
              <td>{k.id}</td>
              <td>{k.name}</td>
              <td>{k.project||''}</td>
              <td>{k.rate_limit_per_min}</td>
              <td>{String(k.active)}</td>
              <td>{new Date(k.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

