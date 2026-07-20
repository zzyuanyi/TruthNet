# 织网鉴真 · 开发手册 — 环境搭建 + Phase B

> 2026-07-18 | 提交截止 2026-08-20
> 蓝图参考：[TruthNet_综合设计方案_V12.md](design/TruthNet_综合设计方案_V12.md)

---

## 开发规范（全员必读）

### Git 工作流

每人一条个人分支：`feature/<你的用户名>-workspace`。主线是 main，只有通过 PR 才能合并。

**日常开发**：

```bash
# 开始写代码前
git switch feature/<你的名字>-workspace
git fetch origin --prune
git pull --ff-only origin feature/<你的名字>-workspace

# 写完一个功能后
git add <改动的文件>
git commit -m "feat: 完成了什么功能"
git push origin feature/<你的名字>-workspace
```

> `git push` = 上传到 GitHub，不影响主线。随时 push，不怕坏。

**什么时候提 PR**：

| 情况                       | 怎么做                                              |
| -------------------------- | --------------------------------------------------- |
| 代码能在本地跑通、测试通过 | 提 PR 到 main，在群里说明                           |
| 代码写到一半、还没跑通     | 只 push 到个人分支，不提 PR                         |
| 多人同时改同一个文件       | 后 push 的人会遇到冲突，群里说一声，不要 force push |

**别人提交了新代码，我怎么拿到**：

```bash
# 如果别人合到了 main（建表脚本、规则文档等）
git checkout feature/<你的名字>-workspace   # 先回自己分支
git fetch origin --prune                    # 看看远程有什么更新
git merge origin/main                       # 把 main 的新内容合到自己的分支
git push origin feature/<你的名字>-workspace

# 如果别人还在分支上没合 main，但你急用他的代码
# 直接 git pull origin <他的分支名>
# 一般不这么做，大部分时候等合 main 后拉取即可
```

> **纪律**：每天开工前先 `git fetch && git merge origin/main`，避免在旧代码上白写一天。

**禁止：** 直接 push 到 main、`git push --force`、`git reset --hard`、不看 diff 就 `git add -A`、提交 `.env`/密码/数据文件/`node_modules`

### 遇到问题怎么办

| 问题                          | 找谁                                     |
| ----------------------------- | ---------------------------------------- |
| 不知道任务怎么做              | 先看 V12 设计方案，还不行在群里问        |
| 验收标准怎么算通过            | 看任务行的"验收标准"列，有具体命令       |
| Python/Conda/MySQL/Neo4j 报错 | 先查 V6 环境搭建文档，还不行群里 @后端组 |
| 前端编译/依赖报错             | 群里 @前端组                             |
| 设计文档不理解                | 群里 @队长                               |

### 代码底线

- 后端：UTF-8，`pathlib.Path`，API 统一 `/api/v1/...`，响应格式 `{data, meta, warnings}`
- 前端：类型从 OpenAPI 生成，组件放对应目录（chat/ analysis/ company/）
- 全组：commit 格式 `feat: / fix: / docs: / chore:`，提交前跑 doctor.py + ruff + pytest + pnpm build

### 任务完成了怎么算

1. 对照任务行确认交付物已产出
2. 跑验收标准确认通过
3. 在群里说"XX 任务完成"，附截图
4. git push 到个人分支

---

## Phase 0 · 开发环境就绪（7/19 前完成）

> **每人本地环境跑通，MySQL/Neo4j 可连接，后端能启动，前端能 build。**

### 安装清单

| 软件    | 版本                         | 验证                                            |
| ------- | ---------------------------- | ----------------------------------------------- |
| Python  | 3.11.x                       | `conda activate truthnet && python --version` |
| Node.js | 22.x（或 ≥18 兼容）         | `node --version`                              |
| pnpm    | 最新                         | `pnpm --version`                              |
| MySQL   | 8.4.x                        | `mysql -u root -p` 登入                       |
| Neo4j   | 2025.06.1+（禁止 2025.06.0） | `http://localhost:7474` 可打开                |

### 仓库与依赖

```bash
git clone https://github.com/zzyuanyi/TruthNet.git && cd TruthNet
conda create -n truthnet python=3.11 -y && conda activate truthnet
pip install -r requirements.txt
```

### 数据库初始化

```sql
CREATE DATABASE IF NOT EXISTS truthnet CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS 'truthnet'@'127.0.0.1' IDENTIFIED BY '你的密码';
GRANT ALL PRIVILEGES ON truthnet.* TO 'truthnet'@'127.0.0.1';
```

### 启动验证

```bash
python scripts/doctor.py                    # 环境检测
python -m pytest backend/tests -v           # 应 ≥ 113 个测试通过
cd frontend && pnpm install --frozen-lockfile && pnpm build && pnpm typecheck && cd ..
```

> 详细安装指引见 CS 侧的《TruthNet_V12_全成员环境复现_Prompt_V6》，含镜像加速、无管理员权限方案。

### Phase 0 完成标志

```
✅ python scripts/doctor.py 跑通
✅ uvicorn 启动看到 Swagger 页面
✅ pnpm dev 看到空白页面
✅ MySQL 可登入，Neo4j 浏览器可打开
✅ 数据文件已在本地
```

---

## Phase B · 最小 E2E（7/20-7/26，7天）

> **输入"康美药业有造假风险吗" → LangGraph 编排调度 → 结构化 JSON → 前端完整展示。**

### 团队分工

| 组     | 人数 | Phase B 做什么                                          |
| ------ | :--: | ------------------------------------------------------- |
| 前端组 | 1 人 | V12 Mock JSON → 三页面 + D3 + WS Reducer（不依赖后端） |
| 后端组 | 3 人 | 康美 fixture → Agent + REST + WS（不等真数据）         |
| 数据组 | 2 人 | CSV → MySQL + Neo4j + fixture（完全独立）              |

### 各组入口文档

| 组   | 必读章节                                                      |
| ---- | ------------------------------------------------------------- |
| 前端 | V12 §4-5（页面/组件）、§11-12（API/WS）、附录A（类型）      |
| 后端 | V12 §6-9（架构/Agent/证据）、§11-13（契约）、§7.3（State） |
| 数据 | V12 §1.4（数据全景）、§10（数据架构）、§8.1（规则）        |

### 康美 fixture 说明

一份只含康美药业（600518.SH）数据的小 SQL 文件——三表 3 个季度、股东 10 条、公告 5 条、研报 3 篇。**数据组从全量 CSV 筛出来，提交到 `data/fixtures/kangmei.sql`。后端用 fixture 开发 Agent，不用等全量 6,700 只股票入库。**

### 执行顺序

```
第一步：后端 ⑤ MySQL 建表脚本 → commit 到仓库（全组的第一个阻塞点）
    数据 ⑦ RULES_SPEC

第二步：数据 ①⑥ 拿到建表脚本 → 全量入库 + 产出康美 fixture
    后端 ①⑧ LangGraph 编排 + DeepSeek Provider（不等数据，先写逻辑）

第三步：后端拿到 fixture → 全部 Agent + REST + Neo4j + WS
    数据 ②③④⑤ 图谱 + Chroma + 情绪映射 + 行业补全

第四步（最后）：前端 WS 联调
    （前端 ①-⑦ 全程独立，用 V12 JSON 样例写 Mock，不等后端）
```

---

### 前端组（完全不依赖后端）

| # | 任务                                                                | 交付物                       | 验收标准                                                             |
| :-: | ------------------------------------------------------------------- | ---------------------------- | -------------------------------------------------------------------- |
| 1 | 从 V12 §11 抄 10 个 P0 端点响应 JSON 写 Mock                       | `mocks/`                   | JSON Schema 校验通过                                                 |
| 2 | 对话主页：用户输入→模块进度→流式文本→结构化卡片→追问建议        | `/` 页面                   | 发送`chat.query` → WS 收到含 `risk_level` 的 `turn.completed` |
| 3 | 面板六状态（empty→loading→partial→success→unavailable→failed） | `AnalysisPanel.tsx`        | 6 种状态各 mock 一遍                                                 |
| 4 | 多会话管理（新建/切换/删除/重命名）                                 | `SessionSidebar.tsx`       | 3 个会话各发 5 条消息，切回第一个无变化                              |
| 5 | 企业画像页：信息/标签/规则/股权图/关联方/时间线/证据                | `/company/:code`           | 7 个请求在 Network 面板中并行发出                                    |
| 6 | D3 股权穿透图：拖拽/缩放/深度筛选/节点详情                          | `EquityGraph.tsx`          | 50+ 节点不卡，路径高亮                                               |
| 7 | WS Reducer 按 V12 §5.9.2 处理 10 种事件                            | `api/websocket/reducer.ts` | 用 mock WS 消息序列验证                                              |

---

### 后端组

| # | 任务                                                                          | 交付物                            | 验收标准                                                                  |
| :-: | ----------------------------------------------------------------------------- | --------------------------------- | ------------------------------------------------------------------------- |
| 1 | LangGraph 编排：LoadContext→ResolveEntity→并行模块→CrossValidate→Generate | `agents/graph.py`               | `graph.invoke` 后 `final_response` 非空，`module_status` 含 3+ 模块 |
| 2 | `/api/v1/chat/ws` WebSocket 对话                                            | WS 端点                           | wscat 连接 → 发送 query → 60s 内 ≥5 条事件，含`turn.completed`       |
| 3 | `/api/v1/companies?query=` 搜索 + `/api/v1/companies/{code}` 画像         | REST × 2                         | curl 查"康美"返回候选，画像返回基本信息                                   |
| 4 | `/api/v1/companies/{code}/equity` 股权穿透                                  | REST                              | 返回 nodes+edges+paths                                                    |
| 5 | MySQL 建表（V12 §10）+ Alembic migration                                     | `alembic/versions/`             | 7 张表创建成功                                                            |
| 6 | Neo4j 图导入（实体对齐+一致行动人合并）                                       | `infrastructure/graph/neo4j/`   | 康美链路+权重正确                                                         |
| 7 | ChromaDB 研报分块入库                                                         | `infrastructure/vector/chroma/` | metadata 含 source_id/wind_code                                           |
| 8 | DeepSeek Provider 接入（封装统一 LLM 接口+结构化输出+重试+降级）              | `infrastructure/llm/deepseek/`  | 调用成功，JSON 可 parse                                                   |

---

### 数据组

| # | 任务                                          | 交付物                        | 验收标准                            |
| :-: | --------------------------------------------- | ----------------------------- | ----------------------------------- |
| 1 | MySQL 全量入库（三表+公司+股东+公告+研报）    | 全量数据库                    | `SELECT COUNT(*)` 与 CSV 核对     |
| 2 | Neo4j 全量图谱（~6161 股）                    | 图数据库                      | 康美+裕兴+茅台，每只控制链路 ≥2 层 |
| 3 | ChromaDB 研报摘要分块入库                     | ChromaDB collections          | metadata 完整                       |
| 4 | 公告情绪映射（33 类 fcode→正/负/中性）       | announcements.sentiment       | 33 类全覆盖                         |
| 5 | 行业分类 akshare 补全                         | companies.industry_l1         | 覆盖率 ≥90%                        |
| 6 | 康美全链路 fixture（导出为`.sql`）          | `data/fixtures/kangmei.sql` | 字段与 V12 一致                     |
| 7 | `RULES_SPEC.md`（7 规则公式+阈值+适用条件） | 提交到仓库                    | 评审会逐条讲清                      |

---

### Phase B 完成标志

```
✅ 对话主页输入"康美有造假风险吗"→ 前端展示结构化回答
✅ 企业画像页 7 区块有数据
✅ 股权穿透图可拖拽
✅ MySQL + Neo4j + ChromaDB 可通过 Python 连接
✅ pytest ≥113 通过，ruff + pre-commit 全绿
```

---

> 下一阶段 Phase C（核心业务）将在 Phase B 末尾下发。先专注做完眼前 22 个任务。
