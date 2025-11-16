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
from systems import coords

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
_PUNISHMENT_IMG = None

# Sound cache
_BLESSINGS_SOUND = None
_CURSES_SOUND = None
_DEMONPACT_SOUND = None
_PUNISHMENT_SOUND = None

# Music paths
_BLESSINGS_MUSIC = None
_CURSES_MUSIC = None
_DEMONPACT_MUSIC = None
_PUNISHMENT_MUSIC = None

# Message lines cache
_BLESSINGS_MESSAGES = None
_CURSES_MESSAGES = None
_DEMONPACT_MESSAGES = None
_PUNISHMENT_MESSAGES = None

def _load_intro_images():
    """Load the intro images."""
    global _BLESSINGS_IMG, _CURSES_IMG, _DEMONPACT_IMG, _PUNISHMENT_IMG
    
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
    
    if _PUNISHMENT_IMG is None:
        path = os.path.join("Assets", "Blessings", "Punishments.png")
        if os.path.exists(path):
            try:
                _PUNISHMENT_IMG = pygame.image.load(path).convert_alpha()
                print(f"✅ Loaded Punishments.png: {_PUNISHMENT_IMG.get_size()}")
            except Exception as e:
                print(f"⚠️ Failed to load Punishments.png: {e}")
        else:
            print(f"⚠️ Punishments.png not found at: {path}")


def _load_intro_sounds():
    """Load the intro sound files."""
    global _BLESSINGS_SOUND, _CURSES_SOUND, _DEMONPACT_SOUND, _PUNISHMENT_SOUND
    
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
    
    if _PUNISHMENT_SOUND is None:
        path = os.path.join("Assets", "Blessings", "Punishments.mp3")
        if os.path.exists(path):
            try:
                _PUNISHMENT_SOUND = pygame.mixer.Sound(path)
                print(f"✅ Loaded Punishments.mp3")
            except Exception as e:
                print(f"⚠️ Failed to load Punishments.mp3: {e}")
        else:
            print(f"⚠️ Punishments.mp3 not found at: {path}")


def _load_card_selection_music():
    """Load the card selection music files."""
    global _BLESSINGS_MUSIC, _CURSES_MUSIC, _DEMONPACT_MUSIC, _PUNISHMENT_MUSIC
    
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
    
    if _PUNISHMENT_MUSIC is None:
        path = os.path.join("Assets", "Blessings", "PunishmentsSong.mp3")
        if os.path.exists(path):
            _PUNISHMENT_MUSIC = path
            print(f"✅ Found PunishmentsSong.mp3")
        else:
            print(f"⚠️ PunishmentsSong.mp3 not found at: {path}")


def _load_message_lines():
    """Load message lines from text files."""
    global _BLESSINGS_MESSAGES, _CURSES_MESSAGES, _DEMONPACT_MESSAGES, _PUNISHMENT_MESSAGES
    
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
    
    if _PUNISHMENT_MESSAGES is None:
        path = os.path.join("Assets", "Blessings", "Punishments.txt")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                _PUNISHMENT_MESSAGES = lines
                print(f"✅ Loaded {len(lines)} punishment messages")
            except Exception as e:
                print(f"⚠️ Failed to load Punishments.txt: {e}")
                _PUNISHMENT_MESSAGES = ["You are punished"]  # Fallback
        else:
            print(f"⚠️ Punishments.txt not found at: {path}")
            _PUNISHMENT_MESSAGES = ["You are punished"]  # Fallback


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
    elif tier == "Punishment":
        if _PUNISHMENT_MESSAGES and len(_PUNISHMENT_MESSAGES) > 0:
            return random.choice(_PUNISHMENT_MESSAGES)
        return "You are punished"  # Fallback
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
    
    # Generate buff selection (pass gs to exclude "once per run" cards)
    selection = buffs.generate_buff_selection(gs)
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
    elif tier == "Punishment":
        intro_image = _PUNISHMENT_IMG
        intro_sound = _PUNISHMENT_SOUND
        message = _get_random_message(tier)
        animation_duration = 8.0  # Punishments.mp3 is 8 seconds
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
    
    # Handle buff application states first (they take priority)
    application = _STATE.get("buff_application")
    if application:
        step = application.get("step")
        
        # Forward events to party_manager if it's open (for vessel selection)
        if step == "vessel_selection":
            from screens import party_manager
            if party_manager.is_open():
                if party_manager.handle_event(event, gs):
                    return True
            return False  # Allow other input to pass through
        
        # Handle stat selection (for single vessel)
        elif step == "stat_selection":
            from screens import vessel_stat_selector
            if vessel_stat_selector.is_active():
                if vessel_stat_selector.handle_event(event, gs):
                    return True
        
        # Handle stat selection (for all vessels)
        elif step == "stat_all_selection":
            from screens import vessel_stat_selector
            if vessel_stat_selector.is_active():
                if vessel_stat_selector.handle_event(event, gs):
                    return True
        
        # Handle move selection
        elif step == "move_selection":
            from screens import vessel_move_selector
            if vessel_move_selector.is_active():
                if vessel_move_selector.handle_event(event, gs):
                    return True
        
        # Handle result card
        elif step == "result_card":
            from systems import buff_applicator
            if buff_applicator.is_result_card_active():
                # Dismiss result card on click/enter
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                    buff_applicator.dismiss_result_card()
                    try:
                        audio_sys.play_click(audio_sys.get_global_bank())
                    except Exception:
                        pass
                    return True
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    buff_applicator.dismiss_result_card()
                    try:
                        audio_sys.play_click(audio_sys.get_global_bank())
                    except Exception:
                        pass
                    return True
                return True  # Block other input while result card is showing
    
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
                # Apply the buff (don't set phase to "done" yet - buff application may continue)
                _apply_selected_buff(gs, clicked)
                # Only set to "done" if buff application is complete (checked in update)
                return True
    
    return False


def update(dt, gs):
    """Update animation and state."""
    global _STATE, _ACTIVE
    
    if not _ACTIVE or _STATE is None:
        return
    
    # Check buff application state
    application = _STATE.get("buff_application")
    if application:
        step = application.get("step")
        
        # Handle stat selection completion for all vessels
        if step == "stat_all_selection":
            from screens import vessel_stat_selector
            if vessel_stat_selector.is_active():
                # Check if a stat was selected
                selected = vessel_stat_selector.get_selected_stat()
                if selected is not None:
                    vessel_idx, stat_name = selected
                    # For "all vessels" mode, vessel_idx will be -1
                    if vessel_idx == -1:
                        # Apply stat bonus to all vessels
                        print(f"🔔 Applying {stat_name} +1 to all vessels")
                        from systems import buff_applicator as ba
                        result = application.get("result", {})
                        stat_bonus = result.get("stat_bonus", 1)
                        if ba.apply_stat_bonus_to_all_vessels(gs, stat_name, stat_bonus):
                            # Show result card
                            ba.show_result_card(
                                f"+{stat_bonus} {stat_name}",
                                f"Applied to all vessels"
                            )
                            application["step"] = "result_card"
                            print(f"✅ Stat bonus applied to all vessels, step set to result_card")
                        else:
                            print(f"⚠️ Failed to apply stat bonus to all vessels")
                            application["step"] = "complete"
                        # Close stat selector
                        vessel_stat_selector.close()
                    else:
                        # This shouldn't happen in "all vessels" mode, but handle it
                        print(f"⚠️ Unexpected vessel_idx {vessel_idx} in stat_all_selection mode")
                        vessel_stat_selector.close()
                        application["step"] = "complete"
            else:
                # Selector was closed (maybe by ESC) - mark complete
                application["step"] = "complete"
        
        # Handle stat selection completion
        if step == "stat_selection":
            from screens import vessel_stat_selector
            if vessel_stat_selector.is_active():
                # Check if a stat was selected
                selected = vessel_stat_selector.get_selected_stat()
                if selected:
                    vessel_idx, stat_name = selected
                    result = application.get("result", {})
                    curse_phase = application.get("curse_phase")
                    
                    from systems import buff_applicator as ba
                    
                    # Check if this is a curse with multiple phases
                    if curse_phase == "plus":
                        # First phase: apply the plus stat
                        stat_plus = result.get("stat_plus", 1)
                        ba.apply_stat_bonus(gs, vessel_idx, stat_name, stat_plus)
                        print(f"✅ Stat {stat_name} +{stat_plus} applied to vessel {vessel_idx}")
                        
                        # Check which curse this is
                        blessing_name = result.get("blessing", "")
                        if blessing_name == "Curse1":
                            # Curse1: Now need to select stat for -1
                            application["curse_phase"] = "minus"
                            application["curse_plus_stat"] = stat_name
                            stat_minus = result.get("stat_minus", 1)
                            # Start stat selection for minus (negative bonus)
                            if vessel_stat_selector.start_stat_selection(gs, vessel_idx, -stat_minus, allow_ac=False):
                                print(f"✅ Stat selection started for -{stat_minus}")
                            else:
                                print(f"⚠️ Failed to start stat selection for minus")
                                vessel_stat_selector.close()
                                application["step"] = "complete"
                        
                        elif blessing_name == "Curse2":
                            # Curse2: Now apply random stat -1
                            stat_minus = result.get("stat_minus", 1)
                            success, random_stat = ba.apply_random_stat_penalty(gs, vessel_idx, stat_minus)
                            if success:
                                # Show result card
                                ba.show_result_card(
                                    f"{stat_name} +{stat_plus}",
                                    f"Random stat {random_stat} -{stat_minus}"
                                )
                                application["step"] = "result_card"
                                print(f"✅ Random stat {random_stat} -{stat_minus} applied")
                            else:
                                print(f"⚠️ Failed to apply random stat penalty")
                                vessel_stat_selector.close()
                                application["step"] = "complete"
                        
                        elif blessing_name == "Curse5":
                            # Curse5: Now roll HP and subtract
                            dice = result.get("dice", (1, 12))
                            from rolling.roller import roll_dice
                            total, rolls = roll_dice(dice[0], dice[1])
                            print(f"🔔 Rolled {dice[0]}d{dice[1]}: {rolls} = {total} HP penalty")
                            
                            # Apply HP penalty
                            ba.apply_hp_penalty(gs, vessel_idx, total)
                            
                            # Show result card
                            ba.show_result_card(
                                f"{stat_name} +{stat_plus}",
                                f"Rolled {dice[0]}d{dice[1]}: -{total} HP",
                                play_dice_sound=True
                            )
                            application["step"] = "result_card"
                            vessel_stat_selector.close()
                            print(f"✅ HP penalty applied, step set to result_card")
                        
                        else:
                            # Normal stat selection (not a curse)
                            vessel_stat_selector.close()
                            application["step"] = "complete"
                    
                    elif curse_phase == "minus":
                        # Second phase: apply the minus stat
                        stat_minus = result.get("stat_minus", 1)
                        # The stat_bonus from selector is already negative, so apply it directly
                        # But we need to get the actual bonus value (which is negative)
                        stat_bonus = result.get("stat_bonus", -stat_minus)
                        if stat_bonus > 0:
                            stat_bonus = -stat_bonus  # Ensure it's negative
                        
                        ba.apply_stat_bonus(gs, vessel_idx, stat_name, stat_bonus)
                        print(f"✅ Stat {stat_name} {stat_bonus} applied to vessel {vessel_idx}")
                        
                        # Check which curse this is
                        blessing_name = result.get("blessing", "")
                        if blessing_name == "Curse1":
                            # Show result card with both changes
                            plus_stat = application.get("curse_plus_stat", "?")
                            stat_plus = result.get("stat_plus", 1)
                            ba.show_result_card(
                                f"{plus_stat} +{stat_plus}",
                                f"{stat_name} -{stat_minus}"
                            )
                            application["step"] = "result_card"
                            vessel_stat_selector.close()
                            print(f"✅ Curse1 complete, showing result card")
                        
                        elif blessing_name == "Curse4":
                            # Show result card with random stat +1 and chosen stat -1
                            random_stat = application.get("random_stat_plus", "?")
                            stat_plus = result.get("stat_plus", 1)
                            ba.show_result_card(
                                f"Random {random_stat} +{stat_plus}",
                                f"{stat_name} -{stat_minus}"
                            )
                            application["step"] = "result_card"
                            vessel_stat_selector.close()
                            print(f"✅ Curse4 complete, showing result card")
                        
                        else:
                            vessel_stat_selector.close()
                            application["step"] = "complete"
                    
                    else:
                        # Normal stat selection (not a curse with phases)
                        stat_bonus = result.get("stat_bonus", 1)
                        max_stat = result.get("max_stat")
                        if stat_name == "AC":
                            ba.apply_ac_bonus(gs, vessel_idx, stat_bonus)
                        else:
                            ba.apply_stat_bonus(gs, vessel_idx, stat_name, stat_bonus, max_stat)
                        print(f"✅ Stat {stat_name} applied to vessel {vessel_idx}")
                        vessel_stat_selector.close()
                        application["step"] = "complete"
            else:
                # Selector was closed (maybe by ESC) - mark complete
                application["step"] = "complete"
        
        # Handle move selection completion
        elif step == "move_selection":
            from screens import vessel_move_selector
            if vessel_move_selector.is_active():
                # Check if a move was selected
                selected = vessel_move_selector.get_selected_move()
                if selected:
                    vessel_idx, move_id = selected
                    result = application.get("result", {})
                    pp_amount = result.get("pp_amount", 2)
                    
                    from systems import buff_applicator as ba
                    ba.apply_pp_bonus(gs, vessel_idx, move_id, pp_amount)
                    print(f"✅ PP {pp_amount} applied to move {move_id} for vessel {vessel_idx}")
                    
                    # Close selector and mark complete
                    vessel_move_selector.close()
                    application["step"] = "complete"
            else:
                # Selector was closed (maybe by ESC) - mark complete
                application["step"] = "complete"
        
        # Handle result card
        elif step == "result_card":
            from systems import buff_applicator
            if not buff_applicator.is_result_card_active():
                # Result card was dismissed
                buff_applicator.clear_result_card()
                application["step"] = "complete"
                print(f"✅ Result card dismissed, step set to complete")
        
        # Check if application is complete (only do this once)
        if application.get("step") == "complete" and not application.get("completed", False):
            application["completed"] = True  # Mark as completed to prevent repeated execution
            print(f"✅ Buff application complete, closing party manager and marking done")
            # Stop card selection music
            _stop_card_selection_music()
            # Close party manager if open
            from screens import party_manager
            if party_manager.is_open():
                party_manager.close()
            # Mark buff popup as done
            _STATE["phase"] = "done"
    
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


def draw(screen, dt, gs=None):
    """Draw the buff popup."""
    global _STATE
    
    if not _ACTIVE or _STATE is None:
        return
    
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    phase = _STATE.get("phase", "intro")
    
    # Draw buff application UI (stat selector, move selector, result card)
    # This takes priority - if buff application is active, don't draw cards/intro
    application = _STATE.get("buff_application")
    if application:
        step = application.get("step")
        
        # Draw party manager if open (for vessel selection)
        if step == "vessel_selection":
            from screens import party_manager
            if party_manager.is_open() and gs is not None:
                party_manager.draw(screen, gs, dt)
                # Don't draw cards/intro when party manager is open for buff application
                return
        
        # Draw stat selector (for single vessel)
        elif step == "stat_selection":
            from screens import vessel_stat_selector
            if vessel_stat_selector.is_active():
                vessel_stat_selector.draw(screen, dt)
                return  # Don't draw other UI when stat selector is active
        
        # Draw stat selector (for all vessels)
        elif step == "stat_all_selection":
            from screens import vessel_stat_selector
            if vessel_stat_selector.is_active():
                vessel_stat_selector.draw(screen, dt)
                return  # Don't draw other UI when stat selector is active
        
        # Draw move selector
        elif step == "move_selection":
            from screens import vessel_move_selector
            if vessel_move_selector.is_active():
                vessel_move_selector.draw(screen, dt)
                return  # Don't draw other UI when move selector is active
        
        # Draw result card (must be drawn last so it appears on top)
        if step == "result_card":
            from systems import buff_applicator
            if buff_applicator.is_result_card_active():
                _draw_result_card(screen, dt)
                return  # Block other UI when result card is showing
            else:
                # Result card was dismissed, but step might not be updated yet
                # Don't draw anything, let update loop handle the transition
                return
        
        # If we get here, buff application is active but no UI to draw yet
        # Don't draw cards/intro
        return
    
    # Only draw intro/cards if buff application is not active
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
    
    # Draw cards (only if no buff application is active)
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
    elif tier == "Punishment":
        title_text = "Choose a Punishment"
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
    num_cards = len(st["cards"])
    
    # Calculate positioning based on number of cards
    if num_cards == 1:
        # Center single card
        total_width = card_width
        start_x = (sw - total_width) // 2
    else:
        # Multiple cards: space them out
        total_width = (card_width * num_cards) + (card_spacing * (num_cards - 1))
        start_x = (sw - total_width) // 2
    
    card_y = sh // 2 - card_height // 2
    
    for i, card in enumerate(st["cards"]):
        if num_cards == 1:
            card_x = start_x
        else:
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
    num_cards = len(_STATE["cards"])
    
    # Calculate positioning based on number of cards
    if num_cards == 1:
        # Center single card
        total_width = card_width
        start_x = (sw - total_width) // 2
    else:
        # Multiple cards: space them out
        total_width = (card_width * num_cards) + (card_spacing * (num_cards - 1))
        start_x = (sw - total_width) // 2
    
    card_y = sh // 2 - card_height // 2
    
    for i in range(num_cards):
        if num_cards == 1:
            card_x = start_x
        else:
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
    
    # Calculate card position for tooltip placement (must match the drawing logic)
    card_width = 280
    card_height = 400
    card_spacing = 40
    num_cards = len(_STATE["cards"]) if _STATE else 1
    
    # Calculate positioning based on number of cards (same logic as drawing code)
    if num_cards == 1:
        # Center single card
        total_width = card_width
        start_x = (sw - total_width) // 2
        card_x = start_x
    else:
        # Multiple cards: space them out
        total_width = (card_width * num_cards) + (card_spacing * (num_cards - 1))
        start_x = (sw - total_width) // 2
        card_x = start_x + card_index * (card_width + card_spacing)
    
    card_y = sh // 2 - card_height // 2
    
    # Tooltip font
    tooltip_font = _get_dh_font(18)
    name_font = _get_dh_font(22, bold=True)
    
    # Get mouse position for tooltip placement - Convert to logical coordinates for QHD support
    screen_mx, screen_my = pygame.mouse.get_pos()
    mx, my = coords.screen_to_logical((screen_mx, screen_my))
    
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
    global _BLESSINGS_MUSIC, _CURSES_MUSIC, _DEMONPACT_MUSIC, _PUNISHMENT_MUSIC
    
    music_path = None
    if tier == "Curse":
        music_path = _CURSES_MUSIC
    elif tier == "DemonPact":
        music_path = _DEMONPACT_MUSIC
    elif tier == "Punishment":
        music_path = _PUNISHMENT_MUSIC
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
        # Removed debug print to prevent console spam
    except Exception as e:
        print(f"⚠️ Failed to stop card selection music: {e}")


def _draw_result_card(screen: pygame.Surface, dt: float):
    """Draw the result card (for dice rolls)."""
    from systems import buff_applicator
    result_card = buff_applicator.get_result_card()
    if not result_card or not result_card.get("active"):
        return
    
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)
    
    # Box styling (matches heal textbox)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)
    
    # Text rendering
    title = result_card.get("title", "")
    subtitle = result_card.get("subtitle", "")
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


def _apply_selected_buff(gs, card_index: int):
    """Apply the selected buff to the game state."""
    if _STATE is None:
        return
    
    card = _STATE["cards"][card_index]
    card_name = card["name"]
    
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
    }
    
    # Add to active buffs and history
    gs.active_buffs.append(buff_entry)
    gs.buffs_history.append(buff_entry)
    
    print(f"✨ Buff selected: {card['name']} ({card['tier']} tier)")
    
    # Apply the blessing based on card name and tier
    from systems import buff_applicator
    from systems import buffs
    
    card_data = buffs.get_card_data(card_name)
    tier = _STATE.get("tier", "Common")
    
    # Route to appropriate blessing function based on tier
    if tier == "Common":
        result = buff_applicator.apply_common_blessing(gs, card_name, card_data)
    elif tier == "Rare":
        result = buff_applicator.apply_rare_blessing(gs, card_name, card_data)
    elif tier == "Epic":
        result = buff_applicator.apply_epic_blessing(gs, card_name, card_data)
    elif tier == "Legendary":
        result = buff_applicator.apply_legendary_blessing(gs, card_name, card_data)
    elif tier == "DemonPact":
        result = buff_applicator.apply_demonpact_blessing(gs, card_name, card_data)
    elif tier == "Curse":
        result = buff_applicator.apply_curse_blessing(gs, card_name, card_data)
    elif tier == "Punishment":
        result = buff_applicator.apply_punishment_blessing(gs, card_name, card_data)
    else:
        result = {"action": "none"}
    
    # Store application state
    _STATE["buff_application"] = {
        "result": result,
        "card_name": card_name,
        "card_data": card_data,
    }
    
    # Handle different action types based on tier
    action = result.get("action", "none")
    
    # Punishment-specific handling
    if tier == "Punishment":
        print(f"🔔 Processing punishment action: {action} for card {card_name}")
        
        if action == "complete":
            # Direct completion - done immediately
            print(f"✅ Punishment applied: {result.get('message', '')}")
            _STATE["buff_application"]["step"] = "complete"
            return
        
        elif action == "gold_deduction":
            # Punishment1: Deduct gold and show result card
            print(f"🔔 Deducting gold (Punishment1)")
            from systems import buff_applicator as ba
            gold_amount = result.get("gold_amount", 10)
            success, actual_deduction = ba.apply_gold_deduction(gs, gold_amount)
            if success:
                # Show result card with custom message
                ba.show_result_card(
                    f"-{actual_deduction} gold",
                    f"You pay Tribute to the Oathbreaker Paladin and pay him {actual_deduction} Gold Pieces"
                )
                _STATE["buff_application"]["step"] = "result_card"
                print(f"✅ Gold deducted, step set to result_card")
            else:
                print(f"⚠️ Failed to deduct gold")
                _STATE["buff_application"]["step"] = "complete"
        
        elif action == "stat_random_penalty_selection":
            # Punishment2: Choose vessel, then apply -2 to 2 random stats
            _STATE["buff_application"]["step"] = "vessel_selection"
            _start_vessel_selection(gs, "stat_random_penalty_selection")
        
        elif action == "ac_penalty_random_vessel":
            # Punishment3: Apply -1 AC to random vessel immediately
            print(f"🔔 Applying AC penalty to random vessel (Punishment3)")
            from systems import buff_applicator as ba
            ac_penalty = result.get("ac_penalty", 1)
            success, vessel_idx, vessel_name = ba.apply_ac_penalty_to_random_vessel(gs, ac_penalty)
            if success and vessel_idx is not None:
                # Get display name
                from systems.name_generator import generate_vessel_name
                display_name = generate_vessel_name(vessel_name) if vessel_name else "Vessel"
                
                # Show result card
                ba.show_result_card(
                    f"{display_name}",
                    f"Lost {ac_penalty} AC"
                )
                _STATE["buff_application"]["step"] = "result_card"
                print(f"✅ AC penalty applied to {display_name}, step set to result_card")
            else:
                print(f"⚠️ Failed to apply AC penalty to random vessel")
                _STATE["buff_application"]["step"] = "complete"
        
        elif action == "hp_roll_penalty":
            # Punishment4: Choose vessel, then roll 1d6 and apply HP penalty
            _STATE["buff_application"]["step"] = "vessel_selection"
            _start_vessel_selection(gs, "hp_roll_penalty")
        
        elif action == "remove_vessel":
            # Punishment5: Choose vessel, then remove it from party
            _STATE["buff_application"]["step"] = "vessel_selection"
            _start_vessel_selection(gs, "remove_vessel")
        
        else:
            # Unknown punishment action
            if action != "none":
                print(f"⚠️ Unknown punishment action: {action}")
            _STATE["buff_application"]["step"] = "complete"
        
        return  # Return early for punishments
    
    # Handle different action types (for non-punishment tiers)
    print(f"🔔 Processing blessing action: {action} for card {card_name}")
    
    if action == "complete":
        # Direct completion - done immediately
        print(f"✅ Blessing applied: {result.get('message', '')}")
        _STATE["buff_application"]["step"] = "complete"
        return
    
    elif action == "inventory_result":
        # Inventory addition - show result card
        print(f"✅ Inventory blessing applied: {result.get('message', '')}")
        _STATE["buff_application"]["step"] = "result_card"
        _STATE["buff_application"]["blessing_type"] = "inventory_result"
        return
    
    elif action == "stat_selection":
        # Need vessel selection, then stat selection
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "stat_selection")
    
    elif action == "hp_roll":
        # Need vessel selection, then roll dice
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "hp_roll")
    
    elif action == "damage_reduction_roll":
        # Need vessel selection, then roll dice
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "damage_reduction_roll")
    
    elif action == "xp_roll":
        # Need vessel selection, then roll dice
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "xp_roll")
    
    elif action == "pp_bonus":
        # Need vessel selection, then move selection
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "pp_bonus")
    
    elif action == "ac_bonus":
        # Need vessel selection only (AC bonus applied directly)
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "ac_bonus")
    
    elif action == "ac_all":
        # Apply AC bonus to all vessels directly (no vessel selection needed)
        print(f"🔔 Applying AC bonus to all vessels")
        from systems import buff_applicator as ba
        ac_amount = result.get("ac_amount", 1)
        success, vessels_updated = ba.apply_ac_bonus_to_all_vessels(gs, ac_amount)
        if success:
            # Show result card
            ba.show_result_card(
                f"+{ac_amount} AC",
                f"Applied to {vessels_updated} vessel(s)"
            )
            _STATE["buff_application"]["step"] = "result_card"
            print(f"✅ AC bonus applied to {vessels_updated} vessel(s), showing result card")
        else:
            print(f"⚠️ Failed to apply AC bonus to all vessels")
            _STATE["buff_application"]["step"] = "complete"
    
    elif action == "ac_and_hp_roll":
        # Need vessel selection, then roll dice for HP, then apply both AC and HP
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "ac_and_hp_roll")
    
    elif action == "hp_all_roll":
        # Roll dice immediately (applies to all vessels)
        dice = result.get("dice", (1, 4))
        _roll_dice_for_all_vessels_hp(gs, dice, result.get("blessing", "Epic3"))
    
    elif action == "ac_all_hp_roll_minus":
        # Curse3: Apply AC to all vessels, then roll dice and apply HP penalty to all
        print(f"🔔 Applying AC to all vessels, then rolling HP penalty (Curse3)")
        from systems import buff_applicator as ba
        ac_amount = result.get("ac_amount", 1)
        dice = result.get("dice", (1, 8))
        
        # Apply AC bonus to all vessels first
        success, vessels_updated = ba.apply_ac_bonus_to_all_vessels(gs, ac_amount)
        if success:
            print(f"✅ Applied +{ac_amount} AC to {vessels_updated} vessel(s)")
        
        # Roll dice and apply HP penalty to all vessels
        from rolling.roller import roll_dice
        total, rolls = roll_dice(dice[0], dice[1])
        print(f"🔔 Rolled {dice[0]}d{dice[1]}: {rolls} = {total} HP penalty")
        
        # Apply HP penalty to all vessels (negative value)
        ba.apply_hp_to_all_vessels(gs, -total)
        
        # Show result card
        ba.show_result_card(
            f"+{ac_amount} AC to all",
            f"Rolled {dice[0]}d{dice[1]}: -{total} HP to all vessels",
            play_dice_sound=True
        )
        
        _STATE["buff_application"]["step"] = "result_card"
        print(f"✅ Curse3 applied, step set to result_card")
    
    elif action == "damage_reduction_all_roll":
        # Roll dice immediately (applies damage reduction to all vessels)
        dice = result.get("dice", (1, 6))
        _roll_dice_for_all_vessels_damage_reduction(gs, dice, result.get("blessing", "DemonPact1"))
    
    elif action == "permanent_damage_all_roll":
        # Roll dice immediately (applies permanent damage bonus to all vessels)
        dice = result.get("dice", (1, 6))
        _roll_dice_for_all_vessels_permanent_damage(gs, dice, result.get("blessing", "DemonPact4"))
    
    elif action == "result_card":
        # Result card already shown (e.g., Legendary5 rolled dice)
        # Just set step to result_card so update loop can handle dismissal
        _STATE["buff_application"]["step"] = "result_card"
        print(f"✅ Result card shown, step set to result_card")
    
    elif action == "stat_all_selection":
        # Need stat selection (for all vessels, no vessel selection needed)
        _STATE["buff_application"]["step"] = "stat_all_selection"
        _start_stat_selection_for_all_vessels(gs, result.get("stat_bonus", 1))
    
    elif action == "permanent_damage":
        # Need vessel selection only
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "permanent_damage")
    
    elif action == "stat_plus_minus_selection":
        # Curse1: Choose vessel, choose stat for +1, choose stat for -1
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "stat_plus_minus_selection")
    
    elif action == "stat_plus_random_minus":
        # Curse2: Choose vessel, choose stat for +2, random stat gets -1
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "stat_plus_random_minus")
    
    elif action == "stat_random_plus_minus_selection":
        # Curse4: Choose vessel, random stat gets +1, choose stat for -1
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "stat_random_plus_minus_selection")
    
    elif action == "stat_plus_hp_roll_minus":
        # Curse5: Choose vessel, choose stat for +2, roll 1d12 HP and subtract
        _STATE["buff_application"]["step"] = "vessel_selection"
        _start_vessel_selection(gs, "stat_plus_hp_roll_minus")
    
    elif action == "random_stat_random_vessel":
        # Apply immediately (random vessel, random stats)
        print(f"🔔 Applying random stats to random vessel")
        from systems import buff_applicator as ba
        stat_bonus = result.get("stat_bonus", 1)
        num_stats = result.get("num_stats", 2)
        success, vessel_idx, modified_stats = ba.apply_random_stat_to_random_vessel(gs, stat_bonus, num_stats)
        
        if success and vessel_idx is not None:
            # Get vessel name
            from systems.name_generator import generate_vessel_name
            names = getattr(gs, "party_slots_names", None) or [None] * 6
            vessel_name = names[vessel_idx] if vessel_idx < len(names) else None
            display_name = generate_vessel_name(vessel_name) if vessel_name else "Vessel"
            
            # Format stats text
            stats_text = ", ".join([f"{stat} +{stat_bonus}" for stat, _ in modified_stats])
            
            # Show result card
            buff_applicator.show_result_card(
                f"{display_name}",
                f"Gained: {stats_text}"
            )
            print(f"✅ Random stats applied: {display_name} gained {stats_text}")
            
            _STATE["buff_application"]["step"] = "result_card"
        else:
            print(f"⚠️ Failed to apply random stats")
            _STATE["buff_application"]["step"] = "complete"
    
    else:
        print(f"⚠️ Unknown blessing action: {action}")


def _start_stat_selection_for_all_vessels(gs, stat_bonus: int):
    """Start stat selection for all vessels (no vessel selection needed)."""
    from screens import vessel_stat_selector
    if vessel_stat_selector.start_stat_selection_for_all_vessels(gs, stat_bonus):
        print(f"✅ Stat selection for all vessels started")
    else:
        print(f"⚠️ Failed to start stat selection for all vessels")


def _start_vessel_selection(gs, blessing_type: str):
    """Start vessel selection in party manager."""
    from screens import party_manager
    from systems import buff_applicator
    
    # Store blessing_type in state so callback can access it
    if "buff_application" not in _STATE:
        _STATE["buff_application"] = {}
    _STATE["buff_application"]["blessing_type"] = blessing_type
    
    def on_vessel_selected(vessel_idx: int):
        """Callback when vessel is selected."""
        print(f"🔔 Vessel selected: {vessel_idx}, blessing_type: {blessing_type}")
        
        # Get application state (might have changed, so get fresh)
        application = _STATE.get("buff_application", {})
        result = application.get("result", {})
        blessing_type_local = application.get("blessing_type", blessing_type)
        
        print(f"🔔 Processing blessing: {blessing_type_local}, result: {result}")
        
        if blessing_type_local == "stat_selection":
            # Start stat selection
            print(f"🔔 Starting stat selection for vessel {vessel_idx}")
            from screens import vessel_stat_selector
            stat_bonus = result.get("stat_bonus", 1)
            max_stat = result.get("max_stat")
            # For "+1 stat" blessings, only allow D&D stats (not AC, HP, XP)
            # Check if this is a "stat" blessing (not AC-specific like Epic1)
            blessing_name = result.get("blessing", "")
            allow_ac = blessing_name not in ("Common1",)  # Common1 is "+1 stat" so no AC
            if vessel_stat_selector.start_stat_selection(gs, vessel_idx, stat_bonus, max_stat, allow_ac=allow_ac):
                _STATE["buff_application"]["step"] = "stat_selection"
                _STATE["buff_application"]["vessel_idx"] = vessel_idx
                print(f"✅ Stat selection started (allow_ac={allow_ac})")
            else:
                print(f"⚠️ Failed to start stat selection")
        
        elif blessing_type_local == "hp_roll":
            # Roll dice and apply HP
            print(f"🔔 Rolling HP for vessel {vessel_idx}")
            from rolling.roller import roll_dice
            dice = result.get("dice", (1, 4))
            total, rolls = roll_dice(dice[0], dice[1])
            print(f"🔔 Rolled {dice[0]}d{dice[1]}: {rolls} = {total}")
            
            # Show result card
            buff_applicator.show_result_card(
                f"Rolled {dice[0]}d{dice[1]}",
                f"Result: {total} HP",
                play_dice_sound=True
            )
            print(f"✅ Result card shown: {total} HP")
            
            # Apply HP
            from systems import buff_applicator as ba
            ba.apply_hp_bonus(gs, vessel_idx, total)
            
            _STATE["buff_application"]["step"] = "result_card"
            _STATE["buff_application"]["vessel_idx"] = vessel_idx
            print(f"✅ HP applied, step set to result_card")
        
        elif blessing_type_local == "xp_roll":
            # Roll dice and apply XP
            print(f"🔔 Rolling XP for vessel {vessel_idx}")
            from rolling.roller import roll_dice
            dice = result.get("dice", (1, 6))
            total, rolls = roll_dice(dice[0], dice[1])
            print(f"🔔 Rolled {dice[0]}d{dice[1]}: {rolls} = {total}")
            
            # Show result card
            buff_applicator.show_result_card(
                f"Rolled {dice[0]}d{dice[1]}",
                f"Result: {total} XP",
                play_dice_sound=True
            )
            print(f"✅ Result card shown: {total} XP")
            
            # Apply XP
            from systems import buff_applicator as ba
            ba.apply_xp_bonus(gs, vessel_idx, total)
            
            _STATE["buff_application"]["step"] = "result_card"
            _STATE["buff_application"]["vessel_idx"] = vessel_idx
            print(f"✅ XP applied, step set to result_card")
        
        elif blessing_type_local == "damage_reduction_roll":
            # Roll dice and apply damage reduction
            print(f"🔔 Rolling damage reduction for vessel {vessel_idx}")
            from rolling.roller import roll_dice
            dice = result.get("dice", (1, 2))
            total, rolls = roll_dice(dice[0], dice[1])
            print(f"🔔 Rolled {dice[0]}d{dice[1]}: {rolls} = {total}")
            
            # Show result card
            buff_applicator.show_result_card(
                f"Rolled {dice[0]}d{dice[1]}",
                f"Result: -{total} damage reduction",
                play_dice_sound=True
            )
            print(f"✅ Result card shown: -{total} damage reduction")
            
            # Apply damage reduction
            from systems import buff_applicator as ba
            ba.apply_damage_reduction(gs, vessel_idx, total)
            
            _STATE["buff_application"]["step"] = "result_card"
            _STATE["buff_application"]["vessel_idx"] = vessel_idx
            print(f"✅ Damage reduction applied, step set to result_card")
        
        elif blessing_type_local == "pp_bonus":
            # Start move selection
            print(f"🔔 Starting move selection for vessel {vessel_idx}")
            from screens import vessel_move_selector
            pp_amount = result.get("pp_amount", 2)
            if vessel_move_selector.start_move_selection(gs, vessel_idx, pp_amount):
                _STATE["buff_application"]["step"] = "move_selection"
                _STATE["buff_application"]["vessel_idx"] = vessel_idx
                print(f"✅ Move selection started")
            else:
                print(f"⚠️ Failed to start move selection")
        
        elif blessing_type_local == "permanent_damage":
            # Apply permanent damage directly
            print(f"🔔 Applying permanent damage to vessel {vessel_idx}")
            from systems import buff_applicator as ba
            damage_bonus = result.get("damage_bonus", 1)
            ba.apply_permanent_damage_bonus(gs, vessel_idx, damage_bonus)
            _STATE["buff_application"]["step"] = "complete"
            print(f"✅ Permanent damage applied, step set to complete")
        
        elif blessing_type_local == "ac_bonus":
            # Apply AC bonus directly
            print(f"🔔 Applying AC bonus to vessel {vessel_idx}")
            from systems import buff_applicator as ba
            ac_amount = result.get("ac_amount", 1)
            ba.apply_ac_bonus(gs, vessel_idx, ac_amount)
            _STATE["buff_application"]["step"] = "complete"
            print(f"✅ AC bonus applied, step set to complete")
        
        elif blessing_type_local == "ac_and_hp_roll":
            # Roll dice for HP, then apply both AC and HP to the selected vessel
            print(f"🔔 Rolling HP and applying AC for vessel {vessel_idx}")
            from rolling.roller import roll_dice
            from systems import buff_applicator as ba
            dice = result.get("dice", (1, 10))
            total, rolls = roll_dice(dice[0], dice[1])
            print(f"🔔 Rolled {dice[0]}d{dice[1]}: {rolls} = {total} HP")
            
            # Apply AC bonus first
            ac_amount = result.get("ac_amount", 1)
            ba.apply_ac_bonus(gs, vessel_idx, ac_amount)
            print(f"✅ Applied +{ac_amount} AC to vessel {vessel_idx}")
            
            # Apply HP bonus
            ba.apply_hp_bonus(gs, vessel_idx, total)
            print(f"✅ Applied +{total} HP to vessel {vessel_idx}")
            
            # Show result card with both bonuses
            ba.show_result_card(
                f"Rolled {dice[0]}d{dice[1]}",
                f"Result: {total} HP and +{ac_amount} AC",
                play_dice_sound=True
            )
            
            _STATE["buff_application"]["step"] = "result_card"
            _STATE["buff_application"]["vessel_idx"] = vessel_idx
            print(f"✅ AC and HP applied, step set to result_card")
        
        elif blessing_type_local == "stat_plus_minus_selection":
            # Curse1: Choose stat for +1, then choose stat for -1
            print(f"🔔 Starting stat selection for +1 (Curse1)")
            from screens import vessel_stat_selector
            stat_plus = result.get("stat_plus", 1)
            # Store vessel_idx and that we need to do minus selection next
            _STATE["buff_application"]["vessel_idx"] = vessel_idx
            _STATE["buff_application"]["curse_phase"] = "plus"  # Track which phase we're in
            if vessel_stat_selector.start_stat_selection(gs, vessel_idx, stat_plus, allow_ac=False):
                _STATE["buff_application"]["step"] = "stat_selection"
                print(f"✅ Stat selection started for +{stat_plus}")
            else:
                print(f"⚠️ Failed to start stat selection")
        
        elif blessing_type_local == "stat_plus_random_minus":
            # Curse2: Choose stat for +2, then random stat gets -1
            print(f"🔔 Starting stat selection for +2 (Curse2)")
            from screens import vessel_stat_selector
            stat_plus = result.get("stat_plus", 2)
            # Store vessel_idx and that we need to do random minus next
            _STATE["buff_application"]["vessel_idx"] = vessel_idx
            _STATE["buff_application"]["curse_phase"] = "plus"
            if vessel_stat_selector.start_stat_selection(gs, vessel_idx, stat_plus, allow_ac=False):
                _STATE["buff_application"]["step"] = "stat_selection"
                print(f"✅ Stat selection started for +{stat_plus}")
            else:
                print(f"⚠️ Failed to start stat selection")
        
        elif blessing_type_local == "stat_random_plus_minus_selection":
            # Curse4: Random stat gets +1, then choose stat for -1
            print(f"🔔 Applying random stat +1 (Curse4)")
            from systems import buff_applicator as ba
            import random
            stat_plus = result.get("stat_plus", 1)
            
            # Get vessel stats
            stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
            vessel_stats = stats_list[vessel_idx] if vessel_idx < len(stats_list) else None
            if vessel_stats and isinstance(vessel_stats, dict):
                abilities = vessel_stats.get("abilities", {})
                dnd_stats = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
                available_stats = [stat for stat in dnd_stats if stat in abilities]
                
                if available_stats:
                    # Pick random stat and apply +1
                    random_stat = random.choice(available_stats)
                    ba.apply_stat_bonus(gs, vessel_idx, random_stat, stat_plus)
                    print(f"✅ Applied +{stat_plus} to random stat {random_stat}")
                    
                    # Store that we need to do minus selection next
                    _STATE["buff_application"]["vessel_idx"] = vessel_idx
                    _STATE["buff_application"]["curse_phase"] = "minus"
                    _STATE["buff_application"]["random_stat_plus"] = random_stat
                    
                    # Now start stat selection for -1
                    from screens import vessel_stat_selector
                    stat_minus = result.get("stat_minus", 1)
                    if vessel_stat_selector.start_stat_selection(gs, vessel_idx, -stat_minus, allow_ac=False):
                        _STATE["buff_application"]["step"] = "stat_selection"
                        print(f"✅ Stat selection started for -{stat_minus}")
                    else:
                        print(f"⚠️ Failed to start stat selection")
                        _STATE["buff_application"]["step"] = "complete"
                else:
                    print(f"⚠️ No stats available for random selection")
                    _STATE["buff_application"]["step"] = "complete"
            else:
                print(f"⚠️ Invalid vessel stats")
                _STATE["buff_application"]["step"] = "complete"
        
        elif blessing_type_local == "stat_plus_hp_roll_minus":
            # Curse5: Choose stat for +2, then roll 1d12 HP and subtract
            print(f"🔔 Starting stat selection for +2 (Curse5)")
            from screens import vessel_stat_selector
            stat_plus = result.get("stat_plus", 2)
            # Store vessel_idx and that we need to do HP roll next
            _STATE["buff_application"]["vessel_idx"] = vessel_idx
            _STATE["buff_application"]["curse_phase"] = "plus"
            if vessel_stat_selector.start_stat_selection(gs, vessel_idx, stat_plus, allow_ac=False):
                _STATE["buff_application"]["step"] = "stat_selection"
                print(f"✅ Stat selection started for +{stat_plus}")
            else:
                print(f"⚠️ Failed to start stat selection")
        
        elif blessing_type_local == "stat_random_penalty_selection":
            # Punishment2: Apply -2 to 2 random stats on selected vessel
            print(f"🔔 Applying random stat penalties to vessel {vessel_idx} (Punishment2)")
            from systems import buff_applicator as ba
            stat_penalty = result.get("stat_penalty", 2)
            num_stats = result.get("num_stats", 2)
            success, penalized_stats = ba.apply_random_stat_penalties(gs, vessel_idx, stat_penalty, num_stats)
            if success and penalized_stats:
                # Get vessel name
                from systems.name_generator import generate_vessel_name
                names = getattr(gs, "party_slots_names", None) or [None] * 6
                vessel_name = names[vessel_idx] if vessel_idx < len(names) else None
                display_name = generate_vessel_name(vessel_name) if vessel_name else "Vessel"
                
                # Format stats text
                stats_text = ", ".join([f"{stat} -{stat_penalty}" for stat in penalized_stats])
                
                # Show result card
                ba.show_result_card(
                    f"{display_name}",
                    f"Lost: {stats_text}"
                )
                _STATE["buff_application"]["step"] = "result_card"
                print(f"✅ Random stat penalties applied: {display_name} lost {stats_text}")
            else:
                print(f"⚠️ Failed to apply random stat penalties")
                _STATE["buff_application"]["step"] = "complete"
        
        elif blessing_type_local == "hp_roll_penalty":
            # Punishment4: Roll dice and apply HP penalty
            print(f"🔔 Rolling HP penalty for vessel {vessel_idx} (Punishment4)")
            from rolling.roller import roll_dice
            from systems import buff_applicator as ba
            dice = result.get("dice", (1, 6))
            total, rolls = roll_dice(dice[0], dice[1])
            print(f"🔔 Rolled {dice[0]}d{dice[1]}: {rolls} = {total} HP penalty")
            
            # Apply HP penalty first (negative value)
            ba.apply_hp_bonus(gs, vessel_idx, -total)
            print(f"✅ HP penalty applied: -{total} HP")
            
            # Show result card
            ba.show_result_card(
                f"Rolled {dice[0]}d{dice[1]}",
                f"Result: -{total} HP",
                play_dice_sound=True
            )
            
            _STATE["buff_application"]["step"] = "result_card"
            _STATE["buff_application"]["vessel_idx"] = vessel_idx
            print(f"✅ Result card shown, step set to result_card")
        
        elif blessing_type_local == "remove_vessel":
            # Punishment5: Remove vessel from party
            print(f"🔔 Removing vessel {vessel_idx} from party (Punishment5)")
            from systems import buff_applicator as ba
            from systems.name_generator import generate_vessel_name
            
            # Get vessel name before removal
            names = getattr(gs, "party_slots_names", None) or [None] * 6
            vessel_name = names[vessel_idx] if vessel_idx < len(names) else None
            
            # Remove vessel
            success, removed_name = ba.remove_vessel_from_party(gs, vessel_idx)
            if success and removed_name:
                # Generate display name
                display_name = generate_vessel_name(removed_name)
                
                # Show result card
                ba.show_result_card(
                    f"{display_name}",
                    f"is dead. Every broken vow demands a life in return."
                )
                
                _STATE["buff_application"]["step"] = "result_card"
                print(f"✅ Vessel removed, result card shown")
            else:
                print(f"⚠️ Failed to remove vessel")
                _STATE["buff_application"]["step"] = "complete"
    
    # Open party manager in picker mode
    print(f"🔔 Opening party manager for vessel selection (blessing: {blessing_type})")
    party_manager.open_picker(on_vessel_selected)


def _roll_dice_for_all_vessels_hp(gs, dice: tuple, blessing: str):
    """Roll dice and apply HP to all vessels in the party."""
    from rolling.roller import roll_dice
    from systems import buff_applicator
    
    total, rolls = roll_dice(dice[0], dice[1])
    print(f"🔔 Rolled {dice[0]}d{dice[1]}: {rolls} = {total} HP for all vessels")
    
    # Show result card
    buff_applicator.show_result_card(
        f"Rolled {dice[0]}d{dice[1]}",
        f"Result: {total} HP to all vessels",
        play_dice_sound=True
    )
    
    # Apply HP to all vessels
    buff_applicator.apply_hp_to_all_vessels(gs, total)
    
    _STATE["buff_application"]["step"] = "result_card"
    print(f"✅ HP applied to all vessels, step set to result_card")


def _roll_dice_for_all_vessels_damage_reduction(gs, dice: tuple, blessing: str):
    """Roll dice and apply damage reduction to all vessels in the party."""
    from rolling.roller import roll_dice
    from systems import buff_applicator
    
    total, rolls = roll_dice(dice[0], dice[1])
    print(f"🔔 Rolled {dice[0]}d{dice[1]}: {rolls} = {total} damage reduction for all vessels")
    
    # Show result card
    buff_applicator.show_result_card(
        f"Rolled {dice[0]}d{dice[1]}",
        f"Result: -{total} damage reduction to all vessels",
        play_dice_sound=True
    )
    
    # Apply damage reduction to all vessels
    buff_applicator.apply_damage_reduction_to_all_vessels(gs, total)
    
    _STATE["buff_application"]["step"] = "result_card"
    print(f"✅ Damage reduction applied to all vessels, step set to result_card")


def _roll_dice_for_all_vessels_permanent_damage(gs, dice: tuple, blessing: str):
    """Roll dice and apply permanent damage bonus to all vessels in the party."""
    from rolling.roller import roll_dice
    from systems import buff_applicator
    
    total, rolls = roll_dice(dice[0], dice[1])
    print(f"🔔 Rolled {dice[0]}d{dice[1]}: {rolls} = {total} permanent damage bonus for all vessels")
    
    # Show result card
    buff_applicator.show_result_card(
        f"Rolled {dice[0]}d{dice[1]}",
        f"Result: +{total} bonus damage to all vessels",
        play_dice_sound=True
    )
    
    # Apply permanent damage bonus to all vessels
    buff_applicator.apply_permanent_damage_bonus_to_all_vessels(gs, total)
    
    _STATE["buff_application"]["step"] = "result_card"
    print(f"✅ Permanent damage bonus applied to all vessels, step set to result_card")

