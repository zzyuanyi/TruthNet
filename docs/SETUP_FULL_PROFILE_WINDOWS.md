# TruthNet V12 Full Profile Windows 部署手册

> 适用于需要 MySQL + Neo4j + ChromaDB persistent 的完整演示环境。
> `<REPO_ROOT>` 替换为实际仓库路径，例如 `C:\Users\<name>\TruthNet`。
> 以下项目命令均从仓库根目录执行。

## 1. 前置条件

- Windows 11 / 10 x64
- 不需要管理员权限（所有服务以 console 模式运行）

## 2. 安装 JDK 21

```powershell
winget install EclipseAdoptium.Temurin.21.JDK
```

## 3. 安装 MySQL 8.4

```powershell
winget install Oracle.MySQL
```

初始化并启动（console 模式）：

```powershell
mkdir <REPO_ROOT>\.local\mysql_data
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" --initialize-insecure --console --datadir="<REPO_ROOT>\.local\mysql_data"
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" --console --datadir="<REPO_ROOT>\.local\mysql_data" --port=3307 --bind-address=127.0.0.1
```

创建数据库和用户：

```sql
CREATE DATABASE truthnet CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'truthnet'@'127.0.0.1' IDENTIFIED BY '<your-password>';
GRANT ALL PRIVILEGES ON truthnet.* TO 'truthnet'@'127.0.0.1';
FLUSH PRIVILEGES;
```

## 4. 安装 Neo4j

下载 ZIP 并解压：

```powershell
mkdir <REPO_ROOT>\.local\neo4j
# 下载 https://neo4j.com/download-center/#community
# 解压到 .local\neo4j\
```

启动（console 模式）：

```powershell
$env:JAVA_HOME="C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot"
$env:NEO4J_HOME="<REPO_ROOT>\.local\neo4j\neo4j-community-2025.06.1"
& "$env:NEO4J_HOME\bin\neo4j.bat" console
```

首次连接：http://127.0.0.1:7474，用 neo4j/neo4j 登录并修改密码。

## 5. 配置 .env

复制 `.env.example` 为 `.env`，填入以下配置：

```env
TRUTHNET_PROFILE=full
SQL_BACKEND=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_DATABASE=truthnet
MYSQL_USER=truthnet
MYSQL_PASSWORD=<your-password>

GRAPH_BACKEND=neo4j
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<your-password>

VECTOR_BACKEND=chroma
CHROMA_PERSIST_DIR=data/chroma_db

LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=<团队共享密钥>
DATASET_VERSION=competition-2026
GRAPH_VERSION=equity-competition-2026
```

## 6. 安装依赖

```powershell
conda create -n truthnet python=3.11 -y
conda activate truthnet
pip install -r requirements-chroma.txt
```

## 7. 建表

```powershell
alembic upgrade head
```

## 8. 数据导入

> 数据文件从团队共享渠道获取，放入 `data/raw/` 各子目录（见 `data/raw/README.md`）。

```powershell
# MySQL 全量入库
python scripts/import_data.py --data-root data/raw --dry-run
python scripts/import_data.py --data-root data/raw

# 公告情绪分类
python scripts/announcement_sentiment.py --data-file data/raw/3/clean.xlsx --dict-file data/raw/3/ditct.txt --update-mysql

# 公司名称回填
python scripts/backfill_company_names.py --dry-run
python scripts/backfill_company_names.py

# Neo4j 全量图谱
python scripts/neo4j_full_import.py --data-file data/raw/2/clean.xlsx --graph-version equity-competition-2026 --dataset-version competition-2026

# Chroma 嵌入（~2h，CPU）
python scripts/chroma_embed.py --output-dir data/processed/chroma-full
python scripts/chroma_import.py --input-dir data/processed/chroma-full --rebuild
```

## 9. 验证

```powershell
python scripts/verify_full_stack.py --profile full --check-external --write-smoke --cleanup

$env:TRUTHNET_RUN_EXTERNAL_TESTS="1"
$env:TRUTHNET_PROFILE="full"
python -m pytest backend/tests/integration -v -m "integration and external"
```

## 10. 常见问题

| 问题 | 解决 |
|------|------|
| 端口 3306 被占用 | 使用 3307 |
| mysqld 启动失败 | 检查 datadir 已初始化 |
| Neo4j 找不到 Java | 设置 JAVA_HOME |
| cryptography 缺失 | `pip install cryptography` |
| 密码认证失败 | MySQL 8.4 使用 caching_sha2_password |
| neo4j_full_import.py 编码报错 | 确保 PowerShell 终端编码为 UTF-8：`chcp 65001` |
| Chroma 嵌入模型下载失败 | huggingface 国内被墙，modelscope 已配置为国内镜像 |
