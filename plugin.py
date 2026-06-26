"""Wildcards plugin for Wan2GP.

Monkey-patches prompt_parser.process_template to expand __wildcard__ and
{opt1|opt2} syntax before generation. Adds a UI tab for file management
and test expansion.
"""

import os
import re
import json
import random
import time

import gradio as gr

from shared.utils.plugins import WAN2GPPlugin
from shared.utils import prompt_parser
from . import expander

PLUGIN_ID = "wildcards"
PLUGIN_LABEL = "Wildcards"
WILDCARDS_SUBDIR = "wildcards"  # under plugin dir


def _get_wildcard_keys() -> list[str]:
    """All valid wildcard keys for autocomplete, e.g. __camera__, __camera/shot__."""
    wc_dir = expander.WILDCARDS_DIR
    if not os.path.isdir(wc_dir):
        return []
    keys: set[str] = set()
    for entry in sorted(os.listdir(wc_dir)):
        sub = os.path.join(wc_dir, entry)
        if os.path.isdir(sub) and not entry.startswith("_"):
            keys.add(f"__{entry}__")
    for root, dirs, fnames in os.walk(wc_dir):
        for fname in sorted(fnames):
            if not fname.endswith(".txt") or fname == "__index__.txt":
                continue
            rel = os.path.relpath(os.path.join(root, fname), wc_dir)
            keys.add(f"__{rel[:-4]}__")  # strip .txt
    return sorted(keys)

# state kept on the plugin instance for the monkey-patch
_original_process_template = prompt_parser.process_template
_expansion_enabled = False  # set True in setup_ui when plugin is loaded
_expansion_seed: int | None = None


def _patched_process_template(input_text, keep_comments=False, keep_empty_lines=False):
    """Wrapper: expand wildcards first, then run original template processing.

    Order matters: {opt1|opt2} wildcard syntax clashes with Wan2GP's {var}
    template syntax, so wildcards must resolve before template parsing.
    """
    if _expansion_enabled and input_text:
        input_text = expander.expand_prompt(input_text, seed=_expansion_seed)
    return _original_process_template(input_text, keep_comments, keep_empty_lines)


class WildcardsPlugin(WAN2GPPlugin):
    def __init__(self):
        super().__init__()
        self.name = "Wildcards"
        self.version = "1.0.0"
        self.description = "Dynamic wildcard expansion for prompts"
        self.type = ["extension"]

    def setup_ui(self):
        self.request_component("state")
        self.request_component("prompt")
        self.request_component("multi_prompts_gen_type")
        self.add_tab(tab_id=PLUGIN_ID, label=PLUGIN_LABEL, component_constructor=self.create_ui)

        # init wildcards dir
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        wildcards_path = os.path.join(plugin_dir, WILDCARDS_SUBDIR)
        expander.set_wildcards_dir(wildcards_path)

        # always active when plugin is enabled in Plugin Manager
        global _expansion_enabled
        _expansion_enabled = True

        # monkey-patch
        prompt_parser.process_template = _patched_process_template

        # inject autocomplete JS (bake wildcard list into the script)
        wc_keys = _get_wildcard_keys()
        js = f"""
(function() {{
  const KEYS = {json.dumps(wc_keys)};

  function findTextarea(id) {{
    const el = document.getElementById(id);
    return el && el.querySelector('textarea');
  }}

  function setupAutocomplete(ta, ddClass) {{
    const dd = document.createElement('div');
    dd.className = ddClass || 'wc-dd';
    dd.style.cssText = 'position:fixed;background:#fff;border:1px solid #d0d0d0;border-radius:6px;max-height:220px;overflow-y:auto;z-index:99999;display:none;width:320px;font-family:monospace;font-size:13px;box-shadow:0 4px 16px rgba(0,0,0,0.15);';
    document.body.appendChild(dd);
    function pos() {{ const r=ta.getBoundingClientRect(); dd.style.left=r.left+'px'; dd.style.top=(r.bottom)+'px'; dd.style.width=Math.max(r.width,200)+'px'; }}
    ta.addEventListener('scroll', pos);
    window.addEventListener('scroll', pos, true);
    let sel = -1, opening = -1;

    function ins(w) {{
      const cur = ta.selectionStart;
      const val = ta.value;
      const before = val.substring(0, cur);
      const after = val.substring(cur);
      const op = before.lastIndexOf('__');
      if (op === -1) return;
      ta.value = before.substring(0, op) + w + after;
      const pos = op + w.length;
      ta.setSelectionRange(pos, pos);
      ta.dispatchEvent(new Event('input', {{bubbles:true}}));
      dd.style.display = 'none';
    }}

    ta.addEventListener('input', function() {{
      const cur = this.selectionStart;
      const before = this.value.substring(0, cur);
      const op = before.lastIndexOf('__');
      if (op === -1) {{ dd.style.display = 'none'; return; }}
      opening = op;
      const between = before.substring(op + 2);
      if (between.includes('__')) {{ dd.style.display = 'none'; return; }}
      if (op > 0 && !/^[\s\n\r\t(,:]$/.test(before[op-1])) {{
        dd.style.display = 'none'; return;
      }}
      const q = between.toLowerCase();
      if (q.length === 0) {{ dd.style.display = 'none'; return; }}
      const matches = KEYS.filter(k => k.substring(2, k.length-2).toLowerCase().startsWith(q));
      if (matches.length === 0) {{ dd.style.display = 'none'; return; }}
      sel = -1;
      dd.innerHTML = matches.map((k, i) => {{
        const inner = k.substring(2, k.length-2);
        const idx = inner.toLowerCase().indexOf(q);
        const hl = idx !== -1
          ? inner.substring(0,idx) + '<strong>' + inner.substring(idx, idx+q.length) + '</strong>' + inner.substring(idx+q.length)
          : inner;
        const dir = k.includes('/') ? k.split('/')[0].substring(2) : '';
        const cls = i === sel ? 'wc-sel' : '';
        return `<div class="wc-item" data-w="${{k}}" style="padding:3px 10px;cursor:pointer;display:flex;gap:8px;${{i===sel?'background:#e8f0fe':''}}"><span style="color:#666;min-width:60px;">${{dir ? dir : '—'}}</span><span>${{hl}}</span></div>`;
      }}).join('');
      pos();
      dd.style.display = 'block';

      dd.querySelectorAll('.wc-item').forEach(el => {{
        el.addEventListener('mousedown', function(e) {{ e.preventDefault(); ins(this.dataset.w); }});
        el.addEventListener('mouseenter', function() {{ dd.querySelectorAll('.wc-item').forEach(x=>x.style.background=''); this.style.background='#e8f0fe'; }});
      }});
    }});

    ta.addEventListener('keydown', function(e) {{
      if (dd.style.display === 'none') return;
      const items = dd.querySelectorAll('.wc-item');
      if (e.key === 'ArrowDown') {{ e.preventDefault(); sel = Math.min(sel+1, items.length-1); items.forEach((x,i)=>x.style.background=i===sel?'#e8f0fe':''); }}
      else if (e.key === 'ArrowUp') {{ e.preventDefault(); sel = Math.max(sel-1, -1); items.forEach((x,i)=>x.style.background=i===sel?'#e8f0fe':''); }}
      else if (e.key === 'Enter' || e.key === 'Tab') {{ if (sel>=0 && items[sel]) {{ e.preventDefault(); ins(items[sel].dataset.w); }} }}
      else if (e.key === 'Escape') {{ dd.style.display = 'none'; }}
    }});

    ta.addEventListener('blur', function() {{ setTimeout(()=>dd.style.display='none', 200); }});
  }}

  function init() {{
    const ta1 = findTextarea('wc-test-input');
    if (ta1) setupAutocomplete(ta1, 'wc-dd');
    const ta2 = findTextarea('wc-batch-prompt');
    if (ta2) setupAutocomplete(ta2, 'wc-dd');
  }}
  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded', init); else init();
}})();
"""
        self.add_custom_js(js)

    def create_ui(self, api_session):

        def _list_wc_files() -> list[str]:
            """Recursively list .txt files, exclude __index__.txt."""
            wc_dir = expander.WILDCARDS_DIR
            if not os.path.isdir(wc_dir):
                return []
            files = []
            for root, dirs, fnames in os.walk(wc_dir):
                for fname in sorted(fnames):
                    if not fname.endswith(".txt") or fname == "__index__.txt":
                        continue
                    rel = os.path.relpath(os.path.join(root, fname), wc_dir)
                    files.append(rel)
            return sorted(files)

        def _read_file(filename: str) -> str:
            if not filename:
                return ""
            path = os.path.join(expander.WILDCARDS_DIR, filename)
            if not os.path.isfile(path):
                return ""
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    return fh.read()
            except OSError:
                return ""

        def _save_file(filename: str, content: str) -> str:
            if not filename:
                return "No filename given."
            if not filename.endswith(".txt"):
                filename += ".txt"
            wc_dir = expander.WILDCARDS_DIR
            path = os.path.join(wc_dir, filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(content)
                return f"Saved {filename}"
            except OSError as e:
                return f"Error saving: {e}"

        def _delete_file(filename: str) -> str:
            if not filename:
                return "No file selected."
            path = os.path.join(expander.WILDCARDS_DIR, filename)
            try:
                os.remove(path)
                return f"Deleted {filename}"
            except OSError as e:
                return f"Error deleting: {e}"

        def _refresh_list() -> gr.update:
            return gr.update(choices=_list_wc_files(), value=None)

        def _set_seed(seed_val: int):
            global _expansion_seed
            _expansion_seed = seed_val if seed_val >= 0 else None

        def _test_expand(prompt: str, seed_val: int) -> str:
            rng = random.Random(seed_val if seed_val >= 0 else None)
            return expander._expand_text(prompt, rng, depth=0)

        with gr.Column():
            gr.Markdown("## Wildcard Prompt Expansion")
            guide = r"""
### Quick Start

| Syntax | Effect | Example |
|---|---|---|
| `__file__` | Random line from `wildcards/file.txt` | `__camera_shot__` → `close-up shot` |
| `__dir__` | Random line from ALL files in `wildcards/dir/` | `__color__` → picks from named, palette, or skin |
| `__dir/file__` | Specific file in subdirectory | `__color/named__` → only from `color/named.txt` |
| `{a|b|c}` | Random inline choice | `{cinematic|vintage|raw}` |
| `N::value` | Weighted option in .txt files | `3::sunset` in file = 3× more likely |

**Seed = -1** for random per generation. **Seed = fixed number** for reproducible results.

### Prompt Examples

```
__camera_shot__ of __character_archetype__ in __environment_nature__, __lighting_style__
__color__ {neon|moody|atmospheric} scene, camera __camera_movement__, __emotion_mood__
A {cyberpunk|fantasy|post-apocalyptic} __environment_urban__, __weather_sky__, __camera_technique__
```

### Library Structure

Check `__index__.txt` for full file map. Quick categories:
`action/*` `aesthetic/*` `camera/*` `character/*` `clothing/*` `color/*`
`composition/*` `effect/*` `emotion/*` `environment/*` `lighting/*`
`material/*` `motion/*` `quality/*` `time/*` `transition/*` `weather/*`
""".strip()
            gr.Markdown(guide)

            seed_input = gr.Number(label="Seed (-1 = random)", value=-1, precision=0)

            seed_input.change(fn=_set_seed, inputs=[seed_input])

            gr.Markdown("> Expansion is active when this plugin is enabled in the **Plugins** tab.")

            gr.Markdown("---")
            gr.Markdown("### Wildcard File Manager")

            file_dropdown = gr.Dropdown(
                label="Wildcard File",
                choices=_list_wc_files(),
                value=None,
                interactive=True,
                allow_custom_value=True,
            )
            refresh_btn = gr.Button("Refresh File List")
            refresh_btn.click(fn=_refresh_list, outputs=[file_dropdown], queue=False)

            file_editor = gr.TextArea(label="File Content", lines=12)

            file_dropdown.change(
                fn=_read_file,
                inputs=[file_dropdown],
                outputs=[file_editor],
            )

            with gr.Row():
                new_name = gr.Textbox(label="New filename", placeholder="e.g. mytheme.txt")
                create_btn = gr.Button("Create")
                save_btn = gr.Button("Save")
                delete_btn = gr.Button("Delete")

            file_msg = gr.Textbox(label="Result", interactive=False)

            create_btn.click(
                fn=lambda name: _save_file(name, ""),
                inputs=[new_name],
                outputs=[file_msg],
            ).then(fn=_refresh_list, outputs=[file_dropdown], queue=False)

            save_btn.click(
                fn=_save_file,
                inputs=[file_dropdown, file_editor],
                outputs=[file_msg],
            ).then(fn=_refresh_list, outputs=[file_dropdown], queue=False)

            delete_btn.click(
                fn=_delete_file,
                inputs=[file_dropdown],
                outputs=[file_msg],
            ).then(fn=_refresh_list, outputs=[file_dropdown], queue=False)

            gr.Markdown("---")
            gr.Markdown("### Test Expansion")

            test_input = gr.Textbox(
                label="Test Prompt",
                lines=3,
                placeholder="e.g. A __color__ {sunlit|moody|dramatic} scene",
                elem_id="wc-test-input",
            )
            test_seed = gr.Number(label="Test Seed (-1 = random)", value=-1, precision=0)
            test_btn = gr.Button("Expand")
            test_output = gr.Textbox(label="Result", lines=3, interactive=False)

            test_btn.click(fn=_test_expand, inputs=[test_input, test_seed], outputs=[test_output])

            gr.Markdown("---")
            gr.Markdown("### Batch Generate N Variations")

            batch_prompt = gr.Textbox(
                label="Prompt Template",
                lines=3,
                placeholder="e.g. A __camera_shot__ of a __character_archetype__, __lighting_style__",
                elem_id="wc-batch-prompt",
            )

            with gr.Row():
                batch_count = gr.Number(label="Number of Variations", value=6, precision=0, minimum=1, maximum=100)
                batch_seed_mode = gr.Radio(
                    label="Seed Mode",
                    choices=["Sequential (0,1,2...)", "Random"],
                    value="Sequential (0,1,2...)",
                )

            generate_btn = gr.Button("Generate N Variations")
            batch_output = gr.Textbox(label="Generated Prompts (one per line)", lines=8, interactive=False)

            send_btn = gr.Button("Send to Prompt Box (sets multi-prompt mode to G)")

            def _generate_batch(prompt_template: str, count: int, seed_mode: str) -> str:
                if not prompt_template:
                    return ""
                count = max(1, min(100, int(count)))
                lines = []
                for i in range(count):
                    seed = i if seed_mode.startswith("Sequential") else None
                    rng = random.Random(seed)
                    expanded = expander._expand_text(prompt_template, rng, depth=0)
                    lines.append(expanded)
                return "\n".join(lines)

            def _send_to_prompt_box(batch_text: str):
                if not batch_text:
                    return gr.update(), gr.update()
                return gr.update(value=batch_text), gr.update(value="G")

            generate_btn.click(
                fn=_generate_batch,
                inputs=[batch_prompt, batch_count, batch_seed_mode],
                outputs=[batch_output],
            )

            send_btn.click(
                fn=_send_to_prompt_box,
                inputs=[batch_output],
                outputs=[self.prompt, self.multi_prompts_gen_type],
            )

        # return components for lifecycle
        self.on_tab_outputs = []
