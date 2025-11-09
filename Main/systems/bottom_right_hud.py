# ============================================================
# systems/bottom_right_hud.py — Bottom Right HUD Panel
# - Displays information in a textbox-styled panel
# - Positioned near the HUD buttons in bottom right
# - Matches the textbox aesthetic (cream/beige, rounded corners)
# ============================================================

import os
import pygame
import settings as S
from systems import hud_buttons

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
HUD_PADDING = 12  # Padding inside the HUD panel
HUD_MARGIN_RIGHT = 12  # Distance from right edge
HUD_MARGIN_BOTTOM = 12  # Distance from bottom edge

# Button grid configuration (should match hud_buttons.py)
BUTTON_SIZE = 100  # Target size for buttons in grid
GRID_COLS = 4  # Number of columns in grid (horizontal layout) - expanded from 3 to fit 2 more buttons
GRID_GAP = 6  # Gap between buttons

# Calculate HUD size based on button grid
# We need space for 4 columns of buttons plus padding
HUD_WIDTH = (GRID_COLS * BUTTON_SIZE) + ((GRID_COLS - 1) * GRID_GAP) + (HUD_PADDING * 2)
# Height: enough for 2 rows of buttons (8 buttons total, 2 rows)
HUD_HEIGHT = (2 * BUTTON_SIZE) + (1 * GRID_GAP) + (HUD_PADDING * 2)

# ---------- HUD State ----------
_ENABLED = True
_HUD_RECT = None  # Store the HUD rect for button positioning

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

# ---------- Public API ----------

def draw(screen: pygame.Surface, gs):
    """
    Draw the bottom right HUD panel with buttons inside it.
    Matches the textbox style: cream/beige background, black border, inner grey border.
    """
    global _HUD_RECT
    
    if not _ENABLED:
        return
    
    # Calculate HUD position (bottom right)
    hud_x = S.LOGICAL_WIDTH - HUD_WIDTH - HUD_MARGIN_RIGHT
    hud_y = S.LOGICAL_HEIGHT - HUD_HEIGHT - HUD_MARGIN_BOTTOM
    
    _HUD_RECT = pygame.Rect(hud_x, hud_y, HUD_WIDTH, HUD_HEIGHT)
    
    # Draw textbox-styled panel (matches rest.py and master_oak.py textboxes)
    # Outer box (cream/beige background)
    pygame.draw.rect(screen, (245, 245, 245), _HUD_RECT, border_radius=8)
    # Outer border (black)
    pygame.draw.rect(screen, (0, 0, 0), _HUD_RECT, 4, border_radius=8)
    # Inner border (dark grey)
    inner_rect = _HUD_RECT.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner_rect, 2, border_radius=6)
    
    # Draw buttons inside the HUD panel
    # Calculate button positions relative to HUD panel
    button_area_x = _HUD_RECT.x + HUD_PADDING
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
        
        # Update the button rect cache so clicks still work
        hud_buttons.get_button_rects()[btn_id] = btn_rect

