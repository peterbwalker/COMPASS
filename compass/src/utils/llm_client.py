"""
Thin wrapper around the Anthropic API for the COMPASS pipeline.

Centralizes model selection, API key handling, and response parsing so
individual agents don't each reimplement client setup. Keep this file
provider-specific -- if a second provider is ever added, give it its own
module with the same call_llm(prompt, system, ...) -> str interface
rather than branching inside this one.
"""

import os
from typing import Optional

from anthropic import Anthropic

# Pick based on latency/cost/quality needs. claude-sonnet-5 is a reasonable
# default for this pipeline's narrative-generation tasks; swap to
# claude-haiku-4-5-20251001 if you want faster/cheaper responses for
# high-volume calls, or claude-opus-5 if COA quality needs to be higher.
DEFAULT_MODEL = "claude-sonnet-5"

_client: Optional[Anthropic] = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Set it as an environment "
                "variable (or load it from a Colab secret into the "
                "environment) before calling any LLM-backed agent."
            )
        _client = Anthropic(api_key=api_key)
    return _client


def call_claude(
    prompt: str,
    system: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1024,
) -> str:
    """
    Send a single-turn prompt to Claude and return the text response.

    Kept deliberately minimal: agents pass in a fully formed prompt
    string and get back a string. If an agent ever needs multi-turn
    conversation state, that belongs in the calling agent, not here.
    """
    client = get_client()
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    return "".join(block.text for block in response.content if block.type == "text")
