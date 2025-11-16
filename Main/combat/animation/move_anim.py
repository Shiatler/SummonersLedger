from __future__ import annotations
import os
import math
import pygame
from .helpers import class_and_level_from_move_id, anim_image_path

# Animation state is stored on gs as _move_anim = {...}
# {
#   'active': bool,
#   'start_ms': int (pygame.time.get_ticks() at start),
#   'duration_ms': int,
#   'surface': pygame.Surface,
#   'angle_deg': float,             # default rotation angle for melee
#   'target_side': 'enemy'|'ally',  # which rect to aim at
#   'move_id': str,
#   'anim_type': 'melee'|'projectile',
# }

DEFAULT_DURATION_MS = 500
DEFAULT_ANGLE_DEG = -90.0  # rotate sprite -90deg so the blade points downward

_MELEE_CLASSES = {"Paladin", "Fighter", "Barbarian", "Monk", "Rogue", "Bloodhunter"}

def _ensure_anim_blob(gs):
    if not hasattr(gs, "_move_anim") or not isinstance(getattr(gs, "_move_anim"), dict):
        gs._move_anim = {'active': False}
    return gs._move_anim

def start_move_anim(gs, move) -> None:
    """
    Begin a move animation based on move.id (class+level) and target_side.
    The caller should set gs._move_anim['target_side'] before calling this
    (e.g., 'enemy' for player attack, 'ally' for enemy attack).
    """
    st = _ensure_anim_blob(gs)
    move_id = getattr(move, "id", None) or ""
    cls, lvl = class_and_level_from_move_id(str(move_id))
    p = anim_image_path(cls, lvl)

    # Determine animation type by class: melee vs projectile
    anim_type = "projectile"
    if cls in _MELEE_CLASSES:
        anim_type = "melee"

    surf = None
    if p and os.path.exists(p):
        try:
            raw = pygame.image.load(p).convert_alpha()
            if anim_type == "melee":
                # rotate for downward swing look
                surf = pygame.transform.rotate(raw, DEFAULT_ANGLE_DEG)
            else:
                # leave projectile unrotated; will rotate per-frame to direction
                surf = raw
        except Exception:
            surf = None
    st.update({
        'active': bool(surf is not None),
        'start_ms': pygame.time.get_ticks(),
        'duration_ms': DEFAULT_DURATION_MS,
        'surface': surf,
        'angle_deg': DEFAULT_ANGLE_DEG,
        'move_id': move_id,
        'anim_type': anim_type,
        # 'target_side' is expected to be preset by caller before this call
    })
    gs._move_anim = st

def cancel(gs):
    st = _ensure_anim_blob(gs)
    st['active'] = False
    st['surface'] = None

def _ease_in_cubic(p: float) -> float:
    return p * p * p

def update_and_draw(screen: pygame.Surface, gs, ally_rect: pygame.Rect | None, enemy_rect: pygame.Rect | None, dt: float) -> bool:
    """
    If an animation is active, update its position and draw it.
    Melee: drops from above onto target center.
    Projectile: travels from attacker center to target center, rotating along direction.
    Returns True while animating, False when finished.
    """
    st = _ensure_anim_blob(gs)
    if not st.get('active') or st.get('surface') is None:
        return False

    target_side = st.get('target_side', 'enemy')
    target_rect = enemy_rect if target_side == 'enemy' else ally_rect
    source_rect = ally_rect if target_side == 'enemy' else enemy_rect  # attacker is the opposite
    if not target_rect:
        cancel(gs)
        return False

    now = pygame.time.get_ticks()
    t0 = st.get('start_ms', now)
    dur = max(1, int(st.get('duration_ms', DEFAULT_DURATION_MS)))
    elapsed = max(0, min(dur, now - t0))
    p = elapsed / float(dur)  # 0..1

    sprite = st['surface']
    if sprite is None:
        cancel(gs); return False

    anim_type = st.get('anim_type', 'melee')

    if anim_type == "melee":
        # simple downward slash: start above target, move to center
        cx, cy = target_rect.centerx, target_rect.centery
        start_y = cy - int(target_rect.height * 1.2)
        x = cx
        y = int(start_y + (cy - start_y) * _ease_in_cubic(p))

        sw, sh = sprite.get_size()
        base = max(1, max(target_rect.width, target_rect.height))
        scale = max(0.5, min(1.2, base / max(sw, sh)))
        spr = pygame.transform.smoothscale(sprite, (max(1, int(sw * scale)), max(1, int(sh * scale))))
        screen.blit(spr, spr.get_rect(center=(x, y)))
    else:
        # projectile: start at attacker center, travel to target center
        if not source_rect:
            cancel(gs); return False
        sx, sy = source_rect.centerx, source_rect.centery
        tx, ty = target_rect.centerx, target_rect.centery
        x = int(sx + (tx - sx) * p)
        y = int(sy + (ty - sy) * p)

        # rotate to face direction
        dx = tx - sx
        dy = ty - sy
        angle_deg = -math.degrees(math.atan2(dy, dx))  # pygame rotates counter-clockwise; negative to align

        sw, sh = sprite.get_size()
        # scale projectile relative to distance or target size (keep modest)
        dist = max(1.0, math.hypot(dx, dy))
        scale = max(0.6, min(1.0, dist / max(sw, sh) * 0.5))
        scaled = pygame.transform.smoothscale(sprite, (max(1, int(sw * scale)), max(1, int(sh * scale))))
        rotated = pygame.transform.rotate(scaled, angle_deg)
        screen.blit(rotated, rotated.get_rect(center=(x, y)))

    if elapsed >= dur:
        cancel(gs)
        return False
    return True


