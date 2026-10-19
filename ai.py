"""AI-assisted wildcard generation for the Wan2GP wildcards plugin.

Two independent backends:

* :func:`compose_variations` - offline, always available. Turns a topic or a
  prompt template into N variations using the *real* wildcard files, with
  deterministic seeds. No GPU, no network, no host imports.
* :class:`PromptEnhancerLLM` - opt-in adapter over Wan2GP's *own* prompt
  enhancer runtime (the local Qwen3.5 / Qwen3.8 or Florence+Llama models
  Wan2GP already ships and can download). It asks the model to invent
  brand-new wildcard entries for a topic.

Importing this module never imports Wan2GP, torch or gradio: every host import
happens lazily inside a call, and every failure is returned as a message
instead of raised, so the plugin tab keeps working with the LLM disabled.
"""

from __future__ import annotations

import random
import re

try:  # imported as part of the package (plugin runtime, tests)
    from . import expander
except ImportError:  # imported as a top-level module (ad-hoc tooling)
    import expander


# Wan2GP's ``server_config["enhancer_enabled"]`` values -> model names.
# Kept in sync with shared/remote_llm/config.py (LOCAL_ENGINE_TO_ENHANCER_ID).
LOCAL_ENGINE_LABELS = {
    0: "Disabled",
    1: "Florence 2 + Llama 3.2 3B (local)",
    2: "Florence 2 + Llama Joy 8B (local)",
    3: "Qwen3.5 VL Abliterated 4B (local, recommended)",
    4: "Qwen3.5 VL Abliterated 9B (local)",
    5: "Qwen3.8 VL Uncensored 27B (local)",
    6: "Qwen3.8 VL Uncensored 9B (local)",
}

# Wildcard keys used to dress up a bare topic when composing offline. Missing
# keys are skipped, so this keeps working on a trimmed-down collection.
_STYLE_TAIL_KEYS = (
    "style",
    "lighting",
    "composition",
    "color-palette",
    "mood",
    "camera",
    "quality",
)

SYSTEM_PROMPT = (
    "You generate wildcard lists for a text-to-image and text-to-video prompt tool.\n"
    "The user gives you a topic. You reply with a plain list of short prompt fragments "
    "about that topic.\n"
    "Rules:\n"
    "- One fragment per line. No numbering, no bullets, no quotes, no headings, no commentary.\n"
    "- Each fragment is 2 to 12 words, concrete and visually descriptive.\n"
    "- Never repeat the same wording twice; keep every line distinct.\n"
    "- Write lowercase fragments unless a proper noun needs capitals.\n"
    "- Output only the list. Never explain what you are doing."
)


class GenerationResult:
    """Outcome of a generation request (never raises)."""

    __slots__ = ("ok", "entries", "raw", "error")

    def __init__(self, ok: bool, entries: list[str] | None = None,
                 raw: str = "", error: str = ""):
        self.ok = ok
        self.entries = entries or []
        self.raw = raw
        self.error = error

    def text(self) -> str:
        """Entries joined one per line ('' when the request failed)."""
        return "\n".join(self.entries)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"GenerationResult(ok={self.ok}, entries={len(self.entries)}, error={self.error!r})"


def engine_label(engine_id: object) -> str:
    """Human label for a Wan2GP prompt-enhancer engine id."""
    try:
        return LOCAL_ENGINE_LABELS.get(int(engine_id), f"Unknown engine ({engine_id})")
    except (TypeError, ValueError):
        return "Unknown engine"


# --------------------------------------------------------------------------
# Text plumbing
# --------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*$")
_ENUM_RE = re.compile(r"^\s*(?:[-*\u2022\u2013\u2014]|\(?\d{1,3}[.)\]]|\[?\d{1,3}\])\s+")
# Prose that commonly wraps a list ("Here are ...", "Note: ...", "List: ...").
# The word must be followed by a word boundary, not by the colon itself, so
# "Note: these are good." is matched while "notes on paper" is not (it is a
# different word, and "notes" is not in the list).
_PREAMBLE_RE = re.compile(
    r"^(here\b|sure\b|certainly\b|of course\b|below\b|the following\b|"
    r"note\b|output\b|list\b|fragments?\b|prompt fragments\b|these\b|those\b|"
    r"each line\b|rules\b|i'm\b|i am\b|i will\b|i can\b|i cannot\b|i can't\b|"
    r"sorry\b|unable\b|as an ai\b|apologies\b)",
    re.IGNORECASE,
)
_QUOTES = "\"'`\u2018\u2019\u201c\u201d*"
# Markdown table rule rows ("| --- |") survive pipe-splitting as dashes/colons.
_TABLE_RULE_RE = re.compile(r"[-:\s]{3,}")


def parse_entries(text: str, limit: int | None = None) -> list[str]:
    """Turn a model reply into clean, de-duplicated wildcard lines.

    Strips code fences, list numbering/bullets, markdown tables and emphasis,
    surrounding quotes and trailing punctuation, drops preambles and lines that
    are too long to be a fragment. Models routinely answer in tables or in bold,
    and ``|`` / ``**`` / ``*`` would otherwise be saved into the user's wildcard
    file and echoed into every prompt that draws from it.
    """
    entries: list[str] = []
    seen: set[str] = set()
    for raw_line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line or _FENCE_RE.match(line):
            continue
        line = _ENUM_RE.sub("", line).strip()
        if "|" in line:
            # Table row: keep the cell contents, drop the pipes.
            line = ", ".join(cell.strip() for cell in line.split("|") if cell.strip())
        line = line.strip(_QUOTES).strip()
        line = line.rstrip(",;:").strip()
        if not line or line.endswith(":"):
            continue
        if _TABLE_RULE_RE.fullmatch(line):
            continue
        if _PREAMBLE_RE.match(line):
            continue
        if len(line) > 300 or len(line.split()) > 40:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        entries.append(line)
        if limit is not None and len(entries) >= limit:
            break
    return entries


def sanitize_for_enhancer(text: str) -> str:
    """Make text safe for Wan2GP's prompt-enhancer user turn.

    The host splits a prompt on ``@@`` / ``@`` and treats the remainder as a
    *system* instruction suffix, so a stray ``@`` would silently rewrite the
    system prompt. Replace it with a plain word.
    """
    return str(text or "").replace("@", " at ")


def build_messages(topic: str, count: int = 20, style: str = "", notes: str = "") -> list[dict]:
    """Build the chat messages asking for ``count`` new wildcard entries."""
    count = max(1, min(200, int(count)))
    parts = [f"Topic: {str(topic or '').strip()}", f"Produce exactly {count} distinct prompt fragments."]
    if style.strip():
        parts.append(f"Lean the vocabulary towards: {style.strip()}")
    if notes.strip():
        parts.append(f"Extra requirements: {notes.strip()}")
    parts.append("Answer with the list only, one fragment per line.")
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(parts)},
    ]


# --------------------------------------------------------------------------
# Offline composer (no LLM)
# --------------------------------------------------------------------------

def _sample(lines: list[str], rng: random.Random) -> str | None:
    clean = [l for l in lines if l]
    if not clean:
        return None
    return rng.choice(clean)


def _style_tail(rng: random.Random) -> str:
    """A tail assembled from real wildcard values, skipping missing files."""
    picks = []
    for key in _STYLE_TAIL_KEYS:
        value = _sample(expander.load_wildcard_lines(key), rng)
        if value:
            picks.append(value)
    return ", ".join(picks[:3])


def compose_variations(text: str, count: int = 6, seed: int | None = None,
                       style_tail: bool = True) -> list[str]:
    """Expand ``text`` into ``count`` variations, offline and deterministically.

    ``text`` may be a prompt template containing ``__wildcards__`` and
    ``{options}``. When it contains neither, the raw text is treated as a topic
    and a small style tail sampled from the collection is appended, so a bare
    topic still produces varied, usable prompts.
    """
    text = str(text or "").strip()
    if not text:
        return []
    count = max(1, min(500, int(count)))
    base_seed = seed

    has_syntax = ("__" in text) or ("{" in text)
    variations: list[str] = []
    seen: set[str] = set()
    attempts = 0
    max_attempts = count * 20
    while len(variations) < count and attempts < max_attempts:
        if base_seed is not None:
            rng = random.Random(base_seed * 1000003 + attempts)
        else:
            rng = random.Random()
        prompt = expander._expand_text(text, rng, depth=0)
        if not has_syntax and style_tail:
            tail = _style_tail(rng)
            if tail:
                prompt = f"{prompt}, {tail}"
        attempts += 1
        if prompt not in seen:
            seen.add(prompt)
            variations.append(prompt)
    return variations


# --------------------------------------------------------------------------
# Wan2GP prompt-enhancer adapter (local Qwen / Florence+Llama)
# --------------------------------------------------------------------------

class PromptEnhancerLLM:
    """Adapter over Wan2GP's local prompt-enhancer runtime.

    All host objects are injected so this class stays importable (and testable)
    without Wan2GP. ``ensure_loaded`` must be Wan2GP's
    ``ensure_prompt_enhancer_loaded`` callable: it downloads the model assets if
    needed and returns ``(model, tokenizer)``. Calling it can unload the user's
    current video model, which is why :meth:`warm_up` is an explicit action.
    """

    def __init__(self, server_config: dict | None = None, ensure_loaded=None,
                 image_caption_model=None, image_caption_processor=None,
                 progress=None):
        self.server_config = server_config if isinstance(server_config, dict) else {}
        self._ensure_loaded = ensure_loaded
        self._image_caption_model = image_caption_model
        self._image_caption_processor = image_caption_processor
        self._progress = progress

    # -- status -----------------------------------------------------------
    @property
    def configured_engine(self) -> int:
        try:
            return int(self.server_config.get("enhancer_enabled", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def available(self) -> bool:
        """True when the host callable was injected and an engine is enabled."""
        return self._ensure_loaded is not None and self.configured_engine > 0

    def status(self) -> dict:
        engine = self.configured_engine
        reachable = self._ensure_loaded is not None
        return {
            "host_reachable": reachable,
            "engine_id": engine,
            "engine_label": engine_label(engine),
            "ready": reachable and engine > 0,
        }

    def status_text(self) -> str:
        info = self.status()
        if not info["host_reachable"]:
            return (
                "Local LLM unavailable: Wan2GP's prompt-enhancer runtime was not exposed to "
                "the plugin (this happens when the plugin runs outside Wan2GP)."
            )
        if info["engine_id"] <= 0:
            return (
                "Local LLM disabled. Enable it in Wan2GP under "
                "Configuration > Extensions > 'Prompt Enhancer / Deepy' and pick a local "
                "Qwen model, then click 'Check LLM again'."
            )
        return (
            f"Local LLM ready to load: {info['engine_label']}. "
            "The model is loaded on first generation (or with 'Load model now'), "
            "which can take a while and may unload the current video model."
        )

    # -- actions ----------------------------------------------------------
    def warm_up(self) -> str:
        """Load the prompt-enhancer runtime now. Returns a status message."""
        if self._ensure_loaded is None:
            return "Local LLM unavailable: the Wan2GP prompt-enhancer runtime was not exposed."
        if self.configured_engine <= 0:
            return (
                "Local LLM disabled. Enable it in Wan2GP under Configuration > Extensions > "
                "'Prompt Enhancer / Deepy' first."
            )
        try:
            self._ensure_loaded(progress=self._progress)
        except Exception as exc:  # gr.Error, torch OOM, download failure, ...
            return f"Could not load the local LLM: {exc}"
        return f"Local LLM loaded ({engine_label(self.configured_engine)})."

    def complete(self, system: str, user: str, *, max_tokens: int = 768,
                 temperature: float = 0.85, top_p: float = 0.9,
                 seed: int | None = None) -> str:
        """Run one text-only generation on the local model. May raise."""
        if self._ensure_loaded is None:
            raise RuntimeError("Wan2GP's prompt-enhancer runtime is not reachable.")
        from shared.prompt_enhancer.prompt_enhance_utils import generate_cinematic_prompt

        model, tokenizer = self._ensure_loaded()
        results = generate_cinematic_prompt(
            self._image_caption_model,
            self._image_caption_processor,
            model,
            tokenizer,
            sanitize_for_enhancer(user),
            images=None,
            video_prompt=False,
            text_prompt=True,
            max_new_tokens=int(max_tokens),
            prompt_enhancer_instructions=system,
            do_sample=True,
            temperature=float(temperature),
            top_p=float(top_p),
            seed=seed,
            thinking_enabled=False,
            inject_duration=False,
        )
        if isinstance(results, str):
            return results
        return (results or [""])[0]

    # -- high level -------------------------------------------------------
    def generate_entries(self, topic: str, *, count: int = 20, style: str = "",
                         notes: str = "", temperature: float = 0.85,
                         seed: int | None = None, max_tokens: int = 768) -> GenerationResult:
        """Ask the local model for ``count`` wildcard entries about ``topic``."""
        topic = str(topic or "").strip()
        if not topic:
            return GenerationResult(False, error="Enter a topic first.")
        if not self.available():
            return GenerationResult(False, error=self.status_text())
        messages = build_messages(topic, count=count, style=style, notes=notes)
        try:
            raw = self.complete(
                messages[0]["content"],
                messages[1]["content"],
                max_tokens=max_tokens,
                temperature=temperature,
                seed=seed,
            )
        except Exception as exc:  # keep the UI alive on OOM / download / cancel
            return GenerationResult(False, error=f"Generation failed: {exc}")
        entries = parse_entries(raw, limit=max(1, min(200, int(count))))
        if not entries:
            return GenerationResult(False, raw=raw, error="The model returned no usable lines. Try again or lower the temperature.")
        return GenerationResult(True, entries=entries, raw=raw)


def build_llm_from_plugin(plugin) -> PromptEnhancerLLM:
    """Wrap a :class:`WildcardsPlugin` instance into a :class:`PromptEnhancerLLM`.

    Reads the globals the plugin requested from Wan2GP; anything missing simply
    leaves the LLM unavailable.
    """
    return PromptEnhancerLLM(
        server_config=getattr(plugin, "server_config", None),
        ensure_loaded=getattr(plugin, "ensure_prompt_enhancer_loaded", None),
        image_caption_model=getattr(plugin, "prompt_enhancer_image_caption_model", None),
        image_caption_processor=getattr(plugin, "prompt_enhancer_image_caption_processor", None),
    )
