# Screen Development Guide

## Important: Screen Size Compatibility & Coordinate System

When creating new screens or modifying existing ones, **always follow these rules** to ensure compatibility with different screen sizes and display modes (fullscreen/windowed).

## ⚠️ CRITICAL: Cursor Hover Detection for Buttons/Clickables

**MANDATORY RULE**: Whenever you create a new button, clickable element, or popup, you **MUST** implement hover detection so the cursor changes to the clicker when hovering over it.

### Why This Matters
The game uses a custom cursor system that changes from the normal cursor to a "clicker" cursor when hovering over clickable elements. This provides important visual feedback to players about what they can interact with.

### Implementation Steps

#### 1. For Simple Buttons (UI Module)
If using the `systems.ui.Button` class, hover detection is **automatic** - no additional work needed! The cursor manager checks all buttons automatically.

```python
# ✅ CORRECT - Button class handles hover automatically
from systems import ui
button = ui.Button(text="Click Me", rect=pygame.Rect(100, 100, 200, 50))
```

#### 2. For Custom Buttons (Combat Buttons, etc.)
If creating custom buttons (like in `combat/btn/`), you **MUST** implement hover detection functions:

**Step 1: Add hover detection function to your button module**

```python
# In your button module (e.g., combat/btn/my_button.py)

def is_hovering_button(pos: tuple[int, int]) -> bool:
    """
    Check if the mouse position is hovering over the button.
    
    Args:
        pos: Mouse position tuple (x, y) in logical coordinates
    
    Returns:
        True if hovering over button, False otherwise
    """
    _ensure()  # Initialize button if needed
    if _RECT is None:
        return False
    return _RECT.collidepoint(pos)

def is_hovering_popup_element(pos: tuple[int, int]) -> bool:
    """
    Check if the mouse position is hovering over any clickable element in a popup.
    Use this if your button opens a popup with clickable items.
    
    Args:
        pos: Mouse position tuple (x, y) in logical coordinates
    
    Returns:
        True if hovering over any clickable element, False otherwise
    """
    if not _OPEN:  # Popup must be open
        return False
    
    # Check individual clickable elements
    if _ITEM_RECTS:
        for rect in _ITEM_RECTS:
            if rect and rect.collidepoint(pos):
                return True
    
    # Check navigation arrows, buttons, etc.
    if _ARROW_RECT and _ARROW_RECT.collidepoint(pos):
        return True
    
    # Check main popup area
    if _PANEL_RECT and _PANEL_RECT.collidepoint(pos):
        return True
    
    return False
```

**Step 2: Add hover detection to cursor_manager.py**

Add your button/popup to the hover detection in `systems/cursor_manager.py`:

```python
# In systems/cursor_manager.py, inside _is_hovering_clickable()

# ==================== YOUR BUTTON/POPUP ====================
try:
    from combat.btn import my_button  # or wherever your button is
    # Check button hover
    if my_button.is_hovering_button(logical_pos):
        return True
    # Check popup hover (if applicable)
    if my_button.is_open() and my_button.is_hovering_popup_element(logical_pos):
        return True
except:
    pass
```

**Important Notes:**
- Always use **logical coordinates** (already converted in `cursor_manager.py`)
- Check if popup is open before checking popup elements
- Store rects as module-level variables (e.g., `_RECT`, `_ITEM_RECTS`)
- Rects should be in logical coordinates (same coordinate system as `S.LOGICAL_WIDTH`/`S.LOGICAL_HEIGHT`)

#### 3. For Popups with Items/List Elements

If your popup has scrollable lists or multiple clickable items:

```python
def is_hovering_popup_element(pos: tuple[int, int]) -> bool:
    """Check hover for popup with scrollable items."""
    global _ITEM_RECTS, _VIEWPORT_RECT, _PANEL_RECT
    
    if not _OPEN:
        return False
    
    # Check individual item rects (most precise)
    if _ITEM_RECTS:
        for rect in _ITEM_RECTS:
            if rect and rect.collidepoint(pos):
                return True
    
    # Check viewport (covers entire scrollable area)
    if _VIEWPORT_RECT and _VIEWPORT_RECT.collidepoint(pos):
        return True
    
    # Check navigation arrows
    if _LEFT_ARROW_RECT and _LEFT_ARROW_RECT.collidepoint(pos):
        return True
    if _RIGHT_ARROW_RECT and _RIGHT_ARROW_RECT.collidepoint(pos):
        return True
    
    # Fallback: check panel area
    if _PANEL_RECT and _PANEL_RECT.collidepoint(pos):
        return True
    
    return False
```

#### 4. For Screen-Specific Clickables

If you're adding clickables to a screen (not a button module):

```python
# In systems/cursor_manager.py

# ==================== YOUR SCREEN ====================
if mode and "YOUR_SCREEN" in str(mode):
    try:
        from screens import your_screen
        # Check if screen has stored button rects
        if gs and hasattr(gs, '_your_screen_buttons'):
            for button_rect in gs._your_screen_buttons:
                if button_rect and button_rect.collidepoint(logical_pos):
                    return True
        # Or calculate rects on the fly
        if hasattr(your_screen, '_get_button_rects'):
            rects = your_screen._get_button_rects()
            for rect in rects:
                if rect and rect.collidepoint(logical_pos):
                    return True
    except:
        pass
```

### Examples

#### Example 1: Simple Button (combat/btn/run_action.py)
```python
def is_hovering_button(pos: tuple[int, int]) -> bool:
    _ensure()
    if _RECT is None:
        return False
    return _RECT.collidepoint(pos)
```

#### Example 2: Button with Popup (combat/btn/bag_action.py)
```python
def is_hovering_button(pos: tuple[int, int]) -> bool:
    _ensure_btn()
    if _RECT is None:
        return False
    return _RECT.collidepoint(pos)

def is_hovering_popup_element(pos: tuple[int, int]) -> bool:
    global _PANEL_RECT, _ITEM_RECTS, _LEFT_ARROW_RECT, _RIGHT_ARROW_RECT, _VIEWPORT_RECT
    
    if not _OPEN:
        return False
    
    # Check navigation arrows
    if _LEFT_ARROW_RECT and _LEFT_ARROW_RECT.collidepoint(pos):
        return True
    if _RIGHT_ARROW_RECT and _RIGHT_ARROW_RECT.collidepoint(pos):
        return True
    
    # Check item rows
    if _ITEM_RECTS:
        for rect in _ITEM_RECTS:
            if rect and rect.collidepoint(pos):
                return True
    
    # Check viewport
    if _VIEWPORT_RECT and _VIEWPORT_RECT.collidepoint(pos):
        return True
    
    # Check panel
    if _PANEL_RECT and _PANEL_RECT.collidepoint(pos):
        return True
    
    return False
```

#### Example 3: HUD Buttons (systems/hud_buttons.py)
```python
def is_hovering_any_button(pos: tuple[int, int]) -> bool:
    """Check if hovering over any HUD button."""
    _load_all_buttons()
    for btn_def in _BUTTONS:
        btn_id = btn_def["id"]
        rect = _BUTTON_RECTS.get(btn_id)
        if rect and rect.collidepoint(pos):
            return True
    return False
```

### Testing Checklist

When adding new buttons/clickables, verify:
- [ ] Cursor changes to clicker when hovering over the button
- [ ] Cursor changes to clicker when hovering over popup elements (if applicable)
- [ ] Cursor changes to clicker when hovering over items in lists (if applicable)
- [ ] Cursor changes to clicker when hovering over navigation arrows (if applicable)
- [ ] Works in both overworld and battle modes (if applicable)
- [ ] Works with different display modes (fullscreen/windowed)
- [ ] Coordinates are correct (no misalignment)

**Optimization Checks:**
- [ ] Hover detection is placed in the correct priority section (popups first, then HUD, then mode-specific)
- [ ] Mode checks are pre-computed (using `mode_str` instead of `str(mode)` multiple times)
- [ ] Early returns are used (return immediately when hover is detected)
- [ ] Mode-specific checks only run when in that mode
- [ ] Rects are stored as module-level variables (not created every frame)
- [ ] `is_open()` is checked before expensive hover calculations (for popups)
- [ ] Similar modes are combined (e.g., battle and wild vessel use same checks)
- [ ] No duplicate checks for the same element
- [ ] Imports are wrapped in try-except blocks

### Common Mistakes to Avoid

❌ **Don't forget to add hover detection** - Every clickable element needs it!
❌ **Don't use screen coordinates** - Always use logical coordinates
❌ **Don't check rects before they're initialized** - Use `_ensure()` or check if rects exist
❌ **Don't forget to check if popup is open** - Use `if _OPEN:` before checking popup elements
❌ **Don't forget to update cursor_manager.py** - Hover detection won't work if not added there
❌ **Don't add mode-specific checks to early popup section** - Mode-specific checks should be in mode sections
❌ **Don't compute mode string multiple times** - Pre-compute `mode_str` once per frame
❌ **Don't skip early returns** - Return immediately when hover is detected
❌ **Don't check hover for closed popups** - Always check `is_open()` first
❌ **Don't create rects every frame** - Store them as module-level variables
❌ **Don't duplicate checks for similar modes** - Combine battle and wild vessel checks

### Optimization Best Practices

**IMPORTANT**: Hover detection runs every frame, so performance is critical! Follow these optimization rules:

#### 1. Priority Order (Check Most Common First)
The hover detection function checks elements in this order for maximum performance:
1. **Open popups first** (most common interaction when open)
   - `bag_action`, `buff_popup`, `hells_deck_popup`, `party_manager`, `ledger`
2. **HUD buttons** (always visible in game mode)
3. **HUD vessel slots** (only in game mode)
4. **Mode-specific elements** (only checked when in that mode)

**When adding new hover detection:**
- If it's a popup that can be open, add it to the "open popups" section (early in the function)
- If it's always visible, add it after HUD buttons
- If it's mode-specific, add it to the appropriate mode section

#### 2. Pre-compute Mode Checks
```python
# ✅ CORRECT - Compute once per frame
mode_str = str(mode) if mode else ""
is_game_mode = (mode == S.MODE_GAME or (mode and "GAME" in mode_str))
is_battle_mode = (mode and ("BATTLE" in mode_str or "WILD_VESSEL" in mode_str))

# ❌ WRONG - Don't compute mode string multiple times
if mode and "MENU" in str(mode):  # Creates string every time
if mode and "BATTLE" in str(mode):  # Creates string again
```

#### 3. Early Returns
```python
# ✅ CORRECT - Return immediately when found
if bag_action.is_open():
    if bag_action.is_hovering_popup_element(logical_pos):
        return True  # Exit immediately

# ❌ WRONG - Don't continue checking after finding a match
found = False
if bag_action.is_open():
    if bag_action.is_hovering_popup_element(logical_pos):
        found = True
# ... continue checking other things ...
return found
```

#### 4. Mode-Specific Checks
```python
# ✅ CORRECT - Only check when in that mode
if mode and "MENU" in mode_str:
    # Check menu buttons
    pass

# ❌ WRONG - Don't check mode-specific things for all modes
# This wastes CPU cycles checking menu buttons when in battle mode
if gs and hasattr(gs, '_menu_buttons'):
    # This runs even when not in menu mode!
    pass
```

#### 5. Combine Similar Checks
```python
# ✅ CORRECT - Battle and Wild Vessel use same buttons
if is_battle_mode:  # Combines "BATTLE" and "WILD_VESSEL" modes
    if battle_action.is_hovering_button(logical_pos):
        return True

# ❌ WRONG - Don't duplicate checks
if mode and "BATTLE" in mode_str:
    if battle_action.is_hovering_button(logical_pos):
        return True
if mode and "WILD_VESSEL" in mode_str:
    if battle_action.is_hovering_button(logical_pos):  # Duplicate!
        return True
```

#### 6. Simplify Coordinate Checks
```python
# ✅ CORRECT - Direct coordinate comparison (faster)
if (card_x <= mx <= card_x + card_width and 
    card_y <= my <= card_y + card_height):
    return True

# ⚠️ ACCEPTABLE - Using rect.collidepoint (slightly slower but clearer)
card_rect = pygame.Rect(card_x, card_y, card_width, card_height)
if card_rect.collidepoint(logical_pos):
    return True
```

#### 7. Check Open State Before Hover
```python
# ✅ CORRECT - Check if open first (fast check)
if bag_action.is_open():
    if bag_action.is_hovering_popup_element(logical_pos):
        return True

# ❌ WRONG - Don't check hover if not open
if bag_action.is_hovering_popup_element(logical_pos):
    # This might do expensive calculations even when closed
    return True
```

#### 8. Avoid Expensive Operations
```python
# ✅ CORRECT - Store rects as module-level variables
_RECT = None
def draw():
    global _RECT
    _RECT = pygame.Rect(x, y, w, h)

def is_hovering_button(pos):
    if _RECT:
        return _RECT.collidepoint(pos)
    return False

# ❌ WRONG - Don't calculate rects every frame
def is_hovering_button(pos):
    rect = pygame.Rect(x, y, w, h)  # Created every frame!
    return rect.collidepoint(pos)
```

#### 9. Use Try-Except for Imports
```python
# ✅ CORRECT - Wrap imports in try-except
try:
    from combat.btn import bag_action
    if bag_action.is_open():
        if bag_action.is_hovering_popup_element(logical_pos):
            return True
except:
    pass  # Module not available, skip

# ❌ WRONG - Don't let import errors crash hover detection
from combat.btn import bag_action  # Might fail if module not loaded
if bag_action.is_open():
    ...
```

### Quick Reference

**For new buttons:**
1. Add `is_hovering_button(pos)` function to button module
2. Add hover check to `cursor_manager.py` in `_is_hovering_clickable()`
3. **Place it in the appropriate priority section** (popups first, then HUD, then mode-specific)

**For popups with items:**
1. Add `is_hovering_popup_element(pos)` function to button module
2. Store rects as module-level variables (`_ITEM_RECTS`, `_PANEL_RECT`, etc.)
3. Add popup hover check to `cursor_manager.py` **in the "open popups" section** (early in function)
4. **Check `is_open()` before calling hover detection**

**For screen-specific clickables:**
1. Store button rects in game state or screen module
2. Add screen-specific hover detection to `cursor_manager.py`
3. **Check mode before checking hover** (use `mode_str` and mode checks)
4. **Place in mode-specific section** (not in early popup checks)

### ✅ ALWAYS DO THIS:

#### 1. Use Logical Resolution for Drawing/Positioning
```python
# ✅ CORRECT - Use logical resolution constants
sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
rect = pygame.Rect(sw // 2 - 100, sh // 2 - 50, 200, 100)

# ❌ WRONG - Don't use physical screen size
sw, sh = S.WIDTH, S.HEIGHT  # These change with display mode!
sw, sh = screen.get_size()  # These might be wrong with SCALED flag!
```

#### 2. Convert Mouse Coordinates
```python
# ✅ CORRECT - Always convert mouse coordinates to logical
from systems import coords

screen_mx, screen_my = pygame.mouse.get_pos()
mx, my = coords.screen_to_logical((screen_mx, screen_my))
if my_rect.collidepoint(mx, my):
    # Handle hover/click

# ❌ WRONG - Don't use raw mouse coordinates
mx, my = pygame.mouse.get_pos()
if my_rect.collidepoint(mx, my):  # This will be misaligned!
```

#### 3. Use Logical Coordinates for All UI Elements
```python
# ✅ CORRECT - All positioning uses logical coordinates
button_x = S.LOGICAL_WIDTH // 2 - 100
button_y = S.LOGICAL_HEIGHT // 2
text_surface = font.render("Text", True, (255, 255, 255))
text_rect = text_surface.get_rect(center=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT // 2))
screen.blit(text_surface, text_rect)

# ❌ WRONG - Using physical screen dimensions
button_x = S.WIDTH // 2 - 100  # Wrong!
```

#### 4. Surface Creation Should Use Logical Size
```python
# ✅ CORRECT - Create surfaces with logical size
overlay = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT), pygame.SRCALPHA)
fade = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT), pygame.SRCALPHA)

# ❌ WRONG - Don't use screen.get_size() for surface creation
overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)  # Wrong!
```

### 📝 Template for New Screens

```python
import pygame
import settings as S
from systems import coords  # ← Always import this!

def draw(screen: pygame.Surface, gs, dt, **_):
    # Use logical resolution for all calculations
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    
    # Draw background
    screen.fill((0, 0, 0))
    
    # Convert mouse coordinates for hover detection
    screen_mx, screen_my = pygame.mouse.get_pos()
    mx, my = coords.screen_to_logical((screen_mx, screen_my))
    
    # Create UI elements using logical coordinates
    button_rect = pygame.Rect(
        sw // 2 - 100,  # Center horizontally
        sh // 2 - 25,   # Center vertically
        200,            # Width
        50              # Height
    )
    
    # Check hover using converted coordinates
    hovered = button_rect.collidepoint(mx, my)
    
    # Draw button
    pygame.draw.rect(screen, (255, 255, 255) if hovered else (200, 200, 200), button_rect)
    
    # Draw text centered using logical coordinates
    font = pygame.font.Font(None, 36)
    text = font.render("Button", True, (0, 0, 0))
    text_rect = text.get_rect(center=button_rect.center)
    screen.blit(text, text_rect)

def handle(events, gs, dt, **_):
    for e in events:
        # Mouse click events are already converted to logical coordinates in main.py
        # So e.pos is already in logical coordinates
        if e.type == pygame.MOUSEBUTTONDOWN:
            # e.pos is already converted - use directly
            if my_rect.collidepoint(e.pos):
                # Handle click
                pass
```

### 🔍 Quick Checklist

Before committing a new screen, verify:

- [ ] All drawing uses `S.LOGICAL_WIDTH` and `S.LOGICAL_HEIGHT` (not `S.WIDTH`/`S.HEIGHT`)
- [ ] Mouse coordinates are converted using `coords.screen_to_logical()` for hover detection
- [ ] All `pygame.Rect` positions use logical coordinates
- [ ] Surface creation uses logical size: `(S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT)`
- [ ] Text positioning centers using logical coordinates
- [ ] `coords` is imported: `from systems import coords`
- [ ] No use of `screen.get_size()` for positioning/drawing
- [ ] **⚠️ CURSOR HOVER DETECTION: All buttons/clickables have hover detection implemented**
  - [ ] Added `is_hovering_button()` function (for custom buttons)
  - [ ] Added `is_hovering_popup_element()` function (for popups with items)
  - [ ] Added hover check to `cursor_manager.py` in `_is_hovering_clickable()`
  - [ ] Tested cursor changes to clicker when hovering
- [ ] Tested in both windowed and fullscreen modes

### 🐛 Common Mistakes to Avoid

1. **Don't use `S.WIDTH`/`S.HEIGHT`** - These change with display mode and cause misalignment
2. **Don't use `screen.get_size()`** - With `pygame.SCALED` flag, this can return wrong values
3. **Don't use raw mouse coordinates** - Always convert with `coords.screen_to_logical()`
4. **Don't create surfaces with `screen.get_size()`** - Use logical constants instead
5. **⚠️ Don't forget hover detection for new buttons/clickables** - Every clickable element MUST have hover detection implemented
6. **Don't forget to add hover check to cursor_manager.py** - Hover detection won't work if not registered there
7. **Don't use screen coordinates in hover functions** - Always use logical coordinates (already converted in cursor_manager)
8. **Don't check rects before initialization** - Use `_ensure()` or check if rects exist before using them

### 📚 Files That Already Follow This Pattern

These screens are good examples to reference:
- `screens/name_entry.py`
- `screens/master_oak.py`
- `screens/black_screen.py`
- `screens/ledger.py`
- `screens/death_saves.py`
- `combat/battle.py`
- `combat/summoner_battle.py`
- `systems/ui.py` (Button class)

**Hover Detection Examples:**
- `combat/btn/bag_action.py` - Button with popup and scrollable items (complete example)
- `combat/btn/run_action.py` - Simple button hover detection
- `combat/btn/battle_action.py` - Button with popup hover detection
- `combat/btn/party_action.py` - Button with popup and confirmation modal
- `systems/hud_buttons.py` - HUD buttons hover detection
- `systems/cursor_manager.py` - See `_is_hovering_clickable()` for all hover detection patterns

### 🔗 Related Files

- `systems/coords.py` - Coordinate conversion system
- `settings.py` - Contains `LOGICAL_WIDTH` and `LOGICAL_HEIGHT` constants
- `main.py` - Main loop that handles coordinate conversion for events

---

**Remember:** The game uses a fixed logical resolution (1920x1080) internally, which is then scaled to fit the physical screen. Always work in logical coordinates, and let the coordinate system handle the scaling!

