# rolling/ui.py
import os
import pygame, re
import settings as S
from systems import audio as audio_sys

_active = None           # {"text": str}
_blink_t = 0.0           # blink timer for the prompt
_BLINK_HZ = 2.0          # 2 toggles per second (0.5s on/off)

# ---------- Font discovery/cache ----------
_FONT_PATH = None
def _resolve_dh_font() -> str | None:
    """Find a font file in Assets/Fonts whose filename contains 'DH' (case-insensitive)."""
    global _FONT_PATH
    if _FONT_PATH is not None:
        return _FONT_PATH
    fonts_dir = os.path.join("Assets", "Fonts")
    if os.path.isdir(fonts_dir):
        for fname in os.listdir(fonts_dir):
            low = fname.lower()
            if "dh" in low and low.endswith((".ttf", ".otf", ".ttc")):
                _FONT_PATH = os.path.join(fonts_dir, fname)
                print(f"🅵 Using DH font: {_FONT_PATH}")
                return _FONT_PATH
    _FONT_PATH = None
    print("ℹ️ DH font not found in Assets/Fonts (looking for *DH*.ttf|otf|ttc). Using fallback.")
    return None

def _get_font(size, bold=False):
    """Prefer DH font from Assets/Fonts; fall back to a system font."""
    try:
        path = _resolve_dh_font()
        if path:
            return pygame.font.Font(path, size)
    except Exception as e:
        print(f"⚠️ Failed to load DH font: {e}")
    # fallback
    try:
        return pygame.font.SysFont("arial", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)

# ---------- public: hook for roller.set_roll_callback ----------
def _on_roll(kind, result):
    """Called by roller when a roll happens with notify=True."""
    # play dice sfx (if global AudioBank is set)
    try:
        bank = getattr(S, "AUDIO_BANK", None)
        if bank:
            audio_sys.play_sfx(bank, "dice_roll")
    except Exception:
        pass

    raw = getattr(result, "text", str(result))
    txt = _clean_roll_text(raw)

    global _active, _blink_t
    _active = {"text": txt}
    _blink_t = 0.0

# ---------- event pump ----------
def handle_event(e) -> bool:
    """
    Returns True if the textbox consumed the event
    (ENTER / SPACE / LEFT CLICK to dismiss).
    """
    global _active
    if not _active:
        return False

    if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE):
        _active = None
        return True
    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
        _active = None
        return True

    # While visible, block all other inputs (so Run doesn’t trigger immediately)
    return True

# ---------- drawing ----------
def draw_roll_popup(screen, dt):
    """Draw retro Pokémon-style textbox with blinking in-box prompt."""
    global _blink_t
    if not _active:
        return

    _blink_t += dt
    blink_on = int(_blink_t * _BLINK_HZ) % 2 == 0

    sw, sh = screen.get_size()
    margin_x = 36
    margin_bottom = 28
    box_h = 120
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)

    _draw_poke_box(screen, rect)

    # text area
    inner_pad = 20
    text_rect = rect.inflate(-inner_pad * 2, -inner_pad * 2)

    font = _get_font(28)
    lines = _wrap(_active["text"], font, text_rect.w)

    y = text_rect.y
    for line in lines:
        surf = font.render(line, False, (16, 16, 16))  # crisp, no antialias
        screen.blit(surf, (text_rect.x, y))
        y += surf.get_height() + 6

    # blinking prompt INSIDE bottom-right of the box
    if blink_on:
        prompt = "Press Enter to continue"
        pfont  = _get_font(20)
        psurf  = pfont.render(prompt, False, (40, 40, 40))
        px = rect.right - 14 - psurf.get_width()
        py = rect.bottom - 12 - psurf.get_height()
        # light highlight for readability
        shadow = pfont.render(prompt, False, (235, 235, 235))
        screen.blit(shadow, (px - 1, py - 1))
        screen.blit(psurf, (px, py))

# ---------- helpers ----------
def _wrap(text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if not cur or font.size(test)[0] <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def _clean_roll_text(s: str) -> str:
    """Remove leading 'Check:', 'Save:', 'Attack:', 'Damage:' and normalize arrow."""
    s = re.sub(r"^(Check:|Save:|Attack:|Damage:)\s*", "", s, flags=re.IGNORECASE)
    return s.replace("->", "=").strip()

def _draw_poke_box(surface, rect: pygame.Rect):
    """Gen-1 style box: white fill, double border, corner lozenges."""
    pygame.draw.rect(surface, (245, 245, 245), rect)
    pygame.draw.rect(surface, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(surface, (60, 60, 60), inner, 2, border_radius=6)

    # corner lozenges
    d = 10
    for cx, cy in (
        (rect.left + 8, rect.top + 8),
        (rect.right - 8, rect.top + 8),
        (rect.left + 8, rect.bottom - 8),
        (rect.right - 8, rect.bottom - 8),
    ):
        _draw_diamond(surface, (cx, cy), d, (60, 60, 60))

def _draw_diamond(surface, center, size, color):
    cx, cy = center
    pts = [
        (cx, cy - size // 2),
        (cx + size // 2, cy),
        (cx, cy + size // 2),
        (cx - size // 2, cy),
    ]
    pygame.draw.polygon(surface, color, pts)

def is_active() -> bool:
    """Return True while the roll textbox is on screen."""
    return _active is not None
