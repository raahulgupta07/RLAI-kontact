"""
Memory & feedback system for KONTACT.
Stores agent memories and user feedback as JSON files in data/.
Builds a learning context block that can be injected into RAG prompts.
"""

import json, os
from datetime import datetime, timezone
import config

MEMORIES_FILE = os.path.join(config.DATA_DIR, "memories.json")
FEEDBACK_FILE = os.path.join(config.DATA_DIR, "feedback.json")


# ─── helpers ───

def _load_json(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_json(path: str, data: list):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── MEMORY STORAGE ───

def save_memory(fact: str):
    """Append a fact with timestamp to memories.json."""
    memories = _load_json(MEMORIES_FILE)
    memories.append({
        "fact": fact,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    _save_json(MEMORIES_FILE, memories)


def get_memories(limit: int = 10) -> list:
    """Return the last N memories (most recent first)."""
    memories = _load_json(MEMORIES_FILE)
    return memories[-limit:][::-1]


def clear_memories():
    """Clear all stored memories."""
    _save_json(MEMORIES_FILE, [])


# ─── FEEDBACK STORAGE ───

def save_feedback(session_id: str, question: str, answer: str, rating: str):
    """Save thumbs-up / thumbs-down feedback for a response."""
    feedback = _load_json(FEEDBACK_FILE)
    feedback.append({
        "session_id": session_id,
        "question": question,
        "answer": answer,
        "rating": rating,  # "up" or "down"
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    _save_json(FEEDBACK_FILE, feedback)


def get_good_feedback(limit: int = 5) -> list:
    """Return the most recent approved (rating='up') responses."""
    feedback = _load_json(FEEDBACK_FILE)
    good = [f for f in feedback if f.get("rating") == "up"]
    return good[-limit:][::-1]


def get_bad_feedback(limit: int = 3) -> list:
    """Return the most recent rejected (rating='down') responses."""
    feedback = _load_json(FEEDBACK_FILE)
    bad = [f for f in feedback if f.get("rating") == "down"]
    return bad[-limit:][::-1]


# ─── BUILD LEARNING CONTEXT ───

def build_learning_context() -> str:
    """
    Build a text block combining memories, feedback, and catalog summary
    for injection into the RAG system prompt.
    """
    sections = []

    # Agent memories
    memories = get_memories(limit=10)
    if memories:
        lines = [f"- {m['fact']}" for m in memories]
        sections.append("AGENT MEMORIES\n" + "\n".join(lines))

    # Approved responses
    good = get_good_feedback(limit=5)
    if good:
        lines = []
        for g in good:
            lines.append(f"Q: {g['question']}\nA: {g['answer']}")
        sections.append("APPROVED RESPONSES\n" + "\n---\n".join(lines))

    # Patterns to avoid
    bad = get_bad_feedback(limit=3)
    if bad:
        lines = []
        for b in bad:
            lines.append(f"Q: {b['question']}\nA (rejected): {b['answer']}")
        sections.append("AVOID THESE PATTERNS\n" + "\n---\n".join(lines))

    # Catalog summary (from tools.py, being created by another agent)
    try:
        from tools import get_catalog_summary
        summary = get_catalog_summary()
        if summary:
            sections.append("CATALOG SUMMARY\n" + summary)
    except (ImportError, Exception):
        pass

    if not sections:
        return ""

    return "\n\n".join(sections)
