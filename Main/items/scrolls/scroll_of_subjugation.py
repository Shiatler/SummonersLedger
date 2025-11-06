import os

ITEM = {
    "id": "scroll_of_subjugation",
    "name": "Scroll of Subjugation",
    "category": "Capture Scroll",
    "description": "Potent runes force obedience. Strong capture power.",
    "icon": os.path.join("Assets", "Items", "Scroll_Of_Subjugation.png"),
    "stackable": True,
    "max_stack": 99,
    "qty": 0,
    "capture": {
        "dc_mod": -4,
        "auto_success": False,
    },
}
