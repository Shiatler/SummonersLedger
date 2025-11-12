# ============================================================
# world/bosses.py — Boss Spawning & Management System
# Handles boss milestone tracking, team generation, and sprite loading
# ============================================================

import os
import random
import pygame
from typing import Dict, List, Optional, Tuple

from combat.team_randomizer import generate_enemy_team, highest_party_level
from systems.name_generator import generate_summoner_name


# Boss milestone thresholds
FIRST_BOSS_SCORE = 5000
SECOND_BOSS_SCORE = 12500
SPECIAL_BOSSES = {
    50000: "Cynthia",
    100000: "Master Oak",
}

# Boss sprite paths
BOSS_SPRITE_DIR = os.path.join("Assets", "SummonersBoss")
MALE_BOSS_SPRITES = [f"BSummonerM{i}.png" for i in range(1, 9)]  # M1-M8
FEMALE_BOSS_SPRITES = [f"BSummonerF{i}.png" for i in range(1, 4)]  # F1-F3


def get_next_boss_threshold(current_score: int, defeated_bosses: List[int], spawned_bosses: List[int]) -> Optional[int]:
    """
    Calculate the next boss threshold based on current score and defeated/spawned bosses.
    Returns None if no more bosses should spawn.
    """
    # First boss at 5000
    if FIRST_BOSS_SCORE not in defeated_bosses and FIRST_BOSS_SCORE not in spawned_bosses and current_score >= FIRST_BOSS_SCORE:
        print(f"[get_next_boss_threshold] Returning FIRST_BOSS_SCORE ({FIRST_BOSS_SCORE})")
        return FIRST_BOSS_SCORE
    
    # Second boss at 12500
    if SECOND_BOSS_SCORE not in defeated_bosses and SECOND_BOSS_SCORE not in spawned_bosses and current_score >= SECOND_BOSS_SCORE:
        return SECOND_BOSS_SCORE
    
    # After second boss, spawn every 5000-10000 points (deterministic per boss)
    if defeated_bosses:
        last_boss_score = max(defeated_bosses)
        if last_boss_score >= SECOND_BOSS_SCORE:
            # Calculate next threshold deterministically based on last boss score
            # Use a deterministic seed to ensure same threshold each time for this boss
            import random as _random
            _random.seed(last_boss_score)
            gap = _random.randint(5000, 10000)
            _random.seed()  # Reset seed
            next_threshold = last_boss_score + gap
            
            # Check if this threshold was already spawned
            if next_threshold not in spawned_bosses and current_score >= next_threshold:
                return next_threshold
    
    # Check special bosses
    for threshold, name in SPECIAL_BOSSES.items():
        if threshold not in defeated_bosses and threshold not in spawned_bosses and current_score >= threshold:
            return threshold
    
    return None


def load_boss_sprite(boss_name: str, gender: str) -> Optional[pygame.Surface]:
    """Load boss sprite based on name and gender."""
    # Special bosses have fixed sprites
    if boss_name == "Cynthia":
        path = os.path.join(BOSS_SPRITE_DIR, "Cynthia.png")
    elif boss_name == "Master Oak":
        path = os.path.join(BOSS_SPRITE_DIR, "Master Oak.png")
    else:
        # Random boss sprite based on gender
        if gender.lower() == "female":
            sprite_file = random.choice(FEMALE_BOSS_SPRITES)
        else:
            sprite_file = random.choice(MALE_BOSS_SPRITES)
        path = os.path.join(BOSS_SPRITE_DIR, sprite_file)
    
    if os.path.exists(path):
        try:
            sprite = pygame.image.load(path).convert_alpha()
            # Scale to appropriate size (similar to summoner sprites)
            target_height = 420  # Same as enemy summoner height
            w, h = sprite.get_size()
            if h > 0:
                scale = target_height / float(h)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                sprite = pygame.transform.smoothscale(sprite, (new_w, new_h))
            return sprite
        except Exception as e:
            print(f"⚠️ Failed to load boss sprite '{path}': {e}")
    
    return None


def generate_boss_name(score_threshold: int, gender: str) -> str:
    """Generate boss name based on score threshold and gender."""
    # Special bosses have fixed names
    if score_threshold == 50000:
        return "Cynthia"
    if score_threshold == 100000:
        return "Master Oak"
    
    # Generate random name for regular bosses
    # Use a deterministic seed based on score threshold for consistency
    random.seed(score_threshold)
    
    # Create a fake token name for name generation
    if gender.lower() == "female":
        fake_token = f"FBoss{score_threshold}"
    else:
        fake_token = f"MBoss{score_threshold}"
    
    name = generate_summoner_name(fake_token)
    
    # Reset random seed
    random.seed()
    
    return name


def determine_boss_party_size(boss_index: int) -> int:
    """
    Determine boss party size based on which boss it is.
    First boss: 3 vessels
    Second boss: 5 vessels
    Rest: 6 vessels
    """
    if boss_index == 0:  # First boss
        return 3
    elif boss_index == 1:  # Second boss
        return 5
    else:  # All subsequent bosses
        return 6


def create_boss_data(gs, score_threshold: int, defeated_bosses: List[int]) -> Optional[Dict]:
    """
    Create boss data dictionary with sprite, name, team, etc.
    Returns None if boss shouldn't spawn yet.
    """
    # Determine boss index (which boss in sequence)
    boss_index = len(defeated_bosses)
    
    # Determine gender (random for regular bosses, fixed for special)
    if score_threshold in SPECIAL_BOSSES:
        # Special bosses: Cynthia is female, Master Oak is male
        gender = "female" if score_threshold == 50000 else "male"
    else:
        gender = random.choice(["male", "female"])
    
    # Generate boss name
    boss_name = generate_boss_name(score_threshold, gender)
    
    # Load boss sprite
    sprite = load_boss_sprite(boss_name, gender)
    if not sprite:
        print(f"⚠️ Failed to load sprite for boss at {score_threshold}")
        return None
    
    # Determine party size
    party_size = determine_boss_party_size(boss_index)
    
    # Generate boss team using same logic as generate_enemy_team but with fixed size
    try:
        from rolling.roller import Roller
        from combat.team_randomizer import generate_enemy_team_fixed_size
        
        # Create RNG seeded by score threshold for deterministic boss teams
        seed = score_threshold & 0x7FFFFFFF
        rng = Roller(seed)
        
        # Use the fixed-size team generator (same logic as generate_enemy_team)
        team_data = generate_enemy_team_fixed_size(
            gs,
            team_size=party_size,
            rng=rng,
            rare_chance=0.12,
            allow_starters=False,
            allow_dupes=False,
        )
        
        if not team_data or not team_data.get("names"):
            print(f"⚠️ Failed to generate boss team (requested {party_size} vessels)")
            return None
        
        actual_size = len(team_data.get("names", []))
        if actual_size != party_size:
            print(f"⚠️ Warning: Boss team has {actual_size} vessels but expected {party_size}")
        
        print(f"✅ Generated boss team: {actual_size} vessels for {boss_name}")
        print(f"   Names: {team_data.get('names', [])}")
        print(f"   Levels: {team_data.get('levels', [])}")
        print(f"   Stats count: {len(team_data.get('stats', []))}")
            
    except Exception as e:
        print(f"⚠️ Failed to generate boss team: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    return {
        "sprite_path": None,  # We already loaded the sprite
        "sprite": sprite,
        "name": boss_name,
        "gender": gender,
        "party_size": party_size,
        "score_threshold": score_threshold,
        "team_data": team_data,
    }


def check_and_spawn_bosses(gs):
    """
    Check if any bosses should spawn based on current score.
    Called from main loop.
    """
    from systems.points import get_total_points
    
    current_score = get_total_points(gs)
    
    # Initialize defeated bosses list if not exists
    if not hasattr(gs, "defeated_boss_scores"):
        gs.defeated_boss_scores = []
    
    # Initialize spawned bosses list if not exists
    if not hasattr(gs, "spawned_boss_scores"):
        gs.spawned_boss_scores = []
    
    # Initialize bosses_on_map if not exists
    if not hasattr(gs, "bosses_on_map"):
        gs.bosses_on_map = []
    
    # Check if we should spawn a boss
    next_threshold = get_next_boss_threshold(current_score, gs.defeated_boss_scores, gs.spawned_boss_scores)
    
    if next_threshold is not None:
        print(f"[check_and_spawn_bosses] Score: {current_score}, Spawning boss at threshold: {next_threshold}")
        print(f"   Defeated bosses: {gs.defeated_boss_scores}, Spawned bosses: {gs.spawned_boss_scores}")
        # Create boss data
        boss_data = create_boss_data(gs, next_threshold, gs.defeated_boss_scores)
        
        if boss_data:
            # Spawn boss
            from world import actors
            actors.spawn_boss_ahead(gs, gs.start_x, boss_data)
            gs.spawned_boss_scores.append(next_threshold)
            print(f"🎯 Boss '{boss_data['name']}' spawned at score threshold {next_threshold}")
            print(f"   Bosses on map count: {len(getattr(gs, 'bosses_on_map', []))}")
        else:
            print(f"⚠️ Failed to create boss data for threshold {next_threshold}")
    elif current_score >= FIRST_BOSS_SCORE and FIRST_BOSS_SCORE not in gs.spawned_boss_scores and FIRST_BOSS_SCORE not in gs.defeated_boss_scores:
        # Debug: why didn't we spawn? (only print once per threshold)
        if not hasattr(gs, "_boss_debug_printed"):
            gs._boss_debug_printed = set()
        if FIRST_BOSS_SCORE not in gs._boss_debug_printed:
            print(f"⚠️ [check_and_spawn_bosses] Score {current_score} >= {FIRST_BOSS_SCORE} but no boss spawning!")
            print(f"   Defeated: {gs.defeated_boss_scores}, Spawned: {gs.spawned_boss_scores}")
            print(f"   get_next_boss_threshold returned: {get_next_boss_threshold(current_score, gs.defeated_boss_scores, gs.spawned_boss_scores)}")
            gs._boss_debug_printed.add(FIRST_BOSS_SCORE)


def mark_boss_defeated(gs, score_threshold: int):
    """Mark a boss as defeated (called after boss battle victory)."""
    if not hasattr(gs, "defeated_boss_scores"):
        gs.defeated_boss_scores = []
    
    if score_threshold not in gs.defeated_boss_scores:
        gs.defeated_boss_scores.append(score_threshold)
        print(f"🏆 Boss at score {score_threshold} marked as defeated")

