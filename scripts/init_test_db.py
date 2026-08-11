"""初始化 MySQL 测试库（truthnet_test）— v3.1 + v3.4 安全边界.

用途：创建测试库 + 专用测试账号（仅 truthnet_test.* 权限，对演示库
truthnet.* 无任何权限）。幂等：IF NOT EXISTS / IF NOT EXIST。

用法（凭据经环境变量传入，不落盘不提交）：
    MYSQL_ROOT_PASSWORD=<root密码> python scripts/init_test_db.py \
        --confirm truthnet_test --test-password <测试账号密码> \
        [--test-user truthnet_test]

安全边界（v3.4）：
- 用户名/库名/主机名均经白名单校验（^[A-Za-z0-9_]+$）后再拼接
  （MySQL GRANT 不支持参数化，白名单后插值安全）；
- 已有账号处理：ALTER USER 更新密码 → REVOKE 全部旧授权
  （含 GRANT OPTION）→ 仅授予测试库权限；
- 拒绝测试用户名 == 演示用户名；
- --confirm <目标库名> 必须显式输入，降低误操作风险；
- 验证：测试凭据连测试库 OK；连演示库必须失败（1044 权限拒绝）。
"""

import argparse
import os
import re
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_REPO_ROOT / ".env")


def get_env(key: str, default: str = "") -> str:
    """读环境变量（.env 已加载，优先级：进程环境 > .env）。"""
    return os.environ.get(key) or default


_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
_FORBIDDEN_DB_NAMES = {
    "truthnet",
    "mysql",
    "information_schema",
    "performance_schema",
    "sys",
}


def validate_ident(name: str, kind: str) -> None:
    """标识符（库名/用户名/主机名）白名单校验（v3.4）。"""
    if not _SAFE_NAME_RE.match(name):
        raise SystemExit(
            f"[init-test-db] {kind} {name!r} 含不安全字符，仅允许字母/数字/下划线"
        )


def validate_db_name(db: str) -> None:
    """与 conftest 守卫同规则的库名校验（建库前双重防线）。"""
    if db.lower() in {n.lower() for n in _FORBIDDEN_DB_NAMES}:
        raise SystemExit(f"[init-test-db] 库名 {db!r} 在拒绝名单中，禁止创建")
    validate_ident(db, "库名")
    demo_db = get_env("MYSQL_DATABASE", "truthnet")
    if db.lower() == demo_db.lower():
        raise SystemExit(f"[init-test-db] 测试库 {db!r} 不得等于演示库 {demo_db!r}")


def _account(user: str, host: str) -> str:
    """白名单验证后的 'user'@'host'（v3.5：GRANT/REVOKE 显式插值。

    MySQL 不支持 GRANT 参数化——两段标识符经白名单校验后拼接，
    密码仍走参数化。
    """
    return f"'{user}'@'{host}'"


def _run_smoke(root_conn, test_db: str, host: str) -> int:
    """真实 MySQL smoke（v3.5）：临时账号 → 授权测试库 → 确认演示库 1044
    → 最后定向清理（DROP USER）。不动正式账号。
    """
    import uuid

    smoke_user = f"smoke_{uuid.uuid4().hex[:8]}"
    smoke_pwd = "smoke_pwd_1a2b"
    account = _account(smoke_user, host)
    try:
        with root_conn.cursor() as cur:
            cur.execute(
                f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY %s", (smoke_pwd,)
            )
            cur.execute(f"GRANT ALL PRIVILEGES ON `{test_db}`.* TO {account}")
        root_conn.commit()
        # 正向：临时账号连测试库 OK
        conn = pymysql.connect(
            host=get_env("MYSQL_HOST", "127.0.0.1"),
            port=int(get_env("MYSQL_PORT", "3306")),
            user=smoke_user,
            password=smoke_pwd,
            database=test_db,
            connect_timeout=5,
        )
        conn.close()
        # 反向：连演示库必须 1044
        try:
            pymysql.connect(
                host=get_env("MYSQL_HOST", "127.0.0.1"),
                port=int(get_env("MYSQL_PORT", "3306")),
                user=smoke_user,
                password=smoke_pwd,
                database=get_env("MYSQL_DATABASE", "truthnet"),
                connect_timeout=5,
            )
            raise SystemExit("[smoke] ❌ 临时账号可访问演示库（隔离失效，未清理?）")
        except pymysql.err.OperationalError as exc:
            if not exc.args or exc.args[0] != 1044:
                raise SystemExit(
                    f"[smoke] ❌ 预期 1044 Access denied，实际 {exc.args}"
                ) from None
        print(f"[smoke] ✅ 正反向验证通过：{smoke_user} 仅 {test_db}.* 权限")
        return 0
    finally:
        with root_conn.cursor() as cur:
            cur.execute(f"DROP USER IF EXISTS {account}")
        root_conn.commit()
        print(f"[smoke] 已定向清理临时账号 {account}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-db", default="truthnet_test")
    parser.add_argument("--test-user", default="truthnet_test")
    parser.add_argument("--test-password", default="")
    parser.add_argument(
        "--confirm",
        default="",
        help="必须显式输入目标测试库名（如 --confirm truthnet_test），防误操作",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="真实 MySQL 冒烟：临时账号→授权测试库→确认演示库 1044→定向清理",
    )
    args = parser.parse_args()

    validate_db_name(args.test_db)
    if not args.test_password:
        raise SystemExit("[init-test-db] 必须通过 --test-password 指定测试账号密码")
    if not args.confirm or args.confirm != args.test_db:
        raise SystemExit(
            f"[init-test-db] 必须显式 --confirm {args.test_db}（建库类命令需确认）"
        )
    validate_ident(args.test_user, "用户名")
    demo_user = get_env("MYSQL_USER", "truthnet")
    if args.test_user == demo_user:
        raise SystemExit(
            f"[init-test-db] 测试用户名 {args.test_user!r} 不得等于演示用户名 {demo_user!r}"
        )

    root_pwd = get_env("MYSQL_ROOT_PASSWORD", "")
    if not root_pwd:
        raise SystemExit(
            "[init-test-db] 缺少 MYSQL_ROOT_PASSWORD 环境变量（root 凭据只走环境变量，不落盘）"
        )

    conn = pymysql.connect(
        host=get_env("MYSQL_HOST", "127.0.0.1"),
        port=int(get_env("MYSQL_PORT", "3306")),
        user="root",
        password=root_pwd,
        connect_timeout=10,
    )
    if args.smoke:
        try:
            return _run_smoke(conn, args.test_db, "127.0.0.1")
        finally:
            conn.close()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE DATABASE IF NOT EXISTS `%s` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                % args.test_db
            )
            # 测试账号：127.0.0.1 与 localhost 双 host
            # v3.5：账号以白名单验证后的 'user'@'host' 显式插值（GRANT 不支持参数化）
            for host in ("127.0.0.1", "localhost"):
                account = _account(args.test_user, host)
                cur.execute(
                    f"CREATE USER IF NOT EXISTS {account} IDENTIFIED BY %s",
                    (args.test_password,),
                )
                # 已有账号：更新密码
                cur.execute(
                    f"ALTER USER {account} IDENTIFIED BY %s",
                    (args.test_password,),
                )
                # 撤销该账号的全部旧授权（含 GRANT OPTION），再仅授测试库
                cur.execute(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM {account}")
                cur.execute(f"GRANT ALL PRIVILEGES ON `{args.test_db}`.* TO {account}")
            cur.execute("FLUSH PRIVILEGES")
        conn.commit()
    finally:
        conn.close()

    # 二次确认：用测试账号连接并 SELECT DATABASE()
    verify = pymysql.connect(
        host=get_env("MYSQL_HOST", "127.0.0.1"),
        port=int(get_env("MYSQL_PORT", "3306")),
        user=args.test_user,
        password=args.test_password,
        database=args.test_db,
        connect_timeout=10,
    )
    try:
        with verify.cursor() as cur:
            cur.execute("SELECT DATABASE()")
            actual = cur.fetchone()[0]
            if str(actual or "").lower() != args.test_db.lower():
                raise SystemExit(
                    f"[init-test-db] 验证失败：实际 {actual!r} != 期望 {args.test_db!r}"
                )
    finally:
        verify.close()

    # 反向确认：测试账号对演示库必须无权限（1044 权限拒绝为预期）
    deny_ok = False
    try:
        pymysql.connect(
            host=get_env("MYSQL_HOST", "127.0.0.1"),
            port=int(get_env("MYSQL_PORT", "3306")),
            user=args.test_user,
            password=args.test_password,
            database=get_env("MYSQL_DATABASE", "truthnet"),
            connect_timeout=5,
        )
    except pymysql.err.OperationalError as exc:
        deny_ok = exc.args[0] == 1044 if exc.args else False
    except Exception:  # noqa: BLE001 — 其他错误无法证明隔离，视为失败
        deny_ok = False
    if not deny_ok:
        raise SystemExit(
            "[init-test-db] 测试账号对演示库的隔离验证失败"
            "（预期 1044 Access denied，实际可访问或无法证明隔离）"
        )

    print(
        f"[init-test-db] OK: 测试库 {args.test_db} 就绪，测试账号 {args.test_user} "
        f"仅 {args.test_db}.* 权限（旧授权已全量撤销），演示库访问已确认拒绝"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
