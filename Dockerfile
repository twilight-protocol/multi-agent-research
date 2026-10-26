# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend-build
WORKDIR /build
# 先拷 manifest 再装依赖：这层能被缓存，只改业务代码时不会重装 node_modules
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com

# 依赖单独一层：requirements.txt 不变时，改后端代码不会触发重新装包
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
# 前端产物放到 frontend/dist，main.py 用它挂 StaticFiles 兜底路由
COPY --from=frontend-build /build/dist ./frontend/dist

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
