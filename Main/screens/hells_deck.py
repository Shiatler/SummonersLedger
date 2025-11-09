# ============================================================
# screens/hells_deck.py — Hell's Deck (Card Collection Viewer)
# Layout: Carousel with 3 cards visible, middle one highlighted/bigger
# Purple design matching archives and book_of_bound
# ============================================================

import os
import re
import pygame
import settings as S
from systems import coords, buffs

# Mode constant
MODE_HELLS_DECK = "HELLS_DECK"

# ===================== Layout Constants =====================
HEADER_HEIGHT = 90

# Card carousel constants
CARD_WIDTH_NORMAL = 280  # Width of side cards
CARD_HEIGHT_NORMAL = 400  # Height of side cards
CARD_WIDTH_HIGHLIGHT = 380  # Width of highlighted (middle) card
CARD_HEIGHT_HIGHLIGHT = 540  # Height of highlighted (middle) card
CARD_SPACING = 40  # Space between cards
CAROUSEL_Y = S.LOGICAL_HEIGHT // 2  # Vertical center

# Arrow button constants
ARROW_BUTTON_SIZE = 60
ARROW_BUTTON_Y = S.LOGICAL_HEIGHT - 150

# Colors - Purple, gloomy, magical, medieval aesthetic (matching archives/book_of_bound)
COLOR_BG = (18, 10, 28)  # Deep dark purple background
COLOR_HEADER_BG = (35, 18, 50)  # Darker header
COLOR_HEADER_SHADOW = (15, 8, 22)  # Shadow for depth
COLOR_HEADER_TEXT = (200, 160, 240)  # Brighter, more ethereal text
COLOR_HEADER_GLOW = (140, 100, 180)  # Subtle glow color
COLOR_CARD_BORDER = (110, 65, 140)  # Card border
COLOR_CARD_BORDER_HIGHLIGHT = (180, 120, 220)  # Highlighted card border
COLOR_TEXT = (185, 145, 215)  # Main text
COLOR_TEXT_DIM = (110, 85, 140)  # Dimmed text
COLOR_BUTTON_BG = (45, 25, 65)  # Button background
COLOR_BUTTON_HOVER = (65, 35, 90)  # Button hover
COLOR_BUTTON_BORDER = (120, 70, 150)  # Button border

# Card data cache
_all_cards = []  # List of (tier, card_name, card_image, card_data) tuples
_cards_loaded = False

# Carousel state
_current_index = 0  # Index of currently selected card (middle card)

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
                    # Try to use bold variant if available
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
        print(f"🃏 No cards obtained yet - Hell's Deck is empty")
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
    
    print(f"🃏 Loaded {len(_all_cards)} obtained cards for Hell's Deck")


def enter(gs, **kwargs):
    """Initialize the Hell's Deck screen."""
    global _current_index
    _load_all_cards(gs)
    _current_index = 0  # Start at first card


def draw(screen: pygame.Surface, gs, dt: float, **deps):
    """Draw the Hell's Deck screen with carousel."""
    # Reload cards to reflect current game state (in case new cards were obtained)
    _load_all_cards(gs)
    
    if len(_all_cards) == 0:
        # Draw empty state
        screen.fill(COLOR_BG)
        
        # Draw header
        header_rect = pygame.Rect(0, 0, S.LOGICAL_WIDTH, HEADER_HEIGHT)
        shadow_rect = header_rect.move(0, 3)
        pygame.draw.rect(screen, COLOR_HEADER_SHADOW, shadow_rect)
        pygame.draw.rect(screen, COLOR_HEADER_BG, header_rect)
        pygame.draw.rect(screen, COLOR_CARD_BORDER, header_rect, 2)
        
        # Draw header text
        header_font = _get_font(64, bold=True)
        title_text = "Hell's Deck"
        header_text = header_font.render(title_text, True, COLOR_HEADER_TEXT)
        header_rect_text = header_text.get_rect(center=(S.LOGICAL_WIDTH // 2, HEADER_HEIGHT // 2))
        
        for offset in range(-2, 3):
            glow_surf = header_font.render(title_text, True, COLOR_HEADER_GLOW)
            glow_surf.set_alpha(40)
            screen.blit(glow_surf, (header_rect_text.x + offset, header_rect_text.y))
            screen.blit(glow_surf, (header_rect_text.x, header_rect_text.y + offset))
        
        screen.blit(header_text, header_rect_text)
        
        # Draw empty message
        font = _get_font(48)
        empty_text = font.render("No cards obtained yet", True, COLOR_TEXT_DIM)
        screen.blit(empty_text, empty_text.get_rect(center=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT // 2)))
        
        hint_font = _get_font(32)
        hint_text = hint_font.render("Obtain cards by selecting blessings, curses, and demon pacts", True, COLOR_TEXT_DIM)
        screen.blit(hint_text, hint_text.get_rect(center=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT // 2 + 60)))
        return
    
    # Draw background
    screen.fill(COLOR_BG)
    
    # Draw header
    header_rect = pygame.Rect(0, 0, S.LOGICAL_WIDTH, HEADER_HEIGHT)
    # Draw shadow first
    shadow_rect = header_rect.move(0, 3)
    pygame.draw.rect(screen, COLOR_HEADER_SHADOW, shadow_rect)
    # Draw header on top
    pygame.draw.rect(screen, COLOR_HEADER_BG, header_rect)
    
    # Draw header borders
    pygame.draw.rect(screen, COLOR_CARD_BORDER, header_rect, 2)
    
    # Draw header text with glow effect
    header_font = _get_font(64, bold=True)
    title_text = "Hell's Deck"
    header_text = header_font.render(title_text, True, COLOR_HEADER_TEXT)
    header_rect_text = header_text.get_rect(center=(S.LOGICAL_WIDTH // 2, HEADER_HEIGHT // 2))
    
    # Draw glow effect
    for offset in range(-2, 3):
        glow_surf = header_font.render(title_text, True, COLOR_HEADER_GLOW)
        glow_surf.set_alpha(40)
        screen.blit(glow_surf, (header_rect_text.x + offset, header_rect_text.y))
        screen.blit(glow_surf, (header_rect_text.x, header_rect_text.y + offset))
    
    screen.blit(header_text, header_rect_text)
    
    # Draw card count
    count_font = _get_font(32)
    count_text = count_font.render(f"Card {_current_index + 1} of {len(_all_cards)}", True, COLOR_TEXT_DIM)
    screen.blit(count_text, (S.LOGICAL_WIDTH // 2 - count_text.get_width() // 2, HEADER_HEIGHT + 20))
    
    # Draw carousel with 3 cards
    center_x = S.LOGICAL_WIDTH // 2
    
    # Calculate which cards to show
    cards_to_show = []
    for offset in [-1, 0, 1]:  # Left, center, right
        idx = _current_index + offset
        if 0 <= idx < len(_all_cards):
            cards_to_show.append((offset, _all_cards[idx]))
        else:
            cards_to_show.append((offset, None))
    
    # Draw cards
    for offset, card_info in cards_to_show:
        if card_info is None:
            continue
        
        tier, card_name, card_image, card_data = card_info
        is_center = (offset == 0)
        
        # Determine card size
        if is_center:
            card_w, card_h = CARD_WIDTH_HIGHLIGHT, CARD_HEIGHT_HIGHLIGHT
        else:
            card_w, card_h = CARD_WIDTH_NORMAL, CARD_HEIGHT_NORMAL
        
        # Calculate card position
        if offset == -1:  # Left card
            card_x = center_x - CARD_WIDTH_HIGHLIGHT // 2 - CARD_SPACING - CARD_WIDTH_NORMAL
        elif offset == 0:  # Center card
            card_x = center_x - CARD_WIDTH_HIGHLIGHT // 2
        else:  # Right card
            card_x = center_x + CARD_WIDTH_HIGHLIGHT // 2 + CARD_SPACING
        
        card_y = CAROUSEL_Y - card_h // 2
        
        # Scale card image to fit
        img_w, img_h = card_image.get_width(), card_image.get_height()
        scale_w = card_w / img_w
        scale_h = card_h / img_h
        scale = min(scale_w, scale_h) * 0.95  # Slightly smaller to leave room for border
        
        scaled_w = int(img_w * scale)
        scaled_h = int(img_h * scale)
        scaled_card = pygame.transform.smoothscale(card_image, (scaled_w, scaled_h))
        
        # Draw card background (slightly larger than image for border)
        card_rect = pygame.Rect(
            card_x + (card_w - scaled_w) // 2 - 8,
            card_y + (card_h - scaled_h) // 2 - 8,
            scaled_w + 16,
            scaled_h + 16
        )
        
        # Draw card border
        border_color = COLOR_CARD_BORDER_HIGHLIGHT if is_center else COLOR_CARD_BORDER
        border_width = 4 if is_center else 2
        pygame.draw.rect(screen, border_color, card_rect, border_width, border_radius=12)
        
        # Draw card image
        img_x = card_x + (card_w - scaled_w) // 2
        img_y = card_y + (card_h - scaled_h) // 2
        screen.blit(scaled_card, (img_x, img_y))
        
        # Draw card info below card (only for center card)
        if is_center:
            info_y = card_y + card_h + 30
            name_font = _get_font(36, bold=True)
            desc_font = _get_font(24)
            tier_font = _get_font(28)
            
            # Card name
            name_text = name_font.render(card_data.get("name", card_name), True, COLOR_TEXT)
            screen.blit(name_text, (center_x - name_text.get_width() // 2, info_y))
            
            # Tier
            tier_text = tier_font.render(tier, True, COLOR_TEXT_DIM)
            screen.blit(tier_text, (center_x - tier_text.get_width() // 2, info_y + 45))
            
            # Description
            desc_text = desc_font.render(card_data.get("description", ""), True, COLOR_TEXT)
            screen.blit(desc_text, (center_x - desc_text.get_width() // 2, info_y + 80))
    
    # Draw arrow buttons
    left_arrow_x = 100
    right_arrow_x = S.LOGICAL_WIDTH - 100 - ARROW_BUTTON_SIZE
    
    # Get mouse position for hover detection (convert from screen to logical)
    try:
        screen_mx, screen_my = pygame.mouse.get_pos()
        mx, my = coords.screen_to_logical((screen_mx, screen_my))
    except:
        mx, my = pygame.mouse.get_pos()
    
    # Left arrow button
    left_arrow_rect = pygame.Rect(left_arrow_x, ARROW_BUTTON_Y, ARROW_BUTTON_SIZE, ARROW_BUTTON_SIZE)
    left_hover = left_arrow_rect.collidepoint(mx, my) and _current_index > 0
    left_enabled = _current_index > 0
    
    # Draw button background
    arrow_bg_color = COLOR_BUTTON_HOVER if left_hover and left_enabled else COLOR_BUTTON_BG
    pygame.draw.rect(screen, arrow_bg_color, left_arrow_rect, border_radius=8)
    pygame.draw.rect(screen, COLOR_BUTTON_BORDER, left_arrow_rect, 2, border_radius=8)
    
    # Draw left arrow shape (pointing left)
    if left_enabled:
        arrow_color = COLOR_TEXT if left_hover else COLOR_TEXT_DIM
    else:
        arrow_color = (60, 50, 70)  # Very dim when disabled
    
    center_x = left_arrow_rect.centerx
    center_y = left_arrow_rect.centery
    arrow_width = 24  # Width of the arrow
    arrow_height = 16  # Height of the arrow
    
    # Left arrow: triangle pointing left (chevron style)
    left_arrow_points = [
        (center_x + arrow_width // 3, center_y),  # Right point (tip)
        (center_x - arrow_width // 3, center_y - arrow_height // 2),  # Top left
        (center_x - arrow_width // 3, center_y + arrow_height // 2),  # Bottom left
    ]
    pygame.draw.polygon(screen, arrow_color, left_arrow_points)
    
    # Right arrow button
    right_arrow_rect = pygame.Rect(right_arrow_x, ARROW_BUTTON_Y, ARROW_BUTTON_SIZE, ARROW_BUTTON_SIZE)
    right_hover = right_arrow_rect.collidepoint(mx, my) and _current_index < len(_all_cards) - 1
    right_enabled = _current_index < len(_all_cards) - 1
    
    # Draw button background
    arrow_bg_color = COLOR_BUTTON_HOVER if right_hover and right_enabled else COLOR_BUTTON_BG
    pygame.draw.rect(screen, arrow_bg_color, right_arrow_rect, border_radius=8)
    pygame.draw.rect(screen, COLOR_BUTTON_BORDER, right_arrow_rect, 2, border_radius=8)
    
    # Draw right arrow shape (pointing right)
    if right_enabled:
        arrow_color = COLOR_TEXT if right_hover else COLOR_TEXT_DIM
    else:
        arrow_color = (60, 50, 70)  # Very dim when disabled
    
    center_x = right_arrow_rect.centerx
    center_y = right_arrow_rect.centery
    arrow_width = 24  # Width of the arrow
    arrow_height = 16  # Height of the arrow
    
    # Right arrow: triangle pointing right (chevron style)
    right_arrow_points = [
        (center_x - arrow_width // 3, center_y),  # Left point (tip)
        (center_x + arrow_width // 3, center_y - arrow_height // 2),  # Top right
        (center_x + arrow_width // 3, center_y + arrow_height // 2),  # Bottom right
    ]
    pygame.draw.polygon(screen, arrow_color, right_arrow_points)
    
    # Store arrow rects for click detection
    gs._hells_deck_left_arrow = left_arrow_rect
    gs._hells_deck_right_arrow = right_arrow_rect


def handle(gs, events, dt, **deps):
    """Handle events for Hell's Deck screen."""
    global _current_index
    
    # Reload cards to reflect current game state
    _load_all_cards(gs)
    
    if len(_all_cards) == 0:
        return None
    
    audio_bank = deps.get("audio_bank")
    
    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # Return to game
                return S.MODE_GAME
            elif event.key == pygame.K_LEFT:
                # Move to previous card
                if _current_index > 0:
                    _current_index -= 1
                    from systems import audio as audio_sys
                    if audio_bank:
                        audio_sys.play_click(audio_bank)
            elif event.key == pygame.K_RIGHT:
                # Move to next card
                if _current_index < len(_all_cards) - 1:
                    _current_index += 1
                    from systems import audio as audio_sys
                    if audio_bank:
                        audio_sys.play_click(audio_bank)
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # Convert mouse position to logical coordinates
            try:
                mx, my = coords.screen_to_logical(event.pos)
            except:
                mx, my = event.pos
            
            if event.button == 1:  # Left click
                # Check arrow button clicks
                left_arrow = getattr(gs, "_hells_deck_left_arrow", None)
                right_arrow = getattr(gs, "_hells_deck_right_arrow", None)
                
                if left_arrow and left_arrow.collidepoint(mx, my) and _current_index > 0:
                    _current_index -= 1
                    from systems import audio as audio_sys
                    if audio_bank:
                        audio_sys.play_click(audio_bank)
                elif right_arrow and right_arrow.collidepoint(mx, my) and _current_index < len(_all_cards) - 1:
                    _current_index += 1
                    from systems import audio as audio_sys
                    if audio_bank:
                        audio_sys.play_click(audio_bank)
            
            elif event.button == 4:  # Scroll up
                if _current_index > 0:
                    _current_index -= 1
                    from systems import audio as audio_sys
                    if audio_bank:
                        audio_sys.play_click(audio_bank)
            elif event.button == 5:  # Scroll down
                if _current_index < len(_all_cards) - 1:
                    _current_index += 1
                    from systems import audio as audio_sys
                    if audio_bank:
                        audio_sys.play_click(audio_bank)
    
    return None  # Stay in this mode

