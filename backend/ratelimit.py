"""进程内 IP 限流。

为什么需要：`/api/chat/stream` 和 `/api/upload` 会在服务端消耗 DashScope 额度。线上是
公开地址，任何人都能直接打接口；没有限流的话，一个脚本就能把额度刷完，Demo 当场失效。

为什么用内存不用 Redis：部署形态是「单容器 + 单 worker」（见 Dockerfile 注释），
内存计数不会出现「A 进程记 3 次、B 进程记 3 次」的分裂。免费档上，少引入一个
外部组件就少一个上线失败点。

已知局限（面试可讲）：
- 一旦开多 worker / 多副本，内存计数不共享，要换成 Redis 的 INCR + EXPIRE；
- 计数按 IP 增长，靠 _prune 在超阈值时清理过期窗口，避免 dict 无限膨胀。
"""

import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_PRUNE_THRESHOLD = 5000  # 单个限流器的记录数超过这个值就清理一轮


def _client_ip(request: Request) -> str:
    """取真实客户端 IP。

    平台（Render / Railway / nginx）在应用前面加了一层代理，此时
    request.client.host 拿到的是代理 IP → 所有用户共用一个配额，限流等于没做。
    所以要优先取 X-Forwarded-For 的第一个地址。
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def make_limiter(max_requests: int, window_sec: int, name: str):
    """生成一个「FastAPI 依赖」形式的限流器。

    每个限流器持有独立计数桶：聊天按次限、上传按份限，两者互不挤占额度。
    """

    hits: dict[str, deque[float]] = defaultdict(deque)

    def _prune(now: float) -> None:
        for ip in [ip for ip, q in hits.items() if not q or now - q[-1] > window_sec]:
            hits.pop(ip, None)

    def dependency(request: Request) -> None:
        now = time.time()
        if len(hits) > _PRUNE_THRESHOLD:
            _prune(now)

        q = hits[_client_ip(request)]
        while q and now - q[0] > window_sec:
            q.popleft()
        if len(q) >= max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，请 {window_sec} 秒后再试",
            )
        q.append(now)

    dependency.__name__ = f"rate_limit_{name}"
    return dependency


# 聊天：一次请求 ≈ 1~3 次 LLM 调用，10 次/分足够正常点着玩
chat_limiter = make_limiter(
    int(os.getenv("RATE_LIMIT_MAX", "10")),
    int(os.getenv("RATE_LIMIT_WINDOW", "60")),
    "chat",
)

# 上传：一份 PDF 会触发 N/10 次 Embedding 调用，解析本身还吃 CPU 和内存，要更紧
upload_limiter = make_limiter(
    int(os.getenv("UPLOAD_RATE_LIMIT_MAX", "3")),
    int(os.getenv("UPLOAD_RATE_LIMIT_WINDOW", "60")),
    "upload",
)
