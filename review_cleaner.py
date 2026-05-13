import json
import os
from typing import Any

from db import connect
from utils import content_value, db_text, now_iso


SUMMARY_KEYS = ("paper_summary", "summary", "review_summary", "brief_summary")
STRENGTH_KEYS = ("summary_of_strengths", "strengths", "strong_points", "positive_aspects")
WEAKNESS_KEYS = ("summary_of_weaknesses", "weaknesses", "weak_points", "negative_aspects")
QUESTION_KEYS = ("questions", "questions_for_the_authors", "clarity_quality_novelty_and_reproducibility")
BODY_KEYS = (
    "review",
    "main_review",
    "comments",
    "comments_suggestions_and_typos",
    "detailed_comments",
    "justification",
    "overall_assessment",
)


def scalar_content(content: dict[str, Any], *keys: str):
    value = content_value(content, *keys)
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return value


def raw_note(review: dict) -> dict:
    raw = review.get("raw_json")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def note_text_blob(note: dict) -> str:
    content = note.get("content") or {}
    parts = []
    for value in content.values():
        if isinstance(value, dict) and "value" in value:
            value = value["value"]
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (int, float)):
            parts.append(str(value))
    return " ".join(parts).lower()


def is_author_or_committee(note: dict) -> bool:
    signatures = " ".join(note.get("signatures") or []).lower()
    return any(token in signatures for token in ("authors", "program_chairs", "area_chair", "senior_area_chair"))


def is_official_review(review: dict) -> bool:
    note = raw_note(review)
    invitations = " ".join(note.get("invitations") or []).lower()
    if is_author_or_committee(note):
        return False
    if any(token in invitations for token in ("rebuttal", "response", "comment", "decision", "meta_review")):
        return False
    if "official_review" in invitations:
        return True
    if review.get("review_type") != "review":
        return False
    content = note.get("content") or {}
    reviewish_keys = set(SUMMARY_KEYS + STRENGTH_KEYS + WEAKNESS_KEYS + QUESTION_KEYS + BODY_KEYS)
    if reviewish_keys.intersection(content.keys()):
        return True
    blob = note_text_blob(note)
    return bool(blob and any(word in blob for word in ("strength", "weakness", "summary", "soundness", "confidence")))


def content_score(content: dict, *keys: str):
    value = scalar_content(content, *keys)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    import re

    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None


def labeled_section(label: str, value) -> str | None:
    value = db_text(value)
    if not value:
        return None
    return f"{label}\n{value}"


def build_rule_review(review: dict, index: int) -> dict:
    note = raw_note(review)
    content = note.get("content") or {}
    summary = db_text(scalar_content(content, *SUMMARY_KEYS))
    strengths = db_text(scalar_content(content, *STRENGTH_KEYS))
    weaknesses = db_text(scalar_content(content, *WEAKNESS_KEYS))
    questions = db_text(scalar_content(content, *QUESTION_KEYS))
    body = db_text(scalar_content(content, *BODY_KEYS))
    sections = [
        labeled_section("Summary", summary),
        labeled_section("Strengths", strengths),
        labeled_section("Weaknesses", weaknesses),
        labeled_section("Questions / Comments", questions),
        labeled_section("Review", body),
    ]
    text = "\n\n".join(section for section in sections if section)
    if not text:
        text = db_text(review.get("text") or review.get("summary") or review.get("strengths") or "") or "No review text captured."
    return {
        "review_index": index,
        "reviewer": review.get("reviewer"),
        "rating": content_score(content, "rating", "recommendation", "overall_assessment", "overall"),
        "confidence": content_score(content, "confidence"),
        "summary": summary,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "questions": questions,
        "text": text,
        "source_note_ids": json.dumps([review.get("openreview_note_id")], ensure_ascii=False),
        "extraction_method": "rules",
    }


def clean_reviews_for_attempt(conn, attempt_id: int, force: bool = False) -> int:
    existing = conn.execute("SELECT COUNT(*) AS count FROM clean_reviews WHERE attempt_id = ?", (attempt_id,)).fetchone()
    if existing["count"] and not force:
        return 0
    conn.execute("DELETE FROM clean_reviews WHERE attempt_id = ?", (attempt_id,))
    rows = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM reviews WHERE attempt_id = ? ORDER BY COALESCE(created_at, id), id",
            (attempt_id,),
        )
    ]
    official = [row for row in rows if is_official_review(row)]
    for index, review in enumerate(official, start=1):
        clean = build_rule_review(review, index)
        conn.execute(
            """
            INSERT INTO clean_reviews (
                attempt_id, review_index, reviewer, rating, confidence, summary, strengths,
                weaknesses, questions, text, source_note_ids, extraction_method, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                clean["review_index"],
                clean["reviewer"],
                clean["rating"],
                clean["confidence"],
                clean["summary"],
                clean["strengths"],
                clean["weaknesses"],
                clean["questions"],
                clean["text"],
                clean["source_note_ids"],
                clean["extraction_method"],
                now_iso(),
            ),
        )
    return len(official)


def clean_all_reviews(force: bool = False) -> dict:
    cleaned = 0
    attempts = 0
    with connect() as conn:
        for row in conn.execute("SELECT id FROM attempts ORDER BY id"):
            attempts += 1
            cleaned += clean_reviews_for_attempt(conn, row["id"], force=force)
    return {"attempts": attempts, "clean_reviews": cleaned}


def deepseek_available() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY"))
