# ============================================================
# combat/team_randomizer.py
# - Randomizes enemy team size & members with bracketed scaling
# - Levels/jitter follow player bracket
# - Returns token filenames + generated stat blocks
# ============================================================

from __future__ import annotations
import os
import glob
import random
import random as _sysrandom
from typing import List, Dict, Optional, Tuple

from rolling.roller import Roller
from combat.vessel_stats import generate_vessel_stats_from_asset

# ----------------------------- Config -----------------------------
MAX_LEVEL = 50

_TOKEN_DIRS = (
    os.path.join("Assets", "VesselsMale"),
    os.path.join("Assets", "VesselsFemale"),
    os.path.join("Assets", "RareVessels"),
    os.path.join("Assets", "Starters"),
)

_TOKEN_PREFIXES = ("FToken", "MToken", "RToken", "StarterToken")


# ------------------------ Utility: player power -------------------

def highest_party_level(gs) -> int:
    try:
        party = getattr(gs, "party_vessel_stats", None) or []
        levels = []
        for st in party:
            if isinstance(st, dict):
                try:
                    levels.append(int(st.get("level", 1)))
                except Exception:
                    pass
        return max(1, min(MAX_LEVEL, max(levels) if levels else 1))
    except Exception:
        return 1

def scaled_enemy_level(gs, rng=None) -> int:
    """
    Get a scaled enemy level based on player's highest party level using tier system.
    Can be used for wild vessel encounters.
    """
    if rng is None:
        import random
        rng = Roller(random.randrange(1 << 30))
    
    player_max = highest_party_level(gs)
    bracket = _bracket_for_level(player_max)
    return _level_for_enemy(player_max, rng, bracket)


# ---------------- Probabilistic team size by level (1..6) ----------------
# Keyframes you can tune any time:
_KEYFRAMES = {
    1:  {1: 0.85, 2: 0.15},
    10: {1: 0.20, 2: 0.75, 3: 0.05},
    20: {1: 0.10, 2: 0.80, 3: 0.10},
    30: {2: 0.10, 3: 0.80, 4: 0.10},
    40: {3: 0.10, 4: 0.80, 5: 0.10},
    50: {4: 0.05, 5: 0.75, 6: 0.20},   # 👈 late-game: mostly 5, sometimes 6
}

_COUNTS = [1, 2, 3, 4, 5, 6]

def _interp_distributions(L: int) -> dict[int, float]:
    """Linear interpolation of categorical distributions across keyframes."""
    L = max(1, min(50, int(L)))

    if L in _KEYFRAMES:
        dist = {k: _KEYFRAMES[L].get(k, 0.0) for k in _COUNTS}
        s = sum(dist.values()) or 1.0
        return {k: v / s for k, v in dist.items()}

    lows = [k for k in _KEYFRAMES.keys() if k < L]
    highs = [k for k in _KEYFRAMES.keys() if k > L]
    lo = max(lows) if lows else min(_KEYFRAMES.keys())
    hi = min(highs) if highs else max(_KEYFRAMES.keys())

    if lo == hi:
        dist = {k: _KEYFRAMES[lo].get(k, 0.0) for k in _COUNTS}
        s = sum(dist.values()) or 1.0
        return {k: v / s for k, v in dist.items()}

    t = (L - lo) / float(hi - lo)

    dist_lo = {k: _KEYFRAMES[lo].get(k, 0.0) for k in _COUNTS}
    dist_hi = {k: _KEYFRAMES[hi].get(k, 0.0) for k in _COUNTS}
    dist = {k: (1.0 - t) * dist_lo[k] + t * dist_hi[k] for k in _COUNTS}
    s = sum(dist.values()) or 1.0
    return {k: v / s for k, v in dist.items()}

def _enemy_count_for_player_level(player_lvl: int, rng) -> int:
    """Sample enemy count from the interpolated distribution at this level."""
    dist = _interp_distributions(player_lvl)
    rfunc = getattr(rng, "random", _sysrandom.random)
    r = rfunc()
    acc = 0.0
    for count in _COUNTS:
        acc += dist[count]
        if r <= acc:
            return count
    return _COUNTS[-1]  # fallback



# ------------------------------ Brackets for level jitter ------------------------------

def _bracket_for_level(player_lvl: int) -> str:
    L = max(1, int(player_lvl))
    if L <= 10:  return "L1-10"
    if L <= 20:  return "L11-20"
    if L <= 30:  return "L21-30"
    if L <= 40:  return "L31-40"
    return "L41+"

def _level_for_enemy(player_lvl: int, rng, bracket: str) -> int:
    """Pick an enemy level using tier-based scaling relative to player's highest level."""
    rfunc = getattr(rng, "random", _sysrandom.random)
    L = max(1, int(player_lvl))
    
    # Tier-based probability system:
    # Common (65%): X-1 to X (slightly easier or same level)
    # Uncommon (25%): X+1 to X+2 (harder)
    # Rare (8%): X+3 to X+4 (challenging)
    # Very Rare (1.8%): X+5 to X+6 (very challenging)
    # Ultra Rare (0.2%): X+7+ (extreme, capped at MAX_LEVEL)
    
    roll = rfunc()
    
    if roll < 0.65:
        # Common: X-1 to X
        offset = -1 if rfunc() < 0.5 else 0  # 50/50 between X-1 and X
        level_offset = offset
    elif roll < 0.90:  # 65% + 25% = 90%
        # Uncommon: X+1 to X+2
        offset = 1 if rfunc() < 0.6 else 2  # 60% chance for +1, 40% for +2
        level_offset = offset
    elif roll < 0.98:  # 90% + 8% = 98%
        # Rare: X+3 to X+4
        offset = 3 if rfunc() < 0.6 else 4  # 60% chance for +3, 40% for +4
        level_offset = offset
    elif roll < 0.998:  # 98% + 1.8% = 99.8%
        # Very Rare: X+5 to X+6
        offset = 5 if rfunc() < 0.6 else 6  # 60% chance for +5, 40% for +6
        level_offset = offset
    else:  # 0.2% remaining
        # Ultra Rare: X+7 or more
        level_offset = 7 + int(rfunc() * 3)  # X+7 to X+9, but will be capped below
    
    final_level = max(1, min(MAX_LEVEL, L + level_offset))
    return final_level


# ---------------------- Utility: token scanning -------------------

def _scan_token_pool() -> Tuple[List[str], List[str], List[str]]:
    commons: List[str] = []
    rares: List[str] = []
    starters: List[str] = []

    for d in _TOKEN_DIRS:
        try:
            for path in glob.glob(os.path.join(d, "*.png")):
                name = os.path.basename(path)
                if not name.startswith(_TOKEN_PREFIXES):
                    continue
                if name.startswith(("FToken", "MToken")):
                    commons.append(name)
                elif name.startswith("RToken"):
                    rares.append(name)
                elif name.startswith("StarterToken"):
                    starters.append(name)
        except Exception:
            pass

    def _dedup(seq: List[str]) -> List[str]:
        seen, out = set(), []
        for x in seq:
            if x not in seen:
                seen.add(x); out.append(x)
        return out

    return _dedup(commons), _dedup(rares), _dedup(starters)


# ---------------------- Pick team member names --------------------

def _pick_token_names(
    n: int,
    rng,
    *,
    rare_chance: float = 0.12,
    allow_starters: bool = False,
    allow_dupes: bool = False,
) -> List[str]:
    """
    Choose N token filenames. Avoid dupes if possible; if pool is too small and
    allow_dupes is False, we still top up with dupes so the requested size is met.
    """
    commons, rares, starters = _scan_token_pool()
    pool_common = list(commons) + (list(starters) if allow_starters else [])

    if not pool_common and not rares:
        return []

    picks: List[str] = []
    rfunc = getattr(rng, "random", _sysrandom.random)
    choice = getattr(rng, "choice", _sysrandom.choice)

    # sample, avoiding dupes while possible
    for _ in range(n):
        use_rare = bool(rares) and (rfunc() < rare_chance)
        pool = rares if use_rare else pool_common

        if not pool:
            pool = pool_common if pool_common else rares
            if not pool:
                break

        take = choice(pool)
        picks.append(take)

        if not allow_dupes:
            try: pool.remove(take)
            except ValueError: pass
            # also remove from the other pool in case of overlap
            other = rares if pool is pool_common else pool_common
            try: other.remove(take)
            except ValueError: pass

        if not allow_dupes and not pool_common and not rares:
            break

    # top up (with dupes) if we came up short
    if len(picks) < n:
        combined = (commons + starters + rares) or picks
        for _ in range(n - len(picks)):
            picks.append(choice(combined))

    return picks[:n]


# -------------------------- Public API ---------------------------

def generate_enemy_team(
    gs,
    *,
    rng: Optional[Roller] = None,
    rare_chance: float = 0.12,
    allow_starters: bool = False,
    allow_dupes: bool = False,
) -> Dict[str, object]:
    """
    Build a randomized enemy team scaled to the player's strongest vessel
    using keyframed, probabilistic team sizes and bracketed level jitter.
    """
    # RNG: prefer caller's, else seed -> Roller, else system randomness
    if rng is None:
        seed = getattr(gs, "seed", None)
        rng = Roller(seed) if seed is not None else Roller(random.randrange(1 << 30))

    player_max = highest_party_level(gs)
    bracket = _bracket_for_level(player_max)
    desired_size = _enemy_count_for_player_level(player_max, rng)

    names = _pick_token_names(
        desired_size,
        rng,
        rare_chance=rare_chance,
        allow_starters=allow_starters,
        allow_dupes=allow_dupes,  # caller can opt into dupes
    )

    if not names:
        return {"names": [], "levels": [], "stats": []}

    # Levels per enemy using bracket jitter
    levels = [_level_for_enemy(player_max, rng, bracket) for _ in range(len(names))]

    # Stats per enemy; keep arrays aligned even if one fails
    stats: List[Dict] = []
    kept: List[Tuple[str, int]] = []
    for name, lvl in zip(names, levels):
        st = None
        try:
            st = generate_vessel_stats_from_asset(name, level=lvl, rng=rng)
        except Exception:
            try:
                st = generate_vessel_stats_from_asset(name, level=lvl)
            except Exception:
                st = None
        if st is not None:
            stats.append(st)
            kept.append((name, lvl))

    if not stats:
        # If everything failed, return empty team (battle code will handle gracefully)
        return {"names": [], "levels": [], "stats": []}

    # Final alignment with only successful entries
    names  = [n for (n, _) in kept]
    levels = [l for (_, l) in kept]

    return {
        "names": names,
        "levels": levels,
        "stats": stats,
    }
