# ============================================================
# items/scrolls/scroll_of_command.py
# ============================================================
import os

ITEM = {
    "id": "scroll_of_command",
    "name": "Scroll of Command",
    "category": "Capture Scroll",
    "description": "A basic sealing rite. Effective on weakened foes.",
    "icon": os.path.join("Assets", "Items", "Scroll_Of_Command.png"),
    "stackable": True,
    "max_stack": 99,
    "qty": 0,
    "capture": {
        "dc_mod": 0,
        "auto_success": False,
    },
}
