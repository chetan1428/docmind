"""LLM setup (Groq via LangChain), prompts, and the offline extractive fallback."""

import re
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.embeddings import tokenize

# ---------- Prompts ----------
GRADE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You judge whether retrieved passages help answer a question. "
            "Reply with ONLY the numbers of the useful passages, comma-separated (e.g. 1,3). "
            "If none are useful, reply with the single word: none",
        ),
        ("human", "Question: {question}\n\nPassages:\n{passages}"),
    ]
)

REWRITE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Rewrite the user's question into a short keyword-rich search query that is more "
            "likely to match technical documentation. Reply with ONLY the query.",
        ),
        ("human", "{question}"),
    ]
)

ANSWER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are DocMind, an assistant that answers questions using ONLY the provided context. "
            "If the answer is not in the context, say you don't know. "
            "Cite sources with their numbers like [1] or [2]. Be concise.",
        ),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ]
)


# ---------- Models ----------
@lru_cache
def get_answer_llm() -> BaseChatModel | None:
    return _groq(settings.groq_model)


@lru_cache
def get_fast_llm() -> BaseChatModel | None:
    return _groq(settings.groq_fast_model)


def _groq(model: str) -> BaseChatModel | None:
    if settings.llm_provider != "groq":
        return None
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY is required when LLM_PROVIDER=groq (or set LLM_PROVIDER=extractive)")
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=model,
        api_key=settings.groq_api_key,
        temperature=settings.llm_temperature,
        max_retries=2,
        timeout=30,
    )


# ---------- Helpers ----------
def message_text(msg: BaseMessage) -> str:
    content = msg.content
    if isinstance(content, list):
        content = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content).strip()


def format_passages(docs: list[dict], max_chars: int | None = None) -> str:
    return "\n\n".join(
        f"[{i}] ({d['filename']})\n{d['text'][:max_chars] if max_chars else d['text']}"
        for i, d in enumerate(docs, 1)
    )


def parse_grades(text: str, n: int) -> list[int]:
    """'1, 3' -> [0, 2] (0-based); 'none' -> []."""
    if "none" in text.lower() and not re.search(r"\d", text):
        return []
    seen: list[int] = []
    for num in re.findall(r"\d+", text):
        i = int(num) - 1
        if 0 <= i < n and i not in seen:
            seen.append(i)
    return sorted(seen)


# ---------- Offline fallback ----------
_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def extractive_answer(question: str, contexts: list[dict], max_sentences: int = 3) -> str:
    q_tokens = set(tokenize(question))
    scored = []
    for ci, ctx in enumerate(contexts, 1):
        for si, sent in enumerate(_SENT_RE.split(ctx["text"])):
            overlap = len(q_tokens & set(tokenize(sent)))
            if overlap:
                scored.append((overlap, -ci, -si, sent.strip(), ci))
    if not scored:
        return "I couldn't find anything relevant to that in your documents."
    best = sorted(scored, reverse=True)[:max_sentences]
    return " ".join(f"{sent} [{ci}]" for *_, sent, ci in best)
