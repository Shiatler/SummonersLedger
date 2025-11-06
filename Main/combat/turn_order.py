# ============================================================
# combat/turn_order.py — Pokémon-style initiative + turn cycle
# ============================================================
from rolling import roller

def _extract_roll_value(roll_obj) -> int:
    if isinstance(roll_obj, (int, float)):
        return int(roll_obj)
    for key in ("total", "result", "roll", "value", "number"):
        if hasattr(roll_obj, key):
            return int(getattr(roll_obj, key))
    try:
        return int(roll_obj)
    except Exception:
        print(f"⚠️ Unknown roll object structure: {roll_obj!r}")
        return 0

def roll_initiative(stats: dict) -> int:
    dex_mod = int(stats.get("dex_mod", 0))
    base_init = int(stats.get("initiative", 0))
    roll_obj = roller.roll_d20(notify=False)
    roll_val = _extract_roll_value(roll_obj)
    total = roll_val + base_init + dex_mod
    print(f"🎲 Initiative roll: d20({roll_val}) + init({base_init}) + DEX({dex_mod}) = {total}")
    return total

def determine_order(gs):
    ally_stats = (getattr(gs, "party_vessel_stats", [None])[getattr(gs, "combat_active_idx", 0)]) or {}
    enemy_stats = getattr(gs, "encounter_stats", {}) or {}

    ally_init = roll_initiative(ally_stats)
    enemy_init = roll_initiative(enemy_stats)

    order = ["player", "enemy"] if ally_init >= enemy_init else ["enemy", "player"]
    gs._turn_order = order
    gs._current_turn_index = 0
    gs._turn_ready = True
    gs._actor = order[0]
    print(f"⚔️ Initiative: Player {ally_init} vs Enemy {enemy_init} → {order[0]} starts!")

def next_turn(gs):
    if not hasattr(gs, "_turn_order"):
        determine_order(gs)
    gs._current_turn_index = (gs._current_turn_index + 1) % len(gs._turn_order)
    cur = gs._turn_order[gs._current_turn_index]
    gs._actor = cur
    # We keep enemy as a real actor even if AI is N/A; wild_vessel will still show the 2s card.
    gs._turn_ready = (cur == "player")
    print(f"➡️ Now it's {cur}'s turn.")
    return cur

def current_actor(gs) -> str:
    if not hasattr(gs, "_turn_order"):
        determine_order(gs)
    return getattr(gs, "_actor", gs._turn_order[gs._current_turn_index])
