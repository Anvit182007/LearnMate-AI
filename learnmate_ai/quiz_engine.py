"""
quiz_engine.py — Pure scoring and weak-topic detection logic.

No UI, no database, no LLM calls.  All functions accept plain Python
objects so they can be unit-tested without any external dependencies.
"""

from __future__ import annotations

import pandas as pd


def evaluate_quiz(questions: list[dict], student_answers: list[str]) -> dict:
    """Score a completed quiz and return per-question feedback.

    Parameters
    ----------
    questions:
        List of MCQ dicts from ``llm_adapter.generate_quiz``, each with
        keys ``question``, ``options`` (list of 4 strings like "A. …")
        and ``answer`` (single letter, e.g. "B").
    student_answers:
        List of the student's selected option strings, single letters,
        empty strings, or ``None`` values — one entry per question.
        Extra answers beyond ``len(questions)`` are ignored.
        Missing answers (shorter list) are treated as unanswered.

    Returns
    -------
    dict with keys:
        score         – int, number of correct answers
        total         – int, number of questions
        accuracy      – float rounded to 4 d.p. (0.0 when total == 0)
        per_question  – list of per-question result dicts
    """
    total = len(questions)
    if total == 0:
        return {"score": 0, "total": 0, "accuracy": 0.0, "per_question": []}

    score = 0
    per_question: list[dict] = []

    for i, q in enumerate(questions):
        # Normalise student answer
        raw_answer = student_answers[i] if i < len(student_answers) else None
        if raw_answer is None:
            student_answer = ""
        else:
            student_answer = str(raw_answer)

        correct_letter = str(q.get("answer", "")).strip()[:1].upper()

        # First non-whitespace char of the student's reply, uppercased
        student_letter = student_answer.strip()[:1].upper() if student_answer.strip() else ""

        is_correct = bool(student_letter and student_letter == correct_letter)
        if is_correct:
            score += 1

        # Resolve the full correct-option string from the options list
        correct_option = ""
        for opt in q.get("options", []):
            if str(opt).startswith(correct_letter + "."):
                correct_option = opt
                break

        per_question.append(
            {
                "question": q.get("question", ""),
                "options": q.get("options", []),
                "correct_answer": correct_option,
                "student_answer": student_answer,
                "is_correct": is_correct,
            }
        )

    accuracy = round(score / total, 4)
    return {"score": score, "total": total, "accuracy": accuracy, "per_question": per_question}


def detect_weak_topics(summary_df: pd.DataFrame, threshold: float = 0.6) -> list[dict]:
    """Return topics where average accuracy falls below *threshold*.

    Parameters
    ----------
    summary_df:
        DataFrame with columns ``subject``, ``topic``, ``attempts``,
        ``avg_accuracy`` — as returned by
        ``database.get_topic_accuracy_summary``.
    threshold:
        Accuracy cut-off (default 0.6 = 60 %).  Topics strictly below
        this value are considered weak.

    Returns
    -------
    List of ``{"subject": …, "topic": …, "avg_accuracy": …}`` dicts
    sorted ascending by ``avg_accuracy`` (worst first).
    Empty list when the DataFrame has no rows or nothing is below the
    threshold.
    """
    if summary_df.empty:
        return []

    weak = summary_df[summary_df["avg_accuracy"] < threshold].copy()
    if weak.empty:
        return []

    weak = weak.sort_values("avg_accuracy", ascending=True)
    return [
        {"subject": row["subject"], "topic": row["topic"], "avg_accuracy": float(row["avg_accuracy"])}
        for _, row in weak.iterrows()
    ]
