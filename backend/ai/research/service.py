from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from backend.ai.research.graph import build_graph
from backend.config import DB_PATH

_ctx = None
GRAPH = None


def get_graph():
    if GRAPH is None:
        raise RuntimeError("GRAPH 未初始化：只能经 FastAPI lifespan 启动后使用")
    return GRAPH


@asynccontextmanager
async def graph_lifespan(app):
    global _ctx,GRAPH
    _ctx = AsyncSqliteSaver.from_conn_string(str(DB_PATH))
    saver = await _ctx.__aenter__()
    GRAPH = build_graph(saver)
    try:
        yield
    finally:
        await _ctx.__aexit__(None,None,None)
        GRAPH = None