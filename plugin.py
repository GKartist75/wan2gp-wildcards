"""Wildcards plugin for Wan2GP.

Monkey-patches prompt_parser.process_template to expand __wildcard__ and
{opt1|opt2} syntax before generation. Adds a UI tab for file management
and test expansion.
"""

import os
import json
import random
import time
import tempfile
import threading
from contextlib import contextmanager

import gradio as gr

from shared.utils.plugins import WAN2GPPlugin
from shared.utils import prompt_parser
from . import expander
from . import character_manager
from . import linter
from . import ai

PLUGIN_ID = "wildcards"
PLUGIN_LABEL = "Wildcards"
WILDCARDS_SUBDIR = "wildcards"  # under plugin dir


def _get_wildcard_keys() -> list[str]:
    """All valid wildcard keys for autocomplete, e.g. __camera__, __camera/shot__.

    Includes directory pools at every depth (a nested folder of lists is a
    usable pool), every real file, and the backward-compat aliases, so the
    dropdown shows both canonical and legacy names.
    """
    wc_dir = expander.WILDCARDS_DIR
    if not os.path.isdir(wc_dir):
        return []
    keys: set[str] = set()
    for root, dirs, _files in os.walk(wc_dir):
        dirs[:] = [d for d in dirs if not d.startswith("__")]
        rel_dir = os.path.relpath(root, wc_dir).replace(os.sep, "/")
        if rel_dir != ".":
            keys.add(f"__{rel_dir}__")  # directory pool (nested included)
    for full in expander.iter_wildcard_files(wc_dir):
        rel = os.path.relpath(full, wc_dir).replace(os.sep, "/")
        keys.add(f"__{rel[:-4]}__")  # strip .txt
    for old_name in expander.WILDCARD_ALIASES:
        keys.add(f"__{old_name}__")
    return sorted(keys)



# Cached file listing (P2): a full os.walk over 3000+ files is ~50ms and was
# done on every search keystroke. Cache with a short TTL; mutations explicitly
# invalidate via invalidate_file_list().
_FILE_LIST_CACHE = {"ts": 0.0, "files": None}
_FILE_LIST_TTL = 1.5  # seconds


def invalidate_file_list() -> None:
    _FILE_LIST_CACHE["files"] = None
    _FILE_LIST_CACHE["ts"] = 0.0


def _list_wc_files() -> list[str]:
    """Recursively list .txt files, excluding __ prefixed metadata files and
    __ prefixed directories. Returns paths relative to wildcards/ with forward
    slashes. Results are cached for FILE_LIST_TTL seconds;
    invalidate_file_list() forces a refresh after any file mutation."""
    wc_dir = expander.WILDCARDS_DIR
    if not os.path.isdir(wc_dir):
        return []
    now = time.time()
    if _FILE_LIST_CACHE["files"] is not None and (now - _FILE_LIST_CACHE["ts"]) < _FILE_LIST_TTL:
        return _FILE_LIST_CACHE["files"]
    files = [
        os.path.relpath(full, wc_dir).replace(os.sep, "/")
        for full in expander.iter_wildcard_files(wc_dir)
    ]
    files.sort()
    _FILE_LIST_CACHE["files"] = files
    _FILE_LIST_CACHE["ts"] = now
    return files


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
        all_files = [p for p in all_files if p.startswith(category + "/")]
    if search:
        q = search.lower()
        all_files = [p for p in all_files if q in p.lower()]
    if favorites_only and favorites:
        all_files = [p for p in all_files if p in favorites]
    return all_files


FAVORITES_FILE = "__favorites__.json"
TEMPLATES_FILE = "__templates__.json"
STATS_FILE = "__stats__.json"


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
    """Persist favorited file paths (atomic write)."""
    path = os.path.join(expander.WILDCARDS_DIR, FAVORITES_FILE)
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(favorites, f)
        os.replace(tmp, path)
        tmp = None
    except OSError as e:
        print(f"[Wildcards] Error saving favorites: {e}")
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _load_templates() -> dict[str, str]:
    """Load saved prompt templates: {name: template_text}."""
    path = os.path.join(expander.WILDCARDS_DIR, TEMPLATES_FILE)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_templates(templates: dict[str, str]):
    """Persist prompt templates. Raises OSError on failure."""
    path = os.path.join(expander.WILDCARDS_DIR, TEMPLATES_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)


def _load_stats() -> dict[str, int]:
    """Load wildcard usage stats: {filepath: count}."""
    path = os.path.join(expander.WILDCARDS_DIR, STATS_FILE)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_stats(stats: dict[str, int]):
    """Persist wildcard usage stats (atomic write)."""
    path = os.path.join(expander.WILDCARDS_DIR, STATS_FILE)
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        tmp = None
    except OSError as e:
        print(f"[Wildcards] Error saving stats: {e}")
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _search_content(query: str) -> str:
    """Search across all wildcard file contents. Returns lines with file:line:match.

    Bounded: max 500 results, and each file's content is sampled to the first
    200 KB to avoid a multi-second stall on the 2.7 MB prompts/misc.txt (P3).
    """
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
                    if len(line) > 200_000:
                        # skip absurdly long lines
                        continue
                    if q in line.lower():
                        snippet = line.rstrip()[:120]
                        results.append(f"{fpath}:{i}: {snippet}")
                    if len(results) >= 500:
                        break
        except Exception:
            continue
        if len(results) >= 500:
            break
    if not results:
        return f"No matches for '{query}'."
    if len(results) >= 500:
        return "\n".join(results) + f"\n... (500+ matches, showing first 500)"
    return "\n".join(results)


def _get_files_for_cat(cat: str) -> list[str]:
    """Files belonging to a category."""
    if not cat or cat == "All":
        return _list_wc_files()
    prefix = cat + "/"
    return [p for p in _list_wc_files() if p.startswith(prefix)]


# --- Wildcard file CRUD ----------------------------------------------------
# Kept at module level (not inside create_ui) so the sanitizing/overwrite rules
# are unit-testable without a browser or Gradio.

def _validate_wc_target(name: str) -> tuple[str | None, str]:
    """Validate a user-supplied relative wildcard filename.

    Returns ``(safe_name, "")`` or ``(None, error_message)``. ``.txt`` is
    appended when missing; ``__``-prefixed paths are refused because they hold
    plugin metadata (favorites/templates/stats/index).
    """
    safe = expander.sanitize_relative_path(name)
    if safe is None:
        return None, "Invalid filename (no absolute paths, '..', or separators other than /)."
    if any(part.startswith("__") for part in safe.split("/")):
        return None, "Names starting with '__' are reserved for plugin metadata."
    if not safe.endswith(".txt"):
        safe += ".txt"
    return safe, ""


def _wc_read_file(filename: str) -> str:
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


def _wc_write_file(filename: str, content: str, *, create_only: bool = False) -> str:
    """Write a wildcard file. ``create_only`` refuses to overwrite (no clobber)."""
    safe, error = _validate_wc_target(filename)
    if safe is None:
        return error
    path = os.path.join(expander.WILDCARDS_DIR, safe)
    if create_only and os.path.exists(path):
        return f"{safe} already exists — pick another name, or open and edit it."
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
    except OSError as e:
        return f"Error saving: {e}"
    expander.invalidate_cache()
    invalidate_file_list()
    return f"Created {safe}" if create_only else f"Saved {safe}"


def _wc_delete_file(filename: str) -> str:
    if not filename:
        return "No file selected."
    safe, error = _validate_wc_target(filename)
    if safe is None:
        return error
    path = os.path.join(expander.WILDCARDS_DIR, safe)
    if not os.path.isfile(path):
        return f"File not found: {safe}"
    try:
        os.remove(path)
    except OSError as e:
        return f"Error deleting: {e}"
    expander.invalidate_cache()
    invalidate_file_list()
    return f"Deleted {safe}"


def _wc_rename_file(old_name: str, new_name: str) -> str:
    """Rename a wildcard file. Refuses reserved names and existing targets."""
    if not old_name or not new_name:
        return "Select a file and enter a new name."
    old_safe, error = _validate_wc_target(old_name)
    if old_safe is None:
        return f"Invalid source file: {error}"
    new_safe, error = _validate_wc_target(new_name)
    if new_safe is None:
        return error
    if old_safe == new_safe:
        return "The new name is identical to the current one."
    old_path = os.path.join(expander.WILDCARDS_DIR, old_safe)
    new_path = os.path.join(expander.WILDCARDS_DIR, new_safe)
    if not os.path.isfile(old_path):
        return f"File not found: {old_safe}"
    if os.path.exists(new_path):
        return f"{new_safe} already exists — delete or rename it first."
    try:
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        os.rename(old_path, new_path)
    except OSError as e:
        return f"Error renaming: {e}"
    expander.invalidate_cache()
    invalidate_file_list()
    return f"Renamed {old_safe} -> {new_safe}"


def _render_chips_html(filename: str, seed: int | None = None) -> str:
    """Read file, pick up to 30 lines, return clickable chip HTML.

    ``seed=None`` (the default) reshuffles the chips on every call, which is
    what the "Shuffle Values" button relies on; pass an int for a repeatable
    preview.
    """
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
    # Sample up to 30 lines WITHOUT shuffling the whole file (P4):
    # shuffling a 2.7 MB file every view is wasteful. Pick a deterministic
    # spread if <30 lines, else a uniform stride sample, then shuffle only that.
    if len(lines) <= 30:
        sample = list(lines)
    else:
        step = len(lines) / 30.0
        sample = [lines[int(i * step)] for i in range(30)]
    rng = random.Random(seed)
    rng.shuffle(sample)
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


# --- Wildcard usage tracking hook ---
# B1: Original implementation wrote stats to disk on EVERY wildcard load
# (read-modify-write of __stats__.json), which (a) made expansion ~4x slower
# and (b) let UI previews pollute real usage counts. Now:
#   - counts are buffered in memory per (thread, request) and flushed to disk
#     only on explicit flush_stats() calls (tab select) or atexit.
#   - preview expansions (test/batch in the UI) are tagged via
#     set_stats_context(track=False) so they NEVER touch usage stats.
#   - writes are guarded by a lock to avoid loss under concurrent threads.
_original_load_lines = expander.load_wildcard_lines

_stats_lock = threading.Lock()
_stats_pending: dict[str, int] = {}
_stats_enabled = True  # master toggle (set False during preview expansions)


def set_stats_context(track: bool) -> None:
    """Control whether the current thread's wildcard loads count toward usage stats.

    UI preview/batch expansions call this with track=False so they don't pollute
    real generation statistics. Prefer the :func:`stats_context` context manager,
    which restores the previous value even if the handler raises.
    """
    _tls_stats_track.value = track


@contextmanager
def stats_context(track: bool):
    """Temporarily set the usage-tracking flag for this thread."""
    previous = getattr(_tls_stats_track, "value", True)
    _tls_stats_track.value = track
    try:
        yield
    finally:
        _tls_stats_track.value = previous


import threading as _th
_tls_stats_track = _th.local()
_tls_stats_track.value = True


def _tracked_load_lines(name: str) -> list[str]:
    lines = _original_load_lines(name)
    if lines and _stats_enabled and getattr(_tls_stats_track, "value", True):
        fname = name.replace("/", "_") + ".txt"
        with _stats_lock:
            _stats_pending[fname] = _stats_pending.get(fname, 0) + 1
    return lines


def flush_stats() -> None:
    """Persist buffered usage counts to disk atomically. Called on tab select
    and at process exit; cheap when nothing is pending."""
    global _stats_pending
    with _stats_lock:
        if not _stats_pending:
            return
        pending = _stats_pending
        _stats_pending = {}
    try:
        stats = _load_stats()
        for k, v in pending.items():
            stats[k] = stats.get(k, 0) + v
        _save_stats(stats)
    except OSError as e:
        print(f"[Wildcards] Error flushing stats: {e}")


import atexit
atexit.register(flush_stats)


# Monkey-patch expander to track usage
expander.load_wildcard_lines = _tracked_load_lines


def _on_tab_select_flush(state):
    flush_stats()
    return None


# state kept on the plugin instance for the monkey-patch
_original_process_template = prompt_parser.process_template
_expansion_enabled = False
_expansion_seed: int | None = None


def _patched_process_template(input_text, keep_comments=False, keep_empty_lines=False):
    """Wrapper: expand wildcards first, then run original template processing."""
    if _expansion_enabled and input_text:
        # Real generation (not a UI preview) -> count toward usage stats.
        set_stats_context(True)
        input_text = expander.expand_prompt(input_text, seed=_expansion_seed)
    return _original_process_template(input_text, keep_comments, keep_empty_lines)


class WildcardsPlugin(WAN2GPPlugin):
    def __init__(self):
        super().__init__()
        self.name = "Wildcards"
        self.version = "1.7.0"
        self.description = "Dynamic wildcard expansion + character profiles + templates + usage stats + AI-assisted generation"
        self.type = ["extension"]

    def setup_ui(self):
        self.request_component("state")
        self.request_component("prompt")
        self.request_component("multi_prompts_gen_type")
        self.request_component("refresh_form_trigger")
        self.request_component("main_tabs")
        self.request_global("get_current_model_settings")
        # Wan2GP's own local prompt enhancer (Qwen3.5/3.8 text models) powers the
        # optional AI generator. Requesting the *callable* instead of the model
        # objects matters: the callable reads Wan2GP's live globals, whereas the
        # model attributes are snapshotted (as None) before the model is loaded.
        self.request_global("server_config")
        self.request_global("ensure_prompt_enhancer_loaded")
        self.request_global("prompt_enhancer_image_caption_model")
        self.request_global("prompt_enhancer_image_caption_processor")
        self.add_tab(tab_id=PLUGIN_ID, label=PLUGIN_LABEL, component_constructor=self.create_ui)

        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        wildcards_path = os.path.join(plugin_dir, WILDCARDS_SUBDIR)
        expander.set_wildcards_dir(wildcards_path)
        character_manager.init(plugin_dir)

        global _expansion_enabled
        _expansion_enabled = True

        prompt_parser.process_template = _patched_process_template

        wc_keys = _get_wildcard_keys()
        KEYS_JSON = json.dumps(wc_keys)
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
        """Refresh the file/category/character dropdowns on every tab visit.

        Also flushes buffered usage stats (B1), invalidates caches (P1/P2) so
        edits made outside the UI are picked up, and re-reads the local-LLM
        status (the user may have just enabled it in the Configuration tab).
        """
        flush_stats()
        expander.invalidate_cache()
        invalidate_file_list()
        char_update = gr.update(choices=character_manager.list_characters())
        try:
            ai_status = ai.build_llm_from_plugin(self).status_text()
        except Exception as e:  # never let a status probe break tab switching
            ai_status = f"Local LLM status unavailable: {e}"
        if hasattr(self, "file_dropdown"):
            cats = ["All"] + _get_categories()
            files = _list_wc_files()
            return [gr.update(choices=files), gr.update(choices=cats), char_update, ai_status]
        return [None, None, char_update, ai_status]

    # This constructor deliberately takes no parameters. Wan2GP inspects the
    # signature to decide whether a plugin wants the API session
    # (shared/utils/plugins.py::_component_constructor_accepts_api): a
    # constructor with a positional parameter is handed a
    # `create_gradio_webui_session()` object and every `gr.Button.click` in it
    # is monkey-patched so session-aware callbacks can submit jobs. This plugin
    # never touches the API session, and taking the parameter is actively
    # harmful: Wan2GP's `_callback_uses_api_session()` compares each handler's
    # referenced globals against `self._session`, which is still `None` while
    # the session is lazily uninitialised, so any handler that merely reads a
    # module-level global holding `None` (here `_expansion_seed`) is
    # mis-detected as session-aware. `_generate_batch` was wrapped that way and
    # then required the main UI's `wangp_main_load_queue_trigger` bridge
    # component. Without the parameter Wan2GP calls the plain `constructor()`
    # path - the same one every official Wan2GP tab plugin uses.
    def create_ui(self):

        def _read_file(filename: str) -> str:
            return _wc_read_file(filename)

        def _save_file(filename: str, content: str) -> str:
            if not filename:
                return "No filename given."
            return _wc_write_file(filename, content)

        def _delete_file(filename: str) -> str:
            return _wc_delete_file(filename)

        def _rename_file(old_name: str, new_name: str) -> tuple[str, gr.update, gr.update]:
            message = _wc_rename_file(old_name, new_name)
            if not message.startswith("Renamed"):
                return message, gr.update(), gr.update()
            files = _list_wc_files()
            cats = ["All"] + _get_categories()
            return message, gr.update(choices=files), gr.update(choices=cats)

        def _refresh_list() -> gr.update:
            return gr.update(choices=_list_wc_files(), value=None)

        def _set_seed(seed_val: int):
            global _expansion_seed
            _expansion_seed = seed_val if seed_val >= 0 else None

        with gr.Column():
            gr.Markdown(f"## Wildcard Prompt Expansion  —  v{self.version}")
            gr.Markdown(
                "> Expansion is active when enabled in the **Plugins** tab. Type `__` in any prompt "
                "for autocomplete.\n>\n"
                "> **Sections:** 1 Prompt Builder · 2 Templates · 3 Character Profiles · "
                "4 File Browser · 5 Usage Stats · 6 Content Search · 7 Linter · 8 AI Generator"
            )

            seed_input = gr.Number(label="Seed (-1 = random)", value=-1, precision=0)
            seed_input.change(fn=_set_seed, inputs=[seed_input])

            # -- Prompt Builder ------------------------------------------
            gr.Markdown("---")
            gr.Markdown("### 1. Prompt Builder")

            with gr.Accordion("\U0001f50d Wildcard Explorer", open=True):
                with gr.Row():
                    wc_cat = gr.Dropdown(label="Category", choices=["All"] + _get_categories(), value="All", scale=2)
                    wc_file = gr.Dropdown(label="File", choices=_list_wc_files() or [], value=None, scale=3, elem_id="wc-file-dd")
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

            def _shuffle_chips(filename: str) -> str:
                # Fresh seed per click so Shuffle always changes something.
                return _render_chips_html(filename, random.randrange(1 << 30))

            wc_cat.change(fn=_filter_cat_files, inputs=[wc_cat], outputs=[wc_file])
            wc_file.change(fn=_render_chips, inputs=[wc_file], outputs=[wc_chips])
            wc_shuffle.click(fn=_shuffle_chips, inputs=[wc_file], outputs=[wc_chips])

            # -- Batch Generation Row --
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
                # Preview: do NOT count toward usage stats (B1), and always
                # restore the tracking flag even if expansion raises.
                with stats_context(False):
                    rng = random.Random(seed_val if seed_val >= 0 else None)
                    return expander.expand_prompt_with_rng(prompt, rng)

            def _generate_batch(prompt_template: str, count: int, seed_mode: str) -> str:
                if not prompt_template:
                    return ""
                # Preview: do NOT count toward usage stats (B1)
                with stats_context(False):
                    count = max(1, min(100, int(count)))
                    if seed_mode.startswith("Sequential"):
                        return "\n".join(
                            expander.expand_prompt_sequential(prompt_template, i)
                            for i in range(count)
                        )
                    # Random mode with optional dedupe, honouring the user's seed
                    # so batches are reproducible (B6).
                    base_seed = _expansion_seed
                    lines: list[str] = []
                    seen: set[str] = set()
                    attempts = 0
                    max_attempts = count * 20
                    while len(lines) < count and attempts < max_attempts:
                        if base_seed is not None:
                            rng = random.Random(base_seed * 1000003 + attempts)
                        else:
                            rng = random.Random()
                        expanded = expander.expand_prompt_with_rng(prompt_template, rng)
                        if expanded not in seen:
                            seen.add(expanded)
                            lines.append(expanded)
                        attempts += 1
                    return "\n".join(lines)

            def _update_prompt_from_state(state_val, batch_text: str):
                if not batch_text:
                    return gr.update()
                settings = self.get_current_model_settings(state_val)
                settings["prompt"] = batch_text
                return time.time()

            test_btn.click(fn=_test_expand, inputs=[prompt_input, seed_input], outputs=[test_output])
            generate_btn.click(fn=_generate_batch, inputs=[prompt_input, batch_count, batch_seed_mode], outputs=[batch_output])
            send_btn.click(
                fn=_update_prompt_from_state,
                inputs=[self.state, batch_output],
                outputs=[self.refresh_form_trigger],
            ).then(
                fn=self.goto_media_tab,
                inputs=[self.state],
                outputs=[self.main_tabs],
            )

            # -- AI Wildcard Generator -------------------------------
            gr.Markdown("---")
            gr.Markdown("### 2. AI Wildcard Generator")
            gr.Markdown(
                "Invents brand-new wildcard entries for a topic using **Wan2GP's own local LLM** "
                "(the Prompt Enhancer / Qwen model already installed with Wan2GP) — or, with no "
                "model loaded, composes variations offline from the wildcards you already have. "
                "Enable the model in Wan2GP under *Configuration > Extensions > Prompt Enhancer / Deepy*."
            )

            def _llm() -> ai.PromptEnhancerLLM:
                return ai.build_llm_from_plugin(self)

            ai_status_output = gr.Textbox(label="Local LLM status", lines=2, interactive=False, value="")
            ai_topic = gr.Textbox(
                label="Topic",
                placeholder="e.g. weathered neon street signs, or ferns, or vintage astronaut helmets",
                lines=1,
            )
            ai_style = gr.Textbox(label="Style / vocabulary hint (optional)", placeholder="e.g. cyberpunk, terse, technical", lines=1)
            with gr.Row():
                ai_count = gr.Number(label="Entries", value=24, precision=0, minimum=1, maximum=200, scale=1)
                ai_temp = gr.Slider(label="Temperature", minimum=0.1, maximum=1.5, value=0.85, step=0.05, scale=2)
                ai_seed = gr.Number(label="Seed (-1 = random)", value=-1, precision=0, scale=1)
            with gr.Row():
                ai_check_btn = gr.Button("Check LLM", size="sm", scale=1)
                ai_load_btn = gr.Button("Load model now", size="sm", scale=1)
                ai_gen_btn = gr.Button("Generate with local LLM", variant="primary", scale=2)
                ai_offline_btn = gr.Button("Compose offline (no LLM)", scale=2)
            ai_output = gr.TextArea(label="Generated entries (one per line — edit freely)", lines=8)
            ai_msg = gr.Textbox(label="Save result", interactive=False)
            with gr.Row():
                ai_save_name = gr.Textbox(label="Save as wildcard file", placeholder="e.g. mytheme/neon-signs", scale=2)
                ai_save_btn = gr.Button("Save as file", scale=1)
                ai_to_template_btn = gr.Button("Send to Prompt Template", scale=1)
                ai_to_batch_btn = gr.Button("Send to Variations box", scale=1)

            def _ai_status() -> str:
                return _llm().status_text()

            def _ai_load():
                with stats_context(False):
                    return _llm().warm_up()

            def _ai_generate(topic, count, style, temperature, seed_val):
                if not topic or not topic.strip():
                    return "Enter a topic first."
                with stats_context(False):
                    llm = _llm()
                    result = llm.generate_entries(
                        topic,
                        count=int(count),
                        style=style or "",
                        temperature=float(temperature),
                        seed=None if seed_val is None or seed_val < 0 else int(seed_val),
                    )
                if not result.ok:
                    return f"{result.error}\n\nGenerated lines so far:\n{result.text()}" if result.entries else result.error
                return result.text()

            def _ai_compose_offline(topic, count, seed_val):
                if not topic or not topic.strip():
                    return "Enter a topic (or a prompt template) first."
                with stats_context(False):
                    variations = ai.compose_variations(
                        topic,
                        count=int(count),
                        seed=None if seed_val is None or seed_val < 0 else int(seed_val),
                    )
                if not variations:
                    return "Nothing to compose — check the topic."
                return "\n".join(variations)

            def _ai_save(name: str, entries: str) -> str:
                if not name or not name.strip():
                    return "Enter a target filename first (e.g. mytheme/neon-signs)."
                lines = [l.strip() for l in (entries or "").splitlines() if l.strip()]
                if not lines:
                    return "Nothing to save — generate entries first."
                return _wc_write_file(name.strip(), "\n".join(lines) + "\n")

            ai_check_btn.click(fn=_ai_status, outputs=[ai_status_output])
            ai_load_btn.click(fn=_ai_load, outputs=[ai_status_output])
            ai_gen_btn.click(
                fn=_ai_generate,
                inputs=[ai_topic, ai_count, ai_style, ai_temp, ai_seed],
                outputs=[ai_output],
            )
            ai_offline_btn.click(
                fn=_ai_compose_offline,
                inputs=[ai_topic, ai_count, ai_seed],
                outputs=[ai_output],
            )
            ai_save_btn.click(fn=_ai_save, inputs=[ai_save_name, ai_output], outputs=[ai_msg])
            ai_to_template_btn.click(
                fn=lambda text: text,
                inputs=[ai_output],
                outputs=[prompt_input],
            )
            ai_to_batch_btn.click(
                fn=lambda text: text,
                inputs=[ai_output],
                outputs=[batch_output],
            )

            # -- Prompt Templates --------------------------------------
            gr.Markdown("---")
            gr.Markdown("### 3. Prompt Templates")
            gr.Markdown("Save and reuse prompt templates with wildcards intact (not expanded).")

            file_msg = gr.Textbox(label="Result", interactive=False)

            templates_dict = _load_templates()
            tmpl_dropdown = gr.Dropdown(
                label="Saved Templates",
                choices=sorted(templates_dict.keys()) if templates_dict else [],
                value=None,
                interactive=True,
            )
            with gr.Row():
                tmpl_name = gr.Textbox(label="Template name", placeholder="e.g. cinematic_portrait", scale=2)
                tmpl_save_btn = gr.Button("Save Current")
                tmpl_load_btn = gr.Button("Load")
                tmpl_delete_btn = gr.Button("Delete")

            def _save_template(name: str, text: str) -> tuple[str, gr.update]:
                if not name or not name.strip():
                    return "Enter a template name.", gr.update()
                name = name.strip()
                templates = _load_templates()
                templates[name] = text
                try:
                    _save_templates(templates)
                except OSError as e:
                    return f"Error saving: {e}", gr.update()
                choices = sorted(templates.keys()) if templates else []
                return f"Template '{name}' saved.", gr.update(choices=choices, value=name)

            def _load_template(name: str) -> tuple[str, gr.update]:
                if not name:
                    return "", gr.update()
                templates = _load_templates()
                text = templates.get(name, "")
                return text, gr.update()

            def _delete_template(name: str) -> tuple[str, gr.update]:
                if not name:
                    return "No template selected.", gr.update()
                templates = _load_templates()
                if name not in templates:
                    return f"Template '{name}' not found.", gr.update()
                del templates[name]
                _save_templates(templates)
                choices = sorted(templates.keys()) if templates else []
                return f"Deleted '{name}'.", gr.update(choices=choices, value=None)

            tmpl_save_btn.click(
                fn=_save_template,
                inputs=[tmpl_name, prompt_input],
                outputs=[file_msg, tmpl_dropdown],
            )
            tmpl_load_btn.click(
                fn=_load_template,
                inputs=[tmpl_dropdown],
                outputs=[prompt_input, file_msg],
            )
            tmpl_delete_btn.click(
                fn=_delete_template,
                inputs=[tmpl_dropdown],
                outputs=[file_msg, tmpl_dropdown],
            )

            # -- Character Profiles --------------------------------------
            gr.Markdown("---")
            gr.Markdown("### 4. Character Profiles")
            _reserved = character_manager.reserved_names()
            _reserved_note = (
                "\n\nReserved names (built-in wildcard lists — pick something else): "
                + ", ".join(f"`{r}`" for r in _reserved)
            ) if _reserved else ""
            gr.Markdown(
                "Define named characters. Use `__character/Name__` in your prompt to inject appearance. "
                "Multi-line appearance = multiple variants. Voice/clothing/tags are metadata for other plugins."
                + _reserved_note
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
                char_export_btn = gr.Button("Export JSON")
                char_import_btn = gr.Button("Import JSON")

            char_msg = gr.Textbox(label="Result", interactive=False)
            char_import_box = gr.Textbox(label="Paste JSON to import", lines=3, placeholder='{"CharacterName": {"appearance": "...", ...}}', visible=False)

            def _load_char(name: str):
                if not name:
                    return "", "", "", "", "", ""
                p = character_manager.get_character(name)
                if not p:
                    return "", "", "", "", "", ""
                return (name, p.get("appearance", ""), p.get("voice", ""), p.get("clothing", ""), p.get("tags", ""), p.get("notes", ""))

            def _clear_char_form():
                return "", "", "", "", "", ""

            def _save_char(name, appearance, voice, clothing, tags, notes):
                profile = {"appearance": appearance, "voice": voice, "clothing": clothing, "tags": tags, "notes": notes}
                msg = character_manager.save_character(name, profile)
                return msg, gr.update(choices=character_manager.list_characters(), value=name)

            def _delete_char(name):
                msg = character_manager.delete_character(name)
                return (msg, gr.update(choices=character_manager.list_characters(), value=None)) + ("",) * 6

            def _export_characters() -> str:
                """Export all character profiles as a JSON string."""
                return character_manager.export_profiles_json()

            def _import_characters(json_str: str) -> tuple[str, gr.update]:
                if not json_str.strip():
                    return "Paste JSON first.", gr.update()
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError as e:
                    return f"Invalid JSON: {e}", gr.update()
                if not isinstance(data, dict):
                    return "JSON must be an object of {name: profile}.", gr.update()
                result = character_manager.import_profiles(data)
                return result.summary(), gr.update(choices=character_manager.list_characters())

            char_dropdown.change(fn=_load_char, inputs=[char_dropdown], outputs=[char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes])
            char_new_btn.click(fn=_clear_char_form, outputs=[char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes])\
                .then(fn=lambda: (gr.update(value=None), ""), outputs=[char_dropdown, char_msg])
            char_save_btn.click(fn=_save_char, inputs=[char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes], outputs=[char_msg, char_dropdown])
            char_delete_btn.click(fn=_delete_char, inputs=[char_dropdown], outputs=[char_msg, char_dropdown, char_name, char_appearance, char_voice, char_clothing, char_tags, char_notes])
            char_export_btn.click(fn=_export_characters, outputs=[char_msg])
            char_import_btn.click(fn=lambda: gr.update(visible=True), outputs=[char_import_box])
            char_import_box.submit(fn=_import_characters, inputs=[char_import_box], outputs=[char_msg, char_dropdown])\
                .then(fn=lambda: gr.update(visible=False), outputs=[char_import_box])

            # -- Wildcard File Browser -----------------------------------
            gr.Markdown("---")
            gr.Markdown("### 5. Wildcard File Browser")
            gr.Markdown("Subdirectories are auto-created when saving a file with `/` in the name (e.g. `mytheme/sunset.txt`).")

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
                fav_only = gr.Checkbox(label="\u2605 Favorites only", value=False)

            file_dropdown = gr.Dropdown(
                label="Wildcard File",
                choices=_list_wc_files() or [],
                value=None,
                interactive=True,
            )

            with gr.Row():
                refresh_btn = gr.Button("Refresh")
                star_btn = gr.Button("\u2605 Toggle Favorite")

            file_editor = gr.TextArea(label="File Content", lines=12)

            file_dropdown.change(
                fn=_read_file,
                inputs=[file_dropdown],
                outputs=[file_editor],
            )

            with gr.Row():
                new_name = gr.Textbox(label="New filename", placeholder="e.g. mytheme/sunset.txt", scale=2)
                create_btn = gr.Button("Create")
                rename_new = gr.Textbox(label="Rename to", placeholder="new_name.txt", scale=2)
                rename_btn = gr.Button("Rename")
                save_btn = gr.Button("Save")
                delete_btn = gr.Button("Delete")

            def _create_file(name: str) -> tuple[str, gr.update, gr.update]:
                if not name:
                    return "No filename given.", gr.update(), gr.update()
                safe, error = _validate_wc_target(name)
                if safe is None:
                    return error, gr.update(), gr.update()
                msg = _wc_write_file(safe, "", create_only=True)
                all_files = _list_wc_files()
                value = safe if safe in all_files else None
                return msg, gr.update(choices=all_files, value=value), gr.update(choices=["All"] + _get_categories())

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

            rename_btn.click(
                fn=_rename_file,
                inputs=[file_dropdown, rename_new],
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
                    return f"Removed \u2605 from {filename}"
                else:
                    favs.append(filename)
                    _save_favorites(favs)
                    return f"Added \u2605 to {filename}"

            star_btn.click(
                fn=_toggle_star,
                inputs=[file_dropdown],
                outputs=[file_msg],
            )

            # -- Wildcard Usage Stats -----------------------------------
            gr.Markdown("---")
            gr.Markdown("### 6. Wildcard Usage Stats")

            def _show_stats() -> str:
                stats = _load_stats()
                if not stats:
                    return "No usage data yet. Generate some prompts first."
                sorted_stats = sorted(stats.items(), key=lambda x: -x[1])
                lines = [f"{fname}: {count} use(s)" for fname, count in sorted_stats[:50]]
                return "\n".join(lines)

            stats_btn = gr.Button("Show Top 50 Used Wildcards")
            stats_output = gr.Textbox(label="Usage Stats", lines=8, interactive=False)
            stats_btn.click(fn=_show_stats, outputs=[stats_output])

            # -- Cross-File Search -------------------------------------
            gr.Markdown("---")
            gr.Markdown("### 7. Cross-File Content Search")

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

            # -- Prompt Linter ----------------------------------------
            gr.Markdown("---")
            gr.Markdown("### 8. Linter")
            gr.Markdown(
                "Checks the current Prompt Template for references that resolve to nothing "
                "(`__name__` typos, `__$var:file__` captures, `__$var__` used without being set), "
                "and can audit the whole collection for broken nested references."
            )

            with gr.Row():
                lint_btn = gr.Button("Check Prompt Template", scale=1)
                lint_all_btn = gr.Button("Audit All Wildcard Files", scale=1)
            lint_output = gr.Textbox(label="Lint Results", lines=10, interactive=False)

            def _lint_prompt(prompt_text: str) -> str:
                if not prompt_text or not prompt_text.strip():
                    return "Enter a prompt template above first."
                return linter.format_text_report(linter.lint_text(prompt_text))

            def _lint_collection() -> str:
                # Preview-style read-only scan: never touch usage stats.
                with stats_context(False):
                    report = linter.lint_collection()
                return linter.format_collection_report(report)

            lint_btn.click(fn=_lint_prompt, inputs=[prompt_input], outputs=[lint_output])
            lint_all_btn.click(fn=_lint_collection, outputs=[lint_output])

        # return components for lifecycle
        self.file_dropdown = file_dropdown
        self.cat_filter = cat_filter
        self.char_dropdown = char_dropdown
        self.ai_status_output = ai_status_output
        self.on_tab_outputs = [self.file_dropdown, self.cat_filter, self.char_dropdown, self.ai_status_output]
