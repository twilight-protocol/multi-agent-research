from fastapi import APIRouter

from backend.database import delete_conversation, get_messages, list_conversations

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
def list_sessions():
    return list_conversations()


@router.get("/{thread_id}")
def session_messages(thread_id: str):
    # 不存在的会话返回 []，不返回 404：
    # 前端 newThread() 后本地会占位一个还没落库的 thread_id，返回对象会让前端 rows.map 崩掉
    return get_messages(thread_id)


@router.delete("/{thread_id}")
def remove_session(thread_id: str):
    delete_conversation(thread_id)
    return {"deleted": thread_id}