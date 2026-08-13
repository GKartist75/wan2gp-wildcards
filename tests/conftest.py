"""Tests conftest: load plugin modules under synthetic package `wp`.

Placing config in tests/ makes tests/ the pytest rootdir, so the repo-root
__init__.py is collected as part of the `wp` package. Its `from .plugin import
WildcardsPlugin` pulls in gradio + Wan2GP `shared`, which aren't installed in
this test venv. We stub those heavy imports so the package can initialize,
while keeping expander and character_manager as the REAL on-disk modules.
"""
import os
import sys
import types
import importlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# --- Stub heavy third-party / host deps so __init__ -> plugin can import ---
for _mod in ("gradio", "shared", "shared.utils", "shared.utils.plugins",
             "shared.utils.prompt_parser"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

# Minimal stub for WAN2GPPlugin base class used by plugin.py
_shared_utils_plugins = sys.modules["shared.utils.plugins"]
_shared_utils_plugins.WAN2GPPlugin = object

# prompt_parser needs a process_template attribute (referenced at import time)
_shared_utils_prompt_parser = sys.modules["shared.utils.prompt_parser"]
_shared_utils_prompt_parser.process_template = lambda *a, **k: ("", "")

# Make `gradio` expose the names plugin.py touches at import time.
_gr = sys.modules["gradio"]
for _name in ("Column", "Markdown", "Dropdown", "Textbox", "TextArea", "Button",
              "Radio", "Number", "Checkbox", "HTML", "Row", "Accordion", "State"):
    setattr(_gr, _name, object)
_gr.update = object

# --- Build the synthetic package `wp` = repo root ---
if "wp" not in sys.modules:
    pkg = types.ModuleType("wp")
    pkg.__path__ = [REPO]
    pkg.__package__ = "wp"
    sys.modules["wp"] = pkg
    expander = importlib.import_module("wp.expander")
    character_manager = importlib.import_module("wp.character_manager")
    expander.set_wildcards_dir(os.path.join(REPO, "wildcards"))
    sys.modules["expander"] = expander
    sys.modules["character_manager"] = character_manager

collect_ignore_glob = ["__init__.py"]
