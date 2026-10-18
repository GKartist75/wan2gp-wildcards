"""Unit tests for the AI helpers (offline composer + LLM plumbing).

The LLM itself is never called: PromptEnhancerLLM is driven with a fake
``ensure_loaded`` so the parsing, status and error handling can be tested
without Wan2GP, torch or a GPU.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import ai  # noqa: E402


# ── parsing ────────────────────────────────────────────────────────────────

def test_parse_entries_strips_fences_numbering_and_quotes():
    raw = """Here are your entries:
```text
1. weathered neon sign
2) "cracked glass tubing"
- flickering gas lamp
* burnt-out letter
```
Note: these should work well.
"""
    assert ai.parse_entries(raw) == [
        "weathered neon sign",
        "cracked glass tubing",
        "flickering gas lamp",
        "burnt-out letter",
    ]


def test_parse_entries_dedupes_case_insensitively():
    assert ai.parse_entries("Sunset\nsunset\nSUNSET\n") == ["Sunset"]


def test_parse_entries_ignores_prose_lines():
    raw = "sure, here you go\nrain on glass\nlist: things to try\ncity at night\n"
    entries = ai.parse_entries(raw)
    assert entries == ["rain on glass", "city at night"]


def test_parse_entries_respects_limit():
    raw = "\n".join(f"value {i}" for i in range(50))
    assert len(ai.parse_entries(raw, limit=5)) == 5


def test_parse_entries_drops_absurdly_long_lines():
    raw = "ok value\n" + ("word " * 100) + "\nanother value\n"
    assert ai.parse_entries(raw) == ["ok value", "another value"]


def test_parse_entries_handles_empty_input():
    assert ai.parse_entries("") == []
    assert ai.parse_entries(None) == []


def test_sanitize_for_enhancer_removes_at_signs():
    # Wan2GP's enhancer splits a prompt on @/@@ and treats the tail as a system
    # instruction; '@' must never reach it from generated text.
    assert "@" not in ai.sanitize_for_enhancer("user@example.com @mention")


def test_build_messages_includes_topic_count_and_style():
    messages = ai.build_messages("brass instruments", count=7, style="vintage")
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    body = messages[1]["content"]
    assert "brass instruments" in body
    assert "7" in body
    assert "vintage" in body


def test_build_messages_clamps_count():
    assert "200" in ai.build_messages("x", count=9999)[1]["content"]
    assert "1" in ai.build_messages("x", count=0)[1]["content"]


# ── engine labels ──────────────────────────────────────────────────────────

def test_engine_label_known_and_unknown():
    assert "Qwen" in ai.engine_label(3)
    assert ai.engine_label(99).startswith("Unknown")
    assert ai.engine_label(None).startswith("Unknown")


# ── offline composer ───────────────────────────────────────────────────────

def test_compose_variations_is_deterministic_with_seed():
    a = ai.compose_variations("a __camera/shot__ of __color/named__", count=5, seed=99)
    b = ai.compose_variations("a __camera/shot__ of __color/named__", count=5, seed=99)
    assert a == b
    assert len(a) == 5
    assert all("__" not in line for line in a)


def test_compose_variations_differ_between_seeds():
    a = ai.compose_variations("__color/named__", count=8, seed=1)
    b = ai.compose_variations("__color/named__", count=8, seed=2)
    assert a != b


def test_compose_variations_adds_a_style_tail_for_a_bare_topic():
    lines = ai.compose_variations("a lonely lighthouse", count=3, seed=5, style_tail=True)
    assert len(lines) == 3
    assert all(line.startswith("a lonely lighthouse, ") for line in lines)


def test_compose_variations_without_style_tail():
    # A literal topic with no wildcard syntax can only produce one unique line;
    # duplicates are dropped rather than padded.
    lines = ai.compose_variations("a lonely lighthouse", count=2, seed=5, style_tail=False)
    assert lines == ["a lonely lighthouse"]


def test_compose_variations_returns_nothing_for_empty_text():
    assert ai.compose_variations("", count=4) == []
    assert ai.compose_variations("   ", count=4) == []


# ── LLM adapter (no host, no GPU) ──────────────────────────────────────────

def test_status_reports_unavailable_without_host():
    llm = ai.PromptEnhancerLLM(server_config={"enhancer_enabled": 3})
    info = llm.status()
    assert info["host_reachable"] is False
    assert info["ready"] is False
    assert "not exposed" in llm.status_text()


def test_status_reports_disabled_engine():
    llm = ai.PromptEnhancerLLM(server_config={"enhancer_enabled": 0}, ensure_loaded=lambda **k: None)
    assert llm.status()["engine_id"] == 0
    assert "disabled" in llm.status_text().lower()


def test_status_reports_ready_engine():
    llm = ai.PromptEnhancerLLM(server_config={"enhancer_enabled": 4}, ensure_loaded=lambda **k: None)
    info = llm.status()
    assert info["ready"] is True
    assert "Qwen3.5" in info["engine_label"]


def test_warm_up_without_host_is_a_message_not_an_exception():
    llm = ai.PromptEnhancerLLM()
    assert "unavailable" in llm.warm_up().lower()


def test_warm_up_surfaces_load_errors():
    def boom(**kwargs):
        raise RuntimeError("CUDA out of memory")

    llm = ai.PromptEnhancerLLM(server_config={"enhancer_enabled": 3}, ensure_loaded=boom)
    assert "CUDA out of memory" in llm.warm_up()


def test_generate_entries_requires_a_topic():
    llm = ai.PromptEnhancerLLM(server_config={"enhancer_enabled": 3}, ensure_loaded=lambda **k: None)
    result = llm.generate_entries("   ")
    assert result.ok is False
    assert "topic" in result.error.lower()


def test_generate_entries_without_engine_fails_cleanly():
    llm = ai.PromptEnhancerLLM(server_config={"enhancer_enabled": 0})
    result = llm.generate_entries("brass instruments")
    assert result.ok is False
    assert result.entries == []


def _fake_llm(reply, engine=3):
    """Build a PromptEnhancerLLM whose complete() returns ``reply``."""
    llm = ai.PromptEnhancerLLM(
        server_config={"enhancer_enabled": engine},
        ensure_loaded=lambda **kwargs: (object(), object()),
    )
    llm.complete = lambda *a, **k: reply  # type: ignore[assignment]
    return llm


def test_generate_entries_parses_the_model_reply():
    llm = _fake_llm("1. brass trumpet\n2. dented euphonium\n3. polished tuba\n")
    result = llm.generate_entries("brass instruments", count=3)
    assert result.ok is True
    assert result.entries == ["brass trumpet", "dented euphonium", "polished tuba"]
    assert result.text().splitlines()[0] == "brass trumpet"


def test_generate_entries_reports_unusable_reply():
    llm = _fake_llm("I'm sorry, I cannot help with that.")
    result = llm.generate_entries("brass instruments", count=3)
    assert result.ok is False
    assert "no usable lines" in result.error


def test_generate_entries_swallows_generation_exceptions():
    llm = _fake_llm("")
    llm.complete = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("cancelled"))
    result = llm.generate_entries("brass instruments")
    assert result.ok is False
    assert "cancelled" in result.error


def test_build_llm_from_plugin_reads_requested_globals():
    class FakePlugin:
        server_config = {"enhancer_enabled": 5}
        ensure_prompt_enhancer_loaded = staticmethod(lambda **k: (object(), object()))
        prompt_enhancer_image_caption_model = None
        prompt_enhancer_image_caption_processor = None

    llm = ai.build_llm_from_plugin(FakePlugin())
    assert llm.configured_engine == 5
    assert llm.available() is True


def test_build_llm_from_plugin_without_globals_is_unavailable():
    class EmptyPlugin:
        pass

    llm = ai.build_llm_from_plugin(EmptyPlugin())
    assert llm.available() is False
