# =============================================================
# world/Tavern/gambling.py — Gambling screen
# - Shows animated gambling background (Gambling.gif)
# - Displays player character (MaleGambling.png or FemaleGambling.png)
# - Positioned same as Master Oak (centered, 15% from top, smaller scale)
# - Tavern music continues playing
# =============================================================

import os
import pygame
import settings as S

# ---------- Animator class (similar to master_oak.py) ----------
class Animator:
    def __init__(self, frames, fps=8, loop=True):
        self.frames = frames or []
        self.fps = max(1, int(fps))
        self.loop = loop
        self.t = 0.0
        self.index = 0

    def update(self, dt: float):
        if not self.frames:
            return
        self.t += dt
        step = 1.0 / self.fps
        while self.t >= step:
            self.t -= step
            self.index += 1
            if self.index >= len(self.frames):
                self.index = 0 if self.loop else len(self.frames) - 1

    def current(self):
        if not self.frames:
            return None
        return self.frames[self.index]

    def reset(self):
        self.t = 0.0
        self.index = 0

# ---------- Assets ----------
_BACKGROUND_FRAMES = None
_BACKGROUND_ANIMATOR = None
_CHARACTER_SCALE = 1.2  # Bigger scale
_LOADING_COMPLETE = False  # Track if all frames are loaded
_LOADING_STARTED = False  # Track if we've started loading all frames
_PIL_IMAGE = None  # Store PIL image for incremental loading
_PIL_FRAME_INDEX = 0  # Current frame index being loaded
_PLAYER_GAMBLING_IMAGE_CACHE = None  # Cache player gambling image
_PLAYER_GAMBLING_GENDER = None  # Track which gender is cached
_FRAMES_PER_UPDATE = 5  # Load 5 frames per update cycle to avoid blocking

def _get_player_display_name(gs) -> str:
    name = (getattr(gs, "player_name", "") or "").strip()
    return name if name else "Player"

def _load_first_frame_instantly(path: str) -> pygame.Surface | None:
    """Load just the first frame instantly using pygame (fast, no PIL needed)."""
    try:
        # pygame can load the first frame of a GIF instantly
        bg = pygame.image.load(path).convert()
        bg = pygame.transform.smoothscale(bg, (S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT))
        return bg
    except Exception as e:
        print(f"⚠️ Failed to load first frame: {e}")
        return None

def _init_pil_loading(path: str) -> bool:
    """Initialize PIL image for incremental loading. Returns True if successful."""
    global _PIL_IMAGE, _LOADING_STARTED
    if _PIL_IMAGE is not None:
        return True
    
    try:
        from PIL import Image
        _PIL_IMAGE = Image.open(path)
        _LOADING_STARTED = True
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"⚠️ Failed to initialize PIL loading: {e}")
        return False

def _load_frames_incrementally(path: str) -> bool:
    """Load a few frames per call to avoid blocking. Returns True if more frames to load."""
    global _BACKGROUND_FRAMES, _BACKGROUND_ANIMATOR, _LOADING_COMPLETE, _PIL_IMAGE, _PIL_FRAME_INDEX
    
    if _LOADING_COMPLETE:
        return False
    
    # Initialize PIL if not already done
    if _PIL_IMAGE is None:
        if not _init_pil_loading(path):
            # PIL not available - mark as complete with just first frame
            _LOADING_COMPLETE = True
            return False
    
    try:
        from PIL import Image
        target_size = (S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT)
        frames_loaded_this_update = 0
        new_frames = []
        
        # Start from where we left off
        try:
            _PIL_IMAGE.seek(_PIL_FRAME_INDEX)
        except (EOFError, ValueError):
            # No more frames
            _LOADING_COMPLETE = True
            if _PIL_IMAGE:
                _PIL_IMAGE.close()
                _PIL_IMAGE = None
            return False
        
        # Load a few frames this update cycle
        while frames_loaded_this_update < _FRAMES_PER_UPDATE:
            try:
                # Convert frame to RGBA
                if _PIL_IMAGE.mode == 'P':
                    frame = _PIL_IMAGE.convert('RGBA')
                elif _PIL_IMAGE.mode != 'RGBA':
                    frame = _PIL_IMAGE.convert('RGBA')
                else:
                    frame = _PIL_IMAGE
                
                # Convert to pygame Surface
                size = frame.size
                data = frame.tobytes()
                pygame_surface = pygame.image.frombytes(data, size, 'RGBA')
                
                # Scale if needed
                if size != target_size:
                    pygame_surface = pygame.transform.smoothscale(pygame_surface, target_size)
                new_frames.append(pygame_surface)
                
                frames_loaded_this_update += 1
                _PIL_FRAME_INDEX += 1
                
                # Try to seek to next frame
                try:
                    _PIL_IMAGE.seek(_PIL_FRAME_INDEX)
                except (EOFError, ValueError):
                    # No more frames
                    _LOADING_COMPLETE = True
                    if _PIL_IMAGE:
                        _PIL_IMAGE.close()
                        _PIL_IMAGE = None
                    break
            except (EOFError, ValueError):
                # No more frames
                _LOADING_COMPLETE = True
                if _PIL_IMAGE:
                    _PIL_IMAGE.close()
                    _PIL_IMAGE = None
                break
        
        # Add new frames to existing frames
        if new_frames:
            # Append to existing frames (first frame is already in _BACKGROUND_FRAMES)
            _BACKGROUND_FRAMES.extend(new_frames)
            
            # Update animator with all frames so far
            _BACKGROUND_ANIMATOR = Animator(_BACKGROUND_FRAMES, fps=20, loop=True)
            
            if _LOADING_COMPLETE:
                print(f"✅ Loaded all {len(_BACKGROUND_FRAMES)} frames from Gambling.gif (started with frame 0, added frames 1+)")
        
        return not _LOADING_COMPLETE  # Return True if more frames to load
    except Exception as e:
        print(f"⚠️ Failed to load frames incrementally: {e}")
        _LOADING_COMPLETE = True
        if _PIL_IMAGE:
            _PIL_IMAGE.close()
            _PIL_IMAGE = None
        return False

def _load_background_animation() -> list[pygame.Surface] | None:
    """Load background animation - loads first frame instantly for immediate display."""
    global _BACKGROUND_FRAMES, _BACKGROUND_ANIMATOR, _LOADING_COMPLETE, _LOADING_STARTED, _PIL_FRAME_INDEX
    
    # If already fully loaded, return cached frames
    if _BACKGROUND_FRAMES is not None and _LOADING_COMPLETE:
        return _BACKGROUND_FRAMES
    
    path = os.path.join("Assets", "Tavern", "Gambling.gif")
    if not os.path.exists(path):
        print(f"⚠️ Gambling.gif not found at {path}")
        return None
    
    # Load first frame instantly (fast, no PIL needed) - screen appears immediately
    if _BACKGROUND_FRAMES is None:
        first_frame = _load_first_frame_instantly(path)
        if not first_frame:
            return None
        
        # Set first frame immediately so screen can display instantly
        _BACKGROUND_FRAMES = [first_frame]
        _BACKGROUND_ANIMATOR = Animator(_BACKGROUND_FRAMES, fps=20, loop=True)
        _LOADING_COMPLETE = False  # Mark as incomplete (only first frame loaded)
        _LOADING_STARTED = False
        _PIL_FRAME_INDEX = 1  # Start from frame 1 (frame 0 is already loaded as first_frame)
        print("✅ Loaded first frame instantly")
    
    return _BACKGROUND_FRAMES

def _load_player_gambling_image(gs) -> pygame.Surface | None:
    """Load the player gambling character image based on gender.
    Returns MaleGambling.png or FemaleGambling.png, scaled to bigger size.
    Caches the image to avoid reloading every frame.
    """
    global _PLAYER_GAMBLING_IMAGE_CACHE, _PLAYER_GAMBLING_GENDER
    
    # Get player gender
    player_gender = getattr(gs, "player_gender", "male")
    
    # Return cached image if gender matches
    if _PLAYER_GAMBLING_IMAGE_CACHE is not None and _PLAYER_GAMBLING_GENDER == player_gender:
        return _PLAYER_GAMBLING_IMAGE_CACHE
    
    # Determine filename based on gender
    if player_gender.lower().startswith("f"):
        filename = "FemaleGambling.png"
    else:
        filename = "MaleGambling.png"
    
    path = os.path.join("Assets", "Tavern", filename)
    if not os.path.exists(path):
        print(f"⚠️ {filename} not found at {path}")
        return None
    
    try:
        img = pygame.image.load(path).convert_alpha()
        # Scale to bigger size (1.2x scale)
        original_size = img.get_size()
        scaled_size = (int(original_size[0] * _CHARACTER_SCALE), int(original_size[1] * _CHARACTER_SCALE))
        img = pygame.transform.smoothscale(img, scaled_size)
        
        # Cache the image
        _PLAYER_GAMBLING_IMAGE_CACHE = img
        _PLAYER_GAMBLING_GENDER = player_gender
        print(f"✅ Loaded and scaled {filename} to {scaled_size[0]}x{scaled_size[1]}")
        return img
    except Exception as e:
        print(f"⚠️ Failed to load {filename}: {e}")
        return None

# ---------- Doom Roll Game State ----------
def _init_doom_roll_game(gs, bet_amount: int = 0):
    """Initialize Doom Roll game state."""
    # Clear any previous state and create fresh dictionary
    gs._gambling_state = {}
    game_state = gs._gambling_state
    
    game_state["game_type"] = "doom_roll"
    game_state["current_die"] = 100  # Start with d100
    game_state["turn"] = "player"  # "player" or "ai"
    game_state["game_over"] = False
    game_state["winner"] = None  # "player" or "ai"
    game_state["waiting_for_result_dismiss"] = False
    game_state["result_card_active"] = False  # No result card showing initially
    game_state["result_card_title"] = ""
    game_state["result_card_subtitle"] = ""
    game_state["bet_amount"] = bet_amount  # Store bet amount
    game_state["gold_updated"] = False  # Track if gold has been updated
    player_name = _get_player_display_name(gs)
    print(f"🎲 Doom Roll game initialized - {player_name} starts with 1d100, betting {bet_amount} gold")

# ---------- Twenty-One Game State ----------
def _init_twenty_one_game(gs, bet_amount: int = 0):
    """Initialize Twenty-One game state."""
    # Clear any previous state and create fresh dictionary
    gs._gambling_state = {}
    game_state = gs._gambling_state
    
    game_state["game_type"] = "twenty_one"
    game_state["bet_amount"] = bet_amount
    game_state["player_total"] = 0
    game_state["gambler_total"] = 0
    game_state["player_dice"] = []
    game_state["gambler_dice"] = []
    game_state["phase"] = "initial_rolls"  # "initial_rolls" | "player_turn" | "gambler_turn" | "game_over"
    game_state["current_turn"] = "player"  # For initial rolls
    game_state["result_card_active"] = False
    game_state["result_card_title"] = ""
    game_state["result_card_subtitle"] = ""
    game_state["waiting_for_result_dismiss"] = False
    game_state["winner"] = None  # "player" | "gambler" | "tie"
    game_state["gold_updated"] = False
    game_state["twenty_one_buttons"] = []  # Clear any leftover buttons
    
    # Start with player's initial roll
    try:
        from rolling.roller import roll_dice
        from rolling.sfx import play_dice
        player_name = _get_player_display_name(gs)
        
        # Player rolls 2d10
        total, rolls = roll_dice(2, 10)
        game_state["player_dice"] = rolls if rolls else [total // 2, total - (total // 2)]
        game_state["player_total"] = sum(game_state["player_dice"])
        play_dice()
        
        # Show result card
        game_state["result_card_active"] = True
        game_state["result_card_title"] = f"{player_name} rolled 2d10"
        game_state["result_card_subtitle"] = f"Result: {game_state['player_dice'][0]}, {game_state['player_dice'][1]} = {game_state['player_total']}"
        game_state["waiting_for_result_dismiss"] = True
        game_state["current_turn"] = "gambler"  # Next will be gambler's initial roll
        
        print(f"🎲 Twenty-One game initialized - {player_name} rolled {game_state['player_dice']} = {game_state['player_total']}, betting {bet_amount} gold")
    except Exception as e:
        print(f"⚠️ Error initializing Twenty-One game: {e}")
        import traceback
        traceback.print_exc()
        # Reset to safe state
        game_state["phase"] = "player_turn"  # Skip initial rolls if they fail
        game_state["result_card_active"] = False

def _get_dh_font(size: int) -> pygame.font.Font:
    """Get DH font at specified size, fallback to default font."""
    try:
        dh_font_path = os.path.join(S.ASSETS_FONTS_DIR, S.DND_FONT_FILE)
        if os.path.exists(dh_font_path):
            return pygame.font.Font(dh_font_path, size)
    except:
        pass
    return pygame.font.SysFont(None, size)

def _draw_result_card(screen: pygame.Surface, title: str, subtitle: str, dt: float):
    """Draw result card at bottom of screen (same style as buff_popup result cards)."""
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)
    
    # Box styling (matches buff_popup result card)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)
    
    # Text rendering
    text = f"{title} - {subtitle}" if title and subtitle else (title or subtitle or "")
    font = _get_dh_font(28)
    words = text.split(" ")
    lines, cur = [], ""
    max_w = rect.w - 40
    for w in words:
        test = (cur + " " + w).strip()
        if not cur or font.size(test)[0] <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    
    y = rect.y + 20
    for line in lines:
        surf = font.render(line, False, (16, 16, 16))
        screen.blit(surf, (rect.x + 20, y))
        y += surf.get_height() + 6
    
    # Blinking prompt
    if not hasattr(_draw_result_card, "blink_t"):
        _draw_result_card.blink_t = 0.0
    _draw_result_card.blink_t += dt
    blink_on = int(_draw_result_card.blink_t * 2) % 2 == 0
    if blink_on:
        prompt_font = _get_dh_font(20)
        prompt = "Press SPACE or Click to continue"
        psurf = prompt_font.render(prompt, False, (100, 100, 100))
        screen.blit(psurf, (rect.right - psurf.get_width() - 20, rect.bottom - psurf.get_height() - 12))

def _draw_player_turn_prompt(screen: pygame.Surface, current_die: int, dt: float):
    """Draw prompt at bottom when it's player's turn to roll (Doom Roll)."""
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)
    
    # Box styling (matches result card)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)
    
    # Text rendering
    title = f"Your Turn - Roll 1d{current_die}"
    subtitle = "First to roll 1 loses!"
    text = f"{title} - {subtitle}"
    font = _get_dh_font(28)
    words = text.split(" ")
    lines, cur = [], ""
    max_w = rect.w - 40
    for w in words:
        test = (cur + " " + w).strip()
        if not cur or font.size(test)[0] <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    
    y = rect.y + 20
    for line in lines:
        surf = font.render(line, False, (16, 16, 16))
        screen.blit(surf, (rect.x + 20, y))
        y += surf.get_height() + 6
    
    # Blinking prompt
    if not hasattr(_draw_player_turn_prompt, "blink_t"):
        _draw_player_turn_prompt.blink_t = 0.0
    _draw_player_turn_prompt.blink_t += dt
    blink_on = int(_draw_player_turn_prompt.blink_t * 2) % 2 == 0
    if blink_on:
        prompt_font = _get_dh_font(20)
        prompt = "Press SPACE or Click to roll"
        psurf = prompt_font.render(prompt, False, (100, 100, 100))
        screen.blit(psurf, (rect.right - psurf.get_width() - 20, rect.bottom - psurf.get_height() - 12))

def _draw_twenty_one_player_turn(screen: pygame.Surface, gs, player_total: int, gambler_total: int, dt: float):
    """Draw player turn UI for Twenty-One (with Roll and Stand buttons)."""
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    box_h = 180
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)
    
    # Box styling (matches result card)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)
    
    # Totals display
    font = _get_dh_font(24)
    player_name = _get_player_display_name(gs)
    totals_text = f"{player_name}'s Total: {player_total} | The Orc: {gambler_total}"
    totals_surf = font.render(totals_text, True, (220, 210, 190))
    totals_x = rect.x + (rect.w - totals_surf.get_width()) // 2
    totals_y = rect.y + 20
    screen.blit(totals_surf, (totals_x, totals_y))
    
    # Buttons
    button_font = _get_dh_font(22)
    button_h = 50
    button_w = 180
    button_gap = 30
    buttons_y = totals_y + totals_surf.get_height() + 20
    
    # Roll button (disabled if player_total >= 21)
    roll_button_x = rect.x + (rect.w - (button_w * 2 + button_gap)) // 2
    roll_button_rect = pygame.Rect(roll_button_x, buttons_y, button_w, button_h)
    
    # Stand button
    stand_button_x = roll_button_x + button_w + button_gap
    stand_button_rect = pygame.Rect(stand_button_x, buttons_y, button_w, button_h)
    
    # Store button rects in game state for click detection
    game_state = getattr(gs, "_gambling_state", {})
    game_state["twenty_one_buttons"] = [
        (roll_button_rect, "roll"),
        (stand_button_rect, "stand"),
    ]
    
    # Mouse position for hover - convert to logical coordinates
    screen_mx, screen_my = pygame.mouse.get_pos()
    try:
        from systems import coords
        logical_mouse_x, logical_mouse_y = coords.screen_to_logical((screen_mx, screen_my))
    except (ImportError, AttributeError):
        # Fallback if coords not available
        logical_mouse_x, logical_mouse_y = screen_mx, screen_my
    
    # Draw Roll button
    roll_enabled = player_total < 21
    roll_hover = roll_button_rect.collidepoint(logical_mouse_x, logical_mouse_y) and roll_enabled
    roll_color = (230, 228, 220) if roll_hover else ((240, 238, 232) if roll_enabled else (200, 200, 200))
    pygame.draw.rect(screen, roll_color, roll_button_rect, border_radius=6)
    pygame.draw.rect(screen, (60, 60, 60), roll_button_rect, 2, border_radius=6)
    roll_text = button_font.render("Roll 1d10", True, ((16, 16, 16) if roll_enabled else (120, 120, 120)))
    roll_text_x = roll_button_rect.x + (roll_button_rect.w - roll_text.get_width()) // 2
    roll_text_y = roll_button_rect.y + (roll_button_rect.h - roll_text.get_height()) // 2
    screen.blit(roll_text, (roll_text_x, roll_text_y))
    
    # Draw Stand button
    stand_hover = stand_button_rect.collidepoint(logical_mouse_x, logical_mouse_y)
    stand_color = (230, 228, 220) if stand_hover else (240, 238, 232)
    pygame.draw.rect(screen, stand_color, stand_button_rect, border_radius=6)
    pygame.draw.rect(screen, (60, 60, 60), stand_button_rect, 2, border_radius=6)
    stand_text = button_font.render("Stand", True, (16, 16, 16))
    stand_text_x = stand_button_rect.x + (stand_button_rect.w - stand_text.get_width()) // 2
    stand_text_y = stand_button_rect.y + (stand_button_rect.h - stand_text.get_height()) // 2
    screen.blit(stand_text, (stand_text_x, stand_text_y))
    
    # Warning if over 21
    if player_total > 21:
        warning_font = _get_dh_font(20)
        warning_text = "BUST! You lose!"
        warning_surf = warning_font.render(warning_text, True, (200, 50, 50))
        warning_x = rect.x + (rect.w - warning_surf.get_width()) // 2
        warning_y = buttons_y + button_h + 10
        screen.blit(warning_surf, (warning_x, warning_y))

# ---------- Screen lifecycle ----------
def enter(gs, bet_amount: int = 0, game_type: str = "doom_roll", **_):
    """Initialize the gambling screen state - loads first frame instantly, rest loads in update()."""
    global _BACKGROUND_ANIMATOR, _BACKGROUND_FRAMES, _LOADING_COMPLETE
    
    # Load first frame instantly (fast, no blocking) - screen appears immediately
    if _BACKGROUND_FRAMES is None or not _LOADING_COMPLETE:
        _load_background_animation()
    
    # Reset animator (instant - first frame is already loaded)
    if _BACKGROUND_ANIMATOR:
        _BACKGROUND_ANIMATOR.reset()
    elif _BACKGROUND_FRAMES:
        _BACKGROUND_ANIMATOR = Animator(_BACKGROUND_FRAMES, fps=20, loop=True)
    
    # Initialize game based on type
    if game_type == "twenty_one":
        _init_twenty_one_game(gs, bet_amount)
    else:
        _init_doom_roll_game(gs, bet_amount)
    
    # Deduct bet amount from player's gold immediately
    if bet_amount > 0:
        if not hasattr(gs, "gold"):
            gs.gold = 0
        player_gold = gs.gold
        if player_gold >= bet_amount:
            gs.gold = player_gold - bet_amount
            print(f"💰 Deducted {bet_amount} gold (had {player_gold}, now {gs.gold})")
    
    # Don't load all frames here - let update() handle it after screen is visible
    # This ensures screen appears instantly with first frame
    
    print(f"🎲 Entered gambling screen ({game_type}) (first frame loaded instantly)")

def draw(screen: pygame.Surface, gs, dt: float, **_):
    """Draw the gambling screen."""
    # Draw animated background
    if _BACKGROUND_ANIMATOR:
        bg_frame = _BACKGROUND_ANIMATOR.current()
        if bg_frame:
            screen.blit(bg_frame, (0, 0))
        else:
            screen.fill((0, 0, 0))
    elif _BACKGROUND_FRAMES and len(_BACKGROUND_FRAMES) > 0:
        # Fallback: show first frame if animator not available
        screen.blit(_BACKGROUND_FRAMES[0], (0, 0))
    else:
        # Fallback: black screen
        screen.fill((0, 0, 0))
    
    # Draw player gambling character (positioned further down)
    player_img = _load_player_gambling_image(gs)
    if player_img:
        # Position: center horizontally, higher up (20% from top)
        player_x = (S.LOGICAL_WIDTH - player_img.get_width()) // 2
        player_y = int(S.LOGICAL_HEIGHT * 0.20)
        screen.blit(player_img, (player_x, player_y))
    
    # Draw result card if showing
    game_state = getattr(gs, "_gambling_state", {})
    game_type = game_state.get("game_type", "doom_roll")
    
    if game_state.get("result_card_active", False):
        title = game_state.get("result_card_title", "")
        subtitle = game_state.get("result_card_subtitle", "")
        _draw_result_card(screen, title, subtitle, dt)
    elif not game_state.get("game_over", False):
        if game_type == "twenty_one":
            # Show player turn UI for Twenty-One
            phase = game_state.get("phase", "initial_rolls")
            if phase == "player_turn":
                _draw_twenty_one_player_turn(screen, gs, game_state.get("player_total", 0), game_state.get("gambler_total", 0), dt)
        else:
            # Show Doom Roll prompt
            if game_state.get("turn") == "player":
                _draw_player_turn_prompt(screen, game_state.get("current_die", 100), dt)

def _player_roll(gs):
    """Player rolls the dice. Returns True if game should continue, False if game over."""
    from rolling.roller import roll_dice
    from rolling.sfx import play_dice
    
    game_state = gs._gambling_state
    current_die = game_state["current_die"]
    player_name = _get_player_display_name(gs)
    
    # Roll 1d[current_die]
    total, rolls = roll_dice(1, current_die)
    roll_result = rolls[0] if rolls else total
    
    # Play dice sound
    play_dice()
    
    # Show result card
    game_state["result_card_active"] = True
    game_state["result_card_title"] = f"{player_name} rolled 1d{current_die}"
    game_state["result_card_subtitle"] = f"Result: {roll_result}"
    game_state["waiting_for_result_dismiss"] = True
    
    print(f"🎲 {player_name} rolled 1d{current_die} = {roll_result}")
    
    # Check if player lost (rolled 1)
    if roll_result == 1:
        game_state["game_over"] = True
        game_state["winner"] = "ai"
        game_state["result_card_title"] = f"{player_name} rolled 1d{current_die}"
        game_state["result_card_subtitle"] = "Result: 1 - You Lose!"
        
        # Play lose sound (Laugh.mp3)
        _play_lose_sound()
        
        # Gold already deducted on enter, no need to deduct again
        print(f"💀 {player_name} lost! Lost {game_state.get('bet_amount', 0)} gold")
        return False
    
    # Update current die for next player
    game_state["current_die"] = roll_result
    game_state["turn"] = "ai"
    return True

def _play_win_sound():
    """Play win sound (Angry.mp3)."""
    try:
        from systems import audio
        sound_path = os.path.join("Assets", "Tavern", "Angry.mp3")
        if os.path.exists(sound_path):
            sfx = pygame.mixer.Sound(sound_path)
            # Use audio.play_sound to respect volume settings
            audio.play_sound(sfx)
            print("🎵 Playing win sound (Angry.mp3)")
        else:
            print(f"⚠️ Win sound not found at {sound_path}")
    except Exception as e:
        print(f"⚠️ Failed to play win sound: {e}")

def _play_lose_sound():
    """Play lose sound (Laugh.mp3)."""
    try:
        from systems import audio
        sound_path = os.path.join("Assets", "Tavern", "Laugh.mp3")
        if os.path.exists(sound_path):
            sfx = pygame.mixer.Sound(sound_path)
            # Use audio.play_sound to respect volume settings
            audio.play_sound(sfx)
            print("🎵 Playing lose sound (Laugh.mp3)")
        else:
            print(f"⚠️ Lose sound not found at {sound_path}")
    except Exception as e:
        print(f"⚠️ Failed to play lose sound: {e}")

def _should_gambler_roll_twenty_one(gambler_total: int, player_total: int) -> bool:
    """AI decision logic for Twenty-One gambler."""
    import random
    
    # Always roll if player is ahead
    if player_total > gambler_total:
        return True
    
    # Always roll if 14 or under
    if gambler_total <= 14:
        return True
    
    # Never roll if 18+ (unless player has 19 or 20)
    if gambler_total >= 18:
        if player_total >= 19:
            return True
        return False
    
    # 15-17: Percentage chance
    if gambler_total == 15:
        return random.random() < 0.50  # 50%
    elif gambler_total == 16:
        return random.random() < 0.30  # 30%
    elif gambler_total == 17:
        return random.random() < 0.15  # 15%
    
    return False

def _twenty_one_player_roll(gs):
    """Player rolls 1d10 in Twenty-One."""
    try:
        from rolling.roller import roll_dice
        from rolling.sfx import play_dice
    except ImportError as e:
        print(f"⚠️ Failed to import dice rolling modules: {e}")
        return False
    
    try:
        game_state = gs._gambling_state
        if not game_state:
            print("⚠️ Game state not found")
            return False
        
        if game_state.get("player_total", 0) >= 21:
            return False  # Can't roll if already at/over 21
        player_name = _get_player_display_name(gs)
        
        # Roll 1d10
        total, rolls = roll_dice(1, 10)
        roll_result = rolls[0] if rolls else total
        
        play_dice()
        
        # Add to player dice and total
        if "player_dice" not in game_state:
            game_state["player_dice"] = []
        game_state["player_dice"].append(roll_result)
        game_state["player_total"] = game_state.get("player_total", 0) + roll_result
        
        # Show result card
        game_state["result_card_active"] = True
        game_state["result_card_title"] = f"{player_name} rolled 1d10"
        game_state["result_card_subtitle"] = f"Result: {roll_result}. New Total: {game_state['player_total']}"
        game_state["waiting_for_result_dismiss"] = True
        
        print(f"🎲 {player_name} rolled 1d10 = {roll_result}, new total: {game_state['player_total']}")
        
        # Check for bust
        if game_state["player_total"] > 21:
            game_state["game_over"] = True
            game_state["winner"] = "gambler"
            game_state["result_card_title"] = f"{player_name} rolled 1d10"
            game_state["result_card_subtitle"] = f"Result: {roll_result}. Total: {game_state['player_total']} - BUST! You Lose!"
            _play_lose_sound()
            return False
        
        # If exactly 21, auto-stand
        if game_state["player_total"] == 21:
            game_state["phase"] = "gambler_turn"
            return True
        
        # Stay in player turn (can roll again or stand)
        return True
    except Exception as e:
        print(f"⚠️ Error in _twenty_one_player_roll: {e}")
        import traceback
        traceback.print_exc()
        return False

def _twenty_one_gambler_roll(gs):
    """Gambler rolls 1d10 in Twenty-One."""
    try:
        from rolling.roller import roll_dice
        from rolling.sfx import play_dice
    except ImportError as e:
        print(f"⚠️ Failed to import dice rolling modules: {e}")
        return False
    
    try:
        game_state = gs._gambling_state
        if not game_state:
            print("⚠️ Game state not found")
            return False
        
        # Roll 1d10
        total, rolls = roll_dice(1, 10)
        roll_result = rolls[0] if rolls else total
        
        play_dice()
        
        # Add to gambler dice and total
        if "gambler_dice" not in game_state:
            game_state["gambler_dice"] = []
        game_state["gambler_dice"].append(roll_result)
        game_state["gambler_total"] = game_state.get("gambler_total", 0) + roll_result
        
        # Show result card
        game_state["result_card_active"] = True
        game_state["result_card_title"] = "The Orc rolled 1d10"
        game_state["result_card_subtitle"] = f"Result: {roll_result}. New Total: {game_state['gambler_total']}"
        game_state["waiting_for_result_dismiss"] = True
        
        print(f"🎲 The Orc rolled 1d10 = {roll_result}, new total: {game_state['gambler_total']}")
        
        # Check for bust
        if game_state["gambler_total"] > 21:
            game_state["game_over"] = True
            game_state["winner"] = "player"
            game_state["result_card_title"] = "The Orc rolled 1d10"
            game_state["result_card_subtitle"] = f"Result: {roll_result}. Total: {game_state['gambler_total']} - BUST! You Win!"
            _play_win_sound()
            # Award double the bet
            bet_amount = game_state.get("bet_amount", 0)
            if bet_amount > 0 and not game_state.get("gold_updated", False):
                if not hasattr(gs, "gold"):
                    gs.gold = 0
                winnings = bet_amount * 2
                gs.gold = gs.gold + winnings
                game_state["gold_updated"] = True
                print(f"💰 {_get_player_display_name(gs)} won! Awarded {winnings} gold")
            return False
        
        # If exactly 21, end game
        if game_state["gambler_total"] == 21:
            game_state["phase"] = "game_over"
            _determine_twenty_one_winner(gs)
            return False
        
        # Continue gambler turn (AI decides again)
        return True
    except Exception as e:
        print(f"⚠️ Error in _twenty_one_gambler_roll: {e}")
        import traceback
        traceback.print_exc()
        return False

def _determine_twenty_one_winner(gs):
    """Determine winner of Twenty-One game and handle payouts."""
    game_state = gs._gambling_state
    player_total = game_state["player_total"]
    gambler_total = game_state["gambler_total"]
    bet_amount = game_state.get("bet_amount", 0)
    player_name = _get_player_display_name(gs)
    
    # Both busted = tie (refund bet)
    if player_total > 21 and gambler_total > 21:
        game_state["winner"] = "tie"
        if bet_amount > 0 and not game_state.get("gold_updated", False):
            if not hasattr(gs, "gold"):
                gs.gold = 0
            gs.gold = gs.gold + bet_amount  # Refund
            game_state["gold_updated"] = True
            print(f"💰 Tie! Refunded {bet_amount} gold")
    # Player busted = gambler wins
    elif player_total > 21:
        game_state["winner"] = "gambler"
        _play_lose_sound()
        print(f"💀 {player_name} lost! Lost {bet_amount} gold")
    # Gambler busted = player wins
    elif gambler_total > 21:
        game_state["winner"] = "player"
        _play_win_sound()
        if bet_amount > 0 and not game_state.get("gold_updated", False):
            if not hasattr(gs, "gold"):
                gs.gold = 0
            winnings = bet_amount * 2
            gs.gold = gs.gold + winnings
            game_state["gold_updated"] = True
            print(f"💰 {player_name} won! Awarded {winnings} gold")
    # Neither busted - higher total wins
    else:
        if player_total > gambler_total:
            game_state["winner"] = "player"
            _play_win_sound()
            if bet_amount > 0 and not game_state.get("gold_updated", False):
                if not hasattr(gs, "gold"):
                    gs.gold = 0
                winnings = bet_amount * 2
                gs.gold = gs.gold + winnings
                game_state["gold_updated"] = True
                print(f"💰 {player_name} won! Awarded {winnings} gold")
        elif gambler_total > player_total:
            game_state["winner"] = "gambler"
            _play_lose_sound()
            print(f"💀 {player_name} lost! Lost {bet_amount} gold")
        else:
            game_state["winner"] = "tie"
            if bet_amount > 0 and not game_state.get("gold_updated", False):
                if not hasattr(gs, "gold"):
                    gs.gold = 0
                gs.gold = gs.gold + bet_amount  # Refund
                game_state["gold_updated"] = True
                print(f"💰 Tie! Refunded {bet_amount} gold")
    
    # Mark game as over
    game_state["game_over"] = True
    
    # Show final result card
    game_state["result_card_active"] = True
    game_state["waiting_for_result_dismiss"] = True
    
    if game_state["winner"] == "player":
        game_state["result_card_title"] = "You Win!"
        game_state["result_card_subtitle"] = f"{player_name}: {player_total} | The Orc: {gambler_total}"
    elif game_state["winner"] == "gambler":
        game_state["result_card_title"] = "You Lose!"
        game_state["result_card_subtitle"] = f"{player_name}: {player_total} | The Orc: {gambler_total}"
    else:
        game_state["result_card_title"] = "Tie!"
        game_state["result_card_subtitle"] = f"{player_name}: {player_total} | The Orc: {gambler_total}"

def _handle_twenty_one_initial_rolls(gs):
    """Handle initial rolls phase for Twenty-One."""
    try:
        game_state = gs._gambling_state
        if not game_state:
            print("⚠️ Game state not found in _handle_twenty_one_initial_rolls")
            return
        
        player_name = _get_player_display_name(gs)
        
        if game_state.get("current_turn") == "gambler":
            # Gambler's initial roll
            try:
                from rolling.roller import roll_dice
                from rolling.sfx import play_dice
            except ImportError as e:
                print(f"⚠️ Failed to import dice rolling modules: {e}")
                return
            
            total, rolls = roll_dice(2, 10)
            game_state["gambler_dice"] = rolls if rolls else [total // 2, total - (total // 2)]
            game_state["gambler_total"] = sum(game_state["gambler_dice"])
            play_dice()
            
            game_state["result_card_active"] = True
            game_state["result_card_title"] = "The Orc rolled 2d10"
            game_state["result_card_subtitle"] = f"Result: {game_state['gambler_dice'][0]}, {game_state['gambler_dice'][1]} = {game_state['gambler_total']}"
            game_state["waiting_for_result_dismiss"] = True
            
            print(f"🎲 The Orc rolled {game_state['gambler_dice']} = {game_state['gambler_total']}")
            
            # Check for instant losses
            player_total = game_state.get("player_total", 0)
            gambler_total = game_state.get("gambler_total", 0)
            
            if player_total > 21 and gambler_total > 21:
                game_state["phase"] = "game_over"
                _determine_twenty_one_winner(gs)
            elif player_total > 21:
                game_state["phase"] = "game_over"
                game_state["winner"] = "gambler"
                _play_lose_sound()
                game_state["result_card_title"] = "You Lose!"
                game_state["result_card_subtitle"] = f"{player_name}: {player_total} (BUST) | The Orc: {gambler_total}"
            elif gambler_total > 21:
                game_state["phase"] = "game_over"
                game_state["winner"] = "player"
                _play_win_sound()
                bet_amount = game_state.get("bet_amount", 0)
                if bet_amount > 0 and not game_state.get("gold_updated", False):
                    if not hasattr(gs, "gold"):
                        gs.gold = 0
                    winnings = bet_amount * 2
                    gs.gold = gs.gold + winnings
                    game_state["gold_updated"] = True
                game_state["result_card_title"] = "You Win!"
                game_state["result_card_subtitle"] = f"{player_name}: {player_total} | The Orc: {gambler_total} (BUST)"
            else:
                # Move to player turn
                game_state["phase"] = "player_turn"
                game_state["current_turn"] = "player"
    except Exception as e:
        print(f"⚠️ Error in _handle_twenty_one_initial_rolls: {e}")
        import traceback
        traceback.print_exc()

def _ai_roll(gs):
    """AI rolls the dice. Returns True if game should continue, False if game over."""
    from rolling.roller import roll_dice
    from rolling.sfx import play_dice
    
    game_state = gs._gambling_state
    current_die = game_state["current_die"]
    
    # Roll 1d[current_die]
    total, rolls = roll_dice(1, current_die)
    roll_result = rolls[0] if rolls else total
    
    # Play dice sound
    play_dice()
    
    # Show result card
    game_state["result_card_active"] = True
    game_state["result_card_title"] = f"The Orc rolled 1d{current_die}"
    game_state["result_card_subtitle"] = f"Result: {roll_result}"
    game_state["waiting_for_result_dismiss"] = True
    
    print(f"🎲 The Orc rolled 1d{current_die} = {roll_result}")
    
    # Check if The Orc lost (rolled 1)
    if roll_result == 1:
        game_state["game_over"] = True
        game_state["winner"] = "player"
        game_state["result_card_title"] = "The Orc rolled 1d" + str(current_die)
        game_state["result_card_subtitle"] = f"Result: 1 - You Win!"
        
        # Play win sound (Angry.mp3)
        _play_win_sound()
        
        # Award double the bet amount (bet was already deducted, so add 2x bet)
        bet_amount = game_state.get("bet_amount", 0)
        if bet_amount > 0 and not game_state.get("gold_updated", False):
            if not hasattr(gs, "gold"):
                gs.gold = 0
            winnings = bet_amount * 2  # Double the bet
            gs.gold = gs.gold + winnings
            game_state["gold_updated"] = True
            print(f"💰 {_get_player_display_name(gs)} won! Awarded {winnings} gold (bet: {bet_amount}, total gold: {gs.gold})")
        
        return False
    
    # Update current die for next player
    game_state["current_die"] = roll_result
    game_state["turn"] = "player"
    return True

def handle(events, gs, dt: float, **_):
    """Handle events for the gambling screen."""
    game_state = getattr(gs, "_gambling_state", {})
    game_type = game_state.get("game_type", "doom_roll")
    
    # If result card is showing, handle dismissal
    if game_state.get("result_card_active", False) and game_state.get("waiting_for_result_dismiss", False):
        for event in events:
            if event.type == pygame.KEYDOWN:
                # ESC always exits
                if event.key == pygame.K_ESCAPE:
                    print("🎲 Exiting gambling screen")
                    return "TAVERN"
                # SPACE or ENTER dismisses result card
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                    # Dismiss result card
                    game_state["result_card_active"] = False
                    game_state["waiting_for_result_dismiss"] = False
                    
                    # Check if game is over
                    if game_state.get("game_over", False):
                        print(f"🎲 Game over! Winner: {game_state.get('winner', 'unknown')}")
                        return "TAVERN"
                    else:
                        # Handle game-specific logic after result card dismissal
                        if game_type == "twenty_one":
                            phase = game_state.get("phase", "initial_rolls")
                            if phase == "initial_rolls":
                                # Continue initial rolls phase
                                _handle_twenty_one_initial_rolls(gs)
                            elif phase == "gambler_turn":
                                # AI decides whether to roll
                                if _should_gambler_roll_twenty_one(game_state["gambler_total"], game_state["player_total"]):
                                    _twenty_one_gambler_roll(gs)
                                else:
                                    # Gambler stands - determine winner
                                    game_state["phase"] = "game_over"
                                    _determine_twenty_one_winner(gs)
                        else:
                            # Doom Roll logic
                            if game_state.get("turn") == "ai":
                                _ai_roll(gs)
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Click dismisses result card
                game_state["result_card_active"] = False
                game_state["waiting_for_result_dismiss"] = False
                
                # Check if game is over
                if game_state.get("game_over", False):
                    print(f"🎲 Game over! Winner: {game_state.get('winner', 'unknown')}")
                    return "TAVERN"
                else:
                    # Handle game-specific logic after result card dismissal
                    if game_type == "twenty_one":
                        phase = game_state.get("phase", "initial_rolls")
                        if phase == "initial_rolls":
                            # Continue initial rolls phase
                            _handle_twenty_one_initial_rolls(gs)
                        elif phase == "gambler_turn":
                            # AI decides whether to roll
                            if _should_gambler_roll_twenty_one(game_state["gambler_total"], game_state["player_total"]):
                                _twenty_one_gambler_roll(gs)
                            else:
                                # Gambler stands - determine winner
                                game_state["phase"] = "game_over"
                                _determine_twenty_one_winner(gs)
                    else:
                        # Doom Roll logic
                        if game_state.get("turn") == "ai":
                            _ai_roll(gs)
        
        # Block other input while result card is showing
        return None
    
    # Normal game state - handle player input
    if game_type == "twenty_one":
        # Twenty-One game logic
        phase = game_state.get("phase", "initial_rolls")
        
        if phase == "player_turn":
            # Handle player turn actions
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        print("🎲 Exiting gambling screen")
                        return "TAVERN"
                    elif event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                        # Roll 1d10
                        if game_state["player_total"] < 21:
                            _twenty_one_player_roll(gs)
                    elif event.key == pygame.K_s:
                        # Stand
                        game_state["phase"] = "gambler_turn"
                        # AI decides immediately
                        if _should_gambler_roll_twenty_one(game_state["gambler_total"], game_state["player_total"]):
                            _twenty_one_gambler_roll(gs)
                        else:
                            # Gambler stands - determine winner
                            game_state["phase"] = "game_over"
                            _determine_twenty_one_winner(gs)
                
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # event.pos is already converted to logical coordinates in main.py
                    click_pos = event.pos
                    
                    buttons = game_state.get("twenty_one_buttons", [])
                    for button_rect, action in buttons:
                        if button_rect.collidepoint(click_pos):
                            if action == "roll" and game_state["player_total"] < 21:
                                _twenty_one_player_roll(gs)
                            elif action == "stand":
                                game_state["phase"] = "gambler_turn"
                                # AI decides immediately
                                if _should_gambler_roll_twenty_one(game_state["gambler_total"], game_state["player_total"]):
                                    _twenty_one_gambler_roll(gs)
                                else:
                                    # Gambler stands - determine winner
                                    game_state["phase"] = "game_over"
                                    _determine_twenty_one_winner(gs)
                            break
    else:
        # Doom Roll game logic
        for event in events:
            if event.type == pygame.KEYDOWN:
                # ESC key exits back to tavern
                if event.key == pygame.K_ESCAPE:
                    print("🎲 Exiting gambling screen")
                    return "TAVERN"
                # SPACE or ENTER rolls (if player's turn)
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                    if game_state.get("turn") == "player" and not game_state.get("game_over", False):
                        # Player rolls
                        _player_roll(gs)
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Click rolls (if player's turn)
                if game_state.get("turn") == "player" and not game_state.get("game_over", False):
                    # Player rolls
                    _player_roll(gs)
    
    return None

def update(gs, dt, **_):
    """Update gambling screen (animate background and load frames incrementally)."""
    global _LOADING_COMPLETE
    
    # Load frames incrementally (a few per update cycle to avoid blocking)
    if not _LOADING_COMPLETE:
        path = os.path.join("Assets", "Tavern", "Gambling.gif")
        if os.path.exists(path):
            # Load a few frames this update cycle (non-blocking)
            _load_frames_incrementally(path)
    
    # Update background animation
    if _BACKGROUND_ANIMATOR:
        _BACKGROUND_ANIMATOR.update(dt)

