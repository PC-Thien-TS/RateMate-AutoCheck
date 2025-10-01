'use client';

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from 'next/navigation';

interface Project {
  project: string;
  sessions: number;
}

export default function SiteSwitcher() {
  const [projects, setProjects] = useState<Project[]>([]);
  const searchParams = useSearchParams();
  const router = useRouter();
  const currentProject = searchParams.get('project') || '';

  useEffect(() => {
    fetch(`/api/proxy/api/projects`)
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
        {projects.map((p) => (
          <option key={p.project} value={p.project}>{p.project} ({p.sessions})</option>
        ))}
      </select>
    </label>
  );
}
