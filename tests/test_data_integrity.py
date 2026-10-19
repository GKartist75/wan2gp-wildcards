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
    # A floor, not a target: it catches a bulk delete or a filter that stops
    # seeing subfolders. Raise it when the collection grows.
    assert len(files) >= 3017, f"collection shrank: only found {len(files)} wildcard files"


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
    assert collection["aliases"] >= 727


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
    # …and the reference regex itself must accept a nested, hyphenated name
    # without swallowing the double underscores that delimit it.
    assert expander.WILDCARD_RE.findall("a __camera/shot__ b __color__") == ["camera/shot", "color"]


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


def test_no_case_variant_duplicates(collection):
    """One pool must not list the same value twice in two spellings.

    ``Frances Macdonald`` and ``Frances MacDonald`` are one artist to a reader
    but two entries to the engine, so the value was drawn twice as often as its
    neighbours.
    """
    details = "\n".join(
        f"  {d['file']}:{d['line']} x{d['count']}: {d['text']}"
        for d in collection["near_duplicates"][:20]
    )
    assert collection["near_duplicate_total"] == 0, (
        f"{collection['near_duplicate_total']} value(s) appear twice in one file"
        f" differing only in case/Unicode normalisation:\n{details}"
    )


def test_a_file_beats_a_same_named_directory():
    """Five pools ship both ``x.txt`` and ``x/``; the file must win.

    Before the fix the glob fallback or-ed both, so the file was also pooled
    through the directory and drawn twice ("close-up" appearing twice as often
    as every other shot), and the greedy name class then leaked the trailing
    ``____`` as a literal.
    """
    for name in ("body/ears", "clothing/period/victorian/female", "nsfw/panties",
                 "nsfw/positions", "nsfw/sex-acts"):
        file_path = os.path.join(WILDCARDS, name + ".txt")
        dir_path = os.path.join(WILDCARDS, name)
        assert os.path.isfile(file_path) and os.path.isdir(dir_path), f"expected a pair at {name}"
        hits = expander.resolve_wildcard_files(name)
        assert [os.path.normcase(h) for h in hits] == [os.path.normcase(file_path)], (
            f"__{name}__ should resolve to its file only, got {hits}"
        )
        # The directory stays usable through a file inside it.
        inner = next(
            f for f in sorted(os.listdir(dir_path))
            if f.endswith(".txt") and not f.startswith("__")
        )
        assert expander.resolve_wildcard_files(f"{name}/{inner[:-4]}"), f"{name}/{inner} unreachable"


def test_a_directory_pool_is_reachable_by_its_own_name():
    """``__color__`` must pool every file in ``color/`` (dirs are wildcards too)."""
    expander.invalidate_cache()
    for name in ("color", "lighting", "art"):
        assert not os.path.isfile(os.path.join(WILDCARDS, name + ".txt")), (
            f"{name}.txt exists, so name-directory precedence covers this case"
        )
        hits = expander.resolve_wildcard_files(name)
        assert len(hits) > 1, f"__{name}__ did not pool its directory: {hits}"
        assert all(os.path.isfile(h) for h in hits)


REF_RE = re.compile(r"__([a-zA-Z0-9_/.\-]+)__")


@pytest.mark.parametrize(
    "rel_path", ["README.md", "docs/infographic-mermaid.md", "wildcards/__index__.txt"]
)
def test_documentation_references_resolve(rel_path, collection):
    """Docs must not advertise wildcards that don't exist."""
    path = os.path.join(REPO_ROOT, rel_path)
    assert os.path.isfile(path), f"{rel_path} is documented but missing"
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
