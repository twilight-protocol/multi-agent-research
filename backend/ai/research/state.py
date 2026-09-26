import operator
from typing import Annotated,TypedDict

class ResearchState(TypedDict):
    question:str
    #多节点累加：默认是覆盖
    search_results:Annotated[list[str],operator.add]
    draft:str
    revision_count:int
