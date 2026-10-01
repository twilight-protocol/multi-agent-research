from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from backend.ai.research.service import graph_lifespan
from backend.api.research import router as research_router
from backend.api.upload import router as upload_router
from backend.config import BASE_DIR, DASHSCOPE_API_KEY

if not DASHSCOPE_API_KEY:
    raise RuntimeError("缺少 DASHSCOPE_API_KEY")

app = FastAPI(title="多智能体行业研究助手", lifespan=graph_lifespan)
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