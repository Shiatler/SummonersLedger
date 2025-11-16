# ============================================================
# systems/currency.py — Currency System for Summoner Battles
# - D&D style: 10 bronze = 1 silver, 10 silver = 1 gold
# - Awards currency only for defeating summoners (not wild vessels)
# - Progressive denominations: early = bronze, late = gold
# ============================================================

from __future__ import annotations
from typing import Dict, Tuple

# --------------------- Configuration ---------------------

# Base currency reward (in bronze)
# Level 1: ~100 bronze, Level 10: ~500 bronze
BASE_BRONZE_PER_LEVEL = 50  # 50 bronze per summoner level (base)
BASE_MINIMUM = 50  # Minimum base reward even at level 1

# Difficulty bonuses (percentage multipliers)
DIFFICULTY_BONUSES = {
    "under_leveled": 0.25,   # +25% if enemy much higher than player
    "even": 0.0,              # Base if even/close
    "over_leveled": -0.25,   # -25% if player much higher than enemy
}

# Team size bonus
TEAM_SIZE_BONUS_PER_ENEMY = 20  # 20 bronze per extra enemy beyond first (reduced)


# --------------------- Currency Calculation ---------------------

def calculate_battle_currency(gs, enemy_team: Dict) -> int:
    """
    Calculate bronze currency awarded for defeating a summoner's team.
    
    Args:
        gs: GameState object
        enemy_team: Dict with 'levels' key containing list of enemy levels
    
    Returns:
        Total bronze earned
    """
    from combat.team_randomizer import highest_party_level
    player_max_level = highest_party_level(gs)
    enemy_levels = enemy_team.get("levels", [])
    
    if not enemy_levels:
        # Fallback: minimum base reward
        avg_enemy_level = player_max_level
    else:
        # Calculate average enemy level
        avg_enemy_level = int(round(sum(enemy_levels) / len(enemy_levels)))
    
    # Base calculation: 50 bronze base + 50 per level
    # This gives: Level 1 = 100, Level 10 = 550 (scaled appropriately)
    base_bronze = BASE_MINIMUM + (avg_enemy_level * BASE_BRONZE_PER_LEVEL)
    
    # Difficulty bonus based on level difference
    level_diff = avg_enemy_level - player_max_level
    if level_diff >= 5:
        difficulty_multiplier = DIFFICULTY_BONUSES["under_leveled"]  # +25%
    elif level_diff <= -5:
        difficulty_multiplier = DIFFICULTY_BONUSES["over_leveled"]    # -25%
    else:
        difficulty_multiplier = DIFFICULTY_BONUSES["even"]            # 0%
    
    difficulty_bonus = int(base_bronze * difficulty_multiplier)
    
    # Team size bonus
    team_size_bonus = max(0, (len(enemy_levels) - 1) * TEAM_SIZE_BONUS_PER_ENEMY)
    
    # Total bronze (apply hard cap)
    total_bronze = base_bronze + difficulty_bonus + team_size_bonus
    
    # Cap rewards to at most 300 bronze, never negative
    return max(0, min(300, total_bronze))


def distribute_to_denominations(total_bronze: int, player_level: int) -> Tuple[int, int, int]:
    """
    Convert total bronze to progressive denominations based on PLAYER's party level.
    This makes progression feel better - as YOU level up, you get better currency.
    
    Args:
        total_bronze: Total currency in bronze
        player_level: Highest level in player's party (for progressive distribution)
    
    Returns:
        Tuple of (gold, silver, bronze)
    """
    # Progressive currency distribution based on PLAYER's party level
    if player_level < 10:
        # Early: All bronze (keep small rewards as pure bronze)
        gold = 0
        silver = 0
        bronze = total_bronze
    
    elif player_level < 20:
        # Mid-early: Mix silver/bronze (silver is primary)
        gold = 0
        silver = total_bronze // 10
        bronze = total_bronze % 10
    
    elif player_level < 30:
        # Mid: Mix gold/silver (gold is primary)
        gold = total_bronze // 100
        remainder = total_bronze % 100
        silver = remainder // 10
        bronze = remainder % 10
    
    else:
        # Late: Mostly gold (with tiny silver/bronze for flavor)
        gold = total_bronze // 100
        remainder = total_bronze % 100
        silver = remainder // 10
        bronze = remainder % 10
    
    return (gold, silver, bronze)


def format_currency(gold: int, silver: int, bronze: int) -> str:
    """
    Format currency for display (e.g., "5 Gold Pieces, 3 Silver Pieces, 2 Bronze Pieces").
    Skips zero denominations.
    """
    parts = []
    if gold > 0:
        parts.append(f"{gold} Gold Piece{'s' if gold != 1 else ''}")
    if silver > 0:
        parts.append(f"{silver} Silver Piece{'s' if silver != 1 else ''}")
    if bronze > 0:
        parts.append(f"{bronze} Bronze Piece{'s' if bronze != 1 else ''}")
    
    if not parts:
        return "0 Bronze Pieces"
    
    return ", ".join(parts)


def award_currency(gs, enemy_team: Dict) -> Tuple[int, int, int]:
    """
    Award currency to the player and return the amounts (gold, silver, bronze).
    
    Args:
        gs: GameState object
        enemy_team: Dict with 'levels' key containing list of enemy levels
    
    Returns:
        Tuple of (gold_earned, silver_earned, bronze_earned)
    """
    # Calculate total bronze reward
    total_bronze = calculate_battle_currency(gs, enemy_team)
    
    # Get player's highest party level for progressive distribution
    # This makes it feel like YOU'RE getting better as you level up
    from combat.team_randomizer import highest_party_level
    player_level = highest_party_level(gs)
    
    # Convert to denominations based on PLAYER's level (not enemy level)
    gold_earned, silver_earned, bronze_earned = distribute_to_denominations(total_bronze, player_level)
    
    # Ensure currency fields exist
    if not hasattr(gs, "gold"):
        gs.gold = 0
    if not hasattr(gs, "silver"):
        gs.silver = 0
    if not hasattr(gs, "bronze"):
        gs.bronze = 0
    
    # Award currency (convert to bronze for storage, then convert back)
    # Actually, let's store separately for now
    gs.gold += gold_earned
    gs.silver += silver_earned
    gs.bronze += bronze_earned
    
    # Auto-convert if needed (10 bronze = 1 silver, 10 silver = 1 gold)
    if gs.bronze >= 10:
        extra_silver = gs.bronze // 10
        gs.silver += extra_silver
        gs.bronze = gs.bronze % 10
    
    if gs.silver >= 10:
        extra_gold = gs.silver // 10
        gs.gold += extra_gold
        gs.silver = gs.silver % 10
    
    return (gold_earned, silver_earned, bronze_earned)


def get_total_bronze(gs) -> int:
    """Get total currency as bronze for calculations."""
    gold = getattr(gs, "gold", 0)
    silver = getattr(gs, "silver", 0)
    bronze = getattr(gs, "bronze", 0)
    return gold * 100 + silver * 10 + bronze


def ensure_currency_fields(gs):
    """Ensure currency fields exist (called on game load/init)."""
    if not hasattr(gs, "gold"):
        gs.gold = 0
    if not hasattr(gs, "silver"):
        gs.silver = 0
    if not hasattr(gs, "bronze"):
        gs.bronze = 0

