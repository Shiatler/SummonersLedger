# ============================================================
# combat/btn/_btn_draw.py
# ============================================================
import pygame
from systems import coords

def draw_icon_button(screen: pygame.Surface, icon: pygame.Surface | None, rect: pygame.Rect, *, hover_alpha: int = 70):
    """Icon-only button with a subtle hover glow, no border."""
    if icon:
        screen.blit(icon, rect.topleft)
    else:
        pygame.draw.rect(screen, (60, 60, 60), rect, border_radius=10)

    mx, my = coords.screen_to_logical(pygame.mouse.get_pos())
    if rect.collidepoint(mx, my):
        glow = pygame.Surface(rect.size, pygame.SRCALPHA)
        glow.fill((255, 255, 255, hover_alpha))
        screen.blit(glow, rect.topleft)