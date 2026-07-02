import { useState, useCallback } from 'react';
import ChatPanel from './components/ChatPanel';
import RiskPanel from './components/RiskPanel';
import EvidenceList from './components/EvidenceList';
import TimelinePanel from './components/TimelinePanel';
import GraphPanel from './components/GraphPanel';
import type { ChatData, WSMessage, RiskScore } from './types/api';
import { sendChat, connectWebSocket, sendWSQuestion } from './api/client';

const emptyRisk: RiskScore = { overall: 0, financial: 0, ownership: 0, sentiment: 0 };

export default function App() {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [useWS, setUseWS] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [wsRef, setWsRef] = useState<WebSocket | null>(null);

  // Response state
  const [answer, setAnswer] = useState('');
  const [riskScore, setRiskScore] = useState<RiskScore>(emptyRisk);
  const [evidence, setEvidence] = useState<NonNullable<ChatData['evidence']>>([]);
  const [timeline, setTimeline] = useState<NonNullable<ChatData['timeline']>>([]);
  const [graph, setGraph] = useState<ChatData['graph']>({ nodes: [], edges: [] });
  const [warnings, setWarnings] = useState<string[]>([]);
  const [missingModules, setMissingModules] = useState<string[]>([]);
  const [traceId, setTraceId] = useState('');
  const [error, setError] = useState('');

  // Partial answer (WS only)
  const [partialText, setPartialText] = useState('');

  const resetState = () => {
    setAnswer('');
    setRiskScore(emptyRisk);
    setEvidence([]);
    setTimeline([]);
    setGraph({ nodes: [], edges: [] });
    setWarnings([]);
    setMissingModules([]);
    setTraceId('');
    setError('');
    setPartialText('');
  };

  // HTTP request
  const handleHttpSend = useCallback(async () => {
    if (!question.trim()) return;
    resetState();
    setLoading(true);
    try {
      const resp = await sendChat({ question: question.trim() });
      if (resp.code === 0 && resp.data) {
        const d = resp.data;
        setAnswer(d.answer);
        setRiskScore(d.risk_score);
        setEvidence(d.evidence || []);
        setTimeline(d.timeline || []);
        setGraph(d.graph || { nodes: [], edges: [] });
        setWarnings(d.warnings || []);
        setMissingModules(d.missing_modules || []);
        setTraceId(d.trace_id);
      }
      if (resp.trace_id) setTraceId(resp.trace_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [question]);

  // WebSocket connect
  const handleWSConnect = useCallback(() => {
    if (wsRef) {
      wsRef.close();
    }
    resetState();
    setWsConnected(false);

    const ws = connectWebSocket(
      (msg: WSMessage) => {
        switch (msg.type) {
          case 'status':
            setPartialText(msg.data.message as string);
            break;
          case 'partial_answer':
            setPartialText((prev) => prev + (msg.data.text as string));
            break;
          case 'final_answer': {
            const d = msg.data as ChatData;
            setAnswer(d.answer);
            setRiskScore(d.risk_score);
            setEvidence(d.evidence || []);
            setTimeline(d.timeline || []);
            setGraph(d.graph || { nodes: [], edges: [] });
            setWarnings(d.warnings || []);
            setMissingModules(d.missing_modules || []);
            setTraceId(d.trace_id);
            setLoading(false);
            break;
          }
          case 'error':
            setError(`[WS Error] ${msg.data.message}`);
            setLoading(false);
            break;
        }
      },
      () => setError('WebSocket 连接错误'),
      () => setWsConnected(false)
    );

    ws.onopen = () => {
      setWsConnected(true);
      setWsRef(ws);
    };

    setWsRef(ws);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // WebSocket send
  const handleWSSend = useCallback(() => {
    if (!question.trim() || !wsRef) return;
    resetState();
    setLoading(true);
    sendWSQuestion(wsRef, {
      type: 'question',
      data: { question: question.trim() },
    });
  }, [question, wsRef]);

  // Disconnect
  const handleWSDisconnect = useCallback(() => {
    if (wsRef) {
      wsRef.close();
      setWsRef(null);
      setWsConnected(false);
    }
  }, [wsRef]);

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '24px 16px' }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>
        TruthNet — 织网鉴真
      </h1>
      <p style={{ color: '#666', marginBottom: 20, fontSize: 14 }}>
        财报反欺诈智能问答系统（MVP Mock）
      </p>

      {/* Input */}
      <ChatPanel
        question={question}
        loading={loading}
        useWS={useWS}
        wsConnected={wsConnected}
        onQuestionChange={setQuestion}
        onSend={handleHttpSend}
        onToggleWS={setUseWS}
        onWSConnect={handleWSConnect}
        onWSSend={handleWSSend}
        onWSDisconnect={handleWSDisconnect}
      />

      {/* Error */}
      {error && (
        <div style={{
          background: '#fff0f0', border: '1px solid #ffcccc',
          padding: 12, borderRadius: 6, marginBottom: 16, color: '#cc0000',
        }}>
          {error}
        </div>
      )}

      {/* Partial answer (WS) */}
      {partialText && loading && (
        <div style={{
          background: '#f5f5f5', padding: 12, borderRadius: 6,
          marginBottom: 16, fontStyle: 'italic', color: '#555',
        }}>
          {partialText}
        </div>
      )}

      {/* Answer */}
      {answer && (
        <div style={{
          background: '#f0f7ff', border: '1px solid #cce0ff',
          padding: 16, borderRadius: 6, marginBottom: 16,
        }}>
          <h3 style={{ fontSize: 16, marginBottom: 8 }}>回答</h3>
          <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{answer}</p>
        </div>
      )}

      {/* Risk Score */}
      {(riskScore.overall > 0 || riskScore.financial > 0) && (
        <RiskPanel riskScore={riskScore} />
      )}

      {/* Evidence */}
      {evidence.length > 0 && <EvidenceList evidence={evidence} />}

      {/* Timeline */}
      {timeline.length > 0 && <TimelinePanel timeline={timeline} />}

      {/* Graph */}
      {(graph.nodes.length > 0 || graph.edges.length > 0) && (
        <GraphPanel graph={graph} />
      )}

      {/* Missing Modules */}
      {missingModules.length > 0 && (
        <div style={{
          background: '#fffbe6', border: '1px solid #ffe58f',
          padding: 12, borderRadius: 6, marginBottom: 16,
        }}>
          <h3 style={{ fontSize: 14, marginBottom: 4, color: '#ad8b00' }}>
            ⚠️ 暂未实现的模块
          </h3>
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: '#666' }}>
            {missingModules.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div style={{
          background: '#fff7e6', border: '1px solid #ffd591',
          padding: 12, borderRadius: 6, marginBottom: 16,
        }}>
          <h3 style={{ fontSize: 14, marginBottom: 4 }}>⚠️ 预警</h3>
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Trace ID */}
      {traceId && (
        <div style={{ fontSize: 12, color: '#999', marginBottom: 16 }}>
          trace_id: {traceId}
        </div>
      )}
    </div>
  );
}
