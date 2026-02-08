"""
Model target configurations.

Defines which models to test and how to reach them.
Primary: Ollama local models ($0). Optional: Claude Haiku (~$0.50).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ModelTarget:
    """A model to benchmark against."""
    name: str           # Human-readable name
    model_id: str       # litellm model ID
    provider: str       # ollama, anthropic, openai
    is_local: bool      # True = free, False = costs money
    max_tokens: int = 1024
    temperature: float = 0.7
    rpm_limit: int = 0  # Requests per minute limit (0 = unlimited)


# --- Built-in targets ---

OLLAMA_LLAMA3_2 = ModelTarget(
    name="Llama 3.2 3B",
    model_id="ollama/llama3.2:3b",
    provider="ollama",
    is_local=True,
)

OLLAMA_MISTRAL = ModelTarget(
    name="Mistral 7B",
    model_id="ollama/mistral:7b",
    provider="ollama",
    is_local=True,
)

OLLAMA_GEMMA2 = ModelTarget(
    name="Gemma 2 2B",
    model_id="ollama/gemma2:2b",
    provider="ollama",
    is_local=True,
)

OLLAMA_QWEN = ModelTarget(
    name="Qwen 2.5 3B",
    model_id="ollama/qwen2.5:3b",
    provider="ollama",
    is_local=True,
)

CLAUDE_HAIKU = ModelTarget(
    name="Claude Haiku",
    model_id="anthropic/claude-haiku-4-5-20251001",
    provider="anthropic",
    is_local=False,
    rpm_limit=30,
)

# Registry
BUILTIN_TARGETS: Dict[str, ModelTarget] = {
    "ollama/llama3.2:3b": OLLAMA_LLAMA3_2,
    "ollama/mistral:7b": OLLAMA_MISTRAL,
    "ollama/gemma2:2b": OLLAMA_GEMMA2,
    "ollama/qwen2.5:3b": OLLAMA_QWEN,
    "anthropic/claude-haiku": CLAUDE_HAIKU,
}

# Default free models for full runs
DEFAULT_LOCAL_MODELS = ["ollama/llama3.2:3b"]


def get_target(model_id: str) -> ModelTarget:
    """Get a target by model ID. Creates a generic one if not built-in."""
    if model_id in BUILTIN_TARGETS:
        return BUILTIN_TARGETS[model_id]
    # Create a generic target
    provider = model_id.split("/")[0] if "/" in model_id else "unknown"
    return ModelTarget(
        name=model_id,
        model_id=model_id,
        provider=provider,
        is_local=(provider == "ollama"),
    )


def list_targets(local_only: bool = False) -> List[ModelTarget]:
    """List all built-in targets."""
    targets = list(BUILTIN_TARGETS.values())
    if local_only:
        targets = [t for t in targets if t.is_local]
    return targets
