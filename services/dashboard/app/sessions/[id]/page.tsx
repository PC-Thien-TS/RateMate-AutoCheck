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
    setErr(null);
    fetch(`${API}/api/sessions/${id}`, { headers: { 'x-api-key': API_KEY }})
      .then(r => r.json()).then(setSess).catch(e=>setErr(String(e)));
    fetch(`${API}/api/jobs/${id}`, { headers: { 'x-api-key': API_KEY }})
      .then(r => r.json()).then(setJob).catch(e=>setErr(String(e)));
  }, [id]);

  const art = job?.artifact_urls || {};
  const screenshotUrl = rewriteUrl(art.screenshot?.presigned_url || art.screenshot_1?.presigned_url);
  const perfUrl = rewriteUrl(art.perf_html?.presigned_url);
  const zapUrl = rewriteUrl(art.zap_html?.presigned_url);

  return (
    <div>
      <a href="/">← Back</a>
      <h2>Session {id}</h2>
      {err && <p style={{ color: 'red' }}>{err}</p>}

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
    </div>
  );
}

