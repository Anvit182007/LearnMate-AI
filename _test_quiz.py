"""
_test_quiz.py — Automated checks for Sub-Task 7: pages/quiz.py

Checks
──────
Static / source
  1.  py_compile: quiz.py
  2.  py_compile: database.py
  3.  render() defined
  4.  _reset_quiz_callback() defined and wired as on_click
  5a. quiz_attempt_id referenced
  5b. quiz_responses_saved referenced
  6.  Slider constants: MIN=3, MAX=10, DEFAULT=5
  7.  DIFFICULTIES list present

Database layer (temp DB via mkstemp, trigger-based rollback proof)
  8.  Normal round-trip: save_quiz_attempt + save_question_responses
  9.  Trigger aborts 2nd insert mid-executemany → full rollback → 0 rows remain
 10.  Retry after failure: same attempt_id reused, 1 attempt, correct responses

AppTest UI
 11.  Profile guard: no profile → warning, no form
 12.  Demo mode badge (st.info) shown
 13.  Empty subject → error
 14.  Empty topic → error
 15.  Quiz generates → N radio widgets
 16.  New Quiz on_click clears answer keys and current_quiz
 17.  Shorter new quiz does not inherit answers from longer prior quiz
 18a. Unanswered first Submit → warning, quiz_submitted still False
 18b. Unanswered second Submit → quiz evaluated (quiz_submitted=True)
 19.  All-answered Submit → feedback phase
 20.  Feedback banner ("Quiz Complete") rendered
 21.  Question Feedback subheader rendered
 22.  Both DB functions called exactly once per submission
 23.  Duplicate-save prevention: reruns never call DB functions again
 24.  Response-save failure: attempt_id stored, responses_saved=False,
      no duplicate attempt on rerun
"""

from __future__ import annotations

import ast
import io
import os
import py_compile
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Force UTF-8 so box-drawing chars / emoji don't crash cp1252 consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

passed: list[str] = []
failed: list[str] = []
skipped: list[str] = []


def ok(label: str) -> None:
    passed.append(label)
    print(f"[OK]  {label}")


def fail(label: str, detail: str = "") -> None:
    failed.append(label)
    print(f"[FAIL] {label}" + (f": {detail}" if detail else ""))


def skip(label: str, reason: str = "") -> None:
    skipped.append(label)
    print(f"[SKIP] {label}" + (f": {reason}" if reason else ""))


QUIZ_PATH = "learnmate_ai/pages/quiz.py"
DB_PATH   = "learnmate_ai/database.py"

# ════════════════════════════════════════════════════════════════════════════ #
# 1–2. py_compile                                                              #
# ════════════════════════════════════════════════════════════════════════════ #
for num, path in [(1, QUIZ_PATH), (2, DB_PATH)]:
    try:
        py_compile.compile(path, doraise=True)
        ok(f"{num}. py_compile clean: {path}")
    except py_compile.PyCompileError as e:
        fail(f"{num}. py_compile: {path}", str(e))

# Load quiz source for static checks
try:
    with open(QUIZ_PATH, "r", encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    _src_ok = True
except Exception as e:
    fail("source-load", str(e))
    _src_ok = False

# ════════════════════════════════════════════════════════════════════════════ #
# 3–7. Static source checks                                                    #
# ════════════════════════════════════════════════════════════════════════════ #
if _src_ok:
    # 3. render() defined
    if any(isinstance(n, ast.FunctionDef) and n.name == "render" for n in ast.walk(tree)):
        ok("3. render() function defined")
    else:
        fail("3. render()", "not found")

    # 4. _reset_quiz_callback defined and wired as on_click
    if "_reset_quiz_callback" in src and "on_click=_reset_quiz_callback" in src:
        ok("4. _reset_quiz_callback() defined and wired as on_click")
    else:
        fail("4. _reset_quiz_callback()", "missing or not wired as on_click")

    # 5a/5b. Resilient persistence keys
    for sub, kw in [("5a", "quiz_attempt_id"), ("5b", "quiz_responses_saved")]:
        if kw in src:
            ok(f"{sub}. session-state key '{kw}' referenced")
        else:
            fail(f"{sub}. session-state key '{kw}'", "not found")

    # 6. Slider constants
    if "_MIN_Q = 3" in src and "_MAX_Q = 10" in src and "_DEFAULT_Q = 5" in src:
        ok("6. slider constants: MIN=3 MAX=10 DEFAULT=5")
    else:
        fail("6. slider constants", "Expected _MIN_Q=3, _MAX_Q=10, _DEFAULT_Q=5")

    # 7. DIFFICULTIES list
    if 'DIFFICULTIES' in src and '"easy"' in src and '"medium"' in src and '"hard"' in src:
        ok('7. DIFFICULTIES list present with easy/medium/hard')
    else:
        fail("7. DIFFICULTIES list", "Not found or missing members")
else:
    for tag in ["3", "4", "5a", "5b", "6", "7"]:
        skip(f"{tag}. static check", "source load failed")

# ════════════════════════════════════════════════════════════════════════════ #
# Database helpers (use mkstemp for safety)                                    #
# ════════════════════════════════════════════════════════════════════════════ #
try:
    import learnmate_ai.database as db_module
    _db_ok = True
except Exception as e:
    fail("db-import", str(e))
    _db_ok = False

_orig_db_path = db_module._DB_PATH if _db_ok else None


def _open_temp_db() -> tuple[Path, int]:
    """Create a temp DB file using mkstemp (safe on all platforms).

    Returns (path, student_id) with schema already initialised and a test
    student already inserted.
    """
    fd, tmp_str = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    tmp = Path(tmp_str)
    db_module._DB_PATH = tmp
    db_module.init_db()
    sid = db_module.upsert_student("TestStudent", "Beginner")
    return tmp, sid


def _close_temp_db(tmp: Path) -> None:
    db_module._DB_PATH = _orig_db_path
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass


# ════════════════════════════════════════════════════════════════════════════ #
# 8. Normal round-trip                                                         #
# ════════════════════════════════════════════════════════════════════════════ #
if _db_ok:
    tmp, sid = _open_temp_db()
    try:
        aid = db_module.save_quiz_attempt(sid, "Math", "Algebra", "easy", 2, 3, 0.67)
        responses = [
            {"question_text": "Q1?", "correct_answer": "A. 1",
             "student_answer": "A. 1", "is_correct": 1},
            {"question_text": "Q2?", "correct_answer": "B. 2",
             "student_answer": "",    "is_correct": 0},
        ]
        db_module.save_question_responses(aid, responses)
        df = db_module.get_responses_by_attempt(aid)
        assert len(df) == 2, f"Expected 2 responses, got {len(df)}"
        ok("8. DB round-trip: save_quiz_attempt + save_question_responses")
    except Exception as e:
        fail("8. DB round-trip", str(e))
    finally:
        _close_temp_db(tmp)
else:
    skip("8. DB round-trip", "database import failed")

# ════════════════════════════════════════════════════════════════════════════ #
# 9. Trigger forces mid-executemany abort → full rollback → 0 rows            #
# ════════════════════════════════════════════════════════════════════════════ #
if _db_ok:
    tmp, sid = _open_temp_db()
    try:
        aid = db_module.save_quiz_attempt(sid, "Math", "Algebra", "easy", 1, 3, 0.33)

        # Install a BEFORE INSERT trigger that aborts the 2nd row.
        # We count rows with a temp counter table to detect the 2nd insert.
        raw_conn = sqlite3.connect(str(tmp))
        raw_conn.execute("CREATE TABLE _counter (n INTEGER DEFAULT 0)")
        raw_conn.execute("INSERT INTO _counter VALUES (0)")
        raw_conn.execute("""
            CREATE TRIGGER abort_second_response
            BEFORE INSERT ON question_responses
            BEGIN
                UPDATE _counter SET n = n + 1;
                SELECT CASE
                    WHEN (SELECT n FROM _counter) >= 2
                    THEN RAISE(ABORT, 'deliberate abort on 2nd row')
                END;
            END
        """)
        raw_conn.commit()
        raw_conn.close()

        # Try to insert 2 responses — trigger aborts the 2nd, rolling back both
        two_responses = [
            {"question_text": "Q1?", "correct_answer": "A. 1",
             "student_answer": "A. 1", "is_correct": 1},
            {"question_text": "Q2?", "correct_answer": "B. 2",
             "student_answer": "B. 2", "is_correct": 1},
        ]
        try:
            db_module.save_question_responses(aid, two_responses)
        except Exception:
            pass  # expected — trigger fired

        df = db_module.get_responses_by_attempt(aid)
        assert len(df) == 0, (
            f"Expected 0 rows after trigger-aborted save, got {len(df)}"
        )
        ok("9. trigger aborts 2nd insert → full rollback → 0 response rows remain")
    except Exception as e:
        fail("9. transaction rollback (trigger)", str(e))
    finally:
        _close_temp_db(tmp)
else:
    skip("9. trigger rollback", "database import failed")

# ════════════════════════════════════════════════════════════════════════════ #
# 10. Retry: same attempt_id → 1 attempt, correct response count, no extras  #
# ════════════════════════════════════════════════════════════════════════════ #
if _db_ok:
    tmp, sid = _open_temp_db()
    try:
        # Create attempt once
        aid = db_module.save_quiz_attempt(sid, "Math", "Algebra", "easy", 2, 3, 0.67)

        # First response-save attempt: pass a bad key to force failure
        bad_responses = [
            {"question_text": "Q1?", "correct_answer": "A. 1",
             "student_answer": "A. 1", "is_correct": 1},
            {"WRONG_KEY": "boom"},
        ]
        try:
            db_module.save_question_responses(aid, bad_responses)
        except Exception:
            pass  # expected

        # Confirm 0 rows after failure
        assert len(db_module.get_responses_by_attempt(aid)) == 0

        # Retry with the SAME attempt_id (quiz.py stores it in session state)
        good_responses = [
            {"question_text": "Q1?", "correct_answer": "A. 1",
             "student_answer": "A. 1", "is_correct": 1},
            {"question_text": "Q2?", "correct_answer": "B. 2",
             "student_answer": "",    "is_correct": 0},
        ]
        db_module.save_question_responses(aid, good_responses)

        # Exactly 1 attempt, exactly 2 responses (no duplicates)
        attempts_df = db_module.get_attempts_by_student(sid)
        assert len(attempts_df) == 1, f"Expected 1 attempt, got {len(attempts_df)}"
        resp_df = db_module.get_responses_by_attempt(aid)
        assert len(resp_df) == 2, f"Expected 2 responses after retry, got {len(resp_df)}"
        ok("10. retry with same attempt_id: 1 attempt, 2 responses, no duplicates")
    except Exception as e:
        fail("10. retry no-duplicate", str(e))
    finally:
        _close_temp_db(tmp)
else:
    skip("10. retry no-duplicate", "database import failed")

# ════════════════════════════════════════════════════════════════════════════ #
# AppTest UI checks 11–24                                                      #
# ════════════════════════════════════════════════════════════════════════════ #
try:
    from streamlit.testing.v1 import AppTest
    _apptest_ok = True
except ImportError:
    _apptest_ok = False

if not _apptest_ok or not _db_ok:
    reason = "streamlit.testing.v1 unavailable" if not _apptest_ok else "db import failed"
    for n in range(11, 25):
        skip(f"{n}. AppTest", reason)
else:
    import learnmate_ai.llm_adapter as la

    shim_src = """\
import sys, os
sys.path.insert(0, os.path.abspath('.'))
from learnmate_ai.pages.quiz import render
render()
"""
    shim_fd, shim_path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(shim_fd, "w", encoding="utf-8") as fh:
        fh.write(shim_src)

    SAMPLE_Q = [
        {"question": "What is 2+2?",
         "options": ["A. 3", "B. 4", "C. 5", "D. 6"], "answer": "B"},
        {"question": "Sky colour?",
         "options": ["A. Red", "B. Green", "C. Blue", "D. Yellow"], "answer": "C"},
        {"question": "Capital of France?",
         "options": ["A. Rome", "B. Berlin", "C. Madrid", "D. Paris"], "answer": "D"},
    ]

    def _fresh_at(*, profile: bool = True) -> AppTest:
        at = AppTest.from_file(shim_path)
        if profile:
            at.session_state["student_id"]     = 1
            at.session_state["student_name"]   = "Tester"
            at.session_state["learning_level"] = "Beginner"
        return at

    def _generate(at: AppTest, questions: list[dict]) -> AppTest:
        """Drive the generation form; returns at after questions are loaded."""
        with patch.object(la, "is_demo_mode", return_value=True), \
             patch.object(la, "generate_quiz", return_value=questions):
            at.run()
            at.text_input[0].set_value("Mathematics")
            at.text_input[1].set_value("Algebra")
            at.button[0].click()
            at.run()
        return at

    def _submit_btn(at: AppTest):
        return next((b for b in at.button if "Submit" in b.label), None)

    def _newquiz_btn(at: AppTest):
        return next((b for b in at.button if "New Quiz" in b.label), None)

    try:
        # 11. Profile guard
        try:
            at11 = AppTest.from_file(shim_path)
            with patch.object(la, "is_demo_mode", return_value=True):
                at11.run()
            assert not at11.exception
            warnings = [w.value for w in at11.warning]
            assert any("Profile" in w for w in warnings), f"warnings: {warnings}"
            assert not at11.text_input, "No inputs expected without profile"
            ok("11. profile guard: warning shown, form not rendered")
        except Exception as e:
            fail("11. profile guard", str(e))

        # 12. Demo mode badge
        try:
            at12 = _fresh_at()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "generate_quiz", return_value=SAMPLE_Q):
                at12.run()
            infos = [i.value for i in at12.info]
            assert any("Demo Mode" in i for i in infos), f"infos: {infos}"
            ok("12. demo mode badge (st.info) shown")
        except Exception as e:
            fail("12. demo badge", str(e))

        # 13. Empty subject → error
        try:
            at13 = _fresh_at()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "generate_quiz", return_value=SAMPLE_Q):
                at13.run()
                at13.text_input[0].set_value("")
                at13.text_input[1].set_value("Algebra")
                at13.button[0].click()
                at13.run()
            assert at13.error, "Expected error for empty subject"
            ok("13. empty subject → error")
        except Exception as e:
            fail("13. empty subject", str(e))

        # 14. Empty topic → error
        try:
            at14 = _fresh_at()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "generate_quiz", return_value=SAMPLE_Q):
                at14.run()
                at14.text_input[0].set_value("Mathematics")
                at14.text_input[1].set_value("")
                at14.button[0].click()
                at14.run()
            assert at14.error, "Expected error for empty topic"
            ok("14. empty topic → error")
        except Exception as e:
            fail("14. empty topic", str(e))

        # 15. Quiz generates → N radios
        try:
            at15 = _fresh_at()
            _generate(at15, SAMPLE_Q)
            assert not at15.exception, f"Exception: {at15.exception}"
            assert len(at15.radio) == len(SAMPLE_Q), (
                f"Expected {len(SAMPLE_Q)} radios, got {len(at15.radio)}"
            )
            ok(f"15. quiz generates: {len(SAMPLE_Q)} radio widgets")
        except Exception as e:
            fail("15. quiz generation", str(e))

        # 16. New Quiz on_click clears answer keys and current_quiz
        try:
            at16 = _fresh_at()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "generate_quiz", return_value=SAMPLE_Q):
                at16.run()
                at16.text_input[0].set_value("Mathematics")
                at16.text_input[1].set_value("Algebra")
                at16.button[0].click()
                at16.run()
                # Select an answer for Q1
                at16.radio[0].set_value(SAMPLE_Q[0]["options"][0])
                at16.run()
                # Click New Quiz
                _newquiz_btn(at16).click()
                at16.run()
            # current_quiz must be gone
            assert "current_quiz" not in at16.session_state
            # answer_1 must be None or absent
            try:
                val = at16.session_state["answer_1"]
                assert val is None, f"answer_1={val!r}, expected None"
            except KeyError:
                pass  # absent is fine
            ok("16. New Quiz on_click: answer keys cleared, current_quiz removed")
        except Exception as e:
            fail("16. New Quiz reset", str(e))

        # 17. Shorter new quiz has no answers inherited from longer prior quiz
        try:
            LONG_Q  = SAMPLE_Q + [
                {"question": "Extra Q?",
                 "options": ["A. 1", "B. 2", "C. 3", "D. 4"], "answer": "A"},
            ]
            SHORT_Q = SAMPLE_Q[:2]

            at17 = _fresh_at()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "generate_quiz", return_value=LONG_Q):
                at17.run()
                at17.text_input[0].set_value("Mathematics")
                at17.text_input[1].set_value("Algebra")
                at17.button[0].click()
                at17.run()
                for i, r in enumerate(at17.radio):
                    r.set_value(LONG_Q[i]["options"][0])
                at17.run()

            # Now start a shorter new quiz
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "generate_quiz", return_value=SHORT_Q):
                _newquiz_btn(at17).click()
                at17.run()
                at17.text_input[0].set_value("Science")
                at17.text_input[1].set_value("Biology")
                at17.button[0].click()
                at17.run()

            # answer_3 and answer_4 must be gone / None
            for i in (3, 4):
                try:
                    val = at17.session_state[f"answer_{i}"]
                    assert val is None, f"answer_{i}={val!r}"
                except KeyError:
                    pass
            assert len(at17.radio) == len(SHORT_Q)
            ok("17. shorter new quiz: no answers inherited from longer prior quiz")
        except Exception as e:
            fail("17. no answer inheritance", str(e))

        # 18. Unanswered — first Submit warns; second submits
        try:
            at18 = _fresh_at()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "generate_quiz", return_value=SAMPLE_Q), \
                 patch.object(db_module, "save_quiz_attempt", return_value=42), \
                 patch.object(db_module, "save_question_responses", return_value=None):
                at18.run()
                at18.text_input[0].set_value("Mathematics")
                at18.text_input[1].set_value("Algebra")
                at18.button[0].click()
                at18.run()
                _submit_btn(at18).click()
                at18.run()
            assert at18.warning, "Expected unanswered warning"
            submitted_after_warn = at18.session_state["quiz_submitted"] if "quiz_submitted" in at18.session_state else False
            assert submitted_after_warn is not True
            ok("18a. unanswered first Submit → warning, not yet submitted")

            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "save_quiz_attempt", return_value=42), \
                 patch.object(db_module, "save_question_responses", return_value=None):
                _submit_btn(at18).click()
                at18.run()
            assert at18.session_state["quiz_submitted"] is True
            ok("18b. unanswered second Submit → quiz evaluated")
        except Exception as e:
            fail("18. unanswered handling", str(e))

        # 19. All-answered Submit → feedback phase
        try:
            at19 = _fresh_at()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "generate_quiz", return_value=SAMPLE_Q), \
                 patch.object(db_module, "save_quiz_attempt", return_value=99), \
                 patch.object(db_module, "save_question_responses", return_value=None):
                at19.run()
                at19.text_input[0].set_value("Mathematics")
                at19.text_input[1].set_value("Algebra")
                at19.button[0].click()
                at19.run()
                for i, r in enumerate(at19.radio):
                    r.set_value(SAMPLE_Q[i]["options"][0])
                _submit_btn(at19).click()
                at19.run()
            assert not at19.exception, f"Exception: {at19.exception}"
            assert at19.session_state["quiz_submitted"] is True
            ok("19. all-answered Submit → feedback phase")
        except Exception as e:
            fail("19. full submission", str(e))

        # 20. Feedback banner present
        try:
            all_banners = (
                [s.value for s in at19.success]
                + [i.value for i in at19.info]
                + [w.value for w in at19.warning]
            )
            assert any("Quiz Complete" in t for t in all_banners), (
                f"No 'Quiz Complete' banner; texts: {all_banners}"
            )
            ok("20. feedback banner (Quiz Complete) rendered")
        except Exception as e:
            fail("20. feedback banner", str(e))

        # 21. Question Feedback subheader
        try:
            subheaders = [s.value for s in at19.subheader]
            assert any("Feedback" in s for s in subheaders), (
                f"No 'Feedback' subheader; got: {subheaders}"
            )
            ok("21. Question Feedback subheader rendered")
        except Exception as e:
            fail("21. per-question feedback section", str(e))

        # 22. Both DB functions called exactly once
        try:
            m_attempt   = MagicMock(return_value=77)
            m_responses = MagicMock(return_value=None)
            at22 = _fresh_at()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "generate_quiz", return_value=SAMPLE_Q), \
                 patch.object(db_module, "save_quiz_attempt",       m_attempt), \
                 patch.object(db_module, "save_question_responses", m_responses):
                at22.run()
                at22.text_input[0].set_value("Mathematics")
                at22.text_input[1].set_value("Algebra")
                at22.button[0].click()
                at22.run()
                for i, r in enumerate(at22.radio):
                    r.set_value(SAMPLE_Q[i]["options"][0])
                _submit_btn(at22).click()
                at22.run()
            assert m_attempt.call_count == 1,   f"save_quiz_attempt called {m_attempt.call_count}x"
            assert m_responses.call_count == 1, f"save_question_responses called {m_responses.call_count}x"
            ok("22. persistence: both DB functions called exactly once")
        except Exception as e:
            fail("22. persistence call counts", str(e))

        # 23. Duplicate-save prevention: rerun does not call DB functions again
        try:
            m_attempt2   = MagicMock(return_value=88)
            m_responses2 = MagicMock(return_value=None)
            at23 = _fresh_at()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "generate_quiz", return_value=SAMPLE_Q), \
                 patch.object(db_module, "save_quiz_attempt",       m_attempt2), \
                 patch.object(db_module, "save_question_responses", m_responses2):
                at23.run()
                at23.text_input[0].set_value("Mathematics")
                at23.text_input[1].set_value("Algebra")
                at23.button[0].click()
                at23.run()
                for i, r in enumerate(at23.radio):
                    r.set_value(SAMPLE_Q[i]["options"][0])
                _submit_btn(at23).click()
                at23.run()   # first feedback render — saves
                at23.run()   # second render (rerun) — must NOT save again
            assert m_attempt2.call_count == 1,   f"save_quiz_attempt called {m_attempt2.call_count}x"
            assert m_responses2.call_count == 1, f"save_question_responses called {m_responses2.call_count}x"
            ok("23. duplicate-save prevention: DB functions called once across reruns")
        except Exception as e:
            fail("23. duplicate-save prevention", str(e))

        # 24. Response-save failure: attempt_id stored, no duplicate attempt on retry
        try:
            m_attempt3   = MagicMock(return_value=55)
            m_resp_fail  = MagicMock(side_effect=Exception("write error"))
            m_resp_retry = MagicMock(return_value=None)

            at24 = _fresh_at()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "generate_quiz", return_value=SAMPLE_Q), \
                 patch.object(db_module, "save_quiz_attempt",       m_attempt3), \
                 patch.object(db_module, "save_question_responses", m_resp_fail):
                at24.run()
                at24.text_input[0].set_value("Mathematics")
                at24.text_input[1].set_value("Algebra")
                at24.button[0].click()
                at24.run()
                for i, r in enumerate(at24.radio):
                    r.set_value(SAMPLE_Q[i]["options"][0])
                _submit_btn(at24).click()
                at24.run()   # attempt saved, responses fail

            assert at24.session_state["quiz_attempt_id"] == 55, (
                f"Expected quiz_attempt_id=55, got "
                + str(at24.session_state["quiz_attempt_id"] if "quiz_attempt_id" in at24.session_state else "MISSING")
            )
            responses_saved_val = at24.session_state["quiz_responses_saved"] if "quiz_responses_saved" in at24.session_state else False
            assert responses_saved_val is False, f"quiz_responses_saved={responses_saved_val!r}"

            # Rerun with responses now succeeding
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "save_quiz_attempt",       m_attempt3), \
                 patch.object(db_module, "save_question_responses", m_resp_retry):
                at24.run()   # retry rerun

            assert m_attempt3.call_count == 1, (
                f"save_quiz_attempt called {m_attempt3.call_count}x (expected 1)"
            )
            assert m_resp_retry.call_count == 1, (
                f"save_question_responses (retry) called {m_resp_retry.call_count}x"
            )
            ok("24. response-save failure: attempt_id stored, no duplicate attempt on retry")
        except Exception as e:
            fail("24. response-save failure / retry", str(e))

    finally:
        try:
            os.unlink(shim_path)
        except OSError:
            pass

# ════════════════════════════════════════════════════════════════════════════ #
# Summary                                                                      #
# ════════════════════════════════════════════════════════════════════════════ #
print()
print(f"Results: {len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped.")
if failed:
    print("FAILED:")
    for f_ in failed:
        print(f"  [x] {f_}")
if skipped:
    print("Skipped:")
    for s_ in skipped:
        print(f"  [-] {s_}")
if not failed and not skipped:
    print("All checks passed.")
elif not failed:
    print("No failures — skipped checks noted above.")
else:
    sys.exit(1)
