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

    # Monster vessels (VesselMonsters folder) - load at native size (no size constraint)
    # IMPORTANT: Only load actual monster sprites (Beholder.png, Dragon.png, etc.)
    # DO NOT load token files (TokenBeholder.png, TokenDragon.png, etc.)
    monsters = []
    monster_dir = os.path.join("Assets", "VesselMonsters")
    if os.path.exists(monster_dir):
        # Load all PNGs but filter out token files
        all_files = glob.glob(os.path.join(monster_dir, "*.png"))
        for path in all_files:
            name = os.path.splitext(os.path.basename(path))[0]
            # Skip token files (files starting with "Token")
            if name.startswith("Token"):
                continue
            try:
                sprite = load_image(path, size=None)  # Load at native size
                monsters.append((name, sprite))
            except Exception as e:
                print(f"⚠️ Failed to load monster sprite {path}: {e}")
        print(f"✅ Loaded {len(monsters)} monster sprites at native size (excluded token files)")
    else:
        print(f"⚠️ Monster directory not found: {monster_dir}")

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

    # Merchant ANIMATION frames (Assets/Animations/Merchant1..12.png)
    # Merchants are slightly bigger than player sprites (1.2x size)
    merchant_frames = []
    animations_dir = os.path.join("Assets", "Animations")
    MERCHANT_SIZE = (int(S.PLAYER_SIZE[0] * 1.2), int(S.PLAYER_SIZE[1] * 1.2))  # ~166x166
    try:
        for i in range(1, 13):  # Merchant1.png through Merchant12.png
            path = os.path.join(animations_dir, f"Merchant{i}.png")
            if os.path.exists(path):
                try:
                    surf = load_image(path, size=MERCHANT_SIZE)
                    merchant_frames.append(surf)
                except Exception as e:
                    print(f"⚠️ Failed to load merchant frame {path}: {e}")
    except Exception as e:
        print(f"⚠️ Merchant frame scan failed: {e}")

    # Tavern sprite (Assets/Tavern/Tavern.png)
    tavern_sprite = None
    tavern_dir = os.path.join("Assets", "Tavern")
    tavern_path = os.path.join(tavern_dir, "Tavern.png")
    TAVERN_SIZE = (int(S.PLAYER_SIZE[0] * 1.5), int(S.PLAYER_SIZE[1] * 1.5))  # 1.5x player size
    if os.path.exists(tavern_path):
        try:
            tavern_sprite = load_image(tavern_path, size=TAVERN_SIZE)
            print(f"✅ Loaded tavern sprite: {tavern_path}")
        except Exception as e:
            print(f"⚠️ Failed to load tavern sprite {tavern_path}: {e}")
    else:
        print(f"⚠️ Tavern sprite not found at: {tavern_path}")

    # Chest sprite (Assets/Map/Chest.png)
    chest_sprite = None
    chest_path = os.path.join(S.ASSETS_MAP_DIR, "Chest.png")
    CHEST_SIZE = (int(S.PLAYER_SIZE[0] * 1.5), int(S.PLAYER_SIZE[1] * 1.5))  # 1.5x player size (same as tavern)
    if os.path.exists(chest_path):
        try:
            chest_sprite = load_image(chest_path, size=CHEST_SIZE)
            print(f"✅ Loaded chest sprite: {chest_path}")
        except Exception as e:
            print(f"⚠️ Failed to load chest sprite {chest_path}: {e}")
    else:
        print(f"⚠️ Chest sprite not found at: {chest_path}")

    print(f"🧪 Loaded: {len(summoners)} summoners, {len(vessels)} vessels, {len(rare_vessels)} rare, {len(monsters)} monsters, {len(mist_frames)} mist frames, {len(merchant_frames)} merchant frames, {'1' if tavern_sprite else '0'} tavern, {'1' if chest_sprite else '0'} chest")
    return {
        "player": player,
        "summoners": summoners,
        "vessels": vessels,
        "rare_vessels": rare_vessels,
        "monsters": monsters,  # <-- monster sprites list
        "mist_frames": mist_frames,   # <-- frames list
        "merchant_frames": merchant_frames,  # <-- merchant frames list
        "tavern_sprite": tavern_sprite,  # <-- tavern sprite
        "chest_sprite": chest_sprite,  # <-- chest sprite
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
