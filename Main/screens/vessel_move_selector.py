# ============================================================
# screens/vessel_move_selector.py — Vessel Move Selection Popup
# Shows vessel moves and allows player to select which move to add PP to
# Uses the same design as ledger.py
# ============================================================

import os
import re
import pygame
import settings as S
from typing import Optional
from systems import audio as audio_sys

# Font helper (matches ledger.py)
_FONT_CACHE: dict[tuple, pygame.font.Font] = {}
def _get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Load DH font if available, fallback to system font (matches ledger.py)."""
    key = ("move_selector", size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    try:
        path = os.path.join(S.ASSETS_FONTS_DIR, getattr(S, "DND_FONT_FILE", "DH.otf"))
        f = pygame.font.Font(path, size)
        if bold:
            # Try to make it bold if possible
            try:
                f = pygame.font.Font(path, size)
                # Some fonts don't support bold, so we'll use regular
            except Exception:
                pass
    except Exception:
        try:
            f = pygame.font.SysFont("georgia", size, bold=bold)
        except Exception:
            f = pygame.font.Font(None, size)
    _FONT_CACHE[key] = f
    return f

# Background image (same as ledger)
_POPUP_BG_PATH = os.path.join("Assets", "Map", "PartyLedger.png")
_popup_bg: pygame.Surface | None = None

def _get_popup_bg() -> pygame.Surface | None:
    """Load and cache the ledger background image."""
    global _popup_bg
    if _popup_bg is not None:
        return _popup_bg
    if not os.path.exists(_POPUP_BG_PATH):
        return None
    try:
        img = pygame.image.load(_POPUP_BG_PATH).convert_alpha()
        iw, ih = img.get_size()
        max_w, max_h = int(S.LOGICAL_WIDTH * 0.75), int(S.LOGICAL_HEIGHT * 0.75)
        scale = min(max_w / iw, max_h / ih, 1.0)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        _popup_bg = pygame.transform.smoothscale(img, (nw, nh))
        return _popup_bg
    except Exception as e:
        print(f"⚠️ Failed to load ledger background: {e}")
        return None

def _try_load(path: str | None):
    """Try to load an image file."""
    if not path:
        return None
    if os.path.exists(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"⚠️ load fail {path}: {e}")
    return None

def _full_vessel_from_token_name(token_name: str | None) -> pygame.Surface | None:
    """Load vessel image from token name (handles monsters)."""
    if not token_name:
        return None
    # Use asset_links for proper token->vessel conversion (handles monsters)
    from systems.asset_links import token_to_vessel, find_image
    vessel_name = token_to_vessel(token_name)
    if vessel_name:
        path = find_image(vessel_name)
        if path and os.path.exists(path):
            return _try_load(path)
    return None

def _fit_center(surf: pygame.Surface, rect: pygame.Rect) -> tuple[pygame.Surface, pygame.Rect]:
    """Fit surface to rect while maintaining aspect ratio, centered."""
    iw, ih = surf.get_size()
    scale = min(rect.w / iw, rect.h / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    scaled = pygame.transform.smoothscale(surf, (nw, nh))
    dest = scaled.get_rect(center=rect.center)
    return scaled, dest

# Animation state
_ANIM_IN_SECS = 0.28
_ANIM_OUT_SECS = 0.22
_OVERLAY_MAX_A = 180
_SCALE_MIN = 0.98
_SLIDE_PIXELS = 80

def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

def _ease_out_cubic(p: float) -> float:
    p = _clamp01(p)
    return 1.0 - (1.0 - p) ** 3

# State
_ACTIVE = False
_STATE = None

def is_active() -> bool:
    """Check if move selector is active."""
    return _ACTIVE

def start_move_selection(gs, vessel_idx: int, pp_amount: int):
    """Start move selection for a vessel."""
    global _ACTIVE, _STATE
    
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    if not (0 <= vessel_idx < len(stats_list)) or not stats_list[vessel_idx]:
        return False
    
    vessel_stats = stats_list[vessel_idx]
    vessel_name = names[vessel_idx] if vessel_idx < len(names) else None
    
    # Get vessel display name
    from systems.name_generator import generate_vessel_name
    display_name = generate_vessel_name(vessel_name) if vessel_name else "Vessel"
    
    # Get available moves for this vessel
    try:
        from combat import moves
        # Temporarily set combat_active_idx to this vessel
        old_active = getattr(gs, "combat_active_idx", 0)
        gs.combat_active_idx = vessel_idx
        available_moves = moves.get_available_moves(gs)
        gs.combat_active_idx = old_active
    except Exception as e:
        print(f"⚠️ Failed to get moves for vessel: {e}")
        available_moves = []
    
    # Get PP for each move
    move_data = []
    for move in available_moves:
        try:
            from combat import moves
            old_active = getattr(gs, "combat_active_idx", 0)
            gs.combat_active_idx = vessel_idx
            current_pp, max_pp = moves.get_pp(gs, move.id)
            gs.combat_active_idx = old_active
            
            move_data.append({
                "move": move,
                "current_pp": current_pp,
                "max_pp": max_pp,  # This is the effective max_pp (base + bonuses)
                "can_apply": True,  # Always allow applying PP bonuses
            })
        except Exception as e:
            print(f"⚠️ Failed to get PP for move {move.id}: {e}")
            move_data.append({
                "move": move,
                "current_pp": 0,
                "max_pp": move.max_pp,
                "can_apply": True,  # Always allow applying PP (no max cap)
            })
    
    # Load vessel image (same logic as ledger.py)
    vessel_image = _full_vessel_from_token_name(vessel_name)
    
    _STATE = {
        "vessel_idx": vessel_idx,
        "vessel_name": display_name,
        "vessel_token": vessel_name,
        "pp_amount": pp_amount,
        "move_data": move_data,
        "selected_move": None,
        "hovered_move": None,
        "vessel_image": vessel_image,
        "phase": "in",  # "in" -> "open" -> "out"
        "t": 0.0,
        "last_ms": pygame.time.get_ticks(),
    }
    
    _ACTIVE = True
    return True

def close():
    """Close the move selector (start close animation)."""
    global _STATE
    if _STATE is None:
        return
    if _STATE.get("phase") != "out":
        _STATE["phase"] = "out"
        _STATE["t"] = 0.0
        _STATE["last_ms"] = pygame.time.get_ticks()

def handle_event(event, gs) -> bool:
    """Handle input events. Returns True if event was consumed."""
    global _STATE
    
    if not _ACTIVE or _STATE is None:
        return False
    
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            close()
            try:
                audio_sys.play_click(audio_sys.get_global_bank())
            except Exception:
                pass
            return True
    
    if event.type == pygame.MOUSEMOTION:
        mx, my = event.pos
        _STATE["hovered_move"] = _get_move_at_position(mx, my)
        return False
    
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        mx, my = event.pos
        clicked_move = _get_move_at_position(mx, my)
        if clicked_move is not None:
            move_data = _STATE["move_data"][clicked_move]
            if move_data.get("can_apply", False):
                # Set selected move before closing (so it can be retrieved)
                _STATE["selected_move"] = clicked_move
                try:
                    audio_sys.play_click(audio_sys.get_global_bank())
                except Exception:
                    pass
                # Don't close here - let the update loop handle it after applying
                # This ensures the selection is applied before the selector closes
                return True
        return False
    
    return False

def get_selected_move() -> Optional[tuple]:
    """Get the selected move index. Returns (vessel_idx, move_id) or None."""
    if not _ACTIVE or _STATE is None:
        return None
    
    selected = _STATE.get("selected_move")
    if selected is not None and selected < len(_STATE["move_data"]):
        move_data = _STATE["move_data"][selected]
        return (_STATE["vessel_idx"], move_data["move"].id)
    return None

def _get_move_at_position(mx: int, my: int) -> Optional[int]:
    """Get the move index at the given mouse position."""
    if _STATE is None:
        return None
    
    # Try to use stored button rects from draw (if available) - most reliable
    button_rects = _STATE.get("_button_rects")
    if button_rects:
        for move_idx, rect in button_rects.items():
            if rect.collidepoint(mx, my):
                return move_idx
    
    # Fallback: calculate button positions (same logic as draw)
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    base_bg = _get_popup_bg()
    
    if base_bg:
        bw, bh = base_bg.get_size()
        bx = (sw - bw) // 2
        by = (sh - bh) // 2
        book_rect = pygame.Rect(bx, by, bw, bh)
    else:
        pw, ph = int(sw * 0.55), int(sh * 0.55)
        px = (sw - pw) // 2
        py = (sh - ph) // 2
        book_rect = pygame.Rect(px, py, pw, ph)
    
    # Right page rect (matches draw)
    right_page = pygame.Rect(
        book_rect.x + int(book_rect.w * 0.54),
        book_rect.y + int(book_rect.h * 0.15),
        int(book_rect.w * 0.38),
        int(book_rect.h * 0.70),
    )
    right_page.x += 40
    right_page.y += 90
    
    cursor_x = right_page.x - 50
    
    # Calculate starting Y position (matches draw: title + inst + gaps)
    title_font = _get_font(max(26, int(book_rect.w * 0.015)))
    body_font = _get_font(max(18, int(book_rect.w * 0.008)))
    
    # Get title and instruction heights
    title_text = "Select Move"
    title_surf = title_font.render(title_text, True, (0, 0, 0))
    title_height = title_surf.get_height()
    
    inst_text = f"+{_STATE['pp_amount']} PP"
    inst_surf = body_font.render(inst_text, True, (0, 0, 0))
    inst_height = inst_surf.get_height()
    
    # Start position: title_y + title_height + gap + inst_height + gap
    cursor_y = right_page.y + 10 + title_height + 12 + inst_height + 24
    LINE_GAP = 12
    
    for i, move_info in enumerate(_STATE["move_data"]):
        move = move_info["move"]
        current_pp = move_info["current_pp"]
        max_pp = move_info["max_pp"]
        
        # Format move text (same format as draw function) - show only current max PP
        move_text = f"  {move.label}"
        move_text += f" ({max_pp} PP)"
        
        # Get text size to calculate button rect
        text_surf = body_font.render(move_text, True, (0, 0, 0))
        text_rect = text_surf.get_rect(topleft=(cursor_x, cursor_y))
        button_rect = text_rect.inflate(20, 8)
        
        if button_rect.collidepoint(mx, my):
            return i
        
        cursor_y += text_surf.get_height() + LINE_GAP
    
    return None

def _anim_update():
    """Update animation and return progress, phase."""
    global _STATE, _ACTIVE
    if _STATE is None:
        return 0.0, "closed"
    
    now = pygame.time.get_ticks()
    dt = max(0, (now - _STATE.get("last_ms", now)) / 1000.0)
    _STATE["last_ms"] = now
    
    phase = _STATE.get("phase", "open")
    t = _STATE.get("t", 0.0)
    
    if phase == "in":
        dur = max(0.001, _ANIM_IN_SECS)
        t = min(1.0, t + dt / dur)
        _STATE["t"] = t
        if t >= 1.0:
            _STATE["phase"] = "open"
            _STATE["t"] = 1.0
    elif phase == "out":
        dur = max(0.001, _ANIM_OUT_SECS)
        t = min(1.0, t + dt / dur)
        _STATE["t"] = t
        if t >= 1.0:
            _ACTIVE = False
            _STATE = None
            return 0.0, "closed"
    
    if _STATE is None:
        return 0.0, "closed"
    
    phase = _STATE["phase"]
    t = _STATE["t"]
    if phase == "in":
        return _ease_out_cubic(t), "in"
    if phase == "open":
        return 1.0, "open"
    if phase == "out":
        return 1.0 - _ease_out_cubic(t), "out"
    return 1.0, "open"

def draw(screen: pygame.Surface, dt: float = 0.016):
    """Draw the move selector using ledger background."""
    global _ACTIVE, _STATE
    
    if not _ACTIVE or _STATE is None:
        return
    
    prog, phase = _anim_update()
    if phase == "closed":
        return
    
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    
    # Dim overlay (matches ledger)
    overlay_alpha = int(_OVERLAY_MAX_A * prog)
    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, overlay_alpha))
    screen.blit(overlay, (0, 0))
    
    # Get ledger background
    base_bg = _get_popup_bg()
    
    # If no background, fall back to simple box
    if base_bg is None:
        pw, ph = int(sw * 0.55), int(sh * 0.55)
        px = (sw - pw) // 2
        py_target = (sh - ph) // 2
        slide_y = int((1.0 - prog) * _SLIDE_PIXELS)
        py = py_target + slide_y
        scale = _SCALE_MIN + (1.0 - _SCALE_MIN) * prog
        pw = int(pw * scale)
        ph = int(ph * scale)
        px = (sw - pw) // 2
        pygame.draw.rect(screen, (220, 200, 130), (px, py, pw, ph), border_radius=14)
        pygame.draw.rect(screen, (70, 45, 30), (px, py, pw, ph), 4, border_radius=14)
        book_rect = pygame.Rect(px, py, pw, ph)
    else:
        # Use ledger background with animation
        bw, bh = base_bg.get_size()
        bx = (sw - bw) // 2
        by_target = (sh - bh) // 2
        slide_y = int((1.0 - prog) * _SLIDE_PIXELS)
        scale = _SCALE_MIN + (1.0 - _SCALE_MIN) * prog
        
        if abs(scale - 1.0) < 0.0001:
            sbw, sbh = bw, bh
            sbx = bx
            sby = by_target + slide_y
            screen.blit(base_bg, (sbx, sby))
        else:
            sbw, sbh = max(1, int(bw * scale)), max(1, int(bh * scale))
            sb_base = pygame.transform.smoothscale(base_bg, (sbw, sbh))
            sbx = (sw - sbw) // 2
            sby = (sh - sbh) // 2 + slide_y
            screen.blit(sb_base, (sbx, sby))
        
        book_rect = pygame.Rect(sbx, sby, sbw, sbh)
    
    # Left and right page rects (like ledger)
    left_page = pygame.Rect(
        book_rect.x + int(book_rect.w * 0.08),
        book_rect.y + int(book_rect.h * 0.15),
        int(book_rect.w * 0.38),
        int(book_rect.h * 0.70),
    )
    right_page = pygame.Rect(
        book_rect.x + int(book_rect.w * 0.54),
        book_rect.y + int(book_rect.h * 0.15),
        int(book_rect.w * 0.38),
        int(book_rect.h * 0.70),
    )
    # Manual offsets (matches ledger positioning)
    left_page.x += 130
    left_page.y += -50
    right_page.x += 40
    right_page.y += 90
    
    # Draw vessel image on left page (like ledger)
    vessel_image = _STATE.get("vessel_image")
    if vessel_image:
        page_pad = 12
        art_rect = left_page.inflate(-page_pad * 2, -page_pad * 2)
        scaled, _ = _fit_center(vessel_image, art_rect)
        shrink = 0.65
        nw, nh = int(scaled.get_width() * shrink), int(scaled.get_height() * shrink)
        scaled = pygame.transform.smoothscale(scaled, (nw, nh))
        dest = scaled.get_rect(center=left_page.center)
        screen.blit(scaled, dest.topleft)
    
    # Content area (right page style, like ledger)
    content_rect = right_page
    
    # Colors (matches ledger)
    light = (36, 34, 30)
    dark = (0, 0, 0)
    CLR_MOVE = (70, 140, 220)  # blue for moves
    
    # Title (with shadow, like ledger)
    title_font = _get_font(max(26, int(book_rect.w * 0.015)))
    title_text = "Select Move"
    title_surf = title_font.render(title_text, True, light)
    title_shadow = title_font.render(title_text, True, dark)
    title_rect = title_surf.get_rect(topleft=(content_rect.x - 50, content_rect.y + 10))
    screen.blit(title_shadow, (title_rect.x + 1, title_rect.y + 1))
    screen.blit(title_surf, title_rect)
    
    # Instructions
    body_font = _get_font(max(18, int(book_rect.w * 0.008)))
    inst_text = f"+{_STATE['pp_amount']} PP"
    inst_surf = body_font.render(inst_text, True, light)
    inst_shadow = body_font.render(inst_text, True, dark)
    inst_rect = inst_surf.get_rect(topleft=(content_rect.x - 50, title_rect.bottom + 12))
    screen.blit(inst_shadow, (inst_rect.x + 1, inst_rect.y + 1))
    screen.blit(inst_surf, inst_rect)
    
    # Move buttons (styled like ledger text, clickable)
    cursor_x = content_rect.x - 50
    cursor_y = inst_rect.bottom + 24
    LINE_GAP = 12
    
    # Store button rects for click detection
    _button_rects = {}
    
    for i, move_info in enumerate(_STATE["move_data"]):
        move = move_info["move"]
        current_pp = move_info["current_pp"]
        max_pp = move_info["max_pp"]
        can_apply = move_info.get("can_apply", True)
        
        # Check hover/selection
        is_hovered = _STATE.get("hovered_move") == i
        is_selected = _STATE.get("selected_move") == i
        
        # Format move text - show only current max PP
        move_text = f"  {move.label}"
        move_text += f" ({max_pp} PP)"
        
        # Text color
        if not can_apply:
            text_color = (120, 120, 120)
        elif is_selected:
            text_color = CLR_MOVE
        elif is_hovered:
            text_color = CLR_MOVE
        else:
            text_color = CLR_MOVE
        
        # Draw text with shadow
        text_surf = body_font.render(move_text, True, text_color)
        text_shadow = body_font.render(move_text, True, dark)
        text_rect = text_surf.get_rect(topleft=(cursor_x, cursor_y))
        screen.blit(text_shadow, (text_rect.x + 1, text_rect.y + 1))
        screen.blit(text_surf, text_rect)
        
        # Store button rect for click detection
        _button_rects[i] = text_rect.inflate(20, 8)
        
        # Highlight if hovered
        if is_hovered and can_apply:
            highlight_rect = text_rect.inflate(8, 4)
            highlight_surf = pygame.Surface((highlight_rect.w, highlight_rect.h), pygame.SRCALPHA)
            highlight_surf.fill((*CLR_MOVE, 40))
            screen.blit(highlight_surf, highlight_rect.topleft)
        
        cursor_y += text_surf.get_height() + LINE_GAP
    
    # Store button rects in state for click detection
    _STATE["_button_rects"] = _button_rects
