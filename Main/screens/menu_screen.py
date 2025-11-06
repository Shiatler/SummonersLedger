# =============================================================
# menu_screen.py
# =============================================================
import pygame, os
import settings as S
from systems import ui
from systems import audio as audio_sys

def enter(gs, screen=None, fonts=None, menu_bg=None, audio_bank=None, **_):
    # lazy cache of menu art
    if not hasattr(gs, "_menu_assets"):
        base = S.ASSETS_MAP_DIR
        gs._menu_assets = {}

        def load_image(name, alpha=True):
            path = os.path.join(base, name)
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path)
                    return img.convert_alpha() if alpha else img.convert()
                except Exception as e:
                    print(f"⚠️ Failed to load {name}: {e}")
            else:
                print(f"⚠️ Missing {name}")
            return None

        gs._menu_assets["bg"]   = load_image("MainMenu.png", alpha=False)
        gs._menu_assets["m"]    = load_image("MainMenuM.png")
        gs._menu_assets["f"]    = load_image("MainMenuF.png")
        gs._menu_assets["logo"] = load_image("Logo.png")

def draw(screen, gs, fonts=None, **kwargs):
    bg = gs._menu_assets.get("bg")
    if bg:
        iw, ih = bg.get_width(), bg.get_height()
        scale = max(S.LOGICAL_WIDTH / iw, S.LOGICAL_HEIGHT / ih)
        bg_scaled = pygame.transform.smoothscale(bg, (int(iw * scale), int(ih * scale)))
        bx = (S.LOGICAL_WIDTH - bg_scaled.get_width()) // 2
        by = (S.LOGICAL_HEIGHT - bg_scaled.get_height()) // 2
        screen.blit(bg_scaled, (bx, by))
    else:
        screen.fill((20, 10, 10))

    # characters
    def draw_char(img, side="left"):
        if not img: return
        target_h = int(S.LOGICAL_HEIGHT * 0.9)
        iw, ih = img.get_width(), img.get_height()
        scale = target_h / ih
        scaled = pygame.transform.smoothscale(img, (int(iw * scale), int(ih * scale)))
        rect = scaled.get_rect()
        rect.bottom = S.LOGICAL_HEIGHT - 40
        rect.left = 60 if side == "left" else rect.left
        if side != "left": rect.right = S.LOGICAL_WIDTH - 60
        screen.blit(scaled, rect.topleft)

    draw_char(gs._menu_assets.get("m"), side="left")
    draw_char(gs._menu_assets.get("f"), side="right")

    # logo
    logo = gs._menu_assets.get("logo")
    if logo:
        lw, lh = logo.get_width(), logo.get_height()
        scale = min(S.LOGICAL_WIDTH * 0.5 / lw, S.LOGICAL_HEIGHT * 0.3 / lh)
        logo_scaled = pygame.transform.smoothscale(logo, (int(lw * scale), int(lh * scale)))
        logo_rect = logo_scaled.get_rect(center=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT // 2 - 220))
        screen.blit(logo_scaled, logo_rect)
    else:
        title = fonts["title"].render(S.APP_NAME, True, (220, 40, 40))
        screen.blit(title, title.get_rect(center=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT // 2 - 220)))

    # buttons
    can_continue = kwargs.get("can_continue", False)
    btn_font = fonts["button"]
    btn_y_start = (S.LOGICAL_HEIGHT // 2) + 60
    btn_spacing = 64
    gs._menu_buttons = [
        ui.Button("New Game",      (S.LOGICAL_WIDTH // 2, btn_y_start + 0 * btn_spacing), btn_font, enabled=True),
        ui.Button("Continue Game", (S.LOGICAL_WIDTH // 2, btn_y_start + 1 * btn_spacing), btn_font, enabled=can_continue),
        ui.Button("Settings",      (S.LOGICAL_WIDTH // 2, btn_y_start + 2 * btn_spacing), btn_font, enabled=True),
        ui.Button("Quit",          (S.LOGICAL_WIDTH // 2, btn_y_start + 3 * btn_spacing), btn_font, enabled=True),
    ]
    for b in gs._menu_buttons: b.draw(screen)

def handle(events, gs, screen=None, fonts=None, audio_bank=None, **kwargs):
    if not hasattr(gs, "_menu_buttons"):
        return None

    b_new, b_cont, b_settings, b_quit = gs._menu_buttons

    for event in events:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

            # -------- NEW GAME --------
            if b_new.clicked(event):
                audio_sys.play_click(audio_bank)

                # ✨ don't kill all audio; just fade out music
                try:
                    pygame.mixer.music.fadeout(120)
                except Exception:
                    pass

                # Reset runtime (same as before, just tidied)
                try:
                    from systems import save_system as saves
                    saves.delete_save()
                except Exception as e:
                    print(f"⚠️ delete_save failed: {e}")

                gs.player_name = ""
                gs.distance_travelled = 0.0
                gs.next_event_at = S.FIRST_EVENT_AT
                gs.rivals_on_map.clear()
                gs.vessels_on_map.clear()
                gs.in_encounter = False
                gs.encounter_timer = 0.0
                gs.encounter_name = ""
                gs.encounter_sprite = None
                gs.party_slots = [None] * 6
                gs.party_slots_names = [None] * 6
                gs.starter_clicked = None
                gs.revealed_class = None
                gs.selected_class = None
                gs.player_token = None

                if hasattr(gs, "_class_select"): delattr(gs, "_class_select")
                if hasattr(gs, "_video"):        delattr(gs, "_video")
                if hasattr(gs, "fade_alpha"):
                    try:
                        del gs.fade_alpha; del gs.fade_speed
                    except Exception:
                        pass
                try:
                    from systems import party_ui as _pui
                    if hasattr(_pui, "_TOKEN_CACHE"):
                        _pui._TOKEN_CACHE.clear()
                except Exception:
                    pass

                gs.player_gender = "male"
                return "CHAR_SELECT"

            # -------- CONTINUE --------
            elif b_cont.clicked(event):
                audio_sys.play_click(audio_bank)
                try:
                    from systems import save_system as saves
                    if saves.has_save():
                        return S.MODE_GAME
                except Exception as e:
                    print(f"⚠️ has_save() failed: {e}")

            # -------- SETTINGS --------
            elif b_settings.clicked(event):
                audio_sys.play_click(audio_bank)
                gs._settings_return_to = S.MODE_MENU
                return "SETTINGS"

            # -------- QUIT --------
            elif b_quit.clicked(event):
                audio_sys.play_click(audio_bank)
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                return None

    return None
