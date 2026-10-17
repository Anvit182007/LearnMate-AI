# LearnMate AI — Your Personal Study Coach

**UN SDG 4: Quality Education** | Python · Streamlit · Pandas · Plotly · SQLite · Groq API

LearnMate AI is an AI-powered study-coach application designed to help students learn more effectively through personalised explanations, interactive quizzes, customised study schedules, and progress tracking.

Students can create a profile, ask the AI Tutor to explain difficult topics, practise with AI-generated multiple-choice questions, identify weaker areas, and monitor their learning progress through an interactive dashboard.

## Key Features

| Feature | Description |
|---|---|
| **Student Profile** | Create and save a learner profile with name and learning level. |
| **AI Tutor** | Get topic explanations and learning support using an AI language model. |
| **Smart Quiz Generator** | Generate multiple-choice quizzes based on the selected subject, topic, difficulty, and question count. |
| **Quiz Results and Feedback** | Review submitted answers, scores, and question-level feedback. |
| **Personalised Study Planner** | Create a study schedule based on learning needs and areas requiring improvement. |
| **Progress Dashboard** | Explore quiz history, accuracy, and subject performance through interactive charts. |
| **Persistent Progress** | Store learner profiles and quiz results using an SQLite database. |

## Technology Stack

- **Programming language:** Python
- **Web application:** Streamlit
- **Data processing:** Pandas
- **Visualisation:** Plotly
- **Database:** SQLite
- **AI integration:** Groq API through an OpenAI-compatible client
- **Configuration:** Environment variables using `python-dotenv`

## Project Structure

```text
Project_IBM/
├── learnmate_ai/
│   ├── app.py
│   ├── config.py
│   ├── database.py
│   ├── llm_adapter.py
│   ├── quiz_engine.py
│   ├── study_planner.py
│   ├── pages/
│   │   ├── profile.py
│   │   ├── tutor.py
│   │   ├── quiz.py
│   │   ├── results.py
│   │   ├── planner.py
│   │   └── dashboard.py
│   ├── data/
│   ├── .env.example
│   ├── requirements.txt
├── _test_progress.py
├── README.md
├── _test_quiz.py
├── _test_study_planner.py
├── _test_study_planner_v2.py
├── _test_tutor.py
└── .gitignore
```

*Note: This structure represents the local project layout. Update it if the files in your GitHub repository differ.*

## Getting Started

### Prerequisites

- Python 3.10 or a compatible Python version supported by the project's dependencies
- pip
- A Groq API key for AI-powered features

### 1. Clone the repository

Replace the placeholder with your GitHub repository URL.

```bash
git clone <YOUR-GITHUB-REPOSITORY-URL>
cd Project_IBM
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

For macOS or Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r learnmate_ai/requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root using the example configuration:

```powershell
Copy-Item .\learnmate_ai\.env.example .\.env
```

Open `.env` and configure the variables required by your application:

```dotenv
LLM_API_KEY=your_groq_api_key
LLM_PROVIDER=groq
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=your_supported_model_id
```

Use a model ID supported by your Groq account and configured in the application. Keep your API key private. **Never commit `.env` or expose your API key on GitHub.**

### 5. Run the application

From the project root, execute:

```bash
python -m streamlit run learnmate_ai/app.py
```

Open the local URL displayed in the terminal, usually:

`http://localhost:8501`

## Environment Variables

| Variable | Purpose |
|---|---|
| `LLM_API_KEY` | API key used to authenticate with the language-model provider. |
| `LLM_PROVIDER` | Specifies the configured AI provider, such as Groq. |
| `LLM_BASE_URL` | Base URL for the OpenAI-compatible API endpoint. |
| `LLM_MODEL` | Model identifier used for AI requests. |

The exact defaults depend on the application's configuration. Refer to `learnmate_ai/config.py` and `learnmate_ai/.env.example` for the current settings.

## Testing

The project includes Python test scripts for checking core functionality, including quiz processing, study-planner logic, tutor behaviour, and progress tracking.

Run the relevant scripts from the project root, for example:

```bash
python _test_quiz.py
python _test_progress.py
python _test_study_planner.py
python _test_tutor.py
```

## Impact and Objective

LearnMate AI supports **UN Sustainable Development Goal 4: Quality Education** by making personalised learning support, practice assessments, study planning, and progress monitoring more accessible through a single application.

The project demonstrates how AI integration, data visualisation, and persistent storage can be combined to create a practical educational tool.

## Future Enhancements

- Deploy the application online for wider access.
- Add more learning resources and subject-specific question banks.
- Improve recommendations using additional learner performance data.
- Expand progress analytics and personalised learning insights.

## Project Links

- **GitHub Repository:** [Add your repository URL here]
- **Live Demo:** Add the deployed application URL here, once available.
- **Project Screenshots:** See the project's screenshot documentation.

---

**LearnMate AI — Learn smarter, plan better, and track your progress.**
