import json
import os
import re

from db import connect
from repository import is_ignored_attempt, refresh_paper_from_latest_attempt
from review_cleaner import clean_reviews_for_attempt
from utils import content_value, db_text, normalize_title, now_iso, timestamp_to_iso


class OpenReviewImportError(RuntimeError):
    pass


def note_to_dict(note) -> dict:
    result = {}
    for key in (
        "id",
        "forum",
        "replyto",
        "number",
        "cdate",
        "mdate",
        "pdate",
        "odate",
        "tcdate",
        "tmdate",
        "invitations",
        "readers",
        "writers",
        "signatures",
        "content",
    ):
        if hasattr(note, key):
            value = getattr(note, key)
            try:
                json.dumps(value)
                result[key] = value
            except TypeError:
                result[key] = str(value)
    return result


def make_openreview_clients():
    try:
        import openreview
    except ImportError as exc:
        raise OpenReviewImportError(
            "The openreview package is not installed. Run `pip3 install openreview-py` first."
        ) from exc

    username = os.environ.get("OPENREVIEW_USERNAME")
    password = os.environ.get("OPENREVIEW_PASSWORD")
    if not username or not password:
        raise OpenReviewImportError(
            "Missing OpenReview credentials. Copy `.env.example` to `.env.local` and fill in OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD."
        )

    clients = []
    requested = os.environ.get("OPENREVIEW_API_VERSION", "auto").lower()
    if requested in ("auto", "2", "api2"):
        try:
            clients.append(
                openreview.api.OpenReviewClient(
                    baseurl="https://api2.openreview.net",
                    username=username,
                    password=password,
                )
            )
        except Exception:
            if requested != "auto":
                raise
    if requested in ("auto", "1", "api1", "v1"):
        try:
            clients.append(
                openreview.Client(
                    baseurl="https://api.openreview.net",
                    username=username,
                    password=password,
                )
            )
        except Exception:
            if requested != "auto":
                raise
    if not clients:
        raise OpenReviewImportError("Could not create an OpenReview client with the configured credentials.")
    return clients


def get_thread_with_client(client, forum_id: str) -> tuple[dict, list[dict]]:
    root = client.get_note(forum_id)
    try:
        replies = client.get_notes(forum=forum_id)
    except TypeError:
        replies = client.get_notes(content={"forum": forum_id})
    notes = [note_to_dict(note) for note in replies]
    root_dict = note_to_dict(root)
    if not any(note.get("id") == root_dict.get("id") for note in notes):
        notes.insert(0, root_dict)
    return root_dict, notes


def get_thread_from_openreview(forum_id: str) -> tuple[dict, list[dict]]:
    last_error = None
    for client in make_openreview_clients():
        try:
            return get_thread_with_client(client, forum_id)
        except Exception as exc:
            last_error = exc
    raise OpenReviewImportError(f"OpenReview import failed: {last_error}")


def candidate_author_ids(client) -> list[str]:
    username = os.environ.get("OPENREVIEW_USERNAME") or ""
    candidates = {username}
    try:
        profile = client.get_profile(username)
    except Exception:
        profile = None
    if profile:
        for attr in ("id", "email"):
            value = getattr(profile, attr, None)
            if value:
                candidates.add(value)
        content = getattr(profile, "content", None) or {}
        for key in ("emails", "preferredEmail"):
            value = content.get(key)
            if isinstance(value, dict) and "value" in value:
                value = value["value"]
            if isinstance(value, list):
                candidates.update(str(item) for item in value if item)
            elif value:
                candidates.add(str(value))
        names = content.get("names")
        if isinstance(names, dict) and "value" in names:
            names = names["value"]
        if isinstance(names, list):
            for name in names:
                if not isinstance(name, dict):
                    continue
                fullname = name.get("fullname")
                if fullname:
                    candidates.add(fullname)
    return [candidate for candidate in candidates if candidate]


def looks_like_submission(note: dict, author_ids: set[str]) -> bool:
    if note.get("replyto"):
        return False
    content = note.get("content") or {}
    if not content_value(content, "title"):
        return False
    note_authors = content_value(content, "authorids") or content_value(content, "authors") or []
    if isinstance(note_authors, str):
        note_authors = [note_authors]
    note_authors = {str(author) for author in note_authors}
    if note_authors & author_ids:
        return True
    invitations = " ".join(note.get("invitations") or []).lower()
    return "submission" in invitations or "blind-submission" in invitations


def discover_openreview_submissions() -> list[tuple[str, object]]:
    found: dict[str, object] = {}
    errors = []
    for client in make_openreview_clients():
        ids = set(candidate_author_ids(client))
        if not ids:
            continue
        queries = []
        for author_id in ids:
            queries.extend(
                (
                    {"content": {"authorids": author_id}},
                    {"tauthor": author_id},
                    {"signature": author_id},
                )
            )
        for query in queries:
            try:
                notes = client.get_all_notes(**query)
            except Exception as exc:
                errors.append(str(exc))
                continue
            for note in notes:
                note_dict = note_to_dict(note)
                if looks_like_submission(note_dict, ids):
                    forum_id = note_dict.get("forum") or note_dict.get("id")
                    if forum_id:
                        found.setdefault(forum_id, client)
    if not found and errors:
        raise OpenReviewImportError("No submissions discovered. Last OpenReview error: " + errors[-1])
    return list(found.items())


def classify_review(note: dict) -> str:
    invitations = " ".join(note.get("invitations") or []).lower()
    content = note.get("content") or {}
    if "decision" in invitations or content_value(content, "decision"):
        return "decision"
    if "meta" in invitations:
        return "meta_review"
    if "comment" in invitations:
        return "comment"
    if "rebuttal" in invitations or "response" in invitations:
        return "response"
    return "review"


def as_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None


def summarize_text(content: dict) -> str:
    parts = []
    for key in ("summary", "review", "main_review", "comment", "decision", "metareview", "recommendation"):
        value = content_value(content, key)
        if value:
            parts.append(str(value))
    return "\n\n".join(parts)


def note_time(note: dict) -> str | None:
    for key in ("cdate", "tcdate", "pdate", "mdate", "tmdate"):
        value = timestamp_to_iso(note.get(key))
        if value:
            return value
    return None


def extract_decision(notes: list[dict]) -> tuple[str | None, str | None]:
    decisions = []
    for note in notes:
        if classify_review(note) != "decision":
            continue
        content = note.get("content") or {}
        text = content_value(content, "decision") or summarize_text(content)
        decisions.append((note_time(note), db_text(text)))
    if not decisions:
        return None, None
    decisions.sort(key=lambda item: item[0] or "")
    return decisions[-1]


def save_openreview_thread_data(root: dict, notes: list[dict], source_url: str) -> dict:
    content = root.get("content") or {}
    title = db_text(content_value(content, "title")) or "Untitled OpenReview submission"
    authors = content_value(content, "authors") or content_value(content, "authorids") or []
    venue = db_text(content_value(content, "venue", "venueid"))
    abstract = db_text(content_value(content, "abstract"))
    pdf = db_text(content_value(content, "pdf"))
    timestamp = now_iso()
    root_forum_id = root.get("forum") or root.get("id")
    submitted_at = note_time(root)
    decision_at, decision = extract_decision(notes)

    with connect() as conn:
        if is_ignored_attempt(conn, root_forum_id, root.get("id")):
            return {"paper_id": None, "attempt_id": None, "reviews": 0, "ignored": True}

        existing = conn.execute(
            "SELECT id, paper_id FROM attempts WHERE openreview_forum_id = ? AND openreview_note_id = ?",
            (root_forum_id, root.get("id")),
        ).fetchone()
        if existing:
            paper_id = existing["paper_id"]
            attempt_id = existing["id"]
            conn.execute("UPDATE papers SET updated_at = ? WHERE id = ?", (timestamp, paper_id))
            conn.execute(
                """
                UPDATE attempts
                SET openreview_url = ?, venue = ?, title = ?, submitted_at = ?, decision_at = ?,
                    decision = ?, abstract = ?, pdf_url = ?, raw_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    source_url,
                    venue,
                    title,
                    submitted_at,
                    decision_at,
                    decision,
                    abstract,
                    pdf,
                    json.dumps(root, ensure_ascii=False),
                    timestamp,
                    attempt_id,
                ),
            )
        else:
            normalized = normalize_title(title)
            row = conn.execute("SELECT id FROM papers WHERE normalized_title = ?", (normalized,)).fetchone()
            if row:
                paper_id = row["id"]
                conn.execute(
                    "UPDATE papers SET title = ?, authors = ?, updated_at = ? WHERE id = ?",
                    (title, json.dumps(authors, ensure_ascii=False), timestamp, paper_id),
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO papers (title, normalized_title, authors, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (title, normalized, json.dumps(authors, ensure_ascii=False), timestamp, timestamp),
                )
                paper_id = cursor.lastrowid
            cursor = conn.execute(
                """
                INSERT INTO attempts (
                    paper_id, openreview_forum_id, openreview_note_id, openreview_url,
                    venue, title, submitted_at, decision_at, decision, abstract, pdf_url,
                    raw_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    root_forum_id,
                    root.get("id"),
                    source_url,
                    venue,
                    title,
                    submitted_at,
                    decision_at,
                    decision,
                    abstract,
                    pdf,
                    json.dumps(root, ensure_ascii=False),
                    timestamp,
                    timestamp,
                ),
            )
            attempt_id = cursor.lastrowid

        refresh_paper_from_latest_attempt(conn, paper_id)

        imported_reviews = 0
        for note in notes:
            if note.get("id") == root.get("id"):
                continue
            note_content = note.get("content") or {}
            review_type = classify_review(note)
            reviewer = ", ".join(note.get("signatures") or [])
            text = summarize_text(note_content)
            if not text and review_type == "comment":
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO reviews (
                    attempt_id, openreview_note_id, reviewer, review_type, rating, confidence,
                    summary, strengths, weaknesses, questions, text, raw_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    note.get("id"),
                    reviewer,
                    review_type,
                    as_float(content_value(note_content, "rating", "recommendation")),
                    as_float(content_value(note_content, "confidence")),
                    db_text(content_value(note_content, "summary")),
                    db_text(content_value(note_content, "strengths")),
                    db_text(content_value(note_content, "weaknesses")),
                    db_text(content_value(note_content, "questions")),
                    db_text(text),
                    json.dumps(note, ensure_ascii=False),
                    timestamp,
                ),
            )
            imported_reviews += 1
        clean_reviews_for_attempt(conn, attempt_id, force=True)
    return {"paper_id": paper_id, "attempt_id": attempt_id, "reviews": imported_reviews}


def save_openreview_thread(forum_id: str, source_url: str) -> dict:
    root, notes = get_thread_from_openreview(forum_id)
    return save_openreview_thread_data(root, notes, source_url)


def sync_openreview_account() -> dict:
    discovered = discover_openreview_submissions()
    imported = 0
    skipped = 0
    failed = []
    for forum_id, client in discovered:
        try:
            root, notes = get_thread_with_client(client, forum_id)
            result = save_openreview_thread_data(root, notes, f"https://openreview.net/forum?id={forum_id}")
            if result.get("ignored"):
                skipped += 1
            else:
                imported += 1
        except Exception as exc:
            failed.append({"forum_id": forum_id, "error": str(exc)})
    return {"discovered": len(discovered), "imported": imported, "skipped": skipped, "failed": failed}
