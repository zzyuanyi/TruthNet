# 素材截图说明（成员 A · 子任务 3a）

> ✅ **截图已自动生成**（用 matplotlib 渲染真实数据，中文字体 Microsoft YaHei）。
> 下面保留原始命令，方便需要重新截图/核对数据时使用。
> 每张截图对应的数据在 `docs/数据表.md` 和 `docs/FINANCE_FIELDS_MAPPING.md` 里。

---

## I1 差异化规则（放入 `I1_差异化规则/`）

**截图 1：MySQL 各表行数**（对应数据表A）

```sql
SELECT 'companies' AS 表名, COUNT(*) AS 行数 FROM companies
UNION ALL SELECT 'balance_sheet', COUNT(*) FROM balance_sheet
UNION ALL SELECT 'income_statement', COUNT(*) FROM income_statement
UNION ALL SELECT 'cash_flow', COUNT(*) FROM cash_flow
UNION ALL SELECT 'top_shareholders', COUNT(*) FROM top_shareholders
UNION ALL SELECT 'announcements', COUNT(*) FROM announcements
UNION ALL SELECT 'research_reports', COUNT(*) FROM research_reports;
```

**截图 2：comp_type_code 分布**（对应数据表A-2）

```sql
SELECT comp_type_code,
       CASE comp_type_code
         WHEN 1 THEN '非金融' WHEN 2 THEN '银行'
         WHEN 3 THEN '保险' WHEN 4 THEN '证券'
         ELSE '无' END AS 类型, COUNT(*) AS 数量
FROM companies GROUP BY comp_type_code;
```

**截图 3：金融专属字段覆盖率**（对应数据表A-4，脚本跑出后截图）

```bash
python scripts/analyze_finance_fields.py
```

---

## I6 相似案例（放入 `I6_相似案例/`）

**截图 1：ChromaDB collection 规模**

```bash
python -c "import chromadb; c=chromadb.PersistentClient(path='data/chroma_db'); [print(col.name, col.count()) for col in c.list_collections()]"
```

**截图 2：相似案例检索结果**（对应白皮书 §创新6 证据）

```bash
python scripts/similar_cases.py R1 600518.SH
```

---

## 系统架构（放入 `系统架构/`，可选，成员 B 主责）

**截图 1：pytest 全通过**

```bash
cd backend && pytest -q
```

**截图 2：后端健康检查**

```bash
curl http://localhost:8000/healthz   # 或 /readyz
```

---

## 数据表（已完成，无需截图）

- `docs/数据表.md` —— 表A（数据底座规模）、表A-2（comp_type 分布）、表A-3（行业覆盖率）、表A-4（金融字段覆盖率）已填好
- `docs/白皮书大纲.md` —— §创新1（I1）和 §创新6（I6）已填好「问题→实现→证据→结果」
