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
        ch = pygame.mixer.find_channel(True)
        ch.play(sfx)
    else:
        audio_sys.play_click()  # fallback small sound
