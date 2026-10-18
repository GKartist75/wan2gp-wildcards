"""Unit tests for the plugin's testable helpers.

create_ui() itself needs a running Gradio app; everything that does real work
lives at module level so it can be tested here without a browser.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import expander  # noqa: E402
import plugin  # noqa: E402


@pytest.fixture
def wc(tmp_path, monkeypatch):
    """A private wildcards directory wired into the plugin + expander."""
    root = tmp_path / "wildcards"
    root.mkdir()
    monkeypatch.setattr(expander, "WILDCARDS_DIR", str(root))
    expander.invalidate_cache()
    plugin.invalidate_file_list()
    yield root
    monkeypatch.undo()
    expander.invalidate_cache()
    plugin.invalidate_file_list()


# ── filename validation (findings: sanitize + reserved metadata) ───────────

def test_validate_appends_txt():
    assert plugin._validate_wc_target("mytheme/sunset") == ("mytheme/sunset.txt", "")
    assert plugin._validate_wc_target("already.txt") == ("already.txt", "")


def test_validate_rejects_absolute_and_traversal():
    for bad in ("/etc/passwd", "C:/Windows/x", "../escape", "a/../../b", "", "   "):
        safe, error = plugin._validate_wc_target(bad)
        assert safe is None, f"{bad!r} should be rejected"
        assert error


def test_validate_rejects_metadata_names():
    for bad in ("__stats__.json", "__favorites__.json", "sub/__index__"):
        safe, error = plugin._validate_wc_target(bad)
        assert safe is None
        assert "reserved" in error


def test_validate_rejects_windows_reserved_names():
    for bad in ("CON", "nul.txt", "sub/com1"):
        safe, _ = plugin._validate_wc_target(bad)
        assert safe is None, f"{bad!r} should be rejected"


# ── create / write / delete / rename ───────────────────────────────────────

def test_write_file_creates_parent_directories(wc):
    message = plugin._wc_write_file("deep/nested/pool", "a\nb\n")
    assert "Saved deep/nested/pool.txt" in message
    assert (wc / "deep" / "nested" / "pool.txt").read_text(encoding="utf-8") == "a\nb\n"


def test_create_only_refuses_to_overwrite(wc):
    (wc / "keep.txt").write_text("original\n", encoding="utf-8")
    message = plugin._wc_write_file("keep", "REPLACED", create_only=True)
    assert "already exists" in message
    assert (wc / "keep.txt").read_text(encoding="utf-8") == "original\n"


def test_save_overwrites_when_not_create_only(wc):
    (wc / "keep.txt").write_text("original\n", encoding="utf-8")
    assert "Saved" in plugin._wc_write_file("keep", "new\n")
    assert (wc / "keep.txt").read_text(encoding="utf-8") == "new\n"


def test_delete_missing_file_is_reported(wc):
    assert "File not found" in plugin._wc_delete_file("ghost.txt")


def test_delete_removes_file(wc):
    (wc / "gone.txt").write_text("x\n", encoding="utf-8")
    assert "Deleted" in plugin._wc_delete_file("gone.txt")
    assert not (wc / "gone.txt").exists()


def test_delete_refuses_metadata(wc):
    (wc / "__index__.txt").write_text("catalog\n", encoding="utf-8")
    assert "reserved" in plugin._wc_delete_file("__index__.txt")
    assert (wc / "__index__.txt").exists()


def test_rename_succeeds_and_appends_txt(wc):
    (wc / "old.txt").write_text("value\n", encoding="utf-8")
    message = plugin._wc_rename_file("old.txt", "new/place")
    assert message == "Renamed old.txt -> new/place.txt"
    assert (wc / "new" / "place.txt").read_text(encoding="utf-8") == "value\n"
    assert not (wc / "old.txt").exists()


def test_rename_refuses_existing_target(wc):
    (wc / "a.txt").write_text("a\n", encoding="utf-8")
    (wc / "b.txt").write_text("b\n", encoding="utf-8")
    message = plugin._wc_rename_file("a.txt", "b.txt")
    assert "already exists" in message
    assert (wc / "a.txt").read_text(encoding="utf-8") == "a\n"


def test_rename_refuses_metadata_target(wc):
    (wc / "a.txt").write_text("a\n", encoding="utf-8")
    assert "reserved" in plugin._wc_rename_file("a.txt", "__stats__.json")
    assert (wc / "a.txt").exists()


def test_rename_rejects_traversal(wc):
    (wc / "a.txt").write_text("a\n", encoding="utf-8")
    assert plugin._wc_rename_file("a.txt", "../escape.txt")
    assert (wc / "a.txt").exists()


# ── file listing excludes metadata ─────────────────────────────────────────

def test_list_wc_files_skips_metadata(wc):
    (wc / "keep.txt").write_text("x\n", encoding="utf-8")
    (wc / "__index__.txt").write_text("catalog\n", encoding="utf-8")
    meta_dir = wc / "__secrets__"
    meta_dir.mkdir()
    (meta_dir / "hidden.txt").write_text("x\n", encoding="utf-8")

    plugin.invalidate_file_list()
    files = plugin._list_wc_files()
    assert files == ["keep.txt"]


def test_get_wildcard_keys_includes_pools_files_and_aliases(wc):
    (wc / "camera").mkdir()
    (wc / "camera" / "shot.txt").write_text("close-up\n", encoding="utf-8")
    (wc / "camera" / "deep").mkdir()
    (wc / "camera" / "deep" / "lens.txt").write_text("85mm\n", encoding="utf-8")
    (wc / "__index__.txt").write_text("catalog\n", encoding="utf-8")

    keys = plugin._get_wildcard_keys()
    assert "__camera__" in keys          # directory pool
    assert "__camera/deep__" in keys     # nested directory pool
    assert "__camera/shot__" in keys     # file
    assert "__camera/deep/lens__" in keys
    assert "__hair-color__" in keys      # legacy alias
    assert not any("__index__" in k for k in keys)


# ── chip preview / shuffle (finding: Shuffle Values did nothing) ───────────

def _make_pool(wc, name="chip.txt", count=40):
    (wc / name).write_text("\n".join(f"value {i}" for i in range(count)) + "\n", encoding="utf-8")


def test_chips_are_deterministic_for_a_given_seed(wc):
    _make_pool(wc)
    assert plugin._render_chips_html("chip.txt", seed=7) == plugin._render_chips_html("chip.txt", seed=7)


def test_chips_change_with_a_different_seed(wc):
    _make_pool(wc)
    assert plugin._render_chips_html("chip.txt", seed=1) != plugin._render_chips_html("chip.txt", seed=2)


def test_chips_reshuffle_when_no_seed_is_given(wc):
    _make_pool(wc)
    renders = {plugin._render_chips_html("chip.txt") for _ in range(5)}
    assert len(renders) > 1, "default (seed=None) must reshuffle, else Shuffle is a no-op"


def test_chips_handle_missing_and_empty_files(wc):
    assert "File not found" in plugin._render_chips_html("nope.txt")
    (wc / "empty.txt").write_text("# comment only\n\n", encoding="utf-8")
    assert "Empty file" in plugin._render_chips_html("empty.txt")
    assert "Select a category" in plugin._render_chips_html("")


# ── stats context manager ──────────────────────────────────────────────────

def test_stats_context_restores_value_after_exception():
    plugin._tls_stats_track.value = True
    with pytest.raises(RuntimeError):
        with plugin.stats_context(False):
            assert plugin._tls_stats_track.value is False
            raise RuntimeError("boom")
    assert plugin._tls_stats_track.value is True


def test_stats_context_restores_nested_values():
    plugin._tls_stats_track.value = True
    with plugin.stats_context(False):
        with plugin.stats_context(True):
            assert plugin._tls_stats_track.value is True
        assert plugin._tls_stats_track.value is False
    assert plugin._tls_stats_track.value is True
