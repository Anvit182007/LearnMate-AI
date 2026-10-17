"""
pages/profile.py — Student Profile page.

Lets a student enter or update their display name and learning level.
On save the record is persisted via ``database.upsert_student`` and the
three session-state keys used by every other page are written:

    st.session_state.student_id      – int
    st.session_state.student_name    – str
    st.session_state.learning_level  – str
"""

from __future__ import annotations

import streamlit as st

from learnmate_ai import database

# Supported learning levels — kept in one place so other pages can import
# this list if they need to offer a level override.
LEARNING_LEVELS: list[str] = ["Beginner", "Intermediate", "Advanced"]

# Maximum allowed length for a student name.
_MAX_NAME_LEN = 50


def _current_level_index() -> int:
    """Return the selectbox index for the level already in session state."""
    level = st.session_state.get("learning_level", LEARNING_LEVELS[0])
    try:
        return LEARNING_LEVELS.index(level)
    except ValueError:
        return 0


def render() -> None:
    """Render the Student Profile page."""
    st.title("🎓 Student Profile")
    st.write(
        "Set up your profile so LearnMate AI can personalise your experience. "
        "You can update these details at any time."
    )

    # ------------------------------------------------------------------ #
    # Profile form                                                         #
    # ------------------------------------------------------------------ #
    with st.form("profile_form", clear_on_submit=False):
        name_input = st.text_input(
            "Your Name",
            value=st.session_state.get("student_name", ""),
            max_chars=_MAX_NAME_LEN,
            placeholder="e.g. Alex Johnson",
            help="Used to personalise your study plan and quiz results.",
        )

        level_input = st.selectbox(
            "Learning Level",
            options=LEARNING_LEVELS,
            index=_current_level_index(),
            help=(
                "Beginner — new to the subject  |  "
                "Intermediate — some prior knowledge  |  "
                "Advanced — confident and looking to stretch"
            ),
        )

        submitted = st.form_submit_button("💾 Save Profile", use_container_width=True)

    # ------------------------------------------------------------------ #
    # Validation and persistence                                           #
    # ------------------------------------------------------------------ #
    if submitted:
        name_clean = name_input.strip()

        if not name_clean:
            st.error("⚠️ Please enter your name before saving.")
        elif len(name_clean) > _MAX_NAME_LEN:
            # Belt-and-suspenders: max_chars already enforces this in the UI.
            st.error(f"⚠️ Name must be {_MAX_NAME_LEN} characters or fewer.")
        else:
            student_id = database.upsert_student(name_clean, level_input)

            # Write to session state — all other pages read these keys.
            st.session_state.student_id = student_id
            st.session_state.student_name = name_clean
            st.session_state.learning_level = level_input

            st.success(
                f"✅ Profile saved! Welcome, **{name_clean}** "
                f"({level_input} learner)."
            )

    # ------------------------------------------------------------------ #
    # Current profile summary (shown when a profile exists in session)    #
    # ------------------------------------------------------------------ #
    if "student_id" in st.session_state:
        st.divider()
        st.subheader("📋 Current Profile")

        col1, col2 = st.columns(2)
        col1.metric("Name", st.session_state.student_name)
        col2.metric("Learning Level", st.session_state.learning_level)

        # Fetch fresh from DB to confirm persistence and show metadata.
        record = database.get_student(st.session_state.student_id)
        if record:
            st.caption(
                f"Profile ID: {record['id']}  |  Created: {record['created_at']}"
            )
