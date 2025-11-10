# ============================================================
# systems/item_pricing.py — Item Pricing System
# - Prices are fixed (no level scaling)
# - Uses D&D currency (bronze/silver/gold)
# - Scroll of Eternity is NOT purchasable
# ============================================================

from __future__ import annotations
from typing import Dict, Tuple, Optional

# --------------------- Fixed Prices (in bronze) ---------------------
# Currency conversion: 1 gp = 100 bp, 1 sp = 10 bp

# fmt: off (explicit bronze totals for readability)
BASE_PRICES = {
    "rations": 300,                 # 3 gp
    "alcohol": 200,                 # 2 gp
    "scroll_of_command": 53,        # 5 sp, 3 bp
    "scroll_of_sealing": 270,       # 2 gp, 7 sp
    "scroll_of_subjugation": 893,   # 8 gp, 9 sp, 3 bp
    "scroll_of_mending": 49,        # 4 sp, 9 bp
    "scroll_of_healing": 230,       # 2 gp, 3 sp
    "scroll_of_regeneration": 600,  # 6 gp
    "scroll_of_revivity": 650,      # 6 gp, 5 sp
    # "scroll_of_eternity": None  # Legendary, not for sale
}
# fmt: on


# --------------------- Pricing Functions ---------------------

def get_item_price(item_id: str, player_level: int) -> Optional[Tuple[int, int, int]]:
    """
    Get the price of an item in (gold, silver, bronze) format.
    
    Args:
        item_id: Item identifier (e.g., "scroll_of_mending", "rations", "alcohol")
        player_level: Player's highest party level (ignored; kept for API compatibility)
    
    Returns:
        Tuple of (gold, silver, bronze) price, or None if item not purchasable
    """
    if not is_item_purchasable(item_id):
        return None
    
    price_bronze = BASE_PRICES.get(item_id)
    if price_bronze is None:
        return None

    gold = price_bronze // 100
    remainder = price_bronze % 100
    silver = remainder // 10
    bronze = remainder % 10

    return (gold, silver, bronze)


def get_item_price_bronze(item_id: str, player_level: int) -> Optional[int]:
    """
    Get the price of an item in total bronze (for calculations).
    
    Returns:
        Total bronze price, or None if not purchasable
    """
    price_bronze = BASE_PRICES.get(item_id)
    if price_bronze is None:
        return None
    return price_bronze


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

