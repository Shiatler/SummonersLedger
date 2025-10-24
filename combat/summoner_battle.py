# ============================================================
# combat/summoner_battle.py — Summoner vs Summoner (FULL MERGE)
#
# Flow (kept from your original file):
#   1) Summoners slide in + textbox: "You are challenged by Summoner <Name>!"
#   2) On confirm (Enter/Space/Left-click) they slide out.
#   3) Swirl VFX + SFX, then swap to vessels:
#        • Ally uses first living vessel from your party (wild_vessel logic)
#        • Enemy uses the staged vessel from systems.enemy_party (exact M/F + index)
#
# After the VFX:
#   • Switch into the integrated battle engine (parity with wild_vessel):
#       - Turn phases: PLAYER_TURN -> RESOLVING -> ENEMY_TURN (500 ms think)
#       - Modal dice popup (rolling.ui) consumes input first
#       - HP bars + XP strip (ally only)
#       - Ally KO -> forced Party popup until a living swap is chosen
#       - Enemy defeat -> fade, then Experience Gained card, then exit
#       - Result cards (info/success/fail) with fade & optional auto-dismiss
#   • No capture / no run in summoner battles (by design)
#
# Notes:
#   • While the intro textbox is visible, inputs are blocked.
#   • Battle UI shows vessel names only (never Token), preserving gender/index.
#   • On exit, pending enemy party cache is cleared.
# ============================================================

from __future__ import annotations
import os, re, glob, random
import pygame
import settings as S

from systems import audio as audio_sys
from systems import xp as xp_sys
from combat.btn import battle_action, bag_action, party_action
from rolling import ui as roll_ui
from rolling.roller import set_roll_callback
from systems.enemy_party import generate_enemy_party
from systems.asset_links import token_to_vessel, find_image
from combat.helpers import _enemy_party_has_living, _trigger_forced_switch_if_needed

from combat import moves
from combat import turn_order
from combat import enemy_ai

# ---------- Layout & tween tunables ----------
SUMMON_TIME        = 0.60
SLIDE_AWAY_TIME    = 0.60

ALLY_OFFSET        = (290, -140)
ENEMY_OFFSET       = (-400, 220)
ALLY_SCALE         = 1.0
ENEMY_SCALE        = 1.0
TARGET_ALLY_H      = 400
TARGET_ENEMY_H     = 420
FALLBACK_ENEMY_H   = 360

# ---------- VFX ----------
SWIRL_DURATION = 2.0
SWIRL_VIS_FPS  = 60
TELEPORT_SFX   = os.path.join("Assets", "Music", "Sounds", "Teleport.mp3")

# ---------- Battle engine tunables ----------
ENEMY_THINK_MS   = 500
ENEMY_FADE_SEC   = 0.60
RESULT_FADE_MS   = 220
RESULT_CARD_W    = 540
RESULT_CARD_H    = 220

PHASE_PLAYER  = "PLAYER_TURN"
PHASE_RESOLVE = "RESOLVING"
PHASE_ENEMY   = "ENEMY_TURN"

# ---------- Gen-1 textbox (white, double border, DH font) ----------
_DH_FONT_PATH = None

def _find_dh_font() -> str | None:
    global _DH_FONT_PATH
    if _DH_FONT_PATH is not None:
        return _DH_FONT_PATH
    fonts_dir = os.path.join("Assets", "Fonts")
    if os.path.isdir(fonts_dir):
        for fname in os.listdir(fonts_dir):
            low = fname.lower()
            if "dh" in low and low.endswith((".ttf", ".otf", ".ttc")):
                _DH_FONT_PATH = os.path.join(fonts_dir, fname)
                break
    return _DH_FONT_PATH

def _dh_font(size: int):
    try:
        p = _find_dh_font()
        if p:
            return pygame.font.Font(p, size)
    except Exception:
        pass
    return pygame.font.Font(None, size)

def _wrap_text(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
    words = text.split()
    out, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if not cur or font.size(test)[0] <= max_w:
            cur = test
        else:
            out.append(cur); cur = w
    if cur: out.append(cur)
    return out

def _draw_gen1_box(surface: pygame.Surface, rect: pygame.Rect):
    pygame.draw.rect(surface, (245, 245, 245), rect)
    pygame.draw.rect(surface, (0, 0, 0), rect, 4, border_radius=4)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(surface, (0, 0, 0), inner, 2, border_radius=3)
    d = 10
    for cx, cy in (
        (rect.left + 8, rect.top + 8),
        (rect.right - 8, rect.top + 8),
        (rect.left + 8, rect.bottom - 8),
        (rect.right - 8, rect.bottom - 8),
    ):
        pts = [(cx, cy - d//2), (cx + d//2, cy), (cx, cy + d//2), (cx - d//2, cy)]
        pygame.draw.polygon(surface, (0,0,0), pts)

def _draw_intro_textbox(screen: pygame.Surface, text: str, show_prompt: bool):
    sw, sh = screen.get_size()
    margin_x, margin_bottom, box_h = 36, 28, 120
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x*2, box_h)
    _draw_gen1_box(screen, rect)
    inner_pad = 20
    text_rect = rect.inflate(-inner_pad*2, -inner_pad*2)
    font = _dh_font(28)
    lines = _wrap_text(text, font, text_rect.w)
    y = text_rect.y
    for ln in lines[:3]:
        surf = font.render(ln, False, (16, 16, 16))  # no AA for crisper look
        screen.blit(surf, (text_rect.x, y))
        y += surf.get_height() + 6
    if show_prompt:
        tri_w, tri_h = 18, 12
        px = rect.right - 18 - tri_w
        py = rect.bottom - 12 - tri_h
        pts = [(px, py), (px + tri_w, py), (px + tri_w//2, py + tri_h)]
        pygame.draw.polygon(screen, (16,16,16), pts)

# ---------- Summoner name pretty-print ----------
def _extract_summoner_display(raw: str | None) -> str:
    """
    'MSummonerAlice2' -> 'Summoner Alice'
    'FSummoner_Rival3' -> 'Summoner Rival'
    """
    if not raw:
        return "Summoner"
    base = os.path.splitext(os.path.basename(str(raw)))[0]
    base = re.sub(r"^[MF](?=[A-Z])", "", base)  # drop gender flag if present
    m = re.match(r"^Summoner[_\- ]?(.*?)(\d+)?$", base, flags=re.IGNORECASE)
    if m:
        tail = (m.group(1) or "").replace("_", " ").replace("-", " ").strip()
        return f"Summoner {tail}" if tail else "Summoner"
    pretty = re.sub(r"\d+$", "", base).replace("_", " ").replace("-", " ").strip()
    return f"Summoner {pretty}" if pretty else "Summoner"

#---------- Loading scrolls ----------------
def _load_scroll_icon():
    scroll_path = os.path.join("Assets", "Items", "Scroll_Of_Sealing.png")
    scroll_icon = pygame.image.load(scroll_path).convert_alpha()
    grey_scroll_icon = pygame.Surface(scroll_icon.get_size(), pygame.SRCALPHA)
    grey_scroll_icon.fill((100, 100, 100, 128))  # Grey out the icon
    grey_scroll_icon.blit(scroll_icon, (0, 0))
    return scroll_icon, grey_scroll_icon

# ---------- Exit helper ----------
def _exit_to_overworld(gs):
    try:
        pygame.mixer.music.fadeout(200)
    except Exception:
        pass
    gs.in_encounter = False
    gs.encounter_name = ""
    gs.encounter_sprite = None
    setattr(gs, "_went_to_summoner", False)
    # drop cached enemy roster so next battle regenerates
    if hasattr(gs, "_pending_enemy_party"):
        try: delattr(gs, "_pending_enemy_party")
        except Exception: pass
    setattr(gs, "mode", S.MODE_GAME)

# ---------- Vessel name/label helpers (never show Token) ----------
def _pretty_from_vessel(vessel_basename: str | None) -> str:
    if not vessel_basename:
        return "Vessel"
    base = os.path.splitext(os.path.basename(vessel_basename))[0]
    base = re.sub(r"^[MFR]Vessel", "", base, flags=re.IGNORECASE)
    base = re.sub(r"\d+$", "", base)
    base = base.replace("_", " ").strip()
    return base or "Vessel"

def _vessel_basename_from_entry(entry: dict | None) -> str | None:
    if not isinstance(entry, dict):
        return None
    vp = entry.get("vessel_png", "")
    return os.path.splitext(os.path.basename(vp))[0] or None

# ---------- Robust HP parsing (from wild_vessel) ----------
import re as _re_hp
def _safe_int(v, default=0) -> int:
    try:
        if isinstance(v, (int, float)): return int(v)
        s = str(v).strip()
        if not s: return int(default)
        m = _re_hp.match(r"^\s*(\d+)\s*/\s*\d+\s*$", s)
        if m: return int(m.group(1))
        m = _re_hp.match(r"^\s*(\d+)\s*(?:of|OF)\s*\d+\s*$", s)
        if m: return int(m.group(1))
        m = _re_hp.search(r"(\d+)\s*(?:→|->)\s*(\d+)\s*$", s)
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

# ---------- Sprite helpers ----------
def _try_load(path: str | None):
    if path and os.path.exists(path):
        try: return pygame.image.load(path).convert_alpha()
        except Exception as e: print(f"⚠️ load fail {path}: {e}")
    return None

def _smooth_scale_to_height(surf: pygame.Surface | None, target_h: int) -> pygame.Surface | None:
    if surf is None or target_h <= 0: return surf
    w, h = surf.get_width(), surf.get_height()
    if h <= 0: return surf
    s = target_h / float(h)
    return pygame.transform.smoothscale(surf, (max(1, int(w*s)), max(1, int(h*s))))

def _smooth_scale(surf: pygame.Surface | None, scale: float) -> pygame.Surface | None:
    if surf is None or abs(scale - 1.0) < 1e-6: return surf
    w, h = surf.get_width(), surf.get_height()
    return pygame.transform.smoothscale(surf, (max(1, int(w*scale)), max(1, int(h*scale))))

def _load_player_summoner_big(gs) -> pygame.Surface | None:
    gender = (getattr(gs, "chosen_gender", "") or "").lower().strip()
    if gender not in ("male", "female"):
        tok = (getattr(gs, "player_token", "") or "").lower()
        if "female" in tok: gender = "female"
        elif "male" in tok: gender = "male"
        else: gender = "male"
    fname = "CharacterMale.png" if gender == "male" else "CharacterFemale.png"
    path = os.path.join("Assets", "PlayableCharacters", fname)
    surf = _try_load(path)
    return _smooth_scale_to_height(surf, TARGET_ALLY_H) if surf else None

def _load_summoner_big(name: str | None, encounter_sprite: pygame.Surface | None) -> pygame.Surface | None:
    n = (name or "").strip()
    search_dirs = []
    if n.startswith("F"): search_dirs.append(os.path.join("Assets", "SummonersFemale"))
    if n.startswith("M"): search_dirs.append(os.path.join("Assets", "SummonersMale"))
    search_dirs.append(os.path.join("Assets", "SummonersBoss"))
    for d in search_dirs:
        surf = _try_load(os.path.join(d, f"{n}.png"))
        if surf:
            return _smooth_scale_to_height(surf, TARGET_ENEMY_H)
    if encounter_sprite is not None:
        h_target = max(FALLBACK_ENEMY_H, TARGET_ENEMY_H)
        return _smooth_scale_to_height(encounter_sprite, h_target)
    return None

def _asset_path_for_vessel_png(vessel_png: str | None) -> str | None:
    """Find exact vessel file (keeps gender/index)."""
    if not vessel_png:
        return None
    for d in ("Assets/VesselsFemale", "Assets/VesselsMale", "Assets/RareVessels"):
        p = os.path.join(d, vessel_png)
        if os.path.exists(p):
            return p
    return None

def _load_vessel_big(name_or_token: str | None, *, target_h: int) -> pygame.Surface | None:
    """
    Load a big vessel sprite. Accepts:
      • Token basename like 'FTokenRanger2' (mapped via token_to_vessel)
      • Vessel basename like 'FVesselRanger2' (used as-is)
    Always preserves gender and index.
    """
    if not name_or_token:
        return None
    base = os.path.splitext(os.path.basename(str(name_or_token)))[0]
    if re.match(r"^[MFR]Vessel", base, flags=re.IGNORECASE):
        vessel_png = base + ".png"
    else:
        try:
            vessel_png = token_to_vessel(base)  # -> 'FVesselRanger2.png'
        except Exception:
            vessel_png = None
    if not vessel_png:
        print(f"⚠️ Could not resolve vessel from '{name_or_token}'")
        return None
    path = find_image(vessel_png) or _asset_path_for_vessel_png(vessel_png)
    if not path:
        print(f"⚠️ Vessel image not found: {vessel_png}")
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        return _smooth_scale_to_height(img, target_h)
    except Exception as e:
        print(f"⚠️ load vessel fail {path}: {e}")
        return None
    

def _trigger_forced_enemy_switch_if_needed(gs, st):
    """
    Checks if the enemy's current vessel is knocked out and triggers a forced switch
    if a living vessel is available, or ends the battle if all enemies are defeated.
    """
    # Retrieve the enemy party
    enemy_party = getattr(gs, "_pending_enemy_party", [])
    
    # Check for any living enemy vessels
    living_enemy_vessels = [
        entry for entry in enemy_party if int(entry["stats"].get("current_hp", 0)) > 0
    ]
    
    if len(living_enemy_vessels) == 0:
        # No living vessels, end the battle
        st["enemy_fade_active"] = True
        st["enemy_fade_t"] = 0.0
        st["enemy_defeated"] = True
        return True
    
    # If there are living vessels, check if the current vessel is KO'd
    enemy_idx = getattr(gs, "enemy_active_idx", 0)  # Default to 0 if not set
    enemy_entry = enemy_party[enemy_idx] if enemy_party else None
    enemy_stats = enemy_entry.get("stats", {}) if enemy_entry else {}

    # Parse the enemy stats for HP
    e_cur, e_max = _parse_enemy_hp_fields(enemy_stats)
    st["enemy_hp_ratio"] = (e_cur / e_max) if e_max > 0 else 1.0

    # Check if the current enemy vessel is KO'd
    if enemy_stats and int(enemy_stats.get("current_hp", 0)) <= 0:
        # If there are other living vessels in the enemy party, perform a forced switch
        living_enemy_indices = [
            idx for idx, entry in enumerate(enemy_party)
            if int(entry["stats"].get("current_hp", 0)) > 0
        ]
        if living_enemy_indices:
            # Select a new enemy vessel to replace the KO'd one
            new_enemy_idx = living_enemy_indices[0]  # You could randomize or prioritize better vessels here
            gs.enemy_active_idx = new_enemy_idx
            st["enemy_swap_playing"] = True  # Trigger swap animation
            
            # Optionally, you can add SFX for the enemy switch here
            try:
                if st.get("swap_sfx"):
                    st["swap_sfx"].play()
            except Exception:
                pass

            # Trigger enemy swap effects (VFX, animations, etc.)
            st["phase"] = "enemy_swap"
            return True

    return False

def _finish_forced_enemy_switch_if_done(gs, st):
    """
    Finalizes the enemy forced switch, ensuring that everything is set for the next turn.
    """
    if st.get("enemy_swap_playing", False):
        st["enemy_swap_playing"] = False
        st["phase"] = PHASE_ENEMY
        gs._turn_ready = True
        try:
            battle_action.close_popup(); bag_action.close_popup(); party_action.close_popup()
        except Exception:
            pass



# ---------- Ally summon (shared with wild_vessel semantics) ----------
def _first_living_party_index(gs) -> int:
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    names = getattr(gs, "party_slots_names", None) or [None]*6
    for i,(st,nm) in enumerate(zip(stats, names)):
        if nm and isinstance(st, dict):
            try:
                if int(st.get("current_hp", st.get("hp", 0))) > 0:
                    return i
            except Exception:
                pass
    return 0

def _summon_ally_sprite_from_active(gs, target_h: int) -> pygame.Surface | None:
    """
    Mirror wild_vessel ally summon:
      active slot token -> token_to_vessel -> find_image -> load -> scale-to-height.
    """
    names = getattr(gs, "party_slots_names", None) or [None]*6
    idx   = getattr(gs, "combat_active_idx", None)
    if idx is None:
        idx = _first_living_party_index(gs)
        gs.combat_active_idx = idx
    token = None
    if 0 <= idx < len(names):
        token = names[idx]
    if not token:
        return None
    base_token = os.path.splitext(os.path.basename(token))[0]
    try:
        vessel_png = token_to_vessel(base_token)
    except Exception:
        vessel_png = None
    if not vessel_png:
        return None
    path = find_image(vessel_png)
    if not path or not os.path.exists(path):
        path = _asset_path_for_vessel_png(vessel_png)
    if not path or not os.path.exists(path):
        return None
    try:
        surf = pygame.image.load(path).convert_alpha()
        return _smooth_scale_to_height(surf, target_h)
    except Exception:
        return None

# ---------- SFX / VFX loaders ----------
def _load_swirl_frames():
    base = os.path.join("Assets", "Animations")
    frames: list[pygame.Surface] = []

    def _load_sorted(paths):
        def key(p):
            import re as _re
            m = _re.search(r"(\d+)(?!.*\d)", os.path.basename(p))
            return (int(m.group(1)) if m else -1, p.lower())
        for p in sorted(set(paths), key=key):
            try: frames.append(pygame.image.load(p).convert_alpha())
            except Exception as e: print(f"⚠️ VFX load fail: {p} -> {e}")

    try:
        fx_candidates = []
        for pat in ("fx_4_ver1_*.png","FX_4_VER1_*.png","Fx_4_VEr1_*.png","fx_4_ver1_*.PNG","FX_4_VER1_*.PNG"):
            fx_candidates.extend(glob.glob(os.path.join(base, pat)))
        if fx_candidates: _load_sorted(fx_candidates)
        if not frames:
            swirl_candidates = []
            for pat in ("swirl*.png","Swirl*.png","SWIRL*.png","swirl*.PNG","Swirl*.PNG","SWIRL*.PNG"):
                swirl_candidates.extend(glob.glob(os.path.join(base, pat)))
            if swirl_candidates: _load_sorted(swirl_candidates)
    except Exception as e:
        print(f"⚠️ VFX glob/list error in {base}: {e}")
    return frames

def _load_swap_sfx():
    try:
        return pygame.mixer.Sound(TELEPORT_SFX) if os.path.exists(TELEPORT_SFX) else None
    except Exception as e:
        print(f"⚠️ SFX load fail {TELEPORT_SFX}: {e}")
        return None

# ---------- HP/XP visuals ----------
def _hp_ratio_from_stats(stats: dict | None) -> float:
    if not isinstance(stats, dict): return 1.0
    try:
        maxhp = max(1, int(stats.get("hp", 10)))
        curhp = int(stats.get("current_hp", maxhp))
        curhp = max(0, min(curhp, maxhp))
        return curhp / maxhp
    except Exception:
        return 1.0

def _xp_compute(stats: dict) -> tuple[int, int, int, float]:
    try:    lvl = max(1, int(stats.get("level", 1)))
    except: lvl = 1
    try:    cur = max(0, int(stats.get("xp_current", stats.get("xp", 0))))
    except: cur = 0
    need = stats.get("xp_needed")
    try:    need = int(need) if need is not None else int(xp_sys.xp_needed(lvl))
    except Exception: need = 1
    need = max(1, need)
    return lvl, cur, need, max(0.0, min(1.0, cur/need))

def _draw_hp_bar(surface: pygame.Surface, rect: pygame.Rect, hp_ratio: float, name: str, align: str):
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
    notch = (pygame.Rect(plate.x, plate.y, notch_w, plate.h) if align=="right"
             else pygame.Rect(plate.right - notch_w, plate.y, notch_w, plate.h))

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
    if align == "left":
        surface.blit(label, label.get_rect(midleft=(plate.x+12, plate.centery)))
    else:
        surface.blit(label, label.get_rect(midright=(plate.right-12, plate.centery)))


def _draw_xp_strip(surface: pygame.Surface, rect: pygame.Rect, stats: dict):
    _, cur, need, r = _xp_compute(stats)
    frame=(70,45,30); border=(140,95,60); trough=(46,40,36); fill=(40,180,90); text=(230,220,200)
    pygame.draw.rect(surface, frame, rect, border_radius=6)
    pygame.draw.rect(surface, border, rect, 2, border_radius=6)
    inner = rect.inflate(-8,-8)
    font = pygame.font.SysFont("georgia", max(14, int(rect.h*0.60)), bold=False)
    label = font.render(f"XP: {cur} / {need}", True, text)
    surface.blit(label, label.get_rect(midleft=(inner.x+6, inner.centery)))
    bar_h = max(4, int(inner.h*0.36)); bar_w = max(90, int(inner.w*0.46))
    bar_x = inner.right - bar_w - 6; bar_y = inner.centery - bar_h//2
    pygame.draw.rect(surface, trough, (bar_x, bar_y, bar_w, bar_h), border_radius=3)
    fw = int(bar_w * r)
    if fw > 0:
        pygame.draw.rect(surface, fill, (bar_x, bar_y, fw, bar_h), border_radius=3)

# ---------- Active party / swap helpers ----------
def _first_filled_slot_index(gs) -> int:
    names = getattr(gs, "party_slots_names", None) or [None]*6
    for i, n in enumerate(names):
        if n: return i
    return 0

def _battle_start_slot(gs) -> int:
    names = getattr(gs, "party_slots_names", None) or [None]*6
    if names and names[0]:
        return 0
    return _first_filled_slot_index(gs)

def _ensure_active_slot(gs):
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

def _has_living_party(gs) -> bool:
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    for st in stats:
        if isinstance(st, dict):
            hp = int(st.get("current_hp", st.get("hp", 0)))
            if hp > 0:
                return True
    return False

# ---------- Result card helpers ----------
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

def _dismiss_result(st: dict, *, allow_exit: bool = True):
    res = st.get("result")
    if not res: return
    exit_on_close = bool(res.get("exit_on_close")) if allow_exit else False
    st["result"] = None
    if exit_on_close:
        st["pending_exit"] = True

def _auto_dismiss_result_if_ready(st: dict):
    res = st.get("result")
    if not res: return
    if res.get("auto_ms", 0) > 0 and res.get("auto_ready", False):
        exit_on_close = bool(res.get("exit_on_close"))
        st["result"] = None
        if exit_on_close:
            st["pending_exit"] = True

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
    dim = pygame.Surface((sw, sh), pygame.SRCALPHA); dim.fill((0, 0, 0, min(160, a)))
    screen.blit(dim, (0, 0))

    card_w, card_h = RESULT_CARD_W, RESULT_CARD_H
    card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
    pygame.draw.rect(card, (245, 245, 245, min(245, a)), card.get_rect(), border_radius=14)
    pygame.draw.rect(card, (0, 0, 0, min(255, a)), card.get_rect(), 4, border_radius=14)
    pygame.draw.rect(card, (60, 60, 60, min(255, a)), card.get_rect().inflate(-10, -10), 2, border_radius=10)

    big = pygame.font.SysFont("georgia", 40, bold=True)
    mid = pygame.font.SysFont("georgia", 24, bold=False)
    t_surf = big.render(res.get("title",""), True, (20, 20, 20))
    s_surf = mid.render(res.get("subtitle",""), True, (45, 45, 45))
    card.blit(t_surf, t_surf.get_rect(center=(card_w//2, card_h//2 - 22)))
    card.blit(s_surf, s_surf.get_rect(center=(card_w//2, card_h//2 + 24)))

    if res.get("auto_ms", 0) <= 0 and not res.get("lock_input", False):
        hint = pygame.font.SysFont("arial", 18, bold=False).render(
            "Click to continue", True, (70, 70, 70)
        )
        card.blit(hint, hint.get_rect(midbottom=(card_w//2, card_h - 14)))

    screen.blit(card, card.get_rect(center=(sw//2, int(sh*0.52))))

    auto_ms = res.get("auto_ms", 0)
    if auto_ms > 0 and (res["t"] * 1000.0) >= auto_ms:
        res["auto_ready"] = True

# ---------- Forced switch (ally KO) ----------
def _trigger_forced_switch_if_needed(gs, st):
    idx = _get_active_party_index(gs)
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    cur = 0
    if 0 <= idx < len(stats) and isinstance(stats[idx], dict):
        cur = int(stats[idx].get("current_hp", stats[idx].get("hp", 0)))
    if cur <= 0 and not st.get("force_switch", False) and not st.get("swap_playing", False):
        if not _has_living_party(gs):
            _show_result_screen(st, "All vessels are down!", "You can’t continue.", kind="fail", exit_on_close=True)
            st["pending_exit"] = True
            return
        st["force_switch"] = True
        setattr(gs, "_force_switch", True)   # keep party_action in sync
        st["turn_phase"] = PHASE_PLAYER
        try:
            battle_action.close_popup(); bag_action.close_popup()
        except Exception: pass
        try:
            party_action.open_popup()
        except Exception: pass

def _finish_forced_switch_if_done(gs, st):
    if st.get("force_switch", False):
        active_idx = _get_active_party_index(gs)
        if not st.get("swap_playing", False) and st.get("ally_from_slot") == active_idx:
            st["force_switch"] = False
            setattr(gs, "_force_switch", False)
            st["turn_phase"] = PHASE_PLAYER
            gs._turn_ready = True
            try:
                party_action.close_popup()
            except Exception:
                pass

# ---------- Lifecycle ----------
def enter(gs, **_):
    # close popups
    for act in (battle_action, bag_action, party_action):
        try: act.close_popup()
        except Exception: pass

    setattr(gs, "mode", "SUMMONER_BATTLE")
    sw, sh = S.WIDTH, S.HEIGHT

    # Music
    try: pygame.mixer.music.fadeout(200)
    except Exception: pass
    track = _pick_summoner_track()
    if track:
        try:
            pygame.mixer.music.load(track)
            pygame.mixer.music.play(-1, fade_ms=220)
        except Exception as e:
            print(f"⚠️ Could not play summoner music: {e}")

    # Intro sprites (big summoners)
    ally_img  = _load_player_summoner_big(gs)
    enemy_img = _load_summoner_big(getattr(gs, "encounter_name", None),
                                   getattr(gs, "encounter_sprite", None))
    if ally_img is not None:  ally_img  = _smooth_scale(ally_img,  ALLY_SCALE)
    if enemy_img is not None: enemy_img = _smooth_scale(enemy_img, ENEMY_SCALE)

    # Anchors
    ax1 = 20 + ALLY_OFFSET[0]
    ay1 = sh - (ally_img.get_height() if ally_img else 240) - 20 + ALLY_OFFSET[1]
    ex1 = sw - (enemy_img.get_width() if enemy_img else 240) - 20 + ENEMY_OFFSET[0]
    ey1 = 20 + ENEMY_OFFSET[1]

    # Slide-in/off positions
    ally_start  = (-(ally_img.get_width() if ally_img else 240) - 60, ay1)
    enemy_start = (sw + 60, ey1)
    ally_out    = (-(ally_img.get_width() if ally_img else 240) - 80, ay1)
    enemy_out   = (sw + 80, ey1)

    # Background
    bg_img = None
    for cand in ("Wild.png", "Trainer.png"):
        p = os.path.join("Assets", "Map", cand)
        if os.path.exists(p):
            try:
                bg_img = pygame.transform.smoothscale(pygame.image.load(p).convert(), (sw, sh))
                break
            except Exception as e:
                print(f"⚠️ Summoner bg load failed: {e}")

    # Party & VFX assets
    party_stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    active_idx  = _first_living_party_index(gs)
    gs.combat_active_idx = active_idx
    ally_stats  = party_stats[active_idx] if 0 <= active_idx < len(party_stats) else None
    swirl_frames = _load_swirl_frames()
    swap_sfx     = _load_swap_sfx()

    # Ally token basename (to map to vessel sprite later)
    party_names = getattr(gs, "party_slots_names", None) or [None]*6
    ally_token_basename = None
    if 0 <= active_idx < len(party_names):
        ally_token_basename = os.path.splitext(os.path.basename(str(party_names[active_idx] or "")))[0] or None

    # Enemy party (single entry for this scene)
    enemy_party = getattr(gs, "_pending_enemy_party", None)
    if not enemy_party:
        enemy_party = generate_enemy_party(gs, max_party=6)
        setattr(gs, "_pending_enemy_party", enemy_party)

    # ✅ Normalize enemy party stats so every entry has a sane current_hp
    for entry in enemy_party:
        stats = entry.setdefault("stats", {})
        try:
            max_hp = max(1, int(stats.get("hp", 10)))
        except Exception:
            max_hp = 10
        cur_hp = stats.get("current_hp")
        try:
            cur_hp = int(cur_hp) if cur_hp is not None else max_hp
        except Exception:
            cur_hp = max_hp
        stats["hp"] = max_hp
        stats["current_hp"] = max(0, min(cur_hp, max_hp))

    # Make sure we have an active enemy index
    if not hasattr(gs, "enemy_active_idx"):
        gs.enemy_active_idx = 0
    enemy_entry = enemy_party[0] if enemy_party else None
    enemy_vessel_basename = _vessel_basename_from_entry(enemy_entry)
    enemy_stats = enemy_entry.get("stats") if enemy_entry else None

    # Stage encounter strictly with VESSEL basenames (keeps gender/index)
    if enemy_stats:
        gs.encounter_stats = dict(enemy_stats)  # ensure dict
        # Ensure hp/current_hp present like wild_vessel does
        try:
            max_hp = max(1, int(gs.encounter_stats.get("hp", 10)))
        except Exception:
            max_hp = 10
        cur_hp = gs.encounter_stats.get("current_hp")
        try:
            cur_hp = int(cur_hp) if cur_hp is not None else max_hp
        except Exception:
            cur_hp = max_hp
        cur_hp = max(0, min(cur_hp, max_hp))
        gs.encounter_stats["hp"] = max_hp
        gs.encounter_stats["current_hp"] = cur_hp

    if enemy_vessel_basename:
        gs.encounter_name = enemy_vessel_basename
        gs.encounter_vessel_name = enemy_vessel_basename
        gs.enemy_active_name = enemy_vessel_basename

    # Announcement text
    raw_enemy_name = (getattr(gs, "encounter_display_name", None)
                      or getattr(gs, "enemy_active_name", None)
                      or getattr(gs, "encounter_vessel_name", None)
                      or getattr(gs, "encounter_name", None))
    enemy_display  = _extract_summoner_display(raw_enemy_name)
    announce_text  = f"You are challenged by {enemy_display}!"

    # Initialize battle engine state (will activate after VFX)
    xp_sys.ensure_profile(gs)
    set_roll_callback(roll_ui._on_roll)

    gs._summ_ui = {
        "bg": bg_img,
        "ally_img": ally_img,
        "enemy_img": enemy_img,

        "ally_anchor": (ax1, ay1),
        "enemy_anchor": (ex1, ey1),
        "ally_pos": list(ally_start),
        "enemy_pos": list(enemy_start),
        "ally_target": (ax1, ay1),
        "enemy_target": (ex1, ey1),

        "ally_out": ally_out,
        "enemy_out": enemy_out,

        "speed": 1.0 / max(0.001, SUMMON_TIME),
        "ally_t": 0.0,
        "enemy_t": 0.0,
        "elapsed": 0.0,
        "phase": "intro",      # intro -> slide_out -> vfx -> battle -> exit
        "out_t": 0.0,
        "out_speed": 1.0 / max(0.001, SLIDE_AWAY_TIME),

        # Battle visuals
        "ally_hp_ratio": _hp_ratio_from_stats(ally_stats),
        "enemy_hp_ratio": 1.0,
        "active_idx": active_idx,
        "track": track,
        "summoner_mode": True,   # while True: show summoner sprites; no plates yet

        # VFX
        "swirl_frames": swirl_frames,
        "swap_sfx": swap_sfx,
        "vfx_t": 0.0,
        "vfx_total": 0.0,
        "vfx_frame": 0,
        "vfx_playing": False,

        "announce_text": announce_text,
        "textbox_active": True,
        "show_prompt": True,

        # ally swap VFX during battle
        "ally_from_slot": None,
        "ally_swap_target_slot": None,
        "ally_img_next": None,
        "swap_playing": False,
        "swap_t": 0.0,
        "swap_total": 0.0,
        "swap_frame": 0,

        # Battle engine fields (activate post-VFX)
        "turn_phase": PHASE_PLAYER,
        "enemy_think_until": 0,
        "ai_started": False,
        "force_switch": False,

        "result": None,
        "ok_sfx": None,      # optional success sfx (not used here)
        "fail_sfx": None,    # optional fail sfx (not used here)
        "pending_exit": False,

        # Enemy fade on defeat
        "enemy_fade_active": False,
        "enemy_fade_t": 0.0,
        "enemy_fade_dur": ENEMY_FADE_SEC,
        "enemy_defeated": False,
        "defeat_debounce_t": 0.0,
        "defeat_debounce_ms": 300,

        # ✅ XP
        "pending_xp_award": None,  # tuple(outcome, enemy_name, estats, active_idx)

        # Spawn info (from intro)
        "ally_token_name": ally_token_basename,     # token
        "enemy_vessel_name": enemy_vessel_basename, # vessel basename
        "enemy_entry": enemy_entry,
    }

    set_roll_callback(roll_ui._on_roll)  # Enable dice popup plumbing
    gs._wild = gs._summ_ui               # Critical: moves.py writes to gs._wild

    # Determine initial turn order (kept simple / optional)
    try:
        turn_order.determine_order(gs)
    except Exception:
        pass
    gs._turn_ready = True  # player starts able to act

def handle(events, gs, **_):
    # Avoid top-level circular import by importing when needed
    from combat.summoner_battle import _trigger_forced_switch_if_needed

    st = getattr(gs, "_summ_ui", None)
    if st is None:
        enter(gs); st = gs._summ_ui

    # If exit is queued and no modal result, leave
    if st.get("pending_exit") and not st.get("result"):
        _exit_to_overworld(gs)
        return S.MODE_GAME

    # Intro textbox is modal (during 'intro' only)
    for e in events:
        if st.get("phase") == "intro" and st.get("textbox_active", False):
            if (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE)) or \
               (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
                st["textbox_active"] = False
                st["phase"] = "slide_out"
                st["out_t"] = 0.0
                return None
            return None

    # Modal dice popup always consumes input first (for move rolls, etc.)
    if roll_ui.is_active():
        for e in events:
            roll_ui.handle_event(e)
        # (No run_action in summoner battles)
        return None

    # --- Global result-card click handling (works in any turn phase)
    res = st.get("result")
    if res:
        # If it's not locked and not auto-dismiss, allow click-to-continue in any phase
        if not res.get("lock_input", False) and res.get("auto_ms", 0) <= 0:
            for e in events:
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    # If we're currently forcing a switch, don't allow exit here
                    _dismiss_result(st, allow_exit=not st.get("force_switch", False))
                    return None
        # If it is locked or auto-dismissing, just pause input
        return None

    # Auto-dismiss result if ready
    _auto_dismiss_result_if_ready(st)

    # After a result is dismissed, if XP pending and no current result, show it now
    if not st.get("result") and st.get("pending_xp_award"):
        try:
            outcome, enemy_name, estats, active_idx = st.pop("pending_xp_award")
        except Exception:
            outcome, enemy_name, estats, active_idx = ("defeat", "Enemy", {}, _get_active_party_index(gs))

        base_xp = xp_sys.compute_xp_reward(estats or {}, enemy_name or "Enemy", outcome or "defeat")
        active_xp, bench_xp, levelups = xp_sys.distribute_xp(gs, int(active_idx), int(base_xp))

        # Optional immediate save
        try:
            from systems import save_system as saves
            saves.save_game(gs, force=True)
        except Exception:
            pass

        xp_line = f"+{active_xp} XP to active  |  +{bench_xp} to each benched"
        if levelups:
            idx, old_lv, new_lv = levelups[0]
            from_name = (getattr(gs, "party_slots_names", None) or [None]*6)[idx] or "Ally"
            base = os.path.splitext(os.path.basename(from_name))[0]
            for p in ("StarterToken", "MToken", "FToken", "RToken"):
                if base.startswith(p):
                    base = base[len(p):]; break
            pretty = re.sub(r"\d+$", "", base) or "Ally"
            subtitle = f"{xp_line}   •   {pretty} leveled up! {old_lv} → {new_lv}"
        else:
            subtitle = xp_line

        _show_result_screen(st, "Experience Gained", subtitle, kind="info", exit_on_close=True)
        st["pending_exit"] = True
        return None

    # Forced switch routing (ally KO)
    if st.get("force_switch", False):
        try:
            selection_committed = getattr(gs, "_pending_party_switch", None) is not None
            if (not st.get("swap_playing", False)) and (not selection_committed):
                if not party_action.is_open():
                    party_action.open_popup()
        except Exception:
            pass

        # allow dismissing any visible non-locked result (but do not exit)
        res = st.get("result")
        if res and not res.get("lock_input", False):
            for e in events:
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    _dismiss_result(st, allow_exit=False)
                    break

        # only Party popup consumes input
        for e in events:
            if party_action.is_open() and party_action.handle_event(e, gs):
                return None
        return None

    # ===== Check if the ally Vessel is KO'd and trigger forced switch =====
    if st.get("phase") == "battle":
        # Check if the ally Vessel is KO'd and if a forced switch is needed
        _trigger_forced_switch_if_needed(gs, st)

    # Normal routing (not during enemy phase)
    if st.get("phase") not in ("intro", "slide_out", "vfx"):
        if st.get("turn_phase") != PHASE_ENEMY:
            for e in events:
                # Block clicks while a result card is visible (unless it's click-to-continue)
                res = st.get("result")
                if res:
                    if res.get("lock_input", False) or res.get("auto_ms", 0) > 0:
                        return None
                    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                        _dismiss_result(st, allow_exit=True)
                        return None

                if st.get("turn_phase") == PHASE_PLAYER:
                    if party_action.is_open() and party_action.handle_event(e, gs):  return None
                    if bag_action.is_open()   and bag_action.handle_event(e, gs):    return None
                    if battle_action.is_open()and battle_action.handle_event(e, gs): return None

                    if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                        _exit_to_overworld(gs)
                        return S.MODE_GAME

                    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                        pos = e.pos
                        if battle_action.handle_click(pos):   return None
                        if bag_action.handle_click(pos):      return None
                        if party_action.handle_click(pos):    return None

    # ===== TURN ENGINE =====
    if st.get("phase") not in ("intro", "slide_out", "vfx"):
        try:
            resolving_moves = bool(moves.is_resolving())
        except Exception:
            resolving_moves = False

        if st.get("turn_phase") == PHASE_PLAYER:
            if getattr(gs, "_turn_ready", True) is False or resolving_moves:
                st["turn_phase"] = PHASE_RESOLVE
                try:
                    battle_action.close_popup(); bag_action.close_popup(); party_action.close_popup()
                except Exception: pass

        scene_busy = (
            st.get("result") or st.get("enemy_fade_active")
            or st.get("swap_playing") or roll_ui.is_active()
        )

        if st.get("turn_phase") == PHASE_RESOLVE and not resolving_moves and not scene_busy:
            try: turn_order.next_turn(gs)
            except Exception: pass
            st["turn_phase"] = PHASE_ENEMY
            st["ai_started"] = False
            st["enemy_think_until"] = pygame.time.get_ticks() + ENEMY_THINK_MS
            try:
                battle_action.close_popup(); bag_action.close_popup(); party_action.close_popup()
            except Exception: pass

        if st.get("turn_phase") == PHASE_ENEMY:
            now = pygame.time.get_ticks()
            if (not st.get("ai_started")
                and now >= int(st.get("enemy_think_until", 0))
                and not resolving_moves
                and not scene_busy):
                try:
                    enemy_ai.take_turn(gs)
                except Exception as _e:
                    print(f"⚠️ enemy_ai failure: {_e}")
                # attempt to play move sfx via last label (if any)
                try:
                    lbl = st.pop("last_enemy_move_label", None) or getattr(gs, "_last_enemy_move_label", None)
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
                st["turn_phase"] = PHASE_PLAYER

    return None



def draw(screen: pygame.Surface, gs, dt, **_):
    st = getattr(gs, "_summ_ui", None)
    if st is None:
        enter(gs); st = gs._summ_ui

    # Background
    if st.get("bg"): screen.blit(st["bg"], (0, 0))
    else:            screen.fill((0, 0, 0))

    ease = lambda t: 1.0 - (1.0 - t) ** 3
    phase = st.get("phase", "intro")
    if phase in ("intro", "slide_out", "vfx"):
        st["elapsed"] = st.get("elapsed", 0.0) + dt

    ax = ay = ex = ey = 0

    # ---------- PHASES ----------
    if phase == "intro":
        st["ally_t"]  = min(1.0, st.get("ally_t", 0.0)  + dt * st.get("speed", 1.0))
        st["enemy_t"] = min(1.0, st.get("enemy_t", 0.0) + dt * st.get("speed", 1.0))
        ax0, ay0 = st["ally_pos"];   ax1, ay1 = st["ally_target"]
        ex0, ey0 = st["enemy_pos"];  ex1, ey1 = st["enemy_target"]
        ax = int(ax0 + (ax1 - ax0) * ease(st["ally_t"]))
        ay = int(ay0 + (ay1 - ay0) * ease(st["ally_t"]))
        ex = int(ex0 + (ex1 - ex0) * ease(st["enemy_t"]))
        ey = int(ey0 + (ey1 - ey0) * ease(st["enemy_t"]))

    elif phase == "slide_out":
        st["out_t"] = min(1.0, st.get("out_t", 0.0) + dt * st.get("out_speed", 1.0))
        ax1, ay1 = st["ally_anchor"];   ax2, ay2 = st["ally_out"]
        ex1, ey1 = st["enemy_anchor"];  ex2, ey2 = st["enemy_out"]
        ax = int(ax1 + (ax2 - ax1) * ease(st["out_t"]))
        ay = int(ay1 + (ay2 - ay1) * ease(st["out_t"]))
        ex = int(ex1 + (ex2 - ex1) * ease(st["out_t"]))
        ey = int(ey1 + (ey2 - ey1) * ease(st["out_t"]))
        if st["out_t"] >= 1.0:
            st["phase"] = "vfx"
            st["vfx_t"] = 0.0
            st["vfx_total"] = 0.0
            st["vfx_frame"] = 0
            st["vfx_playing"] = True
            try:
                if st.get("swap_sfx"): st["swap_sfx"].play()
            except Exception:
                pass

    elif phase == "vfx":
        ax, ay = st["ally_out"]
        ex, ey = st["enemy_out"]
        if st.get("vfx_playing", False) and st.get("swirl_frames"):
            st["vfx_t"]     = st.get("vfx_t", 0.0) + dt
            st["vfx_total"] = st.get("vfx_total", 0.0) + dt
            frames = st["swirl_frames"]
            idx = int(st["vfx_t"] * SWIRL_VIS_FPS) % len(frames)
            swirl_raw = frames[idx]
            target = int(max(TARGET_ALLY_H, TARGET_ENEMY_H) * 1.15)
            sw_, sh_ = swirl_raw.get_width(), swirl_raw.get_height()
            s = target / max(1, max(sw_, sh_))
            swirl = pygame.transform.smoothscale(swirl_raw, (max(1, int(sw_*s)), max(1, int(sh_*s))))
            ax1, ay1 = st["ally_anchor"]; ex1, ey1 = st["enemy_anchor"]
            ally_center  = (ax1 + (st.get("ally_img").get_width()//2  if st.get("ally_img")  else 160),
                            ay1 + (st.get("ally_img").get_height()//2 if st.get("ally_img") else 120))
            enemy_center = (ex1 + (st.get("enemy_img").get_width()//2 if st.get("enemy_img") else 160),
                            ey1 + (st.get("enemy_img").get_height()//2 if st.get("enemy_img") else 120))
            screen.blit(swirl, swirl.get_rect(center=ally_center))
            screen.blit(swirl, swirl.get_rect(center=enemy_center))

            # VFX complete → swap to vessels & show plates + start battle engine
            if st["vfx_total"] >= SWIRL_DURATION:
                st["vfx_playing"] = False

                # --- Ally vessel sprite from active slot (wild_vessel semantics)
                ally_img = _summon_ally_sprite_from_active(gs, TARGET_ALLY_H)
                if not ally_img:
                    ally_img = _load_vessel_big(st.get("ally_token_name"), target_h=TARGET_ALLY_H)
                enemy_vn = st.get("enemy_vessel_name")
                enemy_vessel_img = _load_vessel_big(enemy_vn, target_h=TARGET_ENEMY_H)

                if ally_img:           st["ally_img"]  = ally_img
                if enemy_vessel_img:   st["enemy_img"] = enemy_vessel_img

                # Reassert encounter labels using vessel name (keeps gender/index)
                if enemy_vn:
                    gs.encounter_name = enemy_vn
                    gs.encounter_vessel_name = enemy_vn
                    gs.enemy_active_name = enemy_vn

                st["summoner_mode"] = False
                st["phase"] = "battle"
                st["turn_phase"] = PHASE_PLAYER
                gs._turn_ready = True

    else:  # "battle" (or unrecognized)
        ax, ay = st["ally_anchor"]
        ex, ey = st["enemy_anchor"]

    # ---------- Labels/HP/XP ----------
    names = getattr(gs, "party_slots_names", None) or [None]*6
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    # Track/prepare ally sprite source for swap VFX
    active_i = _get_active_party_index(gs)
    ally_token_name = names[active_i] if 0 <= active_i < len(names) else None
    ally_stats = stats[active_i] if 0 <= active_i < len(stats) else None
    st["ally_hp_ratio"] = _hp_ratio_from_stats(ally_stats)

    ally_lv = 1
    if isinstance(ally_stats, dict):
        try: ally_lv = int(ally_stats.get("level", 1))
        except Exception: ally_lv = 1

    # Ally display name: TOKEN → VESSEL pretty (display only)
    ally_label_vessel = None
    if ally_token_name:
        try:
            ally_label_vessel = os.path.splitext(os.path.basename(
                token_to_vessel(os.path.splitext(os.path.basename(ally_token_name))[0])
            ))[0]
        except Exception:
            ally_label_vessel = None
    ally_pretty = _pretty_from_vessel(ally_label_vessel)
    ally_label  = f"{ally_pretty}  lvl {ally_lv}"

    # Enemy label strictly from vessel (keeps M/F + index)
    enemy_stats_obj = getattr(gs, "encounter_stats", None) or {}
    try: enemy_lv = int(enemy_stats_obj.get("level"))
    except Exception: enemy_lv = getattr(gs, "zone_level", 1)
    enemy_vessel_name = (
        st.get("enemy_vessel_name")
        or getattr(gs, "encounter_vessel_name", None)
        or getattr(gs, "enemy_active_name", None)
        or getattr(gs, "encounter_name", None)
    )
    enemy_pretty = _pretty_from_vessel(enemy_vessel_name)
    enemy_label  = f"{enemy_pretty}  lvl {enemy_lv if enemy_lv else '?'}"

    # ---------- Draw sprites & plates ----------
    bar_w, bar_h = 400, 70
    ally_w = st["ally_img"].get_width() if st.get("ally_img") else 0
    ally_h = st["ally_img"].get_height() if st.get("ally_img") else 0
    ally_bar = pygame.Rect(ax + (ally_w // 2) - (bar_w // 2), ay + ally_h + 12, bar_w, bar_h)
    enemy_bar = pygame.Rect(ex - bar_w - 24, ey + 12, bar_w, bar_h)

    # Enemy HP ratio source (robust)
    if hasattr(gs, "_summ_ui"):
        temp_est = dict(enemy_stats_obj)
        temp_est["_hp_ratio_fallback"] = st.get("enemy_hp_ratio", 1.0)
    else:
        temp_est = enemy_stats_obj
    e_cur, e_max = _parse_enemy_hp_fields(temp_est)
    st["enemy_hp_ratio"] = (e_cur / e_max) if e_max > 0 else 1.0

    # Draw sprites
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
                # After fade completes, queue XP (if not already queued)
                active_idx = _get_active_party_index(gs)
                estats = getattr(gs, "encounter_stats", {}) or {}
                enemy_name = getattr(gs, "encounter_name", "Enemy") or "Enemy"
                if st.get("enemy_defeated", False):
                    if not st.get("pending_xp_award"):
                        st["pending_xp_award"] = ("defeat", enemy_name, estats, active_idx)
        else:
            screen.blit(enemy_surface, (ex, ey))

    if st.get("ally_img"):  screen.blit(st["ally_img"], (ax, ay))

    # Plates only after intro VFX (not during summoner_mode)
    if not st.get("summoner_mode", False):
        _draw_hp_bar(screen, ally_bar, st.get("ally_hp_ratio", 1.0), ally_label, "left")
        if isinstance(ally_stats, dict):
            _draw_xp_strip(screen, pygame.Rect(ally_bar.x, ally_bar.bottom + 6, ally_bar.w, 22), ally_stats)
        _draw_hp_bar(screen, enemy_bar, st.get("enemy_hp_ratio", 1.0), enemy_label, "right")
    
    # --- HP/XP Bars and Enemy Icons ---
    bar_w, bar_h = 400, 70
    ally_w = st["ally_img"].get_width() if st.get("ally_img") else 0
    ally_h = st["ally_img"].get_height() if st.get("ally_img") else 0
    ally_bar = pygame.Rect(ax + (ally_w // 2) - (bar_w // 2), ay + ally_h + 12, bar_w, bar_h)

    enemy_bar = pygame.Rect(ex - bar_w - 24, ey + 12, bar_w, bar_h)

    # Get the enemy stats to determine if any of the vessels are KO'd or alive
    enemy_party = getattr(gs, "_pending_enemy_party", [])

    # Calculate the position for the scroll icons (relative to the enemy HP bar)
    icon_pos_x = ex + (bar_w // 2) - 330  # Adjust horizontally to center icons near the enemy bar
    icon_pos_y = enemy_bar.bottom + 0    # Position just below the enemy HP bar, with spacing

    # Ensure scroll icons are not drawn during intro phase or while fade effect is active
    if st.get("enemy_fade_active", False):
        return None  # Skip drawing icons if fade is active

    # Load scroll icons (normal and greyed out for fainted vessels)
    scroll_icon, grey_scroll_icon = _load_scroll_icon()

    # Scale the icons to ensure they fit consistently within the UI
    scaled_scroll_icon = pygame.transform.smoothscale(scroll_icon, (50, 50))  # Resize to 50x50
    scaled_grey_scroll_icon = pygame.transform.smoothscale(grey_scroll_icon, (50, 50))  # Resize to 50x50

    # Check if the enemy HP bar is visible and we are not in the intro or VFX phase
    phase = st.get("phase", "intro")
    if phase != "intro" and not st.get("vfx_playing", False):  # Ensure the VFX phase is complete
        # Draw the icons for each vessel in the enemy party
        for idx, entry in enumerate(enemy_party):
            # Get the vessel's current HP (fainted or alive)
            cur_hp = int(entry["stats"].get("current_hp", 0))
            is_fainted = cur_hp <= 0
            
            # Draw the icon based on the vessel's status (fainted or alive)
            icon = scaled_grey_scroll_icon if is_fainted else scaled_scroll_icon
            icon_rect = icon.get_rect(topleft=(icon_pos_x + (idx * 55), icon_pos_y))  # Space out icons horizontally
            screen.blit(icon, icon_rect)



    # Enemy KO debounce & fade trigger (only during battle)
    if st.get("phase") == "battle" and st.get("enemy_img") is not None:
        try:
            moves_busy = bool(moves.is_resolving())
        except Exception:
            moves_busy = False

        should_consider_ko = (
            e_cur <= 0 and not st.get("enemy_fade_active", False)
            and not st.get("result", None)
            and not st.get("enemy_defeated", False)
            and not moves_busy
        )
        if should_consider_ko:
            st["defeat_debounce_t"] = st.get("defeat_debounce_t", 0.0) + dt
            if (st["defeat_debounce_t"] * 1000.0) >= int(st.get("defeat_debounce_ms", 300)):
                st["enemy_fade_active"] = True
                st["enemy_fade_t"] = 0.0
                st["enemy_defeated"] = True
        else:
            if e_cur > 0 or moves_busy:
                st["defeat_debounce_t"] = 0.0

    # Ally swap VFX (when party selection changes active slot)
    if st.get("phase") == "battle":
        if st.get("ally_from_slot") is None:
            st["ally_from_slot"] = active_i
            if ally_token_name and not st.get("ally_img"):
                try:
                    vessel_png = token_to_vessel(os.path.splitext(os.path.basename(ally_token_name))[0])
                    path = find_image(vessel_png)
                    if path and os.path.exists(path):
                        st["ally_img"] = _smooth_scale_to_height(pygame.image.load(path).convert_alpha(), TARGET_ALLY_H)
                except Exception: pass
        elif st["ally_from_slot"] != active_i and ally_token_name and not st.get("swap_playing", False):
            try:
                vessel_png = token_to_vessel(os.path.splitext(os.path.basename(ally_token_name))[0])
                path = find_image(vessel_png)
                if path and os.path.exists(path):
                    st["ally_img_next"] = _smooth_scale_to_height(pygame.image.load(path).convert_alpha(), TARGET_ALLY_H)
                    st["ally_swap_target_slot"] = active_i
                    st["swap_playing"] = True
                    st["swap_t"] = 0.0
                    st["swap_total"] = 0.0
                    st["swap_frame"] = 0
                    st["ally_t"] = 1.0
                    try:
                        if st.get("swap_sfx"):
                            audio_sys.play_sound(st["swap_sfx"])
                    except Exception: pass
            except Exception: pass

        if st.get("swap_playing", False):
            frames = st.get("swirl_frames") or []
            if not frames:
                if st.get("ally_img_next"): st["ally_img"] = st["ally_img_next"]
                st["ally_img_next"] = None
                st["ally_from_slot"] = st.get("ally_swap_target_slot", st.get("ally_from_slot"))
                st["ally_swap_target_slot"] = None
                st["swap_playing"]  = False
                _finish_forced_switch_if_done(gs, st)
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

    # ---------- Draw Result Card and Dice Popup ----------

    # Result card (over UI)
    if st.get("result"):
        _draw_result_screen(screen, st, dt)

    # Dice popup always on top
    roll_ui.draw_roll_popup(screen, dt)

    # Buttons & popups (Run intentionally omitted for trainer fights)
    battle_action.draw_button(screen)
    bag_action.draw_button(screen)
    party_action.draw_button(screen)
    if bag_action.is_open():    bag_action.draw_popup(screen, gs)
    if party_action.is_open():  party_action.draw_popup(screen, gs)
    if battle_action.is_open(): battle_action.draw_popup(screen, gs)

    # Intro textbox on top (during intro)
    if st.get("phase") == "intro" and st.get("textbox_active", False):
        _draw_intro_textbox(screen, st.get("announce_text", ""), st.get("show_prompt", True))


    # Turn indicator overlay (debug)
    if st.get("phase") == "battle":
        font = pygame.font.SysFont("georgia", 22, bold=True)
        text = f"Phase: {st.get('turn_phase','?')}  Ready:{getattr(gs,'_turn_ready',True)}  ForceSwitch:{st.get('force_switch', False)}"
        surf = font.render(text, True, (240, 230, 200))
        screen.blit(surf, (12, 12))

    # Buttons & popups (Run intentionally omitted for trainer fights)
    battle_action.draw_button(screen)
    bag_action.draw_button(screen)
    party_action.draw_button(screen)
    if bag_action.is_open():    bag_action.draw_popup(screen, gs)
    if party_action.is_open():  party_action.draw_popup(screen, gs)
    if battle_action.is_open(): battle_action.draw_popup(screen, gs)

    # Intro textbox on top (during intro)
    if st.get("phase") == "intro" and st.get("textbox_active", False):
        _draw_intro_textbox(screen, st.get("announce_text", ""), st.get("show_prompt", True))

    # Result screen (over UI, under dice popup)
    if st.get("result"): _draw_result_screen(screen, st, dt)

    # Dice popup always on top
    roll_ui.draw_roll_popup(screen, dt)

# ---------- Music picker (unchanged from original) ----------
def _pick_summoner_track() -> str | None:
    base = os.path.join("Assets", "Music", "SummonerMusic")
    choices = [os.path.join(base, f"SummonerM{i}.mp3") for i in range(1, 5)]
    choices = [p for p in choices if os.path.exists(p)]
    if not choices: choices = glob.glob(os.path.join(base, "*.mp3"))
    return random.choice(choices) if choices else None
