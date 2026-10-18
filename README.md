# wan2gp-wildcards

Wildcard prompt expansion plugin for [Wan2GP](https://github.com/deepbeepmeep/Wan2GP).

**3,017 wildcard files** · **313,000+ values** · **78 category directories** · **727 legacy aliases** · one-click local-LLM prompt generation.

> **v1.7.0** — Data-integrity release. Every broken nested reference is fixed, every path is
> lowercase (so the collection works on Linux/Colab, not just Windows), duplicates are gone, and a
> test suite plus a built-in auditor now guard the whole collection. Also new: an **AI Wildcard
> Generator** that invents new entries using Wan2GP's own local LLM (with a fully offline fallback),
> a **Linter** that audits both prompts and the collection, and safer file/character handling
> (no clobbering built-ins, no path traversal, atomic writes).

---

## Quick Reference

| Syntax | Effect | Example |
|---|---|---|
| `__name__` | Random line from `wildcards/name.txt` | `__camera/shot__` → `close-up shot` |
| `__dir__` | Random line from ALL files in `wildcards/dir/` | `__color__` → pooled from every color file |
| `__dir/file__` | Specific file in a subdirectory | `__color/named__` |
| `{a\|b\|c}` | Random inline choice | `{cinematic\|vintage\|raw}` |
| `N::value` | Weighted option inside a `.txt` file | `3::sunset` = 3× more likely |
| `__$var=value__` | Assign a literal to a **named variable** (no random) | `__$food=apple__` stores "apple" |
| `__$var:file__` | Pick from a file, store the result as a variable | `__$a:characters/names__` stores "Alice" |
| `__$var__` | Reuse a stored variable | `__$a__` → "Alice" again |

> 💡 **Every wildcard moved into category folders, but no old prompt breaks.** Names like
> `__camera_shot__` still resolve to `camera/shot` through the alias table and a case-insensitive
> fallback. Use the newer `__dir/file__` style for new prompts.

---

## How It Works

```
A __camera/shot__ of __$a:characters/names__ wearing a __color__ hat.
__$a__ smiles at __$b:characters/names__.

        │  plugin expands each reference
        ▼

A close-up shot of Alice wearing a crimson hat.
Alice smiles at Bob.

  __camera/shot__            random line from camera/shot.txt
  __color__                  random line pooled from every file in color/
  __$a:characters/names__    picks a name and stores it as $a
  __$a__                     reuses the stored $a, so it stays "Alice"
  __$b:characters/names__    picks a different name and stores it as $b
```

The same infographic is available as a [Mermaid diagram](docs/infographic-mermaid.md), a
[PNG](docs/infographic.png) and an [SVG](docs/infographic.svg).

### Captured variables — keep a character consistent

`__$var:file__` picks a value **and remembers it**. `__$var__` reuses that exact value anywhere else
in the same prompt, which is what makes "multiple people" prompting work:

```
Prompt:  __$person1:characters/names__ stands next to __$person2:characters/names__.
         __$person1__ wears a blue hat, __$person2__ wears a red hat.

Expands: Alice stands next to Bob.
         Alice wears a blue hat, Bob wears a red hat.
```

Values persist for the whole expansion, across sentences, wildcards and nested references.

### Manual control — `__$var=value__`

Set a variable by hand when you do not want a random pick. Nothing is randomised for that variable,
so it is ideal for batch runs where you change one or two values between generations:

```
Prompt:  An __$food=apple__ pie with a golden crust, __$food__ slices on top.
Expands: An apple pie with a golden crust, apple slices on top.
```

Change `__$food=apple__` to `__$food=cherry__` and every `__$food__` follows along.

---

## Install

1. **Plugins** tab → **Install New Plugin**
2. Paste: `https://github.com/GKartist75/wan2gp-wildcards`
3. Click **Download and Install**
4. Enable it → **Save Settings** → **Restart**

### Working from a source checkout

To run a local checkout inside Wan2GP without copying it, link the repository into the plugins
folder. On Windows a *junction* does the job and needs no administrator rights (a real symlink
does):

```bat
mklink /J "C:\Wan2GP\plugins\wan2gp-wildcards" "D:\dev\wan2gp-wildcards"
```

Wan2GP imports that folder as a Python package, so **the link name must match the repository
name** (`wan2gp-wildcards`). Restart Wan2GP, then enable **Wildcards** in Settings → Plugins.

---

## Usage Guide

The plugin adds one tab with eight sections: **Prompt Builder**, **Prompt Templates**,
**Character Profiles**, **Wildcard File Browser**, **Usage Stats**, **Cross-File Search**,
**Linter** and **AI Wildcard Generator**.

### 1. Prompt Builder

Type a template, pick a seed, hit **Generate 1 row** or **Generate N**.

* **Seed = -1** → random every time. A fixed seed → deterministic picks (same seed, same output).
* **Generate 1 row** renders a single prompt.
* **Generate N** fills the Variations box with `N` rows (1–100).
* **Send to Media Generator** copies the result into Wan2GP's main prompt box.
* The value panel shows clickable chips for the selected file. **Shuffle Values** reshuffles them
  (each click gives a fresh sample); **+ Insert `__file__`** inserts the reference at the cursor.
* **Inline autocomplete**: type `__` in the Prompt Template box and a dropdown of matching wildcards
  appears at the cursor. Arrow keys / Enter / Tab / click to insert, Escape to dismiss.

### 2. Prompt Templates

Save prompts with their wildcards **intact** (not expanded) and reload them later:
type a template, enter a name, **Save Current**; select one and **Load** to restore it.
**Delete** removes it. Stored in `wildcards/__templates__.json`.

### 3. Character Profiles

Named characters, each synced to a wildcard file so `__character/Name__` works like any other
wildcard.

* **Save** writes `wildcards/character/{Name}.txt` (one line per variation) and stores the profile
  in `characters/profiles.json`.
* Multi-line **appearance** becomes multiple variants of the wildcard.
* **Export JSON** / **Import JSON** round-trip all profiles. Imports are validated: unsafe names,
  non-object profiles and attempts to overwrite a shipped wildcard are skipped and reported.
* Names already used by a shipped wildcard in `wildcards/character/` (`age`, `archetype`, `body`,
  `gender`, `identity`, `phrase`, `profession`, `species`) are **reserved** — the UI lists them and
  refuses to overwrite them.
* Profiles are written atomically (temp file + rename), so a crash cannot truncate `profiles.json`.

### 4. Wildcard File Browser

* **Create** — new file; subdirectories are created automatically (`mytheme/sunset.txt`).
* **Rename** / **Save** / **Delete** — standard file management.
* **★ Toggle Favorite** + **★ Favorites only** — keep favourites handy.
* **Search** filters files by name.
* Create / Rename / Save reject absolute paths, `..` traversal, drive letters and Windows-reserved
  names, and refuse to touch the plugin's own `__`-prefixed metadata files.

### 5. Wildcard Usage Stats

`__stats__.json` tracks how often each wildcard file is used. Click
**Show Top 50 Used Wildcards** for your most-used pools. Counts are buffered in memory and flushed
when you leave the tab or exit the app — previews never pollute real usage counts.

### 6. Cross-File Content Search

Search the *contents* of every wildcard file at once (capped at 500 results, long lines skipped).

### 7. Linter

* **Check Prompt Template** — flags anything in the current template that resolves to nothing:
  a mistyped `__name__`, a `__$var:missing/file__` capture pointing at a pool that does not exist,
  or a `__$var__` used without ever being set. It uses the *real* resolver, so aliases and
  case-insensitive names resolve exactly as they will during generation.
* **Audit All Wildcard Files** — walks the whole collection and reports unresolved nested
  references, empty files, duplicate values and broken aliases. On a healthy collection it prints a
  one-line summary instead of a wall of text.

### 8. AI Wildcard Generator

Invent brand-new wildcard entries for any topic using **Wan2GP's own local LLM** — the Prompt
Enhancer / Qwen model that may already be installed with Wan2GP — or compose variations **offline**
from the wildcards you already have.

1. Enable the model in Wan2GP under *Configuration → Extensions → Prompt Enhancer / Deepy*.
2. **Check LLM** shows whether the model is available; **Load model now** warms it up (first load can
   take a while) and reports any load error.
3. Enter a **Topic** (e.g. `weathered neon street signs`) and optionally a **Style / vocabulary hint**
   (`cyberpunk, terse`), then set **Entries**, **Temperature** and a **Seed**.
4. **Generate with local LLM** asks the model for one short fragment per line; **Compose offline
   (no LLM)** does the same thing deterministically from your existing wildcard pools, so the
   feature always works even with no model loaded.
5. Edit the result freely, then **Save as file** (e.g. `mytheme/neon-signs`), **Send to Prompt
   Template**, or **Send to Variations box**.

Nothing is sent to the internet: the generator reuses Wan2GP's local model runtime.

---

## Testing

```bash
python -m pytest          # from the repo root
```

You can also run it from inside `tests/`. No Wan2GP install is required — the tests stub the Gradio
and `shared.*` imports and exercise the real `expander`, `linter`, `ai`, `character_manager` and
`plugin` modules.

The suite includes collection-wide integrity checks that fail the build if anyone
re-introduces a broken nested reference, an uppercase path, a duplicate value, trailing whitespace, a
non-UTF-8 file, or a documentation example that points at a wildcard that does not exist.

### Repository layout

| File | Purpose |
|---|---|
| `plugin.py` | Gradio tab, Wan2GP integration, file/character operations |
| `expander.py` | The expansion engine (aliases, captures, caching, resolution) |
| `aliases.py` | The 727 legacy-name → path table |
| `ai.py` | Offline composer + adapter for Wan2GP's local prompt-enhancer LLM |
| `linter.py` | Prompt and collection linting |
| `character_manager.py` | Profile store + wildcard sync |
| `wildcards/` | The collection itself (`__index__.txt` is a human-readable catalog) |
| `tests/` | pytest suite |

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| A `__name__` stays literal in the output | The reference resolved to nothing. Run **Check Prompt Template**, or **Audit All Wildcard Files** if it came from inside a wildcard file. |
| `__name__` turned into nothing | The file exists but has no usable lines (comments only). The auditor flags these as empty files. |
| Old prompt with `__camera_shot__` stopped working | It should not — legacy names resolve through `aliases.py`. If one is genuinely missing, run **Audit All Wildcard Files** to see the broken alias. |
| Values only work on Windows (e.g. in Colab they don't) | Paths are all lowercase and lookups are case-insensitive, so this should not happen any more; the integrity test enforces it. |
| **Generate with local LLM** says the host API is not exposed | The plugin could not reach Wan2GP's prompt-enhancer runtime — usually because Wan2GP is older than the plugin expects. Use **Compose offline (no LLM)** instead. |
| AI generation is slow or errors on the first try | The model is loading. Use **Load model now** and watch the status box; the error is reported verbatim. |
| Usage stats stay at zero | Stats are disabled while generating previews and are flushed on tab change / exit. Give it a moment, or click **Show Top 50 Used Wildcards** to force a flush. |

---

## Changelog

### v1.7.0 — Data integrity, AI generation, auditing

* **Data**: repaired every broken nested reference (AD&D, Cthulhu, wings), removed duplicate values
  and empty files, stripped trailing whitespace, and verified all 3,017 files decode as UTF-8.
* **Cross-platform**: all 521 uppercase wildcard paths are now lowercase. On case-sensitive
  filesystems (Linux, Colab, Docker) those lookups previously fell through to literal `__name__`
  text. A case-insensitive resolution fallback covers prompts written with any casing.
* **Engine**: `expander.py` slimmed down (aliases extracted to `aliases.py`), hardened against
  recursion, unreadable directories and Windows-reserved filenames, with a bounded thread-safe file
  cache and a public `capture_files()` / `reference_names()` API.
* **AI Wildcard Generator**: new section that generates wildcard entries with Wan2GP's local LLM
  (Prompt Enhancer / Qwen) or fully offline from the existing pools.
* **Linter**: new section with **Check Prompt Template** and **Audit All Wildcard Files**; the
  collection report covers unresolved references, empty files, duplicates and broken aliases.
* **Safety**: Create/Rename/Save reject traversal, absolute paths and reserved names; character
  profiles can no longer clobber shipped wildcards; profile and template writes are atomic.
* **Robustness**: reports and status messages are ASCII-safe (Windows consoles default to cp1252),
  and a plain `pytest` now works from the repo root thanks to a root `pytest.ini`.
* **Wan2GP integration**: `create_ui` no longer declares an unused API-session parameter. Wan2GP
  inspects that signature and, if it looks API-aware, wraps every button in the tab as a job
  callback; the parameter was never used and (through a Wan2GP mis-detection of `None` globals)
  wrapped the Generate button, which then required main-UI bridge components. A test now pins the
  signature.
* **Hygiene**: `wildcards/__stats__.json` is gitignored and no longer tracked — it is per-machine
  usage data, not collection data.
* **Docs**: accurate index and stats, no duplicated infographic, new troubleshooting section.
* **Tests**: 137 tests, including collection-wide integrity checks, the plain-constructor guard and
  a CI workflow.

### v1.6.4 — Bug fixes, performance, prompt linter

* **Bug**: weighted `N::value` picks now require a *numeric* prefix; `a movie:: style` is kept
  verbatim instead of becoming ` style`.
* **Bug**: Create / Rename / Save reject path traversal (`../`, absolute paths, drive letters).
* **Bug**: character import validates every entry — bad names and malformed profiles are skipped
  with a count instead of crashing or writing bad data.
* **Bug**: all-zero/negative weights fall back to a uniform pick (no `ValueError`).
* **Bug**: random batch mode honours the Seed box (deterministic sub-seeds).
* **Bug**: sequential mode strips `N::` weight prefixes (no more leaked `3::`).
* **Perf**: wildcard file contents cached with mtime/size invalidation; file listing cached with a
  TTL, so the search box no longer walks 3,000+ files per keystroke; content search capped; value
  chips use a stride sample instead of shuffling multi-MB files.
* **Stats**: usage counts are buffered and flushed on tab select / exit; previews no longer pollute
  real counts.
* **Lint**: new **Check Prompt Template** button flags references that resolve to no file.

### v1.6.3 — Literal variable assignment

* New `__$var=value__` syntax sets a variable to a literal with no random pick.
* `__$food=apple__` (manual) and `__$food:fruit__` (random) share one variable namespace.

### v1.6.2 — File reorganisation

* All flat files moved into 78 category directories; 727 backward-compat aliases; duplicate
  categories merged; lowercase hyphenated names; all adult content consolidated under `nsfw/`.

### v1.6.1 — Bug fixes and cleanup

* Fixed Gradio crashes in `_load_char` / `_clear_char_form` / `_import_characters` return arity.
* Import JSON now waits for paste → Enter instead of firing on an empty box.
* Atomic writes for stats and favourites.
* Normalised uppercase filenames/dirs to lowercase.
* Removed dead code and duplicate lines; populated an empty wildcard file.

### v1.6.0 — Captured variables and templates

* Named capture variables `__$var:file__` / `__$var__` (fixes multi-person prompting).
* Prompt templates, file rename, usage stats, character export/import.
* Send to Media Generator uses Wan2GP's State API; line counts shown in the file list.

### v1.5.x

* Chip/hint visibility on dark themes, JS cleanup, reliable Send to Media Generator.

### v1.4.0 — Visual explorer

* Category → file → clickable value chips; random-mode dedup; path separator fix.

### v1.3.0

* UI reorder, searchable file browser, favourites, cross-file content search.

### v1.2.0

* Merged the remaining wildcard collections; sequential mode and weight detection fixes.

### v1.1.0

* Character profile manager and inline autocomplete.

---

## Credits

Author: GKartist75 (with PI Agent)
Built in collaboration with [PI Agent](https://github.com/earendil-works/pi-coding-agent).

## Requirements

Wan2GP only. No external dependencies. The AI Wildcard Generator requires the Prompt Enhancer /
Deepy extension to be enabled in Wan2GP; everything else — including the offline composer — works
without it.
