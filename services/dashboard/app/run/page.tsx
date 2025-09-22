"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev-key";

export default function RunPage() {
  const [testType, setTestType] = useState("smoke");
  const [site, setSite] = useState("");
  const [url, setUrl] = useState("");
  const [routes, setRoutes] = useState("");
  const [project, setProject] = useState("");
  const [projects, setProjects] = useState<any[]>([]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/projects`, { headers: { 'x-api-key': API_KEY }})
      .then(r=>r.json()).then(js => setProjects(js.items||[])).catch(()=>{});
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError(null); setLoading(true); setJobId(null);
    try {
      const body: any = { test_type: testType };
      if (site) body.site = site;
      if (url) body.url = url;
      if (routes) body.routes = routes.split(',').map(s => s.trim()).filter(Boolean);
      if (project) body.project = project;
      const res = await fetch(`${API}/api/test/web`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
        body: JSON.stringify(body)
      });
      if (!res.ok) throw new Error(await res.text());
      const js = await res.json();
      setJobId(js.job_id);
    } catch (err: any) {
      setError(err?.message || String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Run Web Test</h2>
      <div style={{ marginBottom: 8 }}>
        Quick type:
        {['smoke','auto','performance','security'].map(t => (
          <button key={t} onClick={()=>setTestType(t)} style={{ marginLeft: 6, background: testType===t? '#e6f7ff':'', borderRadius:4 }}>{t}</button>
        ))}
      </div>
      <form onSubmit={submit}>
        <div style={{ marginBottom: 8 }}>
          <label>Test Type: </label>
          <select value={testType} onChange={e=>setTestType(e.target.value)}>
            <option value="smoke">smoke</option>
            <option value="auto">auto</option>
            <option value="performance">performance</option>
            <option value="security">security</option>
          </select>
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>Project (optional): </label>
          <select value={project} onChange={e=>setProject(e.target.value)}>
            <option value="">(none)</option>
            {projects.map((p:any)=> (<option key={p.project} value={p.project}>{p.project}</option>))}
          </select>
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>Site (optional): </label>
          <input value={site} onChange={e=>setSite(e.target.value)} placeholder="ratemate" />
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>Base URL (optional): </label>
          <input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://example.com" size={40} />
        </div>
        <div style={{ marginBottom: 8 }}>
          <label>Routes (optional, comma-separated): </label>
          <input value={routes} onChange={e=>setRoutes(e.target.value)} placeholder="/en/login,/en/store" size={40} />
        </div>
        <button type="submit" disabled={loading}>{loading ? 'Submitting…' : 'Run'}</button>
      </form>

      {error && <p style={{ color: 'red', marginTop: 12 }}>{error}</p>}

      {jobId && (
        <p style={{ marginTop: 12 }}>
          Enqueued. Job ID: <code>{jobId}</code> — <a href={`/sessions/${jobId}`}>View</a>
        </p>
      )}
    </div>
  );
}
