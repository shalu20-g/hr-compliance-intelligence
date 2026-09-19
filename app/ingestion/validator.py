"""Document validation: safety checks + HR/compliance classification.

This is a *heuristic pre-filter*, not a security guarantee. It catches
accidental uploads of irrelevant/personal documents before they can reach the
shared ChromaDB knowledge base. Authorization (HR-only ingestion) is enforced
separately on the backend and is the real access control.

Pipeline for a candidate file:
  1. File-type + basic safety (extension, non-empty, size, extractable text).
  2. Heuristic classification into HR/compliance vs personal/unrelated.
  3. Verdict: ``approved`` (clearly HR), ``pending`` (uncertain — human must
     review, never auto-indexed), ``rejected`` (clearly personal/unrelated or
     unsafe — quarantined, never indexed).

Only ``approved`` documents (via the legacy validated path) or explicitly
HR-approved pending documents may be indexed into ChromaDB.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.ingestion.loaders import VALID_EXTENSIONS

logger = logging.getLogger(__name__)

Verdict = Literal["approved", "pending", "rejected"]

# Strong HR/compliance signals (company policies, not personal docs).
HR_PHRASES = (
    "leave policy",
    "attendance policy",
    "employee handbook",
    "code of conduct",
    "benefits policy",
    "workplace",
    "compliance policy",
    "compliance",
    "hr policy",
    "human resources",
    "people team",
    "people operations",
    "paid leave",
    "annual leave",
    "sick leave",
    "parental leave",
    "maternity leave",
    "paternity leave",
    "adoption leave",
    "remote work",
    "hybrid work",
    "working hours",
    "overtime",
    "payroll",
    "compensation",
    "harassment policy",
    "harassment",
    "confidentiality policy",
    "confidentiality",
    "disciplinary",
    "grievance",
    "equal opportunity",
    "health and safety",
    "probation period",
    "notice period",
    "employee benefits",
    "acme corp",
)

# Signals of personal / unrelated content that must never enter shared Chroma.
PERSONAL_PHRASES = (
    "resume",
    "curriculum vitae",
    "cv ",
    "job application",
    "cover letter",
    "passport",
    "social security",
    "driver's license",
    "driving licence",
    "bank account",
    "credit card",
    "personal letter",
    "dear mom",
    "dear dad",
    "dear friend",
    "my medical",
    "my diagnosis",
    "recipe",
    "shopping list",
    "invoice",
    "dating profile",
)

PERSONAL_FILENAME_HINTS = (
    "resume",
    "resumé",
    "cv",
    "cover_letter",
    "coverletter",
    "personal",
    "passport",
    "id_card",
    "private",
)

MIN_TEXT_CHARS = 50
MAX_TEXT_CHARS = 500_000


@dataclass
class ClassificationResult:
    """Outcome of validating one candidate document."""

    verdict: Verdict
    reason: str
    category: str
    confidence: float
    hr_hits: int = 0
    personal_hits: int = 0


def _count_hits(text: str, phrases: tuple[str, ...]) -> int:
    lowered = text.lower()
    return sum(1 for p in phrases if p in lowered)


def classify_document(filename: str, text: str) -> ClassificationResult:
    """Heuristically classify extracted document text.

    Thresholds are deliberately conservative: anything uncertain returns
    ``pending`` so a human HR reviewer decides. This function never raises.
    """
    name_hit = any(h in filename.lower() for h in PERSONAL_FILENAME_HINTS)
    hr_hits = _count_hits(text, HR_PHRASES)
    personal_hits = _count_hits(text, PERSONAL_PHRASES) + (2 if name_hit else 0)
    length = len(text.strip())

    if length < MIN_TEXT_CHARS:
        return ClassificationResult(
            verdict="pending",
            reason=(
                "Too little extractable text to classify safely; "
                "held for HR review instead of indexing."
            ),
            category="uncertain",
            confidence=0.3,
            hr_hits=hr_hits,
            personal_hits=personal_hits,
        )

    # Clearly personal/unrelated: personal signals dominate, no HR substance.
    if personal_hits >= 2 and hr_hits <= 2:
        return ClassificationResult(
            verdict="rejected",
            reason=(
                "Appears to be a personal or unrelated document "
                "(e.g. resume, personal letter, ID, or random file), "
                "not a company HR/compliance policy. Quarantined."
            ),
            category="personal_or_unrelated",
            confidence=0.85,
            hr_hits=hr_hits,
            personal_hits=personal_hits,
        )
    if personal_hits >= 1 and hr_hits == 0:
        return ClassificationResult(
            verdict="rejected",
            reason=(
                "Contains personal/unrelated content with no HR/compliance "
                "signals. Quarantined."
            ),
            category="personal_or_unrelated",
            confidence=0.8,
            hr_hits=hr_hits,
            personal_hits=personal_hits,
        )

    # Clearly HR/compliance: multiple HR signals, no personal contamination.
    if hr_hits >= 4 and personal_hits == 0:
        return ClassificationResult(
            verdict="approved",
            reason=f"Company HR/compliance signals detected ({hr_hits} policy indicators).",
            category="hr_compliance",
            confidence=min(0.95, 0.6 + hr_hits * 0.05),
            hr_hits=hr_hits,
            personal_hits=personal_hits,
        )

    # Everything else is uncertain — never auto-index.
    return ClassificationResult(
        verdict="pending",
        reason=(
            "Could not confidently classify as a company HR/compliance "
            f"document (hr_signals={hr_hits}, personal_signals={personal_hits}). "
            "Held for HR review instead of indexing."
        ),
        category="uncertain",
        confidence=0.5,
        hr_hits=hr_hits,
        personal_hits=personal_hits,
    )


def validate_upload(filename: str, content: bytes, text: str) -> ClassificationResult:
    """Combine file-safety checks with classification.

    Unsafe files (bad type, empty, oversized text, binary) are ``rejected``;
    otherwise classification decides approved/pending/rejected.
    """
    ext = Path(filename).suffix.lower()
    if ext not in VALID_EXTENSIONS:
        return ClassificationResult(
            verdict="rejected",
            reason=f"Unsupported file type '{ext}'. Supported: .pdf, .docx, .txt.",
            category="unsupported_type",
            confidence=1.0,
        )
    if not content:
        return ClassificationResult(
            verdict="rejected",
            reason="Uploaded file is empty.",
            category="empty",
            confidence=1.0,
        )
    # Basic binary sniff for .txt (pdf/docx are binary by nature).
    if ext == ".txt" and b"\x00" in content:
        return ClassificationResult(
            verdict="rejected",
            reason="File appears to be binary, not a text HR document.",
            category="unsafe",
            confidence=0.9,
        )
    if len(text.strip()) > MAX_TEXT_CHARS:
        return ClassificationResult(
            verdict="pending",
            reason="Document is unusually large; held for HR review.",
            category="uncertain",
            confidence=0.4,
        )
    result = classify_document(filename, text)
    # Surface which file the verdict applies to in logs/UI.
    logger.info(
        "Validation for '%s': %s (%s) — %s",
        filename,
        result.verdict,
        result.category,
        result.reason,
    )
    return result


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def extractive_summary(text: str, max_chars: int = 1200) -> str:
    """Deterministic offline summary: first sentences, truncated safely."""
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return "No extractable text found in the document."
    sentences = _SENTENCE_SPLIT.split(cleaned)
    out: list[str] = []
    total = 0
    for sent in sentences[:8]:
        if total + len(sent) > max_chars and out:
            break
        out.append(sent)
        total += len(sent)
    summary = " ".join(out).strip()
    if len(cleaned) > len(summary):
        summary += " [...]"
    return summary


__all__ = [
    "Verdict",
    "ClassificationResult",
    "classify_document",
    "validate_upload",
    "extractive_summary",
]
