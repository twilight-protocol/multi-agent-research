from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from backend.ai.vectorstore import get_vectorstore

SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]

def load_pdf(path:Path,source_name:str)->list[Document]:
    pages: list[Document] = []
    for i,page in enumerate(PdfReader(str(path)).pages,start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        pages.append(
            Document(page_content=text,
                metadata={"source":source_name,"page":i}
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