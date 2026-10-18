"""Character profile manager for the Wan2GP wildcards plugin.

Stores named character profiles in JSON and syncs each one to a wildcard
``.txt`` file so ``__character/Name__`` works with the existing expander.

Safety rules:

* A profile may never clobber a shipped wildcard file. ``wildcards/character/``
  already ships ``age.txt``, ``archetype.txt``, ``body.txt``, ``gender.txt``,
  ``identity.txt``, ``phrase.txt``, ``profession.txt`` and ``species.txt``;
  saving a profile with one of those names is refused instead of silently
  replacing the built-in list. :func:`reserved_names` lists them for the UI.
* Profiles are written atomically (temp file + ``os.replace``) so a crash can
  never truncate ``profiles.json``.
"""

import os
import json
import tempfile
from dataclasses import dataclass, field

from . import expander

CHARACTERS_SUBDIR = "characters"        # profiles.json lives here
WILDCARD_CHAR_SUBDIR = "character"      # under wildcards/ dir
PROFILES_FILE = "profiles.json"

_plugin_dir: str = ""  # set by init()


def init(plugin_dir: str):
    global _plugin_dir
    _plugin_dir = plugin_dir
    os.makedirs(os.path.join(plugin_dir, CHARACTERS_SUBDIR), exist_ok=True)


def _safe_char_name(name: str) -> str | None:
    """Validate a character name usable as a filename.

    Rejects empty names, path separators, traversal, and leading dots
    (would escape the wildcards/character/ dir or hide files).
    """
    if not name or not name.strip():
        return None
    name = name.strip()
    if name.startswith(".") or name.startswith("/") or name.startswith("\\"):
        return None
    if any(c in name for c in ("/", "\\", ":", "*", "?", '"', "<", ">", "|")):
        return None
    if "\x00" in name or name in (".", ".."):
        return None
    if name.endswith("."):
        return None  # trailing dots break on Windows
    return name


def _profiles_path() -> str:
    return os.path.join(_plugin_dir, CHARACTERS_SUBDIR, PROFILES_FILE)


def _wildcard_char_dir() -> str:
    """Directory holding one .txt per character.

    Prefers the expander's live wildcards dir so tests (and any host that
    relocates the collection) stay in sync with what expansion actually reads.
    """
    base = getattr(expander, "WILDCARDS_DIR", "") or os.path.join(_plugin_dir, "wildcards")
    return os.path.join(base, WILDCARD_CHAR_SUBDIR)


def wildcard_path(name: str) -> str:
    """Path of the wildcard file backing a character profile."""
    return os.path.join(_wildcard_char_dir(), f"{name}.txt")


def existing_wildcard(name: str) -> str | None:
    """The on-disk character file for ``name``, matched case-insensitively.

    Windows resolves ``Aria.txt`` to a shipped ``aria.txt``; Linux does not, so
    ``os.path.isfile`` alone would let a Linux user create a second, oddly-cased
    file where a Windows user would be stopped (or, worse, would overwrite the
    built-in). Comparing against the directory listing keeps both platforms -
    and the promise that a profile never shadows a shipped character - identical.
    """
    char_dir = _wildcard_char_dir()
    target = f"{name}.txt".lower()
    try:
        entries = os.listdir(char_dir)
    except OSError:
        return None
    for entry in entries:
        if entry.lower() == target:
            return os.path.join(char_dir, entry)
    return None


def load_profiles() -> dict:
    path = _profiles_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_profiles(profiles: dict):
    """Atomically persist the profile store."""
    path = _profiles_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def export_profiles_json() -> str:
    """Read the raw profile store as JSON text (used by the Export button)."""
    path = _profiles_path()
    if not os.path.isfile(path):
        return "{}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        return json.dumps({"error": f"could not read profiles: {e}"})


def list_characters() -> list[str]:
    return sorted(load_profiles().keys())


def get_character(name: str) -> dict | None:
    return load_profiles().get(name)


def reserved_names() -> list[str]:
    """Character names already taken by a shipped (non-profile) wildcard file."""
    try:
        entries = os.listdir(_wildcard_char_dir())
    except OSError:
        return []
    owned = set(load_profiles().keys())
    return sorted(
        f[:-4] for f in entries
        if f.endswith(".txt") and not f.startswith("__") and f[:-4] not in owned
    )


def sync_to_wildcard(name: str, profile: dict):
    """Write/update the wildcard .txt file for a character."""
    char_dir = _wildcard_char_dir()
    os.makedirs(char_dir, exist_ok=True)
    path = wildcard_path(name)
    appearance = str(profile.get("appearance", "") or "").strip()
    # multi-line appearance = multiple variants in wildcard
    lines = [line.strip() for line in appearance.splitlines() if line.strip()]
    if not lines:
        lines = [name]  # fallback so the wildcard always expands to something
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _remove_wildcard_file(name: str) -> bool:
    """Delete the character's wildcard file. Returns True when a file was removed."""
    path = wildcard_path(name)
    if os.path.isfile(path):
        try:
            os.remove(path)
            return True
        except OSError:
            return False
    return False


def remove_wildcard(name: str) -> bool:
    """Delete a character's wildcard file, but never a shipped one."""
    if name not in load_profiles():
        return False  # not ours: refuse to delete built-in wildcard data
    return _remove_wildcard_file(name)


def save_character(name: str, profile: dict) -> str:
    """Save or update a character profile. Syncs to a wildcard file."""
    safe = _safe_char_name(name)
    if safe is None:
        return "Invalid character name (no path separators, dots, or special characters)."
    if not isinstance(profile, dict):
        return "Character profile must be an object."
    name = safe
    profiles = load_profiles()
    if name not in profiles and existing_wildcard(name):
        return (
            f"'{name}' is a built-in wildcard (wildcards/character/{name}.txt). "
            "Pick a different character name."
        )
    profiles[name] = profile
    save_profiles(profiles)
    sync_to_wildcard(name, profile)
    expander.invalidate_cache()
    return f"Character '{name}' saved -> wildcards/character/{name}.txt"


def delete_character(name: str) -> str:
    """Delete a character profile and its wildcard file."""
    profiles = load_profiles()
    if name not in profiles:
        return f"Character '{name}' not found."
    del profiles[name]
    save_profiles(profiles)
    _remove_wildcard_file(name)
    expander.invalidate_cache()
    return f"Character '{name}' deleted."


@dataclass
class ImportResult:
    """Outcome of a bulk import."""
    imported: int = 0
    skipped: int = 0
    reasons: list[str] = field(default_factory=list)

    def summary(self) -> str:
        msg = f"Imported {self.imported} character(s)."
        if self.skipped:
            msg += f" Skipped {self.skipped} entry(ies)."
        if self.reasons:
            msg += "\n" + "\n".join(f"  - {r}" for r in self.reasons[:20])
            if len(self.reasons) > 20:
                msg += f"\n  ... and {len(self.reasons) - 20} more"
        return msg


def import_profiles(data: dict) -> ImportResult:
    """Merge imported character profiles (validated, never partially corrupt).

    Names or profiles that are unsafe/malformed/reserved are skipped and
    reported, instead of crashing or overwriting built-in wildcard data.
    """
    result = ImportResult()
    if not isinstance(data, dict):
        result.reasons.append("Import must be a JSON object of {name: profile}.")
        return result
    for name, profile in data.items():
        safe = _safe_char_name(name)
        if safe is None:
            result.skipped += 1
            result.reasons.append(f"'{name}' is not a valid character name.")
            continue
        if not isinstance(profile, dict):
            result.skipped += 1
            result.reasons.append(f"'{name}' profile is not an object.")
            continue
        message = save_character(safe, profile)
        if message.startswith("Character "):
            result.imported += 1
        else:
            result.skipped += 1
            result.reasons.append(f"'{name}': {message}")
    return result


def import_characters(data: dict) -> tuple[int, int]:
    """Merge imported character profiles (validated).

    Returns (imported_count, skipped_count); see :func:`import_profiles` for the
    per-entry reasons.
    """
    result = import_profiles(data)
    return result.imported, result.skipped
