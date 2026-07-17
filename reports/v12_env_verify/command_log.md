# 命令执行日志

> 所有命令使用 `E:/anaconda/envs/truthnet/python.exe` 直接运行（避免 shell 编码问题）

```bash
# Phase 1: 环境确认
python --version                              # Python 3.12.7 (base)
cat .python-version                           # 3.11
conda info --envs                             # truthnet 存在
E:/anaconda/envs/truthnet/python.exe --version  # Python 3.11.15

# Phase 2: 依赖安装
E:/anaconda/envs/truthnet/python.exe -m pip install --upgrade pip
E:/anaconda/envs/truthnet/python.exe -m pip install -r requirements.txt
# → Successfully installed: Mako, MarkupSafe, alembic, greenlet, jsonschema,
#   jsonschema-specifications, neo4j, pymysql, referencing, rpds-py, sqlalchemy, structlog

# Phase 3: V12 Stack Verify
E:/anaconda/envs/truthnet/python.exe scripts/verify_v12_stack.py
# → [PASS] | V12 技术栈验证通过

# Phase 4: 完整检查
E:/anaconda/envs/truthnet/python.exe -m ruff check .           # All checks passed
E:/anaconda/envs/truthnet/python.exe -m ruff format --check .  # 98 files formatted
E:/anaconda/envs/truthnet/python.exe -m pytest ... -q          # 49 passed
E:/anaconda/envs/truthnet/python.exe -m pip check              # No broken requirements
E:/anaconda/envs/truthnet/python.exe scripts/doctor.py         # 57/60 PASS
E:/anaconda/envs/truthnet/python.exe scripts/encoding_path_audit.py  # 12 pre-existing FAIL
E:/anaconda/envs/truthnet/python.exe scripts/git_safety_check.py     # 1 pre-existing FAIL (main)
```
