# 推荐合并计划

## 总览

三个 PR 不能直接一键合并。需要在集成分支上组合验证后，按顺序回灌。

---

## 推荐合并顺序

```
PR #10 (数据基础层)
  ↓
PR #11 (图谱/规则层)
  ↓
PR #9  (API/Agent层)
```

**理由**：
- PR #10 提供 MySQL 结构化数据（公司、三表、股东、公告、研报）— 这是所有上层功能的基础
- PR #11 提供 Neo4j 图数据和公告情绪分类 — 依赖 MySQL 中的实体 ID 和公告数据
- PR #9 提供 WebSocket Agent 集成 — 依赖 MySQL/Neo4j/Chroma 的真实 adapter

---

## Step 1: 回灌 PR #10（数据基础）

### 文件清单

从集成分支回灌到 PR #10 原分支或新 PR：

| 文件 | 操作 | 说明 |
|------|------|------|
| `scripts/task1_mysql_import.py` | 替换 | 重构版：配置驱动、幂等、安全 |
| `scripts/task5_industry_fill.py` | 替换 | 重构版：CLI args、网络容错 |
| `scripts/task3_chromadb_import.py` | 替换 | 重构版：显式操作、确定性 chunk ID |
| `scripts/_read_data.py` | 替换 | 重构版：移除硬编码 |
| `scripts/load_kangmei_fixture.py` | 新增 | 替换 kangmei.sql |
| `data/fixtures/kangmei.sql` | 删除 | 由 Python loader 替代 |

### 建议 commit message

```
feat(data): 重构 MySQL 全量入库 + 行业补全 + 康美 fixture + ChromaDB

重构 PR #10 数据流水线，修复硬编码凭据/路径/import副作用等安全问题：

- task1_mysql_import.py: 配置驱动(staging+upsert)、统一entity_id、幂等
- task5_industry_fill.py: CLI args、akshare缓存/重试、行业来源标注
- task3_chromadb_import.py: 显式--rebuild-collection、确定性chunk ID
- load_kangmei_fixture.py: 安全Python loader(替代DROP TABLE SQL dump)
- 所有脚本: 副作用只在main()、统一使用normalizer

Co-authored-by: xingran-taro <xingranbu@gmail.com>
```

### 回归命令

```bash
python scripts/task1_mysql_import.py --data-root <比赛数据> --dry-run
python scripts/task1_mysql_import.py --data-root <比赛数据>
python scripts/task1_mysql_import.py --data-root <比赛数据>  # 第二次（幂等验证）
python scripts/load_kangmei_fixture.py --verify-only
python -m pytest backend/tests -v
```

---

## Step 2: 回灌 PR #11（图谱/规则层）

### 前置条件

PR #10 已合并到 main，main 已有：
- MySQL 中 companies 表（含统一 entity_id）
- 公告 sentiment 字段可更新

### 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `scripts/neo4j_full_import.py` | 替换 | 重构版：非破坏性、历史快照、统一 normalizer |
| `scripts/announcement_sentiment.py` | 替换 | 重构版：33类覆盖、版本化、MySQL 幂等更新 |
| `backend/app/infrastructure/graph/neo4j/equity_graph.py` | 替换 | 重构版：normalizer 集成、relationship_id、as_of |
| `backend/app/infrastructure/graph/normalizer.py` | 新增 | Wind Code 统一规范化器 |
| `backend/tests/unit/test_normalizer.py` | 新增 | 40+ 参数化测试 |
| `docs/RULES_SPEC.md` | 更新 | 一致性审核、状态标记、模板化 |

### 建议 commit message

```
feat(graph): 重构 Neo4j 全量图谱 + 公告情绪 + RULES_SPEC

重构 PR #11 图谱/规则层，修复Wind Code、历史快照、情绪覆盖等关键问题：

- Neo4j: relationship_id保留历史持股快照、稳定实体节点、非破坏性导入
- equity_graph: 统一normalizer、移除.SH fallback、支持as_of/is_latest
- announcement_sentiment: 29→33类目标覆盖、unknown标记、映射表版本化
- normalizer: 统一SH/SZ/BJ/XSHG/XSHE处理、fail-closed
- RULES_SPEC: DATA_CHECKLIST对齐、母公司口径声明、状态标记

Co-authored-by: 2659856590-svg <2659856590-svg@users.noreply.github.com>
```

### 回归命令

```bash
python scripts/neo4j_full_import.py --data-file <股东Excel> --dry-run
python scripts/neo4j_full_import.py --data-file <股东Excel>
python scripts/neo4j_full_import.py --data-file <股东Excel>  # 第二次（幂等验证）
python scripts/announcement_sentiment.py --analyze-dict --dict-file <fcode字典>
python -m pytest backend/tests/unit/test_normalizer.py -v
python -m pytest backend/tests -v
```

---

## Step 3: 回灌 PR #9（API/Agent层）

### 前置条件

PR #10 + PR #11 已合并到 main，数据层完全就绪。

### 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/api/v1/routers/chat.py` | 替换 | 重构版：延迟 graph 加载、asyncio.to_thread、结构化日志 |
| `backend/app/api/v1/routers/companies.py` | 替换 | 重构版：entity_id 对齐、404 Problem Details、画像端点 |
| `backend/app/main.py` | 更新 | 路由统一注册、移除重复WS端点、保留legacy |
| `backend/tests/websocket/test_chat_ws_agent.py` | 新增 | 5条 WS 集成测试 |

### 建议 commit message

```
feat(api): WS Agent 接入 + 公司画像 + legacy 兼容

重构 PR #9 API/Agent层，修复import副作用、阻塞事件循环、异常处理：

- chat.py: 延迟graph编译、asyncio.to_thread避免阻塞、结构化异常日志
- companies.py: entity_id对齐V12 CompanyRef、404 Problem Details
- main.py: 每个URL只注册一次、路由统一、保留legacy兼容
- WS: V12 9字段信封、5事件类型dispatch、旧格式兼容

Co-authored-by: zhiyuhan0703 <zyh0703@mail.ustc.edu.cn>
```

### 回归命令

```bash
python -m pytest backend/tests/websocket/test_chat_ws_agent.py -v
python -m pytest backend/tests/contract/ -v
python -m pytest backend/tests -v
cd frontend && pnpm build
```

---

## 替代方案（如无法回灌原分支）

若无法向原作者分支推送，创建单一 integration PR：

```bash
# 在集成分支上
git checkout integration/pr9-pr10-pr11-harmonization

# 创建 PR（人工操作）
gh pr create \
  --base main \
  --head integration/pr9-pr10-pr11-harmonization \
  --title "feat: PR #9+#10+#11 和谐集成 — 数据+图谱+API 全栈" \
  --body "集成 PR #9, #10, #11 的全部有效成果，修复安全问题和不一致。

  原 PR：
  - PR #9 (zhiyuhan0703): WS Agent 接入 + 公司画像
  - PR #10 (xingran-taro): 数据流水线 MySQL/ChromaDB
  - PR #11 (2659856590-svg): Neo4j图谱 + 公告情绪 + RULES_SPEC

  详见 reports/pr9_pr10_pr11_integration/00_summary.md"

# 将原 PR 标记为 superseded（人工操作）
gh pr comment 9 --body "Superseded by PR #X (和谐集成版)"
gh pr comment 10 --body "Superseded by PR #X (和谐集成版)"
gh pr comment 11 --body "Superseded by PR #X (和谐集成版)"
```

---

## 人工操作 Checklist

- [ ] Step 0: 修复 numpy 兼容性 (`pip install "numpy<2"`)
- [ ] Step 0: 确认 MySQL 8.4 运行中 + truthnet 数据库存在
- [ ] Step 0: 确认 Neo4j 2025.06.1 运行中
- [ ] Step 0: 确认 Python 3.11 环境（非 3.12）
- [ ] Step 1: 运行数据流水线（PR #10 文件）
- [ ] Step 1: 验证 MySQL 导入幂等性
- [ ] Step 1: 验证 ChromaDB 导入幂等性
- [ ] Step 2: 运行 Neo4j 全量导入（PR #11 文件）
- [ ] Step 2: 验证图谱节点/关系数稳定
- [ ] Step 2: 验证公告情绪分类覆盖率
- [ ] Step 3: 运行 API/WS 测试（PR #9 文件）
- [ ] Step 3: 验证康美 E2E
- [ ] Step 4: 前端 typecheck + build
- [ ] Step 4: 全部 pytest 通过
- [ ] Step 4: Ruff + pre-commit 通过
- [ ] Step 5: commit → push → create PR → 请求 review
- [ ] Step 5: 通知三位原作者 review 集成版
