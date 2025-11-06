# ============================================================
# systems/shop.py — Shop UI for Merchant Interactions
# - Displays purchasable items with icons, names, prices
# - Hover tooltips with medieval descriptions
# - Purchase functionality
# ============================================================

from __future__ import annotations
import os
import pygame
import importlib
import sys
import re
from typing import Optional, Dict, List

from systems import item_pricing
from systems import item_categories
from combat.team_randomizer import highest_party_level

# Import items system
try:
    from items import items as items_module
except:
    items_module = None

# --------------------- State ---------------------
_ITEM_RECTS = []
_HOVERED_ITEM_INDEX = None
_SCROLL_Y = 0
_LAST_ITEMS = []
_CURRENT_CATEGORY_INDEX = 0  # 0 = healing, 1 = catching, 2 = food
_LEFT_ARROW_RECT = None
_RIGHT_ARROW_RECT = None

# Purchase quantity selector state
_PURCHASE_SELECTOR_ACTIVE = False
_PURCHASE_ITEM_ID = None
_PURCHASE_QUANTITY = 1
_PURCHASE_MAX_QUANTITY = 1
_PURCHASE_CONFIRM_RECT = None
_PURCHASE_UP_ARROW_RECT = None
_PURCHASE_DOWN_ARROW_RECT = None
_PURCHASE_CANCEL_RECT = None

# --------------------- Font Cache ---------------------
_DH_FONT_CACHE = {}

def _dh_font(px: int) -> pygame.font.Font:
    """Load DH font with caching from Assets/Fonts/DH.otf or Assets/Fonts/DH."""
    px = max(12, int(px))
    if px not in _DH_FONT_CACHE:
        try:
            # Primary path: use settings configuration
            dh_font_path = None
            try:
                from settings import S
                # Use the configured font file from settings
                font_path = os.path.join(S.ASSETS_FONTS_DIR, S.DND_FONT_FILE)
                if os.path.exists(font_path):
                    dh_font_path = font_path
                else:
                    # Try "DH.otf" directly
                    path_with_ext = os.path.join(S.ASSETS_FONTS_DIR, "DH.otf")
                    if os.path.exists(path_with_ext):
                        dh_font_path = path_with_ext
                    else:
                        # Try "DH" without extension
                        path_no_ext = os.path.join(S.ASSETS_FONTS_DIR, "DH")
                        if os.path.exists(path_no_ext):
                            dh_font_path = path_no_ext
            except:
                pass
            
            # Fallback: try relative paths
            if not dh_font_path:
                possible_paths = [
                    os.path.join("Assets", "Fonts", "DH.otf"),
                    os.path.join("Assets", "Fonts", "DH"),
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        dh_font_path = path
                        break
            
            if dh_font_path and os.path.exists(dh_font_path):
                _DH_FONT_CACHE[px] = pygame.font.Font(dh_font_path, px)
            else:
                print(f"⚠️ DH font not found in Assets/Fonts/. Using fallback.")
                _DH_FONT_CACHE[px] = pygame.font.SysFont("arial", px)
        except Exception as e:
            print(f"⚠️ Error loading DH font: {e}")
            _DH_FONT_CACHE[px] = pygame.font.SysFont("arial", px)
    return _DH_FONT_CACHE[px]

# --------------------- Constants ---------------------
ROW_H = 72
ROW_GAP = 6
ICON_SZ = 64
SCROLL_SPEED = 36

# --------------------- Item Loading ---------------------

def _snake_from_name(s: str) -> str:
    s = (s or "").strip().replace("'", "'")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s.lower()

def _title_from_id(item_id: str) -> str:
    return item_id.replace("_", " ").title().replace(" Of ", " of ")

def _icon_for(item_id: str) -> Optional[str]:
    """Get icon path for an item (same logic as bag_action)."""
    # Handle special cases for items that don't follow the pattern
    special_names = {
        "rations": "Rations.png",
        "alcohol": "Alcohol.png",
    }
    if item_id in special_names:
        fname = special_names[item_id]
    else:
        fname = "_".join(part.capitalize() for part in item_id.split("_")) + ".png"
    path = os.path.join("Assets", "Items", fname)
    return path if os.path.exists(path) else None

def _get_item_data(item_id: str) -> Optional[Dict]:
    """Load item data from items module."""
    if not items_module:
        return None
    
    try:
        items_list = items_module.items() if hasattr(items_module, "items") else getattr(items_module, "ITEMS", [])
        for it in items_list:
            if isinstance(it, dict):
                iid = it.get("id") or _snake_from_name(it.get("name", ""))
                if iid == item_id:
                    return it
    except Exception:
        pass
    return None

def _get_shop_items() -> List[Dict]:
    """Get all purchasable items with their data."""
    purchasable_ids = item_pricing.get_all_purchasable_items()
    items = []
    
    for item_id in purchasable_ids:
        item_data = _get_item_data(item_id)
        icon = _icon_for(item_id)
        name = item_data.get("name") if item_data else _title_from_id(item_id)
        description = item_data.get("description", "A mystical scroll.") if item_data else "A mystical scroll."
        
        items.append({
            "id": item_id,
            "name": name,
            "icon": icon,
            "description": description,
        })
    
    return items

# --------------------- Icon Caching ---------------------
_ICON_CACHE = {}

def _draw_diamond(surface, center, size, color):
    """Draw a diamond/lozenge shape (for textbox corners)."""
    cx, cy = center
    pts = [
        (cx, cy - size // 2),
        (cx + size // 2, cy),
        (cx, cy + size // 2),
        (cx - size // 2, cy),
    ]
    pygame.draw.polygon(surface, color, pts)

def _get_icon_surface(path: str | None, size: int) -> Optional[pygame.Surface]:
    """Load and cache icon surfaces."""
    if not path or not os.path.exists(path):
        return None
    key = (path, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    try:
        base = pygame.image.load(path).convert_alpha()
        bw, bh = base.get_size()
        s = min(size / max(1, bw), size / max(1, bh))
        w, h = max(1, int(bw * s)), max(1, int(bh * s))
        surf = pygame.transform.smoothscale(base, (w, h))
        _ICON_CACHE[key] = surf
        return surf
    except Exception:
        _ICON_CACHE[key] = None
        return None

# --------------------- Medieval Descriptions ---------------------

_MEDIEVAL_DESCRIPTIONS = {
    "scroll_of_mending": "A humble scroll of minor restoration. Restores a small measure of vitality to wounded allies through gentle mending.",
    "scroll_of_healing": "A scroll of healing light. Channels restorative energies to mend wounds and restore health to battle-worn companions.",
    "scroll_of_regeneration": "A potent scroll of renewal. Calls upon greater healing forces to mend grievous wounds and restore vigor.",
    "scroll_of_revivity": "A sacred scroll of resurrection. Breathes life back into fallen allies, restoring them from death's grasp with renewed strength.",
    "scroll_of_command": "A basic scroll of binding. Attempts to command weaker vessels to submit, most effective when the target is already weakened.",
    "scroll_of_sealing": "An enhanced scroll of binding. Wields refined sigils that strengthen the binding ritual, making capture more likely.",
    "scroll_of_subjugation": "A powerful scroll of domination. Employs potent runes that force obedience, greatly improving the chance of successful capture.",
    "rations": "A bundle of preserved food and provisions. When used at a fireplace, restores all party members to full health through a long rest.",
    "alcohol": "A flask of strong spirits. When used at a fireplace, provides a short rest that restores half of each party member's health.",
}

def get_medieval_description(item_id: str) -> str:
    """Get medieval-style description for an item."""
    desc = _MEDIEVAL_DESCRIPTIONS.get(item_id)
    if desc:
        return desc
    
    # Fallback: use item description if available
    item_data = _get_item_data(item_id)
    if item_data and item_data.get("description"):
        return item_data["description"]
    
    return "A mystical scroll of unknown power."

# --------------------- Drawing ---------------------

def draw(screen: pygame.Surface, gs) -> None:
    """Draw the shop UI."""
    global _ITEM_RECTS, _HOVERED_ITEM_INDEX, _LAST_ITEMS, _SCROLL_Y, _CURRENT_CATEGORY_INDEX, _LEFT_ARROW_RECT, _RIGHT_ARROW_RECT
    
    width, height = screen.get_size()
    
    # Semi-transparent overlay
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))
    
    # Shop panel - textbox style
    panel_w, panel_h = 800, 600
    panel_x = (width - panel_w) // 2
    panel_y = (height - panel_h) // 2
    
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    # Textbox-style background (light like battle popup)
    panel.fill((245, 245, 245))  # Light background like textbox
    
    # Double border style (matching textbox/popup aesthetic)
    pygame.draw.rect(panel, (0, 0, 0), panel.get_rect(), 4, border_radius=8)  # Outer black border
    inner = panel.get_rect().inflate(-8, -8)
    pygame.draw.rect(panel, (60, 60, 60), inner, 2, border_radius=6)  # Inner dark gray border
    
    # Corner lozenges (like textbox)
    d = 10
    for cx, cy in (
        (8, 8),
        (panel_w - 8, 8),
        (8, panel_h - 8),
        (panel_w - 8, panel_h - 8),
    ):
        _draw_diamond(panel, (cx, cy), d, (60, 60, 60))
    
    # Use DH font
    title_font = _dh_font(36)
    name_font = _dh_font(22)
    price_font = _dh_font(18)
    tooltip_font = _dh_font(16)
    
    # Title (dark text like textbox)
    title = title_font.render("Merchant's Wares", True, (16, 16, 16))
    title_rect = title.get_rect(center=(panel_w // 2, 40))
    panel.blit(title, title_rect)
    
    # Get current category
    current_category = item_categories.CATEGORIES[_CURRENT_CATEGORY_INDEX]
    category_name = item_categories.get_category_name(current_category)
    
    # Category label
    category_label = name_font.render(category_name, True, (60, 60, 60))
    category_rect = category_label.get_rect(center=(panel_w // 2, 70))
    panel.blit(category_label, category_rect)
    
    # Get purchasable items and filter by current category
    all_items = _get_shop_items()
    items = item_categories.filter_items_by_category(all_items, current_category)
    _LAST_ITEMS = items
    
    # Reset scroll when category changes
    if not items:
        _SCROLL_Y = 0
    
    # Viewport for scrollable item list
    viewport_x = 50
    viewport_y = 100  # Moved down to make room for category label
    viewport_w = panel_w - 100
    viewport_h = panel_h - 180  # Adjusted for category label
    viewport_rect = pygame.Rect(viewport_x, viewport_y, viewport_w, viewport_h)
    
    # Get player level for pricing
    player_level = highest_party_level(gs)
    
    # Get player currency
    player_gold = getattr(gs, "gold", 0)
    player_silver = getattr(gs, "silver", 0)
    player_bronze = getattr(gs, "bronze", 0)
    
    # Mouse position relative to panel
    mx, my = pygame.mouse.get_pos()
    panel_mx = mx - panel_x
    panel_my = my - panel_y
    
    # Update hover
    _HOVERED_ITEM_INDEX = None
    _ITEM_RECTS = []
    
    # Draw items
    y = viewport_rect.y - _SCROLL_Y
    for idx, item in enumerate(items):
        row_rect = pygame.Rect(viewport_rect.x, y, viewport_rect.w, ROW_H)
        
        if row_rect.bottom < viewport_rect.top:
            y += ROW_H + ROW_GAP
            continue
        if row_rect.top > viewport_rect.bottom:
            break
        
        _ITEM_RECTS.append((row_rect, idx))
        
        # Check hover
        if row_rect.collidepoint(panel_mx, panel_my):
            _HOVERED_ITEM_INDEX = idx
            
            # Hover highlight (subtle like battle popup)
            hover = pygame.Surface((row_rect.w, row_rect.h), pygame.SRCALPHA)
            hover.fill((0, 0, 0, 28))  # Subtle black overlay like battle popup
            panel.blit(hover, row_rect.topleft)
        
        # Icon
        icon_path = item.get("icon")
        if icon_path:
            icon_surf = _get_icon_surface(icon_path, int(ROW_H * 0.9))
            if icon_surf:
                ir = icon_surf.get_rect()
                ir.midleft = (row_rect.x + 8, row_rect.centery)
                panel.blit(icon_surf, ir)
                name_x = ir.right + 12
            else:
                name_x = row_rect.x + 10
        else:
            name_x = row_rect.x + 10
        
        # Name (dark text like textbox)
        name = item.get("name", "")
        can_afford = _can_afford(item["id"], player_level, player_gold, player_silver, player_bronze)
        name_color = (16, 16, 16) if can_afford else (120, 120, 120)  # Dark text, gray if can't afford
        name_s = name_font.render(name, True, name_color)
        panel.blit(name_s, name_s.get_rect(midleft=(name_x, row_rect.centery)))
        
        # Price (right-aligned, dark text) - abbreviated for shop UI
        price = item_pricing.get_item_price(item["id"], player_level)
        if price:
            gold, silver, bronze = price
            # Format as abbreviated (gp, sp, bp) for shop UI
            parts = []
            if gold > 0:
                parts.append(f"{gold} gp")
            if silver > 0:
                parts.append(f"{silver} sp")
            if bronze > 0:
                parts.append(f"{bronze} bp")
            price_text = ", ".join(parts) if parts else "0 bp"
            price_color = (40, 40, 40) if can_afford else (150, 100, 100)  # Dark text, red-ish if can't afford
            price_s = price_font.render(price_text, True, price_color)
            price_rect = price_s.get_rect(midright=(row_rect.right - 20, row_rect.centery))
            panel.blit(price_s, price_rect)
        
        y += ROW_H + ROW_GAP
    
    # Draw tooltip if hovering
    if _HOVERED_ITEM_INDEX is not None and _HOVERED_ITEM_INDEX < len(items):
        item = items[_HOVERED_ITEM_INDEX]
        tooltip_text = get_medieval_description(item["id"])
        
        # Wrap text
        words = tooltip_text.split()
        lines = []
        current_line = ""
        max_width = 300
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if tooltip_font.size(test_line)[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        # Draw tooltip box
        tooltip_padding = 12
        tooltip_w = max(250, max([tooltip_font.size(line)[0] for line in lines]) + tooltip_padding * 2)
        tooltip_h = len(lines) * 22 + tooltip_padding * 2
        
        tooltip_x = min(panel_mx + 20, panel_w - tooltip_w - 20)
        tooltip_y = panel_my - tooltip_h - 10
        
        # Make sure tooltip stays in panel
        if tooltip_y < 60:
            tooltip_y = panel_my + 30
        
        tooltip_rect = pygame.Rect(tooltip_x, tooltip_y, tooltip_w, tooltip_h)
        tooltip_bg = pygame.Surface((tooltip_w, tooltip_h), pygame.SRCALPHA)
        # Match textbox style
        tooltip_bg.fill((245, 245, 245))
        pygame.draw.rect(tooltip_bg, (0, 0, 0), tooltip_bg.get_rect(), 4, border_radius=8)
        inner_tooltip = tooltip_bg.get_rect().inflate(-8, -8)
        pygame.draw.rect(tooltip_bg, (60, 60, 60), inner_tooltip, 2, border_radius=6)
        panel.blit(tooltip_bg, tooltip_rect.topleft)
        
        # Draw text (dark like textbox)
        text_y = tooltip_rect.y + tooltip_padding
        for line in lines:
            line_s = tooltip_font.render(line, True, (16, 16, 16))
            panel.blit(line_s, (tooltip_rect.x + tooltip_padding, text_y))
            text_y += 22
    
    # Close hint (dark text like textbox)
    hint = price_font.render("Press ESC to close | Click item to purchase", True, (60, 60, 60))
    hint_rect = hint.get_rect(center=(panel_w // 2, panel_h - 50))
    panel.blit(hint, hint_rect)
    
    # Draw navigation arrows (cycling enabled)
    global _LEFT_ARROW_RECT, _RIGHT_ARROW_RECT
    arrow_size = 48
    arrow_y = panel_h - 45
    arrow_tip_size = 16
    arrow_color = (60, 60, 60)
    arrow_hover_color = (100, 100, 100)
    
    # Left arrow (triangle pointing left)
    left_arrow_x = 30
    _LEFT_ARROW_RECT = pygame.Rect(left_arrow_x - arrow_size // 2, arrow_y - arrow_size // 2, arrow_size, arrow_size)
    arrow_points = [
        (left_arrow_x, arrow_y),
        (left_arrow_x + arrow_tip_size, arrow_y - arrow_tip_size),
        (left_arrow_x + arrow_tip_size, arrow_y + arrow_tip_size),
    ]
    draw_color = arrow_hover_color if _LEFT_ARROW_RECT.collidepoint(panel_mx, panel_my) else arrow_color
    pygame.draw.polygon(panel, draw_color, arrow_points)
    
    # Right arrow (triangle pointing right)
    right_arrow_x = panel_w - 30
    _RIGHT_ARROW_RECT = pygame.Rect(right_arrow_x - arrow_size // 2, arrow_y - arrow_size // 2, arrow_size, arrow_size)
    arrow_points = [
        (right_arrow_x, arrow_y),
        (right_arrow_x - arrow_tip_size, arrow_y - arrow_tip_size),
        (right_arrow_x - arrow_tip_size, arrow_y + arrow_tip_size),
    ]
    draw_color = arrow_hover_color if _RIGHT_ARROW_RECT.collidepoint(panel_mx, panel_my) else arrow_color
    pygame.draw.polygon(panel, draw_color, arrow_points)
    
    # Blit panel to screen
    screen.blit(panel, (panel_x, panel_y))
    
    # Draw purchase quantity selector if active
    if _PURCHASE_SELECTOR_ACTIVE and _PURCHASE_ITEM_ID:
        _draw_purchase_selector(screen, gs, panel_x, panel_y)

def _draw_purchase_selector(screen: pygame.Surface, gs, panel_x: int, panel_y: int):
    """Draw the purchase quantity selector overlay."""
    global _PURCHASE_CONFIRM_RECT, _PURCHASE_UP_ARROW_RECT, _PURCHASE_DOWN_ARROW_RECT, _PURCHASE_CANCEL_RECT
    
    selector_w, selector_h = 400, 200
    selector_x = panel_x + (800 - selector_w) // 2
    selector_y = panel_y + (600 - selector_h) // 2
    
    selector_rect = pygame.Rect(selector_x, selector_y, selector_w, selector_h)
    
    # Selector panel (textbox style)
    selector_surf = pygame.Surface((selector_w, selector_h), pygame.SRCALPHA)
    selector_surf.fill((245, 245, 245))
    pygame.draw.rect(selector_surf, (0, 0, 0), selector_surf.get_rect(), 4, border_radius=8)
    inner = selector_surf.get_rect().inflate(-8, -8)
    pygame.draw.rect(selector_surf, (60, 60, 60), inner, 2, border_radius=6)
    
    # Get item info
    item_data = _get_item_data(_PURCHASE_ITEM_ID)
    item_name = item_data.get("name") if item_data else _title_from_id(_PURCHASE_ITEM_ID)
    
    # Fonts
    title_font = _dh_font(24)
    qty_font = _dh_font(32)
    button_font = _dh_font(18)
    
    # Title
    title_text = f"Purchase {item_name}"
    title_surf = title_font.render(title_text, True, (16, 16, 16))
    title_rect = title_surf.get_rect(center=(selector_w // 2, 30))
    selector_surf.blit(title_surf, title_rect)
    
    # Quantity display with arrows
    qty_y = selector_h // 2 - 10
    qty_x = selector_w // 2
    
    # Down arrow (left)
    arrow_size = 20
    down_arrow_x = qty_x - 80
    down_arrow_rect = pygame.Rect(down_arrow_x - arrow_size, qty_y - arrow_size // 2, arrow_size * 2, arrow_size)
    _PURCHASE_DOWN_ARROW_RECT = pygame.Rect(selector_x + down_arrow_x - arrow_size, selector_y + qty_y - arrow_size // 2, arrow_size * 2, arrow_size)
    
    # Draw down arrow (triangle pointing down)
    arrow_points = [
        (down_arrow_x, qty_y + arrow_size // 2),
        (down_arrow_x - arrow_size // 2, qty_y - arrow_size // 2),
        (down_arrow_x + arrow_size // 2, qty_y - arrow_size // 2),
    ]
    pygame.draw.polygon(selector_surf, (16, 16, 16) if _PURCHASE_QUANTITY > 1 else (120, 120, 120), arrow_points)
    
    # Quantity number
    qty_surf = qty_font.render(str(_PURCHASE_QUANTITY), True, (16, 16, 16))
    qty_rect = qty_surf.get_rect(center=(qty_x, qty_y))
    selector_surf.blit(qty_surf, qty_rect)
    
    # Up arrow (right)
    up_arrow_x = qty_x + 80
    up_arrow_rect = pygame.Rect(up_arrow_x - arrow_size, qty_y - arrow_size // 2, arrow_size * 2, arrow_size)
    _PURCHASE_UP_ARROW_RECT = pygame.Rect(selector_x + up_arrow_x - arrow_size, selector_y + qty_y - arrow_size // 2, arrow_size * 2, arrow_size)
    
    # Draw up arrow (triangle pointing up)
    arrow_points = [
        (up_arrow_x, qty_y - arrow_size // 2),
        (up_arrow_x - arrow_size // 2, qty_y + arrow_size // 2),
        (up_arrow_x + arrow_size // 2, qty_y + arrow_size // 2),
    ]
    pygame.draw.polygon(selector_surf, (16, 16, 16) if _PURCHASE_QUANTITY < _PURCHASE_MAX_QUANTITY else (120, 120, 120), arrow_points)
    
    # Total price
    player_level = highest_party_level(gs)
    price_per = item_pricing.get_item_price_bronze(_PURCHASE_ITEM_ID, player_level) or 0
    total_price = price_per * _PURCHASE_QUANTITY
    
    total_gold = total_price // 100
    remainder = total_price % 100
    total_silver = remainder // 10
    total_bronze = remainder % 10
    
    # Format as abbreviated (gp, sp, bp) for shop UI
    parts = []
    if total_gold > 0:
        parts.append(f"{total_gold} gp")
    if total_silver > 0:
        parts.append(f"{total_silver} sp")
    if total_bronze > 0:
        parts.append(f"{total_bronze} bp")
    price_text = ", ".join(parts) if parts else "0 bp"
    price_surf = button_font.render(f"Total: {price_text}", True, (16, 16, 16))
    price_rect = price_surf.get_rect(center=(selector_w // 2, qty_y + 35))
    selector_surf.blit(price_surf, price_rect)
    
    # Buttons
    button_h = 35
    button_y = selector_h - button_h - 20
    button_w = 100
    button_gap = 20
    
    # Cancel button (left)
    cancel_x = selector_w // 2 - button_w - button_gap // 2
    cancel_rect = pygame.Rect(cancel_x, button_y, button_w, button_h)
    _PURCHASE_CANCEL_RECT = pygame.Rect(selector_x + cancel_x, selector_y + button_y, button_w, button_h)
    
    pygame.draw.rect(selector_surf, (200, 200, 200), cancel_rect, border_radius=4)
    pygame.draw.rect(selector_surf, (60, 60, 60), cancel_rect, 2, border_radius=4)
    cancel_text = button_font.render("Cancel", True, (16, 16, 16))
    cancel_text_rect = cancel_text.get_rect(center=cancel_rect.center)
    selector_surf.blit(cancel_text, cancel_text_rect)
    
    # Confirm button (right)
    confirm_x = selector_w // 2 + button_gap // 2
    confirm_rect = pygame.Rect(confirm_x, button_y, button_w, button_h)
    _PURCHASE_CONFIRM_RECT = pygame.Rect(selector_x + confirm_x, selector_y + button_y, button_w, button_h)
    
    pygame.draw.rect(selector_surf, (180, 220, 180), confirm_rect, border_radius=4)
    pygame.draw.rect(selector_surf, (60, 60, 60), confirm_rect, 2, border_radius=4)
    confirm_text = button_font.render("Confirm", True, (16, 16, 16))
    confirm_text_rect = confirm_text.get_rect(center=confirm_rect.center)
    selector_surf.blit(confirm_text, confirm_text_rect)
    
    # Blit selector to screen
    screen.blit(selector_surf, selector_rect.topleft)

def reset_scroll():
    """Reset scroll position (call when shop opens/closes)."""
    global _SCROLL_Y, _CURRENT_CATEGORY_INDEX
    _SCROLL_Y = 0
    _CURRENT_CATEGORY_INDEX = 0  # Reset to first category (healing)

def _can_afford(item_id: str, player_level: int, player_gold: int, player_silver: int, player_bronze: int) -> bool:
    """Check if player can afford an item."""
    return item_pricing.can_afford_item(item_id, player_level, player_gold, player_silver, player_bronze)

def handle_event(event, gs) -> bool:
    """Handle shop events. Returns True if event was handled."""
    global _SCROLL_Y, _PURCHASE_QUANTITY, _PURCHASE_MAX_QUANTITY, _CURRENT_CATEGORY_INDEX
    
    if not gs.shop_open:
        return False
    
    # Keyboard navigation
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_LEFT:
            _CURRENT_CATEGORY_INDEX = (_CURRENT_CATEGORY_INDEX - 1) % len(item_categories.CATEGORIES)
            _SCROLL_Y = 0
            try:
                from systems import audio as audio_sys
                audio_sys.play_click(audio_sys.get_global_bank())
            except:
                pass
            return True
        elif event.key == pygame.K_RIGHT:
            _CURRENT_CATEGORY_INDEX = (_CURRENT_CATEGORY_INDEX + 1) % len(item_categories.CATEGORIES)
            _SCROLL_Y = 0
            try:
                from systems import audio as audio_sys
                audio_sys.play_click(audio_sys.get_global_bank())
            except:
                pass
            return True
    
    if event.type == pygame.MOUSEBUTTONDOWN:
        if event.button == 1:  # Left click
            # Check if clicked on an item (use logical resolution)
            import settings as S
            width, height = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
            panel_w, panel_h = 800, 600
            panel_x = (width - panel_w) // 2
            panel_y = (height - panel_h) // 2
            
            mx, my = event.pos  # Already converted to logical coordinates in main.py
            panel_mx = mx - panel_x
            panel_my = my - panel_y
            
            # Check navigation arrows first (cycling enabled)
            if _LEFT_ARROW_RECT and _LEFT_ARROW_RECT.collidepoint(panel_mx, panel_my):
                # Cycle backwards (wrap around)
                _CURRENT_CATEGORY_INDEX = (_CURRENT_CATEGORY_INDEX - 1) % len(item_categories.CATEGORIES)
                _SCROLL_Y = 0  # Reset scroll when changing category
                try:
                    from systems import audio as audio_sys
                    audio_sys.play_click(audio_sys.get_global_bank())
                except:
                    pass
                return True
            
            if _RIGHT_ARROW_RECT and _RIGHT_ARROW_RECT.collidepoint(panel_mx, panel_my):
                # Cycle forwards (wrap around)
                _CURRENT_CATEGORY_INDEX = (_CURRENT_CATEGORY_INDEX + 1) % len(item_categories.CATEGORIES)
                _SCROLL_Y = 0  # Reset scroll when changing category
                try:
                    from systems import audio as audio_sys
                    audio_sys.play_click(audio_sys.get_global_bank())
                except:
                    pass
                return True
            
            # Check if clicking on purchase selector UI
            if _PURCHASE_SELECTOR_ACTIVE:
                # Use screen coordinates for selector rects
                if _PURCHASE_UP_ARROW_RECT and _PURCHASE_UP_ARROW_RECT.collidepoint(mx, my):
                    if _PURCHASE_QUANTITY < _PURCHASE_MAX_QUANTITY:
                        _PURCHASE_QUANTITY += 1
                        # Play click sound
                        try:
                            from systems import audio
                            # Try to get AUDIO from main module
                            import sys
                            main_module = sys.modules.get('__main__')
                            if main_module and hasattr(main_module, 'AUDIO'):
                                audio.play_click(getattr(main_module, 'AUDIO'))
                        except:
                            pass
                    return True
                elif _PURCHASE_DOWN_ARROW_RECT and _PURCHASE_DOWN_ARROW_RECT.collidepoint(mx, my):
                    if _PURCHASE_QUANTITY > 1:
                        _PURCHASE_QUANTITY -= 1
                        # Play click sound
                        try:
                            from systems import audio
                            # Try to get AUDIO from main module
                            import sys
                            main_module = sys.modules.get('__main__')
                            if main_module and hasattr(main_module, 'AUDIO'):
                                audio.play_click(getattr(main_module, 'AUDIO'))
                        except:
                            pass
                    return True
                elif _PURCHASE_CONFIRM_RECT and _PURCHASE_CONFIRM_RECT.collidepoint(mx, my):
                    # Confirm purchase
                    if _PURCHASE_ITEM_ID:
                        success = _confirm_purchase(gs, _PURCHASE_ITEM_ID, _PURCHASE_QUANTITY)
                        _close_purchase_selector()
                        if success:
                            return "purchase_confirmed"  # Signal to main.py to play laugh
                    return True
                elif _PURCHASE_CANCEL_RECT and _PURCHASE_CANCEL_RECT.collidepoint(mx, my):
                    # Cancel purchase
                    _close_purchase_selector()
                    return True
                # Click outside selector closes it
                elif not _purchase_selector_rect().collidepoint(mx, my):
                    _close_purchase_selector()
                    return True
            
            # Check clicks on items
            if not _PURCHASE_SELECTOR_ACTIVE:
                for row_rect, idx in _ITEM_RECTS:
                    if row_rect.collidepoint(panel_mx, panel_my):
                        if idx < len(_LAST_ITEMS):
                            item = _LAST_ITEMS[idx]
                            # Play click sound
                            try:
                                from systems import audio
                                # Try to get AUDIO from main module
                                import sys
                                main_module = sys.modules.get('__main__')
                                if main_module and hasattr(main_module, 'AUDIO'):
                                    audio.play_click(getattr(main_module, 'AUDIO'))
                            except:
                                pass
                            # Open quantity selector
                            _open_purchase_selector(gs, item["id"])
                            return True
            
            # Click outside panel closes shop
            if not pygame.Rect(panel_x, panel_y, panel_w, panel_h).collidepoint(mx, my):
                gs.shop_open = False
                return True
                
        elif event.button == 4:  # Scroll up
            _SCROLL_Y = max(0, _SCROLL_Y - SCROLL_SPEED)
            return True
        elif event.button == 5:  # Scroll down
            # Calculate max scroll
            panel_h = 600  # Same as in draw()
            viewport_h = panel_h - 160  # Same as in draw()
            total_h = len(_LAST_ITEMS) * (ROW_H + ROW_GAP)
            max_scroll = max(0, total_h - viewport_h)
            _SCROLL_Y = min(max_scroll, _SCROLL_Y + SCROLL_SPEED)
            return True
    
    return False

def _open_purchase_selector(gs, item_id: str):
    """Open the purchase quantity selector."""
    global _PURCHASE_SELECTOR_ACTIVE, _PURCHASE_ITEM_ID, _PURCHASE_QUANTITY, _PURCHASE_MAX_QUANTITY
    
    player_level = highest_party_level(gs)
    player_gold = getattr(gs, "gold", 0)
    player_silver = getattr(gs, "silver", 0)
    player_bronze = getattr(gs, "bronze", 0)
    
    if not item_pricing.can_afford_item(item_id, player_level, player_gold, player_silver, player_bronze):
        return
    
    # Get price per item
    price_bronze = item_pricing.get_item_price_bronze(item_id, player_level)
    if price_bronze is None or price_bronze == 0:
        return
    
    # Calculate max affordable quantity
    player_total_bronze = player_gold * 100 + player_silver * 10 + player_bronze
    _PURCHASE_MAX_QUANTITY = player_total_bronze // price_bronze
    
    if _PURCHASE_MAX_QUANTITY <= 0:
        return
    
    _PURCHASE_SELECTOR_ACTIVE = True
    _PURCHASE_ITEM_ID = item_id
    _PURCHASE_QUANTITY = 1

def _close_purchase_selector():
    """Close the purchase quantity selector."""
    global _PURCHASE_SELECTOR_ACTIVE, _PURCHASE_ITEM_ID, _PURCHASE_QUANTITY, _PURCHASE_MAX_QUANTITY
    global _PURCHASE_CONFIRM_RECT, _PURCHASE_UP_ARROW_RECT, _PURCHASE_DOWN_ARROW_RECT, _PURCHASE_CANCEL_RECT
    
    _PURCHASE_SELECTOR_ACTIVE = False
    _PURCHASE_ITEM_ID = None
    _PURCHASE_QUANTITY = 1
    _PURCHASE_MAX_QUANTITY = 1
    _PURCHASE_CONFIRM_RECT = None
    _PURCHASE_UP_ARROW_RECT = None
    _PURCHASE_DOWN_ARROW_RECT = None
    _PURCHASE_CANCEL_RECT = None

def _purchase_selector_rect() -> pygame.Rect:
    """Get the purchase selector panel rect."""
    width, height = pygame.display.get_surface().get_size()
    panel_w, panel_h = 800, 600
    panel_x = (width - panel_w) // 2
    panel_y = (height - panel_h) // 2
    
    selector_w, selector_h = 400, 200
    selector_x = panel_x + (panel_w - selector_w) // 2
    selector_y = panel_y + (panel_h - selector_h) // 2
    
    return pygame.Rect(selector_x, selector_y, selector_w, selector_h)

def _confirm_purchase(gs, item_id: str, quantity: int) -> bool:
    """Purchase multiple items. Returns True if purchase was successful."""
    player_level = highest_party_level(gs)
    player_gold = getattr(gs, "gold", 0)
    player_silver = getattr(gs, "silver", 0)
    player_bronze = getattr(gs, "bronze", 0)
    
    # Get price per item
    price_bronze = item_pricing.get_item_price_bronze(item_id, player_level)
    if price_bronze is None:
        return False
    
    total_cost = price_bronze * quantity
    
    # Check affordability
    player_total_bronze = player_gold * 100 + player_silver * 10 + player_bronze
    if player_total_bronze < total_cost:
        return False
    
    # Deduct currency
    new_total_bronze = player_total_bronze - total_cost
    
    # Convert back to denominations
    gs.gold = new_total_bronze // 100
    remainder = new_total_bronze % 100
    gs.silver = remainder // 10
    gs.bronze = remainder % 10
    
    # Add items to inventory
    if not hasattr(gs, "inventory") or gs.inventory is None:
        gs.inventory = {}
    if not isinstance(gs.inventory, dict):
        # Convert to dict
        gs.inventory = {str(k): int(v) for k, v in gs.inventory.items() if isinstance(v, (int, float))}
    
    gs.inventory[item_id] = gs.inventory.get(item_id, 0) + quantity
    
    return True

def _purchase_item(gs, item_id: str) -> bool:
    """Purchase an item. Returns True if purchase was successful."""
    player_level = highest_party_level(gs)
    player_gold = getattr(gs, "gold", 0)
    player_silver = getattr(gs, "silver", 0)
    player_bronze = getattr(gs, "bronze", 0)
    
    if not item_pricing.can_afford_item(item_id, player_level, player_gold, player_silver, player_bronze):
        # TODO: Play error sound
        print(f"Cannot afford {item_id}")
        return False
    
    # Get price
    price_bronze = item_pricing.get_item_price_bronze(item_id, player_level)
    if price_bronze is None:
        return False
    
    # Deduct currency
    player_total_bronze = player_gold * 100 + player_silver * 10 + player_bronze
    new_total_bronze = player_total_bronze - price_bronze
    
    if new_total_bronze < 0:
        return False
    
    # Convert back to denominations
    gs.gold = new_total_bronze // 100
    remainder = new_total_bronze % 100
    gs.silver = remainder // 10
    gs.bronze = remainder % 10
    
    # Add item to inventory
    if not hasattr(gs, "inventory") or gs.inventory is None:
        gs.inventory = {}
    if not isinstance(gs.inventory, dict):
        # Convert to dict
        gs.inventory = {str(k): int(v) for k, v in gs.inventory.items() if isinstance(v, (int, float))}
    
    gs.inventory[item_id] = gs.inventory.get(item_id, 0) + 1
    
    # Play purchase sound
    try:
        from systems import audio
        from settings import S
        audio_sys = audio.AudioSystem()
        audio_sys.play_click(audio_sys.get_global_bank())
    except:
        pass
    
    return True

