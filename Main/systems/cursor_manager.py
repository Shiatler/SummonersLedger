# ============================================================
# systems/cursor_manager.py — Custom Cursor Management
# Manages custom cursor appearance and click state
# Uses manual cursor drawing since pygame doesn't handle .cur files well
# ============================================================

import os
import pygame
import settings as S

# Cursor state
_normal_cursor_surface = None
_click_cursor_surface = None
_current_cursor_type = "normal"  # "normal" or "click"
_cursors_loaded = False
_hotspot_normal = (0, 0)
_hotspot_click = (0, 0)

def _load_cur_as_surface(cur_path):
    """Load .cur file and convert to pygame Surface for manual drawing."""
    try:
        # Try using Windows API to extract cursor as bitmap
        try:
            import ctypes
            from ctypes import wintypes
            import struct
            
            # Windows API constants
            LR_LOADFROMFILE = 0x0010
            IMAGE_CURSOR = 2
            
            # Load cursor using Windows API
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            
            abs_path = os.path.abspath(cur_path)
            hcursor = user32.LoadImageW(
                None,
                abs_path,
                IMAGE_CURSOR,
                0, 0,
                LR_LOADFROMFILE
            )
            
            if hcursor:
                # Try to get cursor bitmap using Windows API
                # This is complex, so we'll fall back to reading the file directly
                pass
        except Exception as e:
            pass
        
        # Method: Read .cur file format directly
        # .cur files are similar to .ico files - they contain bitmap data
        try:
            with open(cur_path, 'rb') as f:
                # Read file header
                # First 2 bytes: Reserved (must be 0)
                reserved = struct.unpack('<H', f.read(2))[0]
                # Next 2 bytes: Type (1 = ICO, 2 = CUR)
                file_type = struct.unpack('<H', f.read(2))[0]
                # Next 2 bytes: Number of images
                num_images = struct.unpack('<H', f.read(2))[0]
                
                if file_type != 2:  # Not a CUR file
                    raise ValueError(f"Not a valid .cur file (type: {file_type})")
                
                # Read image directory entry (first image)
                # Width (1 byte, 0 = 256)
                width = struct.unpack('<B', f.read(1))[0]
                if width == 0:
                    width = 256
                # Height (1 byte, 0 = 256)
                height = struct.unpack('<B', f.read(1))[0]
                if height == 0:
                    height = 256
                # Color palette (1 byte, usually 0 for 32-bit)
                colors = struct.unpack('<B', f.read(1))[0]
                # Reserved (1 byte)
                reserved = struct.unpack('<B', f.read(1))[0]
                # Hotspot X (2 bytes)
                hotspot_x = struct.unpack('<H', f.read(2))[0]
                # Hotspot Y (2 bytes)
                hotspot_y = struct.unpack('<H', f.read(2))[0]
                # Size of image data (4 bytes)
                image_size = struct.unpack('<I', f.read(4))[0]
                # Offset to image data (4 bytes)
                image_offset = struct.unpack('<I', f.read(4))[0]
                
                hotspot = (hotspot_x, hotspot_y)
                
                # Read image data
                f.seek(image_offset)
                image_data = f.read(image_size)
                
                # Try to load as PNG/ICO using PIL (the image data might be in ICO format)
                try:
                    from PIL import Image
                    import io
                    
                    # Create a BytesIO object from the image data
                    image_stream = io.BytesIO(image_data)
                    pil_image = Image.open(image_stream)
                    
                    # Convert to RGBA
                    if pil_image.mode != 'RGBA':
                        pil_image = pil_image.convert('RGBA')
                    
                    # Get actual size (might differ from header)
                    actual_width, actual_height = pil_image.size
                    
                    # Convert to pygame surface
                    data = pil_image.tobytes()
                    mode = pil_image.mode
                    
                    try:
                        cursor_surface = pygame.image.frombytes(data, (actual_width, actual_height), mode).convert_alpha()
                    except:
                        cursor_surface = pygame.image.fromstring(data, (actual_width, actual_height), mode).convert_alpha()
                    
                    return cursor_surface, hotspot
                    
                except Exception as e:
                    print(f"⚠️ Failed to parse image data from .cur file: {e}")
                    # Fallback: try loading the whole file as an image
                    try:
                        from PIL import Image
                        pil_image = Image.open(cur_path)
                        if pil_image.mode != 'RGBA':
                            pil_image = pil_image.convert('RGBA')
                        size = pil_image.size
                        data = pil_image.tobytes()
                        try:
                            cursor_surface = pygame.image.frombytes(data, size, pil_image.mode).convert_alpha()
                        except:
                            cursor_surface = pygame.image.fromstring(data, size, pil_image.mode).convert_alpha()
                        return cursor_surface, hotspot
                    except Exception as e2:
                        print(f"⚠️ Fallback PIL load also failed: {e2}")
                        return None, (0, 0)
                        
        except Exception as e:
            print(f"⚠️ Failed to read .cur file format: {e}")
            import traceback
            traceback.print_exc()
            # Final fallback: try PIL on the whole file
            try:
                from PIL import Image
                pil_image = Image.open(cur_path)
                if pil_image.mode != 'RGBA':
                    pil_image = pil_image.convert('RGBA')
                size = pil_image.size
                data = pil_image.tobytes()
                try:
                    cursor_surface = pygame.image.frombytes(data, size, pil_image.mode).convert_alpha()
                except:
                    cursor_surface = pygame.image.fromstring(data, size, pil_image.mode).convert_alpha()
                return cursor_surface, (0, 0)
            except:
                return None, (0, 0)
            
    except Exception as e:
        print(f"⚠️ Failed to load cursor file: {e}")
        import traceback
        traceback.print_exc()
        return None, (0, 0)

def load_cursors():
    """Load custom cursor files as surfaces for manual drawing."""
    global _normal_cursor_surface, _click_cursor_surface, _cursors_loaded
    global _hotspot_normal, _hotspot_click
    
    if _cursors_loaded:
        return
    
    cursor_dir = os.path.join("Assets", "Cursor")
    
    # Cursor scale factor (make cursor smaller)
    CURSOR_SCALE = 0.3  # Scale to 30% of original size
    
    # Load normal cursor
    normal_path = os.path.join(cursor_dir, "Cursor.cur")
    if os.path.exists(normal_path):
        _normal_cursor_surface, _hotspot_normal = _load_cur_as_surface(normal_path)
        if _normal_cursor_surface:
            # Scale down the cursor
            original_size = _normal_cursor_surface.get_size()
            new_size = (int(original_size[0] * CURSOR_SCALE), int(original_size[1] * CURSOR_SCALE))
            _normal_cursor_surface = pygame.transform.smoothscale(_normal_cursor_surface, new_size)
            # Scale hotspot proportionally
            _hotspot_normal = (int(_hotspot_normal[0] * CURSOR_SCALE), int(_hotspot_normal[1] * CURSOR_SCALE))
            print(f"✅ Loaded normal cursor surface from {normal_path} (original size: {original_size}, scaled to: {new_size}, hotspot: {_hotspot_normal})")
        else:
            print(f"⚠️ Failed to load normal cursor from {normal_path}")
            _normal_cursor_surface = None
    else:
        print(f"⚠️ Cursor file not found: {normal_path}")
        _normal_cursor_surface = None
    
    # Load click cursor
    click_path = os.path.join(cursor_dir, "Clicker.cur")
    if os.path.exists(click_path):
        _click_cursor_surface, _hotspot_click = _load_cur_as_surface(click_path)
        if _click_cursor_surface:
            # Scale down the cursor
            original_size = _click_cursor_surface.get_size()
            new_size = (int(original_size[0] * CURSOR_SCALE), int(original_size[1] * CURSOR_SCALE))
            _click_cursor_surface = pygame.transform.smoothscale(_click_cursor_surface, new_size)
            # Scale hotspot proportionally
            _hotspot_click = (int(_hotspot_click[0] * CURSOR_SCALE), int(_hotspot_click[1] * CURSOR_SCALE))
            print(f"✅ Loaded click cursor surface from {click_path} (original size: {original_size}, scaled to: {new_size}, hotspot: {_hotspot_click})")
        else:
            print(f"⚠️ Failed to load click cursor from {click_path}")
            _click_cursor_surface = None
    else:
        print(f"⚠️ Click cursor file not found: {click_path}")
        _click_cursor_surface = None
    
    # Hide system cursor if we have custom cursors
    if _normal_cursor_surface or _click_cursor_surface:
        pygame.mouse.set_visible(False)
        print(f"✅ Hidden system cursor - using custom cursor drawing")
    
    _cursors_loaded = True
    print(f"✅ Cursors loaded successfully")


def set_normal_cursor():
    """Set the cursor to normal state."""
    global _current_cursor_type
    _current_cursor_type = "normal"


def set_click_cursor():
    """Set the cursor to click state."""
    global _current_cursor_type
    _current_cursor_type = "click"


def handle_mouse_event(event):
    """Handle mouse events to change cursor state."""
    if event.type == pygame.MOUSEBUTTONDOWN:
        if event.button == 1:  # Left mouse button
            set_click_cursor()
    elif event.type == pygame.MOUSEBUTTONUP:
        if event.button == 1:  # Left mouse button
            set_normal_cursor()


def _is_hovering_clickable(mouse_pos, gs=None, mode=None):
    """
    Check if the mouse is currently hovering over any clickable UI element.
    Returns True if mouse is over a clickable element, False otherwise.
    
    Optimized with early returns and mode-specific checks.
    """
    try:
        from systems import coords
        
        # Convert mouse position to logical coordinates for UI checks
        logical_pos = coords.screen_to_logical(mouse_pos)
        mx, my = logical_pos
        
        # Pre-compute mode string and mode checks once (optimization)
        mode_str = str(mode) if mode else ""
        is_game_mode = (mode == S.MODE_GAME or (mode and "GAME" in mode_str))
        is_battle_mode = (mode and ("BATTLE" in mode_str or "WILD_VESSEL" in mode_str))
        
        # OPTIMIZATION: Check most common/relevant things first (early returns)
        # Priority order: Open popups > HUD buttons > Mode-specific elements
        
        # 1. Check open popups first (most common interaction when open)
        try:
            from combat.btn import bag_action
            if bag_action.is_open():
                if bag_action.is_hovering_popup_element(logical_pos):
                    return True
        except:
            pass
        
        try:
            from systems import buff_popup
            if buff_popup.is_active():
                # Quick card rect check
                try:
                    state = getattr(buff_popup, '_STATE', None)
                    if state and 'cards' in state:
                        cards = state['cards']
                        if cards:
                            card_width = 280
                            card_height = 400
                            card_spacing = 40
                            num_cards = len(cards)
                            if num_cards == 1:
                                start_x = (S.LOGICAL_WIDTH - card_width) // 2
                            else:
                                total_width = (card_width * num_cards) + (card_spacing * (num_cards - 1))
                                start_x = (S.LOGICAL_WIDTH - total_width) // 2
                            card_y = S.LOGICAL_HEIGHT // 2 - card_height // 2
                            for i in range(num_cards):
                                card_x = start_x + i * (card_width + card_spacing) if num_cards > 1 else start_x
                                if (card_x <= mx <= card_x + card_width and 
                                    card_y <= my <= card_y + card_height):
                                    return True
                except:
                    pass
        except:
            pass
        
        try:
            from systems import hells_deck_popup
            if hells_deck_popup.is_open():
                if hasattr(hells_deck_popup, '_LEFT_ARROW_RECT') and hells_deck_popup._LEFT_ARROW_RECT:
                    if hells_deck_popup._LEFT_ARROW_RECT.collidepoint(logical_pos):
                        return True
                if hasattr(hells_deck_popup, '_RIGHT_ARROW_RECT') and hells_deck_popup._RIGHT_ARROW_RECT:
                    if hells_deck_popup._RIGHT_ARROW_RECT.collidepoint(logical_pos):
                        return True
        except:
            pass
        
        try:
            from screens import party_manager
            if party_manager.is_open():
                if hasattr(party_manager, '_ITEM_RECTS'):
                    item_rects = party_manager._ITEM_RECTS
                    for rect in item_rects:
                        if rect and rect.collidepoint(logical_pos):
                            return True
        except:
            pass
        
        try:
            from screens import ledger
            if ledger.is_open():
                if hasattr(ledger, '_last_layout'):
                    layout = ledger._last_layout
                    left = layout.get('left')
                    right = layout.get('right')
                    if left and left.collidepoint(logical_pos):
                        return True
                    if right and right.collidepoint(logical_pos):
                        return True
        except:
            pass
        
        try:
            from systems import rest_popup
            if rest_popup.is_open():
                # Check rest popup buttons (long rest and short rest)
                if hasattr(rest_popup, '_LONG_BTN_RECT') and rest_popup._LONG_BTN_RECT:
                    if rest_popup._LONG_BTN_RECT.collidepoint(logical_pos):
                        return True
                if hasattr(rest_popup, '_SHORT_BTN_RECT') and rest_popup._SHORT_BTN_RECT:
                    if rest_popup._SHORT_BTN_RECT.collidepoint(logical_pos):
                        return True
        except:
            pass
        
        # 2. Check HUD buttons (always visible in game mode)
        try:
            from systems import hud_buttons
            if hud_buttons.is_hovering_any_button(logical_pos):
                return True
        except:
            pass
        
        # 3. Check HUD vessel slots (only in game mode)
        if is_game_mode:
            try:
                from systems import party_ui
                if hasattr(party_ui, '_slot_rects'):
                    slot_rects = party_ui._slot_rects
                    if gs and slot_rects:
                        party_slots = getattr(gs, "party_slots", [None] * 6)
                        party_slots_names = getattr(gs, "party_slots_names", [None] * 6)
                        for i, rect in enumerate(slot_rects):
                            if rect and rect.collidepoint(logical_pos):
                                if (i < len(party_slots) and party_slots[i] is not None) or \
                                   (i < len(party_slots_names) and party_slots_names[i] is not None):
                                    return True
            except:
                pass
        
        # ==================== MENU SCREEN ====================
        if mode == S.MODE_MENU or (mode and "MENU" in mode_str):
            try:
                if gs and hasattr(gs, '_menu_buttons'):
                    for button in gs._menu_buttons:
                        if button.enabled and button.rect.collidepoint(logical_pos):
                            return True
            except:
                pass
        
        # ==================== CHARACTER SELECT ====================
        if mode and "CHAR_SELECT" in mode_str:
            try:
                if gs:
                    # Check male/female buttons
                    if hasattr(gs, '_char_buttons') and gs._char_buttons:
                        for btn in gs._char_buttons:
                            if btn and btn.rect.collidepoint(logical_pos):
                                return True
            except:
                pass
        
        # ==================== PAUSE SCREEN ====================
        if mode and "PAUSE" in mode_str:
            try:
                if gs and hasattr(gs, '_pause_buttons'):
                    for button in gs._pause_buttons:
                        if button.rect.collidepoint(logical_pos):
                            return True
            except:
                pass
        
        # ==================== SETTINGS SCREEN ====================
        if mode and "SETTINGS" in mode_str:
            try:
                from screens import settings_screen
                # Check dropdown
                if hasattr(settings_screen, '_dropdown_rect') and settings_screen._dropdown_rect:
                    if settings_screen._dropdown_rect.collidepoint(logical_pos):
                        return True
                # Check dropdown menu options (if open)
                if hasattr(settings_screen, '_dropdown_open') and settings_screen._dropdown_open:
                    if gs and hasattr(gs, '_dropdown_menu_rect') and gs._dropdown_menu_rect:
                        menu_rect = gs._dropdown_menu_rect
                        if menu_rect.collidepoint(logical_pos):
                            return True
                # Check sliders (music and sfx bars)
                if gs and hasattr(gs, '_settings_bars'):
                    bars = gs._settings_bars
                    if 'music' in bars and bars['music'].collidepoint(logical_pos):
                        return True
                    if 'sfx' in bars and bars['sfx'].collidepoint(logical_pos):
                        return True
            except:
                pass
        
        # ==================== BLACK SCREEN (STARTER SELECTION) ====================
        if mode and "BLACK_SCREEN" in mode_str:
            try:
                if gs and hasattr(gs, '_class_select'):
                    # Check starter cards
                    class_select = gs._class_select
                    if isinstance(class_select, dict) and 'order' in class_select:
                        for key in class_select['order']:
                            data = class_select.get(key, {})
                            if 'rect' in data and data['rect'].collidepoint(logical_pos):
                                return True
                    # Check last starter circle (for selecting the revealed starter)
                    if hasattr(gs, '_starter_last_rect') and gs._starter_last_rect:
                        if gs._starter_last_rect.collidepoint(logical_pos):
                            return True
            except:
                pass
        
        # ==================== MASTER OAK ====================
        if mode and "MASTER_OAK" in mode_str:
            try:
                # Textbox is clickable to advance - check if mouse is over textbox area
                if gs:
                    # Textbox is at bottom of screen
                    box_h = 120
                    margin_bottom = 28
                    textbox_rect = pygame.Rect(36, S.LOGICAL_HEIGHT - box_h - margin_bottom, 
                                             S.LOGICAL_WIDTH - 72, box_h)
                    if textbox_rect.collidepoint(logical_pos):
                        return True
            except:
                pass
        
        # ==================== DEATH SAVES ====================
        if mode and "DEATH_SAVES" in mode_str:
            try:
                if gs and hasattr(gs, '_death_saves'):
                    st = gs._death_saves
                    if 'badge_rect' in st and st['badge_rect']:
                        if st['badge_rect'].collidepoint(logical_pos):
                            return True
            except:
                pass
        
        # ==================== DEATH SCREEN ====================
        if mode and "DEATH" in mode_str and "DEATH_SAVES" not in mode_str:
            try:
                if gs and hasattr(gs, '_death'):
                    st = gs._death
                    if 'btn_rect' in st and st['btn_rect']:
                        if st['btn_rect'].collidepoint(logical_pos):
                            return True
            except:
                pass
        
        # ==================== REST SCREEN ====================
        
        # ==================== SHOP ====================
        # OPTIMIZATION: Only check if shop is open (early exit)
        if gs and getattr(gs, 'shop_open', False):
            try:
                from systems import shop
                try:
                    panel_mx, panel_my = shop._screen_to_panel_coords(mouse_pos)
                    # Check scroll arrows (most common interaction)
                    if hasattr(shop, '_LEFT_ARROW_RECT') and shop._LEFT_ARROW_RECT:
                        if shop._LEFT_ARROW_RECT.collidepoint(panel_mx, panel_my):
                            return True
                    if hasattr(shop, '_RIGHT_ARROW_RECT') and shop._RIGHT_ARROW_RECT:
                        if shop._RIGHT_ARROW_RECT.collidepoint(panel_mx, panel_my):
                            return True
                    # Check shop item rows first (most common interaction)
                    if shop.is_hovering_shop_item(mouse_pos):
                        return True
                    # Check purchase selector buttons (these use screen coordinates, not panel coordinates)
                    if hasattr(shop, '_PURCHASE_SELECTOR_ACTIVE') and shop._PURCHASE_SELECTOR_ACTIVE:
                        if hasattr(shop, '_PURCHASE_CONFIRM_RECT') and shop._PURCHASE_CONFIRM_RECT:
                            if shop._PURCHASE_CONFIRM_RECT.collidepoint(mouse_pos):
                                return True
                        if hasattr(shop, '_PURCHASE_CANCEL_RECT') and shop._PURCHASE_CANCEL_RECT:
                            if shop._PURCHASE_CANCEL_RECT.collidepoint(mouse_pos):
                                return True
                        if hasattr(shop, '_PURCHASE_UP_ARROW_RECT') and shop._PURCHASE_UP_ARROW_RECT:
                            if shop._PURCHASE_UP_ARROW_RECT.collidepoint(mouse_pos):
                                return True
                        if hasattr(shop, '_PURCHASE_DOWN_ARROW_RECT') and shop._PURCHASE_DOWN_ARROW_RECT:
                            if shop._PURCHASE_DOWN_ARROW_RECT.collidepoint(mouse_pos):
                                return True
                except Exception as e:
                    pass
            except:
                pass
        
        # ==================== BOOK OF BOUND ====================
        if mode and "BOOK_OF_BOUND" in mode_str:
            try:
                from screens import book_of_bound
                # Check grid squares - calculate rects the same way the screen does
                try:
                    # Grid layout constants (from book_of_bound.py)
                    GRID_COLS = 2
                    GRID_SQUARE_SIZE = 140
                    GRID_SPACING = 8
                    GRID_PADDING = 20
                    HEADER_HEIGHT = 80
                    LEFT_PANEL_WIDTH = int(S.LOGICAL_WIDTH * 0.65)
                    RIGHT_PANEL_WIDTH = S.LOGICAL_WIDTH - LEFT_PANEL_WIDTH
                    
                    # Right panel rect
                    right_panel_rect = pygame.Rect(LEFT_PANEL_WIDTH, HEADER_HEIGHT, 
                                                  RIGHT_PANEL_WIDTH, S.LOGICAL_HEIGHT - HEADER_HEIGHT)
                    
                    # Grid area
                    grid_start_x = right_panel_rect.x + GRID_PADDING
                    grid_start_y = right_panel_rect.y + GRID_PADDING
                    
                    # Check if mouse is in right panel
                    if right_panel_rect.collidepoint(logical_pos):
                        # Calculate which square the mouse is over
                        rel_x = mx - grid_start_x
                        rel_y = my - grid_start_y
                        col = int(rel_x / (GRID_SQUARE_SIZE + GRID_SPACING))
                        row = int(rel_y / (GRID_SQUARE_SIZE + GRID_SPACING))
                        
                        if col >= 0 and col < GRID_COLS and row >= 0:
                            square_x = grid_start_x + col * (GRID_SQUARE_SIZE + GRID_SPACING)
                            square_y = grid_start_y + row * (GRID_SQUARE_SIZE + GRID_SPACING)
                            square_rect = pygame.Rect(square_x, square_y, GRID_SQUARE_SIZE, GRID_SQUARE_SIZE)
                            if square_rect.collidepoint(logical_pos):
                                # Check if this vessel is discovered (from gs.book_of_bound_discovered)
                                if gs and hasattr(gs, 'book_of_bound_discovered'):
                                    # Calculate index
                                    vessel_index = row * GRID_COLS + col
                                    # Check if discovered (would need to match vessel names, but for hover we can assume any square is clickable if discovered)
                                    return True  # Simplified - assume all squares in grid area are potentially clickable
                except:
                    pass
                
                # Check scrollbar thumb
                try:
                    if hasattr(book_of_bound, '_get_scrollbar_thumb_rect'):
                        # Need right_panel_rect for scrollbar
                        RIGHT_PANEL_WIDTH = S.LOGICAL_WIDTH - int(S.LOGICAL_WIDTH * 0.65)
                        right_panel_rect = pygame.Rect(int(S.LOGICAL_WIDTH * 0.65), 80, 
                                                      RIGHT_PANEL_WIDTH, S.LOGICAL_HEIGHT - 80)
                        thumb_rect = book_of_bound._get_scrollbar_thumb_rect(right_panel_rect)
                        if thumb_rect and thumb_rect.collidepoint(logical_pos):
                            return True
                except:
                    pass
            except:
                pass
        
        # ==================== ARCHIVES ====================
        if mode and "ARCHIVES" in mode_str:
            try:
                from screens import archives
                # Calculate arrow positions (same as archives.py)
                try:
                    HEADER_HEIGHT = 80
                    LEFT_PANEL_WIDTH = int(S.LOGICAL_WIDTH * 0.65)
                    RIGHT_PANEL_WIDTH = S.LOGICAL_WIDTH - LEFT_PANEL_WIDTH
                    right_panel_rect = pygame.Rect(LEFT_PANEL_WIDTH, HEADER_HEIGHT, 
                                                  RIGHT_PANEL_WIDTH, S.LOGICAL_HEIGHT - HEADER_HEIGHT)
                    
                    # Navigation arrows (from archives.py draw function)
                    arrow_size = 24
                    arrow_y = HEADER_HEIGHT + 40
                    page_text = "Page X of Y"  # Placeholder text for width calculation
                    try:
                        font = pygame.font.Font(None, 24)
                        page_text_width = font.size(page_text)[0]
                    except:
                        page_text_width = 100
                    
                    left_arrow_x = right_panel_rect.centerx - (page_text_width // 2) - 50
                    right_arrow_x = right_panel_rect.centerx + (page_text_width // 2) + 50
                    left_arrow_rect = pygame.Rect(left_arrow_x - arrow_size // 2, arrow_y - arrow_size // 2, 
                                                 arrow_size, arrow_size)
                    right_arrow_rect = pygame.Rect(right_arrow_x - arrow_size // 2, arrow_y - arrow_size // 2, 
                                                  arrow_size, arrow_size)
                    
                    if left_arrow_rect.collidepoint(logical_pos):
                        return True
                    if right_arrow_rect.collidepoint(logical_pos):
                        return True
                except:
                    pass
                
                # Check add button and exit button areas
                # These are drawn in the left panel, so check approximate areas
                try:
                    # Add button is typically in left panel, below sprite area
                    # Exit button is typically in right panel, bottom area
                    # For simplicity, we'll check if mouse is in left panel (where add button would be)
                    # or right panel bottom (where exit/storage button would be)
                    LEFT_PANEL_WIDTH = int(S.LOGICAL_WIDTH * 0.65)
                    left_panel_rect = pygame.Rect(0, HEADER_HEIGHT, LEFT_PANEL_WIDTH, S.LOGICAL_HEIGHT - HEADER_HEIGHT)
                    
                    # Add button area (approximate - in left panel, below center)
                    add_button_area = pygame.Rect(left_panel_rect.centerx - 100, left_panel_rect.centery + 100, 
                                                 200, 60)
                    if add_button_area.collidepoint(logical_pos):
                        return True
                    
                    # Exit/storage button area (right panel, bottom)
                    RIGHT_PANEL_WIDTH = S.LOGICAL_WIDTH - LEFT_PANEL_WIDTH
                    right_panel_rect = pygame.Rect(LEFT_PANEL_WIDTH, HEADER_HEIGHT, 
                                                  RIGHT_PANEL_WIDTH, S.LOGICAL_HEIGHT - HEADER_HEIGHT)
                    exit_button_area = pygame.Rect(right_panel_rect.right - 150, right_panel_rect.bottom - 80, 
                                                  120, 50)
                    if exit_button_area.collidepoint(logical_pos):
                        return True
                    
                    # Check stored vessel boxes in right panel
                    # These are in a grid in the right panel
                    if right_panel_rect.collidepoint(logical_pos):
                        # Approximate grid area for stored vessels
                        stored_area = pygame.Rect(right_panel_rect.x + 20, right_panel_rect.y + 100, 
                                                 right_panel_rect.w - 40, right_panel_rect.h - 200)
                        if stored_area.collidepoint(logical_pos):
                            return True
                except:
                    pass
            except:
                pass
        
        # ==================== VESSEL STAT SELECTOR ====================
        if mode and "VESSEL_STAT_SELECTOR" in mode_str:
            try:
                from screens import vessel_stat_selector
                # Check stored button rects in state
                try:
                    if hasattr(vessel_stat_selector, '_STATE'):
                        state = vessel_stat_selector._STATE
                        if '_button_rects' in state:
                            button_rects = state['_button_rects']
                            for stat_name, rect in button_rects.items():
                                if rect and rect.collidepoint(logical_pos):
                                    return True
                except:
                    pass
            except:
                pass
        
        # ==================== VESSEL MOVE SELECTOR ====================
        if mode and "VESSEL_MOVE_SELECTOR" in mode_str:
            try:
                from screens import vessel_move_selector
                # Check stored button rects in state
                try:
                    if hasattr(vessel_move_selector, '_STATE'):
                        state = vessel_move_selector._STATE
                        if '_button_rects' in state:
                            button_rects = state['_button_rects']
                            for move_idx, rect in button_rects.items():
                                if rect and rect.collidepoint(logical_pos):
                                    return True
                except:
                    pass
            except:
                pass
        
        # ==================== BUFF SELECTION ====================
        if mode and "BUFF_SELECTION" in mode_str:
            try:
                from screens import buff_selection
                # Calculate card rects (same as buff_selection.py)
                try:
                    if gs and hasattr(gs, '_buff_selection_state'):
                        st = gs._buff_selection_state
                        if 'cards' in st:
                            card_width = 300
                            card_height = 400
                            card_spacing = 40
                            total_width = (card_width * 3) + (card_spacing * 2)
                            start_x = (S.LOGICAL_WIDTH - total_width) // 2
                            card_y = S.LOGICAL_HEIGHT // 2 - card_height // 2
                            
                            for i in range(len(st['cards'])):
                                card_x = start_x + i * (card_width + card_spacing)
                                card_rect = pygame.Rect(card_x, card_y, card_width, card_height)
                                if card_rect.collidepoint(logical_pos):
                                    return True
                except:
                    pass
            except:
                pass
        
        # ==================== LEDGER ====================
        try:
            from screens import ledger
            if ledger.is_open():
                # Check stored layout rects
                try:
                    if hasattr(ledger, '_last_layout'):
                        layout = ledger._last_layout
                        left = layout.get('left')
                        right = layout.get('right')
                        book = layout.get('book')
                        
                        if left and left.collidepoint(logical_pos):
                            return True
                        if right and right.collidepoint(logical_pos):
                            return True
                        # Book area itself might not be clickable, but areas around it are
                except:
                    pass
        except:
            pass
        
        # ==================== BATTLE/WILD VESSEL SCREEN BUTTONS ====================
        # OPTIMIZATION: Combine battle and wild vessel checks (they use same buttons)
        if is_battle_mode:
            try:
                from combat.btn import battle_action, bag_action, party_action, run_action
                # Check buttons (quick checks first)
                if battle_action.is_hovering_button(logical_pos):
                    return True
                if bag_action.is_hovering_button(logical_pos):
                    return True
                if party_action.is_hovering_button(logical_pos):
                    return True
                if run_action.is_hovering_button(logical_pos):
                    return True
                
                # Check popup elements (only if open - bag_action already checked above)
                if battle_action.is_open() and gs:
                    if battle_action.is_hovering_popup_element(logical_pos, gs):
                        return True
                
                if party_action.is_open():
                    if party_action.is_hovering_popup_element(logical_pos):
                        return True
            except:
                pass
        
        return False
        
    except Exception as e:
        # If anything fails, default to not hovering (don't cache errors)
        return False


def draw_cursor(screen, mouse_pos, gs=None, mode=None):
    """
    Draw the custom cursor on the screen at the mouse position.
    Call this at the end of your draw loop, after all other drawing.
    
    Args:
        screen: The pygame surface to draw on (should be the final screen surface, not virtual)
        mouse_pos: The current mouse position tuple (x, y)
        gs: Game state object (optional, for checking UI state)
        mode: Current game mode (optional, for mode-specific checks)
    """
    global _normal_cursor_surface, _click_cursor_surface, _current_cursor_type
    global _hotspot_normal, _hotspot_click
    
    # Check if hovering over a clickable element
    is_hovering = _is_hovering_clickable(mouse_pos, gs, mode)
    
    # Determine which cursor to draw
    # Use click cursor if: currently clicking OR hovering over clickable element
    if (_current_cursor_type == "click" or is_hovering) and _click_cursor_surface:
        cursor_surface = _click_cursor_surface
        hotspot = _hotspot_click
    elif _normal_cursor_surface:
        cursor_surface = _normal_cursor_surface
        hotspot = _hotspot_normal
    else:
        # No custom cursor available, show system cursor
        pygame.mouse.set_visible(True)
        return
    
    # Calculate position (subtract hotspot offset)
    draw_x = mouse_pos[0] - hotspot[0]
    draw_y = mouse_pos[1] - hotspot[1]
    
    # Draw cursor
    screen.blit(cursor_surface, (draw_x, draw_y))

