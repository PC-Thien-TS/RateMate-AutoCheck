'use client';

import { useEffect, useMemo, useState } from "react";
import ObjectView from "../../../components/ObjectView";

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

const QualitySummary = ({ summary }: { summary: any }) => {
  const perfScore = summary?.performance?.performance_score;
  const zapCounts = summary?.security?.counts;
  const policy = summary?.policy || {};

  if (perfScore === undefined && !zapCounts) {
    return null;
  }

  return (
    <div style={{ marginBottom: 16, border: '1px solid #ddd', padding: '0 12px', borderRadius: 8, background: '#fff' }}>
      <h3>Quality Summary</h3>
      <div style={{ display: 'flex', gap: 32, alignItems: 'center' }}>
        {typeof perfScore === 'number' && (
          <div>
            <h4>Performance</h4>
            <div style={{ fontSize: 36, fontWeight: 'bold', color: perfScore > 89 ? '#389e0d' : perfScore > 49 ? '#d46b08' : '#cf1322' }}>
              {perfScore}
            </div>
            <div style={{ color: policy.performance_ok ? '#389e0d' : '#cf1322', fontWeight: 'bold' }}>
              Policy: {policy.performance_ok ? '✓ Passed' : '✗ Failed'}
            </div>
          </div>
        )}
        {zapCounts && (
          <div>
            <h4>Security (ZAP)</h4>
            <div style={{ display: 'flex', gap: 24, alignItems: 'center' }}>
              <div title="High risk alerts">
                <span style={{ fontSize: 28, color: '#cf1322', fontWeight: 'bold' }}>{zapCounts.High || 0}</span> High
              </div>
              <div title="Medium risk alerts">
                <span style={{ fontSize: 28, color: '#d46b08', fontWeight: 'bold' }}>{zapCounts.Medium || 0}</span> Medium
              </div>
              <div title="Low risk alerts">
                <span style={{ fontSize: 28, color: '#096dd9', fontWeight: 'bold' }}>{zapCounts.Low || 0}</span> Low
              </div>
            </div>
             <div style={{ marginTop: 4, color: policy.security_ok ? '#389e0d' : '#cf1322', fontWeight: 'bold' }}>
              Policy: {policy.security_ok ? '✓ Passed' : '✗ Failed'}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default function Page({ params }: { params: { id: string } }) {
  const id = params.id;
  const [sess, setSess] = useState<any>(null);
  const [job, setJob] = useState<any>(null);
  const [resultDetail, setResultDetail] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [gracePolls, setGracePolls] = useState<number>(6);

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
        const hasArtifacts = !!(j?.artifact_urls && Object.keys(j.artifact_urls||{}).length>0);
        const hasResult = !!resultDetail;
        if (st === 'queued' || st === 'running') {
          timer = setTimeout(load, 2000);
        } else {
          const needMore = (!hasArtifacts || !hasResult) && gracePolls > 0;
          if (needMore) {
            setGracePolls((n)=> Math.max(0, n-1));
            timer = setTimeout(load, 2000);
          }
        }
      } catch (e: any) {
        setErr(String(e));
      }
    };
    load();
    return () => { if (timer) clearTimeout(timer); };
  }, [id, gracePolls, resultDetail]);

  const latestSummary = sess?.latest_result?.summary || {};
  const art = (job?.artifact_urls || latestSummary?.artifact_urls || {}) as any;
  const perfUrl = rewriteUrl(art.perf_html?.presigned_url);
  const zapUrl = rewriteUrl(art.zap_html?.presigned_url);
  const mobsfUrl = rewriteUrl(art.mobsf_html?.presigned_url);
  const mob = latestSummary && (latestSummary.risk_score || latestSummary.permissions || latestSummary.endpoints) ? latestSummary : null;

  const CaseTable = () => {
    if (!resultDetail || !Array.isArray(resultDetail.cases)) return null;
    const cases: any[] = resultDetail.cases;
    const getArt = (name: string) => `${API}/api/artifacts/${id}/${name}?api_key=${encodeURIComponent(API_KEY)}`;
    return (
      <div style={{ background: '#fff', border: '1px solid #ddd', borderRadius: 8, padding: '0 12px 12px' }}>
        <h3>Cases</h3>
        <table cellPadding={8} border={1} style={{ borderCollapse:'collapse', width:'100%', color:'#111' }}>
          <thead>
            <tr style={{ background:'#fafafa' }}>
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
                <tr key={i} style={{ background: ok ? '#f6ffed' : '#fff1f0' }}>
                  <td>{i+1}</td>
                  <td style={{ maxWidth: 480, wordBreak:'break-all' }}>{c.url}</td>
                  <td>
                    <span style={{ padding:'2px 8px', borderRadius:12, background: ok ? '#b7eb8f' : '#ffccc7', color: ok ? '#237804' : '#a8071a', fontWeight:500 }}>{ok? 'passed':'failed'}</span>
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
      <div style={{ background: '#fff', border: '1px solid #ddd', borderRadius: 8, padding: '0 12px 12px' }}>
        <h3>Visual Regression</h3>
        {resultDetail.cases.map((c:any, i:number) => (
          <div key={i} style={{ marginBottom:10, border:'1px solid #eee', padding:8 }}>
            <div style={{ fontSize:12, marginBottom:4 }}>{c.url}</div>
            {c.visual && (
              <div>
                <span>Mismatch: {typeof c.visual.mismatch_pct==='number'? `${c.visual.mismatch_pct}%` : (c.visual.baseline_missing? 'baseline missing' : 'n/a')} </span>
                <span style={{ fontWeight: 'bold', color: c.visual.passed ? '#389e0d' : '#cf1322' }}>{c.visual.passed? '(passed)' : '(failed)'}</span>
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

  const rerun = async () => { /* ... existing code ... */ };
  const retry = async () => { /* ... existing code ... */ };
  const cancel = async () => { /* ... existing code ... */ };

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
               resultDetail.cases.forEach((_:any, i:number) => urls.push(`${API}/api/artifacts/${id}/screenshot_${i+1}?api_key=${encodeURIComponent(API_KEY)}`));
            }
            urls.forEach(u=> window.open(u, '_blank'));
          } catch {}
        }}>Open all screenshots</button>
      </div>

      <QualitySummary summary={latestSummary} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 16 }}>
        <ObjectView title="Session Details" data={sess?.session} />
        <ObjectView title="Job Payload" data={job?.payload} />
      </div>

      <CaseTable />

      {perfUrl && (
        <div style={{ marginTop: 16 }}>
          <h3>Lighthouse Report</h3>
          <iframe src={perfUrl} style={{ width: '100%', height: 600, border: '1px solid #444' }} />
        </div>
      )}

      {zapUrl && (
        <div style={{ marginTop: 16 }}>
          <h3>ZAP Report</h3>
          <iframe src={zapUrl} style={{ width: '100%', height: 600, border: '1px solid #444' }} />
        </div>
      )}

      {mobsfUrl && (
        <div style={{ marginTop: 16 }}>
          <h3>MobSF Report</h3>
          <iframe src={mobsfUrl} style={{ width: '100%', height: 600, border: '1px solid #444' }} />
        </div>
      )}

      <VisualBlock />

      {mob && (
        <div style={{ marginTop: 16 }}>
          <h3>Mobile Analyze</h3>
          <div>Risk Score: {mob.risk_score ?? 'n/a'}</div>
          {mob.permissions && (
            <details>
              <summary>Permissions ({Array.isArray(mob.permissions)? mob.permissions.length: 'n/a'})</summary>
              <ObjectView data={mob.permissions} />
            </details>
          )}
          {mob.endpoints && (
            <details>
              <summary>Endpoints ({Array.isArray(mob.endpoints)? mob.endpoints.length: 'n/a'})</summary>
              <ObjectView data={mob.endpoints} />
            </details>
          )}
        </div>
      )}

      {job?.artifact_urls && (
        <div style={{ marginTop: 16 }}>
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