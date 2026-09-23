import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from backend.ai.agent import graph
from backend.database import add_message,ensure_conversation
from backend.ratelimit import chat_limiter

#创建api路由
router = APIRouter(prefix="/api",tags=["chat"])

#模型请求
class ChatRequest(BaseModel):
    message:str
    thread_id: str = "default"

#SSE构造
def sse_frame(event:str,data:dict)-> str:
    #一个空行等于一帧，少换行就不触发onmessage
    #ensure_ascii=False防止中文转义
    return f"event:{event}\ndata:{json.dumps(data,ensure_ascii=False)}\n\n"

def save_partial(thread_id:str,parts:list[str],suffix:str)->None:
    """中断/失败时补写半截回答：保证 user/assistant 成对，UI 与 SQLite 不分叉。
    同步写（不进线程池）：生成器被取消后不能再 await，await 会再次抛 CancelledError 把写入丢掉。"""
    add_message(thread_id,"assistant","".join(parts)+suffix)

@router.post("/chat/stream",dependencies=[Depends(chat_limiter)])
async def chat_stream(req:ChatRequest):
    #同步SQLite写会占住事件循环，甩线程池（与upload.py同一套做法）
    await asyncio.to_thread(ensure_conversation,req.thread_id,req.message)
    await asyncio.to_thread(add_message,req.thread_id,"user",req.message)

    #闭包
    async def event_gen():
        cfg = {"configurable":{"thread_id":req.thread_id}}
        parts:list[str] = []
        saved = False
        try:
            async for chunk,meta in graph.astream(
                {"messages":[HumanMessage(content=req.message)]},
                cfg,
                stream_mode="messages"
            ):
                #过滤：只要model节点的输出
                if meta.get("langgraph_node") != "model":
                    continue
                #过滤空字符
                if not chunk.content:
                    continue
                parts.append(chunk.content)
                yield sse_frame("message",{"delta":chunk.content})
            #完整流结束后才落库
            await asyncio.to_thread(add_message,req.thread_id,"assistant","".join(parts))
            saved = True
            yield sse_frame("done",{"thread_id":req.thread_id})
        except Exception as e:
            #生成失败：半截回答也落库，否则 SQLite 只剩 user 一条（模型那边的上下文是完整一轮）
            save_partial(req.thread_id,parts,"…（生成失败）")
            saved = True
            yield sse_frame("error",{"detail":str(e)})
        finally:
            #客户端点「停止」或关页面 → CancelledError（BaseException，上面的 except 接不住）走这里
            if not saved:
                save_partial(req.thread_id,parts,"…（已中断）")
    return StreamingResponse(
        event_gen(),
        headers={
            #禁止浏览器\中间层缓存
            "Cache-Control":"no-cache",
            #禁止nginx缓冲响应体
            "x-Accel-Buffering":"no",
        },
        #SSE身份识别
        media_type="text/event-stream",
    )