# ============================================================
# combat/moves.py — lightweight move system (Level 1 kit + PP)
# - Registry of L1 moves for each class
# - Dynamic availability from the active unit’s class
# - Generic executor: d20 vs AC, then damage dice + ability mod
# - Writes enemy HP into gs.encounter_stats["current_hp"]
# - Exposes is_resolving() so scenes can debounce KOs mid-anim
# - Per-move PP (uses). L1 moves default to 20 PP (persisted in gs.move_pp)
# - Per-move SFX: Assets/Music/Moves/<move_label_slug>.mp3  (e.g., thorn_whip.mp3)
# ============================================================
from __future__ import annotations

import os
import re
import pygame
from dataclasses import dataclass
from typing import Optional, Dict, Any, Iterable, Tuple, List

from systems import audio as audio_sys
from rolling import roller  # calls are wrapped in try/except

PROF_FLAT = 2

# --------------------- Data model ----------------------------

@dataclass(frozen=True)
class Move:
    id: str                 # unique id, e.g., "barb_l1_wild_swing"
    label: str              # "Wild Swing"
    desc: str               # blurb for UI
    dice: Tuple[int, int]   # (count, sides)
    ability: str            # "STR","DEX","CON","INT","WIS","CHA" or "STR|DEX"
    to_hit: bool = True
    self_hp_cost: int = 0
    max_pp: int = 40        # default PP cap (level 1 moves → 20)

# --------------------- helpers: state ------------------------

def _active_stats(gs) -> Optional[Dict[str, Any]]:
    """Pick active slot stats; fall back to gs.ally_stats."""
    idx = getattr(gs, "combat_active_idx", 0)
    party_stats = (getattr(gs, "party_vessel_stats", None) or [None] * 6)
    slot_stats = party_stats[idx] if 0 <= idx < len(party_stats) else None
    chosen = slot_stats or getattr(gs, "ally_stats", None)
    return chosen if isinstance(chosen, dict) else None

def _active_token_name(gs) -> str:
    """Stable per-ally key. Prefer the active party token name; fallback to 'ally'."""
    idx = getattr(gs, "combat_active_idx", 0)
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    nm = names[idx] if 0 <= idx < len(names) else None
    return str(nm or "ally")

def _iter_kv(d: Dict[str, Any]):
    for k, v in (d or {}).items():
        yield k, v
        if isinstance(v, dict):
            for kk, vv in _iter_kv(v):
                yield kk, vv

def _class_string(stats: Dict[str, Any] | None) -> str:
    if not isinstance(stats, dict):
        return ""
    for key in ("class_name", "class", "klass", "archetype", "profession", "job", "role"):
        v = stats.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    for key in ("classes", "class_list"):
        v = stats.get(key)
        if isinstance(v, (list, tuple)) and v:
            return " ".join(str(x) for x in v if x)
    for k, v in _iter_kv(stats):
        if k.lower() in ("class", "klass", "archetype") and isinstance(v, str) and v.strip():
            return v.strip()
    return ""

def _ability_mod(stats: Dict[str, Any] | None, ability: str) -> int:
    """Read a mod from stats['mods'] with tolerant keys & alternatives."""
    try:
        mods = (stats or {}).get("mods", {}) or {}
        if "|" in ability:
            left, right = [a.strip().upper() for a in ability.split("|", 1)]
            return max(_ability_mod(stats, left), _ability_mod(stats, right))
        key_upper = ability.upper()
        key_lower = key_upper.lower()
        if key_upper in mods:
            return int(mods.get(key_upper, 0))
        if key_lower in mods:
            return int(mods.get(key_lower, 0))
        return 0
    except Exception:
        return 0

def _enemy_ac(gs) -> int:
    est = getattr(gs, "encounter_stats", {}) or {}
    try:
        return int(est.get("ac", 10))
    except Exception:
        return 10

def _enemy_hp_tuple(gs) -> tuple[int, int]:
    """Return (current_hp, max_hp). Initialize current if missing (using ratio fallback)."""
    est = getattr(gs, "encounter_stats", {}) or {}
    maxhp = max(1, int(est.get("hp", 10)))
    cur = est.get("current_hp")
    if cur is None:
        ratio = float(getattr(gs, "_wild", {}).get("enemy_hp_ratio", 1.0))
        cur = max(0, min(maxhp, int(round(maxhp * ratio))))
        est["current_hp"] = cur
        gs.encounter_stats = est
    return int(est["current_hp"]), int(maxhp)

def _set_enemy_hp(gs, new_cur: int, maxhp: int) -> None:
    est = getattr(gs, "encounter_stats", {}) or {}
    new_cur = max(0, min(maxhp, int(new_cur)))
    est["current_hp"] = new_cur
    gs.encounter_stats = est
    # keep on-screen bar in sync
    st = getattr(gs, "_wild", {}) or {}
    st["enemy_hp_ratio"] = (new_cur / maxhp) if maxhp > 0 else 0.0
    gs._wild = st
    print(f"[moves] enemy HP → {new_cur}/{maxhp} (ratio={st['enemy_hp_ratio']:.3f})")

# combat/moves.py
def _click():
    # Mute UI click in combat result popups
    return


#---------------------- HP Helper -----------------------------
def _ally_hp_tuple(gs) -> tuple[int, int]:
    idx = getattr(gs, "combat_active_idx", 0)
    stats_list = getattr(gs, "party_vessel_stats", None) or [None]*6
    st = stats_list[idx] if 0 <= idx < len(stats_list) else None
    if not isinstance(st, dict):
        return 10, 10
    mx = max(1, int(st.get("hp", 10)))
    cur = st.get("current_hp")
    cur = mx if cur is None else max(0, min(mx, int(cur)))
    st["current_hp"] = cur
    stats_list[idx] = st
    gs.party_vessel_stats = stats_list
    return cur, mx

def _set_ally_hp(gs, new_cur: int, maxhp: int) -> None:
    idx = getattr(gs, "combat_active_idx", 0)
    stats_list = getattr(gs, "party_vessel_stats", None) or [None]*6
    st = stats_list[idx] if 0 <= idx < len(stats_list) else None
    if not isinstance(st, dict):
        return
    new_cur = max(0, min(maxhp, int(new_cur)))
    st["current_hp"] = new_cur
    stats_list[idx] = st
    gs.party_vessel_stats = stats_list
    # keep on-screen bar in sync
    wild = getattr(gs, "_wild", {}) or {}
    wild["ally_hp_ratio"] = (new_cur / maxhp) if maxhp > 0 else 0.0
    gs._wild = wild

# --------------------- Enemy-side helpers --------------------
def _enemy_stats(gs) -> Optional[Dict[str, Any]]:
    """Enemy stat dict comes from gs.encounter_stats (already your CombatStats dict)."""
    est = getattr(gs, "encounter_stats", None)
    return est if isinstance(est, dict) else None

def _enemy_token_name(gs) -> str:
    """Stable key for PP store; enemy is keyed by encounter name."""
    nm = getattr(gs, "encounter_name", None)
    return str(nm or "enemy")

def _enemy_class_string(gs) -> str:
    st = _enemy_stats(gs) or {}
    return _class_string(st)  # reuses tolerant class parser

def get_available_moves_for_enemy(gs) -> List[Move]:
    """L1 moves derived from ENEMY class (using same registry)."""
    norm = _normalize_class(_enemy_stats(gs))
    if not norm:
        # try by class_name string if dict didn't normalize
        s = _enemy_class_string(gs)
        norm = _CLASS_KEYS.get(s.lower(), None) if s else None
    return list(_MOVE_REGISTRY.get(norm, []))

def get_enemy_pp(gs, move_id: str) -> tuple[int, int]:
    """(remaining, max) for ENEMY on a particular move."""
    mv = None
    for lst in _MOVE_REGISTRY.values():
        for m in lst:
            if m.id == move_id:
                mv = m; break
        if mv: break
    if not mv:
        return (0, 0)
    actor = _enemy_token_name(gs)
    rem = _pp_get(gs, actor, mv)
    return rem, mv.max_pp

def _pp_spend_enemy(gs, mv: Move) -> bool:
    return _pp_spend(gs, _enemy_token_name(gs), mv)

def _ability_mod_enemy(gs, ability: str) -> int:
    return _ability_mod(_enemy_stats(gs), ability)

def _ally_ac(gs) -> int:
    """Mirror of _enemy_ac: read AC from the active ALLY stats."""
    cur, idx = None, getattr(gs, "combat_active_idx", 0)
    stats_list = getattr(gs, "party_vessel_stats", None) or [None]*6
    st = stats_list[idx] if 0 <= idx < len(stats_list) else None
    try:
        return int((st or {}).get("ac", 10))
    except Exception:
        return 10

def _perform_enemy_basic_attack(gs, mv: Move) -> bool:
    """Enemy uses a basic attack against the active ally (same math/UX as ally path)."""
    st = getattr(gs, "_wild", None)
    if not isinstance(st, dict):
        return False

    atk_bonus = _ability_mod_enemy(gs, mv.ability) + PROF_FLAT
    ac = _ally_ac(gs)

    _set_resolving(True)
    try:
        # To-hit
        hit = False
        crit = False
        total_to_hit = 0
        try:
            atk_res = roller.roll_attack(attack_bonus=atk_bonus, target_ac=ac, adv=0, notify=False)
            hit = bool(getattr(atk_res, "hit", False))
            crit = bool(getattr(atk_res, "crit", False))
            total_to_hit = int(getattr(atk_res, "total", 0))
        except Exception:
            import random
            d20 = random.randint(1, 20)
            total_to_hit = d20 + atk_bonus
            crit = (d20 == 20)
            hit = (total_to_hit >= ac)

        print(f"[moves][ENEMY] {mv.label} → to-hit total={total_to_hit} vs AC {ac} | hit={hit} crit={crit}")

        if not hit:
            # enemy miss card (info)
            st["result"] = {
                "kind": "info",
                "title": f"Enemy used {mv.label}",
                "subtitle": f"Miss! (roll {total_to_hit} vs AC {ac})",
                "t": 0.0, "alpha": 0, "played": False,
                "exit_on_close": False,
            }
            _play_move_sfx(mv.label); _click()
            return True

        # Damage → target is ALLY
        dice_n, dice_s = mv.dice
        bonus_mod = _ability_mod_enemy(gs, mv.ability)
        try:
            dmg_res = roller.roll_damage(dice=(dice_n, dice_s), bonus=bonus_mod, crit=crit, notify=False)
            total_dmg = int(getattr(dmg_res, "total", 0))
        except Exception:
            import random
            base = sum(random.randint(1, dice_s) for _ in range(dice_n))
            if crit:
                base += sum(random.randint(1, dice_s) for _ in range(dice_n))
            total_dmg = base + bonus_mod

        total_dmg = max(0, total_dmg)
        a_cur, a_max = _ally_hp_tuple(gs)
        new_cur = max(0, a_cur - total_dmg)
        _set_ally_hp(gs, new_cur, a_max)

        print(f"[moves][ENEMY] {mv.label} → damage={total_dmg} | ally {a_cur} → {new_cur}")

        # KO of ally just shows info; player can still exit with ESC, or you can decide later
        st["result"] = {
            "kind": "info",
            "title": f"Enemy used {mv.label}",
            "subtitle": (f"Hit for {total_dmg}!" if new_cur > 0 else f"Hit for {total_dmg}! (You’re down)"),
            "t": 0.0, "alpha": 0, "played": False,
            "exit_on_close": False,
        }
        _play_move_sfx(mv.label); _click()
        return True
    finally:
        _set_resolving(False)

def _perform_enemy_bonk(gs) -> bool:
    """
    Enemy Bonk: 1d4 to ALLY and 1d4 recoil to ENEMY. Always hits.
    Mirrors your ally Bonk.
    """
    st = getattr(gs, "_wild", None)
    if not isinstance(st, dict):
        return False

    import random
    _set_resolving(True)
    try:
        ally_dmg  = random.randint(1, 4)
        recoil    = random.randint(1, 4)

        # deal to ally
        a_cur, a_max = _ally_hp_tuple(gs)
        _set_ally_hp(gs, max(0, a_cur - ally_dmg), a_max)

        # recoil to enemy
        e_cur, e_max = _enemy_hp_tuple(gs)
        _set_enemy_hp(gs, max(0, e_cur - recoil), e_max)

        st["result"] = {
            "kind": "info",
            "title": "Enemy Bonk",
            "subtitle": f"You took {ally_dmg}, enemy took {recoil}",
            "t": 0.0, "alpha": 0, "played": False,
            "exit_on_close": False,
        }
        _play_move_sfx("Bonk"); _click()
        return True
    finally:
        _set_resolving(False)

def queue_enemy(gs, move_id: str) -> bool:
    """Enemy entry point: find move by id, spend enemy PP, execute vs ally."""
    mv = None
    for lst in _MOVE_REGISTRY.values():
        for m in lst:
            if m.id == move_id:
                mv = m; break
        if mv: break
    if not mv:
        return False
    if not _pp_spend_enemy(gs, mv):
        # out of PP → enemy Bonk (if all moves empty or this one empty)
        return _perform_enemy_bonk(gs)
    return _perform_enemy_basic_attack(gs, mv)

def queue_enemy_bonk(gs) -> bool:
    return _perform_enemy_bonk(gs)


#---------------------- No PP Helper --------------------------
def _all_moves_out_of_pp(gs) -> bool:
    """True if the active unit has at least one move, but all are at 0 PP."""
    mv_list = get_available_moves(gs)
    if not mv_list:
        return False
    actor = _active_token_name(gs)
    any_pp = any(_pp_get(gs, actor, mv) > 0 for mv in mv_list)
    return not any_pp

#--------------------- Bonk executor --------------------------
def _perform_bonk(gs) -> bool:
    """
    Bonk (Struggle): 1d4 to enemy and 1d4 recoil to self. Always 'hits'.
    Shows a result card. No PP cost.
    """
    st = getattr(gs, "_wild", None)
    if not isinstance(st, dict):
        return False

    import random
    _set_resolving(True)
    try:
        # roll damage
        enemy_dmg = random.randint(1, 4)
        self_dmg  = random.randint(1, 4)

        # enemy HP change
        e_cur, e_max = _enemy_hp_tuple(gs)
        _set_enemy_hp(gs, max(0, e_cur - enemy_dmg), e_max)

        # ally HP change
        a_cur, a_max = _ally_hp_tuple(gs)
        _set_ally_hp(gs, max(0, a_cur - self_dmg), a_max)

        # results
        if e_cur - enemy_dmg <= 0:
            st["enemy_fade_active"] = True
            st["enemy_fade_t"] = 0.0
            st["pending_result_payload"] = ("success", "Bonk – KO!", f"Enemy took {enemy_dmg}, you took {self_dmg}")
            st["enemy_defeated"] = True
        else:
            st["result"] = {
                "kind": "info",
                "title": "Bonk",
                "subtitle": f"Enemy took {enemy_dmg}, you took {self_dmg}",
                "t": 0.0, "alpha": 0, "played": False,
                "exit_on_close": False,
            }

        _play_move_sfx("Bonk")  # plays Assets/Music/Moves/bonk.mp3 if present
        _click()
        return True
    finally:
        _set_resolving(False)
    

def queue_bonk(gs) -> bool:
    return _perform_bonk(gs)




# --------------------- helpers: SFX --------------------------

_SFX_DIR = os.path.join("Assets", "Music", "Moves")
_SFX_CACHE: dict[str, pygame.mixer.Sound | None] = {}

def _slugify_label(label: str) -> str:
    # "Thorn Whip" -> "thorn_whip"
    s = label.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "move"

def _load_move_sfx(label: str):
    """Load (and cache) a pygame Sound for this move label; return None on failure."""
    slug = _slugify_label(label)
    if slug in _SFX_CACHE:
        return _SFX_CACHE[slug]
    path = os.path.join(_SFX_DIR, f"{slug}.mp3")
    try:
        if not os.path.exists(path):
            _SFX_CACHE[slug] = None
            return None
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        snd = pygame.mixer.Sound(path)
        _SFX_CACHE[slug] = snd
        return snd
    except Exception as e:
        print(f"⚠️ move SFX load fail {path}: {e}")
        _SFX_CACHE[slug] = None
        return None

def _play_move_sfx(label: str):
    try:
        snd = _load_move_sfx(label)
        if snd:
            # OLD: snd.play()
            audio_sys.play_sound(snd)   # honors SFX master
    except Exception:
        pass


# --------------------- Registry (Level 1) --------------------

_CLASS_KEYS = {
    "barbarian": "barbarian",
    "druid": "druid",
    "rogue": "rogue",
    "wizard": "wizard",
    "cleric": "cleric",
    "paladin": "paladin",
    "ranger": "ranger",
    "warlock": "warlock",
    "monk": "monk",
    "sorcerer": "sorcerer",
    "artificer": "artificer",
    "blood hunter": "blood_hunter",
    "bloodhunter": "blood_hunter",
    "fighter": "fighter",
    "bard": "bard",
}

# L1 moves (your scaled set), all with max_pp=20
_MOVE_REGISTRY: Dict[str, List[Move]] = {
    "barbarian": [Move("barb_l1_wild_swing", "Wild Swing", "Sloppy first strike.", (1, 5), "STR", True, 0, 20)],
    "druid":     [Move("druid_l1_thorn_whip", "Thorn Whip", "Cantrip lash of vines.", (2, 3), "WIS", True, 0, 20)],
    "rogue":     [Move("rogue_l1_quick_stab", "Quick Stab", "Hasty jab.", (1, 5), "DEX", True, 0, 20)],
    "wizard":    [Move("wizard_l1_arcane_bolt", "Arcane Bolt", "Spark of arcane energy.", (1, 6), "INT", True, 0, 20)],
    "cleric":    [Move("cleric_l1_sacred_flame", "Sacred Flame", "Radiant spark.", (1, 5), "WIS", True, 0, 20)],
    "paladin":   [Move("paladin_l1_smite_training", "Smite Training", "Basic divine strike.", (1, 6), "STR", True, 0, 20)],
    "ranger":    [Move("ranger_l1_aimed_shot", "Aimed Shot", "Careful bow shot.", (1, 5), "DEX", True, 0, 20)],
    "warlock":   [Move("warlock_l1_eldritch_blast", "Eldritch Blast", "Signature cantrip.", (1, 6), "CHA", True, 0, 20)],
    "monk":      [Move("monk_l1_martial_strike", "Martial Strike", "Basic unarmed strike.", (1, 5), "DEX", True, 0, 20)],
    "sorcerer":  [Move("sorc_l1_burning_hands", "Burning Hands", "Brief cone of flame.", (2, 3), "CHA", True, 0, 20)],
    "artificer": [Move("arti_l1_arcane_shot", "Arcane Shot", "Tinkered magic bolt.", (1, 5), "INT", True, 0, 20)],
    "blood_hunter": [Move("bh_l1_hemorrhage_cut", "Hemorrhage Cut", "Brutal self-fueled cut.", (1, 5), "STR|DEX", True, 0, 20)],
    "fighter": [Move("fighter_l1_weapon_strike", "Weapon Strike", "Disciplined opening attack.", (1, 5), "STR|DEX", True, 0, 20)],
    "bard":    [Move("bard_l1_vicious_mockery", "Vicious Mockery", "Psychic jab that rattles.", (1, 4), "CHA", True, 0, 20)],
}

def _normalize_class(stats: Dict[str, Any] | None) -> str | None:
    s = _class_string(stats).lower()
    if not s:
        return None
    for key, norm in _CLASS_KEYS.items():
        if key in s:
            return norm
    return None

# --------------------- PP persistence ------------------------

def _pp_store(gs) -> Dict[str, Dict[str, int]]:
    """
    Returns gs.move_pp (creating if needed).
    Structure: { actor_key: { move_id: remaining_pp } }
    """
    store = getattr(gs, "move_pp", None)
    if not isinstance(store, dict):
        store = {}
        gs.move_pp = store
    return store

def _pp_get(gs, actor_key: str, move: Move) -> int:
    store = _pp_store(gs)
    rem = store.get(actor_key, {}).get(move.id)
    if rem is None:
        rem = move.max_pp
        store.setdefault(actor_key, {})[move.id] = rem
    return int(rem)

def _pp_spend(gs, actor_key: str, move: Move) -> bool:
    store = _pp_store(gs)
    rem = _pp_get(gs, actor_key, move)
    if rem <= 0:
        return False
    store.setdefault(actor_key, {})[move.id] = rem - 1
    return True

def _pp_set_full(gs, actor_key: str, move: Move) -> None:
    _pp_store(gs).setdefault(actor_key, {})[move.id] = move.max_pp

# --------------------- Busy flag for scenes ------------------

_RESOLVING = False
def is_resolving() -> bool:
    return _RESOLVING

def _set_resolving(v: bool):
    global _RESOLVING
    _RESOLVING = bool(v)

# --------------------- Public API ----------------------------

def get_available_moves(gs) -> List[Move]:
    """Return L1 moves for the active unit's class."""
    stats = _active_stats(gs)
    norm = _normalize_class(stats)
    if not norm:
        return []
    return list(_MOVE_REGISTRY.get(norm, []))

def get_pp(gs, move_id: str) -> tuple[int, int]:
    """
    Return (remaining, max) for the active ally and given move_id.
    If the move isn't known/available, returns (0, 0).
    """
    mv = None
    for lst in _MOVE_REGISTRY.values():
        for m in lst:
            if m.id == move_id:
                mv = m
                break
        if mv:
            break
    if not mv:
        return (0, 0)
    actor = _active_token_name(gs)
    rem = _pp_get(gs, actor, mv)
    return rem, mv.max_pp

def queue(gs, move_id: str) -> bool:
    """UI entry point: find the move and execute immediately (spends PP)."""
    mv = None
    for lst in _MOVE_REGISTRY.values():
        for m in lst:
            if m.id == move_id:
                mv = m
                break
        if mv:
            break
    if not mv:
        return False

    actor = _active_token_name(gs)
    if not _pp_spend(gs, actor, mv):
        # If ALL moves are empty, auto-Struggle → Bonk
        if _all_moves_out_of_pp(gs):
            return _perform_bonk(gs)
        # Otherwise show the usual “No PP remaining!” card
        st = getattr(gs, "_wild", None)
        if isinstance(st, dict):
            st["result"] = {
                "kind": "fail",
                "title": mv.label,
                "subtitle": "No PP remaining!",
                "t": 0.0, "alpha": 0, "played": False,
                "exit_on_close": False,
            }
        return True  # handled
    return _perform_basic_attack(gs, mv)


# --------------------- Executor ------------------------------

def _perform_basic_attack(gs, mv: Move) -> bool:
    """d20 vs AC, then mv.dice + ability mod damage on hit. Info result card on hit/miss."""
    st = getattr(gs, "_wild", None)
    if not isinstance(st, dict):
        return False

    stats = _active_stats(gs)
    atk_bonus = _ability_mod(stats, mv.ability) + PROF_FLAT
    ac = _enemy_ac(gs)

    _set_resolving(True)
    try:
        # To-hit
        hit = False
        crit = False
        total_to_hit = 0
        try:
            atk_res = roller.roll_attack(attack_bonus=atk_bonus, target_ac=ac, adv=0, notify=False)
            hit = bool(getattr(atk_res, "hit", False))
            crit = bool(getattr(atk_res, "crit", False))
            total_to_hit = int(getattr(atk_res, "total", 0))
        except Exception:
            import random
            d20 = random.randint(1, 20)
            total_to_hit = d20 + atk_bonus
            crit = (d20 == 20)
            hit = (total_to_hit >= ac)

        print(f"[moves] {mv.label} → to-hit total={total_to_hit} vs AC {ac} | hit={hit} crit={crit}")

        if not hit:
            st["result"] = {
                "kind": "info",
                "title": mv.label,
                "subtitle": f"Miss! (roll {total_to_hit} vs AC {ac})",
                "t": 0.0, "alpha": 0, "played": False,
                "exit_on_close": False,
            }
            _play_move_sfx(mv.label)
            return True

        # Damage (double dice on crit)
        dice_n, dice_s = mv.dice
        bonus_mod = _ability_mod(stats, mv.ability)
        try:
            dmg_res = roller.roll_damage(dice=(dice_n, dice_s), bonus=bonus_mod, crit=crit, notify=False)
            total_dmg = int(getattr(dmg_res, "total", 0))
        except Exception:
            import random
            base = sum(random.randint(1, dice_s) for _ in range(dice_n))
            if crit:
                base += sum(random.randint(1, dice_s) for _ in range(dice_n))
            total_dmg = base + bonus_mod

        total_dmg = max(0, total_dmg)
        cur, mx = _enemy_hp_tuple(gs)
        new_cur = max(0, cur - total_dmg)
        _set_enemy_hp(gs, new_cur, mx)

        print(f"[moves] {mv.label} → damage={total_dmg} | enemy {cur} → {new_cur}")

        if new_cur <= 0:
            # Trigger fade; wild_vessel will show KO card (from pending_result_payload) then exit.
            st["enemy_fade_active"] = True
            st["enemy_fade_t"] = 0.0

            n, s = mv.dice
            breakdown = f"{n}d{s} + {mv.ability} = {total_dmg}"
            st["pending_result_payload"] = (
                "success",
                f"{mv.label} – KO!",
                f"Dealt {total_dmg} ({breakdown})"
            )

            # Flag is useful if your scene checks it before deciding what to do after fade
            st["enemy_defeated"] = True
        else:
            st["result"] = {
                "kind": "info",
                "title": mv.label,
                "subtitle": f"Hit for {total_dmg}!",
                "t": 0.0, "alpha": 0, "played": False,
                "exit_on_close": False,
            }

        _play_move_sfx(mv.label)
        return True
    finally:
        _set_resolving(False)

# ------------- Back-compat helpers (Wild Swing) --------------

def move_available_wild_swing(gs) -> bool:
    stats = _active_stats(gs)
    norm = _normalize_class(stats)
    return norm == "barbarian"

def queue_wild_swing(gs) -> bool:
    return queue(gs, "barb_l1_wild_swing")

def resolve_after_popup(gs) -> Optional[str]:
    return None
