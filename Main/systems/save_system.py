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
    """Check if save file exists."""
    return os.path.exists(S.SAVE_PATH)

def has_valid_save():
    """
    Check if save file exists AND contains actual vessel data.
    Returns True only if there's at least one vessel in party_slots_names.
    Note: We check party_slots_names because that's what the UI uses to display vessels.
    """
    if not os.path.exists(S.SAVE_PATH):
        return False
    
    try:
        with open(S.SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # CRITICAL: Check party_slots_names - this is what the UI displays
        # The UI shows vessels based on party_slots_names, so we need at least one valid name
        names = data.get("party_slots_names", [])
        if isinstance(names, list):
            valid_names = [name for name in names if name is not None and name != ""]
            if valid_names:
                # Found vessels in party_slots_names - this is a valid save
                return True
        
        # No valid vessel names found - this save has no displayable vessels
        return False
    except Exception as e:
        print(f"⚠️ Error checking valid save: {e}")
        return False

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

    When force=True: Bypasses ALL checks (throttling, dedup, starting position) and always saves.
    When force=False: Throttled and deduped to avoid spam.
    """
    global _LAST_SAVE_MS, _LAST_SAVE_DIGEST

    ensure_save_dir()

    # When force=True, bypass ALL checks and save immediately
    if force:
        # Get current state for logging
        player_name = getattr(gs, "player_name", "")
        distance = getattr(gs, "distance_travelled", 0.0)
        party_slots = getattr(gs, "party_slots_names", [])
        has_party = any(party_slots) if party_slots else False
        inventory = getattr(gs, "inventory", {})
        has_inventory = bool(inventory)
        
        # Always save when force=True - user explicitly requested it
        print(f"💾 Force saving game (player={player_name}, distance={distance:.1f}, party={has_party}, inventory={has_inventory})")
    else:
        # --- throttle (only when not forced) ---
        now = _now_ms()
        if (now - _LAST_SAVE_MS) < _MIN_SAVE_INTERVAL_MS:
            return False  # suppressed due to rate limit

    # ensure parallel filenames list exists
    names = getattr(gs, "party_slots_names", None)
    if names is None:
        # (fixed minor bug in original: attribute name had a stray comma)
        n = len(getattr(gs, "party_slots", [])) or 6
        names = [None] * n
    
    # Ensure names is a list and has exactly 6 slots
    if not isinstance(names, list):
        names = [None] * 6
    if len(names) < 6:
        names = names + [None] * (6 - len(names))
    elif len(names) > 6:
        names = names[:6]
    
    # Normalize names: ensure they're strings or None, and make a clean copy
    normalized_names = []
    for name in names:
        if name is None or name == "":
            normalized_names.append(None)
        else:
            # Ensure it's a string and normalize
            name_str = str(name).strip()
            normalized_names.append(name_str if name_str else None)
    names = normalized_names

    # stats list (JSON-safe list of dicts/None)
    stats_src = getattr(gs, "party_vessel_stats", None)
    stats_list = _jsonify_stats_list(stats_src, length_fallback=len(names))

    # keep lengths aligned
    if len(stats_list) < len(names):
        stats_list += [None] * (len(names) - len(stats_list))
    elif len(stats_list) > len(names):
        stats_list = stats_list[:len(names)]

    # Debug: Log what we're saving
    player_pos = getattr(gs, "player_pos", Vector2(0, 0))
    start_x_val = getattr(gs, "start_x", S.WORLD_W // 2)
    distance = getattr(gs, "distance_travelled", 0.0)
    
    # Only check starting position when NOT forced (autosave protection)
    if not force:
        # CRITICAL: Don't save if we're at the starting position and haven't moved
        # This prevents overwriting a good save with the starting position
        player_half_y = getattr(gs, "player_half", Vector2(0, 0)).y
        if player_half_y == 0:
            player_half_y = S.PLAYER_SIZE[1] / 2
        expected_start_y = S.WORLD_H - player_half_y - 10
        
        # If we're at starting position with no distance travelled, don't overwrite a potentially better save
        is_at_start = abs(player_pos.y - expected_start_y) < 10 and distance == 0.0
        
        if is_at_start and os.path.exists(S.SAVE_PATH):
            # Check if existing save has progress
            try:
                with open(S.SAVE_PATH, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    existing_distance = existing_data.get("distance_travelled", 0.0)
                    existing_y = existing_data.get("player_y", expected_start_y)
                    # If existing save has progress, don't overwrite with starting position
                    if existing_distance > 0.0 or abs(existing_y - expected_start_y) > 10:
                        print(f"⚠️ Skipping save: At starting position (distance=0) but existing save has progress (distance={existing_distance:.1f}, y={existing_y:.1f})")
                        return False  # Don't overwrite good save with starting position
            except Exception:
                pass  # If we can't read existing save, proceed with saving
        
        # Calculate expected starting Y position
        # Warn if saving starting position when player has moved
        if distance > 0.0:
            player_half_y = getattr(gs, "player_half", Vector2(0, 0)).y
            if player_half_y == 0:
                player_half_y = S.PLAYER_SIZE[1] / 2
            expected_start_y = S.WORLD_H - player_half_y - 10
            if abs(player_pos.y - expected_start_y) < 10:
                print(f"⚠️ WARNING: Saving starting position (Y={player_pos.y:.1f}) but distance_travelled={distance:.1f} > 0!")
                print(f"   Expected start Y: {expected_start_y:.1f}, Current Y: {player_pos.y:.1f}")
    
    if not force:
        print(f"💾 Saving position: player=({player_pos.x:.1f}, {player_pos.y:.1f}), start_x={start_x_val:.1f}, distance={distance:.1f}")
    
    data = {
        # player & progress
        "player_y": float(player_pos.y),  # Only save Y position - X is always restored from start_x
        "distance_travelled": float(getattr(gs, "distance_travelled", 0.0)),
        "next_event_at": float(getattr(gs, "next_event_at", 200.0)),
        "player_gender": getattr(gs, "player_gender", "male"),
        # NOTE: player_x and start_x are NOT saved - they're recalculated on load

        # party token filenames (NOT surfaces)
        "party_slots_names": names,  # Save normalized names directly

        # 🔒 persistent rolled stats (JSON dicts)
        "party_vessel_stats": stats_list,

        # spawns on map (no surfaces)
        "rivals_on_map": [
            {
                "name":  r.get("name", ""),
                "filename": r.get("filename", ""),  # Store original filename for sprite lookup
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
        "merchants_on_map": [
            {
                "side": m.get("side", "left"),
                "x":    float(m["pos"].x),
                "y":    float(m["pos"].y),
            }
            for m in getattr(gs, "merchants_on_map", [])
        ],
        "taverns_on_map": [
            {
                "side": t.get("side", "left"),
                "x":    float(t["pos"].x),
                "y":    float(t["pos"].y),
            }
            for t in getattr(gs, "taverns_on_map", [])
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
        
        # 🍺 Tavern state (if in tavern or paused from tavern)
        "saved_in_tavern": False,
        "tavern_state": {},
        "overworld_player_pos": None,
    }
    
    # Check if we're in tavern mode or paused from tavern
    # Store tavern state if we have it
    tavern_state = getattr(gs, "_tavern_state", None)
    pause_return_to = getattr(gs, "_pause_return_to", None)
    is_in_tavern = (pause_return_to == "TAVERN" or tavern_state is not None)
    
    if is_in_tavern and tavern_state:
        # Save tavern state (but exclude non-serializable objects like sprites)
        saved_tavern_state = {}
        for key, value in tavern_state.items():
            # Skip sprite objects and other non-serializable data
            if key in ("whore_sprite", "summoner_sprite", "barkeeper_sprite", "gambler_sprite"):
                continue  # Don't save sprites - they'll be reloaded
            if key == "overworld_player_pos" and value is not None:
                # Save overworld position separately
                data["overworld_player_pos"] = {"x": float(value.x), "y": float(value.y)}
                continue
            if key == "spawn_pos" and value is not None:
                saved_tavern_state["spawn_pos"] = {"x": float(value.x), "y": float(value.y)}
                continue
            if key == "barkeeper_pos" and value is not None:
                saved_tavern_state["barkeeper_pos"] = {"x": float(value.x), "y": float(value.y)}
                continue
            if key == "gambler_pos" and value is not None:
                saved_tavern_state["gambler_pos"] = {"x": float(value.x), "y": float(value.y)}
                continue
            if key == "whore_pos" and value is not None:
                saved_tavern_state["whore_pos"] = {"x": float(value.x), "y": float(value.y)}
                continue
            if key == "summoner_pos" and value is not None:
                saved_tavern_state["summoner_pos"] = {"x": float(value.x), "y": float(value.y)}
                continue
            if key == "camera" and value is not None:
                saved_tavern_state["camera"] = {"x": float(value.x), "y": float(value.y)}
                continue
            if key == "tavern_player_pos" and value is not None:
                saved_tavern_state["tavern_player_pos"] = {"x": float(value.x), "y": float(value.y)}
                continue
            # Save other simple values
            if isinstance(value, (str, int, float, bool, type(None))):
                saved_tavern_state[key] = value
            elif isinstance(value, list):
                # Save lists if they contain serializable data
                saved_tavern_state[key] = value
        
        # Save current player position as tavern_player_pos if not already saved
        if "tavern_player_pos" not in saved_tavern_state:
            saved_tavern_state["tavern_player_pos"] = {"x": float(player_pos.x), "y": float(player_pos.y)}
            print(f"💾 Saving current tavern player position: ({player_pos.x:.1f}, {player_pos.y:.1f})")
        
        data["saved_in_tavern"] = True
        data["tavern_state"] = saved_tavern_state
        print(f"💾 Saving tavern state: {len(saved_tavern_state)} keys")

    # --- dedupe identical snapshots (skip when forced) ---
    now = _now_ms()
    digest = None
    if not force:
        try:
            blob = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
            digest = hashlib.sha1(blob).hexdigest()
            if _LAST_SAVE_DIGEST == digest:
                return False  # nothing changed; skip write
        except Exception:
            digest = None  # fall back to writing

    # --- write ---
    try:
        with open(S.SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            # Flush to ensure data is written to disk
            f.flush()
            if hasattr(f, 'fileno'):
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass  # fsync may not be available on all platforms
        
        _LAST_SAVE_MS = now
        if digest:
            _LAST_SAVE_DIGEST = digest
        
        if force:
            print(f"💾 Force saved game to {S.SAVE_PATH}")
        else:
            _maybe_log_saved(S.SAVE_PATH)
        return True
    except Exception as e:
        print(f"⚠️ Save failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_game(gs, summoner_sprites: dict[str, object] | None = None, merchant_frames: list | None = None, tavern_sprite: object | None = None):
    """
    Load saved data and restore player pos, pacing, character, spawns,
    rebuild party tokens from saved filenames, and rehydrate party stats.
    
    Args:
        gs: GameState object
        summoner_sprites: Dict mapping summoner names to sprites
        merchant_frames: List of merchant animation frames
        tavern_sprite: Tavern sprite surface
    """
    try:
        with open(S.SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # player/progress
        if not hasattr(gs, "player_pos"):  # safety
            gs.player_pos = Vector2(0, 0)
        
        # Restore full position (both X and Y) from save file
        # Use explicit defaults to ensure we get the saved values
        saved_x = data.get("player_x")
        saved_y = data.get("player_y")
        # NOTE: start_x is NOT loaded from save - it's recalculated by start_new_game() in continue_game()
        # start_x should always be WORLD_W // 2 (center of world)
        
        # Restore player position
        # CRITICAL: Only restore Y position from save file
        # X position is NOT saved - it's always restored from start_x in continue_game()
        if saved_y is not None:
            gs.player_pos.y = float(saved_y)
            print(f"✅ Loaded player position Y: {gs.player_pos.y:.1f}, start_x: {gs.start_x:.1f}")
            print(f"   Saved values: player_y={saved_y}")
        else:
            # Fallback: keep current Y or use a default
            if gs.player_pos.y == 0:
                gs.player_pos.y = float(S.WORLD_H - 64)
            print(f"⚠️ No player_y in save, using fallback: {gs.player_pos.y}")
        
        # NOTE: player_x is NOT loaded from save - it will be restored from start_x in continue_game()
        # NOTE: start_x is NOT loaded from save - it's recalculated by start_new_game() in continue_game()
        
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

        # Ensure we have exactly 6 slots
        if len(names) < 6:
            names = names + [None] * (6 - len(names))
        elif len(names) > 6:
            names = names[:6]

        # Load party_slots_names directly (source of truth)
        gs.party_slots_names = list(names)  # Make a copy to avoid reference issues
        
        # Clear party_slots - let party_ui.py rebuild tokens from names
        # This ensures party_ui.py's tracking system works correctly
        gs.party_slots = [None] * 6
        
        # Clear party_ui.py's tracking list so it rebuilds correctly
        if hasattr(gs, "_party_slots_token_names"):
            delattr(gs, "_party_slots_token_names")
        
        # Debug: Log what we loaded
        print(f"📦 Loaded party_slots_names: {gs.party_slots_names}")

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
            # Try filename first (more reliable), then fall back to name
            filename = r.get("filename", "")
            name = r.get("name", "")
            # Use filename if available, otherwise use name
            lookup_key = filename if filename else name
            side = r.get("side", "left")
            x    = float(r.get("x", getattr(gs, "start_x", 0.0)))
            y    = float(r.get("y", gs.player_pos.y))

            sprite = None
            if summoner_sprites:
                # Try filename first, then name
                sprite = summoner_sprites.get(filename) or summoner_sprites.get(name)

            if sprite is None:
                print(f"ℹ️ Skipping rival '{lookup_key}' (sprite not found).")
                continue

            # Use saved name if available, otherwise generate a new one
            display_name = name  # Use saved name by default
            if not display_name or display_name == "":
                # Generate display name if not saved
                from systems.name_generator import generate_summoner_name
                display_name = generate_summoner_name(filename if filename else lookup_key)

            gs.rivals_on_map.append({
                "name": display_name,  # Use saved name or generated name
                "filename": filename if filename else name,  # Original filename for sprite lookup
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

        # rehydrate merchants
        if not hasattr(gs, "merchants_on_map"):
            gs.merchants_on_map = []
        else:
            gs.merchants_on_map.clear()
        
        merchants_json = data.get("merchants_on_map", [])
        for m in merchants_json:
            side = m.get("side", "left")
            x    = float(m.get("x", getattr(gs, "start_x", 0.0)))
            y    = float(m.get("y", gs.player_pos.y))
            
            if merchant_frames and len(merchant_frames) > 0:
                gs.merchants_on_map.append({
                    "frames": merchant_frames,
                    "pos": Vector2(x, y),
                    "side": side,
                    "anim_time": 0.0,
                    "frame_index": 0,
                })

        # rehydrate taverns
        if not hasattr(gs, "taverns_on_map"):
            gs.taverns_on_map = []
        else:
            gs.taverns_on_map.clear()
        
        taverns_json = data.get("taverns_on_map", [])
        for t in taverns_json:
            side = t.get("side", "left")
            x    = float(t.get("x", getattr(gs, "start_x", 0.0)))
            y    = float(t.get("y", gs.player_pos.y))
            
            if tavern_sprite:
                gs.taverns_on_map.append({
                    "sprite": tavern_sprite,
                    "pos": Vector2(x, y),
                    "side": side,
                })

        print(
            f"📂 Loaded save from {S.SAVE_PATH} (character={gs.player_gender}, "
            f"position=({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f}), "
            f"rivals={len(gs.rivals_on_map)}, vessels={len(gs.vessels_on_map)}, "
            f"merchants={len(gs.merchants_on_map)}, taverns={len(gs.taverns_on_map)}, "
            f"party={sum(1 for n in names if n)}, stats={sum(1 for s in gs.party_vessel_stats if s)}, "
            f"inventory_items={len(gs.inventory) if gs.inventory else 0})"
        )
        
        # 🍺 Load tavern state if saved in tavern
        saved_in_tavern = data.get("saved_in_tavern", False)
        if saved_in_tavern:
            tavern_state_data = data.get("tavern_state", {})
            overworld_pos_data = data.get("overworld_player_pos")
            
            # Initialize tavern state
            if not hasattr(gs, "_tavern_state"):
                gs._tavern_state = {}
            
            # Restore tavern state
            for key, value in tavern_state_data.items():
                if key.endswith("_pos") and isinstance(value, dict):
                    # Restore Vector2 positions
                    gs._tavern_state[key] = Vector2(float(value["x"]), float(value["y"]))
                elif key == "camera" and isinstance(value, dict):
                    gs._tavern_state[key] = Vector2(float(value["x"]), float(value["y"]))
                else:
                    gs._tavern_state[key] = value
            
            # Restore overworld position
            if overworld_pos_data:
                gs._tavern_state["overworld_player_pos"] = Vector2(
                    float(overworld_pos_data["x"]), 
                    float(overworld_pos_data["y"])
                )
            
            # Mark that we should restore to tavern mode
            gs._restore_to_tavern = True
            print(f"🍺 Loaded tavern state: {len(tavern_state_data)} keys, overworld_pos={overworld_pos_data}")
        else:
            # Clear tavern state if not saved in tavern
            if hasattr(gs, "_tavern_state"):
                gs._tavern_state = {}
            gs._restore_to_tavern = False
        
        return True

    except Exception as e:
        print(f"⚠️ Load failed: {e}")
        return False


# ===================== Delete ==============================================

def delete_save(gs=None, clear_book_of_bound=False):
    """
    Delete existing save file safely.
    
    Args:
        gs: Optional GameState object. If provided and clear_book_of_bound=True, will clear Book of Bound discoveries.
        clear_book_of_bound: If True, clears Book of Bound discoveries from memory. Default False (preserves discoveries).
    """
    try:
        if os.path.exists(S.SAVE_PATH):
            os.remove(S.SAVE_PATH)
            print("🗑️ Deleted savegame.json")
        
        # Clear Book of Bound discoveries from memory only if explicitly requested
        if clear_book_of_bound and gs is not None:
            if hasattr(gs, "book_of_bound_discovered"):
                gs.book_of_bound_discovered = set()
                print("🗑️ Cleared Book of Bound discoveries from memory")
        
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
