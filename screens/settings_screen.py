# =============================================================
# screens/settings_screen.py
# =============================================================
import pygame
import settings as S
from systems import audio as audio_sys

def enter(gs, **_):
    pass

def draw(screen, gs, fonts=None, menu_bg=None, audio_bank=None, **_):
    if menu_bg:
        screen.blit(pygame.transform.scale(menu_bg, (S.WIDTH, S.HEIGHT)), (0, 0))
        overlay = pygame.Surface((S.WIDTH, S.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
    else:
        screen.fill((20, 10, 10))

    font_title = fonts["title"]
    font_normal = fonts["normal"]

    title = font_title.render("Settings", True, (230, 210, 200))
    screen.blit(title, title.get_rect(center=(S.WIDTH // 2, 160)))

    # Current volumes
    music_vol = pygame.mixer.music.get_volume()
    sfx_vol   = audio_sys.get_sfx_volume()  # ⬅️ master SFX

    def draw_slider(label, value, y):
        text = font_normal.render(f"{label}: {int(value * 100)}%", True, (220, 180, 180))
        screen.blit(text, text.get_rect(center=(S.WIDTH // 2, y - 40)))
        bar = pygame.Rect(S.WIDTH // 2 - 200, y, 400, 10)
        fill = pygame.Rect(bar.x, bar.y, int(bar.w * value), 10)
        pygame.draw.rect(screen, (60, 40, 40), bar)
        pygame.draw.rect(screen, (180, 50, 50), fill)
        pygame.draw.rect(screen, (0, 0, 0), bar, 2)
        return bar

    gs._settings_bars = {
        "music": draw_slider("Music Volume", music_vol, S.HEIGHT // 2 - 40),
        "sfx":   draw_slider("Sound Volume", sfx_vol, S.HEIGHT // 2 + 100),
    }

    info = font_normal.render("Click/drag sliders or press ESC to return", True, (200, 160, 160))
    screen.blit(info, info.get_rect(center=(S.WIDTH // 2, S.HEIGHT - 100)))

def _apply_from_mouse(mx, rect: pygame.Rect) -> float:
    """Convert mouse x to a 0..1 value within the slider rect."""
    if rect is None: return 0.0
    return max(0.0, min(1.0, (mx - rect.x) / rect.w))

def handle(events, gs, fonts=None, audio_bank=None, **_):
    bars = getattr(gs, "_settings_bars", {})
    music_bar = bars.get("music")
    sfx_bar   = bars.get("sfx")

    dragging = getattr(gs, "_settings_drag", {"music": False, "sfx": False})

    for event in events:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return getattr(gs, "_settings_return_to", S.MODE_MENU)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if music_bar and music_bar.collidepoint(mx, my):
                dragging["music"] = True
                val = _apply_from_mouse(mx, music_bar)
                pygame.mixer.music.set_volume(val)
            elif sfx_bar and sfx_bar.collidepoint(mx, my):
                dragging["sfx"] = True
                val = _apply_from_mouse(mx, sfx_bar)
                audio_sys.set_sfx_volume(val, audio_bank)  # ⬅️ set master + apply to loaded sounds
                audio_sys.play_click(audio_bank, vol_scale=1.0)  # tiny feedback

        elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
            mx, my = event.pos
            if dragging.get("music") and music_bar:
                val = _apply_from_mouse(mx, music_bar)
                pygame.mixer.music.set_volume(val)
            if dragging.get("sfx") and sfx_bar:
                val = _apply_from_mouse(mx, sfx_bar)
                audio_sys.set_sfx_volume(val, audio_bank)

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            dragging["music"] = False
            dragging["sfx"] = False

    gs._settings_drag = dragging
    return None
