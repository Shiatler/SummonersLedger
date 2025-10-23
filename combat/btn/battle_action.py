# ============================================================
# combat/btn/battle_action.py — Battle menu (dynamic L1 moves)
# - Builds rows from moves.get_available_moves(gs)
# - Shows dice preview (left) and PP (right)
# - Disables/dims moves at 0 PP and blocks selection
# - Calls moves.queue(gs, move.id) on selection
# ============================================================
import os
import pygame
from ._btn_layout import rect_at, load_scaled
from ._btn_draw import draw_icon_button
from systems import audio as audio_sys
from combat import moves

# ------------- Button assets -------------
_ICON = None
_RECT = None

def _ensure():
    global _ICON, _RECT
    if _RECT is None:
        _RECT = rect_at(0, 0)  # top-left battle button
    if _ICON is None:
        _ICON = load_scaled(os.path.join("Assets", "Map", "BBattleUI.png"))

def draw_button(screen: pygame.Surface):
    _ensure()
    draw_icon_button(screen, _ICON, _RECT)

def handle_click(pos) -> bool:
    _ensure()
    if not _RECT.collidepoint(pos):
        return False
    audio_sys.play_click(audio_sys.get_global_bank())
    toggle_popup()
    return True

# ------------- Popup state -------------
_OPEN = False
_PANEL_RECT: pygame.Rect | None = None
_SELECTED = 0  # index into visible rows

# Box geometry (relative to screen)
_BOX_W = 0.60
_BOX_H = 0.30
_BOX_Y_ANCHOR = 0.70

# Visuals
_BG = (235, 235, 235)
_BORDER = (0, 0, 0)
_TEXT = (20, 20, 20)
_TEXT_SUB = (60, 60, 60)
_TEXT_DISABLED = (120, 120, 120)
_TEXT_HOVER = (0, 0, 0)
_HILITE = (0, 0, 0)

# ------------- DH Font -------------
_DH_FONT_PATH = os.path.join("Assets", "Fonts", "DH.otf")
_DH_FONT_CACHE: dict[int, pygame.font.Font] = {}
def _dh_font(px: int) -> pygame.font.Font:
    px = max(12, int(px))
    f = _DH_FONT_CACHE.get(px)
    if f is None:
        try:
            f = pygame.font.Font(_DH_FONT_PATH, px)
        except Exception:
            f = pygame.font.SysFont("arial", px)
        _DH_FONT_CACHE[px] = f
    return f

# ------------- Popup API -------------
def is_open() -> bool:
    return _OPEN

def open_popup():
    global _OPEN, _SELECTED
    _OPEN = True
    _SELECTED = 0

def close_popup():
    global _OPEN
    _OPEN = False
    _set_cursor_default()

def toggle_popup():
    if _OPEN: close_popup()
    else: open_popup()

# ------------- Layout helpers -------------
def _panel_rect_for(screen: pygame.Surface) -> pygame.Rect:
    sw, sh = screen.get_size()
    w = int(sw * _BOX_W)
    h = int(sh * _BOX_H)
    offset_x = int(sw * 0.2)  # shift right to clear HP bars
    x = (sw - w) // 2 + offset_x
    y = min(int(sh * _BOX_Y_ANCHOR), sh - h - 8)
    return pygame.Rect(x, y, w, h)

def _move_rows(panel: pygame.Rect, gs):
    """
    Return (rects, labels, subs_left, subs_right, handlers, disabled_flags).
    subs_left  -> dice preview (e.g., '1d6 + STR')
    subs_right -> PP text (e.g., 'PP 17/20')
    """
    pad = 14
    row_h = max(28, panel.h // 6)  # allow up to ~5 moves comfortably
    first_y = panel.y + pad + 6

    rects = []
    labels = []
    subs_left = []
    subs_right = []
    handlers = []
    disabled = []

    mv_list = moves.get_available_moves(gs)
    for mv in mv_list:
        n, s = mv.dice
        abil = mv.ability if "|" not in mv.ability else mv.ability.replace("|", "/")
        left = f"{n}d{s} + {abil}"
        rem, mx = moves.get_pp(gs, mv.id)
        right = f"PP {rem}/{mx}"
        i = len(rects)
        rects.append(pygame.Rect(panel.x + pad, first_y + i * (row_h + 6), panel.w - pad*2, row_h))
        labels.append(mv.label)
        subs_left.append(left)
        subs_right.append(right)
        disabled.append(rem <= 0)
        handlers.append((lambda _id=mv.id: (lambda gs: moves.queue(gs, _id)))())

    # BACK row
    i = len(rects)
    rects.append(pygame.Rect(panel.x + pad, first_y + i * (row_h + 6), panel.w - pad*2, row_h))
    labels.append("BACK")
    subs_left.append("")
    subs_right.append("")
    disabled.append(False)
    handlers.append(lambda gs: close_popup())

    return rects, labels, subs_left, subs_right, handlers, disabled

#-------------- NO PP Helper -----------------------
def _all_moves_out_of_pp(gs) -> bool:
    return moves._all_moves_out_of_pp(gs)  # reuse core check

# ------------- Input routing while open -------------
def handle_event(e, gs) -> bool:
    """Return True to consume events while modal."""
    if not _OPEN:
        return False

    bank = audio_sys.get_global_bank()

    # Close on ESC
    if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
        audio_sys.play_click(bank)
        close_popup()
        return True

    rects, labels, subs_left, subs_right, handlers, disabled = _move_rows(_PANEL_RECT or pygame.Rect(0,0,0,0), gs)
    count = len(rects)
    if count == 0:
        close_popup()
        return True

    global _SELECTED
    if e.type == pygame.KEYDOWN:
        if e.key in (pygame.K_UP, pygame.K_w):
            _SELECTED = (_SELECTED - 1) % count
            audio_sys.play_click(bank)
            return True
        if e.key in (pygame.K_DOWN, pygame.K_s):
            _SELECTED = (_SELECTED + 1) % count
            audio_sys.play_click(bank)
            return True
        if e.key in (pygame.K_RETURN, pygame.K_SPACE):
            audio_sys.play_click(bank)
            if not disabled[_SELECTED]:
                ok = handlers[_SELECTED](gs)
                if labels[_SELECTED] == "BACK" or ok:
                    close_popup()
                    gs._turn_ready = False  # <-- mark turn consumed
            else:
                # If all moves are empty, selecting any row triggers Bonk (Struggle)
                try:
                    if moves._all_moves_out_of_pp(gs):
                        moves.queue_bonk(gs)
                        close_popup()
                        gs._turn_ready = False  # <-- mark turn consumed
                except Exception:
                    pass
            return True

    # Mouse motion → cursor style
    if e.type == pygame.MOUSEMOTION and _PANEL_RECT:
        if any(r.collidepoint(e.pos) for r in rects):
            _set_cursor_hand()
        else:
            _set_cursor_default()
        return False  # don't consume

    # Mouse clicks
    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
        mx, my = e.pos
        if _PANEL_RECT and not _PANEL_RECT.collidepoint(mx, my):
            audio_sys.play_click(bank)
            close_popup()
            return True
        if _PANEL_RECT and _PANEL_RECT.collidepoint(mx, my):
            for i, r in enumerate(rects):
                if r.collidepoint(mx, my):
                    _SELECTED = i
                    audio_sys.play_click(bank)
                    if not disabled[i]:
                        ok = handlers[i](gs)
                        if labels[i] == "BACK" or ok:
                            close_popup()
                            gs._turn_ready = False  # <-- mark turn consumed
                    else:
                        try:
                            if moves._all_moves_out_of_pp(gs):
                                moves.queue_bonk(gs)
                                close_popup()
                                gs._turn_ready = False  # <-- mark turn consumed
                        except Exception:
                            pass
                    return True
    return True  # modal



# ------------- Drawing -------------
def draw_popup(screen: pygame.Surface, gs):
    """GB-style double border box with DH font + hover highlight."""
    if not _OPEN:
        return
    panel = _panel_rect_for(screen)
    global _PANEL_RECT, _SELECTED
    _PANEL_RECT = panel

    # Base (GB-like box)
    box = pygame.Surface(panel.size, pygame.SRCALPHA)
    box.fill(_BG)
    pygame.draw.rect(box, _BORDER, box.get_rect(), 3)                       # outer
    pygame.draw.rect(box, _BORDER, box.get_rect().inflate(-10, -10), 3)     # inner
    div_x = 18
    pygame.draw.line(box, _BORDER, (div_x, 8), (div_x, box.get_height() - 8), 3)

    rects, labels, subs_left, subs_right, _handlers, disabled = _move_rows(panel, gs)

    # Clamp selection
    if labels:
        _SELECTED = max(0, min(_SELECTED, len(labels) - 1))
    else:
        _SELECTED = 0

    # Hover
    mx, my = pygame.mouse.get_pos()
    hover_idx = -1
    for i, r in enumerate(rects):
        if r.collidepoint(mx, my):
            hover_idx = i
            break

    # Fonts
    name_font = _dh_font(max(20, min(28, int(panel.h * 0.20))))
    sub_font  = _dh_font(max(14, min(20, int(panel.h * 0.15))))

    # Draw each row
    for i, (r, label, left, right) in enumerate(zip(rects, labels, subs_left, subs_right)):
        _draw_row(
            box, r.move(-panel.x, -panel.y),
            title=label, subtitle_left=left, subtitle_right=right,
            selected=(_SELECTED == i), highlight=(hover_idx == i),
            disabled=disabled[i],
            name_font=name_font, sub_font=sub_font
        )

    screen.blit(box, panel.topleft)

def _draw_row(surface: pygame.Surface, rect: pygame.Rect, *, title: str,
              subtitle_left: str, subtitle_right: str,
              selected: bool, highlight: bool, disabled: bool,
              name_font, sub_font):
    # highlight strip
    if highlight or selected:
        hi = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        hi.fill((0, 0, 0, 56 if selected else 28))
        surface.blit(hi, rect.topleft)

    # arrow pointer
    left_offset = 12
    if selected:
        tri_w = max(8, int(rect.h * 0.24))
        tri_h = max(10, int(rect.h * 0.42))
        tri_x = rect.x + 4
        cy    = rect.y + rect.h // 2
        pts = [(tri_x, cy), (tri_x + tri_w, cy - tri_h // 2), (tri_x + tri_w, cy + tri_h // 2)]
        pygame.draw.polygon(surface, _HILITE, pts)
        left_offset = 24 + tri_w

    # colors
    col_title = (_TEXT_SUB if disabled else (_TEXT_HOVER if (highlight or selected) else _TEXT))
    col_sub   = (_TEXT_SUB if disabled else _TEXT_SUB)

    # geometry
    padding    = 10
    gap_name_dice = 10   # space between title and dice
    right_pad  = 12
    mid_y      = rect.y + rect.h // 2
    x_cursor   = rect.x + left_offset + padding

    # draw PP on the right first, so we know our right boundary
    if subtitle_right:
        txt_pp = sub_font.render(subtitle_right, False, col_sub)
        pp_rect = txt_pp.get_rect(midright=(rect.right - right_pad, mid_y))
        surface.blit(txt_pp, pp_rect)
        right_limit = pp_rect.left - 8
    else:
        right_limit = rect.right - right_pad

    # prepare dice (goes to the RIGHT of the title)
    dice_w = 0
    txt_dice = None
    if subtitle_left:
        txt_dice = sub_font.render(subtitle_left, False, col_sub)
        dice_w = txt_dice.get_width()

    # figure out how much width the title may take (leaving space for dice + gap)
    reserve_for_dice = (dice_w + gap_name_dice) if txt_dice else 0
    max_title_right = right_limit - reserve_for_dice
    if max_title_right <= x_cursor:  # no space at all; drop dice to save room
        txt_dice = None
        dice_w = 0
        reserve_for_dice = 0
        max_title_right = right_limit

    # render (possibly ellipsized) title
    base_title = title
    txt_title = name_font.render(base_title, False, col_title)
    title_rect = txt_title.get_rect(midleft=(x_cursor, mid_y))

    if title_rect.right > max_title_right:
        # shrink by ellipsis until it fits
        while base_title and title_rect.right > max_title_right:
            base_title = base_title[:-1]
            txt_title = name_font.render(base_title + "…", False, col_title)
            title_rect = txt_title.get_rect(midleft=(x_cursor, mid_y))

    surface.blit(txt_title, title_rect)

    # place dice immediately to the right of the title (if it still fits)
    if txt_dice:
        dice_x = title_rect.right + gap_name_dice
        # only draw dice if it won’t collide with PP
        if dice_x + dice_w <= right_limit:
            surface.blit(txt_dice, txt_dice.get_rect(midleft=(dice_x, mid_y)))





# ------------- Cursor helpers (safe no-ops if unsupported) -------------
def _set_cursor_hand():
    try:
        pygame.mouse.set_system_cursor(pygame.SYSTEM_CURSOR_HAND)
    except Exception:
        pass

def _set_cursor_default():
    try:
        pygame.mouse.set_system_cursor(pygame.SYSTEM_CURSOR_ARROW)
    except Exception:
        pass
