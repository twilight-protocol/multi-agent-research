import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.ai.ingest import ingest_pdf
from backend.config import (
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_FILES,
    MAX_UPLOAD_MB,
    MAX_UPLOAD_TOTAL_BYTES,
    MAX_UPLOAD_TOTAL_MB,
    UPLOAD_DIR,
)
from backend.identity import current_user
from backend.ratelimit import upload_limiter

router = APIRouter(prefix="/api",tags=["upload"])
ALLOWED_SUFFIX = {".pdf"}

def _user_upload_dir(user_id:str) -> Path:
    """每个用户一个子目录：uploads/{user_id}/
    目录名来自已校验过的 user_id（只允许字母/数字/-/_），所以拼路径不会穿出去。
    """
    return UPLOAD_DIR / user_id

def _upload_usage(user_id:str) -> tuple[int,int]:
    """该用户上传目录的（文件数，总字节）。
    配额按用户算：全局计数的话，一个人传满别人就传不了，那是 DoS 而不是配额。
    """
    d = _user_upload_dir(user_id)
    if not d.is_dir():
        return 0,0
    files = list(d.glob("*.pdf"))
    return len(files),sum(f.stat().st_size for f in files)

@router.post("/upload",dependencies=[Depends(upload_limiter)])
async def upload_pdf(file:UploadFile=File(...),user_id:str=Depends(current_user)):
    filename =file.filename or ""
    if Path(filename).suffix.lower() not in ALLOWED_SUFFIX:
        raise HTTPException(status_code=400,detail="只支持 PDF 文件")
    user_dir = _user_upload_dir(user_id)
    user_dir.mkdir(parents=True,exist_ok=True)
    used_files,used_bytes = _upload_usage(user_id)
    if MAX_UPLOAD_FILES and used_files >= MAX_UPLOAD_FILES:
        raise HTTPException(status_code=413,detail=f"你的文件数已达上限（{MAX_UPLOAD_FILES} 个），请先清理")
    if MAX_UPLOAD_TOTAL_BYTES and used_bytes >= MAX_UPLOAD_TOTAL_BYTES:
        raise HTTPException(status_code=413,detail=f"你的存储已达上限（{MAX_UPLOAD_TOTAL_MB}MB），请先清理")
    stored:Path = user_dir / f"{uuid.uuid4().hex}.pdf"
    written = 0
    try:
        with stored.open("wb") as f:
            #边写边计数：上传流拿不到可靠的 Content-Length，只能写到超限就掐
            while chunk := await file.read(1024*1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=400,detail=f"文件超过 {MAX_UPLOAD_MB}MB 上限")
                #总量也要边写边判：落盘前的预估靠不住，这里用"已用+这次写入"做精确比较
                if MAX_UPLOAD_TOTAL_BYTES and used_bytes + written > MAX_UPLOAD_TOTAL_BYTES:
                    raise HTTPException(status_code=413,detail=f"你的存储已达上限（{MAX_UPLOAD_TOTAL_MB}MB），请先清理")
                f.write(chunk)
    except HTTPException:
        #超限：先删半截文件再往上抛，否则会被下面的 500 分支吞掉，前端只看到「服务器错误」
        stored.unlink(missing_ok=True)
        raise
    except Exception as e:
        raise HTTPException(status_code=500,detail=f"文件写入失败：{str(e)}")
    finally:
        await file.close()

    try:
        stat = await asyncio.to_thread(ingest_pdf,stored,filename,user_id)
    except Exception as e:
        #入库失败就别留孤儿文件，否则 uploads 里会攒一堆根本查不到的 PDF
        stored.unlink(missing_ok=True)
        raise HTTPException(status_code=500,detail=f"入库失败：{str(e)}")
    return {"file":filename,"stored_as":stored.name,**stat}