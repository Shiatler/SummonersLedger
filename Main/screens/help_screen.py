# =============================================================
# screens/help_screen.py — Help & Rules
# =============================================================
import pygame
import settings as S
from combat import type_chart as TC
from systems.theme import DND_RED, DND_RED_HOV, DND_FRAME, PANEL_BG, PANEL_BORDER, load_fonts
from systems.hud_style import draw_parchment_panel

def enter(gs, **_):
    # Initialize scroll state when entering
    setattr(gs, "_help_scroll", 0)
    # Cache fonts for consistency with the rest of the UI
    fonts = load_fonts()
    setattr(gs, "_help_fonts", fonts)

def handle(events, gs, **_):
    for e in events:
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                ret = getattr(gs, "_help_return_to", None)
                if ret == "PAUSE":
                    return S.MODE_PAUSE
                return S.MODE_MENU
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1:
                if _get_back_rect().collidepoint(e.pos):
                    ret = getattr(gs, "_help_return_to", None)
                    if ret == "PAUSE":
                        return S.MODE_PAUSE
                    return S.MODE_MENU
    return None

def _get_back_rect():
    w, h = 200, 54
    x = (S.LOGICAL_WIDTH - w) // 2
    y = S.LOGICAL_HEIGHT - 80
    return pygame.Rect(x, y, w, h)

def draw(screen, gs, dt=0.0, **_):
    # Background frame
    screen.fill(DND_FRAME)

    fonts = getattr(gs, "_help_fonts", load_fonts())
    title_f = fonts["title"]
    h_f     = fonts["button"]
    body_f  = fonts["normal"]

    # Main layout rect (inset with margins)
    margin = 28
    panel_rect = pygame.Rect(margin, margin, S.LOGICAL_WIDTH - margin * 2, S.LOGICAL_HEIGHT - margin * 2 - 70)
    # Removed outer parchment panel to avoid double-HUD appearance

    # Title removed per request (no header text at top)

    # Scrollable content region inside the panel
    content_padding = 24
    content_rect = panel_rect.inflate(-content_padding * 2, -content_padding * 2)

    # Build content surface (virtual, taller than view)
    scroll = 0
    content_w = content_rect.width - 20  # leave room for scrollbar gutter
    # Estimate content height (we'll over-allocate, it's fine)
    content_h = max(content_rect.height, 1800)
    content = pygame.Surface((content_w, content_h), pygame.SRCALPHA)

    cx, cy = 0, 0

    # Boxed section helpers
    box_gap = 16
    inner_pad = 14

    def _measure_bullets_height(font, lines, gap=6):
        h = 0
        for line in lines:
            h += font.get_height() + gap
        return max(0, h - (gap if lines else 0))

    def box_section(header: str, lines: list[str]):
        nonlocal cy
        # Compute box height
        header_h = h_f.get_height()
        bullets_h = _measure_bullets_height(body_f, lines, gap=6)
        needed_h = inner_pad * 2 + header_h + 8 + bullets_h

        rect = pygame.Rect(cx, cy, content_w, needed_h)
        draw_parchment_panel(content, rect, base_color=(52, 44, 40), border_color=(32, 26, 22), alpha=200)

        # Header
        hx = rect.x + inner_pad
        hy = rect.y + inner_pad
        _blit_header(content, h_f, header, (hx, hy))
        # Divider
        div_y = hy + header_h + 6
        pygame.draw.line(content, (90, 50, 50), (hx, div_y), (rect.right - inner_pad, div_y), 2)

        # Bullets
        by = div_y + 8
        _blit_bullets(content, body_f, lines, hx + 6, by, color=(230, 220, 210), gap=6)

        cy = rect.bottom + box_gap

    def box_type_chart(header: str):
        nonlocal cy
        header_h = h_f.get_height()
        classes = sorted(TC.CLASS_TYPE_CHART.keys())
        types = list(TC.ALL_DAMAGE_TYPES)

        # Measure label column width
        label_w = 0
        for cls in classes:
            sw = body_f.render(cls.title(), True, (0, 0, 0)).get_width()
            label_w = max(label_w, sw)
        label_w += 16  # padding inside label column

        # Cell sizing
        available_w = content_w - inner_pad * 2 - label_w - 8
        cols = max(1, len(types))
        cell_w = max(80, available_w // cols)
        cell_h = max(36, body_f.get_height() + 14)

        grid_h = (len(classes) + 1) * cell_h  # +1 for header row
        legend_h = body_f.get_height() + 10
        needed_h = inner_pad * 2 + header_h + 8 + grid_h + legend_h

        rect = pygame.Rect(cx, cy, content_w, needed_h)
        draw_parchment_panel(content, rect, base_color=(52, 44, 40), border_color=(32, 26, 22), alpha=200)

        hx = rect.x + inner_pad
        hy = rect.y + inner_pad
        _blit_header(content, h_f, header, (hx, hy))
        div_y = hy + header_h + 6
        pygame.draw.line(content, (90, 50, 50), (hx, div_y), (rect.right - inner_pad, div_y), 2)

        # Grid origin
        gx = hx
        gy = div_y + 8

        # Header row background
        header_rect = pygame.Rect(gx, gy, rect.width - inner_pad * 2, cell_h)
        pygame.draw.rect(content, (60, 40, 40), header_rect)
        # Header row: first cell blank (label column), then damage types
        # Label column header
        pygame.draw.rect(content, (50, 35, 35), (gx, gy, label_w, cell_h))
        lbl = body_f.render("Defender", True, (230, 220, 220))
        content.blit(lbl, lbl.get_rect(center=(gx + label_w // 2, gy + cell_h // 2)))

        # Damage type headers
        for i, t in enumerate(types):
            cx0 = gx + label_w + i * cell_w
            rect_h = pygame.Rect(cx0, gy, cell_w, cell_h)
            pygame.draw.rect(content, (70, 50, 50), rect_h, width=1)
            txt = body_f.render(t, True, (255, 230, 230))
            content.blit(txt, txt.get_rect(center=rect_h.center))

        # Rows for each class
        for r, cls in enumerate(classes):
            y0 = gy + (r + 1) * cell_h
            # Zebra background
            if r % 2 == 0:
                pygame.draw.rect(content, (46, 36, 34), (gx, y0, rect.width - inner_pad * 2, cell_h))

            # Left label cell
            pygame.draw.rect(content, (50, 35, 35), (gx, y0, label_w, cell_h), width=1)
            name = body_f.render(cls.title(), True, (235, 225, 220))
            content.blit(name, name.get_rect(midleft=(gx + 8, y0 + cell_h // 2)))

            # Cells per damage type
            for c, t in enumerate(types):
                cx0 = gx + label_w + c * cell_w
                cell_rect = pygame.Rect(cx0, y0, cell_w, cell_h)
                mult = TC.get_type_effectiveness(t, cls)
                label = TC.get_effectiveness_label(mult)
                color = TC.get_effectiveness_color(mult)
                # Background tint by effectiveness
                if label == "2x":
                    bg = (28, 60, 28)
                elif label == "0.5x":
                    bg = (70, 34, 34)
                else:
                    bg = (40, 36, 36)
                pygame.draw.rect(content, bg, cell_rect)
                pygame.draw.rect(content, (80, 60, 60), cell_rect, width=1)
                txt = body_f.render(label, True, color)
                content.blit(txt, txt.get_rect(center=cell_rect.center))

        # Legend
        ly = gy + grid_h + 6
        legend_items = [
            ("2x", (100, 255, 100), (28, 60, 28)),
            ("1x", (220, 220, 220), (40, 36, 36)),
            ("0.5x", (255, 100, 100), (70, 34, 34)),
        ]
        lx = gx
        for text, fg, bg in legend_items:
            chip = pygame.Rect(lx, ly, 64, cell_h - 8)
            pygame.draw.rect(content, bg, chip, border_radius=6)
            pygame.draw.rect(content, (80, 60, 60), chip, 1, border_radius=6)
            t_surf = body_f.render(text, True, fg)
            content.blit(t_surf, t_surf.get_rect(center=chip.center))
            lx += chip.width + 10

        cy = rect.bottom + box_gap

    # Only render the type chart (remove other sections)
    box_type_chart("Type Interactions")

    # Compute max scroll based on content height
    max_scroll = 0

    # Clip and blit the scrolled viewport
    view = pygame.Rect(0, scroll, content_rect.width, content_rect.height)
    screen.set_clip(content_rect)
    screen.blit(content, content_rect.topleft, area=view)
    screen.set_clip(None)

    # No scrollbar when scrolling is disabled

    # Back button styled (use logical coordinates for hover so it works at any resolution)
    back_rect = _get_back_rect()
    try:
        from systems import coords
        mx, my = coords.screen_to_logical(pygame.mouse.get_pos())
    except (ImportError, AttributeError):
        mx, my = pygame.mouse.get_pos()
    hovered = back_rect.collidepoint((mx, my))
    pygame.draw.rect(screen, PANEL_BG, back_rect, border_radius=12)
    pygame.draw.rect(screen, PANEL_BORDER, back_rect, 2, border_radius=12)
    back_lbl = h_f.render("Back", True, DND_RED_HOV if hovered else DND_RED)
    screen.blit(back_lbl, back_lbl.get_rect(center=back_rect.center))

def _blit_header(screen, font, text, pos):
    surf = font.render(text, True, (240, 210, 210))
    screen.blit(surf, pos)

def _blit_bullets(screen, font, lines, x, y, color=(210,210,210), gap=8):
    for line in lines:
        surf = font.render(f"• {line}", True, color)
        screen.blit(surf, (x, y))
        y += surf.get_height() + gap
    return y

def _blit_type_chart(screen, font, x, y, max_w):
    # Create a readable listing: Class — Deals: X | Weak: A,B | Resist: C,D
    line_gap = 6
    for cls in sorted(TC.CLASS_TYPE_CHART.keys()):
        data = TC.CLASS_TYPE_CHART[cls]
        deals = data["deals"]
        weak = ", ".join(data["weak_to"]) or "-"
        resi = ", ".join(data["resists"]) or "-"
        text = f"{cls.title():<12} — Deals: {deals} | Weak: {weak} | Resist: {resi}"
        surf = font.render(text, True, (225, 215, 210))
        screen.blit(surf, (x, y))
        y += surf.get_height() + line_gap
    return y


