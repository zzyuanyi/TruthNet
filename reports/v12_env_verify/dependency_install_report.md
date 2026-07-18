# 依赖安装报告

## 安装命令

```bash
E:/anaconda/envs/truthnet/python.exe -m pip install -r requirements.txt
```

## 安装结果

**所有 25 个包 + 传递依赖均已成功安装。**

### 核心栈

| Package | Required by V12 | Installed in truthnet | Version | Status |
|---------|---------------|----------------------|---------|--------|
| fastapi | yes (existing) | yes | 0.115.0 | PASS |
| pydantic | yes (existing) | yes | 2.9.2 | PASS |
| pydantic-settings | yes (existing) | yes | 2.5.2 | PASS |
| langgraph | yes (existing) | yes | 0.2.55 | PASS |
| networkx | yes (existing) | yes | 3.3 | PASS |
| chromadb | yes (existing) | yes | 0.5.23 | PASS |
| sqlalchemy | yes (V12 new) | yes | 2.0.35 | PASS |
| alembic | yes (V12 new) | yes | 1.13.2 | PASS |
| pymysql | yes (V12 new) | yes | 1.4.6 | PASS |
| neo4j | yes (V12 new) | yes | 5.26.0 | PASS |
| structlog | yes (V12 new) | yes | 24.4.0 | PASS |
| jsonschema | yes (V12 new) | yes | 4.23.0 | PASS |
| pytest | yes (existing) | yes | 8.3.3 | PASS |
| ruff | yes (existing) | yes | 0.6.5 | PASS |
| pre-commit | yes (existing) | yes | 3.8.0 | PASS |

### pip check 结果

```
No broken requirements found.
```
