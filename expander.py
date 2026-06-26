"""Wildcard expansion engine for Wan2GP prompts.

Syntax:
- __name__       -> random line from wildcards/name.txt
- {opt1|opt2}    -> random inline choice
- 2::value       -> weighted option in .txt files (weight 2)
- Nesting: files can reference other __wildcards__ and {options}
- Seed-deterministic via random.Random(seed)
"""

import os
import re
import random
import glob as globmod

WILDCARDS_DIR: str = ""  # set by plugin.py on init
DEPTH_LIMIT = 10

WILDCARD_RE = re.compile(r"__([a-zA-Z0-9_/.\\-]+)__")
VARIANT_RE = re.compile(r"\{([^{}]*)\}")


def set_wildcards_dir(path: str) -> None:
    global WILDCARDS_DIR
    WILDCARDS_DIR = path
    os.makedirs(path, exist_ok=True)


def resolve_wildcard_files(name: str) -> list[str]:
    """Find .txt files matching wildcard name in WILDCARDS_DIR.

    Supports three forms:
      __camera_shot__  (underscore -> slash fallback)
      __camera/shot__  (direct path)
      __camera__       (directory pool)
    """
    base = name.replace("\\", "/").lstrip("/")
    paths = []

    def _try_resolve(b: str) -> list[str]:
        result: list[str] = []
        # direct match: wildcards/name.txt
        direct = os.path.join(WILDCARDS_DIR, b + ".txt")
        if os.path.isfile(direct):
            result.append(direct)
        # directory match: wildcards/name/*.txt
        dirpath = os.path.join(WILDCARDS_DIR, b)
        if os.path.isdir(dirpath):
            for f in sorted(os.listdir(dirpath)):
                if f.endswith(".txt"):
                    result.append(os.path.join(dirpath, f))
        # glob match: wildcards/name*.txt
        if not result:
            for f in sorted(globmod.glob(os.path.join(WILDCARDS_DIR, b))):
                if f.endswith(".txt") and os.path.isfile(f):
                    result.append(f)
        return result

    paths = _try_resolve(base)

    # fallback: convert underscores to slashes
    # __camera_shot__ -> try camera/shot as well
    if not paths and "_" in base:
        slash_version = base.replace("_", "/")
        if slash_version != base:
            paths = _try_resolve(slash_version)

    return paths


def load_wildcard_lines(name: str) -> list[str]:
    """Return all non-empty, non-comment lines from matching wildcard files."""
    lines: list[str] = []
    for fpath in resolve_wildcard_files(name):
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        lines.append(line)
        except OSError:
            continue
    return lines


def pick_random(rng: random.Random, items: list[str]) -> str:
    """Pick item uniformly, or weighted if items use N:: prefix."""
    if not items:
        return ""
    if not items[0].startswith("::") and "::" not in items[0]:
        return rng.choice(items)

    choices: list[str] = []
    weights: list[float] = []
    for item in items:
        if "::" in item:
            weight_str, _, val = item.partition("::")
            try:
                weight = float(weight_str)
            except ValueError:
                weight = 1.0
            val = val.strip()
        else:
            weight = 1.0
            val = item.strip()
        if val:
            choices.append(val)
            weights.append(max(weight, 0.0))

    if not choices:
        return ""
    return rng.choices(choices, weights=weights, k=1)[0]


def _expand_text(text: str, rng: random.Random, depth: int = 0) -> str:
    """Recursive expansion: wildcards first, then variants. Depth-limited."""
    if depth >= DEPTH_LIMIT:
        return text

    # 1. expand __wildcard__ references
    def _replace_wildcard(m: re.Match) -> str:
        name = m.group(1)
        lines = load_wildcard_lines(name)
        if not lines:
            return m.group(0)  # leave as-is if not found
        chosen = pick_random(rng, lines)
        return _expand_text(chosen, rng, depth + 1)

    text = WILDCARD_RE.sub(_replace_wildcard, text)

    # 2. expand {opt1|opt2} inline variants
    def _replace_variant(m: re.Match) -> str:
        inner = m.group(1)
        parts = [p.strip() for p in inner.split("|")]
        if len(parts) < 2:
            return m.group(0)
        chosen = pick_random(rng, parts)
        return _expand_text(chosen, rng, depth + 1)

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
