# Monster Encounter Implementation Plan

## Overview
Implement a new rare encounter type (0.5% spawn chance) featuring powerful Monster vessels that use the wild_vessel.py battle system but with significantly enhanced stats and harder capture DCs.

---

## Phase 1: Spawn System & Asset Loading

### 1.1 Add Monster Spawn Logic
**File**: `Main/world/actors.py`
- Add `spawn_monster_ahead(gs, start_x)` function similar to `spawn_vessel_shadow_ahead`
- Add `monsters_on_map` list to game state (similar to `vessels_on_map`)
- Add `update_monsters(gs, dt, player_half)` function to detect collisions
- Add `draw_monsters(screen, cam, gs)` function for rendering

**File**: `Main/main.py` - `try_trigger_encounter()`
- Add 0.5% monster spawn chance BEFORE vessel chance
- Adjust probability ranges:
  - Merchant: 10%
  - Tavern: 5%
  - **Monster: 0.5%** ← NEW
  - Vessel: 54.5% (reduced from 55%)
  - Summoner: 30%

### 1.2 Asset Loading
**File**: `Main/world/assets.py` or create `Main/world/monster_assets.py`
- Load monster sprites from `Assets/VesselMonsters/`:
  - Beholder.png
  - Dragon.png
  - Golem.png
  - Myconid.png
  - Nothic.png
  - Ogre.png
  - Owlbear.png
- Return list of (asset_name, sprite) tuples similar to vessel loading

---

## Phase 2: Stat Generation & Multipliers

### 2.1 Monster Stat Multipliers
**File**: `Main/combat/vessel_stats.py` or create `Main/combat/monster_stats.py`

**Multiplier Configuration**:
```python
MONSTER_STAT_MULTIPLIERS = {
    "Dragon": 3.0,      # 200% stronger = 3x stats, 3x HP
    "Owlbear": 2.5,    # 150% stronger = 2.5x stats, 2.5x HP
    "Beholder": 2.0,   # 100% stronger = 2x stats, 2x HP
    "Golem": 1.4,      # 40% stronger = 1.4x stats, 1.4x HP
    "Ogre": 1.3,       # 30% stronger = 1.3x stats, 1.3x HP
    "Nothic": 1.3,     # 30% stronger = 1.3x stats, 1.3x HP
    "Myconid": 1.2,    # 20% stronger = 1.2x stats, 1.2x HP
}
```

### 2.2 Modified Stat Generation
**Function**: `generate_monster_stats_from_asset()` (new function)
- Detect if asset_name contains monster name (e.g., "Dragon.png")
- Extract monster type and get multiplier
- Call normal `generate_vessel_stats_from_asset()` first
- Apply multiplier to:
  - All ability scores (STR, DEX, CON, INT, WIS, CHA)
  - HP (both max and current)
  - AC (indirectly through DEX/CON modifiers)
- Keep level scaling intact

**Example**: If normal vessel rolls 10 in all stats → Dragon gets 30 in all stats

---

## Phase 3: Capture Difficulty

### 3.1 Enhanced Capture DC
**File**: `Main/combat/capturing.py`

**Modifications**:
- Add `is_monster(asset_name: str) -> bool` helper
- Modify `compute_capture_dc()` to add monster penalty:
  - **Base DC penalty**: +10 for monsters (on top of normal DC)
  - **Full HP**: DC = base_dc + hp_adj + scroll_adj + **+10 monster penalty**
    - Result: Even Scroll of Command has DC > 20 at full HP
  - **Low HP (1-25%)**: DC = base_dc + hp_adj + scroll_adj + **+5 monster penalty**
    - Result: DC ~20 when low HP (as requested)
- Scroll of Eternity: Still auto-success (no change)

**DC Examples** (Level 1 monster at full HP):
- Scroll of Command: Base 12 + HP +2 + Scroll 0 + Monster +10 = **DC 24** (impossible)
- Scroll of Sealing: Base 12 + HP +2 + Scroll -2 + Monster +10 = **DC 22**
- Scroll of Subjugation: Base 12 + HP +2 + Scroll -4 + Monster +10 = **DC 20**

**DC Examples** (Level 1 monster at 1-25% HP):
- Scroll of Command: Base 12 + HP -5 + Scroll 0 + Monster +5 = **DC 12** (possible)
- Scroll of Sealing: Base 12 + HP -5 + Scroll -2 + Monster +5 = **DC 10**
- Scroll of Subjugation: Base 12 + HP -5 + Scroll -4 + Monster +5 = **DC 8**

---

## Phase 4: Monster-Specific Moves

### 4.1 Move Registry Structure
**File**: `Main/combat/moves.py`

Add to `_MOVE_REGISTRY`:
```python
"dragon": [
    Move("dragon_l1_claw_swipe", "Claw Swipe", "Basic dragon claw attack.", (2, 6), "STR", True, 0, 20),
    Move("dragon_l10_fire_breath", "Fire Breath", "Breathe a cone of fire.", (3, 8), "CON", True, 0, 12),
    Move("dragon_l20_tail_slam", "Tail Slam", "Crushing tail strike.", (4, 10), "STR", True, 0, 6),
    Move("dragon_l30_wing_buffet", "Wing Buffet", "Powerful wing strike.", (5, 10), "STR", True, 0, 3),
    Move("dragon_l40_dragon_roar", "Dragon Roar", "Terrifying roar that weakens foes.", (6, 12), "CHA", True, 0, 1),
],
"owlbear": [
    Move("owlbear_l1_claw", "Claw", "Sharp claw attack.", (1, 8), "STR", True, 0, 20),
    Move("owlbear_l10_beak_peck", "Beak Peck", "Precise beak strike.", (2, 8), "DEX", True, 0, 12),
    Move("owlbear_l20_hunters_pounce", "Hunter's Pounce", "Leap and strike.", (3, 10), "STR", True, 0, 6),
    Move("owlbear_l30_savage_maul", "Savage Maul", "Frenzied mauling attack.", (4, 10), "STR", True, 0, 3),
    Move("owlbear_l40_primal_rage", "Primal Rage", "Unleash primal fury.", (5, 12), "STR", True, 0, 1),
],
"beholder": [
    Move("beholder_l1_eye_ray", "Eye Ray", "Weak magical ray from central eye.", (1, 6), "INT", True, 0, 20),
    Move("beholder_l10_paralyzing_ray", "Paralyzing Ray", "Ray that can paralyze.", (2, 8), "INT", True, 0, 12),
    Move("beholder_l20_disintegration_ray", "Disintegration Ray", "Powerful disintegration beam.", (3, 10), "INT", True, 0, 6),
    Move("beholder_l30_antimagic_cone", "Antimagic Cone", "Suppress magic in cone.", (4, 10), "INT", True, 0, 3),
    Move("beholder_l40_all_seeing_eye", "All-Seeing Eye", "Ultimate beholder power.", (6, 12), "INT", True, 0, 1),
],
"golem": [
    Move("golem_l1_fist_slam", "Fist Slam", "Heavy stone fist strike.", (1, 10), "STR", True, 0, 20),
    Move("golem_l10_stone_throw", "Stone Throw", "Hurl a boulder.", (2, 10), "STR", True, 0, 12),
    Move("golem_l20_ground_slam", "Ground Slam", "Slam ground creating shockwave.", (3, 12), "STR", True, 0, 6),
    Move("golem_l30_immovable_object", "Immovable Object", "Become unstoppable force.", (4, 12), "CON", True, 0, 3),
    Move("golem_l40_titan_strike", "Titan Strike", "Ultimate golem attack.", (5, 12), "STR", True, 0, 1),
],
"ogre": [
    Move("ogre_l1_club_smash", "Club Smash", "Brutal club attack.", (1, 8), "STR", True, 0, 20),
    Move("ogre_l10_belly_slam", "Belly Slam", "Crushing body slam.", (2, 10), "STR", True, 0, 12),
    Move("ogre_l20_rage_swing", "Rage Swing", "Wild swinging attack.", (3, 10), "STR", True, 0, 6),
    Move("ogre_l30_brutal_charge", "Brutal Charge", "Charge and crush.", (4, 10), "STR", True, 0, 3),
    Move("ogre_l40_berserker_fury", "Berserker Fury", "Unleash ogre rage.", (5, 12), "STR", True, 0, 1),
],
"nothic": [
    Move("nothic_l1_claw_scratch", "Claw Scratch", "Sharp claw attack.", (1, 6), "DEX", True, 0, 20),
    Move("nothic_l10_weird_insight", "Weird Insight", "Psychic damage from knowledge.", (2, 8), "INT", True, 0, 12),
    Move("nothic_l20_rotting_gaze", "Rotting Gaze", "Gaze that causes decay.", (3, 10), "INT", True, 0, 6),
    Move("nothic_l30_paranoid_whisper", "Paranoid Whisper", "Maddening whispers.", (4, 10), "CHA", True, 0, 3),
    Move("nothic_l40_eldritch_sight", "Eldritch Sight", "See through all defenses.", (5, 12), "INT", True, 0, 1),
],
"myconid": [
    Move("myconid_l1_spore_puff", "Spore Puff", "Weak spore attack.", (1, 4), "CON", True, 0, 20),
    Move("myconid_l10_poison_spores", "Poison Spores", "Toxic spore cloud.", (2, 6), "CON", True, 0, 12),
    Move("myconid_l20_animating_spores", "Animating Spores", "Spores that sap strength.", (3, 8), "CON", True, 0, 6),
    Move("myconid_l30_pacifying_spores", "Pacifying Spores", "Spores that calm enemies.", (4, 8), "WIS", True, 0, 3),
    Move("myconid_l40_spore_burst", "Spore Burst", "Massive spore explosion.", (5, 10), "CON", True, 0, 1),
],
```

### 4.2 Class Name Normalization
**File**: `Main/combat/moves.py` - `_normalize_class()`
- Add monster class keys to `_CLASS_KEYS` dict:
  - "dragon" → "dragon"
  - "owlbear" → "owlbear"
  - "beholder" → "beholder"
  - "golem" → "golem"
  - "ogre" → "ogre"
  - "nothic" → "nothic"
  - "myconid" → "myconid"

### 4.3 Primary Stats for Monsters
**File**: `Main/combat/stats.py` - `PRIMARY_STAT` dict
- Add monster primary stats:
  - "dragon": "STR" (physical attacks) or "CON" (breath weapons)
  - "owlbear": "STR"
  - "beholder": "INT"
  - "golem": "STR"
  - "ogre": "STR"
  - "nothic": "INT" or "DEX"
  - "myconid": "CON"

---

## Phase 5: Encounter Flow Integration

### 5.1 Monster Encounter Detection
**File**: `Main/world/actors.py` - `update_monsters()`
- When player collides with monster:
  - Set `gs.encounter_type = "MONSTER"` (similar to boss encounters)
  - Load monster sprite and asset name
  - Generate monster stats using `generate_monster_stats_from_asset()`
  - Set `gs.encounter_name`, `gs.encounter_sprite`, `gs.encounter_stats`
  - Set `gs.encounter_token_name` to monster asset name
  - Trigger encounter popup

### 5.2 Battle System Integration
**File**: `Main/combat/wild_vessel.py`
- Already compatible! The system uses `gs.encounter_stats` which will contain monster stats
- Moves system will automatically use monster moves via class name matching
- Capture system will use enhanced DC via monster detection

### 5.3 Name Generation
**File**: `Main/systems/name_generator.py`
- Ensure `generate_vessel_name()` handles monster asset names
- May need to add monster-specific name generation or use generic names

---

## Phase 6: Testing & Balance

### 6.1 Test Cases
1. **Spawn Rate**: Verify 0.5% spawn chance (approximately 1 in 200 encounters)
2. **Stat Scaling**: Verify multipliers apply correctly (e.g., Dragon has 3x stats)
3. **Capture DC**: Test at full HP (should be DC > 20) and low HP (DC ~20)
4. **Moves**: Verify monster moves unlock at correct levels
5. **Battle Flow**: Ensure monsters work seamlessly with wild_vessel.py

### 6.2 Balance Adjustments
- Monitor monster difficulty vs player power
- Adjust multipliers if needed
- Tune capture DC penalties if too easy/hard
- Review move damage scaling

---

## Implementation Order

1. ✅ **Phase 1**: Spawn system & asset loading
2. ✅ **Phase 2**: Stat generation & multipliers
3. ✅ **Phase 3**: Capture difficulty
4. ✅ **Phase 4**: Monster moves
5. ✅ **Phase 5**: Encounter flow integration
6. ✅ **Phase 6**: Testing & balance

---

## Files to Create/Modify

### New Files:
- `Main/world/monster_assets.py` (optional - can integrate into assets.py)
- `Main/combat/monster_stats.py` (optional - can integrate into vessel_stats.py)

### Modified Files:
- `Main/world/actors.py` - Add monster spawn/update/draw functions
- `Main/main.py` - Add 0.5% monster spawn chance
- `Main/combat/vessel_stats.py` - Add monster stat multiplier logic
- `Main/combat/capturing.py` - Add monster DC penalties
- `Main/combat/moves.py` - Add monster move registries
- `Main/combat/stats.py` - Add monster primary stats
- `Main/systems/name_generator.py` - Handle monster names (if needed)

---

## Notes

- Monsters use same battle system as wild vessels (single enemy encounter)
- Monster moves follow same progression pattern: L1 → L10 → L20 → L30 → L40
- Capture difficulty scales with HP% (harder at full HP, easier when low)
- Scroll of Eternity remains auto-success for monsters
- Monster stats scale multiplicatively (all stats × multiplier, HP × multiplier)

