from backend.ai.research.graph import build_graph
from langchain_core.runnables import RunnableConfig
if __name__ == "__main__":
    app = build_graph()
    init = {
        "question": "华为开发者官网在哪", 
        "search_results": [], 
        "analysis": "", 
        "report":"",
        "critique": "",
        "issues": [],
        "verdict": "",
        "revision_count": 0
    }
    print("== stream 逐步增量 ==")
    for chunk in app.stream(init, stream_mode="updates"):
        print(chunk)