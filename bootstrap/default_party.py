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

    # =========================================================
    # Slot 6 → Starter (FTokenBarbarian1)
    # =========================================================
    starter_idx = 5  # zero-based index for slot 6
    tok_png = token_name if token_name.lower().endswith(".png") else f"{token_name}.png"

    gs.party_slots_names[starter_idx] = tok_png
    gs.party_slots[starter_idx]       = tok_png
    gs.party_tokens[starter_idx]      = tok_png

    level = getattr(gs, "zone_level", 1)
    seed  = getattr(gs, "seed", None)
    rng   = StatRoller(seed) if seed is not None else None
    gs.party_vessel_stats[starter_idx] = generate_vessel_stats_from_asset(tok_png, level=level, rng=rng)

    # =========================================================
    # Slot 5 → Rare Vessel (RVesselRanger1)
    # =========================================================
    rare_idx = 4  # zero-based index for slot 5
    rare_vessel = "RVesselRanger1.png"
    rare_token  = "RTokenRanger1.png"

    gs.party_slots_names[rare_idx] = rare_token
    gs.party_slots[rare_idx]       = rare_token
    gs.party_tokens[rare_idx]      = rare_token

    try:
        gs.party_vessel_stats[rare_idx] = generate_vessel_stats_from_asset(
            rare_vessel, level=level, rng=rng
        )
        print(f"🎉 Added default rare vessel: {rare_vessel} (slot {rare_idx + 1})")
    except Exception as e:
        print(f"⚠️ Failed to add rare vessel {rare_vessel}: {e}")

    # =========================================================
    # Clear HUD caches so UI rebuilds
    # =========================================================
    for attr in ("_hud_party_icons", "_hud_party_rects", "_hud_party_cache"):
        if hasattr(gs, attr):
            setattr(gs, attr, None)

    try:
        from systems import party_ui
        if hasattr(party_ui, "on_party_changed"):
            party_ui.on_party_changed(gs)
    except Exception:
        pass
