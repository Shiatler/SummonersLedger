# ============================================================
# combat/stats.py — central place for character/enemy stats
# Refactor highlights:
#   • 5e-style proficiency progression
#   • AC = class baseline + DEX (with class-specific caps/bonuses)
#   • HP scaling:
#       L1 = max hit die + CON
#       L2+ = average per level + CON
#       Milestones (default: {10}) = +1× class hit die each (no CON)
#     -> Barbarian gets +d12 at level 10; Fighter/Paladin/Ranger +d10; etc.
#   • Primary attack stat per class (+ attack bonus = prof + mod)
#   • Stable API: build_stats(...).to_dict()
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Iterable

# ------------ ability & math helpers ------------

def ability_mod(score: int) -> int:
    """5e-style modifier."""
    return (int(score) - 10) // 2

def proficiency_for_level(level: int) -> int:
    """Standard 5e progression (1–20)."""
    lvl = max(1, min(int(level), 20))
    if   lvl <= 4:  return 2
    elif lvl <= 8:  return 3
    elif lvl <= 12: return 4
    elif lvl <= 16: return 5
    else:           return 6

def _norm_class(name: str) -> str:
    """
    Normalize a class name to match our dict keys.
    Handles whitespace, hyphens/underscores, and common aliases.
    """
    raw = (name or "").strip().lower().replace("_", " ").replace("-", " ")
    aliases = {
        "bloodhunter": "blood hunter",
        "bh": "blood hunter",
        "lock": "warlock",
        "sorc": "sorcerer",
        "wiz": "wizard",
        "pally": "paladin",
        "rng": "ranger",
        "barb": "barbarian",
        "arti": "artificer",
    }
    return aliases.get(raw, raw)

def _cap(val: int, cap: Optional[int]) -> int:
    return val if cap is None else min(val, cap)

# ------------ config knobs (class identity) ------------

# Class hit dice
CLASS_HIT_DIE: Dict[str, int] = {
    "barbarian": 12,
    "fighter": 10, "paladin": 10, "ranger": 10,
    "bard": 8, "cleric": 8, "druid": 8, "monk": 8, "rogue": 8, "warlock": 8, "artificer": 8, "blood hunter": 8,
    "sorcerer": 6, "wizard": 6,
    "_default": 8,
}

# Primary attack stat per class (simplified)
PRIMARY_STAT: Dict[str, str] = {
    "barbarian": "STR",
    "bard": "CHA",
    "cleric": "WIS",
    "druid": "WIS",
    "fighter": "STR",
    "monk": "DEX",
    "paladin": "STR",
    "ranger": "DEX",
    "rogue": "DEX",
    "sorcerer": "CHA",
    "warlock": "CHA",
    "wizard": "INT",
    "artificer": "INT",
    "blood hunter": "DEX",
    "_default": "STR",
}

# Extra HP milestones: at these levels, add +1× class hit die (no CON) once.
# Default = {10} to give a noticeable mid-game bump (e.g., Barb +d12 at level 10).
HP_MILESTONES: set[int] = {10}

# Optional global scalar applied after computing HP (keep at 1.0 unless balancing).
GLOBAL_HP_MULTIPLIER: float = 1.0

# ------------ AC (gearless baselines) ------------

def ac_for_class(class_name: str, mods: Dict[str, int]) -> int:
    """Baseline AC model tuned for your game feel."""
    cls = (class_name or "").strip().lower().replace("_", " ").replace("-", " ")
    dex = int(mods.get("DEX", 0))
    con = int(mods.get("CON", 0))
    wis = int(mods.get("WIS", 0))

    if cls == "fighter":
        return 14 + dex
    if cls == "paladin":
        return 14 + _cap(dex, 2)
    if cls == "ranger":
        return 13 + dex
    if cls == "blood hunter":
        return 13 + dex
    if cls == "barbarian":
        return 12 + dex + _cap(con, 2)  # CON adds, capped
    if cls == "monk":
        return 12 + dex + _cap(wis, 2)  # WIS adds, capped
    if cls == "rogue":
        return 12 + dex
    if cls == "artificer":
        return 12 + _cap(dex, 2)
    if cls == "cleric":
        return 12 + _cap(dex, 2)
    if cls == "bard":
        return 11 + dex
    if cls == "warlock":
        return 11 + dex
    if cls == "druid":
        return 11 + _cap(dex, 2)
    if cls == "sorcerer":
        return 10 + dex
    if cls == "wizard":
        return 10 + dex
    # default (unknown class)
    return 11 + dex

# ------------ class lookups ------------

def hit_die_for_class(class_name: str) -> int:
    key = _norm_class(class_name)
    return CLASS_HIT_DIE.get(key, CLASS_HIT_DIE["_default"])

def primary_stat_for_class(class_name: str) -> str:
    key = _norm_class(class_name)
    return PRIMARY_STAT.get(key, PRIMARY_STAT["_default"])

# ------------ HP math ------------

def average_die(d: int) -> int:
    """PHB fixed average per level. d6→4, d8→5, d10→6, d12→7."""
    return (d // 2) + 1

def _count_milestones_reached(level: int, milestones: Iterable[int]) -> int:
    lvl = max(1, int(level))
    return sum(1 for m in milestones if lvl >= int(m))

def compute_hp(
    level: int,
    con_mod: int,
    class_hit_die: int,
    *,
    use_average: bool = True,
    first_level_max: bool = True,
    milestones: Optional[Iterable[int]] = None,
    hp_multiplier: float = 1.0,
) -> int:
    """
    HP formula:
      • L1: (max die or average) + CON
      • L2+: average per level + CON each level
      • Milestones: +1× class hit die (no CON) per milestone reached (once each)
      • Final multiplier (for global tuning or special buffs)
    """
    lvl = max(1, int(level))
    con = int(con_mod)
    d   = int(class_hit_die)

    # Level 1
    l1_base = d if first_level_max else average_die(d)
    hp = l1_base + con

    # Level 2+
    if lvl > 1:
        per_level = average_die(d) if use_average else average_die(d)
        hp += (per_level + con) * (lvl - 1)

    # Milestone bonuses (no CON added)
    ms = list(milestones) if milestones is not None else list(HP_MILESTONES)
    hp += _count_milestones_reached(lvl, ms) * d

    # Apply multipliers (global first, then per-call)
    total_mult = max(0.1, float(GLOBAL_HP_MULTIPLIER)) * max(0.1, float(hp_multiplier))
    hp = int(round(hp * total_mult))

    return max(1, hp)

# ------------ data model ------------

AbilityDict = Dict[str, int]  # keys: STR/DEX/CON/INT/WIS/CHA

def _mods_from_scores(abilities: AbilityDict) -> AbilityDict:
    return {k: ability_mod(v) for k, v in abilities.items()}

@dataclass
class CombatStats:
    name: str
    class_name: str
    level: int
    abilities: AbilityDict          # raw scores
    mods: AbilityDict               # computed mods
    prof: int                       # proficiency bonus
    ac: int                         # class baseline + DEX (+ caps/bonuses)
    hp: int                         # computed total
    initiative: int                 # DEX mod
    attack_stat: str                # primary stat key (e.g., "STR")
    attack_bonus: int               # prof + mod(attack_stat)
    notes: str = ""                 # freeform

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # helpers
    def mod(self, key: str) -> int:
        return int(self.mods.get(key.upper(), 0))

    def ability(self, key: str) -> int:
        return int(self.abilities.get(key.upper(), 10))

    @staticmethod
    def build(
        name: str,
        class_name: str,
        level: int,
        abilities: AbilityDict,
        *,
        override_primary: Optional[str] = None,
        use_average_hp: bool = True,
        first_level_max_hp: bool = True,
        hp_milestones: Optional[Iterable[int]] = None,
        hp_multiplier: float = 1.0,
        notes: str = "",
    ) -> "CombatStats":
        lvl = max(1, int(level))

        # normalize abilities to full 6-pack
        base: AbilityDict = {k: 10 for k in ("STR", "DEX", "CON", "INT", "WIS", "CHA")}
        base.update({k.upper(): int(v) for k, v in (abilities or {}).items()})

        mods = _mods_from_scores(base)
        prof = proficiency_for_level(lvl)

        # AC & initiative
        ac  = ac_for_class(class_name, mods)
        init = mods["DEX"]

        # HP from class die + milestones
        d = hit_die_for_class(class_name)
        hp = compute_hp(
            level=lvl,
            con_mod=mods["CON"],
            class_hit_die=d,
            use_average=use_average_hp,
            first_level_max=first_level_max_hp,
            milestones=hp_milestones,
            hp_multiplier=hp_multiplier,
        )

        # attack stat & bonus
        atk_stat = (override_primary or primary_stat_for_class(class_name)).upper()
        attack_bonus = prof + mods.get(atk_stat, 0)

        return CombatStats(
            name=name,
            class_name=class_name,
            level=lvl,
            abilities=base,
            mods=mods,
            prof=prof,
            ac=ac,
            hp=hp,
            initiative=init,
            attack_stat=atk_stat,
            attack_bonus=attack_bonus,
            notes=notes or "Stat block (scaled HP w/ milestones)",
        )

# ------------ convenience ------------

def build_stats(
    name: str,
    class_name: str,
    level: int,
    abilities: AbilityDict,
    **kwargs,
) -> CombatStats:
    """
    Pass-through for existing call sites.
    Extra kwargs supported (optional):
      - override_primary: str
      - use_average_hp: bool
      - first_level_max_hp: bool
      - hp_milestones: Iterable[int]
      - hp_multiplier: float
      - notes: str
    """
    return CombatStats.build(name, class_name, level, abilities, **kwargs)
