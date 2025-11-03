# ============================================================
# items/scrolls/scroll_of_healing.py
# ============================================================
import os

ITEM = {
    "id": "scroll_of_healing",
    "name": "Scroll of Healing",
    "category": "Healing Scroll",
    "description": "Restore vitality to a battered ally with a healing touch.",
    "icon": os.path.join("Assets", "Items", "Scroll_Of_Healing.png"),  # Same icon as Scroll of Mending
    "stackable": True,
    "max_stack": 99,
    "qty": 0,  # Set via bootstrap or loot
}
