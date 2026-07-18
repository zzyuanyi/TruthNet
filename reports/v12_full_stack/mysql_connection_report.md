# MySQL 连接验证报告

| Item | Value |
|------|-------|
| driver | PyMySQL v1.4.6 |
| sqlalchemy_url_sanitized | mysql+pymysql://truthnet:***@localhost:3306/truthnet |
| tcp_reachable | not_run (port 3306 not open) |
| auth | not_run (MYSQL_PASSWORD not configured) |
| select_1 | not_run |
| write_smoke | not_run |
| cleanup | not_run |
| status | **not_run** — MySQL 未安装在本机 |

## 如何配置

1. 安装 MySQL 8.0
2. 编辑 `.env`，设置 MYSQL_PASSWORD
3. 运行: `python scripts/verify_full_stack.py --profile full --check-external`
