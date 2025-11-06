# ============================================================
# systems/score_display.py — Score Display (Top Right Corner)
# - Only appears after summoner battle victory (4.5 seconds)
# - Shows animated score rolling up to new value
# - Plays thunder sound after animation
# ============================================================

import os
import pygame
import settings as S
from systems import points as points_sys

# ---------- Constants ----------
ANIMATION_DURATION = 4.5  # Total animation duration in seconds

# ---------- Cache ----------
_SCORE_FRAMES: list[pygame.Surface] | None = None
_SCALED_FRAMES: list[pygame.Surface] | None = None
_FONT_CACHE: dict[int, pygame.font.Font] = {}
_ANIM_TIMER: float = 0.0
_ANIM_FPS: float = 8.0  # Animation FPS for the frames
_THUNDER_SOUND: pygame.mixer.Sound | None = None

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


def _load_thunder_sound() -> pygame.mixer.Sound | None:
    """Load and cache the thunder sound."""
    global _THUNDER_SOUND
    if _THUNDER_SOUND is not None:
        return _THUNDER_SOUND
    
    sound_path = os.path.join("Assets", "Music", "Sounds", "ScoreThunder.mp3")
    if not os.path.exists(sound_path):
        print(f"⚠️ ScoreThunder.mp3 not found at {sound_path}")
        return None
    
    try:
        _THUNDER_SOUND = pygame.mixer.Sound(sound_path)
        return _THUNDER_SOUND
    except Exception as e:
        print(f"⚠️ Failed to load ScoreThunder.mp3: {e}")
        return None


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


# ---------- Animation Control ----------

def start_score_animation(gs, start_score: int, target_score: int):
    """Start the score animation after a summoner battle victory."""
    gs.score_animation_active = True
    gs.score_animation_timer = 0.0
    gs.score_animation_start = start_score
    gs.score_animation_target = target_score
    gs.score_thunder_played = False


def is_animation_active(gs) -> bool:
    """Check if the score animation is currently active."""
    return getattr(gs, "score_animation_active", False)


# ---------- Drawing ----------

def draw_score(screen: pygame.Surface, gs, dt: float = 0.016):
    """
    Draw the animated score display in the top right corner.
    Only visible during the 4.5 second animation period after summoner battle victory.
    """
    global _ANIM_TIMER
    
    # Only draw if animation is active
    if not getattr(gs, "score_animation_active", False):
        return
    
    # Play thunder sound immediately when animation starts
    if not gs.score_thunder_played:
        gs.score_thunder_played = True
        thunder_sound = _load_thunder_sound()
        if thunder_sound:
            try:
                thunder_sound.play()
            except Exception as e:
                print(f"⚠️ Failed to play thunder sound: {e}")
    
    # Update animation timer
    gs.score_animation_timer += dt
    
    # Check if animation should end
    if gs.score_animation_timer >= ANIMATION_DURATION:
        gs.score_animation_active = False
        gs.score_animation_timer = 0.0
        return
    
    # Ensure points field exists
    points_sys.ensure_points_field(gs)
    
    # Calculate current displayed score (rolling up from start to target over full duration)
    progress = min(1.0, gs.score_animation_timer / ANIMATION_DURATION)  # Progress from 0.0 to 1.0
    # Use easing function for smooth roll-up (ease-out cubic)
    eased_progress = 1.0 - (1.0 - progress) ** 3
    current_score = int(gs.score_animation_start + (gs.score_animation_target - gs.score_animation_start) * eased_progress)
    
    # Scale factor (smaller)
    scale_factor = 0.25
    
    # Load and get scaled frames
    scaled_frames = _get_scaled_frames(scale_factor)
    if scaled_frames is None or len(scaled_frames) == 0:
        # Fallback: draw a simple rectangle if frames not found
        fallback_rect = pygame.Rect(S.LOGICAL_WIDTH - 200, 20, 180, 60)
        pygame.draw.rect(screen, (40, 40, 40, 200), fallback_rect, border_radius=8)
        pygame.draw.rect(screen, (100, 100, 100), fallback_rect, width=2, border_radius=8)
        font = _get_dh_font(24)
        text = font.render(f"Score: {current_score:,}", True, (255, 255, 255))
        text_rect = text.get_rect(center=fallback_rect.center)
        screen.blit(text, text_rect)
        return
    
    # Update frame animation timer
    _ANIM_TIMER += dt * _ANIM_FPS
    
    # Get current frame (loop through all frames)
    frame_index = int(_ANIM_TIMER) % len(scaled_frames)
    current_frame = scaled_frames[frame_index]
    
    scaled_w = current_frame.get_width()
    scaled_h = current_frame.get_height()
    
    # Position in top right corner (partially off-screen for corner alignment)
    bg_x = S.LOGICAL_WIDTH - scaled_w - 2  # 2px padding from right edge (closer to corner)
    bg_y = -int(scaled_h * 0.1)  # Negative offset to push part of it off-screen at top
    
    # Draw current frame
    screen.blit(current_frame, (bg_x, bg_y))
    
    # Render score text (smaller font)
    font_size = max(14, min(20, int(scaled_h * 0.4)))
    font = _get_dh_font(font_size)
    
    # Format points with commas
    score_text = f"{current_score:,}"
    text_surface = font.render(score_text, True, (255, 255, 255))
    
    # Center text within the scaled image
    text_x = bg_x + (scaled_w - text_surface.get_width()) // 2
    text_y = bg_y + (scaled_h - text_surface.get_height()) // 2
    
    # Optional: Add shadow for readability
    shadow_surface = font.render(score_text, True, (0, 0, 0))
    screen.blit(shadow_surface, (text_x + 2, text_y + 2))
    screen.blit(text_surface, (text_x, text_y))
