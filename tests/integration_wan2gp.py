"""Optional integration smoke test: load the plugin the way Wan2GP itself does.

Everything here goes through Wan2GP's *real* loader and Gradio instead of the
stubs in `conftest.py`, so it catches things the unit suite cannot: the import
path for a hyphenated plugin directory, the constructor signature contract,
whether the tab actually renders, and whether the wildcard expansion hook fires
inside Wan2GP's own `prompt_parser`.

Run it with Wan2GP's interpreter, from the repo root::

    C:\\Wan2GP\\env_uv\\Scripts\\python.exe tests\\integration_wan2gp.py

Environment overrides:

    WAN2GP_ROOT       Wan2GP checkout   (default: C:\\Wan2GP)
    WAN2GP_PLUGIN_ID  plugin directory  (default: wan2gp-wildcards)

Exit code 0 means every check passed. The run leaves a gitignored
`wildcards/__stats__.json` behind, because step 8 exercises the real usage-stats
hook; it is deleted again mid-run and rewritten at interpreter exit.
"""
import importlib
import inspect
import json
import os
import sys
import traceback

WAN2GP_ROOT = os.environ.get("WAN2GP_ROOT", r"C:\Wan2GP")
PLUGINS_DIR = os.path.join(WAN2GP_ROOT, "plugins")
PLUGIN_ID = os.environ.get("WAN2GP_PLUGIN_ID", "wan2gp-wildcards")

EXPECTED_TAB_ORDER = [
    "### 1. Prompt Builder",
    "### 2. AI Wildcard Generator",
    "### 3. Prompt Templates",
    "### 4. Character Profiles",
    "### 5. Wildcard File Browser",
    "### 6. Wildcard Usage Stats",
    "### 7. Cross-File Content Search",
    "### 8. Linter",
]

failures: list[str] = []

if not os.path.isdir(PLUGINS_DIR):
    sys.exit(f"Wan2GP not found at {WAN2GP_ROOT!r}; set WAN2GP_ROOT to your checkout.")

for entry in (WAN2GP_ROOT, PLUGINS_DIR):
    if entry not in sys.path:
        sys.path.insert(0, entry)


def banner(text: str) -> None:
    print()
    print("=" * 72)
    print(text)
    print("=" * 72)


def check(label: str, fn) -> None:
    """Run one smoke check, reporting rather than aborting."""
    try:
        text = str(fn())
        if len(text) > 90:
            text = text[:87] + "..."
        print(f"  OK   {label} -> {text}")
    except Exception as exc:  # noqa: BLE001 - a report is the point
        print(f"  FAIL {label}: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        failures.append(label)


# ---------------------------------------------------------------- 1. discovery
banner("1. discovery (PluginManager.discover_plugins)")
path = os.path.join(PLUGINS_DIR, PLUGIN_ID)
print("  link target :", os.path.realpath(path))
discovered = [
    item
    for item in os.listdir(PLUGINS_DIR)
    if not item.endswith(".bak")
    and os.path.isdir(os.path.join(PLUGINS_DIR, item))
    and (
        os.path.exists(os.path.join(PLUGINS_DIR, item, "__init__.py"))
        or os.path.exists(os.path.join(PLUGINS_DIR, item, "plugin.py"))
    )
]
print("  discovered  :", sorted(discovered))
if PLUGIN_ID in discovered:
    print("  OK   plugin discovered")
else:
    failures.append("discovery")
    print(f"  FAIL {PLUGIN_ID} not discovered in {PLUGINS_DIR}")

# ---------------------------------------------------------------- 2. metadata
banner("2. metadata (PluginManager._load_plugin_metadata)")
meta = json.load(open(os.path.join(path, "plugin_info.json"), encoding="utf-8"))
for key in ("name", "version", "type", "date", "description"):
    print(f"  {key + ':':12} {meta.get(key)}")

# ------------------------------------------------------------------ 3. import
banner("3. import exactly like the loader")
try:
    module = importlib.import_module(f"{PLUGIN_ID}.plugin")
    print(f"  OK   import {PLUGIN_ID}.plugin")
    print("       __name__    =", module.__name__)
    print("       __package__ =", module.__package__)
except Exception as exc:  # noqa: BLE001
    print(f"  FAIL import: {type(exc).__name__}: {exc}")
    traceback.print_exc()
    sys.exit(1)

# -------------------------------------------------- 4. class + instantiation
banner("4. plugin class discovery + instantiation")
from shared.utils.plugins import WAN2GPApplication, WAN2GPPlugin  # noqa: E402

classes = [
    obj
    for _name, obj in inspect.getmembers(module, inspect.isclass)
    if issubclass(obj, WAN2GPPlugin) and obj is not WAN2GPPlugin
]
print("  WAN2GPPlugin subclasses:", [c.__name__ for c in classes])
if not classes:
    sys.exit("no WAN2GPPlugin subclass found")
plugin = classes[0]()
print(f"  OK   {plugin.name} v{plugin.version} type={plugin.type}")

# --------------------------------------------------------------- 5. setup_ui
banner("5. setup_ui()")
plugin.setup_ui()
print("  component requests  :", plugin.component_requests)
print("  global requests     :", plugin.global_requests)
print("  tabs                :", {k: v.label for k, v in plugin.tabs.items()})
print("  expander dir        :", module.expander.WILDCARDS_DIR)
print("  expansion enabled   :", module._expansion_enabled)
print(
    "  prompt_parser patched:",
    module.prompt_parser.process_template is module._patched_process_template,
)
if plugin.tabs:
    print("  OK   tab registered")
else:
    failures.append("tab registration")
    print("  FAIL tab not registered")

# ------------------------------------------- 6. real Gradio UI construction
banner("6. real Gradio UI construction (_create_plugin_tabs)")
import gradio as gr  # noqa: E402

print("  gradio version:", gr.__version__)

tab_id = next(iter(plugin.tabs))
constructor = plugin.tabs[tab_id].component_constructor
uses_api = WAN2GPApplication._component_constructor_accepts_api(constructor)
print("  _component_constructor_accepts_api ->", uses_api)
if uses_api:
    failures.append("constructor opts into the api session")
    print("  FAIL the constructor must not take a positional parameter")

# Count API-session wrapping attempts. Wan2GP only wraps click handlers when the
# constructor opted into the API session, and a wrapped handler is routed through
# the main UI's job bridge - something a plain plugin tab neither wants nor has.
from shared.api_webui import GradioWanGPSession  # noqa: E402

wrapped_calls: list[str] = []
_original_wrap = GradioWanGPSession._wrap_button_click


def _counting_wrap(self, original_click, button, *args, **kwargs):
    fn = kwargs.get("fn")
    wrapped_calls.append(getattr(fn, "__qualname__", repr(fn)))
    return _original_wrap(self, original_click, button, *args, **kwargs)


GradioWanGPSession._wrap_button_click = _counting_wrap

# The manager injects these before calling the constructor
# (plugins.py attaches goto_media_tab; inject_globals attaches the rest).
plugin.goto_media_tab = lambda state: gr.Tabs(selected="media_gen")
plugin.state = gr.State({})
plugin.prompt = gr.Textbox()
plugin.multi_prompts_gen_type = gr.Dropdown(choices=[])
plugin.refresh_form_trigger = gr.Number()
plugin.main_tabs = gr.Tabs()
plugin.get_current_model_settings = lambda state=None: {}
plugin.server_config = {"enhancer_enabled": 3}
plugin.ensure_prompt_enhancer_loaded = lambda **kwargs: (None, None)
plugin.prompt_enhancer_image_caption_model = None
plugin.prompt_enhancer_image_caption_processor = None

try:
    with gr.Blocks() as demo:
        # what _create_plugin_tabs does for one tab
        with gr.Tab(plugin.tabs[tab_id].label, id=f"plugin_{tab_id}"):
            if uses_api:
                from shared.api import create_gradio_webui_session

                plugin._wangp_session = create_gradio_webui_session(plugin)
                with plugin._wangp_session.plugin_ui_context():
                    constructor(plugin._wangp_session)
            else:
                constructor()
    blocks = demo.blocks
    kinds = {}
    for block in blocks.values():
        kinds[type(block).__name__] = kinds.get(type(block).__name__, 0) + 1
    print(f"  OK   UI built: {len(blocks)} gradio blocks")
    print("       " + ", ".join(f"{k} x{v}" for k, v in sorted(kinds.items(), key=lambda kv: -kv[1])))
    if len(blocks) < 40:
        failures.append("UI build too small")
        print(f"  FAIL only {len(blocks)} blocks - the tab looks empty")
    else:
        print("  OK   tab is populated")

    headings = [
        b.value
        for b in blocks.values()
        if isinstance(b, gr.Markdown)
        and isinstance(b.value, str)
        and b.value.startswith("### ")
    ]
    print("  headings, in build order:")
    for heading in headings:
        print("       " + heading)
    if headings == EXPECTED_TAB_ORDER:
        print("  OK   section order matches the README")
    else:
        failures.append("section order")
        print("  FAIL unexpected section order")
        print("       expected:", EXPECTED_TAB_ORDER)
except Exception as exc:  # noqa: BLE001
    print(f"  FAIL UI build: {type(exc).__name__}: {exc}")
    traceback.print_exc()
    failures.append("UI build")

if wrapped_calls:
    failures.append("click handlers wrapped as api callbacks")
    print(f"  FAIL click handlers wrapped: {wrapped_calls}")
else:
    print("  OK   no click handler was wrapped as an api-session callback")

# --------------------------------------------------------- 7. on_tab_outputs
banner("7. on_tab_outputs (tab-select wiring)")
outputs = getattr(plugin, "on_tab_outputs", None)
print("  on_tab_outputs:", [type(o).__name__ for o in outputs] if outputs else outputs)
if outputs is not None and len(outputs) == 4:
    print("  OK   4 outputs")
else:
    failures.append("on_tab_outputs arity")
    print("  FAIL expected exactly 4 outputs")

# ------------------------------------------------ 8. expansion through Wan2GP
banner("8. prompt_parser monkey-patch (Wan2GP's real expansion path)")
from shared.utils import prompt_parser  # noqa: E402

for label, source in (
    ("legacy alias", "A __camera_shot__ of a hero"),
    ("capture variables", "A __camera/shot__ of __$who:characters/names__, __$who__ again"),
):
    out = prompt_parser.process_template(source)
    expanded = out[0] if isinstance(out, (tuple, list)) else out
    print(f"  in : {source}")
    print(f"  out: {expanded!r}")
    if "__" in str(expanded):
        failures.append(f"expansion via process_template ({label})")
        print("  FAIL wildcard left unexpanded")
    else:
        print("  OK   expanded")

stats_path = os.path.join(module.expander.WILDCARDS_DIR, module.STATS_FILE)
try:
    module.flush_stats()
    if os.path.isfile(stats_path):
        stats = json.load(open(stats_path, encoding="utf-8"))
        print(f"  OK   usage stats flushed ({len(stats)} entries, gitignored)")
        os.remove(stats_path)
    else:
        failures.append("usage stats flush")
        print("  FAIL no stats file was written")
except Exception as exc:  # noqa: BLE001
    failures.append("usage stats flush")
    print(f"  FAIL stats flush: {type(exc).__name__}: {exc}")

# ------------------------------------------------------ 9. capability checks
banner("9. public API smoke checks (real modules, real collection)")
expander = module.expander
ai = module.ai
linter = module.linter
cm = module.character_manager

check("legacy alias __camera_shot__", lambda: expander.expand_prompt("__camera_shot__", seed=1))
check("case-insensitive __CAMERA/SHOT__", lambda: expander.expand_prompt("__CAMERA/SHOT__", seed=1))
check("nested __creatures/wings__", lambda: expander.expand_prompt("__creatures/wings__", seed=1))
check(
    "capture group stability",
    lambda: expander.expand_prompt("__$a:characters/names__ / __$b:characters/names__. __$a__ / __$b__", seed=3),
)
check("manual variable __$f=apple__", lambda: expander.expand_prompt("__$f=apple__ __$f__", seed=1))
check("sequential mode", lambda: [expander.expand_prompt_sequential("__camera/shot__", i) for i in range(2)])
check("unknown ref left intact", lambda: expander.expand_prompt("__nope/missing__", seed=1))
check("offline composer (no LLM)", lambda: len(ai.compose_variations("a neon sign", count=3, seed=5)))
check("LLM status text", lambda: ai.build_llm_from_plugin(plugin).status_text().splitlines()[0])
check(
    "linter report",
    lambda: linter.format_text_report(linter.lint_text("A __camera/shot__ of __nope/missing__")).splitlines()[0],
)
check("linter: collection scan", lambda: len(linter.lint_collection(expander.WILDCARDS_DIR)["broken"]) == 0)
check("reserved character names", lambda: len(cm.reserved_names()) > 0)
check("character profile store loads", lambda: isinstance(cm.load_profiles(), dict))
check("wildcard file count", lambda: len(expander.iter_wildcard_files()))
check("sanitize_relative_path('../../evil')", lambda: expander.sanitize_relative_path("../../evil"))

banner("RESULT")
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for item in failures:
        print("  -", item)
else:
    print("ALL CHECKS PASSED")
print("=" * 72)
sys.exit(1 if failures else 0)
