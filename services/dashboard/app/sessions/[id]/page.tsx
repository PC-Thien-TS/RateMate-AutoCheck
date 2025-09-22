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
  const [resultDetail, setResultDetail] = useState<any>(null);
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
        try {
          const rd = await fetch(`${API}/api/job-results/${id}`, { headers: { 'x-api-key': API_KEY }});
          if (rd.ok) setResultDetail(await rd.json());
        } catch {}
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

  // Latest summary from DB
  const latestSummary = sess?.latest_result?.summary || {};
  // Prefer API proxy that re-signs URLs to avoid host/signature mismatch
  const art = (job?.artifact_urls || latestSummary?.artifact_urls || {}) as any;
  const screenshotUrl = `${API}/api/artifacts/${id}/screenshot_1?api_key=${encodeURIComponent(API_KEY)}`;
  const perfUrl = rewriteUrl(art.perf_html?.presigned_url);
  const zapUrl = rewriteUrl(art.zap_html?.presigned_url);
  const mobsfUrl = rewriteUrl(art.mobsf_html?.presigned_url);
  const perfScore = latestSummary?.performance?.performance_score;
  const zapCounts = latestSummary?.security?.counts;
  const mob = latestSummary && (latestSummary.risk_score || latestSummary.permissions || latestSummary.endpoints) ? latestSummary : null;

  const CaseTable = () => {
    if (!resultDetail || !Array.isArray(resultDetail.cases)) return null;
    const cases: any[] = resultDetail.cases;
    const getArt = (name: string) => `${API}/api/artifacts/${id}/${name}?api_key=${encodeURIComponent(API_KEY)}`;
    return (
      <div>
        <h3>Cases</h3>
        <table cellPadding={8} border={1} style={{ borderCollapse:'collapse', width:'100%', background:'#fff', color:'#111' }}>
          <thead>
            <tr style={{ background:'#f5f5f5' }}>
              <th>#</th>
              <th>URL</th>
              <th>Status</th>
              <th>HTTP</th>
              <th>Title</th>
              <th>Missing selectors</th>
              <th>Artifacts</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c, i) => {
              const ok = !!c.passed;
              const sKey = `screenshot_${i+1}`;
              const tKey = `trace_${i+1}`;
              const sUrl = getArt(sKey);
              const tUrl = getArt(tKey);
              return (
                <tr key={i} style={{ background: ok ? '#f6ffed' : '#fff2f0' }}>
                  <td>{i+1}</td>
                  <td style={{ maxWidth: 520, wordBreak:'break-all' }}>{c.url}</td>
                  <td>
                    <span style={{ padding:'2px 8px', borderRadius:12, background: ok ? '#d9f7be' : '#ffccc7', color: ok ? '#135200' : '#a8071a', fontWeight:600 }}>{ok? 'passed':'failed'}</span>
                  </td>
                  <td>{c.status_code ?? ''}</td>
                  <td>{c.title ?? ''}</td>
                  <td style={{ color:'#cf1322' }}>{Array.isArray(c.missing_selectors)? c.missing_selectors.join(', ') : (c.missing_selectors || '')}</td>
                  <td>
                    <a href={sUrl} target="_blank" rel="noreferrer">screenshot</a>
                    {" | "}
                    <a href={tUrl} target="_blank" rel="noreferrer">trace</a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  const VisualBlock = () => {
    if (!resultDetail || !Array.isArray(resultDetail.cases)) return null;
    return (
      <div>
        <h3>Visual Regression</h3>
        {resultDetail.cases.map((c:any, i:number) => (
          <div key={i} style={{ marginBottom:10, border:'1px solid #333', padding:8 }}>
            <div style={{ fontSize:12, marginBottom:4 }}>{c.url}</div>
            {c.visual && (
              <div>
                <span>Mismatch: {typeof c.visual.mismatch_pct==='number'? `${c.visual.mismatch_pct}%` : (c.visual.baseline_missing? 'baseline missing' : 'n/a')} </span>
                <span>{c.visual.passed? '(passed)' : '(failed)'}</span>
              </div>
            )}
            <button onClick={async()=>{
              try {
                const res = await fetch(`${API}/api/visual/accept`, { method:'POST', headers:{ 'Content-Type':'application/json', 'x-api-key': API_KEY }, body: JSON.stringify({ job_id: id, index: i+1 }) });
                if (!res.ok) throw new Error(await res.text());
                alert('Baseline accepted');
              } catch(e:any){ alert(e?.message||String(e)); }
            }}>Accept Baseline</button>
          </div>
        ))}
      </div>
    );
  };

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

  const retry = async () => {
    try {
      const res = await fetch(`${API}/api/jobs/${id}/retry`, { method: 'POST', headers: { 'x-api-key': API_KEY } });
      const js = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(js));
      window.location.href = `/sessions/${js.job_id}`;
    } catch (e: any) { alert('Retry failed: ' + (e?.message || String(e))); }
  };

  const cancel = async () => {
    try {
      const res = await fetch(`${API}/api/jobs/${id}/cancel`, { method: 'POST', headers: { 'x-api-key': API_KEY } });
      if (!res.ok) throw new Error(await res.text());
      alert('Cancel requested');
      location.reload();
    } catch (e:any) { alert('Cancel failed: ' + (e?.message || String(e))); }
  };

  return (
    <div>
      <a href="/">← Back</a>
      <h2>Session {id}</h2>
      {err && <p style={{ color: 'red' }}>{err}</p>}
      <div style={{ margin: '8px 0' }}>
        <button onClick={()=> location.reload()}>Refresh</button>
        <button onClick={rerun} style={{ marginLeft: 8 }}>Re-run</button>
        <button onClick={retry} style={{ marginLeft: 8 }}>Retry</button>
        <button onClick={cancel} style={{ marginLeft: 8 }}>Cancel</button>
        <a href={`/sessions/${id}/results`} style={{ marginLeft: 8 }}>Results History</a>
        <button style={{ marginLeft: 8 }} onClick={()=>{
          try {
            const urls: string[] = [];
            const a: any = art || {};
            Object.keys(a).filter(k=>k.startsWith('screenshot_')).forEach(k=>{
              const u = rewriteUrl(a[k]?.presigned_url);
              if (u) urls.push(u);
            });
            if (urls.length === 0 && Array.isArray(resultDetail?.cases)) {
              if (screenshotUrl) urls.push(screenshotUrl);
            }
            urls.forEach(u=> window.open(u, '_blank'));
          } catch {}
        }}>Open all screenshots</button>
      </div>

      <h3>Summary</h3>
      <pre style={{ whiteSpace: 'pre-wrap', background: '#111', color: '#ddd', padding: 10 }}>
        {JSON.stringify(sess, null, 2)}
      </pre>

      <h3>Job Status</h3>
      <pre style={{ whiteSpace: 'pre-wrap', background: '#111', color: '#ddd', padding: 10 }}>
        {JSON.stringify(job, null, 2)}
      </pre>

      <CaseTable />

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

      {mobsfUrl && (
        <div>
          <h3>MobSF Report</h3>
          <iframe src={mobsfUrl} style={{ width: '100%', height: 600, border: '1px solid #444' }} />
        </div>
      )}

      {(typeof perfScore === 'number' || zapCounts) && (
        <div>
          <h3>Quality Summary</h3>
          <pre style={{ whiteSpace:'pre-wrap', background:'#111', color:'#ddd', padding:10 }}>
            {JSON.stringify({ performance_score: perfScore, zap: zapCounts }, null, 2)}
          </pre>
        </div>
      )}

      <VisualBlock />

      {mob && (
        <div>
          <h3>Mobile Analyze</h3>
          <div>Risk Score: {mob.risk_score ?? 'n/a'}</div>
          {mob.permissions && (
            <details>
              <summary>Permissions ({Array.isArray(mob.permissions)? mob.permissions.length: 'n/a'})</summary>
              <pre style={{ whiteSpace:'pre-wrap' }}>{JSON.stringify(mob.permissions, null, 2)}</pre>
            </details>
          )}
          {mob.endpoints && (
            <details>
              <summary>Endpoints ({Array.isArray(mob.endpoints)? mob.endpoints.length: 'n/a'})</summary>
              <pre style={{ whiteSpace:'pre-wrap' }}>{JSON.stringify(mob.endpoints, null, 2)}</pre>
            </details>
          )}
        </div>
      )}

      {job?.artifact_urls && (
        <div>
          <h3>Artifact URLs</h3>
          <ul>
            {Object.entries(job.artifact_urls).map(([k,v]: any) => (
              <li key={k}><a href={rewriteUrl(v?.presigned_url) || `${API}/api/artifacts/${id}/${k}`} target="_blank" rel="noreferrer">{k}</a></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
