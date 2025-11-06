# ============================================================
# items/scrolls/scroll_of_mending.py
# ============================================================
import os
ITEM = {
    "id": "scroll_of_mending",
    "name": "Scroll of Mending",
    "category": "Healing Scroll",
    "description": "Restore vitality to a battered ally.",
    "icon": os.path.join("Assets", "Items", "Scroll_Of_Mending.png"),
    "stackable": True,
    "max_stack": 99,
    "qty": 0,  # set via bootstrap or loot
}
