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
    # CRITICAL: Check if save file exists AND contains vessel data
    # Continue button should only be enabled if there's actual vessel data to load
    try:
        from systems import save_system as saves
        has_valid_save_data = saves.has_valid_save()
        can_continue = has_valid_save_data  # ONLY set to True if save has vessels
    except Exception as e:
        can_continue = False
    
    btn_font = fonts["button"]
    btn_y_start = (S.LOGICAL_HEIGHT // 2) + 60
    btn_spacing = 64

    # State: play submenu open?
    play_open = bool(getattr(gs, "_menu_play_open", False))

    if not play_open:
        # Top-level menu: Play + other global options
        gs._menu_buttons = [
            ui.Button("Play",         (S.LOGICAL_WIDTH // 2, btn_y_start + 0 * btn_spacing), btn_font, enabled=True),
            ui.Button("Leaderboard",  (S.LOGICAL_WIDTH // 2, btn_y_start + 1 * btn_spacing), btn_font, enabled=True),
            ui.Button("Settings",     (S.LOGICAL_WIDTH // 2, btn_y_start + 2 * btn_spacing), btn_font, enabled=True),
            ui.Button("Quit",         (S.LOGICAL_WIDTH // 2, btn_y_start + 3 * btn_spacing), btn_font, enabled=True),
        ]
    else:
        # Play submenu: New/Continue/Delete (+ Back at the end)
        gs._menu_buttons = [
            ui.Button("New Game",      (S.LOGICAL_WIDTH // 2, btn_y_start + 0 * btn_spacing), btn_font, enabled=True),
            ui.Button("Continue Game", (S.LOGICAL_WIDTH // 2, btn_y_start + 1 * btn_spacing), btn_font, enabled=can_continue),
            ui.Button("Delete Save",   (S.LOGICAL_WIDTH // 2, btn_y_start + 2 * btn_spacing), btn_font, enabled=can_continue),
            ui.Button("Back",          (S.LOGICAL_WIDTH // 2, btn_y_start + 3 * btn_spacing), btn_font, enabled=True),
        ]
    # Store the save check result for handler (for debugging)
    gs._menu_has_save = can_continue
    for b in gs._menu_buttons: b.draw(screen)
    
    # Draw confirmation popups if active
    if getattr(gs, "_delete_save_popup_active", False):
        _draw_delete_confirm_popup(screen, gs, fonts)
    if getattr(gs, "_new_game_popup_active", False):
        _draw_new_game_confirm_popup(screen, gs, fonts)

def _draw_delete_confirm_popup(screen, gs, fonts):
    """Draw the delete save confirmation popup (styled to match menu)."""
    from systems.theme import PANEL_BG, PANEL_BORDER, DND_RED, DND_RED_HOV, DND_FRAME
    
    # Dim background (darker, more subtle)
    dim = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 200))
    screen.blit(dim, (0, 0))
    
    # Popup panel (matching menu button style)
    popup_w, popup_h = 520, 240
    popup_x = (S.LOGICAL_WIDTH - popup_w) // 2
    popup_y = (S.LOGICAL_HEIGHT - popup_h) // 2
    popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
    
    # Draw panel background (same as menu buttons)
    pygame.draw.rect(screen, PANEL_BG, popup_rect, border_radius=12)
    pygame.draw.rect(screen, PANEL_BORDER, popup_rect, 2, border_radius=12)
    
    # Title text (matching menu style - dark red)
    btn_font = fonts.get("button", pygame.font.SysFont(None, 40))
    title_text = btn_font.render("DELETE SAVE?", True, DND_RED)
    title_rect = title_text.get_rect(center=(popup_rect.centerx, popup_rect.y + 50))
    screen.blit(title_text, title_rect)
    
    # Confirmation text (slightly lighter red, smaller)
    normal_font = fonts.get("normal", btn_font)
    confirm_text = normal_font.render("Are you sure?", True, DND_RED_HOV)
    confirm_rect = confirm_text.get_rect(center=(popup_rect.centerx, popup_rect.y + 100))
    screen.blit(confirm_text, confirm_rect)
    
    # Yes and No buttons (matching menu button style)
    btn_y = popup_rect.y + 160
    btn_spacing = 200  # Increased spacing between YES and NO buttons
    btn_w, btn_h = 160, 52  # Same size as menu buttons
    
    # Store button rects for click detection (in logical coordinates)
    yes_btn_rect = pygame.Rect(0, 0, btn_w, btn_h)
    yes_btn_rect.center = (popup_rect.centerx - btn_spacing // 2, btn_y)
    no_btn_rect = pygame.Rect(0, 0, btn_w, btn_h)
    no_btn_rect.center = (popup_rect.centerx + btn_spacing // 2, btn_y)
    
    # Get mouse position in logical coordinates for hover detection
    try:
        from systems import coords
        screen_mx, screen_my = pygame.mouse.get_pos()
        mx, my = coords.screen_to_logical((screen_mx, screen_my))
    except (ImportError, AttributeError):
        # Fallback if coords not available
        mx, my = pygame.mouse.get_pos()
    
    # Draw Yes button (matches menu button style)
    yes_hover = yes_btn_rect.collidepoint(mx, my)
    pygame.draw.rect(screen, PANEL_BG, yes_btn_rect, border_radius=12)
    pygame.draw.rect(screen, PANEL_BORDER, yes_btn_rect, 2, border_radius=12)
    yes_color = DND_RED_HOV if yes_hover else DND_RED
    yes_text = btn_font.render("YES", True, yes_color)
    screen.blit(yes_text, yes_text.get_rect(center=yes_btn_rect.center))
    
    # Draw No button (matches menu button style)
    no_hover = no_btn_rect.collidepoint(mx, my)
    pygame.draw.rect(screen, PANEL_BG, no_btn_rect, border_radius=12)
    pygame.draw.rect(screen, PANEL_BORDER, no_btn_rect, 2, border_radius=12)
    no_color = DND_RED_HOV if no_hover else DND_RED
    no_text = btn_font.render("NO", True, no_color)
    screen.blit(no_text, no_text.get_rect(center=no_btn_rect.center))
    
    # Store button rects in gs for click detection
    gs._delete_confirm_yes_rect = yes_btn_rect
    gs._delete_confirm_no_rect = no_btn_rect

def _draw_new_game_confirm_popup(screen, gs, fonts):
    """Draw the new game confirmation popup (styled to match menu)."""
    from systems.theme import PANEL_BG, PANEL_BORDER, DND_RED, DND_RED_HOV, DND_FRAME
    
    # Dim background (darker, more subtle)
    dim = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 200))
    screen.blit(dim, (0, 0))
    
    # Popup panel (matching menu button style)
    popup_w, popup_h = 520, 240
    popup_x = (S.LOGICAL_WIDTH - popup_w) // 2
    popup_y = (S.LOGICAL_HEIGHT - popup_h) // 2
    popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
    
    # Draw panel background (same as menu buttons)
    pygame.draw.rect(screen, PANEL_BG, popup_rect, border_radius=12)
    pygame.draw.rect(screen, PANEL_BORDER, popup_rect, 2, border_radius=12)
    
    # Title text (matching menu style - dark red)
    btn_font = fonts.get("button", pygame.font.SysFont(None, 40))
    title_text = btn_font.render("START NEW GAME?", True, DND_RED)
    title_rect = title_text.get_rect(center=(popup_rect.centerx, popup_rect.y + 50))
    screen.blit(title_text, title_rect)
    
    # Confirmation text (slightly lighter red, smaller)
    normal_font = fonts.get("normal", btn_font)
    confirm_text = normal_font.render("Are you sure?", True, DND_RED_HOV)
    confirm_rect = confirm_text.get_rect(center=(popup_rect.centerx, popup_rect.y + 100))
    screen.blit(confirm_text, confirm_rect)
    
    # Yes and No buttons (matching menu button style)
    btn_y = popup_rect.y + 160
    btn_spacing = 200  # Increased spacing between YES and NO buttons
    btn_w, btn_h = 160, 52  # Same size as menu buttons
    
    # Store button rects for click detection (in logical coordinates)
    yes_btn_rect = pygame.Rect(0, 0, btn_w, btn_h)
    yes_btn_rect.center = (popup_rect.centerx - btn_spacing // 2, btn_y)
    no_btn_rect = pygame.Rect(0, 0, btn_w, btn_h)
    no_btn_rect.center = (popup_rect.centerx + btn_spacing // 2, btn_y)
    
    # Get mouse position in logical coordinates for hover detection
    try:
        from systems import coords
        screen_mx, screen_my = pygame.mouse.get_pos()
        mx, my = coords.screen_to_logical((screen_mx, screen_my))
    except (ImportError, AttributeError):
        # Fallback if coords not available
        mx, my = pygame.mouse.get_pos()
    
    # Draw Yes button (matches menu button style)
    yes_hover = yes_btn_rect.collidepoint(mx, my)
    pygame.draw.rect(screen, PANEL_BG, yes_btn_rect, border_radius=12)
    pygame.draw.rect(screen, PANEL_BORDER, yes_btn_rect, 2, border_radius=12)
    yes_color = DND_RED_HOV if yes_hover else DND_RED
    yes_text = btn_font.render("YES", True, yes_color)
    screen.blit(yes_text, yes_text.get_rect(center=yes_btn_rect.center))
    
    # Draw No button (matches menu button style)
    no_hover = no_btn_rect.collidepoint(mx, my)
    pygame.draw.rect(screen, PANEL_BG, no_btn_rect, border_radius=12)
    pygame.draw.rect(screen, PANEL_BORDER, no_btn_rect, 2, border_radius=12)
    no_color = DND_RED_HOV if no_hover else DND_RED
    no_text = btn_font.render("NO", True, no_color)
    screen.blit(no_text, no_text.get_rect(center=no_btn_rect.center))
    
    # Store button rects in gs for click detection
    gs._new_game_confirm_yes_rect = yes_btn_rect
    gs._new_game_confirm_no_rect = no_btn_rect

def handle(events, gs, screen=None, fonts=None, audio_bank=None, **kwargs):
    if not hasattr(gs, "_menu_buttons"):
        return None

    # Top-level vs Play submenu state
    play_open = bool(getattr(gs, "_menu_play_open", False))

    # Check if confirmation popups are active
    delete_popup_active = getattr(gs, "_delete_save_popup_active", False)
    new_game_popup_active = getattr(gs, "_new_game_popup_active", False)
    
    if delete_popup_active:
        # Handle delete save popup events
        for event in events:
            # ESC key closes popup (same as clicking No)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                audio_sys.play_click(audio_bank)
                gs._delete_save_popup_active = False
                # Clear button rects
                if hasattr(gs, "_delete_confirm_yes_rect"):
                    delattr(gs, "_delete_confirm_yes_rect")
                if hasattr(gs, "_delete_confirm_no_rect"):
                    delattr(gs, "_delete_confirm_no_rect")
                return None
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # event.pos is already converted to logical coordinates in main.py
                click_pos = event.pos
                
                yes_rect = getattr(gs, "_delete_confirm_yes_rect", None)
                no_rect = getattr(gs, "_delete_confirm_no_rect", None)
                
                if yes_rect and yes_rect.collidepoint(click_pos):
                    # Yes - delete save and ALL persistent data (including Book of Bound)
                    audio_sys.play_click(audio_bank)
                    try:
                        from systems import save_system as saves
                        saves.delete_save(gs, clear_book_of_bound=True)  # Clear everything including Book of Bound
                        print("🗑️ Save and all persistent data (including Book of Bound) deleted from menu")
                    except Exception as e:
                        print(f"⚠️ Delete save failed: {e}")
                    
                    # Close popup and refresh menu
                    gs._delete_save_popup_active = False
                    # Clear button rects
                    if hasattr(gs, "_delete_confirm_yes_rect"):
                        delattr(gs, "_delete_confirm_yes_rect")
                    if hasattr(gs, "_delete_confirm_no_rect"):
                        delattr(gs, "_delete_confirm_no_rect")
                    # Force menu to redraw (buttons will update on next frame)
                    return None
                
                elif no_rect and no_rect.collidepoint(click_pos):
                    # No - close popup
                    audio_sys.play_click(audio_bank)
                    gs._delete_save_popup_active = False
                    # Clear button rects
                    if hasattr(gs, "_delete_confirm_yes_rect"):
                        delattr(gs, "_delete_confirm_yes_rect")
                    if hasattr(gs, "_delete_confirm_no_rect"):
                        delattr(gs, "_delete_confirm_no_rect")
                    return None
                
                # Click outside popup - check if click is outside the popup area
                popup_w, popup_h = 520, 240
                popup_x = (S.LOGICAL_WIDTH - popup_w) // 2
                popup_y = (S.LOGICAL_HEIGHT - popup_h) // 2
                popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
                
                if not popup_rect.collidepoint(click_pos):
                    # Clicked outside popup - close it (same as clicking No)
                    audio_sys.play_click(audio_bank)
                    gs._delete_save_popup_active = False
                    if hasattr(gs, "_delete_confirm_yes_rect"):
                        delattr(gs, "_delete_confirm_yes_rect")
                    if hasattr(gs, "_delete_confirm_no_rect"):
                        delattr(gs, "_delete_confirm_no_rect")
                    return None
        
        # If popup is active, don't process other menu button clicks
        return None
    
    if new_game_popup_active:
        # Handle new game popup events
        for event in events:
            # ESC key closes popup (same as clicking No)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                audio_sys.play_click(audio_bank)
                gs._new_game_popup_active = False
                # Clear button rects
                if hasattr(gs, "_new_game_confirm_yes_rect"):
                    delattr(gs, "_new_game_confirm_yes_rect")
                if hasattr(gs, "_new_game_confirm_no_rect"):
                    delattr(gs, "_new_game_confirm_no_rect")
                return None
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # event.pos is already converted to logical coordinates in main.py
                click_pos = event.pos
                
                yes_rect = getattr(gs, "_new_game_confirm_yes_rect", None)
                no_rect = getattr(gs, "_new_game_confirm_no_rect", None)
                
                if yes_rect and yes_rect.collidepoint(click_pos):
                    # Yes - start new game (preserves Book of Bound discoveries)
                    audio_sys.play_click(audio_bank)
                    
                    # ✨ don't kill all audio; just fade out music
                    try:
                        pygame.mixer.music.fadeout(120)
                    except Exception:
                        pass

                    # Reset runtime (same as before, just tidied)
                    # Note: delete_save() is called but Book of Bound discoveries are preserved (clear_book_of_bound=False by default)
                    try:
                        from systems import save_system as saves
                        saves.delete_save(gs)  # Delete save but preserve Book of Bound discoveries
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
                    
                    # Close popup
                    gs._new_game_popup_active = False
                    # Clear button rects
                    if hasattr(gs, "_new_game_confirm_yes_rect"):
                        delattr(gs, "_new_game_confirm_yes_rect")
                    if hasattr(gs, "_new_game_confirm_no_rect"):
                        delattr(gs, "_new_game_confirm_no_rect")
                    
                    return "CHAR_SELECT"
                
                elif no_rect and no_rect.collidepoint(click_pos):
                    # No - close popup
                    audio_sys.play_click(audio_bank)
                    gs._new_game_popup_active = False
                    # Clear button rects
                    if hasattr(gs, "_new_game_confirm_yes_rect"):
                        delattr(gs, "_new_game_confirm_yes_rect")
                    if hasattr(gs, "_new_game_confirm_no_rect"):
                        delattr(gs, "_new_game_confirm_no_rect")
                    return None
                
                # Click outside popup - check if click is outside the popup area
                popup_w, popup_h = 520, 240
                popup_x = (S.LOGICAL_WIDTH - popup_w) // 2
                popup_y = (S.LOGICAL_HEIGHT - popup_h) // 2
                popup_rect = pygame.Rect(popup_x, popup_y, popup_w, popup_h)
                
                if not popup_rect.collidepoint(click_pos):
                    # Clicked outside popup - close it (same as clicking No)
                    audio_sys.play_click(audio_bank)
                    gs._new_game_popup_active = False
                    if hasattr(gs, "_new_game_confirm_yes_rect"):
                        delattr(gs, "_new_game_confirm_yes_rect")
                    if hasattr(gs, "_new_game_confirm_no_rect"):
                        delattr(gs, "_new_game_confirm_no_rect")
                    return None

    # Button tuple depends on current state
    if not play_open:
        # Play, Leaderboard, Settings, Quit
        if len(gs._menu_buttons) < 4:
            return None
        b_play, b_leaderboard, b_settings, b_quit = gs._menu_buttons
    else:
        # New, Continue, Delete, Back
        if len(gs._menu_buttons) < 4:
            return None
        b_new, b_cont, b_delete, b_back = gs._menu_buttons

    for event in events:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

            # -------- TOP-LEVEL: PLAY --------
            if not play_open and b_play.clicked(event):
                audio_sys.play_click(audio_bank)
                gs._menu_play_open = True
                return None

            # -------- TOP-LEVEL: LEADERBOARD --------
            if not play_open and b_leaderboard.clicked(event):
                audio_sys.play_click(audio_bank)
                return "LEADERBOARD"

            # -------- TOP-LEVEL: SETTINGS --------
            if not play_open and b_settings.clicked(event):
                audio_sys.play_click(audio_bank)
                gs._settings_return_to = S.MODE_MENU
                return "SETTINGS"

            # -------- TOP-LEVEL: QUIT --------
            if not play_open and b_quit.clicked(event):
                audio_sys.play_click(audio_bank)
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                return None

            # ===== PLAY SUBMENU =====
            # -------- NEW GAME --------
            if play_open and b_new.clicked(event):
                audio_sys.play_click(audio_bank)
                # Show confirmation popup
                gs._new_game_popup_active = True
                return None

            # -------- CONTINUE --------
            # FIRST: Check if click is on Continue button area
            elif play_open and b_cont.rect.collidepoint(event.pos):
                # Click detected on Continue button - NOW check if we should allow it
                # CRITICAL: Check for valid save data FIRST, ignore button enabled state
                try:
                    from systems import save_system as saves
                    has_valid_save_data = saves.has_valid_save()
                except Exception as e:
                    has_valid_save_data = False
                
                # ONLY proceed if save file has actual vessel data (ignore button.enabled)
                if not has_valid_save_data:
                    # No valid save data (no vessels) - BLOCK the click completely
                    # Do nothing - the click is completely ignored
                    continue  # Skip to next event
                
                # Save has vessels - proceed
                audio_sys.play_click(audio_bank)
                # Return a special indicator that we're continuing (not starting new game)
                return ("CONTINUE", S.MODE_GAME)

            # -------- DELETE SAVE --------
            elif play_open and b_delete.clicked(event):
                audio_sys.play_click(audio_bank)
                # Show confirmation popup
                gs._delete_save_popup_active = True
                return None

            # -------- BACK (close submenu) --------
            elif play_open and b_back.clicked(event):
                audio_sys.play_click(audio_bank)
                gs._menu_play_open = False
                return None

    return None
