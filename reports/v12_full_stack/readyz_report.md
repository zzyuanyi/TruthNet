# /healthz /readyz 端点报告

## /healthz

- lite profile: `{"status": "healthy", "version": "0.2.0", "profile": "lite"}`
- full profile: `{"status": "healthy", "version": "0.2.0", "profile": "full"}`
- 不依赖任何外部服务

## /readyz — lite profile

```json
{
  "data": {
    "status": "ready",
    "profile": "lite",
    "checks": {
      "sql_backend": {"status": "ok", "backend": "sqlite"},
      "graph_backend": {"status": "ok", "backend": "networkx"},
      "vector_backend": {"status": "ok", "backend": "chroma"},
      "llm_backend": {"status": "ok", "backend": "mock"}
    }
  }
}
```

## /readyz — full profile (无 MySQL/Neo4j)

```json
{
  "data": {
    "status": "not_ready",
    "profile": "full",
    "checks": {
      "mysql": {"status": "not_configured", "reason": "MYSQL_PASSWORD not set"},
      "neo4j": {"status": "not_configured", "reason": "NEO4J_PASSWORD not set"},
      "chroma": {"status": "ok", "persist_dir": "..."},
      "llm": {"status": "mock"}
    }
  },
  "warnings": [
    {"code": "MYSQL_UNAVAILABLE", "message": "mysql: MYSQL_PASSWORD not set", "module": "mysql", "recoverable": true},
    {"code": "NEO4J_UNAVAILABLE", "message": "neo4j: NEO4J_PASSWORD not set", "module": "neo4j", "recoverable": true}
  ]
}
```

## 状态

- /healthz: **passed** ✅
- /readyz lite: **passed** ✅
- /readyz full: **passed** ✅ (正确报告 degraded 状态)
