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
from systems import score_display, hud_buttons, shop
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

OVERWORLD_LANE_X_OFFSET = getattr(S, "OVERWORLD_LANE_X_OFFSET", int(S.PLAYER_SIZE[0] * 0.3))
# Visual offset for player sprite rendering (doesn't affect world position or camera)
PLAYER_VISUAL_X_OFFSET = getattr(S, "PLAYER_VISUAL_X_OFFSET", 30)  # pixels to shift sprite right on screen

# screens
from screens import (
    menu_screen, char_select, name_entry, rival_name_entry,
    black_screen, intro_video, settings_screen, pause_screen, master_oak, leaderboard
)
from screens import help_screen
from screens import boss_vs
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
    vessel_basename = token_to_vessel(token_name)  # FTokenBarbarian1 -> FVesselBarbarian1.png, TokenBeholder -> Beholder.png
    path = find_image(vessel_basename)
    if not path:
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        return img
    except Exception:
        return None


# ===================== Utilities / CWD =======================
def set_cwd():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))


# ===================== Mode Constants ========================
MODE_CHAR_SELECT  = "CHAR_SELECT"
MODE_SETTINGS     = "SETTINGS"
MODE_PAUSE        = "PAUSE"
MODE_NAME_ENTRY   = "NAME_ENTRY"
MODE_RIVAL_NAME_ENTRY = "RIVAL_NAME_ENTRY"
MODE_MASTER_OAK   = "MASTER_OAK"
MODE_BLACK_SCREEN = "BLACK_SCREEN"
MODE_INTRO_VIDEO  = "INTRO_VIDEO"
MODE_WILD_VESSEL = "WILD_VESSEL"
MODE_SUMMONER_BATTLE = "SUMMONER_BATTLE"
MODE_BOSS_VS = "BOSS_VS"
MODE_BATTLE = getattr(S, "MODE_BATTLE", "BATTLE")
MODE_DEATH_SAVES = getattr(S, "MODE_DEATH_SAVES", "DEATH_SAVES")
MODE_DEATH = getattr(S, "MODE_DEATH", "DEATH")
MODE_BOOK_OF_BOUND = "BOOK_OF_BOUND"
MODE_ARCHIVES = "ARCHIVES"
MODE_TAVERN = "TAVERN"
MODE_GAMBLING = "GAMBLING"
MODE_WHORE = "WHORE"
MODE_REST = "REST"
MODE_LEADERBOARD = "LEADERBOARD"
MODE_HELP = "HELP"




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


def _trigger_first_rival_encounter(gs):
    """
    Trigger the first rival encounter after buff selection completes.
    Sets up the walk-down animation and battle.
    """
    from world import rival
    rival.trigger_rival_intro_animation(gs, encounter_number=1)


def _update_rival_intro(gs, dt):
    """
    Update the first rival encounter walk-down animation and dialogue.
    """
    if not hasattr(gs, "rival_intro_state"):
        gs.rival_intro_active = False
        return
    
    state = gs.rival_intro_state
    phase = state.get("phase", "walk_down")
    
    # Initialize walking sound channel if needed
    if not hasattr(gs, "rival_walking_channel"):
        gs.rival_walking_channel = None
    
    if phase == "walk_down":
        # Update walk animation
        if hasattr(gs, "rival_walk_anim") and gs.rival_walk_anim:
            gs.rival_walk_anim.update(dt)
            frame = gs.rival_walk_anim.current()
            if frame:
                gs.rival_image = frame
        
        # Move rival down
        rival_pos = state["rival_pos"]
        target_y = state["target_y"]
        walk_speed = state["walk_speed"]
        
        # Check if rival is moving
        is_walking = rival_pos.y < target_y
        
        # Play walking sound when moving
        if is_walking and not gs.rival_walking_channel:
            # Start playing walking sound (same as player)
            sfx = (
                AUDIO.sfx.get("Walking")
                or AUDIO.sfx.get("walking")
                or AUDIO.sfx.get("WALKING")
            )
            if sfx:
                gs.rival_walking_channel = sfx.play(loops=-1, fade_ms=80)
        elif not is_walking and gs.rival_walking_channel:
            # Stop walking sound when reached target
            gs.rival_walking_channel.stop()
            gs.rival_walking_channel = None
        
        if is_walking:
            rival_pos.y += walk_speed * dt
            rival_pos.y = min(rival_pos.y, target_y)
            # Only transition to dialogue when we've actually reached the target
            if rival_pos.y >= target_y:
                # Reached halfway point - transition to dialogue
                state["phase"] = "dialogue"
                # Switch to idle sprite when dialogue starts
                if hasattr(gs, "rival_idle") and gs.rival_idle:
                    gs.rival_image = gs.rival_idle
                # Stop walking sound
                if gs.rival_walking_channel:
                    gs.rival_walking_channel.stop()
                    gs.rival_walking_channel = None
                print(f"💬 Rival reached halfway point, starting dialogue")
    
    elif phase == "dialogue":
        # Update dialogue blink timer
        state["dialogue_blink_t"] = state.get("dialogue_blink_t", 0.0) + dt


def _draw_rival_dialogue(screen, gs, dt):
    """Draw the rival dialogue textbox."""
    if not getattr(gs, "rival_intro_active", False):
        return
    
    state = getattr(gs, "rival_intro_state", None)
    if not state or state.get("phase") != "dialogue":
        return
    
    dialogue_text = state.get("dialogue_text", "")
    blink_t = state.get("dialogue_blink_t", 0.0)
    
    # Use logical dimensions for consistency
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)
    
    # Box styling (matches other textboxes)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)
    
    # Text rendering with word wrap
    def _get_dh_font(size: int):
        try:
            dh_font_path = os.path.join(S.ASSETS_FONTS_DIR, S.DND_FONT_FILE)
            if os.path.exists(dh_font_path):
                return pygame.font.Font(dh_font_path, size)
        except:
            pass
        return pygame.font.SysFont("arial", size)
    
    font = _get_dh_font(28)
    words = dialogue_text.split(" ")
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


def _handle_rival_dialogue_input(events, gs):
    """Handle input to dismiss rival dialogue and transition to VS screen."""
    if not getattr(gs, "rival_intro_active", False):
        return False
    
    state = getattr(gs, "rival_intro_state", None)
    if not state or state.get("phase") != "dialogue":
        return False
    
    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                # Stop walking sound if still playing
                if hasattr(gs, "rival_walking_channel") and gs.rival_walking_channel:
                    gs.rival_walking_channel.stop()
                    gs.rival_walking_channel = None
                
                # Dismiss dialogue and transition to VS screen
                gs.rival_intro_active = False
                
                # Set up encounter flags for VS screen
                gs.in_encounter = True
                gs.encounter_timer = S.ENCOUNTER_SHOW_TIME
                # Use gs.rival_name (set during name entry) instead of encounter_data name
                gs.encounter_name = getattr(gs, "rival_name", None) or gs.rival_encounter_data.get("name") or "Rival"
                # Update encounter_boss_data with correct name
                gs.rival_encounter_data["name"] = gs.encounter_name
                gs.encounter_sprite = gs.rival_encounter_data["sprite"]
                gs.encounter_type = "RIVAL"  # Mark as rival encounter
                gs.encounter_boss_data = gs.rival_encounter_data  # Store full data for battle
                
                print(f"💬 Rival dialogue dismissed, transitioning to VS screen: {gs.encounter_name}")
                return True  # Signal that we should transition to VS screen
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Stop walking sound if still playing
            if hasattr(gs, "rival_walking_channel") and gs.rival_walking_channel:
                gs.rival_walking_channel.stop()
                gs.rival_walking_channel = None
            
            # Click to dismiss
            gs.rival_intro_active = False
            
            # Set up encounter flags for VS screen
            gs.in_encounter = True
            gs.encounter_timer = S.ENCOUNTER_SHOW_TIME
            # Use gs.rival_name (set during name entry) instead of encounter_data name
            gs.encounter_name = getattr(gs, "rival_name", None) or gs.rival_encounter_data.get("name") or "Rival"
            # Update encounter_boss_data with correct name
            gs.rival_encounter_data["name"] = gs.encounter_name
            gs.encounter_sprite = gs.rival_encounter_data["sprite"]
            gs.encounter_type = "RIVAL"  # Mark as rival encounter
            gs.encounter_boss_data = gs.rival_encounter_data  # Store full data for battle
            
            print(f"💬 Rival dialogue dismissed (click), transitioning to VS screen: {gs.encounter_name}")
            return True  # Signal that we should transition to VS screen
    
    return False


def _open_chest(gs):
    """Handle chest opening: 85% item reward, 15% Chestmonster battle."""
    if not getattr(gs, "near_chest", None):
        return
    
    # Remove chest from map
    chest = gs.near_chest
    if hasattr(gs, "chests_on_map") and chest in gs.chests_on_map:
        gs.chests_on_map.remove(chest)
    gs.near_chest = None
    
    # Play chest opening sound
    _play_chest_sound()
    
    # Roll: 85% item, 15% battle
    roll = random.random()
    if roll < 0.85:
        # Give item reward and show result card
        item_name = _give_chest_item(gs)
        gs.chest_result_card_active = True
        gs.chest_result_card_title = "Chest Opened!"
        gs.chest_result_card_subtitle = f"You found: {item_name}"
        gs.chest_result_is_monster = False
    else:
        # Trigger Chestmonster battle - show attack message
        _trigger_chestmonster_battle(gs)
        attack_messages = [
            "The chest springs open! A Chest Monster lunges at you!",
            "As you open the chest, a monstrous form emerges and attacks!",
            "The chest was a trap! A Chest Monster bursts forth!",
            "Something moves inside the chest... A Chest Monster attacks!",
            "The lid flies open! A Chest Monster leaps out at you!",
        ]
        gs.chest_result_card_active = True
        gs.chest_result_card_title = "Chest Monster!"
        gs.chest_result_card_subtitle = random.choice(attack_messages)
        gs.chest_result_is_monster = True


def _give_chest_item(gs):
    """Give a random item from chest with weighted distribution. Returns formatted item name."""
    # Weighted item distribution (total = 100%)
    items = [
        ("scroll_of_command", 25),      # Highest chance
        ("scroll_of_mending", 25),     # Highest chance
        ("scroll_of_healing", 15),
        ("scroll_of_regeneration", 10),
        ("scroll_of_revivity", 8),
        ("scroll_of_sealing", 7),
        ("scroll_of_subjugation", 5),
        ("rations", 3),
        ("alcohol", 2),
        # scroll_of_eternity is EXCLUDED
    ]
    
    # Select item based on weights
    total_weight = sum(weight for _, weight in items)
    roll = random.random() * total_weight
    cumulative = 0
    selected_item = None
    
    for item_id, weight in items:
        cumulative += weight
        if roll <= cumulative:
            selected_item = item_id
            break
    
    if not selected_item:
        # Fallback to first item if something went wrong
        selected_item = items[0][0]
    
    # Add item to inventory
    if not hasattr(gs, "inventory"):
        gs.inventory = {}
    if not isinstance(gs.inventory, dict):
        gs.inventory = {}
    
    current_qty = gs.inventory.get(selected_item, 0)
    gs.inventory[selected_item] = current_qty + 1
    
    # Format item name for display
    item_name = selected_item.replace("_", " ").title()
    print(f"💎 Chest opened! Received: {item_name}")
    return item_name


def _play_chest_sound():
    """Play chest opening sound effect."""
    try:
        chest_sfx_path = os.path.join("Assets", "Music", "Sounds", "Chest.mp3")
        if os.path.exists(chest_sfx_path):
            chest_sfx = pygame.mixer.Sound(chest_sfx_path)
            audio.play_sound(chest_sfx)
        else:
            print(f"⚠️ Chest.mp3 not found at: {chest_sfx_path}")
    except Exception as e:
        print(f"⚠️ Failed to play chest sound: {e}")


def _trigger_chestmonster_battle(gs):
    """Set up Chestmonster encounter."""
    from combat.team_randomizer import scaled_enemy_level
    from rolling.roller import Roller
    
    # Generate stats for Chestmonster (75% boost = 1.75x multiplier)
    seed = (pygame.time.get_ticks() ^ hash("Chestmonster") ^ int(gs.distance_travelled)) & 0xFFFFFFFF
    try:
        rng = Roller(seed=seed)
    except TypeError:
        rng = Roller()
        for method in ("reseed", "seed", "set_seed"):
            fn = getattr(rng, method, None)
            if callable(fn):
                try:
                    fn(seed)
                    break
                except Exception:
                    pass
    
    enemy_level = scaled_enemy_level(gs, rng)
    
    # Generate Chestmonster stats with 75% boost
    stats = _generate_chestmonster_stats(enemy_level, rng)
    
    # Load Chestmonster sprites
    chestmonster_sprite = None
    token_sprite = None
    try:
        chestmonster_path = os.path.join("Assets", "VesselMonsters", "Chestmonster.png")
        token_path = os.path.join("Assets", "VesselMonsters", "TokenChestmonster.png")
        if os.path.exists(chestmonster_path):
            chestmonster_sprite = pygame.image.load(chestmonster_path).convert_alpha()
        if os.path.exists(token_path):
            token_sprite = pygame.image.load(token_path).convert_alpha()
    except Exception as e:
        print(f"⚠️ Failed to load Chestmonster sprites: {e}")
    
    # Set up encounter
    # Use name generator to get monster name (will return "Chestmonster" directly, like other monsters)
    from systems.name_generator import generate_vessel_name
    gs.encounter_name = generate_vessel_name("Chestmonster")
    gs.encounter_sprite = chestmonster_sprite
    gs.encounter_stats = stats
    # Use "Chestmonster" (not "TokenChestmonster") - the system will convert it to token when needed
    # This matches how other monsters work (they use asset_name like "Dragon.png")
    gs.encounter_token_name = "Chestmonster"
    gs.encounter_type = "MONSTER"  # Use monster battle system (so Chestmonster.mp3 plays)
    
    print(f"⚔️ Chest opened! A Chest Monster appears!")


def _generate_chestmonster_stats(level: int, rng) -> dict:
    """Generate Chestmonster stats with 75% boost (1.75x multiplier)."""
    from combat.monster_stats import generate_monster_stats_from_asset
    
    # Use the monster stats generator which applies the multiplier properly
    stats = generate_monster_stats_from_asset(
        asset_name="Chestmonster",
        level=level,
        rng=rng,
        notes="Chestmonster with 75% stat boost"
    )
    
    # Ensure class_name is set to Chestmonster for move recognition
    stats["class_name"] = "Chestmonster"
    
    return stats


def try_trigger_encounter(gs, summoners, merchant_frames, tavern_sprite=None, monsters=None, chest_sprite=None):
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
            # Normal chance-based spawning (reference values)
            merchant_chance = 0.10  # 10%
            tavern_chance   = 0.05  # 5%
            chest_chance    = 0.05  # 5%
            monster_chance  = 0.01  # 1%
            vessel_chance   = 0.49  # 49% (reduced from 54% to make room for chest)
            summoner_chance = 0.30  # 30%
            
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
            elif roll < merchant_chance + tavern_chance + chest_chance:
                # Spawn chest (tavern_chance to tavern_chance + chest_chance)
                if chest_sprite:
                    actors.spawn_chest_ahead(gs, gs.start_x, chest_sprite)
            elif roll < merchant_chance + tavern_chance + chest_chance + monster_chance:
                # Spawn monster (0.15 to 0.155) - VERY RARE!
                if monsters and len(monsters) > 0:
                    actors.spawn_monster_ahead(gs, gs.start_x, monsters)
                    print(f"🐉 Monster spawned! (rare encounter)")
                else:
                    # Fallback to vessel if no monsters available
                    actors.spawn_vessel_shadow_ahead(gs, gs.start_x)
                    if not gs.first_merchant_spawned:
                        gs.encounters_since_merchant += 1
            elif roll < merchant_chance + tavern_chance + monster_chance + vessel_chance:
                # Spawn vessel (0.155 to 0.70)
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

    # Draw any active vessels/rivals/merchants/taverns/monsters in the world behind the popup
    actors.draw_vessels(screen, cam, gs, mist_frame, S.DEBUG_OVERWORLD)
    actors.draw_monsters(screen, cam, gs, mist_frame, S.DEBUG_OVERWORLD)
    actors.draw_rivals(screen, cam, gs)
    actors.draw_merchants(screen, cam, gs)
    actors.draw_taverns(screen, cam, gs)
    actors.draw_bosses(screen, cam, gs)

    # Player sprite (with visual offset)
    screen.blit(
        gs.player_image,
        (gs.player_pos.x - cam.x - gs.player_half.x + PLAYER_VISUAL_X_OFFSET, gs.player_pos.y - cam.y - gs.player_half.y)
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

    # Don't clear encounter state here - let main loop handle transition to battle
    # The timer expiring will be checked in main loop, which will then transition to battle
    return True


def _get_dh_font_chest(size: int) -> pygame.font.Font:
    """Get D&D font if available, fallback to system font (for chest result card)."""
    try:
        dh_font_path = os.path.join(S.ASSETS_FONTS_DIR, S.DND_FONT_FILE)
        if os.path.exists(dh_font_path):
            return pygame.font.Font(dh_font_path, size)
    except Exception:
        pass
    return pygame.font.SysFont(None, size)


def draw_chest_result_card(screen, gs, dt):
    """Draw chest result card at bottom of screen (same style as gambling result cards)."""
    if not getattr(gs, "chest_result_card_active", False):
        return
    
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)
    
    # Box styling (matches gambling result card)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)
    
    # Text rendering
    title = getattr(gs, "chest_result_card_title", "")
    subtitle = getattr(gs, "chest_result_card_subtitle", "")
    text = f"{title} - {subtitle}" if title and subtitle else (title or subtitle or "")
    font = _get_dh_font_chest(28)
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
    if not hasattr(draw_chest_result_card, "blink_t"):
        draw_chest_result_card.blink_t = 0.0
    draw_chest_result_card.blink_t += dt
    blink_on = int(draw_chest_result_card.blink_t * 2) % 2 == 0
    if blink_on:
        prompt_font = _get_dh_font_chest(20)
        prompt = "Press SPACE or Click to continue"
        psurf = prompt_font.render(prompt, False, (100, 100, 100))
        screen.blit(psurf, (rect.right - psurf.get_width() - 20, rect.bottom - psurf.get_height() - 12))


def draw_shop_ui(screen, gs):
    """Draw the shop UI."""
    shop.draw(screen, gs)


def draw_chest_speech_bubble(screen, cam, gs, chest):
    """Draw a speech bubble above the chest saying 'Press E To Open Chest'."""
    if not chest:
        return
    
    # Chests are bigger (1.5x player size)
    CHEST_SIZE_MULT = 1.5
    SIZE_W = int(S.PLAYER_SIZE[0] * CHEST_SIZE_MULT)
    SIZE_H = int(S.PLAYER_SIZE[1] * CHEST_SIZE_MULT)
    
    pos = chest["pos"]
    screen_x = int(pos.x - cam.x)
    screen_y = int(pos.y - cam.y - SIZE_H // 2 - 40)  # Above chest
    
    # Medieval-style text
    text = "Press E To Open Chest"
    
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
    
    # Draw small triangle pointing down to chest
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
    if hasattr(gs, "monsters_on_map"):
        gs.monsters_on_map.clear()
    gs.distance_travelled = 0.0
    gs.next_event_at = S.FIRST_EVENT_AT


def start_new_game(gs):
    import random
    # Ensure player_half is set before using it
    if not hasattr(gs, "player_half") or gs.player_half.y == 0:
        # Use default player half size if not set
        gs.player_half = Vector2(S.PLAYER_SIZE[0] / 2, S.PLAYER_SIZE[1] / 2)
    
    lane_center_x = S.WORLD_W // 2 + OVERWORLD_LANE_X_OFFSET
    gs.player_pos = Vector2(lane_center_x, S.WORLD_H - gs.player_half.y - 10)
    gs.start_x = lane_center_x
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
    # Starting gold: bootstrap value
    gs.gold = getattr(S, "BOOTSTRAP_GOLD", 0)
    gs.silver = 0
    gs.bronze = 0
    
    # Initialize score with bootstrap value
    from systems import points as points_sys
    points_sys.ensure_points_field(gs)
    gs.total_points = getattr(S, "BOOTSTRAP_TOTAL_POINTS", 0)
    
    # Reset first overworld blessing flag for new run
    gs.first_overworld_blessing_given = False
    # Mark that this is a NEW game (not loaded from save)
    gs._game_was_loaded_from_save = False
    
    # Clear buff history and active buffs for new game
    gs.active_buffs = []
    gs.buffs_history = []
    
    # Reset boss tracking for new game
    gs.defeated_boss_scores = []
    gs.spawned_boss_scores = []
    gs.bosses_on_map = []
    gs.monsters_on_map = []
    gs.chests_on_map = []
    
    # Reset rival tracking for new game
    # NOTE: Don't reset rival_name here - it's already set during name entry BEFORE start_new_game is called
    # Preserve rival_name if it was already set during name entry
    existing_rival_name = getattr(gs, "rival_name", None)
    if existing_rival_name:
        print(f"✅ Preserving existing rival_name: '{existing_rival_name}'")
    # Only reset rival_gender if not already set (it's set during character selection)
    if not hasattr(gs, "rival_gender") or gs.rival_gender is None:
        gs.rival_gender = None  # Will be set when player chooses character
    gs.rival_starter_class = None  # Reset rival starter class
    gs.rival_starter_name = None  # Reset rival starter name
    gs.rival_encounters_completed = []
    gs.first_rival_encounter_complete = False
    gs.rivals_on_map = []
    # Clear rival animation/sprite state
    if hasattr(gs, "rival_walk_anim"):
        gs.rival_walk_anim = None
    if hasattr(gs, "rival_idle"):
        gs.rival_idle = None
    if hasattr(gs, "rival_image"):
        gs.rival_image = None
    if hasattr(gs, "rival_sprite"):
        gs.rival_sprite = None
    
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
    gs.start_x = S.WORLD_W // 2 + OVERWORLD_LANE_X_OFFSET
    
    # Load the save file - this will restore position, distance_travelled, and all other state
    # NOTE: requires SUMMONER_SPRITES, MERCHANT_FRAMES, and TAVERN_SPRITE to be defined (built after assets.load_everything())
    if not saves.load_game(gs, SUMMONER_SPRITES, MERCHANT_FRAMES, TAVERN_SPRITE, MONSTER_SPRITES):
        # If load failed, fall back to new game
        print("⚠️ Failed to load save, falling back to new game state")
        start_new_game(gs)
        return
    
    print(f"✅ Save loaded successfully. Position: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f}), start_x: {gs.start_x:.1f}, distance: {gs.distance_travelled:.1f}")
    
    # After loading, restore player variant and ensure position is valid
    apply_player_variant(gs, gs.player_gender, PLAYER_VARIANTS)
    
    # 🍺 Check if we should restore to tavern mode BEFORE adjusting position
    restore_to_tavern = getattr(gs, "_restore_to_tavern", False)
    
    if restore_to_tavern:
        # Mark that we should start in tavern mode
        gs._start_in_tavern = True
        
        # Restore tavern position if available (tavern.enter() will also restore it, but set it here too)
        tavern_state = getattr(gs, "_tavern_state", {})
        tavern_pos = tavern_state.get("tavern_player_pos")
        if tavern_pos:
            # Restore both X and Y from tavern position
            gs.player_pos.x = tavern_pos.x
            gs.player_pos.y = tavern_pos.y
            print(f"🍺 Restored tavern position in continue_game: ({tavern_pos.x:.1f}, {tavern_pos.y:.1f})")
        else:
            print(f"⚠️ No tavern position found in _tavern_state, using current position")
        
        print(f"🍺 Will restore to tavern mode on continue")
    else:
        # CRITICAL: Restore X position from start_x (NOT from save file) - only for overworld
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
    elif mode == MODE_RIVAL_NAME_ENTRY:
        rival_name_entry.enter(gs, **deps)
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
    elif mode == MODE_BOSS_VS:
        boss_vs.enter(gs, **deps)
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
        # Set gs.mode so save function can detect we're in tavern mode
        setattr(gs, "mode", MODE_TAVERN)
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
    elif mode == MODE_LEADERBOARD:
        leaderboard.enter(gs, **deps)
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
    # For fullscreen, force scale to 1.0 only if screen is EXACTLY 1920x1080 (or very close)
    # For QHD (2560x1440) and other higher resolutions, calculate scale normally to fill screen
    if use_fullscreen and actual_width == S.LOGICAL_WIDTH and actual_height == S.LOGICAL_HEIGHT:
        # Native 1920x1080: use scale 1.0 (no scaling, perfect fit)
        coords.update_scale_factors(actual_width, actual_height, force_scale=1.0)
    else:
        # QHD, 4K, or other resolutions: calculate scale to fill screen (maintains aspect ratio)
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
    MONSTERS        = loaded.get("monsters", [])
    MONSTER_SPRITES = {name: surf for (name, surf) in MONSTERS}
    MIST_FRAMES     = loaded["mist_frames"]
    MERCHANT_FRAMES = loaded["merchant_frames"]
    TAVERN_SPRITE   = loaded.get("tavern_sprite")
    CHEST_SPRITE    = loaded.get("chest_sprite")
    
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
    
    # Debug: Check if chest sprite loaded
    if CHEST_SPRITE:
        print(f"✅ Chest sprite loaded")
    else:
        print("⚠️ No chest sprite loaded - check Assets/Map/Chest.png")
    
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
    lane_center_x = S.WORLD_W // 2 + OVERWORLD_LANE_X_OFFSET
    gs = GameState(
        player_pos=Vector2(lane_center_x, starting_y),
        player_speed=S.PLAYER_SPEED,
        start_x=lane_center_x,
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
    # For fullscreen, force scale to 1.0 only if screen is EXACTLY 1920x1080
    # For QHD (2560x1440) and other higher resolutions, calculate scale normally to fill screen
    if mode_name == "fullscreen" and actual_width == S.LOGICAL_WIDTH and actual_height == S.LOGICAL_HEIGHT:
        # Native 1920x1080: use scale 1.0 (no scaling, perfect fit)
        coords.update_scale_factors(actual_width, actual_height, force_scale=1.0)
    else:
        # QHD, 4K, or windowed: calculate scale to fill screen (maintains aspect ratio)
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
        
        # CRITICAL: For fullscreen, only force scale 1.0 if screen is EXACTLY 1920x1080
        # For QHD (2560x1440) and other higher resolutions, calculate scale normally to fill screen
        if screen_width == S.LOGICAL_WIDTH and screen_height == S.LOGICAL_HEIGHT:
            # Native 1920x1080: use scale 1.0 (no scaling, perfect fit)
            coords.update_scale_factors(screen_width, screen_height, force_scale=1.0)
        else:
            # QHD, 4K, or other resolutions: calculate scale to fill screen (maintains aspect ratio)
            # This will scale the virtual screen to fit the physical screen while maintaining aspect ratio
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
            # Check if we're returning from pause - don't restart music
            if prev_mode == MODE_PAUSE:
                # Returning from pause - music should continue playing, don't restart
                pass
            # Only start tavern music if we're not coming from gambling (where it's already playing)
            elif prev_mode != MODE_GAMBLING:
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
                if hasattr(gs, "is_running"):
                    gs.is_running = False
                if hasattr(gs, "movement_sfx_state"):
                    gs.movement_sfx_state = None
                if hasattr(gs, "walking_channel"):
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
            # Check if we're returning from pause - don't restart music
            if prev_mode == MODE_PAUSE:
                # Returning from pause - music should continue playing, don't restart
                pass
            # Check if we're returning from tavern or gambling - restore overworld music
            elif prev_mode == MODE_TAVERN or prev_mode == MODE_GAMBLING:
                # Stop tavern music
                audio.stop_music(fade_ms=600)
                gs.overworld_music_started = False
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

    # ===================== RIVAL NAME ENTRY ======================
    elif mode == MODE_RIVAL_NAME_ENTRY:
        next_mode = rival_name_entry.handle(events, gs, dt, **deps)
        rival_name_entry.draw(virtual_screen, gs, dt, **deps)
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
        next_mode = black_screen.handle(events, gs, dt, **deps, saves=saves)
        black_screen.draw(virtual_screen, gs, dt, **deps)
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

    # ===================== LEADERBOARD ========================
    elif mode == MODE_LEADERBOARD:
        next_mode = leaderboard.handle(events, gs, **deps)
        leaderboard.update(gs, dt, **deps)
        leaderboard.draw(virtual_screen, gs, dt, **deps)
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

    # ===================== HELP ===========================
    elif mode == MODE_HELP:
        next_mode = help_screen.handle(events, gs, **deps)
        help_screen.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
            mode = next_mode
    
    # ===================== BOSS VS SCREEN =====================
    elif mode == MODE_BOSS_VS:
        # Draw overworld behind the VS popup
        cam = world.get_camera_offset(gs.player_pos, S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT, gs.player_half)
        world.draw_repeating_road(virtual_screen, cam.x, cam.y)
        pg.update_needed(cam.y, S.LOGICAL_HEIGHT)
        pg.draw_props(virtual_screen, cam.x, cam.y, S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT)
        actors.draw_vessels(virtual_screen, cam, gs, mist_frame, S.DEBUG_OVERWORLD)
        actors.draw_monsters(virtual_screen, cam, gs, mist_frame, S.DEBUG_OVERWORLD)
        actors.draw_rivals(virtual_screen, cam, gs)
        actors.draw_merchants(virtual_screen, cam, gs)
        actors.draw_taverns(virtual_screen, cam, gs)
        actors.draw_bosses(virtual_screen, cam, gs)
        
        # Draw player
        virtual_screen.blit(
            gs.player_image,
            (gs.player_pos.x - cam.x - gs.player_half.x,
            gs.player_pos.y - cam.y - gs.player_half.y)
        )
        
        # Draw VS popup overlay on top
        next_mode = boss_vs.handle(events, gs, dt, **deps)
        boss_vs.draw(virtual_screen, gs, dt, **deps)
        blit_virtual_to_screen(virtual_screen, screen)
        mouse_pos = pygame.mouse.get_pos()
        cursor_manager.draw_cursor(screen, mouse_pos, gs, mode)
        pygame.display.flip()
        if next_mode:
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
                # Return to tavern - restart tavern music
                mode = MODE_TAVERN
                # Restart tavern music after whore interaction
                tavern_music_path = os.path.join("Assets", "Tavern", "Tavern.mp3")
                if os.path.exists(tavern_music_path):
                    audio.play_music(AUDIO, tavern_music_path, loop=True, fade_ms=600)
                else:
                    # Fallback: try to find it in the audio bank
                    audio.play_music(AUDIO, "tavern", loop=True, fade_ms=600)
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
                                 or ledger.is_open() or gs.shop_open or rest_popup.is_open())
        tavern_state = getattr(gs, "_tavern_state", None)
        if tavern_state is None:
            tavern_state = {}
            gs._tavern_state = tavern_state
        if (tavern_state.get("kicked_out_textbox_active", False)
                or tavern_state.get("show_gambler_intro", False)
                or tavern_state.get("show_game_selection", False)
                or tavern_state.get("show_bet_selection", False)
                or tavern_state.get("whore_confirm_active", False)):
            any_modal_open_tavern = True

        # Route input to shop first (so clicks don't leak through)
        consumed_event_ids = set()
        if gs.shop_open:
            for e in events:
                purchase_result = shop.handle_event(e, gs)
                # Check if purchase was confirmed (needs laugh sound for merchants)
                if purchase_result == "purchase_confirmed":
                    # Play random laugh after purchase (merchant shops only)
                    laugh_num = random.randint(1, 5)
                    laugh_key = f"laugh{laugh_num}"
                    laugh_sound = AUDIO.sfx.get(laugh_key)
                    if laugh_sound:
                        audio.play_sound(laugh_sound)
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
                # e.pos is already converted to logical coordinates in main.py
                button_clicked = hud_buttons.handle_click(e.pos)
                if button_clicked == 'bag':
                    bag_ui.toggle_popup()
                    hud_button_click_positions_tavern.add(e.pos)
                    audio.play_click(AUDIO)
                elif button_clicked == 'party':
                    if not bag_ui.is_open() and not ledger.is_open():
                        party_manager.toggle()
                        hud_button_click_positions_tavern.add(e.pos)
                        audio.play_click(AUDIO)
                elif button_clicked == 'rest':
                    if not bag_ui.is_open() and not party_manager.is_open() and not ledger.is_open() and not gs.shop_open and not rest_popup.is_open():
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
                # Set gs.mode so save function can detect we're in overworld mode
                setattr(gs, "mode", S.MODE_GAME)
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
        if not esc_pressed_for_pause and not hud_button_click_positions_tavern and not bag_ui.is_open() and not party_manager.is_open() and not ledger.is_open():
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
            
        # --- Handle modal events (bag, party manager, ledger, rest, hells deck) ---
        # Route events to modals (priority: Bag → Party Manager → Ledger → Rest → Hells Deck)
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
            score_display.draw_score(virtual_screen, gs, dt)  # Score HUD in top right (always visible)
            
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
        any_modal_open_walking = buff_popup.is_active() or bag_ui.is_open() or party_manager.is_open() or ledger.is_open() or gs.shop_open or rest_popup.is_open()
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
        
        # Clear the "just finished rival battle" flag timer (but don't check death gate yet)
        # This needs to run every frame to update the timer
        just_finished_rival_battle = getattr(gs, "_just_finished_rival_battle", False)
        if just_finished_rival_battle:
            if not hasattr(gs, "_rival_battle_exit_timer"):
                gs._rival_battle_exit_timer = 0.0
            gs._rival_battle_exit_timer += dt
            
            # Check if any vessels are at low HP (<= 1 HP) - if so, extend the protection
            stats = getattr(gs, "party_vessel_stats", None) or []
            has_low_hp = any(
                isinstance(st, dict) and int(st.get("current_hp", st.get("hp", 0)) or 0) <= 1
                for st in stats
            )
            
            # Clear flag after 30 seconds, but only if vessels are healthy
            clear_delay = 30.0
            if gs._rival_battle_exit_timer >= clear_delay:
                # Before clearing, ensure ALL vessels have at least 1 HP
                for st in stats:
                    if isinstance(st, dict):
                        current_hp = int(st.get("current_hp", st.get("hp", 0)) or 0)
                        max_hp = int(st.get("hp", 0) or 0)
                        if current_hp <= 0 and max_hp > 0:
                            st["current_hp"] = 1
                            print(f"   Safety before flag clear: Vessel set to 1 HP")
                
                # Only clear if vessels are NOT at low HP
                has_low_hp_after_delay = any(
                    isinstance(st, dict) and int(st.get("current_hp", st.get("hp", 0)) or 0) <= 1
                    for st in stats
                )
                
                if not has_low_hp_after_delay:
                    delattr(gs, "_just_finished_rival_battle")
                    if hasattr(gs, "_rival_battle_exit_timer"):
                        delattr(gs, "_rival_battle_exit_timer")
                    print(f"✅ Cleared _just_finished_rival_battle flag after {clear_delay}s delay (vessels healthy)")
                else:
                    # Reset timer to keep protection active
                    gs._rival_battle_exit_timer = 0.0
                    print(f"🛡️ Keeping _just_finished_rival_battle flag active (vessels at low HP)")


        
        # --- Snapshots for this frame (used to suppress ESC->Pause) ---
        bag_open_at_frame_start = bag_ui.is_open()
        modal_open_at_frame_start = (
            bag_ui.is_open() or party_manager.is_open() or ledger.is_open() or gs.shop_open or rest_popup.is_open() or hells_deck_popup.is_open()
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
                # e.pos is already converted to logical coordinates in main.py
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
                elif button_clicked == 'rest':
                    if not bag_ui.is_open() and not party_manager.is_open() and not ledger.is_open() and not gs.shop_open and not rest_popup.is_open():
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
            # Party Manager toggle (Tab) — only if no other modal is open
            if e.type == pygame.KEYDOWN and e.key == pygame.K_TAB:
                if not bag_ui.is_open() and not ledger.is_open():
                    party_manager.toggle()
                    just_toggled_pm = True
            
        # --- Let HUD handle clicks ONLY when no modal is open (this can open the Ledger) ---
        # Only if we didn't click a HUD button (to avoid conflicts)
        if not hud_button_click_positions and not bag_ui.is_open() and not party_manager.is_open() and not ledger.is_open():
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
        buff_was_active = buff_popup.is_active()
        if buff_was_active:
            buff_popup.update(dt, gs)
        
        # Check if buff popup just finished and we need to trigger first rival encounter
        buff_now_active = buff_popup.is_active()
        if (buff_was_active and not buff_now_active and 
            not getattr(gs, "first_rival_encounter_complete", False) and
            getattr(gs, "first_overworld_blessing_given", False)):
            # First buff selection just completed - trigger first rival encounter
            # Ensure rival_name and rival_gender are set (they should be from character selection flow)
            # Check if rival_name is set - only set default if it's truly missing (not just empty string)
            current_rival_name = getattr(gs, "rival_name", None)
            print(f"🔍 [First rival encounter check] gs.rival_name = '{current_rival_name}'")
            if not current_rival_name:
                # Fallback: set default rival name if somehow missing
                rival_gender = getattr(gs, "rival_gender", "male")
                gs.rival_name = "Rival"
                print(f"⚠️ Rival name was missing, set to default 'Rival' (gender: {rival_gender})")
            else:
                print(f"✅ Rival name found: '{current_rival_name}'")
            if not getattr(gs, "rival_gender", None):
                # Fallback: set opposite of player gender
                player_gender = getattr(gs, "chosen_gender") or getattr(gs, "player_gender", "male")
                gs.rival_gender = "female" if player_gender == "male" else "male"
                print(f"⚠️ Rival gender was missing, set to opposite of player ({gs.rival_gender})")
            _trigger_first_rival_encounter(gs)
        
        # --- Route events to modals (priority: Rival Dialogue → Buff Popup → Bag → Party Manager → Ledger) ---
        for e in events:
            # Skip mouse clicks that were HUD button clicks (prevent immediate close)
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if e.pos in hud_button_click_positions:
                    continue  # Skip this event, already handled by HUD button
            
            # Rival dialogue has highest priority (blocks all other input)
            if _handle_rival_dialogue_input([e], gs):
                # Dialogue dismissed, transition to VS screen
                mode = MODE_BOSS_VS
                enter_mode(mode, gs, deps)
                continue
            
            # Buff popup has second priority (blocks all other input)
            if buff_popup.is_active():
                if buff_popup.handle_event(e, gs):
                    continue
                # Block all other input while buff popup is active
                continue
            
            # Handle heal textbox first (it's modal and works even when party manager is closed)
            if party_manager.is_heal_textbox_active():
                if party_manager.handle_event(e, gs):
                    continue
            
            # Handle bag UI events
            if bag_ui.is_open():
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
                    continue
                audio.play_click(AUDIO)
                # Store that we're returning to overworld (not tavern)
                gs._pause_return_to = S.MODE_GAME
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
                        and not gs.shop_open
                        and not rest_popup.is_open() and not hells_deck_popup.is_open()):
                        # Enter tavern mode
                        mode = MODE_TAVERN
                        audio.play_click(AUDIO)
                        # Stop tavern ambient audio if playing
                        tavern_audio_channel = getattr(gs, "_tavern_audio_channel", None)
                        if tavern_audio_channel:
                            tavern_audio_channel.stop()
                            gs._tavern_audio_channel = None
                    # Open chest when near chest and no other modals are open
                    elif (getattr(gs, "near_chest", None) and not bag_ui.is_open() 
                        and not party_manager.is_open() and not ledger.is_open()
                        and not gs.shop_open and not rest_popup.is_open() 
                        and not hells_deck_popup.is_open()):
                        _open_chest(gs)
                        audio.play_click(AUDIO)
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
                            # Play shop music immediately (no delay)
                            audio.play_music(AUDIO, "shopm1", loop=True, fade_ms=400)
                            gs._shop_music_playing = True
                            
                            # Play random laugh sound in background (doesn't block shop music)
                            laugh_num = random.randint(1, 5)
                            laugh_key = f"laugh{laugh_num}"
                            laugh_sound = AUDIO.sfx.get(laugh_key)
                            if laugh_sound:
                                # Play laugh sound (will play over shop music)
                                audio.play_sound(laugh_sound)
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
            # Handle chest result card dismissal on click
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 
                and getattr(gs, "chest_result_card_active", False)):
                # Dismiss result card
                gs.chest_result_card_active = False
                audio.play_click(AUDIO)
                
                # If it's a monster, transition to battle
                if getattr(gs, "chest_result_is_monster", False):
                    # Transition to wild vessel battle
                    try:
                        pygame.mixer.music.fadeout(200)
                    except Exception:
                        pass
                    ch = getattr(gs, "walking_channel", None)
                    if ch:
                        try: ch.stop()
                        except Exception: pass
                    gs.is_walking = False
                    gs.is_running = False
                    gs.movement_sfx_state = None
                    gs.walking_channel = None
                    gs._went_to_wild = True
                    gs.in_encounter = False
                    mode = MODE_WILD_VESSEL
                continue
            
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
        any_modal_open = buff_popup.is_active() or bag_ui.is_open() or party_manager.is_open() or ledger.is_open() or gs.shop_open or rest_popup.is_open()
        keys = pygame.key.get_pressed()
        vertical_input = keys[pygame.K_w] or keys[pygame.K_s]
        shift_down = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        moving_forward = vertical_input and not any_modal_open
        running_forward = moving_forward and shift_down

        gs.is_walking = moving_forward
        gs.is_running = running_forward

        if not hasattr(gs, "movement_sfx_state"):
            gs.movement_sfx_state = None
        if not hasattr(gs, "walking_channel"):
            gs.walking_channel = None

        desired_state = None
        if running_forward:
            running_sfx = AUDIO.sfx.get("Running") or AUDIO.sfx.get("running") or AUDIO.sfx.get("RUNNING")
            if running_sfx:
                desired_state = "running"
            else:
                desired_state = "walking"
        elif moving_forward:
            desired_state = "walking"

        current_state = gs.movement_sfx_state
        if desired_state != current_state:
            if gs.walking_channel:
                gs.walking_channel.stop()
            gs.walking_channel = None
            gs.movement_sfx_state = None

            if desired_state:
                sfx = None
                if desired_state == "running":
                    sfx = running_sfx
                if desired_state == "walking" or (desired_state == "running" and sfx is None):
                    sfx = (
                        AUDIO.sfx.get("Walking")
                        or AUDIO.sfx.get("walking")
                        or AUDIO.sfx.get("WALKING")
                    )
                    desired_state = "walking" if sfx else desired_state
                if sfx:
                    gs.walking_channel = sfx.play(loops=-1, fade_ms=80)
                    gs.movement_sfx_state = desired_state

        if moving_forward:
            anim_speed = getattr(S, "PLAYER_RUN_ANIM_MULT", 1.5) if running_forward else 1.0
            gs.walk_anim.update(dt * anim_speed)
            frame = gs.walk_anim.current()
            if frame is not None:
                gs.player_image = frame
        else:
            gs.walk_anim.reset()
            gs.player_image = gs.player_idle

        # --- Encounters / world update ---
        if gs.in_encounter:
            # Show popup while timer is active
            if gs.encounter_timer > 0:
                update_encounter_popup(virtual_screen, dt, gs, mist_frame, S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT, pg)
            # Timer expired - transition to battle
            # BUT: Don't transition if chest result card is showing (wait for dismissal)
            elif (gs.encounter_stats and not getattr(gs, "_went_to_wild", False)
                  and not getattr(gs, "chest_result_card_active", False)):  # Don't start battle while result card is showing
                # Wild vessel encounter
                try:
                    pygame.mixer.music.fadeout(200)
                except Exception:
                    pass
                ch = getattr(gs, "walking_channel", None)
                if ch:
                    try: ch.stop()
                    except Exception: pass
                gs.is_walking = False
                gs.is_running = False
                gs.movement_sfx_state = None
                gs.walking_channel = None
                gs._went_to_wild = True
                # Clear encounter state
                gs.in_encounter = False
                mode = MODE_WILD_VESSEL

            # Summoner (trainer) encounter – no stats attached
            # Boss encounters go to VS screen first, then summoner_battle
            # Rival encounters also go to VS screen first
            # NOTE: This should not trigger for wild vessels/monsters (they have encounter_stats)
            elif (gs.encounter_sprite is not None 
                  and gs.encounter_stats is None 
                  and not getattr(gs, "_went_to_summoner", False)
                  and getattr(gs, "encounter_type", None) not in ("WILD_VESSEL", "MONSTER")):
                try:
                    pygame.mixer.music.fadeout(200)
                except Exception:
                    pass
                ch = getattr(gs, "walking_channel", None)
                if ch:
                    try: ch.stop()
                    except Exception: pass
                gs.is_walking = False
                gs.is_running = False
                gs.movement_sfx_state = None
                gs.walking_channel = None
                gs._went_to_summoner = True
                # Clear encounter state (but keep encounter_name, encounter_sprite, encounter_summoner_filename for battle)
                gs.in_encounter = False
                # Check if this is a boss or rival encounter - go to VS screen first
                is_boss = getattr(gs, "encounter_type", None) == "BOSS"
                is_rival = getattr(gs, "encounter_type", None) == "RIVAL"
                if is_boss or is_rival:
                    mode = MODE_BOSS_VS
                else:
                    mode = MODE_SUMMONER_BATTLE
        else:
            # Handle first rival encounter walk-down animation
            if getattr(gs, "rival_intro_active", False):
                _update_rival_intro(gs, dt)
                # Lock player movement during rival intro
            elif not any_modal_open:
                world.update_player(gs, dt, gs.player_half)
            actors.update_rivals(gs, dt, gs.player_half)
            actors.update_bosses(gs, dt, gs.player_half)
            actors.update_vessels(gs, dt, gs.player_half, VESSELS, RARE_VESSELS)
            actors.update_monsters(gs, dt, gs.player_half)
            
            # Check if a wild vessel or monster encounter was triggered (no popup, go directly to battle)
            # BUT: Don't transition if chest result card is showing (wait for dismissal)
            if (gs.encounter_stats is not None 
                and not getattr(gs, "_went_to_wild", False)
                and not gs.in_encounter
                and not getattr(gs, "chest_result_card_active", False)):  # Don't start battle while result card is showing
                # Wild vessel or monster encounter - go directly to battle
                encounter_type = getattr(gs, "encounter_type", None)
                if encounter_type in ("WILD_VESSEL", "MONSTER", None):  # None for backwards compatibility
                    try:
                        pygame.mixer.music.fadeout(200)
                    except Exception:
                        pass
                    ch = getattr(gs, "walking_channel", None)
                    if ch:
                        try: ch.stop()
                        except Exception: pass
                    gs.is_walking = False
                    gs.is_running = False
                    gs.movement_sfx_state = None
                    gs.walking_channel = None
                    gs._went_to_wild = True
                    # Clear encounter state
                    gs.in_encounter = False
                    mode = MODE_WILD_VESSEL
            
            # Check if a boss encounter was triggered (no popup, go directly to VS screen)
            elif (getattr(gs, "encounter_type", None) == "BOSS"
                and gs.encounter_sprite is not None
                and not getattr(gs, "_went_to_summoner", False)
                and not gs.in_encounter):
                # Boss encounter - go directly to VS screen
                try:
                    pygame.mixer.music.fadeout(200)
                except Exception:
                    pass
                ch = getattr(gs, "walking_channel", None)
                if ch:
                    try: ch.stop()
                    except Exception: pass
                gs.is_walking = False
                gs.is_running = False
                gs.movement_sfx_state = None
                gs.walking_channel = None
                gs._went_to_summoner = True
                mode = MODE_BOSS_VS
            
            # Check if a regular summoner encounter was triggered (no popup, go directly to battle)
            elif (gs.encounter_sprite is not None 
                and gs.encounter_stats is None 
                and not getattr(gs, "_went_to_summoner", False)
                and not getattr(gs, "_went_to_wild", False)
                and not gs.in_encounter
                and getattr(gs, "encounter_type", None) != "BOSS"
                and getattr(gs, "encounter_type", None) != "RIVAL"
                and getattr(gs, "encounter_type", None) != "WILD_VESSEL"
                and getattr(gs, "encounter_type", None) != "MONSTER"
                and hasattr(gs, "encounter_summoner_filename")
                and getattr(gs, "encounter_summoner_filename", None) is not None):  # Regular summoners have filename set
                # Regular summoner encounter - go directly to battle
                print(f"🎯 Regular summoner battle triggered: {getattr(gs, 'encounter_name', 'Unknown')}")
                try:
                    pygame.mixer.music.fadeout(200)
                except Exception:
                    pass
                ch = getattr(gs, "walking_channel", None)
                if ch:
                    try: ch.stop()
                    except Exception: pass
                gs.is_walking = False
                gs.is_running = False
                gs.movement_sfx_state = None
                gs.walking_channel = None
                gs._went_to_summoner = True
                mode = MODE_SUMMONER_BATTLE
            actors.update_merchants(gs, dt, gs.player_half)
            actors.update_taverns(gs, dt, gs.player_half)
            actors.update_chests(gs, dt, gs.player_half)
            # Check for boss spawns based on score
            from world import bosses
            bosses.check_and_spawn_bosses(gs)
            # Check for rival spawns based on milestones
            from world import rival
            if getattr(gs, "first_rival_encounter_complete", False):
                # Only check for subsequent encounters after first one is complete
                rival.check_and_spawn_rival(gs)
            try_trigger_encounter(gs, RIVAL_SUMMONERS, MERCHANT_FRAMES, TAVERN_SPRITE, MONSTERS, CHEST_SPRITE)

            cam = world.get_camera_offset(gs.player_pos, S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT, gs.player_half)
            world.draw_repeating_road(virtual_screen, cam.x, cam.y)
            pg.update_needed(cam.y, S.LOGICAL_HEIGHT)
            pg.draw_props(virtual_screen, cam.x, cam.y, S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT)
            actors.draw_vessels(virtual_screen, cam, gs, mist_frame, S.DEBUG_OVERWORLD)
            actors.draw_monsters(virtual_screen, cam, gs, mist_frame, S.DEBUG_OVERWORLD)
            actors.draw_rivals(virtual_screen, cam, gs)
            actors.draw_merchants(virtual_screen, cam, gs)
            actors.draw_taverns(virtual_screen, cam, gs)
            actors.draw_chests(virtual_screen, cam, gs)
            actors.draw_bosses(virtual_screen, cam, gs)
            
            # Draw rival during intro walk-down
            if getattr(gs, "rival_intro_active", False) and hasattr(gs, "rival_intro_state"):
                state = gs.rival_intro_state
                rival_pos = state["rival_pos"]
                if hasattr(gs, "rival_image") and gs.rival_image:
                    rival_half = Vector2(gs.rival_image.get_width() / 2, gs.rival_image.get_height() / 2)
                    virtual_screen.blit(
                        gs.rival_image,
                        (rival_pos.x - cam.x - rival_half.x + PLAYER_VISUAL_X_OFFSET,
                         rival_pos.y - cam.y - rival_half.y)
                    )

            virtual_screen.blit(
                gs.player_image,
                (gs.player_pos.x - cam.x - gs.player_half.x + PLAYER_VISUAL_X_OFFSET,
                gs.player_pos.y - cam.y - gs.player_half.y)
            )
            
            # Draw speech bubble when near merchant (if not in shop)
            if gs.near_merchant and not gs.shop_open:
                draw_merchant_speech_bubble(virtual_screen, cam, gs, gs.near_merchant)
            
            # Draw speech bubble when near tavern
            if getattr(gs, "near_tavern", None):
                draw_tavern_speech_bubble(virtual_screen, cam, gs, gs.near_tavern)
            
            # Draw speech bubble when near chest
            if getattr(gs, "near_chest", None):
                draw_chest_speech_bubble(virtual_screen, cam, gs, gs.near_chest)

        # --- Draw HUD then modals (z-order: Bag < Party Manager < Ledger < Shop < Rest Popup) ---
        left_hud.draw(virtual_screen, gs)  # Left side HUD panel behind character token and party UI (textbox style)
        party_ui.draw_party_hud(virtual_screen, gs)  # Character token and party slots (draws on top of left_hud)
        score_display.draw_score(virtual_screen, gs, dt)  # Score in top right (animated)
        bottom_right_hud.draw(virtual_screen, gs)  # Bottom right HUD panel with buttons inside (textbox style)
        
        # Draw chest result card if active (drawn on top of HUD)
        if getattr(gs, "chest_result_card_active", False):
            draw_chest_result_card(virtual_screen, gs, dt)
        
        if bag_ui.is_open():
            bag_ui.draw_popup(virtual_screen, gs)
        # Always draw party manager to show heal textbox even when closed
        party_manager.draw(virtual_screen, gs)
        
        # Draw rival dialogue textbox LAST (on top of everything) if in dialogue phase
        if getattr(gs, "rival_intro_active", False) and hasattr(gs, "rival_intro_state"):
            state = gs.rival_intro_state
            if state.get("phase") == "dialogue":
                _draw_rival_dialogue(virtual_screen, gs, dt)
        
        if ledger.is_open():
            ledger.draw(virtual_screen, gs)
        if gs.shop_open:
            draw_shop_ui(virtual_screen, gs)
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
        
        # ===== Death gate check: AFTER all normal game logic =====
        # This runs AFTER events, updates, and drawing, so it doesn't block normal gameplay
        # Skip death saves check if we're in a rival battle (rival battles handle loss differently)
        # Also skip if we just started a new game (vessels might not be initialized yet)
        # Also skip if rival intro is active or buff selection is pending
        # Also skip if we just finished a rival battle (prevents death gate from triggering after rival battle)
        is_rival_battle = getattr(gs, "_was_rival_battle", False) or getattr(gs, "encounter_type", None) == "RIVAL"
        just_finished_rival_battle = getattr(gs, "_just_finished_rival_battle", False)
        game_was_loaded = getattr(gs, "_game_was_loaded_from_save", False)
        just_started_new_game = not game_was_loaded and getattr(gs, "distance_travelled", 0.0) == 0.0
        rival_intro_active = getattr(gs, "rival_intro_active", False)
        buff_selection_pending = getattr(gs, "pending_buff_selection", False) or buff_popup.is_active()
        waiting_for_first_blessing = not getattr(gs, "first_overworld_blessing_given", False)
        
        # Skip death gate check entirely if no vessels exist yet (e.g., right after intro video)
        stats = getattr(gs, "party_vessel_stats", None) or []
        has_any_member = any(isinstance(st, dict) and st.get("hp", 0) > 0 for st in stats)
        
        # Debug: Check if we're in battle mode (shouldn't run death gate during battle)
        in_battle_mode = getattr(gs, "mode", None) == MODE_BATTLE
        
        # Debug output for death gate check
        if has_any_member:
            # Check vessel HP status
            all_dead = not any(
                isinstance(st, dict) and int(st.get("current_hp", st.get("hp", 0)) or 0) > 0
                for st in stats
            )
            if all_dead:
                print(f"🔍 Death gate check: All vessels dead, conditions:")
                print(f"   in_battle_mode={in_battle_mode}")
                print(f"   is_rival_battle={is_rival_battle}")
                print(f"   just_finished_rival_battle={just_finished_rival_battle}")
                print(f"   just_started_new_game={just_started_new_game}")
                print(f"   rival_intro_active={rival_intro_active}")
                print(f"   buff_selection_pending={buff_selection_pending}")
                print(f"   waiting_for_first_blessing={waiting_for_first_blessing}")
                print(f"   has_any_member={has_any_member}")
        
        # Skip death gate if: in battle mode, rival battle, just finished rival battle, just started, rival intro active, buff selection pending, or waiting for first blessing
        if not in_battle_mode and not is_rival_battle and not just_finished_rival_battle and not just_started_new_game and not rival_intro_active and not buff_selection_pending and not waiting_for_first_blessing and has_any_member:
            # Only initialize current_hp if it's completely missing (not if it's 0 - that means vessel is dead!)
            for st in stats:
                if isinstance(st, dict):
                    if "current_hp" not in st:  # Only fix if completely missing, not if it's 0
                        max_hp = st.get("hp", 10)
                        if max_hp > 0:  # Only fix if vessel has valid max HP
                            st["current_hp"] = max_hp
                            print(f"⚠️ Fixed missing current_hp in death gate check: set to {max_hp}")
                    # Don't fix vessels that are at 0 HP - that means they're dead and death saves should trigger
            
            has_living = any(
                isinstance(st, dict) and int(st.get("current_hp", st.get("hp", 0)) or 0) > 0
                for st in stats
            )
            if not has_living:
                # Debug: print vessel HP before triggering death saves
                print(f"💀 Death gate triggered! Vessel HP status:")
                for i, st in enumerate(stats):
                    if isinstance(st, dict):
                        hp = st.get("hp", 0)
                        current_hp = st.get("current_hp", 0)
                        print(f"   Vessel {i+1}: HP={hp}, current_hp={current_hp}")
                
                # Save game when all vessels hit 0 HP (prevents save scumming)
                try:
                    saves.save_game(gs, force=True)
                    print("💾 Game saved: All vessels at 0 HP - entering death saves")
                except Exception as e:
                    print(f"⚠️ Save failed on death: {e}")
                
                mode = MODE_DEATH_SAVES
                enter_mode(mode, gs, deps)
                # Don't use continue here - let the loop continue normally to process the mode change
