import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()

# 项目根目录：所有数据路径都从它拼出，保证与启动时的 CWD 无关
BASE_DIR = Path(__file__).resolve().parent.parent   
# 数据根目录：集中放 SQLite、上传件、向量库
DATA_DIR = BASE_DIR / "data"
# SQLite 库文件路径（存会话与消息）
DB_PATH = DATA_DIR / "app.db"
# 上传文件落盘目录
UPLOAD_DIR = DATA_DIR / "uploads"
# DashScope 的 OpenAI 兼容端点：因为有它，才能统一用 langchain-openai 调用
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# Chroma 集合名，必须与 ingest 写入时一致
COLLECTION_NAME = "knowledge_base"
# 检索返回条数上限，也顺带限制住了放宽阈值的副作用
RAG_TOP_K = 4
# 相似度阈值：score=2-2cos 的 l2 平方距离，0.8≈cos 0.60；若重建库改成 cosine 度量则此值立即失效
MAX_DISTANCE = 0.8 
# 单次 embedding 请求最大条数：text-embedding-v3 超过 10 条报 400
EMBEDDING_BATCH_SIZE = 10
# 模型服务密钥：只从 .env 读，禁止硬编码进代码
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY","")
# 对话模型名，可用环境变量覆盖
LLM_MODEL = os.getenv("LLM_MODEL","qwen-plus")
# 向量模型名：换它必须重建向量库，否则新旧向量不可比
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL","text-embedding-v3")
# 向量库持久化目录
CHROMA_DIR = os.getenv("CHROMA_DIR") or str(DATA_DIR / "chroma_db")
# 联网搜索密钥（web_search 用）
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
# 单次联网搜索返回的结果条数
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
# 网页正文截断上限：防止长网页把 context 撑爆
WEB_FETCH_MAX_CHARS   = int(os.getenv("WEB_FETCH_MAX_CHARS", "4000"))
# 外部请求超时秒数：不设超时整张图会被一次卡住的抓取拖死
WEB_FETCH_TIMEOUT = 10   
# 单文件上传上限（MB）：超大 PDF 解析会吃满内存，小实例直接被 OOM Kill
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB","20"))
# 上传上限的字节形式，供接口层直接比较
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
# 上传配额：单文件上限只能挡住"一次传个大的"，挡不住"传 1000 次小的"
# 磁盘只增不减（无租户、无 TTL），小机器会被慢慢打满，所以按"总量"再设一道闸
# 0 = 不限制；超限一律 413，不做自动淘汰（淘汰要先删向量，属另一件事）
MAX_UPLOAD_FILES = int(os.getenv("MAX_UPLOAD_FILES","200"))
MAX_UPLOAD_TOTAL_MB = int(os.getenv("MAX_UPLOAD_TOTAL_MB","1024"))
MAX_UPLOAD_TOTAL_BYTES = MAX_UPLOAD_TOTAL_MB * 1024 * 1024
# 启动时清理孤儿 PDF（同名覆盖后旧 UUID 文件会留下，向量库里已无引用）
# 判定依据是 chunk metadata["stored"]；旧数据没这个字段就整轮跳过，绝不猜着删
ORPHAN_CLEANUP_ON_START = os.getenv("ORPHAN_CLEANUP_ON_START","true").lower() == "true"
# 宽限期（秒）：刚落盘还没入库的文件不参与判定，避免与上传请求竞态
ORPHAN_GRACE_SECONDS = int(os.getenv("ORPHAN_GRACE_SECONDS","3600"))
# 自审循环硬上限：judge 不会主动说停，靠代码兜底防振荡
MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "2"))
#人工审查模式
HUMAN_REVIEW_MODE = os.getenv("HUMAN_REVIEW_MODE", "always")
# 人工介入后可额外推动的修订次数：让"人比 AI 多一次机会"，同时兜住无限循环
HUMAN_EXTRA_REVISIONS = int(os.getenv("HUMAN_EXTRA_REVISIONS", "1"))