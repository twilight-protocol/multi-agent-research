from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.memory import InMemorySaver
from backend.ai.research.state import ResearchState
from backend.ai.research.node import search_node,analyze_node,write_node, critique_node, revise_node,human_review_node
from backend.config import MAX_REVISIONS,HUMAN_REVIEW_MODE,HUMAN_EXTRA_REVISIONS

def critique_router(state: ResearchState) -> str:
    if state["verdict"] != "pass" and state["revision_count"] < MAX_REVISIONS:
        return "revise"
    if state["verdict"] == "pass" and HUMAN_REVIEW_MODE != "always":
        return "done"  
    return "human"

def human_router(state:ResearchState)->str:
    return "done" if state.get("human_action") == "approve" else "revise"

def revise_router(state:ResearchState)->str:
    if state["revision_count"] >= MAX_REVISIONS + HUMAN_EXTRA_REVISIONS:
        return "done"
    if state["revision_count"] >= MAX_REVISIONS:
        return "human"
    return "critique"

def build_graph():
    builder = StateGraph(ResearchState)
    builder.add_node("search",search_node)
    builder.add_node("analyze",analyze_node)
    builder.add_node("write",write_node)
    builder.add_node("critique", critique_node)
    builder.add_node("revise", revise_node)
    builder.add_node("human_review",human_review_node)
    builder.add_edge(START,"search")
    builder.add_edge("search","analyze")
    builder.add_edge("analyze","write")
    builder.add_edge("write", "critique")
    builder.add_conditional_edges("critique",critique_router,{"revise":"revise","human":"human_review","done":END})
    builder.add_conditional_edges("human_review",human_router,{"revise":"revise","done":END})
    builder.add_conditional_edges("revise",revise_router,{"critique":"critique","human":"human_review","done":END})
    return builder.compile(checkpointer=InMemorySaver())



