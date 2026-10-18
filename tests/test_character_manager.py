"""Unit tests for character_manager (B4 validation + sync)."""
import os
import sys
import json
import tempfile

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import character_manager  # noqa: E402
import expander  # noqa: E402

pytestmark = pytest.mark.usefixtures("tmp_plugin")


@pytest.fixture
def tmp_plugin(tmp_path, monkeypatch):
    # redirect the manager at a temp dir so we never touch the real repo
    character_manager.init(str(tmp_path))
    monkeypatch.setattr(character_manager.expander, "WILDCARDS_DIR",
                        os.path.join(str(tmp_path), "wildcards"))
    # ensure wildcards/character exists
    os.makedirs(os.path.join(str(tmp_path), "wildcards", "character"), exist_ok=True)
    yield tmp_path
    character_manager.expander.invalidate_cache()


def test_save_and_load_roundtrip(tmp_plugin):
    msg = character_manager.save_character("Sarah", {"appearance": "blonde, blue eyes"})
    assert "saved" in msg
    prof = character_manager.get_character("Sarah")
    assert prof["appearance"] == "blonde, blue eyes"
    # wildcard file synced
    wc = os.path.join(str(tmp_plugin), "wildcards", "character", "Sarah.txt")
    assert os.path.isfile(wc)
    assert "blonde, blue eyes" in open(wc, encoding="utf-8").read()


def test_delete_removes_wildcard(tmp_plugin):
    character_manager.save_character("Bob", {"appearance": "tall"})
    character_manager.delete_character("Bob")
    assert character_manager.get_character("Bob") is None
    wc = os.path.join(str(tmp_plugin), "wildcards", "character", "Bob.txt")
    assert not os.path.isfile(wc)


def test_invalid_name_rejected(tmp_plugin):
    msg = character_manager.save_character("../escape", {"appearance": "x"})
    assert "Invalid character name" in msg
    # nothing written
    assert character_manager.get_character("../escape") is None


def test_non_dict_profile_rejected(tmp_plugin):
    msg = character_manager.save_character("Carl", "notadict")
    assert "must be an object" in msg


def test_import_validates_and_skips_bad(tmp_plugin):
    data = {
        "Good": {"appearance": "ok"},
        "Bad/Name": {"appearance": "x"},   # contains /
        "AlsoBad": "notadict",               # not a dict
    }
    imported, skipped = character_manager.import_characters(data)
    assert imported == 1
    assert skipped == 2
    assert character_manager.get_character("Good") is not None
    assert character_manager.get_character("Bad/Name") is None


# ── name validation ────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["", "   ", ".hidden", "../up", "a/b", "a\\b",
                                  "a:b", "star*", "q?", 'quo"', "less<", "big>",
                                  "pipe|", "trailing."])
def test_safe_char_name_rejects(tmp_plugin, name):
    assert character_manager._safe_char_name(name) is None


@pytest.mark.parametrize("name", ["Sarah", "Dr. Who", "a b", "Jean-Luc", "2001"])
def test_safe_char_name_accepts(tmp_plugin, name):
    assert character_manager._safe_char_name(name) == name


# ── built-in wildcard protection ───────────────────────────────────────────

def _shipped(tmp_plugin, name: str):
    """Create a file that looks like a shipped, non-profile wildcard."""
    path = os.path.join(str(tmp_plugin), "wildcards", "character", f"{name}.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("built-in value\n")
    return path


def test_reserved_names_lists_shipped_files_only(tmp_plugin):
    _shipped(tmp_plugin, "age")
    _shipped(tmp_plugin, "archetype")
    character_manager.save_character("Mine", {"appearance": "x"})

    assert character_manager.reserved_names() == ["age", "archetype"]


def test_save_refuses_to_clobber_builtin_wildcard(tmp_plugin):
    path = _shipped(tmp_plugin, "age")
    message = character_manager.save_character("age", {"appearance": "REPLACED"})
    assert "built-in" in message
    with open(path, encoding="utf-8") as handle:
        assert handle.read() == "built-in value\n"
    assert character_manager.get_character("age") is None


def test_builtin_guard_ignores_case(tmp_plugin):
    """A shipped `aria.txt` must also block a profile named `ARIA`.

    Windows resolves both names to one file, so `os.path.isfile` catches this
    there; on Linux it does not, and the guard used to let a second, oddly-cased
    file appear next to the shipped one.
    """
    shipped = _shipped(tmp_plugin, "aria")
    message = character_manager.save_character("ARIA", {"appearance": "mine"})
    assert "built-in" in message
    assert character_manager.get_character("ARIA") is None
    with open(shipped, encoding="utf-8") as handle:
        assert handle.read() == "built-in value\n"
    assert os.listdir(os.path.dirname(shipped)) == ["aria.txt"]


def test_save_can_update_a_profile_it_owns(tmp_plugin):
    assert "saved" in character_manager.save_character("Hero", {"appearance": "one"})
    assert "saved" in character_manager.save_character("Hero", {"appearance": "two"})
    assert character_manager.get_character("Hero")["appearance"] == "two"


def test_remove_wildcard_refuses_builtin(tmp_plugin):
    path = _shipped(tmp_plugin, "age")
    assert character_manager.remove_wildcard("age") is False
    assert os.path.isfile(path)


def test_delete_character_leaves_builtin_file_alone(tmp_plugin):
    path = _shipped(tmp_plugin, "age")
    assert "not found" in character_manager.delete_character("age")
    assert os.path.isfile(path)


# ── atomic profile store ───────────────────────────────────────────────────

def test_save_profiles_is_valid_json_and_leaves_no_temp_files(tmp_plugin):
    character_manager.save_profiles({"A": {"appearance": "x"}})
    char_dir = os.path.join(str(tmp_plugin), "characters")
    assert os.listdir(char_dir) == ["profiles.json"]
    with open(os.path.join(char_dir, "profiles.json"), encoding="utf-8") as handle:
        assert json.load(handle) == {"A": {"appearance": "x"}}


def test_load_profiles_survives_corrupt_json(tmp_plugin):
    char_dir = os.path.join(str(tmp_plugin), "characters")
    os.makedirs(char_dir, exist_ok=True)
    with open(os.path.join(char_dir, "profiles.json"), "w", encoding="utf-8") as handle:
        handle.write("{not json")
    assert character_manager.load_profiles() == {}


def test_export_profiles_json(tmp_plugin):
    assert character_manager.export_profiles_json() == "{}"
    character_manager.save_character("A", {"appearance": "x"})
    assert json.loads(character_manager.export_profiles_json()) == {"A": {"appearance": "x"}}


# ── wildcard sync ──────────────────────────────────────────────────────────

def test_multiline_appearance_becomes_multiple_variants(tmp_plugin):
    character_manager.save_character(
        "Multi", {"appearance": "young\n  old  \n\nmiddle"}
    )
    path = os.path.join(str(tmp_plugin), "wildcards", "character", "Multi.txt")
    with open(path, encoding="utf-8") as handle:
        assert handle.read() == "young\nold\nmiddle\n"


def test_empty_appearance_falls_back_to_the_name(tmp_plugin):
    character_manager.save_character("Ghost", {})
    path = os.path.join(str(tmp_plugin), "wildcards", "character", "Ghost.txt")
    with open(path, encoding="utf-8") as handle:
        assert handle.read() == "Ghost\n"


def test_saved_character_is_immediately_expandable(tmp_plugin):
    character_manager.save_character("Blade", {"appearance": "silver hair"})
    assert expander.expand_prompt("__character/Blade__") == "silver hair"


# ── import reporting ───────────────────────────────────────────────────────

def test_import_profiles_reports_each_skip_reason(tmp_plugin):
    _shipped(tmp_plugin, "age")
    result = character_manager.import_profiles({
        "Good": {"appearance": "ok"},
        "Bad/Name": {"appearance": "x"},
        "AlsoBad": "notadict",
        "age": {"appearance": "clobber attempt"},
    })
    assert isinstance(result, character_manager.ImportResult)
    assert result.imported == 1
    assert result.skipped == 3
    assert len(result.reasons) == 3
    assert any("valid character name" in r for r in result.reasons)
    assert any("not an object" in r for r in result.reasons)
    assert any("built-in" in r for r in result.reasons)
    assert "Imported 1 character(s)." in result.summary()
    assert "Skipped 3" in result.summary()
    # the built-in file was not touched
    assert character_manager.get_character("age") is None


def test_import_profiles_rejects_non_object(tmp_plugin):
    result = character_manager.import_profiles(["not", "a", "dict"])
    assert result.imported == 0
    assert result.reasons and "JSON object" in result.reasons[0]


def test_import_profiles_truncates_the_reason_list(tmp_plugin):
    data = {f"bad/{i}": {"appearance": "x"} for i in range(30)}
    result = character_manager.import_profiles(data)
    assert result.skipped == 30
    assert len(result.reasons) == 30
    assert "and 10 more" in result.summary()
