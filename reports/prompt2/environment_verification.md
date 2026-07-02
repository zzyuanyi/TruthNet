# 独立虚拟环境验证报告

**验证日期**：2026-07-02

---

## 环境信息

| 项目 | 值 |
|------|---|
| 环境管理器 | conda |
| 环境名称 | `truthnet` |
| Python 版本 | 3.11.15 |
| Python 路径 | `E:\anaconda\envs\truthnet\python.exe` |
| pip 版本 | 26.1.2 |
| pip 路径 | `E:\anaconda\envs\truthnet\Lib\site-packages\pip` |
| 操作系统 | Windows 11 (build 10.0.26200) |
| 架构 | AMD64 |
| 依赖来源 | 唯一 `requirements.txt` |
| pip freeze | `reports/prompt2/pip_freeze_truthnet.txt` |

---

## 十个关键问题

### 1. 是否创建/使用了项目独立环境？
✅ 是。使用 `conda create -n truthnet python=3.11 -y` 创建全新独立环境。

### 2. 环境名称是什么？
`truthnet`

### 3. Python 版本是否为 3.11.x？
✅ 是。Python 3.11.15，符合 `.python-version` 中 `3.11` 的要求。

### 4. pip 是否来自该环境？
✅ 是。`pip 26.1.2 from E:\anaconda\envs\truthnet\Lib\site-packages\pip (python 3.11)`

### 5. 依赖是否全部安装成功？
✅ 是。`pip install -r requirements.txt` 成功，无错误。所有包均从单一 `requirements.txt` 安装。

### 6. `doctor.py` 是否还存在 WARN/FAIL？
✅ 本地运行：**31 PASS / 2 WARN / 0 FAIL**（2 WARN 为 Python 版本显示 3.11 vs 3.11.15 的 minor 差异，以及运行在直接 Python 路径而非 conda activate 激活的环境中）。
✅ CI 模式运行：**33 PASS / 0 WARN / 0 FAIL**。

### 7. pytest 是否通过？
✅ 是。**14/14 tests passed**（在独立 truthnet 环境中）：
- test_health_check
- test_health_check_contract
- test_chat_mock_contract
- test_fastapi_import
- test_pydantic_chat_schema_roundtrip
- test_sqlite_minimal
- test_networkx_ownership_chain
- test_chromadb_minimal
- test_langgraph_minimal_state_graph
- test_pandas_numpy_sklearn
- test_dotenv_and_settings
- test_pydantic_settings_defaults
- test_ruff_installed
- test_pre_commit_installed

### 8. pre-commit 是否通过？
✅ 是。`pre-commit run --all-files` 全部 Passed。

### 9. 失败项是否由 base 环境污染导致？
✅ Prompt1 中的 FAIL 项（numpy 2.x 与 base 环境 scipy 冲突）已完全消除。在独立 truthnet 环境中无任何此类问题。

### 10. 当前环境是否可作为团队标准环境？
✅ 是。`truthnet` (conda, Python 3.11) 环境可作为团队标准开发环境。安装命令：
```bash
conda create -n truthnet python=3.11 -y
conda activate truthnet
pip install -r requirements.txt
```

---

## 与 Prompt1 对比

| 指标 | Prompt1 (base conda, Python 3.12) | Prompt2 (truthnet conda, Python 3.11) |
|------|-----------------------------------|--------------------------------------|
| Python | 3.12.7 ❌ | 3.11.15 ✅ |
| 环境 | base ❌ | truthnet (独立) ✅ |
| doctor.py | 27P/3W/3F ❌ | 31P/2W/0F ✅ |
| doctor.py --ci | 不存在 | 33P/0W/0F ✅ |
| pytest | 1 passed | 14 passed ✅ |

---

## 命令日志

```bash
# 环境创建
conda create -n truthnet python=3.11 -y
# Result: 成功

# 激活并检查
E:/anaconda/envs/truthnet/python.exe --version
# Python 3.11.15

# 安装依赖
E:/anaconda/envs/truthnet/python.exe -m pip install -r requirements.txt
# Result: 全部安装成功

# 环境检测
E:/anaconda/envs/truthnet/python.exe scripts/doctor.py
# Result: 31 PASS, 2 WARN, 0 FAIL

# CI 模式
E:/anaconda/envs/truthnet/python.exe scripts/doctor.py --ci
# Result: 33 PASS

# 测试
E:/anaconda/envs/truthnet/python.exe -m pytest backend/tests -v
# Result: 14 passed

# pre-commit
E:/anaconda/envs/truthnet/python.exe -m pre_commit run --all-files
# Result: All passed

# ruff
E:/anaconda/envs/truthnet/python.exe -m ruff check backend/ scripts/
# Result: All checks passed

# pip freeze
E:/anaconda/envs/truthnet/python.exe -m pip freeze > reports/prompt2/pip_freeze_truthnet.txt
```
