import time
from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from backend.ai.vectorstore import get_vectorstore
from backend.config import ORPHAN_GRACE_SECONDS, ORPHAN_CLEANUP_ON_START, UPLOAD_DIR

SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]

def load_pdf(path:Path,source_name:str,user_id:str)->list[Document]:
    pages: list[Document] = []
    for i,page in enumerate(PdfReader(str(path)).pages,start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        pages.append(
            Document(page_content=text,
                # 三个 metadata 各有分工：
                #   source/user_id → 检索范围与引用渲染（「test.pdf 第3页」）
                #   stored         → 定位磁盘上的 UUID 文件，孤儿清理靠它对齐
                metadata={"source":source_name,"page":i,"stored":path.name,"user_id":user_id}
            )
        )
    return pages

def ingest_pdf(path:Path,source_name:str,user_id:str) -> dict:
    pages = load_pdf(path,source_name,user_id)
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80,
        separators=SEPARATORS,
    ).split_documents(pages)

    vs = get_vectorstore()
    #重复上传防护：必须先删后加，否则同名重传会变成两份（54 条）
    #⚠️ 这里必须用 $and 同时限定 source 和 user_id ——
    #   只按 source 删的话，A 重传自己的 test.pdf 会把 B 的 test.pdf 一起删掉，隔离就是假的
    vs.delete(where={"$and":[{"source":source_name},{"user_id":user_id}]})
    if chunks:
        vs.add_documents(chunks)
    return {"pages":len(pages),"chunks":len(chunks)}


def _referenced_stored_names() -> set[str] | None:
    """向量库里所有 chunk 引用的磁盘文件名。

    返回 None = 「判不了，放弃清理」。两种情况都返回 None：
      ① 存量 chunk 缺 stored 字段（旧格式）
      ② 库里一条都没有 —— 此时"引用了 0 个"会把 uploads 里所有文件都判成孤儿，
         万一 collection 被改名/重建过，就会变成一次批量误删。宁可不清。
    调用方必须放弃清理而不是猜。
    """
    metas = get_vectorstore().get(include=["metadatas"]).get("metadatas") or []
    if any("stored" not in m for m in metas):
        return None
    return {m["stored"] for m in metas} if metas else None


def sweep_orphan_uploads() -> dict:
    """启动时扫一次 uploads/（含各用户子目录），删掉向量库已不再引用的 PDF。

    孤儿从哪来：向量库的「文档主键」是「原始文件名 + 用户」——同名再传会先 delete 再 add，
    旧 chunk 没了，磁盘上那个 UUID 文件还在，没人引用也没人删。
    实测就发生过：同一份 test.pdf 传两次，库里仍是 27 条，uploads 里躺着 2 个 2.68MB 的文件。

    三条保守规则（宁可留着也不误删）：
    ① 库里存在任何一条没有 stored 的旧 chunk → 整轮跳过
    ② 改动时间在 ORPHAN_GRACE_SECONDS 以内的不碰（可能正落盘 / 正在入库）
    ③ 删除结果回传调用方记日志，事后能对上账

    注意：只按文件名做匹配，不做「目录 ↔ user_id」交叉校验——
    存盘名是 uuid4，全局唯一，跨用户撞名不可能；万一将来撞上，代价只是多留一个文件。
    """
    if not ORPHAN_CLEANUP_ON_START:
        return {"skipped": "ORPHAN_CLEANUP_ON_START=false"}

    upload_dir = Path(UPLOAD_DIR)
    if not upload_dir.is_dir():
        return {"scanned": 0, "deleted": []}

    # rglob：多租户后文件在 uploads/{user_id}/ 下面
    files = sorted(upload_dir.rglob("*.pdf"))
    if not files:
        return {"scanned": 0, "deleted": []}

    referenced = _referenced_stored_names()
    if referenced is None:
        return {
            "scanned": len(files),
            "deleted": [],
            "skipped": "库为空或存在无 stored 字段的旧 chunk，整轮跳过（重传一次该 PDF 即可启用）",
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