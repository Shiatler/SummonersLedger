# ============================================================
# systems/left_hud.py — Left Side HUD Panel
# - Displays behind character token and party UI
# - Matches the textbox style (cream/beige, rounded corners)
# ============================================================

import pygame
import settings as S
from systems import party_ui, bottom_right_hud

# ---------- Font helpers ----------
# (We don't need fonts for this HUD, but keeping structure consistent)

# ---------- HUD Configuration ----------
HUD_PADDING = 12  # Padding inside the HUD panel
HUD_MARGIN_LEFT = 12  # Distance from left edge
HUD_MARGIN_BOTTOM = 12  # Distance from bottom edge

# Get dimensions from party_ui
PORTRAIT_SIZE = party_ui.PORTRAIT_SIZE  # (180, 180)
PADDING = party_ui.PADDING  # 16

# Calculate HUD size based on portrait and slots
# Portrait is 180x180
# Slots are 2 rows x 3 columns, positioned to the right of portrait
# Slot size is calculated dynamically based on portrait height
# We need space for: portrait width + gap + slots grid width
portrait_w, portrait_h = PORTRAIT_SIZE
slot_size, slot_gap, inner_margin = party_ui._compute_slot_metrics(portrait_h)
slots_grid_width = (3 * slot_size) + (2 * slot_gap)  # 3 columns
gap_between_portrait_and_slots = 16  # From party_ui.py line 232

HUD_WIDTH = portrait_w + gap_between_portrait_and_slots + slots_grid_width + (HUD_PADDING * 2)
# Match the height of the bottom-right HUD
HUD_HEIGHT = bottom_right_hud.HUD_HEIGHT

# ---------- HUD State ----------
_ENABLED = True
_HUD_RECT = None  # Store the HUD rect

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
    Draw the left side HUD panel behind character token and party UI.
    Matches the textbox style: cream/beige background, black border, inner grey border.
    """
    global _HUD_RECT
    
    if not _ENABLED:
        return
    
    # Calculate HUD position (bottom-left)
    # Match the vertical position of the bottom-right HUD
    # Bottom-right HUD: hud_y = S.LOGICAL_HEIGHT - HUD_HEIGHT - HUD_MARGIN_BOTTOM
    hud_y = S.LOGICAL_HEIGHT - HUD_HEIGHT - HUD_MARGIN_BOTTOM
    
    # Portrait is positioned at: PADDING (16), S.LOGICAL_HEIGHT - portrait_h - PADDING
    # The HUD should start at the same left position as the portrait, but account for padding
    # Portrait x = PADDING, so HUD x should be PADDING - HUD_PADDING to center the portrait inside
    hud_x = PADDING - HUD_PADDING
    
    _HUD_RECT = pygame.Rect(hud_x, hud_y, HUD_WIDTH, HUD_HEIGHT)
    
    # Draw textbox-styled panel (matches rest.py and master_oak.py textboxes)
    # Outer box (cream/beige background)
    pygame.draw.rect(screen, (245, 245, 245), _HUD_RECT, border_radius=8)
    # Outer border (black)
    pygame.draw.rect(screen, (0, 0, 0), _HUD_RECT, 4, border_radius=8)
    # Inner border (dark grey)
    inner_rect = _HUD_RECT.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner_rect, 2, border_radius=6)

