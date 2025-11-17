# ============================================================
# rolling/sfx.py
# ============================================================
import os
import pygame
from systems import audio as audio_sys

DICE_SFX_PATH = os.path.join("Assets", "Music", "Sounds", "dice_roll.mp3")

def play_dice():
    """Play dice roll sound if available."""
    if os.path.exists(DICE_SFX_PATH):
        sfx = pygame.mixer.Sound(DICE_SFX_PATH)
        # Use audio_sys.play_sound to respect volume settings
        audio_sys.play_sound(sfx)
    else:
        audio_sys.play_click()  # fallback small sound
