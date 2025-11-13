# ============================================================
# systems/score_display.py — Score Display (Permanent HUD)
# - Always visible in top right corner
# - Shows score in a small HUD panel matching other HUDs
# - Number animation on score updates after battle victory
# ============================================================

import os
import pygame
import settings as S
from systems import points as points_sys
from systems import hud_style

# ---------- Constants ----------
ANIMATION_DURATION = 1.5  # Number roll-up animation duration in seconds (reduced from 4.5)

# ---------- HUD Configuration ----------
HUD_PADDING = 12  # Padding inside the HUD panel
HUD_MARGIN_RIGHT = 12  # Distance from right edge
HUD_MARGIN_TOP = 12  # Distance from top edge
HUD_MIN_WIDTH = 120  # Minimum width for the score HUD
HUD_HEIGHT = 50  # Height of the score HUD panel

# ---------- Font Cache ----------
_FONT_CACHE: dict[int, pygame.font.Font] = {}

# ---------- HUD State ----------
_HUD_RECT = None  # Store the HUD rect

def _get_dh_font(size: int) -> pygame.font.Font:
    """Get DH font with caching."""
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    
    try:
        font_path = os.path.join("Assets", "Fonts", "DH.otf")
        font = pygame.font.Font(font_path, size)
    except Exception:
        font = pygame.font.SysFont("georgia", size, bold=True)
    
    _FONT_CACHE[size] = font
    return font


def get_hud_rect() -> pygame.Rect | None:
    """Get the score HUD panel rect. Returns None if not calculated yet."""
    return _HUD_RECT


# ---------- Animation Control ----------

def start_score_animation(gs, start_score: int, target_score: int):
    """Start the score number animation after a summoner battle victory."""
    gs.score_animation_active = True
    gs.score_animation_timer = 0.0
    gs.score_animation_start = start_score
    gs.score_animation_target = target_score


def is_animation_active(gs) -> bool:
    """Check if the score animation is currently active."""
    return getattr(gs, "score_animation_active", False)


# ---------- Drawing ----------

def draw_score(screen: pygame.Surface, gs, dt: float = 0.016):
    """
    Draw the permanent score HUD in the top right corner.
    Always visible, with number animation on score updates.
    """
    global _HUD_RECT
    
    # Ensure points field exists
    points_sys.ensure_points_field(gs)
    
    # Get current score (either animated or static)
    current_score = points_sys.get_total_points(gs)
    
    # Check if animation is active and update displayed score
    is_animating = getattr(gs, "score_animation_active", False)
    if is_animating:
        # Update animation timer
        gs.score_animation_timer += dt
        
        # Check if animation should end
        if gs.score_animation_timer >= ANIMATION_DURATION:
            gs.score_animation_active = False
            gs.score_animation_timer = 0.0
            # Use final target score
            current_score = getattr(gs, "score_animation_target", current_score)
        else:
            # Calculate current displayed score (rolling up from start to target)
            progress = min(1.0, gs.score_animation_timer / ANIMATION_DURATION)
            # Use easing function for smooth roll-up (ease-out cubic)
            eased_progress = 1.0 - (1.0 - progress) ** 3
            start = getattr(gs, "score_animation_start", current_score)
            target = getattr(gs, "score_animation_target", current_score)
            current_score = int(start + (target - start) * eased_progress)
    
    # Render score text to determine HUD width
    font = _get_dh_font(24)
    score_text = f"Score: {current_score:,}"
    text_surface = font.render(score_text, True, (255, 255, 255))
    
    # Calculate HUD width based on text width + padding
    text_width = text_surface.get_width()
    hud_width = max(HUD_MIN_WIDTH, text_width + (HUD_PADDING * 2))
    
    # Calculate HUD position (top right)
    hud_x = S.LOGICAL_WIDTH - hud_width - HUD_MARGIN_RIGHT
    hud_y = HUD_MARGIN_TOP
    
    _HUD_RECT = pygame.Rect(hud_x, hud_y, hud_width, HUD_HEIGHT)
    
    # Draw parchment-style HUD background (matching other HUDs)
    hud_style.draw_parchment_panel(screen, _HUD_RECT)
    
    # Center text within the HUD
    text_x = hud_x + (hud_width - text_surface.get_width()) // 2
    text_y = hud_y + (HUD_HEIGHT - text_surface.get_height()) // 2
    
    # Draw text with shadow for readability
    shadow_surface = font.render(score_text, True, (0, 0, 0))
    screen.blit(shadow_surface, (text_x + 2, text_y + 2))
    screen.blit(text_surface, (text_x, text_y))
