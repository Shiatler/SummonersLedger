# =============================================================
# screens/master_oak.py — Master Oak introduction scene
# - Shows Master Oak animation (MasterOak1-4.png)
# - Displays textbox with word-by-word typing (Pokemon style)
# - Plays OakVoice.mp3 when each new section starts
# - Navigates to starter selection (black_screen) when done
# =============================================================

import os
import pygame
import settings as S
from systems import audio as audio_sys

# ---------- Animator class (local copy to avoid circular import) ----------
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

# ---------- Text sections ----------
TEXT_SECTIONS = [
    "Ahh… there you are! So you must be {player_name}, yes?",
    "I've been expecting you.",
    "I am Master Oak, Dungeon Master and god of this realm.",
    "Before you are 3 vessels.",
    "These Vessel once walked the world as heroes, long before our time.",
    "Choose carefully, Summoner.",
    "Every choice you make together will write another page in the story of this world.",
    "The path ahead is not a gentle one. Across these lands wander other Summoners — each bound to their own echoes, each chasing power, glory, or redemption.",
    "To rise above them, you must seek out and capture more Vessels, master their will, and prove your bond stronger than theirs.",
    "In time, perhaps your name will be etched among the greats…",
    "a Summoner whose Ledger reshaped the fate of the realm itself.",
    "Oh.. You should have this for your journey: 5 Scrolls Of Mending, 5 Scrolls Of Command and 10 Gold Pieces, also take some rations and alcohol",
    "Good luck {player_name}.",
]

# ---------- Animation and assets ----------
_OAK_ANIM_FRAMES = None
_OAK_IDLE_IMAGE = None
_OAK_SHUT_IMAGE = None
_OAK_SCALE = 1.8  # Scale factor to make him bigger and closer
_BACKGROUND = None
_OAK_VOICE_SFX = None
_BOOK_SHUT_SFX = None
_OAK_SCROLL_IMAGE = None

def _load_oak_animation() -> list[pygame.Surface] | None:
    """Load Master Oak animation frames (MasterOak1.png to MasterOak4.png) and scale them."""
    global _OAK_ANIM_FRAMES
    if _OAK_ANIM_FRAMES is not None:
        return _OAK_ANIM_FRAMES
    
    frames = []
    base_path = os.path.join("Assets", "Animations")
    
    for i in range(1, 5):  # MasterOak1.png through MasterOak4.png
        path = os.path.join(base_path, f"MasterOak{i}.png")
        if not os.path.exists(path):
            print(f"⚠️ MasterOak{i}.png not found at {path}")
            continue
        try:
            frame = pygame.image.load(path).convert_alpha()
            # Scale up the frame to make it bigger and closer
            original_size = frame.get_size()
            scaled_size = (int(original_size[0] * _OAK_SCALE), int(original_size[1] * _OAK_SCALE))
            frame = pygame.transform.smoothscale(frame, scaled_size)
            frames.append(frame)
        except Exception as e:
            print(f"⚠️ Failed to load MasterOak{i}.png: {e}")
    
    if not frames:
        print("⚠️ No Master Oak animation frames found!")
        return None
    
    _OAK_ANIM_FRAMES = frames
    return frames

def _load_oak_idle() -> pygame.Surface | None:
    """Load Master Oak idle image (MasterOakIdle.png) and scale it."""
    global _OAK_IDLE_IMAGE
    if _OAK_IDLE_IMAGE is not None:
        return _OAK_IDLE_IMAGE
    
    base_path = os.path.join("Assets", "Animations")
    path = os.path.join(base_path, "MasterOakIdle.png")
    
    if not os.path.exists(path):
        print(f"⚠️ MasterOakIdle.png not found at {path}")
        return None
    
    try:
        idle_img = pygame.image.load(path).convert_alpha()
        # Scale up the idle image to match animation size
        original_size = idle_img.get_size()
        scaled_size = (int(original_size[0] * _OAK_SCALE), int(original_size[1] * _OAK_SCALE))
        idle_img = pygame.transform.smoothscale(idle_img, scaled_size)
        _OAK_IDLE_IMAGE = idle_img
        return idle_img
    except Exception as e:
        print(f"⚠️ Failed to load MasterOakIdle.png: {e}")
        return None

def _load_background() -> pygame.Surface | None:
    """Load the Master Oak Lab background."""
    global _BACKGROUND
    if _BACKGROUND is not None:
        return _BACKGROUND
    
    path = os.path.join("Assets", "Map", "MasterOakLab.png")
    if not os.path.exists(path):
        print(f"⚠️ MasterOakLab.png not found at {path}")
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

def _load_oak_voice_sfx() -> pygame.mixer.Sound | None:
    """Load the Oak voice sound effect."""
    global _OAK_VOICE_SFX
    if _OAK_VOICE_SFX is not None:
        return _OAK_VOICE_SFX
    
    path = os.path.join("Assets", "Music", "Sounds", "OakVoice.mp3")
    if not os.path.exists(path):
        print(f"⚠️ OakVoice.mp3 not found at {path}")
        return None
    
    try:
        _OAK_VOICE_SFX = pygame.mixer.Sound(path)
        return _OAK_VOICE_SFX
    except Exception as e:
        print(f"⚠️ Failed to load OakVoice.mp3: {e}")
        return None

def _load_oak_shut() -> pygame.Surface | None:
    """Load Master Oak shut image (MasterOakShut.png) and scale it."""
    global _OAK_SHUT_IMAGE
    if _OAK_SHUT_IMAGE is not None:
        return _OAK_SHUT_IMAGE
    
    base_path = os.path.join("Assets", "Animations")
    path = os.path.join(base_path, "MasterOakShut.png")
    
    if not os.path.exists(path):
        print(f"⚠️ MasterOakShut.png not found at {path}")
        return None
    
    try:
        shut_img = pygame.image.load(path).convert_alpha()
        # Scale up the shut image to match animation size
        original_size = shut_img.get_size()
        scaled_size = (int(original_size[0] * _OAK_SCALE), int(original_size[1] * _OAK_SCALE))
        shut_img = pygame.transform.smoothscale(shut_img, scaled_size)
        _OAK_SHUT_IMAGE = shut_img
        return shut_img
    except Exception as e:
        print(f"⚠️ Failed to load MasterOakShut.png: {e}")
        return None

def _load_book_shut_sfx() -> pygame.mixer.Sound | None:
    """Load the book shut sound effect."""
    global _BOOK_SHUT_SFX
    if _BOOK_SHUT_SFX is not None:
        return _BOOK_SHUT_SFX
    
    path = os.path.join("Assets", "Music", "Sounds", "BookShut.mp3")
    if not os.path.exists(path):
        print(f"⚠️ BookShut.mp3 not found at {path}")
        return None
    
    try:
        _BOOK_SHUT_SFX = pygame.mixer.Sound(path)
        return _BOOK_SHUT_SFX
    except Exception as e:
        print(f"⚠️ Failed to load BookShut.mp3: {e}")
        return None

def _load_oak_scroll_image() -> pygame.Surface | None:
    """Load Master Oak scroll image (MasterOakScroll.png) and scale it to match other Oak images."""
    global _OAK_SCROLL_IMAGE
    if _OAK_SCROLL_IMAGE is not None:
        return _OAK_SCROLL_IMAGE
    
    base_path = os.path.join("Assets", "Animations")
    path = os.path.join(base_path, "MasterOakScroll.png")
    
    if not os.path.exists(path):
        print(f"⚠️ MasterOakScroll.png not found at {path}")
        return None
    
    try:
        scroll_img = pygame.image.load(path).convert_alpha()
        # Scale to match other Master Oak images (using _OAK_SCALE = 1.8)
        original_size = scroll_img.get_size()
        scaled_size = (int(original_size[0] * _OAK_SCALE), int(original_size[1] * _OAK_SCALE))
        scroll_img = pygame.transform.smoothscale(scroll_img, scaled_size)
        _OAK_SCROLL_IMAGE = scroll_img
        return scroll_img
    except Exception as e:
        print(f"⚠️ Failed to load MasterOakScroll.png: {e}")
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
    """Draw the textbox with word-by-word typing effect."""
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

# ---------- Screen lifecycle ----------
def enter(gs, **_):
    """Initialize the Master Oak screen state."""
    if not hasattr(gs, "_master_oak_state"):
        gs._master_oak_state = {
            "current_section": 0,
            "typing_timer": 0.0,
            "text_displayed": "",
            "blink_t": 0.0,
            "sound_played": False,
        }
    
    # Reset state
    st = gs._master_oak_state
    st["current_section"] = 0
    st["typing_timer"] = 0.0
    st["text_displayed"] = ""
    st["blink_t"] = 0.0
    st["sound_played"] = False
    st["shut_timer"] = 0.0
    st["shut_phase"] = False  # True when showing shut image
    st["fade_alpha"] = 0.0  # Fade-to-black alpha (0-255)
    st["fade_speed"] = 0.0  # Fade speed (alpha per second)
    st["showing_scroll"] = False  # True when showing scroll image
    st["items_given"] = False  # Track if items have been given
    
    # Load animation frames and idle image
    frames = _load_oak_animation()
    if frames:
        # Create animator (8 fps, looping)
        gs._master_oak_anim = Animator(frames, fps=8, loop=True)
        # Reset animator so it starts from frame 0
        gs._master_oak_anim.reset()
    else:
        gs._master_oak_anim = None
    
    # Load idle image, shut image, and scroll image (will be used when text is fully displayed)
    _load_oak_idle()
    _load_oak_shut()
    _load_book_shut_sfx()
    _load_oak_scroll_image()

def draw(screen: pygame.Surface, gs, dt: float, **_):
    """Draw the Master Oak screen."""
    st = gs._master_oak_state
    blink_t = st["blink_t"]
    st["blink_t"] += dt
    
    # Handle shut phase (showing shut image, then fade to black)
    if st.get("shut_phase", False):
        # Draw background
        bg = _load_background()
        if bg:
            screen.blit(bg, (0, 0))
        else:
            screen.fill((20, 10, 10))
        
        # Update shut timer
        st["shut_timer"] += dt
        
        # Show shut image for 0.3 seconds
        if st["shut_timer"] < 0.3:
            shut_img = _load_oak_shut()
            if shut_img:
                shut_x = (S.LOGICAL_WIDTH - shut_img.get_width()) // 2
                shut_y = int(S.LOGICAL_HEIGHT * 0.15)
                screen.blit(shut_img, (shut_x, shut_y))
        else:
            # Start fade to black after 0.3 seconds
            if st["fade_speed"] == 0.0:
                # Initialize fade (fade over 1.5 seconds)
                st["fade_alpha"] = 0.0
                st["fade_speed"] = 255.0 / 1.5  # Reach 255 alpha over 1.5 seconds
            
            # Update fade
            st["fade_alpha"] = min(255.0, st["fade_alpha"] + st["fade_speed"] * dt)
            
            # Draw shut image (still visible during fade)
            shut_img = _load_oak_shut()
            if shut_img:
                shut_x = (S.LOGICAL_WIDTH - shut_img.get_width()) // 2
                shut_y = int(S.LOGICAL_HEIGHT * 0.15)
                screen.blit(shut_img, (shut_x, shut_y))
            
            # Draw fade overlay
            if st["fade_alpha"] > 0:
                fade_overlay = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT), pygame.SRCALPHA)
                fade_overlay.fill((0, 0, 0, int(st["fade_alpha"])))
                screen.blit(fade_overlay, (0, 0))
            
            # When fully faded, transition to black screen
            if st["fade_alpha"] >= 255.0:
                # Will transition in handle() function
                pass
        
        return
    
    # Normal text display phase
    # Draw background
    bg = _load_background()
    if bg:
        screen.blit(bg, (0, 0))
    else:
        screen.fill((20, 10, 10))
    
    if st["current_section"] < len(TEXT_SECTIONS):
        current_text = TEXT_SECTIONS[st["current_section"]].format(player_name=gs.player_name)
        
        # Play sound when starting a new section
        if not st["sound_played"]:
            sfx = _load_oak_voice_sfx()
            if sfx:
                audio_sys.play_sound(sfx)
            st["sound_played"] = True
            # Reset animation when starting new section
            if hasattr(gs, "_master_oak_anim") and gs._master_oak_anim:
                gs._master_oak_anim.reset()
        
        # Type text over 2 seconds
        typing_duration = 2.0
        st["typing_timer"] += dt
        
        # Only update animation while text is typing
        is_typing = st["typing_timer"] < typing_duration
        
        if is_typing:
            # Update animation while typing
            if hasattr(gs, "_master_oak_anim") and gs._master_oak_anim:
                gs._master_oak_anim.update(dt)
            # Calculate how many characters to show
            progress = st["typing_timer"] / typing_duration
            chars_to_show = int(len(current_text) * progress)
            st["text_displayed"] = current_text[:chars_to_show]
        else:
            # Text fully displayed
            st["text_displayed"] = current_text
            
            # Check if this is the items line (index 11) and text is fully displayed
            # If so, show scroll image and give items
            if st["current_section"] == 11 and not st.get("showing_scroll", False) and not st.get("items_given", False):
                # Give items to player
                if not hasattr(gs, "inventory"):
                    gs.inventory = {}
                if not isinstance(gs.inventory, dict):
                    gs.inventory = {}
                
                # Add scrolls of mending (5)
                gs.inventory["scroll_of_mending"] = gs.inventory.get("scroll_of_mending", 0) + 5
                # Add scrolls of command (5)
                gs.inventory["scroll_of_command"] = gs.inventory.get("scroll_of_command", 0) + 5
                # Add gold (10)
                gs.gold = getattr(gs, "gold", 0) + 10
                
                st["items_given"] = True
                st["showing_scroll"] = True
        
        # Draw Master Oak sprite
        # Check if we should show scroll image (items line, text fully displayed)
        should_show_scroll = (st["current_section"] == 11 and not is_typing and st.get("showing_scroll", False))
        
        if should_show_scroll:
            # Show scroll image when items line is done typing
            scroll_img = _load_oak_scroll_image()
            if scroll_img:
                scroll_x = (S.LOGICAL_WIDTH - scroll_img.get_width()) // 2
                scroll_y = int(S.LOGICAL_HEIGHT * 0.15)  # Same position as other images
                screen.blit(scroll_img, (scroll_x, scroll_y))
        elif is_typing and hasattr(gs, "_master_oak_anim") and gs._master_oak_anim:
            # Show talking animation while typing
            frame = gs._master_oak_anim.current()
            if frame:
                # Position: center horizontally, higher up on screen (more upright)
                frame_x = (S.LOGICAL_WIDTH - frame.get_width()) // 2
                frame_y = int(S.LOGICAL_HEIGHT * 0.15)  # Higher position, more upright
                screen.blit(frame, (frame_x, frame_y))
        else:
            # Show idle image when text is fully displayed (unless showing scroll)
            idle_img = _load_oak_idle()
            if idle_img:
                idle_x = (S.LOGICAL_WIDTH - idle_img.get_width()) // 2
                idle_y = int(S.LOGICAL_HEIGHT * 0.15)  # Same position as animation
                screen.blit(idle_img, (idle_x, idle_y))
            elif hasattr(gs, "_master_oak_anim") and gs._master_oak_anim:
                # Fallback to first frame of animation if idle not found
                frame = gs._master_oak_anim.frames[0] if gs._master_oak_anim.frames else None
                if frame:
                    frame_x = (S.LOGICAL_WIDTH - frame.get_width()) // 2
                    frame_y = int(S.LOGICAL_HEIGHT * 0.15)
                    screen.blit(frame, (frame_x, frame_y))
        
        # Draw textbox (always visible)
        _draw_textbox(screen, st["text_displayed"], dt, blink_t)

def handle(events, gs, dt: float, **_):
    """Handle events for the Master Oak screen."""
    st = gs._master_oak_state
    
    # Handle shut phase transition
    if st.get("shut_phase", False):
        # Wait for fade to complete, then transition
        if st.get("fade_alpha", 0.0) >= 255.0:
            return "BLACK_SCREEN"
        return None
    
    for event in events:
        if event.type == pygame.KEYDOWN:
            # Escape key skips the screen and goes directly to starter selection
            if event.key == pygame.K_ESCAPE:
                return "BLACK_SCREEN"
            
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                # If showing scroll (items line done), continue to next section (good luck)
                if st.get("showing_scroll", False) and st["current_section"] == 11:
                    st["showing_scroll"] = False
                    st["current_section"] += 1
                    st["typing_timer"] = 0.0
                    st["text_displayed"] = ""
                    st["sound_played"] = False
                # Only advance if text is fully displayed
                elif st["typing_timer"] >= 2.0:
                    # Check if this is the last section
                    if st["current_section"] >= len(TEXT_SECTIONS) - 1:
                        # Start shut phase
                        st["shut_phase"] = True
                        st["shut_timer"] = 0.0
                        st["fade_alpha"] = 0.0
                        st["fade_speed"] = 0.0
                        # Play book shut sound
                        sfx = _load_book_shut_sfx()
                        if sfx:
                            audio_sys.play_sound(sfx)
                    else:
                        st["current_section"] += 1
                        st["typing_timer"] = 0.0
                        st["text_displayed"] = ""
                        st["sound_played"] = False
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # If showing scroll (items line done), continue to next section (good luck)
            if st.get("showing_scroll", False) and st["current_section"] == 11:
                st["showing_scroll"] = False
                st["current_section"] += 1
                st["typing_timer"] = 0.0
                st["text_displayed"] = ""
                st["sound_played"] = False
            # Only advance if text is fully displayed
            elif st["typing_timer"] >= 2.0:
                # Check if this is the last section
                if st["current_section"] >= len(TEXT_SECTIONS) - 1:
                    # Start shut phase
                    st["shut_phase"] = True
                    st["shut_timer"] = 0.0
                    st["fade_alpha"] = 0.0
                    st["fade_speed"] = 0.0
                    # Play book shut sound
                    sfx = _load_book_shut_sfx()
                    if sfx:
                        audio_sys.play_sound(sfx)
                else:
                    st["current_section"] += 1
                    st["typing_timer"] = 0.0
                    st["text_displayed"] = ""
                    st["sound_played"] = False
    
    return None

