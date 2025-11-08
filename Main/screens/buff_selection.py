# ============================================================
# screens/buff_selection.py — Buff/Curse selection screen
# - Shows 3 clickable cards after summoner battle victory
# - Player selects one card to receive the buff
# ============================================================

import os
import pygame
import settings as S
from systems import buffs
from systems import audio as audio_sys

# Font helper
_DH_FONT_PATH = None

def _resolve_dh_font() -> str | None:
    """Find a font file in Assets/Fonts whose filename contains 'DH'."""
    global _DH_FONT_PATH
    if _DH_FONT_PATH is not None:
        return _DH_FONT_PATH
    
    candidates = [
        os.path.join("Assets", "Fonts"),
        r"C:\Users\Frederik\Desktop\SummonersLedger\Assets\Fonts",
    ]
    for folder in candidates:
        if os.path.isdir(folder):
            for fname in os.listdir(folder):
                low = fname.lower()
                if "dh" in low and low.endswith((".ttf", ".otf", ".ttc")):
                    _DH_FONT_PATH = os.path.join(folder, fname)
                    return _DH_FONT_PATH
    _DH_FONT_PATH = None
    return None

def _get_dh_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Prefer DH font; fall back to a system font if missing."""
    try:
        path = _resolve_dh_font()
        if path:
            return pygame.font.Font(path, size)
    except Exception as e:
        print(f"⚠️ Failed to load DH font: {e}")
    try:
        return pygame.font.SysFont("georgia", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)


def enter(gs, **kwargs):
    """Initialize the buff selection screen."""
    # Generate buff selection (pass gs to exclude "once per run" cards)
    selection = buffs.generate_buff_selection(gs)
    
    # Load card images
    card_images = []
    for card in selection["cards"]:
        img = buffs.load_card_image(card["image_path"])
        card_images.append(img)
    
    # Screen state
    gs._buff_selection = {
        "tier": selection["tier"],
        "cards": selection["cards"],
        "card_images": card_images,
        "hovered_index": None,
        "selected_index": None,
    }
    
    # Play click sound
    try:
        audio_sys.play_click(audio_sys.get_global_bank())
    except Exception:
        pass


def handle(events, gs, dt=None, **kwargs):
    """Handle input events."""
    st = getattr(gs, "_buff_selection", None)
    if st is None:
        return None
    
    # If a card was selected, we're done
    if st.get("selected_index") is not None:
        return None
    
    # Handle mouse events
    for event in events:
        if event.type == pygame.MOUSEMOTION:
            # Update hover state
            mouse_pos = event.pos
            hovered = _get_card_at_position(mouse_pos, st)
            st["hovered_index"] = hovered
        
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Click on a card
            mouse_pos = event.pos
            clicked = _get_card_at_position(mouse_pos, st)
            if clicked is not None:
                st["selected_index"] = clicked
                # Play selection sound
                try:
                    audio_sys.play_click(audio_sys.get_global_bank())
                except Exception:
                    pass
                # Apply the buff (for now just store it)
                _apply_selected_buff(gs, st, clicked)
                # Return to overworld after a brief delay (handled in draw)
                return None
        
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # Skip selection (optional - for testing)
                # For now, we'll require selection
                pass
    
    return None


def draw(screen, gs, dt, **kwargs):
    """Draw the buff selection screen."""
    st = getattr(gs, "_buff_selection", None)
    if st is None:
        return
    
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    
    # Dark semi-transparent overlay
    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    screen.blit(overlay, (0, 0))
    
    # Title
    tier = st["tier"]
    title_text = "Choose a Curse" if tier == "Curse" else "Choose a Blessing"
    title_font = _get_dh_font(48, bold=True)
    title_surf = title_font.render(title_text, True, (255, 255, 255))
    title_rect = title_surf.get_rect(center=(sw // 2, 80))
    screen.blit(title_surf, title_rect)
    
    # Tier label
    tier_font = _get_dh_font(32)
    tier_surf = tier_font.render(f"{tier} Tier", True, (200, 200, 200))
    tier_rect = tier_surf.get_rect(center=(sw // 2, title_rect.bottom + 20))
    screen.blit(tier_surf, tier_rect)
    
    # Draw 3 cards
    card_width = 280
    card_height = 400
    card_spacing = 40
    total_width = (card_width * 3) + (card_spacing * 2)
    start_x = (sw - total_width) // 2
    card_y = sh // 2 - card_height // 2
    
    for i, card in enumerate(st["cards"]):
        card_x = start_x + i * (card_width + card_spacing)
        
        # Hover effect
        is_hovered = st.get("hovered_index") == i
        is_selected = st.get("selected_index") == i
        
        # Scale for hover
        scale = 1.1 if is_hovered else 1.0
        if is_selected:
            scale = 1.15
        
        # Card image
        card_img = st["card_images"][i]
        if card_img:
            # Scale image
            scaled_w = int(card_width * scale)
            scaled_h = int(card_height * scale)
            scaled_img = pygame.transform.smoothscale(card_img, (scaled_w, scaled_h))
            
            # Center the scaled card
            draw_x = card_x + (card_width - scaled_w) // 2
            draw_y = card_y + (card_height - scaled_h) // 2
            
            # Draw border/glow for hover
            if is_hovered or is_selected:
                border_color = (255, 215, 0) if is_selected else (255, 255, 255)
                border_width = 4 if is_selected else 2
                border_rect = pygame.Rect(draw_x - border_width, draw_y - border_width,
                                        scaled_w + border_width * 2, scaled_h + border_width * 2)
                pygame.draw.rect(screen, border_color, border_rect, border_width, border_radius=8)
            
            screen.blit(scaled_img, (draw_x, draw_y))
        else:
            # Fallback: draw a placeholder
            placeholder_rect = pygame.Rect(card_x, card_y, card_width, card_height)
            pygame.draw.rect(screen, (60, 60, 60), placeholder_rect)
            pygame.draw.rect(screen, (120, 120, 120), placeholder_rect, 3)
            
            # Card name
            name_font = _get_dh_font(24)
            name_surf = name_font.render(card["name"], True, (255, 255, 255))
            name_rect = name_surf.get_rect(center=placeholder_rect.center)
            screen.blit(name_surf, name_rect)
        
        # Card name below image
        name_font = _get_dh_font(20)
        name_surf = name_font.render(card["name"], True, (255, 255, 255))
        name_rect = name_surf.get_rect(center=(card_x + card_width // 2, card_y + card_height + 30))
        screen.blit(name_surf, name_rect)
    
    # Instructions
    if st.get("selected_index") is None:
        inst_font = _get_dh_font(18)
        inst_text = "Click a card to select"
        inst_surf = inst_font.render(inst_text, True, (180, 180, 180))
        inst_rect = inst_surf.get_rect(center=(sw // 2, sh - 60))
        screen.blit(inst_surf, inst_rect)
    else:
        # Selected - transition back to overworld after brief delay
        st["transition_timer"] = st.get("transition_timer", 0.0) + dt
        if st["transition_timer"] > 0.5:  # 0.5 second delay
            # Clear selection state
            if hasattr(gs, "_buff_selection"):
                delattr(gs, "_buff_selection")
            # Return to overworld
            return S.MODE_GAME
    
    return None


def _get_card_at_position(pos, st) -> int | None:
    """Get the index of the card at the given position, or None."""
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    card_width = 280
    card_height = 400
    card_spacing = 40
    total_width = (card_width * 3) + (card_spacing * 2)
    start_x = (sw - total_width) // 2
    card_y = sh // 2 - card_height // 2
    
    for i in range(len(st["cards"])):
        card_x = start_x + i * (card_width + card_spacing)
        card_rect = pygame.Rect(card_x, card_y, card_width, card_height)
        if card_rect.collidepoint(pos):
            return i
    
    return None


def _apply_selected_buff(gs, st, card_index: int):
    """Apply the selected buff to the game state."""
    card = st["cards"][card_index]
    
    # Initialize buffs list if needed
    if not hasattr(gs, "active_buffs"):
        gs.active_buffs = []
    if not hasattr(gs, "buffs_history"):
        gs.buffs_history = []
    
    # Create buff entry
    buff_entry = {
        "tier": card["tier"],
        "id": card["id"],
        "name": card["name"],
        "image_path": card["image_path"],
        # "effects": {},  # Will be added later
    }
    
    # Add to active buffs and history
    gs.active_buffs.append(buff_entry)
    gs.buffs_history.append(buff_entry)
    
    print(f"✨ Buff selected: {card['name']} ({card['tier']} tier)")

