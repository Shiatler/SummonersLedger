# ============================================================
#  combat/wild_vessel.py — compact vessel encounter scene
#  Flow: enemy swirl -> dice popup -> (success) fade + caught SFX -> result card
#  Also hosts immediate damage from moves via combat.moves
#
#  Improvements in this refactor:
#   • Dice popup remains modal (always consumes input first)
#   • Enemy AI "thinking" buffer set to 500 ms
#   • Ally KO detection -> forces Party popup, locks other inputs until a living swap
#   • If no living vessels remain -> defeat card -> exit
#   • Clearer separation of concerns & helper functions
#   • ✅ XP integration: queue XP on capture/defeat, show XP card after result
# ============================================================
from __future__ import annotations

import os
import re
import random
import glob
import pygame

import settings as S
from systems import audio as audio_sys
from systems import xp as xp_sys  # ✅ XP system

from combat.vessel_stats import generate_vessel_stats_from_asset
from rolling.roller import set_roll_callback, Roller as StatRoller
from rolling import ui as roll_ui

from combat.btn import run_action
from combat.btn import bag_action, battle_action, party_action
from combat.capturing import CaptureContext, attempt_capture
from systems.asset_links import vessel_to_token
from combat import moves
from combat import turn_order
from combat import enemy_ai
from screens import party_manager

# ---------------- Tunables ----------------
FADE_SECONDS   = 0.8
SUMMON_TIME    = 0.60
ALLY_OFFSET    = (290, -140)
ENEMY_OFFSET   = (-400, 220)
ALLY_SCALE     = 1.0
ENEMY_SCALE    = 0.7
SWIRL_DURATION = 2.0
SWIRL_VIS_FPS  = 60

ENEMY_FADE_SEC   = 0.60
RESULT_FADE_MS   = 220
RESULT_CARD_W    = 540
RESULT_CARD_H    = 220

CAPTURE_OK_SFX   = os.path.join("Assets", "Music", "Sounds", "CaptureSuccess.mp3")
CAPTURE_FAIL_SFX = os.path.join("Assets", "Music", "Sounds", "CaptureFail.mp3")
CAUGHT_SFX       = os.path.join("Assets", "Music", "Sounds", "Caught.mp3")
TELEPORT_SFX     = os.path.join("Assets", "Music", "Sounds", "Teleport.mp3")

# --- Turn phases ---
PHASE_PLAYER   = "PLAYER_TURN"    # Player can choose (battle/bag/party/run)
PHASE_RESOLVE  = "RESOLVING"      # Player move is resolving (animations/dmg/etc.)
PHASE_ENEMY    = "ENEMY_TURN"     # Enemy waits 'thinking' buffer then acts

# ---------------- HP parsing (robust) ----------------
import re as _re

def _safe_int(v, default=0) -> int:
    try:
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip()
        if not s:
            return int(default)
        m = _re.match(r"^\s*(\d+)\s*/\s*\d+\s*$", s)
        if m: return int(m.group(1))
        m = _re.match(r"^\s*(\d+)\s*(?:of|OF)\s*\d+\s*$", s)
        if m: return int(m.group(1))
        m = _re.search(r"(\d+)\s*(?:→|->)\s*(\d+)\s*$", s)
        if m: return int(m.group(2))
        return int(float(s))
    except Exception:
        return int(default)

def _parse_enemy_hp_fields(estats: dict) -> tuple[int, int]:
    max_hp = max(1, _safe_int(estats.get("hp", 10), 10))
    if "current_hp" in estats:
        cur_hp = _safe_int(estats.get("current_hp"), max_hp)
    else:
        ratio = estats.get("_hp_ratio_fallback", 1.0)
        try: r = float(ratio)
        except Exception: r = 1.0
        cur_hp = int(round(max(0.0, min(1.0, r)) * max_hp))
    cur_hp = max(0, min(cur_hp, max_hp))
    return cur_hp, max_hp

# ---------------- Active party helpers ----------------
def _first_filled_slot_index(gs) -> int:
    names = getattr(gs, "party_slots_names", None) or [None]*6
    for i, n in enumerate(names):
        if n: return i
    return 0

def _battle_start_slot(gs) -> int:
    """Respect party_active_idx if set; otherwise prefer slot 0; if it's empty, fall back to first filled slot."""
    names = getattr(gs, "party_slots_names", None) or [None]*6
    
    # First, check if party_active_idx is set and valid
    active_idx = getattr(gs, "party_active_idx", None)
    if active_idx is not None and isinstance(active_idx, int):
        if 0 <= active_idx < len(names) and names[active_idx]:
            return active_idx
    
    # Fall back to slot 0 if it has a vessel
    if names and names[0]:
        return 0
    
    # Finally, fall back to first filled slot
    return _first_filled_slot_index(gs)

def _ensure_active_slot(gs):
    # Set combat active slot (respects party_active_idx, falls back to slot 0 or first filled)
    if not hasattr(gs, "combat_active_idx"):
        gs.combat_active_idx = _battle_start_slot(gs)

def _consume_pending_party_switch(gs):
    idx = getattr(gs, "_pending_party_switch", None)
    if isinstance(idx, int):
        names = getattr(gs, "party_slots_names", None) or [None]*6
        if 0 <= idx < len(names) and names[idx]:
            gs.combat_active_idx = idx
        try: delattr(gs, "_pending_party_switch")
        except Exception: pass

def _get_active_party_index(gs) -> int:
    _ensure_active_slot(gs)
    _consume_pending_party_switch(gs)
    return getattr(gs, "combat_active_idx", 0)

#----------------- Helper
def _dismiss_result(st: dict, *, allow_exit: bool = True):
    """Safely close current result card."""
    res = st.get("result")
    if not res:
        return
    exit_on_close = bool(res.get("exit_on_close")) if allow_exit else False
    title = res.get("title", "Unknown")
    st["result"] = None
    if exit_on_close:
        st["pending_exit"] = True

#----------------- Helper ---------------------
def _auto_dismiss_result_if_ready(st: dict):
    """Close result screen if it has auto_ms and has finished fading/timing."""
    res = st.get("result")
    if not res:
        return
    auto_ms = res.get("auto_ms", 0)
    
    # CRITICAL PROTECTION: Never auto-dismiss Echo Infusion or manual-dismiss screens
    is_echo_infusion = res.get("is_echo_infusion", False)
    must_manual_dismiss = res.get("_must_manual_dismiss", False)
    if is_echo_infusion or must_manual_dismiss:
        # Force it to stay as manual-dismiss screen - ABSOLUTELY NEVER auto-dismiss
        res["auto_ms"] = 0
        res["auto_ready"] = False
        # Double-check: even if auto_ready was somehow set, force it back
        if res.get("auto_ready", False):
            res["auto_ready"] = False
        return  # NEVER auto-dismiss these screens - return immediately
    
    # CRITICAL: Only auto-dismiss if auto_ms > 0 AND auto_ready is True
    # If auto_ms == 0 (or any falsy value), NEVER auto-dismiss - requires manual dismissal
    if auto_ms > 0 and res.get("auto_ready", False):
        exit_on_close = bool(res.get("exit_on_close"))
        title = res.get("title", "Unknown")
        st["result"] = None
        print(f"🔔 Auto-dismissing result screen: {title} (auto_ms={auto_ms})")
        if exit_on_close:
            st["pending_exit"] = True
    elif auto_ms == 0:
        # Explicitly ensure auto_ready is False for manual-dismiss screens
        res["auto_ready"] = False

# ---------------- SFX helpers ----------------
def _load_sfx(path: str):
    try:
        if not path or not os.path.exists(path):
            return None
        return pygame.mixer.Sound(path)
    except Exception as e:
        print(f"⚠️ SFX load fail {path}: {e}")
        return None

# ---------------- Asset helpers ----------------
def _try_load(path: str | None):
    if path and os.path.exists(path):
        try: return pygame.image.load(path).convert_alpha()
        except Exception as e: print(f"⚠️ load fail {path}: {e}")
    return None

def _smooth_scale(surf: pygame.Surface | None, scale: float) -> pygame.Surface | None:
    if surf is None or abs(scale - 1.0) < 1e-6: return surf
    w, h = surf.get_width(), surf.get_height()
    return pygame.transform.smoothscale(surf, (max(1, int(w*scale)), max(1, int(h*scale))))

def _smooth_scale_to_height(surf: pygame.Surface | None, target_h: int) -> pygame.Surface | None:
    """Scale sprite to target height while maintaining aspect ratio (like summoner_battle.py)."""
    if surf is None:
        return None
    w, h = surf.get_width(), surf.get_height()
    if h <= 0:
        return surf
    s = target_h / h
    return pygame.transform.smoothscale(surf, (max(1, int(w*s)), max(1, int(h*s))))

def _pretty_name_from_token(fname: str | None) -> str:
    """Get display name for a vessel (uses name generator)."""
    if not fname:
        return "Ally"
    from systems.name_generator import generate_vessel_name
    return generate_vessel_name(fname)

def _ally_sprite_from_token_name(fname: str | None):
    if not fname: return None
    # Check for monster tokens first (TokenDragon, TokenBeholder, etc.)
    if fname.startswith("Token"):
        # Remove "Token" prefix and file extension
        base_name = os.path.splitext(fname)[0]  # Remove .png extension if present
        monster_name = base_name[5:] if len(base_name) > 5 else base_name  # Remove "Token" prefix
        # Check if it's a known monster
        monster_names = ["Beholder", "Dragon", "Golem", "Myconid", "Nothic", "Ogre", "Owlbear"]
        if any(monster_name.startswith(m) for m in monster_names):
            # Load from VesselMonsters folder
            monster_path = os.path.join("Assets", "VesselMonsters", f"{monster_name}.png")
            print(f"🐉 Loading monster ally sprite from: {monster_path} (token: {fname}, name: {monster_name})")
            monster_img = _try_load(monster_path)
            if monster_img:
                print(f"✅ Successfully loaded monster sprite: {monster_name} ({monster_img.get_width()}x{monster_img.get_height()})")
                return monster_img
            else:
                print(f"⚠️ Failed to load monster sprite from: {monster_path}")
    if fname.startswith("StarterToken"):
        return _try_load(os.path.join("Assets", "Starters", fname.replace("Token", "")))
    if fname.startswith(("FToken", "MToken")):
        gender = "VesselsFemale" if fname[0] == "F" else "VesselsMale"
        return _try_load(os.path.join("Assets", gender, fname.replace("Token", "Vessel")))
    if fname.startswith("RToken"):
        body = os.path.splitext(fname)[0].removeprefix("RToken")
        for p in (
            os.path.join("Assets", "RareVessels", f"RVessel{body}.png"),
            os.path.join("Assets", "RareVessels",
                         f"RVessel{re.match(r'([A-Za-z]+)', body).group(1)}.png")
            if re.match(r'([A-Za-z]+)', body) else None
        ):
            img = _try_load(p)
            if img: return img
    for d in ("Starters", "VesselsMale", "VesselsFemale", "RareVessels", "PlayableCharacters"):
        img = _try_load(os.path.join("Assets", d, fname))
        if img: return img
    return None

def _enemy_sprite_from_name(name: str | None):
    if not name: return None
    # Check VesselMonsters first (monsters)
    monster_img = _try_load(os.path.join("Assets", "VesselMonsters", f"{name}.png"))
    if monster_img: return monster_img
    # Then check regular vessel folders
    for d in ("VesselsMale", "VesselsFemale", "RareVessels"):
        img = _try_load(os.path.join("Assets", d, f"{name}.png"))
        if img: return img
    if name and name.startswith("RVessel"):
        m = re.match(r"(RVessel[A-Za-z]+)", name)
        if m:
            img = _try_load(os.path.join("Assets", "RareVessels", f"{m.group(1)}.png"))
            if img: return img
    return None

def _load_swirl_frames():
    base = os.path.join("Assets", "Animations")
    frames: list[pygame.Surface] = []
    def _load_sorted_by_trailing_num(paths):
        def key(p):
            m = re.search(r"(\d+)(?!.*\d)", os.path.basename(p))
            return (int(m.group(1)) if m else -1, p.lower())
        for p in sorted(set(paths), key=key):
            try: frames.append(pygame.image.load(p).convert_alpha())
            except Exception as e: print(f"⚠️ VFX load fail: {p} -> {e}")
    try:
        fx_candidates = []
        for pat in ("fx_4_ver1_*.png","FX_4_VER1_*.png","Fx_4_VEr1_*.png","fx_4_ver1_*.PNG","FX_4_VER1_*.PNG"):
            fx_candidates.extend(glob.glob(os.path.join(base, pat)))
        if fx_candidates: _load_sorted_by_trailing_num(fx_candidates)
        if not frames:
            swirl_candidates = []
            for pat in ("swirl*.png","Swirl*.png","SWIRL*.png","swirl*.PNG","Swirl*.PNG","SWIRL*.PNG"):
                swirl_candidates.extend(glob.glob(os.path.join(base, pat)))
            if swirl_candidates: _load_sorted_by_trailing_num(swirl_candidates)
    except Exception as e:
        print(f"⚠️ VFX glob/list error in {base}: {e}")
    print(f"ℹ️ VFX loader: found {len(frames)} frame(s) in {os.path.abspath(base)}")
    return frames

# Global timer for heal animation
_heal_anim_timer = 0.0

def _draw_heal_animation(screen: pygame.Surface, ax: int, ay: int, ally_sprite, dt: float):
    """Draw healing animation over the active vessel."""
    global _heal_anim_timer
    
    frames = party_manager.get_heal_animation_frames()
    if not frames:
        return
    
    # Reset timer if this is the first frame of animation (check using function attribute)
    if not hasattr(_draw_heal_animation, '_was_active'):
        _draw_heal_animation._was_active = False
    
    # Check if animation just started
    if not _draw_heal_animation._was_active:
        _heal_anim_timer = 0.0
        _draw_heal_animation._was_active = True
    
    # Update animation timer
    _heal_anim_timer += dt
    
    # Calculate frame index - rapid succession (higher FPS)
    HEAL_ANIM_FPS = 30  # frames per second for the animation
    frame_idx = int(_heal_anim_timer * HEAL_ANIM_FPS) % len(frames)
    frame = frames[frame_idx]
    
    # Get ally sprite center for positioning
    if ally_sprite:
        aw = ally_sprite.get_width()
        ah = ally_sprite.get_height()
        center_x = ax + aw // 2
        center_y = ay + ah // 2
    else:
        center_x = ax + 120
        center_y = ay + 120
    
    # Scale animation to match vessel size (slightly larger)
    if ally_sprite:
        target_size = int(max(aw, ah) * 1.2)
    else:
        target_size = 240
    fw, fh = frame.get_width(), frame.get_height()
    scale = target_size / max(1, max(fw, fh))
    scaled_frame = pygame.transform.smoothscale(frame, 
        (max(1, int(fw * scale)), max(1, int(fh * scale))))
    
    # Draw centered over vessel
    screen.blit(scaled_frame, scaled_frame.get_rect(center=(center_x, center_y)))

def _load_swap_sfx():
    return _load_sfx(TELEPORT_SFX)

# ---------------- Party helpers ----------------
def _first_empty_party_slot(gs) -> int | None:
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    for i, n in enumerate(names):
        if not n: return i
    return None

def _add_captured_to_party(gs, vessel_png_name: str, stats_dict: dict) -> bool:
    idx = _first_empty_party_slot(gs)
    if idx is None: return False
    token_png = vessel_to_token(vessel_png_name)
    if not token_png: return False
    if not getattr(gs, "party_slots_names", None): gs.party_slots_names = [None]*6
    if not getattr(gs, "party_slots", None):       gs.party_slots       = [None]*6
    if not getattr(gs, "party_vessel_stats", None):gs.party_vessel_stats= [None]*6
    gs.party_slots_names[idx]  = token_png
    gs.party_slots[idx]        = None
    
    # Clear party_ui.py tracking so it rebuilds from names
    if hasattr(gs, "_party_slots_token_names"):
        delattr(gs, "_party_slots_token_names")
    gs.party_vessel_stats[idx] = dict(stats_dict) if isinstance(stats_dict, dict) else None
    return True

# ---------------- Capture callback ----------------
def _scroll_id_to_kind(iid: str) -> str | None:
    """
    Map ONLY capture scroll ids to capture kinds.
    Healing scrolls (mending/regeneration/revivity) must return None.
    """
    iid = (iid or "").lower().strip()
    if "eternity"    in iid: return "eternity"
    if "subjugation" in iid: return "subjugation"
    if "sealing"     in iid: return "sealing"
    if "command"     in iid: return "command"
    # Healing / other → not a capture scroll
    if any(k in iid for k in ("mending", "regeneration", "revivity", "revive", "healing")):
        return None
    return None

# helper: normalize an item id/name to snake-case
def _norm_item_id(item) -> str:
    s = (str(item.get("id") or item.get("name") or "")).strip().lower()
    s = s.replace(" ", "_")
    return s

# explicit sets
_CAPTURE_SCROLLS = {
    "scroll_of_command", "scroll_of_sealing", "scroll_of_subjugation", "scroll_of_eternity"
}
_HEAL_SCROLL_MODES = {
    # id: mode dict for party_manager.start_use_mode
    "scroll_of_mending":      {"kind":"heal","dice":(1,4), "add_con":True,  "revive":False},
    "scroll_of_regeneration": {"kind":"heal","dice":(2,8), "add_con":True,  "revive":False},
    "scroll_of_revivity":     {"kind":"heal","dice":(2,8), "add_con":False, "revive":True},
}

# ============================================================
# combat/wild_vessel.py — compact vessel encounter scene
# ============================================================
def _on_use_item(gs, item) -> bool:
    """
    Wild battle Bag callback (authoritative).
    STRICT ID-BASED: decide only from item['id'].
    • Healing scrolls -> open Party target mode (consumption on target click)
    • Capture scrolls -> run capture flow
    • Others          -> ignore
    """
    if not item:
        return False

    def _iid(it) -> str:
        s = str((it or {}).get("id") or (it or {}).get("name") or "").strip().lower()
        return s.replace(" ", "_")

    iid = _iid(item)

    HEAL = {
        "scroll_of_mending":      {"kind": "heal", "dice": (1, 4), "add_con": True,  "revive": False},
        "scroll_of_regeneration": {"kind": "heal", "dice": (2, 8), "add_con": True,  "revive": False},
        "scroll_of_revivity":     {"kind": "heal", "dice": (2, 8), "add_con": False, "revive": True},
    }
    CAPTURE_KIND = {
        "scroll_of_command":      "command",
        "scroll_of_sealing":      "sealing",
        "scroll_of_subjugation":  "subjugation",
        "scroll_of_eternity":     "eternity",
    }

    # Prevent multiple uses for the same item
    if not getattr(gs, "_item_consumed", False):
        if iid in HEAL:
            mode = dict(HEAL[iid])
            mode["consume_id"] = iid

            # Process the item use
            try:
                from screens import party_manager
                party_manager.start_use_mode(mode)
            except Exception:
                pass

            # Flag the item as consumed to prevent double usage
            gs._item_consumed = True

            # Close the popup after use
            try:
                bag_action.close_popup()
            except Exception:
                pass
            return True

    # Capture → attempt capture using exact kind
    cap_kind = CAPTURE_KIND.get(iid)
    if cap_kind:
        estats = getattr(gs, "encounter_stats", {}) or {}
        level  = int(estats.get("level", getattr(gs, "zone_level", 1)))
        max_hp = max(1, int(estats.get("hp", 10)))

        # Current HP with ratio fallback (as before)
        cur_hp = int(estats.get("current_hp", max_hp))
        try:
            ratio = float(getattr(gs, "_wild", {}).get("enemy_hp_ratio", 1.0))
            if "current_hp" not in estats:
                cur_hp = max(0, min(max_hp, int(round(max_hp * ratio))))
        except Exception:
            pass

        asset_name = getattr(gs, "encounter_token_name", None)
        ctx = CaptureContext(level=level, max_hp=max_hp, cur_hp=cur_hp,
                             asset_name=asset_name,
                             scroll=cap_kind, status=None, capture_bonus=0, advantage=0)
        res = attempt_capture(ctx)

        st = getattr(gs, "_wild", None)
        if st is not None:
            st["pending_capture"] = res
            st["cap_vfx_playing"] = True
            st["cap_vfx_t"] = 0.0
            st["cap_vfx_total"] = 0.0
            st["cap_vfx_frame"] = 0
            st["cap_popup_fired"] = False
            try:
                if st.get("swap_sfx"):
                    audio_sys.play_sound(st["swap_sfx"])
            except Exception:
                pass

        try:
            bag_action.close_popup()
        except Exception:
            pass
        return True

    # Unknown/non-combat items → ignore
    return False


# ---------------- UI helpers ----------------
def _draw_hp_bar(surface: pygame.Surface, rect: pygame.Rect, hp_ratio: float, name: str, align: str,
                 current_hp: int = None, max_hp: int = None):
    hp_ratio = max(0.0, min(1.0, hp_ratio))
    x, y, w, h = rect
    frame, border, gold, inner = (70,45,30), (140,95,60), (185,150,60), (28,18,14)
    back, front = (60,24,24), (28,150,60)
    pygame.draw.rect(surface, frame, rect, border_radius=10)
    pygame.draw.rect(surface, border, rect, 3, border_radius=10)
    inner_rect = rect.inflate(-10, -10)
    pygame.draw.rect(surface, gold, inner_rect, 2, border_radius=8)
    name_h = max(22, int(h*0.44))
    plate = pygame.Rect(inner_rect.x+8, inner_rect.y+6, inner_rect.w-16, name_h)
    notch_w = max(38, int(h*0.46))
    notch = pygame.Rect(plate.x, plate.y, notch_w, plate.h) if align=="right" \
            else pygame.Rect(plate.right - notch_w, plate.y, notch_w, plate.h)
    pygame.draw.rect(surface, inner, plate, border_radius=6)
    pygame.draw.rect(surface, gold, plate, 2, border_radius=6)
    pygame.draw.rect(surface, frame, notch, border_radius=6)
    trough = pygame.Rect(inner_rect.x+12, plate.bottom+8, inner_rect.w-24, inner_rect.h-name_h-20)
    pygame.draw.rect(surface, back, trough, border_radius=6)
    fw = int(trough.w * hp_ratio)
    if fw > 0:
        pygame.draw.rect(surface, front, (trough.x, trough.y, fw, trough.h), border_radius=6)
    for i in range(1,4):
        tx = trough.x + (trough.w * i)//4
        pygame.draw.line(surface, (30,18,12), (tx, trough.y+3), (tx, trough.bottom-3), 2)
    font = pygame.font.SysFont("georgia", max(20, int(h*0.32)), bold=True)
    label = font.render(name, True, (230,210,180))
    if align=="left":
        surface.blit(label, label.get_rect(midleft=(plate.x+12, plate.centery)))
    else:
        surface.blit(label, label.get_rect(midright=(plate.right-12, plate.centery)))
    
    # Draw HP text inside the green health bar, on the right side (ally only)
    if current_hp is not None and max_hp is not None and align == "left":
        hp_text = f"{current_hp}/{max_hp}"
        hp_font = pygame.font.SysFont("georgia", max(14, int(h*0.22)), bold=True)
        hp_label = hp_font.render(hp_text, True, (255, 255, 255))  # White text for visibility on green
        # Position text on the right edge of the green fill bar
        if fw > 0:
            # Position on the right edge of the green fill, with small margin
            text_x = trough.x + fw - hp_label.get_width() - 6
            text_y = trough.centery - hp_label.get_height() // 2
            # Only draw if there's enough space on the green bar
            if text_x > trough.x + 4:
                surface.blit(hp_label, (text_x, text_y))
        
# ---------- XP strip (matches ledger style, compact) ----------
def _xp_compute(stats: dict) -> tuple[int, int, int, float]:
    """Return (level, cur, need, ratio 0..1) from party stat dict."""
    try:    lvl = max(1, int(stats.get("level", 1)))
    except: lvl = 1
    try:    cur = max(0, int(stats.get("xp_current", stats.get("xp", 0))))
    except: cur = 0
    # prefer stored threshold; else ask the XP system
    need = stats.get("xp_needed")
    try:
        need = int(need) if need is not None else int(xp_sys.xp_needed(lvl))
    except Exception:
        need = 1
    need = max(1, need)
    r = max(0.0, min(1.0, cur / need))
    return lvl, cur, need, r

def _draw_xp_strip(surface: pygame.Surface, rect: pygame.Rect, stats: dict):
    """Compact 'XP cur/need' with a thin progress bar (ledger-like)."""
    _, cur, need, r = _xp_compute(stats)

    frame   = (70, 45, 30)
    border  = (140, 95, 60)
    trough  = (46, 40, 36)
    fill    = (40, 180, 90)
    text    = (230, 220, 200)

    # container
    pygame.draw.rect(surface, frame, rect, border_radius=6)
    pygame.draw.rect(surface, border, rect, 2, border_radius=6)
    inner = rect.inflate(-8, -8)

    # label
    font = pygame.font.SysFont("georgia", max(14, int(rect.h * 0.60)), bold=False)
    label = font.render(f"XP: {cur} / {need}", True, text)
    surface.blit(label, label.get_rect(midleft=(inner.x + 6, inner.centery)))

    # progress bar (right side)
    bar_h = max(4, int(inner.h * 0.36))
    bar_w = max(90, int(inner.w * 0.46))
    bar_x = inner.right - bar_w - 6
    bar_y = inner.centery - bar_h // 2
    bar = pygame.Rect(bar_x, bar_y, bar_w, bar_h)

    pygame.draw.rect(surface, trough, bar, border_radius=3)
    fw = int(bar_w * r)
    if fw > 0:
        pygame.draw.rect(surface, fill, (bar_x, bar_y, fw, bar_h), border_radius=3)


# ---------------- Active party helpers ----------------
def _first_filled_slot_index(gs) -> int:
    names = getattr(gs, "party_slots_names", None) or [None]*6
    for i, n in enumerate(names):
        if n: return i
    return 0

def _ensure_active_slot(gs):
    if not hasattr(gs, "combat_active_idx"):
        base = getattr(gs, "party_active_idx", None)
        if base is None:
            base = _first_filled_slot_index(gs)
        gs.combat_active_idx = int(base)

def _consume_pending_party_switch(gs):
    idx = getattr(gs, "_pending_party_switch", None)
    if isinstance(idx, int):
        names = getattr(gs, "party_slots_names", None) or [None]*6
        if 0 <= idx < len(names) and names[idx]:
            gs.combat_active_idx = idx
        try: delattr(gs, "_pending_party_switch")
        except Exception: pass

def _get_active_party_index(gs) -> int:
    _ensure_active_slot(gs)
    _consume_pending_party_switch(gs)
    return getattr(gs, "combat_active_idx", 0)

def _has_living_party(gs) -> bool:
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    for st in stats:
        if isinstance(st, dict):
            hp = int(st.get("current_hp", st.get("hp", 0)))
            if hp > 0:
                return True
    return False

# ---------------- Lifecycle ----------------
def enter(gs, audio_bank=None, **_):
    xp_sys.ensure_profile(gs)
    # ... (stop walking sfx, etc.)

    # Remember pre-combat UI selection (optional), but COMBAT uses slot #1
    if not hasattr(gs, "_precombat_active_idx"):
        base = getattr(gs, "party_active_idx", None)
        if base is None:
            base = _first_filled_slot_index(gs)
        gs._precombat_active_idx = int(base)

    # Force the combat active to be slot #1 (index 0) if it exists
    gs.combat_active_idx = _battle_start_slot(gs)

    names = getattr(gs, "party_slots_names", None) or [None]*6
    idx = min(max(0, int(gs.combat_active_idx)), len(names)-1)
    ally_token_name = names[idx]
    
    # Reset Infernal Rebirth battle flag for new battle (but keep run flag)
    st = getattr(gs, "_wild", {})
    if st:
        st["infernal_rebirth_used_this_battle"] = False

    # Check if ally is a monster (caught monster in party) BEFORE loading sprite
    is_ally_monster = False
    if ally_token_name and ally_token_name.startswith("Token"):
        # Remove "Token" prefix and file extension
        base_name = os.path.splitext(ally_token_name)[0]  # Remove .png extension if present
        monster_name = base_name[5:] if len(base_name) > 5 else base_name  # Remove "Token" prefix
        monster_names = ["Beholder", "Dragon", "Golem", "Myconid", "Nothic", "Ogre", "Owlbear"]
        is_ally_monster = any(monster_name.startswith(m) for m in monster_names)
    
    # Load ally sprite - use same logic as enemy for monsters
    ally_full = None
    if is_ally_monster:
        # Monster allies: Use _ally_sprite_from_token_name which already handles monsters correctly
        # It checks for Token prefix and loads from VesselMonsters folder
        ally_full = _ally_sprite_from_token_name(ally_token_name)
        if not ally_full:
            # Fallback: try direct loading with monster name
            base_name = os.path.splitext(ally_token_name)[0] if ally_token_name else ""
            monster_name = base_name[5:] if len(base_name) > 5 else base_name  # Remove "Token" prefix
            print(f"🐉 Trying direct monster load for ally: {monster_name} (from token: {ally_token_name})")
            ally_full = _enemy_sprite_from_name(monster_name)
            if ally_full:
                print(f"✅ Successfully loaded monster ally sprite: {monster_name}")
            else:
                print(f"⚠️ Failed to load monster ally sprite for {monster_name}")
    else:
        # Normal vessel allies: Use standard loading
        ally_full = _ally_sprite_from_token_name(ally_token_name)
    
    if ally_full is None:
        ally_full = pygame.Surface(S.PLAYER_SIZE, pygame.SRCALPHA)
        ally_full.fill((40, 160, 40, 220))  # Green placeholder for ally
        print(f"⚠️ Ally sprite not found for {ally_token_name}, using placeholder")
    
    # Load enemy sprite - for monsters, ALWAYS reload fresh from file (never use encounter_sprite)
    # because encounter_sprite is scaled for overworld (1.1x), not battle
    # For vessels, use encounter_sprite if available (pre-loaded at PLAYER_SIZE)
    is_monster = getattr(gs, "encounter_type", None) == "MONSTER"
    enemy_full = None
    
    if is_monster:
        # Monsters: ALWAYS load fresh from file (at native size, then scale for battle)
        # DO NOT use encounter_sprite - it's scaled for overworld display
        token_name = getattr(gs, "encounter_token_name", None)
        if token_name:
            enemy_full = _enemy_sprite_from_name(token_name)
            if not enemy_full:
                print(f"⚠️ Failed to load monster sprite for {token_name}, trying fallback")
                # Last resort: try encounter_name
                enemy_full = _enemy_sprite_from_name(getattr(gs, "encounter_name", None))
        else:
            print(f"⚠️ No token_name for monster, trying encounter_name")
            enemy_full = _enemy_sprite_from_name(getattr(gs, "encounter_name", None))
    else:
        # Vessels: ALWAYS load fresh from source assets using same approach as monsters
        # Use _enemy_sprite_from_name which loads directly from file paths at native size
        # This ensures consistent sizing regardless of game state (never use encounter_sprite - it may be pre-scaled)
        token_name = getattr(gs, "encounter_token_name", None)
        if token_name:
            enemy_full = _enemy_sprite_from_name(token_name)
            if not enemy_full:
                print(f"⚠️ Failed to load vessel sprite for {token_name}, trying fallback")
                # Last resort: try encounter_name
                enemy_full = _enemy_sprite_from_name(getattr(gs, "encounter_name", None))
        else:
            print(f"⚠️ No token_name for vessel, trying encounter_name")
            enemy_full = _enemy_sprite_from_name(getattr(gs, "encounter_name", None))
    
    if enemy_full is None:
        enemy_full = pygame.Surface(S.PLAYER_SIZE, pygame.SRCALPHA)
        enemy_full.fill((160,40,40,220))
    
    # Scale ally sprite - monsters should be sized like enemy vessels (ENEMY_SCALE), not allies
    if is_ally_monster:
        # Monster allies: Scale to fixed height of 500 pixels
        target_height = 500
        if ally_full:
            ally_full = _smooth_scale_to_height(ally_full, target_height)
        print(f"🐉 Monster ally sprite scaled to fixed height: {target_height}px")
    else:
        # Normal vessel allies: Use ALLY_SCALE (1.0)
        ally_full = _smooth_scale(ally_full, ALLY_SCALE)
    
    # Scale enemy sprite - use same logic as battle.py (just apply ENEMY_SCALE)
    if is_monster:
        # Monsters: Scale to match ally sprite height (same size as player's vessel)
        ally_h = ally_full.get_height() if ally_full else S.PLAYER_SIZE[1]
        if enemy_full:
            current_w, current_h = enemy_full.get_size()
            print(f"🐉 Monster sprite loaded: {current_w}x{current_h}, scaling to ally height: {ally_h}")
            
            # Scale monster to match ally height
            if current_h != ally_h:
                enemy_full = _smooth_scale_to_height(enemy_full, ally_h)
                new_w, new_h = enemy_full.get_size()
                print(f"🐉 Scaled monster sprite from {current_w}x{current_h} to {new_w}x{new_h} (ally height: {ally_h})")
            else:
                print(f"🐉 Monster sprite already matches ally height {ally_h}")
    else:
        # Vessels: Use same scaling logic as battle.py - just apply ENEMY_SCALE
        enemy_full = _smooth_scale(enemy_full, ENEMY_SCALE)

    # Use logical resolution for virtual screen dimensions (not physical screen size)
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    ax1 = 20 + ALLY_OFFSET[0]
    ay1 = sh - ally_full.get_height() - 20 + ALLY_OFFSET[1]
    ex1 = sw - enemy_full.get_width() - 20 + ENEMY_OFFSET[0]
    ey1 = 20 + ENEMY_OFFSET[1]
    ally_start  = (-ally_full.get_width() - 60, ay1)
    enemy_start = (sw + 60, ey1)

    bg_img = None
    try:
        p = os.path.join("Assets", "Map", "Wild.png")
        if os.path.exists(p):
            bg_img = pygame.transform.smoothscale(pygame.image.load(p).convert(), (sw, sh))
    except Exception as e:
        print(f"⚠️ Wild bg load failed: {e}")

    try:
        # Use scaled level based on player's highest party level
        from combat.team_randomizer import scaled_enemy_level
        seed  = getattr(gs, "seed", None)
        rng   = StatRoller(seed) if seed is not None else None
        if rng is None:
            import random
            rng = StatRoller(random.randrange(1 << 30))
        
        enemy_level = scaled_enemy_level(gs, rng)
        # Use the stored token name for stat generation (name already generated in world/actors.py)
        token_name = getattr(gs, "encounter_token_name", None)
        if not token_name:
            # Fallback: if no token name stored, this might be an old save - use a safe default
            token_name = "MVesselFighter"
            print("⚠️ Warning: No encounter_token_name found, using default token name")
        gs.encounter_stats = generate_vessel_stats_from_asset(
            token_name,
            level=enemy_level, rng=rng
        )
    except Exception as e:
        print(f"⚠️ Stat generation failed: {e}")
        gs.encounter_stats = {}

    est = gs.encounter_stats or {}
    try:    max_hp = max(1, int(est.get("hp", 10)))
    except: max_hp = 10
    cur_hp = est.get("current_hp")
    try:    cur_hp = int(cur_hp) if cur_hp is not None else max_hp
    except: cur_hp = max_hp
    cur_hp = max(0, min(cur_hp, max_hp))
    est["hp"] = max_hp
    est["current_hp"] = cur_hp
    gs.encounter_stats = est

    gs._wild = {
        "overlay": pygame.Surface((sw, sh), pygame.SRCALPHA),
        "bg": bg_img,

        "ally_img": ally_full,
        "enemy_img": enemy_full,

        "ally_pos": list(ally_start),
        "enemy_pos": list(enemy_start),
        "ally_target": (ax1, ay1),
        "enemy_target": (ex1, ey1),

        # hp visuals (ratios)
        "ally_hp_ratio": 1.0,
        "enemy_hp_ratio": 1.0,

        # scene state
        "intro": True,
        "alpha": 255.0,
        "speed": 255.0 / max(0.001, FADE_SECONDS),
        "ally_t": 0.0,
        "enemy_t": 0.0,

        # ally swapping
        "ally_from_slot": None,
        "ally_swap_target_slot": None,
        "swirl_frames": _load_swirl_frames(),
        "swap_playing": False,
        "swap_t": 0.0,
        "dead_vessel_slot": None,  # Track which vessel died for Infernal Rebirth
        "swap_total": 0.0,
        "swap_frame": 0,
        "ally_img_next": None,
        "swap_sfx": _load_swap_sfx(),

        # capture vfx
        "cap_vfx_playing": False,
        "cap_vfx_t": 0.0,
        "cap_vfx_total": 0.0,
        "cap_vfx_frame": 0,
        "cap_popup_fired": False,

        # result card
        "result": None,  # dict with keys incl. 'kind','title','subtitle','exit_on_close','auto_ms','lock_input'
        "ok_sfx": _load_sfx(CAPTURE_OK_SFX),
        "fail_sfx": _load_sfx(CAPTURE_FAIL_SFX),

        # enemy fade on capture/defeat
        "enemy_fade_active": False,
        "enemy_fade_t": 0.0,
        "enemy_fade_dur": ENEMY_FADE_SEC,
        "caught_sfx": _load_sfx(CAUGHT_SFX),
        "pending_result_payload": None,
        "pending_echo_infusion_message": None,
        "enemy_defeated": False,

        "last_enemy_hp": int(cur_hp),
        "defeat_debounce_t": 0.0,
        "defeat_debounce_ms": 300,

        # Turn/AI
        "phase": PHASE_PLAYER,
        "enemy_think_until": 0,  # pygame.time.get_ticks() + BUFFER when enemy phase starts
        "ai_started": False,

        # Forced switch state when ally faints
        "force_switch": False,     # when True, only Party popup is allowed

        # ✅ XP
        "pending_xp_award": None,  # tuple(outcome, enemy_name, estats, active_idx)
    }

    print(f"ℹ️ wild_vessel.enter: swirl_frames={len(gs._wild.get('swirl_frames') or [])}")

    try: pygame.mixer.music.fadeout(120)
    except Exception: pass
    if audio_bank:
        tracks = audio_sys.get_tracks(audio_bank, prefix="vesselm")
        if tracks:
            pick = random.choice(tracks)
            audio_sys.play_music(audio_bank, pick, loop=True, fade_ms=220)
            gs._wild["track"] = pick

    # Play monster-specific sound when entering monster battle
    if is_monster:
        monster_name = None
        token_name = getattr(gs, "encounter_token_name", None)
        if token_name:
            # Remove "Token" prefix and extension if present
            base = os.path.splitext(token_name)[0]
            if base.startswith("Token"):
                monster_name = base[5:]  # Remove "Token" prefix
            else:
                monster_name = base
        else:
            encounter_name = getattr(gs, "encounter_name", None)
            if encounter_name:
                monster_name = encounter_name
        
        # Map monster name to sound file (MP3s stored alongside monster sprites)
        if monster_name:
            monster_name_lower = monster_name.lower()
            monster_sound_dir = os.path.join("Assets", "VesselMonsters")
            monster_sounds = {
                "beholder": os.path.join(monster_sound_dir, "Beholder.mp3"),
                "dragon": os.path.join(monster_sound_dir, "Dragon.mp3"),
                "golem": os.path.join(monster_sound_dir, "Golem.mp3"),
                "myconid": os.path.join(monster_sound_dir, "Myconid.mp3"),
                "nothic": os.path.join(monster_sound_dir, "Nothic.mp3"),
                "ogre": os.path.join(monster_sound_dir, "Ogre.mp3"),
                "owlbear": os.path.join(monster_sound_dir, "Owlbear.mp3"),
            }

            # Play monster-specific sound
            sound_path = monster_sounds.get(monster_name_lower)
            if sound_path and os.path.exists(sound_path):
                try:
                    monster_sfx = _load_sfx(sound_path)
                    if monster_sfx:
                        audio_sys.play_sound(monster_sfx)
                        print(f"🎵 Playing monster battle sound: {sound_path}")
                except Exception as e:
                    print(f"⚠️ Failed to play monster sound {sound_path}: {e}")

    set_roll_callback(roll_ui._on_roll)
    bag_action.set_use_item_callback(_on_use_item)

    try:
        turn_order.determine_order(gs)
    except Exception:
        pass
    gs._turn_ready = True  # player starts able to act

# ---------------- Result helpers ----------------
def _show_result_screen(st: dict, title: str, subtitle: str, *,
                        kind: str = "info",
                        exit_on_close: bool = False,
                        auto_dismiss_ms: int = 0,
                        lock_input: bool = False):
    st["result"] = {
        "kind": kind,
        "title": title,
        "subtitle": subtitle,
        "t": 0.0,
        "alpha": 0,
        "played": False,
        "exit_on_close": bool(exit_on_close),
        "auto_ms": int(max(0, auto_dismiss_ms)),
        "auto_ready": False,
        "lock_input": bool(lock_input),
    }
    # If auto_dismiss_ms is 0, ensure auto_ready stays False to prevent any auto-dismissal
    if auto_dismiss_ms == 0:
        st["result"]["auto_ready"] = False
        st["result"]["auto_ms"] = 0

def _get_dh_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Load DH font if available, fallback to system font."""
    try:
        font_path = os.path.join("Assets", "Fonts", "DH.otf")
        if os.path.exists(font_path):
            return pygame.font.Font(font_path, size)
    except Exception:
        pass
    # Fallback
    try:
        return pygame.font.SysFont("georgia", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)

def _draw_result_screen(screen: pygame.Surface, st: dict, dt: float):
    res = st.get("result")
    if not res: return
    res["t"] += dt
    a = min(255, res.get("alpha", 0) + int(255 * (dt * 1000 / max(1, RESULT_FADE_MS))))
    res["alpha"] = a

    if not res.get("played", False):
        try:
            if res["kind"] == "success" and st.get("ok_sfx"):
                audio_sys.play_sound(st["ok_sfx"])
            if res["kind"] == "fail" and st.get("fail_sfx"):
                audio_sys.play_sound(st["fail_sfx"])
        except Exception:
            pass
        res["played"] = True

    sw, sh = screen.get_size()
    # No dim overlay - matches heal textbox style
    # dim = pygame.Surface((sw, sh), pygame.SRCALPHA); dim.fill((0, 0, 0, min(160, a)))
    # screen.blit(dim, (0, 0))

    # Position at bottom like heal textbox
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)

    # Box styling (matches heal textbox)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)

    # Combine title and subtitle into one text
    title = res.get("title", "")
    subtitle = res.get("subtitle", "")
    if title and subtitle:
        text = f"{title} - {subtitle}"
    elif title:
        text = title
    elif subtitle:
        text = subtitle
    else:
        text = ""

    # Check for type effectiveness info and extract it for color coding
    effectiveness_info = st.get("last_type_effectiveness")
    effectiveness_color = None
    if effectiveness_info:
        effectiveness_color = effectiveness_info.get("color")
    
    # Text rendering with effectiveness color support
    font = _get_dh_font(28)
    words = text.split(" ")
    lines, cur = [], ""
    max_w = rect.w - 40
    for w in words:
        test = (cur + " " + w).strip()
        if not cur or font.size(test)[0] <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    y = rect.y + 20
    for line in lines:
        # Check if line contains effectiveness label (e.g., "[2x]", "[0.5x]")
        line_text = line
        color = (16, 16, 16)  # Default dark gray
        
        # If effectiveness info exists and line contains the label, use effectiveness color
        if effectiveness_info and effectiveness_color:
            label = effectiveness_info.get("label", "")
            if label and f"[{label}]" in line:
                # Render effectiveness label with color
                parts = line.split(f"[{label}]")
                if len(parts) == 2:
                    # Render text before label
                    if parts[0]:
                        surf1 = font.render(parts[0], False, (16, 16, 16))
                        screen.blit(surf1, (rect.x + 20, y))
                        x_offset = surf1.get_width()
                    else:
                        x_offset = 0
                    
                    # Render effectiveness label with color
                    surf2 = font.render(f"[{label}]", False, effectiveness_color)
                    screen.blit(surf2, (rect.x + 20 + x_offset, y))
                    x_offset += surf2.get_width()
                    
                    # Render text after label
                    if parts[1]:
                        surf3 = font.render(parts[1], False, (16, 16, 16))
                        screen.blit(surf3, (rect.x + 20 + x_offset, y))
                    
                    y += surf2.get_height() + 6
                    continue
        
        # Default rendering (no effectiveness label)
        surf = font.render(line_text, False, color)
        screen.blit(surf, (rect.x + 20, y))
        y += surf.get_height() + 6

    # Blinking prompt bottom-right (matches heal textbox)
    if res.get("auto_ms", 0) <= 0 and not res.get("lock_input", False):
        if "_result_blink_t" not in st:
            st["_result_blink_t"] = 0.0
        st["_result_blink_t"] += dt
        blink_on = int(st["_result_blink_t"] * 2) % 2 == 0
        if blink_on:
            prompt_font = _get_dh_font(20)
            prompt = prompt_font.render("Press SPACE or Click to continue", False, (100, 100, 100))
            screen.blit(prompt, (rect.right - prompt.get_width() - 20, rect.bottom - prompt.get_height() - 12))

    auto_ms = res.get("auto_ms", 0)
    
    # CRITICAL PROTECTION: Check for Echo Infusion or manual-dismiss screens FIRST
    is_echo_infusion = res.get("is_echo_infusion", False)
    must_manual_dismiss = res.get("_must_manual_dismiss", False)
    if is_echo_infusion or must_manual_dismiss:
        # ABSOLUTELY NEVER set auto_ready for these screens - they must be manually dismissed
        res["auto_ms"] = 0
        res["auto_ready"] = False
    else:
        # CRITICAL: Only set auto_ready to True if auto_ms > 0 AND time has elapsed
        # If auto_ms is 0, this is a manual-dismiss screen and auto_ready MUST stay False
        if auto_ms > 0 and (res["t"] * 1000.0) >= auto_ms:
            res["auto_ready"] = True
        else:
            # For manual-dismiss screens (auto_ms == 0), ensure auto_ready is ALWAYS False
            # This prevents any accidental auto-dismissal
            if auto_ms == 0:
                res["auto_ready"] = False

def _resolve_capture_after_popup(gs):
    st = getattr(gs, "_wild", None)
    if not st: return
    res = st.pop("pending_capture", None)
    if not res: return

    if getattr(res, "success", False):
        # Use the stored token name for capture
        # encounter_token_name stores the original asset name (from world/actors.py) like "FVesselBarbarian1"
        # which is already a vessel asset name (not a token name)
        vessel_asset_name = getattr(gs, "encounter_token_name", None)
        if not vessel_asset_name:
            # Fallback: try to extract from encounter_name if it's still a vessel name
            # (for backwards compatibility, but this shouldn't happen with name generator)
            name = getattr(gs, "encounter_name", None)
            if name and any(name.startswith(prefix) for prefix in ["FVessel", "MVessel", "RVessel", "Starter"]):
                vessel_asset_name = name
            else:
                vessel_asset_name = None
        
        if not vessel_asset_name:
            print("⚠️ Capture failed: No vessel asset name found")
            _show_result_screen(st, "Capture Error!", "Could not identify vessel type.", kind="fail", exit_on_close=False)
            return
        
        # Ensure .png extension (encounter_token_name should already be a vessel asset name)
        vessel_png = vessel_asset_name if vessel_asset_name.lower().endswith(".png") else f"{vessel_asset_name}.png"
        stats = getattr(gs, "encounter_stats", None)

        # _add_captured_to_party expects vessel asset names (FVesselBarbarian1.png)
        # and will convert them to token names internally
        if vessel_png and stats:
            # Apply next capture stat bonus if active (before adding to party)
            next_capture_bonus_applied = False
            modified_stats = []
            if hasattr(gs, "next_capture_stat_bonus") and gs.next_capture_stat_bonus > 0:
                try:
                    from systems import buff_applicator
                    success, modified_stats = buff_applicator.apply_next_capture_stat_bonus(gs, stats)
                    if success:
                        next_capture_bonus_applied = True
                        print(f"✨ Applied next capture stat bonus to captured vessel")
                except Exception as e:
                    print(f"⚠️ Failed to apply next capture stat bonus: {e}")
            
            # Try to add to party first
            vessel_idx = None
            if _add_captured_to_party(gs, vessel_png, stats):
                # Successfully added to party - find the vessel index
                for i in range(6):
                    if getattr(gs, "party_slots_names", None) and i < len(gs.party_slots_names):
                        if gs.party_slots_names[i] and vessel_to_token(vessel_png) == gs.party_slots_names[i]:
                            vessel_idx = i
                            break
                
                # Store Echo Infusion message to show after "Vessel Caught!" message
                if next_capture_bonus_applied and modified_stats:
                    from systems.name_generator import generate_vessel_name
                    vessel_name = generate_vessel_name(vessel_png)
                    stats_text = ", ".join([f"{stat} +1" for stat in modified_stats])
                    message = f"{vessel_name} gained +1 to all stats: {stats_text}\n\nThe blessing is gone."
                    # Store to show after capture message
                    st["pending_echo_infusion_message"] = ("Echo Infusion!", message)
            else:
                # Party is full - add to archives instead
                try:
                    from screens.archives import add_vessel_to_archives
                    if add_vessel_to_archives(gs, vessel_png, stats):
                        # Show archive message first, then Echo Infusion message after
                        if next_capture_bonus_applied and modified_stats:
                            from systems.name_generator import generate_vessel_name
                            vessel_name = generate_vessel_name(vessel_png)
                            stats_text = ", ".join([f"{stat} +1" for stat in modified_stats])
                            message = f"{vessel_name} gained +1 to all stats: {stats_text}\n\nThe blessing is gone.\n\n(Vessel sent to Archives - party full)"
                            # Show archive message first (requires click), then Echo Infusion after
                            _show_result_screen(st, "Sent to Archives!", "Your party is full. Vessel stored in The Archives.", kind="success", auto_dismiss_ms=0)
                            # Store Echo Infusion to show after archive message is dismissed
                            st["pending_echo_infusion_message"] = ("Echo Infusion!", message)
                        else:
                            _show_result_screen(st, "Sent to Archives!", "Your party is full. Vessel stored in The Archives.", kind="success", auto_dismiss_ms=2000)
                    else:
                        _show_result_screen(st, "Storage Error!", "Could not store vessel.", kind="fail", auto_dismiss_ms=1500)
                except Exception as e:
                    print(f"⚠️ Failed to add vessel to archives: {e}")
                    _show_result_screen(st, "Storage Error!", "Could not store vessel.", kind="fail", auto_dismiss_ms=1500)
            
            # Mark vessel as discovered in Book of the Bound (regardless of where it went)
            try:
                from screens.book_of_bound import mark_vessel_discovered
                # Remove .png extension for the name
                vessel_name = vessel_png[:-4] if vessel_png.lower().endswith(".png") else vessel_png
                mark_vessel_discovered(gs, vessel_name)
            except Exception as e:
                print(f"⚠️ Failed to mark vessel as discovered: {e}")
            # Play victory music immediately when capture succeeds
            if not st.get("victory_music_played", False):
                victory_path = os.path.join("Assets", "Music", "Sounds", "Victory.mp3")
                if os.path.exists(victory_path):
                    try:
                        # Stop current battle music immediately and play victory music
                        pygame.mixer.music.stop()
                        pygame.mixer.music.load(victory_path)
                        pygame.mixer.music.play(loops=-1)  # Loop until exit
                        st["victory_music_played"] = True
                        print(f"🎵 Victory music started (capture): {victory_path}")
                    except Exception as e:
                        print(f"⚠️ Failed to play victory music: {e}")
                else:
                    print(f"⚠️ Victory music not found at: {victory_path}")
            
            # ✅ Queue XP for capture (only if not already queued)
            # Note: XP award will be set again after enemy fade completes, so we defer it
            # to avoid setting it twice
            # st["pending_xp_award"] = (
            #     "capture",
            #     getattr(gs, "encounter_name", "Enemy"),
            #     dict(getattr(gs, "encounter_stats", {}) or {}),
            #     _get_active_party_index(gs),
            # )
            st["enemy_fade_active"] = True
            st["enemy_fade_t"] = 0.0
            st["pending_result_payload"] = ("success", "Vessel Caught!", f"Bound with roll {res.total} vs DC {res.dc}")
        else:
            _show_result_screen(st, "Party is Full!", "There’s no room to bind this Vessel.", kind="fail", exit_on_close=False)
    else:
        _show_result_screen(st, "It broke free!", f"Your roll {res.total} vs DC {res.dc}", kind="fail", exit_on_close=False)

# ---------------- Turn helpers ----------------
def _begin_player_phase(st: dict):
    st["phase"] = PHASE_PLAYER
    try:
        battle_action.close_popup(); bag_action.close_popup(); party_action.close_popup()
    except Exception: pass
    st["ai_started"] = False  # reset for safety

def _begin_resolving_phase(st: dict):
    st["phase"] = PHASE_RESOLVE
    try:
        battle_action.close_popup(); bag_action.close_popup(); party_action.close_popup()
    except Exception: pass

def _begin_enemy_phase(st: dict):
    st["phase"] = PHASE_ENEMY
    st["ai_started"] = False
    # thinking buffer (ms)
    st["enemy_think_until"] = pygame.time.get_ticks() + 500
    try:
        battle_action.close_popup(); bag_action.close_popup(); party_action.close_popup()
    except Exception:
        pass

# ---------------- Forced switch helpers (ally KO) ----------------
def _trigger_forced_switch_if_needed(gs, st):
    """
    If active ally is KO (HP <= 0) and we aren't already forcing a switch,
    open Party popup and lock other inputs. If no living party members remain,
    show defeat and exit.
    """
    # Active stats
    idx = _get_active_party_index(gs)
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    cur = 0; maxhp = 0
    if 0 <= idx < len(stats) and isinstance(stats[idx], dict):
        cur = int(stats[idx].get("current_hp", stats[idx].get("hp", 0)))
        maxhp = int(stats[idx].get("hp", 0))
    
    # Store which vessel died so we can revive it after the swap
    if cur <= 0 and not st.get("force_switch", False) and not st.get("swap_playing", False):
        print(f"[_trigger_forced_switch_if_needed] Vessel {idx} KO'd (HP={cur}), storing dead vessel slot and triggering forced switch...")
        # Store the dead vessel slot so we can revive it after swap
        st["dead_vessel_slot"] = idx
        if not _has_living_party(gs):
            _show_result_screen(st, "All vessels are down!", "You can't continue.", kind="fail", exit_on_close=True)
            st["pending_exit"] = True
            return
        st["force_switch"] = True
        setattr(gs, "_force_switch", True)   # ← keep party_action in sync
        st["phase"] = PHASE_PLAYER
        try:
            battle_action.close_popup(); bag_action.close_popup()
        except Exception: pass
        try:
            party_action.open_popup()
        except Exception: pass

def _try_revive_dead_vessel_with_infernal_rebirth(gs, st, vessel_slot: int):
    """
    Try to revive a dead vessel using Infernal Rebirth (DemonPact2).
    Called after a vessel swap completes.
    Uses the same logic as scroll_of_revivity - directly restores HP to 50% max.
    """
    # Check if DemonPact2 is in active buffs
    active_buffs = getattr(gs, "active_buffs", [])
    print(f"[_try_revive_dead_vessel_with_infernal_rebirth] Checking active_buffs: count={len(active_buffs)}")
    print(f"[_try_revive_dead_vessel_with_infernal_rebirth] Active buffs: {[b.get('id') if isinstance(b, dict) else str(b)[:50] for b in active_buffs]}")
    
    has_demonpact2 = False
    for buff in active_buffs:
        if isinstance(buff, dict):
            buff_id = buff.get("id")
            buff_tier = buff.get("tier", "")
            buff_name = buff.get("name", "")
            print(f"[_try_revive_dead_vessel_with_infernal_rebirth] Checking buff: id={buff_id}, name={buff_name}, tier={buff_tier}")
            # Check both "DemonPact2" (full name) and 2/"2" (just the ID) with tier "DemonPact"
            # The ID is stored as an integer (2) or string ("2"), not "DemonPact2"
            # Also check the name field which should be "DemonPact2"
            if (buff_id == "DemonPact2" or buff_name == "DemonPact2" or 
                (buff_tier == "DemonPact" and (buff_id == 2 or buff_id == "2"))):
                has_demonpact2 = True
                print(f"[_try_revive_dead_vessel_with_infernal_rebirth] ✅ Found DemonPact2!")
                break
        else:
            print(f"[_try_revive_dead_vessel_with_infernal_rebirth] Non-dict buff: {type(buff)} = {str(buff)[:50]}")
    
    if not has_demonpact2:
        print(f"[_try_revive_dead_vessel_with_infernal_rebirth] ❌ DemonPact2 not found in active_buffs")
        return
    
    # Check if it's been used this battle (resets each battle)
    # NOTE: infernal_rebirth_used_this_run is ONLY for preventing the card from appearing again,
    # NOT for preventing the revival effect. The revival can happen once per battle.
    st_wild = getattr(gs, "_wild", {})
    st_battle = getattr(gs, "_battle", {})
    if st_wild.get("infernal_rebirth_used_this_battle", False) or st_battle.get("infernal_rebirth_used_this_battle", False):
        print(f"[_try_revive_dead_vessel_with_infernal_rebirth] Already used this battle")
        return
    
    stats_list = getattr(gs, "party_vessel_stats", None) or [None]*6
    if vessel_slot < 0 or vessel_slot >= len(stats_list):
        return
    
    vessel_stats = stats_list[vessel_slot]
    if not isinstance(vessel_stats, dict):
        return
    
    current_hp = int(vessel_stats.get("current_hp", 0))
    max_hp = int(vessel_stats.get("hp", 0))
    
    # Only revive if vessel is actually dead (HP = 0)
    if current_hp > 0 or max_hp <= 0:
        print(f"[_try_revive_dead_vessel_with_infernal_rebirth] Vessel {vessel_slot} not dead (HP: {current_hp}/{max_hp})")
        return
    
    print(f"[_try_revive_dead_vessel_with_infernal_rebirth] ✅ Triggering Infernal Rebirth for vessel {vessel_slot} (HP: {current_hp}/{max_hp})")
    
    # Restore to 50% max HP (same logic as _check_infernal_rebirth)
    restored_hp = max(1, max_hp // 2)  # At least 1 HP
    vessel_stats["current_hp"] = restored_hp
    stats_list[vessel_slot] = vessel_stats
    gs.party_vessel_stats = stats_list
    
    # Update on-screen HP ratio for wild_vessel
    if st_wild:
        # Only update if this vessel is currently active (to avoid updating wrong vessel's HP bar)
        active_idx = _get_active_party_index(gs)
        if vessel_slot == active_idx:
            st_wild["ally_hp_ratio"] = (restored_hp / max_hp) if max_hp > 0 else 0.0
            gs._wild = st_wild
    
    # Update on-screen HP ratio for battle
    if st_battle:
        active_idx = _get_active_party_index(gs)
        if vessel_slot == active_idx:
            st_battle["ally_hp_ratio"] = (restored_hp / max_hp) if max_hp > 0 else 0.0
            gs._battle = st_battle
    
    # Mark as used for this battle (resets when entering a new battle)
    # NOTE: We do NOT set infernal_rebirth_used_this_run here because that flag
    # is only for preventing the card from appearing again, not for preventing the revival.
    # The revival can happen once per battle, and the battle flag resets each battle.
    if st_wild:
        st_wild["infernal_rebirth_used_this_battle"] = True
        gs._wild = st_wild
    if st_battle:
        st_battle["infernal_rebirth_used_this_battle"] = True
        gs._battle = st_battle
    
    # Play sound effect
    try:
        import os
        import pygame
        sound_path = os.path.join("Assets", "Blessings", "InfernalRebirth.mp3")
        if os.path.exists(sound_path):
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            try:
                sound = pygame.mixer.Sound(sound_path)
                sound.play()
                print(f"🔊 Played Infernal Rebirth sound: {sound_path}")
            except Exception as e:
                print(f"⚠️ Failed to load/play Infernal Rebirth sound: {e}")
        else:
            print(f"⚠️ Infernal Rebirth sound not found: {sound_path}")
    except Exception as e:
        print(f"⚠️ Failed to play Infernal Rebirth sound: {e}")
    
    # Show result message (same as _check_infernal_rebirth)
    if st_wild:
        st_wild["result"] = {
            "kind": "info",
            "title": "Infernal Rebirth",
            "subtitle": f"Vessel restored to {restored_hp} HP!",
            "t": 0.0, "alpha": 0, "played": False,
            "exit_on_close": False,
            "auto_dismiss_ms": 0,  # Manual dismiss
        }
        st_wild["auto_ready"] = False
    elif st_battle:
        st_battle["result"] = {
            "kind": "info",
            "title": "Infernal Rebirth",
            "subtitle": f"Vessel restored to {restored_hp} HP!",
            "t": 0.0, "alpha": 0, "played": False,
            "exit_on_close": False,
            "auto_dismiss_ms": 0,  # Manual dismiss
        }
        st_battle["auto_ready"] = False
    
    print(f"[_try_revive_dead_vessel_with_infernal_rebirth] ✅ Vessel {vessel_slot} revived to {restored_hp}/{max_hp} HP!")


def _finish_forced_switch_if_done(gs, st):
    if st.get("force_switch", False):
        active_idx = _get_active_party_index(gs)
        if not st.get("swap_playing", False) and st.get("ally_from_slot") == active_idx:
            st["force_switch"] = False
            setattr(gs, "_force_switch", False)   # ← release the lock for party_action
            st["phase"] = PHASE_PLAYER
            gs._turn_ready = True
            
            # After forced switch completes, check if we should revive the dead vessel with Infernal Rebirth
            dead_slot = st.get("dead_vessel_slot")
            if dead_slot is not None:
                _try_revive_dead_vessel_with_infernal_rebirth(gs, st, dead_slot)
                # Clear the dead vessel slot after checking
                st["dead_vessel_slot"] = None

# ---------------- XP helpers ----------------
def _maybe_show_xp_award(gs, st):
    """
    If a pending XP award exists and no result card is on screen,
    compute/distribute and show "Experience Gained". Leaves exit to this card.
    """
    if st.get("result") or not st.get("pending_xp_award"):
        return

    try:
        outcome, enemy_name, estats, active_idx = st.pop("pending_xp_award")
    except Exception:
        st["pending_xp_award"] = None
        return

    # Ensure we know the player's level at time of award
    try:
        active_stats = (getattr(gs, "party_vessel_stats", None) or [None]*6)[int(active_idx)] or {}
        estats = dict(estats or {})
        estats["vs_level"] = int(active_stats.get("level", 1))
    except Exception:
        pass

    base_xp = xp_sys.compute_xp_reward(estats, enemy_name, outcome)
    active_xp, bench_xp, levelups = xp_sys.distribute_xp(gs, int(active_idx), base_xp)

    xp_line = f"+{active_xp} XP to active  |  +{bench_xp} to each benched"
    if levelups:
        idx, old_lv, new_lv = levelups[0]
        from_name = (getattr(gs, "party_slots_names", None) or [None]*6)[idx] or "Ally"
        import os as _os, re as _re
        base = _os.path.splitext(_os.path.basename(from_name))[0]
        for p in ("StarterToken", "MToken", "FToken", "RToken"):
            if base.startswith(p):
                base = base[len(p):]; break
        pretty = _re.sub(r"\d+$", "", base) or "Ally"
        subtitle = f"{xp_line}   •   {pretty} leveled up! {old_lv} → {new_lv}"
    else:
        subtitle = xp_line

    _show_result_screen(
        st,
        "Experience Gained",
        subtitle,
        kind="info",
        exit_on_close=True  # now we exit to overworld after acknowledging XP
    )

    st["pending_exit"] = True

# ---------------- Handle / Exit ----------------
def _exit_encounter(gs):
    try: pygame.mixer.music.fadeout(300)
    except Exception: pass

    pre = getattr(gs, "_precombat_active_idx", None)
    if pre is None:
        pre = _first_filled_slot_index(gs)
    gs.party_active_idx = int(pre)

    if hasattr(gs, "combat_active_idx"): delattr(gs, "combat_active_idx")
    if hasattr(gs, "_pending_party_switch"):
        try: delattr(gs, "_pending_party_switch")
        except Exception: pass

    gs._went_to_wild = False
    gs.in_encounter = False
    gs.encounter_stats = None
    bag_action.set_use_item_callback(None)
    set_roll_callback(None)

def handle(events, gs, **_):
    st = getattr(gs, "_wild", None)
    if st is None:
        gs._wild = {}; st = gs._wild
    
    # Handle heal textbox first (it's modal and works even when party manager is closed)
    if party_manager.is_heal_textbox_active():
        for e in events:
            party_manager.handle_event(e, gs)  # This will handle dismissal
            # If textbox was dismissed, stop processing events
            if not party_manager.is_heal_textbox_active():
                break
        # Clear all events - textbox is modal
        return None
    
    # Let Party Manager eat events (consume and remove handled ones)
    if party_manager.is_open():
        remaining = []
        for e in events:
            # party_manager.handle_event returns True if it handled the event
            if not party_manager.handle_event(e, gs):
                remaining.append(e)
        events = remaining

    

    # Exit queued? (only if no modal result is visible)
    if st.get("pending_exit") and not st.get("result"):
        _exit_encounter(gs)
        return S.MODE_GAME


    # Dice popup is modal
    if roll_ui.is_active():
        for e in events:
            roll_ui.handle_event(e)
        if not roll_ui.is_active():
            mode = run_action.resolve_after_popup(gs)
            if mode is not None:
                return mode
            _resolve_capture_after_popup(gs)
        return None

    # Clear auto-done result cards
    _auto_dismiss_result_if_ready(st)

    # After a result is dismissed, check for Echo Infusion message first (before XP award)
    # IMPORTANT: Only show Echo Infusion if there's NO active result screen
    # This prevents it from being replaced immediately by XP award
    if not st.get("result") and st.get("pending_echo_infusion_message"):
        title, message = st.pop("pending_echo_infusion_message")
        # Show Echo Infusion message - requires manual click to dismiss
        # Explicitly set auto_dismiss_ms to 0 to prevent any auto-dismissal
        _show_result_screen(st, title, message, kind="success", auto_dismiss_ms=0, lock_input=False)
        # Double-check and enforce: make absolutely sure it cannot auto-dismiss
        res = st.get("result")
        if res:
            res["auto_ms"] = 0  # Force it to 0
            res["auto_ready"] = False  # Ensure auto_ready is False
            res["lock_input"] = False  # Ensure input is not locked
            res["exit_on_close"] = False  # Don't exit on close for Echo Infusion
            # Add a flag to mark this as Echo Infusion message so we can track it
            res["is_echo_infusion"] = True
            # Mark that this message must be manually dismissed - never auto-dismiss
            res["_must_manual_dismiss"] = True
        # Return early to prevent XP award from showing until this is dismissed
        return None
    
    # After a result is dismissed, if we have a pending XP award, show it now
    # CRITICAL: Only show XP award if there's NO active result screen
    # This ensures Echo Infusion message stays visible until manually dismissed
    if not st.get("result") and st.get("pending_xp_award"):
        
        try:
            outcome, enemy_name, estats, active_idx = st.pop("pending_xp_award")
        except Exception:
            outcome, enemy_name, estats, active_idx = ("defeat", "Enemy", {}, _get_active_party_index(gs))
        
        # Compute + distribute
        base_xp = xp_sys.compute_xp_reward(estats or {}, enemy_name or "Enemy", outcome or "defeat")
        active_xp, bench_xp, levelups = xp_sys.distribute_xp(gs, int(active_idx), int(base_xp))
        
        # No autosave - user must manually save via "Save Game" button
        
        # Build concise subtitle
        xp_line = f"+{active_xp} XP to active  |  +{bench_xp} to each benched"
        if levelups:
            idx, old_lv, new_lv = levelups[0]
            from_name = (getattr(gs, "party_slots_names", None) or [None]*6)[idx] or "Ally"
            import os, re as _re
            base = os.path.splitext(os.path.basename(from_name))[0]
            for p in ("StarterToken", "MToken", "FToken", "RToken"):
                if base.startswith(p):
                    base = base[len(p):]; break
            pretty = _re.sub(r"\d+$", "", base) or "Ally"
            subtitle = f"{xp_line}   •   {pretty} leveled up! {old_lv} → {new_lv}"
        else:
            subtitle = xp_line
        
        _show_result_screen(
            st,
            "Experience Gained",
            subtitle,
            kind="info",
            exit_on_close=True,  # ← when dismissed, we'll exit to overworld
            auto_dismiss_ms=0  # Must be manually dismissed
        )
        # Don't set pending_exit here - let it be set when the result is dismissed
        return None


    # Note: XP award is handled above (line 1178) after Echo Infusion message
    # This duplicate check is removed to prevent conflicts

    # KO → forced switch?
    _trigger_forced_switch_if_needed(gs, st)

    # ===== INPUT ROUTING =====
    if st.get("force_switch", False):
        # keep the party popup visible during a forced switch,
        # BUT do not auto-open if a selection is already committed
        # (pending swap) or while the swap animation is playing.
        try:
            selection_committed = getattr(gs, "_pending_party_switch", None) is not None
            if (not st.get("swap_playing", False)) and (not selection_committed):
                if not party_action.is_open():
                    party_action.open_popup()
        except Exception:
            pass

        # allow the KO result card to be dismissed while forced
        res = st.get("result")
        if res and not res.get("lock_input", False):
            for e in events:
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    _dismiss_result(st, allow_exit=False)  # don't exit from forced-switch
                    break


        # but otherwise only the Party popup consumes input
        for e in events:
            if party_action.is_open() and party_action.handle_event(e, gs):
                return None
        return None  # still block everything else until a living swap is chosen

    # Normal routing when not forced and not in enemy phase
    if st.get("phase") != PHASE_ENEMY:
        # Check for result screen dismissal FIRST, before other input checks
        # This ensures result screens can be dismissed even if other systems are active
        res = st.get("result")
        if res:
            # Allow clicks/space to dismiss if not locked
            # ALL result screens can be manually dismissed, regardless of auto_ms
            if not res.get("lock_input", False):
                for e in events:
                    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                        _dismiss_result(st, allow_exit=True)
                        # After dismissing, don't process other events in this frame
                        return None
                    if e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_RETURN):
                        _dismiss_result(st, allow_exit=True)
                        # After dismissing, don't process other events in this frame
                        return None
        
        # Now process other input events (only if no result screen, or result screen is locked/auto-dismissing)
        for e in events:
            if st.get("cap_vfx_playing", False):   return None
            if st.get("enemy_fade_active", False): return None

            # If result screen exists and is not locked, block other input (dismissal was handled above)
            if st.get("result") and not st.get("result", {}).get("lock_input", False):
                # Result screen is active and not locked - only allow dismissal (already handled above)
                # Block other input
                continue


            if st.get("phase") == PHASE_PLAYER:
                if party_action.is_open() and party_action.handle_event(e, gs):  return None
                if bag_action.is_open()   and bag_action.handle_event(e, gs):    return None
                if battle_action.is_open()and battle_action.handle_event(e, gs): return None

                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    _exit_encounter(gs)
                    return S.MODE_GAME

                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    pos = e.pos
                    if run_action.handle_click(pos, gs):  return None
                    if battle_action.handle_click(pos):   return None
                    if bag_action.handle_click(pos):      return None
                    if party_action.handle_click(pos):    return None

    # ===== TURN ENGINE =====
    try:
        resolving_moves = bool(moves.is_resolving())
    except Exception:
        resolving_moves = False

    if st.get("phase") == PHASE_PLAYER:
        # Don't advance to RESOLVING while the Party Manager heal picker is open.
        if (getattr(gs, "_turn_ready", True) is False or resolving_moves) and not party_manager.is_open():
            _begin_resolving_phase(st)
            # One-shot any "item consumed" flag so we don't double-advance in this tick
            try:
                gs._turn_consumed_by_item = False
            except Exception:
                pass

    scene_busy = (
        st.get("result") or st.get("cap_vfx_playing") or st.get("enemy_fade_active")
        or st.get("swap_playing") or roll_ui.is_active() or party_manager.is_open()
        or party_manager.is_heal_textbox_active()  # Block enemy turn while heal textbox is showing
    )

    if st.get("phase") == PHASE_RESOLVE and not resolving_moves and not scene_busy:
        try: turn_order.next_turn(gs)
        except Exception: pass
        _begin_enemy_phase(st)

    if st.get("phase") == PHASE_ENEMY:
        now = pygame.time.get_ticks()
        if (not st.get("ai_started")
            and now >= int(st.get("enemy_think_until", 0))
            and not resolving_moves
            and not scene_busy
            and not party_manager.is_open()):  # ← extra guard (belt & suspenders)
            try:
                enemy_ai.take_turn(gs)
            except Exception as _e:
                print(f"⚠️ enemy_ai failure: {_e}")

            try:
                lbl = st.pop("last_enemy_move_label", None) or getattr(gs, "_last_enemy_move_label", None)
                if not lbl:
                    res = st.get("result") or {}
                    title = str(res.get("title", "")) if isinstance(res, dict) else ""
                    m = re.match(r"(?:Enemy used|Enemy\s+Bonk|Enemy)\s+(.+)", title)
                    if m:
                        lbl = m.group(1).strip()
                    elif title.strip().lower().startswith("enemy bonk"):
                        lbl = "Bonk"
                if lbl and not st.get("_enemy_move_sfx_played", False):
                    moves._play_move_sfx(lbl)
                    st["_enemy_move_sfx_played"] = True
            except Exception as _e:
                print(f"⚠️ enemy move sfx fallback error: {_e}")

            st["ai_started"] = True

        if st.get("ai_started") and not resolving_moves and not scene_busy:
            try:
                if turn_order.current_actor(gs) != "player":
                    turn_order.next_turn(gs)
            except Exception:
                pass
            gs._turn_ready = True
            st.pop("_enemy_move_sfx_played", None)
            _begin_player_phase(st)

    def _finish_forced_switch_if_done(gs, st):
        if st.get("force_switch", False):
            active_idx = _get_active_party_index(gs)
            if not st.get("swap_playing", False) and st.get("ally_from_slot") == active_idx:
                st["force_switch"] = False
                setattr(gs, "_force_switch", False)
                st["phase"] = PHASE_PLAYER
                gs._turn_ready = True
                try:
                    party_action.close_popup()   # ← make sure it stays closed
                except Exception:
                    pass

    return None

# ---------------- Draw ----------------
def draw(screen, gs, dt, **_):
    st = getattr(gs, "_wild", None)
    if st is None:
        enter(gs); st = gs._wild

    active_i = _get_active_party_index(gs)
    names = getattr(gs, "party_slots_names", None) or [None]*6
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    active_name  = names[active_i]
    active_stats = stats[active_i] if active_i < len(stats) else None

    # Check if active ally is a monster
    is_active_monster = False
    if active_name and active_name.startswith("Token"):
        # Remove "Token" prefix and file extension
        base_name = os.path.splitext(active_name)[0]  # Remove .png extension if present
        monster_name = base_name[5:] if len(base_name) > 5 else base_name  # Remove "Token" prefix
        monster_names = ["Beholder", "Dragon", "Golem", "Myconid", "Nothic", "Ogre", "Owlbear"]
        is_active_monster = any(monster_name.startswith(m) for m in monster_names)
    
    if st.get("ally_from_slot") is None:
        st["ally_from_slot"] = active_i
        if active_name and not st.get("ally_img"):
            try:
                # Try loading via _ally_sprite_from_token_name first (handles monsters)
                ally_sprite = _ally_sprite_from_token_name(active_name)
                if ally_sprite:
                    if is_active_monster:
                        # Monster allies: Scale to fixed height of 500 pixels
                        target_height = 500
                        st["ally_img"] = _smooth_scale_to_height(ally_sprite, target_height)
                    else:
                        st["ally_img"] = _smooth_scale(ally_sprite, ALLY_SCALE)
                else:
                    # Fallback to asset_links
                    from systems.asset_links import token_to_vessel, find_image
                    vessel_png = token_to_vessel(active_name)
                    path = find_image(vessel_png)
                    if path and os.path.exists(path):
                        loaded = pygame.image.load(path).convert_alpha()
                        if is_active_monster:
                            target_height = 500
                            st["ally_img"] = _smooth_scale_to_height(loaded, target_height)
                        else:
                            st["ally_img"] = _smooth_scale(loaded, ALLY_SCALE)
            except Exception: pass
    elif st["ally_from_slot"] != active_i and active_name and not st.get("swap_playing", False):
        try:
            # Try loading via _ally_sprite_from_token_name first (handles monsters)
            ally_sprite = _ally_sprite_from_token_name(active_name)
            if ally_sprite:
                if is_active_monster:
                    # Monster allies: Scale to fixed height of 500 pixels
                    target_height = 500
                    st["ally_img_next"] = _smooth_scale_to_height(ally_sprite, target_height)
                else:
                    st["ally_img_next"] = _smooth_scale(ally_sprite, ALLY_SCALE)
                st["ally_swap_target_slot"] = active_i
                st["swap_playing"] = True
                st["swap_t"] = 0.0
                st["swap_total"] = 0.0
                st["swap_frame"] = 0
                st["ally_t"] = 1.0
                st["intro"] = False
                try:
                    if st.get("swap_sfx"):
                        audio_sys.play_sound(st["swap_sfx"])
                except Exception: pass
            else:
                # Fallback to asset_links
                from systems.asset_links import token_to_vessel, find_image
                vessel_png = token_to_vessel(active_name)
                path = find_image(vessel_png)
                if path and os.path.exists(path):
                    loaded = pygame.image.load(path).convert_alpha()
                    if is_active_monster:
                        target_height = 500
                        st["ally_img_next"] = _smooth_scale_to_height(loaded, target_height)
                    else:
                        st["ally_img_next"] = _smooth_scale(loaded, ALLY_SCALE)
                    st["ally_swap_target_slot"] = active_i
                    st["swap_playing"] = True
                    st["swap_t"] = 0.0
                    st["swap_total"] = 0.0
                    st["swap_frame"] = 0
                    st["ally_t"] = 1.0
                    st["intro"] = False
                    try:
                        if st.get("swap_sfx"):
                            audio_sys.play_sound(st["swap_sfx"])
                    except Exception: pass
        except Exception: pass

    # Ally HP ratio
    if isinstance(active_stats, dict):
        maxhp = max(1, int(active_stats.get("hp", 10)))
        curhp = max(0, min(int(active_stats.get("current_hp", maxhp)), maxhp))
        st["ally_hp_ratio"] = curhp / maxhp
    else:
        st["ally_hp_ratio"] = 1.0

    # Enemy HP ratio
    estats = getattr(gs, "encounter_stats", None) or {}
    if hasattr(gs, "_wild"):
        estats = dict(estats); estats["_hp_ratio_fallback"] = st.get("enemy_hp_ratio", 1.0)
    e_cur, e_max = _parse_enemy_hp_fields(estats)
    st["enemy_hp_ratio"] = (e_cur / e_max) if e_max > 0 else 1.0
    # Store enemy HP values for HP text display
    st["enemy_cur_hp"] = int(e_cur)
    st["enemy_max_hp"] = int(e_max)

    # Background
    if st.get("bg"): screen.blit(st["bg"], (0, 0))
    else:            screen.fill((0, 0, 0))

    # Slide animation
    st["ally_t"]  = min(1.0, st.get("ally_t", 0.0)  + dt / max(0.001, SUMMON_TIME))
    if st.get("intro", False):
        st["enemy_t"] = min(1.0, st.get("enemy_t", 0.0) + dt / max(0.001, SUMMON_TIME))
    else:
        st["enemy_t"] = 1.0
    ally_ease  = 1.0 - (1.0 - st["ally_t"])  ** 3
    enemy_ease = 1.0 - (1.0 - st["enemy_t"]) ** 3
    ax0, ay0 = st["ally_pos"];   ax1, ay1 = st["ally_target"]
    ex0, ey0 = st["enemy_pos"];  ex1, ey1 = st["enemy_target"]
    ax = int(ax0 + (ax1 - ax0) * ally_ease);  ay = int(ay0 + (ay1 - ay0) * ally_ease)
    ex = int(ex0 + (ex1 - ex0) * enemy_ease); ey = int(ey0 + (ey1 - ey0) * enemy_ease)

    # HP bars
    bar_w, bar_h = 400, 70
    ally_img_w = st["ally_img"].get_width()  if st.get("ally_img")  else 0
    ally_img_h = st["ally_img"].get_height() if st.get("ally_img")  else 0
    ally_bar = pygame.Rect(ax + (ally_img_w // 2) - (bar_w // 2), ay + ally_img_h + 12, bar_w, bar_h)
    enemy_bar = pygame.Rect(ex - bar_w - 24, ey + 12, bar_w, bar_h)

    # --- labels with levels ---
    # Ally label
    ally_lv = 1
    if isinstance(active_stats, dict):
        try: ally_lv = int(active_stats.get("level", 1))
        except Exception: ally_lv = 1
    from systems.name_generator import get_display_vessel_name
    ally_name  = get_display_vessel_name(active_name, active_stats) if active_name else "Ally"
    ally_label = f"{ally_name}  lvl {ally_lv}"

    # Enemy label
    est = getattr(gs, "encounter_stats", {}) or {}
    try: enemy_lv = int(est.get("level", getattr(gs, "zone_level", 1)))
    except Exception: enemy_lv = getattr(gs, "zone_level", 1)
    enemy_name  = getattr(gs, "encounter_name", "Enemy") or "Enemy"
    enemy_label = f"{enemy_name}  lvl {enemy_lv}"


    # Get ally HP values for display
    ally_cur_hp = None
    ally_max_hp = None
    if isinstance(active_stats, dict):
        try:
            ally_max_hp = max(1, int(active_stats.get("hp", 10)))
            ally_cur_hp = max(0, min(int(active_stats.get("current_hp", ally_max_hp)), ally_max_hp))
        except Exception:
            pass
    
    _draw_hp_bar(screen, ally_bar, st.get("ally_hp_ratio", 1.0), ally_label, "left",
                 current_hp=ally_cur_hp, max_hp=ally_max_hp)
    # XP strip under ally HP plate
    if isinstance(active_stats, dict):
        xp_h = 22  # tweak height as you like
        # XP strip position (HP text is now on top, so no adjustment needed)
        xp_rect = pygame.Rect(ally_bar.x, ally_bar.bottom + 6, ally_bar.w, xp_h)
        _draw_xp_strip(screen, xp_rect, active_stats)

    if st.get("enemy_img") is not None:
        # Get enemy HP values for display
        enemy_cur_hp = st.get("enemy_cur_hp")
        enemy_max_hp = st.get("enemy_max_hp")
        _draw_hp_bar(screen, enemy_bar, st.get("enemy_hp_ratio", 1.0), enemy_label, "right",
                     current_hp=enemy_cur_hp, max_hp=enemy_max_hp)

    # Enemy KO debounce & fade
    if st.get("last_enemy_hp") is None: st["last_enemy_hp"] = int(e_cur)
    else:                               st["last_enemy_hp"] = int(e_cur)

    try:
        moves_busy = bool(moves.is_resolving())
    except Exception:
        moves_busy = False

    # Play victory music immediately when enemy HP hits 0
    if (e_cur <= 0 and st.get("enemy_img") is not None and
        not st.get("victory_music_played", False) and
        not st.get("cap_vfx_playing", False) and
        not st.get("result", None)):
        victory_path = os.path.join("Assets", "Music", "Sounds", "Victory.mp3")
        if os.path.exists(victory_path):
            try:
                # Stop current battle music immediately and play victory music
                pygame.mixer.music.stop()
                pygame.mixer.music.load(victory_path)
                pygame.mixer.music.play(loops=-1)  # Loop until exit
                st["victory_music_played"] = True
                print(f"🎵 Victory music started: {victory_path}")
            except Exception as e:
                print(f"⚠️ Failed to play victory music: {e}")
        else:
            print(f"⚠️ Victory music not found at: {victory_path}")

    should_consider_ko = (
        e_cur <= 0 and st.get("enemy_img") is not None and
        not st.get("enemy_fade_active", False) and
        not st.get("cap_vfx_playing", False)   and
        not st.get("result", None)             and
        not st.get("enemy_defeated", False)    and
        not moves_busy
    )
    if should_consider_ko:
        st["defeat_debounce_t"] = st.get("defeat_debounce_t", 0.0) + dt
        if (st["defeat_debounce_t"] * 1000.0) >= int(st.get("defeat_debounce_ms", 300)):
            st["enemy_fade_active"] = True
            st["enemy_fade_t"] = 0.0
            st["enemy_defeated"] = True
            if not st.get("pending_xp_award"):
                st["pending_xp_award"] = (
                    "defeat",
                    getattr(gs, "encounter_name", "Enemy"),
                    dict(getattr(gs, "encounter_stats", {}) or {}),
                    _get_active_party_index(gs),
                )
    else:
        if e_cur > 0 or moves_busy:
            st["defeat_debounce_t"] = 0.0

    # Enemy sprite (with fade)
    if st.get("enemy_img"):
        enemy_surface = st["enemy_img"]
        if st.get("enemy_fade_active", False):
            st["enemy_fade_t"] += dt
            t = st["enemy_fade_t"]
            dur = max(0.001, st.get("enemy_fade_dur", ENEMY_FADE_SEC))
            alpha = max(0, 255 - int(255 * (t / dur)))
            temp = enemy_surface.copy(); temp.set_alpha(alpha)
            screen.blit(temp, (ex, ey))
            if t >= dur:
                st["enemy_fade_active"] = False
                st["enemy_img"] = None

                active_idx = _get_active_party_index(gs)
                estats = getattr(gs, "encounter_stats", {}) or {}
                enemy_name = getattr(gs, "encounter_name", "Enemy") or "Enemy"

                if st.get("pending_result_payload"):
                    try:
                        s = st.get("caught_sfx")
                        if s: audio_sys.play_sound(s)
                    except Exception:
                        pass
                    kind, title, subtitle = st["pending_result_payload"]
                    st["pending_result_payload"] = None
                    # Show capture message first (requires click to dismiss)
                    # Then Echo Infusion message will show after this is dismissed
                    _show_result_screen(st, title, subtitle, kind=kind, exit_on_close=False, auto_dismiss_ms=0)
                    # Queue XP award (will show after Echo Infusion message if present, or after capture message)
                    st["pending_xp_award"] = ("capture", enemy_name, estats, active_idx)
                elif st.get("enemy_defeated", False):
                    st["pending_xp_award"] = ("defeat", enemy_name, estats, active_idx)
        else:
            screen.blit(enemy_surface, (ex, ey))

    # Ally sprite
    if st.get("ally_img"): screen.blit(st["ally_img"], (ax, ay))
    
    # Draw heal animation over active vessel (if healing animation is active)
    # Reset flag when animation stops (outside the draw function)
    if not party_manager.is_heal_animation_active():
        if hasattr(_draw_heal_animation, '_was_active'):
            _draw_heal_animation._was_active = False
            _heal_anim_timer = 0.0
    
    if party_manager.is_heal_animation_active():
        _draw_heal_animation(screen, ax, ay, st.get("ally_img"), dt)

    # Ally swap VFX
    if st.get("swap_playing", False):
        frames = st.get("swirl_frames") or []
        if not frames:
            if st.get("ally_img_next"): st["ally_img"] = st["ally_img_next"]
            st["ally_img_next"] = None
            st["ally_from_slot"] = st.get("ally_swap_target_slot", st.get("ally_from_slot"))
            st["ally_swap_target_slot"] = None
            st["swap_playing"]  = False
            # After swap completes, check for Infernal Rebirth revival
            _finish_forced_switch_if_done(gs, st)
            # Also check for revival after any swap (not just forced switches)
            dead_slot = st.get("dead_vessel_slot")
            if dead_slot is not None:
                _try_revive_dead_vessel_with_infernal_rebirth(gs, st, dead_slot)
                st["dead_vessel_slot"] = None
        else:
            st["swap_t"]     = st.get("swap_t", 0.0) + dt
            st["swap_total"] = st.get("swap_total", 0.0) + dt
            vis_index = int(st["swap_t"] * SWIRL_VIS_FPS) % len(frames)
            st["swap_frame"] = vis_index
            idx = min(st["swap_frame"], len(frames)-1)
            swirl_raw = frames[idx]
            if st.get("ally_img"):
                aw = st["ally_img"].get_width(); ah = st["ally_img"].get_height()
            else:
                aw = ah = 240
            target = int(max(aw, ah) * 1.15)
            sw_, sh_ = swirl_raw.get_width(), swirl_raw.get_height()
            s = target / max(1, max(sw_, sh_))
            swirl = pygame.transform.smoothscale(swirl_raw, (max(1, int(sw_ * s)), max(1, int(sh_ * s))))
            cx = ax + aw // 2; cy = ay + ah // 2
            screen.blit(swirl, swirl.get_rect(center=(cx, cy)))
            if st["swap_total"] >= SWIRL_DURATION:
                if st.get("ally_img_next"): st["ally_img"] = st["ally_img_next"]
                st["ally_img_next"] = None
                st["ally_from_slot"] = st.get("ally_swap_target_slot", st.get("ally_from_slot"))
                st["ally_swap_target_slot"] = None
                st["swap_playing"]  = False
                _finish_forced_switch_if_done(gs, st)

    # --- Turn indicator overlay (debug)
    if "phase" in st:
        font = pygame.font.SysFont("georgia", 22, bold=True)
        text = f"Phase: {st.get('phase','?')}  Ready:{getattr(gs,'_turn_ready',True)}  ForceSwitch:{st.get('force_switch', False)}"
        surf = font.render(text, True, (240, 230, 200))
        screen.blit(surf, (12, 12))

    # Capture swirl VFX on enemy (before dice popup)
    if st.get("cap_vfx_playing", False):
        frames = st.get("swirl_frames") or []
        if not frames:
            st["cap_vfx_playing"] = False
            res = st.get("pending_capture")
            if res and not st.get("cap_popup_fired", False):
                st["cap_popup_fired"] = True
                roll_ui._on_roll("check", res)
                try:
                    if not getattr(S, "AUDIO_BANK", None):
                        from rolling import sfx as dice_sfx; dice_sfx.play_dice()
                except Exception: pass
        else:
            st["cap_vfx_t"]     = st.get("cap_vfx_t", 0.0) + dt
            st["cap_vfx_total"] = st.get("cap_vfx_total", 0.0) + dt
            vis_index = int(st["cap_vfx_t"] * SWIRL_VIS_FPS) % len(frames)
            st["cap_vfx_frame"] = vis_index
            idx = min(st["cap_vfx_frame"], len(frames)-1)
            swirl_raw = frames[idx]
            if st.get("enemy_img"):
                ew = st["enemy_img"].get_width(); eh = st["enemy_img"].get_height()
            else:
                ew = eh = 240
            target = int(max(ew, eh) * 1.2)
            sw_, sh_ = swirl_raw.get_width(), swirl_raw.get_height()
            s = target / max(1, max(sw_, sh_))
            swirl = pygame.transform.smoothscale(swirl_raw, (max(1, int(sw_ * s)), max(1, int(sh_ * s))))
            cx = ex + ew // 2; cy = ey + eh // 2
            screen.blit(swirl, swirl.get_rect(center=(cx, cy)))
            if st["cap_vfx_total"] >= SWIRL_DURATION:
                st["cap_vfx_playing"] = False
                res = st.get("pending_capture")
                if res and not st.get("cap_popup_fired", False):
                    st["cap_popup_fired"] = True
                    roll_ui._on_roll("check", res)
                    try:
                        if not getattr(S, "AUDIO_BANK", None):
                            from rolling import sfx as dice_sfx; dice_sfx.play_dice()
                    except Exception: pass

    # Scene fade overlay
    if st.get("intro", False):
        st["alpha"] = max(0.0, st["alpha"] - st["speed"] * dt)
        if st["alpha"] > 0.0:
            st["overlay"].fill((0, 0, 0, int(st["alpha"])))
            screen.blit(st["overlay"], (0, 0))
        else:
            st["intro"] = False

    # Buttons & popups
    battle_action.draw_button(screen)
    bag_action.draw_button(screen)
    party_action.draw_button(screen)
    run_action.draw_button(screen)
    if bag_action.is_open():    bag_action.draw_popup(screen, gs)
    if party_action.is_open():  party_action.draw_popup(screen, gs)
    if battle_action.is_open(): battle_action.draw_popup(screen, gs)

    # Result screen (over UI, under dice popup)
    if st.get("result"): _draw_result_screen(screen, st, dt)

    # Dice popup always on top
    roll_ui.draw_roll_popup(screen, dt)

    # Draw Party Manager overlay on very top - always draw to show heal textbox if active
    party_manager.draw(screen, gs, dt)

