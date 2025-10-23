# ============================================================
# screens/party_manager.py — Overworld Party Manager (Tab)
# - Modal overlay opened/closed with Tab (or Esc)
# - Shows 6 party slots with icon, name, level, HP bar
# - Click a row to select; click another to SWAP positions
# - Right-click a row to SET ACTIVE (updates gs.party_active_idx)
# - Draws on parchment; blocks overworld input while open
# ============================================================
from __future__ import annotations
import os
import re
import pygame
import settings as S

# Optional: tie into your audio system if present
try:
    from systems import audio as audio_sys
except Exception:  # graceful fallback
    audio_sys = None

# ---------------- Modal open/close ----------------
_OPEN = False
_FADE_START_MS = None
FADE_MS = 180

def is_open() -> bool:
    return _OPEN

def open():
    global _OPEN, _FADE_START_MS
    if _OPEN:
        return
    _OPEN = True
    _FADE_START_MS = pygame.time.get_ticks()
    _play_open()

def close():
    global _OPEN, _FADE_START_MS, _SELECTED
    if not _OPEN:
        return
    _OPEN = False
    _FADE_START_MS = None
    _SELECTED = None
    _play_open()

def toggle():
    if _OPEN:
        close()
    else:
        open()

# ---------------- Assets (scroll parchment) ----------------
_SCROLL_IMG_PATH = os.path.join("Assets", "Map", "PartyScroll.png")
_SCROLL_BASE: pygame.Surface | None = None
_SCROLL_CACHE: dict[tuple[int, int], pygame.Surface] = {}

def _load_scroll_scaled(sw: int, sh: int) -> pygame.Surface | None:
    global _SCROLL_BASE
    if _SCROLL_BASE is None:
        if not os.path.exists(_SCROLL_IMG_PATH):
            return None
        try:
            _SCROLL_BASE = pygame.image.load(_SCROLL_IMG_PATH).convert_alpha()
        except Exception:
            _SCROLL_BASE = None
            return None
    base = _SCROLL_BASE
    iw, ih = base.get_size()
    max_w = int(sw * 0.70)
    max_h = int(sh * 0.74)
    scale = min(max_w / iw, max_h / ih, 1.0)
    w, h = max(1, int(iw * scale)), max(1, int(ih * scale))
    key = (w, h)
    if key in _SCROLL_CACHE:
        return _SCROLL_CACHE[key]
    surf = pygame.transform.smoothscale(base, key)
    _SCROLL_CACHE[key] = surf
    return surf

def _scroll_rect(sw: int, sh: int) -> pygame.Rect:
    sc = _load_scroll_scaled(sw, sh)
    if sc is None:
        w, h = int(sw * 0.70), int(sh * 0.74)
        return pygame.Rect((sw - w)//2, (sh - h)//2, w, h)
    return sc.get_rect(center=(sw//2, sh//2))

# ---------------- Data helpers ----------------
_ICON_CACHE: dict[tuple[str, int], pygame.Surface | None] = {}

def _load_token_icon(fname: str | None, size: int) -> pygame.Surface | None:
    if not fname:
        return None
    key = (fname, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    surf = None
    for d in ("Starters", "VesselsMale", "VesselsFemale", "RareVessels", "PlayableCharacters"):
        p = os.path.join("Assets", d, fname)
        if os.path.exists(p):
            try:
                src = pygame.image.load(p).convert_alpha()
                w, h = src.get_width(), src.get_height()
                s = min(size / max(1, w), size / max(1, h))
                surf = pygame.transform.smoothscale(src, (max(1, int(w*s)), max(1, int(h*s))))
                break
            except Exception:
                pass
    _ICON_CACHE[key] = surf
    return surf

def _pretty_name(fname: str | None) -> str:
    if not fname:
        return ""
    base = os.path.splitext(os.path.basename(fname))[0]
    for p in ("StarterToken", "MToken", "FToken", "RToken"):
        if base.startswith(p):
            base = base[len(p):]
            break
    return re.sub(r"\d+$", "", base) or ""

def _hp_tuple(stats: dict | None) -> tuple[int, int]:
    if isinstance(stats, dict):
        hp = int(stats.get("hp", 10))
        cur = int(stats.get("current_hp", hp))
        cur = max(0, min(cur, hp))
        return cur, hp
    return 10, 10

# ---------------- Audio helpers ----------------
def _play_click():
    try:
        if audio_sys:
            audio_sys.play_click(audio_sys.get_global_bank())
    except Exception:
        pass

def _play_open():
    try:
        if audio_sys:
            audio_sys.play_sfx(audio_sys.get_global_bank(), "scrollopen")
    except Exception:
        _play_click()

# ---------------- Interaction state ----------------
_ITEM_RECTS: list[pygame.Rect] = []
_ITEM_INDEXES: list[int] = []
_PANEL_RECT: pygame.Rect | None = None
_SELECTED: int | None = None   # first click; second click swaps

def _swap(gs, i, j):
    names = getattr(gs, "party_slots_names", None) or [None]*6
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    slots = getattr(gs, "party_slots", None) or [None]*6
    if i == j:
        return

    if len(names) < 6: names += [None]*(6-len(names))
    if len(stats) < 6: stats += [None]*(6-len(stats))
    if len(slots) < 6: slots += [None]*(6-len(slots))

    names[i], names[j] = names[j], names[i]
    stats[i], stats[j] = stats[j], stats[i]
    slots[i], slots[j] = slots[j], slots[i]
    gs.party_slots_names = names
    gs.party_vessel_stats = stats
    gs.party_slots = slots

    act = getattr(gs, "party_active_idx", 0)
    if act == i:
        gs.party_active_idx = j
    elif act == j:
        gs.party_active_idx = i

def _set_active(gs, idx):
    names = getattr(gs, "party_slots_names", None) or [None]*6
    if 0 <= idx < len(names) and names[idx]:
        gs.party_active_idx = idx
        _play_click()

# ---------------- Event handling ----------------
def handle_event(e, gs) -> bool:
    global _SELECTED, _PANEL_RECT
    if not _OPEN:
        return False

    if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_TAB):
        close()
        _play_click()
        return True

    if e.type == pygame.MOUSEBUTTONDOWN:
        mx, my = e.pos

        if _PANEL_RECT and not _PANEL_RECT.collidepoint(mx, my):
            close()
            _play_open()
            return True

        if e.button == 1:
            for j, r in enumerate(_ITEM_RECTS):
                if r.collidepoint(mx, my):
                    real_idx = _ITEM_INDEXES[j] if j < len(_ITEM_INDEXES) else j
                    names = getattr(gs, "party_slots_names", None) or [None]*6
                    if not names[real_idx]:
                        _SELECTED = None
                        _play_click()
                        return True
                    if _SELECTED is None:
                        _SELECTED = real_idx
                        _play_click()
                        return True
                    else:
                        if _SELECTED != real_idx:
                            _swap(gs, _SELECTED, real_idx)
                        _SELECTED = None
                        _play_click()
                        return True

        if e.button == 3:
            for j, r in enumerate(_ITEM_RECTS):
                if r.collidepoint(mx, my):
                    real_idx = _ITEM_INDEXES[j] if j < len(_ITEM_INDEXES) else j
                    _set_active(gs, real_idx)
                    return True
    return False

# ---------------- Drawing ----------------
def draw(screen: pygame.Surface, gs):
    global _ITEM_RECTS, _ITEM_INDEXES, _PANEL_RECT
    if not _OPEN:
        return

    _ITEM_RECTS = []
    _ITEM_INDEXES = []

    sw, sh = screen.get_size()
    layer = pygame.Surface((sw, sh), pygame.SRCALPHA)

    dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 140))
    layer.blit(dim, (0, 0))

    sr = _scroll_rect(sw, sh)
    _PANEL_RECT = sr
    scroll = _load_scroll_scaled(sw, sh)
    if scroll is not None:
        layer.blit(scroll, sr.topleft)
    else:
        pygame.draw.rect(layer, (214, 196, 152), sr, border_radius=16)
        pygame.draw.rect(layer, (90, 70, 40), sr, 3, border_radius=16)

    old_clip = layer.get_clip()
    layer.set_clip(sr)

    side_pad = int(sr.w * 0.08)
    top_pad  = int(sr.h * 0.18)
    bot_pad  = int(sr.h * 0.16)
    inner = pygame.Rect(sr.x + side_pad, sr.y + top_pad, sr.w - side_pad*2, sr.h - (top_pad + bot_pad))
    rows = 6
    gap   = max(4, int(inner.h * 0.012))
    row_h = (inner.h - gap*(rows-1)) // rows
    icon  = max(48, int(row_h * 0.90))
    x_shift = int(inner.w * 0.08)

    name_f  = pygame.font.SysFont("georgia", max(18, int(sr.h * 0.035)), bold=True)
    small_f = pygame.font.SysFont("georgia", max(14, int(sr.h * 0.028)))
    ink      = (48, 34, 22)
    hp_back  = (62, 28, 24)
    hp_fill  = (40, 160, 84)
    sel_tint = (255, 255, 255, 48)
    act_tint = (120, 200, 255, 36)

    names = getattr(gs, "party_slots_names", None) or [None]*6
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    if len(names) < 6:
        names += [None]*(6-len(names))
    if len(stats) < 6:
        stats += [None]*(6-len(stats))
    active_idx = int(getattr(gs, "party_active_idx", 0))

    y = inner.y
    mx, my = pygame.mouse.get_pos()

    for i in range(6):
        r = pygame.Rect(inner.x + x_shift, y, inner.w - x_shift, row_h)
        icon_rect = pygame.Rect(r.x, r.y + (row_h - icon)//2, icon, icon)

        fname = names[i]
        if fname:
            if _SELECTED == i:
                s = pygame.Surface((r.w, r.h), pygame.SRCALPHA); s.fill(sel_tint); layer.blit(s, r.topleft)
            if active_idx == i:
                a = pygame.Surface((r.w, r.h), pygame.SRCALPHA); a.fill(act_tint); layer.blit(a, r.topleft)

            ico = _load_token_icon(fname, icon)
            if ico:
                layer.blit(ico, ico.get_rect(center=icon_rect.center))

            clean = _pretty_name(fname) or "Vessel"
            lvl = int((stats[i] or {}).get("level", 1)) if isinstance(stats[i], dict) else 1
            label = f"{clean}   lvl {lvl}"
            lab_s = name_f.render(label, True, ink)
            text_x = icon_rect.right + int(sr.w * 0.02)
            name_y = r.y + int(row_h * 0.10)
            layer.blit(lab_s, (text_x, name_y))

            hp, maxhp = _hp_tuple(stats[i])
            ratio = 0 if maxhp <= 0 else (hp / maxhp)
            bar_w = int(inner.w * 0.46)
            bar_h = max(10, int(row_h * 0.18))
            bar_x = text_x
            bar_y = name_y + lab_s.get_height() + 6
            bar_r = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
            pygame.draw.rect(layer, hp_back, bar_r, border_radius=6)
            if ratio > 0:
                fill = bar_r.copy(); fill.w = int(bar_r.w * ratio)
                pygame.draw.rect(layer, hp_fill, fill, border_radius=6)
            hp_s = small_f.render(f"HP {hp}/{maxhp}", True, ink)
            layer.blit(hp_s, (bar_r.right + 10, bar_r.y - 2))

            if r.collidepoint(mx, my):
                glow = pygame.Surface((r.w, r.h), pygame.SRCALPHA); glow.fill((255,255,255,28))
                layer.blit(glow, r.topleft)

            _ITEM_RECTS.append(r)
            _ITEM_INDEXES.append(i)
        # else: empty slot — draw nothing at all
        y += row_h + gap

    layer.set_clip(old_clip)

    if _FADE_START_MS is None:
        alpha = 255
    else:
        t = max(0, pygame.time.get_ticks() - _FADE_START_MS)
        alpha = 255 if FADE_MS <= 0 else min(255, int(255 * (t / FADE_MS)))
    layer.set_alpha(alpha)
    screen.blit(layer, (0, 0))
