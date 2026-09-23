from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.chat import router as chat_router
from backend.api.upload import router as upload_router
from backend.api.sessions import router as sessions_router
from backend.config import BASE_DIR, DASHSCOPE_API_KEY
from backend.database import init_db

#启动期校验 Key：没有 Key 时 ChatOpenAI 仍能构造成功，直到第一次对话才 401，
#线上表现是「页面打得开、一问就崩」。在这里直接失败，排错从「猜」变成「一眼」
if not DASHSCOPE_API_KEY:
    raise RuntimeError("缺少 DASHSCOPE_API_KEY：本地写进 .env，线上配到平台环境变量")

#建表：可重复执行，启动时调一次
init_db()

app = FastAPI(title="AI Knowledge Assistant")
#响应压缩：只压 JSON 和静态资源，text/event-stream 不受影响
app.add_middleware(GZipMiddleware,minimum_size=1000)

#囊括路由
app.include_router(chat_router)
app.include_router(upload_router)
app.include_router(sessions_router)

@app.get("/health")
def health():
    return {"status":"ok"}

#前端静态站必须最后挂：mount("/") 是兜底路由，注册早于 /api 会把接口请求全吃掉
#本地没跑过 vite build 时 dist 不存在，跳过挂载，后端接口照常可用
DIST_DIR = BASE_DIR / "frontend" / "dist"
if DIST_DIR.is_dir():
    app.mount("/",StaticFiles(directory=DIST_DIR,html=True),name="static")