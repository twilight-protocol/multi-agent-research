from backend.ai.research.state import ResearchState
def search_node(state:ResearchState):
    return {"search_results":[f"关于{state['question']}的检索结果1"]}
def analyze_node(state:ResearchState):
    return {"draft":f"基于{len(state['search_results'])}条结果的分析草稿"}
def write_node(state:ResearchState):
    return {"revision_count":state["revision_count"] + 1}
