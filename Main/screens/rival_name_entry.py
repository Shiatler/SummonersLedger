# =============================================================
# rival_name_entry.py
# =============================================================

import pygame
import settings as S
from systems import name_generator

def enter(gs, **_):
    if not hasattr(gs, "_rival_name_state"):
        gs._rival_name_state = {
            "text": "", 
            "blink_timer": 0.0, 
            "cursor_on": True,
            "keys_pressed": set(),  # Track which keys are currently held
            "key_repeat_timer": 0.0,  # Timer for key repeat
            "key_repeat_delay": 0.05  # Repeat every 50ms when held
        }
    
    # Generate default name if not set (based on rival gender)
    if not hasattr(gs, "rival_name") or not gs.rival_name:
        # Use a deterministic name generator based on gender
        # For now, use a simple default
        if gs.rival_gender == "male":
            default_name = "Rival"
        else:
            default_name = "Rival"
        # Could use name_generator.generate_summoner_name() here if we had a summoner filename

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
    title = title_font.render("Enter Your Rival's Name", True, (220, 200, 200))
    screen.blit(title, title.get_rect(center=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT // 4)))

    box_w, box_h = 720, 80
    box_rect = pygame.Rect((S.LOGICAL_WIDTH - box_w) // 2, (S.LOGICAL_HEIGHT // 2) - 40, box_w, box_h)
    pygame.draw.rect(screen, (40, 30, 30), box_rect, border_radius=12)
    pygame.draw.rect(screen, (200, 60, 60), box_rect, 3, border_radius=12)

    st = gs._rival_name_state
    disp = st["text"] + ("_" if st["cursor_on"] and len(st["text"]) < 30 else "")
    txt = font_normal.render(disp, True, (240, 220, 220))
    screen.blit(txt, txt.get_rect(center=box_rect.center))

    hint = font_normal.render("Press ENTER to confirm or ESC to cancel", True, (200, 160, 160))
    screen.blit(hint, hint.get_rect(center=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT // 2 + 120)))

def handle(events, gs, dt, **_):
    st = gs._rival_name_state
    st["blink_timer"] += dt
    if st["blink_timer"] >= 0.5:
        st["blink_timer"] = 0.0
        st["cursor_on"] = not st["cursor_on"]

    # Initialize keys_pressed if not present (for backwards compatibility)
    if "keys_pressed" not in st:
        st["keys_pressed"] = set()
        st["key_repeat_timer"] = 0.0
        st["key_repeat_delay"] = 0.05

    # Update key repeat timer
    st["key_repeat_timer"] += dt

    # Process key repeat for held keys
    if st["keys_pressed"] and st["key_repeat_timer"] >= st["key_repeat_delay"]:
        st["key_repeat_timer"] = 0.0  # Reset timer
        # Process backspace if held
        if pygame.K_BACKSPACE in st["keys_pressed"]:
            st["text"] = st["text"][:-1]

    for event in events:
        if event.type == pygame.KEYDOWN:
            st["keys_pressed"].add(event.key)  # Track that key is pressed
            st["key_repeat_timer"] = 0.0  # Reset timer on new key press
            
            if event.key == pygame.K_ESCAPE:
                return "NAME_ENTRY"  # Go back to player name entry
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                entered_name = st["text"].strip()
                gs.rival_name = entered_name if entered_name else "Rival"
                print(f"✅ Rival name set to: '{gs.rival_name}' (entered: '{entered_name}')")
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
        elif event.type == pygame.KEYUP:
            st["keys_pressed"].discard(event.key)  # Remove key when released
            st["key_repeat_timer"] = 0.0  # Reset timer when key is released
    return None

