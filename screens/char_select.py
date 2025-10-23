# =============================================================
# screens/char_select.py
# =============================================================

import pygame
import settings as S
from systems import ui
from systems import party_ui
from systems import audio as audio_sys
from systems import save_system as saves
from combat.vessel_stats import generate_vessel_stats_from_asset

def enter(gs, screen=None, fonts=None, menu_bg=None, audio_bank=None, player_variants=None, **_):
    # Cache variants so draw can always find them
    if player_variants:
        gs._player_variants = player_variants
    # reset buttons each time we enter
    gs._char_male_btn = None
    gs._char_fem_btn  = None
    gs._char_buttons  = None

def draw(screen, gs, fonts=None, menu_bg=None, player_variants=None, **_):
    # Prefer current deps, fallback to cached set on gs
    pv = player_variants or getattr(gs, "_player_variants", {}) or {}

    male_img   = pv.get("male")
    female_img = pv.get("female")

    male_btn, female_btn = ui.draw_character_select(
        screen, S.WIDTH, S.HEIGHT, fonts, S.APP_NAME,
        male_img, female_img,
        bg_surface=menu_bg
    )
    # store for handler (support both old and new names)
    gs._char_male_btn = male_btn
    gs._char_fem_btn  = female_btn
    gs._char_buttons  = (male_btn, female_btn)

def handle(events, gs, screen=None, fonts=None, audio_bank=None, **_):
    for event in events:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            audio_sys.play_click(audio_bank)
            return S.MODE_MENU

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            male = getattr(gs, "_char_male_btn", None)
            fem  = getattr(gs, "_char_fem_btn", None)

            if male and male.clicked(event):
                audio_sys.play_click(audio_bank)
                gs.chosen_gender = "male"
                # (optional) prime token so HUD can show correct portrait later
                gs.player_token = party_ui.load_player_token("male")
                gs.player_name = ""
                gs._name_state = {"text": "", "blink_timer": 0.0, "cursor_on": True}
                return "NAME_ENTRY"

            if fem and fem.clicked(event):
                audio_sys.play_click(audio_bank)
                gs.chosen_gender = "female"
                gs.player_token = party_ui.load_player_token("female")
                gs.player_name = ""
                gs._name_state = {"text": "", "blink_timer": 0.0, "cursor_on": True}
                return "NAME_ENTRY"

    return None

#---- Helpers
def _assign_starter_and_roll(gs, token_name: str, token_surf):
    """
    Put starter in slot 0, roll stats once if absent, then save permanently.
    """
    # Ensure lists exist
    if not getattr(gs, "party_slots", None):
        gs.party_slots = [None] * 6
    if not getattr(gs, "party_slots_names", None):
        gs.party_slots_names = [None] * 6
    if not getattr(gs, "party_vessel_stats", None):
        gs.party_vessel_stats = [None] * 6

    # Assign art/name to slot 0
    gs.party_slots[0] = token_surf
    gs.party_slots_names[0] = token_name

    # Roll once (only if not rolled yet)
    if gs.party_vessel_stats[0] is None:
        try:
            stats = generate_vessel_stats_from_asset(token_name, level=1)
            # store plain dict so it serializes cleanly
            gs.party_vessel_stats[0] = stats
            # persist immediately
            saves.save_game(gs)
            print(f"✅ Starter stats rolled and saved for {token_name}")
        except Exception as e:
            print(f"⚠️ Failed to roll starter stats for {token_name}: {e}")

