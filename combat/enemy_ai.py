# ============================================================
# combat/enemy_ai.py — ultra-simple enemy AI
# - Chooses a random usable move for the ENEMY (L1 kit only)
# - Falls back to Bonk if no PP (or no moves)
# - Uses new enemy helpers added to moves.py
# ============================================================
from __future__ import annotations
import random
from typing import Optional, List
from combat import moves

def _usable(mv, gs) -> bool:
    rem, _ = moves.get_enemy_pp(gs, mv.id)
    return rem > 0

def choose_move(gs) -> Optional[str]:
    mv_list: List[moves.Move] = moves.get_available_moves_for_enemy(gs)
    if not mv_list:
        return None
    usable = [m for m in mv_list if _usable(m, gs)]
    pool = usable or mv_list
    return random.choice(pool).id if pool else None

def take_turn(gs) -> bool:
    """Return True if something was queued/resolved (including Bonk)."""
    mv_id = choose_move(gs)
    if mv_id:
        return moves.queue_enemy(gs, mv_id)
    # no moves or PP → Bonk (enemy version)
    return moves.queue_enemy_bonk(gs)

    if st.get("phase") == PHASE_ENEMY:
        now = pygame.time.get_ticks()

        if (not st.get("ai_started") 
            and now >= int(st.get("enemy_think_until", 0)) 
            and not resolving_moves 
            and not scene_busy):
            try:
                enemy_ai.take_turn(gs)
            except Exception as _e:
                print(f"⚠️ enemy_ai failure: {_e}")
            st["ai_started"] = True

            # --- NEW: try to play the enemy move SFX once ---
            try:
                # Preferred: AI sets this directly
                lbl = st.pop("last_enemy_move_label", None) or getattr(gs, "_last_enemy_move_label", None)
                if not lbl:
                    # Fallback: parse the result card title, e.g., "Enemy used Thorn Whip"
                    res = st.get("result") or {}
                    title = str(res.get("title", "")) if isinstance(res, dict) else ""
                    m = re.match(r"Enemy used\s+(.+)", title)
                    if m: lbl = m.group(1).strip()
                if lbl:
                    # Uses the per-move SFX loader in combat.moves (Assets/Music/Moves/<slug>.mp3)
                    moves._play_move_sfx(lbl)
            except Exception as _e:
                print(f"⚠️ enemy move sfx error: {_e}")

