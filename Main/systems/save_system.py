# ============================================================
#  save_system.py — save/load/delete with player + spawns + party tokens
#  (+ persistent party_vessel_stats)
#  - Throttled + de-duped saves to avoid spam
#  - Optional autosave helpers: mark_save_needed / autosave_tick
# ============================================================

import os
import json
import time
import hashlib
from pygame.math import Vector2
import pygame
import settings as S

# ===================== Throttle / Dedup Guards ===============================

_LAST_SAVE_MS = 0
_MIN_SAVE_INTERVAL_MS = 2000  # rate-limit window (2s)
_LAST_SAVE_DIGEST = None
_SILENT_BURST_MS = 400        # compress log spam when many writes happen close together
_LAST_LOG_MS = 0

def _now_ms() -> int:
    """Safe 'now' even if pygame isn't fully up."""
    try:
        return pygame.time.get_ticks()
    except Exception:
        return int(time.time() * 1000)

def _maybe_log_saved(path: str):
    """Avoid printing the 💾 line every millisecond if spammed."""
    global _LAST_LOG_MS
    now = _now_ms()
    if now - _LAST_LOG_MS >= _SILENT_BURST_MS:
        print(f"💾 Saved game -> {path}")
        _LAST_LOG_MS = now


# ===================== Helpers ==============================================

def ensure_save_dir():
    if not os.path.exists(S.SAVE_DIR):
        os.makedirs(S.SAVE_DIR, exist_ok=True)

def has_save():
    return os.path.exists(S.SAVE_PATH)

def _resolve_token_path(filename: str | None) -> str | None:
    """Try to find a token image by filename across known asset dirs."""
    if not filename:
        return None
    candidates_dirs = [
        os.path.join("Assets", "Starters"),
        os.path.join("Assets", "VesselsMale"),
        os.path.join("Assets", "VesselsFemale"),
        os.path.join("Assets", "RareVessels"),
        os.path.join("Assets", "PlayableCharacters"),
    ]
    for d in candidates_dirs:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return None

def _load_token_surface(filename: str | None):
    """Load a pygame.Surface for a token filename (if found)."""
    path = _resolve_token_path(filename)
    if not path:
        return None
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception as e:
        print(f"⚠️ Failed to load token surface '{path}': {e}")
        return None

def _jsonify_stats_list(stats_list, length_fallback: int = 6):
    """
    Ensure we save a JSON-serializable list the same length as party slots.
    Accepts list[dict|None|object]; objects with `to_dict()` are converted.
    Everything else becomes None.
    """
    if not isinstance(stats_list, list):
        stats_list = [None] * length_fallback

    out = []
    for item in stats_list:
        if item is None:
            out.append(None)
        elif isinstance(item, dict):
            out.append(item)
        elif hasattr(item, "to_dict") and callable(getattr(item, "to_dict")):
            try:
                out.append(item.to_dict())
            except Exception:
                out.append(None)
        else:
            out.append(None)
    return out


# ===================== Save / Load ==========================================

def save_game(gs, *, force: bool = False):
    """
    Save key game state, player choice, spawns, party token filenames,
    and party_vessel_stats (dicts) permanently.

    Throttled: max once per _MIN_SAVE_INTERVAL_MS unless force=True.
    Deduped: skips writing/logging if the snapshot JSON is identical
    to the previous successful save.
    """
    global _LAST_SAVE_MS, _LAST_SAVE_DIGEST

    ensure_save_dir()

    # --- throttle ---
    now = _now_ms()
    if not force and (now - _LAST_SAVE_MS) < _MIN_SAVE_INTERVAL_MS:
        return False  # suppressed due to rate limit

    # ensure parallel filenames list exists
    names = getattr(gs, "party_slots_names", None)
    if names is None:
        # (fixed minor bug in original: attribute name had a stray comma)
        n = len(getattr(gs, "party_slots", [])) or 6
        names = [None] * n

    # stats list (JSON-safe list of dicts/None)
    stats_src = getattr(gs, "party_vessel_stats", None)
    stats_list = _jsonify_stats_list(stats_src, length_fallback=len(names))

    # keep lengths aligned
    if len(stats_list) < len(names):
        stats_list += [None] * (len(names) - len(stats_list))
    elif len(stats_list) > len(names):
        stats_list = stats_list[:len(names)]

    data = {
        # player & progress
        "player_y": float(getattr(gs, "player_pos", Vector2(0, 0)).y),
        "distance_travelled": float(getattr(gs, "distance_travelled", 0.0)),
        "next_event_at": float(getattr(gs, "next_event_at", 200.0)),
        "player_gender": getattr(gs, "player_gender", "male"),

        # party token filenames (NOT surfaces)
        "party_slots_names": names,

        # 🔒 persistent rolled stats (JSON dicts)
        "party_vessel_stats": stats_list,

        # spawns on map (no surfaces)
        "rivals_on_map": [
            {
                "name":  r.get("name", ""),
                "side":  r.get("side", "left"),
                "x":     float(r["pos"].x),
                "y":     float(r["pos"].y),
            }
            for r in getattr(gs, "rivals_on_map", [])
        ],
        "vessels_on_map": [
            {
                "side": v.get("side", "left"),
                "x":    float(v["pos"].x),
                "y":    float(v["pos"].y),
            }
            for v in getattr(gs, "vessels_on_map", [])
        ],

        # ✅ inventory
        "inventory": getattr(gs, "inventory", {}),
        
        # Points system
        "total_points": int(getattr(gs, "total_points", 0)),
        
        # Currency system
        "gold": int(getattr(gs, "gold", 0)),
        "silver": int(getattr(gs, "silver", 0)),
        "bronze": int(getattr(gs, "bronze", 0)),
        
        # 📚 Book of the Bound - discovered vessels (persistent across games)
        "book_of_bound_discovered": list(getattr(gs, "book_of_bound_discovered", set())),
        
        # Archives (storage for vessels when party is full)
        "archives": getattr(gs, "archives", []),
        
        # Buffs system
        "active_buffs": getattr(gs, "active_buffs", []),
        "buffs_history": getattr(gs, "buffs_history", []),
        "first_overworld_blessing_given": getattr(gs, "first_overworld_blessing_given", False),
    }

    # --- dedupe identical snapshots ---
    try:
        blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha1(blob).hexdigest()
        if _LAST_SAVE_DIGEST == digest and not force:
            return False  # nothing changed; skip write
    except Exception:
        digest = None  # fall back to writing

    # --- write ---
    try:
        with open(S.SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        _LAST_SAVE_MS = now
        if digest:
            _LAST_SAVE_DIGEST = digest
        _maybe_log_saved(S.SAVE_PATH)
        return True
    except Exception as e:
        print(f"⚠️ Save failed: {e}")
        return False


def load_game(gs, summoner_sprites: dict[str, object] | None = None):
    """
    Load saved data and restore player pos, pacing, character, spawns,
    rebuild party tokens from saved filenames, and rehydrate party stats.
    """
    try:
        with open(S.SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # player/progress
        if not hasattr(gs, "player_pos"):  # safety
            gs.player_pos = Vector2(0, 0)
        gs.player_pos.y       = float(data.get("player_y", gs.player_pos.y))
        gs.distance_travelled = float(data.get("distance_travelled", 0.0))
        gs.next_event_at      = float(data.get("next_event_at", 200.0))
        gs.player_gender      = data.get("player_gender", "male")

        # ✅ restore inventory
        inv = data.get("inventory", {})
        gs.inventory = inv if isinstance(inv, (dict, list)) else {}
        
        # ✅ restore points
        gs.total_points = int(data.get("total_points", 0))
        
        # ✅ restore currency
        gs.gold = int(data.get("gold", 0))
        gs.silver = int(data.get("silver", 0))
        gs.bronze = int(data.get("bronze", 0))
        
        # 📚 Book of the Bound - discovered vessels (persistent across games)
        discovered = data.get("book_of_bound_discovered", [])
        if not isinstance(discovered, list):
            discovered = []
        # Convert to set for efficient lookup
        gs.book_of_bound_discovered = set(discovered)
        
        # 📦 Archives - stored vessels (when party is full)
        archives_data = data.get("archives", [])
        if not isinstance(archives_data, list):
            archives_data = []
        gs.archives = archives_data
        
        # ✨ Buffs system
        active_buffs = data.get("active_buffs", [])
        if not isinstance(active_buffs, list):
            active_buffs = []
        gs.active_buffs = active_buffs
        
        buffs_history = data.get("buffs_history", [])
        if not isinstance(buffs_history, list):
            buffs_history = []
        gs.buffs_history = buffs_history
        
        # First overworld blessing flag
        gs.first_overworld_blessing_given = bool(data.get("first_overworld_blessing_given", False))

        # ----- Party tokens: rebuild surfaces from filenames -----
        names = data.get("party_slots_names", [None] * 6)
        if not isinstance(names, list):
            names = [None] * 6

        gs.party_slots_names = [None] * len(names)
        gs.party_slots = [None] * len(names)
        for i, fname in enumerate(names):
            gs.party_slots_names[i] = fname
            gs.party_slots[i] = _load_token_surface(fname) if fname else None

        # ----- Party vessel stats (JSON dicts) -----
        stats = data.get("party_vessel_stats", [None] * len(names))
        if not isinstance(stats, list):
            stats = [None] * len(names)

        target_len = max(6, len(names))
        while len(stats) < target_len:
            stats.append(None)
        stats = stats[:target_len]
        gs.party_vessel_stats = stats

        # clear dynamic lists
        if not hasattr(gs, "rivals_on_map"):
            gs.rivals_on_map = []
        else:
            gs.rivals_on_map.clear()

        if not hasattr(gs, "vessels_on_map"):
            gs.vessels_on_map = []
        else:
            gs.vessels_on_map.clear()

        # rehydrate rivals (if we have sprite mapping)
        rivals_json = data.get("rivals_on_map", [])
        for r in rivals_json:
            name = r.get("name", "")
            side = r.get("side", "left")
            x    = float(r.get("x", getattr(gs, "start_x", 0.0)))
            y    = float(r.get("y", gs.player_pos.y))

            sprite = None
            if summoner_sprites:
                sprite = summoner_sprites.get(name)

            if sprite is None:
                print(f"ℹ️ Skipping rival '{name}' (sprite not found).")
                continue

            gs.rivals_on_map.append({
                "name": name,
                "sprite": sprite,
                "pos": Vector2(x, y),
                "side": side,
            })

        # rehydrate vessel shadows
        vessels_json = data.get("vessels_on_map", [])
        for v in vessels_json:
            side = v.get("side", "left")
            x    = float(v.get("x", getattr(gs, "start_x", 0.0)))
            y    = float(v.get("y", gs.player_pos.y))
            gs.vessels_on_map.append({
                "pos": Vector2(x, y),
                "side": side,
            })

        print(
            f"📂 Loaded save from {S.SAVE_PATH} (character={gs.player_gender}, "
            f"rivals={len(gs.rivals_on_map)}, vessels={len(gs.vessels_on_map)}, "
            f"party={sum(1 for n in names if n)}, stats={sum(1 for s in gs.party_vessel_stats if s)}, "
            f"inventory_items={len(gs.inventory) if gs.inventory else 0})"
        )
        return True

    except Exception as e:
        print(f"⚠️ Load failed: {e}")
        return False


# ===================== Delete ==============================================

def delete_save():
    """Delete existing save file safely."""
    try:
        if os.path.exists(S.SAVE_PATH):
            os.remove(S.SAVE_PATH)
            print("🗑️ Deleted savegame.json")
            return True
    except Exception as e:
        print(f"⚠️ Delete failed: {e}")
    return False


# ===================== Optional Autosave Helpers ============================

def mark_save_needed(gs):
    """Flag the world dirty; pair with autosave_tick in your main loop."""
    setattr(gs, "_save_dirty", True)

def autosave_tick(gs, *, force: bool = False):
    """
    Call once per frame; persists only when dirty + not too frequent.
    Use `force=True` to bypass the throttle (e.g., on room transition).
    """
    if getattr(gs, "_save_dirty", False):
        if save_game(gs, force=force):
            setattr(gs, "_save_dirty", False)
