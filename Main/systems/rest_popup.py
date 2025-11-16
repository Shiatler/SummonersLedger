# ============================================================
# systems/rest_popup.py — Rest Selection Popup
# - Small popup that appears over the rest button
# - Allows choosing between Long Rest and Short Rest
# ============================================================

import os
import pygame
import settings as S
from systems import audio as audio_sys
from systems import hud_buttons
from systems import coords

# ---------- Font helpers ----------
_DH_FONT_PATH = None

def _resolve_dh_font() -> str | None:
    """Find a font file in Assets/Fonts whose filename contains 'DH'."""
    global _DH_FONT_PATH
    if _DH_FONT_PATH is not None:
        return _DH_FONT_PATH
    
    candidates = [
        os.path.join("Assets", "Fonts"),
        r"C:\Users\Frederik\Desktop\SummonersLedger\Assets\Fonts",
    ]
    for folder in candidates:
        if os.path.isdir(folder):
            for fname in os.listdir(folder):
                low = fname.lower()
                if "dh" in low and low.endswith((".ttf", ".otf", ".ttc")):
                    _DH_FONT_PATH = os.path.join(folder, fname)
                    return _DH_FONT_PATH
    _DH_FONT_PATH = None
    return None

def _get_dh_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Prefer DH font; fall back to a system font if missing."""
    try:
        path = _resolve_dh_font()
        if path:
            return pygame.font.Font(path, size)
    except Exception as e:
        print(f"⚠️ Failed to load DH font: {e}")
    try:
        return pygame.font.SysFont("arial", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)

# ---------- Popup state ----------
_OPEN = False
_POPUP_RECT = None
_LONG_BTN_RECT = None
_SHORT_BTN_RECT = None

def is_open() -> bool:
    """Check if the rest popup is open."""
    return _OPEN

def open_popup():
    """Open the rest selection popup."""
    global _OPEN, _POPUP_RECT, _LONG_BTN_RECT, _SHORT_BTN_RECT
    _OPEN = True
    
    # Bigger popup size
    popup_w = 420
    popup_h = 200
    gap_from_hud = 12  # Gap between popup and HUD panel
    
    # Try to get the HUD panel position
    from systems import bottom_right_hud
    hud_rect = bottom_right_hud.get_hud_rect()
    
    if hud_rect:
        # Position popup above the HUD panel, right-aligned with it
        popup_x = hud_rect.right - popup_w  # Align right edge with HUD right edge
        popup_y = hud_rect.y - popup_h - gap_from_hud  # Position above HUD with gap
        
        # Make sure it doesn't go off screen
        margin = 12
        if popup_y < margin:
            popup_y = margin
        if popup_x < margin:
            popup_x = margin
        
        _POPUP_RECT = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
        
        # Button dimensions (bigger to match larger popup)
        btn_w = 360
        btn_h = 50
        btn_x = popup_x + (popup_w - btn_w) // 2
        
        # Long rest button
        _LONG_BTN_RECT = pygame.Rect(btn_x, popup_y + 50, btn_w, btn_h)
        
        # Short rest button
        _SHORT_BTN_RECT = pygame.Rect(btn_x, popup_y + 110, btn_w, btn_h)
    else:
        # Fallback: position above where HUD would be (bottom right)
        margin = 12
        popup_x = S.LOGICAL_WIDTH - popup_w - margin
        popup_y = S.LOGICAL_HEIGHT - bottom_right_hud.HUD_HEIGHT - popup_h - gap_from_hud - margin
        
        # Make sure it doesn't go off screen
        if popup_y < margin:
            popup_y = margin
        
        _POPUP_RECT = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
        
        # Button dimensions (bigger to match larger popup)
        btn_w = 360
        btn_h = 50
        btn_x = popup_x + (popup_w - btn_w) // 2
        
        # Long rest button
        _LONG_BTN_RECT = pygame.Rect(btn_x, popup_y + 50, btn_w, btn_h)
        
        # Short rest button
        _SHORT_BTN_RECT = pygame.Rect(btn_x, popup_y + 110, btn_w, btn_h)

def close_popup():
    """Close the rest selection popup."""
    global _OPEN
    _OPEN = False

def handle_event(e, gs) -> str | None:
    """
    Handle events for the rest popup.
    Returns "long" or "short" if a rest type was selected, None otherwise.
    """
    global _OPEN
    
    if not _OPEN:
        return None
    
    # Check for clicks outside popup to close
    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
        mx, my = e.pos
        
        # Check if clicking on buttons
        if _LONG_BTN_RECT and _LONG_BTN_RECT.collidepoint(mx, my):
            if _has_item(gs, "rations"):
                _consume_item(gs, "rations")
                close_popup()
                audio_sys.play_click(audio_sys.get_global_bank())
                return "long"
            else:
                audio_sys.play_click(audio_sys.get_global_bank())
                return None
        
        elif _SHORT_BTN_RECT and _SHORT_BTN_RECT.collidepoint(mx, my):
            if _has_item(gs, "alcohol"):
                _consume_item(gs, "alcohol")
                close_popup()
                audio_sys.play_click(audio_sys.get_global_bank())
                return "short"
            else:
                audio_sys.play_click(audio_sys.get_global_bank())
                return None
        
        # Click outside popup - close it
        elif _POPUP_RECT and not _POPUP_RECT.collidepoint(mx, my):
            close_popup()
            audio_sys.play_click(audio_sys.get_global_bank())
            return None
    
    # ESC to close
    elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
        close_popup()
        audio_sys.play_click(audio_sys.get_global_bank())
        return None
    
    return None  # Event handled but no selection made

def draw(screen: pygame.Surface, gs):
    """Draw the rest selection popup as a speech bubble."""
    if not _OPEN or not _POPUP_RECT:
        return
    
    # Get mouse position for hover - Convert to logical coordinates for QHD support
    screen_mx, screen_my = pygame.mouse.get_pos()
    mx, my = coords.screen_to_logical((screen_mx, screen_my))
    
    # Draw speech bubble background (rounded rectangle)
    bubble_rect = _POPUP_RECT.copy()
    bubble_radius = 16
    
    # Create bubble surface with transparency
    bubble = pygame.Surface((bubble_rect.w, bubble_rect.h), pygame.SRCALPHA)
    
    # Draw main bubble body (cream/beige color like medieval textbox)
    pygame.draw.rect(bubble, (245, 245, 235), bubble.get_rect(), border_radius=bubble_radius)
    pygame.draw.rect(bubble, (0, 0, 0), bubble.get_rect(), 3, border_radius=bubble_radius)
    
    # Draw inner border
    inner_rect = bubble.get_rect().inflate(-6, -6)
    pygame.draw.rect(bubble, (60, 60, 60), inner_rect, 2, border_radius=bubble_radius-3)
    
    # Draw speech bubble tail pointing toward HUD (bottom-center, pointing down)
    tail_size = 20
    tail_center_x = bubble_rect.centerx
    tail_points = [
        (tail_center_x - 15, bubble_rect.bottom),  # Start of tail (left)
        (tail_center_x, bubble_rect.bottom + tail_size),  # Point (extends down)
        (tail_center_x + 15, bubble_rect.bottom),  # End of tail (right)
    ]
    
    # Draw tail on main surface (not on bubble surface since it extends beyond)
    pygame.draw.polygon(screen, (245, 245, 235), tail_points)
    pygame.draw.polygon(screen, (0, 0, 0), tail_points, 3)
    
    # Blit bubble to screen
    screen.blit(bubble, bubble_rect.topleft)
    
    # Draw title
    title_font = _get_dh_font(28)
    title = title_font.render("Select Rest Type", True, (16, 16, 16))
    title_x = _POPUP_RECT.x + (_POPUP_RECT.w - title.get_width()) // 2
    screen.blit(title, (title_x, _POPUP_RECT.y + 15))
    
    # Draw buttons
    btn_font = _get_dh_font(22)
    
    # Long rest button
    if _LONG_BTN_RECT:
        has_rations = _has_item(gs, "rations")
        hover_long = has_rations and _LONG_BTN_RECT.collidepoint(mx, my)
        if has_rations:
            color = (100, 150, 100) if hover_long else (80, 120, 80)
            text_color = (255, 255, 255)
        else:
            color = (70, 70, 70)
            text_color = (160, 160, 160)
        pygame.draw.rect(screen, color, _LONG_BTN_RECT, border_radius=8)
        pygame.draw.rect(screen, (255, 255, 255), _LONG_BTN_RECT, 2, border_radius=8)
        long_text = btn_font.render("Long Rest (Rations)", True, text_color)
        long_text_x = _LONG_BTN_RECT.centerx - long_text.get_width() // 2
        long_text_y = _LONG_BTN_RECT.centery - long_text.get_height() // 2
        screen.blit(long_text, (long_text_x, long_text_y))
    
    # Short rest button
    if _SHORT_BTN_RECT:
        has_alcohol = _has_item(gs, "alcohol")
        hover_short = has_alcohol and _SHORT_BTN_RECT.collidepoint(mx, my)
        if has_alcohol:
            color = (100, 150, 100) if hover_short else (80, 120, 80)
            text_color = (255, 255, 255)
        else:
            color = (70, 70, 70)
            text_color = (160, 160, 160)
        pygame.draw.rect(screen, color, _SHORT_BTN_RECT, border_radius=8)
        pygame.draw.rect(screen, (255, 255, 255), _SHORT_BTN_RECT, 2, border_radius=8)
        short_text = btn_font.render("Short Rest (Alcohol)", True, text_color)
        short_text_x = _SHORT_BTN_RECT.centerx - short_text.get_width() // 2
        short_text_y = _SHORT_BTN_RECT.centery - short_text.get_height() // 2
        screen.blit(short_text, (short_text_x, short_text_y))


# ---------- Inventory helpers ----------
def _has_item(gs, item_id: str) -> bool:
    """Check if player has at least one of the specified item."""
    inv = getattr(gs, "inventory", None)
    if not inv:
        return False
    
    if isinstance(inv, dict):
        return int(inv.get(item_id, 0)) > 0
    
    if isinstance(inv, (list, tuple)):
        for rec in inv:
            if isinstance(rec, dict):
                rid = rec.get("id") or _snake_from_name(rec.get("name", ""))
                if rid == item_id and int(rec.get("qty", 0)) > 0:
                    return True
            elif isinstance(rec, (list, tuple)) and rec:
                rid = str(rec[0])
                qty = int(rec[1]) if len(rec) > 1 else 0
                if rid == item_id and qty > 0:
                    return True
    return False


def _consume_item(gs, item_id: str) -> bool:
    """Consume one of the specified item from inventory. Returns True if consumed."""
    inv = getattr(gs, "inventory", None)
    if not inv:
        return False
    
    if isinstance(inv, dict):
        if item_id in inv and int(inv[item_id]) > 0:
            inv[item_id] = max(0, int(inv[item_id]) - 1)
            if inv[item_id] <= 0:
                try:
                    del inv[item_id]
                except Exception:
                    pass
            gs.inventory = inv
            return True
        return False
    
    if isinstance(inv, (list, tuple)):
        new_list = []
        consumed = False
        for rec in inv:
            if isinstance(rec, dict):
                rid = rec.get("id") or _snake_from_name(rec.get("name", ""))
                if rid == item_id and not consumed:
                    qty = max(0, int(rec.get("qty", 0)) - 1)
                    consumed = True
                    if qty > 0:
                        rec["qty"] = qty
                        new_list.append(rec)
                else:
                    new_list.append(rec)
            elif isinstance(rec, (list, tuple)) and rec:
                rid = str(rec[0])
                if rid == item_id and not consumed:
                    qty = int(rec[1]) if len(rec) > 1 else 0
                    qty = max(0, qty - 1)
                    consumed = True
                    if qty > 0:
                        new_list.append([rid, qty])
                else:
                    new_list.append(rec)
            else:
                new_list.append(rec)
        if consumed:
            gs.inventory = new_list
        return consumed
    return False


def _snake_from_name(name: str) -> str:
    return str(name or "").lower().replace(" ", "_")


