import type { GraphData } from '../types/api';

export default function GraphPanel({ graph }: { graph: GraphData }) {
  return (
    <div style={{
      background: '#fff', border: '1px solid #e8e8e8',
      padding: 16, borderRadius: 6, marginBottom: 16,
    }}>
      <h3 style={{ fontSize: 16, marginBottom: 12 }}>
        关系图谱 ({graph.nodes.length} 节点, {graph.edges.length} 边)
      </h3>
      <p style={{ fontSize: 13, color: '#999', marginBottom: 12 }}>
        图谱可视化组件待引入（d3/visx），当前展示原始数据。
      </p>

      {/* Nodes */}
      <div style={{ marginBottom: 12 }}>
        <h4 style={{ fontSize: 14, marginBottom: 6 }}>节点</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {graph.nodes.map((n) => (
            <span key={n.id} style={{
              display: 'inline-block',
              padding: '3px 10px',
              background: '#e6f7ff',
              border: '1px solid #91d5ff',
              borderRadius: 12,
              fontSize: 12,
            }}>
              {n.label || n.id}
              <span style={{ color: '#999', marginLeft: 4 }}>({n.type})</span>
            </span>
          ))}
        </div>
      </div>

      {/* Edges */}
      <div>
        <h4 style={{ fontSize: 14, marginBottom: 6 }}>关系</h4>
        <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
          {graph.edges.map((e, i) => (
            <li key={i} style={{ marginBottom: 2 }}>
              {e.source} → {e.target}: {e.relation}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
