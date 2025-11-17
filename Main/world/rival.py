# ============================================================
# world/rival.py — Rival System
# Handles rival spawning, animations, team generation, and encounters
# ============================================================

import os
import random
import pygame
from typing import Dict, List, Optional
from pygame.math import Vector2

import settings as S
from combat.team_randomizer import (
    generate_enemy_team, 
    generate_enemy_team_fixed_size, 
    highest_party_level, 
    scaled_enemy_level,
)
# Import private functions for level calculation (same as boss generation)
from combat.team_randomizer import _bracket_for_level, _level_for_enemy
from combat.vessel_stats import generate_vessel_stats_from_asset
from systems.points import get_total_points

# Rival milestone thresholds
RIVAL_MILESTONES = [10000, 25000, 35000, 45000, 55000, 65000, 75000, 85000, 95000, 105000]
# After 10k, pattern continues: every 10k starting from 25k (25k, 35k, 45k, etc.)

# Boss sprite paths (same as regular bosses)
BOSS_SPRITE_DIR = os.path.join("Assets", "SummonersBoss")
MALE_BOSS_SPRITES = [f"BSummonerM{i}.png" for i in range(1, 9)]  # M1-M8
FEMALE_BOSS_SPRITES = [f"BSummonerF{i}.png" for i in range(1, 4)]  # F1-F3


def load_rival_walk_frames(gender: str, target_size: tuple[int, int]) -> List[pygame.Surface]:
    """
    Load walking animation frames for rival based on gender.
    """
    base = os.path.join("Assets", "PlayableCharacters")
    patterns = []
    
    if gender.lower() == "male":
        patterns = ["Mwalk*.png", "male_walk*.png"]
    else:
        patterns = ["Fwalk*.png", "female_walk*.png"]
    
    import glob
    import re
    
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(base, pattern)))
    
    # Natural sort by trailing number
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
            print(f"⚠️ Failed to load rival walk frame '{f}': {e}")
    
    if frames:
        print(f"🖼️ Loaded {len(frames)} rival walk frames for '{gender}'")
    return frames


def load_rival_idle_sprite(gender: str) -> Optional[pygame.Surface]:
    """Load idle sprite for rival based on gender."""
    if gender.lower() == "male":
        path = os.path.join("Assets", "PlayableCharacters", "CharacterMale.png")
    else:
        path = os.path.join("Assets", "PlayableCharacters", "CharacterFemale.png")
    
    if os.path.exists(path):
        try:
            sprite = pygame.image.load(path).convert_alpha()
            sprite = pygame.transform.smoothscale(sprite, S.PLAYER_SIZE)
            return sprite
        except Exception as e:
            print(f"⚠️ Failed to load rival idle sprite '{path}': {e}")
    
    return None


def load_rival_boss_sprite(gs) -> Optional[pygame.Surface]:
    """
    Load boss sprite for rival (for battle screen).
    Uses CharacterFemale.png or CharacterMale.png from PlayableCharacters.
    """
    gender = getattr(gs, "rival_gender", "male")
    
    if gender.lower() == "female":
        path = os.path.join("Assets", "PlayableCharacters", "CharacterFemale.png")
    else:
        path = os.path.join("Assets", "PlayableCharacters", "CharacterMale.png")
    
    if os.path.exists(path):
        try:
            sprite = pygame.image.load(path).convert_alpha()
            # Scale to appropriate size (same as boss sprites)
            target_height = 420
            w, h = sprite.get_size()
            if h > 0:
                scale = target_height / float(h)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                sprite = pygame.transform.smoothscale(sprite, (new_w, new_h))
            return sprite
        except Exception as e:
            print(f"⚠️ Failed to load rival boss sprite '{path}': {e}")
    
    return None


def initialize_rival_animations(gs):
    """Initialize rival walking animations and sprites."""
    gender = getattr(gs, "rival_gender", None)
    if not gender:
        print("⚠️ Cannot initialize rival animations: no rival_gender set")
        return
    
    # Load idle sprite
    gs.rival_idle = load_rival_idle_sprite(gender)
    if gs.rival_idle:
        gs.rival_image = gs.rival_idle
    
    # Load walk frames and create animator
    walk_frames = load_rival_walk_frames(gender, S.PLAYER_SIZE)
    if not walk_frames:
        print("ℹ️ No rival walk frames found; using idle fallback.")
        walk_frames = [gs.rival_idle] * 3 if gs.rival_idle else []
    
    if walk_frames:
        # Create a simple animator class inline (to avoid circular import)
        class SimpleAnimator:
            def __init__(self, frames, fps=12, loop=True):  # Faster fps for running animation
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
        
        gs.rival_walk_anim = SimpleAnimator(walk_frames, fps=8, loop=True)  # Normal walking animation speed
    
    # Load boss sprite
    gs.rival_sprite = load_rival_boss_sprite(gs)
    
    print(f"✅ Initialized rival animations for {gender}")


def get_next_rival_milestone(current_score: int, completed_milestones: List[int]) -> Optional[int]:
    """
    Get the next rival milestone that should trigger.
    Returns None if no more milestones.
    """
    for milestone in RIVAL_MILESTONES:
        if milestone not in completed_milestones and current_score >= milestone:
            return milestone
    return None


def generate_rival_team(gs, encounter_number: int) -> Dict:
    """
    Generate rival team based on encounter number.
    ALWAYS includes the rival's starter vessel as the FIRST vessel.
    Uses boss-style fixed team generation for additional vessels.
    
    Encounter 1: 1 vessel (starter only, level 1) - NO OTHER VESSELS
    Encounter 2: 3 vessels (starter + 2 others)
    Encounter 3: 5 vessels (starter + 4 others)
    Encounter 4+: 6 vessels (starter + 5 others)
    """
    from rolling.roller import Roller
    
    # Get rival starter name (MUST be set - assigned during starter selection)
    rival_starter_name = getattr(gs, "rival_starter_name", None)
    if not rival_starter_name:
        print("⚠️ ERROR: No rival starter name found! Rival starter should be assigned during starter selection.")
        # Try to determine from rival_starter_class
        rival_class = getattr(gs, "rival_starter_class", None)
        if rival_class:
            # Fallback: try to pick a starter from the class
            import os
            import glob
            # random is already imported at module level
            starter_dir = os.path.join("Assets", "Starters")
            pattern = f"Starter{rival_class.capitalize()}*.png"
            candidates = glob.glob(os.path.join(starter_dir, pattern))
            if candidates:
                chosen = random.choice(candidates)
                rival_starter_name = os.path.basename(chosen).replace(".png", "")
                print(f"⚠️ Picked fallback starter: {rival_starter_name}")
            else:
                rival_starter_name = "StarterRogue1"  # Final fallback
                print(f"⚠️ Using hardcoded fallback: {rival_starter_name}")
        else:
            rival_starter_name = "StarterRogue1"  # Final fallback
            print(f"⚠️ Using hardcoded fallback: {rival_starter_name}")
    
    # Determine party size
    if encounter_number == 1:
        party_size = 1
    elif encounter_number == 2:
        party_size = 3
    elif encounter_number == 3:
        party_size = 5
    else:
        party_size = 6
    
    print(f"🎯 [generate_rival_team] Encounter #{encounter_number}, party_size={party_size}, starter={rival_starter_name}")
    
    # Calculate level for this encounter
    player_max_level = highest_party_level(gs)
    
    if encounter_number == 1:
        # First encounter: starter is level 1 - ALWAYS
        starter_level = 1
    else:
        # Subsequent encounters: scale with player (use same logic as boss generation)
        bracket = _bracket_for_level(player_max_level)
        rng = Roller(random.randrange(1 << 30))
        starter_level = _level_for_enemy(player_max_level, rng, bracket)
    
    print(f"🎯 [generate_rival_team] Starter level: {starter_level} (player_max={player_max_level}, encounter={encounter_number})")
    
    # Convert asset name to token name format FIRST (team_randomizer.py uses token names)
    # rival_starter_name is like "StarterRogue5", need "StarterTokenRogue5.png"
    from systems.asset_links import vessel_to_token
    rival_starter_token = vessel_to_token(rival_starter_name)
    if not rival_starter_token:
        # Fallback: try adding "Token" manually
        import os
        base = os.path.splitext(rival_starter_name)[0]
        rival_starter_token = base.replace("Starter", "StarterToken", 1) + ".png"
        print(f"⚠️ [generate_rival_team] vessel_to_token failed, using manual conversion: {rival_starter_token}")
    
    print(f"🎯 [generate_rival_team] Starter asset: {rival_starter_name} -> Token: {rival_starter_token}")
    
    # Create starter vessel stats using ASSET name (not token name)
    # generate_vessel_stats_from_asset expects asset names like "StarterRogue5"
    # The regex in _extract_class looks for "^Starter(?P<class3>[A-Za-z]+)" which won't match "StarterToken..."
    # So we use the original asset name for stats generation, but token name for team names
    starter_stats = generate_vessel_stats_from_asset(rival_starter_name, level=starter_level)
    
    # For encounter 1: ONLY return the starter vessel, nothing else
    if encounter_number == 1:
        team = {
            "names": [rival_starter_token],  # Use token name format
            "levels": [starter_level],
            "stats": [starter_stats],
        }
        print(f"✅ [generate_rival_team] Encounter 1: Returning ONLY starter vessel: {rival_starter_token} (level {starter_level})")
        print(f"   Team size: {len(team['names'])} vessel(s)")
        return team
    
    # For encounters with more than 1 vessel, generate additional vessels using boss logic
    # Build team with starter first (use token name format)
    team = {
        "names": [rival_starter_token],  # Use token name format
        "levels": [starter_level],
        "stats": [starter_stats],
    }
    
    additional_count = party_size - 1  # We already have the starter
    
    # Use boss-style generation: fixed size, seeded RNG, no starters, no dupes
    # Create RNG seeded by encounter number for deterministic teams
    seed = (encounter_number * 1000) & 0x7FFFFFFF
    rng = Roller(seed)
    
    print(f"🎯 [generate_rival_team] Generating {additional_count} additional vessels (excluding starter)")
    
    # Generate additional team using boss logic (fixed size, no starters, no dupes)
    additional_team = generate_enemy_team_fixed_size(
        gs,
        team_size=additional_count,
        rng=rng,
        rare_chance=0.12,
        allow_starters=False,  # Exclude starters (rival already has theirs)
        allow_dupes=False,     # No duplicates
    )
    
    additional_names = additional_team.get("names", [])
    additional_levels = additional_team.get("levels", [])
    additional_stats = additional_team.get("stats", [])
    
    # Filter out starter if it somehow got included (shouldn't happen with allow_starters=False)
    # Check both asset name and token name formats
    filtered_names = [n for n in additional_names if n != rival_starter_name and n != rival_starter_token]
    filtered_levels = []
    filtered_stats = []
    
    # Rebuild levels and stats arrays, matching filtered names
    for i, name in enumerate(additional_names):
        if name != rival_starter_name and name != rival_starter_token:
            if i < len(additional_levels):
                filtered_levels.append(additional_levels[i])
            if i < len(additional_stats):
                filtered_stats.append(additional_stats[i])
    
    # Ensure we have the right number of additional vessels
    while len(filtered_names) < additional_count:
        # Generate one more vessel if needed (excluding starters)
        extra_team = generate_enemy_team_fixed_size(
            gs,
            team_size=1,
            rng=Roller(random.randrange(1 << 30)),
            allow_starters=False,
            allow_dupes=False,
        )
        if extra_team.get("names"):
            extra_name = extra_team["names"][0]
            if extra_name != rival_starter_name and extra_name != rival_starter_token and extra_name not in filtered_names:
                filtered_names.append(extra_name)
                filtered_levels.append(extra_team.get("levels", [1])[0])
                filtered_stats.append(extra_team.get("stats", [{}])[0])
    
    # Combine: starter FIRST, then additional vessels (use token name format)
    team["names"] = [rival_starter_token] + filtered_names[:additional_count]
    team["levels"] = [starter_level] + filtered_levels[:additional_count]
    team["stats"] = [starter_stats] + filtered_stats[:additional_count]
    
    # Final validation: ensure we have exactly party_size vessels
    if len(team["names"]) != party_size:
        print(f"⚠️ [generate_rival_team] WARNING: Team size mismatch! Expected {party_size}, got {len(team['names'])}")
        # Trim to exact party size (starter should always be first)
        team["names"] = team["names"][:party_size]
        team["levels"] = team["levels"][:party_size]
        team["stats"] = team["stats"][:party_size]
    
    # Validate starter is first (check both asset and token name formats)
    if team["names"][0] != rival_starter_token and team["names"][0] != rival_starter_name:
        print(f"⚠️ [generate_rival_team] ERROR: Starter is not first! Moving to front.")
        # Find starter index (check both formats)
        starter_idx = None
        try:
            starter_idx = team["names"].index(rival_starter_token)
        except ValueError:
            try:
                starter_idx = team["names"].index(rival_starter_name)
            except ValueError:
                pass
        
        if starter_idx is not None:
            # Move starter to front
            team["names"].insert(0, team["names"].pop(starter_idx))
            team["levels"].insert(0, team["levels"].pop(starter_idx))
            team["stats"].insert(0, team["stats"].pop(starter_idx))
        else:
            print(f"⚠️ [generate_rival_team] ERROR: Starter not found in team!")
    
    print(f"✅ [generate_rival_team] Generated team: {len(team['names'])} vessels")
    print(f"   Starter: {team['names'][0]} (level {team['levels'][0]})")
    if len(team["names"]) > 1:
        print(f"   Additional: {team['names'][1:]}")
    
    return team


def _generate_rival_challenge_text(gs, encounter_number: int = 1) -> str:
    """Generate medieval challenge dialogue text for the rival."""
    # Get rival name - prioritize gs.rival_name (set during name entry)
    rival_name = getattr(gs, "rival_name", None)
    print(f"🔍 [_generate_rival_challenge_text] gs.rival_name = '{rival_name}'")
    
    # Only use fallback if rival_name is None or empty string, not if it's "Rival" (which is valid)
    if not rival_name:
        # Fallback: try to get from encounter data if available
        if hasattr(gs, "rival_encounter_data") and gs.rival_encounter_data:
            rival_name = gs.rival_encounter_data.get("name")
            print(f"🔍 [_generate_rival_challenge_text] Using encounter_data name: '{rival_name}'")
        if not rival_name:
            rival_name = "Rival"  # Final fallback
            print(f"⚠️ [_generate_rival_challenge_text] Using fallback 'Rival'")
    
    player_name = getattr(gs, "player_name", "Summoner")
    print(f"💬 [_generate_rival_challenge_text] Final: rival_name='{rival_name}', player_name='{player_name}'")
    
    # First meeting dialogue (encounter_number == 1)
    if encounter_number == 1:
        first_meeting = [
            f"{rival_name}: So, {player_name}... we meet at last. I have been watching your progress, and I must say, I am not impressed.",
            f"{rival_name}: {player_name}! The time has come to prove yourself. Face me in combat, and we shall see who is truly worthy!",
            f"{rival_name}: Halt, {player_name}! I challenge you to a duel of vessels. Let us settle this once and for all!",
            f"{rival_name}: {player_name}, I have heard tales of your journey. Now let us see if you are truly worthy of such praise.",
            f"{rival_name}: So you are the one they speak of. Very well, {player_name}. Let us test our strength against each other!",
        ]
        # random is already imported at module level
        return random.choice(first_meeting)
    else:
        # Subsequent meetings dialogue
        subsequent_meetings = [
            f"{rival_name}: So we meet again, {player_name}. I have been waiting for this moment. Prepare yourself!",
            f"{rival_name}: {player_name}, you have grown stronger, but so have I. Let us test our strength against each other!",
            f"{rival_name}: We meet once more, {player_name}. This time, I will not hold back!",
            f"{rival_name}: {player_name}! Our paths cross again. Let us see how much you have improved since our last encounter!",
            f"{rival_name}: You again, {player_name}. I have been training for this rematch. Do not disappoint me!",
        ]
        # random is already imported at module level
        return random.choice(subsequent_meetings)


def trigger_rival_intro_animation(gs, encounter_number: int, rival_data: dict = None):
    """
    Trigger rival intro animation and dialogue for any encounter (first or subsequent).
    Sets up the walk-down animation and battle.
    Called from main.py or actors.py.
    """
    # Initialize rival animations if not already done
    if not hasattr(gs, "rival_walk_anim") or gs.rival_walk_anim is None:
        initialize_rival_animations(gs)
    
    # Get encounter data (either from parameter or generate for first encounter)
    if rival_data is None:
        # First encounter - generate team
        print(f"🎯 [trigger_rival_intro_animation] Generating team for encounter #{encounter_number}")
        print(f"   rival_starter_name: {getattr(gs, 'rival_starter_name', 'NOT SET')}")
        print(f"   rival_starter_class: {getattr(gs, 'rival_starter_class', 'NOT SET')}")
        
        team = generate_rival_team(gs, encounter_number)
        
        # Validate team structure
        print(f"🎯 [trigger_rival_intro_animation] Generated team:")
        print(f"   names: {team.get('names', [])}")
        print(f"   levels: {team.get('levels', [])}")
        print(f"   stats count: {len(team.get('stats', []))}")
        print(f"   Team size: {len(team.get('names', []))} vessels")
        
        # Use gs.rival_name (set during name entry), fallback to "Rival"
        actual_rival_name = getattr(gs, "rival_name", None) or "Rival"
        gs.rival_encounter_data = {
            "name": actual_rival_name,
            "gender": getattr(gs, "rival_gender", "male"),
            "encounter_number": encounter_number,
            "team": team,  # Store the team directly (battle.py expects this)
            "sprite": getattr(gs, "rival_sprite", None),
        }
        print(f"✅ [trigger_rival_intro_animation] Stored rival_encounter_data with team size: {len(team.get('names', []))}")
    else:
        # Subsequent encounter - use provided data, but update name from gs.rival_name if available
        gs.rival_encounter_data = rival_data.copy()  # Make a copy to avoid modifying original
        # Update name from gs.rival_name if it's set (should always be set after name entry)
        if hasattr(gs, "rival_name") and gs.rival_name:
            gs.rival_encounter_data["name"] = gs.rival_name
    
    # Import here to avoid circular import
    from pygame.math import Vector2
    import settings as S
    
    # Set up rival intro state
    gs.rival_intro_active = True
    # Stop halfway down the screen (in world coordinates)
    # Player is at gs.player_pos.y, we want rival to stop halfway between top of screen and player
    # Camera keeps player near bottom, so halfway is approximately player_y - (screen_height / 2)
    halfway_y_world = gs.player_pos.y - (S.LOGICAL_HEIGHT / 2)
    
    # Generate dialogue text (will use gs.rival_name from name entry)
    # Make sure we use the actual rival name, not the default
    actual_rival_name = getattr(gs, "rival_name", None)
    if not actual_rival_name:
        # If rival_name is not set, try to get it from rival_data for subsequent encounters
        if rival_data and rival_data.get("name"):
            actual_rival_name = rival_data["name"]
            gs.rival_name = actual_rival_name  # Update gs.rival_name for consistency
        else:
            actual_rival_name = "Rival"
            gs.rival_name = actual_rival_name
    
    dialogue_text = _generate_rival_challenge_text(gs, encounter_number)
    # Debug: verify the name is correct
    current_rival_name = getattr(gs, "rival_name", "NOT SET")
    print(f"💬 Generated dialogue text: '{dialogue_text[:80]}...'")
    print(f"   gs.rival_name='{current_rival_name}', actual_rival_name='{actual_rival_name}'")
    
    gs.rival_intro_state = {
        "phase": "walk_down",  # "walk_down" -> "dialogue" -> "battle"
        "rival_pos": Vector2(gs.player_pos.x, gs.player_pos.y - S.LOGICAL_HEIGHT),  # Start above screen
        "target_y": halfway_y_world,  # Stop halfway down the screen (world coordinates)
        "walk_speed": 100.0,  # Normal walking speed (pixels per second)
        "timer": 0.0,
        "dialogue_text": dialogue_text,
        "dialogue_blink_t": 0.0,
    }
    print(f"🎬 Rival intro started (encounter #{encounter_number}): start_y={gs.rival_intro_state['rival_pos'].y:.1f}, target_y={halfway_y_world:.1f}, player_y={gs.player_pos.y:.1f}")


def check_and_spawn_rival(gs):
    """
    Check if rival should spawn based on score milestones.
    Called from main loop.
    """
    if not hasattr(gs, "rival_name") or not gs.rival_name:
        return  # No rival set up yet
    
    current_score = get_total_points(gs)
    
    # Initialize completed milestones list if not exists
    if not hasattr(gs, "rival_encounters_completed"):
        gs.rival_encounters_completed = []
    
    # Initialize rivals_on_map if not exists
    if not hasattr(gs, "rivals_on_map"):
        gs.rivals_on_map = []
    
    # Check if we should spawn a rival
    next_milestone = get_next_rival_milestone(current_score, gs.rival_encounters_completed)
    
    if next_milestone is not None:
        # Check if rival intro animation is already active (prevent duplicate triggers)
        if getattr(gs, "rival_intro_active", False):
            return  # Already triggering rival intro
        
        # Check if rival is already spawned for this milestone
        already_spawned = any(
            r.get("milestone") == next_milestone 
            for r in gs.rivals_on_map
        )
        
        if not already_spawned:
            # Determine encounter number
            # First encounter (#1) happens right after initial buff selection (no milestone)
            # Subsequent encounters use milestones, so encounter_number = completed_milestones + 1
            # But we need to account for the first encounter if it's been completed
            first_completed = getattr(gs, "first_rival_encounter_complete", False)
            base_encounters = len(gs.rival_encounters_completed)
            if first_completed:
                encounter_number = base_encounters + 2  # +1 for first encounter, +1 for this one
            else:
                encounter_number = base_encounters + 1  # First encounter not done yet, so this is #1
            
            # Generate rival team
            team = generate_rival_team(gs, encounter_number)
            
            # Instead of spawning on map, trigger intro animation immediately
            print(f"🎯 Rival milestone {next_milestone} reached - triggering intro animation (encounter #{encounter_number})")
            
            # Create rival data for the intro animation
            rival_data = {
                "name": getattr(gs, "rival_name", "Rival"),
                "gender": getattr(gs, "rival_gender", "male"),
                "encounter_number": encounter_number,
                "milestone": next_milestone,
                "team": team,
                "sprite": getattr(gs, "rival_sprite", None),
            }
            
            # Trigger the intro animation immediately (no need to spawn on map)
            trigger_rival_intro_animation(gs, encounter_number, rival_data)
            
            # Mark milestone as spawned (will be marked as completed after battle)
            print(f"✅ Rival intro triggered at milestone {next_milestone} (encounter #{encounter_number})")


def spawn_rival_ahead(gs, milestone: int, encounter_number: int, team: Dict):
    """
    Spawn rival ahead of player on the map.
    Similar to spawn_boss_ahead but for rivals.
    """
    from world import actors
    
    # Calculate spawn position (ahead of player)
    start_x = getattr(gs, "start_x", S.WORLD_W // 2)
    spawn_distance = S.HEIGHT * 0.8  # Spawn ahead of player
    
    x = start_x + OVERWORLD_LANE_X_OFFSET if hasattr(S, "OVERWORLD_LANE_X_OFFSET") else start_x
    y = gs.player_pos.y - spawn_distance
    
    # Create rival data
    rival_data = {
        "pos": Vector2(x, y),
        "name": getattr(gs, "rival_name", "Rival"),
        "gender": getattr(gs, "rival_gender", "male"),
        "milestone": milestone,
        "encounter_number": encounter_number,
        "team": team,
        "sprite": getattr(gs, "rival_sprite", None),  # Boss sprite for VS screen
    }
    
    gs.rivals_on_map.append(rival_data)
    print(f"✅ Rival '{rival_data['name']}' spawned at position ({x}, {y})")



