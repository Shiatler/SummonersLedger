# ============================================================
# combat/helpers.py
# ============================================================
from combat.btn import battle_action, bag_action, party_action
from systems import xp as xp_sys

# Required for forced switch logic
def _get_active_party_index(gs) -> int:
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    names = getattr(gs, "party_slots_names", None) or [None]*6
    for i, (st, nm) in enumerate(zip(stats, names)):
        if nm and isinstance(st, dict):
            try:
                if int(st.get("current_hp", st.get("hp", 0))) > 0:
                    return i
            except Exception:
                pass
    return 0

def _has_living_party(gs) -> bool:
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    for st in stats:
        if isinstance(st, dict):
            hp = int(st.get("current_hp", st.get("hp", 0)))
            if hp > 0:
                return True
    return False

def _show_result_screen(st: dict, title: str, subtitle: str, *,
                        kind: str = "info",
                        exit_on_close: bool = False,
                        auto_dismiss_ms: int = 0,
                        lock_input: bool = False):
    st["result"] = {
        "kind": kind,
        "title": title,
        "subtitle": subtitle,
        "t": 0.0,
        "alpha": 0,
        "played": False,
        "exit_on_close": bool(exit_on_close),
        "auto_ms": int(max(0, auto_dismiss_ms)),
        "auto_ready": False,
        "lock_input": bool(lock_input),
    }

def _trigger_forced_switch_if_needed(gs, st):
    """
    If active ally is KO (HP <= 0) and we aren't already forcing a switch,
    open Party popup and lock other inputs. If no living party members remain,
    show defeat and exit.
    """
    # Active stats
    idx = _get_active_party_index(gs)
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    cur = 0; maxhp = 0
    if 0 <= idx < len(stats) and isinstance(stats[idx], dict):
        cur = int(stats[idx].get("current_hp", stats[idx].get("hp", 0)))
        maxhp = int(stats[idx].get("hp", 0))
    
    # KO?
    if cur <= 0 and not st.get("force_switch", False) and not st.get("swap_playing", False):
        if not _has_living_party(gs):
            _show_result_screen(st, "All vessels are down!", "You can’t continue.", kind="fail", exit_on_close=True)
            st["pending_exit"] = True
            return
        
        st["force_switch"] = True
        setattr(gs, "_force_switch", True)   # ← keep party_action in sync
        st["phase"] = "PLAYER_TURN"
        try:
            battle_action.close_popup(); bag_action.close_popup()
        except Exception: pass
        try:
            party_action.open_popup()
        except Exception: pass

# Function to check if any enemy party members are still alive (HP > 0)
def _enemy_party_has_living(gs) -> bool:
    party = getattr(gs, "_pending_enemy_party", []) or []
    for entry in party:
        st = entry.get("stats", {}) or {}
        try:
            if int(st.get("current_hp", st.get("hp", 0))) > 0:
                return True
        except Exception:
            pass
    return False
