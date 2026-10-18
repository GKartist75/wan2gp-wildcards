"""Data-integrity tests for the shipped wildcard collection.

These guard the whole `wildcards/` tree. A single broken nested reference, a
renamed folder or a stray uppercase path used to leak literal ``__name__`` text
into generated prompts (and broke silently on case-sensitive filesystems such as
Linux/Colab, where Wan2GP also runs).
"""
import os
import re
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import expander  # noqa: E402
import linter  # noqa: E402

WILDCARDS = os.path.join(REPO_ROOT, "wildcards")

# Placeholders that legitimately appear in documentation instead of a real pool,
# plus the plugin's own __-prefixed metadata filenames (which are not wildcards).
DOC_PLACEHOLDERS = {
    "category_file", "character/Name", "dir", "dir/file", "file", "init",
    "name", "stats", "templates", "underscore_name", "your_file", "mytheme/name",
    "topic", "entries", "filename", "index", "favorites",
}


@pytest.fixture(scope="module")
def collection():
    """Lint the real collection once for the whole module."""
    expander.invalidate_cache()
    return linter.lint_collection(WILDCARDS)


def test_collection_is_not_empty():
    files = expander.iter_wildcard_files(WILDCARDS)
    assert len(files) >= 3000, f"only found {len(files)} wildcard files"


def test_no_broken_nested_references(collection):
    details = "\n".join(
        f"  {b['file']}:{b['line']}: __{b['name']}__" for b in collection["broken"][:20]
    )
    assert collection["broken_total"] == 0, (
        f"{collection['broken_total']} nested reference(s) resolve to no file:\n{details}"
    )


def test_no_empty_files(collection):
    assert collection["empty_files"] == [], (
        "wildcard files with no usable values: " + ", ".join(collection["empty_files"][:20])
    )


def test_no_duplicate_values(collection):
    details = "\n".join(
        f"  {d['file']}:{d['line']} x{d['count']}" for d in collection["duplicates"][:20]
    )
    assert collection["duplicate_total"] == 0, (
        f"{collection['duplicate_total']} duplicate value(s):\n{details}"
    )


def test_every_alias_resolves(collection):
    details = "\n".join(
        f"  {a['alias']} -> {a['target']}" for a in collection["unresolved_aliases"][:20]
    )
    assert collection["unresolved_aliases_total"] == 0, (
        f"{collection['unresolved_aliases_total']} alias(es) point at nothing:\n{details}"
    )
    assert collection["aliases"] > 700


def test_paths_are_lowercase():
    """Paths must be lowercase so lookups work on case-sensitive filesystems.

    The alias table is lowercase, so an uppercase folder (``NSFW/``) silently
    failed on Linux while working on Windows.
    """
    offenders = [
        rel for rel in (
            os.path.relpath(full, WILDCARDS).replace(os.sep, "/")
            for full in expander.iter_wildcard_files(WILDCARDS)
        )
        if rel != rel.lower()
    ]
    assert offenders == [], "uppercase wildcard paths break Linux: " + ", ".join(offenders[:20])


def test_resolution_is_case_insensitive():
    """A wrong-case name still resolves, so old prompts keep working."""
    expander.invalidate_cache()
    assert expander.resolve_wildcard_files("camera/shot")
    # Deliberately mismatched case must still find the file.
    upper = expander.resolve_wildcard_files("CAMERA/SHOT")
    assert upper, "case-insensitive lookup is broken"
    assert expander.WILDCARD_RE  # sanity: module loaded


def test_resolution_does_not_lean_on_a_case_insensitive_filesystem(monkeypatch):
    """The same lookup has to work where the filesystem is case-sensitive.

    Windows forgives a wrong-case path twice over: the filesystem resolves the
    directory and glob matches the filename, so a broken segment lookup stays
    invisible until the ubuntu job runs. Substitute a strict, Linux-like glob and
    prove the direct segment-by-segment lookup does the work by itself.
    """
    real_glob = expander.globmod.glob

    def strict_glob(pattern):
        hits = []
        for hit in real_glob(pattern):
            current = expander.WILDCARDS_DIR
            relative = os.path.relpath(hit, expander.WILDCARDS_DIR).replace("\\", "/")
            # Accept only when every segment matches on-disk casing exactly.
            for part in relative.split("/"):
                if part not in expander._listdir(current):
                    break
                current = os.path.join(current, part)
            else:
                hits.append(hit)
        return hits

    monkeypatch.setattr(expander.globmod, "glob", strict_glob)
    expander.invalidate_cache()
    canonical = expander.resolve_wildcard_files("camera/shot")
    assert canonical
    assert expander.resolve_wildcard_files("CAMERA/SHOT") == canonical


def test_no_trailing_whitespace():
    offenders = []
    for full in expander.iter_wildcard_files(WILDCARDS):
        with open(full, "r", encoding="utf-8", errors="replace") as handle:
            for number, line in enumerate(handle, 1):
                bare = line.rstrip("\n").rstrip("\r")
                if bare != bare.rstrip():
                    offenders.append(f"{os.path.basename(full)}:{number}")
                    break
    assert offenders == [], "trailing whitespace in: " + ", ".join(offenders[:20])


def test_files_are_utf8_decodable():
    for full in expander.iter_wildcard_files(WILDCARDS):
        with open(full, "rb") as handle:
            raw = handle.read()
        raw.decode("utf-8")  # raises UnicodeDecodeError on bad data


def test_aliases_and_flavour_are_stable():
    """Spot-check a few well-known names so a bulk rename can't slip through."""
    for name in ("camera/shot", "color/named", "environment/nature", "lighting/style"):
        assert expander.resolve_wildcard_files(name), name


REF_RE = re.compile(r"__([a-zA-Z0-9_/.\-]+)__")


@pytest.mark.parametrize(
    "rel_path", ["README.md", "docs/infographic-mermaid.md", "wildcards/__index__.txt"]
)
def test_documentation_references_resolve(rel_path, collection):
    """Docs must not advertise wildcards that don't exist."""
    path = os.path.join(REPO_ROOT, rel_path)
    if not os.path.isfile(path):
        pytest.skip(f"{rel_path} not present")
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    broken = sorted(
        {
            name
            for name in REF_RE.findall(text)
            if name not in DOC_PLACEHOLDERS
            and not expander.resolve_wildcard_files(name)
        }
    )
    assert broken == [], f"{rel_path} references missing wildcards: {broken}"
