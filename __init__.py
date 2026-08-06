"""Wildcards prompt expansion plugin for Wan2GP.

Provides __wildcard__ expansion, {opt1|opt2} inline variants,
N::weighted choices, __$var=value__ literal variables,
__$var:file__ named capture variables,
character profiles, prompt templates, and a full Gradio UI.
"""

from . import expander
from . import character_manager
from .plugin import WildcardsPlugin
