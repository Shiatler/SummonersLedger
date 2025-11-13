# =============================================================
# screens/boss_vs.py — Medieval VS Popup for Boss Battles
# - Shows player vs boss with medieval-themed VS popup overlay
# - Plays boss music
# - Dismissable by clicking or pressing Enter/Space
# - Transitions to summoner_battle.py when dismissed
# =============================================================
import os
import pygame
import settings as S
from systems import audio as audio_sys

# Animation timing
SLIDE_IN_TIME = 0.6  # Time for characters to slide in
VS_REVEAL_TIME = 0.3  # Time for VS text to appear
MIN_DISPLAY_TIME = 0.5  # Minimum time before can be dismissed

# Font helpers
_DH_FONT_PATH = None
def _resolve_dh_font() -> str | None:
    """Find a font file in Assets/Fonts (or absolute path) whose filename contains 'DH'."""
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

def _try_load(path: str | None):
    if path and os.path.exists(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"⚠️ load fail {path}: {e}")
    return None

def _smooth_scale_to_height(surf: pygame.Surface | None, target_h: int) -> pygame.Surface | None:
    if surf is None or target_h <= 0:
        return surf
    w, h = surf.get_width(), surf.get_height()
    if h <= 0: return surf
    s = target_h / float(h)
    return pygame.transform.smoothscale(surf, (max(1, int(w*s)), max(1, int(h*s))))

def _load_player_sprite(gs) -> pygame.Surface | None:
    """Load player character sprite."""
    gender = (getattr(gs, "chosen_gender", "") or "").lower().strip()
    if gender not in ("male", "female"):
        gender = (getattr(gs, "player_gender", "male") or "male").lower().strip()
        if gender not in ("male", "female"):
            gender = "male"
    fname = "CharacterMale.png" if gender == "male" else "CharacterFemale.png"
    path = os.path.join("Assets", "PlayableCharacters", fname)
    surf = _try_load(path)
    if surf:
        # Scale larger to fill more of the popup
        sh = S.LOGICAL_HEIGHT
        return _smooth_scale_to_height(surf, int(sh * 0.65))  # Larger presence on VS screen
    return None

def _pick_boss_track() -> str | None:
    """Pick a random boss music track."""
    base = os.path.join("Assets", "Music", "Boss")
    choices = [
        os.path.join(base, "Boss1.mp3"),
        os.path.join(base, "Boss2.mp3"),
    ]
    choices = [p for p in choices if os.path.exists(p)]
    return choices[0] if choices else None  # Use first available

def enter(gs, **_):
    """Initialize the VS screen."""
    # Get player name
    player_name = getattr(gs, "player_name", "Player") or "Player"
    
    # Get boss data
    boss_data = getattr(gs, "encounter_boss_data", None)
    if not boss_data:
        # Fallback - shouldn't happen but handle gracefully
        print("⚠️ No boss data for VS screen!")
        return
    
    boss_name = boss_data.get("name", "Boss")
    boss_sprite = boss_data.get("sprite")
    
    # Load player sprite
    player_sprite = _load_player_sprite(gs)
    
    # Scale boss sprite if needed (larger to match player)
    if boss_sprite:
        sh = S.LOGICAL_HEIGHT
        boss_sprite = _smooth_scale_to_height(boss_sprite, int(sh * 0.65))  # Larger presence on VS screen
    
    # Play boss music
    track = _pick_boss_track()
    if track:
        try:
            pygame.mixer.music.load(track)
            pygame.mixer.music.play(-1, fade_ms=200)
        except Exception as e:
            print(f"⚠️ Could not play boss music: {e}")
    
    # Initialize VS screen state
    gs._boss_vs = {
        "player_name": player_name,
        "boss_name": boss_name,
        "player_sprite": player_sprite,
        "boss_sprite": boss_sprite,
        "elapsed": 0.0,
        "phase": "slide_in",  # "slide_in" -> "vs_reveal" -> "done"
        "music_track": track,
        "music_pos": 0.0,
    }

def handle(events, gs, dt=None, **_):
    """Handle VS popup logic."""
    vs_state = getattr(gs, "_boss_vs", None)
    if vs_state is None:
        enter(gs)
        vs_state = gs._boss_vs
    
    # Update timer
    vs_state["elapsed"] += dt
    
    # Check for dismiss input (click or Enter/Space)
    can_dismiss = vs_state["elapsed"] >= MIN_DISPLAY_TIME
    
    if can_dismiss:
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Click anywhere to dismiss
                _dismiss_vs(gs)
                return "SUMMONER_BATTLE"
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                    _dismiss_vs(gs)
                    return "SUMMONER_BATTLE"
    
    return None

def _dismiss_vs(gs):
    """Clean up VS popup state and transition to summoner battle."""
    # Set flag to indicate we're coming from VS screen (for seamless music)
    # IMPORTANT: Set this BEFORE deleting _boss_vs so summoner_battle can check it
    gs._coming_from_boss_vs = True
    gs._keep_boss_music = True
    
    vs_state = getattr(gs, "_boss_vs", None)
    if vs_state:
        track = vs_state.get("music_track")
        if track:
            gs._boss_music_track = track
            print(f"🎵 Stored boss music track: {track}")
        try:
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms is not None and pos_ms >= 0:
                gs._boss_music_pos = pos_ms / 1000.0  # convert ms to seconds
                print(f"🎵 Stored music position: {gs._boss_music_pos:.2f}s")
        except Exception as e:
            print(f"⚠️ Could not get music position: {e}")
            gs._boss_music_pos = 0.0
    
    # Check if music is actually playing before transition
    try:
        is_playing = pygame.mixer.music.get_busy()
        print(f"🎵 Music status before transition: {'playing' if is_playing else 'stopped'}")
    except Exception as e:
        print(f"⚠️ Could not check music status: {e}")
    
    if hasattr(gs, "_boss_vs"):
        delattr(gs, "_boss_vs")
    
    # Transition to summoner battle (music continues seamlessly)
    from combat import summoner_battle
    print(f"🎵 Transitioning to summoner_battle with flag: {getattr(gs, '_coming_from_boss_vs', False)}")
    summoner_battle.enter(gs)

def draw(screen: pygame.Surface, gs, dt=None, **_):
    """Draw the VS popup overlay."""
    vs_state = getattr(gs, "_boss_vs", None)
    if vs_state is None:
        return
    
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    elapsed = vs_state["elapsed"]
    
    # Popup dimensions (smaller, centered on screen)
    popup_w = int(sw * 0.60)  # 60% of screen width (smaller)
    popup_h = int(sh * 0.40)  # 40% of screen height (smaller)
    popup_x = (sw - popup_w) // 2
    popup_y = (sh - popup_h) // 2
    
    # Semi-transparent dark overlay behind popup
    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))  # Darker overlay
    screen.blit(overlay, (0, 0))
    
    # Medieval popup background - diagonal split like Pokémon Gen 5
    popup_surface = pygame.Surface((popup_w, popup_h), pygame.SRCALPHA)
    
    # Left side - red/burgundy with horizontal speed lines
    left_color = (120, 30, 30)  # Dark red/burgundy
    left_stripe_color = (100, 20, 20)  # Darker red
    stripe_height = 8
    for i in range(0, popup_h, stripe_height * 2):
        pygame.draw.rect(popup_surface, left_color, (0, i, popup_w // 2, stripe_height))
        pygame.draw.rect(popup_surface, left_stripe_color, (0, i + stripe_height, popup_w // 2, stripe_height))
    
    # Right side - dark blue/grey with horizontal speed lines
    right_color = (40, 50, 70)  # Dark blue-grey
    right_stripe_color = (30, 40, 60)  # Darker blue-grey
    for i in range(0, popup_h, stripe_height * 2):
        pygame.draw.rect(popup_surface, right_color, (popup_w // 2, i, popup_w // 2, stripe_height))
        pygame.draw.rect(popup_surface, right_stripe_color, (popup_w // 2, i + stripe_height, popup_w // 2, stripe_height))
    
    # Diagonal split in the middle (jagged lightning-like effect)
    center_x = popup_w // 2
    points = []
    # Create jagged diagonal line
    for y in range(0, popup_h + 20, 15):
        offset = 8 if (y // 15) % 2 == 0 else -8
        points.append((center_x + offset, y))
    if len(points) > 1:
        pygame.draw.lines(popup_surface, (60, 60, 60), False, points, width=4)
        pygame.draw.lines(popup_surface, (40, 40, 40), False, points, width=2)
    
    # Draw border
    pygame.draw.rect(popup_surface, (80, 60, 40), popup_surface.get_rect(), width=4)
    
    # Blit popup background
    screen.blit(popup_surface, (popup_x, popup_y))
    
    # Calculate animation progress
    slide_progress = min(1.0, elapsed / SLIDE_IN_TIME)
    vs_progress = min(1.0, max(0.0, (elapsed - SLIDE_IN_TIME) / VS_REVEAL_TIME))
    
    # Easing functions
    ease_out_cubic = lambda t: 1.0 - pow(1.0 - t, 3)
    ease_in_cubic = lambda t: t * t * t
    
    slide_eased = ease_out_cubic(slide_progress)
    vs_eased = ease_in_cubic(vs_progress)
    
    # Calculate positions relative to popup
    popup_center_x = popup_x + popup_w // 2
    popup_center_y = popup_y + popup_h // 2
    
    # Player side (left) - slide in from left, show half-body, touching bottom
    player_sprite = vs_state.get("player_sprite")
    player_name = vs_state.get("player_name", "Player")
    player_half_h = 0  # Initialize for name positioning
    
    if player_sprite:
        player_w, player_h = player_sprite.get_size()
        # Crop to half-body (upper half)
        player_half_h = player_h // 2
        player_half_sprite = player_sprite.subsurface((0, 0, player_w, player_half_h))
        
        player_start_x = popup_x - player_w - 50
        player_target_x = popup_x + popup_w * 0.25  # Left quarter of popup
        player_x = player_start_x + (player_target_x - player_start_x) * slide_eased
        # Position sprite so bottom touches bottom of popup
        player_y = popup_y + popup_h - player_half_h
        
        screen.blit(player_half_sprite, (player_x - player_w // 2, player_y))
    
    # Boss side (right) - slide in from right, show half-body, touching bottom
    boss_sprite = vs_state.get("boss_sprite")
    boss_name = vs_state.get("boss_name", "Boss")
    boss_half_h = 0  # Initialize for name positioning
    
    if boss_sprite:
        boss_w, boss_h = boss_sprite.get_size()
        # Crop to half-body (upper half)
        boss_half_h = boss_h // 2
        boss_half_sprite = boss_sprite.subsurface((0, 0, boss_w, boss_half_h))
        
        boss_start_x = popup_x + popup_w + boss_w + 50
        boss_target_x = popup_x + popup_w * 0.75  # Right quarter of popup
        boss_x = boss_start_x + (boss_target_x - boss_start_x) * slide_eased
        # Position sprite so bottom touches bottom of popup
        boss_y = popup_y + popup_h - boss_half_h
        
        screen.blit(boss_half_sprite, (boss_x - boss_w // 2, boss_y))
    
    # VS text in center - appears after slide-in (Pokémon Gen 5 style)
    if vs_progress > 0:
        vs_font = _get_dh_font(90, bold=True)
        vs_text = "VS"
        
        # Orange/yellow color like Pokémon Gen 5
        vs_color = (255, 140, 0)  # Orange
        vs_outline_color = (255, 255, 255)  # White outline
        
        # Render with outline effect
        vs_surf = pygame.Surface((vs_font.size(vs_text)[0] + 8, vs_font.size(vs_text)[1] + 8), pygame.SRCALPHA)
        
        # Draw outline (white)
        for dx in [-2, 0, 2]:
            for dy in [-2, 0, 2]:
                if dx != 0 or dy != 0:
                    outline_surf = vs_font.render(vs_text, True, vs_outline_color)
                    vs_surf.blit(outline_surf, (4 + dx, 4 + dy))
        
        # Draw main text (orange)
        main_surf = vs_font.render(vs_text, True, vs_color)
        vs_surf.blit(main_surf, (4, 4))
        
        vs_w, vs_h = vs_surf.get_size()
        vs_x = popup_center_x - vs_w // 2
        vs_y = popup_center_y - vs_h // 2
        
        # Fade in
        vs_surf.set_alpha(int(255 * vs_eased))
        screen.blit(vs_surf, (vs_x, vs_y))
    
    # Draw names above sprites (white text like Pokémon Gen 5)
    name_font = _get_dh_font(28, bold=True)
    name_color = (255, 255, 255)  # White
    name_shadow = (40, 40, 40)  # Dark shadow
    
    # Player name (left side, above sprite)
    if player_sprite and slide_progress > 0.5:
        player_name_surf = name_font.render(player_name, True, name_color)
        player_name_shadow_surf = name_font.render(player_name, True, name_shadow)
        player_name_x = popup_x + popup_w * 0.25 - player_name_surf.get_width() // 2
        # Position above sprite (with some spacing)
        player_name_y = popup_y + popup_h - player_half_h - 50
        
        screen.blit(player_name_shadow_surf, (player_name_x + 2, player_name_y + 2))
        screen.blit(player_name_surf, (player_name_x, player_name_y))
    
    # Boss name (right side, above sprite)
    if boss_sprite and slide_progress > 0.5:
        boss_name_surf = name_font.render(boss_name, True, name_color)
        boss_name_shadow_surf = name_font.render(boss_name, True, name_shadow)
        boss_name_x = popup_x + popup_w * 0.75 - boss_name_surf.get_width() // 2
        # Position above sprite (with some spacing)
        boss_name_y = popup_y + popup_h - boss_half_h - 50
        
        screen.blit(boss_name_shadow_surf, (boss_name_x + 2, boss_name_y + 2))
        screen.blit(boss_name_surf, (boss_name_x, boss_name_y))
    
    # Draw dismiss hint (after minimum display time, at very bottom)
    if elapsed >= MIN_DISPLAY_TIME:
        hint_font = _get_dh_font(18)
        hint_text = "CLICK OR PRESS ENTER TO CONTINUE"
        hint_color = (255, 255, 255)  # White
        hint_shadow = (40, 40, 40)
        hint_surf = hint_font.render(hint_text, True, hint_color)
        hint_shadow_surf = hint_font.render(hint_text, True, hint_shadow)
        hint_x = popup_center_x - hint_surf.get_width() // 2
        hint_y = popup_y + popup_h - 20  # Near bottom of popup
        screen.blit(hint_shadow_surf, (hint_x + 1, hint_y + 1))
        screen.blit(hint_surf, (hint_x, hint_y))

