---
name: env-cross-platform
description: 跨平台环境兼容检查。每次涉及环境、依赖、路径、脚本、运行命令时自动激活，确保 Windows/macOS/Linux 兼容。
---

# 跨平台环境兼容

## 核心原则

当涉及以下操作时，必须遵循跨平台兼容规则：

1. 创建或修改 Python 脚本
2. 使用文件路径
3. 创建 shell 脚本
4. 配置环境变量
5. 安装依赖
6. 添加新的 Python 包
7. 运行命令

---

## 编码与换行硬性规定

### UTF-8 编码

1. 所有文本文件统一 UTF-8 编码。
2. **所有** Python 文件读写文本必须显式 `encoding="utf-8"`：

```python
# ✅ 正确
Path("file.md").read_text(encoding="utf-8")
Path("file.md").write_text(content, encoding="utf-8", newline="\n")
open("file.txt", "w", encoding="utf-8")

# ❌ 错误
Path("file.md").read_text()          # 可能使用系统默认编码
open("file.txt", "w")                # 可能使用系统默认编码
```

3. 脚本入口建议加 Windows UTF-8 输出保护：

```python
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```

### 换行符

4. Git 仓库统一 LF 换行符。`.gitattributes` 已配置。
5. 写入文件时使用 `newline="\n"` 确保跨平台一致。

---

## Python 路径规范

- **必须**使用 `pathlib.Path` 进行所有路径操作
- **禁止**硬编码盘符（如 `C:\`, `D:\`, `E:\`, `F:\`）、反斜杠路径、绝对路径
- **禁止**使用 `os.path` 系列函数，统一使用 `pathlib`
- **禁止**在业务代码里写死 `\` 或 `/` 作为路径拼接

```python
# ✅ 正确
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
config_path = ROOT / "data" / "raw" / "file.csv"
data_dir = Path.cwd() / "data" / "raw"

# ❌ 错误
config_path = "C:\\Users\\admin\\project\\config.yaml"
data_path = "data\\raw"              # 反斜杠
data_path = "/home/user/TruthNet"    # 硬编码绝对路径
open(path)                           # 无 encoding
```

---

## 环境检测流程

每次启动开发会话时，应检测以下内容：

### 1. 系统检测

```python
import platform
platform.system()  # Windows / Darwin / Linux
```

### 2. Python 版本

```bash
python --version  # 必须 3.11.x
```

### 3. conda 检测

```bash
conda --version
conda env list
```

### 4. 环境配置决策树

```
有 conda？
  ├── 是 → 创建/使用 truthnet 环境
  │       Python 必须 3.11.x
  │       使用 pip 安装唯一 requirements.txt
  │
  └── 否 → 提示用户安装 Miniconda
           只给官方安装指引（不自动下载）
           如用户暂时不装 → 使用 .venv fallback
           fallback 必须在报告中标注
```

### 5. 无 conda 时的处理

- **输出 Anaconda/Miniconda 官方安装建议**
- **根据系统输出对应说明**
- **不在无确认情况下自动下载安装器**
- **不自动执行未知安装器**
- 提供 venv fallback 路径

### 6. 运行引导脚本

```bash
# 仅检测
python scripts/env_bootstrap.py --check

# 执行配置
python scripts/env_bootstrap.py --apply
```

---

## Shell 脚本

- 任何自动化脚本必须同时提供 `.ps1`（Windows PowerShell）和 `.sh`（macOS/Linux）版本
- 不要在脚本中写死用户名、盘符、绝对路径
- 使用环境变量和相对路径
- 通用逻辑尽量写成 Python 脚本，而不是 shell

---

## Python 版本

- 从 `.python-version` 文件读取 Python 版本要求
- 当前版本：3.11
- 不要假设系统默认 Python 版本

---

## 环境管理

- **首选**：conda 创建隔离环境，pip 安装唯一的 `requirements.txt`
- **备选**：如果系统没有 conda，允许使用 `python -m venv .venv`
- 文档默认以 conda 为主要说明

```bash
# conda 标准流程（推荐）
conda create -n truthnet python=3.11 -y
conda activate truthnet
pip install -r requirements.txt

# venv 备选流程
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\Activate.ps1       # Windows PowerShell
pip install -r requirements.txt
```

---

## 环境检测

- 每次修改环境相关文件后运行 `python scripts/doctor.py`
- 提交前运行 `python scripts/encoding_path_audit.py`

---

## 新增 Python 包

- 所有新包必须加入 `requirements.txt`，使用 `==` 固定版本
- 新包必须验证在 Windows、macOS、Linux 下均可安装
- 如果某包存在平台限制，在 `requirements.txt` 中以注释说明
- 不加入平台特定 GPU 包（如 `torch-cuda`）

---

## 代理与镜像配置

- 代理配置只写入用户本机的全局设置或 `.env`（不提交）
- **禁止**把代理地址、用户名、密码写入仓库任何文件
- 可写入文档作为说明，但只使用占位符（如 `your-proxy:port`）

### pip 下载慢

- **不修改 requirements.txt**
- 可引导用户本机配置 pip index 或使用临时命令
- 不把镜像地址、代理账号、密码提交到仓库

```bash
# 临时使用镜像（仅本机，不写入仓库）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### npm/pnpm 下载慢

```bash
# 临时使用镜像（仅本机，不写入仓库）
pnpm config set registry https://registry.npmmirror.com
```

---

## 常见错误排查

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `conda: command not found` | conda 未安装或未加入 PATH | 安装 Miniconda，或从 Anaconda Prompt 启动 |
| `pip install timeout` | 网络慢 | 使用 `-i` 临时指定镜像 |
| `SSL error` | 证书问题 | `pip install --trusted-host ...` |
| `Windows PowerShell execution policy` | 脚本执行受限 | `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `macOS arm64 包兼容` | Apple Silicon 兼容性 | 优先用 conda（自动处理 arm64） |
| `Linux 缺系统依赖` | 缺少 gcc 等 | `apt install build-essential` 或等效命令 |

---

## 检查清单

在修改涉及环境的代码时，自动检查：

- [ ] 路径操作使用了 `pathlib.Path`？
- [ ] 所有文件读写有 `encoding="utf-8"`？
- [ ] 没有硬编码盘符或反斜杠？
- [ ] 同时提供了 `.ps1` 和 `.sh`？（如果需要脚本）
- [ ] Python 版本与 `.python-version` 一致？
- [ ] 新包已加入 `requirements.txt` 并固定版本？
- [ ] 没有平台特定依赖（GPU 包等）？
- [ ] 代理配置未写死？
- [ ] `.env` 未被 Git track？
- [ ] 脚本入口有 Windows UTF-8 输出保护？

---

## V12 更新（2026-07-17）

### Profile 机制

- `TRUTHNET_PROFILE=lite` — 默认开发/CI，使用 SQLite + NetworkX + Mock LLM
- `TRUTHNET_PROFILE=full` — 正式演示，使用 MySQL + Neo4j + DeepSeek/Qwen
- 新增依赖仍写入唯一 `requirements.txt`
- 外部服务通过 Adapter 和 profile 管理

### lite profile 规则

- 不要求 MySQL/Neo4j 服务在线
- 使用 SQLite/NetworkX/Mock 作为 lite adapter
- CI 基础 job 不依赖外部服务

### full profile 规则

- 使用 MySQL/Neo4j/DeepSeek 或 Qwen
- 通过 `check_connection()` 检测服务可用性
- 不可用时降级并返回 warning
