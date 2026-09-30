from backend.ai.research.graph import build_graph
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

app = build_graph()

def new_thread(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}

if __name__ == "__main__":
    cfg = new_thread("day31")
    init = {
        "question": "华为开发者官网在哪", 
        "search_results": [], 
        "analysis": "", 
        "report":"",
        "critique": "",
        "issues": [],
        "verdict": "",
        "revision_count": 0,
        "human_action": "",
        "human_feedback": "",
    }
    print("== 阶段1：跑到人工介入点 ==")
    for chunk in app.stream(init, cfg, stream_mode="updates"):
        print(chunk)
    print("== 阶段2：人工输入后恢复（同一进程内）==")
    decision = {"action": "approve", "comment": ""}
    for chunk in app.stream(Command(resume=decision), cfg, stream_mode="updates"):
        print(chunk)
