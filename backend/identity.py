import re

from fastapi import Header, HTTPException

# 只允许 uuid 形态：8~64 位字母/数字/-/_，挡住路径穿越（"../x"）和空值
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def current_user(x_user_id: str = Header(default="", alias="X-User-Id")) -> str:
    """FastAPI 依赖：从请求头取出用户标识。"""
    uid = x_user_id.strip()
    if not _USER_ID_RE.match(uid):
        # 400 而不是 401：这不是「认证失败」，是「没按要求带标识」
        raise HTTPException(
            status_code=400,
            detail="缺少或非法的 X-User-Id（8~64 位字母/数字/-/_）",
        )
    return uid
