# ============================================================
# combat/type_chart.py — D&D Damage Type Effectiveness System
# Pokemon-style type chart with 2x, 1x, 0.5x multipliers
# ============================================================

from typing import Dict, List, Optional

# ===================== Damage Type Constants =====================
PIERCING = "Piercing"
BLUDGEONING = "Bludgeoning"
SLASHING = "Slashing"
PSYCHIC = "Psychic"
RADIANT = "Radiant"
NECROTIC = "Necrotic"
LIGHTNING = "Lightning"
FIRE = "Fire"

ALL_DAMAGE_TYPES = [
    PIERCING, BLUDGEONING, SLASHING, PSYCHIC,
    RADIANT, NECROTIC, LIGHTNING, FIRE
]

# ===================== Class Type Chart =====================
# Format: {
#   "class_name": {
#       "deals": damage_type,
#       "weak_to": [damage_types...],  # 2x damage
#       "resists": [damage_types...],   # 0.5x damage
#   }
# }

CLASS_TYPE_CHART: Dict[str, Dict[str, List[str]]] = {
    "druid": {
        "deals": PIERCING,
        "weak_to": [BLUDGEONING, FIRE],
        "resists": [LIGHTNING, PIERCING],
    },
    "barbarian": {
        "deals": BLUDGEONING,
        "weak_to": [SLASHING, PSYCHIC],
        "resists": [FIRE, BLUDGEONING],
    },
    "rogue": {
        "deals": SLASHING,
        "weak_to": [PIERCING, RADIANT],
        "resists": [PSYCHIC, SLASHING],
    },
    "bard": {
        "deals": PSYCHIC,
        "weak_to": [NECROTIC, BLUDGEONING],
        "resists": [RADIANT, PSYCHIC],
    },
    "cleric": {
        "deals": RADIANT,
        "weak_to": [NECROTIC, PSYCHIC],
        "resists": [RADIANT, PIERCING],
    },
    "fighter": {
        "deals": SLASHING,
        "weak_to": [LIGHTNING, PSYCHIC],
        "resists": [PIERCING, BLUDGEONING],
    },
    "monk": {
        "deals": BLUDGEONING,
        "weak_to": [RADIANT, FIRE],
        "resists": [PIERCING, PSYCHIC],
    },
    "paladin": {
        "deals": RADIANT,
        "weak_to": [NECROTIC, SLASHING],
        "resists": [RADIANT, BLUDGEONING],
    },
    "ranger": {
        "deals": PIERCING,
        "weak_to": [FIRE, NECROTIC],
        "resists": [LIGHTNING, PIERCING],
    },
    "sorcerer": {
        "deals": LIGHTNING,
        "weak_to": [PIERCING, BLUDGEONING],
        "resists": [FIRE, LIGHTNING],
    },
    "warlock": {
        "deals": NECROTIC,
        "weak_to": [RADIANT, FIRE],
        "resists": [PSYCHIC, NECROTIC],
    },
    "wizard": {
        "deals": FIRE,
        "weak_to": [PIERCING, SLASHING],
        "resists": [PSYCHIC, FIRE],
    },
    "artificer": {
        "deals": LIGHTNING,
        "weak_to": [FIRE, NECROTIC],
        "resists": [BLUDGEONING, LIGHTNING],
    },
    "bloodhunter": {
        "deals": NECROTIC,
        "weak_to": [RADIANT, SLASHING],
        "resists": [FIRE, NECROTIC],
    },
}

# ===================== Helper Functions =====================

def normalize_class_name(class_name: str) -> Optional[str]:
    """
    Normalize class name to lowercase for lookup.
    Strips common prefixes like RToken, FToken, MToken, RVessel, etc.
    Returns None if class not found in chart.
    """
    if not class_name:
        return None
    
    # Strip common prefixes (order matters - check longer prefixes first)
    prefixes = ["rtoken", "ftoken", "mtoken", "rvessel", "fvessel", "mvessel", "starter"]
    cleaned = class_name.lower().strip()
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break
    
    # Handle variations and aliases
    aliases = {
        "blood hunter": "bloodhunter",
        "bloodhunter": "bloodhunter",
    }
    
    normalized = aliases.get(cleaned, cleaned)
    
    if normalized in CLASS_TYPE_CHART:
        return normalized
    
    return None


def get_class_damage_type(class_name: str) -> Optional[str]:
    """
    Get the damage type that a class deals.
    Returns None if class not found.
    """
    normalized = normalize_class_name(class_name)
    if normalized is None:
        return None
    
    return CLASS_TYPE_CHART[normalized]["deals"]


def get_class_weaknesses(class_name: str) -> List[str]:
    """
    Get list of damage types that deal 2x damage to this class.
    Returns empty list if class not found.
    """
    normalized = normalize_class_name(class_name)
    if normalized is None:
        return []
    
    return CLASS_TYPE_CHART[normalized]["weak_to"].copy()


def get_class_resistances(class_name: str) -> List[str]:
    """
    Get list of damage types that deal 0.5x damage to this class.
    Returns empty list if class not found.
    """
    normalized = normalize_class_name(class_name)
    if normalized is None:
        return []
    
    return CLASS_TYPE_CHART[normalized]["resists"].copy()


def get_type_effectiveness(attacker_damage_type: str, defender_class: str) -> float:
    """
    Calculate type effectiveness multiplier.
    
    Args:
        attacker_damage_type: The damage type being dealt (e.g., "Piercing")
        defender_class: The class of the defender (e.g., "Barbarian")
    
    Returns:
        float: 2.0 (super effective), 1.0 (normal), or 0.5 (not very effective)
    """
    if not attacker_damage_type or not defender_class:
        return 1.0
    
    normalized_class = normalize_class_name(defender_class)
    if normalized_class is None:
        return 1.0
    
    class_data = CLASS_TYPE_CHART[normalized_class]
    
    # Check weaknesses (2x damage)
    if attacker_damage_type in class_data["weak_to"]:
        return 2.0
    
    # Check resistances (0.5x damage)
    if attacker_damage_type in class_data["resists"]:
        return 0.5
    
    # Normal effectiveness (1x)
    return 1.0


def get_effectiveness_label(multiplier: float) -> str:
    """
    Get human-readable label for effectiveness multiplier.
    
    Returns:
        str: "2x", "1x", or "0.5x"
    """
    if multiplier >= 1.9:  # Account for floating point
        return "2x"
    elif multiplier <= 0.6:
        return "0.5x"
    else:
        return "1x"


def get_effectiveness_color(multiplier: float) -> tuple:
    """
    Get color for effectiveness indicator.
    
    Returns:
        tuple: RGB color tuple
        - (100, 255, 100) for super effective (2x) - green
        - (0, 0, 0) for normal (1x) - black
        - (255, 100, 100) for resisted (0.5x) - red
    """
    if multiplier >= 1.9:
        return (100, 255, 100)  # Green for super effective (2x)
    elif multiplier <= 0.6:
        return (255, 100, 100)  # Red for resisted (0.5x)
    else:
        return (0, 0, 0)  # Black for normal (1x)

