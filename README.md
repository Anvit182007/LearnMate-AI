# LearnMate AI

> **UN SDG 4 — Quality Education** · Python · Streamlit · Pandas · Plotly · SQLite · LLM API

LearnMate AI is a personal study-coach web application that helps students learn faster and more
effectively.  Create a profile, ask the AI Tutor to explain any topic in plain language, take
adaptive multiple-choice quizzes, review a personalised study plan based on your weak areas, and
track your progress over time — all in a local, private app that runs entirely on your machine.

---

## Features

| Page | What it does |
|---|---|
| **Student Profile** | Save your name and learning level (Beginner / Intermediate / Advanced) |
| **AI Tutor** | Get clear explanations and worked examples on any subject/topic |
| **Quiz Generator** | Take AI-generated multiple-choice quizzes with instant inline feedback |
| **Quiz Results** | Review your most recent attempt: per-question breakdown and score |
| **Study Planner** | Receive a personalised study schedule derived from your weak topics |
| **Progress Dashboard** | Visualise accuracy trends, attempt history, and subject coverage with Plotly charts |

---

## Demo Mode

**No API key required to try the app.**  When `LLM_API_KEY` is left blank the app runs in
*Demo Mode*: quizzes are served from a bundled `data/demo_questions.json` seed file, tutor
explanations return static example text, and the study planner uses a rule-based schedule.  A
prominent "Demo Mode" badge is shown in the sidebar so it is always clear that generative AI is
not active.

---

## Setup

### 1 — Clone the repository

```bash
git clone <repo-url>
cd learnmate_ai
```

### 2 — Create and activate a virtual environment

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — Configure environment variables

```bash
cp .env.example .env
# Edit .env and add your LLM_API_KEY (or leave blank for demo mode)
```

See [`.env.example`](.env.example) for documentation of every variable.

### 5 — Run the app

```bash
streamlit run app.py
```

The app opens automatically at `http://localhost:8501`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_API_KEY` | *(empty)* | API key for your LLM provider.  Leave empty for demo mode. |
| `LLM_PROVIDER` | `openai` | Provider name (informational). |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint.  Override for Groq, Mistral, etc. |
| `LLM_MODEL` | `gpt-4o-mini` | Model identifier to request from the provider. |

---

## Project Structure

```
learnmate_ai/
├── app.py              # Streamlit entry point & sidebar navigation
├── config.py           # Environment variable loading (Settings dataclass)
├── database.py         # SQLite schema creation and CRUD helpers
├── llm_adapter.py      # Provider-agnostic LLM client + demo fallback
├── quiz_engine.py      # Scoring, accuracy calculation, weak-topic detection
├── study_planner.py    # Rule-based + LLM narrative study plan generation
├── pages/              # One file per Streamlit navigation page
│   ├── profile.py
│   ├── tutor.py
│   ├── quiz.py
│   ├── results.py
│   ├── planner.py
│   └── dashboard.py
├── data/
│   └── demo_questions.json
├── requirements.txt
├── .env.example
└── README.md
```

---

## License

MIT — see `LICENSE` for details.
