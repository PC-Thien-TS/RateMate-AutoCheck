'use client';

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from 'next/navigation';

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "dev-key";

export default function SiteSwitcher() {
  const [projects, setProjects] = useState<any[]>([]);
  const searchParams = useSearchParams();
  const router = useRouter();
  const currentProject = searchParams.get('project') || '';

  useEffect(() => {
    fetch(`${API}/api/projects?api_key=${encodeURIComponent(API_KEY)}`, { headers: { 'x-api-key': API_KEY } })
      .then(r => r.json())
      .then(js => setProjects(js.items || []))
      .catch((e) => { console.warn('Failed to fetch projects', e) });
  }, []);

  const handleSiteChange = (project: string) => {
    const params = new URLSearchParams(window.location.search);
    if (project) {
      params.set('project', project);
    } else {
      params.delete('project');
    }
    router.push(`/?${params.toString()}`);
  };

  return (
    <label>
      Site: 
      <select value={currentProject} onChange={e => handleSiteChange(e.target.value)} style={{ marginLeft: 4 }}>
        <option value="">(all)</option>
        {projects.map((p: any) => (
          <option key={p.project} value={p.project}>{p.project} ({p.sessions})</option>
        ))}
      </select>
    </label>
  );
}
