from __future__ import annotations

from pathlib import Path


DOCS_DIR = Path(__file__).resolve().parents[4] / "docs"


def statement_fixture_path(*candidates: str) -> Path:
    for candidate in candidates:
        path = DOCS_DIR / candidate
        if path.exists():
            return path
    return DOCS_DIR / candidates[-1]


STATEMENT_2025_PATH = statement_fixture_path("2025.pdf", "IB2025.pdf", "U8516450_2025_2025.pdf")
STATEMENT_2026_PATH = statement_fixture_path("2026.pdf", "IB2026.pdf")
STATEMENT_2026_CSV_PATH = statement_fixture_path("IB2026.csv")
FREEDOM24_PATH = statement_fixture_path("FF2026.pdf")
ESPP_PATH = statement_fixture_path("ESPP.pdf", "ESPP2026.pdf")
