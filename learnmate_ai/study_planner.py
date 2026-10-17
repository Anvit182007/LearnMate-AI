"""
study_planner.py — Builds personalised study plans from quiz performance data.

Orchestrates weak-topic detection (quiz_engine) and either calls the LLM
adapter for a narrative plan or falls back to a deterministic rule-based
plan when the adapter is unavailable or demo mode is active.

No UI, no database, no direct LLM calls beyond the adapter interface.
"""

from __future__ import annotations

import pandas as pd

from learnmate_ai import quiz_engine


def build_study_plan(
    summary_df: pd.DataFrame,
    level: str,
    threshold: float = 0.6,
    use_llm: bool = True,
) -> str:
    """Generate a personalised study plan based on quiz performance.

    Parameters
    ----------
    summary_df:
        DataFrame with columns ``subject``, ``topic``, ``attempts``,
        ``avg_accuracy`` — as returned by
        ``database.get_topic_accuracy_summary``.
    level:
        Student's learning level (e.g. "Beginner", "Intermediate",
        "Advanced").  Passed to the LLM for a tailored narrative.
    threshold:
        Accuracy cut-off; topics strictly below this value are considered
        weak (default 0.6 = 60 %).
    use_llm:
        When ``True`` (default) and the LLM adapter is not in demo mode,
        ask the LLM to produce a narrative study plan.  Falls back to the
        rule-based formatter on ``LLMError`` or in demo mode.

    Returns
    -------
    Markdown-formatted study plan string.
    """
    weak_topics = quiz_engine.detect_weak_topics(summary_df, threshold)

    if not weak_topics:
        return (
            "No weak topics detected — great work! "
            "Keep taking quizzes to track your progress."
        )

    # --- Try the live LLM path first ---
    if use_llm:
        try:
            from learnmate_ai import llm_adapter  # noqa: PLC0415

            if not llm_adapter.is_demo_mode():
                try:
                    return llm_adapter.generate_study_plan(weak_topics, level)
                except llm_adapter.LLMError:
                    # Prepend the fallback note; don't expose raw provider details
                    note = (
                        "> ⚠️ **Note:** The AI study plan could not be generated. "
                        "A rule-based plan is shown below instead.\n\n"
                    )
                    return note + _rule_based_plan(weak_topics, level, threshold)
        except Exception:  # noqa: BLE001  # adapter import or any unexpected failure
            pass

    # --- Rule-based path (demo mode, use_llm=False, or import failure) ---
    return _rule_based_plan(weak_topics, level, threshold)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _rule_based_plan(weak_topics: list[dict], level: str, threshold: float) -> str:
    """Build a deterministic Markdown study plan from a list of weak topics.

    Never calls the LLM adapter — safe to use even when the adapter fails.
    The *threshold* is used in the descriptive text so students see the
    exact cut-off that was applied.
    """
    threshold_pct = round(threshold * 100, 1)
    lines: list[str] = []

    lines.append("## 📖 Personalised Study Plan\n")
    lines.append(
        f"Based on your quiz history, the following topics need more attention "
        f"(accuracy below {threshold_pct}%). "
        f"This plan is tailored for a **{level}** learner.\n"
    )

    # Group by subject using a plain dict (insertion-ordered in Python 3.7+)
    by_subject: dict[str, list[dict]] = {}
    for entry in weak_topics:
        subj = entry["subject"]
        if subj not in by_subject:
            by_subject[subj] = []
        by_subject[subj].append(entry)

    lines.append("---\n")
    lines.append("### 🎯 Topics to Revise\n")

    for subject, topics in by_subject.items():
        lines.append(f"**{subject}**\n")
        for t in topics:
            pct = round(t["avg_accuracy"] * 100, 1)
            lines.append(f"- **{t['topic']}** — current accuracy: {pct}%")
            lines.append(f"  - Review core concepts and definitions for *{t['topic']}*.")
            lines.append(
                "  - Work through 2–3 practice problems from your textbook or notes."
            )
            lines.append(
                f"  - Take another LearnMate quiz on *{t['topic']}* to confirm improvement."
            )
        lines.append("")

    # Suggested weekly schedule — every topic gets at least one day;
    # topics share a day when there are more than 7.
    lines.append("---\n")
    lines.append("### 📅 Suggested Weekly Schedule\n")

    all_topics = list(weak_topics)  # already sorted worst-first by detect_weak_topics
    n = len(all_topics)

    if n <= len(_DAYS):
        # Each topic gets its own day; remaining days are for review
        for i, t in enumerate(all_topics):
            lines.append(f"- **{_DAYS[i]}:** {t['subject']} — *{t['topic']}*")
        if n < len(_DAYS):
            remaining = " / ".join(_DAYS[n:])
            lines.append(
                f"- **{remaining}:** Review completed topics or take practice quizzes."
            )
    else:
        # More topics than days — distribute evenly, multiple per day
        for day_idx, day in enumerate(_DAYS):
            # Slice of topics assigned to this day
            day_topics = [all_topics[i] for i in range(n) if i % len(_DAYS) == day_idx]
            if day_topics:
                entries = ", ".join(
                    f"{t['subject']} — *{t['topic']}*" for t in day_topics
                )
                lines.append(f"- **{day}:** {entries}")

    lines.append("")
    lines.append("---\n")
    lines.append(
        "> 💡 **Tip:** Aim for at least 80% accuracy on each topic before moving on. "
        "Regular short study sessions (20–30 minutes) are more effective than one long session."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scheduled plan — day-by-day schedule from user-supplied inputs
# ---------------------------------------------------------------------------

_SCHEDULE_FALLBACK_MARKER = "The AI scheduled plan could not be generated."


def build_scheduled_plan(
    subjects: list[str],
    topics: list[str],
    hours_per_day: float,
    target_date: str,
    summary_df: pd.DataFrame,
    level: str,
    threshold: float = 0.6,
    use_llm: bool = True,
) -> str:
    """Generate a day-by-day study schedule.

    Parameters
    ----------
    subjects:
        Subject names entered by the student.
    topics:
        Corresponding topic names.
    hours_per_day:
        Daily available study time in hours.
    target_date:
        Target exam / completion date string.
    summary_df:
        Topic accuracy summary from ``database.get_topic_accuracy_summary``.
        Used to extract weak topics automatically.
    level:
        Student's learning level.
    threshold:
        Weak-topic accuracy cut-off (default 0.6).
    use_llm:
        When True and the adapter is not in demo mode, delegate to the LLM.

    Returns
    -------
    Markdown-formatted day-by-day schedule string.
    """
    weak_topics = quiz_engine.detect_weak_topics(summary_df, threshold)

    if use_llm:
        try:
            from learnmate_ai import llm_adapter  # noqa: PLC0415

            if not llm_adapter.is_demo_mode():
                try:
                    return llm_adapter.generate_scheduled_plan(
                        subjects=subjects,
                        topics=topics,
                        hours_per_day=hours_per_day,
                        target_date=target_date,
                        weak_topics=weak_topics,
                        level=level,
                    )
                except llm_adapter.LLMError:
                    note = (
                        "> ⚠️ **Note:** The AI scheduled plan could not be generated. "
                        "A rule-based schedule is shown below instead.\n\n"
                    )
                    return note + _rule_based_schedule(
                        subjects, topics, hours_per_day, target_date, weak_topics, level
                    )
        except Exception:  # noqa: BLE001
            pass

    # Demo mode, use_llm=False, or unexpected failure
    try:
        from learnmate_ai import llm_adapter  # noqa: PLC0415

        return llm_adapter.generate_scheduled_plan(
            subjects=subjects,
            topics=topics,
            hours_per_day=hours_per_day,
            target_date=target_date,
            weak_topics=weak_topics,
            level=level,
        )
    except Exception:  # noqa: BLE001
        pass

    return _rule_based_schedule(
        subjects, topics, hours_per_day, target_date, weak_topics, level
    )


def _rule_based_schedule(
    subjects: list[str],
    topics: list[str],
    hours_per_day: float,
    target_date: str,
    weak_topics: list[dict],
    level: str,
) -> str:
    """Build a deterministic day-by-day schedule.  Never calls the LLM."""
    all_items: list[dict] = []
    seen: set[str] = set()

    for w in weak_topics:
        key = f"{w['subject']}|{w['topic']}"
        if key not in seen:
            all_items.append({"subject": w["subject"], "topic": w["topic"], "priority": "high"})
            seen.add(key)

    for s, t in zip(subjects, topics):
        key = f"{s}|{t}"
        if key not in seen:
            all_items.append({"subject": s, "topic": t, "priority": "normal"})
            seen.add(key)

    if not all_items:
        all_items = [{"subject": "General", "topic": "Revision", "priority": "normal"}]

    mins = int(hours_per_day * 60)
    day_names = _DAYS

    lines: list[str] = [
        f"## 🗓️ Day-by-Day Study Schedule ({level} Level)\n",
        f"**Target date:** {target_date}  ",
        f"**Daily study time:** {hours_per_day} hour(s) ({mins} minutes)\n",
    ]

    if weak_topics:
        lines.append("### ⚠️ Priority Topics (from quiz history)\n")
        for w in weak_topics:
            pct = round(w.get("avg_accuracy", 0) * 100, 1)
            lines.append(f"- **{w['subject']} — {w['topic']}** (quiz accuracy: {pct}%)")
        lines.append("")

    lines.append("---\n")

    n = len(all_items)
    n_days = min(14, max(n + 1, 7))
    session_mins = max(20, mins // 3)

    for day_idx in range(n_days):
        item = all_items[day_idx % n]
        day_name = day_names[day_idx % 7]
        priority_tag = "⚠️ Weak topic — prioritised" if item["priority"] == "high" else "📖"
        lines += [
            f"### Day {day_idx + 1} ({day_name}) — {item['subject']}: {item['topic']}",
            f"*{priority_tag}*\n",
            f"- **Review** ({session_mins} min): Re-read notes on *{item['topic']}*.",
            f"- **Practice** ({session_mins} min): Solve 5–8 practice problems.",
            f"- **Self-test** ({session_mins} min): "
            f"Take a LearnMate quiz on *{item['topic']}*.",
            "",
        ]

    lines += [
        f"### Day {n_days + 1} (Final Revision — before {target_date})\n",
        "- Review all topics covered in the schedule.",
        "- Re-take quizzes where accuracy was below 80 %.",
        "- Write a one-page summary of key concepts.\n",
        "---\n",
        "> 💡 **Tip:** Aim for at least 80% accuracy on each topic before moving on. "
        "Regular short sessions (25–30 minutes) are more effective than one long sitting.",
    ]

    return "\n".join(lines)
