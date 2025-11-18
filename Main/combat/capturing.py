# ============================================================
# combat/capturing.py — DC-based capture checks (theme-fit)
# ------------------------------------------------------------
# Uses rolling/roller.py to perform a d20 capture check against
# a computed DC:
#   Base DC by level (progressive 12 → 20)
#   + HP % modifier (from +2 at 100% to –5 at 1–25%)
#   + Scroll modifier (Command 0, Sealing –2, Subjugation –4,
#                      Eternity = auto success)
# Rules:
#   - Nat 20 = auto success, Nat 1 = auto fail.
#   - Optional capture_bonus and advantage supported.
#   - Cosmetic “shakes” value derived from how far above/below DC you rolled.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Dict, Tuple

from rolling.roller import roll_d20

# -------- Level → Base DC (progressive; never goes down) ----
def base_dc_for_level(level: int) -> int:
    L = max(1, min(200, int(level)))
    if   1  <= L <= 10:   return 12
    elif 11 <= L <= 20:   return 13
    elif 21 <= L <= 30:   return 14
    elif 31 <= L <= 40:   return 15
    elif 41 <= L <= 50:   return 16
    elif 51 <= L <= 70:   return 17
    elif 71 <= L <= 100:  return 18
    elif 101 <= L <= 150: return 19
    else:                 return 20  # 151–200

# -------- HP% → DC adjustment --------------------------------
# 100%: +2, 76–99%: +1, 51–75%: +0, 26–50%: –3, 1–25%: –5
def hp_dc_adjust(cur_hp: int, max_hp: int) -> int:
    max_hp = max(1, int(max_hp))
    cur = max(0, min(int(cur_hp), max_hp))
    ratio = 0.0 if max_hp == 0 else (cur / max_hp)

    if ratio >= 1.0:          # 100%
        return +2
    elif ratio >= 0.76:       # 76–99%
        return +1
    elif ratio >= 0.51:       # 51–75%
        return 0
    elif ratio >= 0.26:       # 26–50%
        return -3
    elif ratio > 0.0:         # 1–25%
        return -5
    else:                     # 0 HP edge-case: treat as min band
        return -5

# -------- Scroll → DC adjustment ------------------------------
ScrollName = Literal["command", "sealing", "subjugation", "eternity"]

SCROLL_DC_ADJ: Dict[ScrollName, int] = {
    "command":      +2,  # Increased by 2 (was 0)
    "sealing":      0,   # Increased by 2 (was -2)
    "subjugation": -2,   # Increased by 2 (was -4)
    # "eternity": handled as auto-success
}

# -------- Optional: status → flat DC adjustment (tweakable) ---
Status = Optional[Literal["par", "psn", "brn", "slp", "frz"]]
STATUS_DC_ADJ: Dict[Optional[str], int] = {
    None: 0,
    "par": 0,
    "psn": 0,
    "brn": 0,
    "slp": 0,
    "frz": 0,
}

# -------- Inputs & Outputs -----------------------------------
@dataclass
class CaptureContext:
    level: int
    max_hp: int
    cur_hp: int
    scroll: ScrollName
    status: Status = None
    asset_name: str = None         # Asset name for monster detection

    # Player-side bonuses (feats, passives, temporary buffs)
    capture_bonus: int = 0         # flat bonus added to the d20 total
    advantage: int = 0             # +1 adv, -1 disadv, 0 normal

@dataclass
class CaptureResult:
    success: bool
    dc: int
    total: int            # d20 (best with adv/dis) + capture_bonus
    d20_used: int
    nat20: bool
    nat1: bool
    scroll: ScrollName
    hp_adj: int
    scroll_adj: int
    status_adj: int
    base_dc: int
    shakes: int           # 0..3 for UI flair
    text: str             # formatted breakdown (can be shown in log)

# -------- Monster Detection -----------------------------------
def is_monster(asset_name: str) -> bool:
    """Check if asset name represents a monster."""
    if not asset_name:
        return False
    
    monster_names = ["Dragon", "Owlbear", "Beholder", "Golem", "Ogre", "Nothic", "Myconid", "Chestmonster"]
    base = asset_name.split(".")[0].replace("_", "").lower()
    
    for monster in monster_names:
        if monster.lower() in base:
            return True
    return False

# -------- DC Computation -------------------------------------
def compute_capture_dc(ctx: CaptureContext, asset_name: str = None) -> Tuple[int, Dict[str, int]]:
    base = base_dc_for_level(ctx.level)
    h_adj = hp_dc_adjust(ctx.cur_hp, ctx.max_hp)
    s_adj = 0 if ctx.scroll == "eternity" else SCROLL_DC_ADJ.get(ctx.scroll, 0)
    st_adj = STATUS_DC_ADJ.get(ctx.status, 0)
    
    # Monster penalty: +10 at full HP, +5 at low HP (1-25%)
    monster_adj = 0
    if asset_name and is_monster(asset_name):
        hp_ratio = (ctx.cur_hp / ctx.max_hp) if ctx.max_hp > 0 else 1.0
        if hp_ratio >= 0.26:  # Above 25% HP
            monster_adj = 10  # Full penalty at high HP
        else:  # 1-25% HP
            monster_adj = 5   # Reduced penalty at low HP
    
    dc = base + h_adj + s_adj + st_adj + monster_adj
    dc = max(1, dc)  # safety
    return dc, {"base": base, "hp": h_adj, "scroll": s_adj, "status": st_adj, "monster": monster_adj}

# -------- Cosmetic shakes ------------------------------------
def _shakes_from_margin(margin: int) -> int:
    """
    How many 'shakes' to show before a break/click.
    Margin = total - DC.
      margin <= -5  -> 0
      -4..-1        -> 1
      0..+3         -> 2
      >= +4         -> 3
    """
    if margin <= -5: return 0
    if margin <= -1: return 1
    if margin <= 3:  return 2
    return 3

# -------- Public: attempt capture -----------------------------
def attempt_capture(ctx: CaptureContext) -> CaptureResult:
    # Master scroll = auto success
    if ctx.scroll == "eternity":
        base = base_dc_for_level(ctx.level)
        h_adj = hp_dc_adjust(ctx.cur_hp, ctx.max_hp)
        st_adj = STATUS_DC_ADJ.get(ctx.status, 0)
        # We still compute a DC for display, but force success.
        dc = max(1, base + h_adj + st_adj)  # no scroll adj applied here
        return CaptureResult(
            success=True,
            dc=dc,
            total=999,
            d20_used=20,
            nat20=True,
            nat1=False,
            scroll=ctx.scroll,
            hp_adj=h_adj,
            scroll_adj=-999,  # marked as "auto"
            status_adj=st_adj,
            base_dc=base,
            shakes=3,
            text=f"[Eternity] Auto-bind! (Base {base}, HP {h_adj}, Status {st_adj})"
        )

    # Compute DC (pass asset_name for monster detection)
    dc, parts = compute_capture_dc(ctx, ctx.asset_name)

    # Perform the roll using your roller (includes adv/disadv) **WITH NOTIFY**
    rr = roll_d20(mod=ctx.capture_bonus, adv=ctx.advantage, notify=True)
    used = rr.breakdown["used"]
    total = rr.total

    # Nat 20 / Nat 1 rules
    nat20 = rr.nat20
    nat1 = rr.nat1
    if nat20:
        success = True
    elif nat1:
        success = False
    else:
        success = (total >= dc)

    margin = total - dc
    shakes = _shakes_from_margin(margin) if success else max(0, _shakes_from_margin(margin))

    # Pretty log text
    adv_txt = " [ADV]" if ctx.advantage > 0 else (" [DIS]" if ctx.advantage < 0 else "")
    flags = " (CRIT!)" if nat20 else (" (FUMBLE!)" if nat1 else "")
    monster_txt = f", monster {parts.get('monster', 0):+d}" if parts.get('monster', 0) != 0 else ""
    text = (
        f"Capture{adv_txt}: d20({used}) + {ctx.capture_bonus:+d} = {total} "
        f"vs DC {dc} -> {'SUCCESS' if success else 'FAIL'}{flags}  "
        f"[base {parts['base']}, hp {parts['hp']:+d}, scroll {parts['scroll']:+d}, status {parts['status']:+d}{monster_txt}]"
    )

    return CaptureResult(
        success=success,
        dc=dc,
        total=total,
        d20_used=used,
        nat20=nat20,
        nat1=nat1,
        scroll=ctx.scroll,
        hp_adj=parts["hp"],
        scroll_adj=parts["scroll"],
        status_adj=parts["status"],
        base_dc=parts["base"],
        shakes=shakes,
        text=text,
    )
