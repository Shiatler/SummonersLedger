# ============================================================
#  systems/party_ui.py — portrait + name + 2-row party layout (HUD)
# ============================================================

import os
import pygame
import settings as S
from screens import ledger
from systems.asset_links import vessel_to_token, find_image
from systems import coords

# ---------- Layout ----------
PADDING         = 16
PORTRAIT_SIZE   = (140, 140)  # Reduced from 180x180 for less intrusive UI
SLOTS_COUNT     = 6
EMPTY_FILL      = (255, 255, 255, 26)

# ---------- Name text ----------
NAME_MAX_LEN    = 12
NAME_COLOR      = (0, 0, 0)
NAME_SHADOW     = (255, 255, 255)
NAME_MIN_SIZE   = 10
NAME_MAX_SIZE   = 20
NAME_BOTTOM_PAD = 8
NAME_SIDE_PAD   = 10

# ---------- Caches ----------
_FONT_CACHE: dict[tuple[str, int], pygame.font.Font] = {}
_TOKEN_CACHE: dict[tuple[int, int, int], pygame.Surface] = {}   # (id(surf), slot_size, pad) -> normalized surface

# Hover glow cache for slots (like other buttons)
_SLOT_GLOW_CACHE: dict[tuple[int, int, int, int], pygame.Surface] = {}  # (w,h,alpha,radius) -> surf

# ---------- Click hitboxes ----------
_slot_rects: list[pygame.Rect] = []    # populated per draw; 6 rects (2x3 grid)

def _get_hover_glow_slot(size: tuple[int, int], alpha: int = 60, radius: int = 8) -> pygame.Surface:
    """
    Rounded-rect soft glow for slot hover; cached to avoid per-frame allocs.
    Creates a filled white rectangle with transparency for hover effect.
    """
    key = (size[0], size[1], alpha, radius)
    cached = _SLOT_GLOW_CACHE.get(key)
    if cached is not None:
        return cached
    surf = pygame.Surface(size, pygame.SRCALPHA)
    # Fill with white and alpha for glow effect (same approach as hud_buttons)
    surf.fill((255, 255, 255, alpha))
    _SLOT_GLOW_CACHE[key] = surf
    return surf

# ----------------- Fonts -----------------
def _get_font(size: int) -> pygame.font.Font:
    key = ("dnd", size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    try:
        path = os.path.join(S.ASSETS_FONTS_DIR, getattr(S, "DND_FONT_FILE", "DH.otf"))
        font = pygame.font.Font(path, size)
    except Exception:
        font = pygame.font.SysFont("georgia", size, bold=True)
    _FONT_CACHE[key] = font
    return font

# ---------- Sizing helpers ----------
def _compute_slot_metrics(portrait_h: int) -> tuple[int, int, int]:
    desired = int(S.LOGICAL_HEIGHT * 0.14)
    slot_gap = max(6, int(S.LOGICAL_HEIGHT * 0.010))
    slot_size = int(desired * 0.6)
    inner_margin = max(2, int(slot_size * 0.03))
    return slot_size, slot_gap, inner_margin

# ---------- Token normalization ----------
def _trim_alpha(surf: pygame.Surface) -> pygame.Surface:
    if surf.get_masks()[3] == 0:
        return surf
    import numpy as np
    alpha = pygame.surfarray.pixels_alpha(surf)
    nz = np.argwhere(alpha > 0)
    if nz.size == 0:
        del alpha
        return surf
    (y0, x0), (y1, x1) = nz.min(0), nz.max(0)
    del alpha
    rect = pygame.Rect(int(x0), int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1))
    return surf.subsurface(rect).copy()

def _normalize_token_for_slot(token: pygame.Surface, slot_size: int, pad: int) -> pygame.Surface | None:
    if token is None or not isinstance(token, pygame.Surface):
        return None
    key = (id(token), slot_size, pad)
    if key in _TOKEN_CACHE:
        return _TOKEN_CACHE[key]
    trimmed = _trim_alpha(token)
    inner = max(1, slot_size - pad * 2)
    tw, th = trimmed.get_width(), trimmed.get_height()
    scale = inner / max(tw, th)
    nw, nh = max(1, int(tw * scale)), max(1, int(th * scale))
    scaled = pygame.transform.smoothscale(trimmed, (nw, nh))
    canvas = pygame.Surface((inner, inner), pygame.SRCALPHA)
    canvas.blit(scaled, scaled.get_rect(center=canvas.get_rect().center))
    _TOKEN_CACHE[key] = canvas
    return canvas

# ---------- Token cache (keyed by token name + size) ----------
_TOKEN_SURFACE_CACHE: dict[tuple[str, int, int], pygame.Surface] = {}

# ---------- Lazy load party token by name ----------
def _load_party_token_surface(name: str | None, size: tuple[int, int]) -> pygame.Surface | None:
    """
    Load a token surface from a filename.
    The name should already be a token filename (e.g., "FTokenBarbarian1.png").
    If it's a vessel name, it will be converted to a token name.
    Uses a cache keyed by (name, width, height) to avoid reloading the same token.
    """
    if not name:
        return None
    
    # Normalize the name to use as cache key
    name_normalized = str(name).strip()
    if not name_normalized:
        return None
    
    # Check cache first (keyed by name + size)
    cache_key = (name_normalized, size[0], size[1])
    if cache_key in _TOKEN_SURFACE_CACHE:
        cached = _TOKEN_SURFACE_CACHE[cache_key]
        if cached is not None:
            return cached
    
    # Not in cache - need to load
    # party_slots_names should contain token filenames, but handle both cases
    # Check if it's already a token name (contains "Token") or convert if it's a vessel name
    base = os.path.splitext(os.path.basename(name_normalized))[0]
    if "Token" in base:
        # Already a token name, use as-is
        token_basename = name_normalized if name_normalized.lower().endswith(".png") else f"{name_normalized}.png"
    else:
        # Might be a vessel name, convert it
        token_basename = vessel_to_token(name_normalized)
        if not token_basename:
            _TOKEN_SURFACE_CACHE[cache_key] = None  # Cache None to avoid retrying
            return None
    
    # Find the token image file
    path = find_image(token_basename)
    if not path:
        _TOKEN_SURFACE_CACHE[cache_key] = None  # Cache None to avoid retrying
        return None
    
    try:
        surf = pygame.image.load(path).convert_alpha()
        scaled = pygame.transform.smoothscale(surf, size)
        _TOKEN_SURFACE_CACHE[cache_key] = scaled  # Cache the scaled surface
        return scaled
    except Exception:
        _TOKEN_SURFACE_CACHE[cache_key] = None  # Cache None to avoid retrying
        return None

# ===================== Player Portrait Token =================
def load_player_token(gender: str) -> pygame.Surface | None:
    base = os.path.join("Assets", "PlayableCharacters")
    fname = "MToken.png" if str(gender).lower().startswith("m") else "FToken.png"
    path = os.path.join(base, fname)
    if not os.path.exists(path):
        for alt in ("MToken.png", "FToken.png", "Token.png"):
            p2 = os.path.join(base, alt)
            if os.path.exists(p2):
                path = p2
                break
        else:
            return None
    try:
        surf = pygame.image.load(path).convert_alpha()
        return pygame.transform.smoothscale(surf, PORTRAIT_SIZE)
    except Exception as e:
        print(f"⚠️ Failed to load player token '{path}': {e}")
        return None

# ===================== Name Fit Helper =======================
def _render_name_fitted(text: str, max_w: int, max_size: int, min_size: int) -> pygame.Surface:
    s = max_size
    while s >= min_size:
        f = _get_font(s)
        r = f.render(text, True, NAME_COLOR)
        if r.get_width() <= max_w:
            return r
        s -= 1
    return _get_font(min_size).render(text, True, NAME_COLOR)

# ===================== Event handling ========================
def handle_event(e, gs) -> bool:
    if ledger.is_open():
        return ledger.handle_event(e, gs)
    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
        mx, my = e.pos
        for idx, rect in enumerate(_slot_rects):
            if rect.collidepoint(mx, my):
                has_token = (
                    getattr(gs, "party_slots", None)
                    and idx < len(gs.party_slots)
                    and isinstance(gs.party_slots[idx], pygame.Surface)
                )
                has_name = (
                    getattr(gs, "party_slots_names", None)
                    and idx < len(gs.party_slots_names)
                    and gs.party_slots_names[idx]
                )
                if has_token or has_name:
                    ledger.open(gs, idx)
                    return True
                break
    return False

# ===================== HUD Drawing ===========================
def draw_party_hud(screen: pygame.Surface, gs):
    global _slot_rects

    if not hasattr(gs, "party_slots") or gs.party_slots is None:
        gs.party_slots = [None] * SLOTS_COUNT
    if not hasattr(gs, "party_slots_names") or gs.party_slots_names is None:
        gs.party_slots_names = [None] * SLOTS_COUNT
    if not hasattr(gs, "player_token"):
        gs.player_token = None

    _slot_rects = []

    portrait_w, portrait_h = PORTRAIT_SIZE
    slot_size, slot_gap, inner_margin = _compute_slot_metrics(portrait_h)

    # Try to get HUD position from left_hud to center portrait within it
    try:
        from systems import left_hud
        hud_rect = left_hud.get_hud_rect()
        if hud_rect:
            # Position portrait relative to HUD rect, accounting for HUD padding
            # Portrait x: HUD left edge + HUD padding
            px = hud_rect.x + left_hud.HUD_PADDING
            # Portrait y: centered vertically within the HUD
            py = hud_rect.y + (hud_rect.height - portrait_h) // 2
        else:
            # Fallback: use original positioning
            px = PADDING
            py = S.LOGICAL_HEIGHT - portrait_h - PADDING
    except:
        # Fallback: use original positioning
        px = PADDING
        py = S.LOGICAL_HEIGHT - portrait_h - PADDING

    # --- Portrait ---
    if gs.player_token:
        screen.blit(gs.player_token, (px, py))
    # Empty portrait is transparent - no placeholder drawn

    # --- Name inside portrait ---
    raw_name = (getattr(gs, "player_name", "") or "")[:NAME_MAX_LEN]
    if raw_name:
        max_text_w = portrait_w - 2 * NAME_SIDE_PAD
        name_surf = _render_name_fitted(raw_name, max_text_w, NAME_MAX_SIZE, NAME_MIN_SIZE)
        name_rect = name_surf.get_rect()
        name_rect.midbottom = (px + portrait_w // 2, py + portrait_h - NAME_BOTTOM_PAD)

        NAME_BOX_BG      = (255, 255, 255, 180)
        NAME_BOX_BORDER  = (0, 0, 0, 100)
        NAME_BOX_PAD_X   = 8
        NAME_BOX_PAD_Y   = 2
        NAME_BOX_RADIUS  = 6

        box_w = name_rect.w + NAME_BOX_PAD_X * 2
        box_h = name_rect.h + NAME_BOX_PAD_Y * 2
        box_rect = pygame.Rect(0, 0, box_w, box_h)
        box_rect.center = name_rect.center

        box_surf = pygame.Surface((box_rect.w, box_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(box_surf, NAME_BOX_BG, box_surf.get_rect(), border_radius=NAME_BOX_RADIUS)
        pygame.draw.rect(box_surf, NAME_BOX_BORDER, box_surf.get_rect(), width=1, border_radius=NAME_BOX_RADIUS)
        screen.blit(box_surf, box_rect.topleft)

        shadow = _get_font(name_surf.get_height()).render(raw_name, True, NAME_SHADOW)
        shadow_rect = shadow.get_rect(center=name_rect.center)
        shadow_rect.x += 1
        shadow_rect.y += 1
        screen.blit(shadow, shadow_rect)
        screen.blit(name_surf, name_rect)

    # --- Slots in 2 rows x 3 columns ---
    cols, rows = 3, 2
    grid_left = px + portrait_w + 12  # Reduced gap for less intrusive UI
    total_grid_h = rows * slot_size + (rows - 1) * slot_gap
    grid_top = py + (portrait_h - total_grid_h) // 2

    # Convert mouse position from screen coordinates to logical coordinates
    screen_mx, screen_my = pygame.mouse.get_pos()
    mx, my = coords.screen_to_logical((screen_mx, screen_my))

    # FOOLPROOF: party_slots_names is the SINGLE source of truth from party_manager.py
    # Read party_slots_names directly from gs every frame - no caching, no assumptions
    # This ensures we always reflect the current state that party_manager.py is managing
    
    # Get party_slots_names directly from gs - this is what party_manager.py reads/writes
    party_slots_names_raw = getattr(gs, "party_slots_names", None)
    
    # Normalize to exactly 6 slots - create a clean list we can rely on
    if not isinstance(party_slots_names_raw, list):
        party_slots_names = [None] * SLOTS_COUNT
    else:
        # Create a new list with exactly 6 slots
        party_slots_names = [None] * SLOTS_COUNT
        for idx in range(min(SLOTS_COUNT, len(party_slots_names_raw))):
            party_slots_names[idx] = party_slots_names_raw[idx]
    
    # Initialize party_slots if it doesn't exist (will be rebuilt below)
    if not hasattr(gs, "party_slots") or not isinstance(gs.party_slots, list):
        gs.party_slots = [None] * SLOTS_COUNT
    
    # Ensure party_slots has exactly 6 slots
    if len(gs.party_slots) != SLOTS_COUNT:
        gs.party_slots = [None] * SLOTS_COUNT
    
    # FOOLPROOF REBUILD: For each slot index 0-5, load token from party_slots_names[slot_index]
    # This is a direct 1:1 mapping - slot[i] always shows the token for party_slots_names[i]
    # We rebuild every frame to ensure we always match party_manager.py's view
    for slot_index in range(SLOTS_COUNT):
        # Get token name for this slot from normalized party_slots_names
        token_name = party_slots_names[slot_index]
        
        # Load token surface for this name (or None if no name)
        if token_name:
            # Load the token - cache will handle performance, but we always check the name
            token_surface = _load_party_token_surface(token_name, (slot_size, slot_size))
            gs.party_slots[slot_index] = token_surface
        else:
            # Empty slot
            gs.party_slots[slot_index] = None
    
    # name_list for drawing loop - use the normalized list we just created
    name_list = party_slots_names

    # Now draw the slots using the rebuilt party_slots
    # CRITICAL: Use the same party_slots_names we used to rebuild (name_list) to ensure consistency
    for i in range(SLOTS_COUNT):
        row = i // cols
        col = i % cols
        r = pygame.Rect(
            grid_left + col * (slot_size + slot_gap),
            grid_top  + row * (slot_size + slot_gap),
            slot_size, slot_size
        )

        _slot_rects.append(r)

        # Get token name from party_slots_names (source of truth) and token from rebuilt party_slots
        # Use name_list which is a copy of party_slots_names from the rebuild above
        token_name = name_list[i] if i < len(name_list) else None
        # Get token from the rebuilt party_slots (which was built from party_slots_names above)
        token = gs.party_slots[i] if i < len(gs.party_slots) else None
        
        # Validation: Ensure token matches the name for this slot
        # If there's a mismatch, reload the token (shouldn't happen, but safety check)
        if token_name and (token is None or not isinstance(token, pygame.Surface)):
            # Token is missing - reload it (this shouldn't happen since we just rebuilt, but safety check)
            token = _load_party_token_surface(token_name, (slot_size, slot_size))
            if token:
                gs.party_slots[i] = token
        
        # Ensure stats ONLY if missing for this slot
        stats_list = getattr(gs, "party_vessel_stats", None)

        need_ensure = False
        if token_name:
            if not stats_list or i >= len(stats_list) or not isinstance(stats_list[i], dict):
                need_ensure = True
            else:
                cur = stats_list[i]
                # If current_hp exists, never rebuild here (preserve damage/faint)
                if "current_hp" not in cur:
                    need_ensure = True

        if need_ensure:
            try:
                from screens.ledger import _ensure_stats_for_slot as _ensure
                _ensure(gs, i)
            except Exception as ex:
                print(f"⚠️ stats ensure failed for slot {i}: {ex}")

        # Hover state only if slot is filled (like other buttons)
        has_content = bool(token) or bool(token_name)
        is_hovered = has_content and r.collidepoint(mx, my)

        # Draw slot background using medieval style
        from systems import hud_style
        hud_style.draw_slot_panel(screen, r, hovered=is_hovered, filled=bool(token))
        
        # Draw token if present
        if token and isinstance(token, pygame.Surface):
            inner = _normalize_token_for_slot(token, slot_size, inner_margin)
            if inner:
                screen.blit(inner, inner.get_rect(center=r.center))

    # Ledger modal overlay
    if ledger.is_open():
        ledger.draw(screen, gs)
