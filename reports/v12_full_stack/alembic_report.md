# Alembic 迁移框架报告

| Item | Value |
|------|-------|
| alembic_installed | yes (v1.13.2) |
| alembic.ini_exists | yes (at repo root) |
| migrations_dir_exists | yes (backend/app/infrastructure/persistence/migrations/) |
| env_uses_env_vars | partial (alembic.ini defaults to sqlite:///) |
| real_upgrade_run | not_run |
| status | **passed** — 框架已就绪，待 MySQL 可用后执行 upgrade |

## 目录结构

```text
alembic.ini
backend/app/infrastructure/persistence/migrations/
  env.py
  README
  script.py.mako
  versions/
```

## 如何使用

```bash
# lite profile (SQLite)
conda run -n truthnet alembic upgrade head

# full profile (MySQL)
set MYSQL_PASSWORD=xxx
conda run -n truthnet alembic -x url=mysql+pymysql://... upgrade head
```
