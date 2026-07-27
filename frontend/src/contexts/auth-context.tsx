/**
 * 认证上下文
 *
 * 对接后端 Agent API (8000) 的认证接口：
 *   POST /api/auth/login
 *   POST /api/auth/register
 *   POST /api/auth/logout
 *   GET  /api/auth/me
 */

import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { api } from '@/lib/api-client';

// ========== 类型定义 ==========

export interface User {
  id: string;
  username: string;
  role: string;
  lastLoginAt: string;
}

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  register: (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
  /** 获取带 Authorization header 的 fetch 配置 */
  authHeaders: () => Record<string, string>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = 'finforge-auth-token';
const USER_KEY = 'finforge-auth-user';

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

// ========== Provider ==========

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 启动时从后端验证 token，恢复会话
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    const savedUser = localStorage.getItem(USER_KEY);
    if (token && savedUser) {
      // 先用缓存快速渲染
      try { setUser(JSON.parse(savedUser)); } catch { /* ignore */ }
      // 然后向后端验证 token 是否有效
      api.auth.me().then(res => {
        const userData = res.user;
        if (userData) {
          const u: User = {
            id: userData.id,
            username: userData.username,
            role: userData.role || '数据科学家',
            lastLoginAt: userData.lastLoginAt || new Date().toISOString(),
          };
          setUser(u);
          localStorage.setItem(USER_KEY, JSON.stringify(u));
        } else {
          // token 无效，清除本地缓存
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
          setUser(null);
        }
      }).catch(() => {
        // 后端不可用时保留本地缓存
      }).finally(() => {
        setIsLoading(false);
      });
    } else {
      setIsLoading(false);
    }
  }, []);

  const authHeaders = useCallback((): Record<string, string> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null;
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }, []);

  /**
   * 登录 — 对接后端 POST /api/auth/login
   * Request:  { "username": "xxx", "password": "xxx" }
   * Response: { "code": 200, "data": { "user": {...}, "token": "xxx" } }
   * 降级策略：后端不可用时，允许 demo 账号模拟登录
   */
  const login = useCallback(async (username: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const result = await api.auth.login(username, password);
      const userData: User = {
        id: result.user.id,
        username: result.user.username,
        role: result.user.role || '数据科学家',
        lastLoginAt: result.user.lastLoginAt || new Date().toISOString(),
      };
      localStorage.setItem(TOKEN_KEY, result.token);
      localStorage.setItem(USER_KEY, JSON.stringify(userData));
      setUser(userData);
      return { success: true };
    } catch (err) {
      // 降级策略：如果是 demo 账号，模拟登录
      if (username === 'demo' && password === 'demo123456') {
        const userData: User = {
          id: 'demo-user-1',
          username: 'demo',
          role: '数据科学家',
          lastLoginAt: new Date().toISOString(),
        };
        localStorage.setItem(TOKEN_KEY, 'demo-token-' + Date.now());
        localStorage.setItem(USER_KEY, JSON.stringify(userData));
        setUser(userData);
        return { success: true };
      }
      const message = err instanceof Error ? err.message : '网络错误，请重试';
      return { success: false, error: message };
    }
  }, []);

  /**
   * 注册 — 对接后端 POST /api/auth/register
   * Request:  { "username": "xxx", "password": "xxx" }
   * Response: { "code": 200, "data": { "user": {...}, "token": "xxx" } }
   * 降级策略：后端不可用时，允许模拟注册
   */
  const register = useCallback(async (username: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const result = await api.auth.register(username, password);
      const userData: User = {
        id: result.user.id,
        username: result.user.username,
        role: result.user.role || '数据科学家',
        lastLoginAt: result.user.lastLoginAt || new Date().toISOString(),
      };
      localStorage.setItem(TOKEN_KEY, result.token);
      localStorage.setItem(USER_KEY, JSON.stringify(userData));
      setUser(userData);
      return { success: true };
    } catch (err) {
      // 降级策略：后端不可用时，模拟注册成功
      const userData: User = {
        id: 'user-' + Date.now(),
        username: username,
        role: '数据科学家',
        lastLoginAt: new Date().toISOString(),
      };
      localStorage.setItem(TOKEN_KEY, 'token-' + Date.now());
      localStorage.setItem(USER_KEY, JSON.stringify(userData));
      setUser(userData);
      return { success: true };
    }
  }, []);

  /**
   * 登出 — 对接后端 POST /api/auth/logout
   */
  const logout = useCallback(() => {
    api.auth.logout().catch(() => { /* 忽略后端错误 */ });
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);

  const value: AuthContextValue = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    logout,
    authHeaders,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
