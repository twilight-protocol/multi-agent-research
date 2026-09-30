from backend.ai.research.state import ResearchState
from backend.ai.vectorstore import get_vectorstore
from backend.config import RAG_TOP_K, MAX_DISTANCE,MAX_REVISIONS
from backend.ai.research.tools import web_search
from backend.ai.llm import llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.types import interrupt
from pydantic import BaseModel, Field
from typing import Literal

def search_node(state:ResearchState):
    blocks: list[str] = []

    hits = get_vectorstore().similarity_search_with_score(state["question"],k=RAG_TOP_K)
    kept = [(d,s) for d,s in hits if s <= MAX_DISTANCE]
    blocks.extend(
        f"[{doc.metadata.get('source','未知文档')} 第{doc.metadata.get('page','?')}页]\n{doc.page_content}"
        for doc,_score in kept
    )

    web = web_search.invoke({"query":state["question"]})
    if not web.startswith(("搜索失败","未搜索到")):
        blocks.extend(web.split("\n\n---\n\n"))

    return {"search_results":blocks}

ANALYZE_PROMPT = (
    "你是资料分析师。仅依据下列检索片段回答，禁止使用片段之外的知识，"
    "禁止编造。输出格式：1) 要点清单（每条末尾标 [片段编号]）2) 矛盾或不确定处 3) 信息缺口。"
    "若片段为空，只输出「资料不足」并说明缺什么，不要臆测。"
)

low_llm = llm.bind(temperature = 0.2)

analyze_prompt = ChatPromptTemplate.from_messages([
    ("system",ANALYZE_PROMPT),
    ("user","\n\n搜索结果:{search_results}\n\n问题:{question}\n\n"),
])

analyze_lcel = analyze_prompt | low_llm | StrOutputParser()

def analyze_node(state:ResearchState):
    blocks = "\n\n---\n\n".join(state["search_results"]) or "（本轮无检索片段）"
    analysis = analyze_lcel.invoke({
        "search_results":blocks,
        "question":state["question"]
    })
    return {"analysis":analysis}

REPORT_PROMPT = (
    "你是行业研究员。基于分析笔记撰写结构化报告。"
    "每条关键发现若在笔记中有 [文件名 第N页] 或 [web: url] 出处，"
    "必须原样放进该条的 evidence 字段，不得新增笔记之外的出处，也不要把出处写进 point。"
)

class Finding(BaseModel):
    point:str = Field(description="一条关键发现，一到两句话")
    evidence:list[str] = Field(
        default_factory=list,
        description="支撑该发现的出处，必须原样引用 [文件名 第N页] 或 [web: url]；没有出处就留空数组"
    )
class ReportSchema(BaseModel):
    summary: str = Field(description="概述，3~5 句")
    findings: list[Finding] = Field(description="关键发现，3~6 条")
    conclusion: str = Field(description="结论")

report_prompt = ChatPromptTemplate.from_messages([
    ("system",REPORT_PROMPT),
    ("user","\n\n分析笔记:{analysis}\n\n问题:{question}\n\n"),
])

report_lcel = report_prompt | low_llm.with_structured_output(ReportSchema)

def _render_report(report:ReportSchema) -> str:
    lines = ["## 概述",report.summary,"","## 关键发现"]
    for f in report.findings:
        evidence = " ".join(f.evidence)
        lines.append(f"- {f.point}" + (f" {evidence}" if evidence else ""))
    lines += ["","## 结论",report.conclusion]
    return "\n".join(lines)

def write_node(state:ResearchState):
    report = report_lcel.invoke({
        "question":state["question"],
        "analysis":state["analysis"]
    })
    return {"report":_render_report(report)}

CRITIQUE_PROMPT = (
    "你是严格的审稿人，只做审查，绝不重写。逐条核对草稿是否真的被检索片段支撑。"
    "只检查三类硬问题："
    "① 断言无出处：关键发现没有任何 [文件名 第N页] 或 [web: url] 支撑；"
    "② 出处与断言不符：所引片段其实不支持该结论；"
    "③ 覆盖不足：分析笔记里已写明的矛盾或信息缺口，报告完全没提。"
    "禁止提出风格类意见（措辞、篇幅、排版）。每条意见必须给出可执行的修改动作，"
    "让别人不看原稿就能照做。三类问题都不存在时，verdict 必须为 pass 且 issues 为空数组。"
)

class CritiqueItem(BaseModel):
    target:str = Field(description="问题位置:概述 / findings[0] / findings[1] …… / 结论")
    problem:str = Field(description="属于哪一类：断言无出处 / 出处不符 / 覆盖不足")
    fix:str = Field(description="具体修改动作，一句话，可执行")

class CritiqueSchema(BaseModel):
    verdict:Literal["pass","revise"] = Field(description="pass=可直接发布；revise=必须先改")
    issues:list[CritiqueItem] = Field(
        default_factory=list,description="按严重度降序，最多 5 条；verdict 为 pass 时必须为空"
    )

critique_prompt = ChatPromptTemplate.from_messages([
    ("system",CRITIQUE_PROMPT),
    ("user","\n\n分析笔记:{analysis}\n\n草稿:{report}\n\n问题:{question}\n\n")
])

critique_llm = llm.bind(temperature=0)

critique_lcel = critique_prompt | critique_llm.with_structured_output(CritiqueSchema)

def critique_node(state:ResearchState):
    result = critique_lcel.invoke({
        "question":state["question"],
        "analysis":state["analysis"],
        "report":state["report"],
    })
    issues = [f"[{it.target}] {it.problem} -> {it.fix}"for it in result.issues]
    if not issues:
        return {"verdict":"pass","issues":[],"critique":"审查未发现需要修改的问题","stop_reason":"passed"}
    if result.verdict == "pass":
        return {"verdict":"pass","issues":[],"critique":"审查通过（已忽略非阻塞建议）","stop_reason":"passed"}
    return {"verdict":"revise","issues":issues,"critique":"\n".join(issues)}

REVISE_PROMPT = (
    "你是报告作者。只针对审查清单逐条修改草稿，清单之外的句子保持原样，不要顺手改写。"
    "修改优先选：为断言补上分析笔记里已有的出处；若笔记里也无出处可补，"
    "就删掉该断言，或降级写成「尚无资料支持」。"
    "禁止新增分析笔记之外的出处，禁止新增清单之外的内容。"
    "只输出 Markdown 报告正文，包含 ## 概述 / ## 关键发现 / ## 结论 三个标题，"
    "不要任何前言、解释或结束语。"
)

revise_prompt = ChatPromptTemplate.from_messages([
    ("system", REVISE_PROMPT),
    ("user",
     "\n\n分析笔记:{analysis}\n\n草稿:{report}\n\n审查清单:{issues}\n\n问题:{question}\n\n"),
])

revise_lcel = revise_prompt | low_llm | StrOutputParser()

def revise_node(state: ResearchState):
    report = revise_lcel.invoke({
        "question": state["question"],
        "analysis": state["analysis"],
        "report": state["report"],
        "issues": "\n".join(state["issues"]),
    })
    count = state["revision_count"] + 1
    return {
        "report": report,
        "revision_count": count,
        "stop_reason":"limit_reached" if count >= MAX_REVISIONS else state.get("stop_reason","")
    }

def human_review_node(state:ResearchState)->dict:
    decision = interrupt({
        "type":"draft_review",
        "question":state["question"],
        "draft":state["report"],
        "limit_reached": state["revision_count"] >= MAX_REVISIONS,
        "expect":'{"action":"approve" | "revise", "comment":"修改要求"}'

    })

    #防呆
    action = (decision or {}).get("action") or "approve"
    comment = ((decision or {}).get("comment") or "").strip()

    if action != "approve" and comment:
        return{
            "human_action":"revise",
            "human_feedback":comment,
            "issues":[f"[人工]{comment}"],
        }
    return  {"human_action":"approve","human_feedback":comment}