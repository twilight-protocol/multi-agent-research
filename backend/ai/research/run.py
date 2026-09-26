from backend.ai.research.graph import build_graph
from backend.ai.research.state import ResearchState
if __name__ == "__main__":
    app = build_graph()
    init = {"question": "RAG 是什么", "search_results": [], "draft": "", "revision_count": 0}
    print("== invoke 最终状态 ==", app.invoke(init))
    print("== stream 逐步增量 ==")
    for chunk in app.stream(init, stream_mode="updates"):
        print(chunk)