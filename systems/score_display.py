# ============================================================
# systems/score_display.py — Score Display (Top Right Corner)
# - Displays player's total points in the top right
# - Uses DH font and animated Score frames (Score1.png - Score5.png)
# - 60fps animation
# ============================================================

import os
import pygame
import settings as S
from systems import points as points_sys

# ---------- Cache ----------
_SCORE_FRAMES: list[pygame.Surface] | None = None
_SCALED_FRAMES: list[pygame.Surface] | None = None
_FONT_CACHE: dict[int, pygame.font.Font] = {}
_ANIM_TIMER: float = 0.0
_ANIM_FPS: float = 8.0  # Much slower animation (8 fps)

# ---------- Load Assets ----------

def _load_score_frames() -> list[pygame.Surface] | None:
    """Load and cache all Score animation frames (Score1.png - Score5.png)."""
    global _SCORE_FRAMES
    if _SCORE_FRAMES is not None:
        return _SCORE_FRAMES
    
    frames = []
    base_path = os.path.join("Assets", "Animations")
    
    for i in range(1, 6):  # Score1.png through Score5.png
        path = os.path.join(base_path, f"Score{i}.png")
        if not os.path.exists(path):
            print(f"⚠️ Score{i}.png not found at {path}")
            continue
        
        try:
            frame = pygame.image.load(path).convert_alpha()
            frames.append(frame)
        except Exception as e:
            print(f"⚠️ Failed to load Score{i}.png: {e}")
    
    if not frames:
        print("⚠️ No Score frames found!")
        return None
    
    _SCORE_FRAMES = frames
    return frames


def _get_scaled_frames(scale_factor: float) -> list[pygame.Surface] | None:
    """Get scaled versions of the frames, cached."""
    global _SCALED_FRAMES
    if _SCALED_FRAMES is not None:
        return _SCALED_FRAMES
    
    frames = _load_score_frames()
    if frames is None:
        return None
    
    scaled = []
    for frame in frames:
        w = int(frame.get_width() * scale_factor)
        h = int(frame.get_height() * scale_factor)
        scaled_frame = pygame.transform.smoothscale(frame, (w, h))
        scaled.append(scaled_frame)
    
    _SCALED_FRAMES = scaled
    return scaled


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


# ---------- Drawing ----------

def draw_score(screen: pygame.Surface, gs, dt: float = 0.016):
    """
    Draw the animated score display in the top right corner.
    The score text will be drawn inside the text area of the animated frames.
    """
    global _ANIM_TIMER, _SCALED_FRAMES
    
    # Ensure points field exists
    points_sys.ensure_points_field(gs)
    total_points = points_sys.get_total_points(gs)
    
    # Scale factor (smaller)
    scale_factor = 0.25
    
    # Load and get scaled frames
    scaled_frames = _get_scaled_frames(scale_factor)
    if scaled_frames is None or len(scaled_frames) == 0:
        # Fallback: draw a simple rectangle if frames not found
        fallback_rect = pygame.Rect(S.WIDTH - 200, 20, 180, 60)
        pygame.draw.rect(screen, (40, 40, 40, 200), fallback_rect, border_radius=8)
        pygame.draw.rect(screen, (100, 100, 100), fallback_rect, width=2, border_radius=8)
        font = _get_dh_font(24)
        text = font.render(f"Score: {total_points:,}", True, (255, 255, 255))
        text_rect = text.get_rect(center=fallback_rect.center)
        screen.blit(text, text_rect)
        return
    
    # Update animation timer (60fps)
    _ANIM_TIMER += dt * _ANIM_FPS
    
    # Get current frame (loop through all frames)
    frame_index = int(_ANIM_TIMER) % len(scaled_frames)
    current_frame = scaled_frames[frame_index]
    
    scaled_w = current_frame.get_width()
    scaled_h = current_frame.get_height()
    
    # Position in top right corner (partially off-screen for corner alignment)
    bg_x = S.WIDTH - scaled_w - 2  # 2px padding from right edge (closer to corner)
    bg_y = -int(scaled_h * 0.1)  # Negative offset to push part of it off-screen at top
    
    # Draw current frame
    screen.blit(current_frame, (bg_x, bg_y))
    
    # Render score text (smaller font)
    font_size = max(14, min(20, int(scaled_h * 0.4)))
    font = _get_dh_font(font_size)
    
    # Format points with commas
    score_text = f"{total_points:,}"
    text_surface = font.render(score_text, True, (255, 255, 255))
    
    # Center text within the scaled image
    text_x = bg_x + (scaled_w - text_surface.get_width()) // 2
    text_y = bg_y + (scaled_h - text_surface.get_height()) // 2
    
    # Optional: Add shadow for readability
    shadow_surface = font.render(score_text, True, (0, 0, 0))
    screen.blit(shadow_surface, (text_x + 2, text_y + 2))
    screen.blit(text_surface, (text_x, text_y))

