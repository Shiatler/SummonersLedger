# ============================================================
#  screens/ledger.py — modal "book/ledger" popup for party slots
#  Owns: open/close state, input handling, drawing, stat ensure,
#        smooth fly-in/out animation, and page navigation.
# ============================================================

import os
import re
import zlib
import pygame
import settings as S

from systems import audio as audio_sys
from systems import save_system as saves
from rolling.roller import Roller
from combat.vessel_stats import generate_vessel_stats_from_asset
from combat.stats import build_stats                         # ✅ rebuild without rerolling abilities
from systems.asset_links import token_to_vessel              # ✅ normalize token → vessel for stat gen
from systems import xp as xp_sys 

# ---------- Internal modal state ----------
_state: dict | None = None
_popup_bg: pygame.Surface | None = None      # single-bg fallback cache
_book_sfx: pygame.mixer.Sound | None = None  # open/close sfx

# Two-page backgrounds & page-turn anim
_BG1_PATH = os.path.join("Assets", "Map", "PartyLedger1.png")
_BG2_PATH = os.path.join("Assets", "Map", "PartyLedger2.png")
_bg1: pygame.Surface | None = None
_bg2: pygame.Surface | None = None
_page_anim: dict | None = None  # {"t": float, "dir": int, "last_ms": int}

# Remember latest layout rects for hit-testing
_last_layout: dict[str, pygame.Rect | None] = {
    "book": None, "left": None, "right": None
}

# ---------- Config ----------
_POPUP_BG_PATH = os.path.join("Assets", "Map", "PartyLedger.png")  # legacy single image
_BOOK_SFX_PATH = os.path.join("Assets", "Music", "Sounds", "LedgerFlip.mp3")

_ANIM_IN_SECS  = 0.28
_ANIM_OUT_SECS = 0.22
_OVERLAY_MAX_A = 180
_SCALE_MIN     = 0.98
_SLIDE_PIXELS  = 80

_PAGE_ANIM_SECS = 0.22  # page-turn wipe duration

# ---------- Fonts ----------
_FONT_CACHE: dict[tuple, pygame.font.Font] = {}
def _get_font(size: int) -> pygame.font.Font:
    key = ("ledger", size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    try:
        path = os.path.join(S.ASSETS_FONTS_DIR, getattr(S, "DND_FONT_FILE", "DH.otf"))
        f = pygame.font.Font(path, size)
    except Exception:
        f = pygame.font.SysFont("georgia", size, bold=True)
    _FONT_CACHE[key] = f
    return f

# ---------- Easing ----------
def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

def _ease_out_cubic(p: float) -> float:
    p = _clamp01(p)
    return 1.0 - (1.0 - p) ** 3

def _ease_in_cubic(p: float) -> float:
    p = _clamp01(p)
    return p ** 3

# ---------- SFX ----------
def _play_book_sfx():
    global _book_sfx
    try:
        if os.path.exists(_BOOK_SFX_PATH):
            if _book_sfx is None:
                _book_sfx = pygame.mixer.Sound(_BOOK_SFX_PATH)
            # OLD:
            # ch = pygame.mixer.find_channel(True)
            # if ch: ch.play(_book_sfx)
            # else: _book_sfx.play()
            audio_sys.play_sound(_book_sfx)  # honors SFX master
        else:
            audio_sys.play_click(getattr(S, "AUDIO_BANK", None))
    except Exception as e:
        print(f"⚠️ Book sound failed: {e}")

# ---------- XP helpers (NEW) ----------
def _compute_xp_progress(stats: dict) -> tuple[int, int | None, int | None, float]:
    """
    Returns (level, current_xp or None, needed_xp or None, ratio 0..1)
    - Understands flat fields: xp_current/xp/xp_total and xp_needed/xp_to_next/next_xp/needed_xp
    - Also understands nested dicts: stats['xp'] = {'current':..., 'to_next':..., 'needed':...}
    - If 'needed' can't be found, falls back to xp_sys.xp_needed(level) (table) when possible.
    """
    try:
        level = max(1, int(stats.get("level", 1)))
    except Exception:
        level = 1

    cur: int | None = None
    need: int | None = None

    # ---- nested dict?
    xp_block = stats.get("xp")
    if isinstance(xp_block, dict):
        for k in ("current", "cur", "value", "progress", "xp"):
            if k in xp_block:
                try:
                    cur = int(xp_block[k]); break
                except Exception:
                    pass
        for k in ("to_next", "needed", "need", "next_xp", "xp_to_next", "xp_needed"):
            if k in xp_block:
                try:
                    need = int(xp_block[k]); break
                except Exception:
                    pass

    # ---- flat fields (override only if still missing)
    if cur is None:
        for key in ("xp_current", "xp", "xp_total"):
            if key in stats:
                try:
                    cur = int(stats[key]); break
                except Exception:
                    pass

    if need is None:
        for key in ("xp_needed", "xp_to_next", "next_xp", "needed_xp"):
            if key in stats:
                try:
                    need = int(stats[key]); break
                except Exception:
                    pass

    # ---- as a last resort, use the table for 'needed'
    if need is None:
        try:
            need = int(xp_sys.xp_needed(level))
        except Exception:
            need = None

    # ratio only when both numbers are sensible
    if isinstance(cur, int) and isinstance(need, int) and need > 0:
        ratio = max(0.0, min(1.0, cur / need))
    else:
        ratio = 0.0

    return level, cur, need, ratio



def _draw_xp_bar(surface: pygame.Surface, rect: pygame.Rect, stats: dict):
    """
    Draw 'XP: current / needed' and a thin progress bar inside `rect`.
    Intended height ~22–26px. Width can be flexible.
    """
    level, cur, need, r = _compute_xp_progress(stats)

    # Palette aligned with your UI (HP bars etc.)
    frame   = (70, 45, 30)
    border  = (140, 95, 60)
    trough  = (46, 40, 36)
    fill    = (40, 180, 90)
    text    = (230, 220, 200)

    # Container
    pygame.draw.rect(surface, frame, rect, border_radius=8)
    pygame.draw.rect(surface, border, rect, 2, border_radius=8)

    inner = rect.inflate(-10, -10)

    # Text: "XP: cur / need"
    font = pygame.font.SysFont("georgia", max(16, int(rect.h * 0.55)), bold=False)
    label = font.render(f"XP: {cur} / {need}", True, text)
    surface.blit(label, label.get_rect(midleft=(inner.x + 6, inner.centery)))

    # Level tag (left of bar)
    lvl_font = pygame.font.SysFont("georgia", max(12, int(rect.h * 0.46)), bold=True)
    lvl_lbl  = lvl_font.render(f"Lv {level}", True, text)

    # Slim bar on the right
    bar_h = max(6, int(inner.h * 0.32))
    bar_w = max(100, int(inner.w * 0.40))
    bar_x = inner.right - bar_w - 6
    bar_y = inner.centery - bar_h // 2
    bar_rect = pygame.Rect(bar_x, bar_y, bar_w, bar_h)

    # level tag sits just to the left of the bar
    surface.blit(lvl_lbl, lvl_lbl.get_rect(midright=(bar_rect.left - 8, bar_rect.centery)))

    pygame.draw.rect(surface, trough, bar_rect, border_radius=4)
    fill_w = int(bar_w * r)
    if fill_w > 0:
        pygame.draw.rect(surface, fill, (bar_x, bar_y, fill_w, bar_h), border_radius=4)



# ---------- Image helpers ----------
def _try_load(path: str | None):
    if not path:
        return None
    if os.path.exists(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"⚠️ load fail {path}: {e}")
    return None

def _get_popup_bg() -> pygame.Surface | None:
    """Legacy single background image, scaled & cached."""
    global _popup_bg
    if _popup_bg is not None:
        return _popup_bg
    img = _try_load(_POPUP_BG_PATH)
    if not img:
        return None
    iw, ih = img.get_size()
    max_w, max_h = int(S.LOGICAL_WIDTH * 0.88), int(S.LOGICAL_HEIGHT * 0.88)
    scale = min(max_w / iw, max_h / ih, 1.0)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    _popup_bg = pygame.transform.smoothscale(img, (nw, nh))
    return _popup_bg

def _get_bg_pages() -> tuple[pygame.Surface | None, pygame.Surface | None]:
    """Two-page art (if present), scaled once & cached."""
    global _bg1, _bg2
    if _bg1 is not None and _bg2 is not None:
        return _bg1, _bg2

    img1 = _try_load(_BG1_PATH)
    img2 = _try_load(_BG2_PATH)
    if not img1 or not img2:
        return None, None

    iw, ih = img1.get_size()
    max_w, max_h = int(S.LOGICAL_WIDTH * 0.88), int(S.LOGICAL_HEIGHT * 0.88)
    scale = min(max_w / iw, max_h / ih, 1.0)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    _bg1 = pygame.transform.smoothscale(img1, (nw, nh))
    _bg2 = pygame.transform.smoothscale(img2, (nw, nh))
    return _bg1, _bg2

def _fit_center(surf: pygame.Surface, rect: pygame.Rect) -> tuple[pygame.Surface, pygame.Rect]:
    iw, ih = surf.get_size()
    scale = min(rect.w / iw, rect.h / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    scaled = pygame.transform.smoothscale(surf, (nw, nh))
    dest = scaled.get_rect(center=rect.center)
    return scaled, dest

def _full_vessel_from_token_name(token_name: str | None) -> pygame.Surface | None:
    if not token_name:
        return None
    base = os.path.splitext(os.path.basename(token_name))[0]
    if base.startswith("StarterToken"):
        body = base.replace("StarterToken", "", 1)
        return _try_load(os.path.join("Assets", "Starters", f"Starter{body}.png"))
    if base.startswith("MToken"):
        body = base.replace("MToken", "", 1)
        return _try_load(os.path.join("Assets", "VesselsMale", f"MVessel{body}.png"))
    if base.startswith("FToken"):
        body = base.replace("FToken", "", 1)
        return _try_load(os.path.join("Assets", "VesselsFemale", f"FVessel{body}.png"))
    if base.startswith("RToken"):
        body = base.replace("RToken", "", 1)
        p1 = os.path.join("Assets", "RareVessels", f"RVessel{body}.png")
        img = _try_load(p1)
        if img:
            return img
        m = re.match(r"([A-Za-z]+)", body)
        if m:
            return _try_load(os.path.join("Assets", "RareVessels", f"RVessel{m.group(1)}.png"))
    for d in ("Starters", "VesselsMale", "VesselsFemale", "RareVessels"):
        img = _try_load(os.path.join("Assets", d, f"{base}.png"))
        if img:
            return img
    return None

# ---------- Public: modal control ----------
def is_open() -> bool:
    return _state is not None

def open(gs, slot_index: int):
    """Open for a specific party slot (roll stats if missing / repair if stale)."""
    _ensure_stats_for_slot(gs, slot_index)
    _set_state(slot_index, "in")
    _play_book_sfx()

def close():
    """Begin close animation."""
    global _state
    if _state is None:
        return
    if _state.get("phase") != "out":
        _state["phase"] = "out"
        _state["t"] = 0.0
        _state["last_ms"] = pygame.time.get_ticks()
        _play_book_sfx()

def _set_state(slot_index: int, phase: str):
    global _state, _page_anim
    _state = {
        "slot": int(slot_index),
        "phase": phase,
        "t": 0.0,
        "last_ms": pygame.time.get_ticks(),
    }
    _page_anim = None  # no page-turn running at open

# ---------- Class parsing / migration helpers ----------
def _class_from_vessel_asset(asset_name: str) -> str:
    """
    Extract class like 'Barbarian' from 'MVesselBarbarian[2].png' or 'StarterDruid.png'.
    Token names should already be converted to Vessel via token_to_vessel.
    """
    base = os.path.splitext(os.path.basename(asset_name or ""))[0]
    base = re.sub(r"\d+$", "", base)  # strip trailing digits
    if "Vessel" in base:
        tail = base.split("Vessel", 1)[1]
    elif base.startswith("Starter"):
        tail = base[len("Starter"):]
    else:
        tail = base
    return tail or "Fighter"

def _repair_existing_stats_if_needed(gs, slot_index: int, token_name: str):
    """
    If this slot has old/default-class stats, rebuild to current rules using saved abilities
    (no reroll) so HP/AC/prof/attack bonus match the latest spec.
    """
    try:
        st = gs.party_vessel_stats[slot_index]
        if not isinstance(st, dict):
            return

        vessel_asset = token_to_vessel(str(token_name)) or str(token_name)
        expected_cls = _class_from_vessel_asset(vessel_asset).strip()

        saved_cls = str(st.get("class_name", "")).strip()
        lvl       = int(st.get("level", 1))
        abilities = st.get("abilities") or {}

        needs_rebuild = False
        if not saved_cls or saved_cls.lower() != expected_cls.lower():
            needs_rebuild = True
        else:
            # quick stale-sign checks (old flat AC model, etc.)
            hp = int(st.get("hp", 0))
            mods = st.get("mods") or {}
            dex_mod = int(mods.get("DEX", 0))
            ac = int(st.get("ac", 0))
            if ac == 12 + dex_mod:
                needs_rebuild = True

        if needs_rebuild:
            fixed = build_stats(
                name=vessel_asset,
                class_name=expected_cls,
                level=lvl,
                abilities={k.upper(): int(v) for k, v in (abilities.items() if isinstance(abilities, dict) else [])},
                notes="Migrated to current AC/HP rules (ledger auto-repair)",
            ).to_dict()
            gs.party_vessel_stats[slot_index] = fixed
            try:
                saves.save_game(gs)
            except Exception as e:
                print(f"⚠️ Save after migration failed (slot {slot_index}): {e}")
    except Exception as e:
        print(f"⚠️ Ledger migrate slot {slot_index} failed: {e}")

# ---------- Stats helper ----------
def _ensure_stats_for_slot(gs, slot_index: int):
    if not hasattr(gs, "party_vessel_stats") or gs.party_vessel_stats is None:
        gs.party_vessel_stats = [None] * 6
    while len(gs.party_vessel_stats) < 6:
        gs.party_vessel_stats.append(None)
    if len(gs.party_vessel_stats) > 6:
        gs.party_vessel_stats = gs.party_vessel_stats[:6]

    names = getattr(gs, "party_slots_names", None)
    if not names or not (0 <= slot_index < len(names)):
        return
    token_name = names[slot_index]
    if not token_name:
        return

    # If stats exist, repair/migrate and stop.
    if gs.party_vessel_stats[slot_index]:
        _repair_existing_stats_if_needed(gs, slot_index, token_name)
        return

    # --- build seed: deterministic per token, but unique per run via run_seed
    try:
        base = zlib.crc32(str(token_name).encode("utf-8")) & 0xFFFFFFFF
    except Exception:
        base = 1337

    run_seed = getattr(gs, "run_seed", 0)
    if isinstance(run_seed, int):
        seed = (base ^ (run_seed & 0xFFFFFFFF)) & 0xFFFFFFFF
    else:
        seed = base

    # --- set up RNG
    try:
        rng = Roller(seed=seed)
    except TypeError:
        rng = Roller()
        for m in ("reseed", "seed", "set_seed"):
            fn = getattr(rng, m, None)
            if callable(fn):
                try:
                    fn(seed)
                    break
                except Exception:
                    pass

    # --- roll + save (✅ convert Token -> Vessel BEFORE stat gen)
    vessel_asset = token_to_vessel(str(token_name)) or str(token_name)
    stats = generate_vessel_stats_from_asset(
        asset_name=vessel_asset,
        level=1,
        rng=rng,
        notes="Rolled on add to party",
    )
    gs.party_vessel_stats[slot_index] = stats
    try:
        saves.save_game(gs)
    except Exception as e:
        print(f"⚠️ Save after rolling stats failed (slot {slot_index}): {e}")

# ---------- Slot navigation ----------
def _slot_count(gs) -> int:
    names = getattr(gs, "party_slots_names", None)
    if isinstance(names, list) and names:
        return len(names)
    return 6  # default grid size

def _change_slot(gs, delta: int):
    global _state, _page_anim
    if _state is None:
        return
    n = max(1, _slot_count(gs))
    cur = int(_state.get("slot", 0))
    new_idx = (cur + delta) % n

    _state["slot"] = new_idx
    _state["phase"] = "open"
    _state["t"] = 1.0

    _ensure_stats_for_slot(gs, new_idx)
    _play_book_sfx()

    # kick a page-turn animation (dir>0 = right/next, dir<0 = left/prev)
    _page_anim = {
        "t": 0.0,
        "dir": 1 if delta > 0 else -1,
        "last_ms": pygame.time.get_ticks(),
    }

# ---------- Input ----------
def handle_event(e, gs) -> bool:
    """Modal: consume inputs. Click left/right page to navigate; elsewhere closes."""
    if not is_open():
        return False

    # Keyboard
    if e.type == pygame.KEYDOWN:
        if e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            close()
            return True
        if e.key == pygame.K_LEFT:
            _change_slot(gs, -1)
            return True
        if e.key == pygame.K_RIGHT:
            _change_slot(gs, +1)
            return True

    # Mouse
    if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
        pos = e.pos
        left = _last_layout.get("left")
        right = _last_layout.get("right")
        book = _last_layout.get("book")

        # Page click → navigate; click outside book → close; click inside gutter → ignore
        if left and left.collidepoint(pos):
            _change_slot(gs, -1)
            return True
        if right and right.collidepoint(pos):
            _change_slot(gs, +1)
            return True
        if book and not book.collidepoint(pos):
            close()
            return True
        return True

    # Eat all inputs while modal
    return True

# ---------- Animation step ----------
def _anim_update():
    global _state
    if _state is None:
        return 0.0, 0.0, "closed"

    now = pygame.time.get_ticks()
    dt = max(0, (now - _state.get("last_ms", now)) / 1000.0)
    _state["last_ms"] = now

    phase = _state.get("phase", "open")
    t = _state.get("t", 0.0)

    if phase == "in":
        dur = max(0.001, _ANIM_IN_SECS)
        t = min(1.0, t + dt / dur)
        _state["t"] = t
        if t >= 1.0:
            _state["phase"] = "open"
            _state["t"] = 1.0
    elif phase == "out":
        dur = max(0.001, _ANIM_OUT_SECS)
        t = min(1.0, t + dt / dur)
        _state["t"] = t
        if t >= 1.0:
            _state = None
            return 0.0, 0.0, "closed"

    if _state is None:
        return 0.0, 0.0, "closed"

    phase = _state["phase"]
    t = _state["t"]
    if phase == "in":
        return _ease_out_cubic(t), 0.0, "in"
    if phase == "open":
        return 1.0, 0.0, "open"
    if phase == "out":
        return 1.0 - _ease_in_cubic(t), t, "out"
    return 1.0, 0.0, "open"

# ---------- Draw ----------
def draw(screen: pygame.Surface, gs):
    global _page_anim
    if not is_open():
        return

    prog, _, phase = _anim_update()
    if phase == "closed":
        return

    # Dim overlay
    overlay_alpha = int(_OVERLAY_MAX_A * prog)
    overlay = pygame.Surface((S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, overlay_alpha))
    screen.blit(overlay, (0, 0))

    # ---- Base+Anim Pages: always end on PartyLedger.png ----
    base_bg = _get_popup_bg()           # PartyLedger.png (scaled & cached)
    bg1, bg2 = _get_bg_pages()          # PartyLedger1/2 (optional anim frames)

    # always define before draw_pages
    content_origin = (0, 0)
    book_rect = None

    # If we don't even have the base book image, fall back to simple box
    if base_bg is None:
        pw, ph = int(S.LOGICAL_WIDTH * 0.55), int(S.LOGICAL_HEIGHT * 0.55)
        px = (S.LOGICAL_WIDTH - pw) // 2
        py_target = (S.LOGICAL_HEIGHT - ph) // 2
        py = py_target + int((1.0 - prog) * _SLIDE_PIXELS)
        pygame.draw.rect(screen, (20, 20, 20), (px, py, pw, ph), border_radius=14)
        pygame.draw.rect(screen, (220, 200, 130), (px, py, pw, ph), 4, border_radius=14)
        book_rect = pygame.Rect(px, py, pw, ph)
        _last_layout["book"]  = book_rect
        _last_layout["left"]  = pygame.Rect(px, py, pw // 2, ph)
        _last_layout["right"] = pygame.Rect(px + pw // 2, py, pw // 2, ph)
        # no content layout w/o base metrics
        return

    # Position & scale (same fly-in/out behavior as before) based on base image
    bw, bh = base_bg.get_size()
    bx = (S.LOGICAL_WIDTH - bw) // 2
    by_target = (S.LOGICAL_HEIGHT - bh) // 2
    slide_y = int((1.0 - prog) * _SLIDE_PIXELS)
    scale = _SCALE_MIN + (1.0 - _SCALE_MIN) * prog

    if abs(scale - 1.0) < 0.0001:
        sbw, sbh = bw, bh
        sbx = bx
        sby = by_target + slide_y
        screen.blit(base_bg, (sbx, sby))
    else:
        sbw, sbh = max(1, int(bw * scale)), max(1, int(bh * scale))
        sb_base = pygame.transform.smoothscale(base_bg, (sbw, sbh))
        sbx = (S.LOGICAL_WIDTH - sbw) // 2
        sby = (S.LOGICAL_HEIGHT - sbh) // 2 + slide_y
        screen.blit(sb_base, (sbx, sby))

    book_rect = pygame.Rect(sbx, sby, sbw, sbh)
    content_origin = (sbx, sby)

    # If we have anim pages AND a page-turn is active, draw them as a 2-step wipe over the base
    if bg1 and bg2 and _page_anim is not None:
        # scale anim frames to the same size as base for perfect alignment
        sbg1 = pygame.transform.smoothscale(bg1, (sbw, sbh)) if (bg1.get_width(), bg1.get_height()) != (sbw, sbh) else bg1
        sbg2 = pygame.transform.smoothscale(bg2, (sbw, sbh)) if (bg2.get_width(), bg2.get_height()) != (sbw, sbh) else bg2

        now = pygame.time.get_ticks()
        dt = max(0, (now - _page_anim.get("last_ms", now)) / 1000.0)
        _page_anim["last_ms"] = now
        _page_anim["t"] = min(1.0, _page_anim["t"] + dt / max(0.001, _PAGE_ANIM_SECS))

        p = _ease_out_cubic(_page_anim["t"])
        dir_ = 1 if _page_anim.get("dir", 1) >= 0 else -1

        # two-step: first half reveal bg1, second half reveal bg2; base remains beneath
        if p <= 0.5:
            frac = p / 0.5
            w = int(sbw * frac)
            if w > 0:
                if dir_ > 0:
                    src = pygame.Rect(sbw - w, 0, w, sbh)
                    dst = (sbx + sbw - w, sby)
                else:
                    src = pygame.Rect(0, 0, w, sbh)
                    dst = (sbx, sby)
                screen.blit(sbg1, dst, area=src)
        else:
            frac = (p - 0.5) / 0.5
            w = int(sbw * frac)
            if w > 0:
                if dir_ > 0:
                    src = pygame.Rect(sbw - w, 0, w, sbh)
                    dst = (sbx + sbw - w, sby)
                else:
                    src = pygame.Rect(0, 0, w, sbh)
                    dst = (sbx, sby)
                screen.blit(sbg2, dst, area=src)

        if _page_anim["t"] >= 1.0:
            _page_anim = None  # done; leaves the base page visible again

    # If anim is active but no bg1/bg2 exist, just advance timer (hide content while anim runs)
    elif _page_anim is not None:
        now = pygame.time.get_ticks()
        dt = max(0, (now - _page_anim.get("last_ms", now)) / 1000.0)
        _page_anim["last_ms"] = now
        _page_anim["t"] = min(1.0, _page_anim["t"] + dt / max(0.001, _PAGE_ANIM_SECS))
        if _page_anim["t"] >= 1.0:
            _page_anim = None  # done; base is already drawn

    # Update hit regions & draw content
    _last_layout["book"]  = book_rect
    _last_layout["left"]  = pygame.Rect(book_rect.x, book_rect.y, book_rect.w // 2, book_rect.h)
    _last_layout["right"] = pygame.Rect(book_rect.x + book_rect.w // 2, book_rect.y, book_rect.w // 2, book_rect.h)

    # ✅ Hide text/art while a page-turn is playing
    if _page_anim is None:
        draw_pages(screen, gs, content_origin, book_rect.size)

# ---------- Content (art + text) ----------
def draw_pages(screen: pygame.Surface, gs, origin_xy: tuple[int, int], size_wh: tuple[int, int]):
    bx, by = origin_xy
    bw, bh = size_wh

    slot = _state.get("slot", 0) if _state else 0

    token_name = ""
    if getattr(gs, "party_slots_names", None) and 0 <= slot < len(gs.party_slots_names):
        token_name = gs.party_slots_names[slot] or ""

    vessel = _full_vessel_from_token_name(token_name)

    # Left and Right page rects (tweak to fit your texture)
    left_page  = pygame.Rect(
        bx + int(bw * 0.08),
        by + int(bh * 0.15),
        int(bw * 0.38),
        int(bh * 0.70),
    )
    right_page = pygame.Rect(
        bx + int(bw * 0.54),
        by + int(bh * 0.15),
        int(bw * 0.38),
        int(bh * 0.70),
    )
    # Manual offsets used earlier
    left_page.x  += 130
    left_page.y  += -50
    right_page.x += 40
    right_page.y += 90

    # Vessel art on left page
    if vessel:
        page_pad = 12
        art_rect = left_page.inflate(-page_pad * 2, -page_pad * 2)
        scaled, _ = _fit_center(vessel, art_rect)
        shrink = 0.65
        nw, nh = int(scaled.get_width() * shrink), int(scaled.get_height() * shrink)
        scaled = pygame.transform.smoothscale(scaled, (nw, nh))
        dest = scaled.get_rect(center=left_page.center)
        screen.blit(scaled, dest.topleft)

    # Text on right page
    light = (36, 34, 30)
    dark  = (0, 0, 0)
    # accent colors
    CLR_LEVEL = (40, 180, 90)    # green
    CLR_HP    = (200, 60, 60)    # red
    CLR_AC    = (150, 150, 150)  # steel/armor grey
    CLR_XP    = (70, 140, 220)   # blue

    title_font = _get_font(max(26, int(bw * 0.015)))
    body_font  = _get_font(max(18, int(bw * 0.008)))

    base = os.path.splitext(os.path.basename(token_name))[0]
    for p in ("StarterToken", "MToken", "FToken", "RToken"):
        if base.startswith(p):
            base = base[len(p):]
            break
    clean_name = re.sub(r"\d+$", "", base) or "Unknown Vessel"

    HEADER_TOP_PAD   = 10
    CONTENT_TOP_GAP  = 18
    LINE_GAP         = 8

    header = title_font.render("Vessel Details", True, light)
    header_shadow = title_font.render("Vessel Details", True, dark)
    header_rect = header.get_rect(topleft=(right_page.x - 50, right_page.y + HEADER_TOP_PAD))
    screen.blit(header_shadow, (header_rect.x + 1, header_rect.y + 1))
    screen.blit(header, header_rect)

    sep_y = header_rect.bottom + 6
    cursor_x = right_page.x - 50
    cursor_y = sep_y + CONTENT_TOP_GAP

    def _blit_line(text: str, color: tuple[int,int,int] | None = None):
        nonlocal cursor_y
        col = color or light
        surf   = body_font.render(text, True, col)
        shadow = body_font.render(text, True, dark)
        screen.blit(shadow, (cursor_x + 1, cursor_y + 1))
        screen.blit(surf,   (cursor_x,     cursor_y))
        cursor_y += surf.get_height() + LINE_GAP

    _blit_line(f"Name: {clean_name}")  # unchanged color

    if not getattr(gs, "party_vessel_stats", None):
        gs.party_vessel_stats = [None] * 6
    st = None
    if 0 <= slot < len(gs.party_vessel_stats):
        st = gs.party_vessel_stats[slot]

    if isinstance(st, dict):
        lvl = st.get("level", 1)
        ac  = st.get("ac", 12)
        hp  = st.get("hp", 10)
        abi = st.get("abilities") or {}
        abi = {str(k).upper(): v for k, v in (abi.items() if isinstance(abi, dict) else [])}

        # colored stat lines
        _blit_line(f"Level: {lvl}", CLR_LEVEL)
        _blit_line(f"AC: {ac}",      CLR_AC)
        _blit_line(f"HP: {hp}",      CLR_HP)

        # XP as plain text (no bar) in blue (tolerant to missing fields)
        level, cur_xp, need_xp, _ = _compute_xp_progress(st)
        if cur_xp is not None and need_xp is not None:
            _blit_line(f"XP: {cur_xp} / {need_xp}", CLR_XP)
        elif cur_xp is not None:
            _blit_line(f"XP: {cur_xp}", CLR_XP)  # graceful fallback
        else:
            _blit_line("XP: —", CLR_XP)

        # <-- These lines went missing; add them back:
        if abi:
            _blit_line("Abilities:")
            _blit_line(f"  STR {abi.get('STR','?')}   DEX {abi.get('DEX','?')}   CON {abi.get('CON','?')}")
            _blit_line(f"  INT {abi.get('INT','?')}   WIS {abi.get('WIS','?')}   CHA {abi.get('CHA','?')}")
        else:
            _blit_line("(Abilities not recorded.)")
    else:
        _blit_line("(No stats stored yet.)")


