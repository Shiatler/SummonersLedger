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
from combat.animation import move_anim as move_anim_sys
from rolling import roller  # calls are wrapped in try/except
from combat.stats import proficiency_for_level
from combat.type_chart import (
    get_class_damage_type, 
    normalize_class_name,
    get_type_effectiveness,
    get_effectiveness_label,
    get_effectiveness_color
)

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
    damage_type: Optional[str] = None  # D&D damage type (Piercing, Fire, etc.) - auto-determined from class if None

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
    old_cur = int(st.get("current_hp", maxhp))
    new_cur = max(0, min(maxhp, int(new_cur)))
    
    # Set HP normally - Infernal Rebirth will be checked after the vessel swap
    st["current_hp"] = new_cur
    stats_list[idx] = st
    gs.party_vessel_stats = stats_list
    # keep on-screen bar in sync
    wild = getattr(gs, "_wild", {}) or {}
    wild["ally_hp_ratio"] = (new_cur / maxhp) if maxhp > 0 else 0.0
    gs._wild = wild

def _check_infernal_rebirth(gs, vessel_idx: int, maxhp: int, stats_list=None, vessel_stats_dict=None) -> bool:
    """
    DEPRECATED: This function is no longer used. Infernal Rebirth is now handled
    by _try_revive_dead_vessel_with_infernal_rebirth in wild_vessel.py and battle.py.
    
    Kept for backwards compatibility, but should not be called.
    """
    # This function is deprecated - the revival logic has been moved to
    # _try_revive_dead_vessel_with_infernal_rebirth which is called after vessel swaps.
    print(f"⚠️ _check_infernal_rebirth is deprecated and should not be called")
    return False

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
    """Return moves for the enemy's class, filtered by enemy level."""
    norm = _normalize_class(_enemy_stats(gs))
    if not norm:
        # try by class_name string if dict didn't normalize
        s = _enemy_class_string(gs)
        norm = _CLASS_KEYS.get(s.lower(), None) if s else None
    if not norm:
        return []
    
    # Get enemy level
    stats = _enemy_stats(gs)
    level = 1
    if isinstance(stats, dict):
        try:
            level = int(stats.get("level", 1))
        except Exception:
            level = 1
    
    # Filter moves by level requirement (same logic as allies)
    all_moves = _MOVE_REGISTRY.get(norm, [])
    available = []
    for move in all_moves:
        if "_l1_" in move.id:
            available.append(move)
        elif "_l10_" in move.id and level >= 10:
            available.append(move)
        elif "_l20_" in move.id and level >= 20:
            available.append(move)
        elif "_l40_" in move.id and level >= 40:
            available.append(move)
        elif "_l50_" in move.id and level >= 50:
            available.append(move)
    
    return available

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
    """
    Read AC from the active ALLY stats.
    The AC field should already include bonuses (updated by apply_ac_bonus),
    but we also check ac_bonus as a fallback for compatibility.
    """
    cur, idx = None, getattr(gs, "combat_active_idx", 0)
    stats_list = getattr(gs, "party_vessel_stats", None) or [None]*6
    st = stats_list[idx] if 0 <= idx < len(stats_list) else None
    try:
        # The ac field should already include the bonus (updated by apply_ac_bonus)
        ac_from_field = int((st or {}).get("ac", 10))
        ac_bonus = int((st or {}).get("ac_bonus", 0))
        
        # Use the ac field directly (it should already include bonuses)
        # But if ac_bonus exists and the ac field doesn't include it, add it
        # This handles cases where ac was updated but might need the bonus added
        total_ac = ac_from_field
        
        # Debug logging (can be removed later)
        if ac_bonus > 0:
            print(f"🛡️ _ally_ac: Vessel {idx} has AC {ac_from_field} (ac_bonus field: {ac_bonus})")
        
        return total_ac
    except Exception as e:
        print(f"⚠️ _ally_ac error: {e}")
        return 10

def _perform_enemy_basic_attack(gs, mv: Move) -> bool:
    """Enemy uses a basic attack against the active ally (same math/UX as ally path)."""
    st = getattr(gs, "_wild", None)
    if not isinstance(st, dict):
        return False

    # Get proficiency from enemy stats, or calculate from level
    enemy_stats = _enemy_stats(gs)
    prof = enemy_stats.get("prof") if isinstance(enemy_stats, dict) else 2
    if prof is None or not isinstance(prof, int):
        level = enemy_stats.get("level", 1) if isinstance(enemy_stats, dict) else 1
        try:
            prof = proficiency_for_level(int(level))
        except Exception:
            prof = 2
    atk_bonus = _ability_mod_enemy(gs, mv.ability) + prof
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
            try:
                setattr(gs, "_move_anim", {'target_side': 'ally'})
                move_anim_sys.start_move_anim(gs, mv)
            except Exception:
                pass
            _play_move_sfx(mv); _click()
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
        print(f"[moves][ENEMY] Base damage before type effectiveness: {total_dmg}")
        
        # Apply type effectiveness (D&D damage type system)
        type_effectiveness = 1.0
        effectiveness_label = ""
        try:
            # Get attacker's (enemy's) class
            enemy_stats = _enemy_stats(gs)
            attacker_class = _class_string(enemy_stats) if isinstance(enemy_stats, dict) else None
            
            # Get move's damage type
            move_damage_type = _get_move_damage_type(mv, attacker_class)
            
            # Get defender's (ally's) class
            stats = _active_stats(gs)
            defender_class = _class_string(stats) if isinstance(stats, dict) else None
            
            print(f"[moves][ENEMY] Type calc - attacker_class: '{attacker_class}', move_damage_type: '{move_damage_type}', defender_class: '{defender_class}'")
            
            if move_damage_type and defender_class:
                type_effectiveness = get_type_effectiveness(move_damage_type, defender_class)
                effectiveness_label = get_effectiveness_label(type_effectiveness)
                
                print(f"[moves][ENEMY] Type effectiveness result: {type_effectiveness}, label: '{effectiveness_label}'")
                
                if type_effectiveness != 1.0:
                    original_dmg = total_dmg
                    multiplied = total_dmg * type_effectiveness
                    total_dmg = int(multiplied)
                    print(f"[moves][ENEMY] Type effectiveness: {move_damage_type} vs {defender_class} = {effectiveness_label} ({type_effectiveness}x) | {original_dmg} * {type_effectiveness} = {multiplied} → {total_dmg}")
                else:
                    print(f"[moves][ENEMY] Type effectiveness: {move_damage_type} vs {defender_class} = {effectiveness_label} ({type_effectiveness}x)")
            else:
                print(f"[moves][ENEMY] Missing data for type effectiveness: move_damage_type={move_damage_type}, defender_class={defender_class}")
        except Exception as e:
            print(f"⚠️ Type effectiveness calculation error (enemy): {e}")
            import traceback
            traceback.print_exc()
        
        total_dmg = max(0, total_dmg)
        print(f"[moves][ENEMY] Final damage after type effectiveness: {total_dmg}")
        
        # Apply damage reduction from buffs
        original_dmg = total_dmg
        stats = _active_stats(gs)
        if isinstance(stats, dict):
            damage_reduction = int(stats.get("damage_reduction", 0))
            if damage_reduction > 0:
                total_dmg = max(0, total_dmg - damage_reduction)
                if original_dmg != total_dmg:
                    print(f"[moves][ENEMY] Damage reduced by {damage_reduction}: {original_dmg} → {total_dmg}")
        
        a_cur, a_max = _ally_hp_tuple(gs)
        new_cur = max(0, a_cur - total_dmg)
        _set_ally_hp(gs, new_cur, a_max)

        print(f"[moves][ENEMY] {mv.label} → damage={total_dmg} | ally {a_cur} → {new_cur}")

        # Update display message to show original damage if reduced, and type effectiveness
        dmg_display = total_dmg
        if original_dmg != total_dmg:
            dmg_display = f"{original_dmg} (reduced to {total_dmg})"
        
        subtitle = f"Hit for {dmg_display}!"
        if effectiveness_label:
            subtitle += f" [{effectiveness_label}]"
        if new_cur <= 0:
            subtitle += " (You're down)"
        
        st["result"] = {
            "kind": "info",
            "title": f"Enemy used {mv.label}",
            "subtitle": subtitle,
            "t": 0.0, "alpha": 0, "played": False,
            "exit_on_close": False,
        }
        
        # Store effectiveness info for display (always store, including 1x)
        if effectiveness_label:
            st["last_type_effectiveness"] = {
                "label": effectiveness_label,
                "multiplier": type_effectiveness,
                "color": get_effectiveness_color(type_effectiveness)
            }
        else:
            st.pop("last_type_effectiveness", None)
        
        try:
            setattr(gs, "_move_anim", {'target_side': 'ally'})
            move_anim_sys.start_move_anim(gs, mv)
        except Exception:
            pass
        _play_move_sfx(mv); _click()
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

        # deal to ally (apply damage reduction)
        original_ally_dmg = ally_dmg
        stats = _active_stats(gs)
        if isinstance(stats, dict):
            damage_reduction = int(stats.get("damage_reduction", 0))
            if damage_reduction > 0:
                ally_dmg = max(0, ally_dmg - damage_reduction)
        
        a_cur, a_max = _ally_hp_tuple(gs)
        new_cur = max(0, a_cur - ally_dmg)
        _set_ally_hp(gs, new_cur, a_max)

        # recoil to enemy
        e_cur, e_max = _enemy_hp_tuple(gs)
        _set_enemy_hp(gs, max(0, e_cur - recoil), e_max)

        # Update display message to show original damage if reduced
        dmg_display = ally_dmg
        if original_ally_dmg != ally_dmg:
            dmg_display = f"{original_ally_dmg} (reduced to {ally_dmg})"
        
        st["result"] = {
            "kind": "info",
            "title": "Enemy Bonk",
            "subtitle": f"You took {dmg_display}, enemy took {recoil}",
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
        
        # Apply permanent damage bonus to enemy damage (bonk deals damage to enemy)
        stats = _active_stats(gs)
        if isinstance(stats, dict):
            permanent_damage_bonus = int(stats.get("permanent_damage_bonus", 0))
            if permanent_damage_bonus > 0:
                enemy_dmg += permanent_damage_bonus
                print(f"[moves][Bonk] Permanent damage bonus +{permanent_damage_bonus} applied: {enemy_dmg - permanent_damage_bonus} → {enemy_dmg}")

        # enemy HP change
        e_cur, e_max = _enemy_hp_tuple(gs)
        _set_enemy_hp(gs, max(0, e_cur - enemy_dmg), e_max)

        # ally HP change (self damage - damage reduction doesn't apply to self-damage)
        a_cur, a_max = _ally_hp_tuple(gs)
        new_cur = max(0, a_cur - self_dmg)
        _set_ally_hp(gs, new_cur, a_max)

        # results
        if e_cur - enemy_dmg <= 0:
            st["enemy_fade_active"] = True
            st["enemy_fade_t"] = 0.0
            st["pending_result_payload"] = ("success", "Bonk – KO!", f"Enemy took {enemy_dmg}, you took {self_dmg}")
            st["enemy_defeated"] = True
        elif not st.get("result"):
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

def _class_and_level_from_move_id(move_id: str) -> tuple[str | None, int | None]:
    """
    Extract normalized class key and level from a move id like 'barb_l1_wild_swing' or 'wizard_l20_fireball'.
    Returns (ClassDisplayName, level_number) where ClassDisplayName is capitalized (e.g., 'Barbarian').
    """
    try:
        s = (move_id or "").lower()
        # map prefixes used in ids to canonical class key
        id_to_class_key = {
            "barb": "barbarian",
            "druid": "druid",
            "rogue": "rogue",
            "wizard": "wizard",
            "cleric": "cleric",
            "paladin": "paladin",
            "ranger": "ranger",
            "warlock": "warlock",
            "monk": "monk",
            "sorc": "sorcerer",
            "arti": "artificer",
            "bh": "bloodhunter",
            "fighter": "fighter",
            "bard": "bard",
            # monsters (optional)
            "dragon": "dragon",
            "owlbear": "owlbear",
            "beholder": "beholder",
            "golem": "golem",
            "ogre": "ogre",
            "nothic": "nothic",
            "myconid": "myconid",
        }
        class_key = None
        for prefix, key in id_to_class_key.items():
            if s.startswith(prefix + "_") or s.startswith(prefix + "l") or s.startswith(prefix):
                class_key = key
                break
        lvl = None
        m = re.search(r"_l(\d+)_", s)
        if m:
            try:
                lvl = int(m.group(1))
            except Exception:
                lvl = None
        # Display name → PascalCase without spaces (e.g., BloodHunter)
        class_display = None
        if class_key:
            parts = re.split(r"[^a-zA-Z0-9]+", class_key)
            class_display = "".join(p.capitalize() for p in parts if p)
        return class_display, lvl
    except Exception:
        return None, None

def _load_move_sfx(label_or_move) -> pygame.mixer.Sound | None:
    """
    Load (and cache) a pygame Sound for a move.
    Supports two lookup schemes:
      1) New: Assets/Music/Moves/<Class><Level>.mp3  (e.g., Barbarian1.mp3, Druid10.mp3)
      2) Legacy: Assets/Music/Moves/<slug(label)>.mp3 (e.g., wild_swing.mp3)
    Returns None on failure.
    """
    # Determine cache key and candidate filenames
    cache_key = None
    candidates: list[str] = []

    # If we were passed a Move, try class+level first
    try:
        from dataclasses import is_dataclass
        is_move_obj = is_dataclass(label_or_move) or hasattr(label_or_move, "id")
    except Exception:
        is_move_obj = False

    if is_move_obj:
        mv = label_or_move
        cache_key = getattr(mv, "id", None) or getattr(mv, "label", None)
        class_display, lvl = _class_and_level_from_move_id(str(getattr(mv, "id", "")))
        if class_display and lvl is not None:
            candidates.append(os.path.join(_SFX_DIR, f"{class_display}{lvl}.mp3"))
        # also try class without level as fallback, e.g., Warlock.mp3
        if class_display:
            candidates.append(os.path.join(_SFX_DIR, f"{class_display}.mp3"))
        # fallback to label slug
        slug = _slugify_label(str(getattr(mv, "label", "move")))
        candidates.append(os.path.join(_SFX_DIR, f"{slug}.mp3"))
        # try by damage type name (e.g., Piercing.mp3), if resolvable
        try:
            from combat.type_chart import get_class_damage_type
            dmg_type = None
            # prefer explicit damage_type if present on move
            if getattr(mv, "damage_type", None):
                dmg_type = mv.damage_type
            else:
                # attempt to infer from class_display
                if class_display:
                    dmg_type = get_class_damage_type(class_display)
            if dmg_type:
                candidates.append(os.path.join(_SFX_DIR, f"{dmg_type}.mp3"))
        except Exception:
            pass
        # final generic fallback
        candidates.append(os.path.join(_SFX_DIR, "attack.mp3"))
    else:
        # string label path (legacy behavior)
        label = str(label_or_move or "move")
        cache_key = _slugify_label(label)
        candidates.append(os.path.join(_SFX_DIR, f"{cache_key}.mp3"))

    # Cache hit?
    if cache_key in _SFX_CACHE:
        return _SFX_CACHE[cache_key]

    try:
        # Try candidates in order
        chosen = None
        for path in candidates:
            if os.path.exists(path):
                chosen = path
                break
        if not chosen:
            # Helpful debug so missing SFX are visible in logs
            try:
                print(f"ℹ️ No move SFX found. Tried: " + ", ".join(candidates))
            except Exception:
                pass
            _SFX_CACHE[cache_key] = None
            return None
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        snd = pygame.mixer.Sound(chosen)
        _SFX_CACHE[cache_key] = snd
        return snd
    except Exception as e:
        print(f"⚠️ move SFX load fail: {e}")
        _SFX_CACHE[cache_key] = None
        return None

def _play_move_sfx(label_or_move):
    try:
        snd = _load_move_sfx(label_or_move)
        if snd:
            # OLD: snd.play()
            audio_sys.play_sound(snd)   # honors SFX master
    except Exception:
        pass

def _get_move_damage_type(mv: Move, attacker_class: Optional[str] = None) -> Optional[str]:
    """
    Get the damage type for a move.
    
    Priority:
    1. If move has explicit damage_type, use it
    2. If attacker_class provided, get damage type from class
    3. Extract class from move ID (e.g., "barb_l1_wild_swing" -> "barbarian")
    4. Return None if can't determine
    
    Args:
        mv: The Move object
        attacker_class: Optional class name of the attacker (for fallback)
    
    Returns:
        Damage type string (e.g., "Piercing") or None
    """
    # Priority 1: Explicit damage_type on move
    if mv.damage_type:
        return mv.damage_type
    
    # Priority 2: Use provided attacker class
    if attacker_class:
        dmg_type = get_class_damage_type(attacker_class)
        if dmg_type:
            return dmg_type
    
    # Priority 3: Extract class from move ID
    # Move IDs are like "barb_l1_wild_swing", "druid_l10_flame_seed", etc.
    move_id = mv.id.lower()
    
    # Map move ID prefixes to class names
    id_to_class = {
        "barb": "barbarian",
        "druid": "druid",
        "rogue": "rogue",
        "wizard": "wizard",
        "cleric": "cleric",
        "paladin": "paladin",
        "ranger": "ranger",
        "warlock": "warlock",
        "monk": "monk",
        "sorc": "sorcerer",
        "arti": "artificer",
        "bh": "bloodhunter",
        "fighter": "fighter",
        "bard": "bard",
        # Monsters (fallback to fighter for now, or could add monster types later)
        "dragon": "fighter",  # Default to fighter for monsters
        "owlbear": "fighter",
        "beholder": "fighter",
        "golem": "fighter",
        "ogre": "fighter",
        "nothic": "fighter",
        "myconid": "fighter",
    }
    
    for prefix, class_name in id_to_class.items():
        if move_id.startswith(prefix):
            dmg_type = get_class_damage_type(class_name)
            if dmg_type:
                return dmg_type
    
    return None


# --------------------- Registry (Level 1) --------------------

_CLASS_KEYS = {
    # Monsters
    "dragon": "dragon",
    "owlbear": "owlbear",
    "beholder": "beholder",
    "golem": "golem",
    "ogre": "ogre",
    "nothic": "nothic",
    "myconid": "myconid",
    # Regular classes
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

# All moves (Level 1, 10, 20, 40, 50) - PP balanced system
_MOVE_REGISTRY: Dict[str, List[Move]] = {
    "barbarian": [
        Move("barb_l1_wild_swing", "Wild Swing", "Sloppy first strike.", (1, 5), "STR", True, 0, 20),
        Move("barb_l10_reckless_strike", "Reckless Strike", "Swing with reckless abandon; hits harder, misses often.", (1, 10), "STR", True, 0, 12),
        Move("barb_l20_frenzied_blow", "Frenzied Blow", "A trained rhythm of rage; two brutal chops in one motion.", (2, 6), "STR", True, 0, 6),
        Move("barb_l40_brutal_cleave", "Brutal Cleave", "Heavy strike that channels every ounce of strength.", (2, 10), "STR", True, 0, 3),
        Move("barb_l50_world_breaker", "World Breaker", "Devastating ground slam.", (3, 12), "STR", True, 0, 1),
    ],
    "druid": [
        Move("druid_l1_thorn_whip", "Thorn Whip", "Cantrip lash of vines.", (2, 3), "WIS", True, 0, 20),
        Move("druid_l10_flame_seed", "Flame Seed", "A spark of wildfire magic from nature's fury.", (1, 8), "WIS", True, 0, 15),
        Move("druid_l20_moonbeam", "Moonbeam", "Summon pale lunar energy to sear a single foe.", (2, 6), "WIS", True, 0, 8),
        Move("druid_l40_call_lightning", "Call Lightning", "Command a bolt of the storm itself.", (3, 8), "WIS", True, 0, 2),
        Move("druid_l50_storm_of_ages", "Storm of Ages", "Full fury of nature's wrath.", (5, 10), "WIS", True, 0, 1),
    ],
    "rogue": [
        Move("rogue_l1_quick_stab", "Quick Stab", "Hasty jab.", (1, 5), "DEX", True, 0, 20),
        Move("rogue_l10_sneak_strike", "Sneak Strike", "A practiced backstab from the shadows.", (2, 5), "DEX", True, 0, 10),
        Move("rogue_l20_cunning_flurry", "Cunning Flurry", "Swift, precise blows exploiting every weakness.", (3, 5), "DEX", True, 0, 5),
        Move("rogue_l40_assassinate", "Assassinate", "A deadly opening strike with high crit potential.", (4, 6), "DEX", True, 0, 2),
        Move("rogue_l50_death_mark", "Death Mark", "Guaranteed critical strike.", (6, 10), "DEX", True, 0, 1),
    ],
    "wizard": [
        Move("wizard_l1_arcane_bolt", "Arcane Bolt", "Spark of arcane energy.", (1, 6), "INT", True, 0, 20),
        Move("wizard_l10_scorching_ray", "Scorching Ray", "Twin beams of focused fire.", (4, 3), "INT", True, 0, 8),
        Move("wizard_l20_fireball", "Fireball", "Explosive burst of chaotic flame.", (6, 6), "INT", True, 0, 1),
        Move("wizard_l40_blight", "Blight", "Drain life and vitality with dark magic.", (8, 8), "INT", True, 0, 1),
        Move("wizard_l50_meteor_swarm", "Meteor Swarm", "Summon meteors from the heavens.", (10, 8), "INT", True, 0, 1),
    ],
    "cleric": [
        Move("cleric_l1_sacred_flame", "Sacred Flame", "Radiant spark.", (1, 5), "WIS", True, 0, 20),
        Move("cleric_l10_guiding_bolt", "Guiding Bolt", "Blast of holy energy that scorches evil.", (3, 6), "WIS", True, 0, 4),
        Move("cleric_l20_spiritual_weapon", "Spiritual Weapon", "Summon a spectral blade for radiant punishment.", (2, 8), "WIS", True, 0, 10),
        Move("cleric_l40_flame_strike", "Flame Strike", "Call down holy fire upon your foes.", (4, 8), "WIS", True, 0, 2),
        Move("cleric_l50_divine_intervention", "Divine Intervention", "Channel the full power of your deity.", (6, 10), "WIS", True, 0, 1),
    ],
    "paladin": [
        Move("paladin_l1_smite_training", "Smite Training", "Basic weapon strike infused with faint divine power.", (1, 8), "STR", True, 0, 20),
        Move("paladin_l10_divine_smite", "Divine Smite", "Infuse your attack with sacred light.", (1, 12), "STR", True, 0, 10),
        Move("paladin_l20_crusaders_wrath", "Crusader's Wrath", "Righteous strength guided by faith.", (1, 20), "STR", True, 0, 5),
        Move("paladin_l40_holy_smite", "Holy Smite", "True divine retribution.", (4, 8), "STR", True, 0, 2),
        Move("paladin_l50_avenging_wrath", "Avenging Wrath", "Divine judgment that cannot be denied.", (5, 10), "STR", True, 0, 1),
    ],
    "ranger": [
        Move("ranger_l1_aimed_shot", "Aimed Shot", "Careful bow shot.", (1, 5), "DEX", True, 0, 20),
        Move("ranger_l10_hunters_mark", "Hunter's Mark", "Marked prey takes focused damage.", (2, 7), "DEX", True, 0, 10),  # 1d8+1d6 approximated as 2d7
        Move("ranger_l20_hail_of_thorns", "Hail of Thorns", "Arrows explode into piercing splinters.", (3, 5), "DEX", True, 0, 6),
        Move("ranger_l40_lightning_arrow", "Lightning Arrow", "A charged shot that carries storm power.", (4, 8), "DEX", True, 0, 2),
        Move("ranger_l50_heartseeker", "Heartseeker", "Always finds its mark.", (5, 10), "DEX", True, 0, 1),
    ],
    "warlock": [
        Move("warlock_l1_eldritch_blast", "Eldritch Blast", "Signature cantrip of dark energy.", (1, 6), "CHA", True, 0, 20),
        Move("warlock_l10_agonizing_blast", "Agonizing Blast", "More painful, refined version of your blast.", (1, 12), "CHA", True, 0, 12),
        Move("warlock_l20_hunger_of_hadar", "Hunger of Hadar", "Tear a rift into the void's cold darkness.", (4, 5), "CHA", True, 0, 4),
        Move("warlock_l40_eldritch_torrent", "Eldritch Torrent", "Continuous beam of infernal destruction.", (6, 10), "CHA", True, 0, 1),
        Move("warlock_l50_soul_rend", "Soul Rend", "Tear at the very essence of your target.", (8, 10), "CHA", True, 0, 1),
    ],
    "monk": [
        Move("monk_l1_martial_strike", "Martial Strike", "Basic unarmed strike.", (1, 5), "DEX", True, 0, 20),
        Move("monk_l10_flurry_of_blows", "Flurry of Blows", "Two lightning-fast strikes.", (2, 6), "DEX", True, 0, 10),
        Move("monk_l20_stunning_strike", "Stunning Strike", "Precise nerve hit that disrupts focus.", (2, 10), "DEX", True, 0, 15),
        Move("monk_l40_quivering_palm", "Quivering Palm", "Devastating ki strike from within.", (4, 10), "DEX", True, 0, 2),
        Move("monk_l50_perfect_strike", "Perfect Strike", "Flawless ki strike that transcends the physical.", (5, 12), "DEX", True, 0, 1),
    ],
    "sorcerer": [
        Move("sorc_l1_burning_hands", "Burning Hands", "Brief cone of flame.", (2, 3), "CHA", True, 0, 20),
        Move("sorc_l10_chromatic_orb", "Chromatic Orb", "Hurl an orb of random elemental energy (fire, ice, lightning, or acid). Pure chaos given form.", (3, 5), "CHA", True, 0, 10),
        Move("sorc_l20_fireball", "Fireball", "The classic explosion of chaos and pride.", (8, 6), "CHA", True, 0, 1),
        Move("sorc_l40_disintegrate", "Disintegrate", "A single ray that vaporizes its target.", (10, 6), "CHA", True, 0, 1),
        Move("sorc_l50_reality_warp", "Reality Warp", "Bend reality itself to your will.", (12, 8), "CHA", True, 0, 1),
    ],
    "artificer": [
        Move("arti_l1_arcane_shot", "Arcane Shot", "Tinkered magic bolt.", (1, 5), "INT", True, 0, 20),
        Move("arti_l10_thunder_gauntlet", "Thunder Gauntlet", "Punch augmented by a thunderous shockwave.", (1, 8), "INT", True, 0, 15),
        Move("arti_l20_explosive_device", "Explosive Device", "Throw a timed alchemical bomb for big impact.", (2, 10), "INT", True, 0, 8),
        Move("arti_l40_arcane_cannon", "Arcane Cannon", "Deploy your perfected invention for a devastating burst.", (3, 10), "INT", True, 0, 2),
        Move("arti_l50_grand_invention", "Grand Invention", "Masterpiece weapon fires at full power.", (6, 10), "INT", True, 0, 1),
    ],
    "blood_hunter": [
        Move("bh_l1_hemorrhage_cut", "Hemorrhage Cut", "Brutal self-fueled cut.", (1, 5), "STR|DEX", True, 0, 20),
        Move("bh_l10_crimson_slash", "Crimson Slash", "Empowered strike at the cost of 2 HP.", (2, 5), "STR|DEX", True, 2, 12),
        Move("bh_l20_rite_of_the_blade", "Rite of the Blade", "Channel cursed energy through your weapon; costs 3 HP.", (3, 7), "STR|DEX", True, 3, 6),
        Move("bh_l40_blood_nova", "Blood Nova", "Release stored life force in a devastating arc; costs 5 HP.", (4, 12), "STR|DEX", True, 5, 2),
        Move("bh_l50_final_rite", "Final Rite", "Sacrifice 10 HP for ultimate cursed power.", (6, 12), "STR|DEX", True, 10, 1),
    ],
    "fighter": [
        Move("fighter_l1_weapon_strike", "Weapon Strike", "Disciplined opening attack.", (1, 5), "STR|DEX", True, 0, 20),
        Move("fighter_l10_action_surge", "Action Surge", "Unleash a flurry of precise strikes.", (2, 6), "STR|DEX", True, 0, 10),
        Move("fighter_l20_second_wind", "Second Wind", "Channel renewed vigor into a devastating blow.", (3, 7), "STR|DEX", True, 0, 5),
        Move("fighter_l40_ultimate_technique", "Ultimate Technique", "Masterful execution of combat perfection.", (4, 12), "STR|DEX", True, 0, 2),
        Move("fighter_l50_legendary_strike", "Legendary Strike", "A strike that transcends mortal skill.", (5, 12), "STR|DEX", True, 0, 1),
    ],
    "bard": [
        Move("bard_l1_vicious_mockery", "Vicious Mockery", "Psychic jab that rattles.", (1, 4), "CHA", True, 0, 20),
        Move("bard_l10_cutting_words", "Cutting Words", "Sharp words that strike like blades.", (2, 6), "CHA", True, 0, 12),
        Move("bard_l20_inspire_combat", "Combat Inspiration", "Rally your allies with powerful song; channel that energy into a devastating strike.", (3, 6), "CHA", True, 0, 6),
        Move("bard_l40_sonic_boom", "Sonic Boom", "Unleash a wave of pure sound that shatters reality.", (4, 10), "CHA", True, 0, 2),
        Move("bard_l50_final_cadence", "Final Cadence", "The ultimate performance that brings all things to their end.", (6, 10), "CHA", True, 0, 1),
    ],
    # ===================== Monsters =====================
    "dragon": [
        Move("dragon_l1_claw_swipe", "Claw Swipe", "Basic dragon claw attack.", (2, 6), "STR", True, 0, 20),
        Move("dragon_l10_fire_breath", "Fire Breath", "Breathe a cone of fire.", (3, 8), "CON", True, 0, 12),
        Move("dragon_l20_tail_slam", "Tail Slam", "Crushing tail strike.", (4, 10), "STR", True, 0, 6),
        Move("dragon_l30_wing_buffet", "Wing Buffet", "Powerful wing strike.", (5, 10), "STR", True, 0, 3),
        Move("dragon_l40_dragon_roar", "Dragon Roar", "Terrifying roar that weakens foes.", (6, 12), "CHA", True, 0, 1),
    ],
    "owlbear": [
        Move("owlbear_l1_claw", "Claw", "Sharp claw attack.", (1, 8), "STR", True, 0, 20),
        Move("owlbear_l10_beak_peck", "Beak Peck", "Precise beak strike.", (2, 8), "DEX", True, 0, 12),
        Move("owlbear_l20_hunters_pounce", "Hunter's Pounce", "Leap and strike.", (3, 10), "STR", True, 0, 6),
        Move("owlbear_l30_savage_maul", "Savage Maul", "Frenzied mauling attack.", (4, 10), "STR", True, 0, 3),
        Move("owlbear_l40_primal_rage", "Primal Rage", "Unleash primal fury.", (5, 12), "STR", True, 0, 1),
    ],
    "beholder": [
        Move("beholder_l1_eye_ray", "Eye Ray", "Weak magical ray from central eye.", (1, 6), "INT", True, 0, 20),
        Move("beholder_l10_paralyzing_ray", "Paralyzing Ray", "Ray that can paralyze.", (2, 8), "INT", True, 0, 12),
        Move("beholder_l20_disintegration_ray", "Disintegration Ray", "Powerful disintegration beam.", (3, 10), "INT", True, 0, 6),
        Move("beholder_l30_antimagic_cone", "Antimagic Cone", "Suppress magic in cone.", (4, 10), "INT", True, 0, 3),
        Move("beholder_l40_all_seeing_eye", "All-Seeing Eye", "Ultimate beholder power.", (6, 12), "INT", True, 0, 1),
    ],
    "golem": [
        Move("golem_l1_fist_slam", "Fist Slam", "Heavy stone fist strike.", (1, 10), "STR", True, 0, 20),
        Move("golem_l10_stone_throw", "Stone Throw", "Hurl a boulder.", (2, 10), "STR", True, 0, 12),
        Move("golem_l20_ground_slam", "Ground Slam", "Slam ground creating shockwave.", (3, 12), "STR", True, 0, 6),
        Move("golem_l30_immovable_object", "Immovable Object", "Become unstoppable force.", (4, 12), "CON", True, 0, 3),
        Move("golem_l40_titan_strike", "Titan Strike", "Ultimate golem attack.", (5, 12), "STR", True, 0, 1),
    ],
    "ogre": [
        Move("ogre_l1_club_smash", "Club Smash", "Brutal club attack.", (1, 8), "STR", True, 0, 20),
        Move("ogre_l10_belly_slam", "Belly Slam", "Crushing body slam.", (2, 10), "STR", True, 0, 12),
        Move("ogre_l20_rage_swing", "Rage Swing", "Wild swinging attack.", (3, 10), "STR", True, 0, 6),
        Move("ogre_l30_brutal_charge", "Brutal Charge", "Charge and crush.", (4, 10), "STR", True, 0, 3),
        Move("ogre_l40_berserker_fury", "Berserker Fury", "Unleash ogre rage.", (5, 12), "STR", True, 0, 1),
    ],
    "nothic": [
        Move("nothic_l1_claw_scratch", "Claw Scratch", "Sharp claw attack.", (1, 6), "DEX", True, 0, 20),
        Move("nothic_l10_weird_insight", "Weird Insight", "Psychic damage from knowledge.", (2, 8), "INT", True, 0, 12),
        Move("nothic_l20_rotting_gaze", "Rotting Gaze", "Gaze that causes decay.", (3, 10), "INT", True, 0, 6),
        Move("nothic_l30_paranoid_whisper", "Paranoid Whisper", "Maddening whispers.", (4, 10), "CHA", True, 0, 3),
        Move("nothic_l40_eldritch_sight", "Eldritch Sight", "See through all defenses.", (5, 12), "INT", True, 0, 1),
    ],
    "myconid": [
        Move("myconid_l1_spore_puff", "Spore Puff", "Weak spore attack.", (1, 4), "CON", True, 0, 20),
        Move("myconid_l10_poison_spores", "Poison Spores", "Toxic spore cloud.", (2, 6), "CON", True, 0, 12),
        Move("myconid_l20_animating_spores", "Animating Spores", "Spores that sap strength.", (3, 8), "CON", True, 0, 6),
        Move("myconid_l30_pacifying_spores", "Pacifying Spores", "Spores that calm enemies.", (4, 8), "WIS", True, 0, 3),
        Move("myconid_l40_spore_burst", "Spore Burst", "Massive spore explosion.", (5, 10), "CON", True, 0, 1),
    ],
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
    """Set PP to full (using effective max_pp including bonuses)."""
    # Get effective max_pp (base + bonuses)
    base_max_pp = move.max_pp
    if hasattr(gs, "move_pp_max_bonuses"):
        key = f"{actor_key}:{move.id}"
        bonus = gs.move_pp_max_bonuses.get(key, 0)
        effective_max_pp = base_max_pp + bonus
    else:
        effective_max_pp = base_max_pp
    _pp_store(gs).setdefault(actor_key, {})[move.id] = effective_max_pp

# --------------------- Busy flag for scenes ------------------

_RESOLVING = False
def is_resolving() -> bool:
    return _RESOLVING

def _set_resolving(v: bool):
    global _RESOLVING
    _RESOLVING = bool(v)

# --------------------- Public API ----------------------------

def get_available_moves(gs) -> List[Move]:
    """Return moves for the active unit's class, filtered by level."""
    stats = _active_stats(gs)
    norm = _normalize_class(stats)
    if not norm:
        return []
    
    # Get vessel level
    level = 1
    if isinstance(stats, dict):
        try:
            level = int(stats.get("level", 1))
        except Exception:
            level = 1
    
    # Debug: Print level for troubleshooting
    # print(f"[moves] Ally vessel level: {level}, class: {norm}")
    
    # Filter moves by level requirement
    all_moves = _MOVE_REGISTRY.get(norm, [])
    available = []
    for move in all_moves:
        # Extract level requirement from move ID (e.g., "barb_l10_reckless_strike" -> 10)
        # Level 1 moves (L1) are available at level 1+
        # Level 10 moves (L10) require level 10+
        # Level 20 moves (L20) require level 20+
        # Level 40 moves (L40) require level 40+
        # Level 50 moves (L50) require level 50+
        if "_l1_" in move.id:
            available.append(move)
        elif "_l10_" in move.id and level >= 10:
            available.append(move)
        elif "_l20_" in move.id and level >= 20:
            available.append(move)
        elif "_l40_" in move.id and level >= 40:
            available.append(move)
        elif "_l50_" in move.id and level >= 50:
            available.append(move)
    
    # Debug: Print available moves count
    # print(f"[moves] Available moves for level {level}: {len(available)} out of {len(all_moves)}")
    
    return available

def get_pp(gs, move_id: str) -> tuple[int, int]:
    """
    Return (remaining, max) for the active ally and given move_id.
    If the move isn't known/available, returns (0, 0).
    Max includes any permanent PP max bonuses from buffs.
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
    
    # Get base max_pp from move
    base_max_pp = mv.max_pp
    
    # Apply permanent max_pp bonuses from buffs
    if hasattr(gs, "move_pp_max_bonuses"):
        key = f"{actor}:{move_id}"
        bonus = gs.move_pp_max_bonuses.get(key, 0)
        effective_max_pp = base_max_pp + bonus
    else:
        effective_max_pp = base_max_pp
    
    return rem, effective_max_pp

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
    # Get proficiency from stats, or calculate from level
    prof = stats.get("prof") if isinstance(stats, dict) else 2
    if prof is None or not isinstance(prof, int):
        level = stats.get("level", 1) if isinstance(stats, dict) else 1
        try:
            prof = proficiency_for_level(int(level))
        except Exception:
            prof = 2
    atk_bonus = _ability_mod(stats, mv.ability) + prof
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
            # Start player-side animation towards enemy
            try:
                setattr(gs, "_move_anim", {'target_side': 'enemy'})
                move_anim_sys.start_move_anim(gs, mv)
            except Exception:
                pass
            _play_move_sfx(mv)
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
        
        # Apply permanent damage bonus from buffs
        if isinstance(stats, dict):
            permanent_damage_bonus = int(stats.get("permanent_damage_bonus", 0))
            if permanent_damage_bonus > 0:
                total_dmg += permanent_damage_bonus
                print(f"[moves] Permanent damage bonus +{permanent_damage_bonus} applied: {total_dmg - permanent_damage_bonus} → {total_dmg}")
        
        # Apply type effectiveness (D&D damage type system)
        type_effectiveness = 1.0
        effectiveness_label = ""
        try:
            # Get attacker's class
            attacker_class = _class_string(stats) if isinstance(stats, dict) else None
            
            # Get move's damage type
            move_damage_type = _get_move_damage_type(mv, attacker_class)
            
            # Get defender's (enemy's) class
            enemy_stats = _enemy_stats(gs)
            defender_class = _class_string(enemy_stats) if isinstance(enemy_stats, dict) else None
            
            if move_damage_type and defender_class:
                type_effectiveness = get_type_effectiveness(move_damage_type, defender_class)
                effectiveness_label = get_effectiveness_label(type_effectiveness)
                
                if type_effectiveness != 1.0:
                    original_dmg = total_dmg
                    total_dmg = int(total_dmg * type_effectiveness)
                    print(f"[moves] Type effectiveness: {move_damage_type} vs {defender_class} = {effectiveness_label} ({type_effectiveness}x) | {original_dmg} → {total_dmg}")
                else:
                    print(f"[moves] Type effectiveness: {move_damage_type} vs {defender_class} = {effectiveness_label} ({type_effectiveness}x)")
        except Exception as e:
            print(f"⚠️ Type effectiveness calculation error: {e}")
        
        total_dmg = max(0, total_dmg)
        
        # Apply self HP cost if move has it (Blood Hunter moves)
        if mv.self_hp_cost > 0:
            a_cur, a_max = _ally_hp_tuple(gs)
            new_a_cur = max(0, a_cur - mv.self_hp_cost)
            _set_ally_hp(gs, new_a_cur, a_max)
            print(f"[moves] {mv.label} → self cost {mv.self_hp_cost} HP | ally {a_cur} → {new_a_cur}")
        
        cur, mx = _enemy_hp_tuple(gs)
        new_cur = max(0, cur - total_dmg)
        _set_enemy_hp(gs, new_cur, mx)

        print(f"[moves] {mv.label} → damage={total_dmg} | enemy {cur} → {new_cur}")
        
        # Store effectiveness info for display (always store, including 1x)
        if effectiveness_label:
            st["last_type_effectiveness"] = {
                "label": effectiveness_label,
                "multiplier": type_effectiveness,
                "color": get_effectiveness_color(type_effectiveness)
            }
        else:
            st.pop("last_type_effectiveness", None)

        if new_cur <= 0:
            # Trigger fade; wild_vessel will show KO card (from pending_result_payload) then exit.
            st["enemy_fade_active"] = True
            st["enemy_fade_t"] = 0.0

            n, s = mv.dice
            breakdown = f"{n}d{s} + {mv.ability} = {total_dmg}"
            ko_message = f"Dealt {total_dmg} ({breakdown})"
            if effectiveness_label:
                ko_message += f" [{effectiveness_label}]"
            st["pending_result_payload"] = (
                "success",
                f"{mv.label} – KO!",
                ko_message
            )

            # Flag is useful if your scene checks it before deciding what to do after fade
            st["enemy_defeated"] = True
        else:
            subtitle = f"Hit for {total_dmg}!"
            if effectiveness_label:
                subtitle += f" [{effectiveness_label}]"
            if new_cur <= 0:
                subtitle += " (Enemy down)"
            
            st["result"] = {
                "kind": "info",
                "title": mv.label,
                "subtitle": subtitle,
                "t": 0.0, "alpha": 0, "played": False,
                "exit_on_close": False,
            }

        # Start player-side animation towards enemy
        try:
            setattr(gs, "_move_anim", {'target_side': 'enemy'})
            move_anim_sys.start_move_anim(gs, mv)
        except Exception:
            pass
        _play_move_sfx(mv)
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
