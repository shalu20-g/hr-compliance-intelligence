"""Tests for the retrieval layer and RAG grounding behaviour."""

from __future__ import annotations

from app.ingestion.pipeline import ingest_documents
from app.rag.embeddings import DummyEmbeddings
from app.rag.retriever import dedupe_sources, retrieve
from app.rag.vectorstore import VectorStore
from tests.conftest import write_sample_documents


def test_dummy_embeddings_are_deterministic_and_shape_stable():
    emb = DummyEmbeddings()
    a = emb.embed_query("hello")
    b = emb.embed_query("hello")
    c = emb.embed_query("world")

    assert a == b
    assert a != c
    assert len(a) == emb.dimension
    assert len(emb.embed_documents(["x", "y"])) == 2


def test_retrieve_returns_top_k_chunks(iso_settings):
    write_sample_documents(iso_settings)
    ingest_documents(settings=iso_settings)

    store = VectorStore(iso_settings, DummyEmbeddings())
    chunks = retrieve(store, "annual leave", top_k=2, threshold=0.0)

    assert len(chunks) == 2
    assert chunks[0].score >= 0.0
    assert all(c.document for c in chunks)


def test_retrieve_with_impossible_threshold_returns_nothing(iso_settings):
    write_sample_documents(iso_settings)
    ingest_documents(settings=iso_settings)

    store = VectorStore(iso_settings, DummyEmbeddings())
    chunks = retrieve(store, "annual leave", top_k=5, threshold=0.999)

    assert chunks == []


def test_retrieve_on_empty_collection_returns_empty(iso_settings):
    store = VectorStore(iso_settings, DummyEmbeddings())
    chunks = retrieve(store, "anything", top_k=5, threshold=0.0)
    assert chunks == []


def test_exact_match_scores_highest(iso_settings):
    """Re-ranking is deterministic and best-match-first."""
    write_sample_documents(iso_settings)
    ingest_documents(settings=iso_settings)

    store = VectorStore(iso_settings, DummyEmbeddings())
    chunks = retrieve(store, "Sick Leave", top_k=8, threshold=0.0)

    scores = [c.score for c in chunks]
    assert scores == sorted(scores, reverse=True)


def test_dedupe_sources_collapses_duplicates():
    from app.rag.retriever import RetrievedChunk

    chunks = [
        RetrievedChunk(content="a", metadata={"filename": "p.txt", "page": "1", "section": "Leave"}, score=0.8),
        RetrievedChunk(content="b", metadata={"filename": "p.txt", "page": "1", "section": "Leave"}, score=0.9),
        RetrievedChunk(content="c", metadata={"filename": "q.txt", "section": "General"}, score=0.7),
    ]
    sources = dedupe_sources(chunks)

    assert len(sources) == 2  # two distinct (document, page, section) keys
    assert sources[0].relevance_score == 0.9
    assert {s.document for s in sources} == {"p.txt", "q.txt"}


def test_retrieved_chunk_exposes_readable_source_fields():
    from app.rag.retriever import RetrievedChunk

    chunk = RetrievedChunk(
        content="text",
        metadata={"filename": "handbook.pdf", "page": 4, "section": "Leave Policy"},
        score=0.9,
    )
    assert chunk.document == "handbook.pdf"
    assert chunk.section == "Leave Policy"
    d = chunk.to_dict()
    assert d["score"] == 0.9
    assert d["metadata"]["filename"] == "handbook.pdf"