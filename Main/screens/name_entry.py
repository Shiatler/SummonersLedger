# =============================================================
# name_entry.py
# =============================================================

import pygame
import settings as S

def enter(gs, **_):
    if not hasattr(gs, "_name_state"):
        gs._name_state = {"text": "", "blink_timer": 0.0, "cursor_on": True}

def draw(screen, gs, dt, fonts=None, menu_bg=None, **_):
    if menu_bg:
        bg = pygame.transform.scale(menu_bg, (S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT))
        screen.blit(bg, (0, 0))
        overlay = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
    else:
        screen.fill((20, 10, 10))

    title_font = fonts["title"]
    font_normal = fonts["normal"]
    title = title_font.render("Enter Your Name", True, (220, 200, 200))
    screen.blit(title, title.get_rect(center=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT // 4)))

    box_w, box_h = 720, 80
    box_rect = pygame.Rect((S.LOGICAL_WIDTH - box_w) // 2, (S.LOGICAL_HEIGHT // 2) - 40, box_w, box_h)
    pygame.draw.rect(screen, (40, 30, 30), box_rect, border_radius=12)
    pygame.draw.rect(screen, (200, 60, 60), box_rect, 3, border_radius=12)

    st = gs._name_state
    disp = st["text"] + ("_" if st["cursor_on"] and len(st["text"]) < 30 else "")
    txt = font_normal.render(disp, True, (240, 220, 220))
    screen.blit(txt, txt.get_rect(center=box_rect.center))

    hint = font_normal.render("Press ENTER to confirm or ESC to cancel", True, (200, 160, 160))
    screen.blit(hint, hint.get_rect(center=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT // 2 + 120)))

def handle(events, gs, dt, **_):
    st = gs._name_state
    st["blink_timer"] += dt
    if st["blink_timer"] >= 0.5:
        st["blink_timer"] = 0.0
        st["cursor_on"] = not st["cursor_on"]

    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "CHAR_SELECT"
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                gs.player_name = (st["text"].strip() or "Summoner")
                # force fresh randomization next screen
                if hasattr(gs, "_class_select"):
                    delattr(gs, "_class_select")
                gs.selected_class = None
                gs.revealed_class = None
                return "MASTER_OAK"
            elif event.key == pygame.K_BACKSPACE:
                st["text"] = st["text"][:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable() and len(st["text"]) < 30:
                    st["text"] += ch
    return None
