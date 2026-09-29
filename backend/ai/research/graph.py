from langgraph.graph import StateGraph,START,END
from backend.ai.research.state import ResearchState
from backend.ai.research.node import search_node,analyze_node,write_node, critique_node, revise_node
from backend.config import MAX_REVISIONS

def critique_router(state: ResearchState) -> str:
    if state["verdict"] == "pass":
        return "done"
    # 硬上限：到顶就收，防振荡 + 防 GraphRecursionError
    if state["revision_count"] >= MAX_REVISIONS:
        return "done"  
    return "revise"

def build_graph():
    builder = StateGraph(ResearchState)
    builder.add_node("search",search_node)
    builder.add_node("analyze",analyze_node)
    builder.add_node("write",write_node)
    builder.add_node("critique", critique_node)
    builder.add_node("revise", revise_node)
    builder.add_edge(START,"search")
    builder.add_edge("search","analyze")
    builder.add_edge("analyze","write")
    builder.add_edge("write", "critique")
    builder.add_conditional_edges("critique",critique_router,{"revise":"revise","done":END})
    builder.add_edge("revise", "critique")
    return builder.compile()



