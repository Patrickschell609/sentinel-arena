"""
SENTINEL Action Maps - Predefined mappings from scores to actions.

The model outputs a number. The number maps to one of a fixed set of
actions. No text. No explanation. Just: number → action.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple


class Action(Enum):
    """Base actions available across all maps."""
    SAFE = "SAFE"
    UNSAFE = "UNSAFE"
    PROCEED = "PROCEED"
    CAUTION = "CAUTION"
    DENY = "DENY"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class ActionMap:
    """
    Maps a score in [0.0, 1.0] to a discrete action.

    Each threshold is a (upper_bound, action) pair, checked in order.
    The first threshold where score <= upper_bound wins.
    """
    name: str
    thresholds: Tuple[Tuple[float, Action], ...]
    description: str = ""

    def resolve(self, score: float) -> Action:
        """Map a score to an action."""
        for bound, action in self.thresholds:
            if score <= bound:
                return action
        # Score > all bounds - return last action
        return self.thresholds[-1][1]


# --- Predefined maps ---

BINARY_SAFETY = ActionMap(
    name="binary_safety",
    description="Simple safe/unsafe classification",
    thresholds=(
        (0.5, Action.SAFE),
        (1.0, Action.UNSAFE),
    ),
)

TERNARY_GATE = ActionMap(
    name="ternary_gate",
    description="Proceed / Caution / Deny",
    thresholds=(
        (0.33, Action.PROCEED),
        (0.66, Action.CAUTION),
        (1.0, Action.DENY),
    ),
)

CONTENT_MODERATION = ActionMap(
    name="content_moderation",
    description="Content safety with abstain option",
    thresholds=(
        (0.2, Action.SAFE),
        (0.5, Action.CAUTION),
        (0.8, Action.UNSAFE),
        (1.0, Action.DENY),
    ),
)

# Registry of all built-in maps
BUILTIN_MAPS: Dict[str, ActionMap] = {
    "binary_safety": BINARY_SAFETY,
    "ternary_gate": TERNARY_GATE,
    "content_moderation": CONTENT_MODERATION,
}


def get_action_map(name: str) -> ActionMap:
    """Get a built-in action map by name."""
    if name not in BUILTIN_MAPS:
        available = ", ".join(BUILTIN_MAPS.keys())
        raise ValueError(f"Unknown action map '{name}'. Available: {available}")
    return BUILTIN_MAPS[name]
