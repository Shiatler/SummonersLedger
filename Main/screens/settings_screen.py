# =============================================================
# screens/settings_screen.py
# =============================================================
import pygame
import settings as S
from systems import audio as audio_sys
from systems import ui, coords
from systems.theme import PANEL_BG, PANEL_BORDER, DND_RED, DND_RED_HOV

# Dropdown state
_dropdown_open = False
_dropdown_rect = None
_options = ["Fullscreen", "Windowed"]
_option_values = ["fullscreen", "windowed"]

def enter(gs, **_):
    global _dropdown_open
    _dropdown_open = False

def draw(screen, gs, fonts=None, menu_bg=None, audio_bank=None, **kwargs):
    # Store deps for use in handle
    gs._deps = kwargs
    
    if menu_bg:
        screen.blit(pygame.transform.scale(menu_bg, (S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT)), (0, 0))
        overlay = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
    else:
        screen.fill((20, 10, 10))

    font_title = fonts["title"]
    font_normal = fonts["normal"]

    title = font_title.render("Settings", True, (230, 210, 200))
    screen.blit(title, title.get_rect(center=(S.LOGICAL_WIDTH // 2, 160)))

    # Current volumes
    music_vol = pygame.mixer.music.get_volume()
    sfx_vol   = audio_sys.get_sfx_volume()  # ⬅️ master SFX

    def draw_slider(label, value, y):
        text = font_normal.render(f"{label}: {int(value * 100)}%", True, (220, 180, 180))
        screen.blit(text, text.get_rect(center=(S.LOGICAL_WIDTH // 2, y - 40)))
        bar = pygame.Rect(S.LOGICAL_WIDTH // 2 - 200, y, 400, 10)
        fill = pygame.Rect(bar.x, bar.y, int(bar.w * value), 10)
        pygame.draw.rect(screen, (60, 40, 40), bar)
        pygame.draw.rect(screen, (180, 50, 50), fill)
        pygame.draw.rect(screen, (0, 0, 0), bar, 2)
        return bar

    gs._settings_bars = {
        "music": draw_slider("Music Volume", music_vol, S.LOGICAL_HEIGHT // 2 - 40),
        "sfx":   draw_slider("Sound Volume", sfx_vol, S.LOGICAL_HEIGHT // 2 + 100),
    }
    
    # Display mode dropdown
    get_display_mode = gs._deps.get("get_display_mode", lambda: "windowed")
    current_mode = get_display_mode()
    mode_labels = {
        "fullscreen": "Fullscreen",
        "windowed": "Windowed"
    }
    current_label = mode_labels.get(current_mode, "Windowed")
    
    # Draw dropdown button
    dropdown_y = S.LOGICAL_HEIGHT // 2 + 200
    dropdown_width = 600
    dropdown_height = 70
    dropdown_x = S.LOGICAL_WIDTH // 2 - dropdown_width // 2
    
    global _dropdown_rect, _dropdown_open
    _dropdown_rect = pygame.Rect(dropdown_x, dropdown_y, dropdown_width, dropdown_height)
    
    # Button background - get mouse position in logical coordinates
    try:
        screen_mx, screen_my = pygame.mouse.get_pos()
        mx, my = coords.screen_to_logical((screen_mx, screen_my))
    except:
        mx, my = 0, 0
    hovered = _dropdown_rect.collidepoint(mx, my)
    
    pygame.draw.rect(screen, PANEL_BG, _dropdown_rect, border_radius=12)
    pygame.draw.rect(screen, PANEL_BORDER, _dropdown_rect, 2, border_radius=12)
    
    # Button text
    button_text = f"Display Mode: {current_label}"
    text_surf = font_normal.render(button_text, True, DND_RED_HOV if hovered else DND_RED)
    text_rect = text_surf.get_rect(center=_dropdown_rect.center)
    screen.blit(text_surf, text_rect)
    
    # Dropdown arrow
    arrow_size = 12
    arrow_x = _dropdown_rect.right - 30
    arrow_y = _dropdown_rect.centery
    arrow_points = [
        (arrow_x, arrow_y - arrow_size // 2),
        (arrow_x + arrow_size, arrow_y - arrow_size // 2),
        (arrow_x + arrow_size // 2, arrow_y + arrow_size // 2),
    ]
    pygame.draw.polygon(screen, DND_RED if not hovered else DND_RED_HOV, arrow_points)
    
    # Draw dropdown menu if open
    if _dropdown_open:
        option_height = 50
        dropdown_menu_height = len(_options) * option_height
        dropdown_menu_rect = pygame.Rect(
            dropdown_x,
            dropdown_y + dropdown_height + 2,
            dropdown_width,
            dropdown_menu_height
        )
        
        # Menu background
        menu_surface = pygame.Surface((dropdown_menu_rect.w, dropdown_menu_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(menu_surface, PANEL_BG, menu_surface.get_rect(), border_radius=12)
        pygame.draw.rect(menu_surface, PANEL_BORDER, menu_surface.get_rect(), 2, border_radius=12)
        
        # Draw each option
        for i, (option_label, option_value) in enumerate(zip(_options, _option_values)):
            option_rect = pygame.Rect(0, i * option_height, dropdown_width, option_height)
            is_selected = (option_value == current_mode)
            is_hovered = option_rect.collidepoint(mx - dropdown_menu_rect.x, my - dropdown_menu_rect.y)
            
            if is_hovered:
                pygame.draw.rect(menu_surface, (PANEL_BG[0] + 20, PANEL_BG[1] + 20, PANEL_BG[2] + 20), option_rect, border_radius=8)
            
            if is_selected:
                # Draw checkmark or highlight
                pygame.draw.rect(menu_surface, (PANEL_BG[0] - 20, PANEL_BG[1] - 20, PANEL_BG[2] - 20), option_rect, border_radius=8)
            
            option_text = font_normal.render(option_label, True, DND_RED_HOV if is_hovered or is_selected else DND_RED)
            text_rect = option_text.get_rect(center=option_rect.center)
            menu_surface.blit(option_text, text_rect)
        
        screen.blit(menu_surface, dropdown_menu_rect.topleft)
        gs._dropdown_menu_rect = dropdown_menu_rect
    else:
        gs._dropdown_menu_rect = None

    info = font_normal.render("Click/drag sliders or press ESC to return", True, (200, 160, 160))
    screen.blit(info, info.get_rect(center=(S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT - 100)))

def _apply_from_mouse(mx, rect: pygame.Rect) -> float:
    """Convert mouse x to a 0..1 value within the slider rect."""
    if rect is None: return 0.0
    return max(0.0, min(1.0, (mx - rect.x) / rect.w))

def handle(events, gs, fonts=None, audio_bank=None, **kwargs):
    global _dropdown_open
    bars = getattr(gs, "_settings_bars", {})
    music_bar = bars.get("music")
    sfx_bar   = bars.get("sfx")
    dropdown_menu_rect = getattr(gs, "_dropdown_menu_rect", None)
    
    # Get display mode functions from deps
    change_display_mode = kwargs.get("change_display_mode")
    get_display_mode = kwargs.get("get_display_mode", lambda: "windowed")

    dragging = getattr(gs, "_settings_drag", {"music": False, "sfx": False})

    for event in events:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if _dropdown_open:
                _dropdown_open = False
            else:
                return getattr(gs, "_settings_return_to", S.MODE_MENU)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Check if clicking dropdown button
            if _dropdown_rect and _dropdown_rect.collidepoint(mx, my):
                _dropdown_open = not _dropdown_open
                audio_sys.play_click(audio_bank)
            # Check if clicking dropdown option
            elif _dropdown_open and dropdown_menu_rect and dropdown_menu_rect.collidepoint(mx, my):
                option_height = 50
                option_index = int((my - dropdown_menu_rect.y) / option_height)
                if 0 <= option_index < len(_option_values):
                    selected_mode = _option_values[option_index]
                    if change_display_mode and selected_mode != get_display_mode():
                        change_display_mode(selected_mode)
                        audio_sys.play_click(audio_bank)
                    _dropdown_open = False
            # Close dropdown if clicking outside
            elif _dropdown_open:
                _dropdown_open = False
            elif music_bar and music_bar.collidepoint(mx, my):
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
