# ============================================================
#  systems/asset_links.py
# ============================================================
import os

# --- prefix maps ---
PREFIX_TO_TOKEN  = (
    ("Starter", "StarterToken"),
    ("FVessel", "FToken"),
    ("MVessel", "MToken"),
    ("RVessel", "RToken"),
)
PREFIX_TO_VESSEL = tuple((t, v) for (v, t) in PREFIX_TO_TOKEN)

# --- where to search (matches your tree) ---
SEARCH_DIRS = (
    "Assets/Starters",
    "Assets/VesselsFemale",
    "Assets/VesselsMale",
    "Assets/RareVessels",
    "Assets/PlayableCharacters",  # harmless fallback
)

def _to_png(basename: str) -> str:
    return basename if basename.lower().endswith(".png") else f"{basename}.png"

def vessel_to_token(name: str | None) -> str | None:
    if not name: return None
    base = os.path.splitext(os.path.basename(name))[0]
    for v, t in PREFIX_TO_TOKEN:
        if base.startswith(v):
            base = base.replace(v, t, 1)
            break
    return _to_png(base)

def token_to_vessel(name: str | None) -> str | None:
    if not name: return None
    base = os.path.splitext(os.path.basename(name))[0]
    for t, v in PREFIX_TO_VESSEL:
        if base.startswith(t):
            base = base.replace(t, v, 1)
            break
    return _to_png(base)

def find_image(basename_or_path: str | None) -> str | None:
    """Return a full path if found anywhere in SEARCH_DIRS (or direct path)."""
    if not basename_or_path:
        return None
    if os.path.exists(basename_or_path):
        return basename_or_path
    base = os.path.basename(basename_or_path)
    for d in SEARCH_DIRS:
        p = os.path.join(d, base)
        if os.path.exists(p):
            return p
    return None
