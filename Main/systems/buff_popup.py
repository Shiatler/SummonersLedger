# ============================================================
# systems/buff_popup.py — Buff Selection Popup System
# - Shows intro animation with Blessings/Curses/DemonPact image
# - Displays textbox with message
# - Shows 3 clickable cards for selection
# ============================================================

import os
import random
import pygame
import settings as S
from systems import buffs
from systems import audio as audio_sys
from systems import audio

# Font helper
_DH_FONT_PATH = None

def _resolve_dh_font() -> str | None:
    """Find a font file in Assets/Fonts whose filename contains 'DH'."""
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
    _DH_FONT_PATH = None
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
        return pygame.font.SysFont("georgia", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)

# State
_ACTIVE = False
_STATE = None

# Image cache
_BLESSINGS_IMG = None
_CURSES_IMG = None
_DEMONPACT_IMG = None

# Sound cache
_BLESSINGS_SOUND = None
_CURSES_SOUND = None
_DEMONPACT_SOUND = None

# Music paths
_BLESSINGS_MUSIC = None
_CURSES_MUSIC = None
_DEMONPACT_MUSIC = None

# Message lines cache
_BLESSINGS_MESSAGES = None
_CURSES_MESSAGES = None
_DEMONPACT_MESSAGES = None

def _load_intro_images():
    """Load the intro images."""
    global _BLESSINGS_IMG, _CURSES_IMG, _DEMONPACT_IMG
    
    if _BLESSINGS_IMG is None:
        path = os.path.join("Assets", "Blessings", "Blessings.png")
        if os.path.exists(path):
            try:
                _BLESSINGS_IMG = pygame.image.load(path).convert_alpha()
                print(f"✅ Loaded Blessings.png: {_BLESSINGS_IMG.get_size()}")
            except Exception as e:
                print(f"⚠️ Failed to load Blessings.png: {e}")
        else:
            print(f"⚠️ Blessings.png not found at: {path}")
    
    if _CURSES_IMG is None:
        path = os.path.join("Assets", "Blessings", "Curses.png")
        if os.path.exists(path):
            try:
                _CURSES_IMG = pygame.image.load(path).convert_alpha()
                print(f"✅ Loaded Curses.png: {_CURSES_IMG.get_size()}")
            except Exception as e:
                print(f"⚠️ Failed to load Curses.png: {e}")
        else:
            print(f"⚠️ Curses.png not found at: {path}")
    
    if _DEMONPACT_IMG is None:
        path = os.path.join("Assets", "Blessings", "DemonPact.png")
        if os.path.exists(path):
            try:
                _DEMONPACT_IMG = pygame.image.load(path).convert_alpha()
                print(f"✅ Loaded DemonPact.png: {_DEMONPACT_IMG.get_size()}")
            except Exception as e:
                print(f"⚠️ Failed to load DemonPact.png: {e}")
        else:
            print(f"⚠️ DemonPact.png not found at: {path}")


def _load_intro_sounds():
    """Load the intro sound files."""
    global _BLESSINGS_SOUND, _CURSES_SOUND, _DEMONPACT_SOUND
    
    if _BLESSINGS_SOUND is None:
        path = os.path.join("Assets", "Blessings", "Blessings.mp3")
        if os.path.exists(path):
            try:
                _BLESSINGS_SOUND = pygame.mixer.Sound(path)
                print(f"✅ Loaded Blessings.mp3")
            except Exception as e:
                print(f"⚠️ Failed to load Blessings.mp3: {e}")
        else:
            print(f"⚠️ Blessings.mp3 not found at: {path}")
    
    if _CURSES_SOUND is None:
        path = os.path.join("Assets", "Blessings", "Curses.mp3")
        if os.path.exists(path):
            try:
                _CURSES_SOUND = pygame.mixer.Sound(path)
                print(f"✅ Loaded Curses.mp3")
            except Exception as e:
                print(f"⚠️ Failed to load Curses.mp3: {e}")
        else:
            print(f"⚠️ Curses.mp3 not found at: {path}")
    
    if _DEMONPACT_SOUND is None:
        path = os.path.join("Assets", "Blessings", "DemonPact.mp3")
        if os.path.exists(path):
            try:
                _DEMONPACT_SOUND = pygame.mixer.Sound(path)
                print(f"✅ Loaded DemonPact.mp3")
            except Exception as e:
                print(f"⚠️ Failed to load DemonPact.mp3: {e}")
        else:
            print(f"⚠️ DemonPact.mp3 not found at: {path}")


def _load_card_selection_music():
    """Load the card selection music files."""
    global _BLESSINGS_MUSIC, _CURSES_MUSIC, _DEMONPACT_MUSIC
    
    if _BLESSINGS_MUSIC is None:
        path = os.path.join("Assets", "Blessings", "BlessingsSong.mp3")
        if os.path.exists(path):
            _BLESSINGS_MUSIC = path
            print(f"✅ Found BlessingsSong.mp3")
        else:
            print(f"⚠️ BlessingsSong.mp3 not found at: {path}")
    
    if _CURSES_MUSIC is None:
        path = os.path.join("Assets", "Blessings", "CursesSong.mp3")
        if os.path.exists(path):
            _CURSES_MUSIC = path
            print(f"✅ Found CursesSong.mp3")
        else:
            print(f"⚠️ CursesSong.mp3 not found at: {path}")
    
    if _DEMONPACT_MUSIC is None:
        path = os.path.join("Assets", "Blessings", "DemonPactSong.mp3")
        if os.path.exists(path):
            _DEMONPACT_MUSIC = path
            print(f"✅ Found DemonPactSong.mp3")
        else:
            print(f"⚠️ DemonPactSong.mp3 not found at: {path}")


def _load_message_lines():
    """Load message lines from text files."""
    global _BLESSINGS_MESSAGES, _CURSES_MESSAGES, _DEMONPACT_MESSAGES
    
    if _BLESSINGS_MESSAGES is None:
        path = os.path.join("Assets", "Blessings", "Blessings.txt")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                _BLESSINGS_MESSAGES = lines
                print(f"✅ Loaded {len(lines)} blessing messages")
            except Exception as e:
                print(f"⚠️ Failed to load Blessings.txt: {e}")
                _BLESSINGS_MESSAGES = ["Receive my blessings"]  # Fallback
        else:
            print(f"⚠️ Blessings.txt not found at: {path}")
            _BLESSINGS_MESSAGES = ["Receive my blessings"]  # Fallback
    
    if _CURSES_MESSAGES is None:
        path = os.path.join("Assets", "Blessings", "Curses.txt")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                _CURSES_MESSAGES = lines
                print(f"✅ Loaded {len(lines)} curse messages")
            except Exception as e:
                print(f"⚠️ Failed to load Curses.txt: {e}")
                _CURSES_MESSAGES = ["Curse you"]  # Fallback
        else:
            print(f"⚠️ Curses.txt not found at: {path}")
            _CURSES_MESSAGES = ["Curse you"]  # Fallback
    
    if _DEMONPACT_MESSAGES is None:
        path = os.path.join("Assets", "Blessings", "DemonPact.txt")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                _DEMONPACT_MESSAGES = lines
                print(f"✅ Loaded {len(lines)} demon pact messages")
            except Exception as e:
                print(f"⚠️ Failed to load DemonPact.txt: {e}")
                _DEMONPACT_MESSAGES = ["Make a pact with a devil?"]  # Fallback
        else:
            print(f"⚠️ DemonPact.txt not found at: {path}")
            _DEMONPACT_MESSAGES = ["Make a pact with a devil?"]  # Fallback


def _get_random_message(tier: str) -> str:
    """Get a random message for the given tier."""
    import random
    
    # Load messages if not already loaded
    _load_message_lines()
    
    if tier == "Curse":
        if _CURSES_MESSAGES and len(_CURSES_MESSAGES) > 0:
            return random.choice(_CURSES_MESSAGES)
        return "Curse you"  # Fallback
    elif tier == "DemonPact":
        if _DEMONPACT_MESSAGES and len(_DEMONPACT_MESSAGES) > 0:
            return random.choice(_DEMONPACT_MESSAGES)
        return "Make a pact with a devil?"  # Fallback
    else:
        # Common, Rare, Epic, Legendary all use Blessings messages
        if _BLESSINGS_MESSAGES and len(_BLESSINGS_MESSAGES) > 0:
            return random.choice(_BLESSINGS_MESSAGES)
        return "Receive my blessings"  # Fallback


def is_active() -> bool:
    """Check if buff popup is active."""
    return _ACTIVE


def start_buff_selection(gs):
    """Start the buff selection process."""
    global _ACTIVE, _STATE
    
    # Load intro images and sounds FIRST before using them
    _load_intro_images()
    _load_intro_sounds()
    _load_card_selection_music()
    
    # Generate buff selection
    selection = buffs.generate_buff_selection()
    tier = selection["tier"]
    cards = selection["cards"]
    
    # Curse/DemonPact priority is handled in buffs.generate_buff_selection()
    # So at this point, tier is already correct
    
    # Load message lines before getting random message
    _load_message_lines()
    
    # Determine intro image, message, sound, and animation duration based on tier
    if tier == "Curse":
        intro_image = _CURSES_IMG
        intro_sound = _CURSES_SOUND
        message = _get_random_message(tier)
        animation_duration = 6.0  # Curses.mp3 is 6 seconds
    elif tier == "DemonPact":
        intro_image = _DEMONPACT_IMG
        intro_sound = _DEMONPACT_SOUND
        message = _get_random_message(tier)
        animation_duration = 11.0  # DemonPact.mp3 is 11 seconds
    else:
        intro_image = _BLESSINGS_IMG
        intro_sound = _BLESSINGS_SOUND
        message = _get_random_message(tier)
        animation_duration = 7.0  # Blessings.mp3 is 7 seconds
    
    # Debug: Check if image was loaded
    if intro_image is None:
        print(f"⚠️ Warning: Intro image for tier '{tier}' is None!")
    else:
        print(f"✅ Using intro image for tier '{tier}': {intro_image.get_size()}")
    
    # Play the sound
    if intro_sound:
        try:
            intro_sound.play()
            print(f"🔊 Playing {tier} sound")
        except Exception as e:
            print(f"⚠️ Failed to play {tier} sound: {e}")
    else:
        print(f"⚠️ Warning: Intro sound for tier '{tier}' is None!")
    
    # Load card images and get card data
    card_images = []
    for card in cards:
        img = buffs.load_card_image(card["image_path"])
        card_images.append(img)
        # Add card data (name and description) to card dict
        card_data = buffs.get_card_data(card["name"])
        card["display_name"] = card_data["name"]
        card["description"] = card_data["description"]
    
    # Initialize state
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    # Calculate start position - way off screen (negative, above view)
    start_y = -int(sh * 0.5)  # Start 50% of screen height above the screen
    # Calculate target position - near top of screen but visible
    target_y = int(sh * 0.15)  # 15% from top of screen
    
    _STATE = {
        "phase": "intro",  # "intro" -> "textbox" -> "cards" -> "done"
        "tier": tier,
        "cards": cards,
        "card_images": card_images,
        "intro_image": intro_image,
        "intro_sound": intro_sound,  # Store sound so we can stop it on ESC
        "message": message,
        "intro_y": start_y,  # Start way off-screen top
        "intro_start_y": start_y,  # Store initial start position
        "intro_target_y": target_y,  # Target position (near top, visible)
        "intro_t": 0.0,
        "intro_duration": animation_duration,  # Match sound duration
        "textbox_active": False,
        "hovered_index": None,
        "selected_index": None,
        "transition_timer": 0.0,
    }
    
    # Stop overworld music before starting animation
    try:
        # Store current track if not already stored
        if not hasattr(gs, "_buff_popup_previous_track"):
            gs._buff_popup_previous_track = getattr(gs, "last_overworld_track", None)
        # Stop music with fade
        audio.stop_music(fade_ms=300)
        print(f"🔇 Stopped overworld music for buff popup")
    except Exception as e:
        print(f"⚠️ Failed to stop overworld music: {e}")
    
    _ACTIVE = True
    print(f"🎬 Buff popup started: tier={tier}, phase=intro, intro_image={'loaded' if intro_image else 'MISSING'}")
    
    # Play click sound
    try:
        audio_sys.play_click(audio_sys.get_global_bank())
    except Exception:
        pass


def handle_event(event, gs) -> bool:
    """Handle input events. Returns True if event was consumed."""
    global _STATE, _ACTIVE
    
    if not _ACTIVE or _STATE is None:
        return False
    
    phase = _STATE.get("phase", "intro")
    
    # ESC key handling - skip animation/card selection
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        if phase == "intro":
            # Skip intro animation and textbox, go straight to cards
            _STATE["phase"] = "cards"
            _STATE["intro_t"] = _STATE["intro_duration"]  # Mark animation as complete
            _STATE["intro_y"] = _STATE.get("intro_target_y", 100)  # Set final position
            _STATE["textbox_active"] = False
            # Stop intro sound if playing
            try:
                intro_sound = _STATE.get("intro_sound")
                if intro_sound:
                    intro_sound.stop()
            except Exception:
                pass
            print(f"⏭️ Skipped intro animation")
            return True
        elif phase == "textbox":
            # Skip textbox, go to cards
            _STATE["phase"] = "cards"
            _STATE["textbox_active"] = False
            print(f"⏭️ Skipped textbox")
            return True
        elif phase == "cards":
            # Auto-select a random card
            if _STATE.get("selected_index") is None:
                import random
                cards = _STATE.get("cards", [])
                if cards:
                    random_index = random.randint(0, len(cards) - 1)
                    _STATE["selected_index"] = random_index
                    try:
                        audio_sys.play_click(audio_sys.get_global_bank())
                    except Exception:
                        pass
                    # Apply the buff
                    _apply_selected_buff(gs, random_index)
                    _STATE["phase"] = "done"
                    print(f"⏭️ Skipped card selection, auto-selected card {random_index + 1}")
                    return True
        return True  # Consume ESC in any phase
    
    # Textbox phase - dismiss on click/enter
    if phase == "textbox":
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            _STATE["phase"] = "cards"
            _STATE["textbox_active"] = False
            try:
                audio_sys.play_click(audio_sys.get_global_bank())
            except Exception:
                pass
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            _STATE["phase"] = "cards"
            _STATE["textbox_active"] = False
            try:
                audio_sys.play_click(audio_sys.get_global_bank())
            except Exception:
                pass
            return True
        # Block all input while textbox is active
        return True
    
    # Cards phase
    if phase == "cards":
        if _STATE.get("selected_index") is not None:
            return False  # Already selected, transitioning
        
        if event.type == pygame.MOUSEMOTION:
            mouse_pos = event.pos
            hovered = _get_card_at_position(mouse_pos)
            _STATE["hovered_index"] = hovered
            return False
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_pos = event.pos
            clicked = _get_card_at_position(mouse_pos)
            if clicked is not None:
                _STATE["selected_index"] = clicked
                try:
                    audio_sys.play_click(audio_sys.get_global_bank())
                except Exception:
                    pass
                # Apply the buff
                _apply_selected_buff(gs, clicked)
                _STATE["phase"] = "done"
                return True
    
    return False


def update(dt, gs):
    """Update animation and state."""
    global _STATE, _ACTIVE
    
    if not _ACTIVE or _STATE is None:
        return
    
    phase = _STATE.get("phase", "intro")
    
    # Intro animation - image flies down slowly from way off screen
    if phase == "intro":
        _STATE["intro_t"] += dt
        progress = min(1.0, _STATE["intro_t"] / _STATE["intro_duration"])
        
        # Ease out animation (starts fast, slows down at end)
        ease = 1.0 - (1.0 - progress) ** 3
        
        # Use stored start and target positions
        start_y = _STATE.get("intro_start_y", -200)
        target_y = _STATE.get("intro_target_y", 100)
        current_y = start_y + (target_y - start_y) * ease
        
        _STATE["intro_y"] = current_y
        
        # Debug output (only print occasionally to avoid spam)
        if int(_STATE["intro_t"] * 10) % 5 == 0:  # Print roughly every 0.5 seconds
            print(f"🎬 Intro animation: progress={progress:.2f}, y={current_y:.1f}")
        
        # When animation completes, show textbox
        if progress >= 1.0:
            _STATE["phase"] = "textbox"
            _STATE["textbox_active"] = True
            print(f"✅ Intro animation complete, showing textbox")
    
    # Cards phase - start background music when entering this phase
    elif phase == "cards" and not _STATE.get("music_started", False):
        _start_card_selection_music(_STATE.get("tier", "Common"))
        _STATE["music_started"] = True
    
    # Done phase - transition out
    elif phase == "done":
        _STATE["transition_timer"] += dt
        if _STATE["transition_timer"] > 0.5:  # 0.5 second delay
            # Stop card selection music
            _stop_card_selection_music()
            
            # Restart overworld music after buff selection completes
            try:
                # Get AUDIO bank from settings or gs
                AUDIO = getattr(S, "AUDIO_BANK", None)
                if AUDIO is None:
                    # Try to get it from gs if stored
                    AUDIO = getattr(gs, "_audio_bank", None)
                
                if AUDIO:
                    previous_track = getattr(gs, "_buff_popup_previous_track", None)
                    nxt = audio.pick_next_track(AUDIO, previous_track, prefix="music")
                    if nxt:
                        audio.play_music(AUDIO, nxt, loop=False, fade_ms=600)
                        gs.last_overworld_track = nxt
                        print(f"🔊 Restarted overworld music: {nxt}")
                # Clear stored track
                if hasattr(gs, "_buff_popup_previous_track"):
                    delattr(gs, "_buff_popup_previous_track")
            except Exception as e:
                print(f"⚠️ Failed to restart overworld music: {e}")
            
            # Start score animation after buff selection completes
            if hasattr(gs, "pending_score_animation") and gs.pending_score_animation:
                from systems import score_display
                start_score = getattr(gs, "pending_score_start", 0)
                target_score = getattr(gs, "pending_score_target", 0)
                score_display.start_score_animation(gs, start_score, target_score)
                # Clear pending flags
                gs.pending_score_animation = False
                if hasattr(gs, "pending_score_start"):
                    delattr(gs, "pending_score_start")
                if hasattr(gs, "pending_score_target"):
                    delattr(gs, "pending_score_target")
            
            _ACTIVE = False
            _STATE = None


def draw(screen, dt):
    """Draw the buff popup."""
    global _STATE
    
    if not _ACTIVE or _STATE is None:
        return
    
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    phase = _STATE.get("phase", "intro")
    
    # Draw intro image (flying down animation)
    if phase in ("intro", "textbox"):
        intro_img = _STATE.get("intro_image")
        if intro_img is not None:
            try:
                # Scale image to MASSIVE size
                img_w, img_h = intro_img.get_size()
                if img_h > 0:
                    # Use a huge percentage of screen height for maximum dramatic effect
                    target_h = int(S.LOGICAL_HEIGHT * 0.85)  # 85% of screen height (MASSIVE!)
                    scale = target_h / img_h
                    scaled_w = int(img_w * scale)
                    scaled_h = int(img_h * scale)
                    scaled_img = pygame.transform.smoothscale(intro_img, (scaled_w, scaled_h))
                    
                    # Draw at current position
                    img_x = (sw - scaled_w) // 2
                    img_y = int(_STATE.get("intro_y", -200))
                    screen.blit(scaled_img, (img_x, img_y))
            except Exception as e:
                print(f"⚠️ Error drawing intro image: {e}")
        else:
            # Draw a placeholder if image is missing
            placeholder_rect = pygame.Rect(sw // 2 - 100, int(_STATE.get("intro_y", -200)), 200, 100)
            pygame.draw.rect(screen, (255, 0, 0), placeholder_rect)  # Red placeholder
            font = _get_dh_font(20)
            text = font.render(f"Missing: {_STATE.get('tier', 'Unknown')}", True, (255, 255, 255))
            screen.blit(text, (placeholder_rect.x + 10, placeholder_rect.y + 10))
    
    # Draw textbox
    if phase == "textbox" and _STATE.get("textbox_active"):
        _draw_textbox(screen, _STATE["message"], dt)
    
    # Draw cards
    if phase == "cards":
        _draw_cards(screen, _STATE)


def _draw_textbox(screen, message: str, dt):
    """Draw the textbox with message."""
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)
    
    # Box styling (matches rolling/ui look)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)
    
    # Text rendering
    font = _get_dh_font(28)
    words = message.split(" ")
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
    if not hasattr(_draw_textbox, "blink_t"):
        _draw_textbox.blink_t = 0.0
    _draw_textbox.blink_t += dt
    blink_on = int(_draw_textbox.blink_t * 2) % 2 == 0
    if blink_on:
        prompt_font = _get_dh_font(20)
        prompt = "Press Enter to continue"
        psurf = prompt_font.render(prompt, False, (40, 40, 40))
        px = rect.right - psurf.get_width() - 16
        py = rect.bottom - psurf.get_height() - 12
        screen.blit(psurf, (px, py))


def _draw_cards(screen, st):
    """Draw the 3 card selection."""
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    
    # Dark semi-transparent overlay
    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))
    
    # Title
    tier = st["tier"]
    if tier == "Curse":
        title_text = "Choose a Curse"
    elif tier == "DemonPact":
        title_text = "Make A Pact With A Demon"
    else:
        title_text = "Choose a Blessing"
    title_font = _get_dh_font(48, bold=True)
    title_surf = title_font.render(title_text, True, (255, 255, 255))
    title_rect = title_surf.get_rect(center=(sw // 2, 80))
    screen.blit(title_surf, title_rect)
    
    # Tier label (don't show for DemonPact since the title says it all)
    if tier != "DemonPact":
        tier_font = _get_dh_font(32)
        tier_surf = tier_font.render(f"{tier} Tier", True, (200, 200, 200))
        tier_rect = tier_surf.get_rect(center=(sw // 2, title_rect.bottom + 20))
        screen.blit(tier_surf, tier_rect)
    
    # Draw 3 cards
    card_width = 280
    card_height = 400
    card_spacing = 40
    total_width = (card_width * 3) + (card_spacing * 2)
    start_x = (sw - total_width) // 2
    card_y = sh // 2 - card_height // 2
    
    for i, card in enumerate(st["cards"]):
        card_x = start_x + i * (card_width + card_spacing)
        
        # Hover effect
        is_hovered = st.get("hovered_index") == i
        is_selected = st.get("selected_index") == i
        
        # Scale for hover
        scale = 1.1 if is_hovered else 1.0
        if is_selected:
            scale = 1.15
        
        # Card image
        card_img = st["card_images"][i]
        if card_img:
            # Scale image
            scaled_w = int(card_width * scale)
            scaled_h = int(card_height * scale)
            scaled_img = pygame.transform.smoothscale(card_img, (scaled_w, scaled_h))
            
            # Center the scaled card
            draw_x = card_x + (card_width - scaled_w) // 2
            draw_y = card_y + (card_height - scaled_h) // 2
            
            # Draw border/glow for hover
            if is_hovered or is_selected:
                border_color = (255, 215, 0) if is_selected else (255, 255, 255)
                border_width = 4 if is_selected else 2
                border_rect = pygame.Rect(draw_x - border_width, draw_y - border_width,
                                        scaled_w + border_width * 2, scaled_h + border_width * 2)
                pygame.draw.rect(screen, border_color, border_rect, border_width, border_radius=8)
            
            screen.blit(scaled_img, (draw_x, draw_y))
        else:
            # Fallback: draw a placeholder
            placeholder_rect = pygame.Rect(card_x, card_y, card_width, card_height)
            pygame.draw.rect(screen, (60, 60, 60), placeholder_rect)
            pygame.draw.rect(screen, (120, 120, 120), placeholder_rect, 3)
    
    # Draw tooltip if hovering over a card
    hovered_index = st.get("hovered_index")
    if hovered_index is not None and hovered_index < len(st["cards"]):
        card = st["cards"][hovered_index]
        _draw_card_tooltip(screen, card, st.get("hovered_index"))
    
    # Instructions
    if st.get("selected_index") is None:
        inst_font = _get_dh_font(18)
        inst_text = "Click a card to select"
        inst_surf = inst_font.render(inst_text, True, (180, 180, 180))
        inst_rect = inst_surf.get_rect(center=(sw // 2, sh - 60))
        screen.blit(inst_surf, inst_rect)


def _get_card_at_position(pos) -> int | None:
    """Get the index of the card at the given position, or None."""
    if _STATE is None:
        return None
    
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    card_width = 280
    card_height = 400
    card_spacing = 40
    total_width = (card_width * 3) + (card_spacing * 2)
    start_x = (sw - total_width) // 2
    card_y = sh // 2 - card_height // 2
    
    for i in range(len(_STATE["cards"])):
        card_x = start_x + i * (card_width + card_spacing)
        card_rect = pygame.Rect(card_x, card_y, card_width, card_height)
        if card_rect.collidepoint(pos):
            return i
    
    return None


def _draw_card_tooltip(screen, card, card_index):
    """Draw a tooltip for the hovered card, similar to shop tooltip style."""
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    
    # Get card data
    card_name = card.get("display_name", card.get("name", "Unknown"))
    card_description = card.get("description", "Unknown blessing")
    
    # Calculate card position for tooltip placement
    card_width = 280
    card_height = 400
    card_spacing = 40
    total_width = (card_width * 3) + (card_spacing * 2)
    start_x = (sw - total_width) // 2
    card_y = sh // 2 - card_height // 2
    card_x = start_x + card_index * (card_width + card_spacing)
    
    # Tooltip font
    tooltip_font = _get_dh_font(18)
    name_font = _get_dh_font(22, bold=True)
    
    # Get mouse position for tooltip placement
    mx, my = pygame.mouse.get_pos()
    
    # Build tooltip text: name on first line, description below
    tooltip_lines = [card_name, card_description]
    
    # Wrap description text if needed
    words = card_description.split()
    max_width = 320
    wrapped_lines = []
    current_line = ""
    
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        if tooltip_font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                wrapped_lines.append(current_line)
            current_line = word
    if current_line:
        wrapped_lines.append(current_line)
    
    # Replace description with wrapped lines
    tooltip_lines = [card_name] + wrapped_lines
    
    # Calculate tooltip size
    tooltip_padding = 14
    name_w = name_font.size(card_name)[0]
    desc_w = max([tooltip_font.size(line)[0] for line in wrapped_lines]) if wrapped_lines else 0
    tooltip_w = max(280, max(name_w, desc_w) + tooltip_padding * 2)
    tooltip_h = name_font.get_height() + (len(wrapped_lines) * (tooltip_font.get_height() + 4)) + tooltip_padding * 2 + 8
    
    # Position tooltip near the card (above or below based on mouse position)
    tooltip_x = card_x + card_width // 2 - tooltip_w // 2
    # Keep tooltip on screen
    tooltip_x = max(20, min(tooltip_x, sw - tooltip_w - 20))
    
    # Place tooltip above card if mouse is in lower half, below if in upper half
    if my > sh // 2:
        tooltip_y = card_y - tooltip_h - 20  # Above card
    else:
        tooltip_y = card_y + card_height + 20  # Below card
    
    # Make sure tooltip stays on screen
    if tooltip_y < 20:
        tooltip_y = card_y + card_height + 20
    if tooltip_y + tooltip_h > sh - 20:
        tooltip_y = card_y - tooltip_h - 20
    
    # Draw tooltip box (matching shop style)
    tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_w, tooltip_h)
    tooltip_bg = pygame.Surface((tooltip_w, tooltip_h), pygame.SRCALPHA)
    # Match textbox style (like shop)
    tooltip_bg.fill((245, 245, 245))
    pygame.draw.rect(tooltip_bg, (0, 0, 0), tooltip_bg.get_rect(), 4, border_radius=8)
    inner_tooltip = tooltip_bg.get_rect().inflate(-8, -8)
    pygame.draw.rect(tooltip_bg, (60, 60, 60), inner_tooltip, 2, border_radius=6)
    screen.blit(tooltip_bg, tooltip_rect.topleft)
    
    # Draw card name (bold, larger)
    name_surf = name_font.render(card_name, True, (16, 16, 16))
    name_x = tooltip_rect.x + tooltip_padding
    name_y = tooltip_rect.y + tooltip_padding
    screen.blit(name_surf, (name_x, name_y))
    
    # Draw description (smaller font, below name)
    text_y = name_y + name_font.get_height() + 8
    for line in wrapped_lines:
        line_surf = tooltip_font.render(line, True, (16, 16, 16))
        screen.blit(line_surf, (name_x, text_y))
        text_y += tooltip_font.get_height() + 4


def _start_card_selection_music(tier: str):
    """Start playing the card selection music based on tier."""
    global _BLESSINGS_MUSIC, _CURSES_MUSIC, _DEMONPACT_MUSIC
    
    music_path = None
    if tier == "Curse":
        music_path = _CURSES_MUSIC
    elif tier == "DemonPact":
        music_path = _DEMONPACT_MUSIC
    else:
        # Common, Rare, Epic, Legendary all use BlessingsSong
        music_path = _BLESSINGS_MUSIC
    
    if music_path and os.path.exists(music_path):
        try:
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.play(-1)  # -1 means loop forever
            print(f"🎵 Started card selection music: {os.path.basename(music_path)}")
        except Exception as e:
            print(f"⚠️ Failed to play card selection music: {e}")
    else:
        print(f"⚠️ Card selection music not found for tier '{tier}'")


def _stop_card_selection_music():
    """Stop the card selection music."""
    try:
        pygame.mixer.music.fadeout(400)
        print(f"🔇 Stopped card selection music")
    except Exception as e:
        print(f"⚠️ Failed to stop card selection music: {e}")


def _apply_selected_buff(gs, card_index: int):
    """Apply the selected buff to the game state."""
    if _STATE is None:
        return
    
    card = _STATE["cards"][card_index]
    
    # Initialize buffs list if needed
    if not hasattr(gs, "active_buffs"):
        gs.active_buffs = []
    if not hasattr(gs, "buffs_history"):
        gs.buffs_history = []
    
    # Create buff entry
    buff_entry = {
        "tier": card["tier"],
        "id": card["id"],
        "name": card["name"],
        "image_path": card["image_path"],
        # "effects": {},  # Will be added later
    }
    
    # Add to active buffs and history
    gs.active_buffs.append(buff_entry)
    gs.buffs_history.append(buff_entry)
    
    print(f"✨ Buff selected: {card['name']} ({card['tier']} tier)")

