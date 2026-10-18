"""Wildcard expansion engine for Wan2GP prompts.

Syntax:
- __name__       -> random line from wildcards/name.txt
- {opt1|opt2}    -> random inline choice
- 2::value       -> weighted option in .txt files (weight 2)
- __$var:file__  -> pick from file, store result as var
- __$var=value__ -> assign a literal value to var (no random pick)
- __$var__       -> reuse previously stored var value
- Nesting: files can reference other __wildcards__ and {options}
- Seed-deterministic via random.Random(seed)
"""

import os
import re
import random
import glob as globmod
import threading

WILDCARDS_DIR: str = ""  # set by plugin.py on init
DEPTH_LIMIT = 10

WILDCARD_RE = re.compile(r"__([a-zA-Z0-9_/.\\-]+)__")
VARIANT_RE = re.compile(r"\{([^{}]*)\}")
CAPTURE_ANY_RE = re.compile(
    r"__\$([a-zA-Z0-9_]+):([a-zA-Z0-9_/.\\-]+)__"   # __$var:file__
    r"|__\$([a-zA-Z0-9_]+)\s*=\s*(.+?)__"           # __$var=value__
)
CAPTURE_GET_RE = re.compile(r"__\$([a-zA-Z0-9_]+)__")

# A weighted line must START with a numeric weight: "3::sunset" or "-1.5::x".
# Lines that merely CONTAIN "::" elsewhere (e.g. "a movie:: style") are plain
# values and must not be treated as weights (prevents silent prefix loss).
WEIGHT_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*::(.*)$")

# Parsed-line cache: {name: (signature, lines)} where signature is a tuple of
# (path, mtime_ns, size) for each resolved file. Invalidation is automatic on
# file change (mtime/size), plus explicit invalidate_cache() after edits.
_LINE_CACHE: dict[str, tuple[tuple[tuple[str, int, int], ...], list[str]]] = {}
_CACHE_LOCK = threading.RLock()
_CACHE_MAX_ENTRIES = 512

# Names that Windows treats as devices; writing them can hang or fail even
# when they appear as a subdirectory component.
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


try:  # imported as part of a package (plugin runtime, tests)
    from .aliases import WILDCARD_ALIASES
except ImportError:  # imported as a top-level module (ad-hoc tooling)
    from aliases import WILDCARD_ALIASES




def set_wildcards_dir(path: str) -> None:
    global WILDCARDS_DIR
    WILDCARDS_DIR = path
    os.makedirs(path, exist_ok=True)


def _listdir(path: str) -> list[str]:
    """os.listdir that never raises (returns [] for a missing/unreadable dir)."""
    try:
        return os.listdir(path)
    except OSError:
        return []


def _resolve_path_ci(rel: str) -> str | None:
    """Resolve ``rel`` under WILDCARDS_DIR, matching each segment case-insensitively.

    Returns the *real* on-disk path (canonical casing) or None. An exact-case
    segment wins; this keeps Windows (case-insensitive) and Linux (case-sensitive)
    behaving the same for names typed with the wrong case.
    """
    current = WILDCARDS_DIR
    for part in rel.replace("\\", "/").split("/"):
        if not part:
            continue
        entries = _listdir(current)
        if part in entries:
            current = os.path.join(current, part)
            continue
        lowered = part.lower()
        match = next((e for e in entries if e.lower() == lowered), None)
        if match is None:
            return None
        current = os.path.join(current, match)
    return current


def resolve_wildcard_files(name: str) -> list[str]:
    """Find .txt files matching wildcard name in WILDCARDS_DIR.

    Supports three forms:
      __camera_shot__  (underscore -> slash fallback)
      __camera/shot__  (direct path)
      __camera__       (directory pool)
    Also checks WILDCARD_ALIASES for renamed/moved files (backward compat).
    Names resolve case-insensitively so prompts written before the path
    normalization keep working on every platform.
    """
    base = name.replace("\\", "/").lstrip("/")

    def _try_resolve(b: str, _seen: set[str]) -> list[str]:
        result: list[str] = []
        # direct file / directory pool match (case-insensitive)
        target = _resolve_path_ci(b)
        if target and os.path.isfile(target):
            result.append(target)
        elif target and os.path.isdir(target):
            for f in sorted(_listdir(target)):
                if f.endswith(".txt") and not f.startswith("__"):
                    result.append(os.path.join(target, f))
        # glob match: wildcards/name*.txt (partial-name resolution fallback)
        if not result:
            pattern = os.path.join(WILDCARDS_DIR, b) + "*.txt"
            for f in sorted(globmod.glob(pattern)):
                if os.path.isfile(f):
                    result.append(f)
        # alias check (backward compatibility for renamed/moved files)
        if not result:
            key = b.lower()
            if key in WILDCARD_ALIASES and key not in _seen:
                _seen.add(key)  # guard against alias cycles in the table
                result = _try_resolve(WILDCARD_ALIASES[key], _seen)
        return result

    paths = _try_resolve(base, set())

    # fallback: convert underscores to slashes
    # __camera_shot__ -> try camera/shot as well
    if not paths and "_" in base:
        slash_version = base.replace("_", "/")
        if slash_version != base:
            paths = _try_resolve(slash_version, set())

    return paths


def iter_wildcard_files(root: str | None = None) -> list[str]:
    """Return every real wildcard file (.txt) under the collection.

    ``__``-prefixed files (e.g. ``__index__.txt``) are metadata, not pools,
    and are therefore skipped. Results are sorted for deterministic output.
    """
    root = root or WILDCARDS_DIR
    found: list[str] = []
    for base, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("__"))
        for f in sorted(files):
            if f.endswith(".txt") and not f.startswith("__"):
                found.append(os.path.join(base, f))
    return found


def sanitize_relative_path(name: str) -> str | None:
    """Validate a user-supplied relative filename (e.g. \"mytheme/sunset.txt\").

    Returns the normalized name (forward slashes) if safe, else None.
    Rejects absolute paths, drive letters, ``..`` traversal, NUL, and
    Windows-reserved device names (CON, NUL, COM1, ... which can hang or
    misbehave even when written into a subdirectory).
    """
    if not name or not name.strip():
        return None
    name = name.strip().replace("\\", "/")
    if "\x00" in name or name.startswith("/") or re.match(r"^[a-zA-Z]:", name):
        return None
    parts = name.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return None
    for part in parts:
        stem = part.split(".")[0].strip()
        if stem.upper() in _WINDOWS_RESERVED_NAMES:
            return None
    return name


def invalidate_cache() -> None:
    """Drop cached wildcard lines (call after editing/creating/deleting files)."""
    with _CACHE_LOCK:
        _LINE_CACHE.clear()


def load_wildcard_lines(name: str) -> list[str]:
    """Return all non-empty, non-comment lines from matching wildcard files.

    Results are cached per name with a (path, mtime_ns, size) signature so
    repeated expansions (batches, nesting) don't re-read files from disk.
    A file that disappears between resolution and stat is skipped rather than
    poisoning the cache with an empty signature. The cache is bounded and
    guarded by a lock because Gradio may invoke handlers from threads.
    """
    files = resolve_wildcard_files(name)

    signature_parts: list[tuple[str, int, int]] = []
    for fpath in files:
        try:
            st = os.stat(fpath)
        except OSError:
            continue
        signature_parts.append((fpath, st.st_mtime_ns, st.st_size))
    signature = tuple(signature_parts)

    with _CACHE_LOCK:
        cached = _LINE_CACHE.get(name)
        if cached is not None and cached[0] == signature:
            return cached[1]

    lines: list[str] = []
    for fpath in signature_parts:
        try:
            with open(fpath[0], "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        lines.append(line)
        except OSError:
            continue

    with _CACHE_LOCK:
        if len(_LINE_CACHE) >= _CACHE_MAX_ENTRIES:
            _LINE_CACHE.clear()  # simple bound: never grow without limit
        _LINE_CACHE[name] = (signature, lines)
    return lines


def pick_random(rng: random.Random, items: list[str], sequential_index: int | None = None) -> str:
    """Pick item uniformly, or weighted if items use N:: prefix.

    A line is weighted ONLY when it starts with a numeric weight (``3::sunset``);
    lines merely containing ``::`` in content are kept intact. When
    sequential_index is set, picks items[index % len(items)] for line-by-line
    cycling instead of random choice (weight prefixes are stripped).
    """
    if not items:
        return ""

    # sequential mode: index directly into items, no RNG
    if sequential_index is not None:
        item = items[sequential_index % len(items)]
        m = WEIGHT_RE.match(item)
        if m:
            return m.group(2).strip() or item.strip()
        return item.strip()

    # weighted only if at least one line starts with a numeric N:: prefix
    has_weights = any(WEIGHT_RE.match(item) for item in items)
    if not has_weights:
        return rng.choice(items)

    choices: list[str] = []
    weights: list[float] = []
    for item in items:
        m = WEIGHT_RE.match(item)
        if m:
            try:
                weight = float(m.group(1))
            except ValueError:
                weight = 1.0
            val = m.group(2).strip()
            if not val:
                val = item.strip()
        else:
            weight = 1.0
            val = item.strip()
        if val:
            choices.append(val)
            weights.append(max(weight, 0.0))

    if not choices:
        return ""
    # all weights <= 0 would raise ValueError in rng.choices — fall back to uniform
    if sum(weights) <= 0:
        return rng.choice(choices)
    return rng.choices(choices, weights=weights, k=1)[0]


def _expand_text(text: str, rng: random.Random, depth: int = 0,
                 sequential_index: int | None = None,
                 _context: dict[str, str] | None = None) -> str:
    """Recursive expansion: captures, wildcards, then variants. Depth-limited."""
    if depth >= DEPTH_LIMIT:
        return text
    if _context is None:
        _context = {}

    # 0. expand __$var:file__ (pick + store) and __$var=value__ (literal assign)
    #    in ONE pass so textual order is respected — the last set in the prompt wins.
    def _replace_capture(m: re.Match) -> str:
        var, file, var2, value = m.group(1), m.group(2), m.group(3), m.group(4)
        if file is not None:
            lines = load_wildcard_lines(file)
            if not lines:
                return m.group(0)
            chosen = pick_random(rng, lines, sequential_index=sequential_index)
            chosen = _expand_text(chosen, rng, depth + 1,
                                  sequential_index=sequential_index, _context=_context)
            _context[var] = chosen
            return chosen
        expanded = _expand_text(value.strip(), rng, depth + 1,
                                sequential_index=sequential_index,
                                _context=_context)
        _context[var2] = expanded
        return expanded

    text = CAPTURE_ANY_RE.sub(_replace_capture, text)

    # 0b. expand __$var__ (reuse captured value)
    def _replace_capture_get(m: re.Match) -> str:
        var = m.group(1)
        if var in _context:
            return _context[var]
        return m.group(0)  # unknown var, leave as-is

    text = CAPTURE_GET_RE.sub(_replace_capture_get, text)

    # 1. expand __wildcard__ references
    def _replace_wildcard(m: re.Match) -> str:
        name = m.group(1)
        lines = load_wildcard_lines(name)
        if not lines:
            return m.group(0)  # leave as-is if not found
        chosen = pick_random(rng, lines, sequential_index=sequential_index)
        return _expand_text(chosen, rng, depth + 1, sequential_index=sequential_index, _context=_context)

    text = WILDCARD_RE.sub(_replace_wildcard, text)

    # 2. expand {opt1|opt2} inline variants
    def _replace_variant(m: re.Match) -> str:
        inner = m.group(1)
        parts = [p.strip() for p in inner.split("|")]
        if len(parts) < 2:
            return m.group(0)
        chosen = pick_random(rng, parts, sequential_index=sequential_index)
        return _expand_text(chosen, rng, depth + 1, sequential_index=sequential_index, _context=_context)

    text = VARIANT_RE.sub(_replace_variant, text)
    return text


def expand_prompt(prompt: str, seed: int | None = None) -> str:
    """Public entry point. Expands wildcards/variants in prompt.

    Args:
        prompt: Input prompt string.
        seed: RNG seed for deterministic output. None = random.

    Returns:
        Expanded prompt string.
    """
    if not prompt or not WILDCARDS_DIR:
        return prompt

    rng = random.Random(seed)
    return _expand_text(prompt, rng, depth=0)


def expand_prompt_sequential(prompt: str, index: int) -> str:
    """Expand prompt using sequential (non-random) selection.

    Each __wildcard__ picks the line at position `index % len(lines)`
    instead of a random choice. This cycles through wildcard files in order.

    Args:
        prompt: Input prompt string.
        index: Zero-based index for line-by-line cycling.

    Returns:
        Expanded prompt string.
    """
    if not prompt or not WILDCARDS_DIR:
        return prompt

    rng = random.Random()  # not used in sequential mode, but needed for signature
    return _expand_text(prompt, rng, depth=0, sequential_index=index)


def reference_names(text: str) -> list[str]:
    """Return ordered, de-duplicated ``__wildcard__`` names referenced in text.

    Capture syntax (``__$var:file__``) is not counted; use
    :func:`capture_references` for that.
    """
    names: list[str] = []
    for match in WILDCARD_RE.finditer(text or ""):
        name = match.group(1)
        if name not in names:
            names.append(name)
    return names


def capture_files(text: str) -> list[str]:
    """Return de-duplicated pool files referenced by ``__$var:file__`` captures."""
    files: list[str] = []
    for match in CAPTURE_ANY_RE.finditer(text or ""):
        file = match.group(2)
        if file and file not in files:
            files.append(file)
    return files


def unresolved_references(text: str) -> list[str]:
    """Referenced wildcard names that resolve to no file (broken references)."""
    return [n for n in reference_names(text) if not resolve_wildcard_files(n)]
