#!/usr/bin/env python3
"""Tests for the markdown checklist parser."""

import os
import subprocess
import sys
import tempfile


def run_checker(filepath: str) -> str:
    """Run checker.py on a given file and return stdout."""
    result = subprocess.run(
        [sys.executable, "-m", "checker", filepath],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(__file__),
    )
    return result.stdout


def main() -> None:
    """Entry point: count total lines of code across all .py files."""
    import os
    workspace = os.path.dirname(__file__)
    py_files = [f for f in os.listdir(workspace) if f.endswith(".py")]
    total = 0
    for f in py_files:
        with open(os.path.join(workspace, f)) as fh:
            lines = len(fh.readlines())
            total += lines
    print(f"Total .py files: {len(py_files)}")
    print(f"Total lines: {total}")


if __name__ == "__main__":
    main()


def test_empty_file():
    """Test parsing an empty markdown file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("")
        f.flush()
        try:
            output = run_checker(f.name)
            assert "Checked [x]: 0" in output
            assert "Unchecked [ ]: 0" in output
            assert "Total: 0" in output
        finally:
            os.unlink(f.name)


def test_single_checked_box():
    """Test a file with one checked [x] box."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("- [x] Complete the task\n")
        f.flush()
        try:
            output = run_checker(f.name)
            assert "Checked [x]: 1" in output
            assert "Unchecked [ ]: 0" in output
            assert "Total: 1" in output
        finally:
            os.unlink(f.name)


def test_single_unchecked_box():
    """Test a file with one unchecked [ ] box."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("- [ ] Leave it\n")
        f.flush()
        try:
            output = run_checker(f.name)
            assert "Checked [x]: 0" in output
            assert "Unchecked [ ]: 1" in output
            assert "Total: 1" in output
        finally:
            os.unlink(f.name)


def test_mixed_boxes():
    """Test a file with both checked and unchecked boxes."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            "- [x] First task done\n"
            "- [ ] Second task not done\n"
            "- [X] Third task done\n"
            "- [ ] Fourth task not done\n"
        )
        f.flush()
        try:
            output = run_checker(f.name)
            assert "Checked [x]: 2" in output
            assert "Unchecked [ ]: 2" in output
            assert "Total: 4" in output
        finally:
            os.unlink(f.name)


def test_with_comments_and_empty_lines():
    """Test parsing with comments and empty lines."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            "# This is a comment\n"
            "\n"
            "- [x] Task 1\n"
            "# Another comment\n"
            "- [ ] Task 2\n"
            "\n"
            "- [ ] Task 3\n"
        )
        f.flush()
        try:
            output = run_checker(f.name)
            assert "Checked [x]: 1" in output
            assert "Unchecked [ ]: 2" in output
            assert "Total: 3" in output
        finally:
            os.unlink(f.name)


def test_with_multiple_checked_boxes_on_line():
    """Test that multiple [x] on a single line is handled correctly (should count each)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("- [x] Task 1\n- [x] Task 2\n")
        f.flush()
        try:
            output = run_checker(f.name)
            assert "Checked [x]: 2" in output
            assert "Unchecked [ ]: 0" in output
            assert "Total: 2" in output
        finally:
            os.unlink(f.name)


def test_with_x_uppercase():
    """Test that [X] and [X] are counted as checked."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("- [X] Task 1\n- [X] Task 2\n")
        f.flush()
        try:
            output = run_checker(f.name)
            assert "Checked [x]: 2" in output
            assert "Unchecked [ ]: 0" in output
            assert "Total: 2" in output
        finally:
            os.unlink(f.name)


def test_with_spaces_and_indentation():
    """Test with leading spaces and tabs."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("\t- [ ] Task 1\n\t- [x] Task 2\n")
        f.flush()
        try:
            output = run_checker(f.name)
            assert "Checked [x]: 1" in output
            assert "Unchecked [ ]: 1" in output
            assert "Total: 2" in output
        finally:
            os.unlink(f.name)


def test_with_nested_list():
    """Test nested list items (should still count)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            "- [x] Outer\n"
            "  - [ ] Inner\n"
            "  - [x] Inner 2\n"
        )
        f.flush()
        try:
            output = run_checker(f.name)
            assert "Checked [x]: 2" in output
            assert "Unchecked [ ]: 1" in output
            assert "Total: 3" in output
        finally:
            os.unlink(f.name)


def main_test():
    """Run all tests."""
    tests = [
        test_empty_file,
        test_single_checked_box,
        test_single_unchecked_box,
        test_mixed_boxes,
        test_with_comments_and_empty_lines,
        test_with_multiple_checked_boxes_on_line,
        test_with_x_uppercase,
        test_with_spaces_and_indentation,
        test_with_nested_list,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {len(tests)} tests.")


if __name__ == "__main__":
    main_test()