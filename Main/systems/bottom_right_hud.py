# ============================================================
# systems/bottom_right_hud.py — Bottom Right HUD Panel
# - Displays information in a panel with parchment-style background
# - Simple, non-intrusive medieval design
# - Positioned near the HUD buttons in bottom right
# ============================================================

import os
import pygame
import settings as S
from systems import hud_buttons, hud_style

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
            for filename in os.listdir(folder):
                if "DH" in filename.upper() and filename.lower().endswith((".ttf", ".otf")):
                    _DH_FONT_PATH = os.path.join(folder, filename)
                    return _DH_FONT_PATH
    
    return None

def _get_dh_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Prefer DH font; fall back to a system font if missing."""
    try:
        path = _resolve_dh_font()
        if path:
            return pygame.font.Font(path, size)
    except Exception:
        pass
    
    # Fallback to system font
    try:
        return pygame.font.SysFont("arial", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)

# ---------- HUD Configuration ----------
# Size based on button grid (2 columns, ~2 rows)
HUD_PADDING = 12  # Reduced padding for less intrusive UI
HUD_MARGIN_RIGHT = 12  # Distance from right edge
HUD_MARGIN_BOTTOM = 12  # Distance from bottom edge

# Button grid configuration (should match hud_buttons.py)
# Match party UI slot size - slots are calculated from portrait height
from systems import party_ui
portrait_h = party_ui.PORTRAIT_SIZE[1]  # 140 (reduced)
slot_size, slot_gap, _ = party_ui._compute_slot_metrics(portrait_h)
BUTTON_SIZE = slot_size  # Match slot size (smaller now)
GRID_COLS = 4  # Number of columns in grid (horizontal layout) - expanded from 3 to fit 2 more buttons
GRID_GAP = slot_gap  # Match slot gap

# Calculate base HUD size based on button grid
base_hud_width = (GRID_COLS * BUTTON_SIZE) + ((GRID_COLS - 1) * GRID_GAP) + (HUD_PADDING * 2)
base_hud_height = (2 * BUTTON_SIZE) + (1 * GRID_GAP) + (HUD_PADDING * 2)

# Use base size directly (no scaling) - keep it minimal
HUD_WIDTH = base_hud_width
HUD_HEIGHT = base_hud_height

# ---------- Button Tooltip Descriptions ----------
_BUTTON_DESCRIPTIONS = {
    "bag": "Bag of Holding\n\nItem storage and inventory management. Access your collected scrolls, rations, and other consumables.",
    "party": "Party Manager\n\nView and manage your summoned vessels. Organize your party and inspect their moves and equipment.",
    "coinbag": "Merchant's Purse\n\nView your current gold reserves and currency holdings.",
    "rest": "Campfire\n\nTake a rest to restore health and recover from battle. Requires a safe location.",
    "book_of_bound": "Book of Bound\n\nA mystical tome that catalogs all vessels you have bound to your will. Contains detailed knowledge of their forms, natures, and the bonds that tie them to you.",
    "archives": "Archives\n\nA repository where your bound vessels are stored and preserved. Access your collection of vessels that have been bound to your service.",
    "hells_deck": "Hell's Deck\n\nReview the blessings and curses that have been drawn and chosen during your current journey. See what fate has already been dealt.",
}

# ---------- HUD State ----------
_ENABLED = True
_HUD_RECT = None  # Store the HUD rect for button positioning
_HOVERED_BUTTON_ID = None  # Track which button is currently hovered

def set_enabled(enabled: bool):
    """Enable or disable the HUD."""
    global _ENABLED
    _ENABLED = enabled

def is_enabled() -> bool:
    """Check if the HUD is enabled."""
    return _ENABLED

def get_hud_rect() -> pygame.Rect | None:
    """Get the HUD panel rect. Returns None if not calculated yet."""
    return _HUD_RECT

# ---------- Tooltip Drawing ----------

def _draw_tooltip(screen: pygame.Surface, button_id: str, mouse_x: int, mouse_y: int):
    """Draw a tooltip for the hovered button, similar to shop tooltip style."""
    tooltip_text = _BUTTON_DESCRIPTIONS.get(button_id, "")
    if not tooltip_text:
        return
    
    # Use DH font for tooltip
    tooltip_font = _get_dh_font(18)
    name_font = _get_dh_font(22)  # Title font (larger size)
    
    # Split text into title and description
    lines = tooltip_text.split("\n")
    title = lines[0] if lines else ""
    description = "\n".join(lines[1:]) if len(lines) > 1 else ""
    
    # Wrap description text
    words = description.split() if description else []
    wrapped_lines = []
    current_line = ""
    max_width = 320
    
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        if tooltip_font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                wrapped_lines.append(current_line)
            current_line = word
    if current_line:
        wrapped_lines.append(current_line)
    
    # Calculate tooltip size
    tooltip_padding = 12
    title_width = name_font.size(title)[0] if title else 0
    desc_width = max([tooltip_font.size(line)[0] for line in wrapped_lines]) if wrapped_lines else 0
    tooltip_w = max(250, max(title_width, desc_width) + tooltip_padding * 2)
    
    # Calculate height: title + spacing + description lines
    title_h = name_font.get_height() if title else 0
    line_h = tooltip_font.get_height() + 2  # 2px spacing between lines
    tooltip_h = tooltip_padding * 2
    if title:
        tooltip_h += title_h + 4  # 4px spacing after title
    if wrapped_lines:
        tooltip_h += len(wrapped_lines) * line_h
    
    # Position tooltip near mouse, but keep it on screen
    tooltip_x = mouse_x + 20
    tooltip_y = mouse_y - tooltip_h - 10
    
    # Make sure tooltip stays within logical screen bounds
    if tooltip_x + tooltip_w > S.LOGICAL_WIDTH:
        tooltip_x = mouse_x - tooltip_w - 20
    if tooltip_x < 0:
        tooltip_x = 10
    
    if tooltip_y < 0:
        tooltip_y = mouse_y + 30
    if tooltip_y + tooltip_h > S.LOGICAL_HEIGHT:
        tooltip_y = S.LOGICAL_HEIGHT - tooltip_h - 10
    
    tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_w, tooltip_h)
    
    # Draw tooltip background (matching shop tooltip style)
    tooltip_bg = pygame.Surface((tooltip_w, tooltip_h), pygame.SRCALPHA)
    tooltip_bg.fill((245, 245, 245))  # Light background like textbox
    pygame.draw.rect(tooltip_bg, (0, 0, 0), tooltip_bg.get_rect(), 4, border_radius=8)  # Outer black border
    inner_tooltip = tooltip_bg.get_rect().inflate(-8, -8)
    pygame.draw.rect(tooltip_bg, (60, 60, 60), inner_tooltip, 2, border_radius=6)  # Inner dark gray border
    
    # Draw text
    text_y = tooltip_padding
    if title:
        title_surface = name_font.render(title, True, (16, 16, 16))
        tooltip_bg.blit(title_surface, (tooltip_padding, text_y))
        text_y += title_h + 4
    
    if wrapped_lines:
        for line in wrapped_lines:
            line_surface = tooltip_font.render(line, True, (16, 16, 16))
            tooltip_bg.blit(line_surface, (tooltip_padding, text_y))
            text_y += line_h
    
    # Blit tooltip to screen
    screen.blit(tooltip_bg, tooltip_rect.topleft)

# ---------- Public API ----------

def draw(screen: pygame.Surface, gs):
    """
    Draw the bottom right HUD panel with buttons inside it.
    Uses hud1.png background image, scaled to fit.
    """
    global _HUD_RECT
    
    if not _ENABLED:
        return
    
    # Calculate HUD position (bottom right)
    hud_x = S.LOGICAL_WIDTH - HUD_WIDTH - HUD_MARGIN_RIGHT
    hud_y = S.LOGICAL_HEIGHT - HUD_HEIGHT - HUD_MARGIN_BOTTOM
    
    _HUD_RECT = pygame.Rect(hud_x, hud_y, HUD_WIDTH, HUD_HEIGHT)
    
    # Draw parchment-style HUD background
    hud_style.draw_parchment_panel(screen, _HUD_RECT)
    
    # Draw buttons inside the HUD panel
    # Position buttons to match party UI slot grid vertical position
    # Get party UI position to align buttons vertically with slots
    try:
        from systems import left_hud
        hud_rect = left_hud.get_hud_rect()
        if hud_rect:
            # Get portrait position (same as party_ui uses)
            px = hud_rect.x + HUD_PADDING
            py = hud_rect.y + (hud_rect.height - portrait_h) // 2
            
            # Calculate slot grid vertical position (same as party_ui)
            portrait_w = party_ui.PORTRAIT_SIZE[0]
            total_grid_h = 2 * slot_size + 1 * slot_gap  # 2 rows
            grid_top = py + (portrait_h - total_grid_h) // 2
            
            # Position buttons: right-aligned but vertically matching slots
            # Calculate button grid width
            button_grid_width = (GRID_COLS * BUTTON_SIZE) + ((GRID_COLS - 1) * GRID_GAP)
            button_area_x = S.LOGICAL_WIDTH - button_grid_width - HUD_MARGIN_RIGHT
            button_area_y = grid_top  # Match slot grid top position
        else:
            # Fallback: use original positioning
            original_hud_x = S.LOGICAL_WIDTH - base_hud_width - HUD_MARGIN_RIGHT
            button_area_x = original_hud_x + HUD_PADDING
            button_area_y = _HUD_RECT.y + HUD_PADDING
    except:
        # Fallback: use original positioning
        original_hud_x = S.LOGICAL_WIDTH - base_hud_width - HUD_MARGIN_RIGHT
        button_area_x = original_hud_x + HUD_PADDING
        button_area_y = _HUD_RECT.y + HUD_PADDING
    
    # Get button images and draw them inside the panel
    # Use the public API to load buttons
    hud_buttons.load_all_buttons()
    
    # Convert mouse coordinates to logical for hover detection
    screen_mx, screen_my = pygame.mouse.get_pos()
    try:
        from systems import coords
        mx, my = coords.screen_to_logical((screen_mx, screen_my))
    except:
        mx, my = screen_mx, screen_my
    
    # Track hovered button for tooltip
    global _HOVERED_BUTTON_ID
    _HOVERED_BUTTON_ID = None
    
    for idx, btn_def in enumerate(hud_buttons.get_buttons_list()):
        btn_id = btn_def["id"]
        scaled_img = hud_buttons.get_scaled_buttons().get(btn_id)
        
        if not scaled_img:
            continue
        
        # Calculate grid position (same as hud_buttons.py logic)
        col = idx % GRID_COLS
        row = idx // GRID_COLS
        
        # Position from top-left of button area
        btn_x = button_area_x + col * (BUTTON_SIZE + GRID_GAP)
        btn_y = button_area_y + row * (BUTTON_SIZE + GRID_GAP)
        
        # Center the scaled image in its grid cell
        img_w, img_h = scaled_img.get_width(), scaled_img.get_height()
        offset_x = (BUTTON_SIZE - img_w) // 2
        offset_y = (BUTTON_SIZE - img_h) // 2
        
        btn_rect = pygame.Rect(
            btn_x + offset_x,
            btn_y + offset_y,
            img_w,
            img_h
        )
        
        # Draw button image
        screen.blit(scaled_img, btn_rect.topleft)
        
        # Draw hover glow if mouse is over button
        if btn_rect.collidepoint(mx, my):
            glow = hud_buttons.get_hover_glow((btn_rect.w, btn_rect.h))
            screen.blit(glow, btn_rect.topleft)
            _HOVERED_BUTTON_ID = btn_id
        
        # Update the button rect cache so clicks still work
        hud_buttons.get_button_rects()[btn_id] = btn_rect
    
    # Draw tooltip if hovering over a button
    if _HOVERED_BUTTON_ID and _HOVERED_BUTTON_ID in _BUTTON_DESCRIPTIONS:
        _draw_tooltip(screen, _HOVERED_BUTTON_ID, mx, my)

