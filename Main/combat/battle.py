# ============================================================
# combat/battle.py — Summoner Battle (wild_vessel logic merged)
# - Same HUD, result cards, phases, forced party swap, AI buffer
# - Enemy TEAMS via team_randomizer: auto-summon next on defeat
# - Aggregate XP across all defeated/captured enemies; show once
# - ESC (or Run) exits back to overworld after battle finishes
# ============================================================
from __future__ import annotations

import os
import re
import glob
import random
import pygame

import settings as S

# Systems
from systems import audio as audio_sys
from systems import xp as xp_sys
from systems import points as points_sys

# Enemy team generator
from combat.team_randomizer import generate_enemy_team

# Assets helpers
from systems.asset_links import token_to_vessel, find_image, vessel_to_token

# Turn engine bits (same as wild_vessel)
from combat import moves
from combat import turn_order
from combat import enemy_ai

# Dice UI (present for parity; not used for capture here)
from rolling.roller import set_roll_callback, Roller as StatRoller
from rolling import ui as roll_ui

# UI buttons
from combat.btn import run_action
from combat.btn import bag_action, battle_action, party_action

from screens import party_manager


# ---------------- Modes ----------------
MODE_GAME   = getattr(S, "MODE_GAME", "GAME")
MODE_BATTLE = getattr(S, "MODE_BATTLE", "BATTLE")

# ---------------- Visual Tunables ----------------
FADE_SECONDS     = 0.8
SUMMON_TIME      = 0.60
ALLY_OFFSET      = (290, -140)
ENEMY_OFFSET     = (-400, 220)
ALLY_SCALE       = 1.0
ENEMY_SCALE      = 0.90
SWIRL_DURATION   = 2.0
SWIRL_VIS_FPS    = 60

ENEMY_FADE_SEC   = 0.60
RESULT_FADE_MS   = 220
RESULT_CARD_W    = 540
RESULT_CARD_H    = 220

TELEPORT_SFX     = os.path.join("Assets", "Music", "Sounds", "Teleport.mp3")

# --- Phases ---
PHASE_PLAYER  = "PLAYER_TURN"
PHASE_RESOLVE = "RESOLVING"
PHASE_ENEMY   = "ENEMY_TURN"

# ---------------- Utility: ints & HP parsing ----------------
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

def _parse_enemy_hp_fields(estats: dict, *, ratio_fallback: float = 1.0) -> tuple[int, int]:
    max_hp = max(1, _safe_int(estats.get("hp", 10), 10))
    if "current_hp" in estats:
        cur_hp = _safe_int(estats.get("current_hp"), max_hp)
    else:
        try: r = float(ratio_fallback)
        except Exception: r = 1.0
        cur_hp = int(round(max(0.0, min(1.0, r)) * max_hp))
    cur_hp = max(0, min(cur_hp, max_hp))
    return cur_hp, max_hp

# ---------------- XP award helper -----------------
def _award_xp_for_enemy_event(gs, st, ev):
    """
    ev = (outcome, enemy_name, estats, active_idx)
    Awards XP immediately and shows a small result card.
    """
    try:
        outcome, enemy_name, estats, active_idx = ev
        base = int(xp_sys.compute_xp_reward(estats or {}, enemy_name or "Enemy", outcome or "defeat"))
    except Exception:
        base = 1
        enemy_name = enemy_name or "Enemy"
        active_idx = _get_active_party_index(gs)

    # Safety: ensure XP profile before distributing
    try:
        xp_sys.ensure_profile(gs)
    except Exception:
        pass

    active_xp, bench_xp, levelups = xp_sys.distribute_xp(gs, int(active_idx), int(base))

    # Small auto-dismissing toast
    subtitle = f"+{active_xp} XP to active  |  +{bench_xp} to each benched"
    if levelups:
        idx, old_lv, new_lv = levelups[0]
        from_name = (getattr(gs, "party_slots_names", None) or [None]*6)[idx] or "Ally"
        base_name = os.path.splitext(os.path.basename(from_name))[0]
        for p in ("StarterToken", "MToken", "FToken", "RToken"):
            if base_name.startswith(p):
                base_name = base_name[len(p):]; break
        pretty = re.sub(r"\d+$", "", base_name) or "Ally"
        subtitle = f"{subtitle}   •   {pretty} leveled up! {old_lv} → {new_lv}"

    # Show a quick toast (auto-hides; doesn't block input)
    _show_result_screen(
        st,
        f"Defeated {enemy_name or 'Enemy'}",
        subtitle,
        kind="info",
        auto_dismiss_ms=1200,   # small toast
        lock_input=False
    )

def _maybe_show_xp_award(gs, st):
    """
    If a pending XP award exists and no result card is visible,
    compute + distribute and show an 'Experience Gained' card.
    We DO NOT exit the battle; the next enemy can already be on screen.
    """
    # Removed debug spam: print("[battle] maybe_show_xp_award: result=", bool(st.get("result")), "pending=", bool(st.get("pending_xp_award")))
    if st.get("result") or not st.get("pending_xp_award"):
        return

    try:
        outcome, enemy_name, estats, active_idx = st.pop("pending_xp_award")
    except Exception:
        st["pending_xp_award"] = None
        return

    # capture player's level context at award time
    try:
        party = getattr(gs, "party_vessel_stats", None) or [None]*6
        active_stats = party[int(active_idx)] or {}
        estats = dict(estats or {})
        estats["vs_level"] = int(active_stats.get("level", 1))
    except Exception:
        pass

    base_xp = xp_sys.compute_xp_reward(estats, enemy_name, outcome)
    # Removed debug spam: print("[battle] awarding XP:", outcome, enemy_name, "base=", base_xp, "to active idx", active_idx)
    active_xp, bench_xp, levelups = xp_sys.distribute_xp(gs, int(active_idx), int(base_xp))

    # No autosave - user must manually save via "Save Game" button

    xp_line = f"+{active_xp} XP to active  |  +{bench_xp} to each benched"
    if levelups:
        idx, old_lv, new_lv = levelups[0]
        from_name = (getattr(gs, "party_slots_names", None) or [None]*6)[idx] or "Ally"
        base = os.path.splitext(os.path.basename(from_name))[0]
        for p in ("StarterToken", "MToken", "FToken", "RToken"):
            if base.startswith(p):
                base = base[len(p):]
                break
        pretty = re.sub(r"\d+$", "", base) or "Ally"
        subtitle = f"{xp_line}   •   {pretty} leveled up! {old_lv} → {new_lv}"
    else:
        subtitle = xp_line

    _show_result_screen(
        st,
        "Experience Gained",
        subtitle,
        kind="info",
        exit_on_close=False  # stay in battle (team mode)
    )



# ---------------- Asset helpers ----------------
def _load_bg_scaled(sw: int, sh: int) -> pygame.Surface | None:
    try:
        p = os.path.join("Assets", "Map", "Wild.png")
        if not os.path.exists(p):
            return None
        img = pygame.image.load(p).convert()
        if img.get_width() != sw or img.get_height() != sh:
            img = pygame.transform.smoothscale(img, (sw, sh))
        return img
    except Exception as e:
        print(f"⚠️ Wild bg load failed: {e}")
        return None

def _try_load(path: str | None) -> pygame.Surface | None:
    if path and os.path.exists(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"⚠️ load fail {path}: {e}")
    return None

def _smooth_scale(surf: pygame.Surface | None, scale: float) -> pygame.Surface | None:
    if surf is None or abs(scale - 1.0) < 1e-6:
        return surf
    w, h = surf.get_width(), surf.get_height()
    return pygame.transform.smoothscale(surf, (max(1, int(w * scale)), max(1, int(h * scale))))

def _smooth_scale_to_height(surf: pygame.Surface | None, target_h: int) -> pygame.Surface | None:
    """Scale sprite to target height while maintaining aspect ratio."""
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

def _ally_sprite_from_token_name(fname: str | None) -> pygame.Surface | None:
    return _resolve_sprite_surface(fname)

def _enemy_sprite_from_token_name(token_fname: str | None) -> pygame.Surface | None:
    return _resolve_sprite_surface(token_fname)

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

def _load_sfx(path: str):
    try:
        if not path or not os.path.exists(path):
            return None
        return pygame.mixer.Sound(path)
    except Exception as e:
        print(f"⚠️ SFX load fail {path}: {e}")
        return None

def _load_swap_sfx():
    return _load_sfx(TELEPORT_SFX)

# ---------------- Asset helpers ----------------
def _guess_vessel_name_from_token(fname: str) -> str | None:
    """
    Convert any *Token* filename into a plausible *Vessel* filename.
    Handles prefixes Starter/M/F/R and also removes trailing digits,
    e.g. RTokenWizard1.png -> RVesselWizard.png
    """
    if not fname:
        return None

    base = os.path.basename(fname)
    root, ext = os.path.splitext(base)

    # Map known token prefixes to vessel prefixes
    prefix_map = (
        ("StarterToken", "StarterVessel"),
        ("MToken",       "MVessel"),
        ("FToken",       "FVessel"),
        ("RToken",       "RVessel"),
        # Monsters: TokenBeholder -> Beholder, TokenDragon -> Dragon, etc.
        ("TokenBeholder", "Beholder"),
        ("TokenDragon",   "Dragon"),
        ("TokenGolem",   "Golem"),
        ("TokenNothic",  "Nothic"),
        ("TokenOgre",    "Ogre"),
        ("TokenOwlbear", "Owlbear"),
        ("TokenMyconid", "Myconid"),
        ("Token",        "Vessel"),  # Generic fallback
    )

    for tok, ves in prefix_map:
        if root.startswith(tok):
            # Replace prefix once, then strip any trailing digits
            new_root = root.replace(tok, ves, 1)
            new_root = re.sub(r"\d+$", "", new_root)
            return new_root + ext

    # Last-chance generic: if it contains "Token" anywhere
    if "Token" in root:
        new_root = root.replace("Token", "Vessel", 1)
        new_root = re.sub(r"\d+$", "", new_root)
        return new_root + ext

    return None

ASSET_DEBUG = True  # set False to silence

def _resolve_sprite_surface(name: str | None) -> pygame.Surface | None:
    if not name:
        return None

    def _try_variants(basename: str | None, tag: str) -> pygame.Surface | None:
        if not basename:
            return None
        for g in {basename, basename.lower(), basename.upper()}:
            p = find_image(g)
            if p:
                if ASSET_DEBUG:
                    print(f"[assets] HIT {tag}: {g} -> {p}")
                return _try_load(p)
        if ASSET_DEBUG:
            print(f"[assets] MISS {tag}: {basename}")
        return None

    # Check for monster tokens first (TokenDragon, TokenBeholder, etc.)
    if name.startswith("Token"):
        # Remove "Token" prefix and file extension
        base_name = os.path.splitext(name)[0]  # Remove .png extension if present
        monster_name = base_name[5:] if len(base_name) > 5 else base_name  # Remove "Token" prefix
        # Check if it's a known monster
        monster_names = ["Beholder", "Dragon", "Golem", "Myconid", "Nothic", "Ogre", "Owlbear"]
        if any(monster_name.startswith(m) for m in monster_names):
            # Load from VesselMonsters folder
            monster_path = os.path.join("Assets", "VesselMonsters", f"{monster_name}.png")
            monster_img = _try_load(monster_path)
            if monster_img:
                if ASSET_DEBUG:
                    print(f"[assets] HIT monster: {monster_name} -> {monster_path}")
                return monster_img
            else:
                if ASSET_DEBUG:
                    print(f"[assets] MISS monster: {monster_name} at {monster_path}")

    cand  = token_to_vessel(name)
    guess = _guess_vessel_name_from_token(name)

    # vessel paths first
    surf = _try_variants(cand,  "cand") or _try_variants(guess, "guess")
    if not surf and guess:
        m = re.search(r"(\d+)(?=\.[^.]+$)", os.path.basename(name))
        if m:
            root, ext = os.path.splitext(os.path.basename(guess))
            surf = _try_variants(root + m.group(1) + ext, "guess+num")
    if surf:
        return surf

    # token fallback
    return _try_variants(name, "token-fallback")





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
        # Position text on the right side of the green fill bar
        if fw > 0:
            # Position on the right edge of the green fill, with small margin
            text_x = trough.x + fw - hp_label.get_width() - 6
            text_y = trough.centery - hp_label.get_height() // 2
            # Only draw if there's enough space on the green bar
            if text_x > trough.x + 4:
                surface.blit(hp_label, (text_x, text_y))

# ---------- XP strip ----------
def _xp_compute(stats: dict) -> tuple[int, int, int, float]:
    try:    lvl = max(1, int(stats.get("level", 1)))
    except: lvl = 1
    try:    cur = max(0, int(stats.get("xp_current", stats.get("xp", 0))))
    except: cur = 0
    need = stats.get("xp_needed")
    try:
        need = int(need) if need is not None else int(xp_sys.xp_needed(lvl))
    except Exception:
        need = 1
    need = max(1, need)
    r = max(0.0, min(1.0, cur / need))
    return lvl, cur, need, r

def _draw_xp_strip(surface: pygame.Surface, rect: pygame.Rect, stats: dict):
    _, cur, need, r = _xp_compute(stats)
    frame   = (70, 45, 30)
    border  = (140, 95, 60)
    trough  = (46, 40, 36)
    fill    = (40, 180, 90)
    text    = (230, 220, 200)
    pygame.draw.rect(surface, frame, rect, border_radius=6)
    pygame.draw.rect(surface, border, rect, 2, border_radius=6)
    inner = rect.inflate(-8, -8)
    font = pygame.font.SysFont("georgia", max(14, int(rect.h * 0.60)), bold=False)
    label = font.render(f"XP: {cur} / {need}", True, text)
    surface.blit(label, label.get_rect(midleft=(inner.x + 6, inner.centery)))
    bar_h = max(4, int(inner.h * 0.36))
    bar_w = max(90, int(inner.w * 0.46))
    bar_x = inner.right - bar_w - 6
    bar_y = inner.centery - bar_h // 2
    bar = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
    pygame.draw.rect(surface, trough, bar, border_radius=3)
    fw = int(bar_w * r)
    if fw > 0:
        pygame.draw.rect(surface, fill, (bar_x, bar_y, fw, bar_h), border_radius=3)

# ---------------- Party helpers ----------------
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
        # (Optional) play success/fail sfx here if you add them
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

    # Text rendering (simple wrap, matches heal textbox)
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
        surf = font.render(line, False, (16, 16, 16))
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
    if auto_ms > 0 and (res["t"] * 1000.0) >= auto_ms:
        res["auto_ready"] = True

def _dismiss_result(st: dict, *, allow_exit: bool = True):
    res = st.get("result")
    if not res:
        return
    exit_on_close = bool(res.get("exit_on_close")) if allow_exit else False
    st["result"] = None
    if exit_on_close:
        st["pending_exit"] = True

def _auto_dismiss_result_if_ready(st: dict):
    res = st.get("result")
    if not res:
        return
    if res.get("auto_ms", 0) > 0 and res.get("auto_ready", False):
        exit_on_close = bool(res.get("exit_on_close"))
        st["result"] = None
        if exit_on_close:
            st["pending_exit"] = True

# ---------------- Scene bootstrap ----------------
def _clear_encounter_flags(gs):
    gs.in_encounter = False
    gs.encounter_name = ""
    gs.encounter_sprite = None
    setattr(gs, "_went_to_summoner", False)
    setattr(gs, "_went_to_wild", False)
    # Clear boss encounter flags
    if hasattr(gs, "encounter_type"):
        delattr(gs, "encounter_type")
    if hasattr(gs, "encounter_boss_data"):
        delattr(gs, "encounter_boss_data")

def _nuke_summoner_ui(gs):
    if hasattr(gs, "_summ_ui"):
        try: delattr(gs, "_summ_ui")
        except Exception: pass

def _build_initial_state(gs, preserved_bg=None, preserved_ally_pos=None, preserved_enemy_pos=None, preserved_active_idx=None):
    st = getattr(gs, "_battle", None)
    if st is None:
        gs._battle = st = {}
    if st.get("_built"):
        print(f"[_build_initial_state] WARNING: State already built! Returning existing state without rebuilding team.")
        print(f"   Current enemy_team size: {len(st.get('enemy_team', {}).get('names', []))}")
        return st

    # Team
    # Check if this is a boss encounter - use pre-generated team if available
    is_boss = getattr(gs, "encounter_type", None) == "BOSS"
    print(f"[_build_initial_state] Starting build. is_boss={is_boss}, encounter_type={getattr(gs, 'encounter_type', None)}")
    
    if is_boss:
        boss_data = getattr(gs, "encounter_boss_data", None)
        print(f"[_build_initial_state] boss_data exists: {boss_data is not None}")
        if boss_data:
            print(f"[_build_initial_state] boss_data keys: {list(boss_data.keys()) if isinstance(boss_data, dict) else 'not a dict'}")
            print(f"[_build_initial_state] team_data exists: {boss_data.get('team_data') is not None}")
            if boss_data.get("team_data"):
                team_data = boss_data["team_data"]
                print(f"[_build_initial_state] team_data type: {type(team_data)}")
                print(f"[_build_initial_state] team_data keys: {list(team_data.keys()) if isinstance(team_data, dict) else 'not a dict'}")
                if isinstance(team_data, dict):
                    team = team_data
                    print(f"🎯 Using pre-generated boss team for {boss_data.get('name', 'Boss')}")
                    print(f"   Team size: {len(team.get('names', []))} vessels")
                    print(f"   Team names: {team.get('names', [])}")
                    print(f"   Team levels: {team.get('levels', [])}")
                    print(f"   Team stats count: {len(team.get('stats', []))}")
                else:
                    team = generate_enemy_team(gs)
                    print(f"⚠️ Boss team_data is not a dict, generating normal team")
            else:
                # Fallback: generate team normally
                team = generate_enemy_team(gs)
                print(f"⚠️ Boss team data missing, generating normal team")
        else:
            team = generate_enemy_team(gs)
            print(f"⚠️ No boss_data found, generating normal team")
    else:
        team = generate_enemy_team(gs)  # {names, levels, stats}
        print(f"[_build_initial_state] Regular summoner battle - generated team size: {len(team.get('names', []))}")
    
    st["enemy_team"] = team
    print(f"[_build_initial_state] Final enemy_team size: {len(st['enemy_team'].get('names', []))}")
    print(f"[_build_initial_state] Final enemy_team structure: names={len(team.get('names', []))}, levels={len(team.get('levels', []))}, stats={len(team.get('stats', []))}")
    print(f"[_build_initial_state] Full team: {team}")
    st["enemy_idx"]  = 0  # current index on field

    # Ally - use preserved active_idx if available (from summoner_battle)
    if preserved_active_idx is not None:
        gs.combat_active_idx = preserved_active_idx
    else:
        gs.combat_active_idx = _battle_start_slot(gs)
    names = getattr(gs, "party_slots_names", None) or [None]*6
    ally_token = names[int(gs.combat_active_idx)] if names else None
    
    # Check if ally is a monster (caught monster in party)
    is_ally_monster = False
    if ally_token and ally_token.startswith("Token"):
        # Remove "Token" prefix and file extension
        base_name = os.path.splitext(ally_token)[0]  # Remove .png extension if present
        monster_name = base_name[5:] if len(base_name) > 5 else base_name  # Remove "Token" prefix
        monster_names = ["Beholder", "Dragon", "Golem", "Myconid", "Nothic", "Ogre", "Owlbear"]
        is_ally_monster = any(monster_name.startswith(m) for m in monster_names)
    
    ally_full = _ally_sprite_from_token_name(ally_token) or pygame.Surface(S.PLAYER_SIZE, pygame.SRCALPHA)
    
    # Scale ally sprite - monsters should be sized to fixed 500px height
    if is_ally_monster:
        # Monster allies: Scale to fixed height of 500 pixels
        target_height = 500
        if ally_full:
            ally_full = _smooth_scale_to_height(ally_full, target_height)
        print(f"🐉 Monster ally sprite scaled to fixed height: {target_height}px")
    else:
        # Normal vessel allies: Use ALLY_SCALE (1.0)
        ally_full = _smooth_scale(ally_full, ALLY_SCALE)

    # Enemy 0
    enemy_token = (team.get("names") or [None])[0] if isinstance(team.get("names"), list) else None
    enemy_full  = _enemy_sprite_from_token_name(enemy_token)
    if enemy_full is None:
        enemy_full = pygame.Surface(S.PLAYER_SIZE, pygame.SRCALPHA)
        enemy_full.fill((160,40,40,220))
    enemy_full = _smooth_scale(enemy_full, ENEMY_SCALE)

    # Positions - always recalculate for vessels (they may be different sizes than summoners)
    # Use logical resolution for virtual screen dimensions (not physical screen size)
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    # Calculate positions based on vessel sprite sizes (not preserved summoner positions)
    # This ensures HP bars and HUD elements are positioned correctly
    ax1 = 20 + ALLY_OFFSET[0]
    ay1 = sh - ally_full.get_height() - 20 + ALLY_OFFSET[1]
    ally_start = (ax1, ay1)
    
    ex1 = sw - enemy_full.get_width() - 20 + ENEMY_OFFSET[0]
    ey1 = 20 + ENEMY_OFFSET[1]
    enemy_start = (ex1, ey1)

    # Enemy stats & bind to gs.encounter_* (the engine expects these)
    stats_list = team.get("stats") or []
    enemy_stats = (stats_list[0] if stats_list else {}) or {}
    try:    max_hp = max(1, int(enemy_stats.get("hp", 10)))
    except: max_hp = 10
    cur_hp = enemy_stats.get("current_hp", max_hp)
    try:    cur_hp = int(cur_hp)
    except: cur_hp = max_hp
    enemy_stats["hp"] = max_hp
    enemy_stats["current_hp"] = max(0, min(cur_hp, max_hp))

    gs.encounter_stats = enemy_stats
    # Use generated name instead of token name
    from systems.name_generator import generate_vessel_name
    gs.encounter_name = generate_vessel_name(enemy_token) if enemy_token else "Enemy"
    # Store the token for later reference
    st["enemy_token"] = enemy_token

    # Background - use preserved background if available (from summoner_battle) for seamless transition
    if preserved_bg is not None:
        bg_img = preserved_bg
    else:
        bg_img = _load_bg_scaled(sw, sh)

    # Swirl frames / swap sfx
    swirl = _load_swirl_frames()
    swap_sfx = _load_swap_sfx()

    st.update({
    "_built": True,
    "t": 0.0,

    "bg": bg_img,
    "overlay": pygame.Surface((sw, sh), pygame.SRCALPHA),

    "ally_img": ally_full,
    "enemy_img": enemy_full,

    "ally_pos": [ally_start[0], ally_start[1]],
    "enemy_pos": [enemy_start[0], enemy_start[1]],
    "ally_target": (ax1, ay1),
    "enemy_target": (ex1, ey1),

    "ally_hp_ratio": 1.0,
    "enemy_hp_ratio": 1.0,
    
    # Reset Infernal Rebirth battle flag for new battle (but keep run flag)
    "infernal_rebirth_used_this_battle": False,

    # XP per-enemy (like wild_vessel)
    "pending_xp_award": None,    # tuple(outcome, enemy_name, estats, active_idx)
    "enemy_awarded_this_ko": False,


    # ⬇️ no intro fade, no slide-in
    "intro": False,
    "alpha": 0.0,
    "speed": 0.0,
    "ally_t": 1.0,
    "enemy_t": 1.0,

        # ally swapping
        "ally_from_slot": None,
        "ally_swap_target_slot": None,
        "swirl_frames": swirl,
        "swap_playing": False,
        "swap_t": 0.0,
        "dead_vessel_slot": None,  # Track which vessel died for Infernal Rebirth
        "swap_total": 0.0,
        "swap_frame": 0,
        "ally_img_next": None,
        "swap_sfx": swap_sfx,

        # enemy fade on defeat
        "enemy_fade_active": False,
        "enemy_fade_t": 0.0,
        "enemy_fade_dur": ENEMY_FADE_SEC,
        "enemy_defeated": False,

        "last_enemy_hp": int(cur_hp),
        "defeat_debounce_t": 0.0,
        "defeat_debounce_ms": 300,

        # result card
        "result": None,
        "pending_exit": False,

        # Turn/AI
        "phase": PHASE_PLAYER,
        "enemy_think_until": 0,
        "ai_started": False,

        # Forced switch
        "force_switch": False,

        # XP aggregation across whole battle
        "xp_events": [],  # list of tuples (outcome, enemy_name, estats, active_idx)
        "queued_victory": False,
    })

    # Labels
    st["enemy_label_name"]  = gs.encounter_name or "Enemy"
    st["enemy_label_level"] = int(enemy_stats.get("level", getattr(gs, "zone_level", 1)))

    enemy_names = list(team.get("names", []) or [])
    team_count = min(len(enemy_names), MAX_ENEMY_PARTY_SLOTS)
    empty_slots = ["empty"] * max(0, MAX_ENEMY_PARTY_SLOTS - team_count)
    alive_slots = ["alive"] * team_count
    st["enemy_party_status"] = empty_slots + alive_slots
    st["enemy_party_size"] = team_count
    st["enemy_party_offset"] = len(empty_slots)

    return st

def _label_from_token(token: str | None) -> str:
    if not token:
        return "Enemy"
    base = os.path.splitext(os.path.basename(token))[0]
    for p in ("StarterToken", "MToken", "FToken", "RToken"):
        if base.startswith(p):
            base = base[len(p):]
            break
    return re.sub(r"\d+$", "", base) or "Enemy"

# ---------------- Entry/Exit ----------------
def enter(gs, audio_bank=None, **_):
    # Check if battle is already active - if so, don't rebuild
    existing_battle = getattr(gs, "_battle", None)
    if existing_battle and existing_battle.get("_built"):
        print(f"[battle.enter] Battle already active, skipping rebuild. Enemy team size: {len(existing_battle.get('enemy_team', {}).get('names', []))}")
        return
    
    setattr(gs, "mode", MODE_BATTLE)
    # Don't clear boss data yet - we need it for team generation
    # We'll clear it after battle state is built
    temp_boss_type = getattr(gs, "encounter_type", None)
    temp_boss_data = getattr(gs, "encounter_boss_data", None)
    print(f"[battle.enter] Before clear: encounter_type={temp_boss_type}, boss_data exists={temp_boss_data is not None}")
    _clear_encounter_flags(gs)
    # Restore boss data temporarily
    if temp_boss_type == "BOSS":
        gs.encounter_type = temp_boss_type
        gs.encounter_boss_data = temp_boss_data
        print(f"[battle.enter] Restored boss data: encounter_type={gs.encounter_type}, boss_data keys={list(temp_boss_data.keys()) if temp_boss_data else 'None'}")
    else:
        print(f"[battle.enter] Not a boss encounter (type={temp_boss_type})")

    # Close popups just in case
    try:
        battle_action.close_popup()
        bag_action.close_popup()
        party_action.close_popup()
    except Exception:
        pass

    # Check if we're transitioning from summoner_battle - preserve state for seamless transition
    summ_ui = getattr(gs, "_summ_ui", None)
    preserve_state = summ_ui is not None
    
    # Fresh battle state so _build_initial_state doesn't reuse old data
    # BUT preserve background and positions if coming from summoner_battle
    preserved_bg = None
    preserved_ally_pos = None
    preserved_enemy_pos = None
    preserved_active_idx = None
    
    if preserve_state:
        # Preserve background and positions from summoner_battle for seamless transition
        preserved_bg = summ_ui.get("bg")
        # Use the final anchor positions (where vessels should appear)
        preserved_ally_pos = summ_ui.get("ally_anchor")
        preserved_enemy_pos = summ_ui.get("enemy_anchor")
        preserved_active_idx = summ_ui.get("active_idx")
        # Store background temporarily on gs so draw() can use it immediately (prevents black screen)
        if preserved_bg is not None:
            gs._transition_bg = preserved_bg
        # DON'T delete _summ_ui yet - let draw() delete it after first frame to ensure seamless transition
    
    # Completely clear battle state to ensure fresh build
    if hasattr(gs, "_battle"):
        try:
            delattr(gs, "_battle")
        except Exception:
            pass
    # Ensure _battle doesn't exist before building
    if hasattr(gs, "_battle"):
        delattr(gs, "_battle")

    # Dice callback not used here, but keep parity
    set_roll_callback(roll_ui._on_roll)
    bag_action.set_use_item_callback(_on_battle_use_item)  # allow heals, block capture

    # Build scene - pass preserved state if available
    # Boss data is already restored above, so _build_initial_state will use it
    boss_data_check = getattr(gs, "encounter_boss_data", None)
    print(f"[battle.enter] About to call _build_initial_state.")
    print(f"   encounter_type={getattr(gs, 'encounter_type', None)}")
    print(f"   boss_data exists={boss_data_check is not None}")
    if boss_data_check:
        print(f"   boss_data keys={list(boss_data_check.keys()) if isinstance(boss_data_check, dict) else 'not a dict'}")
        print(f"   boss_data has team_data={boss_data_check.get('team_data') is not None if isinstance(boss_data_check, dict) else 'N/A'}")
    st = _build_initial_state(gs, 
                               preserved_bg=preserved_bg,
                               preserved_ally_pos=preserved_ally_pos,
                               preserved_enemy_pos=preserved_enemy_pos,
                               preserved_active_idx=preserved_active_idx)

    # Now clear boss flags after state is built
    if hasattr(gs, "encounter_type"):
        delattr(gs, "encounter_type")
    if hasattr(gs, "encounter_boss_data"):
        delattr(gs, "encounter_boss_data")

    # 👉 Alias for systems (moves/btn/resolve) that write to gs._wild
    gs._wild = st

    # Turn order
    try:
        turn_order.determine_order(gs)
    except Exception:
        pass
    gs._turn_ready = True

    # make sure party XP fields are sane for this run
    try:
        xp_sys.ensure_profile(gs)
    except Exception:
        pass



def _exit_battle(gs):
    # Check if we should trigger score animation (summoner battle victory)
    st = getattr(gs, "_battle", None)
    trigger_animation = False
    start_score = 0
    target_score = 0
    was_summoner_battle = False
    
    if st and st.get("_trigger_score_animation", False):
        trigger_animation = True
        start_score = st.get("_score_animation_start", 0)
        target_score = st.get("_score_animation_target", 0)
        was_summoner_battle = True
    
    # Check for buff selection trigger (100% for testing, normally 10%)
    if was_summoner_battle:
        # 20% chance to get a buff selection after battle
        trigger_buff = random.random() < 0.20  # 20% chance
        if trigger_buff:
            # Set flag to start buff popup in overworld
            gs.pending_buff_selection = True
            # Store score animation data but don't start it yet (will start after buff selection)
            if trigger_animation:
                gs.pending_score_animation = True
                gs.pending_score_start = start_score
                gs.pending_score_target = target_score
                trigger_animation = False  # Don't start animation now
    
    keep_music = getattr(gs, "_keep_boss_music", False)
    if keep_music and hasattr(gs, "_keep_boss_music"):
        try:
            delattr(gs, "_keep_boss_music")
        except Exception:
            pass
    if not keep_music:
        try:
            pygame.mixer.music.fadeout(300)
        except Exception:
            pass

    pre = getattr(gs, "_precombat_active_idx", None)
    if pre is None:
        pre = _first_filled_slot_index(gs)
    gs.party_active_idx = int(pre)

    if hasattr(gs, "combat_active_idx"):
        delattr(gs, "combat_active_idx")
    if hasattr(gs, "_pending_party_switch"):
        try:
            delattr(gs, "_pending_party_switch")
        except Exception:
            pass

    _nuke_summoner_ui(gs)

    gs._went_to_wild = False
    gs.in_encounter = False
    gs.encounter_stats = None

    # 👉 Clean up alias & battle blob so new encounters start fresh
    if hasattr(gs, "_wild"):
        try:
            delattr(gs, "_wild")
        except Exception:
            pass
    if hasattr(gs, "_battle"):
        try:
            delattr(gs, "_battle")
        except Exception:
            pass

    # (Optional) clear any move resolution queues if your moves module supports it
    try:
        if hasattr(moves, "reset"):
            moves.reset()
    except Exception:
        pass

    set_roll_callback(None)
    
    # Check if we came from tavern - if so, return to tavern instead of overworld
    from_tavern = getattr(gs, "_from_tavern", False)
    if from_tavern:
        # Clear the flag
        gs._from_tavern = False
        # Return to tavern mode
        next_mode = "TAVERN"
        setattr(gs, "mode", next_mode)
    else:
        # Normal exit to overworld
        next_mode = MODE_GAME
        setattr(gs, "mode", next_mode)

    if hasattr(gs, "_ending_battle"):
        delattr(gs, "_ending_battle")
    
    # Trigger score animation if this was a summoner battle victory
    # BUT only if buff selection is NOT pending (otherwise it will start after buff selection)
    if trigger_animation and not getattr(gs, "pending_buff_selection", False):
        from systems import score_display
        score_display.start_score_animation(gs, start_score, target_score)
    
    return next_mode

def _on_battle_use_item(gs, item) -> bool:
    """Authoritative bag use handler (heals only; capture blocked)."""
    def _norm_item_id(it) -> str:
        s = (str(it.get("id") or it.get("name") or "")).strip().lower()
        return s.replace(" ", "_")

    iid = _norm_item_id(item)

    HEAL = {
        "scroll_of_mending":      {"kind": "heal", "dice": (1, 4), "add_con": True,  "revive": False},
        "scroll_of_regeneration": {"kind": "heal", "dice": (2, 8), "add_con": True,  "revive": False},
        "scroll_of_revivity":     {"kind": "heal", "dice": (2, 8), "add_con": False, "revive": True},
    }
    CAPTURE = {
        "scroll_of_command", "scroll_of_sealing", "scroll_of_subjugation", "scroll_of_eternity"
    }

    # Handle healing
    if iid in HEAL:
        from screens import party_manager
        # Prevent double consumption
        if not getattr(gs, "_item_consumed", False):
            mode = dict(HEAL[iid])
            mode["consume_id"] = iid  # Consume the item here
            party_manager.start_use_mode(mode)
            bag_action.close_popup()

            # Flag the item as consumed to prevent double consumption
            gs._item_consumed = True
            return True  # Item handled, no further actions needed

    # Handle capture prevention in summoner battles
    if iid in CAPTURE:
        st = getattr(gs, "_battle", None)
        if st is not None and not st.get("result"):
            _show_result_screen(st, "Cannot Use", "You can't bind a Summoner's Vessel.", kind="fail", auto_dismiss_ms=1100)
        bag_action.close_popup()
        return True  # Handled successfully

    return False  # If not handled, leave the bag popup open

def reset_item_consumption(gs):
    """Call this method at the end of each turn or after item use is resolved."""
    if hasattr(gs, "_item_consumed"):
        del gs._item_consumed



# ---------------- Phase helpers ----------------
def _begin_player_phase(st: dict):
    st["phase"] = PHASE_PLAYER
    try:
        battle_action.close_popup(); bag_action.close_popup(); party_action.close_popup()
    except Exception: pass
    st["ai_started"] = False

def _begin_resolving_phase(st: dict):
    st["phase"] = PHASE_RESOLVE
    try:
        battle_action.close_popup(); bag_action.close_popup(); party_action.close_popup()
    except Exception: pass

def _begin_enemy_phase(st: dict):
    st["phase"] = PHASE_ENEMY
    st["ai_started"] = False
    st["enemy_think_until"] = pygame.time.get_ticks() + 500
    try:
        battle_action.close_popup(); bag_action.close_popup(); party_action.close_popup()
    except Exception: pass

# ---------------- Forced switch helpers ----------------
def _trigger_forced_switch_if_needed(gs, st):
    # Active stats
    idx = _get_active_party_index(gs)
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    cur = 0; maxhp = 0
    if 0 <= idx < len(stats) and isinstance(stats[idx], dict):
        cur = int(stats[idx].get("current_hp", stats[idx].get("hp", 0)))
        maxhp = int(stats[idx].get("hp", 0))
    
    # Store which vessel died so we can revive it after the swap
    if cur <= 0 and not st.get("force_switch", False) and not st.get("swap_playing", False):
        # Store the dead vessel slot so we can revive it after swap
        st["dead_vessel_slot"] = idx
    
    # KO?
    if cur <= 0 and not st.get("force_switch", False) and not st.get("swap_playing", False):
        if not _has_living_party(gs):
            _show_result_screen(st, "All vessels are down!", "You can't continue.", kind="fail", exit_on_close=True)
            st["pending_exit"] = True
            return
        st["force_switch"] = True
        setattr(gs, "_force_switch", True)
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
    has_demonpact2 = False
    for buff in active_buffs:
        if isinstance(buff, dict):
            buff_id = buff.get("id")
            buff_tier = buff.get("tier", "")
            buff_name = buff.get("name", "")
            # Check both "DemonPact2" (full name) and 2/"2" (just the ID) with tier "DemonPact"
            # The ID is stored as an integer (2) or string ("2"), not "DemonPact2"
            # Also check the name field which should be "DemonPact2"
            if (buff_id == "DemonPact2" or buff_name == "DemonPact2" or 
                (buff_tier == "DemonPact" and (buff_id == 2 or buff_id == "2"))):
                has_demonpact2 = True
                break
    
    if not has_demonpact2:
        print(f"[_try_revive_dead_vessel_with_infernal_rebirth] DemonPact2 not found in active buffs")
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
            setattr(gs, "_force_switch", False)
            st["phase"] = PHASE_PLAYER
            
            # After forced switch completes, check if we should revive the dead vessel with Infernal Rebirth
            dead_slot = st.get("dead_vessel_slot")
            if dead_slot is not None:
                _try_revive_dead_vessel_with_infernal_rebirth(gs, st, dead_slot)
                # Clear the dead vessel slot after checking
                st["dead_vessel_slot"] = None
            gs._turn_ready = True
            try:
                party_action.close_popup()
            except Exception:
                pass

# ---------------- Enemy rotation (NEXT SUMMON) ----------------
def _advance_to_next_enemy(gs, st):
    team = st.get("enemy_team") or {}
    names = team.get("names") or []
    stats = team.get("stats") or []
    prev_idx = int(st.get("enemy_idx", 0))
    _set_enemy_party_slot_status(st, prev_idx, "dead")
    idx   = prev_idx + 1

    if idx >= len(names) or idx >= len(stats):
        st["suppress_enemy_draw"] = True
        _finalize_battle_xp(gs, st)
        return

    # Load next enemy sprite
    token = names[idx]
    surf  = _enemy_sprite_from_token_name(token)
    if surf is None:
        surf = pygame.Surface(S.PLAYER_SIZE, pygame.SRCALPHA)
        surf.fill((160, 40, 40, 220))
    surf = _smooth_scale(surf, ENEMY_SCALE)

    # Bind encounter_* for the engine
    est = stats[idx] or {}
    try:    max_hp = max(1, int(est.get("hp", 10)))
    except: max_hp = 10
    cur_hp = est.get("current_hp", max_hp)
    try:    cur_hp = int(cur_hp)
    except: cur_hp = max_hp
    est["hp"] = max_hp
    est["current_hp"] = max(0, min(cur_hp, max_hp))
    gs.encounter_stats = est
    # Use generated name instead of token name
    from systems.name_generator import generate_vessel_name
    gs.encounter_name = generate_vessel_name(token) if token else "Enemy"
    # Store the token for later reference
    st["enemy_token"] = token

    # Reset flags & slide-in animation for enemy
    # Use logical resolution for virtual screen dimensions (not physical screen size)
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    ex1 = sw - surf.get_width() - 20 + ENEMY_OFFSET[0]
    ey1 = 20 + ENEMY_OFFSET[1]
    enemy_start = (sw + 60, ey1)

    st["enemy_idx"] = idx
    st["enemy_img"] = surf
    st["enemy_pos"] = list(enemy_start)
    st["enemy_target"] = (ex1, ey1)
    st["enemy_t"] = 0.0
    st["intro"] = False  # keep ally static
    st["enemy_fade_active"] = False
    st["enemy_fade_t"] = 0.0
    st["enemy_defeated"] = False
    st["defeat_debounce_t"] = 0.0
    st["last_enemy_hp"] = int(est["current_hp"])

    st["enemy_label_name"]  = gs.encounter_name or "Enemy"
    st["enemy_label_level"] = int(est.get("level", getattr(gs, "zone_level", 1)))

    # allow next KO to award again
    st["enemy_awarded_this_ko"] = False
    

def _finalize_battle_xp(gs, st):
    """
    When the battle ends, ensure any pending XP award is shown first.
    After the XP card is dismissed, show the Victory card and exit.
    """
    # If there's an XP award pending and no modal is currently blocking,
    # show XP first and remember to show Victory afterwards.
    if st.get("pending_xp_award") and not st.get("result"):
        st["queued_victory"] = True
        _maybe_show_xp_award(gs, st)
        return

    # If we're here while an XP result is up, just mark that Victory is next.
    if st.get("result") and st.get("pending_xp_award"):
        st["queued_victory"] = True
        return

    # No XP pending (or XP already shown and dismissed) — show Victory now.
    st["enemy_img"] = None
    st["enemy_fade_active"] = False
    st["enemy_hp_ratio"] = 0.0
    gs.encounter_stats = {}
    st["enemy_label_name"] = ""
    st["suppress_enemy_draw"] = True
    gs._ending_battle = True

    # Calculate and award points for this summoner battle
    points_sys.ensure_points_field(gs)
    enemy_team = st.get("enemy_team", {})
    start_score = points_sys.get_total_points(gs)  # Score before awarding
    points_earned = points_sys.award_points(gs, enemy_team)
    total_points = points_sys.get_total_points(gs)  # Score after awarding
    
    # Store scores for score animation (will be triggered on exit)
    st["_score_animation_start"] = start_score
    st["_score_animation_target"] = total_points
    st["_trigger_score_animation"] = True
    
    # Calculate and award currency for this summoner battle
    from systems import currency as currency_sys
    currency_sys.ensure_currency_fields(gs)
    gold_earned, silver_earned, bronze_earned = currency_sys.award_currency(gs, enemy_team)
    currency_display = currency_sys.format_currency(gold_earned, silver_earned, bronze_earned)
    
    # Determine difficulty tier for display
    from combat.team_randomizer import highest_party_level
    player_level = highest_party_level(gs)
    enemy_levels = enemy_team.get("levels", [])
    avg_enemy_level = int(round(sum(enemy_levels) / len(enemy_levels))) if enemy_levels else player_level
    level_diff = avg_enemy_level - player_level
    tier_name = points_sys.get_points_tier_name(level_diff)
    
    # Build victory message with points and currency
    victory_msg = f"All enemies defeated.\n\nPoints Earned: {points_earned:,} ({tier_name})\nTotal Points: {total_points:,}\n\nCurrency Earned: {currency_display}"
    
    # Mark boss as defeated if this was a boss encounter
    is_boss = getattr(gs, "encounter_type", None) == "BOSS"
    if is_boss:
        boss_data = getattr(gs, "encounter_boss_data", None)
        if boss_data:
            score_threshold = boss_data.get("score_threshold", 0)
            if score_threshold > 0:
                from world import bosses
                bosses.mark_boss_defeated(gs, score_threshold)
                print(f"🏆 Boss at score {score_threshold} marked as defeated")
    
    _show_result_screen(st, "Victory!", victory_msg, kind="success", exit_on_close=True)
    st["pending_exit"] = True

    # Clear any queued XP defensively
    st["xp_events"] = []




# ---------------- Handle ----------------
def handle(events, gs, dt=None, **_):
    st = getattr(gs, "_battle", None)
    if st is None or not st.get("_built"):
        enter(gs); st = gs._battle
    
    # NEW: per-handle guard so the enemy AI can only fire once per tick
    st["_ai_fired_this_handle"] = False

    # --- Let Party Manager consume events first (strip handled ones) ---
    # Handle heal textbox first (it's modal and works even when party manager is closed)
    if party_manager.is_heal_textbox_active():
        for e in events:
            party_manager.handle_event(e, gs)  # This will handle dismissal
            # If textbox was dismissed, stop processing events
            if not party_manager.is_heal_textbox_active():
                break
        # Clear all events - textbox is modal
        return None
    
    if party_manager.is_open():
        remaining = []
        for e in events:
            if not party_manager.handle_event(e, gs):
                remaining.append(e)
        events = remaining

    # Exit queued? (only if no modal result is visible)
    if st.get("pending_exit") and not st.get("result"):
        next_mode = _exit_battle(gs)
        return next_mode

    # Dice popup is modal (kept for parity)
    if roll_ui.is_active():
        for e in events:
            roll_ui.handle_event(e)
        if not roll_ui.is_active():
            # 👉 Make sure the alias exists right now
            if getattr(gs, "_wild", None) is None and getattr(gs, "_battle", None):
                gs._wild = gs._battle

            mode = run_action.resolve_after_popup(gs)
            if mode is not None:
                return mode
        return None

    # Clear auto-done result cards
    _auto_dismiss_result_if_ready(st)

    # 👉 If no modal result is visible now, process any queued XP award
    if not st.get("result"):
        _maybe_show_xp_award(gs, st)
    
    # If we were waiting to show Victory until after XP, and the XP card is gone, show it now.
    if not st.get("result") and st.get("queued_victory") and not st.get("pending_xp_award"):
        st["queued_victory"] = False
        _finalize_battle_xp(gs, st)

    # KO → forced switch?
    _trigger_forced_switch_if_needed(gs, st)

    # ===== INPUT ROUTING =====
    if st.get("force_switch", False):
        try:
            selection_committed = getattr(gs, "_pending_party_switch", None) is not None
            if (not st.get("swap_playing", False)) and (not selection_committed):
                if not party_action.is_open():
                    party_action.open_popup()
        except Exception:
            pass

        res = st.get("result")
        if res and not res.get("lock_input", False):
            for e in events:
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    _dismiss_result(st, allow_exit=False)
                    break

        for e in events:
            if party_action.is_open() and party_action.handle_event(e, gs):
                return None
        return None

    # Normal routing when not forced and not in enemy phase
    if st.get("phase") != PHASE_ENEMY:
        for e in events:
            if st.get("enemy_fade_active", False):
                return None

            res = st.get("result")
            if res:
                if res.get("lock_input", False) or res.get("auto_ms", 0) > 0:
                    return None
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    _dismiss_result(st, allow_exit=True)
                    return None

            if st.get("phase") == PHASE_PLAYER:
                if party_action.is_open() and party_action.handle_event(e, gs):  return None
                if bag_action.is_open()   and bag_action.handle_event(e, gs):    return None
                if battle_action.is_open()and battle_action.handle_event(e, gs): return None

                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    # Only allow ESC when battle already concluded (result shown)
                    if st.get("pending_exit") or st.get("result"):
                        next_mode = _exit_battle(gs)
                        return next_mode

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
        if (getattr(gs, "_turn_ready", True) is False or resolving_moves) and not party_manager.is_open():
            _begin_resolving_phase(st)
            # one-shot the item flag so we don't double-advance this tick
            try:
                gs._turn_consumed_by_item = False
            except Exception:
                pass


    scene_busy = (
        st.get("result") or st.get("enemy_fade_active")
        or st.get("swap_playing") or roll_ui.is_active()
        or party_manager.is_heal_textbox_active()  # Block enemy turn while heal textbox is showing
    )

    if st.get("phase") == PHASE_RESOLVE and not resolving_moves and not scene_busy:
        try:
            turn_order.next_turn(gs)
        except Exception:
            pass
        _begin_enemy_phase(st)

    if st.get("phase") == PHASE_ENEMY:
        now = pygame.time.get_ticks()
        if (not st.get("ai_started")
            and now >= int(st.get("enemy_think_until", 0))
            and not resolving_moves
            and not scene_busy
            and not party_manager.is_open()                    # ← block AI while picker is up
            and not st.get("_ai_fired_this_handle", False)):  # per-tick guard
            try:
                enemy_ai.take_turn(gs)
            except Exception as _e:
                print(f"⚠️ enemy_ai failure: {_e}")

            # 👉 Mirror wild_vessel: play move SFX ...
            try:
                lbl = st.pop("last_enemy_move_label", None) or getattr(gs, "_last_enemy_move_label", None)
                if lbl:
                    moves._play_move_sfx(lbl)
            except Exception as _e:
                print(f"⚠️ enemy move sfx fallback error: {_e}")

            st["ai_started"] = True
            st["_ai_fired_this_handle"] = True  # NEW: ensure only once this tick


        if st.get("ai_started") and not resolving_moves and not scene_busy:
            try:
                if turn_order.current_actor(gs) != "player":
                    turn_order.next_turn(gs)
            except Exception:
                pass
            gs._turn_ready = True
            _begin_player_phase(st)

    return None


# ---------------- Draw ----------------
def draw(screen: pygame.Surface, gs, dt: float, **_):
    # CRITICAL: Draw background IMMEDIATELY to prevent black screen on transition
    # Check multiple sources for background (in order of preference)
    immediate_bg = None
    
    # First, try _transition_bg (stored by enter())
    immediate_bg = getattr(gs, "_transition_bg", None)
    
    # If not available, try _summ_ui (might still exist if not deleted yet)
    if immediate_bg is None:
        summ_ui = getattr(gs, "_summ_ui", None)
        if summ_ui is not None:
            immediate_bg = summ_ui.get("bg")
    
    # If we have immediate background, draw it right away before any state checks
    if immediate_bg is not None:
        screen.blit(immediate_bg, (0, 0))
    
    # --- RE-ENTRY GUARD: don't rebuild battle while ending/after result ---
    st = getattr(gs, "_battle", None)

    # If there's no battle blob but we're ending (or not even in battle mode),
    # BUT if we have a transition background, still draw it before returning
    if st is None:
        if getattr(gs, "_ending_battle", False) or getattr(gs, "mode", None) != MODE_BATTLE:
            # Still draw background if available (for smooth transitions)
            if immediate_bg is None:
                return
            # Background already drawn above, just return
            return
        enter(gs); st = gs._battle
    elif not st.get("_built"):
        # Blob exists but wasn't fully built; during result/exit just skip.
        if st.get("pending_exit") or st.get("result") or st.get("suppress_enemy_draw"):
            # Still draw background if available (for smooth transitions)
            if immediate_bg is None:
                return
            # Background already drawn above, just return
            return
        enter(gs); st = gs._battle
    # ----------------------------------------------------------------------

    st["t"] = st.get("t", 0.0) + dt

    # Background - only draw if we didn't already draw the immediate background
    if immediate_bg is None:
        sw, sh = screen.get_size()
        bg = st.get("bg")
        if bg is None or bg.get_width() != sw or bg.get_height() != sh:
            bg = _load_bg_scaled(sw, sh)
            st["bg"] = bg
        if bg is not None:
            screen.blit(bg, (0, 0))
        else:
            screen.fill((0, 0, 0))
    else:
        # Clean up transition background and _summ_ui after first use
        try:
            delattr(gs, "_transition_bg")
        except Exception:
            pass
        # Now safe to clean up _summ_ui after we've used the background
        if hasattr(gs, "_summ_ui"):
            try:
                delattr(gs, "_summ_ui")
            except Exception:
                pass

    # Ally slot tracking + swap animation setup
    active_i = _get_active_party_index(gs)
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    stats = getattr(gs, "party_vessel_stats", None) or [None] * 6
    active_name = names[active_i]
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
                        target_height = 500
                        st["ally_img"] = _smooth_scale_to_height(ally_sprite, target_height)
                    else:
                        st["ally_img"] = _smooth_scale(ally_sprite, ALLY_SCALE)
                else:
                    # Fallback to asset_links
                    vessel_png = token_to_vessel(active_name) or active_name
                    path = find_image(vessel_png) or find_image(active_name)
                    if path and os.path.exists(path):
                        loaded = pygame.image.load(path).convert_alpha()
                        if is_active_monster:
                            target_height = 500
                            st["ally_img"] = _smooth_scale_to_height(loaded, target_height)
                        else:
                            st["ally_img"] = _smooth_scale(loaded, ALLY_SCALE)
            except Exception:
                pass
    elif st["ally_from_slot"] != active_i and active_name and not st.get("swap_playing", False):
        try:
            # Try loading via _ally_sprite_from_token_name first (handles monsters)
            ally_sprite = _ally_sprite_from_token_name(active_name)
            if ally_sprite:
                if is_active_monster:
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
                except Exception:
                    pass
            else:
                # Fallback to asset_links
                vessel_png = token_to_vessel(active_name) or active_name
                path = find_image(vessel_png) or find_image(active_name)
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
                    except Exception:
                        pass
        except Exception:
            pass

    # Ally HP ratio
    if isinstance(active_stats, dict):
        maxhp = max(1, int(active_stats.get("hp", 10)))
        curhp = max(0, min(int(active_stats.get("current_hp", maxhp)), maxhp))
        st["ally_hp_ratio"] = curhp / maxhp
    else:
        st["ally_hp_ratio"] = 1.0

    # Enemy HP ratio from gs.encounter_stats
    estats = getattr(gs, "encounter_stats", None) or {}
    e_cur, e_max = _parse_enemy_hp_fields(estats, ratio_fallback=st.get("enemy_hp_ratio", 1.0))
    st["enemy_hp_ratio"] = (e_cur / e_max) if e_max > 0 else 1.0
    # Store enemy HP values for HP text display
    st["enemy_cur_hp"] = int(e_cur)
    st["enemy_max_hp"] = int(e_max)

    # Slide-in easing
    st["ally_t"] = min(1.0, st.get("ally_t", 0.0) + dt / max(0.001, SUMMON_TIME))
    if st.get("intro", False):
        st["enemy_t"] = min(1.0, st.get("enemy_t", 0.0) + dt / max(0.001, SUMMON_TIME))
    else:
        st["enemy_t"] = min(1.0, st.get("enemy_t", 0.0) + dt / max(0.001, SUMMON_TIME))
    ally_ease = 1.0 - (1.0 - st["ally_t"]) ** 3
    enemy_ease = 1.0 - (1.0 - st["enemy_t"]) ** 3
    ax0, ay0 = st["ally_pos"];   ax1, ay1 = st["ally_target"]
    ex0, ey0 = st["enemy_pos"];  ex1, ey1 = st["enemy_target"]
    ax = int(ax0 + (ax1 - ax0) * ally_ease);  ay = int(ay0 + (ay1 - ay0) * ally_ease)
    ex = int(ex0 + (ex1 - ex0) * enemy_ease); ey = int(ey0 + (ey1 - ey0) * enemy_ease)

    # Draw sprites
    ally = st.get("ally_img")
    if ally is not None:
        screen.blit(ally, (ax, ay))
    
    # Draw heal animation over active vessel (if healing animation is active)
    # Reset flag when animation stops (outside the draw function)
    if not party_manager.is_heal_animation_active():
        if hasattr(_draw_heal_animation, '_was_active'):
            _draw_heal_animation._was_active = False
            _heal_anim_timer = 0.0
    
    if party_manager.is_heal_animation_active():
        _draw_heal_animation(screen, ax, ay, ally, dt)
    
    # (Enemy is drawn later in the fade/draw block)

    # Only suppress enemy visuals when we're actually ending the battle
    suppress_enemy = bool(st.get("pending_exit") or st.get("suppress_enemy_draw"))

    # HP bars + labels
    bar_w, bar_h = 420, 74
    ally_img_w = ally.get_width() if ally else 0
    ally_img_h = ally.get_height() if ally else 0
    ally_bar = pygame.Rect(ax + (ally_img_w // 2) - (bar_w // 2), ay + ally_img_h + 12, bar_w, bar_h)
    enemy_bar = pygame.Rect(ex - bar_w - 24, ey + 12, bar_w, bar_h)

    # Ally label
    ally_lv = 1
    if isinstance(active_stats, dict):
        try:
            ally_lv = int(active_stats.get("level", 1))
        except Exception:
            ally_lv = 1
    ally_name = _pretty_name_from_token(active_name) if active_name else "Ally"
    ally_label = f"{ally_name}  lvl {ally_lv}"

    # Enemy label
    try:
        enemy_lv = int(st.get("enemy_label_level", getattr(gs, "zone_level", 1)))
    except Exception:
        enemy_lv = getattr(gs, "zone_level", 1)
    enemy_label = f"{st.get('enemy_label_name','Enemy')}  lvl {enemy_lv}"

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
    if isinstance(active_stats, dict):
        xp_h = 22
        # XP strip position (HP text is now on top, so no adjustment needed)
        xp_rect = pygame.Rect(ally_bar.x, ally_bar.bottom + 6, ally_bar.w, xp_h)
        _draw_xp_strip(screen, xp_rect, active_stats)

    # Gate enemy HP bar by suppression too
    if st.get("enemy_img") is not None and not suppress_enemy:
        # Get enemy HP values for display
        enemy_cur_hp = st.get("enemy_cur_hp")
        enemy_max_hp = st.get("enemy_max_hp")
        _draw_hp_bar(screen, enemy_bar, st.get("enemy_hp_ratio", 1.0), enemy_label, "right",
                     current_hp=enemy_cur_hp, max_hp=enemy_max_hp)
        _draw_enemy_party_icons(screen, enemy_bar, st)

    # Track last enemy hp
    st["last_enemy_hp"] = int(e_cur)

    # Enemy KO debounce & fade, enqueue XP and rotate
    try:
        moves_busy = bool(moves.is_resolving())
    except Exception:
        moves_busy = False

    # Play victory music immediately when last enemy HP hits 0
    if (e_cur <= 0 and st.get("enemy_img") is not None and
        not st.get("victory_music_played", False) and
        not st.get("result", None) and
        not suppress_enemy):
        # Check if this is the last enemy
        team = st.get("enemy_team") or {}
        names = team.get("names") or []
        current_idx = int(st.get("enemy_idx", 0))
        is_last_enemy = (current_idx + 1 >= len(names))
        
        if is_last_enemy:
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
        not st.get("result", None) and
        not st.get("enemy_defeated", False) and
        not moves_busy and
        not suppress_enemy  # ← don't run KO/fade logic when ending the battle
    )
    if should_consider_ko:
        st["defeat_debounce_t"] = st.get("defeat_debounce_t", 0.0) + dt
        if (st["defeat_debounce_t"] * 1000.0) >= int(st.get("defeat_debounce_ms", 300)):
            st["enemy_fade_active"] = True
            st["enemy_fade_t"] = 0.0
            st["enemy_defeated"] = True
            current_idx = int(st.get("enemy_idx", 0))
            _set_enemy_party_slot_status(st, current_idx, "dead")
            active_idx = _get_active_party_index(gs)
            if not st.get("enemy_awarded_this_ko", False) and not st.get("pending_xp_award"):
                st["pending_xp_award"] = (
                    "defeat",
                    gs.encounter_name or "Enemy",
                    dict(gs.encounter_stats or {}),   # snapshot now
                    int(active_idx),
                )
                # Removed debug spam: print("[battle] queued XP award:", st["pending_xp_award"])
                st["enemy_awarded_this_ko"] = True
    else:
        if e_cur > 0 or moves_busy:
            st["defeat_debounce_t"] = 0.0

    # Enemy fade & draw — completely suppressed during result/exit
    if st.get("enemy_img") and not suppress_enemy:
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

                # make sure an award exists for this KO
                if not st.get("pending_xp_award") and not st.get("enemy_awarded_this_ko", False):
                    active_idx = _get_active_party_index(gs)
                    estats = dict(getattr(gs, "encounter_stats", {}) or {})
                    enemy_name = gs.encounter_name or "Enemy"
                    st["pending_xp_award"] = ("defeat", enemy_name, estats, int(active_idx))
                    # Removed debug spam: print("[battle] queued XP award (post-fade safety):", st["pending_xp_award"])
                    st["enemy_awarded_this_ko"] = True

                if not suppress_enemy:
                    _advance_to_next_enemy(gs, st)


        else:
            screen.blit(enemy_surface, (ex, ey))

    # Ally swap VFX
    if st.get("swap_playing", False):
        frames = st.get("swirl_frames") or []
        if not frames:
            if st.get("ally_img_next"):
                st["ally_img"] = st["ally_img_next"]
            st["ally_img_next"] = None
            st["ally_from_slot"] = st.get("ally_swap_target_slot", st.get("ally_from_slot"))
            st["ally_swap_target_slot"] = None
            st["swap_playing"] = False
            # After swap completes, check for Infernal Rebirth revival
            _finish_forced_switch_if_done(gs, st)
            # Also check for revival after any swap (not just forced switches)
            dead_slot = st.get("dead_vessel_slot")
            if dead_slot is not None:
                _try_revive_dead_vessel_with_infernal_rebirth(gs, st, dead_slot)
                st["dead_vessel_slot"] = None
        else:
            st["swap_t"] = st.get("swap_t", 0.0) + dt
            st["swap_total"] = st.get("swap_total", 0.0) + dt
            vis_index = int(st["swap_t"] * SWIRL_VIS_FPS) % len(frames)
            st["swap_frame"] = vis_index
            idx = min(st["swap_frame"], len(frames) - 1)
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
                if st.get("ally_img_next"):
                    st["ally_img"] = st["ally_img_next"]
                st["ally_img_next"] = None
                st["ally_from_slot"] = st.get("ally_swap_target_slot", st.get("ally_from_slot"))
                st["ally_swap_target_slot"] = None
                st["swap_playing"] = False
                _finish_forced_switch_if_done(gs, st)

    # Scene fade overlay (intro)
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

    # Result screen (over UI, under dice)
    if st.get("result"):
        _draw_result_screen(screen, st, dt)

    # Dice popup (kept on top)
    roll_ui.draw_roll_popup(screen, dt)

    # Party Manager overlay (very top) - always draw to show heal textbox if active
    party_manager.draw(screen, gs, dt)

    # Tiny label
    try:
        font = pygame.font.SysFont("arial", 18, bold=False)
    except Exception:
        font = pygame.font.Font(None, 18)
    label = font.render("Summoner Battle — Team Mode (WIP) — auto-summon next", True, (180, 180, 180))
    # Use logical resolution for virtual screen dimensions
    screen.blit(label, label.get_rect(midbottom=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT - 8)))

# ---------------- Enemy party HUD assets ----------------
MAX_ENEMY_PARTY_SLOTS = 6
ENEMY_PARTY_ICON_SIZE = 48
ENEMY_PARTY_ICON_SPACING = 10
_enemy_party_icon_cache: dict[str, pygame.Surface] = {}


def _create_silhouette(surface: pygame.Surface | None) -> pygame.Surface | None:
    """Return a black silhouette of the provided surface, preserving alpha."""
    if surface is None:
        return None
    result = surface.copy()
    blackout = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    blackout.fill((0, 0, 0, 255))
    result.blit(blackout, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    return result


def _load_enemy_party_icon(kind: str) -> pygame.Surface | None:
    kind_key = kind.lower()
    cached = _enemy_party_icon_cache.get(kind_key)
    if cached is not None:
        return cached

    base_path = os.path.join("Assets", "Items", "Scroll_Of_Sealing.png")
    grey_path = os.path.join("Assets", "Items", "Scroll_Of_Sealing_Grey.png")

    surf: pygame.Surface | None = None
    if kind_key == "alive":
        surf = _try_load(base_path)
    elif kind_key == "dead":
        surf = _try_load(grey_path) or _try_load(base_path)
    elif kind_key == "empty":
        base = _try_load(base_path)
        surf = _create_silhouette(base) if base else None
    else:
        surf = _try_load(base_path)

    if surf is not None:
        surf = pygame.transform.smoothscale(
            surf, (ENEMY_PARTY_ICON_SIZE, ENEMY_PARTY_ICON_SIZE)
        )
        _enemy_party_icon_cache[kind_key] = surf

    return surf


def _set_enemy_party_slot_status(st: dict, slot_index: int, status: str) -> None:
    slots = st.get("enemy_party_status")
    if not isinstance(slots, list):
        return
    offset = int(st.get("enemy_party_offset", 0))
    target = offset + slot_index
    if 0 <= target < len(slots):
        slots[target] = status


def _draw_enemy_party_icons(surface: pygame.Surface, enemy_bar: pygame.Rect, st: dict) -> None:
    statuses = st.get("enemy_party_status")
    if not isinstance(statuses, list) or not statuses:
        return

    icons: list[pygame.Surface | None] = []
    for status in statuses:
        icons.append(_load_enemy_party_icon(status or "empty"))

    if not icons:
        return

    total_slots = len(icons)
    total_width = (
        ENEMY_PARTY_ICON_SIZE * total_slots
        + ENEMY_PARTY_ICON_SPACING * (total_slots - 1)
    )

    start_x = enemy_bar.centerx - total_width // 2
    y = enemy_bar.bottom + 8

    for icon in icons:
        if icon is not None:
            surface.blit(icon, (start_x, y))
        start_x += ENEMY_PARTY_ICON_SIZE + ENEMY_PARTY_ICON_SPACING
