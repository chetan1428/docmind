"""LangGraph pipeline tests with fake LLMs: no Groq key, DB or network needed."""

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.rag_graph import build_graph

DOC = {
    "document_id": 1,
    "filename": "k8s.md",
    "chunk_index": 0,
    "text": "A readiness probe tells Kubernetes whether a pod can receive traffic.",
    "score": 0.42,
}


class FakeRetriever:
    def __init__(self, docs):
        self.docs = docs
        self.queries = []

    def __call__(self, query, top_k):
        self.queries.append(query)
        return self.docs


def run(graph, question="what is a readiness probe?"):
    return graph.invoke({"question": question, "top_k": 4, "rewrites": 0, "steps": []})


def test_extractive_mode_happy_path():
    out = run(build_graph(FakeRetriever([DOC]), None, None))
    assert out["steps"] == ["retrieve", "grade", "generate"]
    assert "readiness probe" in out["answer"]


def test_empty_corpus_goes_to_no_answer():
    fast = FakeListChatModel(responses=["unused"])
    out = run(build_graph(FakeRetriever([]), None, fast))
    assert out["steps"] == ["retrieve", "grade", "no_answer"]
    assert "No documents" in out["answer"]


def test_llm_rewrites_query_when_nothing_relevant_then_answers():
    retriever = FakeRetriever([DOC])
    fast = FakeListChatModel(responses=["none", "kubernetes readiness probe", "1"])
    answer = FakeListChatModel(responses=["It decides if a pod gets traffic [1]."])
    out = run(build_graph(retriever, answer, fast, max_rewrites=1))

    assert out["steps"] == ["retrieve", "grade", "rewrite", "retrieve", "grade", "generate"]
    assert retriever.queries == ["what is a readiness probe?", "kubernetes readiness probe"]
    assert out["search_query"] == "kubernetes readiness probe"
    assert out["relevant"] == [DOC]
    assert out["answer"] == "It decides if a pod gets traffic [1]."


def test_llm_gives_up_after_max_rewrites():
    fast = FakeListChatModel(responses=["none", "better query", "none"])
    answer = FakeListChatModel(responses=["should not be called"])
    out = run(build_graph(FakeRetriever([DOC]), answer, fast, max_rewrites=1))
    assert out["steps"][-1] == "no_answer"
    assert out["steps"].count("rewrite") == 1
