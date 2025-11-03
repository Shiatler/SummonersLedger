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


# Lists live on the GameState object:
# gs.rivals_on_map:  list of dict {name, sprite, pos(Vector2), side}
# gs.vessels_on_map: list of dict {pos(Vector2), side}


# ===================== Shared spawn helpers ==================
def _y_too_close(y: float, gs, min_sep: float) -> bool:
    """Return True if y is within min_sep of any existing spawn (vessels or rivals)."""
    for r in gs.rivals_on_map:
        if abs(y - r["pos"].y) < min_sep:
            return True
    for v in gs.vessels_on_map:
        if abs(y - v["pos"].y) < min_sep:
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
