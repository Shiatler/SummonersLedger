# ============================================================
# combat/monster_stats.py — Monster stat generation with multipliers
# Monsters are significantly stronger than normal vessels
# ============================================================
import re
from typing import Optional, Dict, Any

from combat.vessel_stats import generate_vessel_stats_from_asset
from rolling.roller import Roller

# Monster stat multipliers (applied to all stats and HP)
MONSTER_STAT_MULTIPLIERS = {
    "Dragon": 3.0,      # 200% stronger = 3x stats, 3x HP
    "Owlbear": 2.5,    # 150% stronger = 2.5x stats, 2.5x HP
    "Beholder": 2.0,   # 100% stronger = 2x stats, 2x HP
    "Golem": 1.4,      # 40% stronger = 1.4x stats, 1.4x HP
    "Ogre": 1.3,       # 30% stronger = 1.3x stats, 1.3x HP
    "Nothic": 1.3,     # 30% stronger = 1.3x stats, 1.3x HP
    "Myconid": 1.2,    # 20% stronger = 1.2x stats, 1.2x HP
    "Chestmonster": 1.75,  # 75% stronger = 1.75x stats, 1.75x HP
}

def _extract_monster_name(asset_name: str) -> Optional[str]:
    """Extract monster type from asset name (e.g., 'Dragon.png' -> 'Dragon')."""
    if not asset_name:
        return None
    
    base = asset_name.split(".")[0]  # Remove extension
    base = base.replace("_", "")
    
    # Check each monster name
    for monster_name in MONSTER_STAT_MULTIPLIERS.keys():
        if monster_name.lower() in base.lower():
            return monster_name
    
    return None

def generate_monster_stats_from_asset(
    asset_name: str,
    *,
    level: int = 1,
    rng: Optional[Roller] = None,
    notes: str = "Generated from monster asset name",
) -> Dict[str, Any]:
    """
    Build a CombatStats dict for a monster using its asset name.
    - First generates normal vessel stats
    - Then applies monster-specific multiplier to all stats and HP
    """
    # Extract monster type
    monster_type = _extract_monster_name(asset_name)
    
    if not monster_type:
        # Fallback: treat as normal vessel if not recognized as monster
        print(f"⚠️ Unknown monster type for {asset_name}, using normal vessel stats")
        return generate_vessel_stats_from_asset(asset_name, level=level, rng=rng, notes=notes)
    
    # Get multiplier
    multiplier = MONSTER_STAT_MULTIPLIERS.get(monster_type, 1.0)
    
    # Generate base stats (using monster name as class)
    # We'll use the monster name as the class name for move selection
    base_stats = generate_vessel_stats_from_asset(
        asset_name=asset_name,
        level=level,
        rng=rng,
        notes=f"{notes} (base stats before {monster_type} multiplier)",
    )
    
    # Apply multiplier to all ability scores
    ability_keys = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    for key in ability_keys:
        if key in base_stats:
            base_stats[key] = max(1, int(base_stats[key] * multiplier))
    
    # Recalculate ability modifiers after multiplier
    from rolling.stat_rolls import ability_mods_from_scores
    abilities = {key: base_stats.get(key, 10) for key in ability_keys}
    mods = ability_mods_from_scores(abilities)
    base_stats["mods"] = mods
    
    # Apply multiplier to HP (both max and current)
    if "hp" in base_stats:
        base_stats["hp"] = max(1, int(base_stats["hp"] * multiplier))
    
    if "current_hp" in base_stats:
        base_stats["current_hp"] = max(1, int(base_stats["current_hp"] * multiplier))
    else:
        # Set current_hp to max_hp if not set
        base_stats["current_hp"] = base_stats.get("hp", 10)
    
    # Update AC (it may have changed due to DEX modifier changes)
    # AC is recalculated from mods, so it should update automatically
    # But we can force a recalculation if needed
    from combat.stats import ac_for_class
    class_name = monster_type.lower()  # Use monster name as class
    base_stats["ac"] = ac_for_class(class_name, mods)
    
    # Set class_name to monster type for move selection
    base_stats["class_name"] = monster_type.lower()
    
    print(f"🐉 Generated {monster_type} stats: multiplier={multiplier}x, HP={base_stats.get('hp', 0)}, STR={base_stats.get('STR', 0)}")
    
    return base_stats

