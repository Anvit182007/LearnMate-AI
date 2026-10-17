"""
_test_study_planner_v2.py — Tests for the improved Study Planner (day-by-day schedule).

Checks
──────
Static / compile
  1.  py_compile clean: pages/study_planner.py, study_planner.py, llm_adapter.py
  2.  _render_schedule_form defined in pages/study_planner.py
  3.  build_scheduled_plan defined in study_planner.py
  4.  generate_scheduled_plan defined in llm_adapter.py
  5.  _demo_generate_scheduled_plan defined in llm_adapter.py
  6.  'st.button' referenced in pages/study_planner.py
  7.  'sched_submit_btn' key referenced in pages/study_planner.py
  8.  'hours_per_day' referenced in pages/study_planner.py
  9.  'target_date' referenced in pages/study_planner.py

Logic unit tests (no UI)
 10.  build_scheduled_plan: demo mode returns schedule text (non-empty)
 11.  build_scheduled_plan: weak topics appear in schedule output
 12.  build_scheduled_plan: subject/topic from form appear in schedule output
 13.  build_scheduled_plan: empty subjects + weak topics => generates from weak topics
 14.  build_scheduled_plan: LLMError falls back gracefully, no exception raised
 15.  _demo_generate_scheduled_plan: target date appears in output
 16.  _demo_generate_scheduled_plan: level tip appears in output (Beginner)
 17.  _demo_generate_scheduled_plan: no weak topics => still generates a schedule

AppTest UI
 18.  Schedule form renders on the page (st.form present)
 19.  Submit with empty inputs + no weak topics => validation error
 20.  Submit with partial row (subject only) => validation error
 21.  Submit with valid inputs => schedule output rendered (st.markdown present)
 22.  Weak-topic auto-prioritisation notice shown in form when weak topics exist
 23.  Balanced-plan notice shown in form when no weak topics
 24.  Schedule source label shown after generation
 25.  No 'use_container_width' in pages/study_planner.py (already checked by v1 test 23)
"""

from __future__ import annotations

import io
import os
import py_compile
import sys
import tempfile
from unittest.mock import MagicMock, patch

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


PAGE_PATH     = "learnmate_ai/pages/study_planner.py"
LOGIC_PATH    = "learnmate_ai/study_planner.py"
ADAPTER_PATH  = "learnmate_ai/llm_adapter.py"

# ════════════════════════════════════════════════════════════════════════════ #
# 1. py_compile                                                                #
# ════════════════════════════════════════════════════════════════════════════ #
compile_ok = True
for path in [PAGE_PATH, LOGIC_PATH, ADAPTER_PATH]:
    try:
        py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as e:
        fail(f"1. py_compile: {path}", str(e))
        compile_ok = False
if compile_ok:
    ok("1. py_compile clean: all three files")

# Load sources for static checks
try:
    with open(PAGE_PATH,    encoding="utf-8") as f: page_src    = f.read()
    with open(LOGIC_PATH,   encoding="utf-8") as f: logic_src   = f.read()
    with open(ADAPTER_PATH, encoding="utf-8") as f: adapter_src = f.read()
    src_ok = True
except Exception as e:
    fail("source-load", str(e))
    src_ok = False

# ════════════════════════════════════════════════════════════════════════════ #
# 2–9. Static checks                                                           #
# ════════════════════════════════════════════════════════════════════════════ #
if src_ok:
    checks = [
        ("2", "_render_schedule_form",      page_src,    "pages/study_planner.py"),
        ("3", "build_scheduled_plan",       logic_src,   "study_planner.py"),
        ("4", "generate_scheduled_plan",    adapter_src, "llm_adapter.py"),
        ("5", "_demo_generate_scheduled_plan", adapter_src, "llm_adapter.py"),
        ("6", "st.button",                  page_src,    "pages/study_planner.py"),
        ("7", "sched_submit_btn",           page_src,    "pages/study_planner.py"),
        ("8", "hours_per_day",              page_src,    "pages/study_planner.py"),
        ("9", "target_date",                page_src,    "pages/study_planner.py"),
    ]
    for num, fragment, src, loc in checks:
        if fragment in src:
            ok(f"{num}. '{fragment}' found in {loc}")
        else:
            fail(f"{num}. '{fragment}'", f"not found in {loc}")
else:
    for n in range(2, 10):
        skip(f"{n}. static check", "source load failed")

# ════════════════════════════════════════════════════════════════════════════ #
# 10–17. Logic unit tests                                                      #
# ════════════════════════════════════════════════════════════════════════════ #
try:
    import learnmate_ai.study_planner as sp_module
    import learnmate_ai.llm_adapter   as adapter_module
    logic_import_ok = True
except Exception as e:
    fail("logic-import", str(e))
    logic_import_ok = False

EMPTY_SUMMARY = pd.DataFrame(columns=["subject", "topic", "attempts", "avg_accuracy"])
WEAK_SUMMARY  = pd.DataFrame([
    {"subject": "Mathematics", "topic": "Algebra",  "attempts": 3, "avg_accuracy": 0.40},
    {"subject": "Science",     "topic": "Physics",  "attempts": 2, "avg_accuracy": 0.55},
])
STRONG_SUMMARY = pd.DataFrame([
    {"subject": "Mathematics", "topic": "Calculus", "attempts": 5, "avg_accuracy": 0.90},
])

if logic_import_ok:
    # 10. Demo mode build_scheduled_plan returns non-empty text
    try:
        with patch.object(adapter_module, "is_demo_mode", return_value=True):
            result = sp_module.build_scheduled_plan(
                subjects=["Mathematics"],
                topics=["Algebra"],
                hours_per_day=1.5,
                target_date="2024-12-15",
                summary_df=WEAK_SUMMARY,
                level="Beginner",
            )
        assert result and len(result) > 50, f"Too short: {result!r}"
        ok("10. build_scheduled_plan: demo mode returns non-empty schedule")
    except Exception as e:
        fail("10. build_scheduled_plan demo", str(e))

    # 11. Weak topics appear in schedule output
    try:
        with patch.object(adapter_module, "is_demo_mode", return_value=True):
            result = sp_module.build_scheduled_plan(
                subjects=[], topics=[],
                hours_per_day=1.0, target_date="2024-12-01",
                summary_df=WEAK_SUMMARY, level="Intermediate",
            )
        assert "Algebra" in result or "Physics" in result, (
            f"Expected weak topic in output; got:\n{result[:300]}"
        )
        ok("11. build_scheduled_plan: weak topics appear in schedule")
    except Exception as e:
        fail("11. weak topics in schedule", str(e))

    # 12. Subject/topic from form appear in schedule when no weak topics
    try:
        with patch.object(adapter_module, "is_demo_mode", return_value=True):
            result = sp_module.build_scheduled_plan(
                subjects=["History"],
                topics=["World War II"],
                hours_per_day=2.0, target_date="2025-01-10",
                summary_df=STRONG_SUMMARY, level="Advanced",
            )
        assert "History" in result or "World War II" in result, (
            f"Expected user topic in output; got:\n{result[:300]}"
        )
        ok("12. build_scheduled_plan: form subject/topic appear in schedule")
    except Exception as e:
        fail("12. user topics in schedule", str(e))

    # 13. Empty subjects + weak topics => generates from weak topics
    try:
        with patch.object(adapter_module, "is_demo_mode", return_value=True):
            result = sp_module.build_scheduled_plan(
                subjects=[], topics=[],
                hours_per_day=1.0, target_date="2024-11-30",
                summary_df=WEAK_SUMMARY, level="Beginner",
            )
        assert result and len(result) > 50
        ok("13. build_scheduled_plan: empty subjects + weak topics => generates schedule")
    except Exception as e:
        fail("13. empty subjects with weak topics", str(e))

    # 14. LLMError falls back gracefully
    try:
        with patch.object(adapter_module, "is_demo_mode", return_value=False), \
             patch.object(adapter_module, "generate_scheduled_plan",
                          side_effect=adapter_module.LLMError("api down")):
            result = sp_module.build_scheduled_plan(
                subjects=["Science"], topics=["Biology"],
                hours_per_day=1.0, target_date="2025-02-01",
                summary_df=EMPTY_SUMMARY, level="Beginner",
            )
        assert result and len(result) > 10
        ok("14. build_scheduled_plan: LLMError => graceful fallback, no exception raised")
    except Exception as e:
        fail("14. LLMError fallback", str(e))

    # 15. _demo_generate_scheduled_plan: target date in output
    try:
        result = adapter_module._demo_generate_scheduled_plan(
            subjects=["Math"], topics=["Calculus"],
            hours_per_day=1.0, target_date="2024-12-25",
            weak_topics=[], level="Intermediate",
        )
        assert "2024-12-25" in result, f"Target date not found in: {result[:200]}"
        ok("15. _demo_generate_scheduled_plan: target date appears in output")
    except Exception as e:
        fail("15. target date in demo schedule", str(e))

    # 16. _demo_generate_scheduled_plan: level tip for Beginner
    try:
        result = adapter_module._demo_generate_scheduled_plan(
            subjects=["Math"], topics=["Arithmetic"],
            hours_per_day=1.0, target_date="2025-01-01",
            weak_topics=[], level="Beginner",
        )
        assert "Beginner" in result or "foundation" in result.lower(), (
            f"Expected Beginner tip; got:\n{result[:300]}"
        )
        ok("16. _demo_generate_scheduled_plan: level tip (Beginner) present")
    except Exception as e:
        fail("16. level tip in demo schedule", str(e))

    # 17. _demo_generate_scheduled_plan: no weak topics => still generates
    try:
        result = adapter_module._demo_generate_scheduled_plan(
            subjects=["English"], topics=["Grammar"],
            hours_per_day=1.5, target_date="2025-03-01",
            weak_topics=[], level="Advanced",
        )
        assert result and len(result) > 50
        assert "Grammar" in result or "English" in result, (
            f"Expected topic in output; got:\n{result[:200]}"
        )
        ok("17. _demo_generate_scheduled_plan: no weak topics => schedule generated")
    except Exception as e:
        fail("17. no-weak-topics schedule", str(e))
else:
    for n in range(10, 18):
        skip(f"{n}. logic test", "module import failed")

# ════════════════════════════════════════════════════════════════════════════ #
# 18–25. AppTest UI checks                                                     #
# ════════════════════════════════════════════════════════════════════════════ #
try:
    from streamlit.testing.v1 import AppTest
    apptest_ok = True
except ImportError:
    apptest_ok = False

try:
    import learnmate_ai.database as db_module
    db_ok = True
except Exception as e:
    fail("db-import", str(e))
    db_ok = False

if not apptest_ok or not db_ok or not logic_import_ok:
    reason = "AppTest/import unavailable"
    for n in range(18, 26):
        skip(f"{n}. AppTest", reason)
else:
    shim_src = """\
import sys, os
sys.path.insert(0, os.path.abspath('.'))
from learnmate_ai.pages.study_planner import render
render()
"""
    shim_fd, shim_path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(shim_fd, "w", encoding="utf-8") as fh:
        fh.write(shim_src)

    def _fresh(*, profile: bool = True) -> "AppTest":
        at = AppTest.from_file(shim_path)
        if profile:
            at.session_state["student_id"]     = 1
            at.session_state["student_name"]   = "Tester"
            at.session_state["learning_level"] = "Beginner"
        return at

    _DEMO_SCHEDULE = (
        "# Demo Schedule\n\nDay 1 — Mathematics: Algebra\n- Review\n- Practice"
    )

    try:
        # 18. Schedule form renders
        try:
            at18 = _fresh()
            with patch.object(db_module, "get_topic_accuracy_summary",
                               return_value=WEAK_SUMMARY), \
                 patch.object(db_module, "get_attempts_by_student",
                               return_value=EMPTY_SUMMARY), \
                 patch.object(sp_module,  "build_study_plan",
                               return_value="## Plan\n\nStudy hard."), \
                 patch.object(adapter_module, "is_demo_mode", return_value=True):
                at18.run()
            assert not at18.exception, f"Exception: {at18.exception}"
            # st.form renders a markdown/text_input — check for the text_input widgets
            assert at18.text_input, "Expected text_input widgets from schedule form"
            ok("18. schedule form renders on the page")
        except Exception as e:
            fail("18. schedule form renders", str(e))

        # 19. Submit with empty inputs + no weak topics => validation error
        # AppTest submit: click the form submit button widget, then run inside the patch block.
        try:
            at19 = _fresh()
            with patch.object(db_module, "get_topic_accuracy_summary",
                               return_value=STRONG_SUMMARY), \
                 patch.object(sp_module,  "build_study_plan",
                               return_value="## Plan"), \
                 patch.object(adapter_module, "is_demo_mode", return_value=True):
                at19.run()
                # Use exact label match to avoid catching "Refresh Plan" button
                sched_btn_19 = next(
                    (b for b in at19.button if b.label == "Generate Study Plan"), None
                )
                assert sched_btn_19, (
                    f"'Generate Study Plan' button not found; buttons: {[b.label for b in at19.button]}"
                )
                sched_btn_19.click()
                at19.run()
            assert not at19.exception, f"Exception: {at19.exception}"
            errors = [e.value for e in at19.error]
            assert any("subject" in e.lower() or "topic" in e.lower() or "quiz" in e.lower()
                       for e in errors), f"Expected validation error; got: {errors}"
            ok("19. empty inputs + no weak topics => validation error")
        except Exception as e:
            fail("19. empty-inputs validation", str(e))

        # 20. Partial row (subject only) => validation error
        try:
            at20 = _fresh()
            with patch.object(db_module, "get_topic_accuracy_summary",
                               return_value=STRONG_SUMMARY), \
                 patch.object(sp_module,  "build_study_plan",
                               return_value="## Plan"), \
                 patch.object(adapter_module, "is_demo_mode", return_value=True):
                at20.run()
                at20.text_input[0].set_value("Mathematics")  # subject filled, topic blank
                sched_btn_20 = next(
                    (b for b in at20.button if b.label == "Generate Study Plan"), None
                )
                assert sched_btn_20, "Generate Study Plan button not found"
                sched_btn_20.click()
                at20.run()
            assert not at20.exception
            errors = [e.value for e in at20.error]
            assert any("topic" in e.lower() or "subject" in e.lower() for e in errors), (
                f"Expected partial-row error; got: {errors}"
            )
            ok("20. partial row (subject only) => validation error")
        except Exception as e:
            fail("20. partial-row validation", str(e))

        # 21. Valid inputs => schedule rendered (st.markdown present after submit)
        try:
            at21 = _fresh()
            with patch.object(db_module, "get_topic_accuracy_summary",
                               return_value=WEAK_SUMMARY), \
                 patch.object(sp_module,  "build_study_plan",
                               return_value="## Plan"), \
                 patch.object(sp_module,  "build_scheduled_plan",
                               return_value=_DEMO_SCHEDULE), \
                 patch.object(adapter_module, "is_demo_mode", return_value=True):
                at21.run()
                at21.text_input[0].set_value("Mathematics")
                at21.text_input[1].set_value("Algebra")
                sched_btn_21 = next(
                    (b for b in at21.button if b.label == "Generate Study Plan"), None
                )
                assert sched_btn_21, "Generate Study Plan button not found"
                sched_btn_21.click()
                at21.run()
            assert not at21.exception, f"Exception: {at21.exception}"
            markdown_vals = [m.value for m in at21.markdown]
            assert any("Day" in m or "Schedule" in m for m in markdown_vals), (
                f"Expected schedule content in markdown; got: {markdown_vals[:3]}"
            )
            ok("21. valid inputs => schedule output rendered")
        except Exception as e:
            fail("21. valid submit => schedule rendered", str(e))

        # 22. Weak-topic notice shown in form when weak topics exist
        try:
            at22 = _fresh()
            with patch.object(db_module, "get_topic_accuracy_summary",
                               return_value=WEAK_SUMMARY), \
                 patch.object(sp_module,  "build_study_plan",
                               return_value="## Plan"), \
                 patch.object(adapter_module, "is_demo_mode", return_value=True):
                at22.run()
            assert not at22.exception
            infos = [i.value for i in at22.info]
            assert any("weak" in i.lower() or "prioritis" in i.lower() for i in infos), (
                f"Expected weak-topic notice in st.info; got: {infos}"
            )
            ok("22. weak-topic auto-prioritisation notice shown in form")
        except Exception as e:
            fail("22. weak-topic notice in form", str(e))

        # 23. Balanced-plan notice when no weak topics
        try:
            at23 = _fresh()
            with patch.object(db_module, "get_topic_accuracy_summary",
                               return_value=STRONG_SUMMARY), \
                 patch.object(sp_module,  "build_study_plan",
                               return_value="## Plan"), \
                 patch.object(adapter_module, "is_demo_mode", return_value=True):
                at23.run()
            assert not at23.exception
            infos = [i.value for i in at23.info]
            assert any("balanced" in i.lower() or "no weak" in i.lower() for i in infos), (
                f"Expected balanced-plan notice; got: {infos}"
            )
            ok("23. balanced-plan notice shown when no weak topics")
        except Exception as e:
            fail("23. balanced-plan notice", str(e))

        # 24. Schedule source label shown after generation
        try:
            at24 = _fresh()
            with patch.object(db_module, "get_topic_accuracy_summary",
                               return_value=WEAK_SUMMARY), \
                 patch.object(sp_module,  "build_study_plan",
                               return_value="## Plan"), \
                 patch.object(sp_module,  "build_scheduled_plan",
                               return_value=_DEMO_SCHEDULE), \
                 patch.object(adapter_module, "is_demo_mode", return_value=True):
                at24.run()
                at24.text_input[0].set_value("Science")
                at24.text_input[1].set_value("Physics")
                sched_btn_24 = next(
                    (b for b in at24.button if b.label == "Generate Study Plan"), None
                )
                assert sched_btn_24, "Generate Study Plan button not found"
                sched_btn_24.click()
                at24.run()
            assert not at24.exception
            captions = [c.value for c in at24.caption]
            assert any("schedule source" in c.lower() for c in captions), (
                f"Expected 'Schedule source' caption; got: {captions}"
            )
            ok("24. schedule source label shown after generation")
        except Exception as e:
            fail("24. schedule source label", str(e))

        # 25. No use_container_width in page source and 'Generate Study Plan' button present
        try:
            assert "use_container_width" not in page_src, (
                "use_container_width found in pages/study_planner.py"
            )
            assert "Generate Study Plan" in page_src, (
                "'Generate Study Plan' button label not in page source"
            )
            ok("25. no use_container_width + 'Generate Study Plan' button present")
        except Exception as e:
            fail("25. static checks", str(e))

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
