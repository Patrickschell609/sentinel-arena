"""
Unified attack loader - loads all attack vectors from all categories.

Each attack is a simple dataclass with a prompt, category, and metadata.
These are published jailbreak techniques used for defensive benchmarking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class AttackCategory(Enum):
    JAILBREAKBENCH = "jailbreakbench"
    COT_HIJACK = "cot_hijack"
    AUTODAN = "autodan"
    ENCODING = "encoding"
    ROLE_PLAY = "role_play"
    MULTI_TURN = "multi_turn"
    CUSTOM = "custom"


@dataclass
class Attack:
    """A single attack vector."""
    id: str
    prompt: str
    category: AttackCategory
    description: str = ""
    source: str = ""  # Paper or dataset reference
    turns: List[str] = field(default_factory=list)  # For multi-turn attacks
    expected_behavior: str = ""  # What a jailbroken model would do

    @property
    def is_multi_turn(self) -> bool:
        return len(self.turns) > 0


def load_all_attacks(
    categories: Optional[List[AttackCategory]] = None,
    limit_per_category: Optional[int] = None,
) -> List[Attack]:
    """
    Load all attack vectors from all categories.

    Args:
        categories: Filter to specific categories. None = all.
        limit_per_category: Max attacks per category. None = all.

    Returns:
        List of Attack objects.
    """
    from . import jailbreakbench as jbb
    from . import cot_hijack
    from . import autodan
    from . import encoding
    from . import role_play
    from . import multi_turn
    from . import custom

    loaders = {
        AttackCategory.JAILBREAKBENCH: jbb.load_attacks,
        AttackCategory.COT_HIJACK: cot_hijack.load_attacks,
        AttackCategory.AUTODAN: autodan.load_attacks,
        AttackCategory.ENCODING: encoding.load_attacks,
        AttackCategory.ROLE_PLAY: role_play.load_attacks,
        AttackCategory.MULTI_TURN: multi_turn.load_attacks,
        AttackCategory.CUSTOM: custom.load_attacks,
    }

    if categories:
        loaders = {k: v for k, v in loaders.items() if k in categories}

    all_attacks = []
    for cat, loader_fn in loaders.items():
        attacks = loader_fn()
        if limit_per_category:
            attacks = attacks[:limit_per_category]
        all_attacks.extend(attacks)

    return all_attacks
