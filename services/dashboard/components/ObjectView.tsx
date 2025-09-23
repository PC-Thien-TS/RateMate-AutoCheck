'use client';

import React from 'react';

interface ObjectViewProps {
  data: Record<string, any> | null;
  title?: string;
}

const ObjectView: React.FC<ObjectViewProps> = ({ data, title }) => {
  if (!data) {
    return null;
  }

  const renderValue = (value: any) => {
    if (typeof value === 'boolean') {
      return <span style={{ color: value ? '#389e0d' : '#cf1322' }}>{value ? 'true' : 'false'}</span>;
    }
    if (value === null || value === undefined) {
      return <i style={{ opacity: 0.6 }}>null</i>;
    }
    if (typeof value === 'string' && (value.startsWith('http') || value.startsWith('/'))) {
      try {
        const url = new URL(value);
        return <a href={value} target="_blank" rel="noreferrer">{value}</a>;
      } catch (_){}
    }
    if (typeof value === 'object') {
      return <pre style={{ margin: 0, background: '#f0f0f0', padding: '4px 8px', borderRadius: 4, whiteSpace: 'pre-wrap' }}>{JSON.stringify(value, null, 2)}</pre>;
    }
    return String(value);
  };

  return (
    <div style={{ marginBottom: 16 }}>
      {title && <h3>{title}</h3>}
      <table cellPadding={8} border={1} style={{ borderCollapse: 'collapse', width: '100%', background: '#fff', fontSize: 14 }}>
        <tbody>
          {Object.entries(data).map(([key, value]) => (
            <tr key={key}>
              <td style={{ fontWeight: 'bold', background: '#fafafa', width: '25%' }}>{key}</td>
              <td style={{ wordBreak: 'break-all' }}>{renderValue(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ObjectView;
