# =============================================================
# world/Tavern/tavern.py — Tavern interior screen
# - Shows TavernMap.png as background
# - Camera is locked vertically (no scrolling up/down)
# - Player can move left/right with A/D keys
# - Exit with ESC or E key
# =============================================================

import os
import random
import pygame
from pygame.math import Vector2
import settings as S

from systems import shop
from systems import audio

# Import modal modules for blocking checks
from combat.btn import bag_action as bag_ui
from screens import party_manager, ledger
from systems import currency_display, rest_popup

# ===================== Constants =====================
TAVERN_MAP_PATH = os.path.join("Assets", "Tavern", "TavernMap.png")
BARKEEPER_SPRITE_PATH = os.path.join("Assets", "Tavern", "BarkeeperDwarf.png")
GAMBLER_SPRITE_PATH = os.path.join("Assets", "Tavern", "Gambler.png")
WHORE_SPRITE_PATHS = [
    os.path.join("Assets", "Tavern", "Whore1.png"),
    os.path.join("Assets", "Tavern", "Whore2.png"),
    os.path.join("Assets", "Tavern", "Whore3.png"),
    os.path.join("Assets", "Tavern", "Whore4.png"),
    os.path.join("Assets", "Tavern", "Whore5.png"),
    os.path.join("Assets", "Tavern", "Whore6.png"),
    os.path.join("Assets", "Tavern", "Whore7.png"),
    os.path.join("Assets", "Tavern", "Whore8.png"),
    os.path.join("Assets", "Tavern", "Whore9.png"),
]

# ===================== Global State =====================
_TAVERN_MAP = None
_TAVERN_MAP_WIDTH = 0
_TAVERN_MAP_HEIGHT = 0
_TAVERN_MAP_ANCHOR_X = 0  # X position where map is centered (similar to ROAD_ANCHOR_X)
_BARKEEPER_SPRITE = None  # Barkeeper NPC sprite
_GAMBLER_SPRITE = None  # Gambler NPC sprite
# Whore sprites are loaded on demand (one per tavern visit)

# ===================== Collision Boundaries =====================
# Wall boundaries defined as rectangles (x, y, width, height) in map coordinates (0,0 = top-left of map)
# These will be populated after the map is loaded based on map dimensions
_TAVERN_WALLS = []

def _init_tavern_walls(map_width: int, map_height: int):
    """Initialize wall collision boundaries based on map dimensions.
    Walls are defined as rectangles in map coordinates (0,0 = top-left of map).
    Adding boundaries one at a time with debug visuals.
    """
    global _TAVERN_WALLS
    _TAVERN_WALLS = []
    
    # Wall thickness
    wall_thickness = 5
    
    # ============================================================
    # HORIZONTAL LINE - Kitchen/Storage Division
    # ============================================================
    # Red line: horizontal, ~25% down from top, spans ~1/3 width from left
    # Divides kitchen/storage area (upper left) from main tavern floor
    
    # Position: approximately one-quarter down from top
    line_y = int(map_height * 0.25)
    
    # Starts near left wall, extends about one-third of map width
    line_x_start = int(map_width * 0.08)  # Small margin from left wall
    line_x_end = int(map_width * 0.88)    # Extends to about 35% of map width (1/3 + margin)
    line_width = line_x_end - line_x_start
    
    # Create horizontal wall segment
    _TAVERN_WALLS.append(pygame.Rect(line_x_start, line_y, line_width, wall_thickness))
    
    # ============================================================
    # VERTICAL LINE - Right Wall
    # ============================================================
    # Red line: vertical, starts where horizontal line ends, extends down to bottom
    # Forms perfect corner with horizontal line
    
    # Starts at the corner where horizontal line ends
    vertical_line_x = line_x_end  # Same x as where horizontal line ends
    vertical_line_y_start = line_y  # Same y as horizontal line (perfect corner)
    vertical_line_y_end = int(map_height * 0.93)  # Stops at 80% down from top (adjust 0.80 to change where it stops)
    
    # Create vertical wall segment
    vertical_line_height = vertical_line_y_end - vertical_line_y_start
    _TAVERN_WALLS.append(pygame.Rect(vertical_line_x, vertical_line_y_start, wall_thickness, vertical_line_height))
    
    # ============================================================
    # HORIZONTAL LINE - Bottom Wall (corners vertical line)
    # ============================================================
    # Horizontal line that extends LEFT from where vertical line ends, forming a corner
    
    # Ends at the corner where vertical line ends (line goes from left to this point)
    bottom_line_x_start = int(map_width * 0.08)  # Starts from left edge of map (adjust as needed)
    bottom_line_x_end = vertical_line_x  # Ends at vertical line x position (perfect corner)
    bottom_line_y = vertical_line_y_end  # Same y as where vertical line ends
    
    # Create horizontal wall segment
    bottom_line_width = bottom_line_x_end - bottom_line_x_start
    _TAVERN_WALLS.append(pygame.Rect(bottom_line_x_start, bottom_line_y, bottom_line_width, wall_thickness))
    
    # ============================================================
    # VERTICAL LINE - Left Wall (corners bottom wall)
    # ============================================================
    # Vertical line that extends UP from where bottom wall starts, forming a corner
    
    # Starts at the corner where bottom wall starts (left end)
    left_wall_x = bottom_line_x_start  # Same x as bottom wall start (perfect corner)
    left_wall_y_start = bottom_line_y  # Same y as bottom wall (perfect corner)
    left_wall_y_end = 0  # Extends to top of map (adjust as needed)
    
    # Create vertical wall segment (going up, so we need to calculate from end to start)
    left_wall_height = left_wall_y_start - left_wall_y_end
    _TAVERN_WALLS.append(pygame.Rect(left_wall_x, left_wall_y_end, wall_thickness, left_wall_height))
    
    # ============================================================
    # VERTICAL LINE - Internal Divider (Upper-Left Common Room)
    # ============================================================
    # Red line: vertical, in upper-left portion of common room
    # Starts just below kitchen, extends down about 1/3 of common room height
    # Runs parallel to left wall, positioned to the right of a table
    
    # Starts just below the kitchen division line (common room starts here)
    internal_divider_x = int(map_width * 0.30)  # Positioned to the right of left wall (adjust as needed)
    internal_divider_y_start = line_y  # Starts at kitchen division line (just below kitchen)
    
    # Common room height (from kitchen line to bottom)
    common_room_height = map_height - line_y
    # Extends down about 1/3 of common room height
    internal_divider_y_end = line_y + int(common_room_height * 0.33)
    internal_divider_height = internal_divider_y_end - internal_divider_y_start
    
    # Create vertical wall segment
    _TAVERN_WALLS.append(pygame.Rect(internal_divider_x, internal_divider_y_start, wall_thickness, internal_divider_height))
    
    # ============================================================
    # HORIZONTAL LINE - Bar Counter
    # ============================================================
    # Horizontal line for the bar counter along the left wall
    # Bar counter is in the middle-left area of the common room
    
    # Bar counter position (along left wall, in middle-lower area of common room)
    bar_counter_x_start = int(map_width * 0.08)  # Starts near left wall
    bar_counter_x_end = int(map_width * 0.3)    # Extends into common room (adjust as needed)
    bar_counter_y = int(map_height * 0.50)       # Positioned in middle-lower area (adjust as needed)
    
    # Create horizontal wall segment for bar counter
    bar_counter_width = bar_counter_x_end - bar_counter_x_start
    _TAVERN_WALLS.append(pygame.Rect(bar_counter_x_start, bar_counter_y, bar_counter_width, wall_thickness))
    
    # ============================================================
    # VERTICAL LINE - Table in Middle-Right
    # ============================================================
    # Vertical line across a table in the middle-right area of the main hall
    
    # Table position (middle-right area of common room)
    table_line_x = int(map_width * 0.62)        # X position in middle-right area (adjust as needed)
    table_line_y_start = int(map_height * 0.5) # Starts at top of table area
    table_line_y_end = int(map_height * 0.7)   # Ends at bottom of table area (adjust as needed)
    
    # Create vertical wall segment for table
    table_line_height = table_line_y_end - table_line_y_start
    _TAVERN_WALLS.append(pygame.Rect(table_line_x, table_line_y_start, wall_thickness, table_line_height))
    
    print(f"✅ Added horizontal kitchen division line")
    print(f"   Position: y={line_y} ({line_y/map_height*100:.1f}% from top)")
    print(f"   X range: {line_x_start} to {line_x_end} ({line_width}px wide, {line_width/map_width*100:.1f}% of map)")
    print(f"✅ Added vertical right wall line")
    print(f"   Position: x={vertical_line_x} ({vertical_line_x/map_width*100:.1f}% from left)")
    print(f"   Y range: {vertical_line_y_start} to {vertical_line_y_end} ({vertical_line_height}px tall)")
    print(f"✅ Added horizontal bottom wall line")
    print(f"   Position: y={bottom_line_y} ({bottom_line_y/map_height*100:.1f}% from top)")
    print(f"   X range: {bottom_line_x_start} to {bottom_line_x_end} ({bottom_line_width}px wide)")
    print(f"✅ Added vertical left wall line")
    print(f"   Position: x={left_wall_x} ({left_wall_x/map_width*100:.1f}% from left)")
    print(f"   Y range: {left_wall_y_end} to {left_wall_y_start} ({left_wall_height}px tall)")
    print(f"✅ Added vertical internal divider line (upper-left common room)")
    print(f"   Position: x={internal_divider_x} ({internal_divider_x/map_width*100:.1f}% from left)")
    print(f"   Y range: {internal_divider_y_start} to {internal_divider_y_end} ({internal_divider_height}px tall)")
    print(f"✅ Added horizontal bar counter line")
    print(f"   Position: y={bar_counter_y} ({bar_counter_y/map_height*100:.1f}% from top)")
    print(f"   X range: {bar_counter_x_start} to {bar_counter_x_end} ({bar_counter_width}px wide)")
    print(f"✅ Added vertical table line (middle-right)")
    print(f"   Position: x={table_line_x} ({table_line_x/map_width*100:.1f}% from left)")
    print(f"   Y range: {table_line_y_start} to {table_line_y_end} ({table_line_height}px tall)")
    print(f"   Total boundaries: {len(_TAVERN_WALLS)}")

def _load_tavern_map():
    """Load the tavern map image."""
    global _TAVERN_MAP, _TAVERN_MAP_WIDTH, _TAVERN_MAP_HEIGHT, _TAVERN_MAP_ANCHOR_X
    
    if _TAVERN_MAP is not None:
        return _TAVERN_MAP
    
    # Try the specified path
    path = TAVERN_MAP_PATH
    if not os.path.exists(path):
        # Try alternative path (case-insensitive)
        alt_path = os.path.join("Assets", "Tavern", "TavernMap.png")
        if os.path.exists(alt_path):
            path = alt_path
        else:
            print(f"⚠️ TavernMap.png not found at {path}")
            return None
    
    try:
        img = pygame.image.load(path).convert()
        _TAVERN_MAP = img
        _TAVERN_MAP_WIDTH = img.get_width()
        _TAVERN_MAP_HEIGHT = img.get_height()
        
        # Center the map within WORLD_W (matching overworld road centering)
        world_w = getattr(S, "WORLD_W", _TAVERN_MAP_WIDTH)
        _TAVERN_MAP_ANCHOR_X = max(0, (world_w - _TAVERN_MAP_WIDTH) // 2)
        
        # Initialize wall boundaries
        _init_tavern_walls(_TAVERN_MAP_WIDTH, _TAVERN_MAP_HEIGHT)
        
        print(f"✅ Loaded tavern map: {_TAVERN_MAP_WIDTH}x{_TAVERN_MAP_HEIGHT}, anchor_x={_TAVERN_MAP_ANCHOR_X}")
        return img
    except Exception as e:
        print(f"⚠️ Failed to load tavern map: {e}")
        return None

def _load_barkeeper_sprite():
    """Load and scale the barkeeper NPC sprite to match player size."""
    global _BARKEEPER_SPRITE
    
    if _BARKEEPER_SPRITE is not None:
        return _BARKEEPER_SPRITE
    
    path = BARKEEPER_SPRITE_PATH
    if not os.path.exists(path):
        print(f"⚠️ BarkeeperDwarf.png not found at {path}")
        return None
    
    try:
        sprite = pygame.image.load(path).convert_alpha()
        # Scale sprite to match player size (138x138)
        target_size = S.PLAYER_SIZE
        sprite = pygame.transform.scale(sprite, target_size)
        _BARKEEPER_SPRITE = sprite
        print(f"✅ Loaded and scaled barkeeper sprite to {target_size[0]}x{target_size[1]}")
        return sprite
    except Exception as e:
        print(f"⚠️ Failed to load barkeeper sprite: {e}")
        return None

def _load_gambler_sprite():
    """Load and scale the gambler NPC sprite to match player size."""
    global _GAMBLER_SPRITE
    
    if _GAMBLER_SPRITE is not None:
        return _GAMBLER_SPRITE
    
    path = GAMBLER_SPRITE_PATH
    if not os.path.exists(path):
        print(f"⚠️ Gambler.png not found at {path}")
        return None
    
    try:
        sprite = pygame.image.load(path).convert_alpha()
        # Scale sprite to match player size (138x138)
        target_size = S.PLAYER_SIZE
        sprite = pygame.transform.scale(sprite, target_size)
        _GAMBLER_SPRITE = sprite
        print(f"✅ Loaded and scaled gambler sprite to {target_size[0]}x{target_size[1]}")
        return sprite
    except Exception as e:
        print(f"⚠️ Failed to load gambler sprite: {e}")
        return None

def _load_whore_sprite(whore_number: int):
    """Load and scale a whore NPC sprite to match player size.
    whore_number: 1-9 (indexed from 1, not 0)
    """
    path = WHORE_SPRITE_PATHS[whore_number - 1]  # Convert to 0-based index
    if not os.path.exists(path):
        print(f"⚠️ Whore{whore_number}.png not found at {path}")
        return None
    
    try:
        sprite = pygame.image.load(path).convert_alpha()
        # Scale sprite to match player size (138x138)
        target_size = S.PLAYER_SIZE
        sprite = pygame.transform.scale(sprite, target_size)
        print(f"✅ Loaded and scaled Whore{whore_number} sprite to {target_size[0]}x{target_size[1]}")
        return sprite
    except Exception as e:
        print(f"⚠️ Failed to load Whore{whore_number} sprite: {e}")
        return None

def _select_whore():
    """Select which whore spawns based on probability distribution.
    Returns: (whore_number: int, sprite: pygame.Surface)
    Probabilities:
    - Whore1-5: 14.2% each (71% total)
    - Whore6-8: 8% each (24% total)
    - Whore9: 5% (5% total)
    Total: 100%
    """
    rand = random.random() * 100.0  # Random number 0-100
    
    if rand < 14.2:
        return 1
    elif rand < 28.4:
        return 2
    elif rand < 42.6:
        return 3
    elif rand < 56.8:
        return 4
    elif rand < 71.0:
        return 5
    elif rand < 79.0:
        return 6
    elif rand < 87.0:
        return 7
    elif rand < 95.0:
        return 8
    else:
        return 9

def clamp(v, lo, hi):
    """Clamp a value between lo and hi."""
    return max(lo, min(hi, v))

def get_camera_offset_locked(target_pos: Vector2, screen_w: int, screen_h: int, player_half: Vector2, map_width: int, map_height: int, map_anchor_x: int, locked_cam_x: float = None, locked_cam_y: float = None) -> Vector2:
    """Calculate camera offset with completely locked camera (map doesn't move).
    Camera X and Y are locked to center the map on screen."""
    # Lock camera X to center the map on screen (map doesn't scroll)
    if locked_cam_x is not None:
        cam_x = locked_cam_x
    else:
        # Calculate camera X to center the map horizontally
        # Map anchor is at map_anchor_x in world coordinates
        # We want the center of the map to be at the center of the screen
        map_center_x = map_anchor_x + map_width / 2
        cam_x = map_center_x - screen_w / 2
    
    # Lock camera vertically - use the locked_cam_y if provided, otherwise calculate it once
    if locked_cam_y is not None:
        cam_y = locked_cam_y
    else:
        # Center the map vertically on screen
        map_center_y = map_height / 2
        cam_y = map_center_y - screen_h / 2
    
    return Vector2(cam_x, cam_y)

def _check_collision(player_pos: Vector2, player_half: Vector2, map_anchor_x: int, new_x: float, new_y: float) -> bool:
    """Check if player would collide with any wall at the new position.
    Returns True if collision detected, False otherwise."""
    # Convert player world position to map coordinates
    player_map_x = new_x - map_anchor_x
    player_map_y = new_y
    
    # Create player collision rectangle in map coordinates
    # Use integer coordinates for pygame.Rect
    player_rect = pygame.Rect(
        int(player_map_x - player_half.x),
        int(player_map_y - player_half.y),
        int(player_half.x * 2),
        int(player_half.y * 2)
    )
    
    # Check collision with all walls
    for wall in _TAVERN_WALLS:
        if player_rect.colliderect(wall):
            return True
    
    return False

def update_player_tavern(gs, dt, player_half, map_width: int, map_height: int, map_anchor_x: int):
    """Update player position in tavern (movement with A/D/W/S keys, with wall collision)."""
    keys = pygame.key.get_pressed()
    moving = False
    speed = getattr(gs, "player_speed", 180)
    
    # Store original position for collision checking
    orig_x = gs.player_pos.x
    orig_y = gs.player_pos.y
    new_x = orig_x
    new_y = orig_y
    
    # Allow horizontal movement with A/D keys
    if keys[pygame.K_a] or keys[pygame.K_LEFT]:
        new_x = orig_x - speed * dt
        moving = True
    if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
        new_x = orig_x + speed * dt
        moving = True
    
    # Allow vertical movement with W/S keys (player moves, but camera stays locked)
    if keys[pygame.K_w] or keys[pygame.K_UP]:
        new_y = orig_y - speed * dt
        moving = True
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        new_y = orig_y + speed * dt
        moving = True
    
    # Try X movement first, then Y (separate axis collision)
    if new_x != orig_x:
        if not _check_collision(gs.player_pos, player_half, map_anchor_x, new_x, orig_y):
            gs.player_pos.x = new_x
        else:
            # X collision, don't move horizontally
            new_x = orig_x
    
    if new_y != orig_y:
        if not _check_collision(gs.player_pos, player_half, map_anchor_x, gs.player_pos.x, new_y):
            gs.player_pos.y = new_y
        else:
            # Y collision, don't move vertically
            pass
    
    # Also clamp to map bounds as a safety (shouldn't be needed with proper walls, but good backup)
    min_x = map_anchor_x + player_half.x
    max_x = map_anchor_x + map_width - player_half.x
    gs.player_pos.x = clamp(gs.player_pos.x, min_x, max_x)
    gs.player_pos.y = clamp(gs.player_pos.y, player_half.y, map_height - player_half.y)
    
    # Update walking animation if moving
    if moving:
        if hasattr(gs, "walk_anim"):
            gs.walk_anim.update(dt)
            frame = gs.walk_anim.current()
            if frame is not None:
                gs.player_image = frame
    else:
        if hasattr(gs, "walk_anim"):
            gs.walk_anim.reset()
            if hasattr(gs, "player_idle"):
                gs.player_image = gs.player_idle

# ===================== Screen Lifecycle =====================
def enter(gs, rival_summoners=None, **_):
    """Initialize tavern screen state."""
    # Load tavern map
    _load_tavern_map()
    
    # Don't preload gambling assets - load them instantly when entering gambling screen instead
    # This keeps tavern entry fast
    
    # Initialize tavern state
    if not hasattr(gs, "_tavern_state"):
        gs._tavern_state = {}
    
    st = gs._tavern_state

    # Ensure whore confirmation state keys exist
    st.setdefault("whore_confirm_active", False)
    st.setdefault("whore_confirm_buttons", [])
    st.setdefault("whore_confirm_error", "")
    st.setdefault("whore_confirm_price", 0)
    
    # Store overworld player position when entering a NEW tavern
    # Check if this is a NEW tavern (different from the one we were in before)
    current_tavern = getattr(gs, "near_tavern", None)
    previous_tavern = st.get("overworld_tavern", None)
    is_new_tavern = (current_tavern != previous_tavern)
    
    if is_new_tavern:
        # New tavern - always update overworld position to current position
        st["overworld_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
        print(f"💾 Stored overworld position for NEW tavern: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
        # Reset NPC initialization so they get rolled again
        if "npc_initialized" in st:
            del st["npc_initialized"]
        print(f"🆕 Entering NEW tavern - will roll new NPCs")
    elif "overworld_player_pos" not in st:
        # First tavern ever - store position
        st["overworld_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
        print(f"💾 Stored overworld position on first tavern entry: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
    else:
        # Same tavern - preserve existing overworld position (we're returning from battle/interaction)
        print(f"💾 Preserved overworld position (same tavern): ({st['overworld_player_pos'].x:.1f}, {st['overworld_player_pos'].y:.1f})")
    
    # Store the tavern object from overworld (so we can remove it when kicked out)
    # Only store it on first entry to THIS tavern, preserve it if already stored
    if "overworld_tavern" not in st or is_new_tavern:
        st["overworld_tavern"] = current_tavern
    
    # Only roll NPCs on first entry to this tavern (check if they're already set)
    is_first_entry = "npc_initialized" not in st
    
    if is_first_entry:
        # Load NPC sprites
        _load_barkeeper_sprite()
        _load_gambler_sprite()
        
        # Randomly select and load a whore NPC (100% chance one spawns unless consumed)
        if not st.get("whore_consumed", False):
            whore_number = _select_whore()
            whore_sprite = _load_whore_sprite(whore_number)
            st["whore_number"] = whore_number
            st["whore_sprite"] = whore_sprite
            print(f"💋 Selected Whore{whore_number} ({whore_number}/9)")
        else:
            st["whore_number"] = None
            st["whore_sprite"] = None
            st["whore_pos"] = None
            print("💋 Whore already satisfied - none present in tavern")
        
        # Randomly select and spawn a summoner (like overworld)
        if rival_summoners and len(rival_summoners) > 0:
            from systems.name_generator import generate_summoner_name
            summoner_name, summoner_sprite = random.choice(rival_summoners)
            display_name = generate_summoner_name(summoner_name)
            st["summoner_name"] = display_name
            st["summoner_filename"] = summoner_name
            st["summoner_sprite"] = summoner_sprite
            print(f"⚔️ Selected summoner: {display_name} (filename: {summoner_name})")
        else:
            st["summoner_name"] = None
            st["summoner_filename"] = None
            st["summoner_sprite"] = None
            print("⚠️ No summoners available to spawn in tavern")
        
        # Mark NPCs as initialized for this tavern instance
        st["npc_initialized"] = True
    else:
        # Preserve existing NPCs - don't re-roll
        # BUT reload sprites if they're missing (e.g., after loading from save)
        print(f"💾 Preserving existing NPCs (whore={st.get('whore_number')}, summoner={st.get('summoner_name')})")
        
        # Reload sprites if data exists but sprites are missing (e.g., after loading from save)
        if st.get("whore_number") and st.get("whore_sprite") is None:
            whore_number = st["whore_number"]
            whore_sprite = _load_whore_sprite(whore_number)
            st["whore_sprite"] = whore_sprite
            print(f"🔄 Reloaded Whore{whore_number} sprite from save")
        
        if st.get("summoner_filename") and st.get("summoner_sprite") is None and rival_summoners:
            summoner_filename = st["summoner_filename"]
            # rival_summoners is a list of (name, sprite) tuples, not a dict
            summoner_sprite = None
            for name, sprite in rival_summoners:
                if name == summoner_filename:
                    summoner_sprite = sprite
                    break
            if summoner_sprite:
                st["summoner_sprite"] = summoner_sprite
                # Regenerate display name if missing
                if not st.get("summoner_name"):
                    from systems.name_generator import generate_summoner_name
                    st["summoner_name"] = generate_summoner_name(summoner_filename)
                print(f"🔄 Reloaded summoner '{st['summoner_name']}' sprite from save (filename: {summoner_filename})")
            else:
                print(f"⚠️ Could not find summoner sprite for filename: {summoner_filename}")
        
        # Always reload barkeeper and gambler sprites (they're static)
        _load_barkeeper_sprite()
        _load_gambler_sprite()
    
    # Set player position (center horizontally, at a fixed Y position on the map)
    # Match overworld: player starts at center of world horizontally
    if _TAVERN_MAP:
        map_w = _TAVERN_MAP_WIDTH
        map_h = _TAVERN_MAP_HEIGHT
        map_anchor_x = _TAVERN_MAP_ANCHOR_X
        world_w = getattr(S, "WORLD_W", map_w)
        
        # Initialize camera with locked Y position
        player_half = getattr(gs, "player_half", Vector2(S.PLAYER_SIZE[0] / 2, S.PLAYER_SIZE[1] / 2))
        screen_w = getattr(S, "LOGICAL_WIDTH", S.WIDTH)
        screen_h = getattr(S, "LOGICAL_HEIGHT", S.HEIGHT)
        
        # Check if we're returning from an interaction - restore position if stored
        stored_tavern_pos = st.get("tavern_player_pos", None)
        returning_from_battle = st.get("returning_from_battle", False)
        
        if stored_tavern_pos:
            # Restore position from before interaction
            gs.player_pos.x = stored_tavern_pos.x
            gs.player_pos.y = stored_tavern_pos.y
            print(f"✅ Restored tavern position: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
            # DON'T overwrite spawn_pos - it should remain at the original exit location
            
            # Only show kicked out textbox if returning from battle
            if returning_from_battle:
                # Remove summoner sprite (they're gone after the barfight)
                st["summoner_sprite"] = None
                st["summoner_name"] = None
                st["summoner_filename"] = None
                st["summoner_pos"] = None
                
                # Show "kicked out" textbox
                st["kicked_out_textbox_active"] = True
                st["kicked_out_blink_t"] = 0.0
                print("🚪 Player has been kicked out of the tavern!")
            
            # Clear the flags after restoring position
            del st["tavern_player_pos"]
            if returning_from_battle:
                del st["returning_from_battle"]
            
            # Skip NPC spawning and positioning - preserve existing ones
            # Just ensure positions are set if they don't exist (shouldn't happen, but safety check)
            if "barkeeper_pos" not in st or st["barkeeper_pos"] is None:
                barkeeper_map_x = map_w * 0.19
                barkeeper_map_y = map_h * 0.40
                st["barkeeper_pos"] = Vector2(map_anchor_x + barkeeper_map_x, barkeeper_map_y)
            if "gambler_pos" not in st or st["gambler_pos"] is None:
                gambler_map_x = map_w * 0.75
                gambler_map_y = map_h * 0.35
                st["gambler_pos"] = Vector2(map_anchor_x + gambler_map_x, gambler_map_y)
            if "spawn_pos" not in st or st["spawn_pos"] is None:
                # Fallback: use current player position if spawn_pos somehow missing
                st["spawn_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                print(f"⚠️ spawn_pos was missing, using current position as fallback")
            
            # Calculate camera offset
            cam = get_camera_offset_locked(gs.player_pos, screen_w, screen_h, player_half, map_w, map_h, map_anchor_x)
            st["camera"] = Vector2(cam.x, cam.y)
            st["locked_cam_x"] = cam.x
            st["locked_cam_y"] = cam.y
            
            print(f"🍺 Returned to tavern at player position ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f}), camera=({st['camera'].x:.1f}, {st['camera'].y:.1f})")
            return  # Skip the rest of the initialization
        else:
            # First time entering tavern or returning from overworld - use spawn logic
            # Set player starting position to bottom-left area (on the stairs/platform)
            # Based on screenshot: player is in bottom-left corner, on the stairs landing/platform
            # The stairs are between x: 0.08-0.18 (with walls at edges), and the landing is above y: 0.82
            # We want to spawn in the safe area: center of stairs horizontally, just above the landing
            
            # Safe spawn area: in the main room, to the right of stairs area
            # The stairs area has walls and barriers, so spawn in clear area of main room
            # Position: to the right of stairs (x > 0.20), in lower area but above stairs landing (y < 0.80)
            safe_spawn_x = map_w * 0.22  # To the right of stairs area (stairs end around 0.18 + wall)
            safe_spawn_y = map_h * 0.85  # In lower main room area, well above bottom wall
            
            # Try multiple spawn positions to find a safe one (in main room area)
            spawn_offsets = [
                (0, 0),              # Primary position
                (30, 0),             # More right
                (0, -30),            # More up
                (30, -30),           # Right and up
                (-20, 0),            # Slight left
                (0, 30),             # More down (but still above stairs)
                (map_w * 0.35 - safe_spawn_x, map_h * 0.50 - safe_spawn_y),  # Center of main room
                (map_w * 0.40 - safe_spawn_x, map_h * 0.60 - safe_spawn_y),  # Right-center area
            ]
            
            found_safe_spawn = False
            for offset_x, offset_y in spawn_offsets:
                test_x = safe_spawn_x + offset_x
                test_y = safe_spawn_y + offset_y
                
                # Make sure position is within map bounds (with margin for player size)
                margin = max(player_half.x, player_half.y) + 5
                if test_x < margin or test_x > map_w - margin:
                    continue
                if test_y < margin or test_y > map_h - margin:
                    continue
                
                # Check if this position is collision-free
                test_world_x = map_anchor_x + test_x
                test_world_y = test_y
                
                # Create a temporary player_pos to test collision
                temp_pos = Vector2(test_world_x, test_world_y)
                if not _check_collision(temp_pos, player_half, map_anchor_x, test_world_x, test_world_y):
                    gs.player_pos.x = test_world_x
                    gs.player_pos.y = test_world_y
                    found_safe_spawn = True
                    # Store spawn position in tavern state (in world coordinates for easy comparison)
                    st["spawn_pos"] = Vector2(test_world_x, test_world_y)
                    print(f"✅ Found safe spawn at map coords ({test_x:.1f}, {test_y:.1f}), world ({test_world_x:.1f}, {test_world_y:.1f})")
                    # Verify player can move in at least one direction
                    test_moves = [
                        (test_world_x + 10, test_world_y),  # Right
                        (test_world_x - 10, test_world_y),  # Left
                        (test_world_x, test_world_y + 10),  # Down
                        (test_world_x, test_world_y - 10),  # Up
                    ]
                    movable_directions = sum(1 for mx, my in test_moves 
                                            if not _check_collision(temp_pos, player_half, map_anchor_x, mx, my))
                    print(f"   Player can move in {movable_directions}/4 directions from spawn")
                    break
            
            if not found_safe_spawn:
                # Fallback: spawn in center of main room (should be safe - away from all walls)
                print(f"⚠️ Could not find safe spawn, using center fallback")
                gs.player_pos.x = map_anchor_x + map_w * 0.50
                gs.player_pos.y = map_h * 0.50
                # Verify fallback is safe, if not use a known safe area
                if _check_collision(gs.player_pos, player_half, map_anchor_x, gs.player_pos.x, gs.player_pos.y):
                    # Last resort: spawn near top-center (should be clear)
                    gs.player_pos.x = map_anchor_x + map_w * 0.50
                    gs.player_pos.y = map_h * 0.30
                    print(f"⚠️ Fallback had collision, using top-center position")
                # Store spawn position even for fallback
                st["spawn_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
        
        # Calculate locked camera offset (map is centered and doesn't move)
        cam = get_camera_offset_locked(gs.player_pos, screen_w, screen_h, player_half, map_w, map_h, map_anchor_x)
        st["camera"] = Vector2(cam.x, cam.y)
        st["locked_cam_x"] = cam.x  # Store locked X position
        st["locked_cam_y"] = cam.y  # Store locked Y position
        
        # Only set NPC positions on first entry (preserve them when returning from interactions)
        if is_first_entry:
            # Set barkeeper position (behind the bar counter)
            # Bar counter is at x: 0.08-0.3, y: 0.50
            # Position barkeeper at center of bar counter, further up
            barkeeper_map_x = map_w * 0.19  # Center of bar counter (0.08 + 0.3) / 2
            barkeeper_map_y = map_h * 0.40  # Further up from the bar counter
            st["barkeeper_pos"] = Vector2(map_anchor_x + barkeeper_map_x, barkeeper_map_y)
            print(f"🍺 Barkeeper positioned at map coords ({barkeeper_map_x:.1f}, {barkeeper_map_y:.1f}), world ({st['barkeeper_pos'].x:.1f}, {st['barkeeper_pos'].y:.1f})")
            
            # Set gambler position (top right corner)
            gambler_map_x = map_w * 0.75  # Right side of map
            gambler_map_y = map_h * 0.35  # Top area of map
            st["gambler_pos"] = Vector2(map_anchor_x + gambler_map_x, gambler_map_y)
            print(f"🎲 Gambler positioned at map coords ({gambler_map_x:.1f}, {gambler_map_y:.1f}), world ({st['gambler_pos'].x:.1f}, {st['gambler_pos'].y:.1f})")
            
            # Set whore position (bottom right corner) if present
            if st.get("whore_number") and st.get("whore_sprite") is not None:
                whore_map_x = map_w * 0.81  # Right side of map
                whore_map_y = map_h * 0.70  # Bottom area of map
                st["whore_pos"] = Vector2(map_anchor_x + whore_map_x, whore_map_y)
                print(f"💋 Whore{st['whore_number']} positioned at map coords ({whore_map_x:.1f}, {whore_map_y:.1f}), world ({st['whore_pos'].x:.1f}, {st['whore_pos'].y:.1f})")
            else:
                st["whore_pos"] = None
            
            # Set summoner position (center-left area of main room)
            summoner_map_x = map_w * 0.35  # Left-center area
            summoner_map_y = map_h * 0.55  # Middle area
            st["summoner_pos"] = Vector2(map_anchor_x + summoner_map_x, summoner_map_y)
            if st.get("summoner_name"):
                print(f"⚔️ Summoner '{st['summoner_name']}' positioned at map coords ({summoner_map_x:.1f}, {summoner_map_y:.1f}), world ({st['summoner_pos'].x:.1f}, {st['summoner_pos'].y:.1f})")
        else:
            # Preserve existing positions - don't reset them
            print(f"💾 Preserving existing NPC positions")
    else:
        # Fallback: use current player position
        st["camera"] = Vector2(0, 0)
        st["locked_cam_x"] = 0
        st["locked_cam_y"] = 0
        st["barkeeper_pos"] = None
        st["gambler_pos"] = None
        st["whore_pos"] = None
        st["whore_number"] = None
        st["whore_sprite"] = None
        st["summoner_pos"] = None
        st["summoner_name"] = None
        st["summoner_filename"] = None
        st["summoner_sprite"] = None
    
    print(f"🍺 Entered tavern at player position ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f}), camera=({st['camera'].x:.1f}, {st['camera'].y:.1f})")

def _is_near_spawn(gs, spawn_pos: Vector2, proximity_distance: float = 80.0) -> bool:
    """Check if player is near the spawn position."""
    if not spawn_pos:
        return False
    dx = gs.player_pos.x - spawn_pos.x
    dy = gs.player_pos.y - spawn_pos.y
    distance = (dx * dx + dy * dy) ** 0.5
    return distance <= proximity_distance

def _is_near_barkeeper(gs, barkeeper_pos: Vector2, proximity_distance: float = 200.0) -> bool:
    """Check if player is near the barkeeper.
    This check works through barriers (collision boundaries don't block detection)."""
    if not barkeeper_pos:
        return False
    dx = gs.player_pos.x - barkeeper_pos.x
    dy = gs.player_pos.y - barkeeper_pos.y
    distance = (dx * dx + dy * dy) ** 0.5
    return distance <= proximity_distance

def _is_near_gambler(gs, gambler_pos: Vector2, proximity_distance: float = 200.0) -> bool:
    """Check if player is near the gambler.
    This check works through barriers (collision boundaries don't block detection)."""
    if not gambler_pos:
        return False
    dx = gs.player_pos.x - gambler_pos.x
    dy = gs.player_pos.y - gambler_pos.y
    distance = (dx * dx + dy * dy) ** 0.5
    return distance <= proximity_distance

def _is_near_whore(gs, whore_pos: Vector2, proximity_distance: float = 200.0) -> bool:
    """Check if player is near the whore.
    This check works through barriers (collision boundaries don't block detection)."""
    if not whore_pos:
        return False
    dx = gs.player_pos.x - whore_pos.x
    dy = gs.player_pos.y - whore_pos.y
    distance = (dx * dx + dy * dy) ** 0.5
    return distance <= proximity_distance

def _is_near_summoner(gs, summoner_pos: Vector2, proximity_distance: float = 200.0) -> bool:
    """Check if player is near the summoner.
    This check works through barriers (collision boundaries don't block detection)."""
    if not summoner_pos:
        return False
    dx = gs.player_pos.x - summoner_pos.x
    dy = gs.player_pos.y - summoner_pos.y
    distance = (dx * dx + dy * dy) ** 0.5
    return distance <= proximity_distance

def _draw_exit_popup(screen, gs, spawn_pos: Vector2, map_anchor_x: int, map_src_x: int, map_src_y: int, 
                     map_dst_x: int, map_dst_y: int, player_half: Vector2, screen_w: int, screen_h: int, 
                     map_w: int, map_h: int):
    """Draw exit popup below spawn position when player is near (same style as tavern/shop popups)."""
    # Convert spawn world position to screen coordinates (same logic as player drawing)
    spawn_world_x_relative = spawn_pos.x - map_anchor_x
    spawn_world_y_relative = spawn_pos.y
    
    # Convert to screen coordinates (accounting for map cropping)
    spawn_screen_x = int(map_dst_x + (spawn_world_x_relative - map_src_x))
    spawn_screen_y = int(map_dst_y + (spawn_world_y_relative - map_src_y))
    
    # Medieval-style text
    text = "Press E to exit"
    
    # Load DH font if available, fallback to default (same as tavern/shop popups)
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
    
    # Speech bubble background (same style as tavern/shop popups)
    padding = 12
    bubble_w = text_rect.width + padding * 2
    bubble_h = text_rect.height + padding * 2
    triangle_height = 10  # Height of triangle pointing upward
    
    # Position popup BELOW the spawn point (under the door)
    PLAYER_SIZE_H = int(player_half.y * 2)
    bubble_y = spawn_screen_y + PLAYER_SIZE_H // 2 + 20  # Below spawn position (player's feet)
    bubble_x = spawn_screen_x - bubble_w // 2
    
    # Create bubble surface (need extra height for triangle on top)
    bubble = pygame.Surface((bubble_w, bubble_h + triangle_height), pygame.SRCALPHA)
    
    # Draw bubble with rounded corners effect (using filled rect + border)
    bubble_rect = pygame.Rect(0, triangle_height, bubble_w, bubble_h)
    bubble.fill((40, 35, 30, 240), bubble_rect)  # Dark brown/medieval color
    pygame.draw.rect(bubble, (80, 70, 60, 255), bubble_rect, 2)  # Border
    
    # Draw small triangle pointing UP to spawn position (at top of bubble)
    triangle_points = [
        (bubble_w // 2, triangle_height),  # Point of triangle (at top, pointing up)
        (bubble_w // 2 - 8, triangle_height + 10),  # Base left
        (bubble_w // 2 + 8, triangle_height + 10),  # Base right
    ]
    pygame.draw.polygon(bubble, (40, 35, 30, 240), triangle_points)
    pygame.draw.polygon(bubble, (80, 70, 60, 255), triangle_points, 2)
    
    # Make sure popup is visible on screen
    if bubble_x + bubble_w >= 0 and bubble_x <= screen_w and bubble_y >= 0 and bubble_y + bubble_h + triangle_height <= screen_h:
        screen.blit(bubble, (bubble_x, bubble_y))
        # Draw text on the bubble (offset by triangle height)
        screen.blit(text_surf, (bubble_x + padding, bubble_y + triangle_height + padding))

def _draw_barkeeper_popup(screen, gs, barkeeper_pos: Vector2, map_anchor_x: int, map_src_x: int, map_src_y: int, 
                          map_dst_x: int, map_dst_y: int, player_half: Vector2, screen_w: int, screen_h: int, 
                          map_w: int, map_h: int):
    """Draw barkeeper popup above barkeeper when player is near (same style as tavern/shop popups)."""
    # Convert barkeeper world position to screen coordinates
    barkeeper_world_x_relative = barkeeper_pos.x - map_anchor_x
    barkeeper_world_y_relative = barkeeper_pos.y
    
    # Convert to screen coordinates (accounting for map cropping)
    barkeeper_screen_x = int(map_dst_x + (barkeeper_world_x_relative - map_src_x))
    barkeeper_screen_y = int(map_dst_y + (barkeeper_world_y_relative - map_src_y))
    
    # Medieval-style text (bartender-appropriate)
    text = "Press E to order a drink"
    
    # Load DH font if available, fallback to default (same as tavern/shop popups)
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
    
    # Speech bubble background (same style as tavern/shop popups)
    padding = 12
    bubble_w = text_rect.width + padding * 2
    bubble_h = text_rect.height + padding * 2
    bubble = pygame.Surface((bubble_w, bubble_h), pygame.SRCALPHA)
    
    # Draw bubble with rounded corners effect (using filled rect + border)
    bubble.fill((40, 35, 30, 240))  # Dark brown/medieval color
    pygame.draw.rect(bubble, (80, 70, 60, 255), bubble.get_rect(), 2)  # Border
    
    # Draw small triangle pointing DOWN to barkeeper (at bottom of bubble)
    triangle_points = [
        (bubble_w // 2 - 8, bubble_h),
        (bubble_w // 2 + 8, bubble_h),
        (bubble_w // 2, bubble_h + 10),
    ]
    pygame.draw.polygon(bubble, (40, 35, 30, 240), triangle_points)
    pygame.draw.polygon(bubble, (80, 70, 60, 255), triangle_points, 2)
    
    # Position popup ABOVE the barkeeper
    if _BARKEEPER_SPRITE:
        BARKEEPER_HEIGHT = _BARKEEPER_SPRITE.get_height()
    else:
        BARKEEPER_HEIGHT = int(player_half.y * 2)
    bubble_x = barkeeper_screen_x - bubble_w // 2
    bubble_y = barkeeper_screen_y - BARKEEPER_HEIGHT // 2 - bubble_h - 10  # Above barkeeper
    
    # Make sure popup is visible on screen
    if bubble_x + bubble_w >= 0 and bubble_x <= screen_w and bubble_y >= 0 and bubble_y + bubble_h + 10 <= screen_h:
        screen.blit(bubble, (bubble_x, bubble_y))
        screen.blit(text_surf, (bubble_x + padding, bubble_y + padding))

def _draw_gambler_popup(screen, gs, gambler_pos: Vector2, map_anchor_x: int, map_src_x: int, map_src_y: int, 
                        map_dst_x: int, map_dst_y: int, player_half: Vector2, screen_w: int, screen_h: int, 
                        map_w: int, map_h: int):
    """Draw gambler popup above gambler when player is near (same style as tavern/shop popups)."""
    # Convert gambler world position to screen coordinates
    gambler_world_x_relative = gambler_pos.x - map_anchor_x
    gambler_world_y_relative = gambler_pos.y
    
    # Convert to screen coordinates (accounting for map cropping)
    gambler_screen_x = int(map_dst_x + (gambler_world_x_relative - map_src_x))
    gambler_screen_y = int(map_dst_y + (gambler_world_y_relative - map_src_y))
    
    # Medieval-style text
    text = "Press E To Gamble"
    
    # Load DH font if available, fallback to default (same as tavern/shop popups)
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
    
    # Speech bubble background (same style as tavern/shop popups)
    padding = 12
    bubble_w = text_rect.width + padding * 2
    bubble_h = text_rect.height + padding * 2
    bubble = pygame.Surface((bubble_w, bubble_h), pygame.SRCALPHA)
    
    # Draw bubble with rounded corners effect (using filled rect + border)
    bubble.fill((40, 35, 30, 240))  # Dark brown/medieval color
    pygame.draw.rect(bubble, (80, 70, 60, 255), bubble.get_rect(), 2)  # Border
    
    # Draw small triangle pointing DOWN to gambler (at bottom of bubble)
    triangle_points = [
        (bubble_w // 2 - 8, bubble_h),
        (bubble_w // 2 + 8, bubble_h),
        (bubble_w // 2, bubble_h + 10),
    ]
    pygame.draw.polygon(bubble, (40, 35, 30, 240), triangle_points)
    pygame.draw.polygon(bubble, (80, 70, 60, 255), triangle_points, 2)
    
    # Position popup ABOVE the gambler
    if _GAMBLER_SPRITE:
        GAMBLER_HEIGHT = _GAMBLER_SPRITE.get_height()
    else:
        GAMBLER_HEIGHT = int(player_half.y * 2)
    bubble_x = gambler_screen_x - bubble_w // 2
    bubble_y = gambler_screen_y - GAMBLER_HEIGHT // 2 - bubble_h - 10  # Above gambler
    
    # Make sure popup is visible on screen
    if bubble_x + bubble_w >= 0 and bubble_x <= screen_w and bubble_y >= 0 and bubble_y + bubble_h + 10 <= screen_h:
        screen.blit(bubble, (bubble_x, bubble_y))
        screen.blit(text_surf, (bubble_x + padding, bubble_y + padding))

def _get_whore_popup_text(whore_number: int) -> str:
    """Get the popup text based on whore number."""
    if 1 <= whore_number <= 5:
        return "Press E To Sleep With Whore"
    elif 6 <= whore_number <= 8:
        return "Press E To Sleep With Whores"
    elif whore_number == 9:
        return "Press E To Have A Harem"
    else:
        return "Press E To Interact"

def _whore_price(whore_number: int) -> int:
    """Return the price in gold for the selected whore."""
    if 1 <= whore_number <= 5:
        return 10
    if 6 <= whore_number <= 8:
        return 20
    if whore_number == 9:
        return 50
    return 10

def _whore_description(whore_number: int) -> str:
    """Return a short description of the whore group for UI text."""
    if 1 <= whore_number <= 5:
        return "the tavern maiden"
    if 6 <= whore_number <= 8:
        return "the twin sisters"
    if whore_number == 9:
        return "the harem of five"
    return "the tavern maiden"

def _draw_whore_popup(screen, gs, whore_pos: Vector2, whore_number: int, map_anchor_x: int, map_src_x: int, map_src_y: int, 
                      map_dst_x: int, map_dst_y: int, player_half: Vector2, screen_w: int, screen_h: int, 
                      map_w: int, map_h: int):
    """Draw whore popup above whore when player is near (same style as tavern/shop popups)."""
    # Convert whore world position to screen coordinates
    whore_world_x_relative = whore_pos.x - map_anchor_x
    whore_world_y_relative = whore_pos.y
    
    # Convert to screen coordinates (accounting for map cropping)
    whore_screen_x = int(map_dst_x + (whore_world_x_relative - map_src_x))
    whore_screen_y = int(map_dst_y + (whore_world_y_relative - map_src_y))
    
    # Get text based on whore number
    text = _get_whore_popup_text(whore_number)
    
    # Load DH font if available, fallback to default (same as tavern/shop popups)
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
    
    # Speech bubble background (same style as tavern/shop popups)
    padding = 12
    bubble_w = text_rect.width + padding * 2
    bubble_h = text_rect.height + padding * 2
    bubble = pygame.Surface((bubble_w, bubble_h), pygame.SRCALPHA)
    
    # Draw bubble with rounded corners effect (using filled rect + border)
    bubble.fill((40, 35, 30, 240))  # Dark brown/medieval color
    pygame.draw.rect(bubble, (80, 70, 60, 255), bubble.get_rect(), 2)  # Border
    
    # Draw small triangle pointing DOWN to whore (at bottom of bubble)
    triangle_points = [
        (bubble_w // 2 - 8, bubble_h),
        (bubble_w // 2 + 8, bubble_h),
        (bubble_w // 2, bubble_h + 10),
    ]
    pygame.draw.polygon(bubble, (40, 35, 30, 240), triangle_points)
    pygame.draw.polygon(bubble, (80, 70, 60, 255), triangle_points, 2)
    
    # Position popup ABOVE the whore
    PLAYER_SIZE_H = int(player_half.y * 2)
    bubble_x = whore_screen_x - bubble_w // 2
    bubble_y = whore_screen_y - PLAYER_SIZE_H // 2 - bubble_h - 10  # Above whore
    
    # Make sure popup is visible on screen
    if bubble_x + bubble_w >= 0 and bubble_x <= screen_w and bubble_y >= 0 and bubble_y + bubble_h + 10 <= screen_h:
        screen.blit(bubble, (bubble_x, bubble_y))
        screen.blit(text_surf, (bubble_x + padding, bubble_y + padding))

def _get_dh_font(size: int) -> pygame.font.Font:
    """Get DH font at specified size, fallback to default font."""
    try:
        dh_font_path = os.path.join(S.ASSETS_FONTS_DIR, S.DND_FONT_FILE)
        if os.path.exists(dh_font_path):
            return pygame.font.Font(dh_font_path, size)
    except:
        pass
    return pygame.font.SysFont(None, size)

def _draw_gambler_intro_textbox(screen, gs, dt: float, screen_w: int, screen_h: int):
    """Draw gambler intro textbox (same style as kicked out textbox)."""
    st = gs._tavern_state
    
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, screen_h - box_h - margin_bottom, screen_w - margin_x * 2, box_h)
    
    # Box styling (matches kicked out textbox)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)
    
    # Text rendering (simple wrap)
    font = _get_dh_font(28)
    text = "You want to play eh? Lets play Doom Roll!"
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
    
    # Blinking prompt bottom-right
    blink_t = st.get("gambler_intro_blink_t", 0.0)
    blink_on = int(blink_t * 2) % 2 == 0
    if blink_on:
        prompt_font = _get_dh_font(20)
        prompt = "Press SPACE or Click to continue"
        psurf = prompt_font.render(prompt, False, (40, 40, 40))
        px = rect.right - psurf.get_width() - 16
        py = rect.bottom - psurf.get_height() - 12
        screen.blit(psurf, (px, py))

def _play_laugh_sound():
    """Play laugh sound (Laugh.mp3)."""
    try:
        sound_path = os.path.join("Assets", "Tavern", "Laugh.mp3")
        if os.path.exists(sound_path):
            sfx = pygame.mixer.Sound(sound_path)
            ch = pygame.mixer.find_channel(True)
            ch.play(sfx)
            print("🎵 Playing laugh sound (Laugh.mp3)")
        else:
            print(f"⚠️ Laugh sound not found at {sound_path}")
    except Exception as e:
        print(f"⚠️ Failed to play laugh sound: {e}")

def _play_barkeeper_sound():
    """Play a random barkeeper greeting sound."""
    try:
        choices = [
            os.path.join("Assets", "Tavern Barkeeper1.mp3"),
            os.path.join("Assets", "Tavern Barkeeper2.mp3"),
            os.path.join("Assets", "Tavern Barkeeper3.mp3"),
            os.path.join("Assets", "Tavern Barkeeper4.mp3"),
        ]
        existing = [p for p in choices if os.path.exists(p)]
        if not existing:
            # Try legacy paths inside Assets/Tavern
            fallback = [
                os.path.join("Assets", "Tavern", "Barkeeper1.mp3"),
                os.path.join("Assets", "Tavern", "Barkeeper2.mp3"),
                os.path.join("Assets", "Tavern", "Barkeeper3.mp3"),
                os.path.join("Assets", "Tavern", "Barkeeper4.mp3"),
            ]
            existing = [p for p in fallback if os.path.exists(p)]
        if not existing:
            print("⚠️ Barkeeper sounds not found")
            return
        sound_path = random.choice(existing)
        sfx = pygame.mixer.Sound(sound_path)
        ch = pygame.mixer.find_channel(True)
        ch.play(sfx)
        print(f"🎵 Playing barkeeper sound ({os.path.basename(sound_path)})")
    except Exception as e:
        print(f"⚠️ Failed to play barkeeper sound: {e}")

def _play_ui_click():
    """Play the standard UI click sound if available."""
    try:
        bank = audio.get_global_bank()
        if bank:
            audio.play_click(bank)
    except Exception:
        pass

def _draw_game_selection_popup(screen, gs, dt: float, screen_w: int, screen_h: int):
    """Draw game selection popup (Doom Roll vs Twenty-One)."""
    st = gs._tavern_state
    
    # Popup dimensions (use logical coordinates)
    popup_w = 500
    popup_h = 300
    popup_x = (screen_w - popup_w) // 2
    popup_y = (screen_h - popup_h) // 2
    
    # Draw semi-transparent overlay (use logical size)
    overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))
    
    # Popup box (match whore confirmation styling)
    popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
    pygame.draw.rect(screen, (40, 35, 30), popup_rect)
    pygame.draw.rect(screen, (80, 70, 60), popup_rect, 3)
    inner = popup_rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 50, 40), inner, 2)
    
    # Title
    font = _get_dh_font(32)
    title_text = "Choose a Game"
    title_surf = font.render(title_text, True, (235, 225, 210))
    title_x = popup_x + (popup_w - title_surf.get_width()) // 2
    title_y = popup_y + 20
    screen.blit(title_surf, (title_x, title_y))
    
    # Game buttons
    button_font = _get_dh_font(24)
    button_h = 48
    button_spacing = 20
    button_w = popup_w - 80
    button_y_start = title_y + title_surf.get_height() + 40
    
    # Mouse position in logical coordinates (use coords module)
    try:
        from systems import coords
        screen_mx, screen_my = pygame.mouse.get_pos()
        logical_mouse_x, logical_mouse_y = coords.screen_to_logical((screen_mx, screen_my))
    except (ImportError, AttributeError):
        # Fallback if coords not available
        logical_mouse_x, logical_mouse_y = pygame.mouse.get_pos()
    
    button_specs = [
        ("doom_roll", "Doom Roll", (230, 228, 220), (60, 60, 60)),
        ("twenty_one", "Twenty-One", (230, 228, 220), (60, 60, 60)),
        ("nevermind", "Nevermind", (120, 70, 70), (20, 20, 20)),
    ]
    
    st["game_selection_buttons"] = []
    
    for idx, (game_key, label, base_color, border_color) in enumerate(button_specs):
        button_y = button_y_start + idx * (button_h + button_spacing)
        button_rect = pygame.Rect(popup_x + 40, button_y, button_w, button_h)
        st["game_selection_buttons"].append((button_rect, game_key))
        
        hover = button_rect.collidepoint(logical_mouse_x, logical_mouse_y)
        if game_key == "nevermind":
            color = (140, 90, 90) if hover else base_color
            text_color = (255, 255, 255)
        else:
            color = (240, 238, 232) if not hover else (230, 228, 220)
            text_color = (16, 16, 16)
        pygame.draw.rect(screen, color, button_rect)
        pygame.draw.rect(screen, border_color, button_rect, 2)
        
        text_surf = button_font.render(label, True, text_color)
        text_x = button_rect.x + (button_rect.w - text_surf.get_width()) // 2
        text_y = button_rect.y + (button_rect.h - text_surf.get_height()) // 2
        screen.blit(text_surf, (text_x, text_y))
    

def _draw_bet_selection_popup(screen, gs, dt: float, screen_w: int, screen_h: int):
    """Draw bet selection popup (centered, modal style matching popup style)."""
    st = gs._tavern_state
    
    # Get player's current gold
    player_gold = getattr(gs, "gold", 0)
    
    # Popup dimensions (bigger)
    popup_w = 500
    popup_h = 400
    popup_x = (screen_w - popup_w) // 2
    popup_y = (screen_h - popup_h) // 2
    
    # Draw semi-transparent overlay
    overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))
    
    # Popup box (matches popup style - dark brown/medieval)
    popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
    pygame.draw.rect(screen, (40, 35, 30), popup_rect)
    pygame.draw.rect(screen, (80, 70, 60), popup_rect, 3)
    inner = popup_rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 50, 40), inner, 2)
    
    # Title
    font = _get_dh_font(32)
    title_text = "How much to gamble?"
    title_surf = font.render(title_text, True, (255, 255, 255))
    title_x = popup_x + (popup_w - title_surf.get_width()) // 2
    title_y = popup_y + 20
    screen.blit(title_surf, (title_x, title_y))
    
    # Current gold display
    gold_font = _get_dh_font(20)
    gold_text = f"Your gold: {player_gold}"
    gold_surf = gold_font.render(gold_text, True, (200, 200, 150))
    gold_x = popup_x + (popup_w - gold_surf.get_width()) // 2
    gold_y = title_y + title_surf.get_height() + 15
    screen.blit(gold_surf, (gold_x, gold_y))
    
    # Bet buttons (1, 5, 10, 20, All in)
    button_font = _get_dh_font(24)
    button_options = [
        (1, "1 Gold"),
        (5, "5 Gold"),
        (10, "10 Gold"),
        (20, "20 Gold"),
        (-1, f"All In ({player_gold})"),  # -1 means all in
    ]
    
    button_y_start = gold_y + gold_surf.get_height() + 30
    button_h = 40
    button_spacing = 10
    button_w = popup_w - 80
    
    st["bet_buttons"] = []  # Store button rects for click detection
    
    button_index = 0
    for amount, label in button_options:
        # Skip if amount exceeds available gold
        if amount > 0 and amount > player_gold:
            continue
        if amount == -1 and player_gold == 0:
            continue
        
        button_y = button_y_start + button_index * (button_h + button_spacing)
        button_rect = pygame.Rect(popup_x + 40, button_y, button_w, button_h)
        st["bet_buttons"].append((button_rect, amount))
        button_index += 1
        
        # Button styling (hover effect if mouse over)
        # Get mouse position for hover detection - convert to logical coordinates
        screen_mx, screen_my = pygame.mouse.get_pos()
        try:
            from systems import coords
            logical_mouse_x, logical_mouse_y = coords.screen_to_logical((screen_mx, screen_my))
        except (ImportError, AttributeError):
            # Fallback if coords not available
            logical_mouse_x, logical_mouse_y = screen_mx, screen_my
        
        hover = button_rect.collidepoint(logical_mouse_x, logical_mouse_y)
        button_color = (60, 50, 40) if hover else (50, 40, 30)
        border_color = (100, 90, 80) if hover else (80, 70, 60)
        
        pygame.draw.rect(screen, button_color, button_rect)
        pygame.draw.rect(screen, border_color, button_rect, 2)
        
        # Button text
        button_text = label if amount != -1 or player_gold > 0 else "All In (0)"
        text_surf = button_font.render(button_text, True, (255, 255, 255))
        text_x = button_rect.x + (button_rect.w - text_surf.get_width()) // 2
        text_y = button_rect.y + (button_rect.h - text_surf.get_height()) // 2
        screen.blit(text_surf, (text_x, text_y))
    
    # Cancel/ESC hint
    hint_font = _get_dh_font(18)
    hint_text = "Press ESC to cancel"
    hint_surf = hint_font.render(hint_text, True, (150, 150, 150))
    hint_x = popup_x + (popup_w - hint_surf.get_width()) // 2
    hint_y = popup_y + popup_h - hint_surf.get_height() - 15
    screen.blit(hint_surf, (hint_x, hint_y))

def _draw_kicked_out_textbox(screen, gs, dt: float, screen_w: int, screen_h: int):
    """Draw the 'kicked out' textbox (same style as summoner_battle textbox)."""
    st = gs._tavern_state
    
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, screen_h - box_h - margin_bottom, screen_w - margin_x * 2, box_h)
    
    # Box styling (matches summoner_battle textbox)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)
    
    # Text rendering (simple wrap)
    font = _get_dh_font(28)
    text = "You are kicked out of the tavern"
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
    
    # Blinking prompt bottom-right
    blink_t = st.get("kicked_out_blink_t", 0.0)
    blink_on = int(blink_t * 2) % 2 == 0
    if blink_on:
        prompt_font = _get_dh_font(20)
        prompt = "Press Enter to continue"
        psurf = prompt_font.render(prompt, False, (40, 40, 40))
        px = rect.right - psurf.get_width() - 16
        py = rect.bottom - psurf.get_height() - 12
        screen.blit(psurf, (px, py))

def _draw_whore_confirm_popup(screen, gs, dt: float, screen_w: int, screen_h: int):
    """Draw confirmation popup for whore interaction."""
    st = gs._tavern_state
    
    price = int(st.get("whore_confirm_price", 0))
    whore_number = st.get("whore_number", 0)
    player_gold = max(0, int(getattr(gs, "gold", 0)))
    can_afford = player_gold >= price and price > 0
    
    # Popup dimensions
    popup_w = 440
    popup_h = 230
    popup_x = (screen_w - popup_w) // 2
    popup_y = (screen_h - popup_h) // 2
    
    # Overlay
    overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))
    
    # Popup background
    popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
    pygame.draw.rect(screen, (40, 35, 30), popup_rect)
    pygame.draw.rect(screen, (80, 70, 60), popup_rect, 3)
    inner = popup_rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 50, 40), inner, 2)
    
    # Title
    title_font = _get_dh_font(32)
    title_text = "Spend The Night?"
    title_surf = title_font.render(title_text, True, (235, 225, 210))
    title_x = popup_x + (popup_w - title_surf.get_width()) // 2
    title_y = popup_y + 20
    screen.blit(title_surf, (title_x, title_y))
    
    body_font = _get_dh_font(24)
    cost_text = f"Cost: {price} Gold"
    cost_surf = body_font.render(cost_text, True, (220, 210, 190))
    cost_x = popup_x + (popup_w - cost_surf.get_width()) // 2
    cost_y = title_y + title_surf.get_height() + 24
    screen.blit(cost_surf, (cost_x, cost_y))
    
    # Player gold
    gold_font = _get_dh_font(20)
    gold_text = f"Your gold: {player_gold}"
    gold_color = (200, 200, 150) if can_afford else (200, 80, 80)
    gold_surf = gold_font.render(gold_text, True, gold_color)
    gold_x = popup_x + (popup_w - gold_surf.get_width()) // 2
    gold_y = cost_y + cost_surf.get_height() + 12
    screen.blit(gold_surf, (gold_x, gold_y))
    
    # Error message if set
    error_text = st.get("whore_confirm_error", "")
    if error_text:
        error_font = _get_dh_font(18)
        error_surf = error_font.render(error_text, True, (220, 100, 100))
        screen.blit(error_surf, (popup_x + (popup_w - error_surf.get_width()) // 2, gold_y + gold_surf.get_height() + 4))
    
    # Buttons
    button_font = _get_dh_font(24)
    button_w = 170
    button_h = 44
    button_gap = 30
    buttons_y = popup_y + popup_h - button_h - 32
    
    accept_rect = pygame.Rect(popup_x + popup_w // 2 - button_gap // 2 - button_w, buttons_y, button_w, button_h)
    decline_rect = pygame.Rect(popup_x + popup_w // 2 + button_gap // 2, buttons_y, button_w, button_h)
    
    st["whore_confirm_buttons"] = [
        (accept_rect, "accept"),
        (decline_rect, "decline"),
    ]
    
    # Mouse position in logical coordinates
    mouse_x, mouse_y = pygame.mouse.get_pos()
    screen_surface = pygame.display.get_surface()
    logical_mouse_x = mouse_x * screen_w // screen_surface.get_width() if screen_surface and screen_surface.get_width() != screen_w else mouse_x
    logical_mouse_y = mouse_y * screen_h // screen_surface.get_height() if screen_surface and screen_surface.get_height() != screen_h else mouse_y
    
    # Draw Accept button
    accept_hover = accept_rect.collidepoint(logical_mouse_x, logical_mouse_y)
    accept_enabled = can_afford
    if accept_enabled:
        accept_color = (70, 120, 80) if not accept_hover else (90, 150, 100)
        accept_text_color = (255, 255, 255)
    else:
        accept_color = (70, 70, 70)
        accept_text_color = (160, 160, 160)
        accept_hover = False
    pygame.draw.rect(screen, accept_color, accept_rect, border_radius=6)
    pygame.draw.rect(screen, (20, 20, 20), accept_rect, 2, border_radius=6)
    accept_label = "Accept"
    accept_surf = button_font.render(accept_label, True, accept_text_color)
    screen.blit(accept_surf, (accept_rect.centerx - accept_surf.get_width() // 2, accept_rect.centery - accept_surf.get_height() // 2))
    
    # Draw Decline button
    decline_hover = decline_rect.collidepoint(logical_mouse_x, logical_mouse_y)
    decline_color = (120, 70, 70) if decline_hover else (100, 60, 60)
    pygame.draw.rect(screen, decline_color, decline_rect)
    pygame.draw.rect(screen, (20, 20, 20), decline_rect, 2)
    decline_surf = button_font.render("Decline", True, (255, 255, 255))
    screen.blit(decline_surf, (decline_rect.centerx - decline_surf.get_width() // 2, decline_rect.centery - decline_surf.get_height() // 2))

def _attempt_whore_purchase(gs, st) -> bool:
    """Deduct gold for whore interaction if possible."""
    price = int(st.get("whore_confirm_price", 0))
    player_gold = max(0, int(getattr(gs, "gold", 0)))
    
    if price <= 0:
        st["whore_confirm_active"] = False
        st["whore_confirm_buttons"] = []
        st["whore_confirm_error"] = ""
        return True
    
    if player_gold < price:
        st["whore_confirm_error"] = "You do not have enough gold."
        return False
    
    gs.gold = player_gold - price
    st["whore_confirm_active"] = False
    st["whore_confirm_buttons"] = []
    st["whore_confirm_error"] = ""
    print(f"💰 Paid {price} gold for the whore. Remaining gold: {gs.gold}")
    
    # Stop tavern walking sound before transition
    if hasattr(gs, "tavern_walking_channel") and gs.tavern_walking_channel:
        try:
            gs.tavern_walking_channel.stop()
        except Exception:
            pass
    if hasattr(gs, "tavern_is_walking"):
        gs.tavern_is_walking = False
        gs.tavern_walking_channel = None
    
    return True

def _draw_summoner_popup(screen, gs, summoner_pos: Vector2, map_anchor_x: int, map_src_x: int, map_src_y: int, 
                         map_dst_x: int, map_dst_y: int, player_half: Vector2, screen_w: int, screen_h: int, 
                         map_w: int, map_h: int):
    """Draw summoner popup above summoner when player is near (same style as tavern/shop popups)."""
    # Convert summoner world position to screen coordinates
    summoner_world_x_relative = summoner_pos.x - map_anchor_x
    summoner_world_y_relative = summoner_pos.y
    
    # Convert to screen coordinates (accounting for map cropping)
    summoner_screen_x = int(map_dst_x + (summoner_world_x_relative - map_src_x))
    summoner_screen_y = int(map_dst_y + (summoner_world_y_relative - map_src_y))
    
    # Barfight text
    text = "Press E To Start A Barfight"
    
    # Load DH font if available, fallback to default (same as tavern/shop popups)
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
    
    # Speech bubble background (same style as tavern/shop popups)
    padding = 12
    bubble_w = text_rect.width + padding * 2
    bubble_h = text_rect.height + padding * 2
    bubble = pygame.Surface((bubble_w, bubble_h), pygame.SRCALPHA)
    
    # Draw bubble with rounded corners effect (using filled rect + border)
    bubble.fill((40, 35, 30, 240))  # Dark brown/medieval color
    pygame.draw.rect(bubble, (80, 70, 60, 255), bubble.get_rect(), 2)  # Border
    
    # Draw small triangle pointing DOWN to summoner (at bottom of bubble)
    triangle_points = [
        (bubble_w // 2 - 8, bubble_h),
        (bubble_w // 2 + 8, bubble_h),
        (bubble_w // 2, bubble_h + 10),
    ]
    pygame.draw.polygon(bubble, (40, 35, 30, 240), triangle_points)
    pygame.draw.polygon(bubble, (80, 70, 60, 255), triangle_points, 2)
    
    # Position popup ABOVE the summoner
    PLAYER_SIZE_H = int(player_half.y * 2)
    bubble_x = summoner_screen_x - bubble_w // 2
    bubble_y = summoner_screen_y - PLAYER_SIZE_H // 2 - bubble_h - 10  # Above summoner
    
    # Make sure popup is visible on screen
    if bubble_x + bubble_w >= 0 and bubble_x <= screen_w and bubble_y >= 0 and bubble_y + bubble_h + 10 <= screen_h:
        screen.blit(bubble, (bubble_x, bubble_y))
        screen.blit(text_surf, (bubble_x + padding, bubble_y + padding))

def handle(events, gs, dt: float, **_):
    """Handle events for the tavern screen."""
    st = gs._tavern_state
    if st.get("barkeeper_shop_active") and not gs.shop_open:
        st["barkeeper_shop_active"] = False
    
    # Handle game selection popup first (modal - blocks all other input)
    if st.get("show_game_selection", False):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    _play_ui_click()
                    # Cancel game selection
                    st["show_game_selection"] = False
                    st["game_selection_buttons"] = []
                    st["selected_game"] = None
                    print("🎲 Game selection cancelled")
                elif event.key == pygame.K_1:
                    _play_ui_click()
                    # Select Doom Roll
                    st["selected_game"] = "doom_roll"
                    st["show_game_selection"] = False
                    st["game_selection_buttons"] = []
                    st["show_bet_selection"] = True
                    st["bet_selection_active"] = True
                    print("🎲 Selected Doom Roll")
                elif event.key == pygame.K_2:
                    _play_ui_click()
                    # Select Twenty-One
                    st["selected_game"] = "twenty_one"
                    st["show_game_selection"] = False
                    st["game_selection_buttons"] = []
                    st["show_bet_selection"] = True
                    st["bet_selection_active"] = True
                    print("🎲 Selected Twenty-One")
                elif event.key == pygame.K_3:
                    _play_ui_click()
                    st["selected_game"] = None
                    st["show_game_selection"] = False
                    st["game_selection_buttons"] = []
                    print("🎲 Game selection cancelled")
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # event.pos is already converted to logical coordinates in main.py
                click_pos = event.pos
                
                buttons = st.get("game_selection_buttons", [])
                for button_rect, game_type in buttons:
                    if button_rect.collidepoint(click_pos):
                        _play_ui_click()
                        st["show_game_selection"] = False
                        st["game_selection_buttons"] = []
                        if game_type == "nevermind":
                            st["selected_game"] = None
                            print("🎲 Game selection cancelled")
                        else:
                            st["selected_game"] = game_type
                            st["show_bet_selection"] = True
                            st["bet_selection_active"] = True
                            print(f"🎲 Selected {game_type}")
                        break
        # Block all other input while game selection is active
        return None
    
    # Handle gambler intro textbox (modal - blocks all other input)
    # NOTE: This is now skipped if game selection is used, but kept for backwards compatibility
    if st.get("show_gambler_intro", False) or st.get("gambler_intro_active", False):
        for event in events:
            if event.type == pygame.KEYDOWN:
                # ESC can still exit
                if event.key == pygame.K_ESCAPE:
                    # Cancel intro textbox
                    st["show_gambler_intro"] = False
                    st["gambler_intro_active"] = False
                    print("🎲 Intro cancelled")
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    # Dismiss intro textbox, play laugh sound, show game selection
                    st["show_gambler_intro"] = False
                    st["gambler_intro_active"] = False
                    _play_laugh_sound()
                    st["show_game_selection"] = True
                    print("🎲 Intro dismissed, showing game selection")
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Dismiss intro textbox, play laugh sound, show game selection
                st["show_gambler_intro"] = False
                st["gambler_intro_active"] = False
                _play_laugh_sound()
                st["show_game_selection"] = True
                print("🎲 Intro dismissed, showing game selection")
        # Block all other input while intro is active
        return None
    
    # Handle bet selection popup (modal - blocks all other input)
    if st.get("show_bet_selection", False):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    _play_ui_click()
                    # Cancel bet selection
                    st["show_bet_selection"] = False
                    st["bet_selection_active"] = False
                    st["bet_buttons"] = []
                    print("🎲 Bet selection cancelled")
                elif event.key == pygame.K_1:
                    # Bet 1 gold
                    player_gold = getattr(gs, "gold", 0)
                    if player_gold >= 1:
                        _play_ui_click()
                        st["selected_bet"] = 1
                        st["show_bet_selection"] = False
                        st["bet_selection_active"] = False
                        # Store current position before transitioning to gambling
                        st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                        print(f"💾 Stored tavern position before gambling: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                        print(f"🎲 Selected bet: 1 gold")
                        return "GAMBLING"
                elif event.key == pygame.K_2:
                    # Bet 5 gold
                    player_gold = getattr(gs, "gold", 0)
                    if player_gold >= 5:
                        _play_ui_click()
                        st["selected_bet"] = 5
                        st["show_bet_selection"] = False
                        st["bet_selection_active"] = False
                        # Store current position before transitioning to gambling
                        st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                        print(f"💾 Stored tavern position before gambling: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                        print(f"🎲 Selected bet: 5 gold")
                        return "GAMBLING"
                elif event.key == pygame.K_3:
                    # Bet 10 gold
                    player_gold = getattr(gs, "gold", 0)
                    if player_gold >= 10:
                        _play_ui_click()
                        st["selected_bet"] = 10
                        st["show_bet_selection"] = False
                        st["bet_selection_active"] = False
                        # Store current position before transitioning to gambling
                        st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                        print(f"💾 Stored tavern position before gambling: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                        print(f"🎲 Selected bet: 10 gold")
                        return "GAMBLING"
                elif event.key == pygame.K_4:
                    # Bet 20 gold
                    player_gold = getattr(gs, "gold", 0)
                    if player_gold >= 20:
                        _play_ui_click()
                        st["selected_bet"] = 20
                        st["show_bet_selection"] = False
                        st["bet_selection_active"] = False
                        # Store current position before transitioning to gambling
                        st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                        print(f"💾 Stored tavern position before gambling: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                        print(f"🎲 Selected bet: 20 gold")
                        return "GAMBLING"
                elif event.key == pygame.K_5:
                    # All in
                    player_gold = getattr(gs, "gold", 0)
                    if player_gold > 0:
                        _play_ui_click()
                        st["selected_bet"] = player_gold  # Store actual gold amount for "all in"
                        st["show_bet_selection"] = False
                        st["bet_selection_active"] = False
                        # Store current position before transitioning to gambling
                        st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                        print(f"💾 Stored tavern position before gambling: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                        print(f"🎲 Selected bet: All in ({player_gold} gold)")
                        return "GAMBLING"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # event.pos is already converted to logical coordinates in main.py
                click_pos = event.pos
                
                player_gold = getattr(gs, "gold", 0)
                buttons = st.get("bet_buttons", [])
                for button_rect, amount in buttons:
                    if button_rect.collidepoint(click_pos):
                        # Determine actual bet amount
                        if amount == -1:  # All in
                            bet_amount = player_gold
                        else:
                            bet_amount = amount
                        
                        # Check if player has enough gold
                        if player_gold >= bet_amount and bet_amount > 0:
                            _play_ui_click()
                            st["selected_bet"] = bet_amount
                            st["show_bet_selection"] = False
                            st["bet_selection_active"] = False
                            st["bet_buttons"] = []
                            # Store current position before transitioning to gambling
                            st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                            print(f"💾 Stored tavern position before gambling: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                            print(f"🎲 Selected bet: {bet_amount} gold")
                            return "GAMBLING"
        # Block all other input while bet selection is active
        return None
    
    # Handle whore confirmation popup (modal)
    if st.get("whore_confirm_active", False):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    _play_ui_click()
                    st["whore_confirm_active"] = False
                    st["whore_confirm_buttons"] = []
                    st["whore_confirm_error"] = ""
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    _play_ui_click()
                    if _attempt_whore_purchase(gs, st):
                        # Store current position before transitioning to whore
                        st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                        print(f"💾 Stored tavern position before whore: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                        return "WHORE"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                logical_mouse_x, logical_mouse_y = event.pos
                for rect, action in st.get("whore_confirm_buttons", []):
                    if rect.collidepoint(logical_mouse_x, logical_mouse_y):
                        _play_ui_click()
                        if action == "accept":
                            if _attempt_whore_purchase(gs, st):
                                # Store current position before transitioning to whore
                                st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                                print(f"💾 Stored tavern position before whore: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                                return "WHORE"
                        elif action == "decline":
                            st["whore_confirm_active"] = False
                            st["whore_confirm_buttons"] = []
                            st["whore_confirm_error"] = ""
                        break
        # Block all other input while confirmation is active
        return None
    
    # Handle "kicked out" textbox (modal - blocks all other input)
    if st.get("kicked_out_textbox_active", False):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    # Dismiss textbox
                    st["kicked_out_textbox_active"] = False
                    
                    # Mark that we're exiting (same as normal exit)
                    # Store flag to remove tavern after position is restored
                    st["remove_tavern_on_exit"] = True
                    
                    # Return to overworld (same as normal exit - main.py will handle position restoration)
                    return "GAME"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Dismiss textbox
                st["kicked_out_textbox_active"] = False
                
                # Mark that we're exiting (same as normal exit)
                # Store flag to remove tavern after position is restored
                st["remove_tavern_on_exit"] = True
                
                # Return to overworld (same as normal exit - main.py will handle position restoration)
                return "GAME"
        # Block all other input while textbox is active
        return None
    
    # Use the near_spawn, near_barkeeper, near_gambler, near_whore, and near_summoner state that was updated in update() function
    near_spawn = st.get("near_spawn", False)
    near_barkeeper = st.get("near_barkeeper", False)
    near_gambler = st.get("near_gambler", False)
    near_whore = st.get("near_whore", False)
    near_summoner = st.get("near_summoner", False)
    
    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if gs.shop_open:
                    gs.shop_open = False
                    shop.reset_scroll()
                    shop.clear_shop_override()
                    st["barkeeper_shop_active"] = False
                    try:
                        bank = audio.get_global_bank()
                        if bank:
                            audio.play_click(bank)
                    except Exception:
                        pass
                    # Stop any pending shop music timers (reuse overworld logic)
                    gs._shop_music_playing = False
                    gs._waiting_for_shop_music = False
                    if hasattr(gs, "_shop_music_timer"):
                        delattr(gs, "_shop_music_timer")
                # Skip further handling of ESC within tavern
                continue
            elif event.key == pygame.K_e:
                if near_spawn:
                    # Return to game mode (only when near spawn)
                    return "GAME"
                elif near_barkeeper:
                    # Toggle barkeeper shop (limited inventory: rations & alcohol)
                    if st.get("show_gambler_intro") or st.get("show_bet_selection") or st.get("kicked_out_textbox_active"):
                        # Block barkeeper interaction while other modals are active
                        continue

                    if not gs.shop_open:
                        shop.configure_shop_override(
                            item_ids=["rations", "alcohol"],
                            categories=["food"],
                            title="Barkeep's Provisions",
                        )
                        gs.shop_open = True
                        st["barkeeper_shop_active"] = True
                        try:
                            _play_barkeeper_sound()
                            bank = audio.get_global_bank()
                            if bank:
                                audio.play_click(bank)
                        except Exception:
                            pass
                    else:
                        gs.shop_open = False
                        shop.clear_shop_override()
                        st["barkeeper_shop_active"] = False
                        try:
                            _play_barkeeper_sound()
                            bank = audio.get_global_bank()
                            if bank:
                                audio.play_click(bank)
                        except Exception:
                            pass
                elif near_gambler:
                    # Show game selection popup first (skip intro textbox)
                    st["show_game_selection"] = True
                    st["game_selection_buttons"] = []
                    print("🎲 Player wants to gamble - showing game selection")
                elif near_whore:
                    # Transition to whore screen
                    # Check for any blocking modals
                    blocking_modals = (
                        st.get("show_game_selection") or
                        st.get("show_gambler_intro") or 
                        st.get("show_bet_selection") or 
                        st.get("kicked_out_textbox_active") or 
                        st.get("whore_confirm_active") or
                        gs.shop_open or
                        bag_ui.is_open() or
                        party_manager.is_open() or
                        ledger.is_open() or
                        currency_display.is_open() or
                        rest_popup.is_open()
                    )
                    
                    if blocking_modals:
                        # Block whore interaction while other modals are active or shop is open
                        print(f"💋 Whore interaction blocked - shop_open={gs.shop_open}, bag={bag_ui.is_open()}, party={party_manager.is_open()}, ledger={ledger.is_open()}, currency={currency_display.is_open()}, rest={rest_popup.is_open()}")
                        continue
                    
                    whore_number = st.get("whore_number", 0)
                    whore_sprite = st.get("whore_sprite", None)
                    print(f"💋 Attempting whore interaction - whore_number={whore_number}, whore_sprite={whore_sprite is not None}")
                    if whore_number and whore_sprite is not None:
                        st["whore_confirm_active"] = True
                        st["whore_confirm_price"] = _whore_price(whore_number)
                        st["whore_confirm_error"] = ""
                        st["whore_confirm_buttons"] = []
                        print(f"💰 Whore price set to {st['whore_confirm_price']} gold")
                    else:
                        print(f"⚠️ Whore number is invalid or sprite missing!")
                elif near_summoner:
                    # Trigger summoner battle (same logic as overworld)
                    summoner_name = st.get("summoner_name", None)
                    summoner_filename = st.get("summoner_filename", None)
                    summoner_sprite = st.get("summoner_sprite", None)
                    if summoner_name and summoner_filename and summoner_sprite:
                        # Stop tavern walking sound before battle
                        if hasattr(gs, "tavern_walking_channel") and gs.tavern_walking_channel:
                            try:
                                gs.tavern_walking_channel.stop()
                            except:
                                pass
                        if hasattr(gs, "tavern_is_walking"):
                            gs.tavern_is_walking = False
                            gs.tavern_walking_channel = None
                        
                        # Store current tavern position BEFORE battle (so we can restore it after)
                        st["tavern_player_pos"] = Vector2(gs.player_pos.x, gs.player_pos.y)
                        # Mark that we're returning from battle (so enter() knows to show kicked out textbox)
                        st["returning_from_battle"] = True
                        print(f"💾 Stored tavern position before battle: ({gs.player_pos.x:.1f}, {gs.player_pos.y:.1f})")
                        
                        # Set up encounter data (same as overworld)
                        gs.in_encounter = True
                        gs.encounter_timer = getattr(S, "ENCOUNTER_SHOW_TIME", 0.5)
                        gs.encounter_summoner_filename = summoner_filename
                        gs.encounter_name = summoner_name
                        gs.encounter_sprite = summoner_sprite
                        gs.encounter_stats = None
                        # Mark that we came from tavern (so battle returns to tavern)
                        gs._from_tavern = True
                        print(f"⚔️ Starting barfight with {summoner_name}!")
                        # Transition to summoner battle immediately
                        return "SUMMONER_BATTLE"
    
    return None

def update(gs, dt, **_):
    """Update tavern screen (player movement, camera)."""
    if not _TAVERN_MAP:
        return
    
    st = gs._tavern_state
    map_w = _TAVERN_MAP_WIDTH
    map_h = _TAVERN_MAP_HEIGHT
    map_anchor_x = _TAVERN_MAP_ANCHOR_X
    
    # Get player half size
    player_half = getattr(gs, "player_half", Vector2(S.PLAYER_SIZE[0] / 2, S.PLAYER_SIZE[1] / 2))
    
    # Block player movement if any modal textbox/popup is active
    blocking_modals = (
        st.get("show_gambler_intro", False) or 
        st.get("show_bet_selection", False) or 
        st.get("kicked_out_textbox_active", False) or 
        st.get("whore_confirm_active", False) or
        st.get("show_game_selection", False)
    )
    
    if not blocking_modals:
        # Update player position (horizontal and vertical movement allowed)
        update_player_tavern(gs, dt, player_half, map_w, map_h, map_anchor_x)
    else:
        # Player movement is blocked when textbox/popup is active
        pass
    
    # Check if player is near spawn (update proximity check)
    spawn_pos = st.get("spawn_pos", None)
    st["near_spawn"] = _is_near_spawn(gs, spawn_pos)
    
    # Check if player is near barkeeper (update proximity check)
    barkeeper_pos = st.get("barkeeper_pos", None)
    st["near_barkeeper"] = _is_near_barkeeper(gs, barkeeper_pos)
    
    # Check if player is near gambler (update proximity check)
    gambler_pos = st.get("gambler_pos", None)
    st["near_gambler"] = _is_near_gambler(gs, gambler_pos)
    
    # Check if player is near whore (update proximity check)
    whore_pos = st.get("whore_pos", None)
    st["near_whore"] = _is_near_whore(gs, whore_pos)
    
    # Check if player is near summoner (update proximity check)
    # Only check if summoner still exists (not kicked out)
    if st.get("summoner_sprite") is not None:
        summoner_pos = st.get("summoner_pos", None)
        st["near_summoner"] = _is_near_summoner(gs, summoner_pos)
    else:
        st["near_summoner"] = False
    
    # Update textbox blink timers if textboxes are active
    if st.get("kicked_out_textbox_active", False):
        st["kicked_out_blink_t"] = st.get("kicked_out_blink_t", 0.0) + dt
    if st.get("show_gambler_intro", False):
        st["gambler_intro_blink_t"] = st.get("gambler_intro_blink_t", 0.0) + dt
    
    # Camera is completely locked (map doesn't move)
    screen_w = getattr(S, "LOGICAL_WIDTH", S.WIDTH)
    screen_h = getattr(S, "LOGICAL_HEIGHT", S.HEIGHT)
    locked_cam_x = st.get("locked_cam_x", 0)  # Use locked X position
    locked_cam_y = st.get("locked_cam_y", 0)  # Use locked Y position
    cam = get_camera_offset_locked(gs.player_pos, screen_w, screen_h, player_half, map_w, map_h, map_anchor_x, locked_cam_x, locked_cam_y)
    st["camera"] = Vector2(cam.x, cam.y)

def draw(screen: pygame.Surface, gs, dt: float, **_):
    """Draw the tavern screen."""
    st = gs._tavern_state
    
    # Load tavern map if not already loaded
    tavern_map = _load_tavern_map()
    if not tavern_map:
        # Fallback: draw black screen
        screen.fill((0, 0, 0))
        # Draw error message
        try:
            font = pygame.font.SysFont("arial", 24)
            error_text = font.render("Tavern map not found", True, (255, 255, 255))
            text_rect = error_text.get_rect(center=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT // 2))
            screen.blit(error_text, text_rect)
        except:
            pass
        return
    
    # Get screen dimensions
    screen_w = getattr(S, "LOGICAL_WIDTH", S.WIDTH)
    screen_h = getattr(S, "LOGICAL_HEIGHT", S.HEIGHT)
    
    # Get map dimensions
    map_w = _TAVERN_MAP_WIDTH
    map_h = _TAVERN_MAP_HEIGHT
    map_anchor_x = _TAVERN_MAP_ANCHOR_X
    
    # Fill entire screen with black first (pure black, not grey)
    screen.fill((0, 0, 0))
    
    # Calculate map drawing parameters (centered, with cropping if needed)
    map_screen_x = (screen_w - map_w) // 2
    map_screen_y = (screen_h - map_h) // 2
    
    # Calculate source and destination rectangles for map drawing
    if map_w > screen_w:
        # Map wider than screen: show center portion
        map_src_x = (map_w - screen_w) // 2
        map_src_w = screen_w
        map_dst_x = 0
    else:
        # Map fits horizontally: show entire width
        map_src_x = 0
        map_src_w = map_w
        map_dst_x = map_screen_x
    
    if map_h > screen_h:
        # Map taller than screen: show center portion
        map_src_y = (map_h - screen_h) // 2
        map_src_h = screen_h
        map_dst_y = 0
    else:
        # Map fits vertically: show entire height
        map_src_y = 0
        map_src_h = map_h
        map_dst_y = map_screen_y
    
    # Draw the map (either full or cropped)
    if map_w <= screen_w and map_h <= screen_h:
        # Map fits entirely on screen, draw it centered
        screen.blit(tavern_map, (map_screen_x, map_screen_y))
    else:
        # Map is larger than screen, draw the cropped centered portion
        src_rect = pygame.Rect(map_src_x, map_src_y, map_src_w, map_src_h)
        dst_rect = pygame.Rect(map_dst_x, map_dst_y, map_src_w, map_src_h)
        screen.blit(tavern_map, dst_rect, src_rect)
    
    # Draw barkeeper NPC (behind the bar, before player so player appears on top)
    barkeeper_pos = st.get("barkeeper_pos", None)
    if barkeeper_pos and _BARKEEPER_SPRITE:
        # Convert barkeeper world position to screen coordinates
        barkeeper_world_x_relative = barkeeper_pos.x - map_anchor_x
        barkeeper_world_y_relative = barkeeper_pos.y
        
        # Convert to screen coordinates (accounting for map cropping)
        barkeeper_screen_x = int(map_dst_x + (barkeeper_world_x_relative - map_src_x) - _BARKEEPER_SPRITE.get_width() // 2)
        barkeeper_screen_y = int(map_dst_y + (barkeeper_world_y_relative - map_src_y) - _BARKEEPER_SPRITE.get_height() // 2)
        
        # Only draw barkeeper if visible on screen
        if (barkeeper_screen_x + _BARKEEPER_SPRITE.get_width() >= 0 and barkeeper_screen_x <= screen_w and
            barkeeper_screen_y + _BARKEEPER_SPRITE.get_height() >= 0 and barkeeper_screen_y <= screen_h):
            screen.blit(_BARKEEPER_SPRITE, (barkeeper_screen_x, barkeeper_screen_y))
    
    # Draw gambler NPC (top right corner, before player so player appears on top)
    gambler_pos = st.get("gambler_pos", None)
    if gambler_pos and _GAMBLER_SPRITE:
        # Convert gambler world position to screen coordinates
        gambler_world_x_relative = gambler_pos.x - map_anchor_x
        gambler_world_y_relative = gambler_pos.y
        
        # Convert to screen coordinates (accounting for map cropping)
        gambler_screen_x = int(map_dst_x + (gambler_world_x_relative - map_src_x) - _GAMBLER_SPRITE.get_width() // 2)
        gambler_screen_y = int(map_dst_y + (gambler_world_y_relative - map_src_y) - _GAMBLER_SPRITE.get_height() // 2)
        
        # Only draw gambler if visible on screen
        if (gambler_screen_x + _GAMBLER_SPRITE.get_width() >= 0 and gambler_screen_x <= screen_w and
            gambler_screen_y + _GAMBLER_SPRITE.get_height() >= 0 and gambler_screen_y <= screen_h):
            screen.blit(_GAMBLER_SPRITE, (gambler_screen_x, gambler_screen_y))
    
    # Draw whore NPC (bottom right corner, before player so player appears on top)
    whore_pos = st.get("whore_pos", None)
    whore_sprite = st.get("whore_sprite", None)
    if whore_pos and whore_sprite:
        # Convert whore world position to screen coordinates
        whore_world_x_relative = whore_pos.x - map_anchor_x
        whore_world_y_relative = whore_pos.y
        
        # Convert to screen coordinates (accounting for map cropping)
        whore_screen_x = int(map_dst_x + (whore_world_x_relative - map_src_x) - whore_sprite.get_width() // 2)
        whore_screen_y = int(map_dst_y + (whore_world_y_relative - map_src_y) - whore_sprite.get_height() // 2)
        
        # Only draw whore if visible on screen
        if (whore_screen_x + whore_sprite.get_width() >= 0 and whore_screen_x <= screen_w and
            whore_screen_y + whore_sprite.get_height() >= 0 and whore_screen_y <= screen_h):
            screen.blit(whore_sprite, (whore_screen_x, whore_screen_y))
    
    # Draw summoner NPC (center-left area, before player so player appears on top)
    summoner_pos = st.get("summoner_pos", None)
    summoner_sprite = st.get("summoner_sprite", None)
    if summoner_pos and summoner_sprite:
        # Convert summoner world position to screen coordinates
        summoner_world_x_relative = summoner_pos.x - map_anchor_x
        summoner_world_y_relative = summoner_pos.y
        
        # Convert to screen coordinates (accounting for map cropping)
        summoner_screen_x = int(map_dst_x + (summoner_world_x_relative - map_src_x) - summoner_sprite.get_width() // 2)
        summoner_screen_y = int(map_dst_y + (summoner_world_y_relative - map_src_y) - summoner_sprite.get_height() // 2)
        
        # Only draw summoner if visible on screen
        if (summoner_screen_x + summoner_sprite.get_width() >= 0 and summoner_screen_x <= screen_w and
            summoner_screen_y + summoner_sprite.get_height() >= 0 and summoner_screen_y <= screen_h):
            screen.blit(summoner_sprite, (summoner_screen_x, summoner_screen_y))
    
    # Draw player (player moves in world coordinates, but map is locked)
    # Convert player world position to screen position, accounting for map centering/cropping
    player_half = getattr(gs, "player_half", Vector2(S.PLAYER_SIZE[0] / 2, S.PLAYER_SIZE[1] / 2))
    
    # Calculate player position relative to map anchor
    player_world_x_relative = gs.player_pos.x - map_anchor_x
    player_world_y_relative = gs.player_pos.y
    
    # Convert to screen coordinates (accounting for map cropping)
    player_screen_x = int(map_dst_x + (player_world_x_relative - map_src_x) - player_half.x)
    player_screen_y = int(map_dst_y + (player_world_y_relative - map_src_y) - player_half.y)
    
    # Only draw player if they're visible on screen
    if (player_screen_x + player_half.x * 2 >= 0 and player_screen_x <= screen_w and
        player_screen_y + player_half.y * 2 >= 0 and player_screen_y <= screen_h):
        if hasattr(gs, "player_image") and gs.player_image:
            screen.blit(gs.player_image, (player_screen_x, player_screen_y))
        else:
            # Fallback: draw a rectangle
            pw, ph = S.PLAYER_SIZE
            pygame.draw.rect(screen, (230, 215, 180), 
                           (player_screen_x, player_screen_y, pw, ph), 
                           border_radius=6)
            pygame.draw.rect(screen, (40, 30, 18), 
                           (player_screen_x, player_screen_y, pw, ph), 
                           2, border_radius=6)
    
    # Draw exit popup when near spawn position
    spawn_pos = st.get("spawn_pos", None)
    near_spawn = st.get("near_spawn", False)
    
    if spawn_pos and near_spawn:
        _draw_exit_popup(screen, gs, spawn_pos, map_anchor_x, map_src_x, map_src_y, map_dst_x, map_dst_y, player_half, screen_w, screen_h, map_w, map_h)
    
    # Draw barkeeper popup when near barkeeper (but not when near spawn to avoid overlap)
    barkeeper_pos = st.get("barkeeper_pos", None)
    near_barkeeper = st.get("near_barkeeper", False)
    
    if barkeeper_pos and near_barkeeper and not near_spawn:
        _draw_barkeeper_popup(screen, gs, barkeeper_pos, map_anchor_x, map_src_x, map_src_y, map_dst_x, map_dst_y, player_half, screen_w, screen_h, map_w, map_h)
    
    # Draw gambler popup when near gambler (but not when near spawn or barkeeper to avoid overlap)
    # Also don't show gambler popup when intro textbox or bet selection is active
    gambler_pos = st.get("gambler_pos", None)
    near_gambler = st.get("near_gambler", False)
    show_gambler_popup = (not st.get("show_gambler_intro", False) and 
                          not st.get("show_bet_selection", False))
    
    if gambler_pos and near_gambler and not near_spawn and not near_barkeeper and show_gambler_popup:
        _draw_gambler_popup(screen, gs, gambler_pos, map_anchor_x, map_src_x, map_src_y, map_dst_x, map_dst_y, player_half, screen_w, screen_h, map_w, map_h)
    
    # Draw whore popup when near whore (but not when near spawn, barkeeper, or gambler to avoid overlap)
    whore_pos = st.get("whore_pos", None)
    near_whore = st.get("near_whore", False)
    whore_number = st.get("whore_number", None)
    
    if (whore_pos and near_whore and whore_number and not near_spawn and not near_barkeeper
            and not near_gambler and not st.get("whore_confirm_active", False)):
        _draw_whore_popup(screen, gs, whore_pos, whore_number, map_anchor_x, map_src_x, map_src_y, map_dst_x, map_dst_y, player_half, screen_w, screen_h, map_w, map_h)
    
    # Draw summoner popup when near summoner (but not when near other NPCs to avoid overlap)
    summoner_pos = st.get("summoner_pos", None)
    near_summoner = st.get("near_summoner", False)
    
    if summoner_pos and near_summoner and not near_spawn and not near_barkeeper and not near_gambler and not near_whore:
        _draw_summoner_popup(screen, gs, summoner_pos, map_anchor_x, map_src_x, map_src_y, map_dst_x, map_dst_y, player_half, screen_w, screen_h, map_w, map_h)
    
    # NOTE: Textboxes (gambler intro, bet selection, kicked out) are now drawn in main.py
    # after the HUD elements so they appear on top of the HUD
    
