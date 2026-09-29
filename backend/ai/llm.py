from langchain_openai import ChatOpenAI
from backend.config import DASHSCOPE_API_KEY,DASHSCOPE_BASE_URL,LLM_MODEL

llm = ChatOpenAI(
    model=LLM_MODEL,
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
    temperature=0.7,

)