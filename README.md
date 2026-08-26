# TruthNet · 织网鉴真

[![CI](https://github.com/zzyuanyi/TruthNet/actions/workflows/ci.yml/badge.svg)](https://github.com/zzyuanyi/TruthNet/actions/workflows/ci.yml)

面向上市公司财务核验场景的智能分析原型。系统将自然语言问题转为可追溯的财务勾稽、股权关系与公开事件核查任务，并以“风险信号 → 程度量化 → 核查动作”的结构输出结果。

它用于识别异常信号和提示优先核验方向，不替代审计、监管或司法认定；不提供买卖、持仓或清仓建议。

## 当前能力

| 入口 | 能力 | 输出重点 |
|---|---|---|
| 智能问答 | 识别企业与问题意图，按需调度财务、股权、事件模块 | 可读摘要、限制说明、证据链接 |
| 公司画像 | 展示综合风险、R1–R7 规则、股权图、事件时间线与证据详情 | L0 风险信号、L1 量化参考、L2 核查动作 |
| 公司对比 | 在同一口径下比较多家公司的规则触发、指标和覆盖情况 | 风险排序、共同/独有信号与对比结论 |
| 报告导出 | 将风险评分、趋势图、股权信息和核查清单组织为 PDF | 可回查的分析报告 |

### 核查规则

R1–R7 是一组面向非金融企业、固定母公司报表口径的跨科目勾稽规则：

| 规则 | 核查信号 |
|---|---|
| R1 | 应收账款与营业收入增速背离 |
| R2 | 现金流与利润背离 |
| R3 | 存贷双高 |
| R4 | 存货与营业收入背离 |
| R5 | 毛利率/费用率异常 |
| R6 | 其他应收款与关联占用风险 |
| R7 | 盈利质量与非经常性依赖 |

每条规则记录字段、公式、阈值与版本；在数据条件满足时补充行业分位、历史变化或距触发线的量化参考，并给出常识级核查动作。规则细节见 [RULES_SPEC.md](docs/RULES_SPEC.md)。

## 工作方式

```text
加载上下文 → 识别企业 → 规划所需模块 → 执行财务/股权/事件核查
        → 交叉验证 → 组织结论与证据 → 输出对话、画像、对比或报告
```

- **先算后说**：数值计算、规则触发和严重程度由确定性代码完成；大模型仅承担意图理解与语言组织，异常时可安全降级为规则摘要。
- **先证后文**：结论与报表记录、公式输入、股权路径或公开来源相互关联，用户可从结论返回原始证据。
- **按需调度**：围绕当前对话主体维护近期上下文与摘要记忆；只调用回答问题所需的模块，避免把无关信息混入结论。
- **如实说明覆盖**：数据未覆盖、数据不足、模块尚未生成与接口加载失败会分别展示，空时间线不等同于“未发生事件”。

## 技术架构

| 层级 | 主要技术 |
|---|---|
| 服务与编排 | Python 3.11、FastAPI、LangGraph、Pydantic |
| 数据与关系 | SQLAlchemy、SQLite/MySQL、Neo4j/NetworkX、Chroma |
| 规则与证据 | R1–R7 确定性规则引擎、计算输入与来源追溯、风险模式匹配 |
| 前端呈现 | React 18、Vite 6、TypeScript、Tailwind、G6、Recharts |
| 质量保障 | pytest、Ruff、接口契约测试、评测框架、GitHub Actions |

完整的架构、接口和数据约定分别见 [ARCHITECTURE.md](docs/ARCHITECTURE.md)、[API_CONTRACT_V1.md](docs/API_CONTRACT_V1.md) 与 [DATA_CONTRACT.md](docs/DATA_CONTRACT.md)。

## 快速启动

### 1. 前置条件

- Python 3.11+
- Node.js 20+（CI 使用 Node.js 22）
- pnpm 9（仓库锁定 `pnpm@9.0.0`）

若仅体验内置示例，可使用 SQLite 与 NetworkX；需要完整 MySQL、Neo4j 与外部模型/数据服务时，请按 [SETUP_FULL_PROFILE_WINDOWS.md](docs/SETUP_FULL_PROFILE_WINDOWS.md) 配置。密钥仅写入本地 `.env`，不要提交到仓库。

### 2. 启动后端

```powershell
cd backend
python -m pip install -r requirements.txt
python scripts/seed_db.py             # 可选：初始化内置 SQLite 示例数据
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

健康检查：<http://127.0.0.1:8001/api/v1/healthz>

> `seed_db.py` 只初始化仓库内置的 SQLite 示例库。竞赛演示或完整数据环境请使用团队配置的数据源；不同公司、模块与期间的数据覆盖并不相同。

### 3. 启动前端

另开一个终端：

```powershell
cd frontend
corepack enable
corepack pnpm@9.0.0 install --frozen-lockfile
$env:VITE_API_BASE_URL = "http://127.0.0.1:8001"
pnpm dev
```

浏览器访问 <http://127.0.0.1:5000/>。`VITE_API_BASE_URL` 未设置时，开发代理也默认指向 `http://127.0.0.1:8001`；显式设置可避免多服务环境中连错端口。合并后端代码后，请重启 8001 进程再验收。

## 数据与使用边界

- 财务规则当前固定使用母公司报表口径，金融企业不适用时会明确标注。
- 股权关系可展示上游、下游与多跳路径；路径深度和风险信息受当前图谱数据覆盖限制。
- 事件时间线依赖已接入的公告与事件簇。没有数据覆盖时，系统显示“未覆盖”，而非推断为没有负面事件。
- 系统输出的是核查优先级和原始数据线索，不构成投资建议或造假结论。

## 验证与质量检查

```powershell
# 后端与评测框架
python -m pytest backend/tests -v
python -m pytest tests/evaluation -v

# 代码规范
ruff check .
ruff format --check .

# 前端
cd frontend
pnpm typecheck
pnpm build
```

GitHub Actions 在 Windows、macOS、Linux 上运行 Python 测试、编码与路径检查、Ruff；前端执行依赖锁定安装、TypeScript 类型检查和生产构建。外部 MySQL/Neo4j 集成验证需要显式配置相应环境，详见 [ENVIRONMENT_REPRODUCTION.md](docs/ENVIRONMENT_REPRODUCTION.md)。

## 项目结构

```text
TruthNet/
├── backend/                 # FastAPI、编排、规则、数据访问与测试
├── frontend/                # React 前端：问答、画像、对比与报告入口
├── docs/                    # 架构、接口、规则、数据契约与评测说明
├── data/                    # 本地示例数据与数据工件（不提交敏感信息）
├── scripts/                 # 环境、检查与维护脚本
├── tests/evaluation/        # 对话与评测框架测试
└── .github/workflows/ci.yml # 持续集成配置
```

## 文档索引

| 文档 | 用途 |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系统分层与编排设计 |
| [RULES_SPEC.md](docs/RULES_SPEC.md) | R1–R7 规则、公式、阈值与口径 |
| [API_CONTRACT_V1.md](docs/API_CONTRACT_V1.md) | REST 接口契约 |
| [PROVENANCE_CONTRACT.md](docs/PROVENANCE_CONTRACT.md) | 结论、证据和计算输入的追溯约定 |
| [DATA_CONTRACT.md](docs/DATA_CONTRACT.md) | 数据对象与存储约定 |
| [FRONTEND_DESIGN.md](docs/FRONTEND_DESIGN.md) | 前端页面与交互设计 |
| [EVALUATION_REPORT_FINAL_V1.md](docs/EVALUATION_REPORT_FINAL_V1.md) | 评测口径与结果记录 |
| [SETUP_FULL_PROFILE_WINDOWS.md](docs/SETUP_FULL_PROFILE_WINDOWS.md) | Windows 完整环境配置 |

## 许可证

本项目为竞赛研究原型，许可证待定。
