"""Background jobs, executed by the worker process (not the API)."""

import logging

from app.cache import bump_corpus_version
from app.chunking import chunk_text
from app.config import settings
from app.db import Chunk, Document, SessionLocal
from app.embeddings import embed_texts

log = logging.getLogger(__name__)


def ingest_document(document_id: int) -> int:
    """Chunk + embed a document and store vectors. Returns number of chunks."""
    with SessionLocal() as session:
        doc = session.get(Document, document_id)
        if doc is None:
            log.warning("Document %s no longer exists, skipping", document_id)
            return 0
        doc.status = "processing"
        session.commit()

        try:
            pieces = chunk_text(doc.content, settings.chunk_size, settings.chunk_overlap)
            vectors = embed_texts(pieces) if pieces else []
            session.query(Chunk).filter(Chunk.document_id == doc.id).delete()
            session.add_all(
                Chunk(document_id=doc.id, idx=i, text=t, embedding=v)
                for i, (t, v) in enumerate(zip(pieces, vectors, strict=True))
            )
            doc.status = "ready"
            doc.num_chunks = len(pieces)
            doc.error = None
            session.commit()
        except Exception as exc:
            session.rollback()
            doc = session.get(Document, document_id)
            if doc is not None:
                doc.status = "failed"
                doc.error = str(exc)[:1000]
                session.commit()
            log.exception("Ingestion failed for document %s", document_id)
            raise

    bump_corpus_version()
    log.info("Ingested document %s into %s chunks", document_id, len(pieces))
    return len(pieces)
