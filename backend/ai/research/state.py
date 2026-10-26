import operator
from typing import Annotated,TypedDict

class ResearchState(TypedDict):
    question:str
    user_id:str
    # 检索范围：kb=只查本人上传的文档 / web=只联网 / both=双路都跑（默认）
    scope:str
    # 检索侧的降级说明（例如「联网检索未生效：未配置 TAVILY_API_KEY」）。
    # 不能只写日志：用户看不到日志，只会看到「报告里没有网址」，然后把锅算到模型头上。
    search_note:str
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
    
