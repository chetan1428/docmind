"""Agentic (corrective) RAG as a LangGraph state machine.

    START → retrieve → grade ─┬─(relevant docs)──────────────→ generate → END
                              ├─(none relevant, rewrites left)→ rewrite → retrieve
                              └─(nothing found)──────────────→ no_answer → END

- retrieve : pgvector similarity search
- grade    : fast Groq model keeps only passages that actually help
- rewrite  : fast Groq model turns the question into a better search query
- generate : main Groq model writes a cited answer from the relevant passages

With LLM_PROVIDER=extractive the same graph runs without an LLM: grading keeps
any passage with positive similarity, rewriting is skipped, and the answer is
extracted from the passages.
"""

import operator
from collections.abc import Callable
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.llm import (
    ANSWER_PROMPT,
    GRADE_PROMPT,
    REWRITE_PROMPT,
    extractive_answer,
    format_passages,
    get_answer_llm,
    get_fast_llm,
    message_text,
    parse_grades,
)

Retriever = Callable[[str, int], list[dict]]


class RAGState(TypedDict, total=False):
    question: str
    top_k: int
    search_query: str
    documents: list[dict]  # what retrieval returned
    relevant: list[dict]  # what survived grading
    rewrites: int
    answer: str
    steps: Annotated[list[str], operator.add]  # trace of nodes visited, shown in the UI


def build_graph(
    retriever: Retriever,
    answer_llm: BaseChatModel | None,
    fast_llm: BaseChatModel | None,
    max_rewrites: int = 1,
):
    def retrieve(state: RAGState) -> RAGState:
        query = state.get("search_query") or state["question"]
        return {"documents": retriever(query, state["top_k"]), "steps": ["retrieve"]}

    def grade(state: RAGState) -> RAGState:
        docs = state.get("documents", [])
        if not docs:
            return {"relevant": [], "steps": ["grade"]}
        if fast_llm is None:
            return {"relevant": [d for d in docs if d["score"] > 0], "steps": ["grade"]}
        msg = (GRADE_PROMPT | fast_llm).invoke(
            {"question": state["question"], "passages": format_passages(docs, max_chars=1200)}
        )
        keep = parse_grades(message_text(msg), len(docs))
        return {"relevant": [docs[i] for i in keep], "steps": ["grade"]}

    def rewrite(state: RAGState) -> RAGState:
        msg = (REWRITE_PROMPT | fast_llm).invoke({"question": state["question"]})
        query = message_text(msg).strip().strip('"') or state["question"]
        return {"search_query": query, "rewrites": state.get("rewrites", 0) + 1, "steps": ["rewrite"]}

    def generate(state: RAGState) -> RAGState:
        docs = state["relevant"]
        if answer_llm is None:
            answer = extractive_answer(state["question"], docs)
        else:
            msg = (ANSWER_PROMPT | answer_llm).invoke(
                {"question": state["question"], "context": format_passages(docs)}
            )
            answer = message_text(msg)
        return {"answer": answer, "steps": ["generate"]}

    def no_answer(state: RAGState) -> RAGState:
        if not state.get("documents"):
            answer = "No documents are indexed yet. Upload a document first."
        else:
            answer = "I couldn't find anything relevant to that in your documents."
        return {"answer": answer, "steps": ["no_answer"]}

    def route_after_grade(state: RAGState) -> str:
        if state.get("relevant"):
            return "generate"
        if fast_llm is not None and state.get("documents") and state.get("rewrites", 0) < max_rewrites:
            return "rewrite"
        return "no_answer"

    g = StateGraph(RAGState)
    g.add_node("retrieve", retrieve)
    g.add_node("grade", grade)
    g.add_node("rewrite", rewrite)
    g.add_node("generate", generate)
    g.add_node("no_answer", no_answer)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", route_after_grade, ["generate", "rewrite", "no_answer"])
    g.add_edge("rewrite", "retrieve")
    g.add_edge("generate", END)
    g.add_edge("no_answer", END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        from app.retrieval import search

        _graph = build_graph(search, get_answer_llm(), get_fast_llm(), settings.max_query_rewrites)
    return _graph


def run_rag(question: str, top_k: int) -> dict:
    result = get_graph().invoke({"question": question, "top_k": top_k, "rewrites": 0, "steps": []})
    return {
        "answer": result["answer"],
        "sources": result.get("relevant", []),
        "search_query": result.get("search_query") or question,
        "steps": result.get("steps", []),
    }
