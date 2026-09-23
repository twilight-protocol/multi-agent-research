"""SQLite 持久化层：会话与消息。"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

from backend.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    thread_id  TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '新对话',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id  TEXT NOT NULL,
    role       TEXT NOT NULL,          -- user / assistant
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id, id);
"""


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def _connect():
    """每次调用新建连接；正常结束自动 commit，异常自动 rollback。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """建表。应用启动时调一次，可重复执行。"""
    with _connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)


def ensure_conversation(thread_id: str, first_message: str = "") -> None:
    """会话不存在则创建；标题取首条用户消息前 20 字。已存在则不动（INSERT OR IGNORE）。"""
    title = first_message.strip().replace("\n", " ")[:20] or "新对话"
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO conversations(thread_id, title, created_at, updated_at)"
            " VALUES (?, ?, ?, ?)",
            (thread_id, title, _now(), _now()),
        )


def add_message(thread_id: str, role: str, content: str) -> int:
    """写入一条消息，并刷新会话的 updated_at（会话列表按此倒序）。"""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO messages(thread_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (thread_id, role, content, _now()),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE thread_id = ?",
            (_now(), thread_id),
        )
        return int(cur.lastrowid or 0)


def list_conversations() -> list[dict]:
    """会话列表，按最后活跃时间倒序，附带消息条数。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT c.thread_id, c.title, c.created_at, c.updated_at,"
            " (SELECT COUNT(*) FROM messages m WHERE m.thread_id = c.thread_id) AS message_count"
            " FROM conversations c ORDER BY c.updated_at DESC, c.created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_messages(thread_id: str) -> list[dict]:
    """某个会话的全部消息，按写入顺序。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM messages"
            " WHERE thread_id = ? ORDER BY id",
            (thread_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_conversation(thread_id: str) -> None:
    """删除会话及其消息。注意：不清 LangGraph checkpointer 里的上下文（两条数据线各自独立）。"""
    with _connect() as conn:
        conn.execute("DELETE FROM messages WHERE thread_id = ?", (thread_id,))
        conn.execute("DELETE FROM conversations WHERE thread_id = ?", (thread_id,))
