# wan2gp-wildcards

Wildcard prompt expansion plugin for [Wan2GP](https://github.com/deepbeepmeep/Wan2GP). Randomize prompts with `__file__` and `{opt1|opt2}` syntax.

## Install

1. **Plugins** tab → **Install New Plugin**
2. Paste: `https://github.com/GKartist75/wan2gp-wildcards`
3. Click **Download and Install**
4. Enable it → **Save Settings** → **Restart**

## Usage

| Syntax | Effect | Example |
|---|---|---|
| `__file__` | Random line from `wildcards/file.txt` | `__camera_shot__` → `close-up shot` |
| `__dir__` | Random line from ALL files in `wildcards/dir/` | `__color__` → picks from named, palette, or skin |
| `__dir/file__` | Specific file in subdirectory | `__color/named__` |
| `{a\|b\|c}` | Random inline choice | `{cinematic\|vintage\|raw}` |
| `N::value` | Weighted option in .txt files | `3::sunset` = 3× more likely |

Enable the toggle in the **Wildcards** tab. Set seed = -1 for random, or fixed for reproducibility.

### Batch mode

Wildcards tab has a **Batch Generate N Variations** section — enter a template with wildcards, set count, generate N expanded prompts, send them straight to the prompt box.

## Library

~5,000 terms across 71 files in 17 categories:

`action` `aesthetic` `camera` `character` `clothing` `color` `composition` `effect` `emotion` `environment` `lighting` `material` `motion` `quality` `time` `transition` `weather`

## Files

```
wan2gp-wildcards/
├── __init__.py
├── plugin.py          # WAN2GPPlugin + monkey-patch
├── expander.py        # expansion engine
├── plugin_info.json   # metadata
└── wildcards/         # 71 .txt files
```

## Requirements

Wan2GP only. No external dependencies.
