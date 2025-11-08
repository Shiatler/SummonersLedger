# =============================================================
# main.py — entry point / state machine (thin; screens split out)
# =============================================================

import os
import random
import glob
import re
import pygame
from pygame.math import Vector2

from combat import wild_vessel, summoner_battle, battle
import settings as S
from game_state import GameState


# systems & world
from world import assets, actors, world, procgen
from systems import save_system as saves, theme, ui, audio, party_ui
from systems import score_display, hud_buttons, currency_display, shop
from systems import rest_popup, bottom_right_hud, left_hud, buff_popup
from systems import coords  # Coordinate conversion utilities
from bootstrap.default_party import add_default_on_new_game   # ← add this
from bootstrap.default_inventory import add_default_inventory  # ← NEW



# ✅ rolling package
from rolling.roller import set_roll_callback
from rolling import ui as roll_ui      # <- UI popup helper
from rolling import roller             # <- the dice functions (roll_check, etc.)

from combat.btn import bag_action as bag_ui

from screens import party_manager, ledger
from screens import death_saves as death_saves_screen
from screens import death as death_screen
from screens import rest as rest_screen
from screens import book_of_bound, archives

# screens
from screens import (
    menu_screen, char_select, name_entry,
    black_screen, intro_video, settings_screen, pause_screen, master_oak
)

def _try_load(path: str | None):
    if not path:
        return None
    if os.path.exists(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"⚠️ load fail {path}: {e}")
    return None

from systems.asset_links import token_to_vessel, find_image

def _full_vessel_from_token_name(token_name: str | None) -> pygame.Surface | None:
    if not token_name:
        return None
    vessel_basename = token_to_vessel(token_name)  # FTokenBarbarian1 -> FVesselBarbarian1.png
    path = find_image(vessel_basename)
    if not path:
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        return img
    except Exception:
        return None


    base = os.path.splitext(os.path.basename(token_name))[0]  # strip .png if present
    # keep any trailing digits (…3, …12) on purpose

    if base.startswith("StarterToken"):
        body = base.replace("StarterToken", "", 1)
        return _try_load(os.path.join("Assets", "Starters", f"Starter{body}.png"))

    if base.startswith("MToken"):
        body = base.replace("MToken", "", 1)
        return _try_load(os.path.join("Assets", "VesselsMale", f"MVessel{body}.png"))

    if base.startswith("FToken"):
        body = base.replace("FToken", "", 1)
        return _try_load(os.path.join("Assets", "VesselsFemale", f"FVessel{body}.png"))

    if base.startswith("RToken"):
        body = base.replace("RToken", "", 1)
        # try exact, then strip digits fallback (RVesselWizard from RVesselWizard3)
        p1 = os.path.join("Assets", "RareVessels", f"RVessel{body}.png")
        img = _try_load(p1)
        if img:
            return img
        import re as _re
        m = _re.match(r"([A-Za-z]+)", body)
        if m:
            return _try_load(os.path.join("Assets", "RareVessels", f"RVessel{m.group(1)}.png"))

    # last-chance fallbacks: maybe they already provided a full-name filename
    for d in (
        os.path.join("Assets", "Starters"),
        os.path.join("Assets", "VesselsMale"),
        os.path.join("Assets", "VesselsFemale"),
        os.path.join("Assets", "RareVessels"),
    ):
        img = _try_load(os.path.join(d, f"{base}.png"))
        if img:
            return img

    return None


# ===================== Utilities / CWD =======================
def set_cwd():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))


# ===================== Mode Constants ========================
MODE_CHAR_SELECT  = "CHAR_SELECT"
MODE_SETTINGS     = "SETTINGS"
MODE_PAUSE        = "PAUSE"
MODE_NAME_ENTRY   = "NAME_ENTRY"
MODE_MASTER_OAK   = "MASTER_OAK"
MODE_BLACK_SCREEN = "BLACK_SCREEN"
MODE_INTRO_VIDEO  = "INTRO_VIDEO"
MODE_WILD_VESSEL = "WILD_VESSEL"
MODE_SUMMONER_BATTLE = "SUMMONER_BATTLE"
MODE_BATTLE = getattr(S, "MODE_BATTLE", "BATTLE")
MODE_DEATH_SAVES = getattr(S, "MODE_DEATH_SAVES", "DEATH_SAVES")
MODE_DEATH = getattr(S, "MODE_DEATH", "DEATH")
MODE_REST = "REST"
MODE_BOOK_OF_BOUND = "BOOK_OF_BOUND"
MODE_ARCHIVES = "ARCHIVES"




# music: post an event when a track finishes so we can pick the next
MUSIC_ENDEVENT = pygame.USEREVENT + 11


# ===================== Animator ==============================
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


# ===================== Fade Helpers ==========================
def start_fade_in(gs, seconds: float = 0.8):
    """Begin a fade-in from black over `seconds` seconds."""
    gs.fade_alpha = 255
    gs.fade_speed = 255.0 / max(0.001, seconds)  # alpha per second
    gs._fade_surface = None  # lazy-create the surface sized to screen

def update_and_draw_fade(screen, dt, gs):
    """Draw the black overlay while fading and advance the fade. Returns True if still fading."""
    if not hasattr(gs, "fade_alpha"):
        return False
    if gs.fade_alpha <= 0:
        return False

    # (re)create overlay if needed
    if gs._fade_surface is None or gs._fade_surface.get_size() != screen.get_size():
        gs._fade_surface = pygame.Surface(screen.get_size(), pygame.SRCALPHA)

    # update alpha
    gs.fade_alpha = max(0.0, gs.fade_alpha - gs.fade_speed * dt)

    # draw overlay
    overlay = gs._fade_surface
    overlay.fill((0, 0, 0, int(gs.fade_alpha)))
    screen.blit(overlay, (0, 0))

    # cleanup when done
    if gs.fade_alpha <= 0:
        try:
            del gs.fade_alpha
            del gs.fade_speed
        except Exception:
            pass
    return True


# =============== Load walk frames from individual files ======
def _load_walk_frames_from_files(variant_key: str, target_size: tuple[int, int]) -> list:
    """
    Looks for frames in Assets/PlayableCharacters using common names:
      - Mwalk1.png, Mwalk2.png, Mwalk3.png (male)
      - Fwalk1.png, Fwalk2.png, Fwalk3.png (female)
    Also accepts male_walk*.png, female_walk*.png, <variant>walk*.png, <variant>_walk*.png.
    """
    base = os.path.join("Assets", "PlayableCharacters")
    pats = []
    if variant_key.lower().startswith("m"):
        pats += ["Mwalk*.png", "male_walk*.png"]
    else:
        pats += ["Fwalk*.png", "female_walk*.png"]
    pats += [f"{variant_key}walk*.png", f"{variant_key}_walk*.png"]

    files = []
    for p in pats:
        files.extend(glob.glob(os.path.join(base, p)))

    # natural sort by trailing number
    def _num_key(path):
        m = re.search(r"(\d+)(?!.*\d)", os.path.basename(path))
        return int(m.group(1)) if m else 9999

    files = sorted(set(files), key=_num_key)

    frames = []
    for f in files:
        try:
            img = pygame.image.load(f).convert_alpha()
            img = pygame.transform.smoothscale(img, target_size)
            frames.append(img)
        except Exception as e:
            print(f"⚠️ Failed to load walk frame '{f}': {e}")

    if frames:
        print(f"🖼️ Loaded {len(frames)} walk frames for '{variant_key}' from {base}")
    return frames


# ===================== Helper Functions ======================
def apply_player_variant(gs, variant_key, variants_dict):
    img_raw = variants_dict.get(variant_key) or variants_dict.get("male")
    idle = pygame.transform.smoothscale(img_raw, S.PLAYER_SIZE)

    gs.player_gender = variant_key
    gs.player_idle   = idle
    gs.player_image  = idle
    gs.player_half   = Vector2(idle.get_width() / 2, idle.get_height() / 2)

    # load 3-frame walk animation from files
    walk_frames = _load_walk_frames_from_files(variant_key, S.PLAYER_SIZE)
    if not walk_frames:
        print("ℹ️ No separate walk frames found; using idle fallback.")
        walk_frames = [idle, idle, idle]

    gs.walk_anim = Animator(walk_frames, fps=8, loop=True)


def try_trigger_encounter(gs, summoners, merchant_frames):
    if gs.in_encounter:
        return
    if gs.distance_travelled >= gs.next_event_at:
        roll = random.random()
        
        # Guaranteed FIRST merchant after 3 encounters (only if first merchant hasn't spawned yet)
        force_first_merchant = not gs.first_merchant_spawned and gs.encounters_since_merchant >= 3
        
        # Debug output
        if force_first_merchant:
            print(f"🔔 Force merchant spawn triggered! encounters_since_merchant: {gs.encounters_since_merchant}, first_merchant_spawned: {gs.first_merchant_spawned}")
        
        if force_first_merchant and merchant_frames and len(merchant_frames) > 0:
            # Force first merchant spawn after 3 encounters
            print(f"✅ Forcing first merchant spawn after {gs.encounters_since_merchant} encounters")
            actors.spawn_merchant_ahead(gs, gs.start_x, merchant_frames)
            gs.first_merchant_spawned = True  # Mark first merchant as spawned
            gs.encounters_since_merchant = 0  # Reset counter (no longer needed)
        elif force_first_merchant:
            # Force check was true but merchant_frames is missing
            print(f"⚠️ Force merchant check passed but merchant_frames is missing! merchant_frames: {merchant_frames}")
        else:
            # Normal chance-based spawning
            # Merchant chance: 10% (configurable)
            merchant_chance = 0.10
            
            # Remaining 90% split using ENCOUNTER_WEIGHT_VESSEL (75% vessel, 25% summoner of the remaining)
            remaining_chance = 1.0 - merchant_chance  # 0.90
            vessel_chance = remaining_chance * S.ENCOUNTER_WEIGHT_VESSEL  # 0.90 * 0.75 = 0.675
            summoner_chance = remaining_chance * (1.0 - S.ENCOUNTER_WEIGHT_VESSEL)  # 0.90 * 0.25 = 0.225
            
            # Total percentages: Merchant 10%, Vessel 67.5%, Summoner 22.5%
            if merchant_frames and len(merchant_frames) > 0 and roll < merchant_chance:
                # Spawn merchant (0.0 to 0.10)
                actors.spawn_merchant_ahead(gs, gs.start_x, merchant_frames)
                if not gs.first_merchant_spawned:
                    gs.first_merchant_spawned = True  # Mark first merchant as spawned
                    gs.encounters_since_merchant = 0  # Reset counter (no longer needed)
            elif roll < merchant_chance + vessel_chance:
                # Spawn vessel (0.10 to 0.775)
                actors.spawn_vessel_shadow_ahead(gs, gs.start_x)
                if not gs.first_merchant_spawned:
                    gs.encounters_since_merchant += 1  # Only increment if first merchant not spawned yet
                    print(f"📊 Vessel spawned. encounters_since_merchant: {gs.encounters_since_merchant}")
            elif summoners:
                # Spawn summoner (0.775 to 1.0)
                actors.spawn_rival_ahead(gs, gs.start_x, summoners)
                if not gs.first_merchant_spawned:
                    gs.encounters_since_merchant += 1  # Only increment if first merchant not spawned yet
                    print(f"📊 Summoner spawned. encounters_since_merchant: {gs.encounters_since_merchant}")
            else:
                # Fallback to vessel if no summoners available
                actors.spawn_vessel_shadow_ahead(gs, gs.start_x)
                if not gs.first_merchant_spawned:
                    gs.encounters_since_merchant += 1  # Only increment if first merchant not spawned yet
                    print(f"📊 Fallback vessel spawned. encounters_since_merchant: {gs.encounters_since_merchant}")
        
        gs.next_event_at += random.randint(S.EVENT_MIN, S.EVENT_MAX)


# ===================== Encounter Popup =======================
def update_encounter_popup(screen, dt, gs, mist_frame, width, height, pg_instance=None):
    """
    Draws the encounter popup while freezing overworld movement.
    mist_frame: current animated mist frame surface (or None).
    """
    if not gs.in_encounter:
        return False

    gs.encounter_timer -= dt
    cam = world.get_camera_offset(gs.player_pos, width, height, gs.player_half)

    world.draw_repeating_road(screen, cam.x, cam.y)
    if pg_instance:
        pg_instance.update_needed(cam.y, height)
        pg_instance.draw_props(screen, cam.x, cam.y, width, height)

    # Draw any active vessels/rivals/merchants in the world behind the popup
    actors.draw_vessels(screen, cam, gs, mist_frame, S.DEBUG_OVERWORLD)
    actors.draw_rivals(screen, cam, gs)
    actors.draw_merchants(screen, cam, gs)

    # Player sprite
    screen.blit(
        gs.player_image,
        (gs.player_pos.x - cam.x - gs.player_half.x, gs.player_pos.y - cam.y - gs.player_half.y)
    )

    # Popup panel
    panel = pygame.Surface((440, 160), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 190))
    px, py = (width - 440) // 2, 40
    screen.blit(panel, (px, py))

    font = pygame.font.SysFont(None, 28)
    title = f"Encounter: {gs.encounter_name}"
    screen.blit(font.render(title, True, (230, 230, 230)), (px + 16, py + 12))

    if gs.encounter_sprite:
        screen.blit(gs.encounter_sprite, (px + 16, py + 48))

    if gs.encounter_timer <= 0:
        gs.in_encounter = False
        gs.encounter_name = ""
        gs.encounter_sprite = None
    return True


def draw_shop_ui(screen, gs):
    """Draw the shop UI."""
    shop.draw(screen, gs)


def draw_merchant_speech_bubble(screen, cam, gs, merchant):
    """Draw a speech bubble above the merchant saying 'Press E to shop' or similar medieval text."""
    if not merchant:
        return
    
    # Merchants are slightly bigger (1.2x player size)
    MERCHANT_SIZE_MULT = 1.2
    SIZE_W = int(S.PLAYER_SIZE[0] * MERCHANT_SIZE_MULT)
    SIZE_H = int(S.PLAYER_SIZE[1] * MERCHANT_SIZE_MULT)
    
    pos = merchant["pos"]
    screen_x = int(pos.x - cam.x)
    screen_y = int(pos.y - cam.y - SIZE_H // 2 - 40)  # Above merchant
    
    # Medieval-style text
    text = "Press E to trade"
    
    # Load DH font if available, fallback to default
    try:
        dh_font_path = os.path.join(S.ASSETS_FONTS_DIR, S.DND_FONT_FILE)
        if os.path.exists(dh_font_path):
            font = pygame.font.Font(dh_font_path, 20)
        else:
            font = pygame.font.SysFont(None, 20)
    except:
        font = pygame.font.SysFont(None, 20)
    
    text_surf = font.render(text, True, (255, 255, 255))
    text_rect = text_surf.get_rect()
    
    # Speech bubble background
    padding = 12
    bubble_w = text_rect.width + padding * 2
    bubble_h = text_rect.height + padding * 2
    bubble = pygame.Surface((bubble_w, bubble_h), pygame.SRCALPHA)
    
    # Draw bubble with rounded corners effect (using filled rect + border)
    bubble.fill((40, 35, 30, 240))  # Dark brown/medieval color
    pygame.draw.rect(bubble, (80, 70, 60, 255), bubble.get_rect(), 2)  # Border
    
    # Draw small triangle pointing down to merchant
    triangle_points = [
        (bubble_w // 2 - 8, bubble_h),
        (bubble_w // 2 + 8, bubble_h),
        (bubble_w // 2, bubble_h + 10),
    ]
    pygame.draw.polygon(bubble, (40, 35, 30, 240), triangle_points)
    pygame.draw.polygon(bubble, (80, 70, 60, 255), triangle_points, 2)
    
    bubble_x = screen_x - bubble_w // 2
    bubble_y = screen_y - bubble_h - 10
    
    screen.blit(bubble, (bubble_x, bubble_y))
    screen.blit(text_surf, (bubble_x + padding, bubble_y + padding))


def reset_run_state(gs):
    gs.in_encounter = False
    gs.encounter_timer = 0.0
    gs.encounter_name = ""
    gs.encounter_sprite = None
    gs.rivals_on_map.clear()
    gs.vessels_on_map.clear()
    if hasattr(gs, "merchants_on_map"):
        gs.merchants_on_map.clear()
    gs.distance_travelled = 0.0
    gs.next_event_at = S.FIRST_EVENT_AT


def start_new_game(gs):
    import random
    gs.player_pos = Vector2(S.WORLD_W // 2, S.WORLD_H - gs.player_half.y - 10)
    gs.start_x = gs.player_pos.x
    reset_run_state(gs)

    # NEW: fresh randomness for this run + clear any old party data
    gs.run_seed = random.getrandbits(32)   # 32-bit salt unique to this run
    gs.party_vessel_stats = [None] * 6
    gs.party_slots_names  = [None] * 6
    gs.party_slots        = [None] * 6
    gs.inventory = {}
    
    # Initialize currency (all start at 0)
    from systems import currency as currency_sys
    currency_sys.ensure_currency_fields(gs)
    # Starting gold: 10 gold pieces
    gs.gold = 10
    gs.silver = 0
    gs.bronze = 0
    
    # Reset first overworld blessing flag for new run
    gs.first_overworld_blessing_given = False


def continue_game(gs):
    start_new_game(gs)
    # NOTE: requires SUMMONER_SPRITES to be defined (built after assets.load_everything())
    if saves.load_game(gs, SUMMONER_SPRITES):
        apply_player_variant(gs, gs.player_gender, PLAYER_VARIANTS)
        gs.player_pos.x = gs.start_x
        gs.player_pos.y = max(gs.player_half.y, min(gs.player_pos.y, S.WORLD_H - gs.player_half.y))


# ===================== Mode Switch Helper ====================
def enter_mode(mode, gs, deps):
    """Call screen's enter() exactly once on mode change, if present."""
    if mode == S.MODE_MENU:
        menu_screen.enter(gs, **deps)
    elif mode == MODE_CHAR_SELECT:
        char_select.enter(gs, **deps)
    elif mode == MODE_NAME_ENTRY:
        name_entry.enter(gs, **deps)
    elif mode == MODE_MASTER_OAK:
        master_oak.enter(gs, **deps)
    elif mode == MODE_BLACK_SCREEN:
        black_screen.enter(gs, **deps)
    elif mode == MODE_INTRO_VIDEO:
        intro_video.enter(gs, **deps)
    elif mode == MODE_SETTINGS:
        settings_screen.enter(gs, **deps)
    elif mode == MODE_PAUSE:
        pause_screen.enter(gs, **deps)
    elif mode == MODE_WILD_VESSEL:
        wild_vessel.enter(gs, **deps)
    elif mode == MODE_SUMMONER_BATTLE:
        summoner_battle.enter(gs, **deps)
    elif mode == MODE_BATTLE:
        battle.enter(gs, **deps)
    elif mode == MODE_DEATH_SAVES:                           
        death_saves_screen.enter(gs, **deps)    
    elif mode == MODE_DEATH:
        death_screen.enter(gs, **deps) 
    elif mode == MODE_REST:
        rest_screen.enter(gs, **deps)
    elif mode == MODE_BOOK_OF_BOUND:
        # Note: enter() may already be called when mode is set (in button handler)
        # to capture previous screen for fade transition
        # Only call enter() here if not already called
        if not hasattr(gs, '_book_of_bound_entered'):
            book_of_bound.enter(gs, **deps)
            gs._book_of_bound_entered = True
    elif mode == MODE_ARCHIVES:
        if not hasattr(gs, '_archives_entered'):
            archives.enter(gs, **deps)
            gs._archives_entered = True
    elif mode == S.MODE_GAME:
        # gameplay has no dedicated enter; handled inline
        pass


# ===================== Main / Entrypoint =====================
if __name__ == "__main__":
    # -------- Init ----------
    set_cwd()
    pygame.init()

    audio.init_audio()
    AUDIO = audio.load_all()

    # 👇 make the bank globally visible to rolling/ui.py for dice SFX
    S.AUDIO_BANK = AUDIO

    # Fire an event when a music track ends (used for next-track shuffle)
    pygame.mixer.music.set_endevent(MUSIC_ENDEVENT)

    info = pygame.display.Info()
    
    # CRITICAL: Cache desktop resolution at startup (before any set_mode calls)
    # This is the ONLY reliable way to get the true desktop resolution
    # After set_mode with SCALED flag, Info().current_w/h can return wrong values
    # On Windows, try to get the actual desktop resolution using ctypes as a fallback
    global _cached_desktop_resolution
    
    # Try to get desktop resolution - if it looks suspiciously small, try Windows API
    desktop_w, desktop_h = info.current_w, info.current_h
    
    # If the resolution looks like it might be a window size (not a typical desktop size),
    # try to get the real desktop resolution using Windows API
    if desktop_w < 1280 or desktop_h < 720:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            desktop_w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            desktop_h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            print(f"🔍 Got desktop resolution via Windows API: {desktop_w}x{desktop_h}")
        except:
            print(f"⚠️ Could not get desktop resolution via Windows API, using Info(): {desktop_w}x{desktop_h}")
    
    _cached_desktop_resolution = (desktop_w, desktop_h)
    print(f"🔍 Cached desktop resolution at startup: {desktop_w}x{desktop_h}")
    
    # Minimum resolution check - use windowed mode if screen is too small
    MIN_WIDTH = 1280
    MIN_HEIGHT = 720
    
    screen_width = info.current_w
    screen_height = info.current_h
    
    # Determine if we should use fullscreen or windowed mode
    use_fullscreen = screen_width >= MIN_WIDTH and screen_height >= MIN_HEIGHT
    
    if use_fullscreen:
        # Fullscreen mode for screens that meet minimum requirements
        screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN | pygame.SCALED)
    else:
        # Windowed mode for smaller screens - scale window to fit
        # Calculate window size that maintains aspect ratio while fitting on screen
        scale = min(screen_width / S.LOGICAL_WIDTH, screen_height / S.LOGICAL_HEIGHT)
        window_width = int(S.LOGICAL_WIDTH * scale * 0.9)  # 90% of screen to leave some margin
        window_height = int(S.LOGICAL_HEIGHT * scale * 0.9)
        # Ensure minimum window size
        window_width = max(window_width, 960)
        window_height = max(window_height, 540)
        # Use SCALED flag for automatic scaling
        # Note: RESIZABLE flag is incompatible with SCALED in some Pygame versions
        # Window dragging should work by default without RESIZABLE flag
        screen = pygame.display.set_mode((window_width, window_height), pygame.SCALED)
        print(f"⚠️ Screen too small ({screen_width}x{screen_height}) - using windowed mode ({window_width}x{window_height})")
    
    pygame.display.set_caption(S.APP_NAME)
    
    # Get the ACTUAL physical size for coordinate calculations
    # CRITICAL: With SCALED flag, screen.get_size() might return logical resolution for fullscreen
    # For fullscreen, use cached desktop resolution (true physical size)
    # For windowed, use screen.get_size() (actual window size)
    if use_fullscreen:
        # Fullscreen: Use cached desktop resolution (true physical screen size)
        actual_width, actual_height = desktop_w, desktop_h
    else:
        # Windowed: Use actual window size from get_size()
        actual_width, actual_height = screen.get_size()
    
    S.WIDTH, S.HEIGHT = actual_width, actual_height
    
    clock = pygame.time.Clock()
    
    # Initialize coordinate conversion system with ACTUAL physical dimensions
    # For fullscreen, force scale to 1.0 if screen is >= 1920x1080
    if use_fullscreen and actual_width >= S.LOGICAL_WIDTH and actual_height >= S.LOGICAL_HEIGHT:
        coords.update_scale_factors(actual_width, actual_height, force_scale=1.0)
    else:
        coords.update_scale_factors(actual_width, actual_height)
    
    # Create virtual surface for rendering at logical resolution
    virtual_screen = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT))

    # -------- Theme & Assets ----------
    fonts = theme.load_fonts()
    menu_bg = theme.load_menu_bg()

    loaded = assets.load_everything()
    RIVAL_SUMMONERS = loaded["summoners"]
    VESSELS         = loaded["vessels"]
    RARE_VESSELS    = loaded["rare_vessels"]
    MIST_FRAMES     = loaded["mist_frames"]
    MERCHANT_FRAMES = loaded["merchant_frames"]
    
    # Debug: Check if merchant frames loaded
    if MERCHANT_FRAMES:
        print(f"✅ Loaded {len(MERCHANT_FRAMES)} merchant animation frames")
    else:
        print("⚠️ No merchant frames loaded - check Assets/Animations/Merchant1-5.png")

    # Map summoner names -> surfaces for save/load rehydration
    SUMMONER_SPRITES = {name: surf for (name, surf) in RIVAL_SUMMONERS}

    # Create a global animator for the hovering mist (looping)
    MIST_ANIM = Animator(MIST_FRAMES, fps=8, loop=True) if MIST_FRAMES else None

    PLAYER_VARIANTS = assets.load_player_variants()
    world.load_road()
    pg = procgen.ProcGen(rng_seed=42)

    # -------- GameState ----------
    gs = GameState(
        player_pos=Vector2(S.WORLD_W // 2, S.WORLD_H - 64),
        player_speed=S.PLAYER_SPEED,
        start_x=S.WORLD_W // 2,
    )
    apply_player_variant(gs, "male", PLAYER_VARIANTS)

    # portrait token for current gender
    gs.player_token = party_ui.load_player_token(gs.player_gender)

    # ensure HUD party slots exist & track filenames for save/load
    if not getattr(gs, "party_slots", None):
        gs.party_slots = [None] * 6
    if not getattr(gs, "party_slots_names", None):
        gs.party_slots_names = [None] * 6

    start_new_game(gs)
    
    # Initialize Book of the Bound discovered vessels (persistent across games)
    # This should NOT be reset by start_new_game - it persists across all games
    if not hasattr(gs, "book_of_bound_discovered"):
        gs.book_of_bound_discovered = set()

    # ensure slot stats list exists (JSON-serializable dicts per slot)
    if not getattr(gs, "party_vessel_stats", None):
        gs.party_vessel_stats = [None] * 6

    # -------- Loop State ----------
mode = S.MODE_MENU
prev_mode = None
running = True
settings_return_to = S.MODE_MENU  # used inside settings screen; kept for parity
is_fullscreen = use_fullscreen  # Track fullscreen state for toggle
display_mode = "fullscreen" if use_fullscreen else "windowed"  # Track display mode: "fullscreen", "windowed", "borderless"
# Cache the desktop resolution when entering fullscreen (Info().current_w/h can be unreliable with SCALED flag)
_cached_desktop_resolution = None

# Safety: make sure a display surface exists before we enter the loop
assert pygame.display.get_surface() is not None, "Display not created before main loop"

# ===================== Display Mode Functions ==========================
def change_display_mode(mode_name: str, screen_ref) -> pygame.Surface:
    """
    Change the display mode. Returns the new screen surface.
    Modes: "fullscreen", "windowed", "borderless"
    """
    global display_mode, is_fullscreen
    
    print(f"🔄 change_display_mode called with mode: '{mode_name}'")
    print(f"   OLD display_mode was: '{display_mode}'")
    display_mode = mode_name
    print(f"   NEW display_mode is: '{display_mode}'")
    
    # Get current desktop resolution for reference
    # CRITICAL: Always use the cached desktop resolution from startup
    # Info().current_w/h is unreliable after set_mode with SCALED flag
    global _cached_desktop_resolution
    
    if _cached_desktop_resolution is None:
        # Fallback: should never happen, but just in case
        info = pygame.display.Info()
        desktop_w, desktop_h = info.current_w, info.current_h
        _cached_desktop_resolution = (desktop_w, desktop_h)
    else:
        # Use cached value from startup (most reliable)
        desktop_w, desktop_h = _cached_desktop_resolution
    
    if mode_name == "fullscreen":
        is_fullscreen = True
        # CRITICAL: For fullscreen, we need the ACTUAL physical screen size, not logical
        # The SCALED flag will handle scaling, but we need to know the real screen size for coordinate calculations
        # Use desktop resolution for fullscreen - this is the actual physical screen size
        new_screen = pygame.display.set_mode((desktop_w, desktop_h), pygame.FULLSCREEN | pygame.SCALED)
        # The actual surface size after SCALED might be different, but the physical screen is desktop_w x desktop_h
        actual_physical_width, actual_physical_height = desktop_w, desktop_h
    elif mode_name == "borderless":
        is_fullscreen = True
        # Same as fullscreen - use desktop resolution
        # CACHE IT: Info().current_w/h can return wrong values after set_mode with SCALED flag
        _cached_desktop_resolution = (desktop_w, desktop_h)
        new_screen = pygame.display.set_mode((desktop_w, desktop_h), pygame.NOFRAME | pygame.SCALED)
        actual_physical_width, actual_physical_height = desktop_w, desktop_h
    else:  # windowed
        is_fullscreen = False
        # Calculate windowed size based on desktop, but make it smaller
        scale = min(desktop_w / S.LOGICAL_WIDTH, desktop_h / S.LOGICAL_HEIGHT)
        window_width = int(S.LOGICAL_WIDTH * scale * 0.9)
        window_height = int(S.LOGICAL_HEIGHT * scale * 0.9)
        window_width = max(window_width, 960)
        window_height = max(window_height, 540)
        # Use SCALED flag for automatic scaling
        # Note: RESIZABLE flag is incompatible with SCALED in some Pygame versions
        # Window dragging should work by default without RESIZABLE flag
        new_screen = pygame.display.set_mode((window_width, window_height), pygame.SCALED)
        # For windowed, the actual window size is what we requested
        actual_physical_width, actual_physical_height = window_width, window_height
    
    # CRITICAL: When using SCALED flag, pygame's get_size() returns the SURFACE size,
    # which might be the logical resolution (1920x1080) or the requested size,
    # NOT necessarily the actual physical screen/window size.
    # 
    # For coordinate calculations, we need the PHYSICAL screen size (what the user sees),
    # not the surface size. The SCALED flag handles the scaling internally.
    
    # Get surface size (what pygame thinks the surface is)
    surface_size = new_screen.get_size()
    
    # For coordinate system, we MUST use the actual physical screen/window size
    # This is what we requested (desktop_w/desktop_h for fullscreen, window size for windowed)
    # The SCALED flag will scale the surface to fit the physical size automatically
    actual_width, actual_height = actual_physical_width, actual_physical_height
    
    # Debug: Check if surface size differs from physical size
    if surface_size != (actual_width, actual_height):
        print(f"⚠️ SCALED flag detected: Surface size={surface_size}, Physical size={actual_width}x{actual_height}")
        print(f"   Using physical size for coordinate calculations")
    
    # Update global screen dimensions with PHYSICAL size (not surface size)
    S.WIDTH, S.HEIGHT = actual_width, actual_height
    
    # Update coordinate system with ACTUAL surface dimensions
    # This ensures all coordinate conversions work correctly after mode change
    # For fullscreen, force scale to 1.0 (user requested)
    if mode_name == "fullscreen" or mode_name == "borderless":
        coords.update_scale_factors(actual_width, actual_height, force_scale=1.0)
    else:
        coords.update_scale_factors(actual_width, actual_height)
    
    # Debug output to verify
    scale = coords.get_scale()
    offset_x, offset_y = coords.get_offset()
    print(f"🔧 Display mode changed to {mode_name}:")
    print(f"   Screen size = {actual_width}x{actual_height}")
    print(f"   Scale = {scale:.3f}")
    print(f"   Offset = ({offset_x:.1f}, {offset_y:.1f})")
    print(f"   Scaled virtual size = {int(S.LOGICAL_WIDTH * scale)}x{int(S.LOGICAL_HEIGHT * scale)}")
    
    return new_screen

def get_display_mode() -> str:
    """Get current display mode."""
    return display_mode

# ===================== Main Loop ==========================
# Track last screen size for debugging
_last_blit_size = None

def blit_virtual_to_screen(virtual_screen, screen):
    """Scale and blit the virtual screen to the actual screen."""
    global _last_blit_size, display_mode
    
    # CRITICAL: When using SCALED flag, pygame's get_size() returns the SURFACE size,
    # which might be the logical resolution (1920x1080), NOT the physical screen size.
    # For coordinate calculations and scaling, we MUST use the PHYSICAL screen size.
    
    # Get the current surface
    current_surface = pygame.display.get_surface()
    if current_surface is None:
        current_surface = screen
    
    # Get surface size (might be logical resolution due to SCALED flag)
    surface_size = current_surface.get_size()
    
    # Get physical screen size from display info
    info = pygame.display.Info()
    physical_width, physical_height = info.current_w, info.current_h
    
    # CRITICAL FIX: Determine correct screen size
    # With SCALED flag:
    # - Fullscreen: surface.get_size() = logical (1920x1080), physical = desktop resolution  
    # - Windowed: surface.get_size() = actual window size (e.g., 1728x972)
    
    # CRITICAL DETECTION: Determine if we're in fullscreen
    # Method 1: Check display_mode variable (set by change_display_mode)
    # Method 2: Check if surface size equals logical AND physical is larger (SCALED fullscreen behavior)
    
    surface_is_logical = (surface_size == (S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT))
    physical_is_larger = (physical_width > surface_size[0] + 50 or physical_height > surface_size[1] + 50)
    
    # SIMPLE FIX: If display_mode says fullscreen, ALWAYS use physical screen size
    # No complex detection - just trust the display_mode variable
    if display_mode == "fullscreen" or display_mode == "borderless":
        # Fullscreen: ALWAYS use physical screen size (desktop resolution)
        # CRITICAL: Make absolutely sure we're using physical size
        if physical_width < S.LOGICAL_WIDTH or physical_height < S.LOGICAL_HEIGHT:
            print(f"⚠️ Physical screen {physical_width}x{physical_height} < logical {S.LOGICAL_WIDTH}x{S.LOGICAL_HEIGHT}")
            print(f"   This is unusual - physical screen should be >= 1920x1080")
        screen_width, screen_height = physical_width, physical_height
        is_fullscreen = True
        if _last_blit_size != (screen_width, screen_height):
            print(f"✅ Fullscreen: Using physical size {screen_width}x{screen_height}")
    else:
        # Windowed: CRITICAL - Use S.WIDTH/HEIGHT which are set correctly in change_display_mode
        # Don't trust surface_size - with SCALED flag it might be wrong
        # S.WIDTH/HEIGHT are guaranteed to be the actual window size
        screen_width, screen_height = S.WIDTH, S.HEIGHT
        is_fullscreen = False
        # Double-check: If S.WIDTH/HEIGHT seem wrong (e.g., match logical resolution), use surface_size as fallback
        if screen_width == S.LOGICAL_WIDTH and screen_height == S.LOGICAL_HEIGHT:
            # This shouldn't happen, but if it does, use surface_size
            print(f"⚠️ S.WIDTH/HEIGHT match logical resolution in windowed mode, using surface_size as fallback")
            screen_width, screen_height = surface_size
            S.WIDTH, S.HEIGHT = screen_width, screen_height
    
    # Debug: Print if size changed (only once per size change)
    if _last_blit_size != (screen_width, screen_height):
        print(f"📐 ===== SCREEN SIZE UPDATE =====")
        print(f"   display_mode variable: '{display_mode}'")
        print(f"   Fullscreen detected: {is_fullscreen}")
        print(f"   Surface size (from get_size()): {surface_size}")
        print(f"   Physical size (from Info): {physical_width}x{physical_height}")
        print(f"   Using size for calculations: {screen_width}x{screen_height}")
        print(f"   S.WIDTH/HEIGHT: {S.WIDTH}x{S.HEIGHT}")
        _last_blit_size = (screen_width, screen_height)
    
    # Recalculate scale factors based on ACTUAL screen size (critical for mode changes)
    # This ensures coordinate system is always in sync with actual screen
    # For fullscreen, force scale to 1.0 (user requested) ONLY if screen is >= 1920x1080
    if is_fullscreen:
        # CRITICAL: For fullscreen, we MUST use physical screen size, not surface size
        # Use cached desktop resolution (Info().current_w/h can be unreliable with SCALED flag)
        global _cached_desktop_resolution
        if _cached_desktop_resolution:
            cached_w, cached_h = _cached_desktop_resolution
            screen_width, screen_height = cached_w, cached_h
            S.WIDTH, S.HEIGHT = screen_width, screen_height
        else:
            # Fallback: use Info() if cache not available
            fresh_info = pygame.display.Info()
            screen_width, screen_height = fresh_info.current_w, fresh_info.current_h
            S.WIDTH, S.HEIGHT = screen_width, screen_height
        
        # Debug: Log what we're using
        if hasattr(blit_virtual_to_screen, '_last_fullscreen_size'):
            if blit_virtual_to_screen._last_fullscreen_size != (screen_width, screen_height):
                print(f"🔍 Fullscreen: Fresh physical size = {screen_width}x{screen_height}")
                print(f"   Old physical size was = {physical_width}x{physical_height}")
                print(f"   Surface size = {surface_size}")
                blit_virtual_to_screen._last_fullscreen_size = (screen_width, screen_height)
        else:
            blit_virtual_to_screen._last_fullscreen_size = (screen_width, screen_height)
            print(f"🔍 Fullscreen: Using fresh physical size {screen_width}x{screen_height}")
        
        # CRITICAL: For fullscreen with scale 1.0, screen MUST be >= 1920x1080
        # If screen is smaller, we can't use scale 1.0 (content would be cut off)
        if screen_width >= S.LOGICAL_WIDTH and screen_height >= S.LOGICAL_HEIGHT:
            # Screen is large enough - use scale 1.0
            coords.update_scale_factors(screen_width, screen_height, force_scale=1.0)
        else:
            # Screen is too small - calculate scale normally (shouldn't happen in fullscreen)
            print(f"⚠️ Fullscreen but screen {screen_width}x{screen_height} < logical {S.LOGICAL_WIDTH}x{S.LOGICAL_HEIGHT}")
            print(f"   Calculating scale instead of forcing 1.0")
            coords.update_scale_factors(screen_width, screen_height)
    else:
        coords.update_scale_factors(screen_width, screen_height)
    
    # Get scale and offset from coordinate system
    scale = coords.get_scale()
    offset_x, offset_y = coords.get_offset()
    
    # Scale the virtual screen to fit the actual screen
    scaled_width = int(S.LOGICAL_WIDTH * scale)
    scaled_height = int(S.LOGICAL_HEIGHT * scale)
    
    # Ensure we don't get zero or negative sizes
    scaled_width = max(1, scaled_width)
    scaled_height = max(1, scaled_height)
    
    scaled_surface = pygame.transform.smoothscale(virtual_screen, (scaled_width, scaled_height))
    
    # Clear the CURRENT surface and blit scaled surface centered
    # Always use current_surface, not the stale 'screen' parameter
    current_surface.fill((0, 0, 0))
    current_surface.blit(scaled_surface, (int(offset_x), int(offset_y)))

while running:
    dt = clock.tick(60) / 1000.0
    events = pygame.event.get()
    
    # Clear virtual screen at the start of each frame to prevent content bleeding between modes
    virtual_screen.fill((0, 0, 0))
    
    # Handle fullscreen toggle (Alt+Enter) - remove from events list after processing
    events_to_remove = []
    for i, e in enumerate(events):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_RETURN and (e.mod & pygame.KMOD_ALT):
                # Toggle fullscreen/windowed
                current = display_mode
                if current == "fullscreen":
                    screen = change_display_mode("windowed", screen)
                elif current == "borderless":
                    screen = change_display_mode("windowed", screen)
                else:  # windowed
                    screen = change_display_mode("fullscreen", screen)
                events_to_remove.append(i)
    
    # Remove fullscreen toggle events from events list
    events = [e for i, e in enumerate(events) if i not in events_to_remove]
    
    # Handle window resize events (only in windowed mode)
    for e in events:
        if e.type == pygame.VIDEORESIZE:
            # Window was resized - update dimensions
            if display_mode == "windowed":
                new_width, new_height = e.size
                print(f"🔄 Window resized to {new_width}x{new_height}")
                S.WIDTH, S.HEIGHT = new_width, new_height
                coords.update_scale_factors(new_width, new_height)
                # Force screen refresh by updating the global screen reference
                screen = pygame.display.get_surface()
    
    # Convert mouse coordinates in events to logical coordinates
    converted_events = []
    for e in events:
        if hasattr(e, 'pos') and e.pos is not None:
            # Create a new event with converted coordinates
            new_e = pygame.event.Event(e.type, e.dict)
            new_e.pos = coords.screen_to_logical(e.pos)
            converted_events.append(new_e)
        else:
            converted_events.append(e)
    events = converted_events

    # ========== Mode transitions: high-level music =========
    if mode != prev_mode:
        # per-mode music
        if mode == S.MODE_MENU:
            audio.play_music(AUDIO, "MainMenu")
        elif mode == MODE_CHAR_SELECT:
            audio.play_music(AUDIO, "CharacterSelect")
        elif mode == S.MODE_GAME:
            audio.stop_music()
            gs.overworld_music_started = False
        elif mode == MODE_DEATH:
            audio.stop_music()

        # ensure chosen gender actually updates the player before Name Entry uses it
        if mode == MODE_NAME_ENTRY and getattr(gs, "chosen_gender", None):
            apply_player_variant(gs, gs.chosen_gender, PLAYER_VARIANTS)
            # keep HUD portrait in sync too
            gs.player_token = party_ui.load_player_token(gs.player_gender)

        # call the screen's enter() hook (no 'screen' in deps)
        deps = dict(
            fonts=fonts,
            menu_bg=menu_bg,
            audio_bank=AUDIO,
            player_variants=PLAYER_VARIANTS,  # pass variants to screens
        )
        enter_mode(mode, gs, deps)
        prev_mode = mode

    # Build a shared deps dict each frame (for screens that need these)
    def change_display_mode_callback(mode_name: str):
        """Callback for settings screen to change display mode."""
        global screen, prev_mode, display_mode
        
        # Change display mode - this creates a new surface and sets S.WIDTH/HEIGHT correctly
        new_screen = change_display_mode(mode_name, screen)
        
        # CRITICAL: Always get the actual current display surface from pygame
        current_surface = pygame.display.get_surface()
        if current_surface is not None:
            screen = current_surface
        
        # CRITICAL: For fullscreen, we MUST use physical screen size, not surface size
        # change_display_mode() should have set S.WIDTH/HEIGHT correctly, but verify
        info = pygame.display.Info()
        physical_w, physical_h = info.current_w, info.current_h
        
        if mode_name == "fullscreen" or mode_name == "borderless":
            # For fullscreen: Use physical screen size (desktop resolution)
            actual_w, actual_h = physical_w, physical_h
            print(f"✅ Fullscreen mode: Using physical size {actual_w}x{actual_h}")
        else:
            # For windowed: Use what change_display_mode set (should be window size)
            actual_w, actual_h = S.WIDTH, S.HEIGHT
            print(f"✅ Windowed mode: Using size {actual_w}x{actual_h}")
        
        # Update S.WIDTH/HEIGHT to ensure they're correct
        S.WIDTH, S.HEIGHT = actual_w, actual_h
        
        # Update coordinate system with correct size
        # For fullscreen, force scale to 1.0 (user requested)
        if mode_name == "fullscreen" or mode_name == "borderless":
            coords.update_scale_factors(actual_w, actual_h, force_scale=1.0)
        else:
            coords.update_scale_factors(actual_w, actual_h)
        print(f"   Final scale: {coords.get_scale():.3f}, Offset: {coords.get_offset()}")
        
        # Force a refresh of the current screen by triggering its enter() function
        # This ensures all screens that cache positions/sizes refresh with new dimensions
        if mode:  # Only if we're in a mode
            current_deps = dict(
                fonts=fonts,
                menu_bg=menu_bg,
                audio_bank=AUDIO,
                player_variants=PLAYER_VARIANTS,
            )
            # Temporarily set prev_mode to None to force enter() to run
            saved_prev = prev_mode
            prev_mode = None
            enter_mode(mode, gs, current_deps)
            prev_mode = saved_prev
        return screen
    
    deps = dict(
        fonts=fonts,
        menu_bg=menu_bg,
        audio_bank=AUDIO,
        player_variants=PLAYER_VARIANTS,
        change_display_mode=change_display_mode_callback,
        get_display_mode=get_display_mode,
    )

    # ========== Universal window close ==========
    for e in events:
        if e.type == pygame.QUIT:
            saves.save_game(gs)
            running = False

    # ===================== MENU ============================
    if mode == S.MODE_MENU:
        next_mode = menu_screen.handle(events, gs, **deps, can_continue=saves.has_save())
        menu_screen.draw(virtual_screen, gs, **deps, can_continue=saves.has_save())
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== CHARACTER SELECT ================
    elif mode == MODE_CHAR_SELECT:
        next_mode = char_select.handle(events, gs, **deps)
        char_select.draw(virtual_screen, gs, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== NAME ENTRY ======================
    elif mode == MODE_NAME_ENTRY:
        next_mode = name_entry.handle(events, gs, dt, **deps)
        name_entry.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== MASTER OAK ======================
    elif mode == MODE_MASTER_OAK:
        next_mode = master_oak.handle(events, gs, dt, **deps)
        master_oak.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            if next_mode == MODE_BLACK_SCREEN:
                start_new_game(gs)
                from systems import save_system as saves
                saves.delete_save()  # ensure truly fresh run

                from bootstrap.default_party import add_default_on_new_game
                add_default_on_new_game(gs)

                from bootstrap.default_inventory import add_default_inventory
                add_default_inventory(gs)

                try:
                    pygame.mixer.music.fadeout(120)
                except Exception:
                    pass
            mode = next_mode

    # ===================== BLACK SCREEN ====================
    elif mode == MODE_BLACK_SCREEN:
        next_mode = black_screen.handle(events, gs, **deps, saves=saves)
        black_screen.draw(virtual_screen, gs, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            mode = next_mode

    # ===================== INTRO VIDEO =====================
    elif mode == MODE_INTRO_VIDEO:
        next_mode = intro_video.handle(events, gs, dt, **deps)
        intro_video.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            if next_mode == S.MODE_GAME:
                start_fade_in(gs, 0.8)
            mode = next_mode

    # ===================== SETTINGS ========================
    elif mode == MODE_SETTINGS:
        next_mode = settings_screen.handle(events, gs, **deps)
        settings_screen.draw(virtual_screen, gs, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== PAUSE ===========================
    elif mode == MODE_PAUSE:
        next_mode = pause_screen.handle(events, gs, **deps)
        pause_screen.draw(virtual_screen, gs, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            mode = next_mode
    
    # ===================== SUMMONER BATTLE =====================
    elif mode == MODE_SUMMONER_BATTLE:
        next_mode = summoner_battle.handle(events, gs, dt, **deps)
        summoner_battle.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            mode = next_mode


    # ===================== WILD VESSEL =====================
    elif mode == MODE_WILD_VESSEL:
        next_mode = wild_vessel.handle(events, gs, **deps)
        wild_vessel.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            mode = next_mode  # ESC returns to overworld

    # ===================== Battle ==========================
    elif mode == MODE_BATTLE:
        next_mode = battle.handle(events, gs, dt, **deps)
        battle.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            mode = next_mode
    
    # ===================== Death Saves ==========================
    elif mode == MODE_DEATH_SAVES:
        next_mode = death_saves_screen.handle(events, gs, **deps)
        death_saves_screen.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            mode = next_mode


    # ===================== Death ==========================   
    elif mode == MODE_DEATH:
        next_mode = death_screen.handle(events, gs, **deps)
        death_screen.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== Rest ==========================
    elif mode == MODE_REST:
        next_mode = rest_screen.handle(events, gs, dt, **deps)
        rest_screen.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            if next_mode == "GAME":
                # Ensure campfire sound is stopped before returning to game
                # Use the rest screen's stop function for reliability
                try:
                    from screens import rest as rest_module
                    if hasattr(gs, "_rest_state"):
                        rest_module._stop_campfire_sound(gs._rest_state)
                except Exception as e:
                    print(f"⚠️ Error stopping campfire sound: {e}")
                    # Fallback: try to stop manually
                    if hasattr(gs, "_rest_state") and gs._rest_state.get("campfire_channel"):
                        try:
                            gs._rest_state["campfire_channel"].stop()
                        except:
                            pass
                        gs._rest_state["campfire_channel"] = None
                
                mode = S.MODE_GAME
                # Restart overworld music
                if hasattr(gs, "last_overworld_track"):
                    nxt = audio.pick_next_track(AUDIO, gs.last_overworld_track, prefix="music")
                else:
                    nxt = audio.pick_next_track(AUDIO, None, prefix="music")
                if nxt:
                    audio.play_music(AUDIO, nxt, loop=False, fade_ms=600)
                    gs.last_overworld_track = nxt
            else:
                mode = next_mode

    # ===================== Book of the Bound ==========================
    elif mode == MODE_BOOK_OF_BOUND:
        next_mode = book_of_bound.handle(events, gs, dt, **deps)
        book_of_bound.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            # Clear the entered flag when exiting
            if hasattr(gs, '_book_of_bound_entered'):
                delattr(gs, '_book_of_bound_entered')
            mode = next_mode
    elif mode == MODE_ARCHIVES:
        # Handle party manager events if it's open (for vessel picker)
        try:
            from screens import party_manager
            if party_manager.is_open():
                for e in events:
                    party_manager.handle_event(e, gs)
        except Exception:
            pass
        
        next_mode = archives.handle(gs, events, dt, **deps)
        archives.draw(virtual_screen, gs, dt)
        
        # Draw party manager on top if open
        try:
            from screens import party_manager
            if party_manager.is_open():
                party_manager.draw(virtual_screen, gs, dt)
        except Exception:
            pass
        
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
        if next_mode:
            # Clear the entered flag when exiting
            if hasattr(gs, '_archives_entered'):
                delattr(gs, '_archives_entered')
            mode = next_mode
            continue  # Skip to next iteration to process mode change


    # ===================== GAMEPLAY ========================
    elif mode == S.MODE_GAME:
        # ===== First overworld blessing check =====
        # Check if we should give a blessing when first entering overworld this run
        # Only check if buff popup is not already active and no blessing is pending
        if (not getattr(gs, "first_overworld_blessing_given", False) 
            and not buff_popup.is_active() 
            and not getattr(gs, "pending_buff_selection", False)):
            # 100% chance for testing (change to 0.1 for 10% later)
            import random
            trigger_buff = True  # random.random() < 1.0  # 100% for testing
            if trigger_buff:
                # Set flag to start buff popup in overworld
                gs.pending_buff_selection = True
                gs.first_overworld_blessing_given = True
                print(f"🎁 First overworld blessing triggered!")
        
        # ===== Death gate: only when we actually have a party and none are alive =====
        stats = getattr(gs, "party_vessel_stats", None) or []
        has_any_member = any(isinstance(st, dict) for st in stats)
        has_living = any(
            isinstance(st, dict) and int(st.get("current_hp", st.get("hp", 0)) or 0) > 0
            for st in stats
        )
        if has_any_member and not has_living:
            mode = MODE_DEATH_SAVES
            enter_mode(mode, gs, deps)
            # Draw once to avoid a 1-frame flash of overworld under black
            death_saves_screen.draw(virtual_screen, gs, dt, **deps)
            blit_virtual_to_screen(virtual_screen, screen)
            pygame.display.flip()
            continue


        
        # --- Snapshots for this frame (used to suppress ESC->Pause) ---
        bag_open_at_frame_start = bag_ui.is_open()
        modal_open_at_frame_start = (
            bag_ui.is_open() or party_manager.is_open() or ledger.is_open() or gs.shop_open or currency_display.is_open() or rest_popup.is_open()
        )

        just_toggled_pm = False
        just_toggled_bag = False
        just_opened_ledger = False  # suppress first click that opened it

        # Track HUD button clicks to prevent event propagation
        hud_button_click_positions = set()

        # --- Handle HUD button clicks FIRST (before other UI) ---
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # Convert click position to logical coordinates (button rects are in logical coords)
                logical_pos = coords.screen_to_logical(e.pos)
                button_clicked = hud_buttons.handle_click(logical_pos)
                if button_clicked == 'bag':
                    bag_ui.toggle_popup()
                    just_toggled_bag = True
                    hud_button_click_positions.add(e.pos)
                    audio.play_click(AUDIO)
                elif button_clicked == 'party':
                    if not bag_ui.is_open() and not ledger.is_open():
                        party_manager.toggle()
                        just_toggled_pm = True
                        hud_button_click_positions.add(e.pos)
                        audio.play_click(AUDIO)
                elif button_clicked == 'currency':
                    if not currency_display.is_open() and not bag_ui.is_open() and not party_manager.is_open() and not ledger.is_open():
                        currency_display.toggle()
                        # Play Coin.mp3 sound
                        coin_sound = AUDIO.sfx.get("Coin") or AUDIO.sfx.get("coin")
                        if coin_sound:
                            coin_sound.play()
                        else:
                            # Try to load from the path
                            coin_path = os.path.join("Assets", "Music", "Sounds", "Coin.mp3")
                            if os.path.exists(coin_path):
                                try:
                                    coin_sfx = pygame.mixer.Sound(coin_path)
                                    coin_sfx.play()
                                except:
                                    pass
                    elif currency_display.is_open():
                        currency_display.close()
                    hud_button_click_positions.add(e.pos)
                elif button_clicked == 'rest':
                    if not bag_ui.is_open() and not party_manager.is_open() and not ledger.is_open() and not currency_display.is_open() and not gs.shop_open and not rest_popup.is_open():
                        rest_popup.open_popup()
                        hud_button_click_positions.add(e.pos)
                        audio.play_click(AUDIO)
                elif button_clicked == 'book_of_bound':
                    # Switch to Book of the Bound screen
                    # Capture current screen for fade transition
                    previous_screen = virtual_screen.copy()
                    mode = MODE_BOOK_OF_BOUND
                    # Pass previous screen to enter() for fade transition
                    book_of_bound.enter(gs, previous_screen_surface=previous_screen, **deps)
                    gs._book_of_bound_entered = True
                    hud_button_click_positions.add(e.pos)
                    audio.play_click(AUDIO)
                elif button_clicked == 'archives':
                    # Switch to Archives screen
                    mode = MODE_ARCHIVES
                    archives.enter(gs, **deps)
                    gs._archives_entered = True
                    hud_button_click_positions.add(e.pos)
                    audio.play_click(AUDIO)

        # --- Global hotkeys ---
        for e in events:
            # Bag toggle (I)
            if e.type == pygame.KEYDOWN and e.key == pygame.K_i:
                bag_ui.toggle_popup()
                just_toggled_bag = True

            # Party Manager toggle (Tab) — only if no other modal is open
            if e.type == pygame.KEYDOWN and e.key == pygame.K_TAB:
                if not bag_ui.is_open() and not ledger.is_open():
                    party_manager.toggle()
                    just_toggled_pm = True
            
            # Currency display toggle (C)
            if e.type == pygame.KEYDOWN and e.key == pygame.K_c:
                if not currency_display.is_open() and not bag_ui.is_open() and not party_manager.is_open() and not ledger.is_open():
                    currency_display.toggle()
                    # Play Coin.mp3 sound
                    coin_sound = AUDIO.sfx.get("Coin") or AUDIO.sfx.get("coin")
                    if coin_sound:
                        coin_sound.play()
                    else:
                        # Try to load from the path
                        coin_path = os.path.join("Assets", "Music", "Sounds", "Coin.mp3")
                        if os.path.exists(coin_path):
                            try:
                                coin_sfx = pygame.mixer.Sound(coin_path)
                                coin_sfx.play()
                            except:
                                pass
                elif currency_display.is_open():
                    currency_display.close()
        
        # --- Let HUD handle clicks ONLY when no modal is open (this can open the Ledger) ---
        # Only if we didn't click a HUD button (to avoid conflicts)
        if not hud_button_click_positions and not bag_ui.is_open() and not party_manager.is_open() and not ledger.is_open() and not currency_display.is_open():
            was_ledger_open = ledger.is_open()  # should be False, safety check
            for e in events:
                party_ui.handle_event(e, gs)
            if not was_ledger_open and ledger.is_open():
                just_opened_ledger = True

        # --- Check for pending buff selection and start popup ---
        if getattr(gs, "pending_buff_selection", False) and not buff_popup.is_active():
            gs.pending_buff_selection = False
            # Store AUDIO reference in gs for music restart
            if not hasattr(gs, "_audio_bank"):
                gs._audio_bank = AUDIO
            buff_popup.start_buff_selection(gs)
        
        # --- Update buff popup animation ---
        if buff_popup.is_active():
            buff_popup.update(dt, gs)
        
        # --- Route events to modals (priority: Buff Popup → Bag → Party Manager → Ledger) ---
        for e in events:
            # Skip mouse clicks that were HUD button clicks (prevent immediate close)
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if e.pos in hud_button_click_positions:
                    continue  # Skip this event, already handled by HUD button
            
            # Buff popup has highest priority (blocks all other input)
            if buff_popup.is_active():
                if buff_popup.handle_event(e, gs):
                    continue
                # Block all other input while buff popup is active
                continue
            
            # Ignore the exact key that toggled a modal this frame to avoid double-handling
            if bag_ui.is_open():
                if not (just_toggled_bag and e.type == pygame.KEYDOWN and e.key == pygame.K_i):
                    if bag_ui.handle_event(e, gs, screen):
                        continue

            if party_manager.is_open():
                if not (just_toggled_pm and e.type == pygame.KEYDOWN and e.key == pygame.K_TAB):
                    if party_manager.handle_event(e, gs):
                        continue

            if ledger.is_open():
                # Suppress the opening mouse event so it doesn't immediately close the ledger
                if just_opened_ledger and e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    continue
                if ledger.handle_event(e, gs):
                    continue
            
            if currency_display.is_open():
                if currency_display.handle_event(e, gs):
                    continue
            
            if rest_popup.is_open():
                rest_type = rest_popup.handle_event(e, gs)
                if rest_type:
                    # Transition to rest screen with selected type
                    mode = MODE_REST
                    # Pass rest_type to enter function directly (don't call enter_mode first)
                    rest_screen.enter(gs, rest_type=rest_type, **deps)
                    # Set prev_mode to prevent enter_mode from being called and overwriting rest_type
                    prev_mode = MODE_REST
                elif rest_type is None and e.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                    # Popup was closed
                    continue
            
            if gs.shop_open:
                purchase_result = shop.handle_event(e, gs)
                # Check if purchase was confirmed (needs laugh sound)
                if purchase_result == "purchase_confirmed":
                    # Play random laugh after purchase
                    laugh_num = random.randint(1, 5)
                    laugh_key = f"laugh{laugh_num}"
                    laugh_sound = AUDIO.sfx.get(laugh_key)
                    if laugh_sound:
                        audio.play_sound(laugh_sound)
                if purchase_result:
                    continue

        # --- Pause / music events / shop ---
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                # If any modal was open at frame start OR is open now, don't enter Pause
                if (
                    modal_open_at_frame_start
                    or buff_popup.is_active()
                    or bag_ui.is_open()
                    or party_manager.is_open()
                    or ledger.is_open()
                    or gs.shop_open
                    or currency_display.is_open()
                    or rest_popup.is_open()
                ):
                    # If shop is open, close it instead
                    if gs.shop_open:
                        gs.shop_open = False
                        shop.reset_scroll()
                        # Restore overworld music
                        audio.stop_music(fade_ms=600)
                        gs._shop_music_playing = False
                        gs._waiting_for_shop_music = False
                        # Restart overworld music after fade
                        if hasattr(gs, "_shop_previous_music_track") and gs._shop_previous_music_track:
                            gs.last_overworld_track = gs._shop_previous_music_track
                        # Pick next overworld track
                        nxt = audio.pick_next_track(AUDIO, getattr(gs, "last_overworld_track", None), prefix="music")
                        if nxt:
                            audio.play_music(AUDIO, nxt, loop=False, fade_ms=600)
                            gs.last_overworld_track = nxt
                        audio.play_click(AUDIO)
                    # If currency is open, close it instead
                    if currency_display.is_open():
                        currency_display.close()
                        audio.play_click(AUDIO)
                    continue
                audio.play_click(AUDIO)
                mode = MODE_PAUSE
            elif event.type == pygame.KEYDOWN:
                # Close purchase selector with ESC
                if event.key == pygame.K_ESCAPE:
                    try:
                        from systems import shop
                        if shop._PURCHASE_SELECTOR_ACTIVE:
                            shop._close_purchase_selector()
                            continue
                    except:
                        pass
                
                elif event.key == pygame.K_e:
                    # Open shop when near merchant and no other modals are open
                    if (gs.near_merchant and not bag_ui.is_open() 
                        and not party_manager.is_open() and not ledger.is_open()):
                        was_open = gs.shop_open
                        gs.shop_open = not gs.shop_open
                        if gs.shop_open and not was_open:
                            # Opening shop
                            shop.reset_scroll()
                            # Stop current overworld music
                            audio.stop_music(fade_ms=400)
                            # Store current music track to restore later
                            if not hasattr(gs, "_shop_previous_music_track"):
                                gs._shop_previous_music_track = getattr(gs, "last_overworld_track", None)
                            # Play random laugh sound
                            laugh_num = random.randint(1, 5)
                            laugh_key = f"laugh{laugh_num}"
                            laugh_sound = AUDIO.sfx.get(laugh_key)
                            if laugh_sound:
                                # Play laugh sound
                                laugh_channel = audio.play_sound(laugh_sound)
                                # Get laugh duration
                                try:
                                    laugh_length = laugh_sound.get_length()
                                    # Set timer to play shop music after laugh
                                    gs._shop_music_timer = laugh_length
                                    gs._waiting_for_shop_music = True
                                except:
                                    # If can't get length, wait a bit then play
                                    gs._shop_music_timer = 2.0  # Default 2 seconds
                                    gs._waiting_for_shop_music = True
                            else:
                                # If laugh not found, play shop music immediately
                                audio.play_music(AUDIO, "shopm1", loop=True, fade_ms=800)
                                gs._shop_music_playing = True
                    elif not gs.shop_open and was_open:
                        # Closing shop - restore overworld music
                        audio.stop_music(fade_ms=600)
                        gs._shop_music_playing = False
                        gs._waiting_for_shop_music = False
                        # Restart overworld music after fade
                        if hasattr(gs, "_shop_previous_music_track") and gs._shop_previous_music_track:
                            gs.last_overworld_track = gs._shop_previous_music_track
                        # Pick next overworld track
                        nxt = audio.pick_next_track(AUDIO, getattr(gs, "last_overworld_track", None), prefix="music")
                        if nxt:
                            audio.play_music(AUDIO, nxt, loop=False, fade_ms=600)
                            gs.last_overworld_track = nxt
            elif event.type == MUSIC_ENDEVENT:
                # Don't restart music if shop music is playing (it should loop)
                if getattr(gs, "_shop_music_playing", False):
                    # Shop music ended, restart it (should loop but just in case)
                    audio.play_music(AUDIO, "shopm1", loop=True, fade_ms=0)
                elif not getattr(gs, "_waiting_for_shop_music", False) and not buff_popup.is_active():
                    # Normal overworld music loop (only if not waiting for shop music and buff popup is not active)
                    nxt = audio.pick_next_track(AUDIO, getattr(gs, "last_overworld_track", None), prefix="music")
                    if nxt:
                        audio.play_music(AUDIO, nxt, loop=False)
                        gs.last_overworld_track = nxt

        if not gs.overworld_music_started and not buff_popup.is_active():
            nxt = audio.pick_next_track(AUDIO, getattr(gs, "last_overworld_track", None), prefix="music")
            if nxt:
                audio.play_music(AUDIO, nxt, loop=False)
                gs.last_overworld_track = nxt
            gs.overworld_music_started = True

        # --- Shop music timer (wait for laugh to finish) ---
        if getattr(gs, "_waiting_for_shop_music", False):
            if hasattr(gs, "_shop_music_timer"):
                gs._shop_music_timer -= dt
                if gs._shop_music_timer <= 0:
                    # Laugh finished, play shop music
                    audio.play_music(AUDIO, "shopm1", loop=True, fade_ms=800)
                    gs._shop_music_playing = True
                    gs._waiting_for_shop_music = False
                    delattr(gs, "_shop_music_timer")
        
        # --- Detect shop close and restore music ---
        if not gs.shop_open and getattr(gs, "_shop_music_playing", False):
            # Shop was closed, restore overworld music
            audio.stop_music(fade_ms=600)
            gs._shop_music_playing = False
            gs._waiting_for_shop_music = False
            # Restart overworld music
            if hasattr(gs, "_shop_previous_music_track") and gs._shop_previous_music_track:
                gs.last_overworld_track = gs._shop_previous_music_track
            nxt = audio.pick_next_track(AUDIO, getattr(gs, "last_overworld_track", None), prefix="music")
            if nxt:
                audio.play_music(AUDIO, nxt, loop=False, fade_ms=600)
                gs.last_overworld_track = nxt

        # --- Mist animation ---
        mist_frame = None
        if MIST_ANIM:
            MIST_ANIM.update(dt)
            mist_frame = MIST_ANIM.current()

        # --- Movement & walking SFX (blocked by any modal) ---
        any_modal_open = buff_popup.is_active() or bag_ui.is_open() or party_manager.is_open() or ledger.is_open() or gs.shop_open or currency_display.is_open() or rest_popup.is_open()
        keys = pygame.key.get_pressed()
        walking_forward = (keys[pygame.K_w] or keys[pygame.K_s]) and not any_modal_open

        if not hasattr(gs, "is_walking"):
            gs.is_walking = False
            gs.walking_channel = None
        if walking_forward and not gs.is_walking:
            sfx = AUDIO.sfx.get("Walking") or AUDIO.sfx.get("walking")
            if sfx:
                gs.walking_channel = sfx.play(loops=-1, fade_ms=80)
            gs.is_walking = True
        elif not walking_forward and gs.is_walking:
            if gs.walking_channel:
                gs.walking_channel.stop()
            gs.is_walking = False
            gs.walking_channel = None

        if walking_forward:
            gs.walk_anim.update(dt)
            frame = gs.walk_anim.current()
            if frame is not None:
                gs.player_image = frame
        else:
            gs.walk_anim.reset()
            gs.player_image = gs.player_idle

        # --- Encounters / world update ---
        if gs.in_encounter:
            if gs.encounter_stats and not getattr(gs, "_went_to_wild", False):
                try:
                    pygame.mixer.music.fadeout(200)
                except Exception:
                    pass
                ch = getattr(gs, "walking_channel", None)
                if ch:
                    try: ch.stop()
                    except Exception: pass
                gs.is_walking = False
                gs.walking_channel = None
                gs._went_to_wild = True
                mode = MODE_WILD_VESSEL

            # NEW: summoner (trainer) encounter – no stats attached
            elif gs.encounter_sprite is not None and not getattr(gs, "_went_to_summoner", False):
                try:
                    pygame.mixer.music.fadeout(200)
                except Exception:
                    pass
                ch = getattr(gs, "walking_channel", None)
                if ch:
                    try: ch.stop()
                    except Exception: pass
                gs.is_walking = False
                gs.walking_channel = None
                gs._went_to_summoner = True
                mode = MODE_SUMMONER_BATTLE

            else:
                update_encounter_popup(virtual_screen, dt, gs, mist_frame, S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT, pg)
        else:
            if not any_modal_open:
                world.update_player(gs, dt, gs.player_half)
            actors.update_rivals(gs, dt, gs.player_half)
            actors.update_vessels(gs, dt, gs.player_half, VESSELS, RARE_VESSELS)
            actors.update_merchants(gs, dt, gs.player_half)
            try_trigger_encounter(gs, RIVAL_SUMMONERS, MERCHANT_FRAMES)

            cam = world.get_camera_offset(gs.player_pos, S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT, gs.player_half)
            world.draw_repeating_road(virtual_screen, cam.x, cam.y)
            pg.update_needed(cam.y, S.LOGICAL_HEIGHT)
            pg.draw_props(virtual_screen, cam.x, cam.y, S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT)
            actors.draw_vessels(virtual_screen, cam, gs, mist_frame, S.DEBUG_OVERWORLD)
            actors.draw_rivals(virtual_screen, cam, gs)
            actors.draw_merchants(virtual_screen, cam, gs)

            virtual_screen.blit(
                gs.player_image,
                (gs.player_pos.x - cam.x - gs.player_half.x,
                gs.player_pos.y - cam.y - gs.player_half.y)
            )
            
            # Draw speech bubble when near merchant (if not in shop)
            if gs.near_merchant and not gs.shop_open:
                draw_merchant_speech_bubble(virtual_screen, cam, gs, gs.near_merchant)

        # --- Draw HUD then modals (z-order: Bag < Party Manager < Ledger < Shop < Rest Popup) ---
        left_hud.draw(virtual_screen, gs)  # Left side HUD panel behind character token and party UI (textbox style)
        party_ui.draw_party_hud(virtual_screen, gs)  # Character token and party slots (draws on top of left_hud)
        score_display.draw_score(virtual_screen, gs, dt)  # Score in top right (animated)
        bottom_right_hud.draw(virtual_screen, gs)  # Bottom right HUD panel with buttons inside (textbox style)
        if bag_ui.is_open():
            bag_ui.draw_popup(virtual_screen, gs)
        if party_manager.is_open():
            party_manager.draw(virtual_screen, gs)
        if ledger.is_open():
            ledger.draw(virtual_screen, gs)
        if gs.shop_open:
            draw_shop_ui(virtual_screen, gs)
        if currency_display.is_open():
            currency_display.draw(virtual_screen, gs)
        if rest_popup.is_open():
            rest_popup.draw(virtual_screen, gs)
        if buff_popup.is_active():
            buff_popup.draw(virtual_screen, dt, gs)

        update_and_draw_fade(virtual_screen, dt, gs)
        blit_virtual_to_screen(virtual_screen, screen)
        pygame.display.flip()
