# 开发环境配置

## 适用人群

本文档面向所有团队成员（金融背景 + 计算机背景），提供完整的开发环境配置指南。

---

## 环境配置决策树

```
你的系统是什么？
├── Windows
│   ├── 有 conda？→ 方案 A（推荐）
│   └── 无 conda？→ 先安装 Miniconda（推荐）或使用方案 B（venv fallback）
├── macOS
│   ├── 有 conda？→ 方案 A（推荐）
│   └── 无 conda？→ brew install miniconda 或方案 B
└── Linux
    ├── 有 conda？→ 方案 A（推荐）
    └── 无 conda？→ 安装 Miniconda 或方案 B
```

### 自动检测

运行以下命令自动检测当前环境：

```bash
python scripts/env_bootstrap.py --check
```

如需自动配置环境：

```bash
python scripts/env_bootstrap.py --apply
```

---

## 方案 A：conda（推荐）

### 1. 确认 conda 已安装

```bash
conda --version
```

### 2. 创建并激活环境

```bash
conda create -n truthnet python=3.11 -y
conda activate truthnet
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 验证

```bash
python scripts/doctor.py
```

---

## 如果没有 conda

### 安装 Miniconda（推荐）

Miniconda 是 Anaconda 的轻量版本，只包含 conda 和 Python。

| 系统 | 下载地址 |
|------|----------|
| Windows x86_64 | https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe |
| macOS x86_64 | https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh |
| macOS arm64 (M1/M2/M3) | https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh |
| Linux x86_64 | https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh |
| Linux aarch64 | https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh |

> ⚠️ **安全提醒**：本项目不会自动下载任何安装器。请从上述官方地址手动下载。
> 运行 `python scripts/env_bootstrap.py --check` 可以看到适合你系统的安装建议。

### Windows 安装步骤

1. 下载 Miniconda3 Windows exe 安装器
2. 双击运行安装器
3. 勾选 "Add Miniconda3 to my PATH environment variable"
4. 安装完成后打开新的 PowerShell
5. 验证：`conda --version`

### macOS 安装步骤

```bash
# 或使用 Homebrew（推荐）
brew install miniconda

# 或手动下载安装
# 下载后运行 .sh 安装脚本，按提示完成
# 重启终端后验证
conda --version
```

### Linux 安装步骤

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
# 重启终端
conda --version
```

---

## 方案 B：venv fallback（无 conda 时的备选）

如果暂时无法安装 conda，可以使用 Python 自带的 venv。

### Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> 注意：如果 PowerShell 报 "无法加载文件"，先运行：
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 安装依赖

```bash
pip install -r requirements.txt
```

### 验证

```bash
python scripts/doctor.py
```

> ⚠️ venv fallback 使用系统 Python，请确保 Python 版本为 3.11.x。如果系统 Python 版本不符，建议安装 conda。

---

## CI 环境（GitHub Actions）

CI 使用 `setup-python`（而非 conda），但仍从同一个 `requirements.txt` 安装依赖：

```yaml
# .github/workflows/ci.yml
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
- run: pip install -r requirements.txt
- run: python scripts/doctor.py --ci
- run: python scripts/encoding_path_audit.py --ci
- run: python scripts/git_safety_check.py --ci
- run: python -m pytest backend/tests -v
- run: ruff check .
```

本地开发用 conda，CI 用 setup-python，两者都从同一个 `requirements.txt` 安装，保证依赖一致。

---

## pip 下载慢怎么办

如果从 PyPI 下载依赖很慢（常见于国内网络），可以**临时**使用镜像：

```bash
# 清华大学镜像（仅本机使用，不写入仓库文件）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**不要修改 `requirements.txt` 中的包源**。镜像配置属于本机设置，不提交到仓库。

---

## Node.js / pnpm 开发环境

### 前端开发环境

```bash
# 确保 Node.js >= 18 和 pnpm 已安装
node --version   # 应 >= 18
pnpm --version

# 进入前端目录
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```

### npm/pnpm 下载慢怎么办

```bash
# 临时使用镜像（仅本机，不写入仓库）
pnpm config set registry https://registry.npmmirror.com
```

---

## 代理配置

> ⚠️ **重要**：代理配置仅在你本机生效，**绝不**提交到仓库。

如果你在校园网或公司网络，可能需要配置代理访问 GitHub 和 PyPI。

### Git 代理

```bash
# 临时设置（替换为你的实际代理地址）
git config --global http.proxy http://your-proxy:port
git config --global https.proxy http://your-proxy:port

# 取消代理
git config --global --unset http.proxy
git config --global --unset https.proxy
```

### pip 代理

```bash
pip install -r requirements.txt --proxy http://your-proxy:port
```

### npm/pnpm 代理

```bash
pnpm config set proxy http://your-proxy:port
```

---

## 故障排查

### `conda: command not found`

检查是否安装了 Miniconda/Anaconda。Windows 需从开始菜单打开 "Anaconda Prompt"。
Linux/macOS 需重启终端或执行 `source ~/.bashrc` 或 `source ~/.zshrc`。

### `pip install timeout`

配置 pip 镜像源（见上文"pip 下载慢"章节）。

### `git clone timeout`

检查网络或配置代理（见"代理配置"章节）。

### `SSL error` 使用 pip 时

```bash
# 临时方案（仅开发环境）
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

### Windows PowerShell execution policy

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### macOS arm64 (Apple Silicon) 包兼容

优先使用 conda（自动处理 arm64 兼容），大部分 Python 包已支持 Apple Silicon。

### Linux 缺系统依赖

```bash
# Ubuntu/Debian
sudo apt install build-essential python3-dev

# CentOS/RHEL
sudo yum install gcc python3-devel

# Arch
sudo pacman -S base-devel
```
