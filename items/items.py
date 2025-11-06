# ============================================================
# items/items.py
# ============================================================
import importlib
import os
import pkgutil
import re

# Collect ITEM dicts from items/scrolls/*
ITEMS = []

def _snake(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-zA-Z0-9_]+", "", s)
    return s.lower()

def _collect_from_package(pkg_name: str):
    global ITEMS
    try:
        pkg = importlib.import_module(pkg_name)
    except Exception:
        return
    for _, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if ispkg:
            continue
        full = f"{pkg_name}.{modname}"
        try:
            m = importlib.import_module(full)
            item = getattr(m, "ITEM", None)
            if isinstance(item, dict):
                # normalize minimal fields the bag expects
                name = str(item.get("name", modname))
                qty  = int(item.get("qty", 0))
                icon = item.get("icon")
                iid  = str(item.get("id") or _snake(name))
                cat  = str(item.get("category", ""))

                ITEMS.append({
                    "id": iid,           # ✅ include id
                    "name": name,
                    "category": cat,     # ✅ include category
                    "qty": qty,
                    "icon": icon,
                })
        except Exception:
            # keep going even if one module fails
            pass

_collect_from_package("items.scrolls")

def items():
    """Bag loader compatibility — returns list of item dicts with id, name, category, qty, icon."""
    return ITEMS
