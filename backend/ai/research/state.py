import operator
from typing import Annotated,TypedDict

class ResearchState(TypedDict):
    question:str
    user_id:str
    # 检索范围：kb=只查本人上传的文档 / web=只联网 / both=双路都跑（默认）
    scope:str
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
    
