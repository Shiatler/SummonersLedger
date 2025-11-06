# ============================================================
# combat/btn/_btn_layout.py — shared button layout + loader
# ============================================================
import os
import pygame
import settings as S

BTN_SIZE = (180, 180)
PAD = 16

# simple cache by (path, size)
_IMG_CACHE: dict[tuple[str, tuple[int, int]], pygame.Surface] = {}

def rect_at(col: int, row: int, btn_size=BTN_SIZE, pad=PAD) -> pygame.Rect:
    """2x2 grid: (0,0)=battle, (1,0)=bag, (0,1)=party, (1,1)=run (bottom-right)."""
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    base_x = sw - (btn_size[0] * 2 + pad * 3)
    base_y = sh - (btn_size[1] * 2 + pad * 2)
    x = base_x + col * (btn_size[0] + pad)
    y = base_y + row * (btn_size[1] + pad)
    return pygame.Rect(x, y, *btn_size)

def load_scaled(path: str, size: tuple[int, int] = BTN_SIZE) -> pygame.Surface | None:
    key = (path, size)
    if key in _IMG_CACHE:
        return _IMG_CACHE[key]
    if not os.path.exists(path):
        print(f"⚠️ Missing UI asset: {path}")
        return None
    try:
        img = pygame.image.load(path).convert_alpha()
        img = pygame.transform.smoothscale(img, size)
        _IMG_CACHE[key] = img
        return img
    except Exception as e:
        print(f"⚠️ Failed to load '{path}': {e}")
        return None
