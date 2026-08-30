# TruthNet 后端

FastAPI 后端，负责实体识别、任务编排、R1–R7 财务勾稽、股权关系、事件信息、证据追溯和报告生成。运行配置集中在根目录 `config.py`，由根目录 `.env` 或系统环境变量读取；`app/core/config.py` 仅保留为既有导入的兼容入口。

## 目录

```text
app/
├── api/             # REST 与 WebSocket 接口
├── application/     # 编排与应用服务
├── domain/          # 财务规则与领域模型
├── infrastructure/  # MySQL、Neo4j、LLM、向量库适配
└── core/            # 配置、启动和通用约束
scripts/             # 数据初始化与维护脚本
tests/               # 后端测试
config.py            # 后端运行配置（环境变量读取）
```

## 配置

复制后端目录 `.env.example` 为同目录 `.env` 后按环境填写。`config.py` 支持 SQLite/NetworkX/Mock 的轻量模式，也支持 MySQL、Neo4j 与外部模型服务；数据库账号、密码和 API Key 均只从环境变量读取。开发仓库中若未创建 `backend/.env`，会兼容读取仓库根目录 `.env`。

默认轻量模式无需外部数据库：

```env
TRUTHNET_PROFILE=lite
SQL_BACKEND=sqlite
GRAPH_BACKEND=networkx
LLM_BACKEND=mock
BACKEND_PORT=8001
```

完整 MySQL/Neo4j 配置见根目录 `.env.example` 和 `docs/SETUP_FULL_PROFILE_WINDOWS.md`。

## 启动

在本目录运行：

```powershell
.\start.ps1
```

首次运行会在缺少 FastAPI/Uvicorn 时按根目录 `requirements.txt` 安装依赖。默认服务地址为 <http://127.0.0.1:8001/>，健康检查为 <http://127.0.0.1:8001/api/v1/healthz>。

也可手动执行：

```powershell
python -m pip install -r ..\requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

## 验证

在仓库根目录执行：

```powershell
python -m pytest backend/tests -q
python -m pytest tests/evaluation -q
```
