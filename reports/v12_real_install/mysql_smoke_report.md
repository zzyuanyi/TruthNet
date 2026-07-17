# MySQL Smoke 报告

| Item | Value |
|------|-------|
| driver | PyMySQL v1.4.6 |
| sqlalchemy_url_sanitized | mysql+pymysql://truthnet:***@127.0.0.1:3307/truthnet |
| tcp_reachable | yes |
| auth | passed |
| select_1 | passed |
| write_smoke | passed (truthnet_smoke_test table, smoke_key='v12_install_full_stack') |
| cleanup | passed (smoke row deleted) |
| status | **passed** |

## verify_full_stack.py output

```
[PASS] | PyMySQL driver import  — v1.4.6
[PASS] | SQLAlchemy import  — OK
[PASS] | MySQL TCP reachable  — 127.0.0.1:3307
[PASS] | MySQL SELECT 1  — OK
[PASS] | MySQL current database  — truthnet
[PASS] | MySQL write smoke  — insert+read OK
[PASS] | MySQL cleanup  — smoke data deleted
```

## External Integration Tests

```
test_pymysql_import PASSED
test_sqlalchemy_import PASSED
test_mysql_connection_select_1 PASSED
test_mysql_write_smoke PASSED
```
