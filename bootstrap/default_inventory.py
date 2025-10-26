# ============================================================
# bootstrap/default_inventory.py
# ------------------------------------------------------------
# Sets up the player's starting inventory on a new run.
# Works whether gs.inventory is None, dict, or list-of-dicts.
# ============================================================
import re

STARTING_ITEMS = [
    {"id": "scroll_of_command", "name": "Scroll of Command", "qty": 100},
]

def _snake_from_name(s: str) -> str:
    s = (s or "").strip().replace("’", "'")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s.lower()

def _as_dict(inv):
    """
    Convert any inventory shape to a canonical dict {id: qty}.
    Accepts:
      - None
      - dict like {"scroll_of_command": 3, ...}
      - list like [{"id": "...", "qty": 3}, {"name": "Scroll of Command", "qty": 2}, ...]
    """
    out = {}
    if not inv:
        return out

    if isinstance(inv, dict):
        for k, v in inv.items():
            try:
                out[str(k)] = int(v)
            except Exception:
                pass
        return out

    if isinstance(inv, (list, tuple)):
        for rec in inv:
            if isinstance(rec, dict):
                iid = rec.get("id")
                name = rec.get("name")
                if not iid and name:
                    iid = _snake_from_name(name)
                if not iid:
                    continue
                try:
                    q = int(rec.get("qty", 0))
                except Exception:
                    q = 0
                out[iid] = out.get(iid, 0) + q
            elif isinstance(rec, (list, tuple)) and rec:
                iid = str(rec[0])
                q = int(rec[1]) if len(rec) > 1 else 0
                out[iid] = out.get(iid, 0) + q
        return out

    return out

def add_default_inventory(gs):
    """Merge starting items into gs.inventory (stored canonically as a dict)."""
    try:
        cur = _as_dict(getattr(gs, "inventory", None))
        for it in STARTING_ITEMS:
            iid = it.get("id") or _snake_from_name(it.get("name", ""))
            qty = int(it.get("qty", 0))
            if not iid or qty <= 0:
                continue
            cur[iid] = cur.get(iid, 0) + qty

        # store canonically as dict {id: qty}
        gs.inventory = cur
    except Exception as e:
        print(f"⚠️ Could not add default inventory: {e}")
