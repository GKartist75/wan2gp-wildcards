"""Character profile manager for Wan2GP wildcards plugin.

Stores named character profiles in JSON and syncs them as wildcard .txt
files so __character/Name__ works with the existing expander.
"""

import os
import json

CHARACTERS_SUBDIR = "characters"        # profiles.json lives here
WILDCARD_CHAR_SUBDIR = "character"      # under wildcards/ dir
PROFILES_FILE = "profiles.json"

_plugin_dir: str = ""  # set by init()


def init(plugin_dir: str):
    global _plugin_dir
    _plugin_dir = plugin_dir
    os.makedirs(os.path.join(plugin_dir, CHARACTERS_SUBDIR), exist_ok=True)


def _profiles_path() -> str:
    return os.path.join(_plugin_dir, CHARACTERS_SUBDIR, PROFILES_FILE)


def _wildcard_char_dir() -> str:
    return os.path.join(_plugin_dir, "wildcards", WILDCARD_CHAR_SUBDIR)


def load_profiles() -> dict:
    path = _profiles_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_profiles(profiles: dict):
    path = _profiles_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)


def list_characters() -> list[str]:
    return sorted(load_profiles().keys())


def get_character(name: str) -> dict | None:
    return load_profiles().get(name)


def sync_to_wildcard(name: str, profile: dict):
    """Write/update the wildcard .txt file for a character."""
    char_dir = _wildcard_char_dir()
    os.makedirs(char_dir, exist_ok=True)
    path = os.path.join(char_dir, f"{name}.txt")
    appearance = profile.get("appearance", "").strip()
    # multi-line appearance = multiple variants in wildcard
    with open(path, "w", encoding="utf-8") as f:
        for line in appearance.splitlines():
            line = line.strip()
            if line:
                f.write(line + "\n")
        if not appearance:
            f.write(name + "\n")  # ponytail: fallback so wildcard exists


def remove_wildcard(name: str):
    """Delete the wildcard .txt file for a character."""
    path = os.path.join(_wildcard_char_dir(), f"{name}.txt")
    if os.path.isfile(path):
        os.remove(path)


def save_character(name: str, profile: dict) -> str:
    """Save or update a character profile. Syncs to wildcard file."""
    if not name or not name.strip():
        return "Character name is required."
    name = name.strip()
    profiles = load_profiles()
    profiles[name] = profile
    save_profiles(profiles)
    sync_to_wildcard(name, profile)
    return f"Character '{name}' saved → wildcards/character/{name}.txt"


def delete_character(name: str) -> str:
    """Delete a character profile and its wildcard file."""
    profiles = load_profiles()
    if name not in profiles:
        return f"Character '{name}' not found."
    del profiles[name]
    save_profiles(profiles)
    remove_wildcard(name)
    return f"Character '{name}' deleted."
