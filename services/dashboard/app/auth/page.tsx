"use client";

import { useState } from 'react';

export default function AuthPage() {
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError(null); setLoading(true);
    try {
      const res = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) });
      const js = await res.json();
      if (!res.ok || !js.ok) throw new Error(js?.error || 'Login failed');
      window.location.href = '/';
    } catch (e: any) { setError(e?.message || String(e)); } finally { setLoading(false); }
  };

  return (
    <div>
      <h2>Dashboard Login</h2>
      <form onSubmit={submit}>
        <input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Password" />
        <button type="submit" disabled={loading} style={{ marginLeft: 8 }}>{loading?'Signing in…':'Sign in'}</button>
      </form>
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </div>
  );
}

