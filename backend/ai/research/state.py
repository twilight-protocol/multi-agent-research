import operator
from typing import Annotated,TypedDict

class ResearchState(TypedDict):
    question:str
    # 检索范围限定用：由 api 层从 X-User-Id 取出后注入，图内部只读不写
    # 不放进 config.configurable，是因为 search_local 是普通函数（非 @tool），
    # 走 state 比引入 RunnableConfig / InjectedState 少一层概念
    user_id:str
    # 检索范围：kb=只查本人上传的文档 / web=只联网 / both=双路都跑（默认）
    # 由 api 层注入，search_node 只读；放 state 而不是 config，理由同上
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
    
