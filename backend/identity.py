"""用户身份：只做「数据归属」，不做「权限校验」。

为什么不用登录：本项目是单实例 Demo，没有用户表、没有密码、没有 token 签发。
客户端首次访问时生成一个 uuid 存在 localStorage，之后每个请求用 X-User-Id 头带上。
后端只负责校验格式 + 把它当作「数据归属标签」写进向量库 / 上传目录 / thread_id。

⚠️ 这不是安全边界：header 是客户端自报的，改一下就能冒充别人。
   要真隔离，得改成服务端签发并校验的凭证（JWT / session）。面试口径见 面试台账.md §5.3.3。
"""
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
