# ============================================================
# screens/party_manager.py — Overworld Party Manager (Tab)
# - Modal overlay opened/closed with Tab (or Esc)
# - Shows 6 party slots with icon, name, level, HP bar
# - Click a row to select; click another to SWAP positions
# - Right-click a row to SET ACTIVE (updates gs.party_active_idx)
# - Draws on parchment; blocks overworld input while open
# ============================================================
import os
import re
import random
import pygame
import settings as S
from systems import audio as audio_sys

# Font helper for textbox
def _get_dh_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Load DH font if available, fallback to system font."""
    try:
        font_path = os.path.join("Assets", "Fonts", "DH.otf")
        if os.path.exists(font_path):
            return pygame.font.Font(font_path, size)
    except Exception:
        pass
    # Fallback
    try:
        return pygame.font.SysFont("georgia", size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)

# Healing scroll sounds
_HEALING_SFX_BASE = os.path.join("Assets", "Music", "Sounds")
_HEALING_SOUNDS = {
    "scroll_of_healing": None,
    "scroll_of_mending": None,
    "scroll_of_regeneration": None,
    "scroll_of_revivity": None,
}

def _ensure_healing_sfx():
    """Load healing scroll sound effects if not already loaded."""
    global _HEALING_SOUNDS
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        
        # Map item IDs to sound filenames
        sound_map = {
            "scroll_of_healing": "Healing.mp3",
            "scroll_of_mending": "Mending.mp3",
            "scroll_of_regeneration": "Regeneration.mp3",
            "scroll_of_revivity": "Revivity.mp3",
        }
        
        for item_id, filename in sound_map.items():
            if _HEALING_SOUNDS.get(item_id) is None:
                sound_path = os.path.join(_HEALING_SFX_BASE, filename)
                if os.path.exists(sound_path):
                    _HEALING_SOUNDS[item_id] = pygame.mixer.Sound(sound_path)
                else:
                    print(f"⚠️ party_manager: healing sound not found: {sound_path}")
    except Exception as e:
        print(f"⚠️ party_manager: healing SFX load failed: {e}")

def _play_healing_sound(item_id: str):
    """Play the appropriate healing sound for the given scroll item."""
    _ensure_healing_sfx()
    sound = _HEALING_SOUNDS.get(item_id)
    if sound:
        audio_sys.play_sound(sound)
    else:
        # Fallback to click sound if healing sound not available
        audio_sys.play_click(audio_sys.get_global_bank())

# Optional: use your Roller if available (for consistent RNG)
try:
    from rolling.roller import Roller
    _ROLLER = Roller()
except Exception:
    _ROLLER = None

def _decrement_inventory(gs, item_id: str) -> None:
    inv = getattr(gs, "inventory", None)
    if inv is None:
        return
    # dict shape
    if isinstance(inv, dict):
        if item_id in inv:
            inv[item_id] = max(0, int(inv[item_id]) - 1)
            if inv[item_id] <= 0:
                try: del inv[item_id]
                except Exception: pass
        gs.inventory = inv
        return
    # list/tuple
    if isinstance(inv, (list, tuple)):
        new_list = []
        used = False
        for rec in inv:
            if isinstance(rec, dict):
                rid = rec.get("id") or rec.get("name")
                rid = str(rid or "")
                if (rid == item_id) and not used:
                    q = max(0, int(rec.get("qty", 0)) - 1)
                    used = True
                    if q > 0:
                        rec["qty"] = q
                        new_list.append(rec)
                else:
                    new_list.append(rec)
            elif isinstance(rec, (list, tuple)) and rec:
                rid = str(rec[0])
                if (rid == item_id) and not used:
                    q = int(rec[1]) if len(rec) > 1 else 0
                    q = max(0, q - 1)
                    used = True
                    if q > 0:
                        new_list.append([rid, q])
                else:
                    new_list.append(rec)
            else:
                new_list.append(rec)
        gs.inventory = new_list


def _roll_d(sides: int) -> int:
    """Roll 1d<sides> using Roller if available, else random."""
    s = max(1, int(sides))
    if _ROLLER:
        # Try common method names (be forgiving across your versions)
        for name in ("roll_die", "die", "roll_d"):
            fn = getattr(_ROLLER, name, None)
            if callable(fn):
                try:
                    v = fn(s)
                    return int(v if v is not None else 1)
                except Exception:
                    pass
        # Try generic N,dS signatures
        for name in ("roll", "roll_nds", "roll_dice", "dice"):
            fn = getattr(_ROLLER, name, None)
            if callable(fn):
                try:
                    v = fn(1, s)
                    # could be int or iterable
                    if isinstance(v, int):
                        return v
                    try:
                        return int(sum(v))
                    except Exception:
                        return int(v) if v is not None else 1
                except Exception:
                    pass
        # Last-resort: try roll_d20 style for d20 only
        if s == 20:
            fn = getattr(_ROLLER, "roll_d20", None)
            if callable(fn):
                try:
                    v = fn()
                    return int(v if v is not None else 1)
                except Exception:
                    pass
    # Fallback RNG
    return random.randint(1, s)


# Optional: tie into your audio system if present
try:
    from systems import audio as audio_sys
    # Pre-load global bank eagerly at module import to avoid first-time lag
    _AUDIO_BANK_CACHE = None
    def _get_cached_bank():
        global _AUDIO_BANK_CACHE
        if _AUDIO_BANK_CACHE is None:
            _AUDIO_BANK_CACHE = audio_sys.get_global_bank()
        return _AUDIO_BANK_CACHE
except Exception:  # graceful fallback
    audio_sys = None
    _get_cached_bank = None

# ---------------- Modal open/close ----------------
_OPEN = False
_FADE_START_MS = None
FADE_MS = 180

# NEW: optional picker callback (select-a-target mode)
_ON_PICK = None  # callable(gs, index) -> None

def is_open() -> bool:
    return _OPEN

def open():
    global _OPEN, _FADE_START_MS
    if _OPEN:
        return
    _OPEN = True
    _FADE_START_MS = pygame.time.get_ticks()
    # Sound will be played in draw() after first frame to avoid blocking
    # Reset any stale state
    global _SELECTED
    _SELECTED = None

def open_picker(on_pick):
    """Open Party Manager in 'picker' mode; left click returns index via callback."""
    global _ON_PICK
    _ON_PICK = on_pick
    open()

def close():
    global _OPEN, _FADE_START_MS, _SELECTED, _ON_PICK
    if not _OPEN:
        return
    # Check if we're in picker mode before clearing
    was_picker_mode = (_ON_PICK is not None)
    _OPEN = False
    _FADE_START_MS = None
    _SELECTED = None
    _ON_PICK = None
    # Skip sound when closing picker mode to avoid lag
    if not was_picker_mode:  # Only play sound if not in picker mode
        try:
            _play_open()
        except Exception:
            pass


def toggle():
    if _OPEN:
        close()
    else:
        open()

# ---------------- Assets (scroll parchment) ----------------
_SCROLL_IMG_PATH = os.path.join("Assets", "Map", "PartyScroll.png")
_SCROLL_BASE: pygame.Surface | None = None
_SCROLL_CACHE: dict[tuple[int, int], pygame.Surface] = {}

def _load_scroll_scaled(sw: int, sh: int) -> pygame.Surface | None:
    global _SCROLL_BASE
    if _SCROLL_BASE is None:
        if not os.path.exists(_SCROLL_IMG_PATH):
            return None
        try:
            _SCROLL_BASE = pygame.image.load(_SCROLL_IMG_PATH).convert_alpha()
        except Exception:
            _SCROLL_BASE = None
            return None
    base = _SCROLL_BASE
    iw, ih = base.get_size()
    max_w = int(sw * 0.70)
    max_h = int(sh * 0.74)
    scale = min(max_w / iw, max_h / ih, 1.0)
    w, h = max(1, int(iw * scale)), max(1, int(ih * scale))
    key = (w, h)
    if key in _SCROLL_CACHE:
        return _SCROLL_CACHE[key]
    surf = pygame.transform.smoothscale(base, key)
    _SCROLL_CACHE[key] = surf
    return surf

def _scroll_rect(sw: int, sh: int) -> pygame.Rect:
    sc = _load_scroll_scaled(sw, sh)
    if sc is None:
        w, h = int(sw * 0.70), int(sh * 0.74)
        return pygame.Rect((sw - w)//2, (sh - h)//2, w, h)
    return sc.get_rect(center=(sw//2, sh//2))

# ---------------- Data helpers ----------------
_ICON_CACHE: dict[tuple[str, int], pygame.Surface | None] = {}
_FONT_CACHE: dict[tuple[int, bool], pygame.font.Font] = {}
_DIM_SURFACE: pygame.Surface | None = None
_DIM_SIZE: tuple[int, int] | None = None

def _load_token_icon(fname: str | None, size: int) -> pygame.Surface | None:
    if not fname:
        return None
    key = (fname, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    surf = None
    # Use find_image to search all asset directories (including VesselMonsters for monster tokens)
    from systems.asset_links import find_image
    path = find_image(fname)
    if path and os.path.exists(path):
        try:
            src = pygame.image.load(path).convert_alpha()
            w, h = src.get_width(), src.get_height()
            s = min(size / max(1, w), size / max(1, h))
            surf = pygame.transform.smoothscale(src, (max(1, int(w*s)), max(1, int(h*s))))
        except Exception as e:
            print(f"⚠️ Failed to load token icon {fname} from {path}: {e}")
    else:
        # Debug: print if token not found (especially for monsters)
        if fname and "Token" in fname:
            print(f"⚠️ Token icon not found in party_manager: {fname} (searched in SEARCH_DIRS)")
    _ICON_CACHE[key] = surf
    return surf

def _pretty_name(fname: str | None) -> str:
    """Get display name for a vessel (uses name generator)."""
    if not fname:
        return ""
    from systems.name_generator import generate_vessel_name
    return generate_vessel_name(fname)

def _hp_tuple(stats: dict | None) -> tuple[int, int]:
    if isinstance(stats, dict):
        hp = int(stats.get("hp", 10))
        cur = int(stats.get("current_hp", hp))
        cur = max(0, min(cur, hp))
        return cur, hp
    return 10, 10

def _con_mod_of(stats: dict | None) -> int:
    if not isinstance(stats, dict):
        return 0
    # Common places you store ability data
    if "con_mod" in stats:
        try: return int(stats["con_mod"])
        except Exception: return 0
    # abilities might hold raw scores {"STR": 14, "CON": 12, ...}
    abilities = stats.get("abilities") if isinstance(stats, dict) else None
    if isinstance(abilities, dict):
        for key in ("CON", "con"):
            if key in abilities:
                try:
                    score = int(abilities[key])
                    return (score - 10) // 2
                except Exception:
                    return 0
    return 0

def _apply_heal_or_revive(gs, idx: int, mode: dict) -> tuple[bool, int]:
    """Apply heal/revive to party index; returns (True if changed, heal_amount)."""
    stats_list = getattr(gs, "party_vessel_stats", None) or [None]*6
    if not (0 <= idx < len(stats_list)):
        return (False, 0)
    st = stats_list[idx]
    if not isinstance(st, dict):
        return (False, 0)

    maxhp = int(st.get("hp", 10) or 10)
    curhp_raw = st.get("current_hp", maxhp)
    curhp = int(curhp_raw) if curhp_raw is not None else maxhp
    curhp = max(0, min(curhp, maxhp))
    
    # Strict check: if HP is 0 or less, vessel is dead
    is_dead = (curhp <= 0)

    revive = bool(mode.get("revive", False))
    kind   = (mode.get("kind") or "heal").lower()
    item_id = (mode.get("item_id") or mode.get("consume_id") or "")
    if item_id:
        item_id = str(item_id).lower().strip()
    else:
        item_id = ""

    # CRITICAL: If vessel is dead (0 HP), ONLY Scroll of Revivity can work
    # This check happens FIRST before any other logic
    if is_dead:
        # Debug: print what we're checking
        print(f"DEBUG: Vessel DEAD at {curhp} HP, item_id='{item_id}', revive={revive}")
        
        # For dead vessels, ONLY allow scroll_of_revivity with revive flag
        # Block if: NOT revivity OR revive flag is False
        is_revivity = (item_id == "scroll_of_revivity")
        has_revive_flag = revive
        is_allowed = (is_revivity and has_revive_flag)
        
        if not is_allowed:
            print(f"DEBUG: BLOCKING healing on dead vessel - item_id='{item_id}', revive={revive}")
            return (False, 0)  # Block all non-revivity healing on dead vessels
        else:
            print(f"DEBUG: ALLOWING revivity on dead vessel")
    
    # Scroll of Revivity: ONLY works on vessels with 0 HP
    if item_id == "scroll_of_revivity":
        if curhp > 0:
            return (False, 0)  # Revivity only works on dead vessels

    # If revive: bring to at least 1 HP before applying healing roll
    if revive and curhp <= 0:
        curhp = 1

    heal = 0
    if kind == "heal":
        dice = mode.get("dice") or (0, 0)
        try:
            dN, dS = int(dice[0]), int(dice[1])
        except Exception:
            dN, dS = 0, 0
        for _ in range(max(0, dN)):
            heal += _roll_d(max(1, dS))
        if bool(mode.get("add_con", False)):
            heal += _con_mod_of(st)
        
        # Apply Blessing of Restoration (Legendary5) healing bonus
        # This adds the rolled 1d8 bonus to all healing items
        healing_bonus = getattr(gs, "healing_bonus", 0)
        if healing_bonus > 0:
            heal += healing_bonus
            print(f"✨ Blessing of Restoration: Added +{healing_bonus} healing bonus (total heal: {heal})")
        
        if heal < 0:
            heal = 0

    new_hp = max(0, min(maxhp, curhp + heal))
    if new_hp == int(st.get("current_hp", curhp)):
        # no change
        return (False, 0)

    st["current_hp"] = new_hp
    stats_list[idx] = st
    gs.party_vessel_stats = stats_list
    return (True, heal)

# Handle the scroll of healing in party_manager
def start_use_mode(mode: dict):
    """
    Enter a targeting mode: next left-clicked filled row applies the effect.
    Example mode:
      {"kind":"heal", "dice":(1,8), "add_con":True, "revive":False, "consume_id":"scroll_of_healing"}
    """
    global _USE_MODE
    _USE_MODE = dict(mode or {})
    if not is_open():
        open()

# ---------------- Audio helpers ----------------
def _play_click():
    try:
        if audio_sys and _get_cached_bank:
            bank = _get_cached_bank()
            if bank:
                audio_sys.play_click(bank)
    except Exception:
        pass

def _play_open():
    """Play open sound effect - optimized to avoid blocking."""
    try:
        if audio_sys and _get_cached_bank:
            bank = _get_cached_bank()
            if bank:
                # Play sound asynchronously without blocking
                audio_sys.play_sfx(bank, "scrollopen")
    except Exception:
        try:
            _play_click()
        except Exception:
            pass  # Silently fail if sound can't play

# ---------------- Interaction state ----------------
_ITEM_RECTS: list[pygame.Rect] = []
_ITEM_INDEXES: list[int] = []
_PANEL_RECT: pygame.Rect | None = None
_SELECTED: int | None = None   # first click; second click swaps

# --- Lightweight "use-on-click" mode (e.g., healing, revive) ---
# mode example: {"kind":"heal", "dice":(1,8), "add_con":True, "revive":False}
_USE_MODE: dict | None = None

# --- Heal textbox state ---
_HEAL_TEXTBOX_ACTIVE = False
_HEAL_TEXTBOX_TEXT = ""
_HEAL_TEXTBOX_BLINK_T = 0.0
_HEAL_ANIMATION_ACTIVE = False  # True if healing animation should play
_HEAL_ANIMATION_HEALED_IDX = None  # Index of vessel that was healed
_HEAL_ANIMATION_TIMER = 0.0  # Timer for animation frame selection
_HEAL_ANIMATION_DURATION = 2.0  # Animation duration in seconds
_HEAL_ANIMATION_START_TIME = 0.0  # When animation started (timestamp)
_HEAL_ANIMATION_FRAMES = None  # Cached animation frames

def start_use_mode(mode: dict):
    """
    Enter a targeting mode: next left-clicked filled row applies the effect.
    Example mode:
      {"kind":"heal", "dice":(1,8), "add_con":True, "revive":False, "consume_id":"scroll_of_mending"}
    """
    global _USE_MODE
    _USE_MODE = dict(mode or {})
    if not is_open():
        open()

def clear_use_mode():
    global _USE_MODE
    _USE_MODE = None

def _show_heal_textbox(gs, vessel_name: str, heal_amount: int, healed_idx: int):
    """Show a textbox displaying the heal amount."""
    global _HEAL_TEXTBOX_ACTIVE, _HEAL_TEXTBOX_TEXT, _HEAL_TEXTBOX_BLINK_T
    global _HEAL_ANIMATION_ACTIVE, _HEAL_ANIMATION_HEALED_IDX, _HEAL_ANIMATION_TIMER
    global _HEAL_ANIMATION_START_TIME
    
    _HEAL_TEXTBOX_ACTIVE = True
    _HEAL_TEXTBOX_TEXT = f"{vessel_name} healed for {heal_amount} HP!"
    _HEAL_TEXTBOX_BLINK_T = 0.0
    
    # Check if healed vessel is the active one in combat
    active_idx = getattr(gs, "combat_active_idx", None)
    if active_idx is None:
        active_idx = getattr(gs, "party_active_idx", None)
    
    # Only play animation if healing the active vessel
    if healed_idx is not None and active_idx is not None and healed_idx == active_idx:
        _HEAL_ANIMATION_ACTIVE = True
        _HEAL_ANIMATION_HEALED_IDX = healed_idx
        _HEAL_ANIMATION_TIMER = 0.0
        _HEAL_ANIMATION_START_TIME = pygame.time.get_ticks() / 1000.0  # Current time in seconds
    else:
        _HEAL_ANIMATION_ACTIVE = False

def is_heal_textbox_active() -> bool:
    """Check if the heal textbox is currently showing."""
    return _HEAL_TEXTBOX_ACTIVE

def is_heal_animation_active() -> bool:
    """Check if the heal animation should be playing (stops after 2 seconds)."""
    global _HEAL_ANIMATION_ACTIVE
    if not _HEAL_ANIMATION_ACTIVE:
        return False
    
    # Check if 2 seconds have elapsed
    current_time = pygame.time.get_ticks() / 1000.0
    elapsed = current_time - _HEAL_ANIMATION_START_TIME
    if elapsed >= _HEAL_ANIMATION_DURATION:
        _HEAL_ANIMATION_ACTIVE = False
        return False
    
    return True

def _load_heal_animation_frames():
    """Load healing animation frames (fx_10_ver_3_01.png to fx_10_ver_3_27.png)."""
    global _HEAL_ANIMATION_FRAMES
    if _HEAL_ANIMATION_FRAMES is not None:
        return _HEAL_ANIMATION_FRAMES
    
    _HEAL_ANIMATION_FRAMES = []
    base = os.path.join("Assets", "Animations")
    
    try:
        # Load frames fx_10_ver_3_01.png through fx_10_ver_3_27.png
        for i in range(1, 28):  # 01 to 27
            frame_num = f"{i:02d}"  # 01, 02, ..., 27
            fname = f"fx_10_ver_3_{frame_num}.png"
            path = os.path.join(base, fname)
            if os.path.exists(path):
                try:
                    frame = pygame.image.load(path).convert_alpha()
                    _HEAL_ANIMATION_FRAMES.append(frame)
                except Exception as e:
                    print(f"⚠️ Failed to load heal animation frame {fname}: {e}")
        print(f"ℹ️ Loaded {len(_HEAL_ANIMATION_FRAMES)} heal animation frames")
    except Exception as e:
        print(f"⚠️ Failed to load heal animation: {e}")
    
    return _HEAL_ANIMATION_FRAMES

# Export the function so battle.py and wild_vessel.py can use it
def get_heal_animation_frames():
    """Public accessor for heal animation frames."""
    return _load_heal_animation_frames()

def _draw_heal_textbox(screen: pygame.Surface, dt: float = 0.016):
    """Draw the heal amount textbox (similar to summoner battle textbox)."""
    global _HEAL_TEXTBOX_ACTIVE, _HEAL_TEXTBOX_TEXT, _HEAL_TEXTBOX_BLINK_T
    
    if not _HEAL_TEXTBOX_ACTIVE:
        return
    
    sw, sh = screen.get_size()
    box_h = 120
    margin_x = 36
    margin_bottom = 28
    rect = pygame.Rect(margin_x, sh - box_h - margin_bottom, sw - margin_x * 2, box_h)

    # Box styling (matches summoner battle textbox)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (0, 0, 0), rect, 4, border_radius=8)
    inner = rect.inflate(-8, -8)
    pygame.draw.rect(screen, (60, 60, 60), inner, 2, border_radius=6)

    # Text rendering (simple wrap)
    font = _get_dh_font(28)
    text = _HEAL_TEXTBOX_TEXT
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
    _HEAL_TEXTBOX_BLINK_T += dt
    blink_on = int(_HEAL_TEXTBOX_BLINK_T * 2) % 2 == 0
    if blink_on:
        prompt_font = _get_dh_font(20)
        prompt = prompt_font.render("Press SPACE or Click to continue", False, (100, 100, 100))
        screen.blit(prompt, (rect.right - prompt.get_width() - 20, rect.bottom - prompt.get_height() - 12))


def _swap(gs, i, j):
    # Get current names and stats - create new lists to avoid reference issues
    names_src = getattr(gs, "party_slots_names", None)
    stats_src = getattr(gs, "party_vessel_stats", None)
    
    if i == j:
        return

    # Create new lists with exactly 6 slots (copy to avoid modifying original)
    names = list(names_src) if names_src and isinstance(names_src, list) else [None]*6
    stats = list(stats_src) if stats_src and isinstance(stats_src, list) else [None]*6
    
    # Ensure exactly 6 slots
    while len(names) < 6:
        names.append(None)
    names = names[:6]
    while len(stats) < 6:
        stats.append(None)
    stats = stats[:6]

    # Store original names for debug logging
    name_i_before = names[i] if i < len(names) else None
    name_j_before = names[j] if j < len(names) else None
    
    # Swap names and stats in the new lists
    names[i], names[j] = names[j], names[i]
    stats[i], stats[j] = stats[j], stats[i]
    
    # Debug: Log the swap
    print(f"🔄 Swapped slots {i} and {j}:")
    print(f"   Slot {i}: '{name_i_before}' -> '{names[i]}'")
    print(f"   Slot {j}: '{name_j_before}' -> '{names[j]}'")
    
    # Assign the new lists back to gs (this updates the reference)
    # CRITICAL: Create a fresh list to ensure we're not sharing references
    gs.party_slots_names = list(names)
    gs.party_vessel_stats = list(stats) if isinstance(stats, list) else stats
    
    # CRITICAL: Clear party_slots surfaces - let party_ui.py rebuild from names
    # This ensures party_ui.py correctly detects the swap and rebuilds tokens
    gs.party_slots = [None] * 6

    act = getattr(gs, "party_active_idx", 0)
    if act == i:
        gs.party_active_idx = j
    elif act == j:
        gs.party_active_idx = i
    
    # If a vessel is moved to slot 0, automatically set it as active (leading vessel)
    # This ensures that the first party member leads battles
    if j == 0 and names[0]:
        gs.party_active_idx = 0
    elif i == 0 and names[0]:
        gs.party_active_idx = 0

def _set_active(gs, idx):
    names = getattr(gs, "party_slots_names", None) or [None]*6
    if 0 <= idx < len(names) and names[idx]:
        gs.party_active_idx = idx
        _play_click()

# ---------------- Event handling ----------------
def handle_event(e, gs) -> bool:
    global _SELECTED, _PANEL_RECT, _USE_MODE, _HEAL_TEXTBOX_ACTIVE
    
    # Handle heal textbox dismissal first (modal) - works even when party manager is closed
    if _HEAL_TEXTBOX_ACTIVE:
        # Check for dismissal keys/buttons
        dismissed = False
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                dismissed = True
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 1:  # Left mouse button
                dismissed = True
        
        if dismissed:
            _HEAL_TEXTBOX_ACTIVE = False
            _HEAL_ANIMATION_ACTIVE = False  # Stop animation when textbox is dismissed
            _HEAL_ANIMATION_HEALED_IDX = None
            _HEAL_ANIMATION_TIMER = 0.0  # Reset timer
            _HEAL_ANIMATION_START_TIME = 0.0
            _play_click()
            return True
        
        # Block all other input while textbox is active
        return True
    
    if not _OPEN:
        return False

    if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_TAB):
        close()
        _play_click()
        return True

    if e.type == pygame.MOUSEBUTTONDOWN:
        mx, my = e.pos

        if _PANEL_RECT and not _PANEL_RECT.collidepoint(mx, my):
            close()
            _play_open()
            return True

        if e.button == 1:
            for j, r in enumerate(_ITEM_RECTS):
                if r.collidepoint(mx, my):
                    real_idx = _ITEM_INDEXES[j] if j < len(_ITEM_INDEXES) else j
                    names = getattr(gs, "party_slots_names", None) or [None]*6

                    # Ensure we're dealing with a valid vessel
                    if not names[real_idx]:
                        _SELECTED = None
                        _play_click()
                        return True

                    # --- If we're in 'use-on-click' mode (for healing), apply and exit that mode ---
                    if _USE_MODE:
                        changed, heal_amount = _apply_heal_or_revive(gs, real_idx, _USE_MODE)
                        if changed:
                            # Get item ID for both sound and consumption
                            item_id = _USE_MODE.get("item_id") or _USE_MODE.get("consume_id")
                            if item_id:
                                # Play healing sound after healing is applied
                                _play_healing_sound(item_id)
                                # Consume the specific item now (first time we actually use it)
                                _decrement_inventory(gs, item_id)
                            
                            # Show heal amount textbox (pass the vessel index to check if it's active)
                            vessel_name = _pretty_name(names[real_idx]) or "Vessel"
                            _show_heal_textbox(gs, vessel_name, heal_amount, real_idx)

                            # End the player's turn now that the effect happened
                            try:
                                gs._turn_ready = False
                                gs._turn_consumed_by_item = True
                            except Exception:
                                pass
                        else:
                            # Healing didn't apply (e.g., already at full HP), play click instead
                            _play_click()

                        clear_use_mode()  # Reset the use mode after applying the effect
                        close()
                        return True

                    # --- If we're in picker mode, call the callback and close ---
                    if _ON_PICK is not None:
                        try:
                            _ON_PICK(real_idx)
                        except Exception as e:
                            print(f"⚠️ Picker callback error: {e}")
                        close()
                        _play_click()
                        return True
                    
                    # --- Default behavior: select or swap rows ---
                    if _SELECTED is None:
                        _SELECTED = real_idx
                        _play_click()
                        return True
                    else:
                        if _SELECTED != real_idx:
                            _swap(gs, _SELECTED, real_idx)
                        _SELECTED = None
                        _play_click()
                        return True


        if e.button == 3:
            for j, r in enumerate(_ITEM_RECTS):
                if r.collidepoint(mx, my):
                    real_idx = _ITEM_INDEXES[j] if j < len(_ITEM_INDEXES) else j
                    _set_active(gs, real_idx)
                    return True
    return False

# ---------------- Drawing ----------------
def draw(screen: pygame.Surface, gs, dt: float = 0.016):
    global _ITEM_RECTS, _ITEM_INDEXES, _PANEL_RECT, _FADE_START_MS
    # Draw heal textbox even if party manager is closed (it's modal)
    _draw_heal_textbox(screen, dt)
    
    # Handle deferred sound playing (only if open and sound hasn't played yet)
    # Skip sound for picker mode to reduce lag
    if _OPEN and _FADE_START_MS is not None and _ON_PICK is None:
        elapsed = pygame.time.get_ticks() - _FADE_START_MS
        if elapsed > 16:  # Play sound after first frame (~16ms at 60fps)
            try:
                _play_open()
            except Exception:
                pass
            _FADE_START_MS = None  # Mark as played
    elif _OPEN and _FADE_START_MS is not None and _ON_PICK is not None:
        # Picker mode - skip sound to avoid lag
        _FADE_START_MS = None
    
    if not _OPEN:
        return

    _ITEM_RECTS = []
    _ITEM_INDEXES = []

    sw, sh = screen.get_size()
    layer = pygame.Surface((sw, sh), pygame.SRCALPHA)

    # Cache dim surface to avoid recreating every frame
    global _DIM_SURFACE, _DIM_SIZE
    if _DIM_SURFACE is None or _DIM_SIZE != (sw, sh):
        _DIM_SURFACE = pygame.Surface((sw, sh), pygame.SRCALPHA)
        _DIM_SURFACE.fill((0, 0, 0, 140))
        _DIM_SIZE = (sw, sh)
    layer.blit(_DIM_SURFACE, (0, 0))

    sr = _scroll_rect(sw, sh)
    _PANEL_RECT = sr
    scroll = _load_scroll_scaled(sw, sh)
    if scroll is not None:
        layer.blit(scroll, sr.topleft)
    else:
        pygame.draw.rect(layer, (214, 196, 152), sr, border_radius=16)
        pygame.draw.rect(layer, (90, 70, 40), sr, 3, border_radius=16)

    old_clip = layer.get_clip()
    layer.set_clip(sr)

    side_pad = int(sr.w * 0.08)
    top_pad  = int(sr.h * 0.18)
    bot_pad  = int(sr.h * 0.16)
    inner = pygame.Rect(sr.x + side_pad, sr.y + top_pad, sr.w - side_pad*2, sr.h - (top_pad + bot_pad))
    rows = 6
    gap   = max(4, int(inner.h * 0.012))
    row_h = (inner.h - gap*(rows-1)) // rows
    icon  = max(48, int(row_h * 0.90))
    x_shift = int(inner.w * 0.08)

    # Cache fonts to avoid recreating every frame
    name_size = max(18, int(sr.h * 0.035))
    small_size = max(14, int(sr.h * 0.028))
    name_key = (name_size, True)
    small_key = (small_size, False)
    
    if name_key not in _FONT_CACHE:
        _FONT_CACHE[name_key] = pygame.font.SysFont("georgia", name_size, bold=True)
    if small_key not in _FONT_CACHE:
        _FONT_CACHE[small_key] = pygame.font.SysFont("georgia", small_size)
    
    name_f = _FONT_CACHE[name_key]
    small_f = _FONT_CACHE[small_key]
    ink      = (48, 34, 22)
    hp_back  = (62, 28, 24)
    hp_fill  = (40, 160, 84)
    sel_tint = (255, 255, 255, 48)
    act_tint = (120, 200, 255, 36)

    names = getattr(gs, "party_slots_names", None) or [None]*6
    stats = getattr(gs, "party_vessel_stats", None) or [None]*6
    if len(names) < 6:
        names += [None]*(6-len(names))
    if len(stats) < 6:
        stats += [None]*(6-len(stats))
    active_idx = int(getattr(gs, "party_active_idx", 0))

    y = inner.y
    mx, my = pygame.mouse.get_pos()

    for i in range(6):
        r = pygame.Rect(inner.x + x_shift, y, inner.w - x_shift, row_h)
        icon_rect = pygame.Rect(r.x, r.y + (row_h - icon)//2, icon, icon)

        fname = names[i]
        if fname:
            if _SELECTED == i:
                s = pygame.Surface((r.w, r.h), pygame.SRCALPHA); s.fill(sel_tint); layer.blit(s, r.topleft)
            if active_idx == i:
                a = pygame.Surface((r.w, r.h), pygame.SRCALPHA); a.fill(act_tint); layer.blit(a, r.topleft)

            ico = _load_token_icon(fname, icon)
            if ico:
                layer.blit(ico, ico.get_rect(center=icon_rect.center))

            clean = _pretty_name(fname) or "Vessel"
            lvl = int((stats[i] or {}).get("level", 1)) if isinstance(stats[i], dict) else 1
            label = f"{clean}   lvl {lvl}"
            lab_s = name_f.render(label, True, ink)
            text_x = icon_rect.right + int(sr.w * 0.02)
            name_y = r.y + int(row_h * 0.10)
            layer.blit(lab_s, (text_x, name_y))

            hp, maxhp = _hp_tuple(stats[i])
            ratio = 0 if maxhp <= 0 else (hp / maxhp)
            bar_w = int(inner.w * 0.46)
            bar_h = max(10, int(row_h * 0.18))
            bar_x = text_x
            bar_y = name_y + lab_s.get_height() + 6
            bar_r = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
            pygame.draw.rect(layer, hp_back, bar_r, border_radius=6)
            if ratio > 0:
                fill = bar_r.copy(); fill.w = int(bar_r.w * ratio)
                pygame.draw.rect(layer, hp_fill, fill, border_radius=6)
            hp_s = small_f.render(f"HP {hp}/{maxhp}", True, ink)
            layer.blit(hp_s, (bar_r.right + 10, bar_r.y - 2))

            if r.collidepoint(mx, my):
                glow = pygame.Surface((r.w, r.h), pygame.SRCALPHA); glow.fill((255,255,255,28))
                layer.blit(glow, r.topleft)

            _ITEM_RECTS.append(r)
            _ITEM_INDEXES.append(i)
        # else: empty slot — draw nothing at all
        y += row_h + gap

    layer.set_clip(old_clip)

    if _FADE_START_MS is None:
        alpha = 255
    else:
        t = max(0, pygame.time.get_ticks() - _FADE_START_MS)
        alpha = 255 if FADE_MS <= 0 else min(255, int(255 * (t / FADE_MS)))
    layer.set_alpha(alpha)
    screen.blit(layer, (0, 0))
