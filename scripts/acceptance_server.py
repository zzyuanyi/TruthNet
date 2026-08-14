#!/usr/bin/env python
"""语义/官方验收专用服务启动器（可复用验收工具，非业务代码）。

背景（2026-08-14 验收事故）：临时启动器曾在导入 settings 之后才注入
MYSQL_TEST_* 环境变量，pydantic 缓存实例仍指向演示库 truthnet，导致
验收请求误写演示库。本脚本固化正确顺序，杜绝同类配置顺序错误：

  1. 先从 .env 解析 MYSQL_TEST_USER/PASSWORD/DATABASE 并写入 os.environ
     （在导入 app.core.config 之前完成——这是与演示库隔离的关键顺序）；
  2. 再导入 settings，断言 MYSQL_DATABASE == MYSQL_TEST_DATABASE；
  3. 启动前守卫：真实连接执行 SELECT DATABASE() 必须等于 truthnet_test；
  4. 可选启动后双库探针：用 .env 中的演示凭据与测试凭据分别连接两个库，
     计数指定会话前缀的 conversation_sessions/conversation_turns，
     确认只有测试库被服务写入（默认前缀 semantic_final_%）。

用法（在代码仓库根目录执行，PYTHONPATH=backend）:
    python scripts/acceptance_server.py --port 8001
    python scripts/acceptance_server.py --port 8001 --probe-prefix semantic_final_%

只读验收配套：本脚本不修改 .env、不改业务代码、不 commit。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_REPO_ROOT), str(_REPO_ROOT / "backend")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_ENV_FILE = _REPO_ROOT / ".env"


def load_env_credentials(
    env_file: Path | None = None,
) -> dict[str, dict[str, str]]:
    """解析 .env 的演示/测试两组 MySQL 凭据（不打印任何密码）。

    返回 {"demo": {user/password/database}, "test": {...}}；
    值支持引号包裹；'#' 起视为注释截断。
    """
    path = env_file or _ENV_FILE
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


def apply_test_env_overrides(env_file: Path | None = None) -> dict[str, str]:
    """在导入 app.core.config 之前调用：注入测试三件套环境变量。"""
    creds = load_env_credentials(env_file)
    test = creds["test"]
    for field in ("user", "password", "database"):
        if not test.get(field):
            raise RuntimeError(f".env 缺少 MYSQL_TEST_{field.upper()}")
        os.environ[f"MYSQL_{field.upper()}"] = test[field]
    return test


def verify_selected_database(actual: str, expected: str) -> None:
    """纯守卫函数：SELECT DATABASE() 结果必须等于目标测试库。"""
    if str(actual or "").lower() != str(expected or "").lower():
        raise AssertionError(
            f"启动守卫失败：SELECT DATABASE()={actual!r}，期望 {expected!r}"
        )


def probe_dual_databases(
    *, demo: dict[str, str], test: dict[str, str], prefix: str
) -> dict[str, int]:
    """双库探针：演示库与测试库各自计数会话前缀残留。"""
    from sqlalchemy import URL, create_engine, text

    counts: dict[str, int] = {}
    for label, creds in (("demo", demo), ("test", test)):
        url = URL.create(
            "mysql+pymysql",
            username=creds["user"],
            password=creds["password"],
            host=os.environ.get("MYSQL_HOST", "localhost"),
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            database=creds["database"],
        )
        engine = create_engine(url)
        try:
            with engine.connect() as conn:
                counts[f"{label}_sessions"] = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM conversation_sessions "
                        "WHERE session_id LIKE :p"
                    ),
                    {"p": prefix},
                ).scalar()
                counts[f"{label}_turns"] = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM conversation_turns "
                        "WHERE session_id LIKE :p"
                    ),
                    {"p": prefix},
                ).scalar()
        finally:
            engine.dispose()
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--probe-prefix", default="semantic_final_%")
    ap.add_argument("--skip-probe", action="store_true")
    args = ap.parse_args()

    # 步骤 1：先注入测试三件套（关键顺序：必须在导入 settings 之前）
    test_overrides = apply_test_env_overrides()
    demo_creds = load_env_credentials()["demo"]
    print(
        f"[acceptance-server] 已注入测试库环境变量（database={test_overrides['database']}）"
    )

    # 步骤 2：此时才导入 settings（pydantic 从环境变量初始化测试库身份）
    from app.core.config import settings

    assert settings.MYSQL_DATABASE == settings.MYSQL_TEST_DATABASE, (
        f"配置顺序错误：MYSQL_DATABASE={settings.MYSQL_DATABASE!r} "
        f"!= 测试库 {settings.MYSQL_TEST_DATABASE!r}"
    )

    # 步骤 3：启动前 SELECT DATABASE() 守卫
    from sqlalchemy import URL, create_engine, text

    url = URL.create(
        "mysql+pymysql",
        username=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        host=settings.MYSQL_HOST,
        port=settings.MYSQL_PORT,
        database=settings.MYSQL_DATABASE,
    )
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            actual = conn.execute(text("SELECT DATABASE()")).scalar()
    finally:
        engine.dispose()
    verify_selected_database(str(actual), settings.MYSQL_DATABASE)
    print(f"[acceptance-server] 启动守卫通过：服务将连接 {actual}（测试库）✓")

    # 步骤 4：可选双库探针（确认演示库未被本服务写入）
    if not args.skip_probe:
        counts = probe_dual_databases(
            demo=demo_creds, test=test_overrides, prefix=args.probe_prefix
        )
        print(f"[acceptance-server] 双库探针（prefix={args.probe_prefix}）: {counts}")

    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
