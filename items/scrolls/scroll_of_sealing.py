# ============================================================
# items/scrolls/scroll_of_sealing.py
# ============================================================
import os

ITEM = {
    "id": "scroll_of_sealing",
    "name": "Scroll of Sealing",
    "category": "Capture Scroll",
    "description": "Refined sigils bolster the binding. Better than Command.",
    "icon": os.path.join("Assets", "Items", "Scroll_Of_Sealing.png"),
    "stackable": True,
    "max_stack": 99,
    "qty": 0,
    "capture": {
        "dc_mod": -2,
        "auto_success": False,
    },
}
