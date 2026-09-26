from langgraph.graph import StateGraph,START,END
from backend.ai.research.state import ResearchState
from backend.ai.research.node import search_node,analyze_node,write_node

def should_revise(state:ResearchState) -> str:
    return "revise" if state["revision_count"] < 2 else "done"

def build_graph():
    builder = StateGraph(ResearchState)
    builder.add_node("search",search_node)
    builder.add_node("analyze",analyze_node)
    builder.add_node("write",write_node)
    builder.add_edge(START,"search")
    builder.add_edge("search","analyze")
    builder.add_edge("analyze","write")
    builder.add_conditional_edges("write",should_revise,{"revise":"analyze","done":END})
    return builder.compile()



