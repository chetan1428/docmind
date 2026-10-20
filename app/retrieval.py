"""Vector search over pgvector."""

from sqlalchemy import select

from app.db import Chunk, Document, SessionLocal
from app.embeddings import embed_query


def search(query: str, top_k: int) -> list[dict]:
    qvec = embed_query(query)
    distance = Chunk.embedding.cosine_distance(qvec).label("distance")
    with SessionLocal() as session:
        rows = session.execute(
            select(Chunk, Document.filename, distance)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.status == "ready")
            .order_by(distance)
            .limit(top_k)
        ).all()
    return [
        {
            "document_id": c.document_id,
            "filename": fn,
            "chunk_index": c.idx,
            "text": c.text,
            "score": round(1 - float(dist), 4),
        }
        for c, fn, dist in rows
    ]
