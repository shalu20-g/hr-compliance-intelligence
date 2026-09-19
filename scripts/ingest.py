"""Command-line ingestion entrypoint.

Usage:
    python scripts/ingest.py
    python scripts/ingest.py --force          # re-index everything
    python scripts/ingest.py --document handbook.txt
"""

from __future__ import annotations

import argparse
import logging
import sys

sys.path.insert(0, ".")

from app.config import get_settings  # noqa: E402
from app.exceptions import AppError  # noqa: E402
from app.ingestion.pipeline import ingest_documents  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest HR/compliance documents into ChromaDB."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-index documents even if their content is unchanged.",
    )
    parser.add_argument(
        "--document",
        default=None,
        help="Ingest only this exact filename from the documents directory.",
    )
    args = parser.parse_args()

    setup_logging()
    settings = get_settings()

    try:
        logging.info("Starting ingestion from '%s'...", settings.documents_directory)
        report = ingest_documents(
            settings=settings, force=args.force, filter_name=args.document
        )
    except AppError as exc:
        logging.error("Ingestion failed: %s", exc.message)
        print(f"\nERROR: {exc.message}", file=sys.stderr)
        return 1

    print(f"\n{'='*60}")
    print(f"Files found                : {report.files_found}")
    print(f"Files processed            : {report.files_processed}")
    print(f"Files skipped (unchanged)  : {report.files_skipped_unchanged}")
    print(f"Chunks added               : {report.chunks_added}")
    print(f"Chunks skipped (duplicate) : {report.chunks_skipped_duplicate}")
    if report.failures:
        print(f"Failures                   : {len(report.failures)}")
        for failure in report.failures:
            print(f"  - {failure}")
        return 1
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())