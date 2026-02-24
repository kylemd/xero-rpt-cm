"""SQLite-backed synonym normalisation for accounting terms.

Handles abbreviations (MV -> motor vehicle), synonyms (super -> superannuation),
typos (ammenities -> amenities), and acronyms (SGC -> superannuation guarantee charge).
"""
from __future__ import annotations

import pathlib
import sqlite3


class SynonymDB:
    """Manages a SQLite synonym database for text normalisation."""

    MAX_PHRASE_LENGTH = 4

    def __init__(self, db_path: pathlib.Path | str):
        self.db_path = pathlib.Path(db_path)
        self._conn = sqlite3.connect(str(self.db_path))
        self._create_tables()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS synonyms (
                id INTEGER PRIMARY KEY,
                term TEXT NOT NULL COLLATE NOCASE,
                canonical TEXT NOT NULL,
                category TEXT NOT NULL,
                domain TEXT DEFAULT NULL,
                notes TEXT DEFAULT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_synonyms_term
                ON synonyms(term COLLATE NOCASE);
        """)

    def add(self, term: str, canonical: str, category: str,
            domain: str | None = None, notes: str | None = None):
        """Insert or replace a synonym entry."""
        self._conn.execute(
            "INSERT OR REPLACE INTO synonyms (term, canonical, category, domain, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (term.lower(), canonical.lower(), category, domain, notes),
        )
        self._conn.commit()

    def add_many(self, entries: list[tuple[str, str, str]]):
        """Bulk insert (term, canonical, category) tuples."""
        self._conn.executemany(
            "INSERT OR REPLACE INTO synonyms (term, canonical, category) "
            "VALUES (?, ?, ?)",
            [(t.lower(), c.lower(), cat) for t, c, cat in entries],
        )
        self._conn.commit()

    def lookup(self, term: str) -> str | None:
        """Look up a single term. Returns canonical form or None."""
        row = self._conn.execute(
            "SELECT canonical FROM synonyms WHERE term = ? COLLATE NOCASE",
            (term.lower(),),
        ).fetchone()
        return row[0] if row else None

    def normalise_tokens(self, text: str) -> str:
        """Replace known tokens in text with their canonical forms.

        Tries longest multi-word matches first, then single words.
        """
        words = text.lower().split()
        result = []
        i = 0
        while i < len(words):
            matched = False
            for length in range(min(self.MAX_PHRASE_LENGTH, len(words) - i), 0, -1):
                phrase = " ".join(words[i : i + length])
                canonical = self.lookup(phrase)
                if canonical is not None:
                    result.append(canonical)
                    i += length
                    matched = True
                    break
            if not matched:
                result.append(words[i])
                i += 1
        return " ".join(result)

    def all_entries(self) -> list[dict]:
        """Return all synonym entries as dicts."""
        rows = self._conn.execute(
            "SELECT term, canonical, category, domain, notes FROM synonyms"
        ).fetchall()
        return [
            {"term": r[0], "canonical": r[1], "category": r[2],
             "domain": r[3], "notes": r[4]}
            for r in rows
        ]

    def close(self):
        self._conn.close()
