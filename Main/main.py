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
from screens import book_of_bound, archives
from systems import hells_deck_popup

# screens
from screens import (
    menu_screen, char_select, name_entry,
    black_screen, intro_video, settings_screen, pause_screen, master_oak
)
from screens import rest as rest_screen
from world.Tavern import tavern as tavern_screen
from world.Tavern import gambling as gambling_screen
from world.Tavern import whore as whore_screen

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
MODE_BOOK_OF_BOUND = "BOOK_OF_BOUND"
MODE_ARCHIVES = "ARCHIVES"
MODE_TAVERN = "TAVERN"
MODE_GAMBLING = "GAMBLING"
MODE_WHORE = "WHORE"
MODE_REST = "REST"




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


def try_trigger_encounter(gs, summoners, merchant_frames, tavern_sprite=None):
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
            # Merchant chance: 10%
            merchant_chance = 0.10
            # Tavern chance: 5%
            tavern_chance = 0.05
            # Vessel chance: 55%
            vessel_chance = 0.55
            # Summoner chance: 30%
            summoner_chance = 0.30
            
            if merchant_frames and len(merchant_frames) > 0 and roll < merchant_chance:
                # Spawn merchant (0.0 to 0.10)
                actors.spawn_merchant_ahead(gs, gs.start_x, merchant_frames)
                if not gs.first_merchant_spawned:
                    gs.first_merchant_spawned = True  # Mark first merchant as spawned
                    gs.encounters_since_merchant = 0  # Reset counter (no longer needed)
            elif roll < merchant_chance + tavern_chance:
                # Spawn tavern (merchant_chance to merchant_chance + tavern_chance)
                if tavern_sprite:
                    actors.spawn_tavern_ahead(gs, gs.start_x, tavern_sprite)
            elif roll < merchant_chance + tavern_chance + vessel_chance:
                # Spawn vessel (0.15 to 0.70)
                actors.spawn_vessel_shadow_ahead(gs, gs.start_x)
                if not gs.first_merchant_spawned:
                    gs.encounters_since_merchant += 1  # Only increment if first merchant not spawned yet
                    print(f"📊 Vessel spawned. encounters_since_merchant: {gs.encounters_since_merchant}")
            elif summoners:
                # Spawn summoner (0.70 to 1.0)
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

    # Draw any active vessels/rivals/merchants/taverns in the world behind the popup
    actors.draw_vessels(screen, cam, gs, mist_frame, S.DEBUG_OVERWORLD)
    actors.draw_rivals(screen, cam, gs)
    actors.draw_merchants(screen, cam, gs)
    actors.draw_taverns(screen, cam, gs)

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


def draw_tavern_speech_bubble(screen, cam, gs, tavern):
    """Draw a speech bubble above the tavern saying 'Press E To Enter the Tavern'."""
    if not tavern:
        return
    
    # Taverns are bigger (1.5x player size)
    TAVERN_SIZE_MULT = 1.5
    SIZE_W = int(S.PLAYER_SIZE[0] * TAVERN_SIZE_MULT)
    SIZE_H = int(S.PLAYER_SIZE[1] * TAVERN_SIZE_MULT)
    
    pos = tavern["pos"]
    screen_x = int(pos.x - cam.x)
    screen_y = int(pos.y - cam.y - SIZE_H // 2 - 40)  # Above tavern
    
    # Medieval-style text
    text = "Press E To Enter the Tavern"
    
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
    
    # Draw small triangle pointing down to tavern
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
    # Ensure player_half is set before using it
    if not hasattr(gs, "player_half") or gs.player_half.y == 0:
        # Use default player half size if not set
        gs.player_half = Vector2(S.PLAYER_SIZE[0] / 2, S.PLAYER_SIZE[1] / 2)
    
    gs.player_pos = Vector2(S.WORLD_W // 2, S.WORLD_H - gs.player_half.y - 10)
    gs.start_x = gs.player_pos.x
    reset_run_state(gs)

    # Preserve Book of Bound discoveries across new games (persistent collection)
    # They should already be loaded before start_new_game is called
    preserved_book_of_bound = getattr(gs, "book_of_bound_discovered", set())

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
    # Mark that this is a NEW game (not loaded from save)
    gs._game_was_loaded_from_save = False
    
    # Clear buff history and active buffs for new game
    gs.active_buffs = []
    gs.buffs_history = []
    
    # Restore Book of Bound discoveries (persistent across new games)
    gs.book_of_bound_discovered = preserved_book_of_bound


def continue_game(gs):
    # Preserve Book of Bound discoveries before any resets
    preserved_book_of_bound = getattr(gs, "book_of_bound_discovered", set())
    
    # CRITICAL: For continue game, we need to set start_x but NOT reset the run state
    # The run state (distance_travelled, position, etc.) will be loaded from the save file
    # Only set start_x to the center of the world (it's not saved, always recalculated)
    if not hasattr(gs, "player_half") or gs.player_half.y == 0:
        # Use default player half size if not set
        gs.player_half = Vector2(S.PLAYER_SIZE[0] / 2, S.PLAYER_SIZE[1] / 2)
    
    # Set start_x to center of world (always the same, not saved)
    gs.start_x = S.WORLD_W // 2
    
    # Load the save file - this will restore position, distance_travelled, and all other state
    # NOTE: requires SUMMONER_SPRITES, MERCHANT_FRAMES, and TAVERN_SPRITE to be defined (built after assets.load_everything())
    if not saves.load_game(gs, SUMMONER_SPRITES, MERCHANT_FRAMES, TAVERN_SPRITE):
        # If load failed, fall back to new game
        print("⚠️ Failed to load save, falling back to new game state")
        start_new_game(gs)
        return
    
    print(f"✅ Save loaded successfully. Position: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f}), start_x: {gs.start_x:.1f}, distance: {gs.distance_travelled:.1f}")
    
    # After loading, restore player variant and ensure position is valid
    apply_player_variant(gs, gs.player_gender, PLAYER_VARIANTS)
    
    # CRITICAL: Restore X position from start_x (NOT from save file)
    # The X position is always restored from start_x because player stays centered horizontally
    gs.player_pos.x = gs.start_x
    
    # CRITICAL: Clamp Y position to world bounds after loading
    # This ensures the loaded position is valid even if world bounds changed
    loaded_y_before_clamp = gs.player_pos.y
    min_y = gs.player_half.y
    max_y = S.WORLD_H - gs.player_half.y
    gs.player_pos.y = max(min_y, min(gs.player_pos.y, max_y))
    
    if abs(loaded_y_before_clamp - gs.player_pos.y) > 0.1:
        print(f"⚠️ WARNING: Y position was clamped from {loaded_y_before_clamp:.1f} to {gs.player_pos.y:.1f}")
        print(f"   Bounds: min={min_y:.1f}, max={max_y:.1f}, WORLD_H={S.WORLD_H}")
    
    print(f"✅ After adjustments. Position: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f}), start_x: {gs.start_x:.1f}")
    
    # Mark that this is a continued game (loaded from save), so first overworld blessing should NOT trigger
    gs._game_was_loaded_from_save = True
    gs.first_overworld_blessing_given = True
    
    # 🍺 Check if we should restore to tavern mode
    restore_to_tavern = getattr(gs, "_restore_to_tavern", False)
    if restore_to_tavern:
        # Restore overworld position from tavern state (for when exiting tavern)
        if hasattr(gs, "_tavern_state") and gs._tavern_state.get("overworld_player_pos"):
            overworld_pos = gs._tavern_state["overworld_player_pos"]
            # Store it for later restoration when exiting tavern
            print(f"💾 Restored overworld position from save: ({overworld_pos.x:.1f}, {overworld_pos.y:.1f})")
        
        # Mark that we should start in tavern mode
        gs._start_in_tavern = True
        print(f"🍺 Will restore to tavern mode on continue")
    
    # Ensure Book of Bound discoveries are preserved (should already be loaded, but double-check)
    if preserved_book_of_bound:
        if not hasattr(gs, "book_of_bound_discovered"):
            gs.book_of_bound_discovered = set()
        gs.book_of_bound_discovered.update(preserved_book_of_bound)


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
    elif mode == MODE_TAVERN:
        # Add summoners to deps for tavern
        tavern_deps = dict(deps, rival_summoners=RIVAL_SUMMONERS)
        tavern_screen.enter(gs, **tavern_deps)
    elif mode == MODE_GAMBLING:
        # Get bet amount and game type from tavern state
        bet_amount = 0
        game_type = "doom_roll"  # Default to doom roll for backwards compatibility
        if hasattr(gs, "_tavern_state"):
            bet_amount = gs._tavern_state.get("selected_bet", 0)
            game_type = gs._tavern_state.get("selected_game", "doom_roll")
        gambling_screen.enter(gs, bet_amount=bet_amount, game_type=game_type, **deps)
    elif mode == MODE_WHORE:
        # Get whore number and sprite from tavern state
        whore_number = 1
        whore_sprite = None
        if hasattr(gs, "_tavern_state"):
            st = gs._tavern_state
            whore_number = st.get("whore_number", 1)
            whore_sprite = st.get("whore_sprite", None)
        whore_screen.enter(gs, whore_number=whore_number, whore_sprite=whore_sprite, **deps)
    elif mode == MODE_REST:
        # Get rest type from gs._rest_state
        rest_type = getattr(gs, "_rest_type", "long")
        rest_screen.enter(gs, rest_type=rest_type, **deps)
    elif mode == S.MODE_GAME:
        # Initialize world state (important for camera initialization on loaded games)
        world.enter(gs, **deps)


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
    
    # Load custom cursors AFTER display is initialized
    from systems import cursor_manager
    cursor_manager.load_cursors()

    # -------- Theme & Assets ----------
    fonts = theme.load_fonts()
    menu_bg = theme.load_menu_bg()

    loaded = assets.load_everything()
    RIVAL_SUMMONERS = loaded["summoners"]
    VESSELS         = loaded["vessels"]
    RARE_VESSELS    = loaded["rare_vessels"]
    MIST_FRAMES     = loaded["mist_frames"]
    MERCHANT_FRAMES = loaded["merchant_frames"]
    TAVERN_SPRITE   = loaded.get("tavern_sprite")
    
    # Debug: Check if merchant frames loaded
    if MERCHANT_FRAMES:
        print(f"✅ Loaded {len(MERCHANT_FRAMES)} merchant animation frames")
    else:
        print("⚠️ No merchant frames loaded - check Assets/Animations/Merchant1-5.png")
    
    # Debug: Check if tavern sprite loaded
    if TAVERN_SPRITE:
        print(f"✅ Tavern sprite loaded")
    else:
        print("⚠️ No tavern sprite loaded - check Assets/Tavern/Tavern.png")
    
    # Load tavern ambient audio
    TAVERN_AUDIO_PATH = os.path.join("Assets", "Tavern", "OutsideTavern.mp3")
    TAVERN_AUDIO = None
    if os.path.exists(TAVERN_AUDIO_PATH):
        try:
            TAVERN_AUDIO = pygame.mixer.Sound(TAVERN_AUDIO_PATH)
            print(f"✅ Loaded tavern audio: {TAVERN_AUDIO_PATH}")
        except Exception as e:
            print(f"⚠️ Failed to load tavern audio {TAVERN_AUDIO_PATH}: {e}")
    else:
        print(f"⚠️ Tavern audio not found at: {TAVERN_AUDIO_PATH}")

    # Map summoner names -> surfaces for save/load rehydration
    SUMMONER_SPRITES = {name: surf for (name, surf) in RIVAL_SUMMONERS}

    # Create a global animator for the hovering mist (looping)
    MIST_ANIM = Animator(MIST_FRAMES, fps=8, loop=True) if MIST_FRAMES else None

    PLAYER_VARIANTS = assets.load_player_variants()
    world.load_road()
    pg = procgen.ProcGen(rng_seed=42)

    # -------- GameState ----------
    # Calculate correct starting Y position: WORLD_H - player_half.y - 10
    # Use PLAYER_SIZE[1] / 2 since player_half isn't set yet
    starting_y = S.WORLD_H - (S.PLAYER_SIZE[1] / 2) - 10
    gs = GameState(
        player_pos=Vector2(S.WORLD_W // 2, starting_y),
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

    # Load Book of Bound discoveries (persistent across games)
    # This ensures discoveries are preserved even when starting a new game
    if saves.has_save():
        try:
            import json
            with open(S.SAVE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                discovered = data.get("book_of_bound_discovered", [])
                if isinstance(discovered, list) and discovered:
                    gs.book_of_bound_discovered = set(discovered)
                else:
                    gs.book_of_bound_discovered = set()
        except Exception as e:
            print(f"⚠️ Failed to load Book of Bound discoveries: {e}")
            gs.book_of_bound_discovered = set()
    else:
        gs.book_of_bound_discovered = set()
    
    # CRITICAL: Don't call start_new_game() here - it resets position to start!
    # Only initialize minimal state. start_new_game() will be called when user chooses "New Game"
    # If user chooses "Continue", continue_game() will load the save instead
    # Initialize only what's needed for the menu to work
    if not hasattr(gs, "party_slots"):
        gs.party_slots = [None] * 6
    if not hasattr(gs, "party_slots_names"):
        gs.party_slots_names = [None] * 6
    if not hasattr(gs, "party_vessel_stats"):
        gs.party_vessel_stats = [None] * 6
    if not hasattr(gs, "inventory"):
        gs.inventory = {}
    if not hasattr(gs, "distance_travelled"):
        gs.distance_travelled = 0.0
    if not hasattr(gs, "next_event_at"):
        gs.next_event_at = S.FIRST_EVENT_AT

    # -------- Loop State ----------
mode = S.MODE_MENU
prev_mode = None
running = True
settings_return_to = S.MODE_MENU  # used inside settings screen; kept for parity
is_fullscreen = use_fullscreen  # Track fullscreen state for toggle
display_mode = "fullscreen" if use_fullscreen else "windowed"  # Track display mode: "fullscreen", "windowed"
# Cache the desktop resolution when entering fullscreen (Info().current_w/h can be unreliable with SCALED flag)
_cached_desktop_resolution = None

# Safety: make sure a display surface exists before we enter the loop
assert pygame.display.get_surface() is not None, "Display not created before main loop"

# ===================== Display Mode Functions ==========================
def change_display_mode(mode_name: str, screen_ref) -> pygame.Surface:
    """
    Change the display mode. Returns the new screen surface.
    Modes: "fullscreen", "windowed"
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
    if mode_name == "fullscreen":
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
    if display_mode == "fullscreen":
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
        elif mode == MODE_TAVERN:
            # Only start tavern music if we're not coming from gambling (where it's already playing)
            if prev_mode != MODE_GAMBLING:
                # Stop overworld music and walking sounds
                audio.stop_music(fade_ms=600)
                # Stop overworld walking sound if playing
                if hasattr(gs, "walking_channel") and gs.walking_channel:
                    try:
                        gs.walking_channel.stop()
                    except:
                        pass
                if hasattr(gs, "is_walking"):
                    gs.is_walking = False
                    gs.walking_channel = None
                
                # Try to play tavern music (will use direct path if not in AUDIO bank)
                tavern_music_path = os.path.join("Assets", "Tavern", "Tavern.mp3")
                if os.path.exists(tavern_music_path):
                    audio.play_music(AUDIO, tavern_music_path, loop=True, fade_ms=600)
                else:
                    # Fallback: try to find it in the audio bank
                    audio.play_music(AUDIO, "tavern", loop=True, fade_ms=600)
            # If coming from gambling, music should already be playing - don't restart it
        elif mode == MODE_GAMBLING:
            # Don't stop tavern music - it should continue playing
            # Just make sure we're not playing overworld music
            pass
        elif mode == S.MODE_GAME:
            # Check if we're returning from tavern or gambling - restore overworld music
            if prev_mode == MODE_TAVERN or prev_mode == MODE_GAMBLING:
                # Stop tavern music
                audio.stop_music(fade_ms=600)
            else:
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
        
        if mode_name == "fullscreen":
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
        if mode_name == "fullscreen":
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
            # No autosave - user must manually save via "Save Game" button
            print(f"🛑 Quitting game (mode={mode})")
            running = False

    # ===================== MENU ============================
    if mode == S.MODE_MENU:
        # Use has_valid_save() to check for actual vessel data, not just file existence
        next_mode = menu_screen.handle(events, gs, **deps, can_continue=saves.has_valid_save())
        menu_screen.draw(virtual_screen, gs, **deps, can_continue=saves.has_valid_save())
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            # Check if this is a continue action (tuple with "CONTINUE" marker)
            if isinstance(next_mode, tuple) and next_mode[0] == "CONTINUE":
                # Load the saved game FIRST, before changing mode
                # This ensures _game_was_loaded_from_save flag is set before world.enter() is called
                continue_game(gs)
                # Verify the flag was set
                if not getattr(gs, "_game_was_loaded_from_save", False):
                    print(f"⚠️ WARNING: _game_was_loaded_from_save flag not set after continue_game()!")
                
                # CRITICAL: Check if all vessels are dead after loading
                # If so, redirect to death screen instead of game (death is permanent)
                stats = getattr(gs, "party_vessel_stats", None) or []
                has_any_member = any(isinstance(st, dict) for st in stats)
                has_living = any(
                    isinstance(st, dict) and int(st.get("current_hp", st.get("hp", 0)) or 0) > 0
                    for st in stats
                )
                if has_any_member and not has_living:
                    # All vessels are dead - player died, send them to death screen
                    print("💀 All vessels are dead - redirecting to death screen (death is permanent)")
                    mode = MODE_DEATH
                else:
                    # Vessels are alive - can continue playing
                    # Check if we should restore to tavern mode
                    if getattr(gs, "_start_in_tavern", False):
                        mode = MODE_TAVERN
                        print(f"🍺 Restoring to tavern mode from save")
                    else:
                        mode = next_mode[1]  # Set mode to MODE_GAME
            else:
                mode = next_mode

    # ===================== CHARACTER SELECT ================
    elif mode == MODE_CHAR_SELECT:
        next_mode = char_select.handle(events, gs, **deps)
        char_select.draw(virtual_screen, gs, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== NAME ENTRY ======================
    elif mode == MODE_NAME_ENTRY:
        next_mode = name_entry.handle(events, gs, dt, **deps)
        name_entry.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== MASTER OAK ======================
    elif mode == MODE_MASTER_OAK:
        next_mode = master_oak.handle(events, gs, dt, **deps)
        master_oak.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            if next_mode == MODE_BLACK_SCREEN:
                # Preserve Book of Bound discoveries BEFORE any operations
                # start_new_game() will preserve them, but we need to ensure they're in memory first
                # They should already be loaded from save file at startup, but ensure they exist
                if not hasattr(gs, "book_of_bound_discovered"):
                    # If not in memory, try to load from save file before deleting it
                    from systems import save_system as saves
                    if saves.has_save():
                        try:
                            import json
                            with open(S.SAVE_PATH, "r", encoding="utf-8") as f:
                                data = json.load(f)
                                discovered = data.get("book_of_bound_discovered", [])
                                if isinstance(discovered, list):
                                    gs.book_of_bound_discovered = set(discovered)
                                else:
                                    gs.book_of_bound_discovered = set()
                        except Exception:
                            gs.book_of_bound_discovered = set()
                    else:
                        gs.book_of_bound_discovered = set()
                
                # Now delete save file (discoveries are safe in memory)
                from systems import save_system as saves
                saves.delete_save(gs)  # Delete save file but preserve discoveries in memory
                
                # Start new game (this will preserve discoveries from memory)
                start_new_game(gs)

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
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
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
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
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
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== PAUSE ===========================
    elif mode == MODE_PAUSE:
        next_mode = pause_screen.handle(events, gs, **deps, saves=saves)
        pause_screen.draw(virtual_screen, gs, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            # If pause returns to game, check if we should return to a previous mode (e.g., tavern)
            if next_mode == S.MODE_GAME and hasattr(gs, "_pause_return_to"):
                mode = gs._pause_return_to
                del gs._pause_return_to  # Clear the stored mode
            else:
                mode = next_mode
    
    # ===================== SUMMONER BATTLE =====================
    elif mode == MODE_SUMMONER_BATTLE:
        next_mode = summoner_battle.handle(events, gs, dt, **deps)
        summoner_battle.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            mode = next_mode


    # ===================== WILD VESSEL =====================
    elif mode == MODE_WILD_VESSEL:
        next_mode = wild_vessel.handle(events, gs, **deps)
        wild_vessel.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            mode = next_mode  # ESC returns to overworld

    # ===================== Battle ==========================
    elif mode == MODE_BATTLE:
        next_mode = battle.handle(events, gs, dt, **deps)
        battle.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
                mode = next_mode
    
    # ===================== Gambling =====================
    elif mode == MODE_GAMBLING:
        # Update gambling screen
        gambling_screen.update(gs, dt, **deps)
        # Handle gambling events
        next_mode = gambling_screen.handle(events, gs, dt, **deps)
        # Draw gambling screen
        gambling_screen.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        
        if next_mode:
            if next_mode == "TAVERN":
                # Return to tavern (tavern music should still be playing)
                mode = MODE_TAVERN
            else:
                mode = next_mode
    
    # ===================== Whore =====================
    elif mode == MODE_WHORE:
        # Update whore screen
        whore_screen.update(gs, dt, **deps)
        # Handle whore events
        next_mode = whore_screen.handle(events, gs, dt, **deps)
        # Draw whore screen
        whore_screen.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        
        if next_mode:
            if next_mode == "TAVERN":
                # Return to tavern
                mode = MODE_TAVERN
            else:
                mode = next_mode
    
    # ===================== Rest =====================
    elif mode == MODE_REST:
        # Handle rest events
        next_mode = rest_screen.handle(events, gs, dt, **deps)
        # Draw rest screen
        rest_screen.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        
        if next_mode:
            # Restore music based on return mode
            if next_mode == MODE_TAVERN:
                # Restart tavern music
                audio.stop_music(fade_ms=500)
                tavern_music_path = os.path.join("Assets", "Music", "Tavern.mp3")
                if not os.path.exists(tavern_music_path):
                    tavern_music_path = r"C:\Users\Frederik\Desktop\SummonersLedger\Main\Assets\Music\Tavern.mp3"
                if os.path.exists(tavern_music_path):
                    audio.play_music(AUDIO, tavern_music_path, loop=True, fade_ms=800)
            elif next_mode == S.MODE_GAME:
                # Restart overworld music
                audio.stop_music(fade_ms=500)
                # Reset flag so main loop picks next track
                gs.overworld_music_started = False
            
            mode = next_mode
    
    # ===================== Death Saves ==========================
    elif mode == MODE_DEATH_SAVES:
        next_mode = death_saves_screen.handle(events, gs, **deps)
        death_saves_screen.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            mode = next_mode


    # ===================== Death ==========================   
    elif mode == MODE_DEATH:
        next_mode = death_screen.handle(events, gs, **deps)
        death_screen.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== Tavern ==========================
    elif mode == MODE_TAVERN:
        # Track modal states for HUD button handling
        any_modal_open_tavern = (buff_popup.is_active() or bag_ui.is_open() or party_manager.is_open()
                                 or ledger.is_open() or gs.shop_open or currency_display.is_open()
                                 or rest_popup.is_open())
        tavern_state = getattr(gs, "_tavern_state", None)
        if tavern_state is None:
            tavern_state = {}
            gs._tavern_state = tavern_state
        if (tavern_state.get("kicked_out_textbox_active", False)
                or tavern_state.get("show_gambler_intro", False)
                or tavern_state.get("show_bet_selection", False)
                or tavern_state.get("whore_confirm_active", False)):
            any_modal_open_tavern = True

        # Route input to shop first (so clicks don't leak through)
        consumed_event_ids = set()
        if gs.shop_open:
            for e in events:
                purchase_result = shop.handle_event(e, gs)
                if purchase_result:
                    consumed_event_ids.add(id(e))

        # Sync barkeeper shop state if it was closed externally
        if tavern_state.get("barkeeper_shop_active") and not gs.shop_open:
            tavern_state["barkeeper_shop_active"] = False

        tavern_events = events if not consumed_event_ids else [e for e in events if id(e) not in consumed_event_ids]
        
        # Track HUD button clicks to prevent event propagation
        hud_button_click_positions_tavern = set()
        
        # --- Handle cursor changes for mouse events ---
        for e in events:
            cursor_manager.handle_mouse_event(e)
        
        # --- Handle HUD button clicks FIRST (before other UI) ---
        for e in tavern_events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                # Convert click position to logical coordinates (button rects are in logical coords)
                logical_pos = coords.screen_to_logical(e.pos)
                button_clicked = hud_buttons.handle_click(logical_pos)
                if button_clicked == 'bag':
                    bag_ui.toggle_popup()
                    hud_button_click_positions_tavern.add(e.pos)
                    audio.play_click(AUDIO)
                elif button_clicked == 'party':
                    if not bag_ui.is_open() and not ledger.is_open():
                        party_manager.toggle()
                        hud_button_click_positions_tavern.add(e.pos)
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
                    hud_button_click_positions_tavern.add(e.pos)
                elif button_clicked == 'rest':
                    if not bag_ui.is_open() and not party_manager.is_open() and not ledger.is_open() and not currency_display.is_open() and not gs.shop_open and not rest_popup.is_open():
                        rest_popup.open_popup()
                        hud_button_click_positions_tavern.add(e.pos)
                        audio.play_click(AUDIO)
                elif button_clicked == 'book_of_bound':
                    # Switch to Book of the Bound screen
                    # Store tavern position before leaving
                    if hasattr(gs, "_tavern_state"):
                        st = gs._tavern_state
                        st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                        print(f"💾 Stored tavern position before book of bound: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                    # Capture current screen for fade transition
                    previous_screen = virtual_screen.copy()
                    # Store that we came from tavern so we can return to it
                    gs._book_of_bound_return_to = MODE_TAVERN
                    mode = MODE_BOOK_OF_BOUND
                    # Pass previous screen to enter() for fade transition
                    book_of_bound.enter(gs, previous_screen_surface=previous_screen, **deps)
                    gs._book_of_bound_entered = True
                    hud_button_click_positions_tavern.add(e.pos)
                    audio.play_click(AUDIO)
                elif button_clicked == 'archives':
                    # Switch to Archives screen
                    # Store tavern position before leaving
                    if hasattr(gs, "_tavern_state"):
                        st = gs._tavern_state
                        st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                        print(f"💾 Stored tavern position before archives: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                    # Store that we came from tavern so we can return to it
                    gs._archives_return_to = MODE_TAVERN
                    mode = MODE_ARCHIVES
                    archives.enter(gs, **deps)
                    gs._archives_entered = True
                    hud_button_click_positions_tavern.add(e.pos)
                    audio.play_click(AUDIO)
                elif button_clicked == 'hells_deck':
                    # Open Hell's Deck popup
                    hells_deck_popup.open_popup(gs)
                    hud_button_click_positions_tavern.add(e.pos)
                    audio.play_click(AUDIO)
        
        # --- Handle ESC key for pause menu FIRST (before tavern handles events) ---
        esc_pressed_for_pause = False
        for event in tavern_events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                # Don't open pause if any modal is open
                if not any_modal_open_tavern:
                    # Store previous mode (tavern) so pause can return to it
                    gs._pause_return_to = MODE_TAVERN
                    # Store current position before opening pause menu
                    if hasattr(gs, "_tavern_state"):
                        st = gs._tavern_state
                        st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                        print(f"💾 Stored tavern position before pause: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                    # Open pause menu
                    audio.play_click(AUDIO)
                    mode = MODE_PAUSE
                    esc_pressed_for_pause = True
                    break
        
        # Update tavern screen
        tavern_screen.update(gs, dt, **deps)
        
        # Handle tavern events FIRST (before modals) so tavern interactions (E key) work properly
        # Only if not opening pause menu
        if not esc_pressed_for_pause:
            next_mode = tavern_screen.handle(tavern_events, gs, dt, **deps)
        else:
            next_mode = None
        
        # If tavern handler returned a mode change, apply it immediately and skip the rest
        if next_mode:
            if next_mode == "GAME":
                # Stop tavern walking sound when exiting
                if hasattr(gs, "tavern_walking_channel") and gs.tavern_walking_channel:
                    try:
                        gs.tavern_walking_channel.stop()
                    except:
                        pass
                gs.tavern_is_walking = False
                gs.tavern_walking_channel = None
                
                # Return to game mode
                # Restore player position to where they were when entering the tavern
                if hasattr(gs, "_tavern_state") and gs._tavern_state.get("overworld_player_pos"):
                    overworld_pos = gs._tavern_state["overworld_player_pos"]
                    gs.player_pos.x = overworld_pos.x
                    gs.player_pos.y = overworld_pos.y
                    print(f"✅ Restored player position to overworld: ({overworld_pos.x:.1f}, {overworld_pos.y:.1f})")
                    # Clear stored tavern position so next tavern entry uses spawn logic
                    if "tavern_player_pos" in gs._tavern_state:
                        del gs._tavern_state["tavern_player_pos"]
                    
                    # Check if we need to remove tavern from overworld (kicked out)
                    if gs._tavern_state.get("remove_tavern_on_exit", False):
                        overworld_tavern = gs._tavern_state.get("overworld_tavern", None)
                        if overworld_tavern and hasattr(gs, "taverns_on_map"):
                            if overworld_tavern in gs.taverns_on_map:
                                gs.taverns_on_map.remove(overworld_tavern)
                                print("🚪 Removed tavern from overworld (kicked out)")
                        # Clear near_tavern flag
                        gs.near_tavern = None
                        # Clear the flag
                        gs._tavern_state["remove_tavern_on_exit"] = False
                        
                if gs.shop_open:
                    gs.shop_open = False
                    shop.reset_scroll()
                    shop.clear_shop_override()
                    if tavern_state:
                        tavern_state["barkeeper_shop_active"] = False
                    gs._shop_music_playing = False
                    gs._waiting_for_shop_music = False
                    if hasattr(gs, "_shop_music_timer"):
                        delattr(gs, "_shop_music_timer")

                mode = S.MODE_GAME
                # Reset overworld music state so it restarts in the game mode loop
                gs.overworld_music_started = False
            elif next_mode == "GAMBLING":
                # Transition to gambling screen (tavern music continues)
                mode = MODE_GAMBLING
            elif next_mode == "SUMMONER_BATTLE":
                # Transition to summoner battle immediately
                mode = MODE_SUMMONER_BATTLE
                # Call enter_mode to initialize the summoner battle screen
                enter_mode(mode, gs, deps)
            else:
                # Handle other mode transitions (e.g., whore screen)
                mode = next_mode
            # Continue to next iteration of main loop with new mode
            continue
        
        # --- Let HUD handle clicks in tavern mode (party UI can open Ledger) ---
        # Only if we didn't click a HUD button (to avoid conflicts) and not opening pause
        just_opened_ledger_tavern = False  # Initialize flag
        if not esc_pressed_for_pause and not hud_button_click_positions_tavern and not bag_ui.is_open() and not party_manager.is_open() and not ledger.is_open() and not currency_display.is_open():
            was_ledger_open_tavern = ledger.is_open()  # should be False, safety check
            for e in tavern_events:
                party_ui.handle_event(e, gs)
            if not was_ledger_open_tavern and ledger.is_open():
                just_opened_ledger_tavern = True  # Track that ledger was just opened
        
        # --- Global hotkeys for tavern mode ---
        just_toggled_bag_tavern = False
        just_toggled_pm_tavern = False
        for e in tavern_events:
            # Bag toggle (B or I)
            if e.type == pygame.KEYDOWN and (e.key == pygame.K_b or e.key == pygame.K_i):
                if not gs.shop_open:
                    bag_ui.toggle_popup()
                    just_toggled_bag_tavern = True
            
            # Party Manager toggle (Tab) — only if no other modal is open
            if e.type == pygame.KEYDOWN and e.key == pygame.K_TAB:
                if not bag_ui.is_open() and not ledger.is_open() and not gs.shop_open:
                    party_manager.toggle()
                    just_toggled_pm_tavern = True
            
            # Currency display toggle (C)
            if e.type == pygame.KEYDOWN and e.key == pygame.K_c:
                if not currency_display.is_open() and not bag_ui.is_open() and not party_manager.is_open() and not ledger.is_open() and not gs.shop_open:
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
        
        # --- Handle modal events (bag, party manager, ledger, currency, rest, hells deck) ---
        # Route events to modals (priority: Bag → Party Manager → Ledger → Currency → Rest → Hells Deck)
        # Only process if not opening pause menu
        if not esc_pressed_for_pause:
            for e in tavern_events:
                # Skip mouse clicks that were HUD button clicks (prevent immediate close)
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if e.pos in hud_button_click_positions_tavern:
                        continue  # Skip this event, already handled by HUD button
                
                # Handle modals (only if they're open)
                if bag_ui.is_open():
                    # Ignore the exact key that toggled bag this frame to avoid double-handling
                    if not (just_toggled_bag_tavern and e.type == pygame.KEYDOWN and (e.key == pygame.K_b or e.key == pygame.K_i)):
                        if bag_ui.handle_event(e, gs, virtual_screen):
                            continue
                
                if party_manager.is_open():
                    # Ignore the exact key that toggled party manager this frame to avoid double-handling
                    if not (just_toggled_pm_tavern and e.type == pygame.KEYDOWN and e.key == pygame.K_TAB):
                        if party_manager.handle_event(e, gs):
                            continue
                
                if ledger.is_open():
                    # Suppress the opening mouse event so it doesn't immediately close the ledger
                    if just_opened_ledger_tavern and e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                        continue
                    if ledger.handle_event(e, gs):
                        continue
                
                if currency_display.is_open():
                    if currency_display.handle_event(e, gs):
                        continue
                
                if rest_popup.is_open():
                    rest_type = rest_popup.handle_event(e, gs)
                    if rest_type:
                        # Store return mode (overworld or tavern)
                        gs._rest_return_to = MODE_TAVERN if mode == MODE_TAVERN else S.MODE_GAME
                        gs._rest_type = rest_type
                        mode = MODE_REST
                        enter_mode(mode, gs, deps)
                    continue
                
                if hells_deck_popup.is_open():
                    if hells_deck_popup.handle_event(e, gs):
                        continue
        
        # Draw tavern screen
        tavern_screen.draw(virtual_screen, gs, dt, **deps)
        
        # Draw HUD (same as overworld) - only if not transitioning to pause
        if mode == MODE_TAVERN:
            left_hud.draw(virtual_screen, gs)  # Left side HUD panel behind character token and party UI
            party_ui.draw_party_hud(virtual_screen, gs)  # Character token and party slots (draws on top of left_hud)
            
            # Draw bottom right HUD with buttons (textbox style)
            bottom_right_hud.draw(virtual_screen, gs)  # Bottom right HUD panel with buttons inside (textbox style)
            hud_buttons.draw(virtual_screen)  # Draw buttons on top of bottom_right_hud
            
            # Draw modals (party manager, bag, ledger, currency, etc.)
            if bag_ui.is_open():
                bag_ui.draw_popup(virtual_screen, gs)
            if party_manager.is_open():
                party_manager.draw(virtual_screen, gs, dt)
            if ledger.is_open():
                ledger.draw(virtual_screen, gs)
            if currency_display.is_open():
                currency_display.draw(virtual_screen, gs)
            if rest_popup.is_open():
                rest_popup.draw(virtual_screen, gs)
            if hells_deck_popup.is_open():
                hells_deck_popup.draw(virtual_screen, gs)
            if gs.shop_open:
                draw_shop_ui(virtual_screen, gs)
            
            # Draw tavern textboxes AFTER HUD (so they appear on top)
            # Import the drawing functions from tavern module
            from world.Tavern.tavern import _draw_gambler_intro_textbox, _draw_game_selection_popup, _draw_bet_selection_popup, _draw_kicked_out_textbox, _draw_whore_confirm_popup
            # Use the same tavern_state reference from earlier in the block
            # tavern_state was already retrieved at the top of MODE_TAVERN block
            screen_w = getattr(S, "LOGICAL_WIDTH", S.WIDTH)
            screen_h = getattr(S, "LOGICAL_HEIGHT", S.HEIGHT)
            
            # Draw game selection popup (modal, blocks other input, drawn on top of HUD)
            if tavern_state.get("show_game_selection", False):
                _draw_game_selection_popup(virtual_screen, gs, dt, screen_w, screen_h)
            
            # Draw gambler intro textbox (modal, blocks other input, drawn on top of HUD)
            if tavern_state.get("show_gambler_intro", False):
                _draw_gambler_intro_textbox(virtual_screen, gs, dt, screen_w, screen_h)
            
            # Draw bet selection popup (modal, blocks other input, drawn on top of HUD)
            if tavern_state.get("show_bet_selection", False):
                _draw_bet_selection_popup(virtual_screen, gs, dt, screen_w, screen_h)
            
            # Draw whore confirmation popup
            if tavern_state.get("whore_confirm_active", False):
                _draw_whore_confirm_popup(virtual_screen, gs, dt, screen_w, screen_h)
            
            # Draw "kicked out" textbox (drawn on top of everything, modal)
            if tavern_state.get("kicked_out_textbox_active", False):
                _draw_kicked_out_textbox(virtual_screen, gs, dt, screen_w, screen_h)
        
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        
        # Handle pause menu transition
        if esc_pressed_for_pause:
            # Already set mode to MODE_PAUSE above, will be handled in pause mode
            pass
        
        # --- Tavern walking SFX (same logic as overworld) ---
        # Check if any modal is open (block walking sounds if modal is open)
        any_modal_open_walking = buff_popup.is_active() or bag_ui.is_open() or party_manager.is_open() or ledger.is_open() or gs.shop_open or currency_display.is_open() or rest_popup.is_open()
        # Check if kicked out textbox is active (block walking sounds)
        if (tavern_state.get("kicked_out_textbox_active", False)
                or tavern_state.get("show_gambler_intro", False)
                or tavern_state.get("show_bet_selection", False)
                or tavern_state.get("whore_confirm_active", False)):
            any_modal_open_walking = True
        
        keys = pygame.key.get_pressed()
        # Player is walking if pressing any movement key (A/D/W/S)
        walking = (keys[pygame.K_a] or keys[pygame.K_d] or keys[pygame.K_w] or keys[pygame.K_s]) and not any_modal_open_walking
        
        if not hasattr(gs, "tavern_is_walking"):
            gs.tavern_is_walking = False
            gs.tavern_walking_channel = None
        
        if walking and not gs.tavern_is_walking:
            # Start playing tavern footsteps sound
            sfx = AUDIO.sfx.get("footsteps") or AUDIO.sfx.get("Footsteps")
            if sfx:
                gs.tavern_walking_channel = sfx.play(loops=-1, fade_ms=80)
            gs.tavern_is_walking = True
        elif not walking and gs.tavern_is_walking:
            # Stop playing tavern footsteps sound
            if gs.tavern_walking_channel:
                gs.tavern_walking_channel.stop()
            gs.tavern_is_walking = False
            gs.tavern_walking_channel = None

    # ===================== Book of the Bound ==========================
    elif mode == MODE_BOOK_OF_BOUND:
        next_mode = book_of_bound.handle(events, gs, dt, **deps)
        book_of_bound.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            # Clear the entered flag when exiting
            if hasattr(gs, '_book_of_bound_entered'):
                delattr(gs, '_book_of_bound_entered')
            # Check if we should return to tavern instead of overworld
            if next_mode == S.MODE_GAME and hasattr(gs, "_book_of_bound_return_to"):
                mode = gs._book_of_bound_return_to
                del gs._book_of_bound_return_to
                # Stop any overworld music that was started (book_of_bound starts it)
                # Tavern music should continue playing
                if mode == MODE_TAVERN:
                    audio.stop_music(fade_ms=0)  # Stop overworld music immediately
                    # Tavern music should already be playing, but ensure it continues
                    tavern_music_path = os.path.join("Assets", "Tavern", "Tavern.mp3")
                    if os.path.exists(tavern_music_path):
                        audio.play_music(AUDIO, tavern_music_path, loop=True, fade_ms=0)
                    else:
                        audio.play_music(AUDIO, "tavern", loop=True, fade_ms=0)
            else:
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
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            # Clear the entered flag when exiting
            if hasattr(gs, '_archives_entered'):
                delattr(gs, '_archives_entered')
            # Check if we should return to tavern instead of overworld
            if next_mode == S.MODE_GAME and hasattr(gs, "_archives_return_to"):
                mode = gs._archives_return_to
                del gs._archives_return_to
                # Stop any overworld music that was started (archives starts it)
                # Tavern music should continue playing
                if mode == MODE_TAVERN:
                    audio.stop_music(fade_ms=0)  # Stop overworld music immediately
                    # Tavern music should already be playing, but ensure it continues
                    tavern_music_path = os.path.join("Assets", "Tavern", "Tavern.mp3")
                    if os.path.exists(tavern_music_path):
                        audio.play_music(AUDIO, tavern_music_path, loop=True, fade_ms=0)
                    else:
                        audio.play_music(AUDIO, "tavern", loop=True, fade_ms=0)
            else:
                mode = next_mode
            continue  # Skip to next iteration to process mode change


    # ===================== GAMEPLAY ========================
    elif mode == S.MODE_GAME:
        # ===== First overworld blessing check =====
        # Only trigger on NEW games, not when continuing a saved game
        # Check if this game was loaded from a save file - if so, don't trigger first blessing
        game_was_loaded = getattr(gs, "_game_was_loaded_from_save", False)
        
        if (not game_was_loaded
            and not getattr(gs, "first_overworld_blessing_given", False) 
            and not buff_popup.is_active() 
            and not getattr(gs, "pending_buff_selection", False)):
            # 100% chance to get a buff selection when starting new game
            import random
            trigger_buff = True  # 100% chance
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
            # Save game when all vessels hit 0 HP (prevents save scumming)
            try:
                saves.save_game(gs, force=True)
                print("💾 Game saved: All vessels at 0 HP - entering death saves")
            except Exception as e:
                print(f"⚠️ Save failed on death: {e}")
            
            mode = MODE_DEATH_SAVES
            enter_mode(mode, gs, deps)
            # Draw once to avoid a 1-frame flash of overworld under black
            death_saves_screen.draw(virtual_screen, gs, dt, **deps)
            blit_virtual_to_screen(virtual_screen, screen)
            mouse_pos = pygame.mouse.get_pos()
            cursor_manager.draw_cursor(screen, mouse_pos, gs, MODE_DEATH_SAVES)
            pygame.display.flip()
            continue


        
        # --- Snapshots for this frame (used to suppress ESC->Pause) ---
        bag_open_at_frame_start = bag_ui.is_open()
        modal_open_at_frame_start = (
            bag_ui.is_open() or party_manager.is_open() or ledger.is_open() or gs.shop_open or currency_display.is_open() or rest_popup.is_open() or hells_deck_popup.is_open()
        )

        just_toggled_pm = False
        just_toggled_bag = False
        just_opened_ledger = False  # suppress first click that opened it

        # Track HUD button clicks to prevent event propagation
        hud_button_click_positions = set()

        # --- Handle cursor changes for mouse events ---
        for e in events:
            cursor_manager.handle_mouse_event(e)

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
                elif button_clicked == 'hells_deck':
                    # Open Hell's Deck popup
                    hells_deck_popup.open_popup(gs)
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
                    # Store return mode (overworld or tavern)
                    gs._rest_return_to = MODE_TAVERN if mode == MODE_TAVERN else S.MODE_GAME
                    gs._rest_type = rest_type
                    mode = MODE_REST
                    enter_mode(mode, gs, deps)
                continue
            
            # Handle Hell's Deck popup
            if hells_deck_popup.is_open():
                if hells_deck_popup.handle_event(e, gs):
                    continue  # Event consumed by popup
            
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
            # Handle ESC key - check popups first
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                # Close Hell's Deck popup if open
                if hells_deck_popup.is_open():
                    hells_deck_popup.close_popup()
                    from systems import audio as audio_sys
                    audio_sys.play_click(AUDIO)
                    continue
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
                    or hells_deck_popup.is_open()
                ):
                    # If shop is open, close it instead
                    if gs.shop_open:
                        gs.shop_open = False
                        shop.reset_scroll()
                        shop.clear_shop_override()
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
                    # Enter tavern when near tavern and no other modals are open
                    near_tavern = getattr(gs, "near_tavern", None)
                    if (near_tavern and not bag_ui.is_open() 
                        and not party_manager.is_open() and not ledger.is_open()
                        and not gs.shop_open and not currency_display.is_open()
                        and not rest_popup.is_open() and not hells_deck_popup.is_open()):
                        # Enter tavern mode
                        mode = MODE_TAVERN
                        audio.play_click(AUDIO)
                        # Stop tavern ambient audio if playing
                        tavern_audio_channel = getattr(gs, "_tavern_audio_channel", None)
                        if tavern_audio_channel:
                            tavern_audio_channel.stop()
                            gs._tavern_audio_channel = None
                    # Open shop when near merchant and no other modals are open
                    elif (gs.near_merchant and not bag_ui.is_open() 
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
                        shop.clear_shop_override()
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
        
        # --- Tavern ambient audio ---
        near_tavern = getattr(gs, "near_tavern", None)
        tavern_audio_channel = getattr(gs, "_tavern_audio_channel", None)
        
        if near_tavern and TAVERN_AUDIO:
            # Player is near tavern - play ambient audio if not already playing
            if tavern_audio_channel is None or not tavern_audio_channel.get_busy():
                # Find a free channel and play tavern audio
                channel = pygame.mixer.find_channel(True)
                if channel:
                    # Set volume to 40% of SFX volume (ambient sound)
                    ambient_volume = audio.get_sfx_volume() * 0.4
                    channel.set_volume(ambient_volume)
                    channel.play(TAVERN_AUDIO, loops=-1)  # Loop indefinitely
                    gs._tavern_audio_channel = channel
                    print(f"🔊 Started tavern ambient audio")
            elif tavern_audio_channel and tavern_audio_channel.get_busy():
                # Update volume continuously to respect SFX volume settings
                ambient_volume = audio.get_sfx_volume() * 0.4
                try:
                    tavern_audio_channel.set_volume(ambient_volume)
                except:
                    pass
        else:
            # Player is not near tavern - stop audio if playing
            if tavern_audio_channel and tavern_audio_channel.get_busy():
                tavern_audio_channel.stop()
                gs._tavern_audio_channel = None
                print(f"🔇 Stopped tavern ambient audio")

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
            actors.update_taverns(gs, dt, gs.player_half)
            try_trigger_encounter(gs, RIVAL_SUMMONERS, MERCHANT_FRAMES, TAVERN_SPRITE)

            cam = world.get_camera_offset(gs.player_pos, S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT, gs.player_half)
            world.draw_repeating_road(virtual_screen, cam.x, cam.y)
            pg.update_needed(cam.y, S.LOGICAL_HEIGHT)
            pg.draw_props(virtual_screen, cam.x, cam.y, S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT)
            actors.draw_vessels(virtual_screen, cam, gs, mist_frame, S.DEBUG_OVERWORLD)
            actors.draw_rivals(virtual_screen, cam, gs)
            actors.draw_merchants(virtual_screen, cam, gs)
            actors.draw_taverns(virtual_screen, cam, gs)

            virtual_screen.blit(
                gs.player_image,
                (gs.player_pos.x - cam.x - gs.player_half.x,
                gs.player_pos.y - cam.y - gs.player_half.y)
            )
            
            # Draw speech bubble when near merchant (if not in shop)
            if gs.near_merchant and not gs.shop_open:
                draw_merchant_speech_bubble(virtual_screen, cam, gs, gs.near_merchant)
            
            # Draw speech bubble when near tavern
            if getattr(gs, "near_tavern", None):
                draw_tavern_speech_bubble(virtual_screen, cam, gs, gs.near_tavern)

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
        if hells_deck_popup.is_open():
            hells_deck_popup.draw(virtual_screen, gs)
        if buff_popup.is_active():
            buff_popup.draw(virtual_screen, dt, gs)

        update_and_draw_fade(virtual_screen, dt, gs)
        blit_virtual_to_screen(virtual_screen, screen)
        
        # Draw custom cursor on top of everything
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, S.MODE_GAME)
        
        pygame.display.flip()
