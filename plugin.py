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
from . import character_manager

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
        self.version = "1.2.0"
        self.description = "Dynamic wildcard expansion for prompts + character profile manager"
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

        # init character manager
        character_manager.init(plugin_dir)

        # always active when plugin is enabled in Plugin Manager
        global _expansion_enabled
        _expansion_enabled = True

        # monkey-patch
        prompt_parser.process_template = _patched_process_template

        # inject autocomplete JS (bake wildcard list into the script)
        wc_keys = _get_wildcard_keys()
        KEYS_JSON = json.dumps(wc_keys)
        # raw string template for JS (no f-string escaping issues)
        # %s gets replaced with JSON array literal (valid JS)
        js = r"""(function(){
var K=%s;
function ft(i){var e=document.getElementById(i);return e&&e.querySelector('textarea')}
function sa(t){
var d=document.createElement('div');
d.style.cssText='position:fixed;background:#fff;border:1px solid #d0d0d0;border-radius:6px;max-height:220px;overflow-y:auto;z-index:99999;display:none;width:320px;font-family:monospace;font-size:13px;box-shadow:0 4px 16px rgba(0,0,0,0.15);color:#222;';
document.body.appendChild(d);
function pv(){var r=t.getBoundingClientRect();d.style.left=r.left+'px';d.style.top=(r.bottom)+'px';d.style.width=Math.max(r.width,200)+'px'}
t.addEventListener('scroll',pv);window.addEventListener('scroll',pv,true);
var s=-1;
function iw(w){var c=t.selectionStart,v=t.value,b=v.substring(0,c),a=v.substring(c),o=b.lastIndexOf('__');if(o===-1)return;t.value=b.substring(0,o)+w+a;var n=o+w.length;t.setSelectionRange(n,n);t.dispatchEvent(new Event('input',{bubbles:true}));d.style.display='none'}
t.addEventListener('input',function(){
var c=this.selectionStart,b=this.value.substring(0,c),o=b.lastIndexOf('__');
if(o===-1){d.style.display='none';return}
var bt=b.substring(o+2);
if(bt.includes('__')){d.style.display='none';return}
if(o>0&&!/^[\s\n\r\t(,:]$/.test(b[o-1])){d.style.display='none';return}
var q=bt.toLowerCase();
if(q.length===0){d.style.display='none';return}
var mt=K.filter(function(k){return k.substring(2,k.length-2).toLowerCase().startsWith(q)});
if(mt.length===0){d.style.display='none';return}
s=-1;
d.innerHTML=mt.map(function(k,i){
var inn=k.substring(2,k.length-2);
var ix=inn.toLowerCase().indexOf(q);
var hl=ix!==-1?inn.substring(0,ix)+'<strong>'+inn.substring(ix,ix+q.length)+'</strong>'+inn.substring(ix+q.length):inn;
return '<div class="wc-item" data-w="'+k+'" style="padding:3px 8px;cursor:pointer;color:#222;white-space:nowrap">'+hl+'</div>'
}).join('');
pv();d.style.display='block';
d.querySelectorAll('.wc-item').forEach(function(e){
e.addEventListener('mousedown',function(e){e.preventDefault();iw(this.dataset.w)});
e.addEventListener('mouseenter',function(){d.querySelectorAll('.wc-item').forEach(function(x){x.style.background='';x.style.color='#222'});this.style.background='#e8f0fe';this.style.color='#222'})
})
});
t.addEventListener('keydown',function(e){
if(d.style.display==='none')return;
var is=d.querySelectorAll('.wc-item');
if(e.key==='ArrowDown'){e.preventDefault();s=Math.min(s+1,is.length-1);is.forEach(function(x,i){x.style.background=i===s?'#e8f0fe':'';x.style.color='#222'})}
else if(e.key==='ArrowUp'){e.preventDefault();s=Math.max(s-1,-1);is.forEach(function(x,i){x.style.background=i===s?'#e8f0fe':'';x.style.color='#222'})}
else if(e.key==='Enter'||e.key==='Tab'){if(s>=0&&is[s]){e.preventDefault();iw(is[s].dataset.w)}}
else if(e.key==='Escape'){d.style.display='none'}
});
t.addEventListener('blur',function(){setTimeout(function(){d.style.display='none'},200)})
}
function init(){['wc-test-input','wc-batch-prompt'].forEach(function(i){var t=ft(i);if(t)sa(t)})}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
""" % (KEYS_JSON,)
        self.add_custom_js(js)

    def on_tab_select(self, state: dict):
        """Refresh file dropdown from disk on every tab visit."""
        if hasattr(self, "file_dropdown"):
            return gr.update(choices=_list_wc_files())
        return None

    def create_ui(self, api_session):

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
            gr.Markdown(f"## Wildcard Prompt Expansion  —  v{self.version}")
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

            def _create_file(name: str) -> tuple[str, gr.update]:
                if not name:
                    return "No filename given.", gr.update()
                if not name.endswith(".txt"):
                    name += ".txt"
                msg = _save_file(name, "")
                return msg, gr.update(choices=_list_wc_files(), value=name)

            create_btn.click(
                fn=_create_file,
                inputs=[new_name],
                outputs=[file_msg, file_dropdown],
            )

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
                    if seed_mode.startswith("Sequential"):
                        # line-by-line cycling, no randomness
                        expanded = expander.expand_prompt_sequential(prompt_template, i)
                    else:
                        # random mode: each variation gets fresh RNG (no seed = random)
                        rng = random.Random()
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

            gr.Markdown("---")
            gr.Markdown("### Character Profiles")
            gr.Markdown(
                "Define named characters with appearance descriptions. "
                "Each character becomes a wildcard file — use "
                "`__character/Name__` in your prompt to inject their appearance. "
                "Voice/clothing/tags are metadata for other plugins (LTX Director, SeedVC)."
            )

            char_dropdown = gr.Dropdown(
                label="Character",
                choices=character_manager.list_characters(),
                value=None,
                interactive=True,
            )

            char_name = gr.Textbox(label="Name", placeholder="e.g. Sarah")
            char_appearance = gr.TextArea(
                label="Appearance (what __character/Name__ expands to)",
                lines=4,
                placeholder="blonde hair, blue eyes, red dress, fair skin",
            )
            char_voice = gr.Textbox(
                label="Voice sample (path/filename for TTS plugins)",
                placeholder="voice_sarah.wav",
            )
            char_clothing = gr.Textbox(
                label="Clothing",
                placeholder="red dress",
            )
            char_tags = gr.Textbox(
                label="Tags (comma separated)",
                placeholder="female, human, protagonist",
            )
            char_notes = gr.TextArea(
                label="Notes",
                lines=2,
                placeholder="Main character, confident demeanor",
            )

            with gr.Row():
                char_save_btn = gr.Button("Save", variant="primary")
                char_new_btn = gr.Button("New")
                char_delete_btn = gr.Button("Delete", variant="stop")

            char_msg = gr.Textbox(label="Result", interactive=False)

            def _load_char(name: str):
                if not name:
                    return "", "", "", "", "", ""
                p = character_manager.get_character(name)
                if not p:
                    return "", "", "", "", "", ""
                return (
                    name,
                    p.get("appearance", ""),
                    p.get("voice", ""),
                    p.get("clothing", ""),
                    p.get("tags", ""),
                    p.get("notes", ""),
                )

            def _refresh_char_list():
                return gr.update(choices=character_manager.list_characters(), value=None)

            def _clear_char_form():
                return "", "", "", "", "", ""

            def _save_char(name, appearance, voice, clothing, tags, notes):
                profile = {
                    "appearance": appearance,
                    "voice": voice,
                    "clothing": clothing,
                    "tags": tags,
                    "notes": notes,
                }
                msg = character_manager.save_character(name, profile)
                return msg, gr.update(choices=character_manager.list_characters(), value=name)

            def _delete_char(name):
                msg = character_manager.delete_character(name)
                return msg, gr.update(choices=character_manager.list_characters(), value=None), "", "", "", "", "", ""

            char_dropdown.change(
                fn=_load_char,
                inputs=[char_dropdown],
                outputs=[char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes],
            )

            char_new_btn.click(
                fn=_clear_char_form,
                outputs=[char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes],
            ).then(fn=lambda: (gr.update(value=None), ""), outputs=[char_dropdown, char_msg])

            char_save_btn.click(
                fn=_save_char,
                inputs=[char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes],
                outputs=[char_msg, char_dropdown],
            )

            char_delete_btn.click(
                fn=_delete_char,
                inputs=[char_dropdown],
                outputs=[char_msg, char_dropdown, char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes],
            )

        # return components for lifecycle
        self.file_dropdown = file_dropdown
        self.on_tab_outputs = [self.file_dropdown]
