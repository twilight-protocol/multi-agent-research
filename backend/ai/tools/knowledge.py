from langchain_core.tools import tool
from backend.ai.vectorstore import get_vectorstore
from backend.config import RAG_TOP_K,MAX_DISTANCE
@tool
def search_knowledge_base(query:str)->str:
     """在「用户上传的 PDF 文档」构成的本地知识库中检索内容。
    知识库保存的是用户上传过的文档原文，检索结果附带文件名与页码。凡属于以下情况，
    必须调用本工具查证，禁止凭记忆回答：
    - 用户问「文档里怎么说的」「我上传的资料里有没有提到…」
    - 涉及具体产品/业务的注册、认证、账号、配置、流程、操作步骤、条款、参数
    - 需要用出处（文件名 + 页码）支撑的回答
    入参 query 传关键词或短句即可，不要传整段对话。
    """
     hits = get_vectorstore().similarity_search_with_score(query,k=RAG_TOP_K)
     kept = [(d,s) for d,s in hits if s <= MAX_DISTANCE]
     if not kept:
          return "知识库中未找到相关内容。"
     blocks = []
     for doc,_score in kept:
        blocks.append(f"[{doc.metadata.get('source','未知文档')} 第{doc.metadata.get('page','?')}页]\n"
        f"{doc.page_content}"
        )
     return "\n\n---\n\n".join(blocks)
