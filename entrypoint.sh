#!/bin/sh
# 容器启动时完成依赖安装，随后启动服务。
set -e

echo "[entrypoint] 安装/校验 Python 依赖 …"
pip install --no-cache-dir -r /app/requirements.txt

echo "[entrypoint] 启动 uvicorn，监听 0.0.0.0:${PORT:-8000} …"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
