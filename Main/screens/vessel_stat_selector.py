# ============================================================
# screens/vessel_stat_selector.py — Vessel Stat Selection Popup
# Shows vessel stats and allows player to select which stat to modify
# Uses the same design as ledger.py
# ============================================================

import os
import re
import pygame
import settings as S
from typing import Optional
from systems import audio as audio_sys

# Font helper (matches ledger.py)
_FONT_CACHE: dict[tuple, pygame.font.Font] = {}
def _get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Load DH font if available, fallback to system font (matches ledger.py)."""
    key = ("stat_selector", size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    try:
        path = os.path.join(S.ASSETS_FONTS_DIR, getattr(S, "DND_FONT_FILE", "DH.otf"))
        f = pygame.font.Font(path, size)
        if bold:
            # Try to make it bold if possible
            try:
                f = pygame.font.Font(path, size)
                # Some fonts don't support bold, so we'll use regular
            except Exception:
                pass
    except Exception:
        try:
            f = pygame.font.SysFont("georgia", size, bold=bold)
        except Exception:
            f = pygame.font.Font(None, size)
    _FONT_CACHE[key] = f
    return f

# Background image (same as ledger)
_POPUP_BG_PATH = os.path.join("Assets", "Map", "PartyLedger.png")
_popup_bg: pygame.Surface | None = None

def _get_popup_bg() -> pygame.Surface | None:
    """Load and cache the ledger background image."""
    global _popup_bg
    if _popup_bg is not None:
        return _popup_bg
    if not os.path.exists(_POPUP_BG_PATH):
        return None
    try:
        img = pygame.image.load(_POPUP_BG_PATH).convert_alpha()
        iw, ih = img.get_size()
        max_w, max_h = int(S.LOGICAL_WIDTH * 0.75), int(S.LOGICAL_HEIGHT * 0.75)
        scale = min(max_w / iw, max_h / ih, 1.0)
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        _popup_bg = pygame.transform.smoothscale(img, (nw, nh))
        return _popup_bg
    except Exception as e:
        print(f"⚠️ Failed to load ledger background: {e}")
        return None

def _try_load(path: str | None):
    """Try to load an image file."""
    if not path:
        return None
    if os.path.exists(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"⚠️ load fail {path}: {e}")
    return None

def _full_vessel_from_token_name(token_name: str | None) -> pygame.Surface | None:
    """Load vessel image from token name (handles monsters)."""
    if not token_name:
        return None
    # Use asset_links for proper token->vessel conversion (handles monsters)
    from systems.asset_links import token_to_vessel, find_image
    vessel_name = token_to_vessel(token_name)
    if vessel_name:
        path = find_image(vessel_name)
        if path and os.path.exists(path):
            return _try_load(path)
    return None

def _fit_center(surf: pygame.Surface, rect: pygame.Rect) -> tuple[pygame.Surface, pygame.Rect]:
    """Fit surface to rect while maintaining aspect ratio, centered."""
    iw, ih = surf.get_size()
    scale = min(rect.w / iw, rect.h / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    scaled = pygame.transform.smoothscale(surf, (nw, nh))
    dest = scaled.get_rect(center=rect.center)
    return scaled, dest

# Animation state
_ANIM_IN_SECS = 0.28
_ANIM_OUT_SECS = 0.22
_OVERLAY_MAX_A = 180
_SCALE_MIN = 0.98
_SLIDE_PIXELS = 80

def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

def _ease_out_cubic(p: float) -> float:
    p = _clamp01(p)
    return 1.0 - (1.0 - p) ** 3

# State
_ACTIVE = False
_STATE = None

def is_active() -> bool:
    """Check if stat selector is active."""
    return _ACTIVE

def start_stat_selection(gs, vessel_idx: int, stat_bonus: int, max_stat: Optional[int] = None, allow_ac: bool = True):
    """Start stat selection for a vessel."""
    global _ACTIVE, _STATE
    
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    if not (0 <= vessel_idx < len(stats_list)) or not stats_list[vessel_idx]:
        return False
    
    vessel_stats = stats_list[vessel_idx]
    vessel_name = names[vessel_idx] if vessel_idx < len(names) else None
    
    # Get vessel display name
    from systems.name_generator import generate_vessel_name
    display_name = generate_vessel_name(vessel_name) if vessel_name else "Vessel"
    
    # Get abilities
    abilities = vessel_stats.get("abilities", {})
    mods = vessel_stats.get("mods", {})
    
    # Calculate ability scores and modifiers
    stat_data = {}
    ability_names = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    for stat in ability_names:
        value = abilities.get(stat, 10)
        mod = mods.get(stat, 0)
        # Check if we can apply bonus (respect max_stat if specified)
        can_apply = True
        if max_stat is not None and value >= max_stat:
            can_apply = False
        stat_data[stat] = {
            "value": value,
            "mod": mod,
            "can_apply": can_apply,
        }
    
    # AC data (only if allowed)
    if allow_ac:
        ac = int(vessel_stats.get("ac", 10))
        ac_bonus = vessel_stats.get("ac_bonus", 0)
        ac_total = ac + ac_bonus
        stat_data["AC"] = {
            "value": ac_total,
            "mod": ac_bonus,
            "can_apply": True,
        }
    
    # Load vessel image (same logic as ledger.py)
    vessel_image = _full_vessel_from_token_name(vessel_name)
    
    _STATE = {
        "vessel_idx": vessel_idx,
        "vessel_name": display_name,
        "vessel_token": vessel_name,
        "stat_bonus": stat_bonus,
        "max_stat": max_stat,
        "stat_data": stat_data,
        "selected_stat": None,
        "hovered_stat": None,
        "vessel_image": vessel_image,
        "allow_ac": allow_ac,
        "for_all_vessels": False,  # Flag to indicate if this is for all vessels
        "phase": "in",  # "in" -> "open" -> "out"
        "t": 0.0,
        "last_ms": pygame.time.get_ticks(),
    }
    
    _ACTIVE = True
    return True


def start_stat_selection_for_all_vessels(gs, stat_bonus: int, max_stat: Optional[int] = None):
    """
    Start stat selection for all vessels (no specific vessel, no PNG shown).
    Shows the ledger-style UI but without a vessel image.
    """
    global _ACTIVE, _STATE
    
    # Get average/min stats from all vessels to display
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    # Collect all D&D stats from all vessels
    all_abilities = {}
    ability_names = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    
    # Initialize with default values
    for stat in ability_names:
        all_abilities[stat] = []
    
    # Collect stats from all vessels
    for i, stats in enumerate(stats_list):
        if isinstance(stats, dict) and names[i]:
            abilities = stats.get("abilities", {})
            for stat in ability_names:
                value = abilities.get(stat, 10)
                all_abilities[stat].append(value)
    
    # Calculate ability scores (show average or minimum, or just show that all vessels will be affected)
    # For simplicity, we'll just show that stats can be selected (all vessels will get the bonus)
    stat_data = {}
    for stat in ability_names:
        # Show that this stat can be selected (we'll apply to all vessels when selected)
        # We can show the minimum value or just indicate it's selectable
        min_value = min(all_abilities[stat]) if all_abilities[stat] else 10
        stat_data[stat] = {
            "value": min_value,  # Show minimum as reference
            "mod": 0,  # Modifier doesn't matter for selection
            "can_apply": True,  # All stats can be selected
        }
    
    _STATE = {
        "vessel_idx": -1,  # Special value to indicate "all vessels"
        "vessel_name": "All Vessels",
        "vessel_token": None,
        "stat_bonus": stat_bonus,
        "max_stat": max_stat,
        "stat_data": stat_data,
        "selected_stat": None,
        "hovered_stat": None,
        "vessel_image": None,  # No vessel image for "all vessels" mode
        "allow_ac": False,  # Only D&D stats for "stat to all vessels"
        "for_all_vessels": True,  # Flag to indicate this is for all vessels
        "phase": "in",  # "in" -> "open" -> "out"
        "t": 0.0,
        "last_ms": pygame.time.get_ticks(),
    }
    
    _ACTIVE = True
    return True

def close():
    """Close the stat selector (start close animation)."""
    global _STATE
    if _STATE is None:
        return
    if _STATE.get("phase") != "out":
        _STATE["phase"] = "out"
        _STATE["t"] = 0.0
        _STATE["last_ms"] = pygame.time.get_ticks()

def handle_event(event, gs) -> bool:
    """Handle input events. Returns True if event was consumed."""
    global _STATE
    
    if not _ACTIVE or _STATE is None:
        return False
    
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            close()
            try:
                audio_sys.play_click(audio_sys.get_global_bank())
            except Exception:
                pass
            return True
    
    if event.type == pygame.MOUSEMOTION:
        mx, my = event.pos
        _STATE["hovered_stat"] = _get_stat_at_position(mx, my)
        return False
    
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        mx, my = event.pos
        clicked_stat = _get_stat_at_position(mx, my)
        if clicked_stat:
            stat_data = _STATE["stat_data"].get(clicked_stat)
            if stat_data and stat_data.get("can_apply", False):
                # Set selected stat before closing (so it can be retrieved)
                _STATE["selected_stat"] = clicked_stat
                try:
                    audio_sys.play_click(audio_sys.get_global_bank())
                except Exception:
                    pass
                # Don't close here - let the update loop handle it after applying
                # This ensures the selection is applied before the selector closes
                return True
        return False
    
    return False

def get_selected_stat() -> Optional[tuple]:
    """Get the selected stat and vessel index. Returns (vessel_idx, stat_name) or None."""
    if not _ACTIVE or _STATE is None:
        return None
    
    selected = _STATE.get("selected_stat")
    if selected:
        return (_STATE["vessel_idx"], selected)
    return None

def _get_stat_at_position(mx: int, my: int) -> Optional[str]:
    """Get the stat at the given mouse position."""
    if _STATE is None:
        return None
    
    # Try to use stored button rects from draw (if available) - most reliable
    button_rects = _STATE.get("_button_rects")
    if button_rects:
        for stat_name, rect in button_rects.items():
            if rect.collidepoint(mx, my):
                return stat_name
    
    # Fallback: calculate button positions (same logic as draw)
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    base_bg = _get_popup_bg()
    
    if base_bg:
        bw, bh = base_bg.get_size()
        bx = (sw - bw) // 2
        by = (sh - bh) // 2
        book_rect = pygame.Rect(bx, by, bw, bh)
    else:
        pw, ph = int(sw * 0.55), int(sh * 0.55)
        px = (sw - pw) // 2
        py = (sh - ph) // 2
        book_rect = pygame.Rect(px, py, pw, ph)
    
    # Right page rect (matches draw)
    right_page = pygame.Rect(
        book_rect.x + int(book_rect.w * 0.54),
        book_rect.y + int(book_rect.h * 0.15),
        int(book_rect.w * 0.38),
        int(book_rect.h * 0.70),
    )
    right_page.x += 40
    right_page.y += 90
    
    cursor_x = right_page.x - 50
    
    # Calculate starting Y position (matches draw: title + inst + gaps)
    title_font = _get_font(max(26, int(book_rect.w * 0.015)))
    body_font = _get_font(max(18, int(book_rect.w * 0.008)))
    
    # Get title and instruction heights
    title_text = "Select Stat"
    title_surf = title_font.render(title_text, True, (0, 0, 0))
    title_height = title_surf.get_height()
    
    bonus = _STATE['stat_bonus']
    bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
    inst_text = f"{bonus_str} to selected stat"
    inst_surf = body_font.render(inst_text, True, (0, 0, 0))
    inst_height = inst_surf.get_height()
    
    # Start position: title_y + title_height + gap + inst_height + gap
    cursor_y = right_page.y + 10 + title_height + 12 + inst_height + 24
    LINE_GAP = 12
    
    # Only show AC if allowed
    stat_names = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    if _STATE.get("allow_ac", True) and "AC" in _STATE["stat_data"]:
        stat_names.append("AC")
    
    for stat_name in stat_names:
        stat_data = _STATE["stat_data"].get(stat_name, {})
        value = stat_data.get("value", 10)
        mod = stat_data.get("mod", 0)
        
        if mod != 0:
            mod_str = f"+{mod}" if mod > 0 else str(mod)
            stat_text = f"  {stat_name}: {value} ({mod_str})"
        else:
            stat_text = f"  {stat_name}: {value}"
        
        # Get text size to calculate button rect
        text_surf = body_font.render(stat_text, True, (0, 0, 0))
        text_rect = text_surf.get_rect(topleft=(cursor_x, cursor_y))
        button_rect = text_rect.inflate(20, 8)
        
        if button_rect.collidepoint(mx, my):
            return stat_name
        
        cursor_y += text_surf.get_height() + LINE_GAP
    
    return None

def _anim_update():
    """Update animation and return progress, phase."""
    global _STATE, _ACTIVE
    if _STATE is None:
        return 0.0, "closed"
    
    now = pygame.time.get_ticks()
    dt = max(0, (now - _STATE.get("last_ms", now)) / 1000.0)
    _STATE["last_ms"] = now
    
    phase = _STATE.get("phase", "open")
    t = _STATE.get("t", 0.0)
    
    if phase == "in":
        dur = max(0.001, _ANIM_IN_SECS)
        t = min(1.0, t + dt / dur)
        _STATE["t"] = t
        if t >= 1.0:
            _STATE["phase"] = "open"
            _STATE["t"] = 1.0
    elif phase == "out":
        dur = max(0.001, _ANIM_OUT_SECS)
        t = min(1.0, t + dt / dur)
        _STATE["t"] = t
        if t >= 1.0:
            _ACTIVE = False
            _STATE = None
            return 0.0, "closed"
    
    if _STATE is None:
        return 0.0, "closed"
    
    phase = _STATE["phase"]
    t = _STATE["t"]
    if phase == "in":
        return _ease_out_cubic(t), "in"
    if phase == "open":
        return 1.0, "open"
    if phase == "out":
        return 1.0 - _ease_out_cubic(t), "out"
    return 1.0, "open"

def draw(screen: pygame.Surface, dt: float = 0.016):
    """Draw the stat selector using ledger background."""
    global _ACTIVE, _STATE
    
    if not _ACTIVE or _STATE is None:
        return
    
    prog, phase = _anim_update()
    if phase == "closed":
        return
    
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    
    # Dim overlay (matches ledger)
    overlay_alpha = int(_OVERLAY_MAX_A * prog)
    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, overlay_alpha))
    screen.blit(overlay, (0, 0))
    
    # Get ledger background
    base_bg = _get_popup_bg()
    
    # If no background, fall back to simple box
    if base_bg is None:
        pw, ph = int(sw * 0.55), int(sh * 0.55)
        px = (sw - pw) // 2
        py_target = (sh - ph) // 2
        slide_y = int((1.0 - prog) * _SLIDE_PIXELS)
        py = py_target + slide_y
        scale = _SCALE_MIN + (1.0 - _SCALE_MIN) * prog
        pw = int(pw * scale)
        ph = int(ph * scale)
        px = (sw - pw) // 2
        pygame.draw.rect(screen, (220, 200, 130), (px, py, pw, ph), border_radius=14)
        pygame.draw.rect(screen, (70, 45, 30), (px, py, pw, ph), 4, border_radius=14)
        book_rect = pygame.Rect(px, py, pw, ph)
    else:
        # Use ledger background with animation
        bw, bh = base_bg.get_size()
        bx = (sw - bw) // 2
        by_target = (sh - bh) // 2
        slide_y = int((1.0 - prog) * _SLIDE_PIXELS)
        scale = _SCALE_MIN + (1.0 - _SCALE_MIN) * prog
        
        if abs(scale - 1.0) < 0.0001:
            sbw, sbh = bw, bh
            sbx = bx
            sby = by_target + slide_y
            screen.blit(base_bg, (sbx, sby))
        else:
            sbw, sbh = max(1, int(bw * scale)), max(1, int(bh * scale))
            sb_base = pygame.transform.smoothscale(base_bg, (sbw, sbh))
            sbx = (sw - sbw) // 2
            sby = (sh - sbh) // 2 + slide_y
            screen.blit(sb_base, (sbx, sby))
        
        book_rect = pygame.Rect(sbx, sby, sbw, sbh)
    
    # Left and right page rects (like ledger)
    left_page = pygame.Rect(
        book_rect.x + int(book_rect.w * 0.08),
        book_rect.y + int(book_rect.h * 0.15),
        int(book_rect.w * 0.38),
        int(book_rect.h * 0.70),
    )
    right_page = pygame.Rect(
        book_rect.x + int(book_rect.w * 0.54),
        book_rect.y + int(book_rect.h * 0.15),
        int(book_rect.w * 0.38),
        int(book_rect.h * 0.70),
    )
    # Manual offsets (matches ledger positioning)
    left_page.x += 130
    left_page.y += -50
    right_page.x += 40
    right_page.y += 90
    
    # Draw vessel image on left page (like ledger) - only if vessel_image exists
    vessel_image = _STATE.get("vessel_image")
    for_all_vessels = _STATE.get("for_all_vessels", False)
    if vessel_image and not for_all_vessels:
        page_pad = 12
        art_rect = left_page.inflate(-page_pad * 2, -page_pad * 2)
        scaled, _ = _fit_center(vessel_image, art_rect)
        shrink = 0.65
        nw, nh = int(scaled.get_width() * shrink), int(scaled.get_height() * shrink)
        scaled = pygame.transform.smoothscale(scaled, (nw, nh))
        dest = scaled.get_rect(center=left_page.center)
        screen.blit(scaled, dest.topleft)
    
    # Content area (right page style, like ledger)
    content_rect = right_page
    
    # Colors (matches ledger)
    light = (36, 34, 30)
    dark = (0, 0, 0)
    CLR_STR = (200, 60, 60)    # red
    CLR_DEX = (70, 140, 220)   # blue
    CLR_CON = (180, 140, 60)   # brown
    CLR_INT = (150, 100, 200)  # purple
    CLR_WIS = (40, 180, 90)    # green
    CLR_CHA = (220, 180, 60)   # gold
    CLR_AC = (150, 150, 150)   # steel grey
    
    stat_colors = {
        "STR": CLR_STR,
        "DEX": CLR_DEX,
        "CON": CLR_CON,
        "INT": CLR_INT,
        "WIS": CLR_WIS,
        "CHA": CLR_CHA,
        "AC": CLR_AC,
    }
    
    # Title (with shadow, like ledger)
    title_font = _get_font(max(26, int(book_rect.w * 0.015)))
    title_text = "Select Stat"
    title_surf = title_font.render(title_text, True, light)
    title_shadow = title_font.render(title_text, True, dark)
    title_rect = title_surf.get_rect(topleft=(content_rect.x - 50, content_rect.y + 10))
    screen.blit(title_shadow, (title_rect.x + 1, title_rect.y + 1))
    screen.blit(title_surf, title_rect)

    # Instructions
    body_font = _get_font(max(18, int(book_rect.w * 0.008)))
    bonus = _STATE['stat_bonus']
    bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
    inst_text = f"{bonus_str} to selected stat"
    inst_surf = body_font.render(inst_text, True, light)
    inst_shadow = body_font.render(inst_text, True, dark)
    inst_rect = inst_surf.get_rect(topleft=(content_rect.x - 50, title_rect.bottom + 12))
    screen.blit(inst_shadow, (inst_rect.x + 1, inst_rect.y + 1))
    screen.blit(inst_surf, inst_rect)
    
    # Stat buttons (styled like ledger text, clickable)
    cursor_x = content_rect.x - 50
    cursor_y = inst_rect.bottom + 24
    LINE_GAP = 12
    
    # Only show AC if allowed
    stat_names = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    if _STATE.get("allow_ac", True) and "AC" in _STATE["stat_data"]:
        stat_names.append("AC")
    
    # Store button rects for click detection
    _button_rects = {}
    
    # Stat name mapping (abbreviation to full name)
    stat_name_map = {
        "STR": "Strength",
        "DEX": "Dexterity",
        "CON": "Constitution",
        "INT": "Intelligence",
        "WIS": "Wisdom",
        "CHA": "Charisma",
        "AC": "Armor Class",
    }
    
    for_all_vessels = _STATE.get("for_all_vessels", False)
    
    for stat_name in stat_names:
        stat_data = _STATE["stat_data"].get(stat_name, {})
        value = stat_data.get("value", 10)
        mod = stat_data.get("mod", 0)
        can_apply = stat_data.get("can_apply", True)
        
        # Check hover/selection
        is_hovered = _STATE.get("hovered_stat") == stat_name
        is_selected = _STATE.get("selected_stat") == stat_name
        
        # Stat color
        stat_color = stat_colors.get(stat_name, light)
        
        # Format text - if for_all_vessels, just show stat name
        if for_all_vessels:
            # For "all vessels" mode, just show the stat name (full name if available)
            display_name = stat_name_map.get(stat_name, stat_name)
            stat_text = f"  {display_name}"
        else:
            # For single vessel mode, show value and modifier
            if mod != 0:
                mod_str = f"+{mod}" if mod > 0 else str(mod)
                stat_text = f"  {stat_name}: {value} ({mod_str})"
            else:
                stat_text = f"  {stat_name}: {value}"
            
            # Preview if hovering
            if is_hovered and can_apply and not is_selected:
                new_value = value + _STATE["stat_bonus"]
                if _STATE.get("max_stat"):
                    new_value = min(new_value, _STATE["max_stat"])
                stat_text += f" → {new_value}"
            elif not can_apply:
                stat_text += " (MAX)"
        
        # Text color
        if not can_apply:
            text_color = (120, 120, 120)
        elif is_selected:
            text_color = stat_color
        elif is_hovered:
            text_color = stat_color
        else:
            text_color = stat_color
        
        # Draw text with shadow
        text_surf = body_font.render(stat_text, True, text_color)
        text_shadow = body_font.render(stat_text, True, dark)
        text_rect = text_surf.get_rect(topleft=(cursor_x, cursor_y))
        screen.blit(text_shadow, (text_rect.x + 1, text_rect.y + 1))
        screen.blit(text_surf, text_rect)
        
        # Store button rect for click detection
        _button_rects[stat_name] = text_rect.inflate(20, 8)
        
        # Highlight if hovered
        if is_hovered and can_apply:
            highlight_rect = text_rect.inflate(8, 4)
            highlight_surf = pygame.Surface((highlight_rect.w, highlight_rect.h), pygame.SRCALPHA)
            highlight_surf.fill((*stat_color, 40))
            screen.blit(highlight_surf, highlight_rect.topleft)
        
        cursor_y += text_surf.get_height() + LINE_GAP
    
    # Store button rects in state for click detection
    _STATE["_button_rects"] = _button_rects

