import operator
from typing import Annotated,TypedDict

class ResearchState(TypedDict):
    question:str
    #多节点累加：默认是覆盖
    search_results:Annotated[list[str],operator.add]
    analysis:str
    report:str
    critique:str
    issues:list[str]
    verdict:str
    revision_count:int
    human_action:str
    human_feedback:str
    stop_reason:str
    
