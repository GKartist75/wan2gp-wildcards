# wan2gp-wildcards

Wildcard prompt expansion plugin for [Wan2GP](https://github.com/deepbeepmeep/Wan2GP).

**3,017 wildcard files** · **313,700+ values** · **78 category directories** · **727 legacy aliases** · one-click local-LLM prompt generation.

> **v1.7.2** — Engine-correctness release. The expansion passes now reach a real fixed point, so a
> `__$var=value__` set inside a referenced file (or a capture whose pool name came out of a `{a|b}`
> choice) resolves instead of leaking as literal text; a runaway-cycle budget replaces the fan-out
> explosion that could freeze the UI for minutes; `x.txt` beats a same-named `x/` directory; the
> partial-name fallback can no longer read outside the collection; files are read as UTF-8 with a BOM
> and cp1252 tolerance. The collection itself lost 119 case-variant duplicates, and `__index__.txt`
> now lists the 348 folders that sit below the second level.

> **v1.7.1** — Data-integrity release. Every broken nested reference is fixed, every path is
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

> 💡 **If a pool ships both `name.txt` and a `name/` folder, the file wins.** Five pairs exist
> (`body/ears`, `nsfw/positions`, `nsfw/panties`, `nsfw/sex-acts`, `clothing/period/victorian/female`);
> `__nsfw/positions__` is the list in `positions.txt`, and the folder's contents stay reachable as
> `__nsfw/positions/<file>__`.

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

Values persist for the whole expansion, across sentences, wildcards and nested references — including
a `__$var=value__` or `__$var:file__` that lives inside a wildcard file you reference, so a shared
"casting" file can set the cast once and the rest of the prompt can reuse it.

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

The plugin adds one tab with eight sections: **Prompt Builder**, **AI Wildcard Generator**,
**Prompt Templates**, **Character Profiles**, **Wildcard File Browser**, **Usage Stats**,
**Cross-File Search** and **Linter**.

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

### 2. AI Wildcard Generator

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

### 3. Prompt Templates

Save prompts with their wildcards **intact** (not expanded) and reload them later:
type a template, enter a name, **Save Current**; select one and **Load** to restore it.
**Delete** removes it. Stored in `wildcards/__templates__.json`.

### 4. Character Profiles

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

### 5. Wildcard File Browser

* **Create** — new file; subdirectories are created automatically (`mytheme/sunset.txt`).
* **Rename** / **Save** / **Delete** — standard file management.
* **★ Toggle Favorite** + **★ Favorites only** — keep favourites handy.
* **Search** filters files by name.
* Create / Rename / Save reject absolute paths, `..` traversal, drive letters, `:` in any path
  component (Windows silently drops a `C:` inside a name) and Windows-reserved names, and refuse to
  touch the plugin's own `__`-prefixed metadata files.

### 6. Wildcard Usage Stats

`__stats__.json` tracks how often each wildcard file is used. Click
**Show Top 50 Used Wildcards** for your most-used pools. Counts are buffered in memory and flushed
when you leave the tab or exit the app — previews never pollute real usage counts.

### 7. Cross-File Content Search

Search the *contents* of every wildcard file at once (capped at 500 results, long lines skipped).

### 8. Linter

* **Check Prompt Template** — flags anything in the current template that resolves to nothing:
  a mistyped `__name__`, a `__$var:missing/file__` capture pointing at a pool that does not exist,
  or a `__$var__` used without ever being set. It uses the *real* resolver, so aliases and
  case-insensitive names resolve exactly as they will during generation.
* **Audit All Wildcard Files** — walks the whole collection and reports unresolved nested
  references, `__$var:file__` capture pools that point at nothing, empty files, duplicate values,
  case-only variants of the same value (one artist listed as `Frances Macdonald` and
  `Frances MacDonald` would be drawn twice as often) and broken aliases. On a healthy collection it
  prints a one-line summary instead of a wall of text.

---

## Testing

```bash
python -m pytest          # from the repo root: 161 tests
```

You can also run it from inside `tests/`. No Wan2GP install is required — the tests stub the Gradio
and `shared.*` imports and exercise the real `expander`, `linter`, `ai`, `character_manager` and
`plugin` modules. CI runs the suite on Windows and Linux, on Python 3.10 and 3.13.

The suite includes collection-wide integrity checks that fail the build if anyone
re-introduces a broken nested reference, a capture pool that points at nothing, an uppercase path, a
duplicate or case-variant value, trailing whitespace, a non-UTF-8 file, or a documentation example
that points at a wildcard that does not exist. The collection floors are pinned to the real numbers
(3,017 files, 727 aliases), so a bulk delete fails the build instead of passing quietly.

### Optional: the real Wan2GP loader

`tests/integration_wan2gp.py` does not use the stubs. It drives the plugin through Wan2GP's own
loader and Gradio, so it checks what the unit suite cannot: the import path for a hyphenated plugin
directory, the constructor-signature contract with `create_ui`, that the tab really renders, that its
sections appear in the documented order, and that expansion fires inside Wan2GP's own
`prompt_parser`. Run it with Wan2GP's interpreter:

```bash
C:\Wan2GP\env_uv\Scripts\python.exe tests\integration_wan2gp.py
```

Set `WAN2GP_ROOT` (and optionally `WAN2GP_PLUGIN_ID`) if Wan2GP lives elsewhere. It exits non-zero
and names every failed check.

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
| `tests/` | pytest suite, plus `integration_wan2gp.py` for real-loader checks |

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| A `__name__` stays literal in the output | The reference resolved to nothing. Run **Check Prompt Template**, or **Audit All Wildcard Files** if it came from inside a wildcard file. |
| `__name__` turned into nothing | The file exists but has no usable lines (comments only). The auditor flags these as empty files. |
| Old prompt with `__camera_shot__` stopped working | It should not — legacy names resolve through `aliases.py`. If one is genuinely missing, run **Audit All Wildcard Files** to see the broken alias. |
| Values only work on Windows (e.g. in Colab they don't) | Paths are all lowercase and lookups are case-insensitive, so this should not happen any more; the integrity test enforces it. |
| `__nsfw/positions__` returns a short list instead of the folder's files | By design: when both `positions.txt` and `positions/` exist, the file wins. Reference the folder's files as `__nsfw/positions/<file>__`. |
| **Generate with local LLM** says the host API is not exposed | The plugin could not reach Wan2GP's prompt-enhancer runtime — usually because Wan2GP is older than the plugin expects. Use **Compose offline (no LLM)** instead. |
| AI generation is slow or errors on the first try | The model is loading. Use **Load model now** and watch the status box; the error is reported verbatim. |
| Usage stats stay at zero | Stats are disabled while generating previews and are flushed on tab change / exit. Give it a moment, or click **Show Top 50 Used Wildcards** to force a flush. |

---

## Changelog

### v1.7.2 — Engine correctness, deduped collection, honest index

* **Engine / capture ordering**: the passes now repeat until the text stops changing. A later pass can
  produce syntax an earlier one owns, so a `__$var=value__` **inside a referenced file**, and a
  `__$var:{a|b}/pool__` whose pool name only exists *after* the variant is chosen, both used to be
  left as literal `__$var__` text even though the value had already been stored — the README promised
  the opposite.
* **Engine / runaway cycles**: `DEPTH_LIMIT` bounds nesting depth, not fan-out — a file with *k*
  references per line cost roughly *k*^10 substitutions (minutes of a frozen UI, with no error). Every
  top-level expansion now draws from a fixed work budget, and a substitution that cannot be expanded
  is skipped instead of being re-expanded by the next pass, which is what made the text explode.
  Legitimate nested prompts are unaffected: 200 references in a single prompt still expand in 0.04 s
  with nothing left literal, while the worst-case cycle is now capped at ~130 KB and 0.5 s.
* **Engine / file over directory**: five pools ship both `x.txt` and `x/` (`body/ears`,
  `nsfw/positions`, `nsfw/panties`, `nsfw/sex-acts`, `clothing/period/victorian/female`). The file now
  wins. Before, the glob fallback or-ed both paths, so the file was also pooled through the directory
  and drawn twice, and `__clothing/period/victorian/female__` silently returned *male* attire.
* **Engine / path safety**: the partial-name glob fallback now refuses `..` segments, so a prompt that
  tries to climb out of the collection cannot pull a `.txt` file that sits next to it. The UI
  validator already refused it; prompt text never went through that validator.
* **Engine / encoding**: files are read as `utf-8-sig` with `errors="replace"`. A BOM used to survive
  `strip()`, so a file whose first line was `# comment` served the comment as a value; and one cp1252
  file aborted the whole generation with `UnicodeDecodeError` while the audit called the collection
  healthy.
* **Engine / adjacent references**: the reference name class is non-greedy, so two references written
  back to back expand as two references instead of being read as one unresolvable name and leaking
  into the prompt as literal text.
* **Data**: 119 case/Unicode-variant duplicate lines removed across 19 files — the same artist,
  nationality, colour or phrase listed twice in two spellings (`Frances Macdonald` /
  `Frances MacDonald`) meant that value was drawn twice as often as every other entry in its pool.
  The collection now audits at 0 unresolved references, 0 exact duplicates, 0 case variants.
* **Linter**: the collection audit also checks `__$var:file__` capture pools inside files (it only
  looked at `__name__` references), and reports case-insensitive duplicates as a distinct class.
* **AI generator**: markdown replies are cleaned before saving — `**bold**`, `*emphasis*` and table
  rows (`| sunset |`, `| --- |`) no longer end up inside wildcard files and every prompt drawn from them.
* **UI robustness**: an emptied Gradio number field arrives as `None` and used to raise `TypeError`
  inside `seed >= 0` / `int(count)`; numeric handlers now fall back to their field defaults. A
  foreign or hand-edited `__favorites__.json` / `__templates__.json` / `__stats__.json` is ignored
  instead of breaking the tab (previously `AttributeError` on ★ Toggle, `TypeError` on Show Top 50).
* **Safety**: `:` is now rejected in *every* path component, not just at the start. On Windows
  `sub/C:name` is a drive-relative name whose colon the OS drops, so the write landed in a
  differently-named file and slipped past the reserved-metadata rule.
* **Safety**: `__templates__.json` is written atomically (temp file + `os.replace`) and reports
  failure, so a crash mid-save can no longer truncate every saved template; a failed save also leaves
  no temp file behind. Favourites, stats and character profiles already worked this way.
* **Docs**: `wildcards/__index__.txt` now catalogs the 348 folders below the second level (only
  top-level subfolders were described before, so four fifths of the deeper pools were invisible in
  the index), documents that the per-folder counts are recursive, and states the format it actually
  uses.
* **Hygiene**: `wildcards/__favorites__.json` and `wildcards/__templates__.json` are gitignored next
  to `__stats__.json` — all three are per-machine runtime state, not collection data.
* **Tests**: 161 tests (139 before). New regression tests cover every fix above; the collection floors
  were tightened to the real numbers (3,017 files, 727 aliases, 78 folders) and a vacuous
  "module loaded" assertion plus a dead conftest option were removed.

### v1.7.1 — Case-insensitive lookup fixed on Linux

* **Bug**: a wrong-case reference such as `__CAMERA/SHOT__` returned literal text on Linux, Colab and
  Docker while working fine on Windows. Segment matching compared `SHOT` against the file `shot.txt`
  and gave up, then fell through to a `glob` that only forgives the wrong case on a case-insensitive
  filesystem. The resolver now also matches a `.txt` stem, so the lookup no longer depends on the
  host filesystem at all. Found by the new Linux CI job on its very first run.
* **Bug**: the same assumption hid in the character guard: on Linux a profile named `ARIA` slipped
  past the check that protects a shipped `character/aria.txt` (on Windows both names are one file).
  The guard now compares against the directory listing, so a profile can never shadow a built-in.
* **Tests**: 139 tests. The new regression test swaps in a strict, Linux-like `glob`, so this class of
  bug now fails on Windows too instead of hiding until CI.

### v1.7.0 — Data integrity, AI generation, auditing

* **Data**: repaired every broken nested reference (AD&D, Cthulhu, wings), removed duplicate values
  and empty files, stripped trailing whitespace, and verified all 3,017 files decode as UTF-8.
* **Cross-platform**: all 521 uppercase wildcard paths are now lowercase. On case-sensitive
  filesystems (Linux, Colab, Docker) those lookups previously fell through to literal `__name__`
  text. A case-insensitive resolution fallback covers prompts written with any casing (the file-segment
  half of that fallback was still Windows-only until v1.7.1).
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
* **Layout**: the **AI Wildcard Generator** moved up to section 2, directly after the Prompt Builder,
  since it is the first thing most people reach for; templates and the auditing tools follow.
* **Docs**: accurate index and stats, no duplicated infographic, new troubleshooting section.
* **Tests**: 139 unit tests, collection-wide integrity checks, a guard pinning the `create_ui`
  signature, an optional `tests/integration_wan2gp.py` that drives the real Wan2GP loader and Gradio
  (that is what caught the wrongly wrapped Generate button), and CI on Windows + Linux.

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
