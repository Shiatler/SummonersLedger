# ============================================================
# bootstrap/default_party.py
# ============================================================
from systems import save_system as saves
from combat.vessel_stats import generate_vessel_stats_from_asset
from rolling.roller import Roller as StatRoller

def add_default_on_new_game(gs, *, slot_index: int = 5, token_name: str = "FTokenBarbarian1"):
    try:
        if saves.has_save():
            return
    except Exception:
        pass

    if not getattr(gs, "party_slots_names", None):
        gs.party_slots_names = [None] * 6
    if not getattr(gs, "party_vessel_stats", None):
        gs.party_vessel_stats = [None] * 6
    if not getattr(gs, "party_slots", None):
        gs.party_slots = [None] * 6
    if not getattr(gs, "party_tokens", None):
        gs.party_tokens = [None] * 6

    if any(gs.party_slots_names):
        return

    idx = max(0, min(5, int(slot_index)))

    # ensure “.png”
    tok_png = token_name if token_name.lower().endswith(".png") else f"{token_name}.png"

    # write all the arrays HUDs commonly read
    gs.party_slots_names[idx] = tok_png          # <- make sure it’s the PNG token filename
    gs.party_slots[idx]       = tok_png
    gs.party_tokens[idx]      = tok_png

    level = getattr(gs, "zone_level", 1)
    seed  = getattr(gs, "seed", None)
    rng   = StatRoller(seed) if seed is not None else None
    gs.party_vessel_stats[idx] = generate_vessel_stats_from_asset(tok_png, level=level, rng=rng)

    # nuke common caches so UI rebuilds
    for attr in ("_hud_party_icons", "_hud_party_rects", "_hud_party_cache"):
        if hasattr(gs, attr):
            setattr(gs, attr, None)

    try:
        from systems import party_ui
        if hasattr(party_ui, "on_party_changed"):
            party_ui.on_party_changed(gs)
    except Exception:
        pass
