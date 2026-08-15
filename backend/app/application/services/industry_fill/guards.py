"""数据库守卫与凭据注入（档案 v1.1 §4/§7.1，沿用 acceptance_server.py 模式）。

关键顺序：在导入 app.core.config 之前把目标库三件套写入 os.environ，
再导入 settings 并断言 MYSQL_DATABASE == 目标库，最后真实连接执行
SELECT DATABASE() 守卫。任何一步失败立即退出（fail-closed）。
"""

from __future__ import annotations

import os
import re
from pathlib import Path


def load_env_credentials(
    env_file: Path | None = None,
) -> dict[str, dict[str, str]]:
    """解析 .env 的演示/测试两组 MySQL 凭据（不打印任何密码）。

    与 scripts/acceptance_server.py:load_env_credentials 同构。
    """
    path = env_file or Path(".env")
    out: dict[str, dict[str, str]] = {"demo": {}, "test": {}}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = re.match(r"^(MYSQL(?:_TEST)?_(USER|PASSWORD|DATABASE))\s*=\s*(.*)$", line)
        if not m:
            continue
        key = m.group(1)
        value = m.group(3).strip().strip('"').strip("'")
        if "#" in value:
            value = value.split("#", 1)[0].strip()
        group = "test" if key.startswith("MYSQL_TEST_") else "demo"
        out[group][m.group(2).lower()] = value
    return out


def resolve_database_env(
    database: str, env_file: Path | None = None
) -> tuple[str, str, str]:
    """按 --database 解析目标三件套并注入 os.environ（导入 settings 前调用）。

    返回 (user, password, database)。仅允许 .env 中声明的演示库/测试库，
    其他库名 fail-closed。
    """
    creds = load_env_credentials(env_file)
    demo = creds["demo"]
    test = creds["test"]
    if database == test.get("database"):
        triple = test
    elif database == demo.get("database"):
        triple = demo
    else:
        raise RuntimeError(
            f"目标库 {database!r} 不在 .env 允许清单"
            f"（demo={demo.get('database')!r}, test={test.get('database')!r}）"
        )
    for field in ("user", "password", "database"):
        if not triple.get(field):
            raise RuntimeError(f".env 缺少 MYSQL_{field.upper()}（目标库 {database}）")
        os.environ[f"MYSQL_{field.upper()}"] = triple[field]
    return triple["user"], triple["password"], triple["database"]


def verify_selected_database(actual: str, expected: str) -> None:
    """SELECT DATABASE() 必须等于目标库，否则抛错（档案 §7.1）。"""
    if str(actual or "").lower() != str(expected or "").lower():
        raise AssertionError(
            f"数据库守卫失败：SELECT DATABASE()={actual!r}，期望 {expected!r}"
        )


def masked_profile(user: str, host: str, port: int, database: str) -> str:
    """脱敏 profile：backend/user/host/port/database（不含密码）。"""
    return f"{user}@{host}:{port}/{database}"
