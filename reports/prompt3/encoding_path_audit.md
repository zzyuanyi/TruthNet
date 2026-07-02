# 编码与路径审计报告

> 审计时间：2026-07-02
> 审计工具：`scripts/encoding_path_audit.py --ci`

## 审计结果摘要

| 检查项 | 结果 | 详情 |
|--------|------|------|
| UTF-8 解码 | ✅ PASS | 54/54 文件通过 |
| 裸 open() 无 encoding | ✅ PASS | 未发现真实问题 |
| 硬编码盘符 | ⚠️ PASSED_WITH_WARNINGS | 8 项均为文档反例/test 模式定义（见下方分析） |
| 硬编码个人路径 | ⚠️ PASSED_WITH_WARNINGS | 2 项均为文档反例 |
| .env Git tracked | ✅ PASS | .env 不存在/未被 track |
| 大文件 | ✅ PASS | 无 >500KB 文件 |
| CRLF 换行符 | ✅ PASS | 全部 LF |

## 详细分析

### UTF-8 解码：PASS

所有 54 个文本文件均可以 UTF-8 正确解码。项目统一 UTF-8 编码策略已生效。

### 裸 open() 检查：PASS

所有 Python 文件中的 `open()` 调用均包含 `encoding=` 参数，或使用二进制模式（`rb`/`wb`）。

### 硬编码盘符：8 项 WARNING（全部为可接受假阳性）

所有 flagged 项均属于以下两类，非真实代码问题：

1. **文档反例示例**（5 项）：
   - `.claude/skills/env-cross-platform/SKILL.md:73` — `config_path = "C:\\Users\\admin\\project\\config.yaml"`（标记为 `❌ 错误`）
   - `docs/SOFTWARE_ENGINEERING.md:37` — `data_path = "C:\\Users\\admin\\project\\data\\raw\\file.csv"`（标记为 `❌ 错误`）
   - 这些是在文档中展示"禁止"模式的示例

2. **测试模式定义**（3 项）：
   - `backend/tests/test_encoding_path_policy.py:114` — `'C:/', 'D:/', 'E:/', 'F:/'`（定义搜索模式以检查违规）
   - 这是测试代码的正则模式列表，用于检测其他文件，非实际使用

### 硬编码个人路径：2 项 WARNING（全部为文档反例）

- `.claude/skills/env-cross-platform/SKILL.md:75` — `data_path = "/home/user/TruthNet"`（标记为 `# 硬编码绝对路径`）
- `docs/SOFTWARE_ENGINEERING.md:38` — `data_path = "/home/user/TruthNet/data/raw/file.csv"`（标记为 `❌ 错误`）
- 均为文档中展示"禁止"模式的示例

### 换行符：PASS

所有文本文件使用 LF 换行符。`.gitattributes` 和 `.editorconfig` 已正确配置。

## 编码规范硬化清单

| 规范 | 写入位置 | 状态 |
|------|----------|------|
| UTF-8 统一编码 | `.editorconfig`, `CLAUDE.md`, `SOFTWARE_ENGINEERING.md`, `env-cross-platform/SKILL.md` | ✅ |
| LF 换行符 | `.gitattributes`, `.editorconfig` | ✅ |
| `encoding="utf-8"` 强制 | `CLAUDE.md`, `SOFTWARE_ENGINEERING.md`, `env-cross-platform/SKILL.md` | ✅ |
| Windows UTF-8 保护 | 所有脚本入口 | ✅ |
| `pathlib.Path` 强制 | `CLAUDE.md`, `SOFTWARE_ENGINEERING.md`, `env-cross-platform/SKILL.md` | ✅ |
| 禁止硬编码盘符 | `CLAUDE.md`, `SOFTWARE_ENGINEERING.md`, `env-cross-platform/SKILL.md` | ✅ |
| 审计脚本 | `scripts/encoding_path_audit.py` | ✅ |
| 审计测试 | `backend/tests/test_encoding_path_policy.py` | ✅ |

## 结论

编码与路径跨平台标准已成功硬化到项目规范、skills、脚本和测试中。所有真实代码均遵循规范。审计工具报告的 WARNING 均为文档反例示例和测试模式定义，属于可接受的假阳性。

**状态：PASSED_WITH_WARNINGS**（所有 warning 已验证为可接受假阳性）
