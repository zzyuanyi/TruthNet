# TruthNet V12 Lite Profile 快速开发手册

> 适用于不需要 MySQL/Neo4j 的日常开发和 CI。
> 使用 SQLite + NetworkX + ChromaDB local + Mock LLM。

## 1. 克隆仓库

```bash
git clone https://github.com/zzyuanyi/TruthNet.git
cd TruthNet
```

## 2. 创建 conda 环境

```bash
conda create -n truthnet python=3.11 -y
conda activate truthnet
```

## 3. 安装依赖

```bash
pip install -r requirements.txt
```

## 4. 配置环境

```bash
cp .env.example .env
# 编辑 .env, 确保 TRUTHNET_PROFILE=lite
```

## 5. 验证

```bash
python scripts/verify_v12_stack.py          # 技术栈验证
python scripts/verify_full_stack.py --profile lite  # Lite 验证
python scripts/doctor.py                     # 环境检测
python -m pytest backend/tests -v            # 运行测试
ruff check .                                 # 代码检查
```

## 6. 启动后端

```bash
uvicorn backend.app.main:app --reload
# http://127.0.0.1:8000/healthz
# http://127.0.0.1:8000/api/v1/companies?query=茅台
```

## 不需要

- ❌ MySQL 服务
- ❌ Neo4j 服务
- ❌ JDK
- ❌ DeepSeek/Qwen API key
