import json
import sqlite3

from db import connect
from utils import content_value, db_text, normalize_title, now_iso, timestamp_to_iso, truncate_text


def authors_json_from_attempt(attempt: sqlite3.Row) -> str | None:
    raw_json = attempt["raw_json"] if "raw_json" in attempt.keys() else None
    if not raw_json:
        return None
    try:
        root = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    content = root.get("content") or {}
    authors = content_value(content, "authors") or content_value(content, "authorids")
    if not authors:
        return None
    return json.dumps(authors, ensure_ascii=False)


def refresh_paper_from_latest_attempt(conn: sqlite3.Connection, paper_id: int) -> None:
    latest = conn.execute(
        """
        SELECT * FROM attempts
        WHERE paper_id = ?
        ORDER BY COALESCE(submitted_at, created_at) DESC, id DESC
        LIMIT 1
        """,
        (paper_id,),
    ).fetchone()
    if not latest:
        return
    authors = authors_json_from_attempt(latest)
    normalized = normalize_title(latest["title"])
    timestamp = now_iso()
    conflicting = conn.execute(
        "SELECT id FROM papers WHERE normalized_title = ? AND id != ?",
        (normalized, paper_id),
    ).fetchone()
    if conflicting:
        conn.execute(
            "UPDATE papers SET title = ?, authors = COALESCE(?, authors), updated_at = ? WHERE id = ?",
            (latest["title"], authors, timestamp, paper_id),
        )
        return
    conn.execute(
        "UPDATE papers SET title = ?, normalized_title = ?, authors = COALESCE(?, authors), updated_at = ? WHERE id = ?",
        (latest["title"], normalized, authors, timestamp, paper_id),
    )


def is_ignored_attempt(conn: sqlite3.Connection, forum_id: str | None, note_id: str | None) -> bool:
    if not forum_id and not note_id:
        return False
    row = conn.execute(
        """
        SELECT id FROM ignored_attempts
        WHERE COALESCE(openreview_forum_id, '') = COALESCE(?, '')
          AND COALESCE(openreview_note_id, '') = COALESCE(?, '')
        """,
        (forum_id, note_id),
    ).fetchone()
    return row is not None


def raw_note_time(raw_json: str | None, fallback: str | None = None) -> str | None:
    if not raw_json:
        return fallback
    try:
        note = json.loads(raw_json)
    except json.JSONDecodeError:
        return fallback
    for key in ("cdate", "tcdate", "pdate", "mdate", "tmdate"):
        value = timestamp_to_iso(note.get(key))
        if value:
            return value
    return fallback


def infer_activity_type(row: sqlite3.Row) -> str:
    try:
        note = json.loads(row["raw_json"] or "{}")
    except json.JSONDecodeError:
        return row["review_type"] or "activity"
    invitations = " ".join(note.get("invitations") or []).lower()
    signatures = " ".join(note.get("signatures") or []).lower()
    content = note.get("content") or {}
    if "decision" in invitations or content_value(content, "decision"):
        return "decision"
    if "meta" in invitations:
        return "meta_review"
    if "authors" in signatures or "rebuttal" in invitations or "response" in invitations:
        return "response"
    if "comment" in invitations:
        return "comment"
    if "official_review" in invitations:
        return "review"
    return row["review_type"] or "activity"


def list_activities() -> list[dict]:
    activities = []
    with connect() as conn:
        attempts = conn.execute(
            """
            SELECT a.*, p.title AS paper_title
            FROM attempts a
            JOIN papers p ON p.id = a.paper_id
            ORDER BY COALESCE(a.submitted_at, a.created_at), a.id
            """
        )
        for attempt in attempts:
            submitted_at = attempt["submitted_at"] or attempt["created_at"]
            if submitted_at:
                activities.append(
                    {
                        "type": "submission",
                        "occurred_at": submitted_at,
                        "paper_id": attempt["paper_id"],
                        "paper_title": attempt["paper_title"],
                        "attempt_id": attempt["id"],
                        "venue": attempt["venue"],
                        "title": attempt["title"],
                    }
                )
            if attempt["decision_at"]:
                activities.append(
                    {
                        "type": "decision",
                        "occurred_at": attempt["decision_at"],
                        "paper_id": attempt["paper_id"],
                        "paper_title": attempt["paper_title"],
                        "attempt_id": attempt["id"],
                        "venue": attempt["venue"],
                        "title": attempt["decision"] or "Decision",
                    }
                )

        rows = conn.execute(
            """
            SELECT r.*, a.paper_id, a.venue, a.title AS attempt_title, p.title AS paper_title
            FROM reviews r
            JOIN attempts a ON a.id = r.attempt_id
            JOIN papers p ON p.id = a.paper_id
            ORDER BY r.id
            """
        )
        for row in rows:
            occurred_at = raw_note_time(row["raw_json"], row["created_at"])
            if not occurred_at:
                continue
            activity_type = infer_activity_type(row)
            if activity_type == "decision":
                # The attempt-level decision activity already gives a cleaner label.
                continue
            activities.append(
                {
                    "type": activity_type,
                    "occurred_at": occurred_at,
                    "paper_id": row["paper_id"],
                    "paper_title": row["paper_title"],
                    "attempt_id": row["attempt_id"],
                    "venue": row["venue"],
                    "title": row["attempt_title"],
                    "reviewer": row["reviewer"],
                }
            )
    activities.sort(key=lambda item: item["occurred_at"])
    return activities


def list_papers() -> list[dict]:
    with connect() as conn:
        papers = [
            dict(row)
            for row in conn.execute(
                """
                SELECT p.*
                FROM papers p
                LEFT JOIN attempts a ON a.paper_id = p.id
                GROUP BY p.id
                ORDER BY MIN(COALESCE(a.submitted_at, a.created_at, p.created_at)) DESC, p.id DESC
                """
            )
        ]
        for paper in papers:
            paper["authors"] = json.loads(paper["authors"] or "[]")
            paper["aliases"] = [
                dict(row)
                for row in conn.execute(
                    "SELECT title, source, created_at FROM paper_aliases WHERE paper_id = ? ORDER BY created_at DESC",
                    (paper["id"],),
                )
            ]
            attempts = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT * FROM attempts
                    WHERE paper_id = ?
                    ORDER BY COALESCE(submitted_at, created_at) DESC, id DESC
                    """,
                    (paper["id"],),
                )
            ]
            for attempt in attempts:
                attempt.pop("raw_json", None)
                clean_reviews = [
                    dict(row)
                    for row in conn.execute(
                        """
                        SELECT reviewer, rating, confidence, summary, strengths, weaknesses,
                               questions, text, extraction_method, created_at
                        FROM clean_reviews
                        WHERE attempt_id = ?
                        ORDER BY review_index
                        """,
                        (attempt["id"],),
                    )
                ]
                for review in clean_reviews:
                    review["review_type"] = "review"
                    for key in ("text", "summary", "strengths", "weaknesses", "questions"):
                        review[key] = truncate_text(review.get(key), 2200)
                attempt["reviews"] = clean_reviews
                ratings = [r["rating"] for r in attempt["reviews"] if r["rating"] is not None]
                attempt["average_rating"] = round(sum(ratings) / len(ratings), 2) if ratings else None
            paper["attempts"] = attempts
        return papers


def add_paper_alias(conn: sqlite3.Connection, paper_id: int, title: str, source: str = "manual") -> None:
    normalized = normalize_title(title)
    if not normalized:
        return
    conn.execute(
        """
        INSERT OR IGNORE INTO paper_aliases (paper_id, title, normalized_title, source, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (paper_id, title, normalized, source, now_iso()),
    )


def update_paper_title(payload: dict) -> dict:
    paper_id = int(payload.get("paper_id") or 0)
    title = (payload.get("title") or "").strip()
    if not paper_id or not title:
        raise ValueError("paper_id and title are required.")
    normalized = normalize_title(title)
    timestamp = now_iso()
    with connect() as conn:
        existing = conn.execute("SELECT id FROM papers WHERE normalized_title = ? AND id != ?", (normalized, paper_id)).fetchone()
        if existing:
            raise ValueError("Another paper already uses that canonical title.")
        current = conn.execute("SELECT title FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if not current:
            raise ValueError("Paper not found.")
        add_paper_alias(conn, paper_id, current["title"], "previous_canonical")
        conn.execute(
            "UPDATE papers SET title = ?, normalized_title = ?, updated_at = ? WHERE id = ?",
            (title, normalized, timestamp, paper_id),
        )
    return {"paper_id": paper_id}


def merge_papers(payload: dict) -> dict:
    source_id = int(payload.get("source_paper_id") or 0)
    target_id = int(payload.get("target_paper_id") or 0)
    if not source_id or not target_id or source_id == target_id:
        raise ValueError("Choose two different papers to merge.")
    timestamp = now_iso()
    with connect() as conn:
        source = conn.execute("SELECT * FROM papers WHERE id = ?", (source_id,)).fetchone()
        target = conn.execute("SELECT * FROM papers WHERE id = ?", (target_id,)).fetchone()
        if not source or not target:
            raise ValueError("Paper not found.")
        add_paper_alias(conn, target_id, source["title"], "merged_paper")
        for row in conn.execute("SELECT title FROM attempts WHERE paper_id = ?", (source_id,)):
            add_paper_alias(conn, target_id, row["title"], "submission_title")
        conn.execute("UPDATE attempts SET paper_id = ?, updated_at = ? WHERE paper_id = ?", (target_id, timestamp, source_id))
        for alias in conn.execute("SELECT title, source FROM paper_aliases WHERE paper_id = ?", (source_id,)):
            add_paper_alias(conn, target_id, alias["title"], alias["source"])
        conn.execute("DELETE FROM paper_aliases WHERE paper_id = ?", (source_id,))
        conn.execute("DELETE FROM papers WHERE id = ?", (source_id,))
        refresh_paper_from_latest_attempt(conn, target_id)
    return {"target_paper_id": target_id}


def move_attempt(payload: dict) -> dict:
    attempt_id = int(payload.get("attempt_id") or 0)
    target_id = int(payload.get("target_paper_id") or 0)
    if not attempt_id or not target_id:
        raise ValueError("attempt_id and target_paper_id are required.")
    timestamp = now_iso()
    with connect() as conn:
        attempt = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
        target = conn.execute("SELECT id FROM papers WHERE id = ?", (target_id,)).fetchone()
        if not attempt or not target:
            raise ValueError("Attempt or target paper not found.")
        add_paper_alias(conn, target_id, attempt["title"], "moved_attempt")
        source_id = attempt["paper_id"]
        conn.execute("UPDATE attempts SET paper_id = ?, updated_at = ? WHERE id = ?", (target_id, timestamp, attempt_id))
        refresh_paper_from_latest_attempt(conn, target_id)
        remaining = conn.execute("SELECT COUNT(*) AS count FROM attempts WHERE paper_id = ?", (source_id,)).fetchone()
        if remaining["count"] == 0:
            conn.execute("DELETE FROM papers WHERE id = ?", (source_id,))
        else:
            refresh_paper_from_latest_attempt(conn, source_id)
    return {"attempt_id": attempt_id, "target_paper_id": target_id}


def delete_attempt(payload: dict) -> dict:
    attempt_id = int(payload.get("attempt_id") or 0)
    if not attempt_id:
        raise ValueError("attempt_id is required.")
    timestamp = now_iso()
    with connect() as conn:
        attempt = conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
        if not attempt:
            raise ValueError("Attempt not found.")
        if attempt["openreview_forum_id"] or attempt["openreview_note_id"]:
            conn.execute(
                """
                INSERT OR REPLACE INTO ignored_attempts (
                    openreview_forum_id, openreview_note_id, title, venue, reason, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt["openreview_forum_id"],
                    attempt["openreview_note_id"],
                    attempt["title"],
                    attempt["venue"],
                    db_text(payload.get("reason")) or "manual_delete",
                    timestamp,
                ),
            )
        paper_id = attempt["paper_id"]
        conn.execute("DELETE FROM attempts WHERE id = ?", (attempt_id,))
        remaining = conn.execute("SELECT COUNT(*) AS count FROM attempts WHERE paper_id = ?", (paper_id,)).fetchone()
        if remaining["count"] == 0:
            conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
        else:
            refresh_paper_from_latest_attempt(conn, paper_id)
    return {"attempt_id": attempt_id}


def create_manual_paper(payload: dict) -> dict:
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValueError("Title is required.")
    timestamp = now_iso()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO papers (title, normalized_title, authors, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                title,
                normalize_title(title),
                json.dumps(payload.get("authors") or [], ensure_ascii=False),
                timestamp,
                timestamp,
            ),
        )
        paper_id = cursor.lastrowid
        if not paper_id:
            row = conn.execute("SELECT id FROM papers WHERE normalized_title = ?", (normalize_title(title),)).fetchone()
            paper_id = row["id"]
        if payload.get("venue"):
            conn.execute(
                """
                INSERT INTO attempts (paper_id, venue, title, status, decision, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    payload.get("venue"),
                    title,
                    payload.get("status") or "manual",
                    payload.get("decision"),
                    timestamp,
                    timestamp,
                ),
            )
    return {"paper_id": paper_id}
