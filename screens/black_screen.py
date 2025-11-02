# =============================================================
# screens/black_screen.py — Unlimited starters (absolute paths)
# - Picks a random Starter<Class><N>.png ON FIRST REVEAL only
# - Uses absolute path to .../Assets/Starters so cwd doesn't matter
# - Case-insensitive extension (.png / .PNG)
# - Maps to StarterToken<Class><N>.(png|PNG) in the same folder
# =============================================================
import os, random, re
import pygame
import settings as S
from systems import audio as audio_sys

# ---------- Absolute paths ----------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))          # .../screens
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, ".."))  # .../SummonersLedger
_STARTERS_DIR = os.path.join(_PROJECT_ROOT, "Assets", "Starters")

# ---------- FS helpers ----------
def _safe_load(path):
    try:
        if os.path.exists(path):
            return pygame.image.load(path).convert_alpha()
        else:
            print(f"ℹ️ Missing image: {path}")
    except Exception as e:
        print(f"⚠️ Failed to load '{path}': {e}")
    return None

def _scale_to_h(img, target_h):
    if img is None: return None
    r = target_h / max(1, img.get_height())
    return pygame.transform.smoothscale(img, (max(1, int(img.get_width()*r)), max(1, int(img.get_height()*r))))

def _rescale(img, f=0.96):
    if img is None: return None
    return pygame.transform.smoothscale(img, (max(1, int(img.get_width()*f)), max(1, int(img.get_height()*f))))

# ---------- Starter scanning ----------
_DIGIT_RX = re.compile(r"(\d+)$")

def _scan_starters(prefix: str) -> list[str]:
    """
    Return absolute file paths for all Starter<Class><N>.(png|PNG) in _STARTERS_DIR,
    where N is a positive integer (no upper bound).
    """
    out = []
    if not os.path.isdir(_STARTERS_DIR):
        print(f"[starter] starters dir missing: {_STARTERS_DIR}")
        return out

    pref_low = prefix.lower()
    for fname in os.listdir(_STARTERS_DIR):
        fl = fname.lower()
        if not fl.endswith(".png"):  # .PNG handled via lower()
            continue
        if not fl.startswith(pref_low):
            continue
        name_no_ext = os.path.splitext(fname)[0]
        # must end with digits
        if not _DIGIT_RX.search(name_no_ext):
            continue
        out.append(os.path.join(_STARTERS_DIR, fname))

    print(f"[starter] {_STARTERS_DIR} | {prefix}: {len(out)} candidate(s)")
    return out

def _pick_random_starter(prefix: str):
    """
    Choose a random Starter<Class><N>.png from the Starters dir.
    Returns (surface, basename_without_ext, fullpath) or (None, None, None).
    """
    try:
        candidates = _scan_starters(prefix)
        if not candidates:
            return None, None, None
        choice = random.choice(candidates)
        surf = pygame.image.load(choice).convert_alpha()
        base = os.path.splitext(os.path.basename(choice))[0]  # e.g. 'StarterBarbarian12'
        print(f"[starter] chosen -> {base}")
        return surf, base, choice
    except Exception as e:
        print(f"⚠️ Starter pick failed for {prefix}: {e}")
        return None, None, None

def _find_token_path(starter_basename: str) -> str | None:
    """
    Given 'StarterBarbarian12', look for 'StarterTokenBarbarian12.(png|PNG)' in the same folder.
    """
    token_base = starter_basename.replace("Starter", "StarterToken", 1)
    for ext in ("png", "PNG"):
        p = os.path.join(_STARTERS_DIR, f"{token_base}.{ext}")
        if os.path.exists(p):
            return p
    return None

# ---------- Visual helpers ----------
def _draw_grass(surface, grass_img):
    if not grass_img: return
    g_y = S.HEIGHT - grass_img.get_height() + 80
    surface.blit(grass_img, (0, g_y))

def _draw_glow_ellipse(surface, center_rect, color):
    if center_rect.w == 0 or center_rect.h == 0: return
    glow_w = int(center_rect.w * 0.95); glow_h = int(center_rect.h * 0.28)
    glow = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (*color, 46), glow.get_rect())
    inner = glow.get_rect().inflate(int(-glow_w*0.22), int(-glow_h*0.30))
    pygame.draw.ellipse(glow, (*color, 108), inner)
    dst = glow.get_rect(center=(center_rect.centerx, center_rect.bottom - int(center_rect.h * 0.06)))
    surface.blit(glow, dst.topleft)

def _draw_spotlight_with_starter(surface, book_rect, color, starter_img):
    if not starter_img or book_rect.w == 0:
        return None, None
    diameter = int(book_rect.h * 1.02)
    radius   = max(1, diameter // 2)
    cx = book_rect.centerx
    cy = book_rect.centery - int(book_rect.h * 0.12)
    cy = max(radius + 8, min(S.HEIGHT - radius - 8, cy))
    cx = max(radius + 8, min(S.WIDTH  - radius - 8, cx))
    circle_rect = pygame.Rect(cx - radius, cy - radius, diameter, diameter)

    spot = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    pygame.draw.circle(spot, (*color,  56), (radius, radius), radius)
    pygame.draw.circle(spot, (*color, 108), (radius, radius), int(radius * 0.76))
    pygame.draw.circle(spot, (*color, 150), (radius, radius), int(radius * 0.54))
    surface.blit(spot, circle_rect.topleft)

    max_w = int(diameter * 0.84); max_h = int(diameter * 0.84)
    sw, sh = starter_img.get_width(), starter_img.get_height()
    s = min(max_w / max(1, sw), max_h / max(1, sh))
    starter_scaled = pygame.transform.smoothscale(starter_img, (max(1, int(sw*s)), max(1, int(sh*s))))
    starter_rect = starter_scaled.get_rect(center=(cx, cy))
    surface.blit(starter_scaled, starter_rect)

    ring = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    pygame.draw.circle(ring, (*color, 185), (radius, radius), radius, width=3)
    pygame.draw.circle(ring, (*color, 120), (radius, radius), int(radius * 0.88), width=2)
    surface.blit(ring, circle_rect.topleft)
    return starter_rect, circle_rect

# ---------- Internal helpers ----------
_PREFIX_MAP = {
    "barbarian": "StarterBarbarian",
    "druid":     "StarterDruid",
    "rogue":     "StarterRogue",
}

def _ensure_revealed_starter_for_class(gs, class_key: str):
    """
    Ensure class_key has a chosen starter stored.
    Only picks once; subsequent calls do nothing (so it 'remembers').
    """
    data = gs._class_select.get(class_key, {})
    if data.get("starter") is not None and data.get("starter_name"):
        return  # already chosen for this class

    prefix = _PREFIX_MAP.get(class_key)
    if not prefix:
        return

    starter_img, starter_name, _full = _pick_random_starter(prefix)
    data["starter"] = starter_img
    data["starter_name"] = starter_name
    gs._class_select[class_key] = data  # write back in case dict view is a copy
    if not starter_img:
        print(f"[starter] No candidates found for {prefix} in {_STARTERS_DIR}")

# ---------- Screen lifecycle ----------
def enter(gs, **_):
    if hasattr(gs, "_class_select"):
        return

    barb  = _safe_load(os.path.join(_PROJECT_ROOT, "Assets", "Map", "BarbarianL.png"))
    dru   = _safe_load(os.path.join(_PROJECT_ROOT, "Assets", "Map", "DruidL.png"))
    rog   = _safe_load(os.path.join(_PROJECT_ROOT, "Assets", "Map", "RogueL.png"))
    grass = _safe_load(os.path.join(_PROJECT_ROOT, "Assets", "Map", "Grass_UI.png"))

    target_h = max(1, int(S.HEIGHT * 0.48))
    barb = _rescale(_scale_to_h(barb, target_h))
    dru  = _rescale(_scale_to_h(dru,  target_h))
    rog  = _rescale(_scale_to_h(rog,  target_h))

    if grass:
        ratio = S.WIDTH / max(1, grass.get_width())
        gh = max(1, int(grass.get_height() * ratio * 0.35))
        grass = pygame.transform.smoothscale(grass, (S.WIDTH, gh))

    cx = S.WIDTH // 2
    cy = int(S.HEIGHT * 0.74)
    widths = [img.get_width() for img in (barb, dru, rog) if img]
    gap = int(max(widths) * 1.05) if widths else 420

    barb_rect = barb.get_rect(center=(cx, cy)) if barb else pygame.Rect(cx, cy, 0, 0)
    dru_rect  = dru.get_rect(center=(cx - gap, cy - 28)) if dru else pygame.Rect(cx - gap, cy - 28, 0, 0)
    rog_rect  = rog.get_rect(center=(cx + gap, cy - 28)) if rog else pygame.Rect(cx + gap, cy - 28, 0, 0)

    gs._class_select = {
        "barbarian": {"img": barb, "rect": barb_rect, "color": (220, 20, 20), "starter": None, "starter_name": None},
        "druid":     {"img": dru,  "rect": dru_rect,  "color": (30, 180, 70), "starter": None, "starter_name": None},
        "rogue":     {"img": rog,  "rect": rog_rect,  "color": (40, 120,255), "starter": None, "starter_name": None},
        "order": ["druid", "barbarian", "rogue"],
        "grass": grass,
        "starters_dir": _STARTERS_DIR,  # absolute
    }

    gs.selected_class = None
    gs.revealed_class = None
    gs.starter_clicked = None
    gs._starter_last_rect = None
    gs._starter_circle_rect = None

def draw(screen, gs, **_):
    screen.fill((0, 0, 0))
    _draw_grass(screen, gs._class_select["grass"])

    hovered_key = None
    mx, my = pygame.mouse.get_pos()
    for key in gs._class_select["order"]:
        data = gs._class_select[key]
        if data["rect"].collidepoint(mx, my):
            hovered_key = key

    for key in gs._class_select["order"]:
        data = gs._class_select[key]
        img, rect, color = data["img"], data["rect"], data["color"]
        if img:
            if hovered_key == key:
                _draw_glow_ellipse(screen, rect, color)
            screen.blit(img, rect)

    gs._starter_last_rect = None
    gs._starter_circle_rect = None
    if getattr(gs, "revealed_class", None):
        data = gs._class_select[gs.revealed_class]
        r1, r2 = _draw_spotlight_with_starter(screen, data["rect"], data["color"], data["starter"])
        gs._starter_last_rect = r1
        gs._starter_circle_rect = r2

    if gs._starter_last_rect and gs._starter_last_rect.collidepoint(mx, my) and gs._starter_circle_rect:
        ring = pygame.Surface((gs._starter_circle_rect.w, gs._starter_circle_rect.h), pygame.SRCALPHA)
        pygame.draw.circle(
            ring, (255, 255, 255, 88),
            (gs._starter_circle_rect.w // 2, gs._starter_circle_rect.h // 2),
            gs._starter_circle_rect.w // 2, width=3
        )
        screen.blit(ring, gs._starter_circle_rect.topleft)

def handle(events, gs, saves=None, audio_bank=None, **_):
    for event in events:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            audio_sys.play_click(audio_bank)
            return S.MODE_MENU

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Accept spotlighted starter -> add token + continue
            if gs._starter_last_rect and gs._starter_last_rect.collidepoint(event.pos):
                audio_sys.play_click(audio_bank)
                gs.starter_clicked = gs.revealed_class
                gs.intro_class = gs.revealed_class
                try:
                    cls_data = gs._class_select.get(gs.revealed_class, {})
                    starter_name = cls_data.get("starter_name")  # e.g. StarterRogue5 (NO 'Token', NO extension)
                    if starter_name:
                        token_path = _find_token_path(starter_name)  # maps StarterX -> StarterTokenX.(png|PNG)
                        if token_path and os.path.exists(token_path):
                            token_surf = pygame.image.load(token_path).convert_alpha()
                            if not getattr(gs, "party_slots", None):
                                gs.party_slots = [None] * 6
                            if not getattr(gs, "party_slots_names", None):
                                gs.party_slots_names = [None] * 6
                            if not getattr(gs, "party_vessel_stats", None):
                                gs.party_vessel_stats = [None] * 6

                            token_base = os.path.basename(token_path)  # e.g. StarterTokenRogue5.png

                            # If already in party, don't touch stats (preserves HP/damage/faint)
                            if token_base in (gs.party_slots_names or []):
                                print(f"ℹ️ {token_base} already in party; skipping add.")
                            else:
                                # Place into first empty slot
                                placed = False
                                for i in range(len(gs.party_slots)):
                                    if gs.party_slots[i] is None:
                                        gs.party_slots[i] = token_surf
                                        gs.party_slots_names[i] = token_base
                                        # Initialize stats ONCE with the correct ASSET NAME (starter_name)
                                        if gs.party_vessel_stats[i] is None:
                                            from combat.vessel_stats import generate_vessel_stats_from_asset
                                            # Use 'Starter<Class><N>' — NOT the token filename.
                                            gs.party_vessel_stats[i] = generate_vessel_stats_from_asset(starter_name)
                                        placed = True
                                        print(f"🎉 Added {token_base} to party slot {i+1}")
                                        break
                                if not placed:
                                    print("ℹ️ No empty party slots available.")

                            if saves:
                                try:
                                    saves.save_game(gs)
                                except Exception as se:
                                    print(f"⚠️ Save after starter pick failed: {se}")
                        else:
                            print(f"ℹ️ Token file not found for '{starter_name}' in {_STARTERS_DIR}")
                    else:
                        print("ℹ️ No starter_name available to map a token.")
                except Exception as e:
                    print(f"⚠️ Failed to add starter token to party: {e}")
                return "INTRO_VIDEO"

            # Reveal: pick ONCE per class (remember thereafter)
            for key, data in gs._class_select.items():
                if key in ("order", "grass", "starters_dir"):
                    continue
                if data["rect"].collidepoint(event.pos):
                    audio_sys.play_click(audio_bank)
                    gs.selected_class = key
                    gs.revealed_class = key
                    # Only pick if we haven't already chosen for this class:
                    if data.get("starter") is None or not data.get("starter_name"):
                        _ensure_revealed_starter_for_class(gs, key)
                    print(f"✅ Selected class: {gs.selected_class} (starter revealed)")
                    break
    return None
