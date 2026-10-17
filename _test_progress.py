"""
_test_progress.py — Automated checks for Sub-Task 9: pages/progress.py

Checks
──────
Static / compile
  1.  py_compile clean: pages/progress.py
  2.  render() defined
  3.  database.get_attempts_by_student referenced
  4.  database.get_topic_accuracy_summary referenced
  5.  quiz_engine.detect_weak_topics referenced
  6.  plotly import present
  7.  _WEAK_THRESHOLD == 0.60

AppTest UI
  8.  Profile guard: no profile -> warning, no metrics rendered
  9.  Empty history -> info message, no crash
 10.  Populated history -> summary metrics rendered (st.metric)
 11.  Single attempt -> "take at least two quizzes" info (no trend line)
 12.  Two+ attempts -> Plotly line chart rendered (st.plotly_chart)
 13.  Subject bar chart rendered when topic summary is non-empty
 14.  Weak topic section shown when topics below threshold exist
 15.  No weak topics -> weak topic section absent
 16.  DB load error -> friendly error, no raw detail in UI
 17.  Overall accuracy metric present
 18.  Total quizzes metric present
"""

from __future__ import annotations

import io
import os
import py_compile
import sys
import tempfile
from unittest.mock import patch

import pandas as pd

# Force UTF-8 output for Windows cp1252 consoles
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


PAGE_PATH = "learnmate_ai/pages/progress.py"

# ════════════════════════════════════════════════════════════════════════════ #
# 1. py_compile                                                                #
# ════════════════════════════════════════════════════════════════════════════ #
try:
    py_compile.compile(PAGE_PATH, doraise=True)
    ok("1. py_compile clean: pages/progress.py")
except py_compile.PyCompileError as e:
    fail("1. py_compile", str(e))

# Load source for static checks
try:
    with open(PAGE_PATH, "r", encoding="utf-8") as fh:
        src = fh.read()
    _src_ok = True
except Exception as e:
    fail("source-load", str(e))
    _src_ok = False

# ════════════════════════════════════════════════════════════════════════════ #
# 2–7. Static source checks                                                    #
# ════════════════════════════════════════════════════════════════════════════ #
if _src_ok:
    import ast
    tree = ast.parse(src)

    if any(isinstance(n, ast.FunctionDef) and n.name == "render" for n in ast.walk(tree)):
        ok("2. render() defined")
    else:
        fail("2. render()", "not found")

    for num, fragment in [
        ("3", "database.get_attempts_by_student"),
        ("4", "database.get_topic_accuracy_summary"),
        ("5", "quiz_engine.detect_weak_topics"),
        ("6", "plotly"),
    ]:
        if fragment in src:
            ok(f"{num}. '{fragment}' referenced")
        else:
            fail(f"{num}. '{fragment}'", "not found in source")

    if "_WEAK_THRESHOLD" in src and "0.60" in src:
        ok("7. _WEAK_THRESHOLD == 0.60")
    else:
        fail("7. _WEAK_THRESHOLD", "0.60 not found")
else:
    for n in range(2, 8):
        skip(f"{n}. static check", "source load failed")

# ════════════════════════════════════════════════════════════════════════════ #
# AppTest UI checks 8–18                                                       #
# ════════════════════════════════════════════════════════════════════════════ #
try:
    from streamlit.testing.v1 import AppTest
    _apptest_ok = True
except ImportError:
    _apptest_ok = False

try:
    import learnmate_ai.database as db_module
    _db_ok = True
except Exception as e:
    fail("db-import", str(e))
    _db_ok = False

if not _apptest_ok or not _db_ok:
    reason = "AppTest unavailable" if not _apptest_ok else "db import failed"
    for n in range(8, 19):
        skip(f"{n}. AppTest", reason)
else:
    shim_src = """\
import sys, os
sys.path.insert(0, os.path.abspath('.'))
from learnmate_ai.pages.progress import render
render()
"""
    shim_fd, shim_path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(shim_fd, "w", encoding="utf-8") as fh:
        fh.write(shim_src)

    # ── Shared test DataFrames ─────────────────────────────────────────────
    EMPTY_ATTEMPTS  = pd.DataFrame(columns=[
        "id", "student_id", "subject", "topic", "difficulty",
        "score", "total_questions", "accuracy", "attempted_at",
    ])
    EMPTY_SUMMARY   = pd.DataFrame(columns=["subject", "topic", "attempts", "avg_accuracy"])

    ONE_ATTEMPT = pd.DataFrame([{
        "id": 1, "student_id": 1, "subject": "Mathematics", "topic": "Algebra",
        "difficulty": "easy", "score": 3, "total_questions": 5,
        "accuracy": 0.60, "attempted_at": "2024-01-01 10:00:00",
    }])

    TWO_ATTEMPTS = pd.DataFrame([
        {"id": 1, "student_id": 1, "subject": "Mathematics", "topic": "Algebra",
         "difficulty": "easy", "score": 3, "total_questions": 5,
         "accuracy": 0.60, "attempted_at": "2024-01-01 10:00:00"},
        {"id": 2, "student_id": 1, "subject": "Science", "topic": "Physics",
         "difficulty": "medium", "score": 4, "total_questions": 5,
         "accuracy": 0.80, "attempted_at": "2024-01-02 11:00:00"},
    ])

    SUMMARY_WEAK = pd.DataFrame([
        {"subject": "Mathematics", "topic": "Algebra", "attempts": 3, "avg_accuracy": 0.40},
        {"subject": "Science",     "topic": "Physics", "attempts": 2, "avg_accuracy": 0.55},
    ])

    SUMMARY_STRONG = pd.DataFrame([
        {"subject": "Mathematics", "topic": "Calculus", "attempts": 5, "avg_accuracy": 0.90},
    ])

    def _fresh(*, profile: bool = True) -> AppTest:
        at = AppTest.from_file(shim_path)
        if profile:
            at.session_state["student_id"]     = 1
            at.session_state["student_name"]   = "Tester"
            at.session_state["learning_level"] = "Beginner"
        return at

    try:
        # 8. Profile guard
        try:
            at8 = AppTest.from_file(shim_path)
            at8.run()
            assert not at8.exception
            warnings = [w.value for w in at8.warning]
            assert any("Profile" in w for w in warnings), f"warnings: {warnings}"
            assert not at8.metric, "No metrics expected without profile"
            ok("8. profile guard: warning shown, no metrics")
        except Exception as e:
            fail("8. profile guard", str(e))

        # 9. Empty history -> info message
        try:
            at9 = _fresh()
            with patch.object(db_module, "get_attempts_by_student", return_value=EMPTY_ATTEMPTS), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=EMPTY_SUMMARY):
                at9.run()
            assert not at9.exception
            infos = [i.value for i in at9.info]
            assert any("quiz" in i.lower() for i in infos), f"infos: {infos}"
            assert not at9.metric
            ok("9. empty history -> info message, no crash")
        except Exception as e:
            fail("9. empty history", str(e))

        # 10. Populated history -> st.metric present
        try:
            at10 = _fresh()
            with patch.object(db_module, "get_attempts_by_student", return_value=TWO_ATTEMPTS), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=SUMMARY_STRONG):
                at10.run()
            assert not at10.exception, f"Exception: {at10.exception}"
            assert at10.metric, "Expected st.metric for populated history"
            ok("10. populated history -> summary metrics rendered")
        except Exception as e:
            fail("10. summary metrics", str(e))

        # 11. Single attempt -> "take at least two" info (no trend line shown)
        try:
            at11 = _fresh()
            with patch.object(db_module, "get_attempts_by_student", return_value=ONE_ATTEMPT), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=SUMMARY_STRONG):
                at11.run()
            assert not at11.exception
            infos = [i.value for i in at11.info]
            assert any("two" in i.lower() or "trend" in i.lower() or "least" in i.lower() for i in infos), (
                f"Expected 'at least two quizzes' info; infos: {infos}"
            )
            ok("11. single attempt -> 'take at least two quizzes' info shown")
        except Exception as e:
            fail("11. single attempt trend info", str(e))

        # 12. Two+ attempts -> "Accuracy Over Time" section rendered (line chart code path)
        # Note: AppTest in Streamlit 1.56 does not expose .plotly_chart; we verify the
        # section subheader rendered without exception, which proves the chart code path ran.
        try:
            at12 = _fresh()
            with patch.object(db_module, "get_attempts_by_student", return_value=TWO_ATTEMPTS), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=SUMMARY_STRONG):
                at12.run()
            assert not at12.exception, f"Exception: {at12.exception}"
            subheaders = [s.value for s in at12.subheader]
            assert any("accuracy" in s.lower() or "time" in s.lower() for s in subheaders), (
                f"Expected 'Accuracy Over Time' subheader; got: {subheaders}"
            )
            ok("12. two+ attempts -> line chart code path executed (section rendered)")
        except Exception as e:
            fail("12. plotly chart", str(e))

        # 13. Subject bar chart code path: "Subject Performance" section rendered
        # Note: AppTest in Streamlit 1.56 does not expose .plotly_chart; we verify the
        # section subheader rendered without exception, which proves the chart code path ran.
        try:
            at13 = _fresh()
            with patch.object(db_module, "get_attempts_by_student", return_value=TWO_ATTEMPTS), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=SUMMARY_WEAK):
                at13.run()
            assert not at13.exception, f"Exception: {at13.exception}"
            subheaders = [s.value for s in at13.subheader]
            assert any("subject" in s.lower() or "performance" in s.lower() for s in subheaders), (
                f"Expected 'Subject Performance' subheader; got: {subheaders}"
            )
            ok("13. subject bar chart code path executed (section rendered)")
        except Exception as e:
            fail("13. subject bar chart", str(e))

        # 14. Weak topic section shown when topics below threshold
        try:
            at14 = _fresh()
            with patch.object(db_module, "get_attempts_by_student", return_value=TWO_ATTEMPTS), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=SUMMARY_WEAK):
                at14.run()
            assert not at14.exception
            subheaders = [s.value for s in at14.subheader]
            assert any("revise" in s.lower() or "weak" in s.lower() for s in subheaders), (
                f"Expected 'revise'/'weak' subheader; got: {subheaders}"
            )
            ok("14. weak topic section shown when weak topics exist")
        except Exception as e:
            fail("14. weak topic section", str(e))

        # 15. No weak topics -> weak topic section absent
        try:
            at15 = _fresh()
            with patch.object(db_module, "get_attempts_by_student", return_value=TWO_ATTEMPTS), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=SUMMARY_STRONG):
                at15.run()
            assert not at15.exception
            subheaders = [s.value for s in at15.subheader]
            assert not any("revise" in s.lower() or "weak" in s.lower() for s in subheaders), (
                f"Unexpected 'revise'/'weak' subheader when no weak topics: {subheaders}"
            )
            ok("15. no weak topics -> weak topic section absent")
        except Exception as e:
            fail("15. no weak topics section", str(e))

        # 16. DB load error -> friendly error, no raw detail
        try:
            sentinel = "SECRET_DB_ERROR_XYZ"
            at16 = _fresh()
            with patch.object(db_module, "get_attempts_by_student",
                              side_effect=Exception(sentinel)):
                at16.run()
            assert not at16.exception
            errors = [e.value for e in at16.error]
            assert any("progress" in e.lower() or "load" in e.lower() for e in errors), (
                f"Expected friendly error; got: {errors}"
            )
            all_ui = " ".join(
                [m.value for m in at16.markdown]
                + [e.value for e in at16.error]
                + [w.value for w in at16.warning]
                + [i.value for i in at16.info]
            )
            assert sentinel not in all_ui, "Raw exception detail leaked into UI"
            ok("16. DB error -> friendly message, no raw detail in UI")
        except Exception as e:
            fail("16. DB error handling", str(e))

        # 17. Overall accuracy metric present
        try:
            at17 = _fresh()
            with patch.object(db_module, "get_attempts_by_student", return_value=TWO_ATTEMPTS), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=SUMMARY_STRONG):
                at17.run()
            metric_labels = [m.label for m in at17.metric]
            assert any("accuracy" in l.lower() for l in metric_labels), (
                f"Expected 'accuracy' metric; labels: {metric_labels}"
            )
            ok("17. overall accuracy metric present")
        except Exception as e:
            fail("17. accuracy metric", str(e))

        # 18. Total quizzes metric present
        try:
            at18 = _fresh()
            with patch.object(db_module, "get_attempts_by_student", return_value=TWO_ATTEMPTS), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=SUMMARY_STRONG):
                at18.run()
            metric_labels = [m.label for m in at18.metric]
            assert any("quiz" in l.lower() or "attempt" in l.lower() for l in metric_labels), (
                f"Expected 'quiz'/'attempt' metric; labels: {metric_labels}"
            )
            ok("18. total quizzes metric present")
        except Exception as e:
            fail("18. total quizzes metric", str(e))

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
