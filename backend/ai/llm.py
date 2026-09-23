from langchain_openai import ChatOpenAI
from backend.config import DASHSCOPE_API_KEY,DASHSCOPE_BASE_URL,LLM_MODEL

#选择模型：base_url 统一走 config，避免与 config.DASHSCOPE_BASE_URL 两处各写一份
llm = ChatOpenAI(
    model=LLM_MODEL,
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
    temperature=0.7,

)