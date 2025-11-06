# =============================================================
# screens/rest.py — Rest screen (Long rest / Short rest)
# - Shows campfire background
# - Plays campfire sound (no music)
# - Displays textbox with rest message
# - Fades out with LongRest sound
# - Heals vessels appropriately
# =============================================================

import os
import pygame
import settings as S
from systems import audio as audio_sys
from systems.heal import heal_to_full, heal_to_half
from combat.btn.bag_action import _decrement_inventory as decrement_inventory

# Pre-load global bank at module level to avoid first-time lag
_AUDIO_BANK_CACHE = None
def _get_cached_bank():
    global _AUDIO_BANK_CACHE
    if _AUDIO_BANK_CACHE is None:
        _AUDIO_BANK_CACHE = audio_sys.get_global_bank()
    return _AUDIO_BANK_CACHE

# ---------- Font helpers ----------
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
        return pygame.font.SysFont("arial", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)

# ---------- Assets ----------
_BACKGROUND = None
_CAMPFIRE_SFX = None
_LONGREST_SFX = None
_CAMPFIRE_CHANNEL = None  # Global reference to track the channel
_CHARACTER_LOG_IMAGE = None  # Character sitting on log sprite
_CHARACTER_SCALE = 1.8  # Same scale as Master Oak

def _load_background() -> pygame.Surface | None:
    """Load the campfire background."""
    global _BACKGROUND
    if _BACKGROUND is not None:
        return _BACKGROUND
    
    path = os.path.join("Assets", "Map", "CampfireBG.png")
    if not os.path.exists(path):
        print(f"⚠️ CampfireBG.png not found at {path}")
        return None
    
    try:
        bg = pygame.image.load(path).convert()
        # Scale to logical screen size
        bg = pygame.transform.smoothscale(bg, (S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT))
        _BACKGROUND = bg
        return bg
    except Exception as e:
        print(f"⚠️ Failed to load background: {e}")
        return None

def _load_campfire_sfx() -> pygame.mixer.Sound | None:
    """Load the campfire sound effect."""
    global _CAMPFIRE_SFX
    if _CAMPFIRE_SFX is not None:
        return _CAMPFIRE_SFX
    
    path = os.path.join("Assets", "Music", "Sounds", "Campfire.mp3")
    if not os.path.exists(path):
        print(f"⚠️ Campfire.mp3 not found at {path}")
        return None
    
    try:
        _CAMPFIRE_SFX = pygame.mixer.Sound(path)
        return _CAMPFIRE_SFX
    except Exception as e:
        print(f"⚠️ Failed to load Campfire.mp3: {e}")
        return None

def _load_longrest_sfx() -> pygame.mixer.Sound | None:
    """Load the long rest sound effect."""
    global _LONGREST_SFX
    if _LONGREST_SFX is not None:
        return _LONGREST_SFX
    
    path = os.path.join("Assets", "Music", "Sounds", "LongRest.mp3")
    if not os.path.exists(path):
        print(f"⚠️ LongRest.mp3 not found at {path}")
        return None
    
    try:
        _LONGREST_SFX = pygame.mixer.Sound(path)
        return _LONGREST_SFX
    except Exception as e:
        print(f"⚠️ Failed to load LongRest.mp3: {e}")
        return None

def _load_character_log_image(gs) -> pygame.Surface | None:
    """Load the character sitting on log image based on player gender."""
    global _CHARACTER_LOG_IMAGE
    # Always reload to get the correct gender (could change between sessions)
    _CHARACTER_LOG_IMAGE = None
    
    # Get player gender
    player_gender = getattr(gs, "player_gender", "male")
    
    # Determine filename based on gender
    if player_gender.lower().startswith("f"):
        filename = "FLog.png"
    else:
        filename = "MLog.png"
    
    path = os.path.join("Assets", "PlayableCharacters", filename)
    if not os.path.exists(path):
        print(f"⚠️ {filename} not found at {path}")
        return None
    
    try:
        img = pygame.image.load(path).convert_alpha()
        # Scale up to match Master Oak size (1.8x scale)
        original_size = img.get_size()
        scaled_size = (int(original_size[0] * _CHARACTER_SCALE), int(original_size[1] * _CHARACTER_SCALE))
        img = pygame.transform.smoothscale(img, scaled_size)
        _CHARACTER_LOG_IMAGE = img
        return img
    except Exception as e:
        print(f"⚠️ Failed to load {filename}: {e}")
        return None

# ---------- Textbox helpers ----------
def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = (current_line + " " + word).strip()
        if not current_line or font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return lines

def _draw_textbox(screen: pygame.Surface, text: str, dt: float, blink_t: float):
    """Draw the textbox."""
    sw, sh = screen.get_size()
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)
    
    # Box styling (matches other textboxes)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)
    
    # Text area
    inner_pad = 20
    text_rect = rect.inflate(-inner_pad * 2, -inner_pad * 2)
    
    font = _get_dh_font(28)
    lines = _wrap_text(text, font, text_rect.w)
    
    # Draw text lines
    y = text_rect.y
    for line in lines:
        surf = font.render(line, False, (16, 16, 16))
        screen.blit(surf, (text_rect.x, y))
        y += surf.get_height() + 6
    
    # Blinking prompt
    blink_on = int(blink_t * 2) % 2 == 0
    if blink_on:
        prompt_font = _get_dh_font(20)
        prompt = "Press Enter or Click to continue"
        psurf = prompt_font.render(prompt, False, (40, 40, 40))
        px = rect.right - psurf.get_width() - 16
        py = rect.bottom - psurf.get_height() - 12
        shadow = prompt_font.render(prompt, False, (235, 235, 235))
        screen.blit(shadow, (px - 1, py - 1))
        screen.blit(psurf, (px, py))

# ---------- Item consumption ----------
def _has_item(gs, item_id: str) -> bool:
    """Check if player has the item."""
    inv = getattr(gs, "inventory", None)
    if not inv:
        return False
    
    if isinstance(inv, dict):
        return inv.get(item_id, 0) > 0
    
    if isinstance(inv, (list, tuple)):
        for rec in inv:
            if isinstance(rec, dict):
                rid = rec.get("id") or _snake_from_name(rec.get("name", ""))
                if rid == item_id:
                    return int(rec.get("qty", 0)) > 0
            elif isinstance(rec, (list, tuple)) and len(rec) >= 1:
                rid = str(rec[0])
                if rid == item_id:
                    return int(rec[1]) > 0 if len(rec) > 1 else False
    
    return False

def _snake_from_name(s: str) -> str:
    """Convert item name to snake_case ID."""
    return s.lower().replace(" ", "_")

def _consume_item(gs, item_id: str) -> bool:
    """Consume one item from inventory. Returns True if consumed."""
    decrement_inventory(gs, item_id)
    return True

def _stop_campfire_sound(st):
    """Stop the campfire sound channel reliably."""
    global _CAMPFIRE_CHANNEL
    
    # Stop via stored channel references
    if st.get("campfire_channel"):
        try:
            ch = st["campfire_channel"]
            ch.stop()  # Stop immediately, don't check get_busy
        except:
            pass
        st["campfire_channel"] = None
    
    if _CAMPFIRE_CHANNEL:
        try:
            _CAMPFIRE_CHANNEL.stop()  # Stop immediately
        except:
            pass
        _CAMPFIRE_CHANNEL = None
    
    # Nuclear option: stop ALL busy channels (aggressive but ensures it stops)
    # During rest screen transition, this should be safe
    try:
        num_channels = pygame.mixer.get_num_channels()
        for i in range(num_channels):
            ch = pygame.mixer.Channel(i)
            try:
                if ch.get_busy():
                    ch.stop()
            except:
                pass
    except:
        pass
    
    # Mark that we've stopped
    st["campfire_stopped"] = True

# ---------- Screen lifecycle ----------
def enter(gs, rest_type="long", **_):
    """Initialize the rest screen state. rest_type should be 'long' or 'short'."""
    # Pre-load audio bank synchronously to avoid lag when playing sounds
    # This ensures it's loaded before first sound plays
    try:
        _get_cached_bank()
    except Exception:
        pass
    
    if not hasattr(gs, "_rest_state"):
        gs._rest_state = {}
    
    st = gs._rest_state
    st["phase"] = "resting"  # "resting", "fading"
    st["rest_type"] = str(rest_type).lower()  # "long" or "short" - ensure it's a lowercase string
    st["blink_t"] = 0.0
    st["fade_alpha"] = 0.0
    st["fade_speed"] = 0.0
    st["fade_timer"] = 0.0
    st["campfire_channel"] = None
    st["longrest_channel"] = None
    st["item_consumed"] = False
    st["vessels_healed"] = False
    st["textbox_active"] = True
    st["campfire_stopped"] = False  # Track if we've stopped the campfire sound
    
    # Consume item based on rest type
    if rest_type == "long":
        _consume_item(gs, "rations")
    elif rest_type == "short":
        _consume_item(gs, "alcohol")
    
    # Stop music
    audio_sys.stop_music()
    
    # Play campfire sound at lower volume using audio system
    global _CAMPFIRE_SFX
    sfx = _load_campfire_sfx()
    if sfx:
        # Stop any existing campfire sound first
        _stop_campfire_sound(st)
        
        # Use a dedicated channel and set volume
        channel = pygame.mixer.find_channel(True)
        if channel:
            # Set volume to 0.4 (40% - ambient sound) before playing
            channel.set_volume(0.4)
            channel.play(sfx, loops=-1)
            st["campfire_channel"] = channel
            _CAMPFIRE_CHANNEL = channel  # Store globally as backup

def draw(screen: pygame.Surface, gs, dt: float, **_):
    """Draw the rest screen."""
    global _CAMPFIRE_CHANNEL
    st = gs._rest_state
    st["blink_t"] += dt
    
    # Draw background
    bg = _load_background()
    if bg:
        screen.blit(bg, (0, 0))
    else:
        screen.fill((20, 10, 10))
    
    # Draw character sitting on log (same position and size as Master Oak, but more to the left)
    char_img = _load_character_log_image(gs)
    if char_img:
        # Position: further to the left, at 15% of screen height (same vertical as Master Oak)
        # Use logical dimensions to match the rest of the rest screen
        char_x = int(S.LOGICAL_WIDTH * 0.15)  # 15% from left edge
        char_y = int(S.LOGICAL_HEIGHT * 0.15)
        screen.blit(char_img, (char_x, char_y))
    
    # Resting phase (show textbox)
    if st["phase"] == "resting":
        if st["textbox_active"]:
            if st["rest_type"] == "long":
                text = "Your belly is full, and you sleep through the night"
            elif st["rest_type"] == "short":
                text = "You drink a cup of mead and feel good"
            else:
                # Fallback (shouldn't happen, but just in case)
                text = "You rest and feel refreshed"
            _draw_textbox(screen, text, dt, st["blink_t"])
        
        # Draw fade overlay if fading
        if st["fade_alpha"] > 0:
            fade_overlay = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT), pygame.SRCALPHA)
            fade_overlay.fill((0, 0, 0, int(st["fade_alpha"])))
            screen.blit(fade_overlay, (0, 0))
        
        # Update fade during resting phase
        if st["fade_speed"] > 0:
            st["fade_alpha"] = min(255.0, st["fade_alpha"] + st["fade_speed"] * dt)
            st["fade_timer"] += dt
            
            # Fade out campfire sound during the fade (start fading at 2.5 seconds)
            if st.get("campfire_channel") and st["fade_timer"] >= 2.5:
                # Fade out over the last 0.5 seconds
                fade_progress = (st["fade_timer"] - 2.5) / 0.5
                volume = max(0.0, 0.4 * (1.0 - fade_progress))
                try:
                    st["campfire_channel"].set_volume(volume)
                except:
                    pass
            
            # Stop campfire sound at 3.0 seconds (when fade completes) using fadeout
            if st["fade_timer"] >= 3.0:
                _stop_campfire_sound(st)
            
            # When fade is complete, transition to fading phase (completely black)
            if st["fade_alpha"] >= 255.0:
                # Stop campfire sound immediately when fade completes
                _stop_campfire_sound(st)
                st["phase"] = "fading"
                st["textbox_active"] = False
    
    # Fading phase (completely black)
    elif st["phase"] == "fading":
        screen.fill((0, 0, 0))
        # Update fade timer during fading phase
        st["fade_timer"] += dt
        
        # Stop campfire sound immediately when entering fading phase (fade is complete)
        if not st.get("campfire_stopped", False):
            _stop_campfire_sound(st)
        
        # Continuously ensure it's stopped during fading phase
        if st.get("campfire_channel") or _CAMPFIRE_CHANNEL:
            _stop_campfire_sound(st)

def handle(events, gs, dt: float, **_):
    """Handle events for the rest screen."""
    st = gs._rest_state
    
    # Resting phase (textbox visible)
    if st["phase"] == "resting" and st["textbox_active"]:
        # Heal vessels when textbox first appears
        if not st.get("vessels_healed", False):
            stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
            for idx in range(len(stats_list)):
                if isinstance(stats_list[idx], dict):
                    if st["rest_type"] == "long":
                        heal_to_full(gs, idx)
                    else:  # short
                        heal_to_half(gs, idx)
            st["vessels_healed"] = True
        
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                    # Start fade out (fade starts during resting phase, then transitions to black)
                    st["fade_alpha"] = 0.0
                    st["fade_speed"] = 255.0 / 3.0  # 3 second fade
                    st["fade_timer"] = 0.0
                    # Play long rest sound
                    sfx = _load_longrest_sfx()
                    if sfx:
                        st["longrest_channel"] = sfx.play()
                    audio_sys.play_click(_get_cached_bank())
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Start fade out (fade starts during resting phase, then transitions to black)
                st["fade_alpha"] = 0.0
                st["fade_speed"] = 255.0 / 3.0  # 3 second fade
                st["fade_timer"] = 0.0
                # Play long rest sound
                sfx = _load_longrest_sfx()
                if sfx:
                    st["longrest_channel"] = sfx.play()
                audio_sys.play_click(audio_sys.get_global_bank())
        
        return None
    
    # Fading phase
    if st["phase"] == "fading":
        # Wait for fade to complete (3 seconds) + 0.2 seconds of black
        if st["fade_timer"] >= 3.2:
            # Ensure campfire sound is stopped (final safety check)
            _stop_campfire_sound(st)
            # Return to game
            return "GAME"
        
        return None
    
    return None

