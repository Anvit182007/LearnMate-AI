"""
SQLite persistence layer for LearnMate AI.

All database access goes through the functions in this module.
The database file is created alongside this file as ``learnmate.db``.
``init_db()`` is called automatically at the bottom of this module so the
schema is always ready the moment any page imports from here.
"""

import sqlite3
from pathlib import Path

import pandas as pd

_DB_PATH = Path(__file__).parent / "learnmate.db"



def _connect() -> sqlite3.Connection:
    """Return a new connection with row_factory and foreign keys enabled."""
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables (IF NOT EXISTS).  Safe to call multiple times."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT    NOT NULL UNIQUE,
                learning_level  TEXT    NOT NULL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id      INTEGER NOT NULL REFERENCES students(id),
                subject         TEXT    NOT NULL,
                topic           TEXT    NOT NULL,
                difficulty      TEXT    NOT NULL,
                score           INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                accuracy        REAL    NOT NULL,
                attempted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS question_responses (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id      INTEGER NOT NULL REFERENCES quiz_attempts(id),
                question_text   TEXT    NOT NULL,
                correct_answer  TEXT    NOT NULL,
                student_answer  TEXT    NOT NULL,
                is_correct      INTEGER NOT NULL
            );
            """
        )


# ---------------------------------------------------------------------------
# Student helpers
# ---------------------------------------------------------------------------

def upsert_student(name: str, learning_level: str) -> int:
    """Insert or update a student record by name.

    If no student with *name* exists, one is created.  If one already exists
    their ``learning_level`` is updated.  Returns the student's ``id``.
    """
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO students (name, learning_level) VALUES (?, ?)",
            (name, learning_level),
        )
        conn.execute(
            "UPDATE students SET learning_level = ? WHERE name = ?",
            (learning_level, name),
        )
        row = conn.execute(
            "SELECT id FROM students WHERE name = ?", (name,)
        ).fetchone()
    return row["id"]


def get_student(student_id: int) -> dict | None:
    """Return a dict with keys ``id, name, learning_level, created_at``, or
    ``None`` if the student does not exist."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name, learning_level, created_at FROM students WHERE id = ?",
            (student_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


# ---------------------------------------------------------------------------
# Quiz attempt helpers
# ---------------------------------------------------------------------------

def save_quiz_attempt(
    student_id: int,
    subject: str,
    topic: str,
    difficulty: str,
    score: int,
    total_questions: int,
    accuracy: float,
) -> int:
    """Insert a row into ``quiz_attempts`` and return the new attempt ``id``."""
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO quiz_attempts
                (student_id, subject, topic, difficulty, score, total_questions, accuracy)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (student_id, subject, topic, difficulty, score, total_questions, accuracy),
        )
    return cursor.lastrowid


def save_question_responses(attempt_id: int, responses: list[dict]) -> None:
    """Bulk-insert *responses* into ``question_responses``.

    Each dict must contain the keys:
    ``question_text``, ``correct_answer``, ``student_answer``, ``is_correct``.
    """
    rows = [
        (
            attempt_id,
            r["question_text"],
            r["correct_answer"],
            r["student_answer"],
            r["is_correct"],
        )
        for r in responses
    ]
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO question_responses
                (attempt_id, question_text, correct_answer, student_answer, is_correct)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )


# ---------------------------------------------------------------------------
# DataFrame query helpers
# ---------------------------------------------------------------------------

_ATTEMPT_COLUMNS = [
    "id", "student_id", "subject", "topic", "difficulty",
    "score", "total_questions", "accuracy", "attempted_at",
]

_RESPONSE_COLUMNS = [
    "id", "attempt_id", "question_text", "correct_answer",
    "student_answer", "is_correct",
]

_ACCURACY_SUMMARY_COLUMNS = ["subject", "topic", "attempts", "avg_accuracy"]


def get_attempts_by_student(student_id: int) -> pd.DataFrame:
    """Return all ``quiz_attempts`` rows for *student_id* as a DataFrame."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM quiz_attempts WHERE student_id = ? ORDER BY attempted_at",
            (student_id,),
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=_ATTEMPT_COLUMNS)
    return pd.DataFrame([dict(r) for r in rows], columns=_ATTEMPT_COLUMNS)


def get_responses_by_attempt(attempt_id: int) -> pd.DataFrame:
    """Return all ``question_responses`` rows for *attempt_id* as a DataFrame."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM question_responses WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=_RESPONSE_COLUMNS)
    return pd.DataFrame([dict(r) for r in rows], columns=_RESPONSE_COLUMNS)


def get_topic_accuracy_summary(student_id: int) -> pd.DataFrame:
    """Return a summary DataFrame with columns
    ``[subject, topic, attempts, avg_accuracy]`` grouped by subject and topic."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                subject,
                topic,
                COUNT(*)       AS attempts,
                AVG(accuracy)  AS avg_accuracy
            FROM quiz_attempts
            WHERE student_id = ?
            GROUP BY subject, topic
            ORDER BY subject, topic
            """,
            (student_id,),
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=_ACCURACY_SUMMARY_COLUMNS)
    return pd.DataFrame([dict(r) for r in rows], columns=_ACCURACY_SUMMARY_COLUMNS)


# ---------------------------------------------------------------------------
# Module-level initialisation — run once at import time
# ---------------------------------------------------------------------------

init_db()
