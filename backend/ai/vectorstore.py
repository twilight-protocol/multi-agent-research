from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from backend.config import EMBEDDING_MODEL,DASHSCOPE_API_KEY,DASHSCOPE_BASE_URL,CHROMA_DIR,COLLECTION_NAME,EMBEDDING_BATCH_SIZE
from pathlib import Path

_embeddings = None
_vectorstore = None

#向量模型
def get_embeddings() -> OpenAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
            check_embedding_ctx_length=False,
            #必须限制批量：DashScope 单次最多 10 条，默认 1000 会报 400
            chunk_size=EMBEDDING_BATCH_SIZE,
        )
    return _embeddings

#向量库
def get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        Path(CHROMA_DIR).mkdir(parents=True,exist_ok=True)
        _vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=CHROMA_DIR,
        )
    return _vectorstore
