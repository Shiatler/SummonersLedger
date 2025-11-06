# ============================================================
# systems/heal.py — D&D-style healing helpers
# ============================================================
from __future__ import annotations
from typing import Optional, Tuple

# If you want to use your module roller (shared RNG):
try:
    from rolling.roller import roll_ndm as _roll_ndm
except Exception:
    # very small fallback
    import random
    _rng = random.Random()
    def _roll_ndm(n: int, m: int) -> int:
        return sum(_rng.randint(1, m) for _ in range(max(0, n)))


def _valid_slot(gs, idx: int):
    party = getattr(gs, "party_vessel_stats", None)
    if not isinstance(party, list) or idx < 0 or idx >= len(party):
        return None, None
    st = party[idx]
    return party, st if isinstance(st, dict) else None


def _heal_by_amount(gs, idx: int, amount: int) -> bool:
    """Additive heal: increases current_hp by `amount`, capped at max hp. Never reduces HP."""
    party, st = _valid_slot(gs, idx)
    if not st:
        return False

    try:
        max_hp = int(st.get("hp", st.get("current_hp", 1)))
    except Exception:
        max_hp = 1
    max_hp = max(1, max_hp)

    try:
        cur = int(st.get("current_hp", max_hp))
    except Exception:
        cur = max_hp

    healed = max(0, int(amount))
    st["current_hp"] = min(max_hp, max(0, cur) + healed)
    return True


def _healing_dice_for_level(level_after: int) -> Tuple[int, int]:
    """
    Your spec:
      1–9   -> 1d4
      10–19 -> 1d8
      20–29 -> 2d8
      30–39 -> 1d20
      40–50 -> 1d20
    (Called with the *new* level you just reached.)
    """
    L = max(1, int(level_after))
    if L < 10:   return (1, 4)
    if L < 20:   return (1, 8)
    if L < 30:   return (2, 8)
    if L < 40:   return (1, 20)
    return (1, 20)  # 40–50


def heal_on_level_up(gs, idx: int, level_after: int, *, min_heal: int = 1) -> int:
    """
    Call this *immediately after* you apply a level-up.
    Heals by dice based on the new level (see table above).
    Returns the rolled heal amount actually applied (after capping).
    """
    party, st = _valid_slot(gs, idx)
    if not st:
        return 0

    # Determine dice for this level
    n, d = _healing_dice_for_level(level_after)
    rolled = _roll_ndm(n, d)

    # Optional minimum so you never heal 0 on a bad roll
    rolled = max(int(min_heal), int(rolled))

    # Compute how much will actually apply (respect max HP)
    try:
        max_hp = int(st.get("hp", st.get("current_hp", 1)))
    except Exception:
        max_hp = 1
    max_hp = max(1, max_hp)

    try:
        cur = int(st.get("current_hp", max_hp))
    except Exception:
        cur = max_hp

    applied = max(0, min(rolled, max_hp - max(0, cur)))
    if applied > 0:
        _heal_by_amount(gs, idx, applied)
    return applied


# (Keep these convenience helpers if you still want them around)
def heal_to_percent(gs, idx: int, pct: float, *, lower: bool = False) -> bool:
    party, st = _valid_slot(gs, idx)
    if not st: return False
    try:
        max_hp = int(st.get("hp", st.get("current_hp", 1)))
    except Exception:
        max_hp = 1
    max_hp = max(1, max_hp)
    pct = max(0.0, min(1.0, float(pct)))
    target = int(round(max_hp * pct))
    if pct > 0.0 and target == 0:
        target = 1
    cur = int(st.get("current_hp", max_hp))
    st["current_hp"] = max(0, min(max_hp, target if lower else max(cur, target)))
    return True

def heal_to_half(gs, idx: int) -> bool:
    return heal_to_percent(gs, idx, 0.5, lower=False)

def heal_to_full(gs, idx: int) -> bool:
    return heal_to_percent(gs, idx, 1.0, lower=False)
