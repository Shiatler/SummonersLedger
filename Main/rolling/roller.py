# ============================================================
# rolling/roller.py — generic dice roller + results + callback
# ============================================================
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Union, Callable, Literal

# --- Roll notifications (opt-in, framework-agnostic) ---
RollKind = Literal["check", "save", "attack", "damage", "notation", "d20"]
_roll_callback: Optional[Callable[[RollKind, object], None]] = None

def set_roll_callback(cb: Optional[Callable[[RollKind, object], None]]) -> None:
    """
    Register a callback that fires only when a public roll function is called
    with notify=True. Pass None to clear.
    """
    global _roll_callback
    _roll_callback = cb

# ===================== RNG / Seeding =========================
_rng = random.Random()

def set_seed(seed: int | None) -> None:
    """Seed the module-level RNG (pass None to reseed from system)."""
    _rng.seed(seed)

# ===================== Small Helpers =========================
def ability_mod(score: int) -> int:
    """D&D 5e style ability modifier: floor((score - 10) / 2)."""
    return math.floor((score - 10) / 2)

def _fmt_mod(n: int) -> str:
    """Format a signed modifier like '+3' or '-1' or '+0'."""
    return f"{n:+d}"

def _best_of_two(a: int, b: int, adv: int) -> int:
    """Return best/worst/neutral based on adv (+1 adv, -1 disadv, 0 normal)."""
    if adv > 0: return max(a, b)
    if adv < 0: return min(a, b)
    return a

# ===================== Result DataClasses ====================
@dataclass
class RollResult:
    total: int
    d20: int
    second_d20: Optional[int]
    modifier: int
    advantage: int  # +1 adv, -1 disadv, 0 normal
    nat20: bool
    nat1: bool
    breakdown: Dict[str, Union[int, str, bool]]
    text: str

@dataclass
class CheckResult:
    total: int
    success: Optional[bool]  # None if no DC given
    dc: Optional[int]
    parts: Dict[str, int]
    roll: RollResult
    text: str

@dataclass
class SaveResult:
    total: int
    success: bool
    dc: int
    parts: Dict[str, int]
    roll: RollResult
    text: str

@dataclass
class AttackResult:
    total: int
    hit: bool
    target_ac: int
    crit: bool
    fumble: bool
    roll: RollResult
    text: str

@dataclass
class DamageResult:
    total: int
    dice: Tuple[int, int]            # (count, die)
    rolls: List[int]
    bonus: int
    crit: bool
    crit_rule: str                   # 'double_dice' or 'double_total'
    text: str

@dataclass
class NotationResult:
    total: int
    rolls: List[int]
    bonus: int
    text: str

# ===================== Core Dice Rollers =====================
def roll_dice(n: int, die: int) -> Tuple[int, List[int]]:
    """Roll n d{die}. Returns (sum, list_of_individual_rolls)."""
    rolls = [_rng.randint(1, die) for _ in range(max(0, n))]
    return sum(rolls), rolls

def roll_ndm(n: int, m: int) -> int:
    """Compatibility helper: sum of rolling n dice with m faces."""
    s, _ = roll_dice(n, m)
    return s

def roll_d20(mod: int = 0, adv: int = 0, *, notify: bool = False) -> RollResult:
    """
    Roll a d20 with optional modifier and advantage/disadvantage.
    adv: +1 advantage, -1 disadvantage, 0 normal
    """
    r1 = _rng.randint(1, 20)
    r2 = _rng.randint(1, 20) if adv != 0 else None
    used = _best_of_two(r1, r2 if r2 is not None else r1, adv)
    total = used + mod
    nat20 = (used == 20)
    nat1  = (used == 1)

    breakdown = {
        "d20": r1,
        "second_d20": r2,
        "used": used,
        "mod": mod,
        "adv": adv,
        "nat20": nat20,
        "nat1": nat1,
    }
    parts = f"d20({used}) { _fmt_mod(mod) if mod else ''}".strip()
    adv_txt = " [ADV]" if adv > 0 else (" [DIS]" if adv < 0 else "")
    text = f"{parts}{adv_txt} = {total}"

    res = RollResult(
        total=total,
        d20=r1,
        second_d20=r2,
        modifier=mod,
        advantage=adv,
        nat20=nat20,
        nat1=nat1,
        breakdown=breakdown,
        text=text
    )
    if notify and _roll_callback:
        _roll_callback("d20", res)
    return res

# ===================== Ability/Skill Checks ==================
def roll_check(
    score: int,
    proficiency: bool = False,
    prof_bonus: int = 2,
    dc: Optional[int] = None,
    adv: int = 0,
    misc_bonus: int = 0,
    *,
    notify: bool = False,
) -> CheckResult:
    """
    Ability/Skill check:
      total = d20 + ability_mod(score) + (prof? prof_bonus: 0) + misc_bonus
      If dc provided, returns success True/False; else success=None.
    """
    mod = ability_mod(score)
    prof = prof_bonus if proficiency else 0
    base_mod = mod + prof + misc_bonus

    rr = roll_d20(mod=base_mod, adv=adv)
    success = (rr.total >= dc) if dc is not None else None

    parts = {
        "d20_used": rr.breakdown["used"],
        "ability_mod": mod,
        "prof_bonus": prof,
        "misc_bonus": misc_bonus,
    }
    dc_txt = f" vs DC {dc} {'✔' if success else '✖'}" if dc is not None else ""
    text = f"Check: {rr.text}{dc_txt}"

    res = CheckResult(
        total=rr.total,
        success=success,
        dc=dc,
        parts=parts,
        roll=rr,
        text=text
    )
    if notify and _roll_callback:
        _roll_callback("check", res)
    return res

# ===================== Saving Throws =========================
def roll_save(
    score: int,
    proficiency: bool,
    prof_bonus: int,
    dc: int,
    adv: int = 0,
    misc_bonus: int = 0,
    *,
    notify: bool = False,
) -> SaveResult:
    """Saving throw vs DC: total = d20 + ability_mod + prof? + misc_bonus."""
    mod = ability_mod(score)
    prof = prof_bonus if proficiency else 0
    base_mod = mod + prof + misc_bonus

    rr = roll_d20(mod=base_mod, adv=adv)
    success = rr.total >= dc

    parts = {
        "d20_used": rr.breakdown["used"],
        "ability_mod": mod,
        "prof_bonus": prof,
        "misc_bonus": misc_bonus,
    }
    text = f"Save: {rr.text} vs DC {dc} {'✔' if success else '✖'}"

    res = SaveResult(
        total=rr.total,
        success=success,
        dc=dc,
        parts=parts,
        roll=rr,
        text=text
    )
    if notify and _roll_callback:
        _roll_callback("save", res)
    return res

# ===================== Attacks (to-hit) ======================
def roll_attack(
    attack_bonus: int,
    target_ac: int,
    adv: int = 0,
    crit_range: int = 20,
    *,
    notify: bool = False,
) -> AttackResult:
    """Attack roll vs AC; nat-1 auto-miss; >=crit_range crits."""
    rr = roll_d20(mod=attack_bonus, adv=adv)
    used = rr.breakdown["used"]

    crit = (used >= crit_range)
    fumble = (used == 1)
    if crit:
        hit = True
    elif fumble:
        hit = False
    else:
        hit = rr.total >= target_ac

    adv_txt = " [ADV]" if rr.advantage > 0 else (" [DIS]" if rr.advantage < 0 else "")
    flags = " (CRIT!)" if crit else (" (FUMBLE!)" if fumble else "")
    text = f"Attack: d20({used}){adv_txt} { _fmt_mod(attack_bonus) if attack_bonus else ''} = {rr.total} vs AC {target_ac} -> {'HIT' if hit else 'MISS'}{flags}"

    res = AttackResult(
        total=rr.total,
        hit=hit,
        target_ac=target_ac,
        crit=crit,
        fumble=fumble,
        roll=rr,
        text=text
    )
    if notify and _roll_callback:
        _roll_callback("attack", res)
    return res

# ===================== Damage ================================
def roll_damage(
    dice: Tuple[int, int] | str,
    bonus: int = 0,
    crit: bool = False,
    crit_rule: str = "double_dice",
    *,
    notify: bool = False,
) -> DamageResult:
    """
    Damage:
      - dice as (count, die) or '2d6'
      - bonus added after dice
      - crit: 'double_dice' (roll twice dice) or 'double_total' (double final)
    """
    if isinstance(dice, str):
        cnt, d = _parse_simple_d(dice)
    else:
        cnt, d = dice

    if crit and crit_rule == "double_dice":
        s1, r1 = roll_dice(cnt, d)
        s2, r2 = roll_dice(cnt, d)
        rolls = r1 + r2
        total = s1 + s2 + bonus
    else:
        s, r = roll_dice(cnt, d)
        rolls = r
        total = s + bonus
        if crit and crit_rule == "double_total":
            total *= 2

    dice_txt = f"{cnt}d{d}"
    crit_txt = " (CRIT)" if crit else ""
    bonus_txt = f" { _fmt_mod(bonus) }" if bonus else ""
    text = f"Damage: {dice_txt} rolls {rolls}{bonus_txt}{crit_txt} = {total}"

    res = DamageResult(
        total=total,
        dice=(cnt, d),
        rolls=rolls,
        bonus=bonus,
        crit=crit,
        crit_rule=crit_rule,
        text=text
    )
    if notify and _roll_callback:
        _roll_callback("damage", res)
    return res

# ===================== Dice Notation =========================
def roll_notation(expr: str, *, notify: bool = False) -> NotationResult:
    """
    Roll dice by notation, e.g., "2d6+3".
    Returns total, list of dice, and applied bonus.
    """
    expr = expr.strip().lower().replace(" ", "")
    cnt, die, bonus = _parse_notation(expr)
    s, rolls = roll_dice(cnt, die)
    total = s + bonus
    btxt = f"{_fmt_mod(bonus)}" if bonus else ""
    text = f"{cnt}d{die}{btxt} -> {rolls}{(' ' + btxt) if btxt else ''} = {total}"

    res = NotationResult(total=total, rolls=rolls, bonus=bonus, text=text)
    if notify and _roll_callback:
        _roll_callback("notation", res)
    return res

# ===================== Notation Parsing ======================
def _parse_simple_d(s: str) -> Tuple[int, int]:
    """Parse very simple NdM (no modifiers). E.g., '2d6' -> (2,6), 'd8' -> (1,8)."""
    s = s.strip().lower()
    if 'd' not in s:
        raise ValueError(f"Invalid dice string '{s}', expected NdM like '2d6'")
    left, right = s.split('d', 1)
    cnt = int(left) if left else 1
    die = int(right)
    if cnt < 0 or die <= 0:
        raise ValueError(f"Invalid dice '{s}': count and die must be positive.")
    return cnt, die

def _parse_notation(expr: str) -> Tuple[int, int, int]:
    """Minimal parser for NdM[+/-B], e.g., '2d6+3', '1d8-1', 'd20'."""
    bonus = 0
    sign_pos = max(expr.rfind('+'), expr.rfind('-'))
    d_part = expr if sign_pos == -1 else expr[:sign_pos]
    if sign_pos != -1:
        bonus_str = expr[sign_pos:]
        bonus = int(bonus_str)
    cnt, die = _parse_simple_d(d_part)
    return cnt, die, bonus

# ===================== Roller Class (isolated RNG) ===========
class Roller:
    """Self-contained roller with its own RNG (no callbacks here)."""
    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    def _roll_dice(self, n: int, die: int) -> Tuple[int, List[int]]:
        rolls = [self._rng.randint(1, die) for _ in range(max(0, n))]
        return sum(rolls), rolls

    def roll_ndm(self, n: int, m: int) -> int:
        s, _ = self._roll_dice(n, m)
        return s

    def roll_d20(self, mod: int = 0, adv: int = 0) -> RollResult:
        r1 = self._rng.randint(1, 20)
        r2 = self._rng.randint(1, 20) if adv != 0 else None
        used = _best_of_two(r1, r2 if r2 is not None else r1, adv)
        total = used + mod
        nat20 = (used == 20)
        nat1  = (used == 1)
        breakdown = {"d20": r1, "second_d20": r2, "used": used, "mod": mod, "adv": adv, "nat20": nat20, "nat1": nat1}
        adv_txt = " [ADV]" if adv > 0 else (" [DIS]" if adv < 0 else "")
        parts = f"d20({used}) { _fmt_mod(mod) if mod else ''}".strip()
        text = f"{parts}{adv_txt} = {total}"
        return RollResult(total, r1, r2, mod, adv, nat20, nat1, breakdown, text)

    # These class helpers mirror the module functions but DON'T use callbacks
    def roll_check(self, score: int, proficiency: bool = False, prof_bonus: int = 2,
                   dc: Optional[int] = None, adv: int = 0, misc_bonus: int = 0) -> CheckResult:
        mod = ability_mod(score)
        prof = prof_bonus if proficiency else 0
        base_mod = mod + prof + misc_bonus
        rr = self.roll_d20(mod=base_mod, adv=adv)
        success = (rr.total >= dc) if dc is not None else None
        parts = {"d20_used": rr.breakdown["used"], "ability_mod": mod, "prof_bonus": prof, "misc_bonus": misc_bonus}
        dc_txt = f" vs DC {dc} {'✔' if success else '✖'}" if dc is not None else ""
        text = f"Check: {rr.text}{dc_txt}"
        return CheckResult(rr.total, success, dc, parts, rr, text)

    def roll_save(self, score: int, proficiency: bool, prof_bonus: int, dc: int,
                  adv: int = 0, misc_bonus: int = 0) -> SaveResult:
        mod = ability_mod(score)
        prof = prof_bonus if proficiency else 0
        base_mod = mod + prof + misc_bonus
        rr = self.roll_d20(mod=base_mod, adv=adv)
        success = rr.total >= dc
        parts = {"d20_used": rr.breakdown["used"], "ability_mod": mod, "prof_bonus": prof, "misc_bonus": misc_bonus}
        text = f"Save: {rr.text} vs DC {dc} {'✔' if success else '✖'}"
        return SaveResult(rr.total, success, dc, parts, rr, text)

    def roll_attack(self, attack_bonus: int, target_ac: int, adv: int = 0, crit_range: int = 20) -> AttackResult:
        rr = self.roll_d20(mod=attack_bonus, adv=adv)
        used = rr.breakdown["used"]
        crit = (used >= crit_range)
        fumble = (used == 1)
        if crit: hit = True
        elif fumble: hit = False
        else: hit = rr.total >= target_ac
        adv_txt = " [ADV]" if rr.advantage > 0 else (" [DIS]" if rr.advantage < 0 else "")
        flags = " (CRIT!)" if crit else (" (FUMBLE!)" if fumble else "")
        text = f"Attack: d20({used}){adv_txt} { _fmt_mod(attack_bonus) if attack_bonus else ''} = {rr.total} vs AC {target_ac} -> {'HIT' if hit else 'MISS'}{flags}"
        return AttackResult(rr.total, hit, target_ac, crit, fumble, rr, text)

    def roll_damage(self, dice: Tuple[int,int] | str, bonus: int = 0, crit: bool = False, crit_rule: str = "double_dice") -> DamageResult:
        if isinstance(dice, str): cnt, d = _parse_simple_d(dice)
        else: cnt, d = dice
        if crit and crit_rule == "double_dice":
            s1, r1 = self._roll_dice(cnt, d); s2, r2 = self._roll_dice(cnt, d)
            rolls = r1 + r2; total = s1 + s2 + bonus
        else:
            s, r = self._roll_dice(cnt, d); rolls = r; total = s + bonus
            if crit and crit_rule == "double_total": total *= 2
        dice_txt = f"{cnt}d{d}"; crit_txt = " (CRIT)" if crit else ""; bonus_txt = f" { _fmt_mod(bonus) }" if bonus else ""
        text = f"Damage: {dice_txt} rolls {rolls}{bonus_txt}{crit_txt} = {total}"
        return DamageResult(total, (cnt, d), rolls, bonus, crit, crit_rule, text)

    def roll_notation(self, expr: str) -> NotationResult:
        expr = expr.strip().lower().replace(" ", "")
        cnt, die, bonus = _parse_notation(expr)
        s, rolls = self._roll_dice(cnt, die)
        total = s + bonus
        btxt = f"{_fmt_mod(bonus)}" if bonus else ""
        text = f"{cnt}d{die}{btxt} -> {rolls}{(' ' + btxt) if btxt else ''} = {total}"
        return NotationResult(total, rolls, bonus, text)
