"""Run every backend test module in its own subprocess.

Why: each test module sets ``LOCKET_DB`` and other env vars at import time and
builds its Flask app once. Running them in a single pytest process leaks state
between files (DB rows, provider API key, admin config), so ``pytest tests/``
is not a valid acceptance signal. This runner keeps every module isolated and
returns a non-zero exit code if any module fails.

Usage (from ``backend``)::

    ../.venv/Scripts/python.exe run_tests_isolated.py
    ../.venv/Scripts/python.exe run_tests_isolated.py --reverse tests/test_lunakey_races.py

``--reverse`` runs a module's unittest tests in reverse order to prove the
suite does not depend on execution order.
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import os
import subprocess
import sys
import unittest


def _reverse_suite(suite):
    """Recursively reverse the order of tests inside a unittest suite."""
    items = list(suite)
    reversed_items = []
    for item in reversed(items):
        if isinstance(item, unittest.TestSuite):
            reversed_items.append(_reverse_suite(item))
        else:
            reversed_items.append(item)
    return unittest.TestSuite(reversed_items)


def _run_module_reversed(path: str) -> int:
    name = "reversed_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    result = unittest.TextTestRunner(verbosity=1).run(_reverse_suite(suite))
    return 0 if result.wasSuccessful() else 1


def _run_module_subprocess(path: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", path, "-q", "--tb=short"],
        capture_output=True,
        text=True,
    )
    tail = (proc.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else "(no output)"
    return proc.returncode, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reverse", action="append", default=[],
                        help="module path to additionally run with reversed test order")
    parser.add_argument("--tests-dir", default="tests")
    args = parser.parse_args()

    if not os.path.isdir(args.tests_dir):
        print(f"tests dir not found: {args.tests_dir}", file=sys.stderr)
        return 2

    files = sorted(glob.glob(os.path.join(args.tests_dir, "test_*.py")))
    failures = []
    for path in files:
        code, summary = _run_module_subprocess(path)
        status = "PASS" if code == 0 else "FAIL"
        print(f"[{status}] {os.path.basename(path):<48} {summary}")
        if code != 0:
            failures.append(path)

    for path in args.reverse:
        code = _run_module_reversed(path)
        status = "PASS" if code == 0 else "FAIL"
        print(f"[{status}] {os.path.basename(path)} (reversed order)")
        if code != 0:
            failures.append(f"{path} (reversed)")

    print("-" * 72)
    if failures:
        print(f"{len(failures)} module(s) failed:")
        for path in failures:
            print(f"  - {path}")
        return 1
    print(f"All {len(files)} module(s) passed in isolation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
