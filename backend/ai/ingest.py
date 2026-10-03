import time
from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from backend.ai.vectorstore import get_vectorstore
from backend.config import ORPHAN_GRACE_SECONDS, ORPHAN_CLEANUP_ON_START, UPLOAD_DIR

SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]

def load_pdf(path:Path,source_name:str)->list[Document]:
    pages: list[Document] = []
    for i,page in enumerate(PdfReader(str(path)).pages,start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        pages.append(
            Document(page_content=text,
                # source 给用户看（引用渲染成「test.pdf 第3页」），stored 给代码用（定位磁盘上的 UUID 文件）
                # 少了 stored 就没法把「向量库里的 chunk」和「uploads 里的文件」对上，孤儿清理无从判定
                metadata={"source":source_name,"page":i,"stored":path.name}
            )
        )
    return pages

def ingest_pdf(path:Path,source_name:str) -> dict:
    pages = load_pdf(path,source_name)
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80,
        separators=SEPARATORS,
    ).split_documents(pages)

    vs = get_vectorstore()
    #重复上传防护
    vs.delete(where={"source":source_name})
    if chunks:
        vs.add_documents(chunks)
    return {"pages":len(pages),"chunks":len(chunks)}


def _referenced_stored_names() -> set[str] | None:
    """向量库里所有 chunk 引用的磁盘文件名。

    返回 None = 「存量数据太旧、判不了」，调用方必须放弃清理而不是猜。
    """
    metas = get_vectorstore().get(include=["metadatas"]).get("metadatas") or []
    if not metas:
        # 空库：uploads 里不该有文件（有就是孤儿），此时"引用了 0 个"是准确答案
        return set()
    if any("stored" not in m for m in metas):
        return None
    return {m["stored"] for m in metas}


def sweep_orphan_uploads() -> dict:
    """启动时扫一次 uploads/，删掉向量库已不再引用的 PDF。

    孤儿从哪来：向量库的「文档主键」是原始文件名——同名再传会先 delete 再 add，
    旧 chunk 没了，磁盘上那个 UUID 文件还在，没人引用也没人删。
    实测就发生过：同一份 test.pdf 传两次，库里仍是 27 条，uploads 里躺着 2 个 2.68MB 的文件。

    三条保守规则（宁可留着也不误删）：
    ① 库里存在任何一条没有 stored 的旧 chunk → 整轮跳过
    ② 改动时间在 ORPHAN_GRACE_SECONDS 以内的不碰（可能正落盘 / 正在入库）
    ③ 删除结果回传调用方记日志，事后能对上账
    """
    if not ORPHAN_CLEANUP_ON_START:
        return {"skipped": "ORPHAN_CLEANUP_ON_START=false"}

    upload_dir = Path(UPLOAD_DIR)
    if not upload_dir.is_dir():
        return {"scanned": 0, "deleted": []}

    files = sorted(upload_dir.glob("*.pdf"))
    if not files:
        return {"scanned": 0, "deleted": []}

    referenced = _referenced_stored_names()
    if referenced is None:
        return {
            "scanned": len(files),
            "deleted": [],
            "skipped": "库中存在无 stored 字段的旧 chunk，整轮跳过（重传一次该 PDF 即可启用）",
        }

    now = time.time()
    deleted: list[str] = []
    for f in files:
        if f.name in referenced:
            continue
        if now - f.stat().st_mtime < ORPHAN_GRACE_SECONDS:
            continue
        f.unlink(missing_ok=True)
        deleted.append(f.name)
    return {"scanned": len(files), "referenced": len(referenced), "deleted": deleted}