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
