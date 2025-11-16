# ============================================================
# systems/hells_deck_popup.py — Hell's Deck Popup (Card Collection Viewer)
# Layout: Simple overlay matching buff selection screen style
# Shows up to 5 cards in a carousel, middle one bigger
# ============================================================

import os
import re
import pygame
import settings as S
from systems import coords, buffs

# ===================== Popup State =====================
_OPEN = False

# ===================== Layout Constants =====================
# Card carousel constants
CARD_WIDTH_NORMAL = 200  # Width of side cards
CARD_HEIGHT_NORMAL = 300  # Height of side cards
CARD_WIDTH_HIGHLIGHT = 280  # Width of highlighted (middle) card
CARD_HEIGHT_HIGHLIGHT = 400  # Height of highlighted (middle) card
CARD_SPACING = 30  # Space between cards
MAX_CARDS_VISIBLE = 5  # Maximum cards to show at once

# Colors - Simple, clean style matching buff selection
COLOR_BG_OVERLAY = (0, 0, 0, 140)  # Light semi-transparent overlay
COLOR_TEXT_WHITE = (255, 255, 255)
COLOR_TEXT_GRAY = (200, 200, 200)
COLOR_CARD_BORDER_HOVER = (255, 255, 255)
COLOR_CARD_BORDER_SELECTED = (255, 255, 255)  # White for selected

# Card data cache
_all_cards = []  # List of (tier, card_name, card_image, card_data) tuples
_cards_loaded = False

# Carousel state
_current_index = 0  # Index of currently selected card (middle card)

# Font cache
_font_cache = {}


def _get_font(size: int, bold: bool = False):
    """Get DH font with caching."""
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
                    try:
                        font.set_bold(True)
                    except:
                        pass
                break
            except Exception as e:
                print(f"⚠️ Failed to load font {path}: {e}")
    
    if font is None:
        font = pygame.font.SysFont("arial", size, bold=bold)
    
    _font_cache[key] = font
    return font


def _load_all_cards(gs):
    """Load only cards that have been obtained during the game."""
    global _all_cards, _cards_loaded
    
    # Always reload to reflect current game state
    _all_cards = []
    _cards_loaded = True
    
    # Get all obtained cards from buffs_history
    # buffs_history contains all cards ever obtained, including duplicates
    # This allows showing multiple copies of the same card if obtained multiple times
    buffs_history = getattr(gs, "buffs_history", [])
    obtained_cards = []  # List of all buff entries (allows duplicates)
    
    if isinstance(buffs_history, list):
        for buff in buffs_history:
            if isinstance(buff, dict):
                tier = buff.get("tier")
                card_id = buff.get("id")
                if tier is not None and card_id is not None:
                    obtained_cards.append(buff)
    
    if not obtained_cards:
        return
    
    # Load all obtained cards (including duplicates)
    blessings_dir = buffs.BLESSINGS_DIR
    
    for buff in obtained_cards:
        tier = buff.get("tier")
        card_id = buff.get("id")
        card_name = buff.get("name")
        
        # Normalize card_id to int for consistency
        try:
            card_id = int(card_id)
        except (ValueError, TypeError):
            continue
        
        # Get card name from buff entry, or construct from tier and id
        if not card_name:
            card_name = f"{tier}{card_id}"
        
        # Try to load image from stored image_path first
        card_image = None
        stored_path = buff.get("image_path")
        if stored_path and os.path.exists(stored_path):
            card_image = buffs.load_card_image(stored_path)
        
        # Fall back to standard path if stored path didn't work
        if card_image is None:
            image_path = os.path.join(blessings_dir, f"{card_name}.png")
            if not os.path.exists(image_path):
                # Try uppercase
                image_path = os.path.join(blessings_dir, f"{card_name}.PNG")
            card_image = buffs.load_card_image(image_path)
        
        if card_image is None:
            print(f"⚠️ Could not load image for card {card_name} (tier={tier}, id={card_id})")
            continue
        
        # Get card data
        card_data = buffs.get_card_data(card_name)
        
        _all_cards.append((tier, card_name, card_image, card_data))
    
    # Sort by tier order, then by card id
    tier_order = ["Common", "Rare", "Epic", "Legendary", "DemonPact", "Curse", "Punishment"]
    tier_index = {tier: idx for idx, tier in enumerate(tier_order)}
    
    def get_sort_key(card_tuple):
        tier, card_name, _, _ = card_tuple
        # Extract numeric part from card name for sorting
        match = re.search(r'\d+', card_name)
        card_num = int(match.group(0)) if match else 0
        return (tier_index.get(tier, 999), card_num)
    
    _all_cards.sort(key=get_sort_key)


def is_open() -> bool:
    """Check if the Hell's Deck popup is open."""
    return _OPEN


def open_popup(gs):
    """Open the Hell's Deck popup."""
    global _OPEN, _current_index
    
    _OPEN = True
    _current_index = 0  # Reset to first card
    
    # Load cards
    _load_all_cards(gs)


def close_popup():
    """Close the Hell's Deck popup."""
    global _OPEN
    _OPEN = False


def handle_event(event, gs) -> bool:
    """
    Handle events for the Hell's Deck popup.
    Returns True if event was consumed, False otherwise.
    """
    global _current_index
    
    if not _OPEN:
        return False
    
    # Reload cards to reflect current game state
    _load_all_cards(gs)
    
    # ESC to close
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            from systems import audio as audio_sys
            audio_sys.play_click(audio_sys.get_global_bank())
            close_popup()
            return True
        elif event.key == pygame.K_LEFT:
            # Move to previous card
            if _current_index > 0:
                _current_index -= 1
                from systems import audio as audio_sys
                audio_sys.play_click(audio_sys.get_global_bank())
                return True
        elif event.key == pygame.K_RIGHT:
            # Move to next card
            if _current_index < len(_all_cards) - 1:
                _current_index += 1
                from systems import audio as audio_sys
                audio_sys.play_click(audio_sys.get_global_bank())
                return True
    
    elif event.type == pygame.MOUSEBUTTONDOWN:
        # event.pos is already converted to logical coordinates by main.py - use directly
        mx, my = event.pos
        
        if event.button == 1:  # Left click
            # Check arrow button clicks
            left_arrow = getattr(gs, "_hells_deck_left_arrow", None)
            right_arrow = getattr(gs, "_hells_deck_right_arrow", None)
            
            if left_arrow and left_arrow.collidepoint(mx, my) and _current_index > 0:
                _current_index -= 1
                from systems import audio as audio_sys
                audio_sys.play_click(audio_sys.get_global_bank())
                return True
            elif right_arrow and right_arrow.collidepoint(mx, my) and _current_index < len(_all_cards) - 1:
                _current_index += 1
                from systems import audio as audio_sys
                audio_sys.play_click(audio_sys.get_global_bank())
                return True
            
            # Click outside cards/arrows - close popup
            # Check if click is in card area
            sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
            card_area_y = sh // 2 - CARD_HEIGHT_HIGHLIGHT // 2 - 100
            card_area_h = CARD_HEIGHT_HIGHLIGHT + 200
            
            # Calculate card area bounds
            num_visible = min(MAX_CARDS_VISIBLE, len(_all_cards))
            if num_visible > 0:
                # Calculate total width of visible cards
                total_card_width = 0
                for i in range(num_visible):
                    if i == _current_index:
                        total_card_width += CARD_WIDTH_HIGHLIGHT
                    else:
                        total_card_width += CARD_WIDTH_NORMAL
                total_card_width += (num_visible - 1) * CARD_SPACING
                
                card_area_x = (sw - total_card_width) // 2 - 50
                card_area_w = total_card_width + 100
                
                # If click is outside card area and not on arrows, close
                card_rect = pygame.Rect(card_area_x, card_area_y, card_area_w, card_area_h)
                if not card_rect.collidepoint(mx, my):
                    # Also check if not clicking on title area
                    title_area = pygame.Rect(0, 0, sw, 150)
                    if not title_area.collidepoint(mx, my):
                        from systems import audio as audio_sys
                        audio_sys.play_click(audio_sys.get_global_bank())
                        close_popup()
                        return True
        
        elif event.button == 4:  # Scroll up
            if _current_index > 0:
                _current_index -= 1
                from systems import audio as audio_sys
                audio_sys.play_click(audio_sys.get_global_bank())
                return True
        elif event.button == 5:  # Scroll down
            if _current_index < len(_all_cards) - 1:
                _current_index += 1
                from systems import audio as audio_sys
                audio_sys.play_click(audio_sys.get_global_bank())
                return True
    
    return False  # Event not consumed


def draw(screen: pygame.Surface, gs):
    """Draw the Hell's Deck popup overlay."""
    if not _OPEN:
        return
    
    # Reload cards to reflect current game state
    _load_all_cards(gs)
    
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    
    # Draw light semi-transparent overlay (subtle darkening)
    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill(COLOR_BG_OVERLAY)
    screen.blit(overlay, (0, 0))
    
    # Draw title (similar to buff selection)
    title_font = _get_font(48, bold=True)
    title_text = "Hell's Deck"
    title_surf = title_font.render(title_text, True, COLOR_TEXT_WHITE)
    title_rect = title_surf.get_rect(center=(sw // 2, 80))
    screen.blit(title_surf, title_rect)
    
    if len(_all_cards) == 0:
        # Draw empty message
        empty_font = _get_font(32)
        empty_text = empty_font.render("No cards obtained yet", True, COLOR_TEXT_GRAY)
        screen.blit(empty_text, empty_text.get_rect(center=(sw // 2, sh // 2)))
        
        hint_font = _get_font(20)
        hint_text = hint_font.render("Obtain cards by selecting blessings, curses, and demon pacts", True, COLOR_TEXT_GRAY)
        screen.blit(hint_text, hint_text.get_rect(center=(sw // 2, sh // 2 + 50)))
        return
    
    # Draw card count
    count_font = _get_font(28)
    count_text = count_font.render(f"Card {_current_index + 1} of {len(_all_cards)}", True, COLOR_TEXT_GRAY)
    screen.blit(count_text, count_text.get_rect(center=(sw // 2, title_rect.bottom + 20)))
    
    # Determine which cards to show (up to 5, centered on current_index)
    num_cards = len(_all_cards)
    num_visible = min(MAX_CARDS_VISIBLE, num_cards)
    middle_position = MAX_CARDS_VISIBLE // 2  # Middle position index (2 for 5 cards)
    
    # Calculate which cards to show, centering current_index
    if num_cards <= MAX_CARDS_VISIBLE:
        # Show all cards
        start_index = 0
        visible_indices = list(range(num_cards))
    else:
        # Center the current index in the visible window
        start_index = max(0, min(_current_index - middle_position, num_cards - MAX_CARDS_VISIBLE))
        end_index = min(start_index + MAX_CARDS_VISIBLE, num_cards)
        visible_indices = list(range(start_index, end_index))
    
    # Calculate card positions
    card_y = sh // 2 - CARD_HEIGHT_HIGHLIGHT // 2
    
    # Calculate total width needed for visible cards
    total_width = 0
    for i, card_idx in enumerate(visible_indices):
        if card_idx == _current_index:
            total_width += CARD_WIDTH_HIGHLIGHT
        else:
            total_width += CARD_WIDTH_NORMAL
    total_width += (len(visible_indices) - 1) * CARD_SPACING
    
    start_x = (sw - total_width) // 2
    
    # Draw cards
    current_x = start_x
    for i, card_idx in enumerate(visible_indices):
        if card_idx >= len(_all_cards):
            continue
        
        tier, card_name, card_image, card_data = _all_cards[card_idx]
        is_center = (card_idx == _current_index)
        
        # Determine card size
        if is_center:
            card_w, card_h = CARD_WIDTH_HIGHLIGHT, CARD_HEIGHT_HIGHLIGHT
        else:
            card_w, card_h = CARD_WIDTH_NORMAL, CARD_HEIGHT_NORMAL
        
        # Scale card image to fit
        img_w, img_h = card_image.get_width(), card_image.get_height()
        scale_w = card_w / img_w
        scale_h = card_h / img_h
        scale = min(scale_w, scale_h) * 0.95
        
        scaled_w = int(img_w * scale)
        scaled_h = int(img_h * scale)
        scaled_card = pygame.transform.smoothscale(card_image, (scaled_w, scaled_h))
        
        # Calculate position
        img_x = current_x + (card_w - scaled_w) // 2
        img_y = card_y + (card_h - scaled_h) // 2
        
        # Draw border for center position (matching buff selection style)
        if is_center:
            border_width = 4
            border_color = COLOR_CARD_BORDER_SELECTED
            border_rect = pygame.Rect(
                img_x - border_width,
                img_y - border_width,
                scaled_w + border_width * 2,
                scaled_h + border_width * 2
            )
            pygame.draw.rect(screen, border_color, border_rect, border_width, border_radius=8)
        
        # Draw card image
        screen.blit(scaled_card, (img_x, img_y))
        
        # Move to next card position
        if is_center:
            current_x += CARD_WIDTH_HIGHLIGHT + CARD_SPACING
        else:
            current_x += CARD_WIDTH_NORMAL + CARD_SPACING
    
        # Draw card info below center card
        if is_center:
            info_y = card_y + card_h + 20
            name_font = _get_font(28, bold=True)
            desc_font = _get_font(18)
            tier_font = _get_font(22)
            
            # Card name
            name_text = name_font.render(card_data.get("name", card_name), True, COLOR_TEXT_WHITE)
            screen.blit(name_text, (sw // 2 - name_text.get_width() // 2, info_y))
            
            # Tier
            tier_text = tier_font.render(tier, True, COLOR_TEXT_GRAY)
            screen.blit(tier_text, (sw // 2 - tier_text.get_width() // 2, info_y + 30))
            
            # Description
            desc_text = desc_font.render(card_data.get("description", ""), True, COLOR_TEXT_WHITE)
            screen.blit(desc_text, (sw // 2 - desc_text.get_width() // 2, info_y + 55))
    
    # Draw arrow buttons (only if there are more cards than visible)
    if num_cards > MAX_CARDS_VISIBLE or _current_index > 0 or _current_index < num_cards - 1:
        arrow_y = sh - 100
        arrow_size = 40
        
        # Get mouse position for hover
        try:
            screen_mx, screen_my = pygame.mouse.get_pos()
            mx, my = coords.screen_to_logical((screen_mx, screen_my))
        except:
            mx, my = pygame.mouse.get_pos()
        
        # Left arrow (only show if not at start)
        if _current_index > 0:
            left_arrow_x = 50
            left_arrow_rect = pygame.Rect(left_arrow_x - arrow_size // 2, arrow_y - arrow_size // 2, arrow_size, arrow_size)
            left_hover = left_arrow_rect.collidepoint(mx, my)
            
            # Draw arrow triangle
            arrow_color = COLOR_TEXT_WHITE if left_hover else COLOR_TEXT_GRAY
            arrow_points = [
                (left_arrow_x, arrow_y),  # Right point (tip)
                (left_arrow_x - 15, arrow_y - 10),  # Top left
                (left_arrow_x - 15, arrow_y + 10),  # Bottom left
            ]
            pygame.draw.polygon(screen, arrow_color, arrow_points)
            
            gs._hells_deck_left_arrow = left_arrow_rect
        else:
            gs._hells_deck_left_arrow = None
        
        # Right arrow (only show if not at end)
        if _current_index < num_cards - 1:
            right_arrow_x = sw - 50
            right_arrow_rect = pygame.Rect(right_arrow_x - arrow_size // 2, arrow_y - arrow_size // 2, arrow_size, arrow_size)
            right_hover = right_arrow_rect.collidepoint(mx, my)
            
            # Draw arrow triangle
            arrow_color = COLOR_TEXT_WHITE if right_hover else COLOR_TEXT_GRAY
            arrow_points = [
                (right_arrow_x, arrow_y),  # Left point (tip)
                (right_arrow_x + 15, arrow_y - 10),  # Top right
                (right_arrow_x + 15, arrow_y + 10),  # Bottom right
            ]
            pygame.draw.polygon(screen, arrow_color, arrow_points)
            
            gs._hells_deck_right_arrow = right_arrow_rect
        else:
            gs._hells_deck_right_arrow = None
    
    # Instructions
    inst_font = _get_font(18)
    inst_text = "Use arrow keys or mouse wheel to navigate • ESC to close"
    inst_surf = inst_font.render(inst_text, True, COLOR_TEXT_GRAY)
    inst_rect = inst_surf.get_rect(center=(sw // 2, sh - 40))
    screen.blit(inst_surf, inst_rect)
