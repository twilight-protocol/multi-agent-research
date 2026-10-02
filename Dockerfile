# syntax=docker/dockerfile:1

# ---------- 阶段 1：构建前端静态产物 ----------
# 这个阶段只负责跑 vite build；产物 dist 在阶段 2 被拷走，node 本身不进最终镜像
FROM node:22-alpine AS frontend-build
WORKDIR /build
# 先拷 manifest 再装依赖：这层能被缓存，只改业务代码时不会重装 node_modules
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 阶段 2：运行时 ----------
FROM python:3.14-slim AS runtime
WORKDIR /app

# PYTHONUNBUFFERED：否则日志攒在缓冲区里，容器挂了看不到任何报错
# PIP_INDEX_URL：容器内直连 pypi.org 在国内服务器上会超时/极慢，改走阿里云镜像
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

# --workers 1 是硬约束，不是省资源：
#   1) Chroma 的 PersistentClient 跨进程并发写不安全（向量库落在单个 sqlite 文件上）；
#   2) 限流器 backend/ratelimit.py 的计数桶是进程内 dict，多 worker 会各算一份
#      → 配的 5 次/分钟实际变成 5×worker 次；
#   3) 人工终审的断点已落 SQLite（AsyncSqliteSaver），能跨进程读，但同一 thread_id
#      在多 worker 间漂移会造成 sqlite 写锁竞争。
# 平台（Render / Railway）会注入 $PORT，所以必须用 shell 形式让变量能展开
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
