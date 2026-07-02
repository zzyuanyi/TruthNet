import type { TimelineEvent } from '../types/api';

export default function TimelinePanel({ timeline }: { timeline: TimelineEvent[] }) {
  return (
    <div style={{
      background: '#fff', border: '1px solid #e8e8e8',
      padding: 16, borderRadius: 6, marginBottom: 16,
    }}>
      <h3 style={{ fontSize: 16, marginBottom: 12 }}>
        事件时间线 ({timeline.length})
      </h3>
      <div style={{ position: 'relative', paddingLeft: 20 }}>
        <div style={{
          position: 'absolute', left: 6, top: 4, bottom: 4,
          width: 2, background: '#e8e8e8',
        }} />
        {timeline.map((e, i) => (
          <div key={i} style={{ marginBottom: 12, position: 'relative' }}>
            <div style={{
              position: 'absolute', left: -17, top: 6,
              width: 8, height: 8, borderRadius: '50%',
              background: '#1890ff',
            }} />
            <div style={{ fontSize: 12, color: '#999', marginBottom: 2 }}>
              {e.date}
            </div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>{e.title}</div>
            <div style={{ fontSize: 13, color: '#666' }}>{e.summary}</div>
            <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>
              {e.category} · {e.sentiment}
              {e.sources.length > 0 && ` · 来源: ${e.sources.join(', ')}`}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
