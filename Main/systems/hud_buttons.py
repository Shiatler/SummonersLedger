# ============================================================
# systems/hud_buttons.py — HUD Buttons (Grid System)
# - Clickable buttons in bottom right corner
# - Grid layout for easy expansion
# - Scaled down to small size
# ============================================================

import os
import pygame
import settings as S
from typing import Dict, Tuple

# ---------- Grid Configuration ----------
BUTTON_SCALE = 0.3  # Scale factor for buttons (30% of original size)
BUTTON_SIZE = 100  # Target size for buttons in grid (will scale images to this)
GRID_COLS = 4  # Number of columns in grid (horizontal layout) - expanded from 3 to fit 2 more buttons
GRID_GAP = 6  # Gap between buttons
BOTTOM_PADDING = 12  # Padding from bottom edge
RIGHT_PADDING = 12  # Padding from right edge
HOVER_GLOW_ALPHA = 48  # Alpha value for hover glow effect

# ---------- Button Definitions ----------
# Easy to add more buttons here in the future
_BUTTONS = [
    {"id": "bag", "path": "Bag.png", "action": "bag"},
    {"id": "party", "path": "Party.png", "action": "party"},
    {"id": "coinbag", "path": "CoinBag.png", "action": "currency"},
    {"id": "rest", "path": "Campfire.png", "action": "rest"},
    {"id": "book_of_bound", "path": "BookOfBound.png", "action": "book_of_bound"},
    {"id": "archives", "path": "Archives.png", "action": "archives"},
    {"id": "hells_deck", "path": "DeckOfCards.png", "action": "hells_deck"},
    # Placeholder for future button:
    # {"id": "placeholder", "path": "Placeholder.png", "action": "placeholder"},
]

# ---------- Cache ----------
_LOADED_BUTTONS: Dict[str, pygame.Surface] = {}
_SCALED_BUTTONS: Dict[str, pygame.Surface] = {}
_BUTTON_RECTS: Dict[str, pygame.Rect] = {}
_GLOW_CACHE: Dict[tuple[int, int, int], pygame.Surface] = {}  # (w, h, alpha) -> glow surface

# Expose button rects for other modules
def get_button_rect(button_id: str) -> pygame.Rect | None:
    """Get the rect for a button by ID."""
    _load_all_buttons()
    return _BUTTON_RECTS.get(button_id)


# ---------- Hover Glow Helper ----------

def _get_hover_glow(size: tuple[int, int], alpha: int = HOVER_GLOW_ALPHA) -> pygame.Surface:
    """Get a cached hover glow surface for the given size."""
    key = (size[0], size[1], alpha)
    if key in _GLOW_CACHE:
        return _GLOW_CACHE[key]
    
    glow = pygame.Surface(size, pygame.SRCALPHA)
    glow.fill((255, 255, 255, alpha))
    _GLOW_CACHE[key] = glow
    return glow


# ---------- Load & Scale Assets ----------

def _load_button_image(button_id: str, path: str) -> pygame.Surface | None:
    """Load a single button image."""
    if button_id in _LOADED_BUTTONS:
        return _LOADED_BUTTONS[button_id]
    
    # Special handling for hells_deck button - it's in Blessings folder
    if button_id == "hells_deck":
        full_path = os.path.join("Assets", "Blessings", path)
    else:
        full_path = os.path.join("Assets", "Map", path)
    
    if not os.path.exists(full_path):
        print(f"⚠️ {path} not found at {full_path}")
        return None
    
    try:
        img = pygame.image.load(full_path).convert_alpha()
        _LOADED_BUTTONS[button_id] = img
        return img
    except Exception as e:
        print(f"⚠️ Failed to load {path}: {e}")
        return None


def _scale_button(button_id: str, img: pygame.Surface) -> pygame.Surface:
    """Scale a button image to the target size."""
    if button_id in _SCALED_BUTTONS:
        return _SCALED_BUTTONS[button_id]
    
    # Scale to target size while maintaining aspect ratio
    orig_w, orig_h = img.get_width(), img.get_height()
    scale = BUTTON_SIZE / max(orig_w, orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    
    scaled = pygame.transform.smoothscale(img, (new_w, new_h))
    _SCALED_BUTTONS[button_id] = scaled
    return scaled


def _calculate_grid_positions():
    """Calculate button positions in a grid layout."""
    global _BUTTON_RECTS
    
    if _BUTTON_RECTS:
        return
    
    # Count valid buttons
    valid_buttons = [b for b in _BUTTONS if _load_button_image(b["id"], b["path"])]
    if not valid_buttons:
        return
    
    # Calculate grid dimensions
    total_buttons = len(valid_buttons)
    rows = (total_buttons + GRID_COLS - 1) // GRID_COLS  # Ceiling division
    
    # Start from bottom right (use logical resolution)
    start_x = S.LOGICAL_WIDTH - RIGHT_PADDING
    start_y = S.LOGICAL_HEIGHT - BOTTOM_PADDING
    
    # Position buttons in grid (right to left, bottom to top)
    for idx, btn_def in enumerate(valid_buttons):
        btn_id = btn_def["id"]
        scaled_img = _SCALED_BUTTONS.get(btn_id)
        if scaled_img is None:
            img = _load_button_image(btn_id, btn_def["path"])
            if img:
                scaled_img = _scale_button(btn_id, img)
            else:
                continue
        
        # Calculate grid position
        col = idx % GRID_COLS
        row = idx // GRID_COLS
        
        # Position from right edge
        x = start_x - (GRID_COLS - col) * (BUTTON_SIZE + GRID_GAP)
        y = start_y - (rows - row) * (BUTTON_SIZE + GRID_GAP)
        
        # Center the scaled image in its grid cell
        img_w, img_h = scaled_img.get_width(), scaled_img.get_height()
        offset_x = (BUTTON_SIZE - img_w) // 2
        offset_y = (BUTTON_SIZE - img_h) // 2
        
        _BUTTON_RECTS[btn_id] = pygame.Rect(
            x + offset_x, 
            y + offset_y, 
            img_w, 
            img_h
        )


def _load_all_buttons():
    """Load and scale all button images."""
    for btn_def in _BUTTONS:
        btn_id = btn_def["id"]
        img = _load_button_image(btn_id, btn_def["path"])
        if img:
            _scale_button(btn_id, img)
    
    _calculate_grid_positions()

def load_all_buttons():
    """Public API to load all buttons."""
    _load_all_buttons()

# Expose for bottom_right_hud
def get_buttons_list():
    """Get the list of button definitions."""
    return _BUTTONS

def get_scaled_buttons():
    """Get the dict of scaled button images."""
    return _SCALED_BUTTONS

def get_button_rects():
    """Get the dict of button rects."""
    return _BUTTON_RECTS

def get_hover_glow(size: tuple[int, int], alpha: int = HOVER_GLOW_ALPHA):
    """Get a hover glow surface for the given size."""
    return _get_hover_glow(size, alpha)


# ---------- Public API ----------

def handle_click(pos: tuple[int, int]) -> str | None:
    """
    Handle a mouse click on the buttons.
    Returns the button action ID if clicked, None otherwise.
    """
    _load_all_buttons()
    
    for btn_def in _BUTTONS:
        btn_id = btn_def["id"]
        rect = _BUTTON_RECTS.get(btn_id)
        if rect and rect.collidepoint(pos):
            return btn_def["action"]
    
    return None


def is_hovering_any_button(pos: tuple[int, int]) -> bool:
    """
    Check if the mouse position is hovering over any HUD button.
    Returns True if hovering over any button, False otherwise.
    
    Args:
        pos: Mouse position tuple (x, y) in logical coordinates
    """
    _load_all_buttons()
    
    for btn_def in _BUTTONS:
        btn_id = btn_def["id"]
        rect = _BUTTON_RECTS.get(btn_id)
        if rect and rect.collidepoint(pos):
            return True
    
    return False


def draw(screen: pygame.Surface):
    """Draw all HUD buttons in a grid layout with hover glow effects."""
    _load_all_buttons()
    
    # Get mouse position for hover detection - convert to logical coordinates
    screen_mx, screen_my = pygame.mouse.get_pos()
    try:
        from systems import coords
        mx, my = coords.screen_to_logical((screen_mx, screen_my))
    except:
        mx, my = screen_mx, screen_my
    
    for btn_def in _BUTTONS:
        btn_id = btn_def["id"]
        scaled_img = _SCALED_BUTTONS.get(btn_id)
        rect = _BUTTON_RECTS.get(btn_id)
        
        if scaled_img and rect:
            # Draw button image
            screen.blit(scaled_img, rect.topleft)
            
            # Draw hover glow if mouse is over button
            if rect.collidepoint(mx, my):
                glow = _get_hover_glow((rect.w, rect.h))
                screen.blit(glow, rect.topleft)

