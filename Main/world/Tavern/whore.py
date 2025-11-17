# =============================================================
# world/Tavern/whore.py — Whore interaction screen
# - Shows bedroom background
# - Displays whore sprite (same size as gambling screen)
# - Textbox with randomized medieval text
# - Fade to black after dismissing textbox
# =============================================================

import os
import random
import pygame
import settings as S

from systems import audio
from systems.heal import heal_to_full

# ---------- Assets ----------
_BACKGROUND = None
_WHORE_SPRITE = None
_WHORE_NUMBER = None
_BEDROOM_MUSIC_PLAYING = False
_SEX_SOUND = None

BEDROOM_BACKGROUND_PATHS = [
    os.path.join("Assets", "Tavern Bedroom.png"),
    os.path.join("Assets", "Tavern", "Bedroom.png"),
]
BEDROOM_MUSIC_PATHS = [
    os.path.join("Assets", "Tavern Bedroom.mp3"),
    os.path.join("Assets", "Tavern", "Bedroom.mp3"),
]
SEX_SOUND_PATHS = [
    os.path.join("Assets", "Tavern Sex.mp3"),
    os.path.join("Assets", "Tavern", "Sex.mp3"),
]


def _resolve_existing_path(candidates: list[str]) -> str | None:
    """Return the first existing path from candidates."""
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

# ---------- Text Lines ----------
_SINGLE_WHORE_LINES = [
    "The tavern wench leads you to a private chamber, her eyes gleaming with promise.",
    "She unfastens her bodice with practiced hands, revealing soft curves in the candlelight.",
    "Her lips find yours as she guides you to the bed, her touch both gentle and eager.",
    "The wench kneels before you, her skilled mouth working its magic in the dim light.",
    "She moans softly as you take her, her body moving in rhythm with your own.",
    "Her fingers trace patterns on your skin as she whispers sweet nothings in your ear.",
    "The chamber fills with the sounds of passion as you lose yourself in her embrace.",
    "She rides you with wild abandon, her hair cascading around her flushed face.",
    "Her skilled tongue explores every inch of you, leaving you breathless and wanting more.",
    "As the night wears on, she proves her worth, leaving you spent and satisfied.",
]

_PLURAL_WHORE_LINES = [
    "The two wenches exchange knowing glances before leading you to their shared chamber.",
    "They work in tandem, one taking your front while the other attends to your back.",
    "Their hands roam freely as they take turns pleasuring you in ways you never imagined.",
    "The chamber echoes with their combined moans as they service you together.",
    "They move in perfect harmony, their bodies intertwined with yours in a dance of desire.",
    "One whispers in your ear while the other works below, leaving you overwhelmed with sensation.",
    "Their skilled mouths work in unison, bringing you to heights of ecstasy you've never known.",
    "As the night progresses, they take turns riding you, each bringing her own unique talents.",
]

_HAREM_WHORE_LINES = [
    "Five beautiful wenches surround you, their eyes hungry with desire.",
    "They work as one, their hands and mouths moving in perfect synchronization.",
    "You're passed from one to another, each adding her own special touch to your pleasure.",
    "The chamber becomes a whirlwind of flesh and passion as they take turns with you.",
    "One rides your face while another takes you from behind, and the rest wait their turn eagerly.",
    "Their combined efforts leave you in a state of blissful exhaustion you've never experienced.",
    "They form a circle around you, each taking a part of you in their skilled hands and mouths.",
    "As dawn approaches, you find yourself surrounded by satisfied smiles and spent bodies.",
    "The five of them work together like a well-oiled machine, leaving no part of you untouched.",
    "You lose count of how many times they bring you to completion, lost in their collective embrace.",
]

def _get_dh_font(size: int) -> pygame.font.Font:
    """Get DH font at specified size, fallback to default font."""
    try:
        dh_font_path = os.path.join(S.ASSETS_FONTS_DIR, S.DND_FONT_FILE)
        if os.path.exists(dh_font_path):
            return pygame.font.Font(dh_font_path, size)
    except:
        pass
    return pygame.font.SysFont(None, size)

def _load_background() -> pygame.Surface | None:
    """Load bedroom background image."""
    global _BACKGROUND
    if _BACKGROUND is not None:
        return _BACKGROUND
    
    path = _resolve_existing_path(BEDROOM_BACKGROUND_PATHS)
    if not path:
        print(f"⚠️ Bedroom background not found (checked {BEDROOM_BACKGROUND_PATHS})")
        return None
    
    try:
        img = pygame.image.load(path).convert()
        img = pygame.transform.smoothscale(img, (S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT))
        _BACKGROUND = img
        print(f"✅ Loaded bedroom background")
        return img
    except Exception as e:
        print(f"⚠️ Failed to load bedroom background: {e}")
        return None

def _load_whore_sprite_for_screen(whore_number: int) -> pygame.Surface | None:
    """Load whore sprite for the bedroom screen (same size as gambling screen)."""
    global _WHORE_SPRITE, _WHORE_NUMBER
    
    # Return cached sprite if same whore number
    if _WHORE_SPRITE is not None and _WHORE_NUMBER == whore_number:
        return _WHORE_SPRITE
    
    path = os.path.join("Assets", "Tavern", f"Whore{whore_number}.png")
    if not os.path.exists(path):
        print(f"⚠️ Whore{whore_number}.png not found at {path}")
        return None
    
    try:
        sprite = pygame.image.load(path).convert_alpha()
        # Scale to same size as gambling screen character (1.2x scale)
        from world.Tavern.gambling import _CHARACTER_SCALE
        original_size = sprite.get_size()
        scaled_size = (int(original_size[0] * _CHARACTER_SCALE), int(original_size[1] * _CHARACTER_SCALE))
        sprite = pygame.transform.smoothscale(sprite, scaled_size).convert_alpha()
        
        _WHORE_SPRITE = sprite
        _WHORE_NUMBER = whore_number
        print(f"✅ Loaded and scaled Whore{whore_number} to {scaled_size[0]}x{scaled_size[1]}")
        return sprite
    except Exception as e:
        print(f"⚠️ Failed to load Whore{whore_number}: {e}")
        return None

def _load_bedroom_music():
    """Load and play bedroom music at 50% volume."""
    global _BEDROOM_MUSIC_PLAYING
    
    if _BEDROOM_MUSIC_PLAYING:
        return
    
    path = _resolve_existing_path(BEDROOM_MUSIC_PATHS)
    if not path:
        print(f"⚠️ Bedroom music not found (checked {BEDROOM_MUSIC_PATHS})")
        _BEDROOM_MUSIC_PLAYING = False
        return
    
    try:
        # Use audio.play_music to respect volume settings
        from systems import audio
        audio.play_music(None, path, loop=True, fade_ms=0)
        # Set volume to 50% of music volume
        current_vol = pygame.mixer.music.get_volume() or 0.6
        pygame.mixer.music.set_volume(current_vol * 0.5)
        print(f"✅ Playing bedroom music at 50% volume")
        _BEDROOM_MUSIC_PLAYING = True
    except Exception as e:
        print(f"⚠️ Failed to play bedroom music: {e}")
        _BEDROOM_MUSIC_PLAYING = False

def _play_sex_sound():
    """Play sex sound effect."""
    global _SEX_SOUND
    
    path = _resolve_existing_path(SEX_SOUND_PATHS)
    if not path:
        print(f"⚠️ Sex sound not found (checked {SEX_SOUND_PATHS})")
        return
    
    try:
        if _SEX_SOUND is None:
            _SEX_SOUND = pygame.mixer.Sound(path)
        # Use audio.play_sound to respect volume settings
        audio.play_sound(_SEX_SOUND)
        print(f"🔊 Playing sex sound")
    except Exception as e:
        print(f"⚠️ Failed to play sex sound: {e}")

def _get_random_text(whore_number: int) -> str:
    """Get random text based on whore number."""
    if 1 <= whore_number <= 5:
        return random.choice(_SINGLE_WHORE_LINES)
    elif 6 <= whore_number <= 8:
        return random.choice(_PLURAL_WHORE_LINES)
    elif whore_number == 9:
        return random.choice(_HAREM_WHORE_LINES)
    else:
        return random.choice(_SINGLE_WHORE_LINES)

def _draw_textbox(screen: pygame.Surface, text: str, dt: float):
    """Draw textbox at bottom of screen (same style as gambling screen)."""
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)
    
    # Box styling (matches gambling screen)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)
    
    # Text rendering
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
    if not hasattr(_draw_textbox, "blink_t"):
        _draw_textbox.blink_t = 0.0
    _draw_textbox.blink_t += dt
    blink_on = int(_draw_textbox.blink_t * 2) % 2 == 0
    if blink_on:
        prompt_font = _get_dh_font(20)
        prompt = "Press SPACE or Click to continue"
        psurf = prompt_font.render(prompt, False, (100, 100, 100))
        screen.blit(psurf, (rect.right - psurf.get_width() - 20, rect.bottom - psurf.get_height() - 12))

# ---------- Screen lifecycle ----------
def enter(gs, whore_number: int, whore_sprite=None, **_):
    """Initialize the whore screen state."""
    global _WHORE_SPRITE, _WHORE_NUMBER
    
    # Load background
    _load_background()
    
    # Load whore sprite (prefer loading from disk for high quality)
    sprite = _load_whore_sprite_for_screen(whore_number)
    if sprite is None and whore_sprite is not None:
        try:
            from world.Tavern.gambling import _CHARACTER_SCALE
            original_size = whore_sprite.get_size()
            scaled_size = (int(original_size[0] * _CHARACTER_SCALE), int(original_size[1] * _CHARACTER_SCALE))
            sprite = pygame.transform.smoothscale(whore_sprite, scaled_size).convert_alpha()
            print(f"✅ Fallback: scaled provided sprite for Whore{whore_number} to {scaled_size[0]}x{scaled_size[1]}")
        except Exception as e:
            print(f"⚠️ Failed to scale provided whore sprite: {e}")
            sprite = None
    
    _WHORE_SPRITE = sprite
    _WHORE_NUMBER = whore_number
    
    # Initialize state (always reset when entering whore screen)
    if not hasattr(gs, "_whore_state"):
        gs._whore_state = {}
    
    st = gs._whore_state
    # Reset all state when entering whore screen (important for multiple visits)
    st["whore_number"] = whore_number
    st["textbox_active"] = True
    st["textbox_blink_t"] = 0.0
    st["text"] = _get_random_text(whore_number)
    st["fade_started"] = False
    st["fade_alpha"] = 0
    st["fade_timer"] = 0.0
    st["total_timer"] = 0.0
    st["return_to_tavern"] = False  # CRITICAL: Reset return flag
    
    # Store the tavern reference when entering whore screen (so we can mark it as consumed when returning)
    # Get current tavern position to store which tavern this whore belongs to
    current_tavern = getattr(gs, "near_tavern", None)
    if current_tavern and isinstance(current_tavern, dict) and "pos" in current_tavern:
        tavern_pos = current_tavern["pos"]
        st["tavern_key"] = (float(tavern_pos.x), float(tavern_pos.y))
        print(f"💋 Stored tavern key for whore: ({st['tavern_key'][0]:.1f}, {st['tavern_key'][1]:.1f})")
    else:
        # Fallback: try to get from tavern_state's overworld_tavern
        tavern_state = getattr(gs, "_tavern_state", None)
        if isinstance(tavern_state, dict) and "overworld_tavern" in tavern_state:
            fallback_tavern = tavern_state["overworld_tavern"]
            if fallback_tavern and isinstance(fallback_tavern, dict) and "pos" in fallback_tavern:
                tavern_pos = fallback_tavern["pos"]
                st["tavern_key"] = (float(tavern_pos.x), float(tavern_pos.y))
                print(f"💋 Stored tavern key from fallback: ({st['tavern_key'][0]:.1f}, {st['tavern_key'][1]:.1f})")
            else:
                st["tavern_key"] = None
                print(f"⚠️ Could not determine tavern key for whore")
        else:
            st["tavern_key"] = None
            print(f"⚠️ Could not determine tavern key for whore")
    
    # Play bedroom music
    _load_bedroom_music()
    
    print(f"💋 Entered whore screen with Whore{whore_number}")

def update(gs, dt: float, **_):
    """Update whore screen state."""
    st = gs._whore_state
    
    if st.get("textbox_active", False):
        st["textbox_blink_t"] = st.get("textbox_blink_t", 0.0) + dt
    
    if st.get("fade_started", False):
        st["fade_timer"] = st.get("fade_timer", 0.0) + dt
        st["total_timer"] = st.get("total_timer", 0.0) + dt
        
        # Fade to black over 5 seconds
        fade_duration = 5.0
        if st["fade_timer"] <= fade_duration:
            st["fade_alpha"] = min(255, int((st["fade_timer"] / fade_duration) * 255))
        else:
            st["fade_alpha"] = 255
        
        # Return to tavern after 8 seconds total
        if st["total_timer"] >= 8.0:
            st["return_to_tavern"] = True

def handle(events, gs, dt: float, **_):
    """Handle whore screen events."""
    st = gs._whore_state
    
    if st.get("return_to_tavern", False):
        # Stop music using audio system
        from systems import audio
        audio.stop_music(fade_ms=300)
        global _BEDROOM_MUSIC_PLAYING
        _BEDROOM_MUSIC_PLAYING = False

        # Mark whore as consumed for THIS specific tavern and remove from tavern state
        tavern_state = getattr(gs, "_tavern_state", None)
        if isinstance(tavern_state, dict):
            # Initialize per-tavern whore tracking if needed
            if "tavern_whores_consumed" not in tavern_state:
                tavern_state["tavern_whores_consumed"] = {}
            
            # Use the stored tavern key from when we entered the whore screen
            # This ensures we mark the correct tavern even if near_tavern is None or changed
            tavern_key = st.get("tavern_key", None)
            if tavern_key:
                tavern_state["tavern_whores_consumed"][tavern_key] = True
                print(f"💋 Marked whore as consumed for tavern at ({tavern_key[0]:.1f}, {tavern_key[1]:.1f})")
            else:
                # Fallback: try to get from near_tavern or overworld_tavern
                current_tavern = getattr(gs, "near_tavern", None)
                if not current_tavern and "overworld_tavern" in tavern_state:
                    current_tavern = tavern_state["overworld_tavern"]
                
                if current_tavern and isinstance(current_tavern, dict) and "pos" in current_tavern:
                    tavern_pos = current_tavern["pos"]
                    tavern_key = (float(tavern_pos.x), float(tavern_pos.y))
                    tavern_state["tavern_whores_consumed"][tavern_key] = True
                    print(f"💋 Marked whore as consumed for tavern at ({tavern_key[0]:.1f}, {tavern_key[1]:.1f}) [fallback]")
                else:
                    print(f"⚠️ Could not determine tavern key to mark whore as consumed")
            
            # Remove whore from current tavern state
            tavern_state["whore_pos"] = None
            tavern_state["whore_sprite"] = None
            tavern_state["whore_number"] = None
            tavern_state["near_whore"] = False
            print("💋 Whore removed from tavern state")

        # Heal all party members to full (long rest effect)
        party = getattr(gs, "party_vessel_stats", None)
        if isinstance(party, list):
            for idx in range(len(party)):
                healed = heal_to_full(gs, idx)
                if healed:
                    print(f"❤️ Healed party slot {idx} to full HP")
        return "TAVERN"
    
    if st.get("textbox_active", False):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    # Dismiss textbox and start fade
                    st["textbox_active"] = False
                    st["fade_started"] = True
                    st["fade_timer"] = 0.0
                    st["total_timer"] = 0.0
                    _play_sex_sound()
                    print("💋 Textbox dismissed, starting fade")
                    return None
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Dismiss textbox and start fade
                st["textbox_active"] = False
                st["fade_started"] = True
                st["fade_timer"] = 0.0
                st["total_timer"] = 0.0
                _play_sex_sound()
                print("💋 Textbox dismissed, starting fade")
                return None
    
    return None

def draw(screen: pygame.Surface, gs, dt: float, **_):
    """Draw the whore screen."""
    st = gs._whore_state
    
    # Draw background
    if _BACKGROUND:
        screen.blit(_BACKGROUND, (0, 0))
    else:
        screen.fill((0, 0, 0))
    
    # Draw whore sprite (positioned same as gambling screen character)
    if _WHORE_SPRITE:
        # Position: center horizontally, 20% from top (same as gambling screen)
        whore_x = (S.LOGICAL_WIDTH - _WHORE_SPRITE.get_width()) // 2
        whore_y = int(S.LOGICAL_HEIGHT * 0.20)
        screen.blit(_WHORE_SPRITE, (whore_x, whore_y))
    
    # Draw textbox if active
    if st.get("textbox_active", False):
        text = st.get("text", "")
        _draw_textbox(screen, text, dt)
    
    # Draw fade overlay if fading
    if st.get("fade_started", False):
        fade_alpha = st.get("fade_alpha", 0)
        if fade_alpha > 0:
            overlay = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, fade_alpha))
            screen.blit(overlay, (0, 0))

