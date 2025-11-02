# ============================================================
# screens/death_saves.py — Death Saves screen
#  • Loops LowHealth.mp3
#  • Backdrop image
#  • Gender-specific figure falls in from top
#  • Faint red blink
#  • Top-right clickable badge rolls 1d20:
#       <10 = fail, >10 = success, 10 = no change
#    - Shows Success.png / Fail.png overlay with short fade-in + sound
#    - Overlay click/key dismisses; once 3 fails → Death; 3 successes → Overworld (all party to 1 HP)
#  • Hover glow on badge
# ============================================================

import os
import random
import pygame
import settings as S
from systems import audio as audio_sys

MODE_DEATH = getattr(S, "MODE_DEATH", "DEATH")

# ---- Paths ----
DEATHSAVES_DIR = os.path.join("Assets", "DeathSaves")  # Success.png / Fail.png live here

# ---- Tunables ----
BLINK_INTERVAL = 0.35   # seconds per state (black -> red -> black …)
RED_ALPHA      = 72     # faint red overlay alpha (0..255)
BADGE_MARGIN   = 16     # px from top-right edges
BADGE_MAX_WFR  = 0.38   # badge max width fraction of screen
BADGE_MAX_HFR  = 0.28   # badge max height fraction of screen

# Overlay (Success/Fail) visuals
OVERLAY_FADE_DUR = 0.25   # seconds to fade Success/Fail PNG in
OVERLAY_MAX_HFR  = 0.55   # max overlay height as fraction of screen

# Character fall & screen fade
CHAR_FALL_DUR = 1.2       # seconds for the character to fall into place
SCREEN_FADE_DUR = 1.2     # seconds for the whole screen fade-in


# ================= Helpers ================= #

def _compute_badge_rect(sw: int, sh: int, badge: pygame.Surface) -> pygame.Rect:
    """Compute where the badge should draw (scaled) in top-right corner."""
    bw, bh = badge.get_width(), badge.get_height()
    max_bw = int(sw * BADGE_MAX_WFR)
    max_bh = int(sh * BADGE_MAX_HFR)
    scale = min(1.0, max_bw / max(1, bw), max_bh / max(1, bh))
    draw = pygame.transform.smoothscale(badge, (int(bw * scale), int(bh * scale))) if scale < 1.0 else badge
    rect = draw.get_rect()
    rect.top = BADGE_MARGIN
    rect.right = sw - BADGE_MARGIN
    return rect

def _death_save_image_path(gender: str) -> str | None:
    """MDeathSave.* or FDeathSave.* under Assets/PlayableCharacters"""
    base = os.path.join("Assets", "PlayableCharacters")
    stem = "MDeathSave" if (gender or "").lower().startswith("m") else "FDeathSave"
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(base, stem + ext)
        if os.path.exists(p):
            return p
    return None

def _badge_path_for_counts(succ: int, fail: int) -> str | None:
    """
    Prefer Assets/DeathSaves/DeathSavesS{succ}F{fail}.(png|jpg|jpeg),
    fallback to Assets/DeathSaves/DeathSaves.png if present.
    """
    base = os.path.join("Assets", "DeathSaves")
    # Try numbered variants first
    stem = f"DeathSavesS{int(succ)}F{int(fail)}"
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(base, stem + ext)
        if os.path.exists(p):
            return p
    # Fallback to plain DeathSaves
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(base, "DeathSaves" + ext)
        if os.path.exists(p):
            return p
    return None


def _backdrop_path() -> str | None:
    """Backdrop behind everything."""
    p = os.path.join("Assets", "Map", "DeathSavesBackdrop.png")
    return p if os.path.exists(p) else None

def _find_success_image() -> str | None:
    """Look for Success.png/jpg/jpeg in Assets/DeathSaves."""
    if not os.path.isdir(DEATHSAVES_DIR): 
        return None
    for f in os.listdir(DEATHSAVES_DIR):
        name, ext = os.path.splitext(f)
        if name.lower() == "success" and ext.lower() in (".png", ".jpg", ".jpeg"):
            return os.path.join(DEATHSAVES_DIR, f)
    return None

def _find_fail_image() -> str | None:
    """Look for Fail.png/jpg/jpeg in Assets/DeathSaves."""
    if not os.path.isdir(DEATHSAVES_DIR): 
        return None
    for f in os.listdir(DEATHSAVES_DIR):
        name, ext = os.path.splitext(f)
        if name.lower() == "fail" and ext.lower() in (".png", ".jpg", ".jpeg"):
            return os.path.join(DEATHSAVES_DIR, f)
    return None

def _fail_success_sound_path() -> str | None:
    """FailSuccess.mp3 (one-shot on showing overlay)."""
    p = os.path.join("Assets", "Music", "Sounds", "FailSuccess.mp3")
    return p if os.path.exists(p) else None


# ================= Lifecycle ================= #

def enter(gs, **_):
    gender  = getattr(gs, "player_gender", None) or getattr(gs, "chosen_gender", "male")
    img_p   = _death_save_image_path(gender)
    badge_p = _badge_path_for_counts(0, 0)
    back_p  = _backdrop_path()

    main_surf  = None
    badge_surf = None
    back_surf  = None

    # --- Looping Low Health SFX (music channel) ---
    try:
        low_hp_path = os.path.join("Assets", "Music", "Sounds", "LowHealth.mp3")
        if os.path.exists(low_hp_path):
            pygame.mixer.music.stop()
            pygame.mixer.music.load(low_hp_path)
            pygame.mixer.music.play(-1)  # loop forever, no fade
            print(f"[death_saves] Playing loop: {low_hp_path}")
        else:
            print(f"[death_saves] ⚠️ Missing sound: {low_hp_path}")
    except Exception as e:
        print(f"[death_saves] ⚠️ Could not play LowHealth.mp3: {e}")

    # --- Images ---
    if img_p:
        try:
            main_surf = pygame.image.load(img_p).convert_alpha()
        except Exception as e:
            print(f"⚠️ Failed to load death save art '{img_p}': {e}")

    if badge_p:
        try:
            badge_surf = pygame.image.load(badge_p).convert_alpha()
        except Exception as e:
            print(f"⚠️ Failed to load badge '{badge_p}': {e}")

    if back_p:
        try:
            back_surf = pygame.image.load(back_p).convert()
        except Exception as e:
            print(f"⚠️ Failed to load backdrop '{back_p}': {e}")

    # --- Overlays ---
    succ_img = None
    fail_img = None
    try:
        sp = _find_success_image()
        fp = _find_fail_image()
        if sp: succ_img = pygame.image.load(sp).convert_alpha()
        if fp: fail_img = pygame.image.load(fp).convert_alpha()
    except Exception as e:
        print(f"[death_saves] ⚠️ Failed to load Success/Fail overlays: {e}")

    gs._death_saves = {
        "t": 0.0,                 # elapsed time since enter
        "surf": main_surf,        # gender figure
        "badge": badge_surf,
        "backdrop": back_surf,
        "gender": gender,
        "blink_on": False,
        "blink_acc": 0.0,
        "succ": 0,                # death save successes
        "fail": 0,                # death save failures
        "badge_rect": None,

        # Overlay state
        "overlay": None,                      # {"img": Surface, "t": seconds since shown}
        "overlay_success_img": succ_img,
        "overlay_fail_img": fail_img,
        "overlay_sfx_path": _fail_success_sound_path(),
    }


def handle(events, gs, **_):
    st = getattr(gs, "_death_saves", None)
    if st is None:
        enter(gs); st = gs._death_saves

    # If an overlay is up, dismiss on any key or left-click, then check resolution.
    if st.get("overlay"):
        for e in events:
            if e.type == pygame.KEYDOWN or (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
                st["overlay"] = None  # dismiss
                # Resolve terminal states now
                if st["fail"] >= 3:
                    try: pygame.mixer.music.stop()
                    except Exception: pass
                    return MODE_DEATH
                if st["succ"] >= 3:
                    stats = getattr(gs, "party_vessel_stats", []) or []
                    for st_v in stats:
                        if isinstance(st_v, dict):
                            st_v["current_hp"] = 1
                    try: pygame.mixer.music.stop()
                    except Exception: pass
                    return S.MODE_GAME
                return None
        return None  # overlay visible, keep consuming until dismissed

    for e in events:
        # Badge click rolls a death save (only LMB)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            badge = st.get("badge")
            if badge:
                surf = pygame.display.get_surface()
                sw, sh = surf.get_size() if surf else (S.WIDTH, S.HEIGHT)
                rect = _compute_badge_rect(sw, sh, badge)
                if rect.collidepoint(e.pos):
                    # Dice SFX (try keys; else click fallback)
                    bank = getattr(S, "AUDIO_BANK", None)
                    if bank:
                        for key in ("dice", "diceroll", "roll", "dice_roll"):
                            if key in bank.sfx:
                                audio_sys.play_sfx(bank, key, vol_scale=1.0)
                                break
                        else:
                            audio_sys.play_click(bank)

                    # Roll and apply
                    roll = random.randint(1, 20)
                    outcome = None
                    if roll < 10:
                        st["fail"] += 1
                        outcome = "fail"
                    elif roll > 10:
                        st["succ"] += 1
                        outcome = "success"

                    # If we had a change (not 10), pop overlay right now
                    if outcome:
                        # ---- refresh the badge based on new S/F ----
                        try:
                            new_badge_p = _badge_path_for_counts(st["succ"], st["fail"])
                            if new_badge_p:
                                st["badge"] = pygame.image.load(new_badge_p).convert_alpha()
                        except Exception as e:
                            print(f"[death_saves] ⚠️ Failed to refresh badge: {e}")

                        img = st["overlay_success_img"] if outcome == "success" else st["overlay_fail_img"]
                        if img:
                            st["overlay"] = {"img": img, "t": 0.0}  # draw() will fade-in

                            # One-shot overlay SFX (bank key 'failsuccess' else direct path)
                            played = False
                            if bank and "failsuccess" in bank.sfx:
                                audio_sys.play_sfx(bank, "failsuccess", vol_scale=1.0)
                                played = True
                            if not played:
                                sfx_path = st.get("overlay_sfx_path")
                                if sfx_path and os.path.exists(sfx_path):
                                    try:
                                        s = pygame.mixer.Sound(sfx_path)
                                        audio_sys.play_sound(s, vol_scale=1.0)
                                    except Exception as ee:
                                        print(f"[death_saves] ⚠️ overlay SFX failed: {ee}")


                    # Do not resolve to DEATH/GAME immediately; wait until overlay dismissed.
                    return None

        # Escape hatch: any key without overlay goes straight to death
        if e.type == pygame.KEYDOWN:
            try: pygame.mixer.music.stop()
            except Exception: pass
            return MODE_DEATH

    return None


def draw(screen, gs, dt, **_):
    st = getattr(gs, "_death_saves", None)
    if st is None:
        enter(gs); st = gs._death_saves

    st["t"] += dt
    st["blink_acc"] += dt
    while st["blink_acc"] >= BLINK_INTERVAL:
        st["blink_acc"] -= BLINK_INTERVAL
        st["blink_on"] = not st["blink_on"]

    sw, sh = screen.get_size()

    # ---- BACKDROP ----
    back = st.get("backdrop")
    if back:
        bw, bh = back.get_width(), back.get_height()
        scale = max(sw / max(1, bw), sh / max(1, bh))
        bg_scaled = back if scale == 1 else pygame.transform.smoothscale(back, (int(bw * scale), int(bh * scale)))
        rect = bg_scaled.get_rect(center=(sw // 2, sh // 2))
        screen.blit(bg_scaled, rect)
    else:
        screen.fill((0, 0, 0))

    # ---- MAIN CHARACTER ART (fall from top) ----
    surf = st.get("surf")
    if surf:
        iw, ih = surf.get_width(), surf.get_height()
        scale = min(sw / max(1, iw), sh / max(1, ih))
        tw, th = max(1, int(iw * scale)), max(1, int(ih * scale))
        scaled = surf if (iw == tw and ih == th) else pygame.transform.smoothscale(surf, (tw, th))

        target_y = sh // 2
        progress = min(1.0, st["t"] / CHAR_FALL_DUR)
        ease = 1 - pow(1 - progress, 3)  # ease-out cubic
        y = -th + (target_y + th) * ease

        rect = scaled.get_rect(center=(sw // 2, int(y)))
        screen.blit(scaled, rect)

    # ---- FAINT RED BLINK ----
    if st.get("blink_on", False):
        red = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        red.fill((255, 0, 0, RED_ALPHA))
        screen.blit(red, (0, 0))

    # ---- TOP-RIGHT BADGE (with hover glow) ----
    badge = st.get("badge")
    if badge:
        rect = _compute_badge_rect(sw, sh, badge)
        st["badge_rect"] = rect  # debug

        # Exact size as computed
        bw, bh = badge.get_width(), badge.get_height()
        draw_w, draw_h = rect.size
        badge_draw = pygame.transform.smoothscale(badge, (draw_w, draw_h)) if (draw_w, draw_h) != (bw, bh) else badge

        # Hover glow
        mx, my = pygame.mouse.get_pos()
        if rect.collidepoint(mx, my):
            glow_pad_w = int(rect.w * 0.16)
            glow_pad_h = int(rect.h * 0.16)
            glow_w = rect.w + glow_pad_w * 2
            glow_h = rect.h + glow_pad_h * 2
            glow = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (255, 255, 255, 42), glow.get_rect())
            screen.blit(glow, glow.get_rect(center=rect.center))

        screen.blit(badge_draw, rect)

    # ---- SUCCESS/FAIL OVERLAY (center, short fade-in) ----
    ov = st.get("overlay")
    if ov and ov.get("img"):
        ov["t"] = ov.get("t", 0.0) + dt
        alpha = 255 if ov["t"] >= OVERLAY_FADE_DUR else int(255 * (ov["t"] / OVERLAY_FADE_DUR))

        img = ov["img"]
        iw, ih = img.get_size()
        target_h = int(sh * OVERLAY_MAX_HFR)
        scale = target_h / max(1, ih)
        tw, th = max(1, int(iw * scale)), max(1, int(ih * scale))
        draw_img = img if (tw, th) == (iw, ih) else pygame.transform.smoothscale(img, (tw, th))

        tinted = draw_img.copy()
        tinted.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)

        rect = tinted.get_rect(center=(sw // 2, sh // 2))
        screen.blit(tinted, rect)

    # ---- SCREEN FADE-IN OVERLAY (on enter) ----
    if st["t"] < SCREEN_FADE_DUR:
        fade_alpha = int(255 * (1 - st["t"] / SCREEN_FADE_DUR))
        fade = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        fade.fill((0, 0, 0, fade_alpha))
        screen.blit(fade, (0, 0))
