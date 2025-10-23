# ============================================================
#  ui.py — reusable UI + menu + character select
# ============================================================

import pygame
import settings as S
from systems.theme import DND_RED, DND_RED_HOV, DND_FRAME, PANEL_BG, PANEL_BORDER


# ===================== Constants ============================

BTN_W, BTN_H = 420, 52



# ===================== Font Helpers =========================

def _unpack_fonts(fonts):
    """
    Accepts either:
      - tuple: (title_font, button_font)
      - dict:  {"title": ..., "button": ..., "normal": ...}
    Returns: (title_font, button_font, normal_font)
    """
    if isinstance(fonts, dict):
        title  = fonts.get("title")  or pygame.font.SysFont(None, 64)
        button = fonts.get("button") or pygame.font.SysFont(None, 36)
        normal = fonts.get("normal") or button
        return title, button, normal
    else:
        # assume tuple (title, button)
        try:
            title, button = fonts
        except Exception:
            title  = pygame.font.SysFont(None, 64)
            button = pygame.font.SysFont(None, 36)
        return title, button, button



# ===================== Button Widget ========================

class Button:
    def __init__(self, label, center, font, enabled=True):
        self.label   = label
        self.font    = font
        self.enabled = enabled
        self.rect    = pygame.Rect(0, 0, BTN_W, BTN_H)
        self.rect.center = center

    def draw(self, surf):
        mx, my  = pygame.mouse.get_pos()
        hovered = self.rect.collidepoint(mx, my) and self.enabled

        # Background & border
        pygame.draw.rect(surf, PANEL_BG, self.rect, border_radius=12)
        pygame.draw.rect(surf, PANEL_BORDER, self.rect, 2, border_radius=12)

        # Text color
        color = (150, 120, 120) if not self.enabled else (DND_RED_HOV if hovered else DND_RED)
        text  = self.font.render(self.label, True, color)
        surf.blit(text, text.get_rect(center=self.rect.center))

    def clicked(self, event):
        if not self.enabled:
            return False
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )



# ===================== Main Menu ============================

def _draw_bg_centered_native(screen, width, height, bg_surface):
    """
    Draws the menu background at its original pixel size (no scaling),
    centered on screen. Anything outside the window bounds is cropped.
    """
    # Base fill behind the image (so you don't see junk at edges)
    screen.fill(DND_FRAME)

    if not bg_surface:
        return

    bg_w, bg_h = bg_surface.get_width(), bg_surface.get_height()
    x = (width  - bg_w) // 2
    y = (height - bg_h) // 2
    screen.blit(bg_surface, (x, y))


def draw_menu(screen, width, height, fonts, app_name, can_continue, menu_bg):
    font_title, font_btn, _ = _unpack_fonts(fonts)

    # --- Background: NO SCALING, centered at native size ---
    _draw_bg_centered_native(screen, width, height, menu_bg)

    # --- Border frame (nice inset frame) ---
    pygame.draw.rect(screen, (0, 0, 0), (12, 12, width - 24, height - 24), 3, border_radius=18)

    # --- Title (keep for fallback if no logo is drawn elsewhere) ---
    # If you’re drawing the logo in main.py, this title text can be ignored.
    title = font_title.render(app_name, True, DND_RED)
    screen.blit(title, title.get_rect(center=(width // 2, height // 2 - 140)))

    # --- Buttons ---
    buttons = [
        Button("New Game",      (width // 2, height // 2 - 20),  font_btn),
        Button("Continue Game", (width // 2, height // 2 + 40),  font_btn, enabled=can_continue),
        Button("Settings",      (width // 2, height // 2 + 100), font_btn),
        Button("Quit",          (width // 2, height // 2 + 160), font_btn),
    ]

    for b in buttons:
        b.draw(screen)

    pygame.display.flip()
    return buttons


# ===================== ClickRect Helper =====================

class ClickRect:
    def __init__(self, rect, key):
        self.rect = rect
        self.key  = key

    def clicked(self, event):
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )



# ===================== Image Fit Helper =====================

def _fit_surface(surf, max_w, max_h):
    """Return a scaled copy of surf that fits inside (max_w, max_h) maintaining aspect."""
    if surf is None:
        return None

    w, h = surf.get_width(), surf.get_height()
    if w <= max_w and h <= max_h:
        return surf

    scale   = min(max_w / w, max_h / h)
    new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
    # For pixel art you may prefer pygame.transform.scale; using smoothscale for nicer menu preview
    return pygame.transform.smoothscale(surf, new_size)



# ===================== Character Select =====================

def draw_character_select(screen, width, height, fonts, app_name, male_surface, female_surface, bg_surface=None):
    font_title, _, font_normal = _unpack_fonts(fonts)

    # Background (with optional image)
    if bg_surface:
        bg = pygame.transform.scale(bg_surface, (width, height))
        screen.blit(bg, (0, 0))
        shade = pygame.Surface((width, height), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 80))  # soft dark overlay
        screen.blit(shade, (0, 0))
    else:
        screen.fill((20, 10, 10))

    # Border frame
    pygame.draw.rect(screen, (0, 0, 0), (12, 12, width - 24, height - 24), 3, border_radius=18)

    # Title
    title = font_title.render("Choose Your Character", True, DND_RED)
    screen.blit(title, title.get_rect(center=(width // 2, height // 6)))

    # Layout
    card_w, card_h = 440, 560
    spacing = 180
    total_w = card_w * 2 + spacing
    start_x = width // 2 - total_w // 2
    y = height // 2 - card_h // 2 + 40

    cards = []
    variants = [
        ("male",   male_surface),
        ("female", female_surface),
    ]

    mx, my = pygame.mouse.get_pos()

    for i, (key, surf) in enumerate(variants):
        x = start_x + i * (card_w + spacing)
        rect = pygame.Rect(x, y, card_w, card_h)
        hovered = rect.collidepoint(mx, my)

        # Card background and border
        bg_col     = (36, 24, 24)
        border_col = DND_RED_HOV if hovered else (120, 60, 60)
        shadow = rect.copy()
        shadow.x += 4
        shadow.y += 5

        pygame.draw.rect(screen, (0, 0, 0, 60), shadow, border_radius=18)
        pygame.draw.rect(screen, bg_col, rect, border_radius=18)
        pygame.draw.rect(screen, border_col, rect, 5, border_radius=18)

        # Character sprite
        img_area = rect.inflate(-80, -160)
        fitted = _fit_surface(surf, img_area.w, img_area.h)
        if fitted:
            img_rect = fitted.get_rect(center=(rect.centerx, rect.centery - 20))
            screen.blit(fitted, img_rect)

        # Hover hint
        if hovered:
            hint = font_normal.render("Click to select", True, DND_RED_HOV)
            screen.blit(hint, hint.get_rect(center=(rect.centerx, rect.bottom - 35)))

        cards.append(ClickRect(rect, key))

    pygame.display.flip()
    return cards[0], cards[1]
