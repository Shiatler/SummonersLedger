# ============================================================
# systems/currency_display.py — Currency Display Popup
# Shows gold, silver, bronze in a popup overlay
# ============================================================

import os
import pygame
import settings as S

# Currency state (stored in GameState, but we manage display)
_is_open = False
_fade_start_time = 0
_fade_duration = 0.15  # seconds

# Asset cache
_coin_bag_bg = None
_gold_icon = None
_silver_icon = None
_bronze_icon = None

def _load_assets():
    """Load coin bag and coin icon images."""
    global _coin_bag_bg, _gold_icon, _silver_icon, _bronze_icon
    
    if _coin_bag_bg is None:
        coin_bag_path = os.path.join("Assets", "Map", "OpenCoinBag.png")
        if os.path.exists(coin_bag_path):
            try:
                _coin_bag_bg = pygame.image.load(coin_bag_path).convert_alpha()
            except Exception as e:
                print(f"⚠️ Failed to load OpenCoinBag.png: {e}")
    
    if _gold_icon is None:
        gold_path = os.path.join("Assets", "Map", "Gold.png")
        if os.path.exists(gold_path):
            try:
                _gold_icon = pygame.image.load(gold_path).convert_alpha()
            except Exception as e:
                print(f"⚠️ Failed to load Gold.png: {e}")
    
    if _silver_icon is None:
        silver_path = os.path.join("Assets", "Map", "Silver.png")
        if os.path.exists(silver_path):
            try:
                _silver_icon = pygame.image.load(silver_path).convert_alpha()
            except Exception as e:
                print(f"⚠️ Failed to load Silver.png: {e}")
    
    if _bronze_icon is None:
        bronze_path = os.path.join("Assets", "Map", "Bronze.png")
        if os.path.exists(bronze_path):
            try:
                _bronze_icon = pygame.image.load(bronze_path).convert_alpha()
            except Exception as e:
                print(f"⚠️ Failed to load Bronze.png: {e}")

def is_open() -> bool:
    """Check if currency display is open."""
    return _is_open

def toggle():
    """Toggle currency display open/closed."""
    global _is_open, _fade_start_time
    _is_open = not _is_open
    if _is_open:
        _fade_start_time = pygame.time.get_ticks()

def close():
    """Close currency display."""
    global _is_open
    _is_open = False

def handle_event(event, gs) -> bool:
    """
    Handle events (clicks outside to close, ESC to close).
    Returns True if event was handled (should consume it).
    """
    if not _is_open:
        return False
    
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE or event.key == pygame.K_c:
            close()
            return True
    
    if event.type == pygame.MOUSEBUTTONDOWN:
        # Click outside popup to close
        width, height = pygame.display.get_surface().get_size()
        if _coin_bag_bg:
            panel_w, panel_h = _coin_bag_bg.get_size()
        else:
            panel_w, panel_h = 500, 350
        panel_x = (width - panel_w) // 2
        panel_y = (height - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        
        if event.button == 1 and not panel_rect.collidepoint(event.pos):
            close()
            return True
    
    return False

def draw(screen: pygame.Surface, gs):
    """Draw the currency display popup."""
    if not _is_open:
        return
    
    _load_assets()  # Ensure assets are loaded
    
    width, height = screen.get_width(), screen.get_height()
    current_time = pygame.time.get_ticks()
    
    # Fade animation
    fade_alpha = 1.0
    if _fade_start_time > 0:
        elapsed = (current_time - _fade_start_time) / 1000.0
        fade_alpha = min(1.0, max(0.0, elapsed / _fade_duration))
    
    # Dim background
    dim = pygame.Surface((width, height), pygame.SRCALPHA)
    dim.fill((0, 0, 0, int(180 * fade_alpha)))
    screen.blit(dim, (0, 0))
    
    # Use coin bag background image or fallback
    if _coin_bag_bg:
        coin_bag_w, coin_bag_h = _coin_bag_bg.get_size()
        # Scale to reasonable size (60% of screen)
        max_w = int(width * 0.6)
        max_h = int(height * 0.6)
        scale = min(max_w / coin_bag_w, max_h / coin_bag_h, 1.0)
        if scale < 1.0:
            scaled_bg = pygame.transform.smoothscale(_coin_bag_bg, (int(coin_bag_w * scale), int(coin_bag_h * scale)))
        else:
            scaled_bg = _coin_bag_bg
        panel_w, panel_h = scaled_bg.get_size()
    else:
        # Fallback panel if image missing
        panel_w, panel_h = 500, 350
        scaled_bg = None
    
    panel_x = (width - panel_w) // 2
    panel_y = (height - panel_h) // 2
    
    # Create panel surface
    if scaled_bg:
        panel = scaled_bg.copy()
    else:
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((40, 35, 30, int(255 * fade_alpha)))
        pygame.draw.rect(panel, (80, 70, 60, int(255 * fade_alpha)), panel.get_rect(), 3)
    
    # Load font for numbers
    try:
        dh_font_path = os.path.join(S.ASSETS_FONTS_DIR, S.DND_FONT_FILE)
        if os.path.exists(dh_font_path):
            currency_font = pygame.font.Font(dh_font_path, 36)  # Increased from 28
            hint_font = pygame.font.Font(dh_font_path, 18)
        else:
            currency_font = pygame.font.SysFont(None, 36)
            hint_font = pygame.font.SysFont(None, 18)
    except:
        currency_font = pygame.font.SysFont(None, 36)
        hint_font = pygame.font.SysFont(None, 18)
    
    # Get currency from game state
    gold = getattr(gs, "gold", 0)
    silver = getattr(gs, "silver", 0)
    bronze = getattr(gs, "bronze", 0)
    
    # Coin icon size (scale to fit nicely in the bag)
    coin_size = int(panel_h * 0.08)  # ~8% of bag height (bigger)
    icon_spacing = int(panel_h * 0.08)  # Vertical spacing between coins (close together)
    start_y = int(panel_h * 0.35)  # Start position (35% from top)
    icon_x = int(panel_w * 0.40)  # Left position for icons (40% from left)
    number_x = int(panel_w * 0.55)  # Right position for numbers (55% from left - much closer to icons)
    
    # Gold
    if _gold_icon:
        scaled_gold = pygame.transform.smoothscale(_gold_icon, (coin_size, coin_size))
        gold_y = start_y
        panel.blit(scaled_gold, (icon_x - scaled_gold.get_width() // 2, gold_y - scaled_gold.get_height() // 2))
    
    gold_text = currency_font.render(f"{gold}", True, (255, 255, 255))
    gold_y = start_y
    panel.blit(gold_text, (number_x - gold_text.get_width() // 2, gold_y - gold_text.get_height() // 2))
    
    # Silver
    if _silver_icon:
        scaled_silver = pygame.transform.smoothscale(_silver_icon, (coin_size, coin_size))
        silver_y = start_y + icon_spacing
        panel.blit(scaled_silver, (icon_x - scaled_silver.get_width() // 2, silver_y - scaled_silver.get_height() // 2))
    
    silver_text = currency_font.render(f"{silver}", True, (255, 255, 255))
    silver_y = start_y + icon_spacing
    panel.blit(silver_text, (number_x - silver_text.get_width() // 2, silver_y - silver_text.get_height() // 2))
    
    # Bronze
    if _bronze_icon:
        scaled_bronze = pygame.transform.smoothscale(_bronze_icon, (coin_size, coin_size))
        bronze_y = start_y + icon_spacing * 2
        panel.blit(scaled_bronze, (icon_x - scaled_bronze.get_width() // 2, bronze_y - scaled_bronze.get_height() // 2))
    
    bronze_text = currency_font.render(f"{bronze}", True, (255, 255, 255))
    bronze_y = start_y + icon_spacing * 2
    panel.blit(bronze_text, (number_x - bronze_text.get_width() // 2, bronze_y - bronze_text.get_height() // 2))
    
    # Close hint (only if using fallback panel)
    if not scaled_bg:
        hint = hint_font.render("Press C or ESC to close", True, (150, 150, 150))
        hint_rect = hint.get_rect(center=(panel_w // 2, panel_h - 30))
        panel.blit(hint, hint_rect)
    
    # Apply fade to panel
    if fade_alpha < 1.0:
        panel_surf = panel.copy()
        panel_surf.fill((255, 255, 255, int(255 * fade_alpha)), special_flags=pygame.BLEND_RGBA_MULT)
        panel = panel_surf
    
    screen.blit(panel, (panel_x, panel_y))

