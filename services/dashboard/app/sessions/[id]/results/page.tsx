"use client";

import { useEffect, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'dev-key';

export default function ResultsPage({ params }: { params: { id: string }}) {
  const id = params.id;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true); setError(null);
    fetch(`${API}/api/sessions/${id}/results?limit=50`, { headers: { 'x-api-key': API_KEY }})
      .then(r => r.json()).then(setData).catch(e=> setError(String(e))).finally(()=> setLoading(false));
  }, [id]);

  return (
    <div>
      <a href={`/sessions/${id}`}>← Back</a>
      <h2>Results for {id}</h2>
      {loading && <p>Loading…</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <table cellPadding={6} border={1} style={{ borderCollapse: 'collapse', width: '100%' }}>
        <thead>
          <tr><th>Result ID</th><th>Created</th><th>Summary</th></tr>
        </thead>
        <tbody>
          {data?.items?.map((r:any) => (
            <tr key={r.id}>
              <td>{r.id}</td>
              <td>{new Date(r.created_at).toLocaleString()}</td>
              <td><pre style={{ whiteSpace:'pre-wrap', maxWidth: '1000px', overflow:'auto' }}>{JSON.stringify(r.summary, null, 2)}</pre></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

