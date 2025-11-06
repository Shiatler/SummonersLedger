# ============================================================
# systems/coords.py — Coordinate conversion utilities
# Converts between physical screen coordinates and logical coordinates
# ============================================================

import pygame
import settings as S


# Global scale factors (updated when screen size changes)
_scale_x = 1.0
_scale_y = 1.0
_offset_x = 0.0
_offset_y = 0.0


def update_scale_factors(screen_width: int, screen_height: int, force_scale: float = None):
    """
    Update scale factors based on current screen size.
    This should be called whenever the screen size changes.
    
    Args:
        screen_width: Physical screen width (MUST be actual physical screen size, not logical)
        screen_height: Physical screen height (MUST be actual physical screen size, not logical)
        force_scale: If provided, use this scale instead of calculating (for fullscreen)
    """
    global _scale_x, _scale_y, _offset_x, _offset_y
    
    if force_scale is not None:
        # Use forced scale (for fullscreen mode)
        scale = force_scale
    else:
        # Calculate scale to fit logical resolution in screen (maintain aspect ratio)
        scale_x = screen_width / S.LOGICAL_WIDTH
        scale_y = screen_height / S.LOGICAL_HEIGHT
        
        # Use the smaller scale to maintain aspect ratio (letterboxing/pillarboxing)
        scale = min(scale_x, scale_y)
    
    _scale_x = scale
    _scale_y = scale
    
    # Calculate offsets for centering (letterboxing/pillarboxing)
    # CRITICAL: screen_width and screen_height MUST be the actual physical screen size
    # The scaled size is the logical resolution * scale
    scaled_width = S.LOGICAL_WIDTH * scale
    scaled_height = S.LOGICAL_HEIGHT * scale
    
    # Offset should center the scaled content on the physical screen
    # If screen is larger than scaled, offset is positive (centering)
    # If screen is smaller than scaled, offset is negative (content extends beyond screen)
    _offset_x = (screen_width - scaled_width) / 2
    _offset_y = (screen_height - scaled_height) / 2
    
    # Debug: Log if offsets are negative (indicates wrong screen size)
    if _offset_x < 0 or _offset_y < 0:
        print(f"⚠️ Negative offset detected! screen={screen_width}x{screen_height}, scaled={int(scaled_width)}x{int(scaled_height)}, offset=({_offset_x:.1f}, {_offset_y:.1f})")
        print(f"   This suggests screen_width/height are wrong - they should be physical screen size, not logical size")


def screen_to_logical(screen_pos: tuple[int, int]) -> tuple[int, int]:
    """
    Convert physical screen coordinates to logical coordinates.
    Use this for all mouse input handling.
    
    Args:
        screen_pos: (x, y) tuple in screen coordinates
        
    Returns:
        (x, y) tuple in logical coordinates
    """
    if _scale_x == 0 or _scale_y == 0:
        return screen_pos
    
    screen_x, screen_y = screen_pos
    
    # Convert to logical coordinates
    logical_x = (screen_x - _offset_x) / _scale_x
    logical_y = (screen_y - _offset_y) / _scale_y
    
    return (int(logical_x), int(logical_y))


def logical_to_screen(logical_pos: tuple[int, int]) -> tuple[int, int]:
    """
    Convert logical coordinates to physical screen coordinates.
    Usually not needed, but available if needed.
    
    Args:
        logical_pos: (x, y) tuple in logical coordinates
        
    Returns:
        (x, y) tuple in screen coordinates
    """
    logical_x, logical_y = logical_pos
    
    screen_x = logical_x * _scale_x + _offset_x
    screen_y = logical_y * _scale_y + _offset_y
    
    return (int(screen_x), int(screen_y))


def get_scale() -> float:
    """Get the current scale factor."""
    return _scale_x


def get_offset() -> tuple[float, float]:
    """Get the current offset (for centering)."""
    return (_offset_x, _offset_y)

