# Screen Development Guide

## Important: Screen Size Compatibility & Coordinate System

When creating new screens or modifying existing ones, **always follow these rules** to ensure compatibility with different screen sizes and display modes (fullscreen/windowed).

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
- [ ] Tested in both windowed and fullscreen modes

### 🐛 Common Mistakes to Avoid

1. **Don't use `S.WIDTH`/`S.HEIGHT`** - These change with display mode and cause misalignment
2. **Don't use `screen.get_size()`** - With `pygame.SCALED` flag, this can return wrong values
3. **Don't use raw mouse coordinates** - Always convert with `coords.screen_to_logical()`
4. **Don't create surfaces with `screen.get_size()`** - Use logical constants instead

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

### 🔗 Related Files

- `systems/coords.py` - Coordinate conversion system
- `settings.py` - Contains `LOGICAL_WIDTH` and `LOGICAL_HEIGHT` constants
- `main.py` - Main loop that handles coordinate conversion for events

---

**Remember:** The game uses a fixed logical resolution (1920x1080) internally, which is then scaled to fit the physical screen. Always work in logical coordinates, and let the coordinate system handle the scaling!

