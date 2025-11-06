# ============================================================
# rolling/stat_rolls.py
# ============================================================
from __future__ import annotations

import random
from typing import Sequence

# Canonical ability order
ABILITY_ORDER: tuple[str, ...] = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
ABILITIES: tuple[str, ...]     = ABILITY_ORDER

# Priority triplets for mapping top rolls
CLASS_PRIORITIES = {
    "barbarian": ("STR", "CON", "DEX"),
    "fighter":   ("STR", "CON", "DEX"),
    "paladin":   ("STR", "CHA", "CON"),
    "ranger":    ("DEX", "WIS", "CON"),
    "monk":      ("DEX", "WIS", "CON"),
    "rogue":     ("DEX", "INT", "CHA"),
    "bard":      ("CHA", "DEX", "CON"),
    "cleric":    ("WIS", "CON", "STR"),
    "druid":     ("WIS", "CON", "DEX"),
    "wizard":    ("INT", "CON", "DEX"),
    "sorcerer":  ("CHA", "CON", "DEX"),
    "warlock":   ("CHA", "CON", "DEX"),
    "artificer": ("INT", "CON", "DEX"),
    "blood hunter": ("DEX", "CON", "STR"),
}

def _randint(rng, a: int, b: int) -> int:
    if rng is None:
        return random.randint(a, b)
    if hasattr(rng, "randint"):
        return rng.randint(a, b)  # type: ignore[attr-defined]
    if hasattr(rng, "_rng") and hasattr(rng._rng, "randint"):
        return rng._rng.randint(a, b)  # type: ignore[attr-defined]
    return random.randint(a, b)

def _roll_dice(n: int, die: int, rng=None) -> list[int]:
    return [_randint(rng, 1, die) for _ in range(max(0, n))]

# -------- 4d6 drop lowest --------
def roll_4d6_drop_lowest(rng=None) -> int:
    rolls = _roll_dice(4, 6, rng)
    return sum(sorted(rolls)[1:])

def _roll_six_scores(rng=None) -> list[int]:
    return [roll_4d6_drop_lowest(rng) for _ in range(6)]

def roll_abilities_list(rng=None) -> list[int]:
    """Kept for API; now uses 4d6 drop lowest."""
    return _roll_six_scores(rng)

def roll_abilities_dict_flat(rng=None, order: Sequence[str] = ABILITY_ORDER) -> dict[str, int]:
    """Even assignment in the given order (rarely used)."""
    scores = _roll_six_scores(rng)
    return {k: scores[i] for i, k in enumerate(order)}

def roll_abilities_for_class(class_name: str, rng=None) -> dict[str, int]:
    """
    4d6 drop-lowest ×6, then assign the highest scores to the class’s
    primary/secondary/tertiary, remaining scores fill the leftover abilities.
    """
    scores = sorted(_roll_six_scores(rng), reverse=True)
    cls = (class_name or "").strip().lower()
    prio = CLASS_PRIORITIES.get(cls, ("STR", "DEX", "CON"))

    # start with empty mapping
    out: dict[str, int] = {k: 0 for k in ABILITY_ORDER}

    # assign top three to priorities
    for i, stat in enumerate(prio):
        out[stat] = scores[i]

    # fill the rest to the remaining ability keys
    remaining_keys = [k for k in ABILITY_ORDER if k not in prio]
    remaining_scores = scores[len(prio):]
    for k, v in zip(remaining_keys, remaining_scores):
        out[k] = v

    return out

# reuse your existing helper
from .roller import ability_mod

def ability_mods_from_scores(scores: dict[str, int]) -> dict[str, int]:
    return {k: ability_mod(v) for k, v in scores.items()}

__all__ = [
    "ABILITY_ORDER",
    "ABILITIES",
    "CLASS_PRIORITIES",
    "roll_4d6_drop_lowest",
    "roll_abilities_list",
    "roll_abilities_dict_flat",
    "roll_abilities_for_class",
    "ability_mods_from_scores",
]
