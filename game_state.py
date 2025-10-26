# ===================== GameState =============================
from dataclasses import dataclass, field
from pygame.math import Vector2

@dataclass
class GameState:
    # player
    player_pos: Vector2
    player_speed: float
    start_x: float

    # chosen character (saved/loaded)
    player_gender: str = "male"
    player_image: object = None
    player_half: Vector2 = field(default_factory=lambda: Vector2(0, 0))

    # progress
    distance_travelled: float = 0.0
    next_event_at: float = 120.0

    # encounter popup
    in_encounter: bool = False
    encounter_timer: float = 0.0
    encounter_name: str = ""
    encounter_sprite: object = None  # pygame.Surface or None
    encounter_stats: dict | None = None  # full stat block for active encounter

    # world spawns
    rivals_on_map: list = field(default_factory=list)
    vessels_on_map: list = field(default_factory=list)

    # audio state
    is_walking: bool = False
    overworld_music_started: bool = False

    # party / HUD
    player_token: object | None = None           # small face portrait (pygame.Surface)
    party_slots: list = field(default_factory=lambda: [None] * 6)  # 6 slots for vessel tokens
