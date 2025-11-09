# ============================================================
# combat/btn/party_action.py — button + 6-slot party popup
# - Respects Audio master SFX via systems.audio
# - Fade-in transition for the popup
# - Fainted (HP<=0) slots are greyed out & unclickable
# - Supports "forced switch" mode (cannot close until living pick)
# ============================================================
import os
import re
import pygame
import settings as S
from ._btn_layout import rect_at, load_scaled
from ._btn_draw import draw_icon_button
from systems import audio as audio_sys   # ✅ use audio system

# ---------- Button (bottom-left of the 2x2 grid) ----------
_ICON = None
_RECT = None

def _ensure_btn():
    global _ICON, _RECT
    if _RECT is None:
        _RECT = rect_at(0, 1)
    if _ICON is None:
        _ICON = load_scaled(os.path.join("Assets", "Map", "BPartyUI.png"))

def draw_button(screen: pygame.Surface):
    _ensure_btn()
    draw_icon_button(screen, _ICON, _RECT)

def is_hovering_button(pos: tuple[int, int]) -> bool:
    """
    Check if the mouse position is hovering over the party button.
    Returns True if hovering over the button, False otherwise.
    
    Args:
        pos: Mouse position tuple (x, y) in logical coordinates
    """
    _ensure_btn()
    if _RECT is None:
        return False
    return _RECT.collidepoint(pos)

def is_hovering_popup_element(pos: tuple[int, int]) -> bool:
    """
    Check if the mouse position is hovering over any clickable element in the party popup.
    Returns True if hovering over vessel rows, confirmation buttons, or the panel, False otherwise.
    
    Args:
        pos: Mouse position tuple (x, y) in logical coordinates
    """
    if not _OPEN:
        return False
    
    # Check vessel rows
    for rect in _ITEM_RECTS:
        if rect and rect.collidepoint(pos):
            return True
    
    # Check confirmation modal buttons
    if _CONFIRM:
        confirm_rects = _CONFIRM_RECTS
        if confirm_rects.get('yes') and confirm_rects['yes'].collidepoint(pos):
            return True
        if confirm_rects.get('no') and confirm_rects['no'].collidepoint(pos):
            return True
        if confirm_rects.get('panel') and confirm_rects['panel'].collidepoint(pos):
            return True
    
    # Check if mouse is over the panel
    if _PANEL_RECT and _PANEL_RECT.collidepoint(pos):
        return True
    
    return False

def handle_click(pos) -> bool:
    _ensure_btn()
    if not _RECT.collidepoint(pos):
        return False
    _play_click()       # ✅ feedback respects master
    toggle_popup()
    return True

# ---------- popup state ----------
_OPEN = False
_ITEM_RECTS: list[pygame.Rect] = []   # clickable rects (filled & alive only)
_ITEM_INDEXES: list[int] = []         # matching slot indices for each rect
_PANEL_RECT: pygame.Rect | None = None

# --- confirmation modal state ---
_CONFIRM: dict | None = None          # {"slot": int, "name": str}
_CONFIRM_RECTS = {"panel": None, "yes": None, "no": None}

# --- Fade-in state (for popup) ---
_FADE_START_MS = None
FADE_TIME_MS   = 220  # ~0.22s fade-in

# ---------- Audio helpers (bank + playback through systems.audio) ----------
def _bank():
    return getattr(S, "AUDIO_BANK", None) or audio_sys.get_global_bank()

def _play_click():
    try:
        audio_sys.play_click(_bank())
    except Exception:
        pass

def _play_open():
    """Party scroll open/close SFX (filename 'ScrollOpen.mp3' -> key 'scrollopen')."""
    try:
        audio_sys.play_sfx(_bank(), "scrollopen")
    except Exception:
        # fall back to click if missing
        _play_click()

# hover glow cache to avoid per-frame allocations
_GLOW_CACHE: dict[tuple[int, int, int], pygame.Surface] = {}

def _get_hover_glow(size: tuple[int, int], alpha: int = 36) -> pygame.Surface:
    key = (size[0], size[1], alpha)
    surf = _GLOW_CACHE.get(key)
    if surf is None:
        s = pygame.Surface(size, pygame.SRCALPHA)
        s.fill((255, 255, 255, alpha))
        _GLOW_CACHE[key] = s
        return s
    return surf

#============== Helper to request switch
def _request_switch(slot_idx: int, gs):
    try:
        names = getattr(gs, "party_slots_names", [None]*6)
        if 0 <= slot_idx < 6 and names[slot_idx]:
            gs._pending_party_switch = slot_idx  # consumed by wild_vessel
    except Exception:
        pass

# ---------- Party scroll asset + cache (aspect preserved) ----------
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
    max_w = int(sw * 0.60)
    max_h = int(sh * 0.58)
    scale = min(max_w / iw, max_h / ih, 1.0)
    w, h = max(1, int(iw * scale)), max(1, int(ih * scale))
    key = (w, h)
    if key in _SCROLL_CACHE:
        return _SCROLL_CACHE[key]
    surf = pygame.transform.smoothscale(base, key)
    _SCROLL_CACHE[key] = surf
    return surf

def _scroll_rect(sw: int, sh: int) -> pygame.Rect:
    scroll = _load_scroll_scaled(sw, sh)
    if scroll is None:
        w, h = int(sw * 0.60), int(sh * 0.58)
        return pygame.Rect((sw - w)//2, (sh - h)//2, w, h)
    return scroll.get_rect(center=(sw//2, sh//2))

def _content_metrics(sr: pygame.Rect):
    side_pad = int(sr.w * 0.08)
    top_pad  = int(sr.h * 0.22)
    bot_pad  = int(sr.h * 0.18)
    inner = pygame.Rect(
        sr.x + side_pad,
        sr.y + top_pad,
        sr.w - side_pad*2,
        sr.h - (top_pad + bot_pad),
    )
    rows = 6
    gap   = max(4, int(inner.h * 0.012))
    row_h = (inner.h - gap*(rows-1)) // rows
    icon  = max(48, int(row_h * 0.90))
    return inner, row_h, icon, gap

# ---------- Helpers ----------
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
                nw, nh = max(1, int(w * s)), max(1, int(h * s))
                surf = pygame.transform.smoothscale(src, (nw, nh))
                break
            except Exception:
                pass
    _ICON_CACHE[key] = surf
    return surf

def _pretty_name(fname: str | None) -> str:
    """Get display name for a vessel (uses name generator)."""
    if not fname:
        return ""
    from systems.name_generator import generate_vessel_name
    return generate_vessel_name(fname)

def _hp_tuple(stats: dict | None) -> tuple[int, int]:
    if isinstance(stats, dict):
        hp = int(stats.get("hp", 10))
        cur = int(stats.get("current_hp", hp))
        cur = max(0, min(cur, hp))
        return cur, hp
    return 10, 10

# ---------- Lifecycle ----------
def is_open() -> bool:
    return _OPEN

def open_popup():
    global _OPEN, _FADE_START_MS
    if _OPEN:                      # ← don't replay if already open
        return
    _OPEN = True
    _FADE_START_MS = pygame.time.get_ticks()
    _play_open()

def close_popup():
    global _OPEN, _FADE_START_MS, _CONFIRM
    was_open = _OPEN or bool(_CONFIRM)   # only sfx if we’re actually closing something
    if not was_open:
        return
    _OPEN = False
    _FADE_START_MS = None
    _CONFIRM = None
    _play_open()

def toggle_popup():
    if _OPEN:
        close_popup()
    else:
        open_popup()

# ---------- Popup events ----------
def handle_event(e, gs) -> bool:
    global _OPEN, _CONFIRM, _CONFIRM_RECTS, _PANEL_RECT, _ITEM_RECTS, _ITEM_INDEXES
    if not _OPEN:
        return False

    forced = bool(getattr(gs, "_force_switch", False))

    # Esc
    if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
        if _CONFIRM:
            _CONFIRM = None
            _play_click()  # ✅ feedback
        else:
            if forced:
                _play_click()  # cannot close while forced
                return True
            _OPEN = False
            _play_open()   # ✅ close sound
        return True

    # Confirm modal consumes clicks first
    if _CONFIRM and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
        mx, my = e.pos
        pan = _CONFIRM_RECTS.get("panel")
        yes = _CONFIRM_RECTS.get("yes")
        no  = _CONFIRM_RECTS.get("no")

        if pan and not pan.collidepoint(mx, my):
            _CONFIRM = None
            _play_click()  # ✅ click out
            return True

        if yes and yes.collidepoint(mx, my):
            _request_switch(_CONFIRM["slot"], gs)
            _CONFIRM = None
            _OPEN = False
            _play_click()
            _play_open()
            # Only consume the turn for voluntary swaps.
            if not forced:
                gs._turn_ready = False  # <-- mark turn consumed
            return True

        if no and no.collidepoint(mx, my):
            _CONFIRM = None
            _play_click()   # ✅ cancel click
            return True

        if pan and pan.collidepoint(mx, my):
            return True

    # Normal click path
    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
        mx, my = e.pos

        # outside parchment closes — unless forced
        if _PANEL_RECT and not _PANEL_RECT.collidepoint(mx, my):
            if forced:
                _play_click()
                return True
            _OPEN = False
            _play_open()  # ✅ close sound
            return True

        # click a filled & alive row → open confirm
        for j, r in enumerate(_ITEM_RECTS):
            if r.collidepoint(mx, my):
                real_idx = _ITEM_INDEXES[j] if j < len(_ITEM_INDEXES) else j
                names = getattr(gs, "party_slots_names", None) or [None]*6
                fname = names[real_idx]
                pretty = _pretty_name(fname) or "Vessel"
                _CONFIRM = {"slot": real_idx, "name": pretty}
                _play_click()  # ✅ open confirm feedback
                return True

    return False

# ---------- Popup draw ----------
def draw_popup(screen: pygame.Surface, gs):
    global _ITEM_RECTS, _ITEM_INDEXES, _PANEL_RECT, _CONFIRM_RECTS, _CONFIRM
    _ITEM_RECTS = []
    _ITEM_INDEXES = []

    sw, sh = screen.get_width(), screen.get_height()

    # === draw everything to a transparent LAYER so we can fade it in ===
    layer = pygame.Surface((sw, sh), pygame.SRCALPHA)

    # Dim background slightly (to layer)
    dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 140))
    layer.blit(dim, (0, 0))

    # Parchment
    sr = _scroll_rect(sw, sh)
    _PANEL_RECT = sr
    scroll = _load_scroll_scaled(sw, sh)
    if scroll is not None:
        layer.blit(scroll, sr.topleft)
    else:
        pygame.draw.rect(layer, (214, 196, 152), sr, border_radius=16)
        pygame.draw.rect(layer, (90, 70, 40), sr, 3, border_radius=16)

    # Clip drawing to the parchment so hover glow never bleeds out
    old_clip = layer.get_clip()
    layer.set_clip(sr)

    # Layout metrics
    inner, ROW_H, ICON_SIZE, ROW_GAP = _content_metrics(sr)

    # shift everything to the right a little (~12% of the inner width)
    x_shift = int(inner.w * 0.12)

    # Fonts & colors
    name_f  = pygame.font.SysFont("georgia", max(18, int(sr.h * 0.035)), bold=True)
    small_f = pygame.font.SysFont("georgia", max(14, int(sr.h * 0.028)))
    ink        = (48, 34, 22)
    ink_soft   = (92, 72, 52)
    hp_back    = (62, 28, 24)
    hp_fill    = (40, 160, 84)

    # Data
    names = getattr(gs, "party_slots_names", None) or [None]*6
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    if len(names) < 6: names += [None]*(6-len(names))
    if len(stats) < 6: stats += [None]*(6-len(stats))

    # --- Rows — invisible buttons; only content on parchment ---
    y = inner.y
    from systems import coords
    mx, my = coords.screen_to_logical(pygame.mouse.get_pos())

    for i in range(6):
        # move the whole row to the right
        r = pygame.Rect(inner.x + x_shift, y, inner.w - x_shift, ROW_H)
        fname = names[i]
        has   = bool(fname)

        # Icon (left column, aligned with the shifted row)
        icon_rect = pygame.Rect(r.x, r.y + (ROW_H - ICON_SIZE)//2, ICON_SIZE, ICON_SIZE)

        if has:
            # Name + level
            clean = _pretty_name(fname) or "Vessel"
            lvl = int((stats[i] or {}).get("level", 1)) if isinstance(stats[i], dict) else 1

            text_x = icon_rect.right + int(sr.w * 0.02)
            label      = f"{clean}   Lv {lvl}"
            label_surf = name_f.render(label, True, ink)
            name_y     = r.y + int(ROW_H * 0.10)

            # HP
            hp, maxhp = _hp_tuple(stats[i])
            ratio = 0 if maxhp <= 0 else (hp / maxhp)
            dead = (hp <= 0)

            # soft hover glow only if alive and no confirm modal
            if not dead and r.collidepoint(mx, my) and not _CONFIRM:
                layer.blit(_get_hover_glow((r.w, r.h), 36), r.topleft)

            # icon
            icon_surf = _load_token_icon(fname, ICON_SIZE)
            if icon_surf is not None:
                layer.blit(icon_surf, icon_surf.get_rect(center=icon_rect.center).topleft)

            # label
            layer.blit(label_surf, (text_x, name_y))

            # HP bar — LEFT, just under the label
            bar_w = int(inner.w * 0.42)
            bar_h = max(10, int(ROW_H * 0.18))
            bar_x = text_x
            bar_y = name_y + label_surf.get_height() + 6

            bar_r = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
            pygame.draw.rect(layer, hp_back, bar_r, border_radius=6)
            if ratio > 0:
                fill = bar_r.copy()
                fill.w = int(bar_r.w * ratio)
                pygame.draw.rect(layer, hp_fill, fill, border_radius=6)

            # HP text to the right of the bar
            hp_s = small_f.render(f"HP {hp}/{maxhp}", True, ink)
            layer.blit(hp_s, (bar_r.right + 10, bar_r.y - 2))

            # register invisible click target + which slot it is (alive only)
            if not dead:
                _ITEM_RECTS.append(r)
                _ITEM_INDEXES.append(i)

            # Add visual dim / "Fainted" tag for dead rows
            if dead:
                dim = _get_hover_glow((r.w, r.h), 80)
                layer.blit(dim, r.topleft)
                faint = small_f.render("Fainted", True, (110, 90, 90))
                layer.blit(faint, (bar_r.right + 10, bar_r.y - 2))

        # next row
        y += ROW_H + ROW_GAP

    # Footer (subtle)
    foot = small_f.render("Press Esc to cancel", True, ink_soft)
    layer.blit(foot, foot.get_rect(midbottom=(sr.centerx, sr.bottom - int(sr.h*0.07))))

    # ===== Confirmation modal (on top of parchment) =====
    _CONFIRM_RECTS = {"panel": None, "yes": None, "no": None}
    if _CONFIRM:
        # Slight extra dim over the parchment
        dim2 = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim2.fill((0, 0, 0, 90))
        layer.blit(dim2, (0, 0))

        # Panel size anchored to scroll rect
        pw = int(sr.w * 0.62)
        ph = int(sr.h * 0.28)
        panel = pygame.Rect(0, 0, pw, ph)
        panel.center = sr.center
        _CONFIRM_RECTS["panel"] = panel

        # Panel look (parchment-like)
        pygame.draw.rect(layer, (214, 196, 152), panel, border_radius=14)
        pygame.draw.rect(layer, (90, 70, 40), panel, 3, border_radius=14)

        # Text
        title_f = pygame.font.SysFont("georgia", max(20, int(ph * 0.18)), bold=True)
        body_f = pygame.font.SysFont("georgia", max(18, int(ph * 0.15)))
        ink = (48, 34, 22)

        title = title_f.render("Confirm Swap", True, ink)
        layer.blit(title, title.get_rect(midtop=(panel.centerx, panel.y + int(ph * 0.10))))

        msg = body_f.render(f"Swap to “{_CONFIRM['name']}”?", True, ink)
        layer.blit(msg, msg.get_rect(midtop=(panel.centerx, panel.y + int(ph * 0.34))))

        # YES / NO buttons
        bw = int(pw * 0.30)
        bh = int(ph * 0.28)
        gap = int(pw * 0.06)

        yes_rect = pygame.Rect(0, 0, bw, bh)
        no_rect  = pygame.Rect(0, 0, bw, bh)

        total_w = bw * 2 + gap
        left_x = panel.centerx - total_w // 2
        yes_rect.topleft = (left_x, panel.y + int(ph * 0.58))
        no_rect.topleft  = (left_x + bw + gap, panel.y + int(ph * 0.58))

        _CONFIRM_RECTS["yes"] = yes_rect
        _CONFIRM_RECTS["no"]  = no_rect

        # Get mouse pos for hover highlight (already converted to logical above)
        # mx, my already converted to logical coordinates above

        def _button(rect, label, hover=False):
            # base
            pygame.draw.rect(layer, (214, 196, 152), rect, border_radius=12)
            pygame.draw.rect(layer, (90, 70, 40), rect, 3, border_radius=12)
            if hover:
                glow = _get_hover_glow((rect.w, rect.h), 48)
                layer.blit(glow, rect.topleft)
            lab = title_f.render(label, True, ink)
            layer.blit(lab, lab.get_rect(center=rect.center))

        # Draw YES / NO with hover glow if under mouse
        _button(yes_rect, "YES", hover=yes_rect.collidepoint(mx, my))
        _button(no_rect,  "NO",  hover=no_rect.collidepoint(mx, my))

    # restore previous clip on the layer
    layer.set_clip(old_clip)

    # === Fade-in composite ===
    now = pygame.time.get_ticks()
    if _FADE_START_MS is None:
        alpha = 255
    else:
        t = max(0, now - _FADE_START_MS)
        alpha = 255 if FADE_TIME_MS <= 0 else min(255, int(255 * (t / FADE_TIME_MS)))

    layer.set_alpha(alpha)
    screen.blit(layer, (0, 0))
