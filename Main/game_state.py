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
    merchants_on_map: list = field(default_factory=list)
    
    # merchant interaction
    near_merchant: object | None = None  # merchant dict when player is near
    shop_open: bool = False  # whether shop UI is open
    encounters_since_merchant: int = 0  # Counter for guaranteed FIRST merchant after 3 encounters
    first_merchant_spawned: bool = False  # Track if first merchant has already spawned
    
    # tavern interaction
    near_tavern: object | None = None  # tavern dict when player is near
    
    # currency (D&D style: 10 bronze = 1 silver, 10 silver = 1 gold)
    gold: int = 0
    silver: int = 0
    bronze: int = 0

    # audio state
    is_walking: bool = False
    is_running: bool = False
    movement_sfx_state: str | None = None
    overworld_music_started: bool = False
    
    # score animation state (only after summoner battle victory)
    score_animation_active: bool = False
    score_animation_timer: float = 0.0
    score_animation_start: int = 0  # Score value before battle
    score_animation_target: int = 0  # Score value after battle
    score_thunder_played: bool = False

    # party / HUD
    player_token: object | None = None           # small face portrait (pygame.Surface)
    party_slots: list = field(default_factory=lambda: [None] * 6)  # 6 slots for vessel tokens
    
    # buffs system
    active_buffs: list = field(default_factory=list)  # List of active buffs
    buffs_history: list = field(default_factory=list)  # Track all buffs received
    first_overworld_blessing_given: bool = False  # Track if first overworld blessing was given this run