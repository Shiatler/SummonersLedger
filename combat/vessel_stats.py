# ============================================================
# combat/vessel_stats.py — glue between asset names and stats
# Uses: 4d6 drop-lowest with class priority assignment,
#       class-based AC baselines/caps, PHB HP progression.
# ============================================================
import re
from typing import Optional, Dict, Any

from combat.stats import build_stats
from rolling.stat_rolls import roll_abilities_for_class, ability_mods_from_scores
from rolling.roller import Roller  # ✅ Roller lives here

_CLASS_RE = re.compile(
    r"""
    (?:
        ^(?:F|M)?Vessel(?P<class1>[A-Za-z]+)
      | ^R?Vessel(?P<class2>[A-Za-z]+)
      | ^Starter(?P<class3>[A-Za-z]+)
    )
    """,
    re.VERBOSE
)

def _extract_class(asset_name: str) -> Optional[str]:
    base = asset_name or ""
    base = base.split(".")[0]
    base = base.replace("_", "")
    base = re.sub(r"\d+$", "", base)

    m = _CLASS_RE.match(base)
    if not m:
        tail = re.sub(r"^.*Vessel", "", base)
        tail = re.sub(r"^Starter", "", tail)
        tail = re.sub(r"\d+$", "", tail)
        tail = tail.strip()
        return tail if tail else None

    cls = m.group("class1") or m.group("class2") or m.group("class3")
    return cls

def generate_vessel_stats_from_asset(
    asset_name: str,
    *,
    level: int = 1,
    rng: Optional[Roller] = None,
    override_primary: Optional[str] = None,
    notes: str = "Generated from asset name",
) -> Dict[str, Any]:
    """
    Build a CombatStats dict for a vessel using its asset/token name.
    - Parses class from the name.
    - Rolls class-prioritized 4d6-drop-lowest abilities.
    - Uses updated AC baselines and PHB HP progression from combat.stats.
    """
    cls = _extract_class(asset_name) or "Fighter"
    rng = rng or Roller()  # isolated RNG for stat rolling

    abilities = roll_abilities_for_class(cls, rng)  # dict STR/DEX/CON/INT/WIS/CHA

    stats = build_stats(
        name=asset_name,
        class_name=cls,
        level=level,
        abilities=abilities,
        override_primary=override_primary,
        notes=notes,
    )
    return stats.to_dict()
