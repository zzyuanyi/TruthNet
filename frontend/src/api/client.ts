/**
 * TruthNet API 客户端
 *
 * 提供 HTTP 和 WebSocket 两种通信方式。
 * API 基础地址从环境变量读取，默认 localhost:8000。
 */

import type {
  UnifiedResponse,
  HealthData,
  ChatRequest,
  ChatData,
  WSMessage,
  WSQuestionRequest,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const WS_BASE = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000';

// ============================================================
// HTTP
// ============================================================

export async function healthCheck(): Promise<UnifiedResponse<HealthData>> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status}`);
  }
  return res.json();
}

export async function sendChat(
  request: ChatRequest
): Promise<UnifiedResponse<ChatData>> {
  const res = await fetch(`${API_BASE}/api/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ============================================================
// WebSocket
// ============================================================

export type WSMessageHandler = (msg: WSMessage) => void;
export type WSErrorHandler = (err: Event) => void;
export type WSCloseHandler = () => void;

export function connectWebSocket(
  onMessage: WSMessageHandler,
  onError?: WSErrorHandler,
  onClose?: WSCloseHandler
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/api/v1/chat/ws`);

  ws.onopen = () => {
    console.log('[WS] Connected to', `${WS_BASE}/api/v1/chat/ws`);
  };

  ws.onmessage = (event: MessageEvent) => {
    try {
      const msg: WSMessage = JSON.parse(event.data as string);
      onMessage(msg);
    } catch {
      console.error('[WS] Failed to parse message:', event.data);
    }
  };

  ws.onerror = (err: Event) => {
    console.error('[WS] Error:', err);
    onError?.(err);
  };

  ws.onclose = () => {
    console.log('[WS] Disconnected');
    onClose?.();
  };

  return ws;
}

export function sendWSQuestion(ws: WebSocket, request: WSQuestionRequest): void {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(request));
  }
}
