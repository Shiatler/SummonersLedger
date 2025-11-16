# ============================================================
# systems/name_generator.py — Vessel Name Generator
# Generates random first + last names from text files
# Names are deterministic per token (same vessel = same name)
# ============================================================

import os
import random
from typing import Optional

# Cache for generated names (token_name -> "FirstName LastName")
_NAME_CACHE: dict[str, str] = {}

# Public: prefer custom_name in stats if present
def get_display_vessel_name(token_name: Optional[str], stats: Optional[dict]) -> str:
    """
    Resolve the display name for a vessel.
    - If stats contains non-empty 'custom_name', use that.
    - Otherwise fall back to deterministic generated name from token_name.
    """
    try:
        if isinstance(stats, dict):
            custom = (stats.get("custom_name") or "").strip()
            if custom:
                return custom
    except Exception:
        pass
    return generate_vessel_name(token_name or "")

# Cache for loaded name lists (vessels)
_FIRST_NAMES_MALE: Optional[list[str]] = None
_FIRST_NAMES_FEMALE: Optional[list[str]] = None
_LAST_NAMES: Optional[list[str]] = None

# Cache for loaded name lists (summoners)
_SUMMONER_NAMES_MALE: Optional[list[str]] = None
_SUMMONER_NAMES_FEMALE: Optional[list[str]] = None

def _load_name_file(path: str) -> list[str]:
    """Load names from a text file (one name per line, strip whitespace)."""
    names = []
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    name = line.strip()
                    if name:  # Skip empty lines
                        names.append(name)
    except Exception as e:
        print(f"⚠️ Failed to load names from {path}: {e}")
    return names

def _ensure_vessel_names_loaded():
    """Lazy-load vessel name files on first use."""
    global _FIRST_NAMES_MALE, _FIRST_NAMES_FEMALE, _LAST_NAMES
    
    if _FIRST_NAMES_MALE is None:
        path = os.path.join("Assets", "VesselsMale", "MVesselNames.txt")
        _FIRST_NAMES_MALE = _load_name_file(path)
        if not _FIRST_NAMES_MALE:
            print(f"⚠️ No male vessel names loaded from {path}")
    
    if _FIRST_NAMES_FEMALE is None:
        path = os.path.join("Assets", "VesselsFemale", "FVesselNames.txt")
        _FIRST_NAMES_FEMALE = _load_name_file(path)
        if not _FIRST_NAMES_FEMALE:
            print(f"⚠️ No female vessel names loaded from {path}")
    
    if _LAST_NAMES is None:
        path = os.path.join("Assets", "VesselsMale", "LastNames.txt")
        _LAST_NAMES = _load_name_file(path)
        if not _LAST_NAMES:
            print(f"⚠️ No last names loaded from {path}")

def _ensure_summoner_names_loaded():
    """Lazy-load summoner name files on first use."""
    global _SUMMONER_NAMES_MALE, _SUMMONER_NAMES_FEMALE
    
    if _SUMMONER_NAMES_MALE is None:
        path = os.path.join("Assets", "SummonersMale", "MSummonerNames.txt")
        _SUMMONER_NAMES_MALE = _load_name_file(path)
        # Fallback to vessel names if summoner names don't exist
        if not _SUMMONER_NAMES_MALE:
            _ensure_vessel_names_loaded()
            _SUMMONER_NAMES_MALE = _FIRST_NAMES_MALE
            if not _SUMMONER_NAMES_MALE:
                print(f"⚠️ No male summoner names loaded from {path} (using vessel names as fallback)")
    
    if _SUMMONER_NAMES_FEMALE is None:
        path = os.path.join("Assets", "SummonersFemale", "FSummonerNames.txt")
        _SUMMONER_NAMES_FEMALE = _load_name_file(path)
        # Fallback to vessel names if summoner names don't exist
        if not _SUMMONER_NAMES_FEMALE:
            _ensure_vessel_names_loaded()
            _SUMMONER_NAMES_FEMALE = _FIRST_NAMES_FEMALE
            if not _SUMMONER_NAMES_FEMALE:
                print(f"⚠️ No female summoner names loaded from {path} (using vessel names as fallback)")

def _deterministic_random(seed: int, min_val: int, max_val: int) -> int:
    """Generate a deterministic random number from a seed."""
    r = random.Random(seed)
    return r.randint(min_val, max_val)

def generate_vessel_name(token_name: str) -> str:
    """
    Generate a deterministic name for a vessel based on its token name.
    Same token name always produces the same name.
    Normalizes vessel/token names so "FVesselBarbarian1" and "FTokenBarbarian1" produce the same name.
    
    Args:
        token_name: Token filename like "FTokenBarbarian1" or "MTokenMonk2" or vessel name like "FVesselBarbarian1"
    
    Returns:
        "FirstName LastName" string
    """
    if not token_name:
        return "Unknown"
    
    # Normalize the name (FVessel/FToken -> same base, MVessel/MToken -> same base, etc.)
    # This ensures "FVesselBarbarian1" and "FTokenBarbarian1" generate the same name
    base = os.path.splitext(os.path.basename(token_name))[0] if token_name else ""
    # Convert vessel prefixes to token prefixes for consistent hashing
    if base.startswith("FVessel"):
        normalized = "FToken" + base[7:]  # Replace "FVessel" with "FToken"
    elif base.startswith("MVessel"):
        normalized = "MToken" + base[7:]  # Replace "MVessel" with "MToken"
    elif base.startswith("RVessel"):
        normalized = "RToken" + base[7:]  # Replace "RVessel" with "RToken"
    elif base.startswith("Starter"):
        normalized = "StarterToken" + base[7:]  # Replace "Starter" with "StarterToken"
    elif base.startswith("Token"):
        # Already a token (including monster tokens like "TokenBeholder")
        normalized = base
    elif base in ("Beholder", "Dragon", "Golem", "Nothic", "Ogre", "Owlbear", "Myconid"):
        # Monster name without prefix - add Token prefix
        normalized = "Token" + base
    else:
        normalized = base  # Already a token name or unknown format
    
    # Check cache first (check both original and normalized)
    if token_name in _NAME_CACHE:
        return _NAME_CACHE[token_name]
    if normalized in _NAME_CACHE:
        return _NAME_CACHE[normalized]
    
    # Determine gender / type from normalized prefix
    is_monster = normalized.startswith("Token") and normalized[5:] in ("Beholder", "Dragon", "Golem", "Nothic", "Ogre", "Owlbear", "Myconid")

    # Monsters keep their species name instead of generated names
    if is_monster:
        monster_name = normalized[5:]
        full_name = monster_name
        _NAME_CACHE[token_name] = full_name
        if normalized != token_name:
            _NAME_CACHE[normalized] = full_name
        return full_name

    # Load vessel name lists
    _ensure_vessel_names_loaded()
    
    # Determine gender from normalized prefix
    is_female = (normalized.startswith("FToken") or normalized.startswith("FVessel")) and not is_monster
    
    # Select appropriate first name list (monsters use male names)
    first_names = _FIRST_NAMES_FEMALE if is_female else _FIRST_NAMES_MALE
    
    # Use normalized name as seed for deterministic generation
    # This ensures "FVesselBarbarian1" and "FTokenBarbarian1" produce the same name
    seed = hash(normalized) & 0x7FFFFFFF  # Ensure positive
    
    # Generate first name
    if first_names:
        first_idx = _deterministic_random(seed, 0, len(first_names) - 1)
        first_name = first_names[first_idx]
    else:
        first_name = "Unknown"
    
    # Generate last name (use different seed offset)
    if _LAST_NAMES:
        last_seed = (seed * 31) & 0x7FFFFFFF  # Different seed for last name
        last_idx = _deterministic_random(last_seed, 0, len(_LAST_NAMES) - 1)
        last_name = _LAST_NAMES[last_idx]
    else:
        last_name = ""
    
    # Combine
    full_name = f"{first_name} {last_name}".strip()
    if not full_name:
        full_name = "Unknown Vessel"
    
    # Cache it under both original and normalized name for future lookups
    _NAME_CACHE[token_name] = full_name
    if normalized != token_name:
        _NAME_CACHE[normalized] = full_name
    return full_name

def generate_summoner_name(summoner_name: str) -> str:
    """
    Generate a deterministic name for a summoner based on its filename.
    Same summoner filename always produces the same name.
    
    Args:
        summoner_name: Filename like "MSummoner1" or "FSummoner5"
    
    Returns:
        "FirstName LastName" string
    """
    if not summoner_name:
        return "Unknown Summoner"
    
    # Check cache first
    cache_key = f"summoner_{summoner_name}"
    if cache_key in _NAME_CACHE:
        return _NAME_CACHE[cache_key]
    
    # Load summoner name lists
    _ensure_summoner_names_loaded()
    
    # Determine gender from prefix
    is_female = summoner_name.startswith("FSummoner") or summoner_name.lower().startswith("fsummoner")
    
    # Select appropriate first name list
    first_names = _SUMMONER_NAMES_FEMALE if is_female else _SUMMONER_NAMES_MALE
    
    # Use summoner name as seed for deterministic generation
    seed = hash(summoner_name) & 0x7FFFFFFF  # Ensure positive
    
    # Generate first name
    if first_names:
        first_idx = _deterministic_random(seed, 0, len(first_names) - 1)
        first_name = first_names[first_idx]
    else:
        first_name = "Unknown"
    
    # Generate last name (use different seed offset)
    _ensure_vessel_names_loaded()  # Last names are shared between vessels and summoners
    if _LAST_NAMES:
        last_seed = (seed * 31) & 0x7FFFFFFF  # Different seed for last name
        last_idx = _deterministic_random(last_seed, 0, len(_LAST_NAMES) - 1)
        last_name = _LAST_NAMES[last_idx]
    else:
        last_name = ""
    
    # Combine
    full_name = f"{first_name} {last_name}".strip()
    if not full_name:
        full_name = "Unknown Summoner"
    
    # Cache it
    _NAME_CACHE[cache_key] = full_name
    return full_name

def clear_cache():
    """Clear the name cache (useful for testing or reloading)."""
    global _NAME_CACHE
    _NAME_CACHE.clear()

