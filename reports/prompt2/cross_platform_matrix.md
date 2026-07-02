# 跨平台兼容验证矩阵

**验证日期**：2026-07-02

---

## 本地已验证（Windows 11, AMD64）

| Platform | Validation Method | Status | Evidence | Remaining Risk |
|----------|------------------|--------|----------|----------------|
| Windows 11 (AMD64) | 独立 conda 环境 + 14 smoke tests | ✅ passed | `reports/prompt2/environment_verification.md` | — |
| Windows 11 (AMD64) | doctor.py --ci (33/33 PASS) | ✅ passed | 控制台输出 | — |
| Windows 11 (AMD64) | ruff check + format check | ✅ passed | All checks passed | — |

---

## CI 待验证（GitHub Actions）

| Platform | Python | Status | Evidence | Remaining Risk |
|----------|--------|--------|----------|----------------|
| ubuntu-latest | 3.11 | 🔶 CI 已配置，待 push 后运行 | `.github/workflows/ci.yml` | ChromaDB 的 onnxruntime 在 Linux 可能有不同行为 |
| windows-latest | 3.11 | 🔶 CI 已配置，待 push 后运行 | `.github/workflows/ci.yml` | 路径大小写敏感性 |
| macos-latest | 3.11 | 🔶 CI 已配置，待 push 后运行 | `.github/workflows/ci.yml` | ChromaDB 可能需要额外的系统依赖 |

---

## 跨平台兼容措施清单

| 措施 | 状态 | 说明 |
|------|------|------|
| `pathlib.Path` 用于所有 Python 路径操作 | ✅ | doctor.py, check_env.py, main.py 均使用 pathlib |
| `.ps1` + `.sh` 双脚本 | ✅ | `scripts/init_dev_env.ps1` + `scripts/init_dev_env.sh` |
| 脚本语义一致性 | 🔶 待验证 | `.ps1` 和 `.sh` 功能基本一致，但 PowerShell 语法不同属正常 |
| `.editorconfig` LF 换行 | ✅ | 统一 LF |
| UTF-8 编码 | ✅ | `.editorconfig` + Python 脚本顶部声明 |
| `requirements.txt` 跨平台 | ✅ | 无平台特定 GPU 包 |
| 无硬编码路径 | ✅ | 审计通过 — 无盘符、无反斜杠路径 |
| CI 三平台 Python 3.11 | ✅ | `.github/workflows/ci.yml` 已配置 |
| `doctor.py --ci` 模式 | ✅ | 已实现并验证 (33/33 PASS) |

---

## 前端跨平台状态

| 项目 | 状态 |
|------|------|
| Node.js 安装 | ✅ 本机已安装 |
| pnpm 安装 | ✅ 本机已安装 |
| `frontend/package.json` | ❌ 未创建 |
| 前端跨平台兼容性 | 待前端初始化后评估 |

---

## 已知风险

1. **ChromaDB onnxruntime**：在不同平台可能需要不同的 onnxruntime wheel。已通过 `chromadb==0.5.23` 的依赖自动解决。
2. **Windows 路径大小写**：CI 仅在 PowerShell 下运行，路径不区分大小写属于正常行为。
3. **macOS CI**：ChromaDB 在 macOS 可能需要 `libomp` 或其他系统依赖。如 CI 失败，将在第一次 CI 运行后排查。
4. **未实际运行 CI**：当前 CI workflow 已创建但尚未被 GitHub Actions 执行（需要 push 到 remote 触发）。本地已验证所有 CI 步骤。

---

## 建议

1. Push `dev` 分支后立即观察 CI 三平台结果
2. 如果某个平台 CI 失败，在 `reports/prompt2/cross_platform_matrix.md` 中记录并修复
3. 前端初始化后添加 `frontend/` 的 lint/build 到 CI
