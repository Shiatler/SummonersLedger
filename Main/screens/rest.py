# =============================================================
# screens/rest.py — Rest screen (Long Rest / Short Rest)
# - Shows campfire background with player character sprite
# - Displays textbox with rest message
# - Fades out while LongRest.mp3 plays
# - Applies healing and PP restoration
# =============================================================

import os
import pygame
import settings as S
from systems import audio as audio_sys
from systems.heal import heal_to_full, heal_to_half
from combat.moves import get_available_moves, _pp_set_full, _pp_get, _pp_store

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
_PLAYER_SPRITE = None
_PLAYER_GENDER = None
_CAMPFIRE_MUSIC = None
_LONGREST_SOUND = None

_PLAYER_SCALE = 1.8  # Same as master_oak scale
_SPRITE_X_OFFSET = -320  # Shift player sprite left on rest screen

def _load_background() -> pygame.Surface | None:
    """Load the campfire background."""
    global _BACKGROUND
    if _BACKGROUND is not None:
        return _BACKGROUND
    
    candidates = [
        os.path.join("Assets", "Map", "CampfireBG.png"),
        os.path.join("Assets", "CampfireBG.png"),
        r"C:\Users\Frederik\Desktop\SummonersLedger\Main\Assets\Map\CampfireBG.png",
        r"C:\Users\Frederik\Desktop\SummonersLedger\Main\Assets\CampfireBG.png",
    ]
    
    for path in candidates:
        if os.path.exists(path):
            try:
                bg = pygame.image.load(path).convert()
                # Scale to logical size if needed
                if bg.get_size() != (S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT):
                    bg = pygame.transform.smoothscale(bg, (S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT))
                _BACKGROUND = bg
                print(f"✅ Loaded CampfireBG.png from {path}")
                return bg
            except Exception as e:
                print(f"⚠️ Failed to load CampfireBG.png: {e}")
    
    print(f"⚠️ CampfireBG.png not found")
    return None

def _load_player_sprite(gs) -> pygame.Surface | None:
    """Load player sprite (FLog.png or MLog.png) based on gender."""
    global _PLAYER_SPRITE, _PLAYER_GENDER
    
    player_gender = getattr(gs, "player_gender", "male")
    
    # Check if we already have the correct sprite cached
    if _PLAYER_SPRITE is not None and _PLAYER_GENDER == player_gender:
        return _PLAYER_SPRITE
    
    # Determine filename based on gender
    if player_gender.lower().startswith("f"):
        filename = "FLog.png"
    else:
        filename = "MLog.png"
    
    candidates = [
        os.path.join("Assets", "PlayableCharacters", filename),
        os.path.join("Assets", filename),
        os.path.join("Assets", "Animations", filename),
        r"C:\Users\Frederik\Desktop\SummonersLedger\Main\Assets\PlayableCharacters\{}".format(filename),
        r"C:\Users\Frederik\Desktop\SummonersLedger\Main\Assets\{}".format(filename),
    ]
    
    for path in candidates:
        if os.path.exists(path):
            try:
                sprite = pygame.image.load(path).convert_alpha()
                # Scale to match master_oak size
                original_size = sprite.get_size()
                scaled_size = (int(original_size[0] * _PLAYER_SCALE), int(original_size[1] * _PLAYER_SCALE))
                sprite = pygame.transform.smoothscale(sprite, scaled_size)
                _PLAYER_SPRITE = sprite
                _PLAYER_GENDER = player_gender
                print(f"✅ Loaded {filename}")
                return sprite
            except Exception as e:
                print(f"⚠️ Failed to load {filename}: {e}")
    
    print(f"⚠️ {filename} not found")
    return None

def _load_campfire_music() -> str | None:
    """Get path to campfire music."""
    global _CAMPFIRE_MUSIC
    if _CAMPFIRE_MUSIC is not None:
        return _CAMPFIRE_MUSIC
    
    candidates = [
        os.path.join("Assets", "Music", "Sounds", "Campfire.mp3"),
        r"C:\Users\Frederik\Desktop\SummonersLedger\Main\Assets\Music\Sounds\Campfire.mp3",
    ]
    
    for path in candidates:
        if os.path.exists(path):
            _CAMPFIRE_MUSIC = path
            return path
    
    print(f"⚠️ Campfire.mp3 not found")
    return None

def _load_longrest_sound() -> pygame.mixer.Sound | None:
    """Load LongRest.mp3 sound."""
    global _LONGREST_SOUND
    if _LONGREST_SOUND is not None:
        return _LONGREST_SOUND
    
    candidates = [
        os.path.join("Assets", "Music", "Sounds", "LongRest.mp3"),
        r"C:\Users\Frederik\Desktop\SummonersLedger\Main\Assets\Music\Sounds\LongRest.mp3",
    ]
    
    for path in candidates:
        if os.path.exists(path):
            try:
                sound = pygame.mixer.Sound(path)
                _LONGREST_SOUND = sound
                print(f"✅ Loaded LongRest.mp3")
                return sound
            except Exception as e:
                print(f"⚠️ Failed to load LongRest.mp3: {e}")
    
    print(f"⚠️ LongRest.mp3 not found")
    return None

# ---------- Textbox helpers ----------
def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current_line = []
    current_width = 0
    
    for word in words:
        test_line = " ".join(current_line + [word])
        test_surf = font.render(test_line, False, (0, 0, 0))
        if test_surf.get_width() <= max_width or not current_line:
            current_line.append(word)
            current_width = test_surf.get_width()
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_width = font.render(word, False, (0, 0, 0)).get_width()
    
    if current_line:
        lines.append(" ".join(current_line))
    
    return lines

def _draw_textbox(screen: pygame.Surface, text: str, blink_t: float):
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

# ---------- PP restoration ----------
def _get_moves_for_vessel(gs, vessel_idx: int):
    """Get available moves for a specific vessel by index."""
    from combat.moves import _MOVE_REGISTRY, _normalize_class
    
    party_stats = getattr(gs, "party_vessel_stats", None) or [None] * 6
    if vessel_idx < 0 or vessel_idx >= len(party_stats):
        return []
    
    stats = party_stats[vessel_idx]
    if not isinstance(stats, dict):
        return []
    
    norm = _normalize_class(stats)
    if not norm:
        return []
    
    # Get vessel level
    level = 1
    try:
        level = int(stats.get("level", 1))
    except Exception:
        level = 1
    
    # Filter moves by level requirement
    all_moves = _MOVE_REGISTRY.get(norm, [])
    available = []
    for move in all_moves:
        if "_l1_" in move.id:
            available.append(move)
        elif "_l10_" in move.id and level >= 10:
            available.append(move)
        elif "_l20_" in move.id and level >= 20:
            available.append(move)
        elif "_l40_" in move.id and level >= 40:
            available.append(move)
        elif "_l50_" in move.id and level >= 50:
            available.append(move)
    
    return available

def _restore_pp_full(gs):
    """Restore all PP to full for all party members."""
    party_names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    for idx in range(6):
        if not party_names[idx]:
            continue
        
        vessel_name = str(party_names[idx])
        moves = _get_moves_for_vessel(gs, idx)
        
        for move in moves:
            _pp_set_full(gs, vessel_name, move)

def _restore_pp_half(gs):
    """Restore PP to half for all party members."""
    party_names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    for idx in range(6):
        if not party_names[idx]:
            continue
        
        vessel_name = str(party_names[idx])
        moves = _get_moves_for_vessel(gs, idx)
        
        for move in moves:
            # Get current PP and max PP
            current_pp = _pp_get(gs, vessel_name, move)
            
            # Get effective max_pp (base + bonuses)
            base_max_pp = move.max_pp
            if hasattr(gs, "move_pp_max_bonuses"):
                key = f"{vessel_name}:{move.id}"
                bonus = gs.move_pp_max_bonuses.get(key, 0)
                effective_max_pp = base_max_pp + bonus
            else:
                effective_max_pp = base_max_pp
            
            # Restore to half (at least current + half of remaining)
            half_pp = effective_max_pp // 2
            new_pp = max(current_pp, half_pp)
            
            store = _pp_store(gs)
            store.setdefault(vessel_name, {})[move.id] = new_pp

# ---------- Screen lifecycle ----------
def enter(gs, rest_type: str = "long", **_):
    """Initialize the rest screen state."""
    if not hasattr(gs, "_rest_state"):
        gs._rest_state = {}
    
    st = gs._rest_state
    st["rest_type"] = rest_type  # "long" or "short"
    st["text_displayed"] = False
    st["blink_t"] = 0.0
    st["fade_alpha"] = 0.0
    st["fade_started"] = False
    st["fade_timer"] = 0.0
    st["sound_played"] = False
    
    # Preserve current volume settings before entering rest
    try:
        st["saved_music_vol"] = pygame.mixer.music.get_volume()
        st["saved_sfx_vol"] = audio_sys.get_sfx_volume()
    except Exception:
        st["saved_music_vol"] = getattr(S, "MUSIC_VOLUME", 0.6)
        st["saved_sfx_vol"] = getattr(S, "SFX_VOLUME", 0.8)
    
    # Set text message based on rest type
    if rest_type == "long":
        st["message"] = "You drift off to the sound of crackling wood and a faint, with a full stomach."
    else:
        st["message"] = "The mug's empty, your head spins. Perfect time to get back up!"
    
    # Load assets
    _load_background()
    _load_player_sprite(gs)
    
    # Play campfire music
    music_path = _load_campfire_music()
    if music_path:
        audio_sys.play_music(audio_sys.get_global_bank(), music_path, loop=True, fade_ms=500)
    
    # Load longrest sound (will play during fade)
    _load_longrest_sound()

def draw(screen: pygame.Surface, gs, dt: float, **_):
    """Draw the rest screen."""
    st = gs._rest_state
    
    # Update blink timer
    st["blink_t"] += dt
    
    # Draw background
    bg = _load_background()
    if bg:
        screen.blit(bg, (0, 0))
    else:
        screen.fill((20, 10, 10))
    
    # Draw player sprite (same position as master_oak)
    sprite = _load_player_sprite(gs)
    if sprite:
        sprite_x = (S.LOGICAL_WIDTH - sprite.get_width()) // 2 + _SPRITE_X_OFFSET
        sprite_y = int(S.LOGICAL_HEIGHT * 0.15)
        screen.blit(sprite, (sprite_x, sprite_y))
    
    # Draw textbox if not fading
    if not st.get("fade_started", False):
        _draw_textbox(screen, st["message"], st["blink_t"])
    
    # Draw fade overlay if fading
    if st.get("fade_started", False):
        fade_alpha = int(st["fade_alpha"])
        if fade_alpha > 0:
            overlay = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT))
            overlay.set_alpha(fade_alpha)
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))

def handle(events, gs, dt: float, **_):
    """Handle events for the rest screen."""
    st = gs._rest_state
    
    # Handle fade phase
    if st.get("fade_started", False):
        st["fade_timer"] += dt
        
        # Fade out over 3 seconds (LongRest.mp3 is 3 seconds)
        fade_duration = 3.0
        if st["fade_timer"] < fade_duration:
            st["fade_alpha"] = min(255.0, (st["fade_timer"] / fade_duration) * 255.0)
            return None
        else:
            # Fade complete - apply healing and return
            st["fade_alpha"] = 255.0
            
            # Apply healing and PP restoration
            party_stats = getattr(gs, "party_vessel_stats", None) or [None] * 6
            
            if st["rest_type"] == "long":
                # Long rest: fully heal all party members and restore all PP
                for idx in range(6):
                    if party_stats[idx]:
                        heal_to_full(gs, idx)
                _restore_pp_full(gs)
            else:
                # Short rest: half HP and half PP
                for idx in range(6):
                    if party_stats[idx]:
                        heal_to_half(gs, idx)
                _restore_pp_half(gs)
            
            # Determine return mode
            if hasattr(gs, "_rest_return_to"):
                return_mode = gs._rest_return_to
                delattr(gs, "_rest_return_to")
            else:
                # Default to overworld
                return_mode = S.MODE_GAME
            
            # Stop campfire music before returning
            audio_sys.stop_music(fade_ms=0)
            
            # Restore volumes to what they were before entering rest
            try:
                saved_music_vol = st.get("saved_music_vol")
                saved_sfx_vol = st.get("saved_sfx_vol")
                
                if saved_music_vol is not None:
                    pygame.mixer.music.set_volume(saved_music_vol)
                
                if saved_sfx_vol is not None:
                    audio_sys.set_sfx_volume(saved_sfx_vol, audio_sys.get_global_bank())
            except Exception as e:
                print(f"⚠️ Failed to restore volumes: {e}")
                pass
            
            return return_mode
    
    # Handle textbox dismissal
    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                # Start fade
                st["fade_started"] = True
                st["fade_timer"] = 0.0
                st["fade_alpha"] = 0.0
                
                # Play LongRest sound
                if not st.get("sound_played", False):
                    sound = _load_longrest_sound()
                    if sound:
                        audio_sys.play_sound(sound)
                    st["sound_played"] = True
                
                return None
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Start fade
            st["fade_started"] = True
            st["fade_timer"] = 0.0
            st["fade_alpha"] = 0.0
            
            # Play LongRest sound
            if not st.get("sound_played", False):
                sound = _load_longrest_sound()
                if sound:
                    audio_sys.play_sound(sound)
                st["sound_played"] = True
            
            return None
    
    return None

