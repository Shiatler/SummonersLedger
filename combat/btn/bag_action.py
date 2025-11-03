# ============================================================
# combat/btn/bag_action.py
# ============================================================
import os
import sys
import importlib
import pygame
from ._btn_layout import rect_at, load_scaled
from ._btn_draw import draw_icon_button
from systems import audio as audio_sys
import re
from screens import party_manager

# NEW:
import random
try:
    from rolling.roller import Roller
    _ROLLER = Roller()
except Exception:
    _ROLLER = None

# ---------------- Use callback ----------------
_USE_CALLBACK = None  # fn(gs, item_dict) -> bool (True => consume one)
_LAST_ITEMS = []  # kept in sync with _ITEM_RECTS during draw

def set_use_item_callback(fn):
    """
    Register a function that handles 'use item' when the user clicks a row.
    Signature: fn(gs, item) -> bool
      - item: {"id", "name", "qty", "icon"}
      - return True if the item should be CONSUMED (qty -1), else False
    """
    global _USE_CALLBACK
    _USE_CALLBACK = fn

# ---------------- Button assets ----------------
_ICON = None
_RECT = None

def _ensure_btn():
    global _ICON, _RECT
    if _RECT is None:
        _RECT = rect_at(1, 0)  # top-right in 2x2 grid
    if _ICON is None:
        _ICON = load_scaled(os.path.join("Assets", "Map", "BBagUI.png"))

def draw_button(screen: pygame.Surface):
    _ensure_btn()
    draw_icon_button(screen, _ICON, _RECT)

# ---------------- Popup state/media ----------------
_OPEN = False
_PANEL_RECT = None  # image rect
_LAST_DRAW_TICKS = 0

_BAG_IMG = None
_BAG_IMG_PATH = os.path.join("Assets", "Map", "boh.png")
_SCALED_CACHE = {}

_OPEN_SFX_PATH = os.path.join("Assets", "Music", "Sounds", "boh.mp3")
_BOH_SND = None

# Healing scroll sounds
_HEALING_SFX_BASE = os.path.join("Assets", "Music", "Sounds")
_HEALING_SOUNDS = {
    "scroll_of_healing": None,
    "scroll_of_mending": None,
    "scroll_of_regeneration": None,
    "scroll_of_revivity": None,
}

def _ensure_sfx():
    global _BOH_SND
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        if _BOH_SND is None and os.path.exists(_OPEN_SFX_PATH):
            _BOH_SND = pygame.mixer.Sound(_OPEN_SFX_PATH)
    except Exception as e:
        print(f"⚠️ bag_action: audio init/load failed: {e}")

def _ensure_healing_sfx():
    """Load healing scroll sound effects if not already loaded."""
    global _HEALING_SOUNDS
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        
        # Map item IDs to sound filenames
        sound_map = {
            "scroll_of_healing": "Healing.mp3",
            "scroll_of_mending": "Mending.mp3",
            "scroll_of_regeneration": "Regeneration.mp3",
            "scroll_of_revivity": "Revivity.mp3",
        }
        
        for item_id, filename in sound_map.items():
            if _HEALING_SOUNDS.get(item_id) is None:
                sound_path = os.path.join(_HEALING_SFX_BASE, filename)
                if os.path.exists(sound_path):
                    _HEALING_SOUNDS[item_id] = pygame.mixer.Sound(sound_path)
                else:
                    print(f"⚠️ bag_action: healing sound not found: {sound_path}")
    except Exception as e:
        print(f"⚠️ bag_action: healing SFX load failed: {e}")

def _play_healing_sound(item_id: str):
    """Play the appropriate healing sound for the given scroll item."""
    _ensure_healing_sfx()
    sound = _HEALING_SOUNDS.get(item_id)
    if sound:
        audio_sys.play_sound(sound)
    else:
        # Fallback to click sound if healing sound not available
        audio_sys.play_click(audio_sys.get_global_bank())

def _play_boh(fade_ms=120):
    _ensure_sfx()
    if _BOH_SND:
        audio_sys.play_sound(_BOH_SND)  # master-controlled
    else:
        audio_sys.play_click(audio_sys.get_global_bank())

# visual fade
_FADE_DUR = 0.20
_FADE_T0 = 0

# ---- Bag size controls ----
BAG_FIT_W = 2.5  # <= 1.0 — max fraction of screen width
BAG_FIT_H = 2.5  # <= 1.0 — max fraction of screen height
ABSOLUTE_SCALE = 2.5  # set None to auto-fit, or a number (e.g. 2.5)

# Fixed, short list box (ignore bag width)
_BOX_POS_REL = (0.5, 0.55)  # where the box is centered inside the *visible* bag (x%, y%)
_BOX_SIZE_PX = (700, 400)  # width, height in pixels

# Tight “Pokémon-ish” metrics
_ROW_H = 72  # per row height
_ROW_GAP = 6  # vertical gap
_ICON_SZ = 64  # small square icon frame
_SCROLL_SPEED = 36  # px per wheel step
_QTY_RIGHT_MARGIN = 8
_SB_TRACK_INSET = 3

_VIEWPORT_RECT = None
_SCROLL_Y = 0
_TOTAL_CONTENT_H = 0
_ITEM_RECTS = []
_ITEM_INDEXES = []  # Maps rect index to actual item index in _LAST_ITEMS

# ---------- Healing item helpers ----------
_HEAL_PENDING = None  # {"item": dict}

def _is_heal_item(item_id: str) -> bool:
    iid = (item_id or "").lower()
    return iid in ("scroll_of_mending", "scroll_of_regeneration", "scroll_of_revivity", "scroll_of_healing")

def _heal_roll(num_dice: int, die_size: int = 8) -> int:
    """Roll healing dice. Default is d8, but can roll other sizes (e.g., d4 for Mending)."""
    if _ROLLER:
        total = 0
        for _ in range(num_dice):
            r = _ROLLER.roll_die(die_size)
            total += int(r or 1)
        return max(1, total)
    return sum(random.randint(1, die_size) for _ in range(num_dice))

def _con_mod(stats: dict) -> int:
    try:
        if "con_mod" in stats:
            return int(stats["con_mod"])
        con = int(stats.get("CON") or stats.get("con") or 10)
        return (con - 10) // 2
    except Exception:
        return 0

def _apply_heal_or_revive(gs, idx: int, item_id: str) -> None:
    stats_list = getattr(gs, "party_vessel_stats", None) or []
    if not (0 <= idx < len(stats_list)):
        return
    st = stats_list[idx]
    if not isinstance(st, dict):
        return

    max_hp = int(st.get("hp", 1))
    cur_hp = int(st.get("current_hp", max_hp))
    cm = _con_mod(st)

    if item_id == "scroll_of_revivity":
        if cur_hp > 0:
            return
        # Revives dead ally and heals 2d8
        heal = _heal_roll(2)
        st["current_hp"] = min(max_hp, max(1, heal))
    elif item_id == "scroll_of_mending":
        heal = _heal_roll(1, 4) + cm  # 1d4 + CON for Scroll of Mending
        st["current_hp"] = min(max_hp, max(0, cur_hp) + max(1, heal))
    elif item_id == "scroll_of_regeneration":
        heal = _heal_roll(2) + cm
        st["current_hp"] = min(max_hp, max(0, cur_hp) + max(1, heal))
    elif item_id == "scroll_of_healing":
        heal = _heal_roll(1) + cm  # 1d8 + CON for Scroll of Healing
        st["current_hp"] = min(max_hp, max(0, cur_hp) + max(1, heal))
    else:
        return

    try:
        gs._turn_ready = False
    except Exception:
        pass

    _decrement_inventory(gs, item_id)
    audio_sys.play_click(audio_sys.get_global_bank())

# --- Small icon cache for item thumbnails ---
_ICON_CACHE = {}

def _get_icon_surface(path: str | None, size: int) -> pygame.Surface | None:
    if not path or not os.path.exists(path):
        return None
    key = (path, size)
    surf = _ICON_CACHE.get(key)
    if surf is not None:
        return surf
    try:
        base = pygame.image.load(path).convert_alpha()
        bw, bh = base.get_size()
        s = min(size / max(1, bw), size / max(1, bh))
        w, h = max(1, int(bw * s)), max(1, int(bh * s))
        surf = pygame.transform.smoothscale(base, (w, h))
        _ICON_CACHE[key] = surf
        return surf
    except Exception as e:
        print(f"⚠️ bag_action: failed to load icon '{path}': {e}")
        _ICON_CACHE[key] = None
        return None

# ---------------- Inventory plumbing ----------------
_FONT_CACHE = {}

def _font(px: int, bold=False) -> pygame.font.Font:
    key = (px, bold)
    f = _FONT_CACHE.get(key)
    if f is None:
        try:
            f = pygame.font.SysFont("georgia", max(12, px), bold=bold)
        except Exception:
            f = pygame.font.SysFont(None, max(12, px), bold=bold)
        _FONT_CACHE[key] = f
    return f

def _snake_from_name(s: str) -> str:
    s = (s or "").strip()
    s = s.replace("’", "'")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s.lower()

def _title_from_id(item_id: str) -> str:
    return item_id.replace("_", " ").title().replace(" Of ", " of ")

def _icon_for(item_id: str):
    fname = "_".join(part.capitalize() for part in item_id.split("_")) + ".png"
    path = os.path.join("Assets", "Items", fname)
    return path if os.path.exists(path) else None

def _load_items_from_module():
    importlib.invalidate_caches()
    for mod_name in ("items.items", "items"):
        try:
            mod = importlib.reload(sys.modules[mod_name]) if mod_name in sys.modules else importlib.import_module(mod_name)
        except Exception:
            continue
        data = None
        if hasattr(mod, "items") and callable(mod.items):
            try:
                data = mod.items()
            except Exception:
                data = None
        if data is None and hasattr(mod, "ITEMS"):
            data = getattr(mod, "ITEMS")
        if not isinstance(data, (list, tuple)):
            continue
        out = []
        for it in data:
            if isinstance(it, dict):
                name = str(it.get("name") or it.get("id") or "")
                try:
                    qty = int(it.get("qty", 0))
                except Exception:
                    qty = 0
                iid = it.get("id") or _snake_from_name(name)
                icon = it.get("icon") or _icon_for(iid)
                nid = _snake_from_name(iid or name)
                out.append({"id": nid, "name": name or _title_from_id(nid), "qty": qty, "icon": icon})
            elif isinstance(it, (list, tuple)) and it:
                name = str(it[0])
                qty = int(it[1]) if len(it) > 1 else 0
                iid = _snake_from_name(name)
                out.append({"id": iid, "name": name, "qty": qty, "icon": _icon_for(iid)})
        return out
    return []

def _items_from_gs(gs):
    out = []
    inv = getattr(gs, "inventory", None) or {}

    if isinstance(inv, dict):
        normalized = {}
        for raw_id, qty in inv.items():
            try:
                q = int(qty)
            except Exception:
                q = 0
            nid = _snake_from_name(str(raw_id))
            normalized[nid] = normalized.get(nid, 0) + max(0, q)

        gs.inventory = normalized

        for nid, q in normalized.items():
            name = _title_from_id(nid)
            out.append({"id": nid, "name": name, "qty": q, "icon": _icon_for(nid)})
        return out

    if isinstance(inv, (list, tuple)):
        for rec in inv:
            if not isinstance(rec, dict):
                if isinstance(rec, (list, tuple)) and rec:
                    item_id = str(rec[0])
                    q = int(rec[1]) if len(rec) > 1 else 0
                    out.append({"id": item_id, "name": _title_from_id(item_id), "qty": q, "icon": _icon_for(item_id)})
                continue

            item_id = rec.get("id")
            name = rec.get("name")
            qty = rec.get("qty", 0)

            if not item_id and name:
                item_id = _snake_from_name(name)
            if not name and item_id:
                name = _title_from_id(item_id)

            try:
                q = int(qty)
            except Exception:
                q = 0

            if item_id or name:
                iid = item_id or _snake_from_name(name)
                out.append({"id": iid, "name": name or _title_from_id(iid), "qty": q, "icon": _icon_for(iid)})
        return out

    return []

def _get_items(gs=None):
    if gs and getattr(gs, "inventory", None):
        return _items_from_gs(gs)
    return _load_items_from_module()

# ---------- Inventory mutation (consume one) ----------
def _decrement_inventory(gs, item_id: str) -> None:
    inv = getattr(gs, "inventory", None)
    if inv is None:
        return

    if isinstance(inv, dict):
        if item_id in inv:
            inv[item_id] = max(0, int(inv[item_id]) - 1)
            if inv[item_id] <= 0:
                try:
                    del inv[item_id]
                except Exception:
                    pass
        gs.inventory = inv
        return

    if isinstance(inv, (list, tuple)):
        new_list = []
        found = False
        for rec in inv:
            if isinstance(rec, dict):
                rid = rec.get("id") or _snake_from_name(rec.get("name", ""))
                if rid == item_id and not found:
                    qty = max(0, int(rec.get("qty", 0)) - 1)
                    found = True
                    if qty > 0:
                        rec["qty"] = qty
                        new_list.append(rec)
                else:
                    new_list.append(rec)
            elif isinstance(rec, (list, tuple)) and len(rec) >= 1:
                rid = str(rec[0])
                if rid == item_id and not found:
                    q = int(rec[1]) if len(rec) > 1 else 0
                    q = max(0, q - 1)
                    found = True
                    if q > 0:
                        new_list.append([rid, q])
                else:
                    new_list.append(rec)
            else:
                new_list.append(rec)
        gs.inventory = new_list
        return

# ---------------- Media helpers ----------------
def _ensure_media():
    global _BAG_IMG
    if _BAG_IMG is None and os.path.exists(_BAG_IMG_PATH):
        try:
            _BAG_IMG = pygame.image.load(_BAG_IMG_PATH).convert_alpha()
        except Exception as e:
            print(f"⚠️ bag_action: failed to load boh.png: {e}")
            _BAG_IMG = None

def _scaled_bag(sw: int, sh: int) -> pygame.Surface | None:
    _ensure_media()
    base = _BAG_IMG
    if base is None:
        return None
    key = (sw, sh, ABSOLUTE_SCALE, BAG_FIT_W, BAG_FIT_H)
    if key in _SCALED_CACHE:
        return _SCALED_CACHE[key]

    bw, bh = base.get_width(), base.get_height()

    if ABSOLUTE_SCALE is not None:
        w = int(bw * ABSOLUTE_SCALE)
        h = int(bh * ABSOLUTE_SCALE)
        fit_w = int(sw * BAG_FIT_W)
        fit_h = int(sh * BAG_FIT_H)
        if w > fit_w or h > fit_h:
            s = min(fit_w / max(1, w), fit_h / max(1, h))
            w = max(1, int(w * s))
            h = max(1, int(h * s))
    else:
        fit_w = int(sw * BAG_FIT_W)
        fit_h = int(sh * BAG_FIT_H)
        s = min(fit_w / max(1, bw), fit_h / max(1, bh))
        w = max(1, int(bw * s))
        h = max(1, int(bh * s))

    surf = pygame.transform.smoothscale(base, (w, h))
    _SCALED_CACHE[key] = surf
    return surf

# ---------------- Lifecycle ----------------
def is_open() -> bool: return _OPEN

def open_popup():
    global _OPEN, _FADE_T0, _SCROLL_Y
    if _OPEN:  # already open? don't replay SFX
        return
    _OPEN = True
    _FADE_T0 = pygame.time.get_ticks()
    _SCROLL_Y = 0
    _play_boh(fade_ms=int(_FADE_DUR * 1000))

def close_popup():
    global _OPEN
    if not _OPEN:  # only play if we’re actually closing it
        return
    _OPEN = False
    _play_boh(fade_ms=120)

def toggle_popup():
    close_popup() if _OPEN else open_popup()

# ---------------- Button input ----------------
def handle_click(pos) -> bool:
    _ensure_btn()
    if not _RECT.collidepoint(pos):
        return False
    audio_sys.play_click(audio_sys.get_global_bank())
    toggle_popup()
    return True

# ---------------- Modal input (ESC, click-outside, scroll, row-click) ----------------
def handle_event(e, gs, screen=None) -> bool:
    # Get screen from pygame if not provided
    if screen is None:
        screen = pygame.display.get_surface()
        if screen is None:
            return False
    
    global _SCROLL_Y, _PANEL_RECT

    if not _OPEN:
        return False

    if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
        close_popup()
        return True

    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
        if _PANEL_RECT is None or not _PANEL_RECT.collidepoint(e.pos):
            close_popup()
            return True
        
        for i, r in enumerate(_ITEM_RECTS):
            if r.collidepoint(e.pos):
                # Get the actual item index using the mapping
                actual_idx = _ITEM_INDEXES[i] if i < len(_ITEM_INDEXES) else i
                if 0 <= actual_idx < len(_LAST_ITEMS):
                    item = _LAST_ITEMS[actual_idx]
                    item_id = _snake_from_name(item.get("id") or item.get("name", ""))

                    # Handle item usage
                    if int(item.get("qty", 0)) <= 0:
                        audio_sys.play_click(audio_sys.get_global_bank())
                        return True

                    if _USE_CALLBACK:
                        consume = False
                        try:
                            consume = bool(_USE_CALLBACK(gs, item))
                        except Exception as ex:
                            print(f"⚠️ bag_action: use callback error: {ex}")
                        if consume:
                            _decrement_inventory(gs, item_id)
                            try:
                                gs._turn_ready = False
                            except Exception:
                                pass
                            audio_sys.play_click(audio_sys.get_global_bank())
                            return True

                    # Handle healing items
                    if _is_heal_item(item_id):
                        # If callback exists and already consumed the item, we would have returned above
                        # So if we reach here, either no callback exists or callback didn't consume it
                        # In either case, handle healing items directly
                        if item_id == "scroll_of_mending":
                            party_manager.start_use_mode({"kind": "heal", "dice": (1, 4), "add_con": True, "revive": False, "item_id": item_id})
                        elif item_id == "scroll_of_regeneration":
                            party_manager.start_use_mode({"kind": "heal", "dice": (2, 8), "add_con": True, "revive": False, "item_id": item_id})
                        elif item_id == "scroll_of_revivity":
                            party_manager.start_use_mode({"kind": "heal", "dice": (2, 8), "add_con": False, "revive": True, "item_id": item_id})
                        elif item_id == "scroll_of_healing":
                            party_manager.start_use_mode({"kind": "heal", "dice": (1, 8), "add_con": True, "revive": False, "item_id": item_id})

                        # Don't decrement inventory here - party_manager will handle it after healing is applied
                        close_popup()
                        return True

    # Scrolling inside the bag
    if e.type == pygame.MOUSEWHEEL:
        # Ensure panel rect is set - calculate it if needed (matches draw_popup logic)
        if _PANEL_RECT is None:
            sw, sh = screen.get_width(), screen.get_height()
            popup = _scaled_bag(sw, sh)
            if popup:
                _PANEL_RECT = popup.get_rect(center=(sw // 2, sh // 2))
            else:
                # Fallback calculation (matches draw_popup fallback)
                margin_w = int(sw * 0.06)
                margin_h = int(sh * 0.12)
                _PANEL_RECT = pygame.Rect(margin_w, margin_h, sw - margin_w * 2, sh - margin_h * 2)
        
        # Initialize viewport and content height by calling draw function
        _draw_inventory_on_popup(screen, _PANEL_RECT, 1, gs)
        
        # Check if mouse is over the viewport area
        mouse_pos = pygame.mouse.get_pos()
        if _VIEWPORT_RECT and _VIEWPORT_RECT.collidepoint(mouse_pos):
            # Calculate max scroll based on content height
            if _TOTAL_CONTENT_H > 0 and _VIEWPORT_RECT.h > 0:
                max_scroll = max(0, _TOTAL_CONTENT_H - _VIEWPORT_RECT.h)
                _SCROLL_Y = max(0, min(_SCROLL_Y - e.y * _SCROLL_SPEED, max_scroll))

                # Recalculate the rect positions after scroll
                _ITEM_RECTS.clear()
                _ITEM_INDEXES.clear()
                _draw_inventory_on_popup(screen, _PANEL_RECT, 1, gs)

            return True

    # Return False if we didn't handle this event (so other handlers can process it)
    return False





# ---------------- Inventory drawing (inside invisible box) ----------------
def _draw_inventory_on_popup(screen: pygame.Surface, popup_rect: pygame.Rect, fade_alpha: float, gs):
    global _ITEM_RECTS, _VIEWPORT_RECT, _TOTAL_CONTENT_H, _LAST_ITEMS, _ITEM_INDEXES

    # only use on-screen part of the bag
    vis = popup_rect.clip(screen.get_rect())

    # --- FIXED short box: center at relative position, use pixel size ---
    cx = vis.x + int(vis.w * _BOX_POS_REL[0])
    cy = vis.y + int(vis.h * _BOX_POS_REL[1])
    vw, vh = _BOX_SIZE_PX

    vx = cx - vw // 2
    vy = cy - vh // 2

    # clamp to the visible bag so it never spills off-screen
    box = pygame.Rect(vx, vy, vw, vh)
    box.clamp_ip(vis)
    _VIEWPORT_RECT = box

    items = _get_items(gs)
    _LAST_ITEMS = items[:]  # full list of all items
    _ITEM_RECTS = []  # only visible item rects
    _ITEM_INDEXES = []  # maps _ITEM_RECTS index to _LAST_ITEMS index

    layer = pygame.Surface((vw, vh), pygame.SRCALPHA)
    name_font = _font(30, bold=False)
    qty_font  = _font(30, bold=False)
    ink       = (232, 220, 180)
    ink_dim   = (150, 130, 100)

    # total content height for scrolling/clamp
    if items:
        _TOTAL_CONTENT_H = len(items) * _ROW_H + (len(items) - 1) * _ROW_GAP
    else:
        _TOTAL_CONTENT_H = 0

    max_scroll = max(0, _TOTAL_CONTENT_H - vh)
    if _SCROLL_Y > max_scroll:
        globals()['_SCROLL_Y'] = max_scroll

    # --- scrollbar metrics (used both for drawing and qty padding) ---
    has_scrollbar = max_scroll > 0
    sb_w = max(6, int(vw * 0.012)) if has_scrollbar else 0

    # local mouse for hover
    mx, my = pygame.mouse.get_pos()
    local_mouse = (mx - vx, my - vy)

    y = -_SCROLL_Y
    if not items:
        msg = "No items yet"
        txt = name_font.render(msg, True, ink_dim)
        layer.blit(txt, txt.get_rect(center=(vw//2, vh//2)))
    else:
        for idx, it in enumerate(items):
            row_rect = pygame.Rect(0, y, vw, _ROW_H)
            if row_rect.bottom < 0:
                y += _ROW_H + _ROW_GAP
                continue
            if row_rect.top > vh:
                break

            # hover highlight
            if row_rect.collidepoint(local_mouse):
                hover = pygame.Surface((row_rect.w, row_rect.h), pygame.SRCALPHA)
                hover.fill((255, 255, 255, 22))
                layer.blit(hover, row_rect.topleft)

            # --- ICON only (no frame) ---
            icon_path = it.get("icon")
            if icon_path:
                # load with a slightly larger target so it fills its row nicely
                icon_surf = _get_icon_surface(icon_path, int(_ROW_H * 0.9))
                if icon_surf:
                    ir = icon_surf.get_rect()
                    # vertically center the icon in the row
                    ir.midleft = (row_rect.x + 8, row_rect.centery)
                    layer.blit(icon_surf, ir)
                name_x = ir.right + 12
            else:
                # fallback spacing if no icon
                name_x = row_rect.x + 10

            # name
            name = it.get("name") or ""
            name_s = name_font.render(name, True, ink if name else ink_dim)
            layer.blit(name_s, name_s.get_rect(midleft=(name_x, row_rect.centery)))



            # qty right aligned (pad away from scrollbar)
            qty = it.get("qty", None)
            if isinstance(qty, int):
                qty_s = qty_font.render(f"x{qty}", True, ink)
                qty_right_edge = row_rect.right - (sb_w + _SB_TRACK_INSET + _QTY_RIGHT_MARGIN if has_scrollbar
                                                   else _QTY_RIGHT_MARGIN)
                layer.blit(qty_s, qty_s.get_rect(midright=(qty_right_edge, row_rect.centery)))

            # register absolute click rect
            # Convert row_rect.y (layer-relative) to screen-absolute position
            # row_rect.y is relative to layer, layer is blitted at (vx, vy)
            # So absolute screen position is (vx, vy) + (row_rect.x, row_rect.y)
            abs_x = vx + row_rect.x
            abs_y = vy + row_rect.y
            _ITEM_RECTS.append(pygame.Rect(abs_x, abs_y, row_rect.w, row_rect.h))
            _ITEM_INDEXES.append(idx)  # Store the actual item index

            y += _ROW_H + _ROW_GAP

        # simple scrollbar (draw after rows)
        if has_scrollbar:
            sb_h = max(24, int(vh * (vh / (_TOTAL_CONTENT_H + 1e-6))))
            sb_x = vw - sb_w - _SB_TRACK_INSET
            sb_y = int((_SCROLL_Y / max_scroll) * (vh - sb_h))
            pygame.draw.rect(layer, (0, 0, 0, 60), (sb_x, 0, sb_w, vh), border_radius=4)
            pygame.draw.rect(layer, (220, 210, 180, 160), (sb_x, sb_y, sb_w, sb_h), border_radius=4)

    layer.set_alpha(int(255 * fade_alpha))
    screen.blit(layer, (vx, vy))

# ---------------- Drawing ----------------
def draw_popup(screen: pygame.Surface, gs):
    """
    Dim background, draw boh.png centered & large (with fade),
    then draw the inventory viewport on top.
    """
    global _PANEL_RECT, _LAST_DRAW_TICKS
    sw, sh = screen.get_width(), screen.get_height()
    _LAST_DRAW_TICKS = pygame.time.get_ticks()

    # fade 0..1
    a = 1.0 if _FADE_T0 <= 0 else min(1.0, max(0.0, (_LAST_DRAW_TICKS - _FADE_T0) / max(1, int(_FADE_DUR * 1000))))

    # dim layer
    dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
    dim.fill((0, 0, 0, int(180 * a)))
    screen.blit(dim, (0, 0))

    popup = _scaled_bag(sw, sh)
    if popup is None:
        # fallback panel if png missing
        margin_w = int(sw * 0.06)
        margin_h = int(sh * 0.12)
        rect = pygame.Rect(margin_w, margin_h, sw - margin_w * 2, sh - margin_h * 2)
        _PANEL_RECT = rect
        tmp = pygame.Surface(rect.size, pygame.SRCALPHA)
        base = (212, 196, 152, int(255 * a))
        frame = (92, 70, 40, int(255 * a))
        pygame.draw.rect(tmp, base, tmp.get_rect(), border_radius=18)
        pygame.draw.rect(tmp, frame, tmp.get_rect(), 4, border_radius=18)
        screen.blit(tmp, rect.topleft)
        return

    # popup fade
    if a < 1.0:
        popup_surf = popup.copy()
        popup_surf.fill((255, 255, 255, int(255 * a)), special_flags=pygame.BLEND_RGBA_MULT)
    else:
        popup_surf = popup

    rect = popup_surf.get_rect(center=(sw // 2, sh // 2))
    _PANEL_RECT = rect
    screen.blit(popup_surf, rect.topleft)

    # inventory viewport
    _draw_inventory_on_popup(screen, rect, a, gs)
