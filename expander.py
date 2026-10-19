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
# Total nested substitutions allowed for ONE top-level expansion. DEPTH_LIMIT
# alone bounds how deep nesting goes, not how much work it does: a cyclic file
# with k references per line fans out to about k**DEPTH_LIMIT substitutions
# (minutes of a frozen UI), so every expansion also draws from this budget.
MAX_EXPANSIONS = 4096

# Non-greedy: in `__a____b__` the name must end at the first closing `__`, else
# both references are read as one unresolvable name and leak as literal text.
WILDCARD_RE = re.compile(r"__([a-zA-Z0-9_/.\\-]+?)__")
# A variant needs at least one `|`; `{solo}` is plain text (no random choice to
# make), and requiring it means one pass can never rewrite a brace group with
# itself. Nesting (`{a|{b|c}}`) is handled by repeating the pass.
VARIANT_RE = re.compile(r"\{([^{}]*\|[^{}]*)\}")
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


def _match_entry(entries: list[str], part: str) -> str | None:
    """Pick the on-disk entry named ``part``, ignoring case.

    Three passes, best match first: the exact name, then a case-insensitive full
    name (directories, extension-less files), then a case-insensitive ``.txt``
    *stem*. That last pass is what makes ``__CAMERA/SHOT__`` find ``shot.txt``:
    without it the segment ``SHOT`` matches nothing, and resolution used to fall
    through to glob, which only forgives the wrong case on a case-insensitive
    filesystem - so a capitalised reference worked on Windows and silently
    returned nothing on Linux/Colab.
    """
    if part in entries:
        return part
    lowered = part.lower()
    for entry in entries:
        if entry.lower() == lowered:
            return entry
    for entry in entries:
        if entry.lower().endswith(".txt") and entry[:-4].lower() == lowered:
            return entry
    return None


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
        match = _match_entry(_listdir(current), part)
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
    A ``name.txt`` file takes precedence over a same-named directory, so
    ``__nsfw/positions__`` reaches ``positions.txt`` rather than silently
    resolving to the ``positions/`` pool. Also checks WILDCARD_ALIASES for
    renamed/moved files (backward compat). Names resolve case-insensitively so
    prompts written before the path normalization keep working on every
    platform.
    """
    base = name.replace("\\", "/").lstrip("/")

    def _try_resolve(b: str, _seen: set[str]) -> list[str]:
        result: list[str] = []
        # An exact ``name.txt`` file wins over a same-named directory. Five such
        # pairs exist in the collection (body/ears, nsfw/positions,
        # nsfw/panties, nsfw/sex-acts, clothing/period/victorian/female); without
        # this the *.txt half was unreachable through its documented name and
        # ``__clothing/period/victorian/female__`` silently returned *male*
        # attire from the sibling directory.
        if not b.endswith(".txt"):
            target = _resolve_path_ci(b + ".txt")
            if target and os.path.isfile(target):
                result.append(target)
        # direct file / directory pool match (case-insensitive)
        if not result:
            target = _resolve_path_ci(b)
            if target and os.path.isfile(target):
                result.append(target)
            elif target and os.path.isdir(target):
                for f in sorted(_listdir(target)):
                    if f.endswith(".txt") and not f.startswith("__"):
                        result.append(os.path.join(target, f))
        # glob match: wildcards/name*.txt (partial-name resolution fallback).
        # `..` segments are refused here as well as in sanitize_relative_path:
        # that one only guards UI input, while this runs on prompt text, so a
        # `__../secrets__` reference could otherwise read outside the collection.
        if not result and ".." not in b.split("/"):
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
    Rejects absolute paths, drive letters, ``..`` traversal, NUL, ``:`` in any
    component (a mid-path colon is a drive-relative name / NTFS alternate data
    stream on Windows, where the OS drops it and writes a *different* file than
    the one the UI reports), and Windows-reserved device names (CON, NUL, COM1,
    ... which can hang or misbehave even when written into a subdirectory).
    """
    if not name or not name.strip():
        return None
    name = name.strip().replace("\\", "/")
    if "\x00" in name or name.startswith("/") or re.match(r"^[a-zA-Z]:", name) or ":" in name:
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
            # utf-8-sig strips a BOM, which `str.strip()` does not: with plain
            # "utf-8" a file whose first line is `# comment` kept the BOM and
            # started serving the comment as a value. errors="replace" matches
            # the linter's read path, so one cp1252 file can no longer raise
            # UnicodeDecodeError through the plugin and abort a generation while
            # the audit reports the collection healthy.
            with open(fpath[0], "r", encoding="utf-8-sig", errors="replace") as fh:
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
    """Recursive expansion: captures, wildcards, then variants. Depth-limited.

    The passes are repeated until the text stops changing, because a later pass
    can produce syntax an earlier one owns: a ``__$var:file__`` written inside a
    referenced file, or a capture whose file name came out of a ``{a|b}``
    choice. A single ordered pass left both as literal ``__$var__`` text even
    though the value was already stored.
    """
    if _context is None:
        # One shared budget per top-level expansion; "$" cannot appear in a
        # variable name, so the key can never collide with a user variable.
        _context = {"$budget": MAX_EXPANSIONS}
    else:
        # Charged *before* the depth check: a depth-limited call would
        # otherwise be free, and the caller's fixed-point loop would keep
        # substituting cycles into it for DEPTH_LIMIT more rounds.
        _context["$budget"] -= 1
        if _context["$budget"] <= 0:
            return text
    if depth >= DEPTH_LIMIT:
        return text

    def _spent() -> bool:
        """True when this expansion's work budget is used up.

        A substitution that cannot recurse must NOT be performed at all:
        inserting a value that still contains ``__references__`` makes the next
        fixed-point pass replace those again, so the text grows by the file's
        reference count on every pass (a 5-reference cycle would multiply by
        5**DEPTH_LIMIT). Leaving the reference literal stops the growth and the
        fixed-point loop terminates.
        """
        return _context["$budget"] <= 0

    # 0. expand __$var:file__ (pick + store) and __$var=value__ (literal assign)
    #    in ONE pass so textual order is respected — the last set in the prompt wins.
    def _replace_capture(m: re.Match) -> str:
        if _spent():
            return m.group(0)
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

    # 0b. expand __$var__ (reuse captured value)
    def _replace_capture_get(m: re.Match) -> str:
        var = m.group(1)
        if var in _context:
            return _context[var]
        return m.group(0)  # unknown var, leave as-is

    # 1. expand __wildcard__ references
    def _replace_wildcard(m: re.Match) -> str:
        if _spent():
            return m.group(0)
        name = m.group(1)
        lines = load_wildcard_lines(name)
        if not lines:
            return m.group(0)  # leave as-is if not found
        chosen = pick_random(rng, lines, sequential_index=sequential_index)
        return _expand_text(chosen, rng, depth + 1, sequential_index=sequential_index, _context=_context)

    # 2. expand {opt1|opt2} inline variants
    def _replace_variant(m: re.Match) -> str:
        if _spent():
            return m.group(0)
        inner = m.group(1)
        parts = [p.strip() for p in inner.split("|")]
        chosen = pick_random(rng, parts, sequential_index=sequential_index)
        return _expand_text(chosen, rng, depth + 1, sequential_index=sequential_index, _context=_context)

    for _ in range(DEPTH_LIMIT):
        before = text
        text = CAPTURE_ANY_RE.sub(_replace_capture, text)
        text = CAPTURE_GET_RE.sub(_replace_capture_get, text)
        text = WILDCARD_RE.sub(_replace_wildcard, text)
        text = VARIANT_RE.sub(_replace_variant, text)
        if text == before:
            break
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

    return expand_prompt_with_rng(prompt, random.Random(seed))


def expand_prompt_with_rng(prompt: str, rng: random.Random) -> str:
    """Expand ``prompt`` using a caller-supplied RNG.

    Batch generation and previews need to control the RNG themselves (so a seed
    box produces reproducible variations) without importing the private
    recursive expander, so this is the supported entry point for that.

    Args:
        prompt: Input prompt string.
        rng: The random.Random instance to draw picks from.

    Returns:
        Expanded prompt string.
    """
    if not prompt or not WILDCARDS_DIR:
        return prompt

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
    :func:`capture_files` for that.
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
