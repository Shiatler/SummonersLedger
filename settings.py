# ============================================================
#  settings.py — constants & toggles
# ============================================================

import os


# ===================== App / Window ==========================
APP_NAME = "Summoner's Ledger"

# Window (will be overridden to fullscreen in main.py)
WIDTH, HEIGHT = 800, 480
FLAGS = 0


# ===================== World ================================
WORLD_W, WORLD_H = 2400, 100000
TILE = 64
BG_COLOR   = (34, 40, 48)
GRID_COLOR = (50, 58, 68)


# ===================== Assets (folders) ======================
# Keep these as STRINGS, not lists
ASSETS_MAP_DIR              = os.path.join("Assets", "Map")
ASSETS_PLAYABLE_DIR         = os.path.join("Assets", "PlayableCharacters")
ASSETS_SUMMONERS_MALE_DIR   = os.path.join("Assets", "SummonersMale")
ASSETS_SUMMONERS_FEMALE_DIR = os.path.join("Assets", "SummonersFemale")
ASSETS_SUMMONERS_BOSS_DIR   = os.path.join("Assets", "SummonersBoss")
ASSETS_VESSELS_MALE_DIR     = os.path.join("Assets", "VesselsMale")
ASSETS_VESSELS_FEMALE_DIR   = os.path.join("Assets", "VesselsFemale")
ASSETS_VESSELS_RARE_DIR     = os.path.join("Assets", "RareVessels")
ASSETS_FONTS_DIR            = os.path.join("Assets", "Fonts")


# ===================== Player ===============================
PLAYER_SIZE       = (138, 138)  # keeps player at consistent size
PLAYER_MALE_FILE  = "CharacterMale.png"
PLAYER_FEMALE_FILE= "CharacterFemale.png"
PLAYER_SPEED      = 260
SPRITE_SIZE       = PLAYER_SIZE  # temporary compatibility alias


# ===================== Encounters & pacing ===================
EVENT_MIN, EVENT_MAX      = 160, 320
FIRST_EVENT_AT            = 120
ENCOUNTER_WEIGHT_VESSEL   = 0.75  # 75% vessel, 25% summoner
SPAWN_GAP_MIN             = 1500
SPAWN_GAP_MAX             = 10000
ENCOUNTER_SHOW_TIME       = 2.0

# Guaranteed vertical separation between any two spawns (regardless of type)
# Tune this as you like; start around player sprite height * ~1.2
OVERWORLD_MIN_SEPARATION_Y = max(int(PLAYER_SIZE[1] * 1.2), 180)


# ===================== Lanes / Collision =====================
LANE_OFFSET      = 140
FRONT_TOLERANCE  = 4
DEBUG_OVERWORLD  = False


# ===================== Audio Defaults ========================
# Referenced by audio.py via getattr(..., default)
MUSIC_VOLUME = 0.6
SFX_VOLUME   = 0.8


# ===================== Save Files ============================
SAVE_DIR  = "Saves"
SAVE_PATH = os.path.join(SAVE_DIR, "savegame.json")


# ===================== Menu / Theme ==========================
MENU_BG_FILE  = "mainmenu.png"
DND_FONT_FILE = "DH.otf"


# ===================== Modes ================================
MODE_MENU = "MENU"
MODE_GAME = "GAME"
MODE_DEATH = "DEATH"


# ===================== Road / Background =====================
# Used for horizontal cropping and lane positioning (world.py tiles vertically)
ROAD_W = 1200  # width of the road (centered at WORLD_W//2)

LEVEL_UP_HEALS_FULL = True  # set False to preserve previous HP ratio on level-up

