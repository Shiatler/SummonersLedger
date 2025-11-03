# ============================================================
# systems/item_pricing.py — Item Pricing System
# - Prices scale with player's highest party level
# - Uses D&D currency (bronze/silver/gold)
# - Scroll of Eternity is NOT purchasable
# ============================================================

from __future__ import annotations
from typing import Dict, Tuple, Optional

# --------------------- Base Prices (in bronze, for level 1) ---------------------
# Balance: Early game win (~250-350 bronze) should afford ~1 early game item
# Items are tiered: Cheap → Medium → Expensive → Legendary (not sold)

BASE_PRICES = {
    # Tier: Cheap (basic items) - Prices designed to show mixed denominations
    "scroll_of_mending": 213,          # 1d4 + CON - 2 GP, 1 SP, 3 BP (affordable after 1 win)
    "scroll_of_healing": 437,          # 1d8 + CON - 4 GP, 3 SP, 7 BP (requires ~1.5-2 wins)
    "scroll_of_command": 265,          # DC +0 - 2 GP, 6 SP, 5 BP (affordable after 1 win)
    
    # Tier: Medium (moderate power) - ~3-6 wins at level 1
    "scroll_of_regeneration": 1527,     # 2d8 + CON - 15 GP, 2 SP, 7 BP (requires 5+ wins)
    "scroll_of_sealing": 843,          # DC -2 - 8 GP, 4 SP, 3 BP (requires 3+ wins)
    
    # Tier: Expensive (powerful items) - ~4-6 wins at level 1
    "scroll_of_revivity": 1569,         # Revive + 2d8 - 15 GP, 6 SP, 9 BP (requires 5+ wins)
    "scroll_of_subjugation": 1234,     # DC -4 - 12 GP, 3 SP, 4 BP (requires 4+ wins)
    
    # Tier: Legendary (NOT purchasable)
    # "scroll_of_eternity": None  # Auto-capture - legendary, not for sale
}

# Level scaling multiplier
# Price grows by this % per level above 1
PRICE_SCALING_PER_LEVEL = 0.20  # 20% increase per level (level 10 = +180%, level 20 = +380%)


# --------------------- Pricing Functions ---------------------

def get_item_price(item_id: str, player_level: int) -> Optional[Tuple[int, int, int]]:
    """
    Get the price of an item in (gold, silver, bronze) format.
    
    Args:
        item_id: Item identifier (e.g., "scroll_of_mending")
        player_level: Player's highest party level
    
    Returns:
        Tuple of (gold, silver, bronze) price, or None if item not purchasable
    """
    if not is_item_purchasable(item_id):
        return None
    
    base_price_bronze = BASE_PRICES.get(item_id)
    if base_price_bronze is None:
        return None
    
    # Calculate scaled price
    # Level 1: 1.0x, Level 2: 1.15x, Level 10: 2.35x, Level 20: 3.85x
    level_multiplier = 1.0 + (player_level - 1) * PRICE_SCALING_PER_LEVEL
    scaled_price_bronze = int(base_price_bronze * level_multiplier)
    
    # Convert to denominations
    gold = scaled_price_bronze // 100
    remainder = scaled_price_bronze % 100
    silver = remainder // 10
    bronze = remainder % 10
    
    return (gold, silver, bronze)


def get_item_price_bronze(item_id: str, player_level: int) -> Optional[int]:
    """
    Get the price of an item in total bronze (for calculations).
    
    Returns:
        Total bronze price, or None if not purchasable
    """
    price = get_item_price(item_id, player_level)
    if price is None:
        return None
    gold, silver, bronze = price
    return gold * 100 + silver * 10 + bronze


def is_item_purchasable(item_id: str) -> bool:
    """
    Check if an item can be purchased (Scroll of Eternity cannot).
    """
    # Scroll of Eternity is legendary and NOT purchasable
    if item_id == "scroll_of_eternity":
        return False
    
    # Check if item has a base price defined
    return item_id in BASE_PRICES


def format_price(gold: int, silver: int, bronze: int) -> str:
    """
    Format price for display (e.g., "2 Gold Pieces, 5 Silver Pieces, 3 Bronze Pieces").
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
        return "Free"
    
    return ", ".join(parts)


def can_afford_item(item_id: str, player_level: int, player_gold: int, player_silver: int, player_bronze: int) -> bool:
    """
    Check if player can afford an item.
    
    Args:
        item_id: Item identifier
        player_level: Player's highest party level
        player_gold, player_silver, player_bronze: Player's current currency
    
    Returns:
        True if player can afford the item
    """
    price = get_item_price_bronze(item_id, player_level)
    if price is None:
        return False
    
    player_total_bronze = player_gold * 100 + player_silver * 10 + player_bronze
    return player_total_bronze >= price


def get_all_purchasable_items() -> list[str]:
    """
    Get list of all purchasable item IDs.
    """
    return [item_id for item_id in BASE_PRICES.keys() if is_item_purchasable(item_id)]

