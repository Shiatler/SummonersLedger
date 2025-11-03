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

# screens
from screens import (
    menu_screen, char_select, name_entry,
    black_screen, intro_video, settings_screen, pause_screen
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
MODE_BLACK_SCREEN = "BLACK_SCREEN"
MODE_INTRO_VIDEO  = "INTRO_VIDEO"
MODE_WILD_VESSEL = "WILD_VESSEL"
MODE_SUMMONER_BATTLE = "SUMMONER_BATTLE"
MODE_BATTLE = getattr(S, "MODE_BATTLE", "BATTLE")
MODE_DEATH_SAVES = getattr(S, "MODE_DEATH_SAVES", "DEATH_SAVES")
MODE_DEATH = getattr(S, "MODE_DEATH", "DEATH")




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
        elif roll < merchant_chance + vessel_chance:
            # Spawn vessel (0.10 to 0.775)
            actors.spawn_vessel_shadow_ahead(gs, gs.start_x)
        elif summoners:
            # Spawn summoner (0.775 to 1.0)
            actors.spawn_rival_ahead(gs, gs.start_x, summoners)
        else:
            # Fallback to vessel if no summoners available
            actors.spawn_vessel_shadow_ahead(gs, gs.start_x)
        
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

    pygame.display.flip()

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
    S.WIDTH, S.HEIGHT = info.current_w, info.current_h
    screen = pygame.display.set_mode((S.WIDTH, S.HEIGHT), pygame.FULLSCREEN | pygame.SCALED)
    pygame.display.set_caption(S.APP_NAME)
    clock = pygame.time.Clock()

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

    # ensure slot stats list exists (JSON-serializable dicts per slot)
    if not getattr(gs, "party_vessel_stats", None):
        gs.party_vessel_stats = [None] * 6

    # -------- Loop State ----------
mode = S.MODE_MENU
prev_mode = None
running = True
settings_return_to = S.MODE_MENU  # used inside settings screen; kept for parity

# Safety: make sure a display surface exists before we enter the loop
assert pygame.display.get_surface() is not None, "Display not created before main loop"

# ===================== Main Loop ==========================
while running:
    dt = clock.tick(60) / 1000.0
    events = pygame.event.get()

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
    deps = dict(
        fonts=fonts,
        menu_bg=menu_bg,
        audio_bank=AUDIO,
        player_variants=PLAYER_VARIANTS,
    )

    # ========== Universal window close ==========
    for e in events:
        if e.type == pygame.QUIT:
            saves.save_game(gs)
            running = False

    # ===================== MENU ============================
    if mode == S.MODE_MENU:
        next_mode = menu_screen.handle(events, gs, **deps, can_continue=saves.has_save())
        menu_screen.draw(screen, gs, **deps, can_continue=saves.has_save())
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== CHARACTER SELECT ================
    elif mode == MODE_CHAR_SELECT:
        next_mode = char_select.handle(events, gs, **deps)
        char_select.draw(screen, gs, **deps)
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== NAME ENTRY ======================
    elif mode == MODE_NAME_ENTRY:
        next_mode = name_entry.handle(events, gs, dt, **deps)
        name_entry.draw(screen, gs, dt, **deps)
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
            # ✅ THIS LINE WAS MISSING
            mode = next_mode



    # ===================== BLACK SCREEN ====================
    elif mode == MODE_BLACK_SCREEN:
        next_mode = black_screen.handle(events, gs, **deps, saves=saves)
        black_screen.draw(screen, gs, **deps)
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
        intro_video.draw(screen, gs, dt, **deps)
        pygame.display.flip()
        if next_mode:
            if next_mode == S.MODE_GAME:
                start_fade_in(gs, 0.8)
            mode = next_mode

    # ===================== SETTINGS ========================
    elif mode == MODE_SETTINGS:
        next_mode = settings_screen.handle(events, gs, **deps)
        settings_screen.draw(screen, gs, **deps)
        pygame.display.flip()
        if next_mode:
            mode = next_mode

    # ===================== PAUSE ===========================
    elif mode == MODE_PAUSE:
        next_mode = pause_screen.handle(events, gs, **deps)
        pause_screen.draw(screen, gs, **deps)
        pygame.display.flip()
        if next_mode:
            mode = next_mode
    
    # ===================== SUMMONER BATTLE =====================
    elif mode == MODE_SUMMONER_BATTLE:
        next_mode = summoner_battle.handle(events, gs, dt, **deps)
        summoner_battle.draw(screen, gs, dt, **deps)
        pygame.display.flip()
        if next_mode:
            mode = next_mode


    # ===================== WILD VESSEL =====================
    elif mode == MODE_WILD_VESSEL:
        next_mode = wild_vessel.handle(events, gs, **deps)
        wild_vessel.draw(screen, gs, dt, **deps)
        pygame.display.flip()
        if next_mode:
            mode = next_mode  # ESC returns to overworld

    # ===================== Battle ==========================
    elif mode == MODE_BATTLE:
        next_mode = battle.handle(events, gs, dt, **deps)
        battle.draw(screen, gs, dt, **deps)
        pygame.display.flip()
        if next_mode:
            mode = next_mode
    
    # ===================== Death Saves ==========================
    elif mode == MODE_DEATH_SAVES:
        next_mode = death_saves_screen.handle(events, gs, **deps)
        death_saves_screen.draw(screen, gs, dt, **deps)
        pygame.display.flip()
        if next_mode:
            mode = next_mode


    # ===================== Death ==========================   
    elif mode == MODE_DEATH:
        next_mode = death_screen.handle(events, gs, **deps)
        death_screen.draw(screen, gs, dt, **deps)
        pygame.display.flip()
        if next_mode:
            mode = next_mode


    # ===================== GAMEPLAY ========================
    elif mode == S.MODE_GAME:
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
            death_saves_screen.draw(screen, gs, dt, **deps)
            pygame.display.flip()
            continue


        
        # --- Snapshots for this frame (used to suppress ESC->Pause) ---
        bag_open_at_frame_start = bag_ui.is_open()
        modal_open_at_frame_start = (
            bag_ui.is_open() or party_manager.is_open() or ledger.is_open() or gs.shop_open or currency_display.is_open()
        )

        just_toggled_pm = False
        just_toggled_bag = False
        just_opened_ledger = False  # suppress first click that opened it

        # Track HUD button clicks to prevent event propagation
        hud_button_click_positions = set()

        # --- Handle HUD button clicks FIRST (before other UI) ---
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                button_clicked = hud_buttons.handle_click(e.pos)
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

        # --- Route events to modals (priority: Bag → Party Manager → Ledger) ---
        for e in events:
            # Skip mouse clicks that were HUD button clicks (prevent immediate close)
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if e.pos in hud_button_click_positions:
                    continue  # Skip this event, already handled by HUD button
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
                    or bag_ui.is_open()
                    or party_manager.is_open()
                    or ledger.is_open()
                    or gs.shop_open
                    or currency_display.is_open()
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
                elif not getattr(gs, "_waiting_for_shop_music", False):
                    # Normal overworld music loop (only if not waiting for shop music)
                    nxt = audio.pick_next_track(AUDIO, getattr(gs, "last_overworld_track", None), prefix="music")
                    if nxt:
                        audio.play_music(AUDIO, nxt, loop=False)
                        gs.last_overworld_track = nxt

        if not gs.overworld_music_started:
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
        any_modal_open = bag_ui.is_open() or party_manager.is_open() or ledger.is_open() or gs.shop_open or currency_display.is_open()
        keys = pygame.key.get_pressed()
        walking_forward = keys[pygame.K_w] and not any_modal_open

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
                update_encounter_popup(screen, dt, gs, mist_frame, S.WIDTH, S.HEIGHT, pg)
        else:
            if not any_modal_open:
                world.update_player(gs, dt, gs.player_half)
            actors.update_rivals(gs, dt, gs.player_half)
            actors.update_vessels(gs, dt, gs.player_half, VESSELS, RARE_VESSELS)
            actors.update_merchants(gs, dt, gs.player_half)
            try_trigger_encounter(gs, RIVAL_SUMMONERS, MERCHANT_FRAMES)

            cam = world.get_camera_offset(gs.player_pos, S.WIDTH, S.HEIGHT, gs.player_half)
            world.draw_repeating_road(screen, cam.x, cam.y)
            pg.update_needed(cam.y, S.HEIGHT)
            pg.draw_props(screen, cam.x, cam.y, S.WIDTH, S.HEIGHT)
            actors.draw_vessels(screen, cam, gs, mist_frame, S.DEBUG_OVERWORLD)
            actors.draw_rivals(screen, cam, gs)
            actors.draw_merchants(screen, cam, gs)

            screen.blit(
                gs.player_image,
                (gs.player_pos.x - cam.x - gs.player_half.x,
                gs.player_pos.y - cam.y - gs.player_half.y)
            )
            
            # Draw speech bubble when near merchant (if not in shop)
            if gs.near_merchant and not gs.shop_open:
                draw_merchant_speech_bubble(screen, cam, gs, gs.near_merchant)

        # --- Draw HUD then modals (z-order: Bag < Party Manager < Ledger < Shop) ---
        party_ui.draw_party_hud(screen, gs)
        score_display.draw_score(screen, gs, dt)  # Score in top right (animated)
        hud_buttons.draw(screen)  # Bag & Party buttons in bottom right
        if bag_ui.is_open():
            bag_ui.draw_popup(screen, gs)
        if party_manager.is_open():
            party_manager.draw(screen, gs)
        if ledger.is_open():
            ledger.draw(screen, gs)
        if gs.shop_open:
            draw_shop_ui(screen, gs)
        if currency_display.is_open():
            currency_display.draw(screen, gs)

        update_and_draw_fade(screen, dt, gs)
        pygame.display.flip()
