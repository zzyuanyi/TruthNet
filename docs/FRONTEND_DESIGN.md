# 前端设计文档 — V12 Baseline

> **版本**: 1.0
> **基线**: V12 (2026-07-17)

---

## 技术栈

| 层级 | 技术 | 状态 |
|------|------|------|
| 框架 | React 18 + Vite 6 + TypeScript 5.6 | ✅ 已初始化 |
| UI 组件 | shadcn/ui + Tailwind CSS | 🔸 待接入 |
| 图表 | Recharts | 🔸 待接入 |
| 图谱 | D3.js | 🔸 待接入 |
| HTTP 客户端 | fetch / axios | ✅ 已实现 |
| WebSocket 客户端 | 原生 WebSocket API | ✅ 已实现 |

---

## 组件树

```text
App
├── Header
├── ChatPanel          — 对话主界面（输入框 + 消息列表）
│   ├── MessageList    — 消息流（支持 Markdown 渲染）
│   └── InputBox       — 问题输入
├── RiskPanel          — 风险评分仪表盘
├── EvidenceList       — 证据链列表
├── TimelinePanel      — 事件时间线
└── GraphPanel         — 股权穿透图谱（D3.js）
```

---

## 类型对齐

`frontend/src/types/api.ts` 必须与 `backend/app/schemas/` 和 `backend/app/api/v1/schemas/` 严格一致。

V12 新增类型：
- `V12Response<T>` — `{data, meta, warnings}`
- `ApiMeta` — 响应元数据
- `WarningItem` — 警告项
- `ProblemDetail` — 错误格式
- `CompanyRef` — 公司引用
- `EvidenceRef` — 证据引用
- `Claim` — 结论声明

---

## 开发命令

```bash
cd frontend
pnpm install
pnpm dev          # 开发服务器
pnpm build        # 生产构建
pnpm typecheck    # 类型检查
```

---

## 注意事项

1. 前端不私自修改后端定义的字段名和类型
2. V12 新响应格式 `{data, meta, warnings}` 与旧 `{code, data, message, trace_id}` 并存
3. WebSocket 使用 V12 event envelope
4. shadcn/ui / Recharts / D3.js 接入为后续阶段任务
