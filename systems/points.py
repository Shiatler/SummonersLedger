# ============================================================
# systems/points.py — Point System for Summoner Battles
# - Awards points only for defeating summoners (not wild vessels)
# - Scales based on enemy difficulty relative to player level
# - Numbers in 100s-1000s range for satisfying feedback
# ============================================================

from __future__ import annotations
from typing import Dict, List, Optional

# --------------------- Configuration ---------------------

BASE_POINTS = 500              # Base reward per summoner victory
LEVEL_MULTIPLIER = 50          # Points per average enemy level
TEAM_SIZE_BONUS = 100          # Per additional enemy beyond the first

# Difficulty tier multipliers (percentage bonuses on base + level points)
DIFFICULTY_TIERS = {
    "common": 0.0,        # Enemy level ≤ player level (no bonus)
    "uncommon": 0.25,     # Enemy level = player +1 to +2
    "rare": 0.50,         # Enemy level = player +3 to +4
    "very_rare": 1.0,     # Enemy level = player +5 to +6
    "ultra_rare": 2.0,    # Enemy level ≥ player +7
}

# --------------------- Point Calculation ---------------------

def calculate_battle_points(gs, enemy_team: Dict) -> int:
    """
    Calculate points awarded for defeating a summoner's team.
    
    Args:
        gs: GameState object
        enemy_team: Dict with 'levels' key containing list of enemy levels
    
    Returns:
        Total points earned (always ≥ BASE_POINTS)
    """
    from combat.team_randomizer import highest_party_level
    player_max_level = highest_party_level(gs)
    enemy_levels = enemy_team.get("levels", [])
    
    if not enemy_levels:
        # Fallback: minimum base reward
        return BASE_POINTS
    
    # Calculate average enemy level
    avg_enemy_level = sum(enemy_levels) / len(enemy_levels)
    avg_enemy_level = int(round(avg_enemy_level))
    
    # Base calculation
    base = BASE_POINTS
    level_points = avg_enemy_level * LEVEL_MULTIPLIER
    
    # Determine difficulty tier based on level difference
    level_diff = avg_enemy_level - player_max_level
    if level_diff <= 0:
        tier_multiplier = DIFFICULTY_TIERS["common"]
    elif level_diff <= 2:
        tier_multiplier = DIFFICULTY_TIERS["uncommon"]
    elif level_diff <= 4:
        tier_multiplier = DIFFICULTY_TIERS["rare"]
    elif level_diff <= 6:
        tier_multiplier = DIFFICULTY_TIERS["very_rare"]
    else:
        tier_multiplier = DIFFICULTY_TIERS["ultra_rare"]
    
    # Difficulty bonus (percentage of base + level)
    difficulty_bonus = int((base + level_points) * tier_multiplier)
    
    # Team size bonus (100 per additional enemy beyond first)
    team_size_bonus = max(0, (len(enemy_levels) - 1) * TEAM_SIZE_BONUS)
    
    # Total calculation
    total = base + level_points + difficulty_bonus + team_size_bonus
    
    return max(BASE_POINTS, total)  # Ensure minimum reward


def get_points_tier_name(level_diff: int) -> str:
    """Get the human-readable tier name for display."""
    if level_diff <= 0:
        return "Common"
    elif level_diff <= 2:
        return "Uncommon"
    elif level_diff <= 4:
        return "Rare"
    elif level_diff <= 6:
        return "Very Rare"
    else:
        return "Ultra Rare"


def award_points(gs, enemy_team: Dict) -> int:
    """
    Award points to the player and return the amount awarded.
    Stores points in gs.total_points (creating if needed).
    """
    points = calculate_battle_points(gs, enemy_team)
    
    # Initialize total_points if it doesn't exist
    if not hasattr(gs, "total_points"):
        gs.total_points = 0
    
    # Award points
    gs.total_points = int(getattr(gs, "total_points", 0)) + points
    
    return points


def get_total_points(gs) -> int:
    """Get the player's current total points."""
    return int(getattr(gs, "total_points", 0))


# --------------------- Save/Load Integration ---------------------

def ensure_points_field(gs):
    """Ensure gs.total_points exists (called on game load/init)."""
    if not hasattr(gs, "total_points"):
        gs.total_points = 0

