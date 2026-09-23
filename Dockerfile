FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# 应用代码与依赖清单
COPY requirements.txt /app/requirements.txt
COPY app /app/app
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 依赖安装随容器启动完成（见 entrypoint.sh）
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
