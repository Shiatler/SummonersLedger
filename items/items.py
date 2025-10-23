# items/items.py
import importlib
import os
import pkgutil

# Collect ITEM dicts from items/scrolls/*
ITEMS = []

def _collect_from_package(pkg_name: str):
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
                ITEMS.append({"name": name, "qty": qty, "icon": icon})
        except Exception:
            # keep going even if one module fails
            pass

_collect_from_package("items.scrolls")

def items():
    """Bag loader compatibility — returns a list of {name, qty, icon}."""
    return ITEMS
