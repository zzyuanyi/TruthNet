# PR 文件级决策矩阵

> 每个 PR 的文件逐一审计，标注接受/重做/替代/拒绝及理由。

---

## PR #9: feat(api): WS 接入 Agent 图 + 公司搜索画像 + 清理 legacy

**head**: feature/zhiyuhan0703-github-skill-test @ 064688ab
**CI**: FAILURE (all platforms)
**作者**: zhiyuhan0703

| 文件 | 原始意图 | 处理 | 理由 | 测试 |
|------|---------|------|------|------|
| `backend/app/api/v1/routers/chat.py` | WS 接入 Agent graph + V12 9字段信封 + 客户端事件 dispatch | **accept_with_rework** | 接受：Agent 图接入、V12 信封、事件分发、旧格式兼容。重做：延迟编译 graph（非 import 时）、asyncio.to_thread（非 sync invoke）、结构化日志（非 bare except）、保留 ChatContext Pydantic 类型 | `test_chat_ws_agent.py` |
| `backend/app/api/v1/routers/companies.py` | 搜索字段对齐 V12 CompanyRef + `/{code}` 画像端点 | **accept_with_rework** | 接受：entity_id/wind_code/sec_name/exchange/industry_l1 字段对齐、画像端点。重做：404 Problem Details（非 200+data=null）、mock 数据标注 TODO、硬编码风险注明 mock | 合约测试 |
| `backend/app/api/v1/schemas/chat.py` | 移除 domain.conversation 依赖 | **accept_with_rework** | ChatContext 降级为 dict → 改为保留 ChatContext Pydantic 类型（当前有循环导入问题，待 Phase C 解决） | - |
| `backend/app/main.py` | 删除 legacy WS 和 POST 端点 | **superseded** | 不直接删除。legacy WS 移至 router 统一处理（保留兼容），legacy chat POST 保留，路由不再重复注册 | `test_api_contract_smoke.py` |
| `backend/tests/contract/test_api_v1_contract.py` | 旧格式测试 → V12 格式 | **accept_with_rework** | 接受 V12 字段名更新。修复遗留的 `data["warnings"]` / `data["missing_modules"]` 断言（V12 turn.completed payload 结构不同） | 合约测试 |
| `backend/tests/websocket/test_chat_ws_agent.py` | 新增 5 条 WS 集成测试 | **accept** | V12 信封完整性、事件流验证、legacy 格式兼容、ping/heartbeat、错误处理 | WS 集成测试 |
| `backend/tests/test_websocket_smoke.py` | 更新为 V12 格式 | **accept_with_rework** | 修复遗留断言引用已移除字段 | WS smoke测试 |

---

## PR #10: feat(data): 成员A数据流水线完成

**head**: feature/xingran-taro-workspace @ 0de6e7ea
**CI**: FAILURE (all platforms)
**作者**: xingran-taro

| 文件 | 原始意图 | 处理 | 理由 | 测试 |
|------|---------|------|------|------|
| `scripts/task1_mysql_import.py` | MySQL 全量入库（7 表） | **accept_with_rework** | 接受：读取逻辑、表映射、批次写入。重做：硬编码凭据→环境变量、硬编码路径→CLI args、if_exists="append"→staging+upsert、entity_id→统一格式、sys.stdout替换→移除 | 幂等性测试 |
| `scripts/task5_industry_fill.py` | akshare 行业分类补全 | **accept_with_rework** | 接受：研报优先策略、akshare 补全思路。重做：硬编码路径→CLI args、模块级副作用→main()、网络请求缓存/超时/重试、行业来源标注、名称推断注明 heuristic | 行业覆盖率对账 |
| `scripts/task3_chromadb_import.py` | ChromaDB 研报分块入库 | **accept_with_rework** | 接受：分块逻辑、BGE 嵌入思路。重做：import 时 delete_collection→--rebuild-collection 显式操作、硬编码路径→CLI args、sys.stdout替换→移除、chunk ID→确定性生成、collection 名称→V12 契约 | Chroma 检索测试 |
| `scripts/_read_data.py` | 比赛数据读取辅助 | **accept_with_rework** | 接受：数据探索逻辑。重做：硬编码路径→CLI args、sys.stdout替换→移除 | - |
| `data/fixtures/kangmei.sql` | 康美药业 fixture | **reworked_completely** | mysqldump 含 DROP TABLE + warning + 旧 schema → 重写为 Python loader（`scripts/load_kangmei_fixture.py`），仅数据操作、幂等、安全、使用统一 entity_id | fixture 加载测试 |

---

## PR #11: feat(data): 数据组成员B Phase B 交付

**head**: feature/2659856590-svg-workspace @ c36a8962
**CI**: SUCCESS (all platforms)
**作者**: 2659856590-svg

| 文件 | 原始意图 | 处理 | 理由 | 测试 |
|------|---------|------|------|------|
| `scripts/neo4j_full_import.py` | Neo4j 全量图谱构建 | **accept_with_rework** | 接受：实体对齐、批量 UNWIND、一致行动人检测、验证链。重做：DETACH DELETE 默认→--replace-graph-version 显式、MERGE 覆盖历史→relationship_id 快照、entity_type 误分类→政府机构识别、Normalizer 统一 | 图谱查询测试 |
| `scripts/announcement_sentiment.py` | 29 类公告情绪映射 | **accept_with_rework** | 接受：fcode 映射思路、负面优先策略。重做：29→33 类目标覆盖、未知→unknown（非 neutral）、映射表版本化、启发式规则标注、支持 MySQL 幂等更新 | 情绪分类测试 |
| `docs/RULES_SPEC.md` | 7条财务规则完整规格 | **accept_with_rework** | 接受：详细公式/阈值/适用条件/严重等级。需要一致性审核：与 DATA_CHECKLIST 规则组成对齐、母公司口径声明、康美名称→{company_name} 模板、规则状态标记、机器可读契约 | 规则向量的确定性测试 |
| `docs/任务4_公告情绪映射指令.md` | 任务4指令文档 | **accept** | 开发参考文档，保留 | - |
| `backend/app/infrastructure/graph/neo4j/equity_graph.py` | Wind Code 后缀推断修复 | **accept_with_rework** | 接受：去硬编码 .SH、根据前缀推断交易所。重做：使用统一 normalizer（非独立实现）、移除 fallback .SH、增加 as_of/is_latest/relationship_id | Wind Code 参数化测试、NetworkX一致性 |
