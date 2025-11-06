# ============================================================
#  world/procgen.py
# ============================================================
import os, random, pygame
from dataclasses import dataclass, field
from pygame.math import Vector2
import settings as S

# ---- Config ----
SEG_H = 512
AHEAD_SEGMENTS = 6
BEHIND_SEGMENTS = 3
LEFT_MARGIN = 40
RIGHT_MARGIN = 40

# Road geometry (use settings if present)
ROAD_W = getattr(S, "ROAD_W", 1200)
CENTER_X = S.WORLD_W // 2
ROAD_X0 = CENTER_X - ROAD_W // 2
ROAD_X1 = CENTER_X + ROAD_W // 2

# Asset names expected in Assets/Map (optional):
PROP_FILES = {
    "tree":  "tree.png",
    "rock":  "rock.png",
    "grass": "grass.png",
}

FALLBACK_COLORS = {
    "tree":  (22, 92, 30),
    "rock":  (110, 110, 110),
    "grass": (46, 122, 60),
}

SPAWN_COUNTS = {
    "tree":  (1, 3),
    "rock":  (0, 2),
    "grass": (2, 6),
}

SCALE_RANGES = {
    "tree":  (0.8, 1.25),
    "rock":  (0.7, 1.1),
    "grass": (0.6, 1.25),
}

@dataclass
class Prop:
    kind: str
    pos: Vector2
    sprite: pygame.Surface | None = None
    fallback_size: tuple[int, int] = (28, 28)

@dataclass
class Segment:
    idx: int
    y0: int
    y1: int
    props: list[Prop] = field(default_factory=list)

class ProcGen:
    def __init__(self, rng_seed: int = 1337):
        self.rng = random.Random(rng_seed)
        self.segments: dict[int, Segment] = {}
        self.prop_images = self._load_prop_images()

    def _load_prop_images(self):
        images = {}
        base = S.ASSETS_MAP_DIR  # <-- FIX: brug string path direkte
        for kind, fname in PROP_FILES.items():
            path = os.path.join(base, fname)
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    images[kind] = img
                except Exception as e:
                    print(f"⚠️ Failed to load {kind} at {path}: {e}")
        if not images:
            print("ℹ️ procgen: no prop images found (using vector fallbacks).")
        return images

    def _random_scaled(self, kind: str):
        base = self.prop_images.get(kind)
        lo, hi = SCALE_RANGES[kind]
        scale = self.rng.uniform(lo, hi)
        if base is not None:
            w = max(1, int(base.get_width() * scale))
            h = max(1, int(base.get_height() * scale))
            return pygame.transform.smoothscale(base, (w, h))
        return None

    def _spawn_props_for_side(self, y0: int, side: str):
        props = []
        if side == "left":
            x_min = LEFT_MARGIN
            x_max = ROAD_X0 - 30
        else:
            x_min = ROAD_X1 + 30
            x_max = S.WORLD_W - RIGHT_MARGIN

        if x_max <= x_min:
            return props

        for kind in ("tree", "rock", "grass"):
            cmin, cmax = SPAWN_COUNTS[kind]
            count = self.rng.randint(cmin, cmax)
            for _ in range(count):
                x = self.rng.randint(x_min, x_max)
                y = self.rng.randint(y0 + 10, y0 + SEG_H - 10)
                sprite = self._random_scaled(kind)
                props.append(Prop(kind=kind, pos=Vector2(x, y), sprite=sprite))
        return props

    def _generate_segment(self, idx: int):
        if idx in self.segments:
            return
        y0 = idx * SEG_H
        seg = Segment(idx=idx, y0=y0, y1=y0 + SEG_H)
        seg.props.extend(self._spawn_props_for_side(y0, "left"))
        seg.props.extend(self._spawn_props_for_side(y0, "right"))
        self.segments[idx] = seg

    def update_needed(self, cam_y: float, screen_h: int):
        top_idx = int(cam_y // SEG_H)
        needed = range(top_idx - BEHIND_SEGMENTS, top_idx + AHEAD_SEGMENTS + 1)
        for idx in needed:
            self._generate_segment(idx)
        for idx in list(self.segments.keys()):
            if idx < top_idx - BEHIND_SEGMENTS - 4 or idx > top_idx + AHEAD_SEGMENTS + 8:
                del self.segments[idx]

    def draw_props(self, screen: pygame.Surface, cam_x: float, cam_y: float, screen_w: int, screen_h: int):
        y_min = cam_y - 64
        y_max = cam_y + screen_h + 64
        i0 = int(y_min // SEG_H) - 1
        i1 = int(y_max // SEG_H) + 1
        for idx in range(i0, i1 + 1):
            seg = self.segments.get(idx)
            if not seg: 
                continue
            for p in seg.props:
                sx = int(p.pos.x - cam_x)
                sy = int(p.pos.y - cam_y)
                if 0 - 64 <= sx <= screen_w + 64 and 0 - 64 <= sy <= screen_h + 64:
                    if p.sprite is not None:
                        screen.blit(p.sprite, (sx - p.sprite.get_width()//2, sy - p.sprite.get_height()//2))
                    # Don't draw fallback shapes if sprite is missing (prevents green triangles)
