# Popup & Button Development Guide

## Important: Coordinate System & Event Handling for Popups/Buttons

When creating new popups, buttons, or clickable UI elements, **always follow these rules** to ensure compatibility with different screen sizes and display modes (fullscreen/windowed).

## ⚠️ CRITICAL: Event Coordinate Conversion

**MANDATORY RULE**: Events passed to handlers (`handle()`, `handle_event()`, etc.) **already have `event.pos` converted to logical coordinates** in `main.py`. **DO NOT convert them again!**

### Why This Matters

In `main.py` (lines 1178-1188), all mouse events are automatically converted to logical coordinates before being passed to screen/component handlers:

```python
# Convert mouse coordinates in events to logical coordinates
converted_events = []
for e in events:
    if hasattr(e, 'pos') and e.pos is not None:
        # Create a new event with converted coordinates
        new_e = pygame.event.Event(e.type, e.dict)
        new_e.pos = coords.screen_to_logical(e.pos)  # ← Already converted!
        converted_events.append(new_e)
    else:
        converted_events.append(e)
events = converted_events
```

This means **every event handler receives `event.pos` already in logical coordinates**. Converting again causes misalignment!

### ✅ CORRECT Pattern

```python
def handle(events, gs, **kwargs):
    for event in events:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # ✅ CORRECT - event.pos is already in logical coordinates
            click_pos = event.pos
            
            if my_button_rect.collidepoint(click_pos):
                # Handle click
                pass
```

### ❌ WRONG Pattern (Double Conversion)

```python
def handle(events, gs, **kwargs):
    for event in events:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # ❌ WRONG - Don't convert again! event.pos is already converted
            from systems import coords
            click_pos = coords.screen_to_logical(event.pos)  # ← Double conversion!
            
            if my_button_rect.collidepoint(click_pos):
                # Handle click
                pass
```

## 📋 Rules for Popups/Buttons

### 1. Use Logical Coordinates for All UI Elements

**Always use `S.LOGICAL_WIDTH` and `S.LOGICAL_HEIGHT` for positioning:**

```python
# ✅ CORRECT - Use logical resolution constants
sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
popup_w, popup_h = 500, 300
popup_x = (sw - popup_w) // 2
popup_y = (sh - popup_h) // 2
popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)

# ❌ WRONG - Don't use physical screen size
sw, sh = S.WIDTH, S.HEIGHT  # These change with display mode!
popup_x = (sw - popup_w) // 2  # Wrong!
```

### 2. Store Button Rects in Logical Coordinates

**Button rects must be stored in logical coordinates (same as drawing):**

```python
def draw(screen, gs, **kwargs):
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    
    # Calculate button positions using logical coordinates
    button_w, button_h = 160, 52
    button_x = (sw - button_w) // 2
    button_y = sh // 2
    
    button_rect = pygame.Rect(button_x, button_y, button_w, button_h)
    
    # Store rect in game state (for click detection)
    gs._my_button_rect = button_rect
    
    # Draw button
    pygame.draw.rect(screen, (200, 200, 200), button_rect)
```

### 3. Use event.pos Directly (Already Converted)

**In event handlers, use `event.pos` directly - it's already in logical coordinates:**

```python
def handle(events, gs, **kwargs):
    for event in events:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # ✅ CORRECT - event.pos is already converted
            click_pos = event.pos
            
            button_rect = getattr(gs, "_my_button_rect", None)
            if button_rect and button_rect.collidepoint(click_pos):
                # Handle click
                return "ACTION"
```

### 4. Hover Detection Uses Logical Coordinates

**For hover detection in draw functions, convert mouse position:**

```python
def draw(screen, gs, **kwargs):
    # Get mouse position for hover detection - convert to logical coordinates
    screen_mx, screen_my = pygame.mouse.get_pos()
    try:
        from systems import coords
        mx, my = coords.screen_to_logical((screen_mx, screen_my))
    except (ImportError, AttributeError):
        # Fallback if coords not available
        mx, my = screen_mx, screen_my
    
    # Check hover using converted coordinates
    hover = button_rect.collidepoint(mx, my)
    
    # Draw button with hover effect
    color = (255, 255, 255) if hover else (200, 200, 200)
    pygame.draw.rect(screen, color, button_rect)
```

**Note**: Hover detection in `draw()` needs conversion because `pygame.mouse.get_pos()` returns screen coordinates. But `event.pos` in handlers is already converted!

### 5. Add Hover Detection to cursor_manager.py

**For cursor changes, add hover detection to `cursor_manager.py`:**

```python
# In systems/cursor_manager.py, inside _is_hovering_clickable()

# ==================== YOUR POPUP/BUTTON ====================
if mode and "YOUR_MODE" in mode_str:
    try:
        if gs and hasattr(gs, '_your_button_rect'):
            button_rect = gs._your_button_rect
            if button_rect and button_rect.collidepoint(logical_pos):
                return True
    except:
        pass
```

**Important**: `cursor_manager.py` receives `logical_pos` which is already converted, so use it directly!

## 📝 Complete Popup Example

Here's a complete example following all the rules:

```python
# popup_example.py

import pygame
import settings as S

def draw(screen, gs, fonts=None, **kwargs):
    """Draw a confirmation popup."""
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    
    # Popup dimensions (logical coordinates)
    popup_w, popup_h = 520, 240
    popup_x = (sw - popup_w) // 2
    popup_y = (sh - popup_h) // 2
    popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
    
    # Draw overlay (logical size)
    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    screen.blit(overlay, (0, 0))
    
    # Draw popup background
    pygame.draw.rect(screen, (40, 35, 30), popup_rect, border_radius=12)
    pygame.draw.rect(screen, (80, 70, 60), popup_rect, 2, border_radius=12)
    
    # Button dimensions
    btn_w, btn_h = 160, 52
    btn_spacing = 200
    btn_y = popup_rect.y + 160
    
    # Yes button
    yes_btn_rect = pygame.Rect(0, 0, btn_w, btn_h)
    yes_btn_rect.center = (popup_rect.centerx - btn_spacing // 2, btn_y)
    
    # No button
    no_btn_rect = pygame.Rect(0, 0, btn_w, btn_h)
    no_btn_rect.center = (popup_rect.centerx + btn_spacing // 2, btn_y)
    
    # Get mouse position for hover (convert to logical)
    screen_mx, screen_my = pygame.mouse.get_pos()
    try:
        from systems import coords
        mx, my = coords.screen_to_logical((screen_mx, screen_my))
    except (ImportError, AttributeError):
        mx, my = screen_mx, screen_my
    
    # Draw Yes button with hover
    yes_hover = yes_btn_rect.collidepoint(mx, my)
    yes_color = (255, 255, 255) if yes_hover else (200, 200, 200)
    pygame.draw.rect(screen, yes_color, yes_btn_rect, border_radius=12)
    
    # Draw No button with hover
    no_hover = no_btn_rect.collidepoint(mx, my)
    no_color = (255, 255, 255) if no_hover else (200, 200, 200)
    pygame.draw.rect(screen, no_color, no_btn_rect, border_radius=12)
    
    # Store button rects for click detection (logical coordinates)
    gs._popup_yes_rect = yes_btn_rect
    gs._popup_no_rect = no_btn_rect

def handle(events, gs, **kwargs):
    """Handle popup events."""
    popup_active = getattr(gs, "_popup_active", False)
    
    if not popup_active:
        return None
    
    for event in events:
        # ESC closes popup
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            gs._popup_active = False
            return None
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # ✅ CORRECT - event.pos is already in logical coordinates
            click_pos = event.pos
            
            yes_rect = getattr(gs, "_popup_yes_rect", None)
            no_rect = getattr(gs, "_popup_no_rect", None)
            
            if yes_rect and yes_rect.collidepoint(click_pos):
                # Yes clicked
                gs._popup_active = False
                return "YES_ACTION"
            
            elif no_rect and no_rect.collidepoint(click_pos):
                # No clicked
                gs._popup_active = False
                return None
            
            # Click outside popup closes it
            popup_w, popup_h = 520, 240
            popup_x = (S.LOGICAL_WIDTH - popup_w) // 2
            popup_y = (S.LOGICAL_HEIGHT - popup_h) // 2
            popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
            
            if not popup_rect.collidepoint(click_pos):
                # Clicked outside - close popup
                gs._popup_active = False
                return None
    
    # Popup is active - block other input
    return None
```

## 🔍 Quick Checklist

Before committing a new popup/button, verify:

- [ ] All drawing uses `S.LOGICAL_WIDTH` and `S.LOGICAL_HEIGHT` (not `S.WIDTH`/`S.HEIGHT`)
- [ ] Button rects are stored in logical coordinates
- [ ] Event handlers use `event.pos` directly (no conversion)
- [ ] Hover detection in `draw()` converts `pygame.mouse.get_pos()` to logical coordinates
- [ ] Hover detection added to `cursor_manager.py` (uses `logical_pos` directly)
- [ ] Surface creation uses logical size: `(S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT)`
- [ ] No use of `screen.get_size()` for positioning/drawing
- [ ] Tested in both windowed and fullscreen modes

## 🐛 Common Mistakes to Avoid

1. **❌ Don't convert `event.pos` again** - It's already converted in main.py!
   ```python
   # ❌ WRONG
   click_pos = coords.screen_to_logical(event.pos)
   
   # ✅ CORRECT
   click_pos = event.pos
   ```

2. **❌ Don't use `S.WIDTH`/`S.HEIGHT`** - These change with display mode!
   ```python
   # ❌ WRONG
   popup_x = (S.WIDTH - popup_w) // 2
   
   # ✅ CORRECT
   popup_x = (S.LOGICAL_WIDTH - popup_w) // 2
   ```

3. **❌ Don't forget to convert mouse position in `draw()`** - `pygame.mouse.get_pos()` returns screen coordinates!
   ```python
   # ❌ WRONG (for hover detection in draw)
   mx, my = pygame.mouse.get_pos()
   
   # ✅ CORRECT (for hover detection in draw)
   screen_mx, screen_my = pygame.mouse.get_pos()
   mx, my = coords.screen_to_logical((screen_mx, screen_my))
   ```

4. **❌ Don't use `screen.get_size()`** - With `pygame.SCALED` flag, this can return wrong values!
   ```python
   # ❌ WRONG
   sw, sh = screen.get_size()
   
   # ✅ CORRECT
   sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
   ```

5. **❌ Don't forget to add hover detection to cursor_manager.py** - Cursor won't change without it!

## 📚 Files That Follow This Pattern

These files are good examples to reference:
- `screens/menu_screen.py` - Menu popups (yes/no buttons)
- `world/Tavern/tavern.py` - Game selection popup
- `systems/shop.py` - Shop purchase selector popup
- `systems/hud_buttons.py` - HUD buttons
- `combat/btn/bag_action.py` - Bag popup
- `combat/btn/party_action.py` - Party popup with confirmation

## 🔗 Related Files

- `systems/coords.py` - Coordinate conversion system
- `settings.py` - Contains `LOGICAL_WIDTH` and `LOGICAL_HEIGHT` constants
- `main.py` - Main loop that handles coordinate conversion for events (lines 1178-1188)
- `systems/cursor_manager.py` - Cursor hover detection

---

**Remember**: The game uses a fixed logical resolution (1920x1080) internally, which is then scaled to fit the physical screen. Always work in logical coordinates, and let the coordinate system handle the scaling!

**Key Rule**: `event.pos` in handlers is **already converted** to logical coordinates. Use it directly!

