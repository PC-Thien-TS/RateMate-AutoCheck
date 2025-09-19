"use client";

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev-key";

export default function RunMobile() {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError(null); setLoading(true); setJobId(null);
    try {
      if (!file) throw new Error('Select an APK/IPA file');
      const fd = new FormData();
      fd.append('file', file);
      const up = await fetch(`${API}/api/upload/mobile`, { method: 'POST', headers: { 'x-api-key': API_KEY }, body: fd });
      if (!up.ok) throw new Error(await up.text());
      const info = await up.json();
      const body = { apk_path: info.path, test_type: 'analyze' };
      const enq = await fetch(`${API}/api/test/mobile`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY }, body: JSON.stringify(body) });
      if (!enq.ok) throw new Error(await enq.text());
      const js = await enq.json();
      setJobId(js.job_id);
    } catch (e: any) { setError(e?.message || String(e)); } finally { setLoading(false); }
  };

  return (
    <div>
      <h2>Run Mobile Analyze (APK/IPA)</h2>
      <form onSubmit={submit}>
        <input type="file" accept=".apk,.ipa" onChange={e=> setFile(e.target.files?.[0] || null)} />
        <button type="submit" disabled={loading || !file} style={{ marginLeft: 8 }}>{loading? 'Submitting…' : 'Upload & Run'}</button>
      </form>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {jobId && <p>Enqueued. Job ID: <code>{jobId}</code> — <a href={`/sessions/${jobId}`}>View</a></p>}
    </div>
  );
}

