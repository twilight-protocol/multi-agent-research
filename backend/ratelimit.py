import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_PRUNE_THRESHOLD = 5000  # 单个限流器的记录数超过这个值就清理一轮


def _client_ip(request: Request) -> str:
    """取真实客户端 IP。"""
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


# 研究：一次请求要跑 4~8 次 LLM 调用（检索→分析→写作→自审→最多 3 轮修订），比聊天重得多
research_limiter = make_limiter(
    int(os.getenv("RESEARCH_RATE_LIMIT_MAX", "5")),
    int(os.getenv("RESEARCH_RATE_LIMIT_WINDOW", "60")),
    "research",
)

# 上传：一份 PDF 会触发 N/10 次 Embedding 调用，解析本身还吃 CPU 和内存，要更紧
upload_limiter = make_limiter(
    int(os.getenv("UPLOAD_RATE_LIMIT_MAX", "3")),
    int(os.getenv("UPLOAD_RATE_LIMIT_WINDOW", "60")),
    "upload",
)
