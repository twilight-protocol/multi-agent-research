import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent   # 项目根，与 CWD 无关
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "app.db"
UPLOAD_DIR = DATA_DIR / "uploads"


DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
COLLECTION_NAME = "knowledge_base"
RAG_TOP_K = 4
MAX_DISTANCE = 0.7    #暂定
#DashScope text-embedding-v3 单次请求最多 10 条，超出报 400 batch size is invalid
EMBEDDING_BATCH_SIZE = 10

#从.env里读取数据
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY","")
LLM_MODEL = os.getenv("LLM_MODEL","qwen-plus")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL","text-embedding-v3")
CHROMA_DIR = os.getenv("CHROMA_DIR") or str(DATA_DIR / "chroma_db")

#单次上传上限：pypdf 解析超大 PDF 会吃满内存，免费档 512MB 实例直接被 OOM Kill
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB","20"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024