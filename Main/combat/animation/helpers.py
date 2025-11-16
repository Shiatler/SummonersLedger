import os
import re

def class_and_level_from_move_id(move_id: str) -> tuple[str | None, int | None]:
    s = (move_id or "").lower()
    id_to_class_key = {
        "barb": "barbarian", "druid": "druid", "rogue": "rogue", "wizard": "wizard",
        "cleric": "cleric", "paladin": "paladin", "ranger": "ranger", "warlock": "warlock",
        "monk": "monk", "sorc": "sorcerer", "arti": "artificer", "bh": "bloodhunter",
        "fighter": "fighter", "bard": "bard",
        "dragon": "dragon", "owlbear": "owlbear", "beholder": "beholder",
        "golem": "golem", "ogre": "ogre", "nothic": "nothic", "myconid": "myconid",
    }
    klass = None
    for p, k in id_to_class_key.items():
        if s.startswith(p + "_") or s.startswith(p + "l") or s.startswith(p):
            klass = k
            break
    lvl = None
    m = re.search(r"_l(\d+)_", s)
    if m:
        try:
            lvl = int(m.group(1))
        except Exception:
            lvl = None
    if klass:
        parts = re.split(r"[^a-zA-Z0-9]+", klass)
        disp = "".join(p.capitalize() for p in parts if p)
    else:
        disp = None
    return disp, lvl

def anim_image_path(class_display: str | None, level: int | None) -> str | None:
    if not class_display or level is None:
        return None
    return os.path.join("Assets", "Moves", f"{class_display}{level}.png")


