# ============================================================
#  world/assets.py — image + sprite loaders
# ============================================================

import os
import glob
import pygame
import settings as S


# ===================== Image Helpers ========================

def load_image(path: str, size=None) -> pygame.Surface:
    surf = pygame.image.load(path).convert_alpha()
    if size:
        surf = pygame.transform.scale(surf, size)
    return surf


def load_all_sprites(folders, pattern="*.png", size=None):
    """
    folders: list/tuple of folder STRINGS
    returns: list of (name, surface)
    If size is None, images load at native size.
    """
    results = []
    for folder in folders:
        for path in glob.glob(os.path.join(folder, pattern)):
            name = os.path.splitext(os.path.basename(path))[0]
            try:
                results.append((name, load_image(path, size)))
            except Exception as e:
                print(f"⚠️ Failed to load sprite {path}: {e}")
    return results



# ===================== Load All Assets =======================

def load_everything():
    # Choose a default player (male) so older code that expects "player" still works.
    default_player_path = os.path.join(S.ASSETS_PLAYABLE_DIR, S.PLAYER_MALE_FILE)
    player = None
    if os.path.exists(default_player_path):
        player = load_image(default_player_path, size=S.PLAYER_SIZE)
    else:
        print(f"⚠️ Missing default player: {default_player_path}")

    # Summoners (male + female) — scale to gameplay size
    summoners = load_all_sprites(
        [S.ASSETS_SUMMONERS_MALE_DIR, S.ASSETS_SUMMONERS_FEMALE_DIR],
        pattern="*Summoner*.png",
        size=S.PLAYER_SIZE
    )

    # Common vessels (male + female)
    vessels = load_all_sprites(
        [S.ASSETS_VESSELS_MALE_DIR, S.ASSETS_VESSELS_FEMALE_DIR],
        pattern="*Vessel*.png",
        size=S.PLAYER_SIZE
    )

    # Rare vessels
    rare_vessels = load_all_sprites(
        [S.ASSETS_VESSELS_RARE_DIR],
        pattern="RVessel*.png",
        size=S.PLAYER_SIZE
    )

    # Mist ANIMATION frames (Assets/Map/Mist1..9.png, or any Mist*.png)
    mist_frames = []
    try:
        for path in sorted(
            glob.glob(os.path.join(S.ASSETS_MAP_DIR, "Mist*.png")),
            key=lambda p: p.lower()
        ):
            try:
                surf = load_image(path, size=S.PLAYER_SIZE)  # match player size like before
                mist_frames.append(surf)
            except Exception as e:
                print(f"⚠️ Failed to load mist frame {path}: {e}")
    except Exception as e:
        print(f"⚠️ Mist frame scan failed: {e}")

    if not mist_frames:
        # Fallback: try old single-file mist.png (kept for backward compatibility)
        mist_path = os.path.join(S.ASSETS_MAP_DIR, "mist.png")
        if os.path.exists(mist_path):
            try:
                mist_frames = [load_image(mist_path, size=S.PLAYER_SIZE)]
            except Exception as e:
                print(f"⚠️ Failed to load fallback mist {mist_path}: {e}")

    print(f"🧪 Loaded: {len(summoners)} summoners, {len(vessels)} vessels, {len(rare_vessels)} rare, {len(mist_frames)} mist frames")
    return {
        "player": player,
        "summoners": summoners,
        "vessels": vessels,
        "rare_vessels": rare_vessels,
        "mist_frames": mist_frames,   # <-- frames list
    }



# ===================== Player Variants (RAW) =================

def load_player_variants():
    """Loads raw male/female sprites (no scaling) for menu; gameplay scales later."""
    variants = {}
    male_path   = os.path.join(S.ASSETS_PLAYABLE_DIR, S.PLAYER_MALE_FILE)
    female_path = os.path.join(S.ASSETS_PLAYABLE_DIR, S.PLAYER_FEMALE_FILE)

    if os.path.exists(male_path):
        variants["male"] = pygame.image.load(male_path).convert_alpha()
    else:
        print(f"⚠️ Missing {male_path}")

    if os.path.exists(female_path):
        variants["female"] = pygame.image.load(female_path).convert_alpha()
    else:
        print(f"⚠️ Missing {female_path}")

    return variants
