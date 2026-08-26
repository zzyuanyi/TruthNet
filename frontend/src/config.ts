/**
 * 前端运行配置。
 *
 * Vite 只会把 VITE_ 前缀变量暴露给浏览器。部署时通过 frontend/.env
 * 或宿主环境注入；不在前端代码中保存账号、密码或密钥。
 */
function normalizeBaseUrl(value: string | undefined): string {
  return value?.trim().replace(/\/+$/, '') ?? '';
}

export const frontendConfig = Object.freeze({
  /** 空值表示同源访问：开发时由 Vite proxy 转发，生产时由反向代理转发。 */
  apiBaseUrl: normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL),
  /** 可选；不填时由 API 地址或当前页面地址推导 WebSocket 地址。 */
  wsBaseUrl: normalizeBaseUrl(import.meta.env.VITE_WS_BASE_URL),
});

export const apiV1Base = `${frontendConfig.apiBaseUrl}/api/v1`;

export function websocketEndpoint(path: string): string {
  const configuredBase = frontendConfig.wsBaseUrl || frontendConfig.apiBaseUrl;
  if (configuredBase) {
    const wsBase = configuredBase
      .replace(/^https:/, 'wss:')
      .replace(/^http:/, 'ws:');
    return `${wsBase}${path}`;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${path}`;
}
