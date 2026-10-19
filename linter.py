"""Offline linters for prompts and for the wildcard collection itself.

Pure Python (no gradio, no Wan2GP, no torch) so the same code powers the plugin
UI and the test-suite. Nothing here raises on bad data: every problem is
collected into a report.
"""

from __future__ import annotations

import os
import unicodedata
from collections import Counter

try:  # imported as part of the package (plugin runtime, tests)
    from . import expander
except ImportError:  # imported as a top-level module (ad-hoc tooling)
    import expander

MAX_DETAILS = 40  # rows shown per problem class in the text reports


# --------------------------------------------------------------------------
# Prompt linting
# --------------------------------------------------------------------------

def lint_text(text: str) -> dict:
    """Analyse a single prompt/template.

    Returns a report with unresolved references, unresolved captures and
    ``__$var__`` variables that are never assigned. This is a superset of the
    original prompt linter (which only checked ``__name__`` references).
    """
    text = str(text or "")
    references = expander.reference_names(text)
    missing = [n for n in references if not expander.resolve_wildcard_files(n)]

    capture_files = expander.capture_files(text)
    missing_captures = [f for f in capture_files if not expander.resolve_wildcard_files(f)]

    assigned: list[str] = []
    for match in expander.CAPTURE_ANY_RE.finditer(text):
        var = match.group(1) or match.group(3)
        if var and var not in assigned:
            assigned.append(var)
    used: list[str] = []
    for match in expander.CAPTURE_GET_RE.finditer(text):
        var = match.group(1)
        if var and var not in used:
            used.append(var)
    unset = [v for v in used if v not in assigned]

    variants = sum(1 for m in expander.VARIANT_RE.finditer(text) if m.group(1).count("|") > 0)

    return {
        "references": references,
        "missing": missing,
        "capture_files": capture_files,
        "missing_captures": missing_captures,
        "assigned_variables": assigned,
        "used_variables": used,
        "unset_variables": unset,
        "variants": variants,
        "ok": not (missing or missing_captures),
    }


def format_text_report(report: dict) -> str:
    """Human-readable version of :func:`lint_text`."""
    if not (
        report["references"]
        or report["capture_files"]
        or report["variants"]
        or report["unset_variables"]
    ):
        return "No __wildcard__, __$capture__ or {variant} syntax found."

    lines = [
        f"{len(report['references'])} wildcard reference(s), "
        f"{len(report['capture_files'])} capture(s), {report['variants']} inline variant(s)."
    ]

    if report["missing"]:
        lines.append(f"FAIL: {len(report['missing'])} reference(s) NOT found on disk:")
        lines += [f"    __{m}__" for m in report["missing"][:MAX_DETAILS]]
        if len(report["missing"]) > MAX_DETAILS:
            lines.append(f"    ... and {len(report['missing']) - MAX_DETAILS} more")
        lines.append("  Tip: old flat names (e.g. __camera_shot__) still resolve through aliases.")
    if report["missing_captures"]:
        lines.append(f"FAIL: {len(report['missing_captures'])} capture file(s) NOT found:")
        lines += [f"    {f}" for f in report["missing_captures"][:MAX_DETAILS]]
    if report["unset_variables"]:
        lines.append(f"WARN: {len(report['unset_variables'])} variable(s) used with __$var__ but never set:")
        lines += [f"    ${v}" for v in report["unset_variables"][:MAX_DETAILS]]
        lines.append("  (Set them with __$var:file__ or __$var=value__ before use.)")

    if report["ok"]:
        lines.insert(0, "OK: All references resolve.")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Collection linting
# --------------------------------------------------------------------------

def _display_path(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except Exception:  # pragma: no cover - defensive
        return str(path)


def lint_files(paths, root: str | None = None, *, check_duplicates: bool = True) -> dict:
    """Lint a list of wildcard files.

    Reports unresolved nested references (``__name__`` and the ``__$var:file__``
    captures the engine also resolves inside files), whitespace-insensitive
    duplicate lines and empty files. Resolution results are memoised because a
    large collection repeats the same reference names thousands of times.
    """
    root = root or expander.WILDCARDS_DIR
    resolved: dict[str, bool] = {}

    def resolves(name: str) -> bool:
        hit = resolved.get(name)
        if hit is None:
            hit = bool(expander.resolve_wildcard_files(name))
            resolved[name] = hit
        return hit

    broken: list[dict] = []
    duplicates: list[dict] = []
    near_duplicates: list[dict] = []
    empty_files: list[str] = []
    files_scanned = 0
    lines_scanned = 0

    for path in paths:
        display = _display_path(path, root)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
                raw_lines = handle.read().split("\n")
        except OSError:
            continue
        files_scanned += 1

        counts: Counter = Counter()
        first_seen: dict[str, int] = {}
        # Whitespace/case/Unicode-normalisation-insensitive view of the same
        # lines: "Frances Macdonald" and "Frances MacDonald" are one artist to a
        # reader (and both get drawn), but an exact-string counter sees two.
        folded: Counter = Counter()
        folded_first: dict[str, tuple[str, int]] = {}
        folded_texts: dict[str, set[str]] = {}
        values = 0
        for number, raw in enumerate(raw_lines, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            values += 1
            lines_scanned += 1
            if check_duplicates:
                counts[line] += 1
                if counts[line] == 1:
                    first_seen[line] = number
                key = unicodedata.normalize("NFKC", line).casefold()
                folded[key] += 1
                if folded[key] == 1:
                    folded_first[key] = (line, number)
                folded_texts.setdefault(key, set()).add(line)
            for name in expander.reference_names(line) + expander.capture_files(line):
                if not resolves(name):
                    broken.append({"file": display, "line": number, "name": name})

        if check_duplicates:
            for text, count in counts.items():
                if count > 1:
                    duplicates.append(
                        {"file": display, "line": first_seen[text], "text": text, "count": count}
                    )
            for key, count in folded.items():
                # Only spellings that differ beyond case/normalisation are
                # interesting; byte-identical repeats are already reported above.
                if count > 1 and len(folded_texts[key]) > 1:
                    text, number = folded_first[key]
                    near_duplicates.append(
                        {"file": display, "line": number, "text": text, "count": count}
                    )
        if values == 0:
            empty_files.append(display)

    duplicates.sort(key=lambda d: (d["file"], d["line"]))
    near_duplicates.sort(key=lambda d: (d["file"], d["line"]))
    return {
        "files": files_scanned,
        "lines": lines_scanned,
        "broken": broken,
        "broken_total": len(broken),
        "duplicates": duplicates,
        "duplicate_total": len(duplicates),
        "near_duplicates": near_duplicates,
        "near_duplicate_total": len(near_duplicates),
        "empty_files": empty_files,
        # near_duplicates are reported but do not fail the audit: the collection
        # is curated data, and only an exact repeat is unambiguously a defect.
        "ok": not broken and not empty_files,
    }


def lint_collection(root: str | None = None) -> dict:
    """Lint every wildcard file plus the alias table."""
    root = root or expander.WILDCARDS_DIR
    report = lint_files(expander.iter_wildcard_files(root), root)

    unresolved_aliases = []
    for alias, target in sorted(expander.WILDCARD_ALIASES.items()):
        if not expander.resolve_wildcard_files(alias):
            unresolved_aliases.append({"alias": alias, "target": target})
    report["aliases"] = len(expander.WILDCARD_ALIASES)
    report["unresolved_aliases"] = unresolved_aliases
    report["unresolved_aliases_total"] = len(unresolved_aliases)
    report["ok"] = report["ok"] and not unresolved_aliases
    return report


def format_collection_report(report: dict) -> str:
    """Human-readable version of :func:`lint_collection`."""
    lines = [
        f"Scanned {report['files']} file(s), {report['lines']} value line(s), "
        f"{report.get('aliases', 0)} alias(es)."
    ]

    if report["empty_files"]:
        lines.append(f"WARN: {len(report['empty_files'])} empty file(s) (no usable values):")
        lines += [f"    {f}" for f in report["empty_files"][:MAX_DETAILS]]

    if report["broken"]:
        lines.append(f"FAIL: {report['broken_total']} unresolved __reference__(s):")
        lines += [
            f"    {b['file']}:{b['line']}: __{b['name']}__"
            for b in report["broken"][:MAX_DETAILS]
        ]
        if report["broken_total"] > MAX_DETAILS:
            lines.append(f"    ... and {report['broken_total'] - MAX_DETAILS} more")
    else:
        lines.append("OK: Every nested __reference__ resolves.")

    if report.get("unresolved_aliases"):
        lines.append(f"FAIL: {report['unresolved_aliases_total']} broken alias(es):")
        lines += [
            f"    {a['alias']} -> {a['target']}"
            for a in report["unresolved_aliases"][:MAX_DETAILS]
        ]
    else:
        lines.append(f"OK: All {report.get('aliases', 0)} aliases resolve.")

    if report["duplicates"]:
        shown = report["duplicates"][:MAX_DETAILS]
        lines.append(f"WARN: {report['duplicate_total']} duplicate value(s) inside a file:")
        lines += [f"    {d['file']}:{d['line']} x{d.get('count', 2)}: {d['text'][:80]}" for d in shown]
        if report["duplicate_total"] > MAX_DETAILS:
            lines.append(f"    ... and {report['duplicate_total'] - MAX_DETAILS} more")
    else:
        lines.append("OK: No duplicate values inside any file.")

    if report.get("near_duplicates"):
        shown = report["near_duplicates"][:MAX_DETAILS]
        lines.append(
            f"WARN: {report['near_duplicate_total']} value(s) repeat a different spelling "
            "(same text ignoring case/unicode normalisation) — drawn twice per pick:"
        )
        lines += [f"    {d['file']}:{d['line']}: {d['text'][:80]}" for d in shown]
        if report["near_duplicate_total"] > MAX_DETAILS:
            lines.append(f"    ... and {report['near_duplicate_total'] - MAX_DETAILS} more")

    if report["ok"]:
        lines.insert(0, "OK: Collection is healthy.")
    else:
        lines.insert(0, "WARN: Collection has issues (details below).")
    return "\n".join(lines)
