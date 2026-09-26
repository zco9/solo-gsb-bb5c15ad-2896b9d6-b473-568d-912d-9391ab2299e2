FROM python:3.12-slim

WORKDIR /app

# 镜像构建时预装依赖；容器启动命令会再次确认安装（已满足时立即跳过），
# 保证“依赖安装随容器启动完成”。
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# 容器启动时先完成依赖安装，再启动服务
CMD ["sh", "-c", "pip install --no-cache-dir -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
