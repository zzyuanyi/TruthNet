# TruthNet V12 环境复现与经验总结

> 最后更新：2026-07-18
> 适用对象：所有新成员、后端组、全栈验证
> 前置条件：Windows 11 / 10 x64，不需要管理员权限

---

## 一、已验证的完整组件版本矩阵

### 核心环境

| 组件 | 版本 | 安装方式 | 备注 |
|------|------|----------|------|
| Windows | 11 Home China 10.0.26200 | 预装 | x64 |
| Python | **3.11.15** | conda create | 必须 3.11，不要 3.12 |
| conda | 24.9.2 | Miniconda | 环境名固定 `truthnet` |
| pip | 26.1.2 | conda 自带 | |
| Git | 2.54.0 | winget / 官网 | |

### Python 依赖（25 → 26 包）

| 包 | 版本 | 类别 | 踩坑记录 |
|------|------|------|----------|
| fastapi | 0.115.0 | Web | |
| uvicorn | 0.30.6 | Web | |
| websockets | 12.0 | Web | |
| pydantic | 2.9.2 | Schema | V2，不要用 V1 语法 |
| pydantic-settings | 2.5.2 | Config | |
| python-dotenv | 1.0.1 | Config | |
| langgraph | 0.2.55 | Agent | |
| langchain-core | 0.3.29 | Agent | |
| langchain-openai | 0.2.14 | LLM | |
| networkx | 3.3 | Graph (lite) | |
| chromadb | 0.5.23 | Vector | 首次 install 很慢（~400MB 依赖） |
| pandas | 2.2.3 | Data | |
| numpy | 1.26.4 | Data | |
| scikit-learn | 1.5.2 | ML | |
| sqlalchemy | 2.0.35 | ORM | **V12 新增** |
| alembic | 1.13.2 | Migration | **V12 新增** |
| pymysql | 1.1.1 | MySQL Driver | **V12 新增**，纯 Python，Windows 无需编译 |
| cryptography | **49.0.0** | MySQL Auth | **必装！** 见踩坑 #1 |
| neo4j | 5.26.0 | Graph (full) | **V12 新增** |
| structlog | 24.4.0 | Logging | **V12 新增** |
| jsonschema | 4.23.0 | Validation | **V12 新增** |
| pytest | 8.3.3 | Testing | |
| pytest-asyncio | 0.24.0 | Testing | |
| httpx | 0.27.2 | Testing | |
| ruff | 0.6.5 | Lint | |
| pre-commit | 3.8.0 | Git Hooks | |

### 外部服务

| 组件 | 版本 | 端口 | 模式 | 踩坑记录 |
|------|------|:---:|------|----------|
| **JDK** | Temurin 21.0.11 LTS | — | winget 安装 | Neo4j 2025.x 要求 JDK 17+，JDK 21 推荐 |
| **MySQL** | 8.4.9 Community | 3307 | console 模式 | 见踩坑 #2、#3 |
| **Neo4j** | **2025.06.1** Community | 7687/7474 | console 模式 | 见踩坑 #4 |
| **ChromaDB** | 0.5.23 | — | PersistentClient | 无独立服务进程 |

### 前端工具

| 组件 | 版本 | 备注 |
|------|------|------|
| Node.js | v26.1.0 | CI 用 v22 |
| pnpm | 11.9.0 | 前端包管理 |
| React | 18.3.1 | |
| Vite | 6.4.3 | |
| TypeScript | 5.6.3 | |

---

## 二、关键踩坑与解决方案

### 踩坑 #1：MySQL 8.4 连接报错 `cryptography` 缺失

**现象**：
```
'cryptography' package is required for sha256_password or caching_sha2_password auth methods
```

**原因**：MySQL 8.4 默认使用 `caching_sha2_password` 认证插件，PyMySQL 需要 `cryptography` 完成 SHA-256 握手。

**解决**：`requirements.txt` 中必须包含 `cryptography==49.0.0`。最初遗漏了此依赖，已补充。

### 踩坑 #2：MySQL 端口冲突

**现象**：`mysqld` 启动失败或端口被占用。

**原因**：Windows 上 3306 端口可能已被其他 MySQL 实例占用。

**解决**：本项目使用 **3307** 端口（console 模式），数据目录 `E:\project\TruthNet\.local\mysql_data`。不需要管理员权限安装 Windows 服务。

### 踩坑 #3：MySQL 初始化步骤遗漏

**现象**：`mysqld` 启动报错找不到数据目录。

**解决**：首次使用前必须初始化数据目录：
```bash
"/c/Program Files/MySQL/MySQL Server 8.4/bin/mysqld" \
  --initialize-insecure --console \
  --datadir="E:/project/TruthNet/.local/mysql_data"
```

`--initialize-insecure` 创建无密码 root 用户（仅本地开发用）。

### 踩坑 #4：Neo4j 2025.06.0 死锁 Bug

**现象**：数据库随机卡死。

**原因**：官方确认 2025.06.0 存在检查点互斥锁死锁缺陷。

**解决**：**必须使用 2025.06.1+**。2025.06.1 于 2025-07-11 发布，修复了此问题。从 dist.neo4j.org 下载时 curl 可能断连（~160MB），建议用 PowerShell `WebClient` 下载。

### 踩坑 #5：conda 环境未激活

**现象**：`python --version` 显示 3.12.x 而非 3.11.x。

**原因**：当前 shell 使用 base 环境。

**解决**：
```bash
# 每次开发前执行
conda activate truthnet
python --version  # 应显示 3.11.15

# 或者直接用完整路径
E:/anaconda/envs/truthnet/python.exe scripts/doctor.py
```

### 踩坑 #6：WebSocket 测试死循环

**现象**：CI 运行 6 小时后被 GitHub 强制取消。

**原因**：legacy WS 端点和 V12 WS 测试的格式不匹配，`while True` 循环永不退出。

**解决**：WebSocket 测试加入 `max_messages=30` 安全上限，同时兼容 legacy `{type}` 和 V12 `{event_type}` 两种格式。已在 `test_ws_v1_contract.py` 和 `test_websocket_smoke.py` 中修复。

### 踩坑 #7：Pydantic `class Config` 弃用

**现象**：`PydanticDeprecatedSince20` 警告。

**原因**：`class Config` 在 Pydantic V2 中已弃用。

**解决**：改用 `model_config = ConfigDict(arbitrary_types_allowed=True)`。已在 `agents/state.py` 中修复。

### 踩坑 #8：ChromaDB Windows 临时文件锁

**现象**：`tempfile.TemporaryDirectory` + ChromaDB `PersistentClient` 报 `PermissionError`。

**原因**：Windows 上 ChromaDB 的 SQLite/duckdb 文件在 `TemporaryDirectory` 上下文退出时可能未释放。

**解决**：集成测试改用 `tempfile.mkdtemp` + 手动 `shutil.rmtree` 清理。smoke 测试优先用 `EphemeralClient` 或 in-memory 模式。

---

## 三、从零安装完整流程

### Step 1：克隆仓库

```bash
git clone https://github.com/zzyuanyi/TruthNet.git
cd TruthNet
```

### Step 2：创建 conda 环境（3 分钟）

```bash
conda create -n truthnet python=3.11 -y
conda activate truthnet
pip install -r requirements.txt   # 首次约 5-10 分钟（chromadb 很慢）
```

### Step 3：配置 .env

```bash
cp .env.example .env
# 编辑 .env，设置 TRUTHNET_PROFILE=lite（默认）
```

### Step 4：验证 lite profile（无需外部服务）

```bash
python scripts/verify_v12_stack.py
python scripts/verify_full_stack.py --profile lite
python -m pytest backend/tests -q
```

### Step 5（可选）：安装 Full Profile 外部服务

```bash
# JDK 21
winget install EclipseAdoptium.Temurin.21.JDK

# MySQL 8.4
winget install Oracle.MySQL

# 初始化 MySQL 数据目录
mkdir E:\project\TruthNet\.local\mysql_data
"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld" \
  --initialize-insecure --console \
  --datadir="E:\project\TruthNet\.local\mysql_data"

# 启动 MySQL（端口 3307）
"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld" \
  --console --datadir="E:\project\TruthNet\.local\mysql_data" \
  --port=3307 --bind-address=127.0.0.1 &

# 创建数据库和用户
mysql -u root --host 127.0.0.1 --port 3307 -e "
CREATE DATABASE truthnet CHARACTER SET utf8mb4;
CREATE USER 'truthnet'@'127.0.0.1' IDENTIFIED BY 'truthnet_v12_dev';
GRANT ALL ON truthnet.* TO 'truthnet'@'127.0.0.1';
FLUSH PRIVILEGES;
"

# Neo4j 2025.06.1（注意：必须 .1+，不要 .0）
# 下载：https://neo4j.com/download-center/#community
# 解压到 E:\project\TruthNet\.local\neo4j\

# 启动 Neo4j
$env:JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot"
$env:NEO4J_HOME="E:\project\TruthNet\.local\neo4j\neo4j-community-2025.06.1"
& "$env:NEO4J_HOME\bin\neo4j.bat" console

# 首次连接 http://127.0.0.1:7474 修改密码（neo4j → truthnet_v12_dev）

# 配置 .env
TRUTHNET_PROFILE=full
SQL_BACKEND=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_DATABASE=truthnet
MYSQL_USER=truthnet
MYSQL_PASSWORD=truthnet_v12_dev
GRAPH_BACKEND=neo4j
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=truthnet_v12_dev
```

### Step 6：验证 full profile

```bash
python scripts/verify_full_stack.py --profile full --check-external --write-smoke --cleanup
# 预期: 25/25 PASSED

$env:TRUTHNET_RUN_EXTERNAL_TESTS="1"
python -m pytest backend/tests/integration -v -m "integration and external"
# 预期: 8/8 PASSED
```

---

## 四、常用验证命令速查

```bash
# 环境相关
conda activate truthnet                                  # 激活环境
python --version                                         # 必须 3.11.x
pip check                                                # 依赖冲突检查
python scripts/doctor.py                                 # 环境全检

# 代码质量
ruff check . && ruff format --check .                    # 代码检查
pre-commit run --all-files                               # Git hooks

# 测试
python -m pytest backend/tests -q                        # 默认测试（~113 个）
python -m pytest backend/tests/contract -q               # 契约测试
python -m pytest backend/tests/unit -q                   # 单元测试

# V12 验证
python scripts/verify_v12_stack.py                       # 技术栈验证
python scripts/verify_full_stack.py --profile lite       # Lite 验证
python scripts/verify_full_stack.py --profile full \
  --check-external --write-smoke --cleanup               # Full 验证

# 外部服务集成测试（需服务运行中）
$env:TRUTHNET_RUN_EXTERNAL_TESTS="1"
python -m pytest backend/tests/integration -v -m "integration and external"

# 服务管理（PowerShell）
powershell -File scripts/services/start_full_stack_dev.ps1
powershell -File scripts/services/check_full_stack_ports.ps1
powershell -File scripts/services/stop_full_stack_dev.ps1
```

---

## 五、CI 注意事项

1. **首次 CI 可能很慢**：chromadb 的 onnxruntime 依赖约 400MB，三平台同时下载可能导致超时。后续 GitHub Actions 有缓存会快很多。
2. **WebSocket 测试必须在 30 条消息内退出**：我们已在测试中加入 `max_messages=30` 限制。
3. **External 测试不默认运行**：需要 `TRUTHNET_RUN_EXTERNAL_TESTS=1` 显式启用。
4. **Node.js 版本**：CI 使用 Node.js v22，本地可能用 v26，`pnpm-lock.yaml` 确保一致性。

---

## 六、版本变更记录

| 日期 | 变更 | 原因 |
|------|------|------|
| 2026-07-17 | requirements.txt 19→25 包 | V12 新增 SQLAlchemy/Alembic/Neo4j/PyMySQL/structlog/jsonschema |
| 2026-07-17 | MySQL 8.4.9 安装 | winget，console 模式，端口 3307 |
| 2026-07-17 | Neo4j 2025.06.0 安装 | ZIP，console 模式 |
| 2026-07-18 | **Neo4j 2025.06.0 → 2025.06.1** | 修复检查点互斥锁死锁 bug |
| 2026-07-18 | **cryptography==49.0.0 加入 requirements.txt** | MySQL 8.4 caching_sha2_password 认证必需 |
| 2026-07-18 | WebSocket 测试死循环修复 | CI 6 小时超时 |
| 2026-07-18 | Pydantic ConfigDict 迁移 | 弃用警告消除 |
