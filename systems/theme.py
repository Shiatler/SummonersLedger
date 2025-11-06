# ============================================================
#  theme.py — your visual “CSS”
# ============================================================

import os
import pygame
import settings as S


# ===================== Palette ==============================
# Brighter reds (matched to your logo)
DND_RED      = (220, 0, 0)      # normal accents / button text
DND_RED_HOV  = (255, 64, 64)    # hover accents / highlights

# Neutral UI tones (soft, dark stone)
DND_FRAME    = (28, 32, 38)     # fallback bg when no image
PANEL_BG     = (36, 28, 28)     # button background fill
PANEL_BORDER = (90, 30, 30)     # subtle border for buttons/panels

# Optional extra accents if you need them elsewhere
DND_ACCENT_1 = (64, 84, 92)
DND_ACCENT_2 = (18, 20, 24)


# ===================== Small Helpers ========================
def _safe_sysfont(name: str | None, size: int, bold=False):
    try:
        return pygame.font.SysFont(name or None, size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)

def _smooth_scale(surf: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    w, h = size
    if surf.get_width() == w and surf.get_height() == h:
        return surf
    return pygame.transform.smoothscale(surf, (max(1, w), max(1, h)))


# ===================== Fonts ================================
def load_fonts():
    """
    Load medieval/DnD-style fonts and return a dict:
        { "title": ..., "button": ..., "normal": ... }

    Sizes can be overridden in settings.py:
        DND_TITLE_SIZE  = 72
        DND_BUTTON_SIZE = 44
        DND_NORMAL_SIZE = 28
    """
    title_size   = getattr(S, "DND_TITLE_SIZE", 72)
    button_size  = getattr(S, "DND_BUTTON_SIZE", 44)
    normal_size  = getattr(S, "DND_NORMAL_SIZE", max(16, button_size - 12))

    font_path = os.path.join(S.ASSETS_FONTS_DIR, S.DND_FONT_FILE)
    if os.path.exists(font_path):
        try:
            title  = pygame.font.Font(font_path, title_size)
            button = pygame.font.Font(font_path, button_size)
            normal = pygame.font.Font(font_path, normal_size)
            return {"title": title, "button": button, "normal": normal}
        except Exception as e:
            print(f"⚠️ Failed to load custom font at {font_path}: {e}")

    # Fallbacks
    print(f"⚠️ D&D font not found at {font_path} — using system fonts.")
    title  = _safe_sysfont("georgia", title_size, bold=True)
    button = _safe_sysfont("georgia", button_size)
    normal = _safe_sysfont("georgia", normal_size)
    return {"title": title, "button": button, "normal": normal}


# ===================== Backgrounds ==========================
def load_menu_bg() -> pygame.Surface | None:
    """
    Optional main-menu background image.
    """
    bg_path = os.path.join(S.ASSETS_MAP_DIR, getattr(S, "MENU_BG_FILE", "mainmenu.png"))
    if os.path.exists(bg_path):
        try:
            return pygame.image.load(bg_path).convert()
        except Exception as e:
            print(f"⚠️ Failed to load menu bg '{bg_path}': {e}")
    return None


# ===================== Brand Logo ===========================
def load_logo() -> pygame.Surface | None:
    """
    Load the red 'Summoner's Ledger' logo from Assets/Map/Logo.png (or .jpg/.jpeg).
    Returns a Surface with per-pixel alpha if available.
    """
    base = S.ASSETS_MAP_DIR
    for name in ("Logo.png", "logo.png", "Logo.jpg", "logo.jpg", "Logo.jpeg", "logo.jpeg"):
        path = os.path.join(base, name)
        if os.path.exists(path):
            try:
                img = pygame.image.load(path)
                # Preserve alpha if present
                img = img.convert_alpha() if img.get_alpha() else img.convert()
                return img
            except Exception as e:
                print(f"⚠️ Failed to load logo '{path}': {e}")
                return None
    return None


def draw_logo_centered(screen: pygame.Surface, logo: pygame.Surface, y: int, max_w: int, max_h: int) -> pygame.Rect:
    """
    Draw the logo centered horizontally at y, fitting within (max_w, max_h).
    Returns the rect where it was drawn (use rect.bottom for layout below).
    """
    if not logo:
        return pygame.Rect(0, y, 0, 0)

    # Fit within bounds but keep aspect
    lw, lh = logo.get_width(), logo.get_height()
    scale = min(max_w / max(1, lw), max_h / max(1, lh))
    sw, sh = int(lw * scale), int(lh * scale)
    logo_scaled = _smooth_scale(logo, (sw, sh))

    x = (S.LOGICAL_WIDTH - sw) // 2
    screen.blit(logo_scaled, (x, y))
    return pygame.Rect(x, y, sw, sh)
