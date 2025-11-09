# =============================================================
# combat/btn/run_action.py — "Run" button + escape flow
# (now honors SFX master volume for success SFX)
# =============================================================
import os
import pygame
import settings as S
from rolling import roller
from ._btn_layout import rect_at, load_scaled
from ._btn_draw import draw_icon_button
from systems import audio as audio_sys  # CLICK + SFX via master

_ICON = None
_RECT = None
_RUN_SFX = os.path.join("Assets", "Music", "Sounds", "RunAway.mp3")

def _ensure():
    global _ICON, _RECT
    if _RECT is None:
        _RECT = rect_at(1, 1)  # bottom-right
    if _ICON is None:
        _ICON = load_scaled(os.path.join("Assets", "Map", "BRunUI.png"))

def draw_button(screen: pygame.Surface):
    _ensure()
    draw_icon_button(screen, _ICON, _RECT)

def is_hovering_button(pos: tuple[int, int]) -> bool:
    """
    Check if the mouse position is hovering over the run button.
    Returns True if hovering over the button, False otherwise.
    
    Args:
        pos: Mouse position tuple (x, y) in logical coordinates
    """
    _ensure()
    if _RECT is None:
        return False
    return _RECT.collidepoint(pos)

def handle_click(pos, gs) -> bool:
    """Kick off a DEX check via roller; resolution deferred until popup closes."""
    _ensure()
    if not _RECT.collidepoint(pos):
        return False

    # Click feedback (master-controlled)
    audio_sys.play_click(audio_sys.get_global_bank())

    dex_score = getattr(gs, "dexterity", 10)
    result = roller.roll_check(dex_score, dc=10, notify=True)
    print(f"🏃 Run Attempt: {result.text}")
    st = getattr(gs, "_wild", None)
    if st is not None:
        st["pending_run"] = ("escape" if result.success else "fail")

    gs._turn_ready = False  # <-- mark turn consumed
    return True


def _play_runaway_sfx():
    """Play the escape jingle honoring the SFX master volume."""
    bank = audio_sys.get_global_bank()
    # Try bank key first (RunAway.mp3 -> "runaway")
    try:
        audio_sys.play_sfx(bank, "runaway")
        return
    except Exception:
        pass
    # Fallback: load the exact file and play via master helper
    try:
        if os.path.exists(_RUN_SFX):
            snd = pygame.mixer.Sound(_RUN_SFX)
            audio_sys.play_sound(snd)  # <- uses master
    except Exception as e:
        print(f"⚠️ RunAway SFX error: {e}")

def resolve_after_popup(gs):
    """Called by wild_vessel.handle after the roll popup is dismissed."""
    st = getattr(gs, "_wild", None)
    if not st:
        return None
    outcome = st.pop("pending_run", None)
    if outcome == "escape":
        _play_runaway_sfx()

        try:
            pygame.mixer.music.fadeout(300)
        except Exception:
            pass

        gs._went_to_wild = False
        gs.in_encounter = False
        gs.encounter_stats = None
        from rolling.roller import set_roll_callback
        set_roll_callback(None)
        return S.MODE_GAME
    return None
