# TruthNet 后端镜像 — Phase D #9
# 使用明确的 Python 3.11 版本（不用 latest）
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 系统依赖：MySQL 客户端（pymysql 纯 Python，不需要 native lib）
# tzdata 用于时区；curl 用于 healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制 requirements 以利用构建缓存
COPY requirements.txt requirements-chroma.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# 后端代码
COPY backend/ backend/
COPY alembic.ini ./

# 数据目录（Chroma 持久化 / 报告输出）
RUN mkdir -p /app/data/chroma_db /app/data/reports

EXPOSE 8000

# 生产用 uvicorn（非 --reload）
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
