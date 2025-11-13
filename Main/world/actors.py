# ============================================================
#  world/actors.py — rivals & vessels spawn/update/draw
# ============================================================

import random
import pygame
from pygame.math import Vector2
import settings as S

# ✅ Stats/rolling for encounters (new path)
from combat.vessel_stats import generate_vessel_stats_from_asset
from rolling.roller import Roller

MONSTER_OVERWORLD_SCALE = getattr(S, "MONSTER_OVERWORLD_SCALE", 1.8)


# Lists live on the GameState object:
# gs.rivals_on_map:  list of dict {name, sprite, pos(Vector2), side}
# gs.vessels_on_map: list of dict {pos(Vector2), side}
# gs.merchants_on_map: list of dict {animator, pos(Vector2), side}
# gs.taverns_on_map: list of dict {sprite, pos(Vector2), side}


# ===================== Shared spawn helpers ==================
def _y_too_close(y: float, gs, min_sep: float) -> bool:
    """Return True if y is within min_sep of any existing spawn (vessels, rivals, merchants, taverns, or monsters)."""
    for r in gs.rivals_on_map:
        if abs(y - r["pos"].y) < min_sep:
            return True
    for v in gs.vessels_on_map:
        if abs(y - v["pos"].y) < min_sep:
            return True
    for m in getattr(gs, "merchants_on_map", []):
        if abs(y - m["pos"].y) < min_sep:
            return True
    for t in getattr(gs, "taverns_on_map", []):
        if abs(y - t["pos"].y) < min_sep:
            return True
    for mon in getattr(gs, "monsters_on_map", []):
        if abs(y - mon["pos"].y) < min_sep:
            return True
    return False


def _pick_spawn_y(gs, base_y: float, min_sep: float, max_attempts: int = 8):
    """
    Try to find a y above the player (<= base_y) that is at least min_sep away
    vertically from all existing spawns. We nudge upward each attempt.
    Returns y or None if no slot found.
    """
    y = base_y
    nudge = int(min_sep * 0.75)  # how much to move further up each attempt
    for _ in range(max_attempts):
        if not _y_too_close(y, gs, min_sep):
            return y
        y -= nudge
    return None


# ===================== Rivals (summoners) ====================
def spawn_rival_ahead(gs, start_x, summoners):
    """Spawn a visible rival (left/right lane) some distance above the player, with separation."""
    if not summoners:
        return

    name, sprite = random.choice(summoners)
    # Generate display name for summoner (name is the filename like "MSummoner1")
    from systems.name_generator import generate_summoner_name
    display_name = generate_summoner_name(name)
    side = random.choice(["left", "right"])
    x = start_x + (-S.LANE_OFFSET if side == "left" else S.LANE_OFFSET)

    # Propose a base y well above the player
    spawn_gap = random.randint(S.SPAWN_GAP_MIN, S.SPAWN_GAP_MAX)
    base_y = gs.player_pos.y - spawn_gap

    # Ensure vertical separation from ALL existing spawns
    sep = getattr(S, "OVERWORLD_MIN_SEPARATION_Y", 200)
    y = _pick_spawn_y(gs, base_y, sep)
    if y is None:
        # If no clean slot found, skip spawn to avoid visual overlap
        return

    gs.rivals_on_map.append({
        "name": display_name,  # Store generated name
        "filename": name,  # Store original filename for sprite lookup
        "sprite": sprite,
        "pos": Vector2(x, y),
        "side": side,
    })


def update_rivals(gs, dt, player_half: Vector2):
    """Trigger encounter when the player overlaps a rival in the same lane."""
    if gs.in_encounter:
        return

    SIZE_W, SIZE_H = S.PLAYER_SIZE
    x_threshold = S.LANE_OFFSET + SIZE_W
    triggered_index = None

    player_top    = gs.player_pos.y - player_half.y
    player_bottom = gs.player_pos.y + player_half.y

    for i, r in enumerate(gs.rivals_on_map):
        same_lane = abs(r["pos"].x - gs.player_pos.x) <= x_threshold

        rival_top    = r["pos"].y - SIZE_H // 2
        rival_bottom = r["pos"].y + SIZE_H // 2

        in_front = player_top <= (rival_bottom + S.FRONT_TOLERANCE)
        overlapping_vertically = player_bottom >= (rival_top - S.FRONT_TOLERANCE)

        if same_lane and in_front and overlapping_vertically:
            gs.in_encounter     = True
            gs.encounter_timer  = S.ENCOUNTER_SHOW_TIME
            # Store both generated name and original filename
            gs.encounter_summoner_filename = r.get("filename", r.get("name", "MSummoner1"))  # Original filename for sprite
            gs.encounter_name = r.get("name", "MSummoner1")  # Generated name (already generated in spawn_rival_ahead)
            gs.encounter_sprite = r["sprite"]
            gs.encounter_stats  = None  # rivals can have stats later if you want
            triggered_index     = i
            break

    if triggered_index is not None:
        gs.rivals_on_map.pop(triggered_index)

    # Cull far below player
    cutoff = gs.player_pos.y + S.HEIGHT * 1.5
    gs.rivals_on_map[:] = [r for r in gs.rivals_on_map if r["pos"].y < cutoff]


def draw_rivals(screen, cam, gs):
    SIZE_W, SIZE_H = S.PLAYER_SIZE
    for r in gs.rivals_on_map:
        pos = r["pos"]
        screen.blit(
            r["sprite"],
            (pos.x - cam.x - SIZE_W // 2,
             pos.y - cam.y - SIZE_H // 2)
        )


# ===================== Vessels (mist shadows) =================
def spawn_vessel_shadow_ahead(gs, start_x):
    """Spawn a mist shadow (left/right lane) some distance above the player, with separation."""
    side = random.choice(["left", "right"])
    x = start_x + (-S.LANE_OFFSET if side == "left" else S.LANE_OFFSET)

    spawn_gap = random.randint(S.SPAWN_GAP_MIN, S.SPAWN_GAP_MAX)
    base_y = gs.player_pos.y - spawn_gap

    # Ensure vertical separation from ALL existing spawns
    sep = getattr(S, "OVERWORLD_MIN_SEPARATION_Y", 200)
    y = _pick_spawn_y(gs, base_y, sep)
    if y is None:
        return

    gs.vessels_on_map.append({"pos": Vector2(x, y), "side": side})


def update_vessels(gs, dt, player_half: Vector2, vessels, rare_vessels):
    """Reveal an actual vessel sprite when overlapping a mist shadow and ROLL ITS STATS."""
    if gs.in_encounter:
        return

    SIZE_W, SIZE_H = S.PLAYER_SIZE
    x_threshold = S.LANE_OFFSET + SIZE_W
    triggered_index = None

    player_top    = gs.player_pos.y - player_half.y
    player_bottom = gs.player_pos.y + player_half.y

    for i, v in enumerate(gs.vessels_on_map):
        same_lane = abs(v["pos"].x - gs.player_pos.x) <= x_threshold

        mist_top    = v["pos"].y - SIZE_H // 2
        mist_bottom = v["pos"].y + SIZE_H // 2

        in_front = player_top <= (mist_bottom + S.FRONT_TOLERANCE)
        overlapping_vertically = player_bottom >= (mist_top - S.FRONT_TOLERANCE)

        if same_lane and in_front and overlapping_vertically:
            # Choose which vessel art/name appears
            if rare_vessels and random.random() <= 0.005:
                asset_name, sprite = random.choice(rare_vessels)
            elif vessels:
                asset_name, sprite = random.choice(vessels)
            else:
                asset_name, sprite = "Unknown Vessel", None

            # 🧮 Roll stat block NOW (encounter time) using the asset name -> class mapping
            seed = (pygame.time.get_ticks() ^ hash(asset_name) ^ int(gs.distance_travelled)) & 0xFFFFFFFF
            # Be defensive about Roller’s constructor
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

            # Use scaled level based on player's highest party level
            from combat.team_randomizer import scaled_enemy_level
            enemy_level = scaled_enemy_level(gs, rng)
            
            stats = generate_vessel_stats_from_asset(
                asset_name=asset_name,
                level=enemy_level,
                rng=rng,
                notes="Rolled on encounter"
            )

            # Generate display name from token name
            from systems.name_generator import generate_vessel_name
            gs.encounter_name   = generate_vessel_name(asset_name) if asset_name else "Wild Vessel"
            gs.encounter_sprite = sprite
            gs.encounter_stats  = stats
            # Store original token name for stat generation
            gs.encounter_token_name = asset_name
            gs.in_encounter     = True
            gs.encounter_timer  = S.ENCOUNTER_SHOW_TIME
            triggered_index     = i
            break

    if triggered_index is not None:
        gs.vessels_on_map.pop(triggered_index)

    # Cull far below player
    cutoff = gs.player_pos.y + S.HEIGHT * 1.5
    gs.vessels_on_map[:] = [v for v in gs.vessels_on_map if v["pos"].y < cutoff]


# ===================== Monsters =================
def scale_monster_overworld_sprite(sprite: pygame.Surface | None) -> pygame.Surface | None:
    if sprite is None:
        return None
    current_w, current_h = sprite.get_size()
    if current_w <= 0 or current_h <= 0:
        return sprite
    target_w = int(S.PLAYER_SIZE[0] * MONSTER_OVERWORLD_SCALE)
    target_h = int(S.PLAYER_SIZE[1] * MONSTER_OVERWORLD_SCALE)
    scale_w = target_w / current_w
    scale_h = target_h / current_h
    scale = min(scale_w, scale_h)
    final_w = max(1, int(current_w * scale))
    final_h = max(1, int(current_h * scale))
    return pygame.transform.smoothscale(sprite, (final_w, final_h))


def spawn_monster_ahead(gs, start_x, monsters):
    """Spawn a monster with its actual sprite (left/right lane) some distance above the player, with separation."""
    if not monsters or len(monsters) == 0:
        return
    
    # Choose random monster and get its sprite
    asset_name, sprite = random.choice(monsters)
    
    side = random.choice(["left", "right"])
    x = start_x + (-S.LANE_OFFSET if side == "left" else S.LANE_OFFSET)

    spawn_gap = random.randint(S.SPAWN_GAP_MIN, S.SPAWN_GAP_MAX)
    base_y = gs.player_pos.y - spawn_gap

    # Ensure vertical separation from ALL existing spawns
    sep = getattr(S, "OVERWORLD_MIN_SEPARATION_Y", 200)
    y = _pick_spawn_y(gs, base_y, sep)
    if y is None:
        return

    if not hasattr(gs, "monsters_on_map"):
        gs.monsters_on_map = []
    
    scaled_sprite = scale_monster_overworld_sprite(sprite)
    
    # Store monster with sprite and asset name
    gs.monsters_on_map.append({
        "pos": Vector2(x, y),
        "side": side,
        "sprite": sprite,
        "scaled_sprite": scaled_sprite,
        "asset_name": asset_name
    })


def update_monsters(gs, dt, player_half: Vector2):
    """Check collision with monster sprites and trigger encounter."""
    if gs.in_encounter:
        return
    
    if not hasattr(gs, "monsters_on_map"):
        gs.monsters_on_map = []
        return

    SIZE_W, SIZE_H = S.PLAYER_SIZE
    x_threshold = S.LANE_OFFSET + SIZE_W
    triggered_index = None

    player_top    = gs.player_pos.y - player_half.y
    player_bottom = gs.player_pos.y + player_half.y

    for i, m in enumerate(gs.monsters_on_map):
        same_lane = abs(m["pos"].x - gs.player_pos.x) <= x_threshold

        monster_top    = m["pos"].y - SIZE_H // 2
        monster_bottom = m["pos"].y + SIZE_H // 2

        in_front = player_top <= (monster_bottom + S.FRONT_TOLERANCE)
        overlapping_vertically = player_bottom >= (monster_top - S.FRONT_TOLERANCE)

        if same_lane and in_front and overlapping_vertically:
            # Get monster data from spawn
            asset_name = m.get("asset_name", "Unknown Monster")
            sprite = m.get("sprite")

            # 🧮 Roll stat block NOW (encounter time) using monster stat generation
            seed = (pygame.time.get_ticks() ^ hash(asset_name) ^ int(gs.distance_travelled)) & 0xFFFFFFFF
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

            # Use scaled level based on player's highest party level
            from combat.team_randomizer import scaled_enemy_level
            enemy_level = scaled_enemy_level(gs, rng)
            
            # Generate monster stats (with multipliers)
            from combat.monster_stats import generate_monster_stats_from_asset
            stats = generate_monster_stats_from_asset(
                asset_name=asset_name,
                level=enemy_level,
                rng=rng,
                notes="Rolled on monster encounter"
            )

            # Generate display name from monster name
            from systems.name_generator import generate_vessel_name
            gs.encounter_name   = generate_vessel_name(asset_name) if asset_name else "Wild Monster"
            gs.encounter_sprite = sprite
            gs.encounter_stats  = stats
            # Store original asset name for stat generation
            gs.encounter_token_name = asset_name
            gs.encounter_type = "MONSTER"  # Mark as monster encounter
            gs.in_encounter     = True
            gs.encounter_timer  = S.ENCOUNTER_SHOW_TIME
            triggered_index     = i
            break

    if triggered_index is not None:
        gs.monsters_on_map.pop(triggered_index)

    # Cull far below player
    cutoff = gs.player_pos.y + S.HEIGHT * 1.5
    gs.monsters_on_map[:] = [m for m in gs.monsters_on_map if m["pos"].y < cutoff]


def draw_monsters(screen, cam, gs, vessel_mist=None, debug=False):
    """Draw actual monster sprites on the overworld (larger than player)."""
    if not hasattr(gs, "monsters_on_map"):
        return
    
    for m in gs.monsters_on_map:
        pos = m["pos"]
        sprite = m.get("sprite")
        scaled_sprite = m.get("scaled_sprite")
        
        if scaled_sprite is None and sprite is not None:
            scaled_sprite = scale_monster_overworld_sprite(sprite)
            m["scaled_sprite"] = scaled_sprite
        
        if scaled_sprite:
            screen_x = int(pos.x - cam.x - scaled_sprite.get_width() // 2)
            screen_y = int(pos.y - cam.y - scaled_sprite.get_height() // 2)
            screen.blit(scaled_sprite, (screen_x, screen_y))
        elif sprite:
            screen_x = int(pos.x - cam.x - sprite.get_width() // 2)
            screen_y = int(pos.y - cam.y - sprite.get_height() // 2)
            screen.blit(sprite, (screen_x, screen_y))
        
        if debug:
            pygame.draw.circle(screen, (255, 0, 255), (int(pos.x - cam.x), int(pos.y - cam.y)), 5)


def draw_vessels(screen, cam, gs, vessel_mist, debug=False):
    SIZE_W, SIZE_H = S.PLAYER_SIZE
    for v in gs.vessels_on_map:
        pos = v["pos"]
        screen_x = int(pos.x - cam.x - SIZE_W // 2)
        screen_y = int(pos.y - cam.y - SIZE_H // 2)

        if debug:
            rect = pygame.Rect(screen_x, screen_y, SIZE_W, SIZE_H)
            pygame.draw.rect(screen, (255, 0, 255), rect, 2)
            pygame.draw.circle(screen, (255, 255, 0), rect.center, 3)

        if vessel_mist:
            screen.blit(vessel_mist, (screen_x, screen_y))
        else:
            # Fallback visible placeholder
            temp = pygame.Surface((SIZE_W, SIZE_H), pygame.SRCALPHA)
            temp.fill((30, 30, 30, 220))
            pygame.draw.circle(
                temp, (0, 0, 0, 255),
                (SIZE_W // 2, SIZE_H // 2),
                SIZE_W // 2
            )
            screen.blit(temp, (screen_x, screen_y))


# ===================== Merchants =================
def spawn_merchant_ahead(gs, start_x, merchant_frames):
    """Spawn a merchant (left/right lane) some distance above the player, with separation."""
    if not merchant_frames or len(merchant_frames) == 0:
        return
    
    # Import Animator from main.py (or create a simple animator here)
    # For now, we'll use a simple frame index
    side = random.choice(["left", "right"])
    x = start_x + (-S.LANE_OFFSET if side == "left" else S.LANE_OFFSET)
    
    spawn_gap = random.randint(S.SPAWN_GAP_MIN, S.SPAWN_GAP_MAX)
    base_y = gs.player_pos.y - spawn_gap
    
    # Ensure vertical separation from ALL existing spawns
    sep = getattr(S, "OVERWORLD_MIN_SEPARATION_Y", 200)
    y = _pick_spawn_y(gs, base_y, sep)
    if y is None:
        # If no valid spawn location found, try spawning further away (force spawn)
        print(f"⚠️ No valid spawn location found for merchant, trying fallback position")
        y = base_y - 500  # Spawn further away
        # Check if even this position is too close, if so just use it anyway (force spawn)
        if _y_too_close(y, gs, sep):
            print(f"⚠️ Fallback position also too close, forcing spawn anyway")
    
    # Create animator for merchant (will be updated in update_merchants)
    # We'll pass frames reference and create animator in update
    if not hasattr(gs, "merchants_on_map"):
        gs.merchants_on_map = []
    
    gs.merchants_on_map.append({
        "frames": merchant_frames,
        "pos": Vector2(x, y),
        "side": side,
        "anim_time": 0.0,
        "frame_index": 0,
    })
    print(f"✅ Merchant spawned at position ({x}, {y}) on {side} side")


def update_merchants(gs, dt, player_half: Vector2):
    """Update merchant animations and detect player proximity for speech bubble."""
    if not hasattr(gs, "merchants_on_map"):
        gs.merchants_on_map = []
        return
    
    # Merchants are slightly bigger than player (1.2x)
    MERCHANT_SIZE_MULT = 1.2
    SIZE_W = int(S.PLAYER_SIZE[0] * MERCHANT_SIZE_MULT)
    SIZE_H = int(S.PLAYER_SIZE[1] * MERCHANT_SIZE_MULT)
    x_threshold = S.LANE_OFFSET + SIZE_W
    
    player_top    = gs.player_pos.y - player_half.y
    player_bottom = gs.player_pos.y + player_half.y
    
    MERCHANT_ANIM_FPS = 7.0  # Faster animation
    frame_duration = 1.0 / MERCHANT_ANIM_FPS
    
    near_merchant = None
    
    for m in gs.merchants_on_map:
        # Update animation
        m["anim_time"] += dt
        if m["anim_time"] >= frame_duration:
            m["anim_time"] = 0.0
            m["frame_index"] = (m["frame_index"] + 1) % len(m["frames"])
        
        # Check if player is near merchant
        same_lane = abs(m["pos"].x - gs.player_pos.x) <= x_threshold
        merchant_top = m["pos"].y - SIZE_H // 2
        merchant_bottom = m["pos"].y + SIZE_H // 2
        
        in_front = player_top <= (merchant_bottom + S.FRONT_TOLERANCE)
        overlapping_vertically = player_bottom >= (merchant_top - S.FRONT_TOLERANCE)
        
        if same_lane and in_front and overlapping_vertically:
            near_merchant = m
    
    # Store which merchant is near (for speech bubble display)
    gs.near_merchant = near_merchant
    
    # Cull far below player
    cutoff = gs.player_pos.y + S.HEIGHT * 1.5
    gs.merchants_on_map[:] = [m for m in gs.merchants_on_map if m["pos"].y < cutoff]


def draw_merchants(screen, cam, gs):
    """Draw merchant sprites with animation, facing the player."""
    if not hasattr(gs, "merchants_on_map"):
        return
    
    # Merchants are slightly bigger than player (1.2x)
    MERCHANT_SIZE_MULT = 1.2
    SIZE_W = int(S.PLAYER_SIZE[0] * MERCHANT_SIZE_MULT)
    SIZE_H = int(S.PLAYER_SIZE[1] * MERCHANT_SIZE_MULT)
    
    for m in gs.merchants_on_map:
        pos = m["pos"]
        frame_index = m.get("frame_index", 0)
        frames = m.get("frames", [])
        
        if frames and 0 <= frame_index < len(frames):
            current_frame = frames[frame_index]
            
            # Make merchant face the player
            # If merchant is on left side (x < player.x), flip to face right
            # If merchant is on right side (x > player.x), face left (no flip)
            flip_horizontal = pos.x < gs.player_pos.x
            
            if flip_horizontal:
                current_frame = pygame.transform.flip(current_frame, True, False)
            
            screen.blit(
                current_frame,
                (pos.x - cam.x - SIZE_W // 2,
                 pos.y - cam.y - SIZE_H // 2)
            )


# ===================== Taverns =================
def spawn_tavern_ahead(gs, start_x, tavern_sprite):
    """Spawn a tavern (left/right lane) some distance above the player, with separation."""
    if not tavern_sprite:
        return
    
    side = random.choice(["left", "right"])
    x = start_x + (-S.LANE_OFFSET if side == "left" else S.LANE_OFFSET)
    
    spawn_gap = random.randint(S.SPAWN_GAP_MIN, S.SPAWN_GAP_MAX)
    base_y = gs.player_pos.y - spawn_gap
    
    # Ensure vertical separation from ALL existing spawns
    sep = getattr(S, "OVERWORLD_MIN_SEPARATION_Y", 200)
    y = _pick_spawn_y(gs, base_y, sep)
    if y is None:
        # If no valid spawn location found, try spawning further away (force spawn)
        print(f"⚠️ No valid spawn location found for tavern, trying fallback position")
        y = base_y - 500  # Spawn further away
        # Check if even this position is too close, if so just use it anyway (force spawn)
        if _y_too_close(y, gs, sep):
            print(f"⚠️ Fallback position also too close, forcing spawn anyway")
    
    if not hasattr(gs, "taverns_on_map"):
        gs.taverns_on_map = []
    
    gs.taverns_on_map.append({
        "sprite": tavern_sprite,
        "pos": Vector2(x, y),
        "side": side,
    })
    print(f"✅ Tavern spawned at position ({x}, {y}) on {side} side")


def update_taverns(gs, dt, player_half: Vector2):
    """Update tavern detection for player proximity."""
    if not hasattr(gs, "taverns_on_map"):
        gs.taverns_on_map = []
        return
    
    # Taverns are bigger than player (1.5x size)
    TAVERN_SIZE_MULT = 1.5
    SIZE_W = int(S.PLAYER_SIZE[0] * TAVERN_SIZE_MULT)
    SIZE_H = int(S.PLAYER_SIZE[1] * TAVERN_SIZE_MULT)
    x_threshold = S.LANE_OFFSET + SIZE_W
    
    player_top    = gs.player_pos.y - player_half.y
    player_bottom = gs.player_pos.y + player_half.y
    
    near_tavern = None
    
    for t in gs.taverns_on_map:
        # Check if player is near tavern
        same_lane = abs(t["pos"].x - gs.player_pos.x) <= x_threshold
        tavern_top = t["pos"].y - SIZE_H // 2
        tavern_bottom = t["pos"].y + SIZE_H // 2
        
        in_front = player_top <= (tavern_bottom + S.FRONT_TOLERANCE)
        overlapping_vertically = player_bottom >= (tavern_top - S.FRONT_TOLERANCE)
        
        if same_lane and in_front and overlapping_vertically:
            near_tavern = t
    
    # Store which tavern is near (for popup display and audio)
    gs.near_tavern = near_tavern
    
    # Cull far below player
    cutoff = gs.player_pos.y + S.HEIGHT * 1.5
    gs.taverns_on_map[:] = [t for t in gs.taverns_on_map if t["pos"].y < cutoff]


def draw_taverns(screen, cam, gs):
    """Draw tavern sprites."""
    if not hasattr(gs, "taverns_on_map"):
        return
    
    # Taverns are bigger than player (1.5x size)
    TAVERN_SIZE_MULT = 1.5
    SIZE_W = int(S.PLAYER_SIZE[0] * TAVERN_SIZE_MULT)
    SIZE_H = int(S.PLAYER_SIZE[1] * TAVERN_SIZE_MULT)
    
    for t in gs.taverns_on_map:
        pos = t["pos"]
        sprite = t.get("sprite")
        
        if sprite:
            screen.blit(
                sprite,
                (pos.x - cam.x - SIZE_W // 2,
                 pos.y - cam.y - SIZE_H // 2)
            )


# ===================== Bosses =================
def spawn_boss_ahead(gs, start_x, boss_data: dict):
    """
    Spawn a boss in the middle of the road, far ahead of the player.
    boss_data should contain: sprite_path, name, gender, party_size, score_threshold, team_data
    """
    if not boss_data:
        return
    
    # Boss spawns in the middle of the road (centered like player)
    x = start_x  # Center of road (same as player's start_x; already offset in gs.start_x)
    
    # Spawn far ahead (further than normal encounters)
    spawn_gap = random.randint(800, 1200)  # Much further than normal spawns
    base_y = gs.player_pos.y - spawn_gap
    
    # Ensure vertical separation from ALL existing spawns
    sep = getattr(S, "OVERWORLD_MIN_SEPARATION_Y", 200)
    y = _pick_spawn_y(gs, base_y, sep)
    if y is None:
        # Force spawn if no clean slot found (bosses are important)
        y = base_y - 500
    
    if not hasattr(gs, "bosses_on_map"):
        gs.bosses_on_map = []
    
    gs.bosses_on_map.append({
        "sprite_path": boss_data.get("sprite_path"),
        "sprite": boss_data.get("sprite"),  # Pre-loaded sprite
        "name": boss_data.get("name"),
        "gender": boss_data.get("gender"),
        "party_size": boss_data.get("party_size", 3),
        "score_threshold": boss_data.get("score_threshold", 0),
        "team_data": boss_data.get("team_data"),  # Pre-generated team
        "pos": Vector2(x, y),
    })
    print(f"✅ Boss '{boss_data.get('name')}' spawned at position ({x}, {y})")


def update_bosses(gs, dt, player_half: Vector2):
    """Check if player is close to a boss and trigger encounter."""
    if gs.in_encounter:
        return
    
    if not hasattr(gs, "bosses_on_map"):
        gs.bosses_on_map = []
        return
    
    SIZE_W, SIZE_H = S.PLAYER_SIZE
    # Bosses are bigger than player (1.5x multiplier)
    BOSS_SIZE_MULT = 1.5
    BOSS_SIZE_W = int(SIZE_W * BOSS_SIZE_MULT)
    BOSS_SIZE_H = int(SIZE_H * BOSS_SIZE_MULT)
    
    # Check proximity (bosses are in center, so use threshold based on boss size)
    x_threshold = BOSS_SIZE_W // 2 + SIZE_W // 2
    triggered_index = None
    
    player_top = gs.player_pos.y - player_half.y
    player_bottom = gs.player_pos.y + player_half.y
    
    for i, boss in enumerate(gs.bosses_on_map):
        same_lane = abs(boss["pos"].x - gs.player_pos.x) <= x_threshold
        
        boss_top = boss["pos"].y - BOSS_SIZE_H // 2
        boss_bottom = boss["pos"].y + BOSS_SIZE_H // 2
        
        in_front = player_top <= (boss_bottom + S.FRONT_TOLERANCE)
        overlapping_vertically = player_bottom >= (boss_top - S.FRONT_TOLERANCE)
        
        if same_lane and in_front and overlapping_vertically:
            # Trigger boss encounter - main loop will route to VS screen
            gs.in_encounter = True
            gs.encounter_timer = S.ENCOUNTER_SHOW_TIME
            gs.encounter_name = boss.get("name", "Boss")
            gs.encounter_sprite = boss.get("sprite")
            gs.encounter_type = "BOSS"  # Mark as boss encounter
            gs.encounter_boss_data = boss  # Store full boss data for battle
            triggered_index = i
            break
    
    if triggered_index is not None:
        gs.bosses_on_map.pop(triggered_index)
    
    # Cull far below player
    cutoff = gs.player_pos.y + S.HEIGHT * 1.5
    gs.bosses_on_map[:] = [b for b in gs.bosses_on_map if b["pos"].y < cutoff]


def draw_bosses(screen, cam, gs):
    """Draw boss sprites in the middle of the road, facing the player."""
    if not hasattr(gs, "bosses_on_map"):
        return
    
    SIZE_W, SIZE_H = S.PLAYER_SIZE
    # Bosses are bigger than player (1.5x multiplier)
    BOSS_SIZE_MULT = 1.5
    BOSS_SIZE_W = int(SIZE_W * BOSS_SIZE_MULT)
    BOSS_SIZE_H = int(SIZE_H * BOSS_SIZE_MULT)
    
    for boss in gs.bosses_on_map:
        pos = boss["pos"]
        sprite = boss.get("sprite")
        
        if sprite:
            # Scale sprite to boss size (bigger than player)
            if sprite.get_width() != BOSS_SIZE_W or sprite.get_height() != BOSS_SIZE_H:
                sprite = pygame.transform.smoothscale(sprite, (BOSS_SIZE_W, BOSS_SIZE_H))
            
            # Boss faces player (flip sprite if needed)
            # If boss is to the left of player, flip to face right
            flip_horizontal = pos.x < gs.player_pos.x
            
            display_sprite = sprite
            if flip_horizontal:
                display_sprite = pygame.transform.flip(sprite, True, False)
            
            # Center boss on road (same x as player's start_x)
            screen.blit(
                display_sprite,
                (pos.x - cam.x - BOSS_SIZE_W // 2,
                 pos.y - cam.y - BOSS_SIZE_H // 2)
            )