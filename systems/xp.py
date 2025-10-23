# ============================================================
#  systems/xp.py  —  XP + Leveling system (Option A: simple table)
# ============================================================
#  Responsibilities:
#   • Define static XP-to-next-level table (L1→50)
#   • Compute XP reward from enemy data
#   • Distribute XP between active and benched party members
#   • Apply level-ups by rebuilding stats via combat.stats.build_stats
#   • Preserve existing abilities / current HP ratio
# ============================================================

import math
from typing import Tuple, List
import settings as S

from combat.stats import build_stats

# ---------- Config: XP requirements table ----------
# Index = current level; value = XP needed to reach next level
# Feel free to hand-edit the curve for balancing.
REQ: list[int | None] = [
    None,  # 0 unused
    3, 4, 5, 6, 7, 9, 11, 13, 15, 17,    # L1–10
    20, 23, 26, 29, 32, 36, 40, 44, 48, 52,  # L11–20
    57, 62, 68, 74, 80, 86, 92, 98, 104, 110,  # L21–30
    118, 126, 134, 142, 150, 158, 166, 174, 182, 190,  # L31–40
    200, 210, 220, 230, 240, 250, 260, 270, 280, 300,  # L41–50
]

MAX_LEVEL = 50


# ---------- Helpers ----------
def xp_needed(level: int) -> int:
    """Return XP required to reach the next level."""
    if level < 1:
        return 1
    if level >= len(REQ) or REQ[level] is None:
        return 99999999  # practically infinite (cap)
    return int(REQ[level])


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ---------- Reward formula ----------
def compute_xp_reward(enemy_stats: dict, enemy_name: str, outcome: str) -> int:
    """
    Compute XP reward from an encounter.
    outcome: 'capture' or 'defeat' (both give same XP).
    """
    try:
        enemy_lvl = int(enemy_stats.get("level", 1))
    except Exception:
        enemy_lvl = 1

    # --- Basic multipliers ---
    base = 1.0
    level_scale = max(1.0, enemy_lvl ** 0.75)
    rarity_mult = 1.0
    name = str(enemy_name or "").lower()

    # crude rarity detection
    if "rare" in name:
        rarity_mult = 1.7
    elif "boss" in name:
        rarity_mult = 2.2
    elif "elite" in name or "summoner" in name:
        rarity_mult = 1.3

    diff = 0.0
    try:
        diff = float(enemy_lvl - int(enemy_stats.get("vs_level", enemy_lvl)))
    except Exception:
        diff = 0.0
    diff_mult = clamp(1.0 + 0.12 * diff, 0.6, 1.6)

    reward = base * level_scale * rarity_mult * diff_mult
    reward = max(1, int(round(reward)))
    return reward


# ---------- Distribution ----------
def distribute_xp(gs, active_idx: int, base_xp: int) -> Tuple[int, int, List[Tuple[int, int, int]]]:
    """
    Give XP to active and benched allies.
    Returns (active_gain, bench_gain, levelups_list[(idx, old_lv, new_lv)]).
    """
    if not hasattr(gs, "party_vessel_stats"):
        return 0, 0, []

    party = gs.party_vessel_stats
    if not isinstance(party, list):
        return 0, 0, []

    active_gain = int(base_xp)
    bench_gain = int(round(base_xp * 0.3))
    levelups: list[tuple[int, int, int]] = []

    for idx, st in enumerate(party):
        if not isinstance(st, dict):
            continue
        lvl = int(st.get("level", 1))
        xp  = int(st.get("xp_current", 0))

        if not st.get("class_name"):
            continue

        alive = True
        if "current_hp" in st:
            try:
                alive = st["current_hp"] > 0
            except Exception:
                alive = True

        gain = active_gain if idx == active_idx else (bench_gain if alive else 0)
        if gain <= 0:
            # still ensure fields exist
            st.setdefault("xp_needed", xp_needed(lvl))
            st.setdefault("xp_total", 0)
            continue

        # apply XP
        xp += gain
        st["xp_total"] = int(st.get("xp_total", 0)) + gain

        # handle level-ups (may chain)
        while lvl < MAX_LEVEL and xp >= xp_needed(lvl):
            xp -= xp_needed(lvl)
            old_lv = lvl
            lvl += 1
            levelups.append((idx, old_lv, lvl))
            apply_level_up(gs, idx, lvl)

        st["xp_current"] = xp
        st["level"] = lvl
        st["xp_needed"] = xp_needed(lvl)


    # auto-save if function available
    try:
        from systems import save_system as saves
        saves.save_game(gs)
    except Exception:
        pass

    return active_gain, bench_gain, levelups


# ---------- Level-up ----------
def apply_level_up(gs, idx: int, new_level: int, *, preserve_hp_ratio: bool = True):
    """
    Rebuild vessel stats at new level while keeping ability rolls.
    """
    try:
        st = gs.party_vessel_stats[idx]
    except Exception:
        return
    if not isinstance(st, dict):
        return

    # Preserve abilities + HP ratio
    abilities = st.get("abilities") or {}
    old_hp = float(st.get("hp", 1))
    cur_hp = float(st.get("current_hp", old_hp))
    ratio = clamp(cur_hp / old_hp if old_hp > 0 else 1.0, 0.0, 1.0)

    cls = st.get("class_name") or "Fighter"
    name = st.get("name") or cls
    notes = "Level up rebuild"

    # Build fresh stats
    try:
        new_stats = build_stats(
            name=name,
            class_name=cls,
            level=new_level,
            abilities={k.upper(): int(v) for k, v in abilities.items()},
            notes=notes,
        ).to_dict()
    except Exception as e:
        print(f"⚠️ build_stats failed during level-up for slot {idx}: {e}")
        return

    # Merge back into old dict to preserve XP & other keys
    st.update(new_stats)
    st["level"] = new_level
    st.setdefault("xp_current", 0)

    if preserve_hp_ratio and "hp" in st:
        st["current_hp"] = int(round(st["hp"] * ratio))

    # Optional: you could play a sound or trigger animation elsewhere
    try:
        from systems import audio as audio_sys
        audio_sys.play_sfx("LevelUp")
    except Exception:
        pass

# ============================================================
# XP profile initialization
# ============================================================

def ensure_profile(gs):
    """
    Ensure each party slot has consistent XP fields:
      - xp_current: XP toward next level
      - xp_needed:  threshold to reach the next level
      - xp_total:   lifetime XP (optional, for UI/stats)
    Also migrates legacy keys (xp / xp_to_next) if present.
    """
    if not hasattr(gs, "party_vessel_stats") or not isinstance(gs.party_vessel_stats, list):
        gs.party_vessel_stats = [None] * 6

    for i in range(6):
        st = gs.party_vessel_stats[i]
        if not isinstance(st, dict):
            continue

        lvl = int(st.get("level", 1))

        # --- migrate legacy fields if they exist
        if "xp_current" not in st and "xp" in st:
            try:
                st["xp_current"] = int(st.get("xp", 0))
            except Exception:
                st["xp_current"] = 0
        if "xp_needed" not in st and "xp_to_next" in st:
            try:
                st["xp_needed"] = int(st.get("xp_to_next", xp_needed(lvl)))
            except Exception:
                st["xp_needed"] = xp_needed(lvl)

        # --- ensure modern fields
        if "xp_current" not in st:
            st["xp_current"] = 0
        st["xp_current"] = max(0, int(st["xp_current"]))

        if "xp_needed" not in st:
            st["xp_needed"] = xp_needed(lvl)
        else:
            # keep it in sync with the current level if clearly wrong/missing
            try:
                need = int(st["xp_needed"])
            except Exception:
                need = -1
            if need <= 0:
                st["xp_needed"] = xp_needed(lvl)

        if "xp_total" not in st:
            st["xp_total"] = 0

    return gs

