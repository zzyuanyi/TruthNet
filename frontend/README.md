# TruthNet 前端

React + Vite + TypeScript 前端，提供智能问答、公司画像、跨公司对比和报告入口。所有后端请求统一经 `src/config.js` 配置，不在浏览器代码中保存数据库账号、模型密钥或服务器密码。

## 目录

```text
src/
├── pages/        # 路由页面
├── components/   # 通用组件与业务组件
├── lib/          # API 客户端与前端工具
├── types/        # API 数据类型
└── config.js     # 前端运行配置
public/           # 静态资源
```

## 配置

复制 `.env.example` 为 `.env`，按部署环境填写：

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
# VITE_WS_BASE_URL=ws://127.0.0.1:8001
```

`VITE_API_BASE_URL` 为空时，前端使用同源 `/api/v1`；开发模式由 Vite 代理转发到 8001。前端环境变量会被打包进浏览器，因此只能放公开地址，不能放任何密钥或密码。

## 启动

需先启动后端。Windows 下在本目录运行：

```powershell
.\start.ps1
```

首次运行脚本会在 `node_modules/` 缺失时执行锁文件安装；该目录已被 `.gitignore` 排除。默认访问 <http://127.0.0.1:5000/>。

也可手动执行：

```powershell
corepack pnpm@9.0.0 install --frozen-lockfile
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8001'
pnpm dev
```

## 验证与构建

```powershell
pnpm typecheck
pnpm build
```
