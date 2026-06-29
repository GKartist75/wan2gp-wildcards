"""Wildcards plugin for Wan2GP.

Monkey-patches prompt_parser.process_template to expand __wildcard__ and
{opt1|opt2} syntax before generation. Adds a UI tab for file management
and test expansion.
"""

import os
import re
import json
import html
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
    """Recursively list .txt files, exclude __index__.txt and __favorites__.json."""
    wc_dir = expander.WILDCARDS_DIR
    if not os.path.isdir(wc_dir):
        return []
    files = []
    for root, dirs, fnames in os.walk(wc_dir):
        for fname in sorted(fnames):
            if not fname.endswith(".txt") or fname == "__index__.txt":
                continue
            rel = os.path.relpath(os.path.join(root, fname), wc_dir).replace(os.sep, "/")
            files.append(rel)
    return sorted(files)


def _get_categories() -> list[str]:
    """Sorted list of subdirectory names (skip __ prefixed)."""
    wc_dir = expander.WILDCARDS_DIR
    if not os.path.isdir(wc_dir):
        return []
    cats = []
    for entry in sorted(os.listdir(wc_dir)):
        if os.path.isdir(os.path.join(wc_dir, entry)) and not entry.startswith("_"):
            cats.append(entry)
    return cats


def _filter_files(search: str, category: str, favorites_only: bool, favorites: list[str]) -> list[str]:
    """Filter file list by search term, category, and favorites."""
    all_files = _list_wc_files()
    if category and category != "All":
        all_files = [f for f in all_files if f.startswith(category + "/")]
    if search:
        q = search.lower()
        all_files = [f for f in all_files if q in f.lower()]
    if favorites_only and favorites:
        all_files = [f for f in all_files if f in favorites]
    return all_files


FAVORITES_FILE = "__favorites__.json"


def _load_favorites() -> list[str]:
    """Load favorited file paths."""
    path = os.path.join(expander.WILDCARDS_DIR, FAVORITES_FILE)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_favorites(favorites: list[str]):
    """Persist favorited file paths."""
    path = os.path.join(expander.WILDCARDS_DIR, FAVORITES_FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(favorites, f)
    except OSError:
        pass


def _search_content(query: str) -> str:
    """Search across all wildcard file contents. Returns lines with file:line:match."""
    if not query or not query.strip():
        return "Enter a search term."
    q = query.strip().lower()
    wc_dir = expander.WILDCARDS_DIR
    if not os.path.isdir(wc_dir):
        return "Wildcards directory not found."
    results = []
    for fpath in _list_wc_files():
        full = os.path.join(wc_dir, fpath)
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if q in line.lower():
                        snippet = line.rstrip()[:120]
                        results.append(f"{fpath}:{i}: {snippet}")
        except Exception:
            continue
        if len(results) >= 500:
            break
    if not results:
        return f"No matches for '{query}'."
    return "\n".join(results)


def _get_files_for_cat(cat: str) -> list[str]:
    """Files belonging to a category (subdirectory). Empty cat / 'All' = all files."""
    if not cat or cat == "All":
        return _list_wc_files()
    prefix = cat + "/"
    return [f for f in _list_wc_files() if f.startswith(prefix)]


def _render_chips_html(filename: str, seed: int = 0) -> str:
    """Read file, pick up to 30 lines, return clickable chip HTML."""
    if not filename:
        return '<div class="wc-chips"><p class="wc-hint">\u2190 Select a category + file to see values</p></div>'
    full = os.path.join(expander.WILDCARDS_DIR, filename)
    if not os.path.isfile(full):
        return '<div class="wc-chips"><p>File not found</p></div>'
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            lines = [l.rstrip() for l in f if l.strip() and not l.startswith("#")]
    except Exception:
        return '<div class="wc-chips"><p>Error reading file</p></div>'
    if not lines:
        return '<div class="wc-chips"><p>Empty file</p></div>'
    rng = random.Random(seed)
    rng.shuffle(lines)
    sample = lines[:30]
    def esc(s):
        return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")
    chips = "".join(
        f'<span class="wc-chip" data-value="{esc(v)}">{esc(v[:60])}</span>'
        for v in sample
    )
    css = """<style>
.wc-chips{display:flex;flex-wrap:wrap;gap:6px;padding:6px 0}
.wc-chip{background:rgba(100,100,130,0.12);border:1px solid rgba(100,100,130,0.25);border-radius:16px;padding:4px 12px;cursor:pointer;font-size:13px;color:#222;transition:background .15s;white-space:nowrap;display:inline-block}
.wc-chip:hover{background:rgba(100,100,130,0.22);border-color:rgba(100,100,130,0.4)}
.wc-hint{color:#222;opacity:.5;font-style:italic;font-size:13px}
</style>"""
    return css + '<div class="wc-chips">' + chips + '</div>'


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
        self.version = "1.5.0"
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
function ft2(i){var e=document.getElementById(i);return e&&e.querySelector('select')||e&&e.querySelector('input:not([type=hidden])')}
function iv(t,v){if(!t||!v)return;var s=t.selectionStart,e=t.selectionEnd,sp=s>0&&!t.value[s-1].match(/\s/)?' ':'';t.value=t.value.substring(0,s)+sp+v+t.value.substring(e);var np=s+sp.length+v.length;t.selectionStart=t.selectionEnd=np;t.dispatchEvent(new Event('input',{bubbles:true}))}
function init(){['wc-prompt-input'].forEach(function(i){var t=ft(i);if(t)sa(t)})}
// chip click + Insert __file__ via event delegation
document.body.addEventListener('click',function(e){
var ch=e.target.closest('.wc-chip');
if(ch){e.preventDefault();var p=document.getElementById('wc-prompt-input'),ta=p&&p.querySelector('textarea');if(ta)iv(ta,ch.dataset.value);return}
var ib=e.target.closest('button');
if(ib&&ib.textContent.trim().includes('Insert __file__')){e.preventDefault();var sd=ft2('wc-file-dd'),fv=sd&&sd.value||'';if(!fv)return;var ref='__'+fv.replace(/\.txt$/,'')+'__';var p=document.getElementById('wc-prompt-input'),ta=p&&p.querySelector('textarea');if(ta)iv(ta,ref);return}
});
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
""" % (KEYS_JSON,)
        self.add_custom_js(js)

    def on_tab_select(self, state: dict):
        """Refresh file dropdown and category filter from disk on every tab visit."""
        if hasattr(self, "file_dropdown"):
            # refresh file list and category list
            cats = ["All"] + _get_categories()
            files = _list_wc_files()
            return [gr.update(choices=files), gr.update(choices=cats)]
        return [None, None]

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

        with gr.Column():
            gr.Markdown(f"## Wildcard Prompt Expansion  —  v{self.version}")
            gr.Markdown("> Expansion active when enabled in **Plugins** tab. Type `__` for wildcard autocomplete.")

            seed_input = gr.Number(label="Seed (-1 = random)", value=-1, precision=0)
            seed_input.change(fn=_set_seed, inputs=[seed_input])

            # ── Prompt Builder ──────────────────────────────────────────
            gr.Markdown("---")
            gr.Markdown("### 1. Prompt Builder")

            # ── Visual Wildcard Explorer ──
            with gr.Accordion("\U0001f50d Wildcard Explorer", open=True):
                with gr.Row():
                    wc_cat = gr.Dropdown(label="Category", choices=["All"] + _get_categories(), value="All", scale=2)
                    wc_file = gr.Dropdown(label="File", choices=_list_wc_files(), value=None, scale=3, elem_id="wc-file-dd")
                wc_chips = gr.HTML(_render_chips_html(""))
                with gr.Row():
                    wc_shuffle = gr.Button("\u21bb Shuffle Values", size="sm", scale=1)
                    wc_insert_ref = gr.Button("+ Insert __file__", size="sm", scale=1)

            prompt_input = gr.Textbox(
                label="Prompt Template",
                lines=4,
                placeholder="e.g. A __camera_shot__ of a young woman in __environment_nature__, __lighting_style__",
                elem_id="wc-prompt-input",
            )

            def _filter_cat_files(cat: str) -> gr.update:
                return gr.update(choices=_get_files_for_cat(cat), value=None)

            def _render_chips(filename: str) -> str:
                return _render_chips_html(filename)

            # Insert __file__ handled in JS (event delegation in setup_ui) — no Python event to avoid Gradio arg mismatch
            wc_cat.change(fn=_filter_cat_files, inputs=[wc_cat], outputs=[wc_file])
            wc_file.change(fn=_render_chips, inputs=[wc_file], outputs=[wc_chips])
            wc_shuffle.click(fn=_render_chips, inputs=[wc_file], outputs=[wc_chips])

            with gr.Row():
                test_btn = gr.Button("Generate 1 row", scale=1)
                batch_count = gr.Number(label="Variations", value=6, precision=0, minimum=1, maximum=100, scale=1)
                batch_seed_mode = gr.Radio(
                    label="Mode",
                    choices=["Sequential", "Random"],
                    value="Random",
                    scale=1,
                )
                generate_btn = gr.Button("Generate N", scale=1, variant="primary")
                send_btn = gr.Button("Send to Media Generator", scale=1)

            test_output = gr.Textbox(label="Preview (single expansion)", lines=2, interactive=False)
            batch_output = gr.Textbox(label="Generated Variations (one per line)", lines=6, interactive=False, elem_id="wc-batch-output")

            def _test_expand(prompt: str, seed_val: int) -> str:
                rng = random.Random(seed_val if seed_val >= 0 else None)
                return expander._expand_text(prompt, rng, depth=0)

            def _generate_batch(prompt_template: str, count: int, seed_mode: str) -> str:
                if not prompt_template:
                    return ""
                count = max(1, min(100, int(count)))
                lines = []
                if seed_mode.startswith("Sequential"):
                    for i in range(count):
                        lines.append(expander.expand_prompt_sequential(prompt_template, i))
                else:
                    seen = set()
                    max_attempts = count * 20
                    attempts = 0
                    while len(lines) < count and attempts < max_attempts:
                        rng = random.Random()
                        expanded = expander._expand_text(prompt_template, rng, depth=0)
                        if expanded not in seen:
                            seen.add(expanded)
                            lines.append(expanded)
                        attempts += 1
                return "\n".join(lines)

            def _send_to_prompt_box(batch_text: str):
                if not batch_text:
                    return gr.update(), gr.update()
                return gr.update(value=batch_text), gr.update(value="G")

            test_btn.click(fn=_test_expand, inputs=[prompt_input, seed_input], outputs=[test_output])
            generate_btn.click(fn=_generate_batch, inputs=[prompt_input, batch_count, batch_seed_mode], outputs=[batch_output])
            send_btn.click(fn=_send_to_prompt_box, inputs=[batch_output], outputs=[self.prompt, self.multi_prompts_gen_type])

            # ── Character Profiles ──────────────────────────────────────
            gr.Markdown("---")
            gr.Markdown("### 2. Character Profiles")
            gr.Markdown(
                "Define named characters. Use `__character/Name__` in your prompt to inject appearance. "
                "Voice/clothing/tags are metadata for other plugins."
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
                lines=3,
                placeholder="blonde hair, blue eyes, red dress, fair skin",
            )
            char_voice = gr.Textbox(label="Voice sample (path/filename for TTS)", placeholder="voice_sarah.wav")
            char_clothing = gr.Textbox(label="Clothing", placeholder="red dress")
            char_tags = gr.Textbox(label="Tags (comma separated)", placeholder="female, human, protagonist")
            char_notes = gr.TextArea(label="Notes", lines=2, placeholder="Main character")

            with gr.Row():
                char_save_btn = gr.Button("Save", variant="primary")
                char_new_btn = gr.Button("New")
                char_delete_btn = gr.Button("Delete", variant="stop")

            char_msg = gr.Textbox(label="Result", interactive=False)

            def _load_char(name: str):
                if not name:
                    return "" * 6
                p = character_manager.get_character(name)
                if not p:
                    return "" * 6
                return (name, p.get("appearance", ""), p.get("voice", ""), p.get("clothing", ""), p.get("tags", ""), p.get("notes", ""))

            def _clear_char_form():
                return "" * 6

            def _save_char(name, appearance, voice, clothing, tags, notes):
                profile = {"appearance": appearance, "voice": voice, "clothing": clothing, "tags": tags, "notes": notes}
                msg = character_manager.save_character(name, profile)
                return msg, gr.update(choices=character_manager.list_characters(), value=name)

            def _delete_char(name):
                msg = character_manager.delete_character(name)
                return (msg, gr.update(choices=character_manager.list_characters(), value=None)) + ("",) * 6

            char_dropdown.change(fn=_load_char, inputs=[char_dropdown], outputs=[char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes])
            char_new_btn.click(fn=_clear_char_form, outputs=[char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes])\
                .then(fn=lambda: (gr.update(value=None), ""), outputs=[char_dropdown, char_msg])
            char_save_btn.click(fn=_save_char, inputs=[char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes], outputs=[char_msg, char_dropdown])
            char_delete_btn.click(fn=_delete_char, inputs=[char_dropdown], outputs=[char_msg, char_dropdown, char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes])

            # ── Wildcard File Browser ───────────────────────────────────
            gr.Markdown("---")
            gr.Markdown("### 3. Wildcard File Browser")

            with gr.Row():
                cat_filter = gr.Dropdown(
                    label="Category",
                    choices=["All"] + _get_categories(),
                    value="All",
                    interactive=True,
                )
                search_filter = gr.Textbox(
                    label="Search files",
                    placeholder="type to filter...",
                    scale=2,
                )
                fav_only = gr.Checkbox(label="★ Favorites only", value=False)

            file_dropdown = gr.Dropdown(
                label="Wildcard File",
                choices=_list_wc_files(),
                value=None,
                interactive=True,
            )

            with gr.Row():
                refresh_btn = gr.Button("Refresh")
                star_btn = gr.Button("★ Toggle Favorite")

            file_editor = gr.TextArea(label="File Content", lines=12)

            file_dropdown.change(
                fn=_read_file,
                inputs=[file_dropdown],
                outputs=[file_editor],
            )

            with gr.Row():
                new_name = gr.Textbox(label="New filename", placeholder="e.g. mytheme.txt", scale=2)
                create_btn = gr.Button("Create")
                save_btn = gr.Button("Save")
                delete_btn = gr.Button("Delete")

            file_msg = gr.Textbox(label="Result", interactive=False)

            def _create_file(name: str) -> tuple[str, gr.update, gr.update]:
                if not name:
                    return "No filename given.", gr.update(), gr.update()
                if not name.endswith(".txt"):
                    name += ".txt"
                msg = _save_file(name, "")
                all_files = _list_wc_files()
                return msg, gr.update(choices=all_files, value=name), gr.update(choices=["All"] + _get_categories())

            def _update_filter(search: str, category: str, fav_only: bool):
                favs = _load_favorites()
                filtered = _filter_files(search, category, fav_only, favs)
                return gr.update(choices=filtered, value=None)

            search_filter.change(
                fn=_update_filter,
                inputs=[search_filter, cat_filter, fav_only],
                outputs=[file_dropdown],
            )
            cat_filter.change(
                fn=_update_filter,
                inputs=[search_filter, cat_filter, fav_only],
                outputs=[file_dropdown],
            )
            fav_only.change(
                fn=_update_filter,
                inputs=[search_filter, cat_filter, fav_only],
                outputs=[file_dropdown],
            )

            create_btn.click(
                fn=_create_file,
                inputs=[new_name],
                outputs=[file_msg, file_dropdown, cat_filter],
            )

            save_btn.click(
                fn=_save_file,
                inputs=[file_dropdown, file_editor],
                outputs=[file_msg],
            ).then(
                fn=_update_filter,
                inputs=[search_filter, cat_filter, fav_only],
                outputs=[file_dropdown],
            )

            delete_btn.click(
                fn=_delete_file,
                inputs=[file_dropdown],
                outputs=[file_msg],
            ).then(
                fn=_update_filter,
                inputs=[search_filter, cat_filter, fav_only],
                outputs=[file_dropdown],
            ).then(
                fn=lambda: gr.update(choices=["All"] + _get_categories()),
                outputs=[cat_filter],
            )

            refresh_btn.click(
                fn=_update_filter,
                inputs=[search_filter, cat_filter, fav_only],
                outputs=[file_dropdown],
            )

            def _toggle_star(filename: str) -> str:
                if not filename:
                    return "No file selected."
                favs = _load_favorites()
                if filename in favs:
                    favs.remove(filename)
                    _save_favorites(favs)
                    return f"Removed ★ from {filename}"
                else:
                    favs.append(filename)
                    _save_favorites(favs)
                    return f"Added ★ to {filename}"

            star_btn.click(
                fn=_toggle_star,
                inputs=[file_dropdown],
                outputs=[file_msg],
            )

            # ── Cross-File Search ─────────────────────────────────────
            gr.Markdown("---")
            gr.Markdown("### 4. Cross-File Content Search")

            with gr.Row():
                content_query = gr.Textbox(
                    label="Search term",
                    placeholder="e.g. sunset, cyberpunk, dragon...",
                    scale=3,
                )
                content_search_btn = gr.Button("Search All Files", scale=1)

            content_results = gr.Textbox(
                label="Matches (file:line:content)",
                lines=8,
                interactive=False,
            )

            content_search_btn.click(fn=_search_content, inputs=[content_query], outputs=[content_results])
            content_query.submit(fn=_search_content, inputs=[content_query], outputs=[content_results])

        # return components for lifecycle
        self.file_dropdown = file_dropdown
        self.cat_filter = cat_filter
        self.on_tab_outputs = [self.file_dropdown, self.cat_filter]
