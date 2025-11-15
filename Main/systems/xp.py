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


    # No autosave - user must manually save via "Save Game" button

    return active_gain, bench_gain, levelups


# ---------- Level-up ----------
# ---------- Level-up ----------
def apply_level_up(gs, idx: int, new_level: int, *, preserve_hp_ratio: bool = True):
    """
    Rebuild stats at new level and handle HP + on-level healing.

    HP growth:
      • Milestones only (levels 10, 20, 30, 40, 50)
      • On each milestone: Max HP increases by (1dHitDie + CON mod), minimum +1 total
      • We keep previous max HP as the base and add milestone gains on top

    Healing on level-up (thematic D&D-style, additive, capped at max):
      • After we set the new level and HP fields, we heal a small amount
        based on the *new* level range (implemented in systems.heal.heal_on_level_up).

    We preserve abilities and refresh AC/prof/etc. via build_stats.
    """
    import random
    try:
        st = gs.party_vessel_stats[idx]
    except Exception:
        return
    if not isinstance(st, dict):
        return

    # Preserve abilities & a snapshot of current/max HP BEFORE rebuild
    abilities = st.get("abilities") or {}
    old_hp_max = float(st.get("hp", 1))
    cur_hp     = float(st.get("current_hp", old_hp_max))
    
    # Preserve buff-related fields that should persist through level-ups
    # These are applied by blessings and should not be lost when stats are rebuilt
    preserved_buffs = {
        "ac_bonus": st.get("ac_bonus", 0),
        "permanent_damage_bonus": st.get("permanent_damage_bonus", 0),
        "damage_reduction": st.get("damage_reduction", 0),
    }

    # --- Rebuild non-HP stats for new level ---
    cls  = st.get("class_name") or "Fighter"
    name = st.get("name") or cls
    try:
        new_stats = build_stats(
            name=name,
            class_name=cls,
            level=new_level,
            abilities={k.upper(): int(v) for k, v in abilities.items()},
            notes="Level up rebuild (milestone HP handled in XP)",
        ).to_dict()
    except Exception as e:
        print(f"⚠️ build_stats failed during level-up for slot {idx}: {e}")
        return

    # Remove HP from new_stats - we calculate it separately using milestone system
    # build_stats uses compute_hp which includes per-level gains (wrong for vessels)
    new_stats.pop("hp", None)
    new_stats.pop("current_hp", None)  # Also remove current_hp, we handle it separately

    # Merge rebuilt stats; keep our XP fields intact if present
    st.update(new_stats)
    st["level"] = int(new_level)
    st.setdefault("xp_current", int(st.get("xp_current", 0)))
    
    # Restore preserved buff-related fields
    for buff_key, buff_value in preserved_buffs.items():
        if buff_value:  # Only restore if non-zero (saves space)
            st[buff_key] = buff_value
    
    # Update the base AC field to include the ac_bonus from blessings
    # This ensures the AC is displayed correctly everywhere
    if preserved_buffs.get("ac_bonus", 0):
        base_ac = int(st.get("ac", 10))
        ac_bonus = preserved_buffs["ac_bonus"]
        st["ac"] = base_ac + ac_bonus
        print(f"📊 Level-up: Restored AC bonus +{ac_bonus} (base AC: {base_ac}, total AC: {st['ac']})")

    # ---------- HP: carry forward previous max, then apply milestone gains ----------
    new_hp_max = int(round(old_hp_max))

    # Milestone levels (every 10)
    if new_level % 10 == 0:
        # Determine class hit die and CON modifier
        try:
            from combat.stats import hit_die_for_class, ability_mod
            d = int(hit_die_for_class(cls))
        except Exception:
            d = 8  # safe default
        try:
            con_mod = int(st.get("mods", {}).get("CON"))
        except Exception:
            # fall back to computing from abilities if mods missing
            try:
                from combat.stats import ability_mod as _abmod
                con_mod = int(_abmod(int(abilities.get("CON", 10))))
            except Exception:
                con_mod = 0

        # Roll 1d(HitDie) + CON (minimum +1 total gain)
        roll = random.randint(1, max(2, d))
        gain = max(1, roll + con_mod)
        new_hp_max = max(1, int(round(old_hp_max + gain)))

        # Optional: record roll history
        hist = st.setdefault("hp_rolls", [])
        hist.append({"level": new_level, "die": d, "roll": roll, "con": con_mod, "gain": gain})

    # Update HP fields (max)
    st["hp"] = new_hp_max

    # Preserve current HP ratio unless the caller opts to full-heal
    if preserve_hp_ratio:
        ratio = 1.0 if old_hp_max <= 0 else max(0.0, min(1.0, cur_hp / old_hp_max))
        st["current_hp"] = int(round(new_hp_max * ratio))
    else:
        st["current_hp"] = int(new_hp_max)

    # ---------- Bonus on-level healing (small dice-based heal; capped; never lowers HP) ----------
    try:
        from systems.heal import heal_on_level_up
        # Heals based on level bands (1d4 / 1d8 / 2d8 / 1d20 / 1d20). min_heal=1 avoids 0 on bad rolls.
        heal_on_level_up(gs, idx, new_level, min_heal=1)
    except Exception:
        pass

    # Optional: SFX
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

