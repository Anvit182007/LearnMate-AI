"""
_test_study_planner.py — Automated checks for Sub-Task 8: pages/study_planner.py

Checks
──────
Static / compile
  1.  py_compile clean: pages/study_planner.py
  2.  render() defined
  3.  database.get_topic_accuracy_summary called
  4.  study_planner.build_study_plan called
  5.  quiz_engine.detect_weak_topics called
  6.  Demo mode badge referenced
  7.  _WEAK_THRESHOLD == 0.60

AppTest UI (original 18)
  8.  Profile guard: no profile -> warning shown, table not rendered
  9.  Empty quiz history -> encouraging info message, no crash
 10.  Weak topics present -> warning banner shown
 11.  All topics strong -> success banner shown
 12.  Demo mode badge shown in st.info
 13.  Accuracy table rendered (st.dataframe present)
 14.  Study plan markdown rendered
 15.  Refresh Plan button clears cached plan and regenerates
 16.  LLMError during build_study_plan -> error message, no crash, no raw detail
 17.  Plan source label: "rule-based" in demo mode
 18.  Plan source label: "AI-generated" in live mode (LLM succeeds)

AppTest UI (new checks)
 19.  Live mode LLM success -> source label is "AI-generated"
 20.  Live mode LLM fallback -> source label contains "fallback" or "not AI"
 21.  Source label never shows "AI-generated" for rule-based fallback
 22.  Cache invalidated when quiz history grows (new row -> plan regenerated)
 23.  width="stretch" used in st.dataframe (not use_container_width)
 24.  Error message does not expose raw exception detail in UI
"""

from __future__ import annotations

import io
import os
import py_compile
import sys
import tempfile
from pathlib import Path
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


PAGE_PATH = "learnmate_ai/pages/study_planner.py"

# ════════════════════════════════════════════════════════════════════════════ #
# 1. py_compile                                                                #
# ════════════════════════════════════════════════════════════════════════════ #
try:
    py_compile.compile(PAGE_PATH, doraise=True)
    ok("1. py_compile clean: pages/study_planner.py")
except py_compile.PyCompileError as e:
    fail("1. py_compile", str(e))

# Load source
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
        ("3", "database.get_topic_accuracy_summary"),
        ("4", "study_planner.build_study_plan"),
        ("5", "quiz_engine.detect_weak_topics"),
        ("6", "is_demo_mode"),
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
# AppTest checks 8–18                                                          #
# ════════════════════════════════════════════════════════════════════════════ #
try:
    from streamlit.testing.v1 import AppTest
    _apptest_ok = True
except ImportError:
    _apptest_ok = False

try:
    import learnmate_ai.database as db_module
    import learnmate_ai.llm_adapter as la
    import learnmate_ai.study_planner as sp_module
    _imports_ok = True
except Exception as e:
    fail("imports", str(e))
    _imports_ok = False

if not _apptest_ok:
    for n in range(8, 19):
        skip(f"{n}. AppTest", "streamlit.testing.v1 not available")
elif not _imports_ok:
    for n in range(8, 19):
        skip(f"{n}. AppTest", "module import failed")
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

    # ── Common test DataFrames ────────────────────────────────────────────────
    EMPTY_DF = pd.DataFrame(columns=["subject", "topic", "attempts", "avg_accuracy"])

    WEAK_DF = pd.DataFrame({
        "subject":      ["Mathematics", "Science"],
        "topic":        ["Algebra",     "Physics"],
        "attempts":     [3,             2],
        "avg_accuracy": [0.40,          0.55],
    })

    STRONG_DF = pd.DataFrame({
        "subject":      ["Mathematics"],
        "topic":        ["Calculus"],
        "attempts":     [5],
        "avg_accuracy": [0.92],
    })

    SAMPLE_PLAN = "## Study Plan\n\n- Revise Algebra\n- Revise Physics\n"

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
            with patch.object(la, "is_demo_mode", return_value=True):
                at8.run()
            assert not at8.exception
            warnings = [w.value for w in at8.warning]
            assert any("Profile" in w for w in warnings), f"warnings: {warnings}"
            assert not at8.dataframe, "No dataframe expected without profile"
            ok("8. profile guard: warning shown, table not rendered")
        except Exception as e:
            fail("8. profile guard", str(e))

        # 9. Empty history → info message
        try:
            at9 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=EMPTY_DF):
                at9.run()
            assert not at9.exception, f"Exception: {at9.exception}"
            infos = [i.value for i in at9.info]
            assert any("quiz" in i.lower() for i in infos), f"infos: {infos}"
            assert not at9.dataframe, "No dataframe for empty history"
            ok("9. empty history → info message, no crash")
        except Exception as e:
            fail("9. empty history", str(e))

        # 10. Weak topics → warning banner
        try:
            at10 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=WEAK_DF), \
                 patch.object(sp_module, "build_study_plan", return_value=SAMPLE_PLAN):
                at10.run()
            assert not at10.exception, f"Exception: {at10.exception}"
            warnings = [w.value for w in at10.warning]
            assert any("attention" in w.lower() or "need" in w.lower() for w in warnings), (
                f"Expected weak-topic warning; got: {warnings}"
            )
            ok("10. weak topics → warning banner shown")
        except Exception as e:
            fail("10. weak topics warning", str(e))

        # 11. All strong → success banner
        try:
            at11 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=STRONG_DF), \
                 patch.object(sp_module, "build_study_plan", return_value="No weak topics detected — great work! Keep taking quizzes to track your progress."):
                at11.run()
            assert not at11.exception
            successes = [s.value for s in at11.success]
            assert any("60%" in s or "above" in s.lower() for s in successes), (
                f"Expected all-strong success; got successes: {successes}"
            )
            ok("11. all topics strong → success banner shown")
        except Exception as e:
            fail("11. all strong success", str(e))

        # 12. Demo mode badge (st.info)
        try:
            at12 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=WEAK_DF), \
                 patch.object(sp_module, "build_study_plan", return_value=SAMPLE_PLAN):
                at12.run()
            infos = [i.value for i in at12.info]
            assert any("Demo Mode" in i for i in infos), f"infos: {infos}"
            ok("12. demo mode badge shown in st.info")
        except Exception as e:
            fail("12. demo badge", str(e))

        # 13. Accuracy table rendered
        try:
            at13 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=WEAK_DF), \
                 patch.object(sp_module, "build_study_plan", return_value=SAMPLE_PLAN):
                at13.run()
            assert not at13.exception
            assert at13.dataframe, "Expected at least one st.dataframe"
            ok("13. accuracy table rendered (st.dataframe present)")
        except Exception as e:
            fail("13. accuracy table", str(e))

        # 14. Study plan markdown rendered
        try:
            at14 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=WEAK_DF), \
                 patch.object(sp_module, "build_study_plan", return_value=SAMPLE_PLAN):
                at14.run()
            markdowns = [m.value for m in at14.markdown]
            assert any("Study Plan" in m or "Algebra" in m for m in markdowns), (
                f"Study plan markdown not found; markdowns: {markdowns[:3]}"
            )
            ok("14. study plan markdown rendered")
        except Exception as e:
            fail("14. study plan markdown", str(e))

        # 15. Refresh Plan button clears and regenerates
        try:
            call_count = [0]
            def _counting_plan(*args, **kwargs):
                call_count[0] += 1
                return f"Plan generation #{call_count[0]}"

            at15 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=WEAK_DF), \
                 patch.object(sp_module, "build_study_plan", side_effect=_counting_plan):
                at15.run()   # first render → plan generated (count=1)
                at15.run()   # rerun without refresh → plan NOT regenerated (still count=1)
                refresh_btn = next((b for b in at15.button if "Refresh" in b.label), None)
                assert refresh_btn is not None, "Refresh Plan button not found"
                refresh_btn.click()
                at15.run()   # after refresh → plan regenerated (count=2)

            assert call_count[0] == 2, (
                f"Expected build_study_plan called 2 times, got {call_count[0]}"
            )
            ok("15. Refresh Plan button clears cache and regenerates plan")
        except Exception as e:
            fail("15. Refresh Plan button", str(e))

        # 16. LLMError -> error message, no crash, no raw detail
        try:
            raw_detail = "secret_api_key_in_error_xyz"
            at16 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=WEAK_DF), \
                 patch.object(sp_module, "build_study_plan",
                              side_effect=Exception(raw_detail)):
                at16.run()
            assert not at16.exception, f"App crashed: {at16.exception}"
            errors = [e.value for e in at16.error]
            assert any("study plan" in e.lower() or "generate" in e.lower() for e in errors), (
                f"Expected error message; got: {errors}"
            )
            # Raw exception detail must NOT appear in any UI element
            all_text = " ".join(
                [m.value for m in at16.markdown]
                + [e.value for e in at16.error]
                + [w.value for w in at16.warning]
                + [i.value for i in at16.info]
            )
            assert raw_detail not in all_text, (
                f"Raw exception detail leaked into UI: {raw_detail!r}"
            )
            ok("16. exception -> error message shown, no crash, no raw detail in UI")
        except Exception as e:
            fail("16. LLMError handling", str(e))

        # 17. Plan source label: "rule-based" in demo mode
        try:
            at17 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=WEAK_DF), \
                 patch.object(sp_module, "build_study_plan", return_value=SAMPLE_PLAN):
                at17.run()
            captions = [c.value for c in at17.caption]
            assert any("rule-based" in c.lower() or "demo" in c.lower() for c in captions), (
                f"Expected rule-based/demo source label; captions: {captions}"
            )
            ok("17. plan source label: 'rule-based' in demo mode")
        except Exception as e:
            fail("17. plan source label (demo)", str(e))

        # 18. Plan source label: "AI-generated" in live mode
        try:
            at18 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=False), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=WEAK_DF), \
                 patch.object(sp_module, "build_study_plan", return_value=SAMPLE_PLAN):
                at18.run()
            captions = [c.value for c in at18.caption]
            assert any("ai-generated" in c.lower() or "ai generated" in c.lower() for c in captions), (
                f"Expected AI-generated source label; captions: {captions}"
            )
            ok("18. plan source label: 'AI-generated' in live mode")
        except Exception as e:
            fail("18. plan source label (live)", str(e))

        # 19. Live mode LLM success -> source label is "AI-generated"
        # (same as check 18 but explicit about what _detect_plan_source does)
        try:
            at19 = _fresh()
            ai_plan = "## Weekly Study Schedule\n\nFocus on Algebra this week."
            with patch.object(la, "is_demo_mode", return_value=False), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=WEAK_DF), \
                 patch.object(sp_module, "build_study_plan", return_value=ai_plan):
                at19.run()
            captions = [c.value for c in at19.caption]
            assert any("ai-generated" in c.lower() for c in captions), (
                f"Expected 'AI-generated' label; captions: {captions}"
            )
            ok("19. live mode LLM success -> source label 'AI-generated'")
        except Exception as e:
            fail("19. live LLM success source label", str(e))

        # 20. Live mode LLM fallback -> source label contains "fallback" or "not AI"
        try:
            from learnmate_ai.pages.study_planner import _LLM_FALLBACK_MARKER
            fallback_plan = (
                f"> ⚠️ **Note:** {_LLM_FALLBACK_MARKER} "
                "A rule-based plan is shown below instead.\n\n"
                "## Rule-Based Plan\n\n- Revise Algebra"
            )
            at20 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=False), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=WEAK_DF), \
                 patch.object(sp_module, "build_study_plan", return_value=fallback_plan):
                at20.run()
            captions = [c.value for c in at20.caption]
            assert any("fallback" in c.lower() or "not ai-generated" in c.lower() for c in captions), (
                f"Expected 'fallback'/'not AI' label; captions: {captions}"
            )
            ok("20. live mode LLM fallback -> source label contains 'fallback' or 'not AI-generated'")
        except Exception as e:
            fail("20. live LLM fallback source label", str(e))

        # 21. Source label for fallback must say "fallback" or "not AI-generated",
        #     NOT purely "AI-generated based on your quiz history"
        try:
            from learnmate_ai.pages.study_planner import _detect_plan_source, _LLM_FALLBACK_MARKER
            fallback_text = (
                f"> ⚠️ **Note:** {_LLM_FALLBACK_MARKER} Rule-based plan follows.\n\n## Plan"
            )
            label = _detect_plan_source(fallback_text)
            # Must NOT return the plain AI-success label
            assert label != "AI-generated based on your quiz history", (
                f"Fallback plan must not be labelled as purely AI-generated; got: {label!r}"
            )
            # Must indicate fallback or non-AI origin
            assert "fallback" in label.lower() or "not ai-generated" in label.lower(), (
                f"Label should say 'fallback' or 'not AI-generated'; got: {label!r}"
            )
            ok("21. _detect_plan_source: fallback marker -> label indicates fallback, not AI-generated")
        except Exception as e:
            fail("21. _detect_plan_source fallback", str(e))

        # 22. Cache invalidated when quiz history grows
        try:
            call_count2 = [0]
            def _counting_plan2(*args, **kwargs):
                call_count2[0] += 1
                return f"Plan #{call_count2[0]}"

            BIGGER_DF = pd.DataFrame({
                "subject":      ["Mathematics", "Science", "History"],
                "topic":        ["Algebra",     "Physics", "WWI"],
                "attempts":     [3, 2, 1],
                "avg_accuracy": [0.40, 0.55, 0.35],
            })

            at22 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=WEAK_DF), \
                 patch.object(sp_module, "build_study_plan", side_effect=_counting_plan2):
                at22.run()   # first render with WEAK_DF (2 rows) -> count=1
                at22.run()   # rerun, same DF -> count stays 1

            # Simulate new quiz results (3 rows now)
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary", return_value=BIGGER_DF), \
                 patch.object(sp_module, "build_study_plan", side_effect=_counting_plan2):
                at22.run()   # cache key changes (3 rows != 2) -> count=2

            assert call_count2[0] == 2, (
                f"Expected 2 calls after history growth, got {call_count2[0]}"
            )
            ok("22. cache invalidated when quiz history grows (new row triggers regeneration)")
        except Exception as e:
            fail("22. cache invalidation on history growth", str(e))

        # 23. width="stretch" used (not use_container_width)
        try:
            with open("learnmate_ai/pages/study_planner.py", "r", encoding="utf-8") as fh:
                page_src = fh.read()
            assert 'width="stretch"' in page_src, \
                "Expected width='stretch' in st.dataframe call"
            assert "use_container_width" not in page_src, \
                "use_container_width should have been replaced by width='stretch'"
            ok('23. st.dataframe uses width="stretch" (not use_container_width)')
        except Exception as e:
            fail("23. width=stretch", str(e))

        # 24. Error message does not expose raw exception detail
        # (Covers database load failure path as well as plan generation failure)
        try:
            sentinel = "INTERNAL_DB_ERROR_DO_NOT_SHOW"
            at24 = _fresh()
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(db_module, "get_topic_accuracy_summary",
                              side_effect=Exception(sentinel)):
                at24.run()
            assert not at24.exception
            all_ui = " ".join(
                [m.value for m in at24.markdown]
                + [e.value for e in at24.error]
                + [w.value for w in at24.warning]
                + [i.value for i in at24.info]
            )
            assert sentinel not in all_ui, (
                f"Sentinel error detail leaked into UI"
            )
            ok("24. DB load error: raw exception detail not exposed in UI")
        except Exception as e:
            fail("24. DB error no raw detail", str(e))

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
