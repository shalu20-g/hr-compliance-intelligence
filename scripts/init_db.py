"""Initialise the users database (create the ``users`` table).

Usage:
    python scripts/init_db.py

Reads ``DATABASE_URL`` from the environment / ``.env``. Safe to re-run.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import init_db


def main() -> int:
    init_db()
    print("Database initialised.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
