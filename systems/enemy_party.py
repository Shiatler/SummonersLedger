# ============================================================
# systems/enemy_party.py
# Simple enemy team generator (easy-leaning, duplicates OK)
# - Scans vessel asset folders and builds a catalog of exact basenames
#   (keeps gender + index, e.g. MVesselWizard2, FVesselRogue1)
# - Picks N based on player's highest level
# - Generates stats via combat.vessel_stats.generate_vessel_stats_from_asset
# - Returns entries ready for UIs:
#     { 'vessel_png': 'FVesselWizard2.png', 'level': L, 'stats': {...} }
# ============================================================
from __future__ import annotations
import os, glob, re, random
from typing import List, Dict, Any, Optional

import settings as S
from combat.vessel_stats import generate_vessel_stats_from_asset

# ------------------------------ Catalog scan ------------------------------
def _scan_vessel_basenames() -> List[str]:
    """
    Return exact *.png basenames across Female/Male/Rare dirs that start with
    [M|F|R]Vessel*. This preserves M/F and numeric variants (…1, …2, …3, …).
    """
    dirs = [
        getattr(S, "ASSETS_VESSELS_FEMALE_DIR", os.path.join("Assets", "VesselsFemale")),
        getattr(S, "ASSETS_VESSELS_MALE_DIR",   os.path.join("Assets", "VesselsMale")),
        getattr(S, "ASSETS_VESSELS_RARE_DIR",   os.path.join("Assets", "RareVessels")),
    ]
    seen, out = set(), []
    for d in dirs:
        try:
            for path in glob.glob(os.path.join(d, "*.png")):
                base = os.path.splitext(os.path.basename(path))[0]
                if not re.match(r"^[MFR]Vessel", base, flags=re.IGNORECASE):
                    continue  # drop Token and anything else
                if base not in seen:
                    seen.add(base)
                    out.append(base)
        except Exception:
            pass

    # Fallback if nothing is found (shouldn't normally happen)
    if not out:
        out = [
            "FVesselFighter1", "FVesselRogue1", "FVesselCleric1", "FVesselWizard1",
            "MVesselFighter1", "MVesselRogue1", "MVesselCleric1", "MVesselWizard1",
            "RVesselFighter1", "RVesselDruid1", "RVesselSorcerer1", "RVesselWizard1",
        ]
    return out

# ------------------------------ Difficulty knobs ------------------------------
def _enemy_count_for_player_level(player_lvl: int, rng: random.Random) -> int:
    L = max(1, int(player_lvl))
    if L <= 10:  return 2 if rng.random() < 0.10 else 1
    if L <= 20:  return 2
    if L <= 30:  return 3
    if L <= 40:  return 4
    return 5

def _level_for_enemy(player_lvl: int, rng: random.Random, bracket: str) -> int:
    L = max(1, int(player_lvl))
    if bracket == "L1-10":   choices = [-2, -1, -1, 0]
    elif bracket == "L11-20":choices = [-1, -1, 0, +1]
    elif bracket == "L21-30":choices = [-1, 0, +1]
    elif bracket == "L31-40":choices = [0, +1, +2]
    else:                    choices = [0, +1, +2, +3]
    return max(1, min(50, L + rng.choice(choices)))

def _bracket_for_level(player_lvl: int) -> str:
    L = max(1, int(player_lvl))
    if L <= 10:  return "L1-10"
    if L <= 20:  return "L11-20"
    if L <= 30:  return "L21-30"
    if L <= 40:  return "L31-40"
    return "L41+"

# ------------------------------ Public helpers ------------------------------
def highest_player_level(gs) -> int:
    try:
        stats = getattr(gs, "party_vessel_stats", None) or []
        hi = 1
        for st in stats:
            if isinstance(st, dict):
                try:
                    hi = max(hi, int(st.get("level", 1)))
                except Exception:
                    pass
        return max(1, int(hi))
    except Exception:
        return 1

def generate_enemy_party(gs,
                         *,
                         rng: Optional[random.Random] = None,
                         max_party: int = 6) -> List[Dict[str, Any]]:
    """
    Build an enemy party list with exact asset matches (M/F + index preserved).
    Each entry:
      {
        'vessel_png': 'FVesselFighter2.png',
        'level': lvl,
        'stats': {...}
      }
    """
    rng = rng or random.Random()
    catalog = _scan_vessel_basenames()
    if not catalog:
        return []

    rng.shuffle(catalog)  # small randomness in picks
    player_hi = highest_player_level(gs)
    bracket = _bracket_for_level(player_hi)
    count = min(max_party, _enemy_count_for_player_level(player_hi, rng))

    # Rare inclusion chance (small, only once)
    want_rare = (player_hi >= 15) and (rng.random() < 0.15)
    rares   = [n for n in catalog if n.startswith("RVessel")]
    commons = [n for n in catalog if not n.startswith("RVessel")]

    party: List[Dict[str, Any]] = []

    for i in range(count):
        pool = commons
        if want_rare and rares:
            pool = rares if i == 0 else commons

        name = rng.choice(pool) if pool else rng.choice(catalog)   # e.g., 'FVesselWizard2'
        lvl  = _level_for_enemy(player_hi, rng, bracket)

        # Generate stats using the exact asset basename so class parsing matches wild flow
        stats = generate_vessel_stats_from_asset(name, level=lvl)
        stats["vs_level"] = int(player_hi)  # used by XP system

        party.append({
            "vessel_png": name if name.lower().endswith(".png") else f"{name}.png",
            "level": lvl,
            "stats": stats,
        })

    return party
