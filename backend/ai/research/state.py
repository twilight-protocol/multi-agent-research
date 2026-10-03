import operator
from typing import Annotated,TypedDict

class ResearchState(TypedDict):
    question:str
    # 检索范围限定用：由 api 层从 X-User-Id 取出后注入，图内部只读不写
    # 不放进 config.configurable，是因为 search_local 是普通函数（非 @tool），
    # 走 state 比引入 RunnableConfig / InjectedState 少一层概念
    user_id:str
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
    
