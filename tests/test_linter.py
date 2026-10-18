"""Unit tests for the offline linter (prompt + collection reports)."""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import expander  # noqa: E402
import linter  # noqa: E402


def test_lint_text_reports_missing_reference():
    report = linter.lint_text("a __definitely/not/here__ shot")
    assert report["ok"] is False
    assert report["missing"] == ["definitely/not/here"]
    assert "FAIL" in linter.format_text_report(report)


def test_lint_text_accepts_real_references():
    report = linter.lint_text("A __camera/shot__ of __color/named__")
    assert report["missing"] == []
    assert report["ok"] is True
    assert report["references"] == ["camera/shot", "color/named"]
    assert "OK" in linter.format_text_report(report)


def test_lint_text_understands_legacy_alias_names():
    # `hair-color` is a legacy alias and `camera_shot` resolves through the
    # underscore->slash fallback, so neither may be reported as missing.
    report = linter.lint_text("__camera_shot__ of someone with __hair-color__")
    assert report["missing"] == []


def test_lint_text_detects_unset_variable():
    report = linter.lint_text("__$nobody__ walks by")
    assert report["unset_variables"] == ["nobody"]
    assert "WARN" in linter.format_text_report(report)


def test_lint_text_does_not_flag_assigned_variable():
    report = linter.lint_text("__$who:color/named__ and __$who__ again")
    assert report["assigned_variables"] == ["who"]
    assert report["unset_variables"] == []


def test_lint_text_reports_missing_capture_file():
    report = linter.lint_text("__$x:no/such/pool__")
    assert report["missing_captures"] == ["no/such/pool"]
    assert report["ok"] is False


def test_lint_text_counts_variants():
    report = linter.lint_text("{red|green|blue} and {solo}")
    assert report["variants"] == 1  # {solo} has no |, so it is not a random variant


def test_lint_text_handles_plain_text():
    report = linter.lint_text("just a normal prompt")
    assert report["references"] == []
    assert "No __wildcard__" in linter.format_text_report(report)


def test_lint_files_finds_broken_nested_reference(tmp_path, monkeypatch):
    wc = tmp_path / "wildcards"
    wc.mkdir()
    (wc / "good.txt").write_text("one\ntwo\n", encoding="utf-8")
    (wc / "bad.txt").write_text("a __good__ value\nand a __missing/thing__ here\n", encoding="utf-8")

    monkeypatch.setattr(expander, "WILDCARDS_DIR", str(wc))
    expander.invalidate_cache()
    try:
        report = linter.lint_files(expander.iter_wildcard_files(str(wc)), str(wc))
        assert report["broken_total"] == 1
        assert report["broken"][0]["name"] == "missing/thing"
        assert report["broken"][0]["file"] == "bad.txt"
        assert report["broken"][0]["line"] == 2
    finally:
        monkeypatch.undo()
        expander.invalidate_cache()


def test_lint_files_detects_whitespace_duplicates(tmp_path, monkeypatch):
    wc = tmp_path / "wildcards"
    wc.mkdir()
    (wc / "dupes.txt").write_text("sunset\nsunset \n  sunset\n", encoding="utf-8")

    monkeypatch.setattr(expander, "WILDCARDS_DIR", str(wc))
    expander.invalidate_cache()
    try:
        report = linter.lint_files(expander.iter_wildcard_files(str(wc)), str(wc))
        assert report["duplicate_total"] == 1
        assert report["duplicates"][0]["count"] == 3
        assert report["duplicates"][0]["line"] == 1
    finally:
        monkeypatch.undo()
        expander.invalidate_cache()


def test_lint_files_flags_empty_file(tmp_path, monkeypatch):
    wc = tmp_path / "wildcards"
    wc.mkdir()
    (wc / "empty.txt").write_text("# only a comment\n\n", encoding="utf-8")

    monkeypatch.setattr(expander, "WILDCARDS_DIR", str(wc))
    expander.invalidate_cache()
    try:
        report = linter.lint_files(expander.iter_wildcard_files(str(wc)), str(wc))
        assert report["empty_files"] == ["empty.txt"]
        assert report["ok"] is False
    finally:
        monkeypatch.undo()
        expander.invalidate_cache()


def test_lint_collection_ignores_metadata_files(tmp_path, monkeypatch):
    wc = tmp_path / "wildcards"
    wc.mkdir()
    (wc / "__index__.txt").write_text("# catalog\n__whatever__\n", encoding="utf-8")
    (wc / "real.txt").write_text("fine\n", encoding="utf-8")

    monkeypatch.setattr(expander, "WILDCARDS_DIR", str(wc))
    expander.invalidate_cache()
    try:
        report = linter.lint_collection(str(wc))
        # __index__.txt is metadata and must not be scanned as a pool.
        assert report["files"] == 1
        assert report["broken_total"] == 0
    finally:
        monkeypatch.undo()
        expander.invalidate_cache()
