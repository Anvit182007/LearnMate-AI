# LearnMate AI — Implementation Plan

> **UN SDG 4: Quality Education** | Python · Streamlit · Pandas · Plotly · SQLite · LLM API

---

## Top-Level Overview

LearnMate AI is a personal study coach web application built with Streamlit. Students create a
profile, request AI-generated explanations on any topic, take adaptive multiple-choice quizzes,
and receive a personalised study plan derived from their quiz performance. All quiz history is
persisted in a local SQLite database. When no LLM API key is configured the application falls
back to a demo mode that uses a bundled JSON seed file — the UI makes no claim that demo mode
uses generative AI.

### Scope
- Six navigation pages: AI Tutor, Quiz Generator, Quiz Results, Study Planner, Progress
  Dashboard, Student Profile.
- A thin LLM adapter layer so any OpenAI-compatible provider (or future providers) can be
  plugged in via environment variables.
- Demo mode via a bundled `demo_questions.json` seed file.
- Supporting files: `requirements.txt`, `.env.example`, `.gitignore`, `README.md`.

### Non-Goals (initial version)
- User authentication / login.
- Paid third-party services.
- Deployment infrastructure (Docker, cloud hosting).
- Multi-user isolation (single-user local app).

---

## Folder Structure

```
learnmate_ai/
├── app.py                     # Streamlit entry point, sidebar navigation
├── config.py                  # Reads env vars, exposes settings object
├── database.py                # SQLite schema, CRUD helpers
├── llm_adapter.py             # Provider-agnostic LLM client + demo fallback
├── quiz_engine.py             # Score calculation, accuracy, weak-topic detection
├── study_planner.py           # Rule-based weak-topic list + LLM narrative plan
├── pages/
│   ├── profile.py             # Student Profile page
│   ├── tutor.py               # AI Tutor page
│   ├── quiz.py                # Smart Quiz Generator + inline feedback page
│   ├── results.py             # Quiz Results (last attempt) page
│   ├── planner.py             # Personalized Study Planner page
│   └── dashboard.py           # Progress Dashboard page
├── data/
│   └── demo_questions.json    # Seed questions for demo mode
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Database Design

**File:** `database.py` / `learnmate.db` (auto-created on first run)

### Table: `students`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | auto-increment |
| name | TEXT | student display name |
| learning_level | TEXT | Beginner / Intermediate / Advanced |
| created_at | TIMESTAMP | |

### Table: `quiz_attempts`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| student_id | INTEGER FK | references students.id |
| subject | TEXT | e.g. "Mathematics" |
| topic | TEXT | e.g. "Algebra" |
| difficulty | TEXT | easy / medium / hard |
| score | INTEGER | raw correct count |
| total_questions | INTEGER | |
| accuracy | REAL | 0.0 – 1.0 |
| attempted_at | TIMESTAMP | |

### Table: `question_responses`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| attempt_id | INTEGER FK | references quiz_attempts.id |
| question_text | TEXT | |
| correct_answer | TEXT | |
| student_answer | TEXT | |
| is_correct | INTEGER | 0 or 1 |

---

## AI Integration Design

**File:** `llm_adapter.py`

The adapter exposes three functions consumed by pages and services:

| Function | Purpose |
|---|---|
| `explain_topic(subject, topic, level)` | Returns a plain-language explanation + example |
| `generate_quiz(subject, topic, level, difficulty, n)` | Returns a list of MCQ dicts |
| `generate_study_plan(weak_topics, level)` | Returns a narrative study schedule string |

Internally the adapter checks `config.LLM_PROVIDER` and `config.LLM_API_KEY`:
- If a key is present it constructs an OpenAI-compatible HTTP request (works with OpenAI,
  Groq, Together AI, Mistral, etc. via `LLM_BASE_URL`).
- If no key is present it routes to `_demo_*` functions that draw from `demo_questions.json`
  and return static/rule-based text. The UI layer is responsible for showing the
  "Demo Mode" badge; the adapter simply returns data, never claims AI origin.

MCQ dict schema returned by `generate_quiz`:
```json
{
  "question": "...",
  "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
  "answer": "A"
}
```

---

## Sub-Tasks

---

### Sub-Task 1 — Project Scaffold & Configuration

**Intent**
Establish the folder structure, environment variable handling, dependency list, and supporting
project files so every subsequent sub-task has a stable foundation to build on.

**Expected Outcomes**
- All directories and placeholder files exist.
- `config.py` reads `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_PROVIDER` from
  environment (via `python-dotenv`) and exposes a `Settings` dataclass.
- `requirements.txt` lists all direct dependencies with minimum versions.
- `.env.example` documents every variable.
- `.gitignore` excludes `.env`, `*.db`, `__pycache__`, `.venv`.
- `README.md` contains project description, setup steps, run command, and demo-mode note.

**Todo List**
1. Create the folder tree (`learnmate_ai/`, `learnmate_ai/pages/`, `learnmate_ai/data/`).
2. Write `config.py` — load dotenv, define `Settings` dataclass with all LLM variables and
   a computed `is_demo_mode` boolean.
3. Write `requirements.txt` with: `streamlit>=1.36`, `pandas`, `plotly`, `python-dotenv`,
   `requests`, and `openai` (for the OpenAI-compatible SDK path).
   Use `st.navigation` / `st.Page` API (requires Streamlit ≥ 1.36).
4. Write `.env.example`.
5. Write `.gitignore`.
6. Write `README.md`.

**Relevant Context**
- No existing code.
- `config.LLM_BASE_URL` defaults to `https://api.openai.com/v1` so OpenAI works out of
  the box; other providers override it.

**Status:** `[x] done`

---

### Sub-Task 2 — SQLite Database Layer

**Intent**
Implement all database initialisation, schema creation, and CRUD helpers so pages never
write raw SQL — they call typed Python functions.

**Expected Outcomes**
- `database.py` creates `learnmate.db` and all three tables on first import.
- Functions available: `upsert_student`, `get_student`, `save_quiz_attempt`,
  `save_question_responses`, `get_attempts_by_student`, `get_responses_by_attempt`,
  `get_topic_accuracy_summary`.
- `get_topic_accuracy_summary` returns a Pandas DataFrame with columns
  `[subject, topic, attempts, avg_accuracy]` for use by the dashboard and planner.

**Todo List**
1. Write `database.py`: `init_db()` creates tables with `IF NOT EXISTS`.
2. Implement student CRUD: `upsert_student(name, level)` → student_id,
   `get_student(student_id)`.
3. Implement `save_quiz_attempt(...)` → attempt_id.
4. Implement `save_question_responses(attempt_id, responses_list)`.
5. Implement `get_attempts_by_student(student_id)` → DataFrame.
6. Implement `get_topic_accuracy_summary(student_id)` → DataFrame.
7. Call `init_db()` at module import time so the schema is always ready.

**Relevant Context**
- Use Python's built-in `sqlite3`; no ORM required.
- Store `student_id` in `st.session_state` after profile setup; pass it to every DB call.

**Status:** `[x] done`

---

### Sub-Task 3 — LLM Adapter & Demo Seed Data

**Intent**
Build the provider-agnostic LLM client and the demo fallback so the rest of the application
can call a stable interface regardless of whether an API key is present.

**Expected Outcomes**
- `llm_adapter.py` exposes `explain_topic`, `generate_quiz`, `generate_study_plan`.
- When `config.is_demo_mode` is `True`, functions return data from `demo_questions.json`
  or deterministic rule-based text — never fabricated AI claims.
- `demo_questions.json` contains ≥ 30 questions spread across ≥ 5 subjects and 3 difficulty
  levels, each conforming to the MCQ dict schema.
- When an API key is present, the adapter builds an OpenAI-compatible chat completion
  request with a well-structured prompt and parses JSON from the response.
- API errors are caught and re-raised as a single `LLMError` exception so pages can handle
  them uniformly.
-In demo mode, ensure the AI Tutor provides useful, clearly labelled sample explanations for supported topics rather than only generic placeholder text. The app must remain fully usable without an API key, including quiz generation, scoring, weak-topic detection, study planning and dashboard history. Clearly distinguish sample/demo content from genuinely AI-generated content.


**Todo List**
1. Author `data/demo_questions.json` with subjects: Mathematics, Science, History,
   English, Computer Science — 6+ questions each, spread across difficulties.
2. Write `llm_adapter.py`: define `LLMError`, implement `_call_llm(prompt)` using the
   `openai` SDK pointed at `config.LLM_BASE_URL`.
3. Implement `explain_topic` — live path sends a prompt requesting an explanation and
   two concrete examples; demo path returns a clearly labelled sample explanation for the
   five bundled subjects and a clearly labelled generic explanation for any other topic —
   both explicitly marked as demo/sample content, not AI-generated. The tutor must remain
   fully usable in demo mode.
4. Implement `generate_quiz` — live path requests N MCQs in JSON; parses and validates
   the list; demo path filters `demo_questions.json` by subject/difficulty and returns a
   random sample.
5. Implement `generate_study_plan` — live path sends weak topics + level and requests a
   structured weekly study schedule; demo path returns a rule-based bullet-list string.
6. Write a `is_demo_mode()` convenience re-export so pages can check and show the badge.

**Relevant Context**
- Prompts must instruct the LLM to reply **only** with valid JSON (for quiz and tutor
  endpoints) to make parsing reliable.
- Use `json.loads` with a try/except; on failure retry once with a stricter prompt, then
  raise `LLMError`.

**Status:** `[x] done`

---

### Sub-Task 4 — Quiz Engine & Study Planner Logic ✅

**Intent**
Implement the pure-Python business logic for scoring, weak-topic detection, and study plan
generation so it is fully testable without UI or database dependencies.

**Expected Outcomes**
- `quiz_engine.py` exports `evaluate_quiz(questions, student_answers)` → dict with keys
  `score`, `total`, `accuracy`, `per_question` (list of correct/wrong flags).
- `quiz_engine.py` exports `detect_weak_topics(summary_df, threshold=0.6)` → list of
  `{subject, topic}` dicts where `avg_accuracy < threshold`.
- `study_planner.py` exports `build_study_plan(weak_topics, level, use_llm=True)` →
  string narrative; calls `llm_adapter.generate_study_plan` when `use_llm=True`, otherwise
  generates a formatted bullet list.

**Todo List**
1. Write `quiz_engine.py` — `evaluate_quiz` compares student answers to correct answers
   case-insensitively (first letter match, e.g. "A" vs "A. Newton's first law").
2. Write `detect_weak_topics` — filters the summary DataFrame returned by
   `get_topic_accuracy_summary`.
3. Write `study_planner.py` — `build_study_plan` calls `detect_weak_topics` then either
   the LLM adapter or the rule-based formatter.
4. Add brief docstrings to all public functions.

**Relevant Context**
- `detect_weak_topics` takes the DataFrame from `database.get_topic_accuracy_summary` so
  no direct DB call inside `quiz_engine.py` — keep layers separate.
- The threshold of 0.6 (60%) is configurable via a keyword argument.

**Status:** `[x] done`

---

### Sub-Task 5 — Student Profile Page

**Intent**
Give students a place to enter or update their name and learning level, which is persisted
to the database and stored in session state for the entire session.

**Expected Outcomes**
- `pages/profile.py` renders a form: Name (text input), Learning Level (selectbox:
  Beginner / Intermediate / Advanced), Save button.
- On save, calls `database.upsert_student` and writes `student_id`, `student_name`,
  `learning_level` to `st.session_state`.
- Shows a success confirmation after saving.
- If session state already has a profile, pre-fills the form.
- Input validation: name must be non-empty and ≤ 50 characters.

**Todo List**
1. Write `pages/profile.py` with the form and validation logic.
2. On successful save, set `st.session_state.student_id` etc.
3. Display the current profile summary below the form if a profile exists.

**Relevant Context**
- `app.py` will guard all other pages: if `student_id` is not in session state, redirect
  to Profile with an informational message.

**Status:** `[x] done`

---

### Sub-Task 6 — AI Tutor Page

**Intent**
Let students request a plain-language explanation of any topic, with the AI providing a
summary and concrete examples at their learning level.

**Expected Outcomes**
- `pages/tutor.py` renders inputs: Subject, Topic, Learning Level (pre-filled from profile).
- On submit, calls `llm_adapter.explain_topic`; shows the explanation in a styled card.
- If `is_demo_mode()` is True, shows a visible "⚠️ Demo Mode — not AI-generated" badge
  above the explanation.
- `LLMError` is caught and displayed as a Streamlit error message.
- Input validation: subject and topic must be non-empty.

**Todo List**
1. Write `pages/tutor.py` with inputs and submit button.
2. Show a spinner while the LLM call is in flight.
3. Render the explanation in `st.info` or a custom `st.markdown` card.
4. Add the demo mode badge using `st.warning`.
5. Handle and display `LLMError`.

**Relevant Context**
- Learning level is pre-filled from `st.session_state.learning_level` but can be overridden
  per-request.

**Status:** `[x] done`
**Test result:** `_test_tutor.py` — 16 passed, 0 failed, 0 skipped, exit code 0.

---

### Sub-Task 7 — Smart Quiz Generator & Inline Feedback Page

**Intent**
Generate a multiple-choice quiz for a chosen subject/topic/difficulty, display all questions
on one page, and show per-question feedback inline after the student submits.

**Expected Outcomes**
- `pages/quiz.py` renders: Subject, Topic, Difficulty (easy/medium/hard), Number of
  Questions (3–10 slider, default 5), Generate button.
- Generated questions are stored in `st.session_state.current_quiz`.
- All questions are shown at once; each has a radio-group for A/B/C/D.
- On Submit: calls `quiz_engine.evaluate_quiz`, shows per-question feedback inline
  (✅ correct / ❌ wrong + correct answer revealed), then shows a summary banner
  (score, accuracy %).
- Saves the attempt and responses to the database via `database.save_quiz_attempt` and
  `database.save_question_responses`.
- If `is_demo_mode()`, shows demo badge before generating.

**Todo List**
1. Write `pages/quiz.py` — generation form and state management.
2. Render the question list using `st.radio` per question after generation.
3. Implement the Submit flow: evaluate → inline feedback → summary banner → DB save.
4. Guard against submitting without answering all questions (show a warning).
5. Add a "New Quiz" button to clear `st.session_state.current_quiz` and restart.

**Relevant Context**
- Streamlit re-runs the script on every interaction; use session state carefully to
  distinguish "quiz generated", "quiz submitted", and "feedback shown" phases.
- The `evaluate_quiz` function from `quiz_engine.py` is the single source of truth for
  scoring.

**Status:** `[x] done`
**Test result:** `_test_quiz.py` — 26 passed, 0 failed, 0 skipped, exit code 0.
**Files:** `learnmate_ai/pages/quiz.py`, `_test_quiz.py`

---

### Sub-Task 8 — Study Planner Page

**Intent**
Show students which topics they are struggling with and present an AI-generated (or
rule-based in demo mode) study plan.

**Expected Outcomes**
- `pages/planner.py` calls `database.get_topic_accuracy_summary` for the current student.
- Displays a table of topics with colour-coded accuracy (red < 60%, amber 60–79%,
  green ≥ 80%).
- Calls `study_planner.build_study_plan` and renders the narrative plan.
- If no quiz history exists, shows an encouraging prompt to take some quizzes first.
- Provides a "Refresh Plan" button to regenerate.

**Todo List**
1. Write `pages/planner.py` — load summary, render accuracy table.
2. Colour-code rows using Pandas Styler.
3. Call `build_study_plan` and render the result in a markdown block.
4. Handle the empty-history edge case.
5. Add demo mode badge if applicable.

**Relevant Context**
- The 60% threshold used by `detect_weak_topics` should be displayed to the student
  as an explanation ("topics below 60% accuracy are flagged for revision").

**Status:** `[x] done`
**Test result:** `_test_study_planner.py` — 24 passed, 0 failed, 0 skipped, exit code 0.
**Files:** `learnmate_ai/pages/study_planner.py`, `_test_study_planner.py`

---

### Sub-Task 9 — Progress Dashboard Page

**Intent**
Give students a visual overview of their learning history: quiz attempts over time, average
accuracy per subject, and a weak-topic summary.

**Expected Outcomes**
- `pages/dashboard.py` renders three sections:
  1. **Summary Cards** — total quizzes taken, overall average accuracy, number of weak
     topics.
  2. **Accuracy Over Time** — Plotly line chart of `accuracy` per `attempted_at`.
  3. **Subject Performance** — Plotly bar chart of average accuracy per subject.
- All charts use Plotly via `st.plotly_chart`.
- If no history, shows an empty-state message.

**Todo List**
1. Write `pages/dashboard.py` — load attempts DataFrame.
2. Compute summary card metrics with Pandas.
3. Build and render the line chart.
4. Build and render the bar chart.
5. Handle empty-state.

**Relevant Context**
- `database.get_attempts_by_student` returns the raw attempts DataFrame needed for
  all three sections.
- `database.get_topic_accuracy_summary` provides the subject-level roll-up for the
  bar chart.

**Status:** `[-] in progress`

---

### Sub-Task 10 — App Entry Point & Navigation

**Intent**
Wire all pages together in `app.py` with a sidebar navigator, global session-state guards,
and the demo-mode status indicator.

**Expected Outcomes**
- `app.py` configures the Streamlit page (title, icon, wide layout).
- Sidebar shows: app logo/title, SDG 4 tagline, navigation links, current student name
  if logged in, demo mode indicator if applicable.
- Pages: Profile, AI Tutor, Quiz, Study Planner, Dashboard.
- Any page other than Profile redirects to Profile with a message if no `student_id`
  in session state.
- `database.init_db()` is called once at startup.

**Todo List**
1. Write `app.py` — page config, sidebar, navigation using `st.sidebar.radio` or
   `st.Page` / `st.navigation` (Streamlit ≥ 1.36).
2. Import and call `init_db()` at the top.
3. Add the session-state guard and redirect logic.
4. Add demo mode banner in the sidebar.
5. Route to the selected page module.

**Relevant Context**
- Because Streamlit's multi-page `pages/` directory auto-discovers pages, and we want
  manual control of ordering and guards, use the programmatic `st.navigation` API
  (Streamlit ≥ 1.36) or a manual `if/elif` dispatch inside a single `app.py`.
- The `pages/` modules should not call `st.set_page_config` themselves.

**Status:** `[x] done`

---

## Implementation Order

```
Sub-Task 1  →  Sub-Task 2  →  Sub-Task 3  →  Sub-Task 4
                                                    ↓
Sub-Task 10 ←  Sub-Task 9 ←  Sub-Task 8 ←  Sub-Task 5
                                    ↑
                              Sub-Task 6
                              Sub-Task 7
```

1. Scaffold (1) — stable base for everything.
2. Database (2) — needed by all pages.
3. LLM Adapter + Seed Data (3) — needed by Tutor, Quiz, Planner.
4. Business Logic (4) — needed by Quiz and Planner pages.
5. Pages 5–9 — can be built in any order once 1–4 are done.
6. App Entry Point (10) — last, wires everything together.

---

## Testing Strategy

No dedicated test framework is required for the initial version. Validation is done by:

| Layer | Approach |
|---|---|
| `quiz_engine.py` | Manual test script (`python -m learnmate_ai.quiz_engine`) that runs `evaluate_quiz` with known inputs and prints pass/fail. |
| `database.py` | Call each helper against a temporary in-memory SQLite DB (`:memory:`) in a scratch script. |
| `llm_adapter.py` | Run with `is_demo_mode=True` to verify seed-data path; run with a real key to verify the live path parses correctly. |
| Full app | Manual walkthrough of the happy path: create profile → tutor explanation → take quiz → view dashboard → view planner. |

Formal pytest suite is explicitly out of scope for the initial version.

---

## Environment Variables Reference

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `LLM_API_KEY` | No | — | Activates live AI mode; absent = demo mode |
| `LLM_PROVIDER` | No | `openai` | Informational label |
| `LLM_BASE_URL` | No | `https://api.openai.com/v1` | Override for Groq, Together AI, etc. |
| `LLM_MODEL` | No | `gpt-4o-mini` | Model name passed to the API |
