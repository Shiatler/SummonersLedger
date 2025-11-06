# ============================================================
# systems/item_categories.py — Item Category System
# ============================================================

# Category definitions
CATEGORY_HEALING = "healing"
CATEGORY_CATCHING = "catching"
CATEGORY_FOOD = "food"

# Category order for pagination
CATEGORIES = [CATEGORY_HEALING, CATEGORY_CATCHING, CATEGORY_FOOD]

# Category display names
CATEGORY_NAMES = {
    CATEGORY_HEALING: "Healing",
    CATEGORY_CATCHING: "Catching",
    CATEGORY_FOOD: "Food",
}

# Item to category mapping
ITEM_CATEGORIES = {
    # Healing scrolls
    "scroll_of_mending": CATEGORY_HEALING,
    "scroll_of_healing": CATEGORY_HEALING,
    "scroll_of_regeneration": CATEGORY_HEALING,
    "scroll_of_revivity": CATEGORY_HEALING,
    
    # Catching scrolls
    "scroll_of_command": CATEGORY_CATCHING,
    "scroll_of_sealing": CATEGORY_CATCHING,
    "scroll_of_subjugation": CATEGORY_CATCHING,
    "scroll_of_eternity": CATEGORY_CATCHING,
    
    # Food/consumables
    "rations": CATEGORY_FOOD,
    "alcohol": CATEGORY_FOOD,
}

def get_item_category(item_id: str) -> str:
    """Get the category for an item. Returns 'healing' as default."""
    return ITEM_CATEGORIES.get(item_id, CATEGORY_HEALING)

def get_category_name(category: str) -> str:
    """Get the display name for a category."""
    return CATEGORY_NAMES.get(category, category.title())

def filter_items_by_category(items: list, category: str) -> list:
    """Filter a list of items by category."""
    return [item for item in items if get_item_category(item.get("id", "")) == category]

