import json
import sqlite3

from db import connect
from llm_client import chat_completion, llm_configured, llm_model
from utils import content_value, db_text, normalize_title, now_iso, timestamp_to_iso, truncate_text


CONTEXT_TEXT_LIMIT = 32000
REVIEW_TEXT_LIMIT = 2600
CHAT_HISTORY_LIMIT = 12


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


def trim_for_context(value, limit: int) -> str:
    text = db_text(value) or ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[truncated]"


def row_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def ensure_chat_session(conn: sqlite3.Connection, paper_id: int) -> dict:
    paper = conn.execute("SELECT id, title FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if not paper:
        raise ValueError("Paper not found.")
    session = conn.execute(
        "SELECT * FROM chat_sessions WHERE paper_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
        (paper_id,),
    ).fetchone()
    if session:
        return dict(session)
    timestamp = now_iso()
    cursor = conn.execute(
        "INSERT INTO chat_sessions (paper_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (paper_id, "AI analysis", timestamp, timestamp),
    )
    return {
        "id": cursor.lastrowid,
        "paper_id": paper_id,
        "title": "AI analysis",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def list_chat_messages(conn: sqlite3.Connection, session_id: int, limit: int | None = None) -> list[dict]:
    sql = "SELECT id, role, content, source_scope, created_at FROM chat_messages WHERE session_id = ? ORDER BY id"
    params: tuple = (session_id,)
    if limit:
        sql = """
        SELECT id, role, content, source_scope, created_at
        FROM (
            SELECT id, role, content, source_scope, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
        )
        ORDER BY id
        """
        params = (session_id, limit)
    return [dict(row) for row in conn.execute(sql, params)]


def save_chat_message(conn: sqlite3.Connection, session_id: int, role: str, content: str, source_scope: str | None = None) -> dict:
    timestamp = now_iso()
    cursor = conn.execute(
        "INSERT INTO chat_messages (session_id, role, content, source_scope, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, role, content, source_scope, timestamp),
    )
    conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (timestamp, session_id))
    return {
        "id": cursor.lastrowid,
        "session_id": session_id,
        "role": role,
        "content": content,
        "source_scope": source_scope,
        "created_at": timestamp,
    }


def list_llm_artifacts(conn: sqlite3.Connection, paper_id: int) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT id, paper_id, attempt_id, artifact_type, scope_key, content, model, created_at, updated_at
            FROM llm_artifacts
            WHERE paper_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (paper_id,),
        )
    ]


def get_paper_chat(paper_id: int) -> dict:
    with connect() as conn:
        session = ensure_chat_session(conn, paper_id)
        return {
            "configured": llm_configured(),
            "model": llm_model(),
            "session": session,
            "messages": list_chat_messages(conn, session["id"]),
            "artifacts": list_llm_artifacts(conn, paper_id),
        }


def paper_context_text(conn: sqlite3.Connection, paper_id: int, attempt_id: int | None = None) -> str:
    paper = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if not paper:
        raise ValueError("Paper not found.")
    if attempt_id:
        attempt = conn.execute("SELECT paper_id FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
        if not attempt or attempt["paper_id"] != paper_id:
            raise ValueError("Attempt not found for this paper.")

    authors = json.loads(paper["authors"] or "[]")
    lines = [
        f"Canonical paper title: {paper['title']}",
        f"Authors: {', '.join(authors) if authors else 'Unknown'}",
        "",
        "Submission attempts are listed from earliest to latest.",
    ]
    attempts = conn.execute(
        """
        SELECT *
        FROM attempts
        WHERE paper_id = ?
        ORDER BY COALESCE(submitted_at, created_at) ASC, id ASC
        """,
        (paper_id,),
    )
    for index, attempt in enumerate(attempts, start=1):
        selected = " [FOCUSED ATTEMPT]" if attempt_id and attempt["id"] == attempt_id else ""
        lines.extend(
            [
                "",
                f"Attempt {index}{selected}",
                f"- attempt_id: {attempt['id']}",
                f"- venue: {attempt['venue'] or 'Unknown venue'}",
                f"- title: {attempt['title']}",
                f"- submitted_at: {attempt['submitted_at'] or attempt['created_at'] or 'Unknown'}",
                f"- decision: {attempt['decision'] or 'Unknown'}",
                f"- status: {attempt['status'] or 'Unknown'}",
            ]
        )
        abstract = trim_for_context(attempt["abstract"], 1200)
        if abstract:
            lines.append(f"- abstract: {abstract}")
        reviews = [
            dict(row)
            for row in conn.execute(
                """
                SELECT review_index, reviewer, rating, confidence, summary, strengths,
                       weaknesses, questions, text
                FROM clean_reviews
                WHERE attempt_id = ?
                ORDER BY review_index
                """,
                (attempt["id"],),
            )
        ]
        if not reviews:
            lines.append("- clean_reviews: none captured")
            continue
        lines.append("- clean_reviews:")
        for review in reviews:
            label_parts = [f"Review {review['review_index']}"]
            if review["rating"] is not None:
                label_parts.append(f"score {review['rating']}")
            if review["confidence"] is not None:
                label_parts.append(f"confidence {review['confidence']}")
            lines.append(f"  - {'; '.join(label_parts)}")
            text = trim_for_context(review["text"], REVIEW_TEXT_LIMIT)
            if text:
                lines.append(f"    text: {text}")

    context = "\n".join(lines)
    if len(context) > CONTEXT_TEXT_LIMIT:
        context = context[:CONTEXT_TEXT_LIMIT].rstrip() + "\n[context truncated]"
    return context


def chat_system_prompt() -> str:
    return (
        "You are PaperTrail's research assistant for an AI PhD student. "
        "Answer in Chinese unless the user asks otherwise. Use only the provided PaperTrail context. "
        "Be concrete: cite venues, dates, scores, reviewer concerns, and decision labels when useful. "
        "If the context is insufficient, say what is missing instead of inventing details."
    )


def run_paper_chat(payload: dict) -> dict:
    paper_id = int(payload.get("paper_id") or 0)
    message = db_text(payload.get("message"))
    attempt_id = int(payload.get("attempt_id") or 0) or None
    if not paper_id or not message:
        raise ValueError("paper_id and message are required.")
    if not llm_configured():
        raise ValueError("Missing DEEPSEEK_API_KEY. Add it to `.env.local` and restart PaperTrail.")
    with connect() as conn:
        session = ensure_chat_session(conn, paper_id)
        source_scope = f"attempt:{attempt_id}" if attempt_id else "paper"
        history = list_chat_messages(conn, session["id"], CHAT_HISTORY_LIMIT)
        context = paper_context_text(conn, paper_id, attempt_id)

    llm_messages = [
        {"role": "system", "content": chat_system_prompt()},
        {"role": "user", "content": f"PaperTrail context:\n\n{context}"},
    ]
    llm_messages.extend({"role": item["role"], "content": item["content"]} for item in history if item["role"] in ("user", "assistant"))
    llm_messages.append({"role": "user", "content": message})
    answer = chat_completion(llm_messages)

    with connect() as conn:
        user_message = save_chat_message(conn, session["id"], "user", message, source_scope)
        assistant_message = save_chat_message(conn, session["id"], "assistant", answer, source_scope)
        session = row_dict(conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session["id"],)).fetchone())
        messages = list_chat_messages(conn, session["id"])
    return {
        "session": session,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "messages": messages,
    }


def summary_prompt(attempt_id: int | None) -> str:
    if attempt_id:
        return (
            "请总结标记为 [FOCUSED ATTEMPT] 的这一次投稿审稿意见。"
            "请包含：总体评价、主要优点、主要问题、分数/信心、decision、以及下一轮修改优先级。"
        )
    return (
        "请总结这篇 paper 的完整投稿历程。请包含：各轮投稿时间线、审稿意见如何变化、"
        "反复出现的问题、最终状态/接收亮点，以及下一步改进建议。"
    )


def summarize_paper(payload: dict) -> dict:
    paper_id = int(payload.get("paper_id") or 0)
    attempt_id = int(payload.get("attempt_id") or 0) or None
    if not paper_id:
        raise ValueError("paper_id is required.")
    if not llm_configured():
        raise ValueError("Missing DEEPSEEK_API_KEY. Add it to `.env.local` and restart PaperTrail.")
    prompt = summary_prompt(attempt_id)
    with connect() as conn:
        session = ensure_chat_session(conn, paper_id)
        context = paper_context_text(conn, paper_id, attempt_id)

    answer = chat_completion(
        [
            {"role": "system", "content": chat_system_prompt()},
            {"role": "user", "content": f"PaperTrail context:\n\n{context}\n\nTask:\n{prompt}"},
        ]
    )

    timestamp = now_iso()
    artifact_type = "attempt_summary" if attempt_id else "paper_summary"
    scope_key = str(attempt_id) if attempt_id else "paper"
    source_scope = f"attempt:{attempt_id}" if attempt_id else "paper"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_artifacts (
                paper_id, attempt_id, artifact_type, scope_key, content, model, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(paper_id, artifact_type, scope_key)
            DO UPDATE SET content = excluded.content, model = excluded.model, updated_at = excluded.updated_at
            """,
            (paper_id, attempt_id, artifact_type, scope_key, answer, llm_model(), timestamp, timestamp),
        )
        save_chat_message(conn, session["id"], "user", prompt, source_scope)
        assistant_message = save_chat_message(conn, session["id"], "assistant", answer, source_scope)
        artifact = row_dict(
            conn.execute(
                """
                SELECT id, paper_id, attempt_id, artifact_type, scope_key, content, model, created_at, updated_at
                FROM llm_artifacts
                WHERE paper_id = ? AND artifact_type = ? AND scope_key = ?
                """,
                (paper_id, artifact_type, scope_key),
            ).fetchone()
        )
        messages = list_chat_messages(conn, session["id"])
    return {"artifact": artifact, "assistant_message": assistant_message, "messages": messages}


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
