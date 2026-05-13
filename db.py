import sqlite3

from paths import DB_PATH


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                normalized_title TEXT NOT NULL UNIQUE,
                authors TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id INTEGER NOT NULL,
                openreview_forum_id TEXT,
                openreview_note_id TEXT,
                openreview_url TEXT,
                venue TEXT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'imported',
                submitted_at TEXT,
                decision_at TEXT,
                decision TEXT,
                abstract TEXT,
                pdf_url TEXT,
                raw_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
                UNIQUE(openreview_forum_id, openreview_note_id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                openreview_note_id TEXT,
                reviewer TEXT,
                review_type TEXT NOT NULL DEFAULT 'review',
                rating REAL,
                confidence REAL,
                summary TEXT,
                strengths TEXT,
                weaknesses TEXT,
                questions TEXT,
                text TEXT,
                raw_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
                UNIQUE(attempt_id, openreview_note_id)
            );

            CREATE TABLE IF NOT EXISTS paper_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
                UNIQUE(paper_id, normalized_title)
            );

            CREATE TABLE IF NOT EXISTS ignored_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                openreview_forum_id TEXT,
                openreview_note_id TEXT,
                title TEXT,
                venue TEXT,
                reason TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(openreview_forum_id, openreview_note_id)
            );

            CREATE TABLE IF NOT EXISTS clean_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                review_index INTEGER NOT NULL,
                reviewer TEXT,
                rating REAL,
                confidence REAL,
                summary TEXT,
                strengths TEXT,
                weaknesses TEXT,
                questions TEXT,
                text TEXT NOT NULL,
                source_note_ids TEXT,
                extraction_method TEXT NOT NULL DEFAULT 'rules',
                created_at TEXT NOT NULL,
                FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
                UNIQUE(attempt_id, review_index)
            );
            """
        )
