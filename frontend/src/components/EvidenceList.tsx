import type { EvidenceItem } from '../types/api';

export default function EvidenceList({ evidence }: { evidence: EvidenceItem[] }) {
  return (
    <div style={{
      background: '#fff', border: '1px solid #e8e8e8',
      padding: 16, borderRadius: 6, marginBottom: 16,
    }}>
      <h3 style={{ fontSize: 16, marginBottom: 12 }}>
        证据链 ({evidence.length})
      </h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: '#fafafa', textAlign: 'left' }}>
            <th style={{ padding: '6px 8px', borderBottom: '2px solid #e8e8e8' }}>来源</th>
            <th style={{ padding: '6px 8px', borderBottom: '2px solid #e8e8e8' }}>字段</th>
            <th style={{ padding: '6px 8px', borderBottom: '2px solid #e8e8e8' }}>值</th>
          </tr>
        </thead>
        <tbody>
          {evidence.map((e, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #f0f0f0' }}>
              <td style={{ padding: '6px 8px' }}>{e.source}</td>
              <td style={{ padding: '6px 8px' }}>{e.field}</td>
              <td style={{ padding: '6px 8px', fontWeight: 500 }}>{e.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
