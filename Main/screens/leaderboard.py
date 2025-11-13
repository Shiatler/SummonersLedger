# ============================================================
# screens/leaderboard.py — Leaderboard Screen
# Displays top 100 scores with player name, character token, and score
# ============================================================

import os
import pygame
import settings as S
from systems import leaderboard as lb_sys, party_ui, coords
from systems.theme import PANEL_BG, PANEL_BORDER, DND_RED, DND_RED_HOV

# Mode constants are defined in main.py

# Colors matching the menu screen theme
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_BG = (20, 20, 25)  # Dark background

# Layout constants
ENTRIES_PER_PAGE = 20
ENTRY_HEIGHT = 60
ENTRY_SPACING = 4
TOKEN_SIZE = 50
SCROLL_SPEED = 300  # pixels per second


def _get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Get font for leaderboard."""
    try:
        path = os.path.join(S.ASSETS_FONTS_DIR, getattr(S, "DND_FONT_FILE", "DH.otf"))
        return pygame.font.Font(path, size)
    except Exception:
        return pygame.font.SysFont("arial", size, bold=bold)


def enter(gs, **_):
    """Initialize leaderboard screen."""
    st = {
        "scroll_offset": 0.0,
        "max_scroll": 0.0,
        "entries": [],
    }
    gs._leaderboard = st
    
    # Load leaderboard entries
    entries = lb_sys.get_top_scores(limit=100)
    st["entries"] = entries
    
    # Calculate max scroll (total height - visible height)
    total_height = len(entries) * (ENTRY_HEIGHT + ENTRY_SPACING)
    visible_height = S.LOGICAL_HEIGHT - 200  # Leave space for title and back button
    st["max_scroll"] = max(0, total_height - visible_height)


def handle(events, gs, **_):
    """Handle leaderboard screen events."""
    st = getattr(gs, "_leaderboard", None)
    if st is None:
        enter(gs)
        st = gs._leaderboard
    
    for event in events:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return S.MODE_MENU
            # Scroll with arrow keys
            elif event.key == pygame.K_UP:
                st["scroll_offset"] = max(0, st["scroll_offset"] - ENTRY_HEIGHT)
            elif event.key == pygame.K_DOWN:
                st["scroll_offset"] = min(st["max_scroll"], st["scroll_offset"] + ENTRY_HEIGHT)
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:  # Scroll up
                st["scroll_offset"] = max(0, st["scroll_offset"] - ENTRY_HEIGHT * 2)
            elif event.button == 5:  # Scroll down
                st["scroll_offset"] = min(st["max_scroll"], st["scroll_offset"] + ENTRY_HEIGHT * 2)
            
            # Check if back button clicked
            back_rect = st.get("back_button_rect")
            if back_rect and back_rect.collidepoint(event.pos):
                return S.MODE_MENU
    
    return None


def update(gs, dt, **_):
    """Update leaderboard screen (handle smooth scrolling)."""
    st = getattr(gs, "_leaderboard", None)
    if st is None:
        return
    
    # Smooth scroll with mouse wheel (if implemented)
    # For now, scroll_offset is updated directly in handle()


def draw(screen: pygame.Surface, gs, dt, **_):
    """Draw leaderboard screen."""
    st = getattr(gs, "_leaderboard", None)
    if st is None:
        enter(gs)
        st = gs._leaderboard
    
    # Dark background
    screen.fill(DARK_BG)
    
    # Title
    title_font = _get_font(48, bold=True)
    title_text = title_font.render("LEADERBOARD", True, DND_RED)
    title_rect = title_text.get_rect(center=(S.LOGICAL_WIDTH // 2, 60))
    screen.blit(title_text, title_rect)
    
    # Main panel (red border matching menu style)
    panel_x = 100
    panel_y = 120
    panel_w = S.LOGICAL_WIDTH - 200
    panel_h = S.LOGICAL_HEIGHT - 240
    
    # Draw panel background
    panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
    pygame.draw.rect(screen, PANEL_BG, panel_rect, border_radius=8)
    pygame.draw.rect(screen, PANEL_BORDER, panel_rect, 3, border_radius=8)
    
    # Header row
    header_y = panel_y + 20
    header_font = _get_font(20, bold=True)
    rank_text = header_font.render("RANK", True, DND_RED)
    name_text = header_font.render("PLAYER", True, DND_RED)
    score_text = header_font.render("SCORE", True, DND_RED)
    
    screen.blit(rank_text, (panel_x + 30, header_y))
    screen.blit(name_text, (panel_x + 150, header_y))
    screen.blit(score_text, (panel_x + panel_w - 200, header_y))
    
    # Draw entries
    entries = st["entries"]
    start_y = panel_y + 60
    visible_start = int(st["scroll_offset"] // (ENTRY_HEIGHT + ENTRY_SPACING))
    visible_end = min(len(entries), visible_start + ENTRIES_PER_PAGE + 1)
    
    for i in range(visible_start, visible_end):
        if i >= len(entries):
            break
        
        entry = entries[i]
        rank = i + 1
        y_pos = start_y + (i - visible_start) * (ENTRY_HEIGHT + ENTRY_SPACING) - int(st["scroll_offset"] % (ENTRY_HEIGHT + ENTRY_SPACING))
        
        # Skip if off-screen
        if y_pos < panel_y + 50 or y_pos > panel_y + panel_h - 20:
            continue
        
        # Entry background (alternating or highlight top 3)
        entry_rect = pygame.Rect(panel_x + 10, y_pos, panel_w - 20, ENTRY_HEIGHT)
        if rank <= 3:
            # Top 3 get special highlight (red tint)
            highlight_color = (DND_RED[0] // 4, DND_RED[1] // 4, DND_RED[2] // 4, 100)
            highlight_surf = pygame.Surface((entry_rect.w, entry_rect.h), pygame.SRCALPHA)
            highlight_surf.fill(highlight_color)
            screen.blit(highlight_surf, entry_rect.topleft)
        elif i % 2 == 0:
            # Alternating rows
            pygame.draw.rect(screen, (30, 30, 35), entry_rect, border_radius=4)
        
        # Rank
        rank_font = _get_font(24, bold=(rank <= 3))
        rank_color = DND_RED if rank <= 3 else WHITE
        rank_str = f"{rank:02d}"
        rank_surf = rank_font.render(rank_str, True, rank_color)
        screen.blit(rank_surf, (panel_x + 30, y_pos + (ENTRY_HEIGHT - rank_surf.get_height()) // 2))
        
        # Character token
        try:
            token = party_ui.load_player_token(entry.get("gender", "male"))
            if token:
                # Scale token to TOKEN_SIZE
                token_w, token_h = token.get_width(), token.get_height()
                scale = TOKEN_SIZE / max(token_w, token_h)
                scaled_w = int(token_w * scale)
                scaled_h = int(token_h * scale)
                scaled_token = pygame.transform.smoothscale(token, (scaled_w, scaled_h))
                token_x = panel_x + 100
                token_y = y_pos + (ENTRY_HEIGHT - scaled_h) // 2
                screen.blit(scaled_token, (token_x, token_y))
        except Exception as e:
            print(f"⚠️ Failed to load token for entry {i}: {e}")
        
        # Player name
        name_font = _get_font(22)
        name = entry.get("name", "Unknown")
        name_surf = name_font.render(name, True, WHITE)
        screen.blit(name_surf, (panel_x + 170, y_pos + (ENTRY_HEIGHT - name_surf.get_height()) // 2))
        
        # Score
        score_font = _get_font(24, bold=True)
        score = entry.get("score", 0)
        score_str = f"{score:,}"
        score_surf = score_font.render(score_str, True, DND_RED)
        score_x = panel_x + panel_w - 200
        screen.blit(score_surf, (score_x, y_pos + (ENTRY_HEIGHT - score_surf.get_height()) // 2))
    
    # Scrollbar (if needed)
    if st["max_scroll"] > 0:
        scrollbar_x = panel_x + panel_w - 20
        scrollbar_y = panel_y + 60
        scrollbar_h = panel_h - 80
        scrollbar_w = 8
        
        # Background
        pygame.draw.rect(screen, (50, 50, 55), (scrollbar_x, scrollbar_y, scrollbar_w, scrollbar_h), border_radius=4)
        
        # Thumb
        thumb_height = max(20, int(scrollbar_h * (panel_h / (len(entries) * (ENTRY_HEIGHT + ENTRY_SPACING)))))
        thumb_y = scrollbar_y + int((st["scroll_offset"] / st["max_scroll"]) * (scrollbar_h - thumb_height)) if st["max_scroll"] > 0 else scrollbar_y
        pygame.draw.rect(screen, DND_RED, (scrollbar_x, thumb_y, scrollbar_w, thumb_height), border_radius=4)
    
    # Back button
    back_font = _get_font(32, bold=True)
    
    # Hover effect
    try:
        screen_mx, screen_my = pygame.mouse.get_pos()
        mx, my = coords.screen_to_logical((screen_mx, screen_my))
    except:
        mx, my = pygame.mouse.get_pos()
    
    back_rect = pygame.Rect(0, 0, 200, 50)
    back_rect.center = (S.LOGICAL_WIDTH // 2, S.LOGICAL_HEIGHT - 60)
    
    # Determine color based on hover (matching menu button style)
    if back_rect.collidepoint(mx, my):
        back_color = DND_RED_HOV
    else:
        back_color = DND_RED
    
    back_text = back_font.render("BACK", True, back_color)
    screen.blit(back_text, back_text.get_rect(center=back_rect.center))
    st["back_button_rect"] = back_rect

