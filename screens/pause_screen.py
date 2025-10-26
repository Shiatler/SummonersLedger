# =============================================================
# screens/pause_screen.py
# =============================================================
import pygame
import settings as S
from systems import ui
from systems import audio as audio_sys

def enter(gs, **_):
    # Reset cached buttons so we rebuild with the current window size/fonts.
    gs._pause_buttons = None

def draw(screen, gs, fonts=None, audio_bank=None, **_):
    # Dim the current frame
    dim = pygame.Surface((S.WIDTH, S.HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 160))
    screen.blit(dim, (0, 0))

    # Title
    title_font = fonts["title"] if fonts else pygame.font.SysFont(None, 64)
    btn_font   = fonts["button"] if fonts else pygame.font.SysFont(None, 36)
    title = title_font.render("Paused", True, (230, 210, 200))
    screen.blit(title, title.get_rect(center=(S.WIDTH // 2, S.HEIGHT // 2 - 200)))

    # Buttons (cached on gs)
    y0 = S.HEIGHT // 2 - 60
    if getattr(gs, "_pause_buttons", None) is None:
        gs._pause_buttons = [
            ui.Button("Resume",       (S.WIDTH // 2, y0 + 0),   btn_font),
            ui.Button("Save Game",    (S.WIDTH // 2, y0 + 60),  btn_font),
            ui.Button("Settings",     (S.WIDTH // 2, y0 + 120), btn_font),
            ui.Button("Quit to Menu", (S.WIDTH // 2, y0 + 180), btn_font),
        ]

    for b in gs._pause_buttons:
        b.draw(screen)

def handle(events, gs, audio_bank=None, saves=None, **_):
    buttons = getattr(gs, "_pause_buttons", None)
    if not buttons:
        return None
    b_resume, b_save, b_settings, b_quit = buttons

    for event in events:
        # ESC resumes
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            audio_sys.play_click(audio_bank)
            return S.MODE_GAME

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if b_resume.clicked(event):
                audio_sys.play_click(audio_bank)
                return S.MODE_GAME

            if b_save.clicked(event):
                audio_sys.play_click(audio_bank)
                if saves:
                    try:
                        saves.save_game(gs)
                        print("💾 Saved game from Pause.")
                    except Exception as e:
                        print(f"⚠️ Save failed: {e}")

            if b_settings.clicked(event):
                audio_sys.play_click(audio_bank)
                gs._settings_return_to = "PAUSE"
                return "SETTINGS"

            if b_quit.clicked(event):
                audio_sys.play_click(audio_bank)
                if saves:
                    try:
                        saves.save_game(gs)
                    except Exception as e:
                        print(f"⚠️ Save-on-quit failed: {e}")
                return S.MODE_MENU

    return None
