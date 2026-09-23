from langchain_core.messages import HumanMessage,SystemMessage
from langgraph.graph import StateGraph,MessagesState,START,END
from langgraph.checkpoint.memory import InMemorySaver
from backend.ai.llm import llm
from langgraph.prebuilt import ToolNode, tools_condition
from backend.ai.tools import ALL_TOOLS

SYSTEM_PROMPT = """你是一个 AI 知识助手，回答简洁准确。

硬规则：
1. 涉及上传文档中的注册/认证/账号/配置/流程/操作步骤/条款/参数等具体问题，
   必须先调用 search_knowledge_base 查证，禁止凭记忆回答。
2. 回答必须以文档内容为唯一依据，并标注出处（文件名 + 页码）。
3. 工具未检索到内容时，直接回答「文档中未提及」，不要编造。"""

llm_with_tools = llm.bind_tools(ALL_TOOLS)

#调用模型并添加信息
async def call_model(state:MessagesState):
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages":[response]}

#建图
builder = StateGraph(MessagesState)
builder.add_node("model",call_model)
builder.add_node("tools",ToolNode(ALL_TOOLS))
builder.add_edge(START,"model")
builder.add_conditional_edges("model", tools_condition) 
builder.add_edge("tools", "model")   

#编译
graph = builder.compile(checkpointer=InMemorySaver())

