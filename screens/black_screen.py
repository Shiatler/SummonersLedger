# =============================================================
# screens/black_screen.py
# =============================================================
import pygame, os, glob, random
import settings as S
from systems import ui
from systems import party_ui
from systems import audio as audio_sys


def enter(gs, **_):
    # one-time cache of art & layout
    if hasattr(gs, "_class_select"):
        return

    def safe_load(path):
        try:
            if os.path.exists(path):
                return pygame.image.load(path).convert_alpha()
            else:
                print(f"ℹ️ Missing image: {path}")
        except Exception as e:
            print(f"⚠️ Failed to load '{path}': {e}")
        return None

    barb  = safe_load(os.path.join("Assets", "Map", "BarbarianL.png"))
    dru   = safe_load(os.path.join("Assets", "Map", "DruidL.png"))
    rog   = safe_load(os.path.join("Assets", "Map", "RogueL.png"))
    grass = safe_load(os.path.join("Assets", "Map", "Grass_UI.png"))

    target_h = max(1, int(S.HEIGHT * 0.48))
    def scale_to_h(img):
        if img is None: return None
        r = target_h / max(1, img.get_height())
        w = max(1, int(img.get_width() * r))
        h = max(1, int(img.get_height() * r))
        return pygame.transform.smoothscale(img, (w, h))

    def rescale(img, f=0.96):
        if img is None: return None
        w = max(1, int(img.get_width() * f))
        h = max(1, int(img.get_height() * f))
        return pygame.transform.smoothscale(img, (w, h))

    barb = rescale(scale_to_h(barb))
    dru  = rescale(scale_to_h(dru))
    rog  = rescale(scale_to_h(rog))

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

    starters_dir = os.path.join("Assets", "Starters")
    def pick_random_starter(prefix):
        try:
            paths = sorted(glob.glob(os.path.join(starters_dir, f"{prefix}*.png")))
            if not paths:
                print(f"ℹ️ No starters found for {prefix}")
                return None, None
            choice = random.choice(paths)
            surf = pygame.image.load(choice).convert_alpha()
            base = os.path.splitext(os.path.basename(choice))[0]  # e.g., StarterBarbarian2
            return surf, base
        except Exception as e:
            print(f"⚠️ Starter load failed for {prefix}: {e}")
            return None, None

    barb_starter_img, barb_starter_name = pick_random_starter("StarterBarbarian")
    dru_starter_img,  dru_starter_name  = pick_random_starter("StarterDruid")
    rog_starter_img,  rog_starter_name  = pick_random_starter("StarterRogue")

    gs._class_select = {
        "barbarian": {"img": barb, "rect": barb_rect, "color": (220, 20, 20), "starter": barb_starter_img, "starter_name": barb_starter_name},
        "druid":     {"img": dru,  "rect": dru_rect,  "color": (30, 180, 70), "starter": dru_starter_img,  "starter_name": dru_starter_name},
        "rogue":     {"img": rog,  "rect": rog_rect,  "color": (40, 120,255), "starter": rog_starter_img,  "starter_name": rog_starter_name},
        "order": ["druid", "barbarian", "rogue"],
        "grass": grass,
    }
    gs.selected_class = None
    gs.revealed_class = None
    gs.starter_clicked = None
    gs._starter_last_rect = None
    gs._starter_circle_rect = None

def _draw_grass(surface, grass_img):
    if not grass_img: return
    import settings as S
    g_y = S.HEIGHT - grass_img.get_height() + 80
    surface.blit(grass_img, (0, g_y))

def _draw_glow_ellipse(surface, center_rect, color):
    if center_rect.w == 0 or center_rect.h == 0: return
    glow_w = int(center_rect.w * 0.95)
    glow_h = int(center_rect.h * 0.28)
    glow = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (*color, 46), glow.get_rect())
    inner = glow.get_rect().inflate(int(-glow_w*0.22), int(-glow_h*0.30))
    pygame.draw.ellipse(glow, (*color, 108), inner)
    dst = glow.get_rect(center=(center_rect.centerx, center_rect.bottom - int(center_rect.h * 0.06)))
    surface.blit(glow, dst.topleft)

def _draw_spotlight_with_starter(surface, book_rect, color, starter_img):
    if not starter_img or book_rect.w == 0:
        return None, None
    import settings as S
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

    max_w = int(diameter * 0.84)
    max_h = int(diameter * 0.84)
    sw, sh = starter_img.get_width(), starter_img.get_height()
    s = min(max_w / max(1, sw), max_h / max(1, sh))
    starter_scaled = pygame.transform.smoothscale(starter_img, (max(1, int(sw * s)), max(1, int(sh * s))))
    starter_rect = starter_scaled.get_rect(center=(cx, cy))
    surface.blit(starter_scaled, starter_rect)

    ring = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    pygame.draw.circle(ring, (*color, 185), (radius, radius), radius, width=3)
    pygame.draw.circle(ring, (*color, 120), (radius, radius), int(radius * 0.88), width=2)
    surface.blit(ring, circle_rect.topleft)

    return starter_rect, circle_rect

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
            # Click on the revealed STARTER image -> add token + go to intro video
            if gs._starter_last_rect and gs._starter_last_rect.collidepoint(event.pos):
                audio_sys.play_click(audio_bank)
                gs.starter_clicked = gs.revealed_class
                gs.intro_class = gs.revealed_class

                # add the starter's token to first empty party slot & save
                try:
                    cls_data = gs._class_select.get(gs.revealed_class, {})
                    starter_name = cls_data.get("starter_name")  # e.g. StarterBarbarian2
                    if starter_name:
                        token_basename = starter_name.replace("Starter", "StarterToken") + ".png"
                        token_path = os.path.join("Assets", "Starters", token_basename)
                        if os.path.exists(token_path):
                            token_surf = pygame.image.load(token_path).convert_alpha()

                            if not getattr(gs, "party_slots", None):
                                gs.party_slots = [None] * 6
                            if not getattr(gs, "party_slots_names", None):
                                gs.party_slots_names = [None] * 6

                            if token_basename in gs.party_slots_names:
                                print(f"ℹ️ {token_basename} already in party; skipping add.")
                            else:
                                placed = False
                                for i in range(len(gs.party_slots)):
                                    if gs.party_slots[i] is None:
                                        gs.party_slots[i] = token_surf
                                        gs.party_slots_names[i] = token_basename
                                        placed = True
                                        print(f"🎉 Added {token_basename} to party slot {i+1}")
                                        break
                                if not placed:
                                    print("ℹ️ No empty party slots available.")

                            if saves:
                                try:
                                    saves.save_game(gs)
                                except Exception as se:
                                    print(f"⚠️ Save after starter pick failed: {se}")
                        else:
                            print(f"ℹ️ Token file not found: {token_path}")
                    else:
                        print("ℹ️ No starter_name available to map a token.")
                except Exception as e:
                    print(f"⚠️ Failed to add starter token to party: {e}")

                return "INTRO_VIDEO"

            # Otherwise, click a book (“ledger”) to reveal its starter
            for key, data in gs._class_select.items():
                if key in ("order", "grass"):
                    continue
                if data["rect"].collidepoint(event.pos):
                    audio_sys.play_click(audio_bank)
                    gs.selected_class = key
                    gs.revealed_class = key
                    print(f"✅ Selected class: {gs.selected_class} (starter revealed)")
                    break

    return None
