"""
_test_tutor.py — Automated checks for Sub-Task 6: pages/tutor.py

Checks
──────
 1.  Syntax parses cleanly (py_compile).
 2.  Import convention matches project (from learnmate_ai import ...).
 3.  render() function defined.
 4.  LEARNING_LEVELS imported from profile — not redefined locally.
 5.  llm_adapter.explain_topic() called in source.
 6.  llm_adapter.LLMError caught in source.
 7.  Demo mode badge and is_demo_mode() referenced in source.
 8.  AppTest — demo mode: badge shown on page load, no crash.
 9.  AppTest — empty subject: error shown, no explanation card.
10.  AppTest — empty topic: error shown.
11.  AppTest — LLMError: error message shown, no crash.
12.  AppTest — valid demo submit: explanation card (subheader) rendered.
13.  AppTest — session_state.learning_level pre-set to "Advanced": selectbox
     pre-selected to "Advanced".
14.  AppTest — level override: changed level is passed to explain_topic.
15.  Real adapter public API demo mode — supported topic returns sample-content label.
16.  Real adapter public API demo mode — unsupported topic returns generic-sample label.

Summary: PASSED / FAILED / SKIPPED counts printed at end.
"All checks passed" only when FAILED == 0 and SKIPPED == 0.
"""

from __future__ import annotations

import ast
import io
import os
import py_compile
import sys
import tempfile
from unittest.mock import patch

# Force UTF-8 output on Windows so box-drawing chars and arrows don't crash.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TUTOR_PATH = "learnmate_ai/pages/tutor.py"

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


# ════════════════════════════════════════════════════════════════════════════ #
# 1. Syntax (py_compile)                                                       #
# ════════════════════════════════════════════════════════════════════════════ #
try:
    py_compile.compile(TUTOR_PATH, doraise=True)
    ok("1. syntax: py_compile clean")
except py_compile.PyCompileError as e:
    fail("1. syntax", str(e))

# ── Load source for static checks ────────────────────────────────────────────
try:
    with open(TUTOR_PATH, "r", encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src)
    _src_ok = True
except Exception as e:
    fail("source-load", f"Cannot read/parse {TUTOR_PATH}: {e}")
    _src_ok = False

# ════════════════════════════════════════════════════════════════════════════ #
# 2–7. Static source checks                                                    #
# ════════════════════════════════════════════════════════════════════════════ #
if _src_ok:
    # 2. Import convention
    if "from learnmate_ai import llm_adapter" in src:
        ok("2. import convention: 'from learnmate_ai import llm_adapter'")
    else:
        fail("2. import convention", "Expected 'from learnmate_ai import llm_adapter'")

    # 3. render() defined
    if any(isinstance(n, ast.FunctionDef) and n.name == "render" for n in ast.walk(tree)):
        ok("3. render() function defined")
    else:
        fail("3. render()", "render() not found")

    # 4. LEARNING_LEVELS imported from profile, not redefined
    if "from learnmate_ai.pages.profile import LEARNING_LEVELS" in src:
        redef = any(
            isinstance(n, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(t, ast.Name) and t.id == "LEARNING_LEVELS"
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
            )
            for n in ast.walk(tree)
        )
        if redef:
            fail("4. LEARNING_LEVELS", "Re-defined locally — should be imported only")
        else:
            ok("4. LEARNING_LEVELS imported from profile, not redefined")
    else:
        fail("4. LEARNING_LEVELS", "Not imported from learnmate_ai.pages.profile")

    # 5. explain_topic called
    if "llm_adapter.explain_topic(" in src:
        ok("5. llm_adapter.explain_topic() called")
    else:
        fail("5. explain_topic", "llm_adapter.explain_topic() not found")

    # 6. LLMError caught
    if "llm_adapter.LLMError" in src:
        ok("6. llm_adapter.LLMError referenced (caught)")
    else:
        fail("6. LLMError", "llm_adapter.LLMError not referenced")

    # 7. Demo mode badge
    if "Demo Mode" in src and "is_demo_mode" in src:
        ok("7. demo mode badge and is_demo_mode() referenced")
    else:
        fail("7. demo badge", "Demo Mode badge or is_demo_mode() missing")
else:
    for n in range(2, 8):
        skip(f"{n}. static check", "source load failed")

# ════════════════════════════════════════════════════════════════════════════ #
# 15–16. Real adapter public API — demo mode                                  #
# (no Streamlit runtime needed; patches is_demo_mode so no API key required)  #
# ════════════════════════════════════════════════════════════════════════════ #
try:
    import learnmate_ai.llm_adapter as la
    _la_ok = True
except Exception as e:
    fail("adapter-import", str(e))
    _la_ok = False

if _la_ok:
    # 15. Supported topic via public API
    try:
        with patch.object(la, "is_demo_mode", return_value=True):
            result_supported = la.explain_topic("Mathematics", "Algebra", "Beginner")
        assert "Demo Mode — Sample Content" in result_supported, (
            f"Expected 'Demo Mode — Sample Content' header; got:\n{result_supported[:200]}"
        )
        assert "Algebra" in result_supported
        ok("15. real adapter public API (demo) — supported topic returns sample-content label")
    except Exception as e:
        fail("15. real adapter public API — supported topic", str(e))

    # 16. Unsupported topic via public API
    try:
        with patch.object(la, "is_demo_mode", return_value=True):
            result_unknown = la.explain_topic("FakeSubject", "QuantumFoam", "Beginner")
        assert "Demo Mode — Generic Sample" in result_unknown, (
            f"Expected 'Demo Mode — Generic Sample' header; got:\n{result_unknown[:200]}"
        )
        assert "QuantumFoam" in result_unknown
        ok("16. real adapter public API (demo) — unsupported topic returns generic-sample label")
    except Exception as e:
        fail("16. real adapter public API — unsupported topic", str(e))
else:
    skip("15. real adapter public API — supported topic", "adapter import failed")
    skip("16. real adapter public API — unsupported topic", "adapter import failed")

# ════════════════════════════════════════════════════════════════════════════ #
# 8–14. AppTest UI checks                                                      #
# ════════════════════════════════════════════════════════════════════════════ #
try:
    from streamlit.testing.v1 import AppTest
    _apptest_ok = True
except ImportError:
    _apptest_ok = False

if not _apptest_ok:
    for n in range(8, 15):
        skip(f"{n}. AppTest check", "streamlit.testing.v1 not available")
elif not _la_ok:
    for n in range(8, 15):
        skip(f"{n}. AppTest check", "adapter import failed")
else:
    # Build a one-use shim file so AppTest has a runnable script path.
    shim_src = """\
import sys, os
sys.path.insert(0, os.path.abspath('.'))
from learnmate_ai.pages.tutor import render
render()
"""
    shim_fd, shim_path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(shim_fd, "w", encoding="utf-8") as fh:
            fh.write(shim_src)

        # ── 8. Demo mode badge shown on page load ─────────────────────────
        try:
            with patch.object(la, "is_demo_mode", return_value=True):
                at8 = AppTest.from_file(shim_path)
                at8.run()
            assert not at8.exception, f"Exception: {at8.exception}"
            warnings = [w.value for w in at8.warning]
            assert any("Demo Mode" in w for w in warnings), (
                f"Badge not shown; warnings: {warnings}"
            )
            ok("8. AppTest — demo mode badge shown on page load")
        except Exception as e:
            fail("8. AppTest — demo mode badge", str(e))

        # ── 9. Empty subject → error, no explanation card ─────────────────
        try:
            with patch.object(la, "is_demo_mode", return_value=True):
                at9 = AppTest.from_file(shim_path)
                at9.run()
                at9.text_input[0].set_value("")
                at9.text_input[1].set_value("Algebra")
                at9.button[0].click()
                at9.run()
            assert not at9.exception, f"Exception: {at9.exception}"
            assert at9.error, "Expected error message for empty subject"
            subheaders = [s.value for s in at9.subheader]
            assert not any("📖" in s for s in subheaders), (
                f"Explanation card shown for empty subject: {subheaders}"
            )
            ok("9. AppTest — empty subject → error, no explanation card")
        except Exception as e:
            fail("9. AppTest — empty subject", str(e))

        # ── 10. Empty topic → error ───────────────────────────────────────
        try:
            with patch.object(la, "is_demo_mode", return_value=True):
                at10 = AppTest.from_file(shim_path)
                at10.run()
                at10.text_input[0].set_value("Mathematics")
                at10.text_input[1].set_value("")
                at10.button[0].click()
                at10.run()
            assert not at10.exception, f"Exception: {at10.exception}"
            assert at10.error, "Expected error message for empty topic"
            ok("10. AppTest — empty topic → error shown")
        except Exception as e:
            fail("10. AppTest — empty topic", str(e))

        # ── 11. LLMError → error message, no crash ────────────────────────
        try:
            with patch.object(la, "is_demo_mode", return_value=False), \
                 patch.object(la, "explain_topic", side_effect=la.LLMError("timeout")):
                at11 = AppTest.from_file(shim_path)
                at11.run()
                at11.text_input[0].set_value("Mathematics")
                at11.text_input[1].set_value("Algebra")
                at11.button[0].click()
                at11.run()
            assert not at11.exception, f"App crashed: {at11.exception}"
            assert at11.error, "Expected error message for LLMError"
            ok("11. AppTest — LLMError → error message shown, no crash")
        except Exception as e:
            fail("11. AppTest — LLMError", str(e))

        # ── 12. Valid demo submit → explanation subheader rendered ─────────
        try:
            fake_expl = "**Algebra** is the study of variables and equations."
            with patch.object(la, "is_demo_mode", return_value=True), \
                 patch.object(la, "explain_topic", return_value=fake_expl):
                at12 = AppTest.from_file(shim_path)
                at12.run()
                at12.text_input[0].set_value("Mathematics")
                at12.text_input[1].set_value("Algebra")
                at12.button[0].click()
                at12.run()
            assert not at12.exception, f"App crashed: {at12.exception}"
            assert not at12.error, f"Unexpected errors: {[e.value for e in at12.error]}"
            subheaders = [s.value for s in at12.subheader]
            assert any("Algebra" in s for s in subheaders), (
                f"Explanation subheader not found; subheaders: {subheaders}"
            )
            ok("12. AppTest — valid demo submit → explanation card rendered")
        except Exception as e:
            fail("12. AppTest — valid submit", str(e))

        # ── 13. session_state pre-set → selectbox pre-selected ────────────
        try:
            with patch.object(la, "is_demo_mode", return_value=True):
                at13 = AppTest.from_file(shim_path)
                at13.session_state["learning_level"] = "Advanced"
                at13.run()
            assert not at13.exception, f"Exception: {at13.exception}"
            sb13 = at13.selectbox[0]
            assert sb13.value == "Advanced", (
                f"Expected 'Advanced', got '{sb13.value}'"
            )
            ok("13. AppTest — session_state.learning_level='Advanced' → selectbox pre-selected to 'Advanced'")
        except Exception as e:
            fail("13. AppTest — selectbox pre-selection", str(e))

        # ── 14. Level override → correct level passed to explain_topic ────
        try:
            captured: list[tuple[str, str, str]] = []

            def _fake_explain(subject: str, topic: str, level: str) -> str:
                captured.append((subject, topic, level))
                return f"Explanation at {level} level."

            with patch.object(la, "is_demo_mode", return_value=False), \
                 patch.object(la, "explain_topic", side_effect=_fake_explain):
                at14 = AppTest.from_file(shim_path)
                at14.session_state["learning_level"] = "Beginner"
                at14.run()
                at14.text_input[0].set_value("Science")
                at14.text_input[1].set_value("Physics")
                at14.selectbox[0].set_value("Advanced")   # override
                at14.button[0].click()
                at14.run()
            assert not at14.exception, f"App crashed: {at14.exception}"
            assert len(captured) == 1, f"explain_topic called {len(captured)} times"
            assert captured[0][2] == "Advanced", (
                f"Expected level='Advanced', got '{captured[0][2]}'"
            )
            ok("14. AppTest — level override: 'Advanced' passed to explain_topic")
        except Exception as e:
            fail("14. AppTest — level override", str(e))

    finally:
        # Always clean up the shim, even if a test assertion raised.
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
