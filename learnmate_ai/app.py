"""
app.py — LearnMate AI entry point.

Run from the project root:
    streamlit run learnmate_ai/app.py

Responsibilities
----------------
- Configure the global Streamlit page (title, icon, wide layout).
- Initialise the database on first run (init_db is also called at import
  time inside database.py, so a second call is a safe no-op).
- Build the sidebar: app branding, SDG 4 tagline, student name, demo-mode
  banner.
- Declare the five pages via st.navigation / st.Page and run the active page.
- Pages other than Profile are *not* guarded here — each page already
  renders a friendly warning when student_id is absent.  This keeps the
  routing logic simple and avoids double-redirects.
"""

from __future__ import annotations

import streamlit as st

# ── Page config (must be the very first Streamlit call) ───────────────────────
st.set_page_config(
    page_title="LearnMate AI",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Database initialisation ───────────────────────────────────────────────────
# Importing database triggers init_db() at module level; the explicit call
# below is a defensive belt-and-braces guard for future refactors.
from learnmate_ai import database  # noqa: E402 — must follow set_page_config
from learnmate_ai.llm_adapter import is_demo_mode  # noqa: E402

database.init_db()

# ── Page imports (callable form — avoids executing module-level code twice) ───
from learnmate_ai.pages.profile import render as render_profile  # noqa: E402
from learnmate_ai.pages.tutor import render as render_tutor  # noqa: E402
from learnmate_ai.pages.quiz import render as render_quiz  # noqa: E402
from learnmate_ai.pages.study_planner import render as render_planner  # noqa: E402
from learnmate_ai.pages.progress import render as render_progress  # noqa: E402

# ── Navigation ────────────────────────────────────────────────────────────────

_pages = [
    st.Page(
        render_profile,
        title="Student Profile",
        icon="🎓",
        default=True,
        url_path="profile",
    ),
    st.Page(
        render_tutor,
        title="AI Tutor",
        icon="🤖",
        url_path="tutor",
    ),
    st.Page(
        render_quiz,
        title="Smart Quiz",
        icon="📝",
        url_path="quiz",
    ),
    st.Page(
        render_planner,
        title="Study Planner",
        icon="🗓️",
        url_path="study-planner",
    ),
    st.Page(
        render_progress,
        title="Progress Dashboard",
        icon="📊",
        url_path="progress",
    ),
]

current_page = st.navigation(_pages, position="sidebar")

# ── Sidebar branding ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📚 LearnMate AI")
    st.caption("Your Personal Study Coach")
    st.markdown(
        "<small style='color:#57606a;'>🌍 Supporting UN SDG 4 — Quality Education</small>",
        unsafe_allow_html=True,
    )
    st.divider()

    # Student info (shown once profile is saved)
    if "student_name" in st.session_state:
        name  = st.session_state["student_name"]
        level = st.session_state.get("learning_level", "")
        st.markdown(f"**👤 {name}**")
        if level:
            st.caption(f"Level: {level}")
        st.divider()

    # Demo mode indicator
    if is_demo_mode():
        st.warning(
            "**Demo Mode**\n\n"
            "No API key is set. The app is running on sample data — "
            "content is not AI-generated.",
            icon="⚠️",
        )
        st.divider()

    st.caption("LearnMate AI · Academic Project")

# ── Run the selected page ─────────────────────────────────────────────────────
current_page.run()
