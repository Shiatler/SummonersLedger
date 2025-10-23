# ============================================================
# items/scrolls/scroll_of_eternity.py
# ============================================================
import os

ITEM = {
    "id": "scroll_of_eternity",
    "name": "Scroll of Eternity",
    "category": "Capture Scroll",
    "description": "A legendary rite that binds fate itself. Never fails.",
    "icon": os.path.join("Assets", "Items", "Scroll_Of_Eternity.png"),
    "stackable": True,
    "max_stack": 99,
    "qty": 0,
    "capture": {
        "dc_mod": 0,         # ignored when auto_success=True
        "auto_success": True,
    },
}
