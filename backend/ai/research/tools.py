from langchain_core.tools import tool
from bs4 import BeautifulSoup
from tavily import TavilyClient
from backend.ai.tools.knowledge import search_knowledge_base
from backend.config import TAVILY_API_KEY, WEB_SEARCH_MAX_RESULTS,WEB_FETCH_MAX_CHARS, WEB_FETCH_TIMEOUT
import httpx
import re
_client:TavilyClient | None = None

def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        if not TAVILY_API_KEY:
            raise RuntimeError("未配置TAVILY_API_KEY")
        _client = TavilyClient(api_key=TAVILY_API_KEY)
    return _client

@tool
def web_search(query:str) -> str:
    """联网搜索公开信息，返回标题、摘要与网址。

    适用于：时效性信息（新闻、最新版本、发布会）、公开常识、本地文档未覆盖的内容。
    不适用于：用户上传文档里的内容（那要用 search_knowledge_base）。
    入参 query 传关键词或短句，不要传整段对话；摘要不够时再对具体网址调用 fetch_url。
    """
    try:
        response = _get_client().search(query,max_results=WEB_SEARCH_MAX_RESULTS)
    except Exception as e:
        return f"搜索失败:{e}"
    results = response.get("results") or []
    if not results:
        return "未搜索到相关结果."
    blocks = []
    for r in results:
        url= r.get("url","")
        title = (r.get("title") or "").strip()
        snippet = (r.get("content") or "").strip()
        blocks.append(f"[web:{url}] {title}\n{snippet}")
    return "\n\n---\n\n".join(blocks)

_WS_RE = re.compile(r"\s+")

@tool
def fetch_url(url:str)->str:
    """抓取指定网页的正文文本。

    什么时候用：web_search 给的摘要不够、需要读原文细节时。
    注意：正文超过长度上限会被直接截断，末尾没有省略号提示。
    """
    try:
        response =httpx.get(
            url,
            timeout=WEB_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent":"Mozilla/5.0"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text,"html.parser")
        for tag in soup(["script","style","noscript","svg","iframe"]):
            tag.decompose()
        text = _WS_RE.sub(" ",soup.get_text(" ",strip=True)).strip()
    except Exception as e:
        return f"抓取失败:{e}"
    if not text:
        return f"抓取失败:页面无可用正文({url})"
    return f"[web:{url}]\n{text[:WEB_FETCH_MAX_CHARS]}"

ALL_TOOLS = [search_knowledge_base,web_search,fetch_url]