"use client";

import { useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev-key";
const S3_PUBLIC = process.env.NEXT_PUBLIC_S3_PUBLIC || "http://localhost:9000";

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

export default function Page({ params }: { params: { id: string } }) {
  const id = params.id;
  const [sess, setSess] = useState<any>(null);
  const [job, setJob] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let timer: any;
    const load = async () => {
      try {
        setErr(null);
        const [s, j] = await Promise.all([
          fetch(`${API}/api/sessions/${id}`, { headers: { 'x-api-key': API_KEY }}).then(r=>r.json()),
          fetch(`${API}/api/jobs/${id}`, { headers: { 'x-api-key': API_KEY }}).then(r=>r.json()),
        ]);
        setSess(s); setJob(j);
        const st = j?.status;
        if (st === 'queued' || st === 'running') {
          timer = setTimeout(load, 2000);
        }
      } catch (e: any) {
        setErr(String(e));
      }
    };
    load();
    return () => { if (timer) clearTimeout(timer); };
  }, [id]);

  const art = job?.artifact_urls || {};
  const screenshotUrl = rewriteUrl(art.screenshot?.presigned_url || art.screenshot_1?.presigned_url);
  const perfUrl = rewriteUrl(art.perf_html?.presigned_url);
  const zapUrl = rewriteUrl(art.zap_html?.presigned_url);

  const rerun = async () => {
    try {
      const payload: any = job?.payload || {};
      if (!payload?.test_type) payload.test_type = 'smoke';
      const res = await fetch(`${API}/api/test/web`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY }, body: JSON.stringify(payload) });
      const js = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(js));
      window.location.href = `/sessions/${js.job_id}`;
    } catch (e: any) {
      alert('Re-run failed: ' + (e?.message || String(e)));
    }
  };

  return (
    <div>
      <a href="/">← Back</a>
      <h2>Session {id}</h2>
      {err && <p style={{ color: 'red' }}>{err}</p>}
      <div style={{ margin: '8px 0' }}>
        <button onClick={()=> location.reload()}>Refresh</button>
        <button onClick={rerun} style={{ marginLeft: 8 }}>Re-run</button>
      </div>

      <h3>Summary</h3>
      <pre style={{ whiteSpace: 'pre-wrap', background: '#111', color: '#ddd', padding: 10 }}>
        {JSON.stringify(sess, null, 2)}
      </pre>

      <h3>Job Status</h3>
      <pre style={{ whiteSpace: 'pre-wrap', background: '#111', color: '#ddd', padding: 10 }}>
        {JSON.stringify(job, null, 2)}
      </pre>

      {screenshotUrl && (
        <div>
          <h3>Screenshot</h3>
          <img src={screenshotUrl} alt="screenshot" style={{ maxWidth: '100%', border: '1px solid #444' }} />
        </div>
      )}

      {perfUrl && (
        <div>
          <h3>Lighthouse Report</h3>
          <iframe src={perfUrl} style={{ width: '100%', height: 600, border: '1px solid #444' }} />
        </div>
      )}

      {zapUrl && (
        <div>
          <h3>ZAP Report</h3>
          <iframe src={zapUrl} style={{ width: '100%', height: 600, border: '1px solid #444' }} />
        </div>
      )}

      {job?.artifact_urls && (
        <div>
          <h3>Artifact URLs</h3>
          <ul>
            {Object.entries(job.artifact_urls).map(([k,v]: any) => (
              <li key={k}><a href={rewriteUrl(v?.presigned_url)} target="_blank" rel="noreferrer">{k}</a></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
