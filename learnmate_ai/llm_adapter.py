"""
llm_adapter.py — Provider-agnostic LLM client with demo-mode fallback.

Public interface
----------------
    is_demo_mode() -> bool
    explain_topic(subject, topic, level) -> str
    generate_quiz(subject, topic, level, difficulty, n) -> list[dict]
    generate_study_plan(weak_topics, level) -> str

When config.settings.is_demo_mode is True every function returns deterministic,
clearly labelled sample content drawn from demo_questions.json or inline text.
When an API key is present the openai SDK is used (lazy import) to call any
OpenAI-compatible provider; errors are re-raised as LLMError.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from learnmate_ai import config

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Raised when the live LLM call fails for any reason."""


# ---------------------------------------------------------------------------
# Demo-data cache (loaded once, reused)
# ---------------------------------------------------------------------------

_demo_questions: list[dict] | None = None


def _load_demo_questions() -> list[dict]:
    global _demo_questions
    if _demo_questions is None:
        data_path = Path(__file__).parent / "data" / "demo_questions.json"
        with data_path.open(encoding="utf-8") as fh:
            _demo_questions = json.load(fh)
    return _demo_questions


# ---------------------------------------------------------------------------
# Convenience re-export
# ---------------------------------------------------------------------------


def is_demo_mode() -> bool:
    """Return True when no LLM API key is configured."""
    return config.settings.is_demo_mode


# ---------------------------------------------------------------------------
# Demo-mode sample explanations
# ---------------------------------------------------------------------------

_DEMO_EXPLANATIONS: dict[str, dict[str, str]] = {
    "mathematics": {
        "algebra": """\
## Algebra

Algebra is the branch of mathematics that uses letters (variables) to represent unknown
numbers, allowing us to write general rules and solve equations.

**Key idea:** A variable like *x* is just a placeholder for a number we want to find.

**Example 1 — Solving a simple equation**
> Solve **2x + 3 = 7**
> 1. Subtract 3 from both sides: 2x = 4
> 2. Divide both sides by 2: **x = 2**

**Example 2 — Expanding brackets**
> Expand **3(x + 4)**
> Multiply 3 by each term inside: **3x + 12**

**Tips for practice:**
- Always perform the same operation on both sides of the equals sign.
- Check your answer by substituting it back into the original equation.
""",
        "geometry": """\
## Geometry

Geometry is the study of shapes, sizes, and the properties of space.

**Key concepts:**
- **Angles**: An acute angle is less than 90°; a right angle is exactly 90°; an obtuse
  angle is between 90° and 180°.
- **Triangles**: The angles of any triangle always sum to **180°**.
- **Pythagorean Theorem** (right-angled triangles): **a² + b² = c²** where *c* is the
  hypotenuse.

**Example 1 — Area of a triangle**
> Base = 8 cm, Height = 5 cm
> Area = ½ × 8 × 5 = **20 cm²**

**Example 2 — Pythagorean theorem**
> Legs: 3 cm and 4 cm → c² = 9 + 16 = 25 → **c = 5 cm**
""",
        "statistics": """\
## Statistics

Statistics is about collecting, summarising, and interpreting data.

**Key measures:**
- **Mean** — sum of all values ÷ number of values (sensitive to outliers).
- **Median** — the middle value when data is sorted.
- **Mode** — the value that appears most often.
- **Standard deviation** — measures how spread out values are around the mean.

**Example 1 — Finding the mean**
> Data: 4, 7, 7, 10, 12 → Mean = (4+7+7+10+12)/5 = **8**

**Example 2 — Interpreting spread**
> A small standard deviation means data points cluster tightly around the mean;
> a large one means they are widely spread.
""",
        "calculus": """\
## Calculus

Calculus studies change (differentiation) and accumulation (integration).

**Differentiation** finds the rate of change (slope) of a function.
- Rule: the derivative of **xⁿ** is **n·xⁿ⁻¹**

**Integration** finds the area under a curve — the reverse of differentiation.
- Rule: ∫xⁿ dx = **xⁿ⁺¹/(n+1) + C**

**Example 1 — Differentiation**
> f(x) = x³ → f′(x) = **3x²**

**Example 2 — Integration**
> ∫2x dx = x² + C
""",
    },
    "science": {
        "photosynthesis": """\
## Photosynthesis

Photosynthesis is the process by which green plants convert sunlight into food.

**Equation:**
> 6CO₂ + 6H₂O + light energy → **C₆H₁₂O₆ (glucose) + 6O₂**

Plants absorb **carbon dioxide** through their leaves, **water** through their roots, and
use energy from **sunlight** captured by chlorophyll in the chloroplasts.

**Example 1 — Why leaves are green**
> Chlorophyll absorbs red and blue light but reflects green light — that is why we see
> leaves as green.

**Example 2 — Limiting factors**
> On a cloudy day less light is available, so the rate of photosynthesis decreases even
> if CO₂ and water are plentiful.
""",
        "biology": """\
## Biology

Biology is the scientific study of living organisms and life processes.

**Key areas:**
- **Cell biology**: the cell is the basic unit of life; cells contain a nucleus (control
  centre), mitochondria (energy), and ribosomes (protein synthesis).
- **Genetics**: DNA carries hereditary information; genes are sections of DNA that code
  for proteins.
- **Ecology**: the study of how organisms interact with each other and their environment.

**Example 1 — Cell respiration**
> Glucose + Oxygen → Carbon Dioxide + Water + Energy (ATP)

**Example 2 — Inheritance**
> If a trait is dominant (e.g. brown eyes), one copy of the allele is enough to express it.
""",
        "physics": """\
## Physics

Physics explains how the universe works through matter, energy, and their interactions.

**Newton's Laws of Motion (simplified):**
1. An object stays still or keeps moving at constant speed unless acted on by a force.
2. Force = mass × acceleration (F = ma).
3. For every action there is an equal and opposite reaction.

**Example 1 — Calculating force**
> A 5 kg object accelerates at 3 m/s². F = 5 × 3 = **15 N**

**Example 2 — Speed vs velocity**
> Speed is a scalar (magnitude only); velocity is a vector (magnitude + direction).
""",
        "chemistry": """\
## Chemistry

Chemistry studies the composition, structure, and transformation of matter.

**Atoms and molecules:**
- Atoms are the smallest units of an element.
- Molecules are two or more atoms bonded together (e.g. H₂O = 2 hydrogen + 1 oxygen).

**Acids and bases:**
- pH scale runs 0–14; below 7 = acid, 7 = neutral, above 7 = base/alkali.

**Example 1 — Balancing an equation**
> H₂ + O₂ → H₂O becomes **2H₂ + O₂ → 2H₂O** (balanced).

**Example 2 — Neutralisation**
> Acid + Base → Salt + Water (e.g. HCl + NaOH → NaCl + H₂O).
""",
    },
    "history": {
        "world war ii": """\
## World War II

World War II (1939–1945) was the deadliest conflict in human history, involving most of
the world's nations.

**Key dates:**
- **1 Sept 1939** — Germany invades Poland; UK and France declare war.
- **7 Dec 1941** — Japan attacks Pearl Harbor; USA enters the war.
- **6 June 1944 (D-Day)** — Allied forces land in Normandy, France.
- **8 May 1945 (VE Day)** — Germany surrenders.
- **15 Aug 1945 (VJ Day)** — Japan surrenders after atomic bombs on Hiroshima and Nagasaki.

**Significance:**
- Led to the creation of the United Nations (1945) to promote peace.
- Began the Cold War between the USA and USSR.
- Resulted in the Nuremberg Trials and recognition of war crimes against humanity.
""",
        "ancient civilizations": """\
## Ancient Civilizations

Ancient civilizations laid the foundations for modern society through advances in writing,
law, agriculture, and governance.

**Key civilizations:**
- **Mesopotamia** (modern Iraq) — one of the first civilizations; invented writing
  (cuneiform) and early law codes (Code of Hammurabi).
- **Ancient Egypt** — built the pyramids; developed hieroglyphics; ruled by pharaohs.
- **Ancient Greece** — birthplace of democracy, philosophy, and the Olympic Games.
- **Roman Empire** — spread law, roads, and the Latin language across Europe and beyond.

**Example 1 — Egyptian pyramids**
> The Great Pyramid of Giza was built around 2560 BCE for Pharaoh Khufu and required an
> estimated 20,000 workers over 20 years.

**Example 2 — Greek democracy**
> In Athens (5th century BCE), free male citizens could vote in the assembly — an early
> model for modern democratic systems.
""",
        "modern history": """\
## Modern History

Modern history (roughly 1500 CE to the present) covers the rise of nation-states,
revolutions, industrialisation, and two World Wars.

**Key events:**
- **1789** — French Revolution; end of absolute monarchy in France.
- **1914–1918** — World War I; reshaped Europe; led to the Treaty of Versailles (1919).
- **1939–1945** — World War II (see dedicated topic).
- **1947–1991** — Cold War between the USA and USSR.
- **1989** — Fall of the Berlin Wall; end of the Cold War.

**Example 1 — Industrial Revolution**
> Beginning in Britain in the late 1700s, the Industrial Revolution transformed manual
> labour into machine-based manufacturing, fuelling urbanisation and global trade.

**Example 2 — Cold War impact**
> The Space Race (1957–1969) was driven by Cold War competition; the USA landed on the
> Moon in 1969 partly as a demonstration of technological superiority over the USSR.
""",
    },
    "english": {
        "grammar": """\
## Grammar

Grammar is the set of rules that governs how words combine to form sentences.

**Parts of speech:**
- **Noun** — a person, place, or thing (e.g. *dog*, *London*).
- **Verb** — an action or state (e.g. *run*, *is*).
- **Adjective** — describes a noun (e.g. *fast*, *blue*).
- **Adverb** — modifies a verb, adjective, or other adverb (e.g. *quickly*, *very*).
- **Pronoun** — replaces a noun (e.g. *he*, *they*, *it*).

**Example 1 — Sentence breakdown**
> *"The quick brown fox jumps over the lazy dog."*
> - "quick" and "brown" = adjectives; "fox" = noun; "jumps" = verb; "lazy" = adjective;
>   "dog" = noun.

**Example 2 — Subject–verb agreement**
> Incorrect: *She don't know.*  Correct: *She **doesn't** know.*
> The verb must agree with its subject in person and number.
""",
        "vocabulary": """\
## Vocabulary

A strong vocabulary helps you understand and express ideas precisely.

**Strategies to build vocabulary:**
1. **Context clues** — guess an unknown word's meaning from surrounding text.
2. **Root words** — knowing roots, prefixes, and suffixes unlocks many words
   (e.g. *bene-* = good: *benevolent*, *benefit*, *benefactor*).
3. **Synonyms & antonyms** — learn words alongside their opposites.
4. **Regular reading** — varied reading material exposes you to new words in context.

**Example 1 — Using context**
> *"The politician gave an eloquent speech, her words flowing smoothly and persuasively."*
> → *eloquent* means fluent and persuasive.

**Example 2 — Root analysis**
> *ephemeral*: Greek *ephemeros* (lasting only a day) → means lasting a very short time.
""",
        "literature": """\
## Literature

Literature is written work valued for its artistic quality and the ideas it explores.

**Key literary devices:**
- **Simile** — comparison using "like" or "as" (e.g. *brave as a lion*).
- **Metaphor** — direct comparison without "like" or "as" (e.g. *life is a journey*).
- **Personification** — giving human traits to non-human things (e.g. *the wind whispered*).
- **Hyperbole** — deliberate exaggeration (e.g. *I've told you a million times*).

**Example 1 — Shakespeare's Romeo and Juliet**
> "But soft! What light through yonder window breaks? It is the east, and Juliet is the sun."
> Romeo uses **metaphor** to compare Juliet to the sun.

**Example 2 — Narrative perspective**
> First-person narration ("I saw…") creates intimacy; third-person omniscient narration
> ("She thought…") gives the author freedom to reveal multiple characters' inner thoughts.
""",
    },
    "computer science": {
        "algorithms": """\
## Algorithms

An algorithm is a step-by-step procedure for solving a problem or accomplishing a task.

**Characteristics of a good algorithm:**
- **Correctness** — produces the right output for every valid input.
- **Efficiency** — uses time and memory economically (measured with Big-O notation).
- **Clarity** — steps are unambiguous and can be followed by anyone (or any machine).

**Example 1 — Bubble Sort**
> Repeatedly compare adjacent elements and swap them if out of order.
> After each full pass the largest unsorted element "bubbles" to its correct position.
> Time complexity: O(n²) worst case.

**Example 2 — Binary Search**
> To find a value in a **sorted** list:
> 1. Look at the middle element.
> 2. If it matches, done. If the target is smaller, search the left half; otherwise the right.
> 3. Repeat until found or the list is empty.
> Time complexity: O(log n) — much faster than checking every element.
""",
        "data structures": """\
## Data Structures

A data structure organises data in memory so it can be used efficiently.

**Common structures:**
- **Array** — fixed-size ordered collection; O(1) access by index.
- **Linked list** — nodes connected by pointers; efficient insertion/deletion, slow search.
- **Stack** — Last-In-First-Out (LIFO); used for undo operations, call stacks.
- **Queue** — First-In-First-Out (FIFO); used for task scheduling, print queues.
- **Tree** — hierarchical structure; binary search trees enable O(log n) search.
- **Hash table** — key-value pairs with O(1) average lookup.

**Example 1 — Stack usage**
> Your browser's "Back" button uses a stack: each page visited is pushed on; pressing
> Back pops the most recent page off.

**Example 2 — Choosing a structure**
> Need fast lookup by key? Use a **hash table**. Need sorted data with fast search?
> Use a **binary search tree**.
""",
        "programming": """\
## Programming

Programming is the process of writing instructions (code) that a computer can execute.

**Core concepts:**
- **Variables** — named storage for values (e.g. `x = 5`).
- **Control flow** — `if/else` for decisions; `for`/`while` for loops.
- **Functions** — reusable blocks of code that take inputs and return outputs.
- **Data types** — integers, floats, strings, lists, booleans, etc.

**Example 1 — Python function**
```python
def greet(name):
    return f"Hello, {name}!"

print(greet("Alice"))  # Hello, Alice!
```

**Example 2 — Loop**
```python
for i in range(1, 6):
    print(i)   # prints 1, 2, 3, 4, 5
```
""",
        "networking": """\
## Networking

Computer networking connects devices so they can share data and resources.

**Key concepts:**
- **IP address** — a unique numerical label for every device on a network.
- **TCP/IP** — the foundational protocol suite of the Internet; TCP ensures reliable
  delivery, IP handles routing.
- **OSI model** — 7 layers (Physical → Data Link → Network → Transport → Session →
  Presentation → Application) each with a defined role.
- **DNS** — translates human-readable domain names (e.g. `example.com`) into IP addresses.

**Example 1 — Client–server model**
> When you visit a website, your browser (client) sends an HTTP request to a web server,
> which responds with the HTML page.

**Example 2 — Ports**
> HTTP uses port 80, HTTPS uses port 443, SMTP (email) uses port 25. Ports let a single
> device run many services simultaneously.
""",
    },
}

# Valid answer letters and expected option prefixes
_VALID_ANSWERS = {"A", "B", "C", "D"}
_OPTION_PREFIXES = ("A. ", "B. ", "C. ", "D. ")


# ---------------------------------------------------------------------------
# Live-mode helpers
# ---------------------------------------------------------------------------


def _get_openai_client():  # type: ignore[return]
    """Lazily import and instantiate the openai client."""
    try:
        import openai  # noqa: PLC0415
    except ImportError as exc:
        raise LLMError(
            "The 'openai' package is not installed. Run: pip install openai"
        ) from exc
    return openai.OpenAI(
        api_key=config.settings.llm_api_key,
        base_url=config.settings.llm_base_url,
    )


def _call_llm(prompt: str) -> str:
    """Send a single user-turn prompt and return the response text.

    Both client creation and the API call sit inside the try block so any
    failure (import error, auth error, network error) is consistently wrapped
    as LLMError.
    """
    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=config.settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content or ""
    except LLMError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise LLMError(str(exc)) from exc


def _strip_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        end = -1 if lines[-1].strip() == "```" else len(lines)
        stripped = "\n".join(lines[1:end])
    return stripped


def _validate_mcq_list(data: object, n: int) -> list[dict]:
    """Validate that *data* is a list of exactly *n* well-formed MCQ dicts.

    Raises ValueError with a descriptive message on any violation.
    """
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array, got {type(data).__name__}")
    if len(data) != n:
        raise ValueError(f"Expected {n} questions, got {len(data)}")
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Question {idx + 1} is not an object")
        missing = {"question", "options", "answer"} - item.keys()
        if missing:
            raise ValueError(f"Question {idx + 1} missing keys: {missing}")
        extra = set(item.keys()) - {"question", "options", "answer"}
        if extra:
            raise ValueError(f"Question {idx + 1} has unexpected keys: {extra}")
        if not isinstance(item["question"], str) or not item["question"].strip():
            raise ValueError(f"Question {idx + 1}: 'question' must be a non-empty string")
        opts = item["options"]
        if not isinstance(opts, list) or len(opts) != 4:
            raise ValueError(f"Question {idx + 1}: 'options' must be a list of 4 strings")
        for prefix, opt in zip(_OPTION_PREFIXES, opts):
            if not isinstance(opt, str) or not opt.startswith(prefix):
                raise ValueError(
                    f"Question {idx + 1}: option '{opt}' must start with '{prefix}'"
                )
        # Type check before membership test (guards against non-string answers)
        if not isinstance(item["answer"], str) or item["answer"] not in _VALID_ANSWERS:
            raise ValueError(
                f"Question {idx + 1}: 'answer' must be one of A/B/C/D, "
                f"got {item['answer']!r}"
            )
    return data  # type: ignore[return-value]


def _quiz_prompt(subject: str, topic: str, level: str, difficulty: str, n: int) -> str:
    return (
        f"Generate exactly {n} multiple-choice questions about '{topic}' in '{subject}' "
        f"at {difficulty} difficulty for a {level} student. "
        "Reply with ONLY a JSON array — no explanation, no markdown fences. "
        "Each element must have exactly these keys: "
        '"question" (non-empty string), '
        '"options" (array of exactly 4 strings each formatted as '
        '"A. ...", "B. ...", "C. ...", "D. ..."), '
        '"answer" (single uppercase letter A, B, C, or D).'
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def explain_topic(subject: str, topic: str, level: str) -> str:
    """Return a plain-language explanation of *topic* within *subject* for
    a student at *level* (Beginner / Intermediate / Advanced)."""
    if is_demo_mode():
        return _demo_explain_topic(subject, topic, level)

    prompt = (
        f"You are an expert tutor. Explain the topic '{topic}' within the subject "
        f"'{subject}' to a {level} student. "
        "Provide a clear explanation with 2 concrete examples. "
        "Reply using plain markdown (headings, bullet points, code blocks where helpful). "
        "Do not wrap your answer in JSON."
    )
    return _call_llm(prompt)


def generate_quiz(
    subject: str,
    topic: str,
    level: str,
    difficulty: str,
    n: int,
) -> list[dict]:
    """Return a list of *n* MCQ dicts with keys: question, options, answer.

    *options* is a list of 4 strings like ["A. ...", "B. ...", "C. ...", "D. ..."].
    *answer* is a single letter A/B/C/D.
    """
    if is_demo_mode():
        return _demo_generate_quiz(subject, difficulty, n)

    prompt = _quiz_prompt(subject, topic, level, difficulty, n)
    raw = _call_llm(prompt)

    # Attempt 1
    try:
        parsed = json.loads(_strip_fences(raw))
        return _validate_mcq_list(parsed, n)
    except (json.JSONDecodeError, ValueError):
        pass  # fall through to retry

    # Attempt 2 — stricter prompt
    strict_prompt = (
        "Reply with ONLY a JSON array, no explanation, no markdown fences. "
        + _quiz_prompt(subject, topic, level, difficulty, n)
    )
    raw2 = _call_llm(strict_prompt)
    try:
        parsed2 = json.loads(_strip_fences(raw2))
        return _validate_mcq_list(parsed2, n)
    except json.JSONDecodeError as exc:
        raise LLMError(
            f"LLM returned invalid JSON after two attempts: {exc}"
        ) from exc
    except ValueError as exc:
        raise LLMError(
            f"LLM response failed validation after two attempts: {exc}"
        ) from exc


def generate_study_plan(weak_topics: list[dict], level: str) -> str:
    """Return a structured weekly study plan as a markdown string.

    *weak_topics* is a list of dicts with keys 'subject' and 'topic'.
    """
    if is_demo_mode():
        return _demo_generate_study_plan(weak_topics, level)

    topics_text = "\n".join(
        f"- {item['subject']}: {item['topic']}" for item in weak_topics
    )
    prompt = (
        f"You are a personalised study coach. A {level} student needs to improve on "
        "the following topics:\n"
        f"{topics_text}\n\n"
        "Create a structured weekly study plan in markdown. "
        "Include: a short introduction, day-by-day schedule spread across 5–7 days, "
        "specific activities or exercises for each topic, and motivational tips. "
        "Use bullet points and headings."
    )
    return _call_llm(prompt)


# ---------------------------------------------------------------------------
# Demo-mode implementations
# ---------------------------------------------------------------------------


def _demo_explain_topic(subject: str, topic: str, _level: str) -> str:
    subject_key = subject.strip().lower()
    topic_key = topic.strip().lower()

    subject_dict = _DEMO_EXPLANATIONS.get(subject_key, {})
    explanation = subject_dict.get(topic_key)

    # Partial match across all subjects when exact subject/topic not found
    if explanation is None:
        for _subj_dict in _DEMO_EXPLANATIONS.values():
            for stored_topic, stored_text in _subj_dict.items():
                if topic_key in stored_topic or stored_topic in topic_key:
                    explanation = stored_text
                    break
            if explanation is not None:
                break

    if explanation is not None:
        header = (
            "> **📚 Demo Mode — Sample Content**\n"
            "> This is pre-written sample content, not AI-generated. "
            "Configure an LLM API key in `.env` for real AI explanations.\n\n"
        )
        return header + explanation

    # Generic fallback for completely unknown topics
    return (
        "> **📚 Demo Mode — Generic Sample**\n"
        "> No bundled explanation exists for this specific topic. "
        "The content below is a general learning framework, not AI-generated "
        f"and not specific to *{topic}*. "
        "Configure an LLM API key in `.env` for a real AI-generated explanation.\n\n"
        f"## {subject}: {topic}\n\n"
        f"Welcome! You are about to explore **{topic}** in the subject of **{subject}**.\n\n"
        "Even without a specific guide, you can make great progress by following this "
        "general learning framework:\n\n"
        "### 🔍 Step 1 — Define It\n"
        f"Start by writing a one-sentence definition of *{topic}* in your own words. "
        "Look it up in a textbook, Wikipedia, or a trusted website. "
        "Understanding the definition precisely is the foundation of everything else.\n\n"
        "### 🧩 Step 2 — Break It Into Parts\n"
        f"Most topics in *{subject}* have several sub-concepts. "
        f"List the 3–5 key ideas or components that make up *{topic}*. "
        "Tackle each one separately before combining them.\n\n"
        "### 💡 Step 3 — Find Real-World Examples\n"
        "Look for 2–3 concrete examples of your topic in everyday life, history, or "
        "current technology. Connecting abstract ideas to real situations dramatically "
        "improves understanding and recall.\n\n"
        "### ✏️ Step 4 — Practice\n"
        "Retrieve the quiz in this app to test your knowledge. "
        "Attempt practice problems or past-paper questions. "
        "Each mistake is a learning opportunity — review the correct answer and "
        "understand *why* it is correct.\n\n"
        "### 📅 Step 5 — Review & Spaced Repetition\n"
        "Revisit this topic tomorrow, then again in three days, then a week later. "
        "Spaced repetition is the most effective technique for long-term retention.\n\n"
        "*Keep going — consistent effort always pays off! 🎯*"
    )


def _demo_generate_quiz(subject: str, difficulty: str, n: int) -> list[dict]:
    questions = _load_demo_questions()
    subject_lower = subject.strip().lower()
    difficulty_lower = difficulty.strip().lower()

    # Filter by subject (case-insensitive) and difficulty
    pool: list[dict] = [
        q for q in questions
        if q["subject"].lower() == subject_lower
        and q["difficulty"].lower() == difficulty_lower
    ]

    # If no match for subject, fall back to any subject at that difficulty
    if not pool:
        pool = [
            q for q in questions
            if q["difficulty"].lower() == difficulty_lower
        ]

    # Last resort: return from entire dataset
    if not pool:
        pool = list(questions)

    sample = random.sample(pool, min(n, len(pool)))

    # Return only the keys the quiz engine expects
    return [
        {
            "question": q["question"],
            "options": q["options"],
            "answer": q["answer"],
        }
        for q in sample
    ]


def _demo_generate_study_plan(weak_topics: list[dict], level: str) -> str:
    if not weak_topics:
        return (
            "> **📚 Demo Mode — Sample Study Plan**\n"
            "> This is a rule-based study plan, not AI-generated.\n\n"
            "## 🎉 Great job!\n\n"
            "No weak topics were detected based on your quiz history. "
            "Keep practising to maintain your performance!"
        )

    # Group by subject
    by_subject: dict[str, list[str]] = {}
    for item in weak_topics:
        subj = item.get("subject", "General")
        topic = item.get("topic", "Unknown")
        by_subject.setdefault(subj, []).append(topic)

    subjects = list(by_subject.keys())
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    lines: list[str] = [
        "> **📚 Demo Mode — Sample Study Plan**",
        "> This is a rule-based study plan generated from your quiz results, not AI-generated. "
        "Configure an LLM API key for a personalised AI study schedule.",
        "",
        f"# 📅 Your Personalised Study Plan ({level} Level)",
        "",
        "Based on your recent quiz performance, the following topics need extra attention:",
        "",
    ]

    for subj, topics in by_subject.items():
        lines.append(f"- **{subj}**: {', '.join(topics)}")
    lines.append("")

    lines += [
        "---",
        "",
        "## 🗓️ Suggested Weekly Schedule",
        "",
    ]

    for i, day in enumerate(days):
        subj = subjects[i % len(subjects)]
        topics_for_day = by_subject[subj]
        topic_str = " & ".join(topics_for_day[:2])
        lines.append(f"### {day} — {subj}")
        lines.append(f"- **Focus:** {topic_str}")
        lines.append("- **Activities:**")
        lines.append("  - Re-read your notes or a relevant textbook section (20 min)")
        lines.append("  - Work through 5–10 practice questions (25 min)")
        lines.append("  - Write a one-paragraph summary in your own words (10 min)")
        lines.append("")

    lines += [
        "---",
        "",
        "## 💡 Study Tips",
        "",
        "- **Little and often**: 30–45 minute focused sessions beat marathon cramming.",
        "- **Active recall**: test yourself rather than just re-reading notes.",
        "- **Spaced repetition**: revisit each topic after 1 day, 3 days, then 1 week.",
        "- **Take breaks**: a 5-minute break every 25 minutes (Pomodoro technique) keeps "
        "your mind fresh.",
        "- **Use the Quiz tab**: retake quizzes on weak topics to track improvement.",
        "",
        "*You've got this! Consistent effort every day leads to great results. 🎯*",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Scheduled plan — day-by-day schedule from user-supplied inputs
# ---------------------------------------------------------------------------


def generate_scheduled_plan(
    subjects: list[str],
    topics: list[str],
    hours_per_day: float,
    target_date: str,
    weak_topics: list[dict],
    level: str,
) -> str:
    """Return a day-by-day study schedule as a markdown string.

    Parameters
    ----------
    subjects:
        List of subjects the student wants to cover.
    topics:
        List of specific topics within those subjects.
    hours_per_day:
        Available study hours per day (e.g. 1.5).
    target_date:
        Target exam / completion date as a string (e.g. "2024-12-15").
    weak_topics:
        List of dicts with 'subject' and 'topic' keys — from quiz history.
        May be empty if no quiz history exists.
    level:
        Student's learning level (Beginner / Intermediate / Advanced).

    Returns
    -------
    Markdown-formatted day-by-day schedule.
    """
    if is_demo_mode():
        return _demo_generate_scheduled_plan(
            subjects, topics, hours_per_day, target_date, weak_topics, level
        )

    weak_lines = (
        "\n".join(f"  - {w['subject']}: {w['topic']}" for w in weak_topics)
        if weak_topics
        else "  (none — generate a balanced plan)"
    )
    topic_lines = "\n".join(
        f"  - {s}: {t}" for s, t in zip(subjects, topics)
    ) if topics else "  (use weak topics above as the focus)"

    prompt = (
        f"You are a personalised study coach for a {level} student.\n\n"
        f"The student wants to study the following subjects and topics:\n{topic_lines}\n\n"
        f"They have identified these weak areas from their quiz history (prioritise these):\n"
        f"{weak_lines}\n\n"
        f"Available study time: {hours_per_day} hour(s) per day.\n"
        f"Target completion / exam date: {target_date}.\n\n"
        "Create a detailed, practical day-by-day study schedule in markdown. "
        "Include:\n"
        "1. A brief introduction summarising the plan.\n"
        "2. A day-by-day schedule from today to the target date (cap at 14 days if the "
        "date is far away, labelling remaining days as 'continued revision').\n"
        "3. For each day: the topic focus, suggested activities (reading, practice "
        "questions, flashcards, quiz), and estimated time per activity.\n"
        "4. Prioritise weak topics in the first half of the schedule.\n"
        "5. Include revision days and a final review day before the target date.\n"
        "6. End with 3 actionable study tips tailored to the student's level.\n"
        "Use markdown headings, bullet points, and bold text for clarity."
    )
    return _call_llm(prompt)


def _demo_generate_scheduled_plan(
    subjects: list[str],
    topics: list[str],
    hours_per_day: float,
    target_date: str,
    weak_topics: list[dict],
    level: str,
) -> str:
    """Rule-based day-by-day schedule for demo mode (no LLM)."""
    # Build the combined topic list: weak topics first, then user-supplied ones
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
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    lines: list[str] = [
        "> **📚 Demo Mode — Sample Scheduled Plan**",
        "> This is a rule-based schedule, not AI-generated. "
        "Set `LLM_API_KEY` in `.env` for a personalised AI schedule.",
        "",
        f"# 🗓️ Day-by-Day Study Schedule ({level} Level)",
        "",
        f"**Target date:** {target_date}  ",
        f"**Daily study time:** {hours_per_day} hour(s) ({mins} minutes)  ",
        "",
    ]

    if weak_topics:
        lines += [
            "## ⚠️ Priority Topics (from quiz history)",
            "",
        ]
        for w in weak_topics:
            pct = round(w.get("avg_accuracy", 0) * 100, 1)
            lines.append(f"- **{w['subject']} — {w['topic']}** (accuracy: {pct}%)")
        lines.append("")

    lines += [
        "---",
        "",
        "## 📅 Schedule",
        "",
    ]

    n = len(all_items)
    # Spread across up to 14 days; cycle through items if fewer items than days
    for day_idx in range(min(14, max(n + 1, 7))):
        item = all_items[day_idx % n]
        day_name = days_of_week[day_idx % 7]
        label = "⚠️ Weak topic" if item["priority"] == "high" else "📖 Topic"
        session_mins = max(20, mins // 3)
        lines += [
            f"### Day {day_idx + 1} ({day_name}) — {item['subject']}: {item['topic']}",
            "",
            f"*{label} — allocate {hours_per_day}h today*",
            "",
            f"- **Review** ({session_mins} min): Re-read notes / textbook section on "
            f"*{item['topic']}*.",
            f"- **Practice** ({session_mins} min): Work through 5–8 practice questions.",
            f"- **Self-test** ({session_mins} min): Take a LearnMate quiz on "
            f"*{item['topic']}* to check progress.",
            "",
        ]

    # Final revision day
    lines += [
        f"### Day {min(14, max(n + 1, 7)) + 1} (Final Revision — before {target_date})",
        "",
        "- Review all topics covered this week.",
        "- Re-take any quizzes where accuracy was below 80%.",
        "- Write a one-page summary of key concepts.",
        "",
        "---",
        "",
        "## 💡 Study Tips",
        "",
        f"- **{level} tip:** "
        + (
            "Focus on building solid foundations before moving on."
            if level == "Beginner"
            else "Connect new concepts to things you already know."
            if level == "Intermediate"
            else "Challenge yourself with harder practice problems."
        ),
        "- **Spaced repetition:** revisit each topic after 1 day, 3 days, then 1 week.",
        "- **Active recall:** close your notes and write down everything you remember "
        "before checking.",
        "",
        "*Consistent daily effort beats last-minute cramming every time. You've got this! 🎯*",
    ]

    return "\n".join(lines)
