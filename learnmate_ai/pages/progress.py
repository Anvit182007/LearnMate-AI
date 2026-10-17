"""
pages/progress.py — Progress Dashboard page.

Displays a student's quiz history as three sections:

1. Summary cards  — total attempts, overall accuracy, weak-topic count.
2. Accuracy over time — Plotly line chart (only when >= 2 data points exist).
3. Subject performance — Plotly bar chart of avg accuracy per subject.

All data is loaded from existing database helpers scoped to the current
student.  No LLM calls are made.  Raw exception details are never shown in
the UI.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from learnmate_ai import database, quiz_engine

_WEAK_THRESHOLD = 0.60


def _has_profile() -> bool:
    return "student_id" in st.session_state


def render() -> None:
    """Render the Progress Dashboard page."""
    st.title("Progress Dashboard")

    # ── Profile guard ─────────────────────────────────────────────────────────
    if not _has_profile():
        st.warning(
            "Please complete your **Student Profile** first. "
            "Your progress is tracked per student.",
            icon="⚠️",
        )
        return

    student_id = st.session_state.student_id
    name       = st.session_state.get("student_name", "Student")

    st.write(f"Here is your learning progress, **{name}**.")

    # ── Load data ─────────────────────────────────────────────────────────────
    try:
        attempts_df = database.get_attempts_by_student(student_id)
        summary_df  = database.get_topic_accuracy_summary(student_id)
    except Exception:
        st.error(
            "Your progress data could not be loaded. "
            "Please try refreshing the page."
        )
        return

    # ── Empty state ───────────────────────────────────────────────────────────
    if attempts_df.empty:
        st.info(
            "No quiz history yet. "
            "Head to the **Smart Quiz Generator** to take your first quiz — "
            "your progress will appear here.",
            icon="💡",
        )
        return

    # ── Section 1: Summary cards ──────────────────────────────────────────────
    st.subheader("Summary")

    total_attempts   = len(attempts_df)
    overall_accuracy = float(attempts_df["accuracy"].mean())
    weak_topics      = quiz_engine.detect_weak_topics(summary_df, threshold=_WEAK_THRESHOLD)
    n_weak           = len(weak_topics)

    # Latest quiz
    latest = attempts_df.iloc[-1]
    latest_score = f"{int(latest['score'])} / {int(latest['total_questions'])}"
    latest_pct   = f"{round(float(latest['accuracy']) * 100, 1)}%"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Quizzes", total_attempts)
    col2.metric("Overall Accuracy", f"{round(overall_accuracy * 100, 1)}%")
    col3.metric("Latest Quiz", latest_pct, help=f"Score: {latest_score}")
    col4.metric(
        "Weak Topics",
        n_weak,
        help="Topics where your average accuracy is below 60%",
    )

    # ── Section 2: Accuracy over time ─────────────────────────────────────────
    st.divider()
    st.subheader("Accuracy Over Time")

    # Parse attempted_at; keep only rows where parsing succeeds
    time_df = attempts_df.copy()
    time_df["attempted_at"] = pd.to_datetime(time_df["attempted_at"], errors="coerce")
    time_df = time_df.dropna(subset=["attempted_at"]).sort_values("attempted_at")

    if len(time_df) < 2:
        st.info(
            "Take at least two quizzes to see an accuracy trend.",
            icon="📈",
        )
    else:
        fig_line = go.Figure()
        fig_line.add_trace(
            go.Scatter(
                x=time_df["attempted_at"],
                y=(time_df["accuracy"] * 100).round(1),
                mode="lines+markers",
                name="Accuracy %",
                line=dict(color="#3b82d4", width=2),
                marker=dict(size=6),
                hovertemplate="%{x|%Y-%m-%d %H:%M}<br>Accuracy: %{y:.1f}%<extra></extra>",
            )
        )
        fig_line.update_layout(
            xaxis_title="Date",
            yaxis_title="Accuracy (%)",
            yaxis=dict(range=[0, 105]),
            height=350,
            margin=dict(l=40, r=20, t=30, b=40),
        )
        st.plotly_chart(fig_line, width="stretch")

    # ── Section 3: Subject performance ────────────────────────────────────────
    st.divider()
    st.subheader("Subject Performance")

    if summary_df.empty:
        st.info("No subject data available yet.", icon="📚")
    else:
        # Roll up to subject level
        subject_df = (
            summary_df
            .groupby("subject", as_index=False)
            .agg(avg_accuracy=("avg_accuracy", "mean"), attempts=("attempts", "sum"))
            .sort_values("avg_accuracy", ascending=False)
        )

        colours = [
            "#d4edda" if row["avg_accuracy"] >= 0.80
            else "#fff3cd" if row["avg_accuracy"] >= _WEAK_THRESHOLD
            else "#ffe0e0"
            for _, row in subject_df.iterrows()
        ]

        fig_bar = go.Figure(
            go.Bar(
                x=subject_df["subject"],
                y=(subject_df["avg_accuracy"] * 100).round(1),
                marker_color=colours,
                text=(subject_df["avg_accuracy"] * 100).round(1).astype(str) + "%",
                textposition="outside",
                hovertemplate="%{x}<br>Avg accuracy: %{y:.1f}%<extra></extra>",
            )
        )
        fig_bar.update_layout(
            xaxis_title="Subject",
            yaxis_title="Average Accuracy (%)",
            yaxis=dict(range=[0, 115]),
            height=350,
            margin=dict(l=40, r=20, t=30, b=60),
        )
        st.plotly_chart(fig_bar, width="stretch")

    # ── Section 4: Weak topic detail ─────────────────────────────────────────
    if weak_topics:
        st.divider()
        st.subheader("Topics to Revise")
        st.caption("Topics where your average accuracy is below 60%:")
        for t in weak_topics:
            pct = round(t["avg_accuracy"] * 100, 1)
            st.markdown(
                f"- **{t['subject']} — {t['topic']}**  "
                f"(accuracy: {pct}%)"
            )
