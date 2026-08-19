# Task A 阶段 Checkpoint — Web Search 真正调通（2026-08-19）

> 组长三项要求 Task A 完成 checkpoint。BASE_SHA=`21d8c6ca1c83fd6c639dec64f42c8baca282ae1c`（main PR #47+#48）。

## A1 官方 Bocha 契约核验

**联网核验结论（多来源一致，2026-08-19）**：

- `POST https://api.bocha.cn/v1/web-search`（或 `https://api.bochaai.com/v1/web-search`，两者均可用）
- 请求头：`Authorization: Bearer {KEY}`、`Content-Type: application/json`
- 请求体：`{"query", "freshness": "noLimit", "summary": true, "count": 1-50}`
- **响应根结构**：`{"code": 200, "log_id", "msg", "data"}`
- **结果位于 `data.webPages.value[]`**（当前代码解析路径与官方契约一致）
- webPages.value 字段：`name/url/displayUrl/snippet/summary/siteName/siteIcon/datePublished/dateLastCrawled`
- 常见错误码：401 Key 无效 / 403 余额不足 / 429 请求频繁 / 500 服务器错误

**结论**：任务 Prompt 中"当前真实契约是 `payload.webPages`（顶层）"的假设**未被证实**。官方契约是 `data.webPages`，当前代码解析正确。但为兼容历史/镜像变体，已新增顶层 `webPages` 兜底解析（不改现有 `data.webPages` 优先路径）。

## A2 上市日期事实提取（核心修复）

`web_search_fact_fill.py` 重写：

- **禁止** `SearchResult.published_at` 作为 listing_date（网页发布日期 ≠ 公司上市事实）——只读 snippet/title；
- 日期必须伴随「上市/挂牌」语义关键字（±16 字符上下文窗口），且无「发布于/成立于/公告日期/更新时间/年报披露」等反例语义；
- 多结果上市日期互异 → **fail-closed 返回 None**，不猜；
- 同一文本"成立日期 1997-01-01，上市日期 2001-03-19"→ 上下文消歧只取 `2001-03-19`。

负例已测：`文章发布于 2026-08-18`、`公司成立于 1997-01-01`、`成立日期 1997-01-01`、`公告日期 2024-03-10`、`更新时间 2025-06-01`、`年报披露日期 2024-04-30` 全部拒绝。

## A3 联网 query 改进

三触发点 query 均带 wind_code + 交易所消歧：

- 问答 `_web_search_fill_company_fact`：`"{sec_name} {wind_code} {label} 交易所"`
- 画像 `_web_search_fill_profile_listing_date`：`"{sec_name} {wind_code} 上市日期 交易所"`
- 舆情 `_web_search_company_news`：`"{sec_name} {wind_code} 公告 舆情 最新"`

「库内有数据不搜」保持：触发 gate `not value and fact_key in _WEB_SEARCHABLE_FACTS`（答案节点）、`profile.listing_date is None`（画像）、`no_announcement and not announcement_error`（舆情）。

## A4 缓存语义

`web_search_service.py`：

- 非空结果进程内常驻；
- **空结果短 TTL（30s）**：一次 timeout/5xx/网络中断返回的 `[]` 不再永久污染进程缓存，过期后同 query 可重新联网；
- 空结果 TTL 窗口内仍命中（同 turn 防重复空搜）。

## A5 HTTP 失败可诊断

`bocha/provider.py`：

- 区分并统计：`http_401_403`（key/auth）、`http_429`（provider 限流，透出 Retry-After）、`http_5xx`（provider server）、`timeout`、`connection_error`、`empty_real_result`（HTTP 200 真实空）、`parse_empty`、`not_observable`；
- `report_stats()` 暴露统计；日志不含完整 API Key；
- 调用方保持 fail-closed → `[]`，但报告可区分"API 请求失败"与"真实搜索无结果"。

## A7 真实 smoke

本地 `WEB_SEARCH_API_KEY` **未配置** → **BLOCKED_BY_MISSING_LOCAL_API_KEY**。

- 已交付 `scripts/web_search_real_smoke.py`：配置 key 后可直接运行（固定 康美药业/宁德时代/贵州茅台 三查询，记录 query/HTTP outcome/result_count/top domain/snippet 非空/elapsed_ms/parse success）；
- 已实测无 key 时正确输出 BLOCKED，未发起任何网络请求，**未伪造真实联网结果**。

## A8 三触发点 E2E（truthnet_test，mock 后端）

`backend/tests/unit/test_web_search_phaseE_e2e.py`（5 passed）：

| Case | 场景 | 断言 | 结果 |
|---|---|---|---|
| A | 库内 listing_date 为空 → 画像联网 | profile.listing_date=2001-03-19 + WEB_SEARCH_SOURCE warning + 恰好 1 次联网 | ✓ |
| B | 库内已有 listing_date | Web Search 调用数=0 | ✓ |
| C | 无公告 → 联网补 evidence | EvidenceRef source_type=web_search、source_uri/source_excerpt/retrieved_at 存在；module_status 仍 NO_ANNOUNCEMENT_DATA | ✓ |
| — | Section 6 安全边界 | 实体歧义未确认 → company_disambiguation，web_search 零调用 | ✓ |
| — | A9 off 回归 | 零 Provider 创建、零网络、原降级保持 | ✓ |

## A9 off 回归

`WEB_SEARCH_BACKEND=off` → 零 Provider 创建、零网络请求、原降级行为保持（E2E + 单测双重覆盖）。

## 测试证据

```text
web_search_provider    +fact_fill +service   65 passed
web_search_phaseE_e2e                        5 passed
web_search + semantic  (149)                149 passed
ruff check                                    通过
ruff format --check                           通过
```

## 完成判据核对

- [x] 官方 `data.webPages.value` 可解析；顶层 `webPages` 兼容
- [x] legacy `data.webPages` 仍兼容
- [ ] 真实 key 存在时返回非空真实结果 → **BLOCKED_BY_MISSING_LOCAL_API_KEY**（需本地配置 key 后跑 `web_search_real_smoke.py`）
- [x] published_at 不再污染 listing_date
- [x] 非上市日期不误识别（负例测试）
- [x] 冲突日期 fail-closed
- [x] 库内有数据不搜（Case B + 答案节点单测）
- [x] 库内无数据才搜（Case A）
- [x] 来源完整（source_type/source_uri/source_excerpt/retrieved_at）
- [x] off 零网络（A9）
- [x] timeout/429/异常不击穿业务流程（fail-closed + 分类统计）
- [x] 密钥无泄露

## 未完成 / 阻塞

- `REAL_SMOKE`：`ENVIRONMENT_BLOCKED`（本地无 Bocha key）。代码层契约修复、mock/fixture 测试、real-smoke runner 均已交付；配置 `WEB_SEARCH_BACKEND=bocha` + `WEB_SEARCH_API_KEY=<key>` 后运行 `scripts/web_search_real_smoke.py` 即可完成最后一步真实验证。
