# ============================================================
# items/base_items.py
# ============================================================
class Item:
    def __init__(self, name, desc, max_stack=99, category="misc"):
        self.name = name
        self.desc = desc
        self.max_stack = max_stack
        self.category = category
        self.qty = 0  # current quantity owned
