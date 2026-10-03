import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from backend.ai.ingest import sweep_orphan_uploads
from backend.ai.research.service import graph_lifespan
from backend.api.research import router as research_router
from backend.api.upload import router as upload_router
from backend.config import BASE_DIR, DASHSCOPE_API_KEY

if not DASHSCOPE_API_KEY:
    raise RuntimeError("缺少 DASHSCOPE_API_KEY")

logger = logging.getLogger("mar")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 套在 graph_lifespan 外层：图先建好，再顺手清一次上传目录的孤儿文件
    async with graph_lifespan(app):
        # 同步 IO（glob + stat + unlink）不能放在事件循环上，甩线程池
        result = await asyncio.to_thread(sweep_orphan_uploads)
        if result.get("deleted"):
            logger.warning("启动清理：删除孤儿 PDF %s（扫描 %s 个）",result["deleted"],result.get("scanned"))
        else:
            logger.info("启动清理：无孤儿文件（%s）",result)
        yield

app = FastAPI(title="多智能体行业研究助手", lifespan=lifespan)
#响应压缩：只压 JSON 和静态资源，text/event-stream 不受影响
app.add_middleware(GZipMiddleware,minimum_size=1000)

#囊括路由
app.include_router(research_router)
app.include_router(upload_router)

@app.get("/health")
def health():
    return {"status":"ok"}

DIST_DIR = BASE_DIR / "frontend" / "dist"
if DIST_DIR.is_dir():
    app.mount("/",StaticFiles(directory=DIST_DIR,html=True),name="static")