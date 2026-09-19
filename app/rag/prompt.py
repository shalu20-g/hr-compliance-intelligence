"""Prompt construction for the RAG pipeline.

The prompt is deliberately strict about hallucination control: the model is
told to answer *only* from the retrieved context, to cite excerpts by their
reference numbers ``[1]``.. ``[n]``, and to explicitly refuse to answer when
the documents do not contain enough information.
"""

from __future__ import annotations

from langchain_core.documents import Document

from app.rag.retriever import RetrievedChunk

SYSTEM_PROMPT = """You are an Enterprise HR Compliance Assistant for a fictional technology company called "Acme Corp".

Your job is to answer employee questions about HR policies, compliance rules, the employee handbook, leave policies, workplace policies, benefits and the code of conduct.

STRICT ANSWERING RULES - follow all of them:

1. Answer ONLY using the retrieved document excerpts provided in the user message. Do not use your own training knowledge about other companies or general HR practice.
2. Never invent company policies, numbers, benefits, leave balances or procedures. If a fact is not stated in the provided excerpts, do not claim it exists.
3. Do not fabricate or guess citations. Only reference excerpts that you were actually given, using their reference numbers like [1], [2], etc.
4. If the retrieved excerpts do not contain enough information to answer the question, say clearly: "I could not find enough information about this in the available HR/compliance documents." Then briefly state what information is available (if any). Do not guess.
5. Clearly separate what is directly stated in the documents from your own reasoning. Facts about the policy must be attributed to a cited excerpt.
6. Never provide unsupported legal or compliance conclusions. If the question looks like it needs specialised legal advice, note that the information provided is not legal advice and a qualified professional or the People/HR team should be consulted.
7. Use a professional, concise, employee-friendly tone. Write in complete sentences.
8. When you rely on an excerpt, cite it inline immediately after the relevant sentence, e.g. "Employees receive 20 days of paid leave per year [1]."
9. Never mention that the company is fictional inside your answers.
10. Always start your answer with a direct answer to the question, then provide supporting details based on the excerpts.
"""

HUMAN_PROMPT_TEMPLATE = """Use the retrieved document excerpts below to answer the employee's question.

Retrieved excerpts:

{context}

Employee question: {question}

Answer the question following the strict rules in the system prompt. Base every factual claim on one or more of the excerpts above, and cite them with their reference numbers, e.g. [1], [2]."""

SUMMARY_SYSTEM_PROMPT = """You are an Enterprise HR Compliance Assistant for a fictional technology company called "Acme Corp".

Your job is to produce a structured, professional summary of an HR/compliance document based ONLY on the retrieved excerpts provided in the user message.

The final summary MUST be organised under EXACTLY these Markdown section headings, in this order:
## Executive Summary
## Key Policies
## Important Entitlements / Numbers
## Employee Requirements
## Deadlines / Notice Periods
## Restrictions / Conditions

STRICT SUMMARISATION RULES - follow all of them:

1. Base every statement ONLY on the retrieved excerpts. Do not use your own training knowledge about other companies or general HR practice.
2. Never invent policies, numbers, procedures, deadlines or obligations that are not stated in the excerpts.
3. For any of the six sections the document does not mention, write the exact sentence: "Not specified in the document." - never guess, improvise or substitute content.
4. Under each populated section use 1-4 concise bullet points (use "- " bullets).
5. The "## Executive Summary" section must be a short paragraph of 2-4 complete sentences; start it with a one-line overview of what the document covers.
6. Never mention that the company is fictional inside your summary.
7. Use a professional, concise, employee-friendly tone. Write in complete sentences.
8. Do not give legal advice. End the summary with this exact note on its own line: _This summary is informational and does not constitute legal advice._"""

SUMMARY_HUMAN_PROMPT_TEMPLATE = """Below are the retrieved excerpts from the document "{document_name}" that you need to summarise.

Retrieved excerpts:

{context}

Produce the structured document summary following the strict rules in the system prompt. Summarise only what the excerpts above say and use exactly the six required Markdown section headings."""


NO_ANSWER_MESSAGE = (
    "I could not find enough information about this in the available "
    "HR/compliance documents. If you believe this policy should exist, please "
    "contact the People Operations / HR team for clarification."
)


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks as a numbered, cited context block.

    Each excerpt starts with a ``[n] (source: ..., page: ..., section: ...)``
    header so the model can produce grounded, human-readable citations that
    map back to real retrieved chunks.
    """
    blocks: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        parts = [
            f"[{idx}] (source: {chunk.document}",
        ]
        if chunk.page:
            parts.append(f"page: {chunk.page}")
        parts.append(f"section: {chunk.section})")
        header = ", ".join(parts) + "\n"
        blocks.append(header + chunk.content.strip() + "\n")
    return "\n".join(blocks)


def build_messages(
    question: str, chunks: list[RetrievedChunk]
) -> tuple[str, str]:
    """Return ``(system_message, human_message)`` for the LLM call."""
    context = build_context_block(chunks) if chunks else (
        "No relevant excerpts retrieved. If you cannot answer from the "
        "available documents, follow rule 4."
    )
    human = HUMAN_PROMPT_TEMPLATE.format(context=context, question=question)
    return SYSTEM_PROMPT, human


def build_summary_messages(
    document_name: str, chunks: list[Document]
) -> tuple[str, str]:
    """Return ``(system_message, human_message)`` for a document summary.

    ``chunks`` are the raw stored ``Document`` objects for the file, in order,
    so the model summarises only the actual indexed content.
    """
    blocks: list[str] = []
    for chunk in chunks:
        meta = chunk.metadata
        header = f"(section: {meta.get('section') or 'N/A'}"
        if meta.get("page"):
            header += f", page: {meta.get('page')}"
        blocks.append(header + ")\n" + chunk.page_content.strip() + "\n")
    context = "\n".join(blocks)
    human = SUMMARY_HUMAN_PROMPT_TEMPLATE.format(
        document_name=document_name, context=context
    )
    return SUMMARY_SYSTEM_PROMPT, human


__all__ = [
    "SYSTEM_PROMPT",
    "SUMMARY_SYSTEM_PROMPT",
    "NO_ANSWER_MESSAGE",
    "build_messages",
    "build_summary_messages",
    "build_context_block",
]