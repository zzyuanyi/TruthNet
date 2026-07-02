interface ChatPanelProps {
  question: string;
  loading: boolean;
  useWS: boolean;
  wsConnected: boolean;
  onQuestionChange: (v: string) => void;
  onSend: () => void;
  onToggleWS: (v: boolean) => void;
  onWSConnect: () => void;
  onWSSend: () => void;
  onWSDisconnect: () => void;
}

export default function ChatPanel({
  question,
  loading,
  useWS,
  wsConnected,
  onQuestionChange,
  onSend,
  onToggleWS,
  onWSConnect,
  onWSSend,
  onWSDisconnect,
}: ChatPanelProps) {
  return (
    <div style={{ marginBottom: 20 }}>
      {/* Mode toggle */}
      <div style={{ marginBottom: 12, display: 'flex', gap: 12, alignItems: 'center' }}>
        <label style={{ fontSize: 14, cursor: 'pointer' }}>
          <input
            type="radio"
            checked={!useWS}
            onChange={() => onToggleWS(false)}
          />{' '}
          HTTP REST
        </label>
        <label style={{ fontSize: 14, cursor: 'pointer' }}>
          <input
            type="radio"
            checked={useWS}
            onChange={() => onToggleWS(true)}
          />{' '}
          WebSocket
        </label>

        {useWS && (
          <>
            {!wsConnected ? (
              <button
                onClick={onWSConnect}
                style={{
                  padding: '4px 12px', fontSize: 13,
                  background: '#52c41a', color: '#fff', border: 'none',
                  borderRadius: 4, cursor: 'pointer',
                }}
              >
                连接 WS
              </button>
            ) : (
              <button
                onClick={onWSDisconnect}
                style={{
                  padding: '4px 12px', fontSize: 13,
                  background: '#ff4d4f', color: '#fff', border: 'none',
                  borderRadius: 4, cursor: 'pointer',
                }}
              >
                断开 WS
              </button>
            )}
            {wsConnected && (
              <span style={{ fontSize: 13, color: '#52c41a' }}>● 已连接</span>
            )}
          </>
        )}
      </div>

      {/* Input */}
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type="text"
          value={question}
          onChange={(e) => onQuestionChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !loading) {
              useWS ? onWSSend() : onSend();
            }
          }}
          placeholder="输入问题，例如：请分析贵州茅台2023年营收"
          disabled={loading}
          style={{
            flex: 1, padding: '8px 12px', fontSize: 14,
            border: '1px solid #d9d9d9', borderRadius: 6,
            outline: 'none',
          }}
        />
        <button
          onClick={useWS ? onWSSend : onSend}
          disabled={loading || (!useWS && !question.trim()) || (useWS && (!wsConnected || !question.trim()))}
          style={{
            padding: '8px 20px', fontSize: 14,
            background: loading ? '#b0b0b0' : '#1890ff',
            color: '#fff', border: 'none', borderRadius: 6,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? '请求中...' : '发送'}
        </button>
      </div>
    </div>
  );
}
