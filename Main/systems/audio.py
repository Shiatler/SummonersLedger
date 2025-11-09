# ============================================================
#  systems/audio.py — simple audio manager for Summoner's Ledger
# ============================================================

import os, random, math, array, pygame
import settings as S

DEFAULT_MUSIC_VOL = getattr(S, "MUSIC_VOLUME", 0.6)
DEFAULT_SFX_VOL   = getattr(S, "SFX_VOLUME", 0.8)

# --- Master SFX volume (0..1), controlled by Settings screen
_SFX_MASTER = DEFAULT_SFX_VOL

def get_sfx_volume() -> float:
    return max(0.0, min(1.0, _SFX_MASTER))

def set_sfx_volume(v: float, bank: "AudioBank|None" = None):
    """Set global SFX master volume and apply to currently loaded sounds."""
    global _SFX_MASTER
    _SFX_MASTER = max(0.0, min(1.0, float(v)))
    # Apply to loaded SFX in a bank (if provided)
    if bank and getattr(bank, "sfx", None):
        for s in bank.sfx.values():
            try:
                s.set_volume(_SFX_MASTER)
            except Exception:
                pass

_MUSIC_DIRS = [
    os.path.join("Assets", "Music"),
    os.path.join("Assets", "Music", "Shop"),  # Shop music directory
    os.path.join("Assets", "Tavern"),  # Tavern music directory
    os.path.join("Assets", "Audio", "Music"),
    os.path.join("Assets", "audio", "music"),
]
_SFX_DIRS = [
    os.path.join("Assets", "Music", "Sounds"),  # legacy layout
    os.path.join("Assets", "Music", "Shop"),   # Shop laugh sounds
    os.path.join("Assets", "Tavern"),  # Tavern sounds (footsteps)
    os.path.join("Assets", "Sounds"),
    os.path.join("Assets", "Audio", "SFX"),
    os.path.join("Assets", "audio", "sfx"),
    os.path.join("Assets", "Audio", "Effects"),
]

class AudioBank:
    def __init__(self):
        self.music = {}  # key -> path
        self.sfx   = {}  # key -> pygame.Sound

# ---------- init ----------
_PREINIT = dict(frequency=44100, size=-16, channels=2, buffer=512)

def init_audio():
    try:
        if not pygame.get_init():
            pygame.init()
        if not pygame.mixer.get_init():
            pygame.mixer.pre_init(**_PREINIT)
            pygame.mixer.init()
        pygame.mixer.set_num_channels(32)  # plenty for UI + loops
        pygame.mixer.music.set_volume(DEFAULT_MUSIC_VOL)
        print("🎵 Audio initialized")
    except Exception as e:
        print(f"⚠️ Audio init failed: {e}")

# ---------- helpers ----------
def _is_audio_file(n): return n.lower().endswith((".mp3",".ogg",".wav"))
def _norm_key(p): return os.path.splitext(os.path.basename(p))[0].lower()

def _load_sfx(full, vol):
    try:
        s = pygame.mixer.Sound(full)
        # Use current master, not the passed-in vol
        s.set_volume(get_sfx_volume())
        return s
    except Exception as e:
        print(f"⚠️ Could not load SFX '{full}': {e}")
        return None

def _alias_click(bank: AudioBank):
    """Map any suitable SFX to the canonical key 'click' if not present."""
    if "click" in bank.sfx:
        return
    # strong names first
    for k in ("ui_click", "button_click", "uiclick", "btn_click"):
        if k in bank.sfx:
            bank.sfx["click"] = bank.sfx[k]
            return
    # fuzzy
    for k in list(bank.sfx.keys()):
        if "click" in k or "button" in k:
            bank.sfx["click"] = bank.sfx[k]
            return

def _beep_fallback(volume=0.8, ms=80, freq=1000):
    """Generate a tiny sine beep so clicks always make noise."""
    try:
        if not pygame.mixer.get_init():
            return None
        sr = 44100
        length = int(sr * (ms/1000.0))
        amp = int(32767 * max(0.0, min(1.0, volume)))
        buf = array.array("h")
        for i in range(length):
            t = i / sr
            sample = int(amp * math.sin(2 * math.pi * freq * t))
            buf.append(sample); buf.append(sample)  # stereo
        return pygame.mixer.Sound(buffer=buf)
    except Exception:
        return None

def _play_on_free_channel(snd: pygame.mixer.Sound, fade_ms=0):
    ch = pygame.mixer.find_channel(True)  # force a free one
    if ch:
        ch.play(snd, fade_ms=fade_ms)
        return True
    return False

def play_sound(snd: pygame.mixer.Sound, vol_scale: float = 1.0, fade_ms: int = 0):
    """Play an already-loaded pygame.Sound honoring the SFX master volume."""
    if not snd:
        return
    try:
        snd.set_volume(max(0.0, min(1.0, get_sfx_volume() * float(vol_scale))))
        _play_on_free_channel(snd, fade_ms=fade_ms)
    except Exception as e:
        print(f"⚠️ play_sound failed: {e}")

# ---------- load ----------
def load_all() -> AudioBank:
    bank = AudioBank()

    # music
    for root_dir in _MUSIC_DIRS:
        if not os.path.isdir(root_dir): continue
        for root, _, files in os.walk(root_dir):
            if os.path.basename(root).lower() in ("sfx","sounds","effects"):  # avoid sfx under music
                continue
            for f in files:
                if not _is_audio_file(f): continue
                # Skip Footsteps.mp3 (it's a sound effect, not music)
                if f.lower() == "footsteps.mp3":
                    continue
                bank.music[_norm_key(f)] = os.path.join(root, f)

    # sfx
    for root_dir in _SFX_DIRS:
        if not os.path.isdir(root_dir): continue
        for root, _, files in os.walk(root_dir):
            for f in files:
                if not _is_audio_file(f): continue
                # Skip Tavern.mp3 (it's music, not SFX) - but include Footsteps.mp3
                if f.lower() == "tavern.mp3":
                    continue
                full = os.path.join(root, f)
                s = _load_sfx(full, DEFAULT_SFX_VOL)
                if s: bank.sfx[_norm_key(f)] = s

    _alias_click(bank)

    print(f"🎶 Loaded {len(bank.music)} music tracks and {len(bank.sfx)} SFX.")
    if "click" in bank.sfx:
        print("🔊 Click SFX available.")
    else:
        print("ℹ️ No click SFX found; will use generated beep fallback.")
    return bank

# ---------- music ----------
def play_music(bank: AudioBank, key: str, loop=True, fade_ms=800):
    path = bank.music.get(key.lower())
    if not path and os.path.exists(key):  # allow direct path
        path = key
    if not path:
        print(f"⚠️ Music '{key}' not found.")
        return
    try:
        vol = pygame.mixer.music.get_volume() or DEFAULT_MUSIC_VOL
        pygame.mixer.music.load(path)
        pygame.mixer.music.play(loops=(-1 if loop else 0), start=0.0, fade_ms=fade_ms)
        pygame.mixer.music.set_volume(vol)
        print(f"▶️ Playing music: {_norm_key(path)} (loop={'∞' if loop else 'no'})")
    except Exception as e:
        print(f"⚠️ Failed to play '{key}': {e}")

def stop_music(fade_ms=600):
    try:
        pygame.mixer.music.fadeout(fade_ms)
    except Exception:
        try: pygame.mixer.music.stop()
        except Exception: pass

def get_tracks(bank: AudioBank, prefix="music"):
    pfx = (prefix or "").lower()
    return [k for k in bank.music if k.startswith(pfx)] if pfx else list(bank.music.keys())

def pick_next_track(bank: AudioBank, last_key: str | None, prefix="music"):
    tracks = get_tracks(bank, prefix)
    if not tracks: return None
    if last_key in tracks and len(tracks) > 1:
        tracks = [t for t in tracks if t != last_key]
    return random.choice(tracks)

# ---------- sfx ----------
def play_sfx(bank: AudioBank, key: str, vol_scale: float = 1.0, fade_ms: int = 0):
    s = bank.sfx.get(key.lower())
    if not s:
        print(f"⚠️ SFX '{key}' not found.")
        return
    try:
        s.set_volume(max(0.0, min(1.0, get_sfx_volume() * vol_scale)))
        if not _play_on_free_channel(s, fade_ms=fade_ms):
            print("⚠️ No free audio channel for SFX.")
    except Exception as e:
        print(f"⚠️ Failed to play SFX '{key}': {e}")

def play_click(bank: AudioBank, vol_scale: float = 1.0, fade_ms: int = 8):
    if not pygame.mixer.get_init():
        init_audio()

    s = bank.sfx.get("click")
    used_fallback = False
    if s is None:
        s = _beep_fallback(volume=get_sfx_volume() * vol_scale)
        used_fallback = True
        if s: bank.sfx["_click_fallback"] = s

    if s:
        try:
            s.set_volume(max(0.0, min(1.0, get_sfx_volume() * vol_scale)))
            if not _play_on_free_channel(s, fade_ms=fade_ms):
                print("⚠️ No free channel for click.")
            else:
                print(f"🔊 click: {'fallback beep' if used_fallback else 'asset'}")
        except Exception as e:
            print(f"⚠️ play_click failed: {e}")
    else:
        print("ℹ️ No click SFX and fallback unavailable.")

# ---------- looping ----------
_active_loops = {}

def play_looping_sfx(bank: AudioBank, key: str):
    k = key.lower()
    s = bank.sfx.get(k)
    if not s:
        print(f"⚠️ Looping SFX '{k}' not found."); return
    ch = _active_loops.get(k)
    if ch and ch.get_busy(): return
    new_ch = pygame.mixer.find_channel(True)
    if new_ch:
        new_ch.play(s, loops=-1)
        # Ensure loop respects master SFX volume
        try:
            new_ch.set_volume(get_sfx_volume())
        except Exception:
            pass
        _active_loops[k] = new_ch
        print(f"🔁 Loop start: {k}")
    else:
        print(f"⚠️ No free mixer channel to loop '{k}'")

def stop_looping_sfx(bank: AudioBank, key: str, fade_ms: int = 200):
    k = key.lower()
    ch = _active_loops.pop(k, None)
    if ch:
        try: ch.fadeout(fade_ms)
        except Exception:
            try: ch.stop()
            except Exception: pass
        print(f"🛑 Loop stop: {k}")

# ---------- global helper for anywhere in the game ----------
_GLOBAL_BANK = None

def get_global_bank():
    """Return a global AudioBank (loads once if missing)."""
    global _GLOBAL_BANK
    if _GLOBAL_BANK is None:
        # Check if bank was already loaded in main.py (stored in settings)
        try:
            import settings as S
            if hasattr(S, 'AUDIO_BANK') and S.AUDIO_BANK is not None:
                _GLOBAL_BANK = S.AUDIO_BANK
                return _GLOBAL_BANK
        except Exception:
            pass
        # Fallback: load it ourselves if not available
        _GLOBAL_BANK = load_all()
    return _GLOBAL_BANK
