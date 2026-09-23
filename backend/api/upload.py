import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.ai.ingest import ingest_pdf
from backend.config import MAX_UPLOAD_BYTES, MAX_UPLOAD_MB, UPLOAD_DIR
from backend.ratelimit import upload_limiter

router = APIRouter(prefix="/api",tags=["upload"])
ALLOWED_SUFFIX = {".pdf"}

@router.post("/upload",dependencies=[Depends(upload_limiter)])
async def upload_pdf(file:UploadFile=File(...)):
    filename =file.filename or ""
    if Path(filename).suffix.lower() not in ALLOWED_SUFFIX:
        raise HTTPException(status_code=400,detail="只支持 PDF 文件")
    UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
    stored:Path = UPLOAD_DIR / f"{uuid.uuid4().hex}.pdf"
    written = 0
    try:
        with stored.open("wb") as f:
            #边写边计数：上传流拿不到可靠的 Content-Length，只能写到超限就掐
            while chunk := await file.read(1024*1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=400,detail=f"文件超过 {MAX_UPLOAD_MB}MB 上限")
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
        stat = await asyncio.to_thread(ingest_pdf,stored,filename)
    except Exception as e:
        #入库失败就别留孤儿文件，否则 uploads 里会攒一堆根本查不到的 PDF
        stored.unlink(missing_ok=True)
        raise HTTPException(status_code=500,detail=f"入库失败：{str(e)}")
    return {"file":filename,"stored_as":stored.name,**stat}