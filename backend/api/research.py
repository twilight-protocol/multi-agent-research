import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel

from backend.ai.research.service import get_graph
from backend.identity import current_user
from backend.ratelimit import research_limiter

router = APIRouter(prefix="/api/research", tags=["research"])

NODE_LABEL = {
    "search": "正在检索（本地知识库 + 联网）",
    "analyze": "正在分析资料",
    "write": "正在撰写报告",
    "critique": "正在自审",
    "revise": "正在按审查意见修订",
    "human_review": "等待人工终审",
}


def sse_frame(event: str, data: dict) -> str:
    """一个空行 = 一帧；ensure_ascii=False 防止中文被转义"""
    return f"event:{event}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n"


class ResearchRequest(BaseModel):
    question: str
    #前端可复用自己生成的 thread_id（多标签页/刷新后接着看）；不传则后端发一个
    thread_id: str = ""


class ResumeRequest(BaseModel):
    thread_id: str
    action: str = "approve"      # approve | revise，与 human_review_node 的取值约定一致
    comment: str = ""


def _init_state(question: str, user_id: str) -> dict:
    return {
        "question": question,
        # 检索范围：search_node 只用自己这个用户的文档
        "user_id": user_id,
        "search_results": [],
        "analysis": "",
        "report": "",
        "critique": "",
        "issues": [],
        "verdict": "",
        "revision_count": 0,
        "human_action": "",
        "human_feedback": "",
        "stop_reason": "",
    }


def scoped_thread_id(user_id: str, raw: str) -> str:
    """把用户归属编进 thread_id："{user_id}:{raw}"。

    为什么不用「查表看这个 thread 属于谁」：checkpointer 的键就是 thread_id，
    前缀法把归属变成**可从 ID 直接判定**的属性，不需要额外查询，也不可能漏改。
    代价：ID 变长，且换用户就找不回旧会话（这本来就是期望行为）。
    """
    return f"{user_id}:{raw}"


def _require_own_thread(user_id: str, thread_id: str) -> None:
    """resume 前校验归属：别人的 thread_id 一概拒绝。"""
    if not thread_id.startswith(f"{user_id}:"):
        raise HTTPException(status_code=403, detail="无权访问该会话")


async def _stream(graph_input, thread_id: str):
    graph = get_graph()          
    cfg = {"configurable": {"thread_id": thread_id}}
    try:
        async for chunk in graph.astream(graph_input, cfg, stream_mode="updates"):
            if "__interrupt__" in chunk:
                st = await graph.aget_state(cfg)
                yield sse_frame("interrupt", {
                    **chunk["__interrupt__"][0].value,
                    #必须回传 thread_id：前端手上那份是「未加前缀的原始 id」，
                    #拿它去 /resume 会被 403 挡住（多租户后才有的坑）
                    "thread_id": thread_id,
                    "issues": st.values.get("issues", []),
                    "revision_count": st.values.get("revision_count", 0),
                    "stop_reason": st.values.get("stop_reason", ""),
                })
                return
            for node in chunk:
                yield sse_frame("progress", {"node": node, "label": NODE_LABEL.get(node, node)})
        #没中断 = 图自己走到 END（人已签字，或 HUMAN_REVIEW_MODE 没开 always）
        state = await graph.aget_state(cfg)
        yield sse_frame("done", {
            "thread_id": thread_id,
            "report": state.values.get("report", ""),
            #前端靠这两个字段显示「审查通过 / AI 额度用尽待放行」，不是重复信息
            "stop_reason": state.values.get("stop_reason", ""),
            "revision_count": state.values.get("revision_count", 0),
        })
    except Exception as e:
        yield sse_frame("error", {"detail": str(e)})


@router.post("/stream", dependencies=[Depends(research_limiter)])
async def research_stream(req: ResearchRequest, user_id: str = Depends(current_user)):
    raw = req.thread_id.strip() or uuid.uuid4().hex[:12]
    thread_id = scoped_thread_id(user_id, raw)
    return StreamingResponse(
        _stream(_init_state(req.question, user_id), thread_id),
        headers={"Cache-Control": "no-cache", "x-Accel-Buffering": "no"},
        media_type="text/event-stream",
    )


@router.post("/resume", dependencies=[Depends(research_limiter)])
async def research_resume(req: ResumeRequest, user_id: str = Depends(current_user)):
    _require_own_thread(user_id, req.thread_id)
    decision = {"action": req.action, "comment": req.comment}
    # 不需要重新注入 user_id：state 里那份已经落在 checkpoint 里了，
    # resume 时 LangGraph 会把断点状态整个恢复（所以校验归属才是必需的，
    # 否则拿到别人的 thread_id 就能读别人的状态）
    return StreamingResponse(
        _stream(Command(resume=decision), req.thread_id),
        headers={"Cache-Control": "no-cache", "x-Accel-Buffering": "no"},
        media_type="text/event-stream",
    )


