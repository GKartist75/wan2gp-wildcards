"""Unit tests for the wildcard expander.

These run against the real on-disk `wildcards/` collection (3017+ files),
so WILDCARDS_DIR is pointed at the repo's wildcards dir. No network needed.
"""
import os
import sys
import tempfile
import random

import pytest

# Make the plugin package importable when run from repo root or tests/.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import expander  # noqa: E402

# Point the expander at the real collection so alias/resolve tests are meaningful.
expander.set_wildcards_dir(os.path.join(REPO_ROOT, "wildcards"))


# ── determinism ────────────────────────────────────────────────────────────
def test_deterministic_with_seed():
    p = "A __camera/shot__ of __color/named__ standing in __environment/nature__"
    a = expander.expand_prompt(p, seed=12345)
    b = expander.expand_prompt(p, seed=12345)
    assert a == b
    assert "__" not in a  # fully expanded


def test_random_varies_without_seed():
    p = "__color/named__ __color/named__"
    outs = {expander.expand_prompt(p) for _ in range(20)}
    # very unlikely all identical unless the file has 1 line
    assert len(outs) > 1 or len(expander.load_wildcard_lines("color/named")) == 1


# ── wildcards + variants ─────────────────────────────────────────────────────
def test_simple_wildcard_expands():
    out = expander.expand_prompt("__color/named__", seed=1)
    assert out and "__" not in out


def test_variant_choice_expands():
    out = expander.expand_prompt("{a|b|c}", seed=1)
    assert out in ("a", "b", "c")


def test_nested_wildcard_in_file():
    # many wildcard files reference other wildcards; ensure no leakage of __x__
    out = expander.expand_prompt("__camera/shot__", seed=7)
    assert "__" not in out


# ── captured variables ──────────────────────────────────────────────────────
def test_capture_variable_reuse():
    out = expander.expand_prompt("__$a:color/named__ and __$a__", seed=3)
    first, _, second = out.partition(" and ")
    assert first == second
    assert out.count(first) == 2


def test_capture_literal_value():
    out = expander.expand_prompt("An __$food=apple__ pie with __$food__ slices", seed=1)
    assert out == "An apple pie with apple slices"


def test_unknown_variable_left_as_is():
    out = expander.expand_prompt("hello __$ghost__ world", seed=1)
    assert "__$ghost__" in out


def test_multiple_variables_independent(tmp_path, monkeypatch):
    # Use an isolated wildcard dir with single-line files so output is exact.
    (tmp_path / "a.txt").write_text("Alice\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("Bob\n", encoding="utf-8")
    expander.set_wildcards_dir(str(tmp_path))
    try:
        out = expander.expand_prompt(
            "__$a:a__ __$b:b__ __$a__ __$b__", seed=9
        )
    finally:
        expander.set_wildcards_dir(os.path.join(REPO_ROOT, "wildcards"))
        expander.invalidate_cache()
    parts = out.split(" ")
    assert parts[0] == parts[2] == "Alice"
    assert parts[1] == parts[3] == "Bob"


# ── weighted picks (B2 / B5 / B7) ────────────────────────────────────────────
def test_weighted_prefix_not_stripped_when_plain_doublecolon():
    # Only NUMERIC-prefixed "N::" lines are weights. A line whose "::" is not
    # preceded by a number (e.g. "a movie:: style") must be kept verbatim (B2).
    # A numeric-prefixed "3::weighted" is a legit weight and yields "weighted".
    items = ["a movie:: style", "plain value", "3::weighted"]
    rng = random.Random(1)
    valid = set(items) | {"weighted"}
    for _ in range(50):
        pick = expander.pick_random(rng, list(items))
        assert pick in valid
        assert pick != ""  # never drops to empty


def test_weighted_only_numeric_prefix_treated_as_weight():
    items = ["3::sunset", "1::day", "1::night"]
    rng = __import__("random").Random(42)
    counts = {"sunset": 0, "day": 0, "night": 0}
    for _ in range(200):
        counts[expander.pick_random(rng, list(items))] += 1
    # sunset should dominate
    assert counts["sunset"] > counts["day"]
    assert counts["sunset"] > counts["night"]


def test_all_zero_weights_falls_back_to_uniform():
    items = ["0::a", "0::b", "0::c"]
    rng = __import__("random").Random(5)
    for _ in range(50):
        pick = expander.pick_random(rng, list(items))
        assert pick in ("a", "b", "c")  # never raises ValueError (B5)


def test_negative_weights_allowed():
    items = ["2::big", "-1::small", "1::mid"]
    rng = __import__("random").Random(11)
    for _ in range(50):
        pick = expander.pick_random(rng, list(items))
        assert pick in ("big", "small", "mid")


# ── sequential mode (B7 strips weight prefix) ───────────────────────────────
def test_sequential_strips_weight_prefix():
    items = ["3::sunset", "1::day"]
    rng = __import__("random").Random(0)
    out = expander.pick_random(rng, list(items), sequential_index=0)
    assert out == "sunset"
    out2 = expander.pick_random(rng, list(items), sequential_index=1)
    assert out2 == "day"


def test_sequential_cycles(tmp_path):
    # Isolated single-line files so sequential picks are exact and fully expanded.
    (tmp_path / "x.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
    expander.set_wildcards_dir(str(tmp_path))
    try:
        out = [expander.expand_prompt_sequential("__x__", i) for i in range(3)]
    finally:
        expander.set_wildcards_dir(os.path.join(REPO_ROOT, "wildcards"))
        expander.invalidate_cache()
    assert out == ["one", "two", "three"]
    assert all("__" not in o for o in out)


# ── aliases / resolution (no data breakage) ──────────────────────────────────
def test_all_aliases_resolve():
    missing = [
        (old, target)
        for old, target in expander.WILDCARD_ALIASES.items()
        if not expander.resolve_wildcard_files(target)
        and not expander.resolve_wildcard_files(old)
    ]
    assert missing == [], f"aliases missing both forms: {missing[:5]}"


def test_underscore_to_slash_resolution():
    # __camera_shot__ (legacy) should still resolve to camera/shot
    assert expander.resolve_wildcard_files("camera_shot")


# ── path sanitizer (B3) ─────────────────────────────────────────────────────
def test_sanitize_rejects_traversal():
    assert expander.sanitize_relative_path("../escape.txt") is None
    assert expander.sanitize_relative_path("a/../../b.txt") is None
    assert expander.sanitize_relative_path("/abs.txt") is None
    assert expander.sanitize_relative_path("C:/x.txt") is None


def test_sanitize_allows_nested():
    assert expander.sanitize_relative_path("mytheme/sunset.txt") == "mytheme/sunset.txt"
    assert expander.sanitize_relative_path("plain") == "plain"


# ── line cache (P1) ─────────────────────────────────────────────────────────
def test_cache_returns_same_lines_and_invalidates():
    name = "color/named"
    first = expander.load_wildcard_lines(name)
    # force cache by calling again
    assert expander.load_wildcard_lines(name) == first
    expander.invalidate_cache()
    assert expander.load_wildcard_lines(name) == first


def test_cache_invalidates_on_file_change():
    with tempfile.TemporaryDirectory() as d:
        expander.set_wildcards_dir(d)
        f = os.path.join(d, "tmp_cache_test.txt")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("one\ntwo\n")
        lines1 = expander.load_wildcard_lines("tmp_cache_test")
        assert lines1 == ["one", "two"]
        # modify file, change mtime deterministically
        import time
        time.sleep(0.01)
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("three\n")
        lines2 = expander.load_wildcard_lines("tmp_cache_test")
        assert lines2 == ["three"]
        expander.set_wildcards_dir(os.path.join(REPO_ROOT, "wildcards"))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
