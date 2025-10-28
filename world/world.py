# ============================================================
#  world/world.py
# ============================================================
import os
import pygame
from pygame.math import Vector2
import settings as S
from screens import party_manager
from screens import death as death_screen

# ====================================================
# ================ PLAYER & CAMERA ===================
# ====================================================

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def update_player(gs, dt, player_half):
    """Simple vertical walking movement logic (disabled when Party Manager is open)."""
    if party_manager.is_open():
        return  # freeze movement while modal is open

    keys = pygame.key.get_pressed()
    moving = False
    speed = getattr(gs, "player_speed", 180)

    if keys[pygame.K_w] or keys[pygame.K_UP]:
        gs.player_pos.y -= speed * dt
        moving = True
    if keys[pygame.K_s] or keys[pygame.K_DOWN]:
        gs.player_pos.y += speed * dt
        moving = True

    # Clamp to world bounds
    gs.player_pos.x = clamp(gs.player_pos.x, player_half.x, S.WORLD_W - player_half.x)
    gs.player_pos.y = clamp(gs.player_pos.y, player_half.y, S.WORLD_H - player_half.y)

    if moving:
        gs.distance_travelled = getattr(gs, "distance_travelled", 0.0) + speed * dt


def get_camera_offset(target_pos: Vector2, screen_w: int, screen_h: int, player_half: Vector2) -> Vector2:
    """Keep the player near bottom of the screen."""
    bottom_margin = 40  # pixels from bottom edge
    desired_screen_y = screen_h - (player_half.y + bottom_margin)
    desired_x = target_pos.x - screen_w / 2
    desired_y = target_pos.y - desired_screen_y
    cam_x = clamp(desired_x, 0, max(0, S.WORLD_W - screen_w))
    cam_y = clamp(desired_y, 0, max(0, S.WORLD_H - screen_h))
    return Vector2(cam_x, cam_y)


def draw_grid_background(surface: pygame.Surface, cam_x: float, cam_y: float):
    """Simple debug background (fallback if road is missing)."""
    surface.fill(S.BG_COLOR)
    w, h = surface.get_size()
    x = - (int(cam_x) % S.TILE)
    while x < w:
        pygame.draw.line(surface, S.GRID_COLOR, (x, 0), (x, h))
        x += S.TILE
    y = - (int(cam_y) % S.TILE)
    while y < h:
        pygame.draw.line(surface, S.GRID_COLOR, (0, y), (w, y))
        y += S.TILE


# ====================================================
# ===================== ROAD =========================
# ====================================================

ROAD_IMG        = None
ROAD_W_NATIVE   = 0
ROAD_H_NATIVE   = 0
ROAD_ANCHOR_X   = 0  # x position in world where we draw the road (centered by default)


def load_road():
    """
    Load Assets/Map/road.png once at **native size**.
    - No scaling is performed.
    - We compute ROAD_ANCHOR_X to center the road image within WORLD_W.
    """
    global ROAD_IMG, ROAD_W_NATIVE, ROAD_H_NATIVE, ROAD_ANCHOR_X
    path = os.path.join(S.ASSETS_MAP_DIR, "road.png")
    if not os.path.exists(path):
        print(f"⚠️ road.png not found at {path}")
        ROAD_IMG = None
        return

    try:
        img = pygame.image.load(path).convert_alpha()
    except Exception as e:
        print(f"⚠️ Failed to load road.png at {path}: {e}")
        ROAD_IMG = None
        return

    ROAD_IMG = img  # keep native size
    ROAD_W_NATIVE = ROAD_IMG.get_width()
    ROAD_H_NATIVE = ROAD_IMG.get_height()

    # Center the road image in the world width by default
    ROAD_ANCHOR_X = max(0, (S.WORLD_W - ROAD_W_NATIVE) // 2)

    print(f"✅ Loaded road (native {ROAD_W_NATIVE}x{ROAD_H_NATIVE}), anchor_x={ROAD_ANCHOR_X}")


def draw_repeating_road(surface: pygame.Surface, cam_x_or_y: float, maybe_cam_y: float = None, repeat_x: bool = False):
    """
    Draw the road at **native size** (no scaling).
    Vertical tiling (infinite); optional horizontal tiling via repeat_x=True.
    """
    if ROAD_IMG is None:
        # Fallback grid if asset missing
        if maybe_cam_y is None:
            draw_grid_background(surface, 0, cam_x_or_y)
        else:
            draw_grid_background(surface, cam_x_or_y, maybe_cam_y)
        return

    # Back-compat argument handling
    if maybe_cam_y is None:
        cam_x = 0
        cam_y = cam_x_or_y
    else:
        cam_x = cam_x_or_y
        cam_y = maybe_cam_y

    screen_w, screen_h = surface.get_size()
    img_w, img_h = ROAD_W_NATIVE, ROAD_H_NATIVE

    # Determine horizontal draw columns
    column_xs = [ROAD_ANCHOR_X]
    if repeat_x:
        left = ROAD_ANCHOR_X - img_w
        right = ROAD_ANCHOR_X + img_w
        while left >= 0:
            column_xs.append(left)
            left -= img_w
        while right < S.WORLD_W:
            column_xs.append(right)
            right += img_w

    # Compute visible vertical range
    y_off = int(cam_y) % img_h
    y_screen = 0
    remaining = screen_h

    while remaining > 0:
        h = min(img_h - y_off, remaining)
        src_rect = pygame.Rect(0, y_off, img_w, h)

        for col_x in column_xs:
            dest_x_world = col_x
            dest_x_screen = int(dest_x_world - cam_x)

            if dest_x_screen >= screen_w or (dest_x_screen + img_w) <= 0:
                continue

            crop_left = max(0, -dest_x_screen)
            crop_right = max(0, (dest_x_screen + img_w) - screen_w)
            src_x = crop_left
            draw_w = img_w - crop_left - crop_right

            if draw_w > 0:
                src = pygame.Rect(src_x, src_rect.y, draw_w, src_rect.h)
                dst = pygame.Rect(dest_x_screen + src_x, y_screen, draw_w, src_rect.h)
                surface.blit(ROAD_IMG, dst, src)

        y_screen += h
        remaining -= h
        y_off = 0


# ====================================================
# ================= WORLD LIFECYCLE ==================
# ====================================================

def enter(gs, **_):
    """Initialize overworld state."""
    # If party has no living vessels, jump to death screen immediately.
    stats = getattr(gs, "party_vessel_stats", None) or []
    has_living = any(
        isinstance(st, dict) and int(st.get("current_hp", st.get("hp", 0)) or 0) > 0
        for st in stats
    )
    if not has_living:
        death_screen.enter(gs)
        return

    if ROAD_IMG is None:
        load_road()

    # default player state
    if not hasattr(gs, "player_pos"):
        gs.player_pos = Vector2(S.WORLD_W / 2, S.WORLD_H / 2)
    if not hasattr(gs, "player_speed"):
        gs.player_speed = 180
    if not hasattr(gs, "distance_travelled"):
        gs.distance_travelled = 0.0

    # camera cache
    gs._cam = Vector2(0, 0)


def handle(events, gs, **_):
    """
    Overworld input. The Party Manager is modal:
    - If open, it eats inputs first (Esc/Tab closes, clicks/keys swap/set active).
    - If closed, Tab toggles it.
    """
    # If the Party Manager is open, let it consume and block world input.
    if party_manager.is_open():
        for e in events:
            party_manager.handle_event(e, gs)
        return None

    # Normal world input
    for e in events:
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_TAB:
                party_manager.toggle()
                return None
        # ... add other world-level inputs here (interact, pause, etc.) ...

    return None


def update(gs, dt, **_):
    """Advance player & camera (frozen when Party Manager is open)."""

    # If party wipes outside of battle, go to death screen immediately.
    stats = getattr(gs, "party_vessel_stats", None) or []
    if not any(
        isinstance(st, dict) and int(st.get("current_hp", st.get("hp", 0)) or 0) > 0
        for st in stats
    ):
        death_screen.enter(gs)
        return

    player_half = Vector2(S.PLAYER_SIZE[0] / 2, S.PLAYER_SIZE[1] / 2)
    update_player(gs, dt, player_half)

    # camera follows even while manager is open (player is frozen anyway)
    cam = get_camera_offset(gs.player_pos, S.WIDTH, S.HEIGHT, player_half)
    gs._cam.update(cam.x, cam.y)


def draw(screen: pygame.Surface, gs, dt, **_):
    """Draw world and overlays."""
    cam_x, cam_y = getattr(gs, "_cam", Vector2(0, 0))

    # background / road
    draw_repeating_road(screen, cam_x, cam_y, repeat_x=True)

    # --- draw player (placeholder rectangle; replace with your sprite draw) ---
    px = int(gs.player_pos.x - cam_x)
    py = int(gs.player_pos.y - cam_y)
    pw, ph = S.PLAYER_SIZE
    pygame.draw.rect(screen, (230, 215, 180), (px - pw//2, py - ph//2, pw, ph), border_radius=6)
    pygame.draw.rect(screen, (40, 30, 18), (px - pw//2, py - ph//2, pw, ph), 2, border_radius=6)

    # HUD (optional simple debug)
    dbg = pygame.font.SysFont("consolas", 16).render(f"Pos {int(gs.player_pos.x)},{int(gs.player_pos.y)}", True, (240, 230, 210))
    screen.blit(dbg, (8, 8))

    # --- overlay: Party Manager (drawn last; modal) ---
    party_manager.draw(screen, gs)
