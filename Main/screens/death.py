# ============================================================
# screens/death.py — party wipe screen (self-animating in draw)
# Background: Assets/Map/Graveyard.png (scaled to screen)
# Music: Assets/Music/Sounds/GraveyardDeath.mp3 (infinite loop, no fades)
# Exit button: alternates DeathR.png/DeathW.png every 0.2s, big, no border
# ============================================================

from __future__ import annotations
import os, pygame
import settings as S

MODE_DEATH = getattr(S, "MODE_DEATH", "DEATH")
MODE_MENU  = getattr(S, "MODE_MENU",  "MENU")

BG_IMG        = None
ANIM_FRAMES   = None  # [Surface, Surface]
MUSIC_PATH    = os.path.join("Assets", "Music", "Sounds", "GraveyardDeath.mp3")
BG_PATH       = os.path.join("Assets", "Map", "Graveyard.png")
DEATH_R_PATH  = os.path.join("Assets", "Animations", "DeathR.png")
DEATH_W_PATH  = os.path.join("Assets", "Animations", "DeathW.png")

# flip every 0.2s
ANIM_INTERVAL = 0.2

def _load_bg():
    global BG_IMG
    if BG_IMG is not None:
        return BG_IMG
    if not os.path.exists(BG_PATH):
        print(f"⚠️ Missing death background at {BG_PATH}")
        return None
    try:
        BG_IMG = pygame.image.load(BG_PATH).convert()
    except Exception as e:
        print(f"⚠️ Failed to load Graveyard.png: {e}")
        BG_IMG = None
    return BG_IMG

def _load_anim_frames():
    """Load DeathR/DeathW once; return list[Surface] (can be length 1 if one missing)."""
    global ANIM_FRAMES
    if ANIM_FRAMES is not None:
        return ANIM_FRAMES
    frames = []
    for p in (DEATH_R_PATH, DEATH_W_PATH):
        if os.path.exists(p):
            try:
                frames.append(pygame.image.load(p).convert_alpha())
            except Exception as e:
                print(f"⚠️ Failed to load {p}: {e}")
        else:
            print(f"⚠️ Missing animation frame: {p}")
    ANIM_FRAMES = frames
    return ANIM_FRAMES

def _start_loop_music():
    """Play the death theme on an infinite loop, no fade, bypassing audio bank."""
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    try:
        if os.path.exists(MUSIC_PATH):
            pygame.mixer.music.load(MUSIC_PATH)
            pygame.mixer.music.play(-1)  # loop forever, no fade
        else:
            print(f"⚠️ Death music file not found: {MUSIC_PATH}")
    except Exception as e:
        print(f"⚠️ Could not play death music: {e}")

def _stop_music():
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass

def enter(gs, **_):
    """Initialize death screen state."""
    _load_bg()
    _load_anim_frames()
    st = {
        "t": 0.0,         # elapsed time (used by draw now)
        "frame_i": 0,     # current frame index
        "btn_rect": None, # clickable rect set in draw
    }
    gs._death = st
    _start_loop_music()

def handle(events, gs, **_):
    st = getattr(gs, "_death", None)
    if st is None:
        enter(gs); st = gs._death

    for e in events:
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
            _stop_music()
            return MODE_MENU
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            rect = st.get("btn_rect")
            if rect and rect.collidepoint(e.pos):
                _stop_music()
                return MODE_MENU
    return None

def update(gs, dt, **_):
    # Note: We no longer rely on update() to advance animation; draw() handles it.
    pass

def draw(screen: pygame.Surface, gs, dt, **_):
    st = getattr(gs, "_death", None)
    if st is None:
        enter(gs); st = gs._death

    sw, sh = screen.get_size()

    # --- Background ---
    bg = _load_bg()
    if bg:
        if bg.get_width() != sw or bg.get_height() != sh:
            screen.blit(pygame.transform.smoothscale(bg, (sw, sh)), (0, 0))
        else:
            screen.blit(bg, (0, 0))
    else:
        screen.fill((0, 0, 0))

    # --- Advance animation timer HERE so it works even if update() isn't called ---
    st["t"] = st.get("t", 0.0) + dt
    frames = _load_anim_frames()
    if frames and len(frames) >= 2:
        flips = int(st["t"] // ANIM_INTERVAL)
        st["frame_i"] = flips % 2
    else:
        st["frame_i"] = 0

    # --- Animated Exit Button (DeathR/DeathW) ---
    frame = frames[st["frame_i"] % max(1, len(frames))] if frames else None

    # Big: ~55% of screen height (min 240, max 700)
    target_h = max(240, min(int(sh * 0.8), 1000))
    if frame:
        fw, fh = frame.get_width(), frame.get_height()
        scale = target_h / max(1, fh)
        target_w = int(fw * scale)
        btn_surf = pygame.transform.smoothscale(frame, (target_w, target_h))
    else:
        target_w = target_h
        btn_surf = pygame.Surface((target_w, target_h), pygame.SRCALPHA)
        pygame.draw.ellipse(btn_surf, (235, 235, 235, 200), btn_surf.get_rect())

    # Position centered a bit lower
    btn_rect = btn_surf.get_rect(center=(sw // 2, int(sh * 0.5)))
    st["btn_rect"] = btn_rect

    # Hover glow only (no border/ring)
    if btn_rect.collidepoint(pygame.mouse.get_pos()):
        glow = pygame.Surface((int(btn_rect.w * 1.14), int(btn_rect.h * 1.14)), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 255, 255, 42), glow.get_rect())
        screen.blit(glow, glow.get_rect(center=btn_rect.center))

    # Draw the button
    screen.blit(btn_surf, btn_rect)
