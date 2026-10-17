"""
pages/study_planner.py — Personalised Study Planner page.

Retrieves the student's quiz performance history, identifies weak topics
(accuracy < 60 %), presents a colour-coded accuracy table, and calls the
existing study-planner logic to produce a narrative weekly study plan.

Additionally provides a "Generate Schedule" form where students enter
subjects/topics, available study time, and a target date to receive a
practical day-by-day study schedule powered by the Groq LLM adapter.

Plan-source labelling rules
───────────────────────────
* Demo mode (no API key) → always "rule-based (demo mode — not AI-generated)".
* Live mode, LLM succeeded  → "AI-generated".
* Live mode, LLM failed/fell back → study_planner prepends a visible
  "> ⚠️ Note: The AI study plan could not be generated." marker; the page
  detects this marker and labels the plan as "rule-based fallback".

The page never claims AI generation when none occurred.
"""

from __future__ import annotations

import datetime

import pandas as pd
import streamlit as st

from learnmate_ai import database, llm_adapter, quiz_engine, study_planner

# Accuracy thresholds for colour coding (matches detect_weak_topics default)
_WEAK_THRESHOLD = 0.60   # below this → weak (red)
_GOOD_THRESHOLD = 0.80   # at/above this → strong (green); between → amber

# Marker prepended by study_planner._rule_based_plan when LLM fails
_LLM_FALLBACK_MARKER = "The AI study plan could not be generated."


def _has_profile() -> bool:
    return "student_id" in st.session_state


def _colour_accuracy(val: float) -> str:
    """Return CSS colour string for a Pandas Styler .map() call."""
    if val < _WEAK_THRESHOLD:
        return "background-color: #ffe0e0; color: #8b0000"
    if val < _GOOD_THRESHOLD:
        return "background-color: #fff3cd; color: #856404"
    return "background-color: #d4edda; color: #155724"


def _plan_cache_key(level: str, n_rows: int) -> tuple[str, int]:
    """Cache key: invalidated when the level changes or new quiz rows appear."""
    return (level, n_rows)


def _detect_plan_source(plan_text: str) -> str:
    """Return a human-readable source label for *plan_text*.

    Inspects the content that study_planner.py produces:
    - Demo/rule-based plans contain the demo-mode blockquote marker.
    - LLM-failure fallbacks contain the LLM-fallback marker.
    - Otherwise, the LLM generated the plan.

    Callers must also check is_demo_mode() before calling this.
    """
    if _LLM_FALLBACK_MARKER in plan_text:
        return "rule-based fallback (AI generation failed — not AI-generated)"
    return "AI-generated based on your quiz history"


def render() -> None:
    """Render the Personalised Study Planner page."""
    st.title("Personalised Study Planner")

    # ── Profile guard ─────────────────────────────────────────────────────────
    if not _has_profile():
        st.warning(
            "Please complete your **Student Profile** before viewing your study plan. "
            "Your plan is personalised to your quiz history and learning level.",
            icon="⚠️",
        )
        return

    student_id = st.session_state.student_id
    level      = st.session_state.get("learning_level", "Beginner")
    name       = st.session_state.get("student_name", "Student")

    st.write(f"Here is your personalised study plan, **{name}**.")

    # ── Demo mode badge ───────────────────────────────────────────────────────
    if llm_adapter.is_demo_mode():
        st.info(
            "Demo Mode — No API key is configured. "
            "The study plan below uses rule-based recommendations, not AI.",
            icon="📚",
        )

    # ── Load performance data ─────────────────────────────────────────────────
    try:
        summary_df = database.get_topic_accuracy_summary(student_id)
    except Exception:
        st.error(
            "Your quiz history could not be loaded. "
            "Please try refreshing the page."
        )
        return

    # ── Empty history ─────────────────────────────────────────────────────────
    if summary_df.empty:
        st.info(
            "You haven't taken any quizzes yet. "
            "Head to the **Smart Quiz Generator** to get started — "
            "your personalised study plan will appear here once you have some results.",
            icon="💡",
        )
        return

    # ── Accuracy table ────────────────────────────────────────────────────────
    st.subheader("Topic Accuracy Summary")
    st.caption(
        f"Topics below **{round(_WEAK_THRESHOLD * 100)}%** accuracy are flagged for revision."
    )

    display_df = summary_df.copy()
    display_df["accuracy %"] = (display_df["avg_accuracy"] * 100).round(1)
    display_df = display_df.rename(columns={
        "subject":    "Subject",
        "topic":      "Topic",
        "attempts":   "Quizzes Taken",
        "accuracy %": "Accuracy %",
    }).drop(columns=["avg_accuracy"])

    styled = (
        display_df.style
        .map(_colour_accuracy, subset=["Accuracy %"])
        .format({"Accuracy %": "{:.1f}%"})
    )
    st.dataframe(styled, width="stretch", hide_index=True)

    # ── Weak topic summary ────────────────────────────────────────────────────
    weak_topics = quiz_engine.detect_weak_topics(summary_df, threshold=_WEAK_THRESHOLD)
    if weak_topics:
        n_weak = len(weak_topics)
        worst  = weak_topics[0]
        st.warning(
            f"**{n_weak} topic{'s' if n_weak > 1 else ''} need attention.** "
            f"Your lowest accuracy is **{round(worst['avg_accuracy'] * 100, 1)}%** "
            f"on {worst['subject']} — *{worst['topic']}*.",
            icon="⚠️",
        )
    else:
        st.success(
            "All topics are above the 60% threshold — great work! "
            "Keep taking quizzes to maintain and improve your scores.",
            icon="🌟",
        )

    # ── Study plan (quiz-history-based narrative) ─────────────────────────────
    st.divider()
    st.subheader("Your Study Plan")

    # Cache key includes level AND number of quiz rows so new results invalidate it.
    cache_key = _plan_cache_key(level, len(summary_df))
    if st.session_state.get("study_plan_cache_key") != cache_key:
        st.session_state.study_plan_text      = None
        st.session_state.study_plan_cache_key = cache_key

    refresh_clicked = st.button("Refresh Plan", help="Regenerate the study plan")
    if refresh_clicked:
        st.session_state.study_plan_text = None

    if st.session_state.get("study_plan_text") is None:
        with st.spinner("Building your study plan…"):
            try:
                plan_text = study_planner.build_study_plan(
                    summary_df=summary_df,
                    level=level,
                    threshold=_WEAK_THRESHOLD,
                    use_llm=True,
                )
                st.session_state.study_plan_text = plan_text
            except Exception:
                st.error(
                    "Your study plan could not be generated at this time. "
                    "Please try clicking **Refresh Plan**, or check back later."
                )
                return

    plan = st.session_state.study_plan_text

    # ── Plan source label ─────────────────────────────────────────────────────
    if llm_adapter.is_demo_mode():
        source_label = "rule-based recommendations (demo mode — not AI-generated)"
    else:
        source_label = _detect_plan_source(plan)
    st.caption(f"Plan source: {source_label}.")

    st.markdown(plan)

    # ── Day-by-Day Schedule Generator ────────────────────────────────────────
    st.divider()
    st.subheader("Generate a Day-by-Day Schedule")
    st.write(
        "Enter your subjects, topics, available study time, and target date "
        "to get a practical daily schedule. "
        "Weak topics from your quiz history are automatically prioritised."
    )

    _render_schedule_form(
        summary_df=summary_df,
        level=level,
        weak_topics=weak_topics,
    )


# ---------------------------------------------------------------------------
# Schedule form helper
# ---------------------------------------------------------------------------

_MAX_TOPICS = 5   # maximum subject/topic rows in the form
_SCHEDULE_FALLBACK_MARKER = "The AI scheduled plan could not be generated."


def _detect_schedule_source(schedule_text: str) -> str:
    """Return a human-readable source label for the schedule text."""
    if _SCHEDULE_FALLBACK_MARKER in schedule_text:
        return "rule-based fallback (AI generation failed — not AI-generated)"
    if "Demo Mode" in schedule_text:
        return "rule-based schedule (demo mode — not AI-generated)"
    return "AI-generated"


def _render_schedule_form(
    summary_df: pd.DataFrame,
    level: str,
    weak_topics: list[dict],
) -> None:
    """Render the day-by-day schedule generator form and output section."""

    # ── Inputs ────────────────────────────────────────────────────────────────
    st.markdown("**Step 1 — Subjects & Topics**")
    st.caption(
        f"Enter up to {_MAX_TOPICS} subject/topic pairs you want to cover. "
        "Leave rows blank to skip them."
    )

    col_subj, col_topic = st.columns(2)
    with col_subj:
        st.markdown("**Subject**")
    with col_topic:
        st.markdown("**Topic**")

    subject_inputs: list[str] = []
    topic_inputs: list[str] = []

    for i in range(_MAX_TOPICS):
        c1, c2 = st.columns(2)
        with c1:
            subject_inputs.append(
                st.text_input(
                    f"Subject {i + 1}",
                    key=f"sched_subject_{i}",
                    label_visibility="collapsed",
                    placeholder="e.g. Mathematics" if i == 0 else "",
                )
            )
        with c2:
            topic_inputs.append(
                st.text_input(
                    f"Topic {i + 1}",
                    key=f"sched_topic_{i}",
                    label_visibility="collapsed",
                    placeholder="e.g. Algebra" if i == 0 else "",
                )
            )

    st.markdown("**Step 2 — Study Time & Target Date**")
    col_hours, col_date = st.columns(2)
    with col_hours:
        hours_per_day = st.slider(
            "Available study hours per day",
            min_value=0.5,
            max_value=8.0,
            value=1.5,
            step=0.5,
            key="sched_hours",
            help="How many hours can you dedicate to studying each day?",
        )
    with col_date:
        today = datetime.date.today()
        target_date = st.date_input(
            "Target exam / completion date",
            value=today + datetime.timedelta(weeks=2),
            min_value=today + datetime.timedelta(days=1),
            key="sched_target_date",
            help="The date you want to be ready by.",
        )

    if weak_topics:
        n_weak = len(weak_topics)
        st.info(
            f"✅ **{n_weak} weak topic{'s' if n_weak > 1 else ''} detected** from your "
            f"quiz history — {'they' if n_weak > 1 else 'it'} will be automatically "
            "prioritised in the schedule.",
            icon="⚠️",
        )
    else:
        st.info(
            "No weak topics detected — a balanced schedule will be generated "
            "across your chosen subjects and topics.",
            icon="💡",
        )

    submitted = st.button("Generate Study Plan", type="primary", key="sched_submit_btn")

    # ── Validation & generation ───────────────────────────────────────────────
    if not submitted:
        # Show previously generated schedule if cached
        if st.session_state.get("schedule_text"):
            _render_schedule_output(st.session_state["schedule_text"])
        return

    # Filter out blank rows
    pairs = [
        (s.strip(), t.strip())
        for s, t in zip(subject_inputs, topic_inputs)
        if s.strip() and t.strip()
    ]

    # Validation
    errors: list[str] = []

    if not pairs and not weak_topics:
        errors.append(
            "Please enter at least one subject and topic, "
            "or take a quiz first so weak topics can be detected."
        )

    # Check for partial rows (one filled, other empty)
    for i, (s, t) in enumerate(zip(subject_inputs, topic_inputs)):
        s, t = s.strip(), t.strip()
        if bool(s) != bool(t):
            errors.append(
                f"Row {i + 1}: both **Subject** and **Topic** must be filled in, "
                "or both left blank."
            )

    if errors:
        for err in errors:
            st.error(err)
        return

    subjects = [p[0] for p in pairs]
    topics   = [p[1] for p in pairs]
    date_str = target_date.strftime("%Y-%m-%d")

    with st.spinner("Generating your day-by-day schedule…"):
        try:
            schedule_text = study_planner.build_scheduled_plan(
                subjects=subjects,
                topics=topics,
                hours_per_day=hours_per_day,
                target_date=date_str,
                summary_df=summary_df,
                level=level,
                threshold=_WEAK_THRESHOLD,
                use_llm=True,
            )
            st.session_state["schedule_text"] = schedule_text
        except Exception:
            st.error(
                "Your schedule could not be generated. "
                "Please try again or check your connection."
            )
            return

    _render_schedule_output(st.session_state["schedule_text"])


def _render_schedule_output(schedule_text: str) -> None:
    """Display a generated schedule with its source label."""
    source = _detect_schedule_source(schedule_text)
    st.caption(f"Schedule source: {source}.")
    st.markdown(schedule_text)
