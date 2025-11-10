# ============================================================
# systems/left_hud.py — Left Side HUD Panel
# - Displays behind character token and party UI
# - Parchment-inspired medieval background (code-drawn)
# ============================================================

import pygame
import settings as S
from systems import party_ui, bottom_right_hud, hud_style

# ---------- HUD Configuration ----------
HUD_PADDING = 12  # Reduced padding for less intrusive UI
HUD_MARGIN_LEFT = 12  # Distance from left edge
HUD_MARGIN_BOTTOM = 12  # Distance from bottom edge

# Get dimensions from party_ui
PORTRAIT_SIZE = party_ui.PORTRAIT_SIZE  # (140, 140) - reduced size
PADDING = party_ui.PADDING  # 16

# Calculate HUD size based on portrait and slots
# Portrait is 140x140 (reduced)
# Slots are 2 rows x 3 columns, positioned to the right of portrait
# Slot size is calculated dynamically based on portrait height
# We need space for: portrait width + gap + slots grid width
portrait_w, portrait_h = PORTRAIT_SIZE
slot_size, slot_gap, inner_margin = party_ui._compute_slot_metrics(portrait_h)
slots_grid_width = (3 * slot_size) + (2 * slot_gap)  # 3 columns
gap_between_portrait_and_slots = 12  # Reduced gap

# Calculate base HUD size based on content
base_hud_width = portrait_w + gap_between_portrait_and_slots + slots_grid_width + (HUD_PADDING * 2)
# Use the same base height calculation as the right HUD for perfect alignment
# This ensures both HUDs have the same height and align properly
base_hud_height = bottom_right_hud.base_hud_height

# Use base size directly (no scaling) - keep it minimal
HUD_WIDTH = base_hud_width
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
    Uses hud1.png background image, scaled to fit.
    """
    global _HUD_RECT
    
    if not _ENABLED:
        return
    
    # Calculate HUD position (bottom-left)
    # Match the vertical position of the bottom-right HUD
    hud_y = S.LOGICAL_HEIGHT - HUD_HEIGHT - HUD_MARGIN_BOTTOM
    
    # Position HUD with a small left margin
    # Portrait will be positioned at hud_x + HUD_PADDING
    hud_x = HUD_MARGIN_LEFT
    
    _HUD_RECT = pygame.Rect(hud_x, hud_y, HUD_WIDTH, HUD_HEIGHT)
    
    # Draw parchment-style HUD background
    hud_style.draw_parchment_panel(screen, _HUD_RECT)

