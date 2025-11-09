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
    if not hasattr(gs, "_gambling_state"):
        gs._gambling_state = {}
    
    game_state = gs._gambling_state
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
    print(f"🎲 Doom Roll game initialized - Player starts with 1d100, betting {bet_amount} gold")

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
    """Draw prompt at bottom when it's player's turn to roll."""
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

# ---------- Screen lifecycle ----------
def enter(gs, bet_amount: int = 0, **_):
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
    
    # Initialize Doom Roll game with bet amount
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
    
    print("🎲 Entered gambling screen (first frame loaded instantly)")

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
    if game_state.get("result_card_active", False):
        title = game_state.get("result_card_title", "")
        subtitle = game_state.get("result_card_subtitle", "")
        _draw_result_card(screen, title, subtitle, dt)
    elif not game_state.get("game_over", False) and game_state.get("turn") == "player":
        # Show prompt when it's player's turn (no result card showing)
        _draw_player_turn_prompt(screen, game_state.get("current_die", 100), dt)

def _player_roll(gs):
    """Player rolls the dice. Returns True if game should continue, False if game over."""
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
    game_state["result_card_title"] = f"Player rolled 1d{current_die}"
    game_state["result_card_subtitle"] = f"Result: {roll_result}"
    game_state["waiting_for_result_dismiss"] = True
    
    print(f"🎲 Player rolled 1d{current_die} = {roll_result}")
    
    # Check if player lost (rolled 1)
    if roll_result == 1:
        game_state["game_over"] = True
        game_state["winner"] = "ai"
        game_state["result_card_title"] = "Player rolled 1d" + str(current_die)
        game_state["result_card_subtitle"] = f"Result: 1 - You Lose!"
        
        # Play lose sound (Laugh.mp3)
        _play_lose_sound()
        
        # Gold already deducted on enter, no need to deduct again
        print(f"💀 Player lost! Lost {game_state.get('bet_amount', 0)} gold")
        return False
    
    # Update current die for next player
    game_state["current_die"] = roll_result
    game_state["turn"] = "ai"
    return True

def _play_win_sound():
    """Play win sound (Angry.mp3)."""
    try:
        sound_path = os.path.join("Assets", "Tavern", "Angry.mp3")
        if os.path.exists(sound_path):
            sfx = pygame.mixer.Sound(sound_path)
            ch = pygame.mixer.find_channel(True)
            ch.play(sfx)
            print("🎵 Playing win sound (Angry.mp3)")
        else:
            print(f"⚠️ Win sound not found at {sound_path}")
    except Exception as e:
        print(f"⚠️ Failed to play win sound: {e}")

def _play_lose_sound():
    """Play lose sound (Laugh.mp3)."""
    try:
        sound_path = os.path.join("Assets", "Tavern", "Laugh.mp3")
        if os.path.exists(sound_path):
            sfx = pygame.mixer.Sound(sound_path)
            ch = pygame.mixer.find_channel(True)
            ch.play(sfx)
            print("🎵 Playing lose sound (Laugh.mp3)")
        else:
            print(f"⚠️ Lose sound not found at {sound_path}")
    except Exception as e:
        print(f"⚠️ Failed to play lose sound: {e}")

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
            print(f"💰 Player won! Awarded {winnings} gold (bet: {bet_amount}, total gold: {gs.gold})")
        
        return False
    
    # Update current die for next player
    game_state["current_die"] = roll_result
    game_state["turn"] = "player"
    return True

def handle(events, gs, dt: float, **_):
    """Handle events for the gambling screen."""
    game_state = getattr(gs, "_gambling_state", {})
    
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
                        # Return to tavern after a brief delay (or immediately)
                        print(f"🎲 Game over! Winner: {game_state.get('winner', 'unknown')}")
                        return "TAVERN"
                    else:
                        # Continue game - if it's AI turn, AI rolls immediately
                        if game_state.get("turn") == "ai":
                            # AI rolls automatically after player dismisses
                            _ai_roll(gs)
                        # If it's player turn, wait for player to click/roll
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Click dismisses result card
                game_state["result_card_active"] = False
                game_state["waiting_for_result_dismiss"] = False
                
                # Check if game is over
                if game_state.get("game_over", False):
                    # Return to tavern
                    print(f"🎲 Game over! Winner: {game_state.get('winner', 'unknown')}")
                    return "TAVERN"
                else:
                    # Continue game - if it's AI turn, AI rolls immediately
                    if game_state.get("turn") == "ai":
                        # AI rolls automatically after player dismisses
                        _ai_roll(gs)
                    # If it's player turn, wait for player to click/roll
        
        # Block other input while result card is showing
        return None
    
    # Normal game state - handle player input
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

