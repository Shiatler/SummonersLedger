# ============================================================
# screens/archives.py — The Archives (Pokemon Box-style storage)
# Layout: Left panel for detailed vessel info, right panel for grid of stored vessels
# REDESIGNED: Clean, polished medieval purple aesthetic
# ============================================================

import os
import pygame
import settings as S
from systems import coords
from systems.asset_links import vessel_to_token, token_to_vessel, find_image
# Import party_manager at module level to avoid import lag
try:
    from screens import party_manager
except ImportError:
    party_manager = None

# Mode constant
MODE_ARCHIVES = "ARCHIVES"

# ===================== Layout Constants =====================
HEADER_HEIGHT = 90  # Slightly taller for better proportions
LEFT_PANEL_WIDTH = int(S.LOGICAL_WIDTH * 0.65)  # 65% of screen width
RIGHT_PANEL_WIDTH = S.LOGICAL_WIDTH - LEFT_PANEL_WIDTH

# Grid layout for right panel (storage boxes)
GRID_COLS = 6  # 6 columns
GRID_ROWS = 8  # 8 rows per page
SLOTS_PER_PAGE = GRID_COLS * GRID_ROWS  # 48 slots per page
GRID_SQUARE_SIZE = 80
GRID_SPACING = 10  # Slightly more spacing for cleaner look
GRID_PADDING = 24  # More padding
MAX_PAGES = 20  # Maximum number of pages

# Colors - Enhanced Purple, gloomy, magical, medieval aesthetic
COLOR_BG = (18, 10, 28)  # Deeper, richer background
COLOR_HEADER_BG = (35, 18, 50)  # Darker header
COLOR_HEADER_SHADOW = (15, 8, 22)  # Shadow for depth
COLOR_HEADER_TEXT = (200, 160, 240)  # Brighter, more ethereal text
COLOR_HEADER_GLOW = (140, 100, 180)  # Subtle glow color
COLOR_PANEL_BG = (28, 16, 42)  # Richer panel background
COLOR_PANEL_BORDER_OUTER = (70, 35, 95)  # Outer border
COLOR_PANEL_BORDER_INNER = (110, 65, 140)  # Inner border for depth
COLOR_PANEL_SHADOW = (12, 6, 18)  # Shadow color
COLOR_GRID_SQUARE = (38, 22, 55)  # Refined square color
COLOR_GRID_SQUARE_BORDER = (95, 55, 125)  # Subtle border
COLOR_GRID_SQUARE_HOVER = (55, 32, 75)  # Hover state
COLOR_GRID_SQUARE_SELECTED = (120, 70, 160)  # Selected border
COLOR_GRID_SQUARE_GLOW = (180, 120, 220)  # Glow for selected
COLOR_INFO_BOX = (32, 18, 48)  # Info box background
COLOR_INFO_BORDER = (85, 50, 115)  # Info box border
COLOR_INFO_SHADOW = (20, 12, 30)  # Shadow for info boxes
COLOR_TEXT = (185, 145, 215)  # Main text - cleaner
COLOR_TEXT_DIM = (110, 85, 140)  # Dimmed text
COLOR_TEXT_HIGHLIGHT = (230, 195, 255)  # Highlighted text
COLOR_BUTTON_BG = (45, 25, 65)  # Button background
COLOR_BUTTON_HOVER = (65, 35, 90)  # Button hover
COLOR_BUTTON_DISABLED = (30, 20, 40)  # Disabled button
COLOR_BUTTON_BORDER = (120, 70, 150)  # Button border
COLOR_BUTTON_TEXT = (220, 180, 250)  # Button text

# Scroll state for grid
_scroll_offset = 0
_scrollbar_dragging = False
_drag_start_y = 0
_drag_start_offset = 0

# Selected vessel state
_selected_vessel_index = None  # Index in archives list

# Page navigation state
_current_page = 0  # Current page (0-indexed)

# Drag and drop state
_dragging_vessel = False  # Whether we're currently dragging a vessel
_drag_source_index = None  # Global index of the vessel being dragged
_drag_vessel_data = None  # The vessel data being dragged
_drag_offset_x = 0  # Mouse offset from vessel sprite when drag started
_drag_offset_y = 0
_drag_sprite = None  # Cached sprite for the dragged vessel

# Party picker state (for moving vessels to archives)
_party_picker_active = False

# Font cache
_font_cache = {}


def _get_font(size: int, bold: bool = False):
    """Get DH font with caching - medieval magical aesthetic."""
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    
    font_paths = [
        os.path.join("Assets", "Fonts", "DH.otf"),
        os.path.join("Assets", "Fonts", "DH.ttf"),
    ]
    
    font = None
    for path in font_paths:
        if os.path.exists(path):
            try:
                font = pygame.font.Font(path, size)
                if bold:
                    font.set_bold(True)
                break
            except Exception:
                continue
    
    if font is None:
        font = pygame.font.SysFont("georgia", size, bold=bold)
    
    _font_cache[key] = font
    return font


def _draw_panel_with_depth(screen, rect, bg_color, border_outer, border_inner, shadow_offset=3):
    """Draw a panel with depth using shadows and borders."""
    # Shadow
    shadow_rect = rect.move(shadow_offset, shadow_offset)
    pygame.draw.rect(screen, COLOR_PANEL_SHADOW, shadow_rect)
    
    # Main panel
    pygame.draw.rect(screen, bg_color, rect)
    
    # Outer border
    pygame.draw.rect(screen, border_outer, rect, 2)
    
    # Inner border (subtle)
    inner_rect = rect.inflate(-6, -6)
    pygame.draw.rect(screen, border_inner, inner_rect, 1)


def _draw_button_polished(screen, rect, text, font, enabled=True, hovered=False):
    """Draw a polished button with depth and glow."""
    # Shadow
    shadow_rect = rect.move(2, 2)
    pygame.draw.rect(screen, COLOR_INFO_SHADOW, shadow_rect)
    
    # Button background
    if enabled:
        bg_color = COLOR_BUTTON_HOVER if hovered else COLOR_BUTTON_BG
    else:
        bg_color = COLOR_BUTTON_DISABLED
    
    pygame.draw.rect(screen, bg_color, rect)
    
    # Border
    border_color = COLOR_BUTTON_BORDER if enabled else COLOR_INFO_BORDER
    pygame.draw.rect(screen, border_color, rect, 2)
    
    # Inner highlight (subtle)
    if enabled:
        highlight_rect = rect.inflate(-4, -4)
        highlight_rect.height = 3
        pygame.draw.rect(screen, (70, 45, 90), highlight_rect)
    
    # Text
    text_color = COLOR_BUTTON_TEXT if enabled else COLOR_TEXT_DIM
    text_surf = font.render(text, True, text_color)
    text_rect = text_surf.get_rect(center=rect.center)
    screen.blit(text_surf, text_rect)


def _draw_info_box_polished(screen, rect):
    """Draw an info box with depth and polish."""
    # Shadow
    shadow_rect = rect.move(2, 2)
    pygame.draw.rect(screen, COLOR_INFO_SHADOW, shadow_rect)
    
    # Main box
    pygame.draw.rect(screen, COLOR_INFO_BOX, rect)
    
    # Outer border
    pygame.draw.rect(screen, COLOR_INFO_BORDER, rect, 2)
    
    # Inner border (subtle)
    inner_rect = rect.inflate(-4, -4)
    pygame.draw.rect(screen, (60, 35, 80), inner_rect, 1)


def _draw_text_with_glow(screen, text, font, pos, color, glow_color=None, glow_size=2):
    """Draw text with a subtle glow effect."""
    if glow_color is None:
        glow_color = COLOR_HEADER_GLOW
    
    # Draw glow (multiple passes for softness)
    for offset_x in range(-glow_size, glow_size + 1):
        for offset_y in range(-glow_size, glow_size + 1):
            if offset_x == 0 and offset_y == 0:
                continue
            glow_surf = font.render(text, True, glow_color)
            glow_surf.set_alpha(60)
            screen.blit(glow_surf, (pos[0] + offset_x, pos[1] + offset_y))
    
    # Draw main text
    text_surf = font.render(text, True, color)
    screen.blit(text_surf, pos)


def _calculate_grid_position(right_panel_rect, stored_box_rect):
    """Calculate centered grid position for both drawing and event handling."""
    # Calculate grid dimensions
    grid_total_width = GRID_COLS * GRID_SQUARE_SIZE + (GRID_COLS - 1) * GRID_SPACING
    grid_total_height = GRID_ROWS * GRID_SQUARE_SIZE + (GRID_ROWS - 1) * GRID_SPACING
    
    # Space for arrows/page indicator at bottom
    arrow_area_height = 60
    
    # Available vertical space for grid (between stored box and arrows)
    available_height = right_panel_rect.height - stored_box_rect.height - GRID_PADDING * 2 - arrow_area_height
    
    # Center grid horizontally and vertically
    grid_start_x = right_panel_rect.centerx - grid_total_width // 2
    grid_start_y = stored_box_rect.bottom + GRID_PADDING + (available_height - grid_total_height) // 2
    
    return grid_start_x, grid_start_y


def _get_grid_cell_from_point(mx, my, grid_start_x, grid_start_y):
    """
    Calculate which grid cell contains the mouse point (for selection only).
    Returns: (row, col, square_rect) or (None, None, None) if outside grid
    """
    # Calculate relative position from grid start
    rel_x = mx - grid_start_x
    rel_y = my - grid_start_y
    
    # If outside grid bounds, return None
    if rel_x < 0 or rel_y < 0:
        return None, None, None
    
    # The distance from the start of one square to the start of the next
    cell_pitch = GRID_SQUARE_SIZE + GRID_SPACING
    
    # Calculate which cell the mouse is in
    col = int(rel_x // cell_pitch)
    row = int(rel_y // cell_pitch)
    
    # Check if within valid grid bounds
    if col < 0 or col >= GRID_COLS or row < 0 or row >= GRID_ROWS:
        return None, None, None
    
    # Calculate final square position
    square_x = grid_start_x + col * cell_pitch
    square_y = grid_start_y + row * cell_pitch
    square_rect = pygame.Rect(square_x, square_y, GRID_SQUARE_SIZE, GRID_SQUARE_SIZE)
    
    return row, col, square_rect


def _get_archives_list(gs) -> list:
    """Get the archives list from game state, initializing if needed."""
    if not hasattr(gs, "archives"):
        gs.archives = []  # List of dicts: {"vessel_name": str, "token_name": str, "stats": dict}
    return gs.archives


def _add_to_archives(gs, vessel_png_name: str, stats_dict: dict) -> bool:
    """Add a vessel to the archives in the first available slot. Returns True if successful."""
    try:
        token_png = vessel_to_token(vessel_png_name)
        if not token_png:
            return False
        
        # Remove .png extension for storage
        vessel_name = vessel_png_name[:-4] if vessel_png_name.lower().endswith(".png") else vessel_png_name
        token_name = token_png[:-4] if token_png.lower().endswith(".png") else token_png
        
        archive_entry = {
            "vessel_name": vessel_name,
            "token_name": token_name,
            "stats": dict(stats_dict) if isinstance(stats_dict, dict) else {}
        }
        
        archives = _get_archives_list(gs)
        
        # Find first available slot (None or empty)
        max_slots = MAX_PAGES * SLOTS_PER_PAGE
        for i in range(max_slots):
            if i >= len(archives) or archives[i] is None:
                # Found an available slot
                if i >= len(archives):
                    # Extend list to this index
                    while len(archives) <= i:
                        archives.append(None)
                archives[i] = archive_entry
                return True
        
        # All slots are full
        print("⚠️ Archives are full - cannot add more vessels")
        return False
    except Exception as e:
        print(f"⚠️ Failed to add vessel to archives: {e}")
        return False


def _move_party_vessel_to_archives(gs, party_index: int) -> bool:
    """Move a vessel from party to archives. Returns True if successful."""
    try:
        # Ensure party slots exist
        if not hasattr(gs, "party_slots_names"):
            gs.party_slots_names = [None] * 6
        if not hasattr(gs, "party_slots"):
            gs.party_slots = [None] * 6
        if not hasattr(gs, "party_vessel_stats"):
            gs.party_vessel_stats = [None] * 6
        
        if party_index < 0 or party_index >= len(gs.party_slots_names):
            return False
        
        party_vessel_name = gs.party_slots_names[party_index]
        party_vessel_stats = gs.party_vessel_stats[party_index]
        
        if not party_vessel_name or not party_vessel_stats:
            return False  # Empty slot
        
        # Prevent moving the last vessel in the party
        party_count = sum(1 for slot in gs.party_slots_names if slot)
        if party_count <= 1:
            print("⚠️ Cannot move the last vessel from the party to archives")
            return False
        
        # Convert token name back to vessel name
        from systems.asset_links import token_to_vessel
        vessel_name = token_to_vessel(party_vessel_name)
        if not vessel_name:
            return False
        
        # Remove .png extension
        vessel_name = vessel_name[:-4] if vessel_name.lower().endswith(".png") else vessel_name
        token_name = party_vessel_name[:-4] if party_vessel_name.lower().endswith(".png") else party_vessel_name
        
        # Create archive entry
        archive_entry = {
            "vessel_name": vessel_name,
            "token_name": token_name,
            "stats": dict(party_vessel_stats) if isinstance(party_vessel_stats, dict) else {}
        }
        
        # Add to archives - find first available slot (same logic as _add_to_archives)
        archives = _get_archives_list(gs)
        max_slots = MAX_PAGES * SLOTS_PER_PAGE
        
        # Find first available slot (None or empty)
        slot_found = False
        for i in range(max_slots):
            if i >= len(archives) or archives[i] is None:
                # Found an available slot
                if i >= len(archives):
                    # Extend list to this index
                    while len(archives) <= i:
                        archives.append(None)
                archives[i] = archive_entry
                slot_found = True
                break
        
        if not slot_found:
            print("⚠️ Archives are full - cannot store vessel")
            return False
        
        # Remove from party
        gs.party_slots_names[party_index] = None
        gs.party_slots[party_index] = None
        gs.party_vessel_stats[party_index] = None
        
        return True
    except Exception as e:
        print(f"⚠️ Failed to move vessel to archives: {e}")
        return False


def _move_archives_vessel_to_party(gs, archive_index: int) -> bool:
    """Move a vessel from archives to party. Returns True if successful."""
    try:
        archives = _get_archives_list(gs)
        if archive_index < 0 or archive_index >= len(archives):
            print(f"⚠️ Invalid archive index: {archive_index} (archives length: {len(archives)})")
            return False
        
        # Ensure party slots exist
        if not hasattr(gs, "party_slots_names"):
            gs.party_slots_names = [None] * 6
        if not hasattr(gs, "party_slots"):
            gs.party_slots = [None] * 6
        if not hasattr(gs, "party_vessel_stats"):
            gs.party_vessel_stats = [None] * 6
        
        # Find first empty party slot
        empty_slot = None
        for idx, slot in enumerate(gs.party_slots_names):
            if not slot:
                empty_slot = idx
                break
        
        if empty_slot is None:
            # Party is full - cannot add
            print("⚠️ Cannot add vessel to party: party is full (6/6)")
            return False
        
        # Get archive vessel
        archive_vessel = archives[archive_index]
        token_name = archive_vessel.get("token_name", "")
        stats = archive_vessel.get("stats", {})
        
        if not token_name:
            print(f"⚠️ Archive vessel at index {archive_index} has no token_name")
            return False
        
        # Ensure token name has .png extension
        if not token_name.endswith(".png"):
            token_name = f"{token_name}.png"
        
        # Add to party
        print(f"📦 Adding {token_name} to party slot {empty_slot}")
        gs.party_slots_names[empty_slot] = token_name
        gs.party_slots[empty_slot] = None  # Will be loaded when needed
        gs.party_vessel_stats[empty_slot] = dict(stats) if isinstance(stats, dict) else {}
        
        # Clear party_ui.py tracking so it rebuilds from names
        if hasattr(gs, "_party_slots_token_names"):
            delattr(gs, "_party_slots_token_names")
        
        # Remove from archives
        removed_vessel = archives.pop(archive_index)
        print(f"🗑️ Removed {removed_vessel.get('vessel_name', 'unknown')} from archives")
        
        # Clear selection if it was the one we just moved
        global _selected_vessel_index
        if _selected_vessel_index == archive_index:
            _selected_vessel_index = None
        elif _selected_vessel_index is not None and _selected_vessel_index > archive_index:
            # Adjust selection index if we removed an item before it
            _selected_vessel_index -= 1
        
        return True
    except Exception as e:
        print(f"⚠️ Failed to move vessel from archives to party: {e}")
        import traceback
        traceback.print_exc()
        return False


def _swap_vessel_with_party(gs, archive_index: int, party_index: int) -> bool:
    """Swap a vessel from archives with a vessel in the party. Returns True if successful."""
    try:
        archives = _get_archives_list(gs)
        if archive_index < 0 or archive_index >= len(archives):
            return False
        
        # Ensure party slots exist
        if not hasattr(gs, "party_slots_names"):
            gs.party_slots_names = [None] * 6
        if not hasattr(gs, "party_slots"):
            gs.party_slots = [None] * 6
        if not hasattr(gs, "party_vessel_stats"):
            gs.party_vessel_stats = [None] * 6
        
        if party_index < 0 or party_index >= len(gs.party_slots_names):
            return False
        
        # Get archive vessel
        archive_vessel = archives[archive_index]
        
        # Get party vessel (if any)
        party_vessel_name = gs.party_slots_names[party_index]
        party_vessel_stats = gs.party_vessel_stats[party_index]
        
        # Swap: archive vessel goes to party
        # Convert vessel_name back to token for party
        token_name = archive_vessel["token_name"]
        gs.party_slots_names[party_index] = f"{token_name}.png" if not token_name.endswith(".png") else token_name
        gs.party_slots[party_index] = None  # Will be loaded when needed
        gs.party_vessel_stats[party_index] = dict(archive_vessel["stats"])
        
        # Clear party_ui.py tracking so it rebuilds from names
        if hasattr(gs, "_party_slots_token_names"):
            delattr(gs, "_party_slots_token_names")
        
        # Swap: party vessel goes to archives (if there was one)
        if party_vessel_name:
            # Convert token back to vessel name
            from systems.asset_links import token_to_vessel
            vessel_name = token_to_vessel(party_vessel_name)
            if vessel_name:
                vessel_name = vessel_name[:-4] if vessel_name.lower().endswith(".png") else vessel_name
                archives[archive_index] = {
                    "vessel_name": vessel_name,
                    "token_name": party_vessel_name[:-4] if party_vessel_name.lower().endswith(".png") else party_vessel_name,
                    "stats": dict(party_vessel_stats) if isinstance(party_vessel_stats, dict) else {}
                }
            else:
                # If conversion fails, just remove from archives
                archives.pop(archive_index)
        else:
            # Empty party slot, just remove from archives
            archives.pop(archive_index)
        
        # No autosave - user must manually save via "Save Game" button
        
        return True
    except Exception as e:
        print(f"⚠️ Failed to swap vessel: {e}")
        return False


def _load_vessel_sprite(vessel_name: str, is_token: bool) -> pygame.Surface | None:
    """Load a vessel sprite or token. Returns None if not found."""
    try:
        if is_token:
            # For tokens, try find_image first (searches all asset dirs including VesselMonsters)
            from systems.asset_links import find_image
            token_path = find_image(vessel_name)
            if token_path and os.path.exists(token_path):
                return pygame.image.load(token_path).convert_alpha()
            
            # Fallback to Assets/Map
            map_path = os.path.join("Assets", "Map", f"{vessel_name}.png")
            if os.path.exists(map_path):
                return pygame.image.load(map_path).convert_alpha()
            
            # Try category folders (including VesselMonsters)
            for category_dir in ["VesselMonsters", "Starters", "VesselsFemale", "VesselsMale", "RareVessels"]:
                category_path = os.path.join("Assets", category_dir, f"{vessel_name}.png")
                if os.path.exists(category_path):
                    return pygame.image.load(category_path).convert_alpha()
        else:
            # For full vessel sprites, convert token name to vessel name if needed
            from systems.asset_links import token_to_vessel
            if "Token" in vessel_name:
                vessel_name = token_to_vessel(vessel_name) or vessel_name
            
            # Try find_image first
            from systems.asset_links import find_image
            vessel_path = find_image(vessel_name)
            if vessel_path and os.path.exists(vessel_path):
                return pygame.image.load(vessel_path).convert_alpha()
            
            # Try category folders (including VesselMonsters)
            for category_dir in ["VesselMonsters", "Starters", "VesselsFemale", "VesselsMale", "RareVessels"]:
                category_path = os.path.join("Assets", category_dir, f"{vessel_name}.png")
                if os.path.exists(category_path):
                    return pygame.image.load(category_path).convert_alpha()
        
        return None
    except Exception as e:
        print(f"⚠️ Failed to load vessel sprite {vessel_name}: {e}")
        return None


def add_vessel_to_archives(gs, vessel_png_name: str, stats_dict: dict) -> bool:
    """Public function to add a vessel to archives."""
    return _add_to_archives(gs, vessel_png_name, stats_dict)


def enter(gs, previous_screen_surface=None, **deps):
    """Enter the Archives screen."""
    global _scroll_offset, _selected_vessel_index, _party_picker_active, _current_page
    global _dragging_vessel, _drag_source_index, _drag_vessel_data, _drag_offset_x, _drag_offset_y, _drag_sprite
    
    _scroll_offset = 0
    _selected_vessel_index = None
    _party_picker_active = False
    _current_page = 0
    _dragging_vessel = False
    _drag_source_index = None
    _drag_vessel_data = None
    _drag_offset_x = 0
    _drag_offset_y = 0
    _drag_sprite = None
    
    # Ensure party manager is closed when entering archives
    if party_manager:
        try:
            if party_manager.is_open():
                party_manager.close()
        except Exception:
            pass
    
    # Initialize archives if needed
    _get_archives_list(gs)
    
    # Pre-warm party_manager assets to avoid lag when opening
    if party_manager:
        try:
            # Pre-load scroll image for common screen size
            sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
            # Access the private function to pre-cache the scroll
            load_scroll = getattr(party_manager, '_load_scroll_scaled', None)
            if load_scroll:
                load_scroll(sw, sh)
            
            # Pre-load token icons for all party members to avoid first-time lag
            # Load multiple common sizes to cover different screen resolutions
            party_slots_names = getattr(gs, "party_slots_names", [None] * 6)
            load_icon = getattr(party_manager, '_load_token_icon', None)
            if load_icon:
                # Pre-load common icon sizes (party manager calculates dynamically)
                icon_sizes = [48, 56, 64, 72, 80]  # Common sizes for different screen sizes
                for fname in party_slots_names:
                    if fname:
                        for icon_size in icon_sizes:
                            try:
                                # Pre-load and cache the icon - this will populate the cache
                                load_icon(fname, icon_size)
                            except Exception:
                                pass
        except Exception as e:
            print(f"⚠️ Failed to pre-warm party_manager assets: {e}")
    
    # Handle music transition
    import systems.audio as audio_sys
    audio_bank = deps.get("audio_bank")
    
    # Stop overworld music and play Archives music
    if audio_bank:
        # Stop current music (overworld)
        audio_sys.stop_music(fade_ms=500)
        
        # Try multiple possible paths for Archives music
        possible_paths = [
            os.path.join("Assets", "Music", "Sounds", "Sounds Archives.mp3"),
            os.path.join("Assets", "Music", "Sounds", "Archives.mp3"),
            os.path.join("Assets", "Music", "Sounds Archives.mp3"),
            r"C:\Users\Frederik\Desktop\SummonersLedger\Assets\Music\Sounds\Sounds Archives.mp3",
            r"C:\Users\Frederik\Desktop\SummonersLedger\Assets\Music\Sounds\Archives.mp3",
        ]
        
        archives_music_path = None
        for path in possible_paths:
            if os.path.exists(path):
                archives_music_path = path
                print(f"✅ Found Archives music at: {path}")
                break
        
        if archives_music_path:
            try:
                # Use direct path - play_music will check os.path.exists if not in bank
                audio_sys.play_music(audio_bank, archives_music_path, loop=True, fade_ms=800)
                print(f"▶️ Playing Archives music via audio_sys: {archives_music_path}")
            except Exception as e:
                print(f"⚠️ Failed to play via audio_sys, trying direct pygame.mixer.music: {e}")
                # Fallback: use pygame.mixer.music directly
                try:
                    vol = pygame.mixer.music.get_volume() or 0.6
                    pygame.mixer.music.load(archives_music_path)
                    pygame.mixer.music.play(loops=-1, start=0.0, fade_ms=800)
                    pygame.mixer.music.set_volume(vol)
                    print(f"▶️ Playing Archives music directly: {archives_music_path}")
                except Exception as e2:
                    print(f"⚠️ Failed to play Archives music directly: {e2}")
                    import traceback
                    traceback.print_exc()
        else:
            print(f"⚠️ Archives music not found. Tried paths:")
            for path in possible_paths:
                exists = os.path.exists(path)
                print(f"   - {path} (exists: {exists})")


def handle(gs, events, dt, **deps):
    """Handle events for the Archives screen. Returns next mode or None."""
    global _scroll_offset, _selected_vessel_index, _scrollbar_dragging, _drag_start_y, _drag_start_offset, _party_picker_active
    global _current_page, _dragging_vessel, _drag_source_index, _drag_vessel_data, _drag_offset_x, _drag_offset_y, _drag_sprite
    
    archives = _get_archives_list(gs)
    next_mode = None
    audio_bank = deps.get("audio_bank")
    
    # Always use 20 pages with the same layout
    total_pages = MAX_PAGES
    max_valid_page = MAX_PAGES - 1
    if _current_page > max_valid_page:
        _current_page = max_valid_page
    
    # Calculate arrow button positions for page navigation
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    right_panel_rect_nav = pygame.Rect(LEFT_PANEL_WIDTH, HEADER_HEIGHT, RIGHT_PANEL_WIDTH, sh - HEADER_HEIGHT)
    stored_box_height_nav = 50
    stored_box_rect_nav = pygame.Rect(
        right_panel_rect_nav.x + GRID_PADDING,
        right_panel_rect_nav.y + GRID_PADDING,
        right_panel_rect_nav.width - GRID_PADDING * 2,
        stored_box_height_nav
    )
    grid_start_x_nav, grid_start_y_nav = _calculate_grid_position(right_panel_rect_nav, stored_box_rect_nav)
    grid_total_height_nav = GRID_ROWS * GRID_SQUARE_SIZE + (GRID_ROWS - 1) * GRID_SPACING
    grid_bottom_nav = grid_start_y_nav + grid_total_height_nav
    
    arrow_size = 40
    arrow_y = grid_bottom_nav + 20  # Position arrows below the grid with some spacing
    
    # Calculate page text width to position arrows relative to it (matches draw function)
    page_font_nav = _get_font(20)
    page_text_nav = f"Page {_current_page + 1} / {MAX_PAGES}"
    page_text_width_nav = page_font_nav.size(page_text_nav)[0]
    
    left_arrow_x = right_panel_rect_nav.centerx - (page_text_width_nav // 2) - 50
    right_arrow_x = right_panel_rect_nav.centerx + (page_text_width_nav // 2) + 50  # Move further right
    left_arrow_rect = pygame.Rect(left_arrow_x - arrow_size // 2, arrow_y - arrow_size // 2, arrow_size, arrow_size)
    right_arrow_rect = pygame.Rect(right_arrow_x - arrow_size // 2, arrow_y - arrow_size // 2, arrow_size, arrow_size)
    
    # Calculate "Add to Party" button position (matches draw function exactly)
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    left_panel_rect_temp = pygame.Rect(0, HEADER_HEIGHT, LEFT_PANEL_WIDTH, sh - HEADER_HEIGHT)
    sprite_area_size = 350
    sprite_area_margin = 30
    sprite_area_rect_temp = pygame.Rect(
        left_panel_rect_temp.centerx - sprite_area_size // 2,
        left_panel_rect_temp.y + sprite_area_margin,
        sprite_area_size,
        sprite_area_size
    )
    sprite_area_bottom = sprite_area_rect_temp.bottom
    name_rect_bottom = sprite_area_bottom + 30
    add_button_width = 240  # Match draw function
    add_button_height = 50  # Match draw function
    add_button_x = sprite_area_rect_temp.centerx - add_button_width // 2  # Center with sprite area
    add_button_y = name_rect_bottom + 20  # Match draw function
    add_button_rect = pygame.Rect(add_button_x, add_button_y, add_button_width, add_button_height)
    
    party_slots_check = getattr(gs, "party_slots_names", [None] * 6)
    party_count_check = sum(1 for slot in party_slots_check if slot)
    can_add_to_party = party_count_check < 6
    
    # Check if a vessel was selected from party picker (this happens immediately when clicked)
    # The party manager's callback sets this flag, and we process it here
    if hasattr(gs, '_archives_party_selected_idx'):
        selected_idx = gs._archives_party_selected_idx
        # Move vessel from party to archives
        if _move_party_vessel_to_archives(gs, selected_idx):
            # Clear selection flag
            delattr(gs, '_archives_party_selected_idx')
            # Close party manager if it's still open
            if party_manager:
                try:
                    if party_manager.is_open():
                        party_manager.close()
                    _party_picker_active = False
                except Exception:
                    pass
            # No autosave - user must manually save via "Save Game" button
        else:
            # Failed to move - clear flag anyway
            delattr(gs, '_archives_party_selected_idx')
            if party_manager:
                try:
                    if party_manager.is_open():
                        party_manager.close()
                    _party_picker_active = False
                except Exception:
                    pass
    
    # Handle button clicks first (check for "Store Vessel" button)
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    button_width = 200
    button_height = 50
    button_x = sw - button_width - 20
    button_y = sh - button_height - 20
    button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
    
    # Check party count to determine if button should be disabled
    party_slots = getattr(gs, "party_slots_names", [None] * 6)
    party_count = sum(1 for slot in party_slots if slot)
    can_store_vessel = party_count > 1  # Must have more than 1 vessel to store one
    
    for event in events:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = coords.screen_to_logical(pygame.mouse.get_pos())
            if button_rect.collidepoint(mx, my):
                if not _party_picker_active:
                    # Check if we can store a vessel (must have more than 1)
                    if not can_store_vessel:
                        print("⚠️ Cannot store vessel: must have at least 2 vessels in party")
                        continue  # Don't open picker if disabled
                    # Open party picker (optimized - no import lag)
                    if party_manager:
                        try:
                            def on_pick(idx):
                                gs._archives_party_selected_idx = idx
                            party_manager.open_picker(on_pick)
                            _party_picker_active = True
                        except Exception as e:
                            print(f"⚠️ Failed to open party picker: {e}")
                    else:
                        print("⚠️ party_manager not available")
                else:
                    # Cancel picker
                    if party_manager:
                        try:
                            party_manager.close()
                            _party_picker_active = False
                        except Exception:
                            pass
                continue  # Skip other event processing for this click
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if _dragging_vessel:
                    # Cancel drag
                    _dragging_vessel = False
                    _drag_source_index = None
                    _drag_vessel_data = None
                    _drag_offset_x = 0
                    _drag_offset_y = 0
                    _drag_sprite = None
                    return None
                elif _party_picker_active:
                    # Close party picker
                    if party_manager:
                        try:
                            party_manager.close()
                            _party_picker_active = False
                        except Exception:
                            pass
                    return None
                else:
                    next_mode = S.MODE_GAME  # Return to world/game mode
                    # Always close party manager when exiting archives
                    if party_manager:
                        try:
                            if party_manager.is_open():
                                party_manager.close()
                            _party_picker_active = False
                        except Exception:
                            pass
                    # Handle music transition when exiting
                    import systems.audio as audio_sys
                    
                    # Stop Archives music
                    audio_sys.stop_music(fade_ms=600)
                    
                    # Resume overworld music
                    if audio_bank:
                        # Pick next overworld track
                        last_track = getattr(gs, "last_overworld_track", None)
                        nxt = audio_sys.pick_next_track(audio_bank, last_track, prefix="music")
                        if nxt:
                            audio_sys.play_music(audio_bank, nxt, loop=False, fade_ms=800)
                            gs.last_overworld_track = nxt
                    
                    return next_mode
            
            # Arrow key navigation for pages (works even if pages are empty, wraps around)
            if not _party_picker_active:
                if event.key == pygame.K_LEFT:
                    # Wrap around: page 0 -> page 19
                    _current_page = (_current_page - 1) % MAX_PAGES
                    try:
                        from systems import audio as audio_sys
                        audio_sys.play_click(audio_sys.get_global_bank())
                    except:
                        pass
                elif event.key == pygame.K_RIGHT:
                    # Wrap around: page 19 -> page 0
                    _current_page = (_current_page + 1) % MAX_PAGES
                    try:
                        from systems import audio as audio_sys
                        audio_sys.play_click(audio_sys.get_global_bank())
                    except:
                        pass
        
        # Process other events only if picker is not active
        if not _party_picker_active:
            if event.type == pygame.MOUSEWHEEL:
                if event.y != 0:
                    # Scroll through pages with mouse wheel (wraps around)
                    if event.y > 0:
                        # Scroll up: wrap around from page 0 to page 19
                        _current_page = (_current_page - 1) % MAX_PAGES
                        try:
                            from systems import audio as audio_sys
                            audio_sys.play_click(audio_sys.get_global_bank())
                        except:
                            pass
                    elif event.y < 0:
                        # Scroll down: wrap around from page 19 to page 0
                        _current_page = (_current_page + 1) % MAX_PAGES
                        try:
                            from systems import audio as audio_sys
                            audio_sys.play_click(audio_sys.get_global_bank())
                        except:
                            pass
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    mx, my = coords.screen_to_logical(pygame.mouse.get_pos())
                    
                    # Check arrow button clicks (wraps around)
                    if left_arrow_rect.collidepoint(mx, my):
                        # Wrap around: page 0 -> page 19
                        _current_page = (_current_page - 1) % MAX_PAGES
                        try:
                            from systems import audio as audio_sys
                            audio_sys.play_click(audio_sys.get_global_bank())
                        except:
                            pass
                        continue
                    elif right_arrow_rect.collidepoint(mx, my):
                        # Wrap around: page 19 -> page 0
                        _current_page = (_current_page + 1) % MAX_PAGES
                        try:
                            from systems import audio as audio_sys
                            audio_sys.play_click(audio_sys.get_global_bank())
                        except:
                            pass
                        continue
                    
                    # Check "Add to Party" button first (if a vessel is selected)
                    if _selected_vessel_index is not None and _selected_vessel_index < len(archives):
                        if add_button_rect.collidepoint(mx, my):
                            print(f"🖱️ 'Add to Party' button clicked! Selected index: {_selected_vessel_index}, Can add: {can_add_to_party}")
                            if can_add_to_party:
                                # Move vessel from archives to party
                                print(f"🔄 Attempting to add vessel index {_selected_vessel_index} to party...")
                                success = _move_archives_vessel_to_party(gs, _selected_vessel_index)
                                if success:
                                    print(f"✅ Successfully moved vessel to party!")
                                    # No autosave - user must manually save via "Save Game" button
                                else:
                                    print(f"⚠️ Failed to move vessel to party")
                            else:
                                print(f"⚠️ Cannot add to party: party is full (6/6)")
                            continue  # Skip other event processing for this click
                        else:
                            # Debug: check if we're close to the button
                            if _selected_vessel_index is not None:
                                dist_x = abs(mx - add_button_rect.centerx)
                                dist_y = abs(my - add_button_rect.centery)
                                if dist_x < 150 and dist_y < 50:
                                    print(f"🔍 Close to button: mx={mx}, my={my}, button_rect={add_button_rect}")
                    
                    # No scrollbar - using page system instead
                    
                    # Check if clicking on a grid square for drag start or selection
                    right_panel_rect_check = pygame.Rect(LEFT_PANEL_WIDTH, HEADER_HEIGHT, RIGHT_PANEL_WIDTH, S.LOGICAL_HEIGHT - HEADER_HEIGHT)
                    stored_box_height_check = 50
                    stored_box_rect_check = pygame.Rect(
                        right_panel_rect_check.x + GRID_PADDING,
                        right_panel_rect_check.y + GRID_PADDING,
                        right_panel_rect_check.width - GRID_PADDING * 2,
                        stored_box_height_check
                    )
                    grid_start_x, grid_start_y = _calculate_grid_position(right_panel_rect_check, stored_box_rect_check)
                    
                    # Calculate which grid cell was clicked
                    row, col, square_rect = _get_grid_cell_from_point(mx, my, grid_start_x, grid_start_y)
                    
                    if row is not None and col is not None:
                        # Found a valid grid cell
                        page_slot_index = row * GRID_COLS + col
                        global_index = _current_page * SLOTS_PER_PAGE + page_slot_index
                        
                        # Check if clicking on a vessel (not empty slot)
                        if global_index < len(archives) and archives[global_index] is not None:
                            # Start dragging this vessel
                            _dragging_vessel = True
                            _drag_source_index = global_index
                            _drag_vessel_data = archives[global_index].copy()
                            
                            # Calculate offset from mouse to center of square
                            square_center_x = square_rect.x + square_rect.width // 2
                            square_center_y = square_rect.y + square_rect.height // 2
                            _drag_offset_x = mx - square_center_x
                            _drag_offset_y = my - square_center_y
                            
                            # Load and cache the sprite for dragging
                            token_name = _drag_vessel_data.get("token_name", "")
                            _drag_sprite = _load_vessel_sprite(token_name, is_token=True)
                            
                            # Clear selection while dragging
                            _selected_vessel_index = None
                        else:
                            # Empty slot - just select it
                            _selected_vessel_index = global_index
            
            elif event.type == pygame.MOUSEMOTION:
                # Update drag position if dragging
                if _dragging_vessel:
                    pass  # Position is calculated in draw function
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    _scrollbar_dragging = False
                    
                    # Handle drag and drop completion
                    if _dragging_vessel and _drag_source_index is not None:
                        mx, my = coords.screen_to_logical(pygame.mouse.get_pos())
                        
                        # Calculate grid position for drop
                        right_panel_rect_drop = pygame.Rect(LEFT_PANEL_WIDTH, HEADER_HEIGHT, RIGHT_PANEL_WIDTH, S.LOGICAL_HEIGHT - HEADER_HEIGHT)
                        stored_box_height_drop = 50
                        stored_box_rect_drop = pygame.Rect(
                            right_panel_rect_drop.x + GRID_PADDING,
                            right_panel_rect_drop.y + GRID_PADDING,
                            right_panel_rect_drop.width - GRID_PADDING * 2,
                            stored_box_height_drop
                        )
                        grid_start_x_drop, grid_start_y_drop = _calculate_grid_position(right_panel_rect_drop, stored_box_rect_drop)
                        
                        # Calculate which grid cell was dropped on
                        row, col, square_rect = _get_grid_cell_from_point(mx, my, grid_start_x_drop, grid_start_y_drop)
                        
                        if row is not None and col is not None:
                            # Found a valid grid cell for drop
                            page_slot_index = row * GRID_COLS + col
                            global_index = _current_page * SLOTS_PER_PAGE + page_slot_index
                            
                            # Only swap if dropping on a different slot
                            if global_index != _drag_source_index:
                                # Ensure archives list is long enough
                                max_slots = MAX_PAGES * SLOTS_PER_PAGE
                                while len(archives) < max_slots:
                                    archives.append(None)
                                
                                # Get the vessel at the drop location (if any)
                                target_vessel = archives[global_index] if global_index < len(archives) else None
                                
                                # Swap vessels
                                archives[_drag_source_index] = target_vessel
                                archives[global_index] = _drag_vessel_data
                                
                                # No autosave - user must manually save via "Save Game" button
                                
                                # Select the new location
                                _selected_vessel_index = global_index
                            else:
                                # Dropped on same slot - just select it
                                _selected_vessel_index = global_index
                        else:
                            # Dropped outside grid - cancel drag (vessel stays in original position)
                            pass
                        
                        # Clear drag state
                        _dragging_vessel = False
                        _drag_source_index = None
                        _drag_vessel_data = None
                        _drag_offset_x = 0
                        _drag_offset_y = 0
                        _drag_sprite = None
    
    return next_mode


def _get_scrollbar_thumb_rect(right_panel_rect, total_rows, max_scroll):
    """Calculate the scrollbar thumb rectangle."""
    if max_scroll <= 0:
        return None
    
    scrollbar_x = right_panel_rect.right - 20
    scrollbar_width = 12
    scrollbar_y = right_panel_rect.y + GRID_PADDING
    scrollbar_height = right_panel_rect.height - GRID_PADDING * 2
    
    visible_height = scrollbar_height
    content_height = max(1, total_rows * (GRID_SQUARE_SIZE + GRID_SPACING))
    thumb_height = max(20, int(visible_height * (visible_height / content_height)))
    
    if _scroll_offset > 0:
        thumb_y = scrollbar_y + int((_scroll_offset / max_scroll) * (scrollbar_height - thumb_height))
    else:
        thumb_y = scrollbar_y
    
    return pygame.Rect(scrollbar_x, thumb_y, scrollbar_width, thumb_height)


def draw(screen, gs, dt):
    """Draw the Archives screen with polished, clean design."""
    global _selected_vessel_index
    
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    # Always get fresh archives list to show immediate updates
    archives = _get_archives_list(gs)
    
    # Clear entire screen first
    screen.fill(COLOR_BG)
    screen.set_clip(None)
    
    # ===================== HEADER =====================
    header_rect = pygame.Rect(0, 0, sw, HEADER_HEIGHT)
    
    # Header shadow for depth
    shadow_rect = header_rect.move(0, 3)
    pygame.draw.rect(screen, COLOR_HEADER_SHADOW, shadow_rect)
    
    # Header background
    pygame.draw.rect(screen, COLOR_HEADER_BG, header_rect)
    
    # Header borders
    pygame.draw.rect(screen, COLOR_PANEL_BORDER_OUTER, header_rect, 2)
    inner_header = header_rect.inflate(-4, -4)
    pygame.draw.rect(screen, COLOR_PANEL_BORDER_INNER, inner_header, 1)
    
    # Header text with glow
    title_font = _get_font(52, bold=True)
    title_text = "THE ARCHIVES"
    title_surf = title_font.render(title_text, True, COLOR_HEADER_TEXT)
    title_rect = title_surf.get_rect(center=(sw // 2, HEADER_HEIGHT // 2))
    
    # Draw glow
    for offset in range(-3, 4):
        glow_surf = title_font.render(title_text, True, COLOR_HEADER_GLOW)
        glow_surf.set_alpha(40)
        screen.blit(glow_surf, (title_rect.x + offset, title_rect.y))
        screen.blit(glow_surf, (title_rect.x, title_rect.y + offset))
    
    screen.blit(title_surf, title_rect)
    
    # ===================== LEFT PANEL (Vessel Details) =====================
    left_panel_rect = pygame.Rect(0, HEADER_HEIGHT, LEFT_PANEL_WIDTH, sh - HEADER_HEIGHT)
    _draw_panel_with_depth(screen, left_panel_rect, COLOR_PANEL_BG, COLOR_PANEL_BORDER_OUTER, COLOR_PANEL_BORDER_INNER)
    
    # Draw vessel details if one is selected and exists
    if _selected_vessel_index is not None and _selected_vessel_index < len(archives) and archives[_selected_vessel_index] is not None:
        archive_vessel = archives[_selected_vessel_index]
        vessel_name = archive_vessel["vessel_name"]
        stats = archive_vessel.get("stats", {})
        
        # Load vessel sprite
        sprite = _load_vessel_sprite(vessel_name, is_token=False)
        
        # Vessel sprite area with polished frame
        sprite_area_size = 350
        sprite_area_margin = 30
        sprite_area_rect = pygame.Rect(
            left_panel_rect.centerx - sprite_area_size // 2,
            left_panel_rect.y + sprite_area_margin,
            sprite_area_size,
            sprite_area_size
        )
        
        # Draw sprite frame with depth
        _draw_info_box_polished(screen, sprite_area_rect)
        
        if sprite:
            # Scale sprite to fit
            padding = 20
            max_w = sprite_area_size - (padding * 2)
            max_h = sprite_area_size - (padding * 2)
            spr_w, spr_h = sprite.get_size()
            scale_x = max_w / max(spr_w, 1)
            scale_y = max_h / max(spr_h, 1)
            scale = min(scale_x, scale_y)
            scaled_w = int(spr_w * scale)
            scaled_h = int(spr_h * scale)
            scaled_sprite = pygame.transform.scale(sprite, (scaled_w, scaled_h))
            spr_x = sprite_area_rect.x + (sprite_area_size - scaled_w) // 2
            spr_y = sprite_area_rect.y + (sprite_area_size - scaled_h) // 2
            screen.blit(scaled_sprite, (spr_x, spr_y))
        
        # Vessel name with glow - centered with sprite area
        name_font = _get_font(38, bold=True)
        from systems.name_generator import generate_vessel_name
        token_name = archive_vessel.get("token_name", vessel_name)
        name_text = generate_vessel_name(token_name)
        
        # Center the name with the sprite area (not the entire left panel)
        name_surf = name_font.render(name_text, True, COLOR_TEXT_HIGHLIGHT)
        name_rect = name_surf.get_rect(center=(sprite_area_rect.centerx, sprite_area_rect.bottom + 30))
        
        # Draw glow first
        _draw_text_with_glow(screen, name_text, name_font, (name_rect.x, name_rect.y), COLOR_TEXT_HIGHLIGHT, COLOR_HEADER_GLOW, 3)
        
        # "Add to Party" button (polished) - centered with sprite area
        add_button_width = 240
        add_button_height = 50
        add_button_x = sprite_area_rect.centerx - add_button_width // 2  # Center with sprite area
        add_button_y = name_rect.bottom + 20
        
        add_button_rect = pygame.Rect(add_button_x, add_button_y, add_button_width, add_button_height)
        
        # Check if party has space
        party_slots_check = getattr(gs, "party_slots_names", [None] * 6)
        party_count_check = sum(1 for slot in party_slots_check if slot)
        can_add_to_party = party_count_check < 6
        
        # Check if hovered
        mx, my = coords.screen_to_logical(pygame.mouse.get_pos())
        is_add_hovered = add_button_rect.collidepoint(mx, my) and can_add_to_party
        
        # Draw button
        add_button_font = _get_font(22, bold=True)
        if can_add_to_party:
            add_button_text = "Add to Party"
        else:
            add_button_text = "Party Full"
        _draw_button_polished(screen, add_button_rect, add_button_text, add_button_font, can_add_to_party, is_add_hovered)
        
        # Store button rect for click handling (we'll use sprite_area_rect.centerx for consistency)
        # The handle function will calculate the same position
        
        # Stats info box (polished)
        info_box_y = add_button_rect.bottom + 20
        info_box_width = left_panel_rect.width - 60
        num_stats = 11
        line_height = 32
        info_box_height = num_stats * line_height + 50
        
        info_box_rect = pygame.Rect(
            left_panel_rect.x + 30,
            info_box_y,
            info_box_width,
            info_box_height
        )
        _draw_info_box_polished(screen, info_box_rect)
        
        # Draw stats
        stat_font = _get_font(22)
        y_offset = info_box_rect.y + 25
        line_height = 32
        
        # Class
        class_name = stats.get("class_name", "Unknown")
        class_text = f"Class: {class_name}"
        class_surf = stat_font.render(class_text, True, COLOR_TEXT)
        screen.blit(class_surf, (info_box_rect.x + 20, y_offset))
        y_offset += line_height
        
        # Level
        level = stats.get("level", 1)
        level_text = f"Level: {level}"
        level_surf = stat_font.render(level_text, True, COLOR_TEXT)
        screen.blit(level_surf, (info_box_rect.x + 20, y_offset))
        y_offset += line_height
        
        # XP
        xp = stats.get("xp", 0)
        xp_text = f"XP: {xp}"
        xp_surf = stat_font.render(xp_text, True, COLOR_TEXT)
        screen.blit(xp_surf, (info_box_rect.x + 20, y_offset))
        y_offset += line_height
        
        # HP
        hp = stats.get("hp", 10)
        max_hp = stats.get("max_hp", 10)
        hp_text = f"HP: {hp} / {max_hp}"
        hp_surf = stat_font.render(hp_text, True, COLOR_TEXT)
        screen.blit(hp_surf, (info_box_rect.x + 20, y_offset))
        y_offset += line_height
        
        # AC
        ac = stats.get("ac", 10)
        ac_text = f"AC: {ac}"
        ac_surf = stat_font.render(ac_text, True, COLOR_TEXT)
        screen.blit(ac_surf, (info_box_rect.x + 20, y_offset))
        y_offset += line_height
        
        # Abilities
        ability_names = {
            "str": "Strength",
            "dex": "Dexterity",
            "con": "Constitution",
            "int": "Intelligence",
            "wis": "Wisdom",
            "cha": "Charisma",
        }
        
        for abbr, full_name in ability_names.items():
            ability_score = stats.get(abbr, 10)
            ability_text = f"{full_name}: {ability_score}"
            ability_surf = stat_font.render(ability_text, True, COLOR_TEXT)
            screen.blit(ability_surf, (info_box_rect.x + 20, y_offset))
            y_offset += line_height
    
    # ===================== RIGHT PANEL (Storage Grid) =====================
    right_panel_rect = pygame.Rect(LEFT_PANEL_WIDTH, HEADER_HEIGHT, RIGHT_PANEL_WIDTH, sh - HEADER_HEIGHT)
    _draw_panel_with_depth(screen, right_panel_rect, COLOR_PANEL_BG, COLOR_PANEL_BORDER_OUTER, COLOR_PANEL_BORDER_INNER)
    
    # "Stored" counter box (polished, fixed at top)
    stored_box_height = 50
    stored_box_rect = pygame.Rect(
        right_panel_rect.x + GRID_PADDING,
        right_panel_rect.y + GRID_PADDING,
        right_panel_rect.width - GRID_PADDING * 2,
        stored_box_height
    )
    _draw_info_box_polished(screen, stored_box_rect)
    
    # "Stored" text (count only actual vessels, not None entries)
    stored_font = _get_font(24, bold=True)
    stored_count = sum(1 for vessel in archives if vessel is not None)
    stored_text = f"Stored: {stored_count}"
    stored_surf = stored_font.render(stored_text, True, COLOR_TEXT_HIGHLIGHT)
    stored_text_rect = stored_surf.get_rect(center=stored_box_rect.center)
    screen.blit(stored_surf, stored_text_rect)
    
    # Calculate centered grid position
    grid_start_x, grid_start_y = _calculate_grid_position(right_panel_rect, stored_box_rect)
    
    # Calculate current page's vessels (always show all 48 slots per page)
    page_start_index = _current_page * SLOTS_PER_PAGE
    
    # Draw grid squares for current page (always draw all SLOTS_PER_PAGE slots, even if empty)
    for page_slot in range(SLOTS_PER_PAGE):
        row = page_slot // GRID_COLS
        col = page_slot % GRID_COLS
        
        square_x = grid_start_x + col * (GRID_SQUARE_SIZE + GRID_SPACING)
        square_y = grid_start_y + row * (GRID_SQUARE_SIZE + GRID_SPACING)
        square_rect = pygame.Rect(square_x, square_y, GRID_SQUARE_SIZE, GRID_SQUARE_SIZE)
        
        # Calculate global index
        global_index = page_start_index + page_slot
        
        # Check if hovered or selected
        mx, my = coords.screen_to_logical(pygame.mouse.get_pos())
        hover_row, hover_col, hover_rect = _get_grid_cell_from_point(mx, my, grid_start_x, grid_start_y)
        is_hovered = (hover_row == row and hover_col == col)
        is_selected = (_selected_vessel_index == global_index)
        
        # Check if this is the source slot being dragged (hide sprite)
        is_drag_source = (_dragging_vessel and global_index == _drag_source_index)
        
        # Check if this is a valid drop target when dragging
        is_drop_target = False
        if _dragging_vessel and global_index != _drag_source_index:
            # Check if mouse is over this cell
            is_drop_target = (hover_row == row and hover_col == col)
        
        # Check if this slot has a vessel (can be empty if beyond archives length)
        if global_index < len(archives) and archives[global_index] is not None:
            # Slot has a vessel
            archive_vessel = archives[global_index]
            
            # Draw square with polish
            if is_drop_target:
                # Valid drop target - highlight with special color
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_HOVER, square_rect)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_GLOW, square_rect, 3)
            elif is_selected:
                # Selected: draw glow effect
                for offset in range(-2, 3):
                    glow_rect = square_rect.inflate(offset * 2, offset * 2)
                    pygame.draw.rect(screen, COLOR_GRID_SQUARE_GLOW, glow_rect, 1)
                    if offset != 0:
                        # Make glow fade
                        glow_surf = pygame.Surface(glow_rect.size, pygame.SRCALPHA)
                        pygame.draw.rect(glow_surf, (*COLOR_GRID_SQUARE_GLOW, 30), glow_surf.get_rect(), 1)
                        screen.blit(glow_surf, glow_rect.topleft)
                
                # Selected square
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_HOVER, square_rect)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_SELECTED, square_rect, 3)
            elif is_hovered and not _dragging_vessel:
                # Hovered square (only if not dragging)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_HOVER, square_rect)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_BORDER, square_rect, 2)
            else:
                # Normal square with shadow
                shadow_rect = square_rect.move(1, 1)
                pygame.draw.rect(screen, COLOR_INFO_SHADOW, shadow_rect)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE, square_rect)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_BORDER, square_rect, 1)
            
            # Load and draw token (skip if this is the drag source)
            if not is_drag_source:
                token_name = archive_vessel.get("token_name", "")
                token_sprite = _load_vessel_sprite(token_name, is_token=True)
                if token_sprite:
                    # Scale token to fit square
                    token_w, token_h = token_sprite.get_size()
                    scale = min((GRID_SQUARE_SIZE - 8) / max(token_w, 1), (GRID_SQUARE_SIZE - 8) / max(token_h, 1))
                    scaled_w = int(token_w * scale)
                    scaled_h = int(token_h * scale)
                    scaled_token = pygame.transform.scale(token_sprite, (scaled_w, scaled_h))
                    token_x = square_rect.x + (GRID_SQUARE_SIZE - scaled_w) // 2
                    token_y = square_rect.y + (GRID_SQUARE_SIZE - scaled_h) // 2
                    screen.blit(scaled_token, (token_x, token_y))
            else:
                # Draw semi-transparent placeholder for drag source
                shadow_rect = square_rect.move(1, 1)
                pygame.draw.rect(screen, COLOR_INFO_SHADOW, shadow_rect)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE, square_rect)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_BORDER, square_rect, 1)
                # Draw faded vessel sprite
                token_name = archive_vessel.get("token_name", "")
                token_sprite = _load_vessel_sprite(token_name, is_token=True)
                if token_sprite:
                    token_w, token_h = token_sprite.get_size()
                    scale = min((GRID_SQUARE_SIZE - 8) / max(token_w, 1), (GRID_SQUARE_SIZE - 8) / max(token_h, 1))
                    scaled_w = int(token_w * scale)
                    scaled_h = int(token_h * scale)
                    scaled_token = pygame.transform.scale(token_sprite, (scaled_w, scaled_h))
                    scaled_token.set_alpha(100)  # Make semi-transparent
                    token_x = square_rect.x + (GRID_SQUARE_SIZE - scaled_w) // 2
                    token_y = square_rect.y + (GRID_SQUARE_SIZE - scaled_h) // 2
                    screen.blit(scaled_token, (token_x, token_y))
        else:
            # Empty slot - draw empty square (always show all slots, even if empty)
            if is_drop_target:
                # Valid drop target - highlight
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_HOVER, square_rect)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_GLOW, square_rect, 3)
            elif is_hovered and not _dragging_vessel:
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_HOVER, square_rect)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_BORDER, square_rect, 2)
            else:
                shadow_rect = square_rect.move(1, 1)
                pygame.draw.rect(screen, COLOR_INFO_SHADOW, shadow_rect)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE, square_rect)
                pygame.draw.rect(screen, COLOR_GRID_SQUARE_BORDER, square_rect, 1)
    
    # Draw page navigation arrows (positioned below centered grid)
    grid_total_height = GRID_ROWS * GRID_SQUARE_SIZE + (GRID_ROWS - 1) * GRID_SPACING
    grid_bottom = grid_start_y + grid_total_height
    arrow_size = 40
    arrow_y = grid_bottom + 20  # Position arrows below the grid with some spacing
    arrow_tip_size = 12
    
    # Calculate page text width to position arrows relative to it
    page_font_temp = _get_font(20)
    page_text_temp = f"Page {_current_page + 1} / {MAX_PAGES}"
    page_text_width = page_font_temp.size(page_text_temp)[0]
    
    left_arrow_x = right_panel_rect.centerx - (page_text_width // 2) - 50
    right_arrow_x = right_panel_rect.centerx + (page_text_width // 2) + 50  # Move further right
    
    # Always 20 pages
    total_pages = MAX_PAGES
    max_valid_page = MAX_PAGES - 1
    
    # Left arrow (always enabled, wraps around)
    left_arrow_rect = pygame.Rect(left_arrow_x - arrow_size // 2, arrow_y - arrow_size // 2, arrow_size, arrow_size)
    mx, my = coords.screen_to_logical(pygame.mouse.get_pos())
    left_arrow_color = COLOR_TEXT_HIGHLIGHT if left_arrow_rect.collidepoint(mx, my) else COLOR_TEXT_DIM
    # Always draw left arrow (wraps around)
    arrow_points_left = [
        (left_arrow_x, arrow_y),
        (left_arrow_x + arrow_tip_size, arrow_y - arrow_tip_size),
        (left_arrow_x + arrow_tip_size, arrow_y + arrow_tip_size),
    ]
    pygame.draw.polygon(screen, left_arrow_color, arrow_points_left)
    
    # Right arrow (always enabled, wraps around)
    right_arrow_rect = pygame.Rect(right_arrow_x - arrow_size // 2, arrow_y - arrow_size // 2, arrow_size, arrow_size)
    right_arrow_color = COLOR_TEXT_HIGHLIGHT if right_arrow_rect.collidepoint(mx, my) else COLOR_TEXT_DIM
    # Always draw right arrow (wraps around)
    arrow_points_right = [
        (right_arrow_x, arrow_y),
        (right_arrow_x - arrow_tip_size, arrow_y - arrow_tip_size),
        (right_arrow_x - arrow_tip_size, arrow_y + arrow_tip_size),
    ]
    pygame.draw.polygon(screen, right_arrow_color, arrow_points_right)
    
    # Page number indicator (always shows X / 20)
    page_font = _get_font(20)
    page_text = f"Page {_current_page + 1} / {MAX_PAGES}"
    page_surf = page_font.render(page_text, True, COLOR_TEXT)
    page_rect = page_surf.get_rect(center=(right_panel_rect.centerx, arrow_y))
    screen.blit(page_surf, page_rect)
    
    # ===================== BOTTOM INFO =====================
    # Party count
    party_slots = getattr(gs, "party_slots_names", [None] * 6)
    party_count = sum(1 for slot in party_slots if slot)
    
    party_font = _get_font(24, bold=True)
    party_text = f"Party: {party_count}"
    party_surf = party_font.render(party_text, True, COLOR_TEXT_HIGHLIGHT)
    party_rect = party_surf.get_rect(bottomleft=(20, sh - 20))
    screen.blit(party_surf, party_rect)
    
    # "Store Vessel" button (polished)
    button_width = 220
    button_height = 50
    button_x = sw - button_width - 20
    button_y = sh - button_height - 20
    
    button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
    
    # Check if button should be disabled
    party_slots_draw = getattr(gs, "party_slots_names", [None] * 6)
    party_count_draw = sum(1 for slot in party_slots_draw if slot)
    can_store_vessel = party_count_draw > 1
    
    # Check if hovered
    mx, my = coords.screen_to_logical(pygame.mouse.get_pos())
    is_hovered = button_rect.collidepoint(mx, my) and can_store_vessel and not _party_picker_active
    
    # Draw button
    button_font = _get_font(20, bold=True)
    if _party_picker_active:
        button_text = "Cancel"
    elif can_store_vessel:
        button_text = "Store Vessel"
    else:
        button_text = "Store Vessel\n(Min 2 required)"
    
    # Handle multi-line text
    if "\n" in button_text:
        lines = button_text.split("\n")
        # Draw button background
        _draw_button_polished(screen, button_rect, "", button_font, can_store_vessel, False)
        # Draw text lines
        text_surfs = [button_font.render(line, True, COLOR_BUTTON_TEXT if can_store_vessel else COLOR_TEXT_DIM) for line in lines]
        total_height = sum(surf.get_height() for surf in text_surfs) + (len(lines) - 1) * 4
        y_offset = button_rect.centery - total_height // 2
        for surf in text_surfs:
            text_rect = surf.get_rect(centerx=button_rect.centerx, y=y_offset)
            screen.blit(surf, text_rect)
            y_offset += surf.get_height() + 4
    else:
        _draw_button_polished(screen, button_rect, button_text, button_font, can_store_vessel and not _party_picker_active, is_hovered)
    
    # Exit hint (subtle)
    exit_font = _get_font(18)
    exit_text = "Press ESC to exit"
    exit_surf = exit_font.render(exit_text, True, COLOR_TEXT_DIM)
    exit_rect = exit_surf.get_rect(centery=button_rect.centery, right=button_rect.x - 15)
    screen.blit(exit_surf, exit_rect)
    
    # ===================== DRAG AND DROP =====================
    # Draw dragged vessel sprite following the mouse cursor
    if _dragging_vessel and _drag_sprite is not None:
        mx, my = coords.screen_to_logical(pygame.mouse.get_pos())
        
        # Scale sprite to match grid square size
        sprite_w, sprite_h = _drag_sprite.get_size()
        scale = min((GRID_SQUARE_SIZE - 8) / max(sprite_w, 1), (GRID_SQUARE_SIZE - 8) / max(sprite_h, 1))
        scaled_w = int(sprite_w * scale)
        scaled_h = int(sprite_h * scale)
        scaled_sprite = pygame.transform.scale(_drag_sprite, (scaled_w, scaled_h))
        
        # Draw sprite centered on mouse position (accounting for drag offset)
        sprite_x = mx - scaled_w // 2 - _drag_offset_x
        sprite_y = my - scaled_h // 2 - _drag_offset_y
        
        # Draw with slight transparency and shadow for better visibility
        shadow_sprite = scaled_sprite.copy()
        shadow_sprite.set_alpha(100)
        screen.blit(shadow_sprite, (sprite_x + 2, sprite_y + 2))
        
        # Draw main sprite
        screen.blit(scaled_sprite, (sprite_x, sprite_y))
