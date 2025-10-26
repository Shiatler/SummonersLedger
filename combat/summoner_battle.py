# ============================================================
# combat/summoner_battle.py — Summoner vs Summoner (ally uses your chosen character)
# Enemy side: big summoner sprite (vessel-sized).
# Ally side : your playable character sprite (scaled to vessel-ish height).
# Plates are hidden while summoners are present.
# Adds: after 1.0s, both summoners slide off-screen (ally -> left, enemy -> right),
#       then a 2-second swirl animation plays exactly where each summoner stood.
# ============================================================
from __future__ import annotations
import os
import re
import glob
import random
import pygame
import settings as S

from systems import xp as xp_sys   # kept so XP strip calls compile (visual only here)
from systems import audio as audio_sys  # ← SFX playback like wild_vessel
from combat.btn import battle_action, bag_action, party_action
from rolling import ui as roll_ui


# ---------- Layout & tween tunables ----------
SUMMON_TIME        = 0.60
SLIDE_AWAY_DELAY   = 1.00   # wait this long, then start sliding them away
SLIDE_AWAY_TIME    = 0.60   # how long the slide-away takes

ALLY_OFFSET        = (290, -140)
ENEMY_OFFSET       = (-400, 220)
ALLY_SCALE         = 1.0
ENEMY_SCALE        = 1.0
TARGET_ALLY_H      = 400
TARGET_ENEMY_H     = 420
FALLBACK_ENEMY_H   = 360

# --- Swirl placement tunables (nudge these to taste) ---
SWIRL_ALLY_OFFSET  = (-10, -20)
SWIRL_ENEMY_OFFSET = ( 20, -10)

# Swirl timing & playback
SWIRL_TOTAL_DUR = 2.0   # play VFX for 2 seconds total (end of phase)
SWIRL_FPS       = 30    # target frames per second for the swirl
SWIRL_LOOP      = True  # loop through frames during those 2 seconds

# Fallback if your settings doesn’t define a battle mode constant
MODE_BATTLE = getattr(S, "MODE_BATTLE", "BATTLE")

# --- SFX path (same style as wild_vessel) ---
TELEPORT_SFX = os.path.join("Assets", "Music", "Sounds", "Teleport.mp3")

# --- Font helpers for DH font (local or absolute fallback) ---
_DH_FONT_PATH = None
def _resolve_dh_font() -> str | None:
    """Find a font file in Assets/Fonts (or absolute path) whose filename contains 'DH'."""
    global _DH_FONT_PATH
    if _DH_FONT_PATH is not None:
        return _DH_FONT_PATH

    candidates = [
        os.path.join("Assets", "Fonts"),
        r"C:\Users\Frederik\Desktop\SummonersLedger\Assets\Fonts",  # absolute fallback
    ]
    for folder in candidates:
        if os.path.isdir(folder):
            for fname in os.listdir(folder):
                low = fname.lower()
                if "dh" in low and low.endswith((".ttf", ".otf", ".ttc")):
                    _DH_FONT_PATH = os.path.join(folder, fname)
                    print(f"🅵 Using DH font: {_DH_FONT_PATH}")
                    return _DH_FONT_PATH

    print("ℹ️ DH font not found; using system fallback.")
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
    # fallback
    try:
        return pygame.font.SysFont("arial", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)



# --- New helper to load animation frames ---
def _load_swirl_animation() -> list[pygame.Surface]:
    frames = []
    base_dir = os.path.join("Assets", "Animations")

    # Keep VFX reasonable; huge alpha surfaces are expensive.
    target_h = int(S.HEIGHT * 0.65)  # tune if needed (0.5–0.8 works well)

    for i in range(1, 43):
        fname = f"fx_4_ver1_{i:02}.png"
        path = os.path.join(base_dir, fname)
        if not os.path.exists(path):
            continue
        try:
            img = pygame.image.load(path).convert_alpha()
            # Scale to a target HEIGHT (keeps aspect)
            w, h = img.get_size()
            if h > 0:
                s = target_h / float(h)
                if s != 1.0:
                    img = pygame.transform.smoothscale(img, (max(1, int(w * s)), max(1, int(h * s))))
            # IMPORTANT: convert_alpha again after scaling for display-optimized blits
            img = img.convert_alpha()
            frames.append(img)
        except Exception as e:
            print(f"⚠️ Failed to load swirl frame {fname}: {e}")
    return frames


# ---------- Small helpers ----------
def _load_sfx(path: str):
    """Match wild_vessel style SFX loader."""
    try:
        if not path or not os.path.exists(path):
            return None
        return pygame.mixer.Sound(path)
    except Exception as e:
        print(f"⚠️ SFX load fail {path}: {e}")
        return None

def _try_load(path: str | None):
    if path and os.path.exists(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"⚠️ load fail {path}: {e}")
    return None

def _smooth_scale_to_height(surf: pygame.Surface | None, target_h: int) -> pygame.Surface | None:
    if surf is None or target_h <= 0:
        return surf
    w, h = surf.get_width(), surf.get_height()
    if h <= 0: return surf
    s = target_h / float(h)
    return pygame.transform.smoothscale(surf, (max(1, int(w*s)), max(1, int(h*s))))

def _smooth_scale(surf: pygame.Surface | None, scale: float) -> pygame.Surface | None:
    if surf is None or abs(scale - 1.0) < 1e-6:
        return surf
    w, h = surf.get_width(), surf.get_height()
    return pygame.transform.smoothscale(surf, (max(1, int(w*scale)), max(1, int(h*scale))))

def _pretty_name_from_token(fname: str | None) -> str:
    if not fname: return "Ally"
    base = os.path.splitext(os.path.basename(fname))[0]
    for p in ("StarterToken", "MToken", "FToken", "RToken"):
        if base.startswith(p):
            base = base[len(p):]; break
    return re.sub(r"\d+$", "", base) or "Ally"

def _hp_ratio_from_stats(stats: dict | None) -> float:
    if not isinstance(stats, dict):
        return 1.0
    try:
        maxhp = max(1, int(stats.get("hp", 10)))
        curhp = int(stats.get("current_hp", maxhp))
        curhp = max(0, min(curhp, maxhp))
        return curhp / maxhp
    except Exception:
        return 1.0

#----- Music helper ---------------------
def _pick_summoner_track() -> str | None:
    base = os.path.join("Assets", "Music", "SummonerMusic")
    choices = [os.path.join(base, f"SummonerM{i}.mp3") for i in range(1, 5)]
    choices = [p for p in choices if os.path.exists(p)]
    if not choices:
        choices = glob.glob(os.path.join(base, "*.mp3"))
    return random.choice(choices) if choices else None

# --- XP helpers (visuals only) ---
def _xp_compute(stats: dict) -> tuple[int, int, int, float]:
    try:    lvl = max(1, int(stats.get("level", 1)))
    except: lvl = 1
    try:    cur = max(0, int(stats.get("xp_current", stats.get("xp", 0))))
    except: cur = 0
    need = stats.get("xp_needed")
    try:
        need = int(need) if need is not None else int(xp_sys.xp_needed(lvl))
    except Exception:
        need = 1
    need = max(1, need)
    return lvl, cur, need, max(0.0, min(1.0, cur/need))

def _draw_xp_strip(surface: pygame.Surface, rect: pygame.Rect, stats: dict):
    _, cur, need, r = _xp_compute(stats)
    frame=(70,45,30); border=(140,95,60); trough=(46,40,36); fill=(40,180,90); text=(230,220,200)
    pygame.draw.rect(surface, frame, rect, border_radius=6)
    pygame.draw.rect(surface, border, rect, 2, border_radius=6)
    inner = rect.inflate(-8,-8)
    font = pygame.font.SysFont("georgia", max(14, int(rect.h*0.60)), bold=False)
    label = font.render(f"XP: {cur} / {need}", True, text)
    surface.blit(label, label.get_rect(midleft=(inner.x+6, inner.centery)))
    bar_h = max(4, int(inner.h*0.36)); bar_w = max(90, int(inner.w*0.46))
    bar_x = inner.right - bar_w - 6; bar_y = inner.centery - bar_h//2
    pygame.draw.rect(surface, trough, (bar_x, bar_y, bar_w, bar_h), border_radius=3)
    fw = int(bar_w * r)
    if fw > 0:
        pygame.draw.rect(surface, fill, (bar_x, bar_y, fw, bar_h), border_radius=3)

def _draw_hp_bar(surface: pygame.Surface, rect: pygame.Rect, hp_ratio: float, name: str, align: str):
    hp_ratio = max(0.0, min(1.0, hp_ratio))
    x,y,w,h = rect
    frame=(70,45,30); border=(140,95,60); gold=(185,150,60); inner=(28,18,14)
    back=(60,24,24); front=(28,150,60)
    pygame.draw.rect(surface, frame, rect, border_radius=10)
    pygame.draw.rect(surface, border, rect, 3, border_radius=10)
    inner_rect = rect.inflate(-10, -10)
    pygame.draw.rect(surface, gold, inner_rect, 2, border_radius=8)
    name_h = max(22, int(h*0.44))
    plate = pygame.Rect(inner_rect.x+8, inner_rect.y+6, inner_rect.w-16, name_h)
    notch_w = max(38, int(h*0.46))
    notch = (pygame.Rect(plate.x, plate.y, notch_w, plate.h) if align=="right"
             else pygame.Rect(plate.right - notch_w, plate.y, notch_w, plate.h))
    pygame.draw.rect(surface, inner, plate, border_radius=6)
    pygame.draw.rect(surface, gold, plate, 2, border_radius=6)
    pygame.draw.rect(surface, frame, notch, border_radius=6)
    trough = pygame.Rect(inner_rect.x+12, plate.bottom+8, inner_rect.w-24, inner_rect.h-name_h-20)
    pygame.draw.rect(surface, back, trough, border_radius=6)
    fw = int(trough.w * hp_ratio)
    if fw > 0:
        pygame.draw.rect(surface, front, (trough.x, trough.y, fw, trough.h), border_radius=6)
    for i in range(1,4):
        tx = trough.x + (trough.w * i)//4
        pygame.draw.line(surface, (30,18,12), (tx, trough.y+3), (tx, trough.bottom-3), 2)
    font = pygame.font.SysFont("georgia", max(20, int(h*0.32)), bold=True)
    label = font.render(name, True, (230,210,180))
    if align == "left":
        surface.blit(label, label.get_rect(midleft=(plate.x+12, plate.centery)))
    else:
        surface.blit(label, label.get_rect(midright=(plate.right-12, plate.centery)))

# ---------- Ally summoner sprite loader ----------
def _load_player_summoner_big(gs) -> pygame.Surface | None:
    gender = (getattr(gs, "chosen_gender", "") or "").lower().strip()
    if gender not in ("male", "female"):
        tok = (getattr(gs, "player_token", "") or "").lower()
        if "female" in tok: gender = "female"
        elif "male" in tok: gender = "male"
        else: gender = "male"
    fname = "CharacterMale.png" if gender == "male" else "CharacterFemale.png"
    path = os.path.join("Assets", "PlayableCharacters", fname)
    surf = _try_load(path)
    if surf:
        return _smooth_scale_to_height(surf, TARGET_ALLY_H)
    return None

# ---------- Enemy summoner sprite loader ----------
def _load_summoner_big(name: str | None, encounter_sprite: pygame.Surface | None) -> pygame.Surface | None:
    n = (name or "").strip()
    search_dirs = []
    if n.startswith("F"): search_dirs.append(os.path.join("Assets", "SummonersFemale"))
    if n.startswith("M"): search_dirs.append(os.path.join("Assets", "SummonersMale"))
    search_dirs.append(os.path.join("Assets", "SummonersBoss"))
    for d in search_dirs:
        surf = _try_load(os.path.join(d, f"{n}.png"))
        if surf:
            return _smooth_scale_to_height(surf, TARGET_ENEMY_H)
    if encounter_sprite is not None:
        h_target = max(FALLBACK_ENEMY_H, TARGET_ENEMY_H)
        return _smooth_scale_to_height(encounter_sprite, h_target)
    return None

# ---------- Scene state ----------
def enter(gs, **_):
    try: battle_action.close_popup()
    except Exception: pass
    try: bag_action.close_popup()
    except Exception: pass
    try: party_action.close_popup()
    except Exception: pass

    setattr(gs, "mode", "SUMMONER_BATTLE")
    sw, sh = S.WIDTH, S.HEIGHT

    # Music
    try:
        pygame.mixer.music.fadeout(200)
    except Exception:
        pass
    track = _pick_summoner_track()
    if track:
        try:
            pygame.mixer.music.load(track)
            pygame.mixer.music.play(-1, fade_ms=220)
        except Exception as e:
            print(f"⚠️ Could not play summoner music: {e}")

    # Sprites
    ally_img  = _load_player_summoner_big(gs)
    enemy_img = _load_summoner_big(getattr(gs, "encounter_name", None),
                                   getattr(gs, "encounter_sprite", None))
    if ally_img is not None:  ally_img  = _smooth_scale(ally_img,  ALLY_SCALE)
    if enemy_img is not None: enemy_img = _smooth_scale(enemy_img, ENEMY_SCALE)

    # Anchors (their on-screen resting positions)
    ax1 = 20 + ALLY_OFFSET[0]
    ay1 = sh - (ally_img.get_height() if ally_img else 240) - 20 + ALLY_OFFSET[1]
    ex1 = sw - (enemy_img.get_width() if enemy_img else 240) - 20 + ENEMY_OFFSET[0]
    ey1 = 20 + ENEMY_OFFSET[1]

    # Centers for where the swirls should appear (middle of each summoner)
    ally_swirl_center = (
        ax1 + (ally_img.get_width() // 2 if ally_img else 120),
        ay1 + (ally_img.get_height() // 2 if ally_img else 120),
    )
    enemy_swirl_center = (
        ex1 + (enemy_img.get_width() // 2 if enemy_img else 120),
        ey1 + (enemy_img.get_height() // 2 if enemy_img else 120),
    )

    # Slide-in starts off-screen
    ally_start  = (-(ally_img.get_width() if ally_img else 240) - 60, ay1)
    enemy_start = (sw + 60, ey1)

    # Slide-away targets (off-screen)
    ally_out  = (-(ally_img.get_width() if ally_img else 240) - 80, ay1)  # further left
    enemy_out = (sw + 80, ey1)                                           # further right

    # Background
    bg_img = None
    for cand in ("Wild.png", "Trainer.png"):
        p = os.path.join("Assets", "Map", cand)
        if os.path.exists(p):
            try:
                bg_img = pygame.transform.smoothscale(pygame.image.load(p).convert(), (sw, sh))
                break
            except Exception as e:
                print(f"⚠️ Summoner bg load failed: {e}")

    # Party stats -> hp ratio (kept)
    party_stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    active_idx = getattr(gs, "combat_active_idx", 0)
    ally_stats = party_stats[active_idx] if 0 <= active_idx < len(party_stats) else None

    # Enemy name for the challenge line
    enemy_name = getattr(gs, "encounter_name", "a Summoner") or "a Summoner"
    st_text = f"You are challenged by {enemy_name}!"

    gs._summ_ui = {
        "bg": bg_img,

        # sprites
        "ally_img": ally_img,
        "enemy_img": enemy_img,

        # anchors + tween start/targets
        "ally_anchor": (ax1, ay1),     # on-screen positions after slide-in
        "enemy_anchor": (ex1, ey1),
        "ally_pos": list(ally_start),  # current tween start (for slide-in)
        "enemy_pos": list(enemy_start),
        "ally_target": (ax1, ay1),
        "enemy_target": (ex1, ey1),

        # slide-away targets
        "ally_out": ally_out,
        "enemy_out": enemy_out,

        # timing / phases
        "speed": 1.0 / max(0.001, SUMMON_TIME),
        "ally_t": 0.0,
        "enemy_t": 0.0,
        "elapsed": 0.0,
        "phase": "intro",              # "intro" -> (wait for click) -> "slide_out" -> "swirl" -> "done"
        "out_t": 0.0,
        "out_speed": 1.0 / max(0.001, SLIDE_AWAY_TIME),

        # plates data (hidden while summoners are present)
        "ally_hp_ratio": _hp_ratio_from_stats(ally_stats),
        "enemy_hp_ratio": 1.0,
        "active_idx": active_idx,
        "track": track,
        "summoner_mode": True,

        # swirl animation
        "swirl_frames": _load_swirl_animation(),
        "swirl_timer": 0.0,
        "swirl_idx": 0,

        # exact centers where the swirls should render
        "ally_swirl_center": ally_swirl_center,
        "enemy_swirl_center": enemy_swirl_center,

        # --- SFX cache (loaded once)
        "swirl_sfx": _load_sfx(TELEPORT_SFX),

        # --- Challenge textbox state ---
        "textbox_text": st_text,
        "textbox_active": False,      # ⬅ start hidden until slide-in completes
        "text_revealed": False,       # ⬅ internal guard so we reveal only once
        "text_reveal_delay": 0.15,    # ⬅ optional tiny delay after slide-in
        "text_reveal_t": 0.0,         # ⬅ timer for the delay
        "blink_t": 0.0,
    }


def handle(events, gs, dt=None, **_):
    st = getattr(gs, "_summ_ui", None)
    if st is None:
        enter(gs)
        st = gs._summ_ui

    # --- 0) If the intro finished, jump to the black battle scene immediately ---
    if st.get("pending_battle"):
        # (keep music playing seamlessly — no fade/stop here)

        # Clear encounter-related flags so overworld can trigger again later
        gs.in_encounter = False
        gs.encounter_name = ""
        gs.encounter_sprite = None
        setattr(gs, "_went_to_summoner", False)
        setattr(gs, "_went_to_wild", False)

        setattr(gs, "mode", MODE_BATTLE)
        try:
            from combat import battle as battle_scene
            battle_scene.enter(gs)
        except Exception:
            pass
        return MODE_BATTLE



    # --- 1) Textbox is modal until dismissed ---
    if st.get("textbox_active", False):
        for e in events:
            if (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE)) or \
               (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1):
                st["textbox_active"] = False
                st["phase"] = "slide_out"
                st["out_t"] = 0.0
                return None
        return None  # block all other input while textbox is up

    # --- 2) Dice popup (if ever shown here) is also modal ---
    if roll_ui.is_active():
        for e in events:
            roll_ui.handle_event(e)
        return None

    # --- 3) Minimal global escape to bail out back to overworld (optional) ---
    for e in events:
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            try:
                pygame.mixer.music.fadeout(200)
            except Exception:
                pass
            gs.in_encounter = False
            gs.encounter_name = ""
            gs.encounter_sprite = None
            setattr(gs, "_went_to_summoner", False)
            setattr(gs, "mode", S.MODE_GAME)
            return S.MODE_GAME

    # No-op otherwise
    return None




def draw(screen: pygame.Surface, gs, dt, **_):
    # If we already switched modes this frame, do nothing.
    if getattr(gs, "mode", None) != "SUMMONER_BATTLE":
        return

    # If the summoner intro UI was cleared during handoff, do nothing.
    st = getattr(gs, "_summ_ui", None)
    if st is None:
        return

    # Background
    if st.get("bg"):
        screen.blit(st["bg"], (0, 0))
    else:
        screen.fill((0, 0, 0))

    # Ease function
    ease = lambda t: 1.0 - (1.0 - t) ** 3

    # Phase timing
    st["elapsed"] = st.get("elapsed", 0.0) + dt
    phase = st.get("phase", "intro")

    # Update tween per phase
    if phase == "intro":
        # Cap how much the tween can advance this frame so we never snap to the end
        dt_anim = min(dt, 1.0 / 60.0)  # ~16.7ms max progress per frame

        # Slide IN to anchors
        st["ally_t"]  = min(1.0, st.get("ally_t", 0.0)  + dt_anim * st.get("speed", 1.0))
        st["enemy_t"] = min(1.0, st.get("enemy_t", 0.0) + dt_anim * st.get("speed", 1.0))

        ax0, ay0 = st["ally_pos"];   ax1, ay1 = st["ally_target"]
        ex0, ey0 = st["enemy_pos"];  ex1, ey1 = st["enemy_target"]
        ax = int(ax0 + (ax1 - ax0) * ease(st["ally_t"]))
        ay = int(ay0 + (ay1 - ay0) * ease(st["ally_t"]))
        ex = int(ex0 + (ex1 - ex0) * ease(st["enemy_t"]))
        ey = int(ey0 + (ey1 - ey0) * ease(st["enemy_t"]))

        # Reveal the textbox only after both have fully arrived (with a tiny delay)
        if st["ally_t"] >= 1.0 and st["enemy_t"] >= 1.0 and not st["text_revealed"]:
            st["text_reveal_t"] += dt_anim
            if st["text_reveal_t"] >= st.get("text_reveal_delay", 0.0):
                st["textbox_active"] = True
                st["text_revealed"] = True

    elif phase == "slide_out":
        st["out_t"] = min(1.0, st.get("out_t", 0.0) + dt * st.get("out_speed", 1.0))

        ax1, ay1 = st["ally_anchor"];   ax2, ay2 = st["ally_out"]
        ex1, ey1 = st["enemy_anchor"];  ex2, ey2 = st["enemy_out"]

        ax = int(ax1 + (ax2 - ax1) * ease(st["out_t"]))
        ay = int(ay1 + (ay2 - ay1) * ease(st["out_t"]))
        ex = int(ex1 + (ex2 - ex1) * ease(st["out_t"]))
        ey = int(ey1 + (ey2 - ey1) * ease(st["out_t"]))

        if st["out_t"] >= 1.0:
            st["phase"] = "swirl"
            st["swirl_timer"] = 0.0
            st["swirl_idx"] = 0

            # Play teleport sound once at swirl start
            try:
                sfx = st.get("swirl_sfx")
                if sfx:
                    audio_sys.play_sound(sfx)
                else:
                    if os.path.exists(TELEPORT_SFX):
                        _tmp = pygame.mixer.Sound(TELEPORT_SFX)
                        _tmp.set_volume(0.9)
                        _tmp.play()
            except Exception as e:
                print(f"⚠️ Teleport sound failed: {e}")

    elif phase == "swirl":
        # Keep summoner sprites off-screen while VFX plays
        ax, ay = st["ally_out"]
        ex, ey = st["enemy_out"]

        # Advance animation timer
        st["swirl_timer"] += dt
        frames = st.get("swirl_frames", [])
        if frames:
            frame_count = len(frames)
            raw_index = int(st["swirl_timer"] * SWIRL_FPS)
            idx = (raw_index % frame_count) if SWIRL_LOOP else min(frame_count - 1, raw_index)
            st["swirl_idx"] = idx
            fx = frames[idx]

            # Centers captured at enter() so the swirl plays exactly where summoners stood
            axc, ayc = st.get("ally_swirl_center", (S.WIDTH//3, S.HEIGHT//2))
            exc, eyc = st.get("enemy_swirl_center", (S.WIDTH*2//3, S.HEIGHT//2))

            # Apply tunable nudges
            ally_center  = (axc + SWIRL_ALLY_OFFSET[0],  ayc + SWIRL_ALLY_OFFSET[1])
            enemy_center = (exc + SWIRL_ENEMY_OFFSET[0], eyc + SWIRL_ENEMY_OFFSET[1])

            # Draw the same frame on both sides
            screen.blit(fx, fx.get_rect(center=ally_center))
            screen.blit(fx, fx.get_rect(center=enemy_center))

        # End the VFX after the fixed duration
        if st["swirl_timer"] >= SWIRL_TOTAL_DUR:
            st["phase"] = "done"
            st["pending_battle"] = True   # <-- tell handle() to switch scenes

    else:  # "done" — keep them off-screen
        ax, ay = st["ally_out"]
        ex, ey = st["enemy_out"]

    # Draw summoner sprites while visible phases are active
    if phase in ("intro", "slide_out"):
        if st.get("enemy_img"):
            screen.blit(st["enemy_img"], (ex, ey))
        if st.get("ally_img"):
            screen.blit(st["ally_img"], (ax, ay))

    # --- Challenge textbox (drawn over sprites, before buttons)
    if st.get("textbox_active", False):
        sw, sh = screen.get_size()
        box_h = 120
        margin_x = 36
        margin_bottom = 28
        rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)

        # Box styling (matches rolling/ui look)
        pygame.draw.rect(screen, (245, 245, 245), rect)
        pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
        inner = rect.inflate(-8, -8)
        pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)

        # Text rendering (simple wrap)
        font = _get_dh_font(28)
        text = st.get("textbox_text", "")
        words = text.split(" ")
        lines, cur = [], ""
        max_w = rect.w - 40
        for w in words:
            test = (cur + " " + w).strip()
            if not cur or font.size(test)[0] <= max_w:
                cur = test
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)

        y = rect.y + 20
        for line in lines:
            surf = font.render(line, False, (16, 16, 16))
            screen.blit(surf, (rect.x + 20, y))
            y += surf.get_height() + 6

        # Blinking prompt bottom-right
        st["blink_t"] = st.get("blink_t", 0.0) + dt
        blink_on = int(st["blink_t"] * 2) % 2 == 0
        if blink_on:
            prompt_font = _get_dh_font(20)
            prompt = "Press Enter to continue"
            psurf = prompt_font.render(prompt, False, (40, 40, 40))
            px = rect.right - psurf.get_width() - 16
            py = rect.bottom - psurf.get_height() - 12
            screen.blit(psurf, (px, py))

    # --- Buttons & popups (hidden during intro phases) ---
    if not st.get("textbox_active", False) and st.get("phase") not in ("intro", "slide_out", "swirl"):
        battle_action.draw_button(screen)
        bag_action.draw_button(screen)
        party_action.draw_button(screen)

        if bag_action.is_open():    bag_action.draw_popup(screen, gs)
        if party_action.is_open():  party_action.draw_popup(screen, gs)
        if battle_action.is_open(): battle_action.draw_popup(screen, gs)

    roll_ui.draw_roll_popup(screen, dt)
