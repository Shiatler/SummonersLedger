# ============================================================
# bootstrap/default_party.py
# ============================================================
from systems import save_system as saves
from combat.vessel_stats import generate_vessel_stats_from_asset
from rolling.roller import Roller as StatRoller

def add_default_on_new_game(gs, *, slot_index: int = 5, token_name: str = "FTokenBarbarian1"):
    """
    Bootstrap function - DISABLED FOR TESTING.
    All bootstrap vessels (including starter barbarian) have been removed.
    """
    # All bootstrap vessels removed for testing
    # Initialize empty party slots if needed
    if not getattr(gs, "party_slots_names", None):
        gs.party_slots_names = [None] * 6
    if not getattr(gs, "party_vessel_stats", None):
        gs.party_vessel_stats = [None] * 6
    if not getattr(gs, "party_slots", None):
        gs.party_slots = [None] * 6
    if not getattr(gs, "party_tokens", None):
        gs.party_tokens = [None] * 6
    
    print("ℹ️ Bootstrap vessels disabled for testing - party starts empty")
    
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
