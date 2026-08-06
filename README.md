# wan2gp-wildcards

Wildcard prompt expansion plugin for [Wan2GP](https://github.com/deepbeepmeep/Wan2GP).  
**149,000+ terms** across **3,019 files** organized into **78 category directories**.

> **v1.6.3** — Set variables manually: `__$food=apple__` assigns a literal value (no random pick),
> reuse it anywhere via `__$food__`. Perfect for batch runs where you change one or two values between generations.

---

## Quick Reference

| Syntax | Effect | Example |
|---|---|---|
| `__name__` | Random line from `wildcards/name.txt` | `__camera/shot__` → `close-up shot` |
| `__dir__` | Random line from ALL files in `wildcards/dir/` | `__color__` → pooled from all color files |
| `__dir/file__` | Specific file in subdirectory | `__color/named__` |
| `{a\|b\|c}` | Random inline choice | `{cinematic\|vintage\|raw}` |
| `N::value` | Weighted option (weight N) | `3::sunset` = 3× more likely |
| `__$var=value__` | Assign a literal value to a **named variable** (manual, no random) | `__$food=apple__` → stores "apple" as `$food` |
| `__$var:file__` | Pick from file, store result as **named variable** | `__$a:name__` → stores "Alice" as `$a` |
| `__$var__` | Reuse previously stored variable | `__$a__` → "Alice" again |

> 💡 **All existing wildcards moved.** Old names like `__camera_shot__` still work
> automatically — no prompt changes needed. Use the new `__dir/file__` style going forward.

---

## Infographic — How Wildcards Work

```
┌─────────────────────────────────────────────────────┐
│  Prompt Template (what you type)                     │
│                                                      │
│  A __camera_shot__ of __$a:name__ wearing a          │
│  __color__ hat. __$a__ smiles at __$b:name__.        │
│                                                      │
│  ↓  Wildcard Plugin expands each wildcard            │
│                                                      │
│  A close-up shot of Alice wearing a crimson hat.     │
│  Alice smiles at Bob.                                │
│                                                      │
│  Key: __camera_shot__ → random from camera/shot.txt  │
│       __$a:name__   → picks & stores "Alice"         │
│       __$a__        → reuses "Alice" (same pick)     │
│       __$b:name__   → picks & stores "Bob"           │
│       __color__     → random from color pool         │
└─────────────────────────────────────────────────────┘
```

### Also available as:

| Format | File | Preview |
|---|---|---|
| **A — Mermaid** | [`docs/infographic-mermaid.md`](docs/infographic-mermaid.md) | Renders as flowchart on GitHub |
| **B — PNG** | `docs/infographic.png` | 900×700 dark-themed image |
| **C — SVG** | `docs/infographic.svg` | Scales perfectly, renders inline |

```
┌─────────────────────────────────────────────────────┐
│  Prompt Template (what you type)                     │
│                                                      │
│  A __camera_shot__ of __$a:name__ wearing a          │
│  __color__ hat. __$a__ smiles at __$b:name__.        │
│                                                      │
│  ↓  Wildcard Plugin expands each wildcard            │
│                                                      │
│  A close-up shot of Alice wearing a crimson hat.     │
│  Alice smiles at Bob.                                │
│                                                      │
│  Key: __camera_shot__ → random from camera/shot.txt  │
│       __$a:name__   → picks & stores "Alice"         │
│       __$a__        → reuses "Alice" (same pick)     │
│       __$b:name__   → picks & stores "Bob"           │
│       __color__     → random from color pool         │
└─────────────────────────────────────────────────────┘
```

### Captured Variables — The Big New Feature

Use `__$var:file__` to pick a value AND remember it. Then use `__$var__` to reuse:

```
Prompt:  __$person1:name__ stands next to __$person2:name__.
         __$person1__ wears a blue hat, __$person2__ wears a red hat.

Expands: Alice stands next to Bob.
         Alice wears a blue hat, Bob wears a red hat.
```

Each variable keeps its value throughout the entire prompt expansion — even across sentences.

#### Manual control: `__$var=value__`

Don't want a random pick? Set the variable by hand with `__$var=value__` — great for batch runs where you change one or two values between generations:

```
Prompt:  An __$food=apple__ pie with a golden crust, __$food__ slices on top.
Expands: An apple pie with a golden crust, apple slices on top.
```

Change `__$food=apple__` → `__$food=cherry__` between runs — everything referencing `__$food__` follows along, and nothing is ever picked randomly.

---

## Install

1. **Plugins** tab → **Install New Plugin**
2. Paste: `https://github.com/GKartist75/wan2gp-wildcards`
3. Click **Download and Install**
4. Enable it → **Save Settings** → **Restart**

---

## Usage Guide

### Syntax Reference

| Syntax | Effect |
|---|---|
| `__name__` | Random line from `wildcards/name.txt` |
| `__dir__` | Random line pooled from ALL files in `wildcards/dir/` |
| `__dir/file__` | Specific file in subdirectory |
| `__$var=value__` | Assign a literal value to variable `var` (no random pick) |
| `__$var:file__` | Pick from file, store result under variable name `var` |
| `__$var__` | Reuse stored variable `var` (must be set first) |
| `{a\|b\|c}` | Random inline choice |
| `N::value` | Weighted choice inside .txt files |

### Inline Autocomplete

Type `__` in the Prompt Template box → dropdown shows matching wildcards at cursor.  
Arrow keys / Enter / Tab / Click to insert. Escape to dismiss.

### Seed

- **Seed = -1** → random each time
- **Fixed seed** → deterministic expansion (same seed = same picks)

### Prompt Templates (v1.6.0)

Save your prompt templates with wildcards intact (not expanded) and reload them later:

1. Type a template with wildcards in the **Prompt Template** box
2. Enter a name and click **Save Current**
3. Select from the dropdown and click **Load** to restore

Templates are stored in `wildcards/__templates__.json`.

### Batch Generation

| Mode | Behavior |
|---|---|
| **Random** (default) | Each variation uses fresh randomness. No duplicates. |
| **Sequential** | Line-by-line cycling through each file. Index 0 → line 1, etc. |

1. Type a prompt template with wildcards
2. Set the **Variations** count (1-100)
3. Pick **Random** or **Sequential** mode
4. Click **Generate N** — fills the batch output box
5. Click **Send to Media Generator** — copies to main prompt, switches tab

### Character Profiles

Define named characters. Each becomes a wildcard file — use `__character/Name__` in prompts.

- **Save** — creates/updates `wildcards/character/{Name}.txt`
- **Export JSON** — dumps all profiles as JSON
- **Import JSON** — merge profiles from JSON

### Wildcard Usage Stats (v1.6.0)

The plugin tracks how often each wildcard file is used. Click **Show Top 50 Used Wildcards** to see your most-used wildcards. Data stored in `wildcards/__stats__.json`.

### File Browser

- **Create** — new file (subdirs auto-created: `mytheme/sunset.txt`)
- **Rename** — select a file, enter new name, click Rename
- **Save** / **Delete** — standard file management
- **★ Toggle Favorite** — mark files as favorites, filter by favorites only
- **Search** — type to filter files by name
- **Cross-File Search** — search content across all 3,044 files

---

## Changelog

### v1.6.3 — Literal Variable Assignment

- **Set variables manually**: new `__$var=value__` syntax assigns a literal value — no random pick, full user control. Perfect for batch runs where you change a few values between generations:
  ```
  Prompt:  A delicious __$food=apple__ pie, topped with fresh __$food__ slices.
  Expands: A delicious apple pie, topped with fresh apple slices.
  ```
- **Mix freely**: `__$food=apple__` (manual) and `__$food:fruit__` (random from file) share the same variable namespace — set it either way, reuse with `__$food__`

### v1.6.2 — File Reorganization
- **Complete reorganization**: all 1,500+ flat files moved into 78 category directories
- **727 backward-compat aliases**: every old `__underscore_name__` still resolves
- **Merged duplicates**: `color/`+`colors/`, `material/`+`materials/`, `clothing/`+`clothings/` merged
- **Clear naming**: all files use lowercase, hyphenated names (`world-heritage-sites` not `wh-site`)
- **NSFW consolidated**: all adult content unified under `nsfw/` subdirectories
- **0 flat files remain**: every `.txt` lives in a logical category directory

### v1.6.1
- **Bugfix**: `_load_char`/`_clear_char_form` now returns 6 separate values (fixes Gradio crash when selecting/clearing characters)
- **Bugfix**: `_import_characters` error paths now return the right number of values (fixes event handler crash)
- **Bugfix**: Import JSON flow now waits for paste → Enter submit (was firing on empty box)
- **Atomic writes**: stats and favorites use tempfile + atomic rename (prevents data corruption)
- **Cross-platform**: all 321 uppercase filenames/dirs normalized to lowercase (Linux compat)
- **Dead code**: removed unused `_count_lines` function
- **Dedup**: removed duplicate lines across all wildcard files
- **Empty file**: populated empty `books/grimoires.txt` with default entries
- **Glob fix**: fixed dead glob resolution in expander (now uses `name*.txt`)
- **Error reporting**: silent `except: pass` replaced with `print()` diagnostics
- **Package doc**: `__init__.py` now has a docstring and exports

### v1.6.0
- **Named capture variables**: `__$var:file__` picks + stores, `__$var__` reuses same value across the whole prompt (fixes "multiple people" prompting)
- **Prompt Templates**: save/load named templates with wildcards intact (`__templates__.json`)
- **Rename files**: rename wildcard files from the UI
- **Usage stats**: tracks how often each wildcard is used, viewable from the UI
- **Character export/import**: export JSON, import to merge profiles
- **Send to Media Generator**: now uses Wan2GP's State API (works after Gradio updates)
- **Line count display**: file dropdown shows number of lines per file
- **Performance**: optimized file listing for 3,000+ files
- **Bugfix**: `_load_char`/`_clear_char_form` now returns 6 separate values (fixes Gradio crash when selecting/clearing characters)
- **Bugfix**: `_import_characters` error paths now return the right number of values (fixes event handler crash)
- **Bugfix**: Import JSON flow now waits for paste → Enter submit (was firing on empty box)
- **Atomic writes**: stats and favorites use tempfile + atomic rename (prevents data corruption)
- **Cross-platform**: all 321 uppercase filenames/dirs normalized to lowercase (Linux compat)
- **Dead code**: removed unused `_count_lines` function
- **Dedup**: removed duplicate lines across all wildcard files
- **Empty file**: populated empty `books/grimoires.txt` with default entries
- **Glob fix**: fixed dead glob resolution in expander (now uses `name*.txt`)
- **Error reporting**: silent `except: pass` replaced with `print()` diagnostics
- **Package doc**: `__init__.py` now has a docstring and exports

### v1.5.2
- Final cleanup: removed unused copy button, kept only Python handler for Send to Media Generator
- Typo fix: `path/filename` label in char_voice fixed
- CSS fix: chips visible on dark themes
- JS cleanup: only chip click + Insert `__file__` handlers remain

### v1.5.1
- CSS fix: chips/hint use `color:#222` (was invisible on dark themes)
- Removed JS handler for Send to Media Generator that conflicted with Python handler

### v1.5.0
- Send to Media Generator now uses JS event handler (works after Wan2GP updates)
- Batch output textbox has elem_id for reliable JS selection

### v1.4.0
- Visual Wildcard Explorer: category → file → clickable value chips
- Random mode dedup, path separator fix, button renames

### v1.3.0
- UI reorder, searchable file browser, favorites system, cross-file content search

### v1.2.0
- Merged all remaining wildcard collections (3,044 total files)
- Sequential mode fix, weight detection, dropdown refresh

### v1.1.0
- Character profile manager, inline autocomplete JS

---

## Credits

Author: GKartist75 (with PI Agent)  
Built in collaboration with [PI Agent](https://github.com/earendil-works/pi-coding-agent).

## Requirements

Wan2GP only. No external dependencies.
