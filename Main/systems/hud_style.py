# ============================================================
# systems/hud_style.py — Helper utilities for HUD styling
# ============================================================

import pygame


def _gradient_overlay(size: tuple[int, int],
                      top_color: tuple[int, int, int],
                      bottom_color: tuple[int, int, int],
                      alpha: int = 60) -> pygame.Surface:
    """Return a vertical gradient surface with the provided colors."""
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    if height <= 1:
        surface.fill((*top_color, alpha))
        return surface

    for y in range(height):
        t = y / (height - 1)
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        pygame.draw.line(surface, (r, g, b, alpha), (0, y), (width, y))
    return surface


def _draw_corner_studs(panel: pygame.Surface,
                       width: int,
                       height: int) -> None:
    """Draw decorative studs on each corner of the panel."""
    outer = (50, 35, 20)  # Darker outer
    inner = (180, 150, 110)  # Darker inner
    radius_outer = max(4, min(width, height) // 18)
    radius_inner = max(2, radius_outer - 2)
    offsets = (
        (radius_outer + 3, radius_outer + 3),
        (width - radius_outer - 3, radius_outer + 3),
        (radius_outer + 3, height - radius_outer - 3),
        (width - radius_outer - 3, height - radius_outer - 3),
    )
    for pos in offsets:
        pygame.draw.circle(panel, outer, pos, radius_outer)
        pygame.draw.circle(panel, inner, pos, radius_inner)


def _draw_notches_alpha(panel: pygame.Surface,
                        color: tuple[int, int, int, int],
                        shade: tuple[int, int, int, int],
                        width: int,
                        height: int) -> None:
    """Draw parchment-like notches on each edge of the panel with alpha support."""
    notch_positions = (0.12, 0.32, 0.55, 0.78)
    notch_depth = max(3, min(width, height) // 22)

    # Top edge
    for ratio in notch_positions:
        x = int(ratio * width)
        pygame.draw.polygon(panel, color, [(x - notch_depth, 0),
                                           (x + notch_depth, 0),
                                           (x, notch_depth)])
        pygame.draw.polygon(panel, shade, [(x - notch_depth + 2, 1),
                                           (x + notch_depth - 2, 1),
                                           (x, notch_depth - 2)])

    # Bottom edge
    for ratio in notch_positions:
        x = int(ratio * width)
        pygame.draw.polygon(panel, color, [(x - notch_depth, height),
                                           (x + notch_depth, height),
                                           (x, height - notch_depth)])
        pygame.draw.polygon(panel, shade, [(x - notch_depth + 2, height - 1),
                                           (x + notch_depth - 2, height - 1),
                                           (x, height - notch_depth + 2)])

    # Left edge
    for ratio in notch_positions:
        y = int(ratio * height)
        pygame.draw.polygon(panel, color, [(0, y - notch_depth),
                                           (0, y + notch_depth),
                                           (notch_depth, y)])
        pygame.draw.polygon(panel, shade, [(1, y - notch_depth + 2),
                                           (1, y + notch_depth - 2),
                                           (notch_depth - 2, y)])

    # Right edge
    for ratio in notch_positions:
        y = int(ratio * height)
        pygame.draw.polygon(panel, color, [(width, y - notch_depth),
                                           (width, y + notch_depth),
                                           (width - notch_depth, y)])
        pygame.draw.polygon(panel, shade, [(width - 1, y - notch_depth + 2),
                                           (width - 1, y + notch_depth - 2),
                                           (width - notch_depth + 2, y)])


def draw_parchment_panel(screen: pygame.Surface,
                         rect: pygame.Rect,
                         *,
                         base_color: tuple[int, int, int] = (60, 50, 40),
                         border_color: tuple[int, int, int] = (30, 25, 20),
                         alpha: int = 180) -> None:
    """
    Draw a very dark HUD panel that fits a medieval aesthetic.
    Semi-transparent background to let the world show through.
    """
    width, height = rect.width, rect.height
    if width <= 0 or height <= 0:
        return

    alpha = max(0, min(255, alpha))
    base_rgba = (*base_color, alpha)

    # Create transparent-ready surface
    panel = pygame.Surface((width, height), pygame.SRCALPHA)
    panel.fill(base_rgba)

    # Very dark gradient for depth
    gradient = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(70 * (1 - t) + 50 * t)
        g = int(60 * (1 - t) + 40 * t)
        b = int(50 * (1 - t) + 30 * t)
        pygame.draw.line(gradient, (r, g, b, alpha), (0, y), (width, y))
    panel.blit(gradient, (0, 0))

    # Decorative notches around the edges (darker)
    notch_color = (80, 70, 60, alpha)
    notch_shade = (50, 40, 35, min(255, int(alpha * 0.8)))
    _draw_notches_alpha(panel, notch_color, notch_shade, width, height)

    # Main border - still readable
    pygame.draw.rect(panel, (*border_color, alpha), panel.get_rect(), width=2)
    inner_border_color = (90, 75, 60, min(255, int(alpha * 0.9)))
    pygame.draw.rect(panel, inner_border_color, panel.get_rect().inflate(-5, -5), width=1)

    # Corner studs removed

    screen.blit(panel, rect.topleft)


def draw_slot_panel(screen: pygame.Surface,
                    rect: pygame.Rect,
                    *,
                    hovered: bool = False,
                    filled: bool = False) -> None:
    """Draw a medieval-style slot panel that matches the parchment HUD."""
    width, height = rect.width, rect.height
    if width <= 0 or height <= 0:
        return

    panel = pygame.Surface((width, height), pygame.SRCALPHA)
    
    # Darker base color that matches the darker HUD
    if filled:
        base = (120, 95, 65, 220)
        highlight = (150, 120, 85, 50)
    else:
        base = (100, 80, 55, 180)
        highlight = (130, 105, 75, 40)
    
    panel.fill(base)
    
    # Inner highlight for depth
    inner_rect = panel.get_rect().inflate(-3, -3)
    pygame.draw.rect(panel, highlight, inner_rect)
    
    # Border that matches the HUD style
    pygame.draw.rect(panel, (60, 45, 30), panel.get_rect(), width=2)
    pygame.draw.rect(panel, (160, 130, 95, 70), inner_rect, width=1)
    
    # Subtle corner accents
    corner_size = 3
    corners = [
        (corner_size, corner_size),
        (width - corner_size, corner_size),
        (corner_size, height - corner_size),
        (width - corner_size, height - corner_size),
    ]
    for cx, cy in corners:
        pygame.draw.circle(panel, (80, 60, 40), (cx, cy), 2)
    
    if hovered:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((200, 170, 120, 40))
        panel.blit(overlay, (0, 0))

    screen.blit(panel, rect.topleft)
