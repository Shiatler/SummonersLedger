# ============================================================
# screens/book_of_bound.py — Book of the Bound (Pokedex-style)
# Layout: Left panel for detailed sprite/info display, right panel for scrollable grid
# ============================================================

import os
import pygame
import random
import math
import glob
import settings as S
from systems import coords  # ← Always import this for coordinate conversion!

# Mode constant
MODE_BOOK_OF_BOUND = "BOOK_OF_BOUND"

# ===================== Layout Constants =====================
# Use logical resolution for all calculations
HEADER_HEIGHT = 80
LEFT_PANEL_WIDTH = int(S.LOGICAL_WIDTH * 0.65)  # ~65% of screen width
RIGHT_PANEL_WIDTH = S.LOGICAL_WIDTH - LEFT_PANEL_WIDTH

# Grid layout for right panel
GRID_COLS = 2  # 2 columns of squares (2 per row)
GRID_SQUARE_SIZE = 140  # Size of each square in the grid (larger for better visibility)
GRID_SPACING = 8  # Space between squares (reduced for tighter layout)
GRID_PADDING = 20  # Padding around the grid

# Colors - Purple, gloomy, magical, medieval aesthetic
COLOR_BG = (25, 15, 35)  # Deep dark purple background (gloomy)
COLOR_HEADER_BG = (60, 30, 80)  # Dark purple header (medieval)
COLOR_HEADER_TEXT = (180, 140, 220)  # Light purple text (ghostly magic)
COLOR_PANEL_BG = (35, 20, 50)  # Dark purple-gray panel background
COLOR_PANEL_BORDER = (90, 50, 120)  # Purple border (magical)
COLOR_GRID_SQUARE = (45, 25, 65)  # Dark purple squares
COLOR_GRID_SQUARE_BORDER = (100, 60, 130)  # Purple border for squares
COLOR_INFO_BOX = (40, 22, 58)  # Dark purple for info boxes
COLOR_INFO_BORDER = (85, 45, 115)  # Purple border for info boxes
COLOR_TEXT = (170, 130, 200)  # Light purple text (ghostly)
COLOR_TEXT_DIM = (120, 90, 150)  # Dimmer purple for secondary text

# Scroll state
_scroll_offset = 0
_total_entries = 0  # Will be set based on loaded silhouettes
_scrollbar_dragging = False  # Track if scrollbar thumb is being dragged
_drag_start_y = 0  # Mouse Y position when drag started
_drag_start_offset = 0  # Scroll offset when drag started

# Vessel silhouette cache
_vessel_silhouettes = []  # List of (name, silhouette_surface, category) tuples
_silhouettes_loaded = False

# Selected vessel state
_selected_vessel_index = None  # Index of currently selected vessel in _vessel_silhouettes

# Mist effect state
_mist_particles = []
_mist_initialized = False

# Fade transition state
_fade_state = None  # "fade_out", "fade_in", or None
_fade_alpha = 0.0
_fade_speed = 0.0
_fade_surface = None
_previous_screen_surface = None  # Snapshot of previous screen for fade out


# ===================== Sprite Silhouette Generation =====================
def _create_silhouette(sprite_surface: pygame.Surface) -> pygame.Surface:
    """Convert a sprite to a black silhouette while preserving transparency."""
    # Create a copy of the sprite
    result = sprite_surface.copy()
    
    # Fill with black while preserving alpha channel
    # Use BLEND_RGB_MULT to multiply RGB by 0 (black) while keeping alpha
    black_surf = pygame.Surface(sprite_surface.get_size(), pygame.SRCALPHA)
    black_surf.fill((0, 0, 0, 255))
    
    # Blend: multiply RGB values by 0 (makes everything black) but keep alpha
    result.blit(black_surf, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    
    return result


def _load_all_vessel_silhouettes():
    """Load all vessel sprites and convert them to silhouettes in logical order."""
    global _vessel_silhouettes, _total_entries, _silhouettes_loaded
    
    if _silhouettes_loaded:
        return
    
    _vessel_silhouettes = []
    
    # Order: Starters first (Druids, Barbarians, Rogues), then Female, then Male, then Rares last
    starters_dir = os.path.join("Assets", "Starters")
    
    # 1. Load Starters (15 vessels) - Druids first, then Barbarians, then Rogues
    starter_order = ["Druid", "Barbarian", "Rogue"]
    for starter_class in starter_order:
        starter_paths = sorted(glob.glob(os.path.join(starters_dir, f"Starter{starter_class}*.png")))
        # Filter out tokens - only get vessel files
        starter_paths = [p for p in starter_paths if "Token" not in os.path.basename(p)]
        for path in starter_paths:
            try:
                sprite = pygame.image.load(path).convert_alpha()
                silhouette = _create_silhouette(sprite)
                name = os.path.splitext(os.path.basename(path))[0]
                _vessel_silhouettes.append((name, silhouette, "starter"))
            except Exception as e:
                print(f"⚠️ Failed to load starter vessel {path}: {e}")
    
    # 2. Load VesselsFemale (30 vessels)
    female_dir = S.ASSETS_VESSELS_FEMALE_DIR
    female_paths = sorted(glob.glob(os.path.join(female_dir, "FVessel*.png")))
    for path in female_paths:
        try:
            sprite = pygame.image.load(path).convert_alpha()
            silhouette = _create_silhouette(sprite)
            name = os.path.splitext(os.path.basename(path))[0]
            _vessel_silhouettes.append((name, silhouette, "female"))
        except Exception as e:
            print(f"⚠️ Failed to load female vessel {path}: {e}")
    
    # 3. Load VesselsMale (29 vessels)
    male_dir = S.ASSETS_VESSELS_MALE_DIR
    male_paths = sorted(glob.glob(os.path.join(male_dir, "MVessel*.png")))
    for path in male_paths:
        try:
            sprite = pygame.image.load(path).convert_alpha()
            silhouette = _create_silhouette(sprite)
            name = os.path.splitext(os.path.basename(path))[0]
            _vessel_silhouettes.append((name, silhouette, "male"))
        except Exception as e:
            print(f"⚠️ Failed to load male vessel {path}: {e}")
    
    # 4. Load RareVessels LAST (14 vessels)
    rare_dir = S.ASSETS_VESSELS_RARE_DIR
    rare_paths = sorted(glob.glob(os.path.join(rare_dir, "RVessel*.png")))
    for path in rare_paths:
        try:
            sprite = pygame.image.load(path).convert_alpha()
            silhouette = _create_silhouette(sprite)
            name = os.path.splitext(os.path.basename(path))[0]
            _vessel_silhouettes.append((name, silhouette, "rare"))
        except Exception as e:
            print(f"⚠️ Failed to load rare vessel {path}: {e}")
    
    # 5. Load Monster Vessels VERY LAST (always blacked out in the book list)
    #    Folder: Assets/VesselMonsters, include only actual vessel sprites (exclude Token*.png)
    monster_dir = os.path.join("Assets", "VesselMonsters")
    monster_paths = sorted(glob.glob(os.path.join(monster_dir, "*.png")))
    monster_paths = [p for p in monster_paths if not os.path.basename(p).lower().startswith("token")]
    for path in monster_paths:
        try:
            sprite = pygame.image.load(path).convert_alpha()
            silhouette = _create_silhouette(sprite)
            name = os.path.splitext(os.path.basename(path))[0]
            _vessel_silhouettes.append((name, silhouette, "monster"))
        except Exception as e:
            print(f"⚠️ Failed to load monster vessel {path}: {e}")
    
    _total_entries = len(_vessel_silhouettes)
    _silhouettes_loaded = True
    print(f"📚 Book of the Bound: Loaded {_total_entries} vessel silhouettes")


def mark_vessel_discovered(gs, vessel_asset_name: str):
    """Mark a vessel as discovered in the Book of the Bound (persistent across games)."""
    if not hasattr(gs, "book_of_bound_discovered"):
        gs.book_of_bound_discovered = set()
    
    # Remove .png extension if present, store just the name
    vessel_name = vessel_asset_name
    if vessel_name.lower().endswith(".png"):
        vessel_name = vessel_name[:-4]
    
    # Add to discovered set
    if vessel_name not in gs.book_of_bound_discovered:
        gs.book_of_bound_discovered.add(vessel_name)
        print(f"📚 Discovered vessel: {vessel_name}")
        
        # No autosave - user must manually save via "Save Game" button to persist discovery


def is_vessel_discovered(gs, vessel_name: str) -> bool:
    """Check if a vessel has been discovered."""
    if not hasattr(gs, "book_of_bound_discovered"):
        return False
    
    # Remove .png extension if present
    name = vessel_name
    if name.lower().endswith(".png"):
        name = name[:-4]
    
    return name in gs.book_of_bound_discovered


def _load_vessel_sprite(vessel_name: str, category: str) -> pygame.Surface | None:
    """Load the actual sprite for a discovered vessel."""
    try:
        # Determine the directory based on category
        if category == "starter":
            sprite_path = os.path.join("Assets", "Starters", f"{vessel_name}.png")
        elif category == "rare":
            sprite_path = os.path.join(S.ASSETS_VESSELS_RARE_DIR, f"{vessel_name}.png")
        elif category == "female":
            sprite_path = os.path.join(S.ASSETS_VESSELS_FEMALE_DIR, f"{vessel_name}.png")
        elif category == "male":
            sprite_path = os.path.join(S.ASSETS_VESSELS_MALE_DIR, f"{vessel_name}.png")
        elif category == "monster":
            sprite_path = os.path.join("Assets", "VesselMonsters", f"{vessel_name}.png")
        else:
            return None
        
        if os.path.exists(sprite_path):
            return pygame.image.load(sprite_path).convert_alpha()
    except Exception as e:
        print(f"⚠️ Failed to load vessel sprite {vessel_name}: {e}")
    return None


def _format_vessel_name(vessel_name: str) -> str:
    """Format vessel name for display (remove prefixes, make readable)."""
    # Remove common prefixes
    name = vessel_name
    prefixes = ["FVessel", "MVessel", "RVessel", "Starter"]
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    
    # Add spaces before capital letters (e.g., "Barbarian1" -> "Barbarian 1")
    import re
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    name = re.sub(r'([A-Za-z])(\d)', r'\1 \2', name)
    
    return name


def _extract_class_from_vessel_name(vessel_name: str) -> str:
    """Extract class name from vessel asset name (e.g., 'FVesselBarbarian1' -> 'Barbarian')."""
    from combat.vessel_stats import _extract_class
    cls = _extract_class(vessel_name)
    return cls or "Fighter"


def _count_unique_discovered_species(gs) -> int:
    """Count unique discovered vessel species (by class)."""
    if not hasattr(gs, "book_of_bound_discovered"):
        return 0
    
    discovered_classes = set()
    for vessel_name in gs.book_of_bound_discovered:
        cls = _extract_class_from_vessel_name(vessel_name)
        discovered_classes.add(cls.lower())  # Normalize to lowercase
    
    return len(discovered_classes)


def _get_base_ac_for_vessel(vessel_name: str) -> int:
    """Get base AC for a vessel (level 1, baseline)."""
    try:
        from combat.vessel_stats import generate_vessel_stats_from_asset
        # Generate level 1 stats to get baseline AC
        stats = generate_vessel_stats_from_asset(vessel_name, level=1)
        return stats.get("ac", 10)
    except Exception as e:
        print(f"⚠️ Failed to get AC for {vessel_name}: {e}")
        return 10  # Default fallback


def _get_main_stat_for_vessel(vessel_name: str) -> tuple[str, int]:
    """Get main stat name and value for a vessel. Returns (stat_name, stat_value)."""
    try:
        from combat.vessel_stats import generate_vessel_stats_from_asset
        from combat.stats import primary_stat_for_class
        
        # Generate level 1 stats to get abilities
        stats = generate_vessel_stats_from_asset(vessel_name, level=1)
        
        # Get class to determine main stat
        class_name = stats.get("class_name", "Fighter")
        main_stat_key = primary_stat_for_class(class_name)
        
        # Get the ability score for the main stat
        abilities = stats.get("abilities", {})
        main_stat_value = abilities.get(main_stat_key, 10)
        
        # Format stat name nicely
        stat_display_names = {
            "STR": "Strength",
            "DEX": "Dexterity",
            "CON": "Constitution",
            "INT": "Intelligence",
            "WIS": "Wisdom",
            "CHA": "Charisma",
        }
        stat_name = stat_display_names.get(main_stat_key, main_stat_key)
        
        return (stat_name, main_stat_value)
    except Exception as e:
        print(f"⚠️ Failed to get main stat for {vessel_name}: {e}")
        return ("Strength", 10)  # Default fallback


def _get_dex_text_for_vessel(vessel_name: str, category: str) -> str:
    """Get the Dex text content for a vessel from its .txt file."""
    try:
        # Determine the directory and file pattern based on category
        if category == "starter":
            # Starters: StarterBarbarianDex1.txt, StarterDruidDex1.txt, etc.
            # Extract class and number from vessel name (e.g., "StarterBarbarian1" -> "Barbarian", "1")
            import re
            match = re.match(r"Starter([A-Za-z]+)(\d+)", vessel_name)
            if match:
                class_name = match.group(1)
                number = match.group(2)
                txt_path = os.path.join("Assets", "Starters", f"Starter{class_name}Dex{number}.txt")
            else:
                return "???"
        elif category == "rare":
            # Rare: RDexBarbarian.txt, RDexDruid.txt, etc.
            # Extract class from vessel name (e.g., "RVesselBarbarian1" -> "Barbarian")
            import re
            match = re.match(r"RVessel([A-Za-z]+)", vessel_name)
            if match:
                class_name = match.group(1)
                txt_path = os.path.join("Assets", "RareVessels", f"RDex{class_name}.txt")
            else:
                return "???"
        elif category == "female":
            # Female: FDexBarbarian1.txt, FDexDruid1.txt, etc.
            # Extract class and number from vessel name (e.g., "FVesselBarbarian1" -> "Barbarian", "1")
            import re
            match = re.match(r"FVessel([A-Za-z]+)(\d+)", vessel_name)
            if match:
                class_name = match.group(1)
                number = match.group(2)
                txt_path = os.path.join("Assets", "VesselsFemale", f"FDex{class_name}{number}.txt")
            else:
                return "???"
        elif category == "male":
            # Male: MDexBarbarian1.txt, MDexDruid1.txt, etc.
            # Extract class and number from vessel name (e.g., "MVesselBarbarian1" -> "Barbarian", "1")
            import re
            match = re.match(r"MVessel([A-Za-z]+)(\d+)", vessel_name)
            if match:
                class_name = match.group(1)
                number = match.group(2)
                txt_path = os.path.join("Assets", "VesselsMale", f"MDex{class_name}{number}.txt")
            else:
                return "???"
        elif category == "monster":
            # Monsters: MonsterDexDragon.txt, MonsterDexNothic.txt, etc.
            # Monster names are already the class name (e.g., "Dragon", "Nothic", "Chestmonster")
            # Extract monster name from vessel name (remove any extensions)
            import re
            from combat.vessel_stats import _extract_class
            monster_name = _extract_class(vessel_name)
            if monster_name:
                txt_path = os.path.join("Assets", "VesselMonsters", f"MonsterDex{monster_name}.txt")
            else:
                return "???"
        else:
            return "???"
        
        # Load and return the text content
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                return content
        else:
            return "???"
    except Exception as e:
        print(f"⚠️ Failed to load Dex text for {vessel_name}: {e}")
        return "???"


def _render_text_with_wrapping(text: str, font: pygame.font.Font, color: tuple, max_width: int) -> pygame.Surface:
    """Render text with word wrapping to fit within max_width."""
    if not text or text == "???":
        return font.render(text, True, color)
    
    # Split text into words
    words = text.split(' ')
    lines = []
    current_line = []
    
    for word in words:
        # Test if adding this word would exceed max width
        test_line = ' '.join(current_line + [word])
        test_surf = font.render(test_line, True, color)
        
        if test_surf.get_width() <= max_width:
            current_line.append(word)
        else:
            # Current line is full, start a new one
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    # Add the last line
    if current_line:
        lines.append(' '.join(current_line))
    
    # Render each line
    line_surfs = []
    for line in lines:
        line_surf = font.render(line, True, color)
        line_surfs.append(line_surf)
    
    # Combine lines into a single surface
    if not line_surfs:
        return font.render("", True, color)
    
    total_height = sum(surf.get_height() for surf in line_surfs) + (len(line_surfs) - 1) * 2  # 2px spacing
    max_line_width = max(surf.get_width() for surf in line_surfs)
    combined_surf = pygame.Surface((max_line_width, total_height), pygame.SRCALPHA)
    
    y_offset = 0
    for line_surf in line_surfs:
        combined_surf.blit(line_surf, (0, y_offset))
        y_offset += line_surf.get_height() + 2
    
    return combined_surf


# ===================== Font Loading =====================
_font_cache = {}

def _get_font(size: int, bold: bool = False):
    """Get DH font with caching - medieval magical aesthetic."""
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    try:
        # Try to load DH font (absolute path fallback)
        font_paths = [
            os.path.join("Assets", "Fonts", "DH.otf"),
            r"C:\Users\Frederik\Desktop\SummonersLedger\Assets\Fonts\DH.otf",
            os.path.join("Assets", "Fonts", "DH.ttf"),
        ]
        for font_path in font_paths:
            if os.path.exists(font_path):
                font = pygame.font.Font(font_path, size)
                _font_cache[key] = font
                return font
    except Exception as e:
        print(f"⚠️ Failed to load DH font: {e}")
    # Fallback to system font
    try:
        font = pygame.font.SysFont("georgia", size, bold=bold)  # Georgia has medieval feel
    except Exception:
        font = pygame.font.Font(None, size)
    _font_cache[key] = font
    return font


# ===================== Mist Effect =====================
def _init_mist():
    """Initialize mist particles for the magical atmosphere."""
    global _mist_particles, _mist_initialized
    if _mist_initialized:
        return
    
    _mist_particles = []
    num_particles = 40  # Number of mist particles
    
    for _ in range(num_particles):
        particle = {
            'x': random.uniform(0, S.LOGICAL_WIDTH),
            'y': random.uniform(0, S.LOGICAL_HEIGHT),
            'size': random.uniform(60, 120),  # Particle size
            'speed_x': random.uniform(-8, 8),  # Horizontal drift speed
            'speed_y': random.uniform(-3, 3),  # Vertical drift speed
            'alpha': random.uniform(20, 50),  # Transparency (ghostly)
            'pulse_speed': random.uniform(0.5, 1.5),  # Pulse animation speed
            'pulse_phase': random.uniform(0, math.pi * 2),  # Starting phase
            'pulse_range': random.uniform(10, 30),  # How much alpha varies
        }
        _mist_particles.append(particle)
    
    _mist_initialized = True


def _update_mist(dt):
    """Update mist particle positions and animations."""
    global _mist_particles
    
    for particle in _mist_particles:
        # Update position (drifting movement)
        particle['x'] += particle['speed_x'] * dt * 0.5
        particle['y'] += particle['speed_y'] * dt * 0.5
        
        # Wrap around screen edges
        if particle['x'] < -particle['size']:
            particle['x'] = S.LOGICAL_WIDTH + particle['size']
        elif particle['x'] > S.LOGICAL_WIDTH + particle['size']:
            particle['x'] = -particle['size']
        
        if particle['y'] < -particle['size']:
            particle['y'] = S.LOGICAL_HEIGHT + particle['size']
        elif particle['y'] > S.LOGICAL_HEIGHT + particle['size']:
            particle['y'] = -particle['size']
        
        # Update pulse animation
        particle['pulse_phase'] += particle['pulse_speed'] * dt * 0.05
        if particle['pulse_phase'] > math.pi * 2:
            particle['pulse_phase'] -= math.pi * 2


def _draw_mist(screen: pygame.Surface):
    """Draw the mist effect - magical purple fog."""
    global _mist_particles
    
    # Create a temporary surface for each particle with proper alpha
    for particle in _mist_particles:
        # Calculate pulsing alpha
        pulse_alpha = particle['pulse_range'] * math.sin(particle['pulse_phase'])
        current_alpha = int(particle['alpha'] + pulse_alpha)
        current_alpha = max(10, min(60, current_alpha))  # Clamp alpha
        
        # Create particle surface with alpha
        size = int(particle['size'])
        particle_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
        
        # Draw mist particle (purple-tinted, semi-transparent)
        # Use a gradient circle for a soft mist look
        center = (size, size)
        radius = size
        
        # Draw multiple circles for a soft, foggy appearance
        for i in range(3):
            fade_radius = radius * (1.0 - i * 0.3)
            fade_alpha = int(current_alpha * (1.0 - i * 0.3))
            # Purple mist color - varying shades
            mist_color = (
                int(120 + fade_alpha * 0.5),  # Purple tint
                int(80 + fade_alpha * 0.3),
                int(140 + fade_alpha * 0.4),
                fade_alpha
            )
            pygame.draw.circle(particle_surf, mist_color, center, int(fade_radius))
        
        # Blit particle to screen
        screen.blit(particle_surf, (particle['x'] - size, particle['y'] - size))


# ===================== Fade Transition =====================
def start_fade_transition(gs, previous_screen_surface=None):
    """Start a fade transition: fade out from previous screen, then fade in to Book of Bound."""
    global _fade_state, _fade_alpha, _fade_speed, _previous_screen_surface
    
    _previous_screen_surface = previous_screen_surface
    _fade_state = "fade_out"  # Start by fading out
    _fade_alpha = 0.0  # Start transparent (will fade to black)
    _fade_speed = 255.0 / 0.5  # Fade out over 0.5 seconds
    _fade_surface = None


def update_fade(dt):
    """Update fade transition state. Returns True if still fading."""
    global _fade_state, _fade_alpha, _fade_speed
    
    if _fade_state is None:
        return False
    
    if _fade_state == "fade_out":
        # Fade out: increase alpha to 255 (black)
        _fade_alpha = min(255.0, _fade_alpha + _fade_speed * dt)
        if _fade_alpha >= 255.0:
            # Fade out complete, switch to fade in
            _fade_state = "fade_in"
            _fade_alpha = 255.0  # Start at black
            _fade_speed = 255.0 / 0.5  # Fade in over 0.5 seconds
            return True
    elif _fade_state == "fade_in":
        # Fade in: decrease alpha from 255 to 0
        _fade_alpha = max(0.0, _fade_alpha - _fade_speed * dt)
        if _fade_alpha <= 0.0:
            # Fade complete
            _fade_state = None
            _fade_alpha = 0.0
            return False
    
    return True


def draw_fade_overlay(screen):
    """Draw the fade overlay on top of the screen."""
    global _fade_state, _fade_alpha, _fade_surface
    
    if _fade_state is None or _fade_alpha <= 0:
        return
    
    # Create fade surface if needed
    # Use logical dimensions for consistency (per screen development guide)
    logical_size = (S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT)
    if _fade_surface is None or _fade_surface.get_size() != logical_size:
        _fade_surface = pygame.Surface(logical_size, pygame.SRCALPHA)
    
    # Draw fade overlay
    _fade_surface.fill((0, 0, 0, int(_fade_alpha)))
    screen.blit(_fade_surface, (0, 0))


# ===================== Lifecycle =====================
def enter(gs, audio_bank=None, previous_screen_surface=None, **_):
    """Initialize the screen with fade transition and music."""
    global _scroll_offset, _scrollbar_dragging, _mist_initialized, _fade_state, _selected_vessel_index
    
    _scroll_offset = 0
    _scrollbar_dragging = False
    _mist_initialized = False  # Reset mist so it reinitializes
    _selected_vessel_index = None  # Reset selection
    _init_mist()
    
    # Load vessel silhouettes if not already loaded
    _load_all_vessel_silhouettes()
    
    # Start fade transition
    start_fade_transition(gs, previous_screen_surface)
    
    # Handle music transition
    import systems.audio as audio_sys
    
    # Stop overworld music and play BookOfBound music
    if audio_bank:
        # Stop current music (overworld)
        audio_sys.stop_music(fade_ms=500)
        
        # Play BookOfBound music on repeat
        book_music_path = os.path.join("Assets", "Music", "Sounds", "BookOfBound.mp3")
        if os.path.exists(book_music_path):
            audio_sys.play_music(audio_bank, book_music_path, loop=True, fade_ms=800)
        else:
            # Try alternative path
            book_music_path = r"C:\Users\Frederik\Desktop\SummonersLedger\Assets\Music\Sounds\BookOfBound.mp3"
            if os.path.exists(book_music_path):
                audio_sys.play_music(audio_bank, book_music_path, loop=True, fade_ms=800)
    
    setattr(gs, "mode", MODE_BOOK_OF_BOUND)


def handle(events, gs, dt=None, audio_bank=None, **_):
    """Handle input events."""
    global _scroll_offset, _scrollbar_dragging, _drag_start_y, _drag_start_offset
    
    # Update mist animation
    if dt is not None:
        _update_mist(dt)
    
    # Update fade transition
    if dt is not None:
        update_fade(dt)
    
    # Convert mouse coordinates to logical
    screen_mx, screen_my = pygame.mouse.get_pos()
    mx, my = coords.screen_to_logical((screen_mx, screen_my))
    
    # Calculate right panel rect for scrollbar interaction
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    right_panel_rect = pygame.Rect(LEFT_PANEL_WIDTH, HEADER_HEIGHT, RIGHT_PANEL_WIDTH, sh - HEADER_HEIGHT)
    
    for e in events:
        # ESC to exit
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                # Handle music transition when exiting
                import systems.audio as audio_sys
                
                # Stop BookOfBound music
                audio_sys.stop_music(fade_ms=600)
                
                # Resume overworld music
                if audio_bank:
                    # Pick next overworld track
                    last_track = getattr(gs, "last_overworld_track", None)
                    nxt = audio_sys.pick_next_track(audio_bank, last_track, prefix="music")
                    if nxt:
                        audio_sys.play_music(audio_bank, nxt, loop=False, fade_ms=800)
                        gs.last_overworld_track = nxt
                
                return S.MODE_GAME
        
        # Mouse wheel scrolling
        if e.type == pygame.MOUSEWHEEL:
            # Scroll the grid - much faster and more responsive
            scroll_speed = 60  # How many pixels to scroll per wheel tick (much faster)
            max_scroll = _calculate_max_scroll()
            _scroll_offset = max(0, min(_scroll_offset - e.y * scroll_speed, max_scroll))
        
        # Mouse button down - check for clicks on grid squares or scrollbar
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            # Check scrollbar first
            thumb_rect = _get_scrollbar_thumb_rect(right_panel_rect)
            if thumb_rect and thumb_rect.collidepoint(mx, my):
                _scrollbar_dragging = True
                _drag_start_y = my
                _drag_start_offset = _scroll_offset
            else:
                # Check if clicking on a grid square
                clicked_index = _get_clicked_vessel_index(mx, my, right_panel_rect)
                if clicked_index is not None:
                    # Only allow selection of discovered vessels
                    if clicked_index < len(_vessel_silhouettes):
                        name, _, _ = _vessel_silhouettes[clicked_index]
                        if is_vessel_discovered(gs, name):
                            global _selected_vessel_index
                            _selected_vessel_index = clicked_index
                            print(f"📚 Selected vessel: {name}")
        
        # Mouse button up - stop dragging
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            _scrollbar_dragging = False
        
        # Mouse motion - update scroll if dragging
        if e.type == pygame.MOUSEMOTION and _scrollbar_dragging:
            # Calculate scroll based on mouse position within scrollbar track
            scrollbar_width = 20
            scrollbar_x = right_panel_rect.right - scrollbar_width - 5
            scrollbar_rect = pygame.Rect(scrollbar_x, right_panel_rect.y + 10, scrollbar_width, right_panel_rect.height - 20)
            
            # Track area (excluding arrow areas at top/bottom)
            track_top = scrollbar_rect.y + 10
            track_bottom = scrollbar_rect.bottom - 10
            track_height = track_bottom - track_top
            
            # Clamp mouse Y to track area
            mouse_y = max(track_top, min(my, track_bottom))
            
            # Calculate scroll position based on mouse position in track
            max_scroll = _calculate_max_scroll()
            if max_scroll > 0:
                # Calculate ratio of mouse position in track (0.0 = top, 1.0 = bottom)
                mouse_ratio = (mouse_y - track_top) / track_height
                
                # Convert to scroll offset
                new_offset = mouse_ratio * max_scroll
                _scroll_offset = max(0, min(new_offset, max_scroll))
    
    return None


def _calculate_max_scroll():
    """Calculate maximum scroll offset."""
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    grid_area_height = sh - HEADER_HEIGHT - (GRID_PADDING * 2)
    rows_visible = grid_area_height // (GRID_SQUARE_SIZE + GRID_SPACING)
    rows_total = (_total_entries + GRID_COLS - 1) // GRID_COLS  # Ceiling division
    max_scroll = max(0, rows_total - rows_visible) * (GRID_SQUARE_SIZE + GRID_SPACING)
    return max_scroll


def _get_clicked_vessel_index(mx: int, my: int, right_panel_rect: pygame.Rect) -> int | None:
    """Get the index of the vessel that was clicked, or None if none."""
    global _scroll_offset
    
    # Calculate grid position
    total_grid_width = (GRID_COLS * GRID_SQUARE_SIZE) + ((GRID_COLS - 1) * GRID_SPACING)
    grid_start_x = right_panel_rect.x + (right_panel_rect.width - total_grid_width) // 2
    grid_start_y = right_panel_rect.y + GRID_PADDING - _scroll_offset
    
    # Check each square
    for i in range(_total_entries):
        row = i // GRID_COLS
        col = i % GRID_COLS
        
        square_x = grid_start_x + col * (GRID_SQUARE_SIZE + GRID_SPACING)
        square_y = grid_start_y + row * (GRID_SQUARE_SIZE + GRID_SPACING)
        
        square_rect = pygame.Rect(square_x, square_y, GRID_SQUARE_SIZE, GRID_SQUARE_SIZE)
        
        # Check if click is within this square
        if square_rect.collidepoint(mx, my):
            return i
    
    return None


def draw(screen: pygame.Surface, gs, dt, **_):
    """Draw the Book of the Bound screen."""
    global _fade_state, _previous_screen_surface
    
    # During fade_out phase, draw previous screen instead
    if _fade_state == "fade_out" and _previous_screen_surface:
        # Draw previous screen (will be covered by fade overlay)
        screen.blit(_previous_screen_surface, (0, 0))
        # Draw fade overlay
        draw_fade_overlay(screen)
        return  # Don't draw Book of Bound content during fade out
    
    # Use logical resolution for all calculations
    sw, sh = S.LOGICAL_WIDTH, S.LOGICAL_HEIGHT
    
    # Get mouse position for hover detection
    screen_mx, screen_my = pygame.mouse.get_pos()
    mx, my = coords.screen_to_logical((screen_mx, screen_my))
    
    # Clear screen
    screen.fill(COLOR_BG)
    
    # ===================== MIST EFFECT =====================
    # Draw mist behind everything for atmospheric depth
    _draw_mist(screen)
    
    # ===================== HEADER =====================
    header_rect = pygame.Rect(0, 0, sw, HEADER_HEIGHT)
    # Draw header with subtle gradient effect (darker at edges)
    pygame.draw.rect(screen, COLOR_HEADER_BG, header_rect)
    # Add subtle border glow
    pygame.draw.rect(screen, (100, 60, 140), header_rect, 3)
    # Inner glow line
    inner_rect = header_rect.inflate(-6, -6)
    pygame.draw.rect(screen, (70, 40, 100), inner_rect, 1)
    
    # Title text with magical glow
    title_font = _get_font(48, bold=True)
    title_text = "Book of the Bound"
    # Main text
    title_surf = title_font.render(title_text, True, COLOR_HEADER_TEXT)
    title_rect = title_surf.get_rect(center=(sw // 2, HEADER_HEIGHT // 2))
    # Subtle glow effect (draw slightly offset copies)
    glow_surf = title_font.render(title_text, True, (120, 80, 160))
    screen.blit(glow_surf, (title_rect.x + 2, title_rect.y + 2))
    screen.blit(title_surf, title_rect)
    
    # ===================== LEFT PANEL (Details View) =====================
    left_panel_rect = pygame.Rect(0, HEADER_HEIGHT, LEFT_PANEL_WIDTH, sh - HEADER_HEIGHT)
    pygame.draw.rect(screen, COLOR_PANEL_BG, left_panel_rect)
    # Magical border with inner glow
    pygame.draw.rect(screen, COLOR_PANEL_BORDER, left_panel_rect, 3)
    inner_border = left_panel_rect.inflate(-6, -6)
    pygame.draw.rect(screen, (70, 40, 100), inner_border, 1)
    
    # Name box at top
    name_box_height = 60
    name_box_rect = pygame.Rect(
        left_panel_rect.x + 20,
        left_panel_rect.y + 20,
        left_panel_rect.width - 40,
        name_box_height
    )
    pygame.draw.rect(screen, COLOR_INFO_BOX, name_box_rect)
    pygame.draw.rect(screen, COLOR_INFO_BORDER, name_box_rect, 2)
    
    # Name text - show selected vessel name or "???"
    name_font = _get_font(32)
    if _selected_vessel_index is not None and _selected_vessel_index < len(_vessel_silhouettes):
        vessel_name, _, _ = _vessel_silhouettes[_selected_vessel_index]
        if is_vessel_discovered(gs, vessel_name):
            # Format name nicely (remove prefixes, make readable)
            name_text = _format_vessel_name(vessel_name)
        else:
            name_text = "???"  # Not discovered yet
    else:
        name_text = "???"  # No selection
    name_surf = name_font.render(name_text, True, COLOR_TEXT)
    name_surf_rect = name_surf.get_rect(center=name_box_rect.center)
    screen.blit(name_surf, name_surf_rect)
    
    # Sprite display area (large square below name)
    sprite_area_margin = 30
    sprite_area_size = min(
        left_panel_rect.width - (sprite_area_margin * 2),
        left_panel_rect.height - name_box_height - sprite_area_margin - 200  # Leave space for info boxes
    )
    sprite_area_rect = pygame.Rect(
        left_panel_rect.centerx - sprite_area_size // 2,
        name_box_rect.bottom + sprite_area_margin,
        sprite_area_size,
        sprite_area_size
    )
    
    # Draw sprite area with magical purple grid pattern
    pygame.draw.rect(screen, (30, 18, 45), sprite_area_rect)  # Dark purple background
    pygame.draw.rect(screen, COLOR_PANEL_BORDER, sprite_area_rect, 2)
    # Inner magical border
    inner_sprite_border = sprite_area_rect.inflate(-4, -4)
    pygame.draw.rect(screen, (80, 45, 110), inner_sprite_border, 1)
    
    # Draw subtle magical grid pattern (purple-tinted)
    grid_step = 20
    grid_color = (40, 25, 60)  # Dark purple grid lines
    for x in range(sprite_area_rect.left, sprite_area_rect.right, grid_step):
        pygame.draw.line(screen, grid_color, (x, sprite_area_rect.top), (x, sprite_area_rect.bottom))
    for y in range(sprite_area_rect.top, sprite_area_rect.bottom, grid_step):
        pygame.draw.line(screen, grid_color, (sprite_area_rect.left, y), (sprite_area_rect.right, y))
    
    # Draw magical concentric circles (purple glow)
    center_x, center_y = sprite_area_rect.center
    for radius in range(40, sprite_area_size // 2, 60):
        pygame.draw.circle(screen, (50, 30, 70), (center_x, center_y), radius, 1)
    
    # Draw selected vessel sprite if one is selected and discovered
    if _selected_vessel_index is not None and _selected_vessel_index < len(_vessel_silhouettes):
        vessel_name, _, category = _vessel_silhouettes[_selected_vessel_index]
        if is_vessel_discovered(gs, vessel_name):
            # Load and draw the actual sprite
            sprite = _load_vessel_sprite(vessel_name, category)
            if sprite:
                # Scale sprite to fit in the sprite area with padding
                padding = 40
                max_w = sprite_area_size - (padding * 2)
                max_h = sprite_area_size - (padding * 2)
                
                spr_w, spr_h = sprite.get_size()
                scale_x = max_w / max(spr_w, 1)
                scale_y = max_h / max(spr_h, 1)
                scale = min(scale_x, scale_y)
                
                scaled_w = int(spr_w * scale)
                scaled_h = int(spr_h * scale)
                scaled_sprite = pygame.transform.scale(sprite, (scaled_w, scaled_h))
                
                # Center in sprite area
                spr_x = sprite_area_rect.x + (sprite_area_rect.width - scaled_w) // 2
                spr_y = sprite_area_rect.y + (sprite_area_rect.height - scaled_h) // 2
                
                screen.blit(scaled_sprite, (spr_x, spr_y))
    
    # Info boxes at bottom
    info_box_height = 100  # Taller box to fit more text
    info_box_spacing = 15
    info_box_y = sprite_area_rect.bottom + sprite_area_margin
    
    # Define font for info boxes
    info_font = _get_font(24)
    
    # Dex text box - shows vessel description from .txt file (single box)
    dex_text_box_rect = pygame.Rect(
        left_panel_rect.x + 20,
        info_box_y,
        left_panel_rect.width - 40,
        info_box_height
    )
    pygame.draw.rect(screen, COLOR_INFO_BOX, dex_text_box_rect)
    pygame.draw.rect(screen, COLOR_INFO_BORDER, dex_text_box_rect, 2)
    
    # Get Dex text for selected vessel
    if _selected_vessel_index is not None and _selected_vessel_index < len(_vessel_silhouettes):
        vessel_name, _, category = _vessel_silhouettes[_selected_vessel_index]
        if is_vessel_discovered(gs, vessel_name):
            dex_text = _get_dex_text_for_vessel(vessel_name, category)
        else:
            dex_text = "???"
    else:
        dex_text = "???"
    
    # Render text with word wrapping in the single box
    dex_text_surf = _render_text_with_wrapping(dex_text, info_font, COLOR_TEXT, dex_text_box_rect.width - 30)
    # Center the text vertically in the box
    dex_text_rect = dex_text_surf.get_rect(midleft=(dex_text_box_rect.x + 15, dex_text_box_rect.centery))
    screen.blit(dex_text_surf, dex_text_rect)
    
    # ===================== RIGHT PANEL (Grid List) =====================
    right_panel_rect = pygame.Rect(LEFT_PANEL_WIDTH, HEADER_HEIGHT, RIGHT_PANEL_WIDTH, sh - HEADER_HEIGHT)
    pygame.draw.rect(screen, COLOR_PANEL_BG, right_panel_rect)
    # Magical border with inner glow
    pygame.draw.rect(screen, COLOR_PANEL_BORDER, right_panel_rect, 3)
    inner_border = right_panel_rect.inflate(-6, -6)
    pygame.draw.rect(screen, (70, 40, 100), inner_border, 1)
    
    # Calculate unique discovered species count (by class) - for "Owned" display
    unique_species_count = _count_unique_discovered_species(gs)
    
    # "Owned" box - positioned above the grid squares on the right panel
    owned_box_height = 40
    owned_box_width = 150
    owned_box_rect = pygame.Rect(
        right_panel_rect.centerx - owned_box_width // 2,  # Centered horizontally
        right_panel_rect.y + 20,  # Just below panel top
        owned_box_width,
        owned_box_height
    )
    pygame.draw.rect(screen, COLOR_INFO_BOX, owned_box_rect)
    pygame.draw.rect(screen, COLOR_INFO_BORDER, owned_box_rect, 2)
    
    owned_font = _get_font(24)
    owned_text = f"Owned: {unique_species_count}"
    owned_surf = owned_font.render(owned_text, True, COLOR_TEXT)
    owned_surf_rect = owned_surf.get_rect(center=owned_box_rect.center)
    screen.blit(owned_surf, owned_surf_rect)
    
    # Set clipping rectangle to prevent drawing outside the panel
    # Save the current clip state
    old_clip = screen.get_clip()
    
    # Clip to the right panel (accounting for padding and "Owned" box)
    # Start clipping below the "Owned" box so it stays visible
    clip_start_y = owned_box_rect.bottom + GRID_PADDING
    clip_rect = pygame.Rect(
        right_panel_rect.x + GRID_PADDING,
        clip_start_y,
        right_panel_rect.width - GRID_PADDING - 25,  # Leave space for scrollbar
        right_panel_rect.height - (clip_start_y - right_panel_rect.y) - GRID_PADDING
    )
    screen.set_clip(clip_rect)
    
    # Draw grid of squares - centered with proper spacing
    # Calculate total width needed for 2 columns: 2 squares + 1 gap
    total_grid_width = (GRID_COLS * GRID_SQUARE_SIZE) + ((GRID_COLS - 1) * GRID_SPACING)
    # Center the grid horizontally within the right panel
    grid_start_x = right_panel_rect.x + (right_panel_rect.width - total_grid_width) // 2
    # Start grid below the "Owned" box (fixed position, not affected by scroll)
    grid_base_y = owned_box_rect.bottom + GRID_PADDING
    grid_start_y = grid_base_y - _scroll_offset
    
    rows_total = (_total_entries + GRID_COLS - 1) // GRID_COLS  # Ceiling division
    
    for i in range(_total_entries):
        row = i // GRID_COLS
        col = i % GRID_COLS
        
        square_x = grid_start_x + col * (GRID_SQUARE_SIZE + GRID_SPACING)
        square_y = grid_start_y + row * (GRID_SQUARE_SIZE + GRID_SPACING)
        
        square_rect = pygame.Rect(square_x, square_y, GRID_SQUARE_SIZE, GRID_SQUARE_SIZE)
        
        # Only draw if visible (below the "Owned" box and within right panel bounds)
        if square_rect.bottom > grid_base_y and square_rect.top < right_panel_rect.bottom:
            # Draw square
            pygame.draw.rect(screen, COLOR_GRID_SQUARE, square_rect)
            pygame.draw.rect(screen, COLOR_GRID_SQUARE_BORDER, square_rect, 2)
            
            # Draw sprite or silhouette if available
            if i < len(_vessel_silhouettes):
                name, silhouette_surf, category = _vessel_silhouettes[i]
                
                # Check if vessel is discovered and selected
                is_discovered = is_vessel_discovered(gs, name)
                is_selected = (_selected_vessel_index == i)
                is_hovered = square_rect.collidepoint(mx, my) and is_discovered
                
                # Draw hover glow effect for discovered vessels (only if square is fully below "Owned" box)
                if is_hovered and not is_selected and square_rect.top >= grid_base_y:
                    # Create a glowing effect - outer glow with semi-transparent overlay
                    glow_rect = square_rect.inflate(6, 6)
                    # Create glow surface
                    glow_surf = pygame.Surface((glow_rect.w, glow_rect.h), pygame.SRCALPHA)
                    # Draw multiple concentric rectangles for soft glow
                    for glow_i in range(3):
                        glow_alpha = int(40 * (1.0 - glow_i / 3.0))
                        glow_color = (120, 80, 160, glow_alpha)
                        inner_glow = pygame.Rect(glow_i * 2, glow_i * 2, glow_rect.w - glow_i * 4, glow_rect.h - glow_i * 4)
                        pygame.draw.rect(glow_surf, glow_color, inner_glow, border_radius=6 - glow_i)
                    screen.blit(glow_surf, (glow_rect.x, glow_rect.y))
                    # Inner highlight border (bright purple)
                    highlight_rect = square_rect.inflate(2, 2)
                    pygame.draw.rect(screen, (150, 100, 200), highlight_rect, 2, border_radius=4)
                
                # Highlight selected square (stronger than hover)
                if is_selected:
                    # Draw selection highlight (stronger than hover)
                    highlight_rect = square_rect.inflate(4, 4)
                    pygame.draw.rect(screen, (120, 80, 160), highlight_rect, 3, border_radius=4)
                    # Add inner glow for selected
                    inner_rect = square_rect.inflate(2, 2)
                    pygame.draw.rect(screen, (140, 90, 180), inner_rect, 1, border_radius=4)
                
                # Scale to fit within the square (with padding)
                padding = 8
                max_size = GRID_SQUARE_SIZE - (padding * 2)
                
                # Get dimensions
                spr_w, spr_h = silhouette_surf.get_size()
                
                # Calculate scale to fit within max_size while maintaining aspect ratio
                scale_x = max_size / max(spr_w, 1)
                scale_y = max_size / max(spr_h, 1)
                scale = min(scale_x, scale_y)
                
                # Scale the sprite/silhouette
                scaled_w = int(spr_w * scale)
                scaled_h = int(spr_h * scale)
                
                # If discovered, load and display the actual sprite; otherwise use silhouette
                # Show full sprite once discovered (same behavior for all categories, including monsters)
                if is_discovered:
                    # Load the actual sprite
                    actual_sprite = _load_vessel_sprite(name, category)
                    if actual_sprite:
                        scaled_sprite = pygame.transform.scale(actual_sprite, (scaled_w, scaled_h))
                        # Center in the square
                        spr_x = square_rect.x + (square_rect.width - scaled_w) // 2
                        spr_y = square_rect.y + (square_rect.height - scaled_h) // 2
                        screen.blit(scaled_sprite, (spr_x, spr_y))
                    else:
                        # Fallback to silhouette if sprite loading fails
                        scaled_silhouette = pygame.transform.scale(silhouette_surf, (scaled_w, scaled_h))
                        sil_x = square_rect.x + (square_rect.width - scaled_w) // 2
                        sil_y = square_rect.y + (square_rect.height - scaled_h) // 2
                        screen.blit(scaled_silhouette, (sil_x, sil_y))
                else:
                    # Draw silhouette
                    scaled_silhouette = pygame.transform.scale(silhouette_surf, (scaled_w, scaled_h))
                    sil_x = square_rect.x + (square_rect.width - scaled_w) // 2
                    sil_y = square_rect.y + (square_rect.height - scaled_h) // 2
                    screen.blit(scaled_silhouette, (sil_x, sil_y))
    
    # Restore the original clip state
    screen.set_clip(old_clip)
    
    # Draw scrollbar
    _draw_scrollbar(screen, right_panel_rect)
    
    # ===================== FADE OVERLAY =====================
    # Draw fade overlay on top of everything
    draw_fade_overlay(screen)


def _get_scrollbar_thumb_rect(panel_rect: pygame.Rect):
    """Get the scrollbar thumb rectangle for hit testing."""
    scrollbar_width = 20
    scrollbar_x = panel_rect.right - scrollbar_width - 5
    scrollbar_rect = pygame.Rect(scrollbar_x, panel_rect.y + 10, scrollbar_width, panel_rect.height - 20)
    
    visible_height = panel_rect.height - 20
    total_height = max(1, _calculate_total_grid_height())
    panel_height = panel_rect.height - (GRID_PADDING * 2)
    
    if total_height > panel_height:
        thumb_height = max(20, int(visible_height * (panel_height / max(1, total_height))))
        thumb_height = min(thumb_height, visible_height - 20)
        
        max_scroll = _calculate_max_scroll()
        if max_scroll > 0:
            scroll_ratio = _scroll_offset / max_scroll
            thumb_y = scrollbar_rect.y + 10 + int((visible_height - thumb_height - 20) * scroll_ratio)
            
            return pygame.Rect(scrollbar_x + 2, thumb_y, scrollbar_width - 4, thumb_height)
    return None


def _draw_scrollbar(screen: pygame.Surface, panel_rect: pygame.Rect):
    """Draw scrollbar on the right side of the panel - magical purple theme."""
    scrollbar_width = 20
    scrollbar_x = panel_rect.right - scrollbar_width - 5
    scrollbar_rect = pygame.Rect(scrollbar_x, panel_rect.y + 10, scrollbar_width, panel_rect.height - 20)
    
    # Scrollbar background (dark purple)
    pygame.draw.rect(screen, (50, 30, 70), scrollbar_rect)
    pygame.draw.rect(screen, (80, 50, 100), scrollbar_rect, 1)
    
    # Calculate thumb size and position
    visible_height = panel_rect.height - 20
    total_height = max(1, _calculate_total_grid_height())
    panel_height = panel_rect.height - (GRID_PADDING * 2)
    thumb_height = max(20, int(visible_height * (panel_height / max(1, total_height))))
    thumb_height = min(thumb_height, visible_height - 20)
    
    if total_height > panel_height:
        max_scroll = _calculate_max_scroll()
        if max_scroll > 0:
            scroll_ratio = _scroll_offset / max_scroll
            thumb_y = scrollbar_rect.y + 10 + int((visible_height - thumb_height - 20) * scroll_ratio)
            
            thumb_rect = pygame.Rect(scrollbar_x + 2, thumb_y, scrollbar_width - 4, thumb_height)
            # Magical purple thumb (highlight if dragging)
            thumb_color = (120, 80, 160) if _scrollbar_dragging else (100, 60, 140)
            pygame.draw.rect(screen, thumb_color, thumb_rect)
            pygame.draw.rect(screen, (120, 80, 160), thumb_rect, 1)
    
    # Up arrow (purple)
    up_arrow_y = scrollbar_rect.y + 5
    up_arrow_points = [
        (scrollbar_x + scrollbar_width // 2, up_arrow_y),
        (scrollbar_x + 5, up_arrow_y + 8),
        (scrollbar_x + scrollbar_width - 5, up_arrow_y + 8),
    ]
    pygame.draw.polygon(screen, (120, 80, 160), up_arrow_points)
    
    # Down arrow (purple)
    down_arrow_y = scrollbar_rect.bottom - 13
    down_arrow_points = [
        (scrollbar_x + scrollbar_width // 2, down_arrow_y + 8),
        (scrollbar_x + 5, down_arrow_y),
        (scrollbar_x + scrollbar_width - 5, down_arrow_y),
    ]
    pygame.draw.polygon(screen, (120, 80, 160), down_arrow_points)


def _calculate_total_grid_height():
    """Calculate total height needed for the grid."""
    rows_total = (_total_entries + GRID_COLS - 1) // GRID_COLS
    return rows_total * (GRID_SQUARE_SIZE + GRID_SPACING) + GRID_PADDING * 2
