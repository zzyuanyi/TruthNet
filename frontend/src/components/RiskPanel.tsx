import type { RiskScore } from '../types/api';

interface RiskPanelProps {
  riskScore: RiskScore;
}

function barColor(v: number): string {
  if (v >= 0.7) return '#ff4d4f';
  if (v >= 0.4) return '#faad14';
  return '#52c41a';
}

function RiskBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 2 }}>
        <span>{label}</span>
        <span style={{ fontWeight: 600 }}>{pct}%</span>
      </div>
      <div style={{ background: '#f0f0f0', borderRadius: 4, height: 8, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`,
          height: '100%',
          background: barColor(value),
          borderRadius: 4,
          transition: 'width 0.3s',
        }} />
      </div>
    </div>
  );
}

export default function RiskPanel({ riskScore }: RiskPanelProps) {
  return (
    <div style={{
      background: '#fff', border: '1px solid #e8e8e8',
      padding: 16, borderRadius: 6, marginBottom: 16,
    }}>
      <h3 style={{ fontSize: 16, marginBottom: 12 }}>风险评分</h3>
      <RiskBar label="综合风险" value={riskScore.overall} />
      <RiskBar label="财务风险" value={riskScore.financial} />
      <RiskBar label="股权风险" value={riskScore.ownership} />
      <RiskBar label="舆情风险" value={riskScore.sentiment} />
    </div>
  );
}
