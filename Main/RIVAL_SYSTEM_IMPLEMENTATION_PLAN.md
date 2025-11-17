# Rival System Implementation Plan

## Overview
Implement a Pokemon-style rival system where the player faces an opposite-gender rival throughout the game. The rival uses boss battle mechanics, has a persistent name, and appears at specific milestones.

---

## 1. Rival Selection & Naming

### 1.1 Rival Gender Assignment
- **Location**: `screens/char_select.py` or `screens/name_entry.py`
- **Logic**: 
  - If player chooses `male` → rival is `female`
  - If player chooses `female` → rival is `male`
- **Storage**: Store in `gs.rival_gender` (opposite of `gs.chosen_gender`)

### 1.2 Rival Name Entry Screen
- **New File**: `screens/rival_name_entry.py` (similar to `name_entry.py`)
- **Trigger**: After player name entry (`name_entry.py`), before `MASTER_OAK` screen
- **Flow**: `NAME_ENTRY` → `RIVAL_NAME_ENTRY` → `MASTER_OAK`
- **Features**:
  - Text input field (same UI as player name entry)
  - Title: "Enter Your Rival's Name"
  - Store in `gs.rival_name` (persistent through game)
  - Default fallback: Generate name using `name_generator.generate_summoner_name()` based on rival gender

### 1.3 Rival Starter Determination
- **Location**: `screens/black_screen.py` (Master Oak screen) or after starter selection
- **Logic**: Determine player's starter type (Barbarian/Druid/Rogue), then assign rival the weak type:
  - Player picks **Barbarian** (Fire) → Rival gets **Rogue** (Water) starter
  - Player picks **Druid** → Rival gets **Barbarian** starter  
  - Player picks **Rogue** → Rival gets **Druid** starter
- **Type Chart Reference**: Use `combat/type_chart.py` to determine weakness relationships
- **Storage**: 
  - `gs.rival_starter_class` (e.g., "rogue", "barbarian", "druid")
  - `gs.rival_starter_name` (e.g., "StarterRogue1", "StarterBarbarian3", etc.)
  - Pick random starter vessel from that class (similar to `_pick_random_starter()` in `black_screen.py`)

---

## 2. Rival Animation System

### 2.1 Rival Walking Animation
- **Location**: `main.py` or new `world/rival.py`
- **Animation Loading**:
  - Male rival: Use `Mwalk1.png`, `Mwalk2.png`, `Mwalk3.png` from `Assets/PlayableCharacters/`
  - Female rival: Use `Fwalk1.png`, `Fwalk2.png`, `Fwalk3.png` from `Assets/PlayableCharacters/`
  - Reuse `_load_walk_frames_from_files()` logic from `main.py` (lines 185-222)
- **Storage**: 
  - `gs.rival_walk_anim` (Animator instance, similar to `gs.walk_anim`)
  - `gs.rival_idle` (idle sprite)
  - `gs.rival_image` (current frame)

### 2.2 Rival Sprite Loading
- **Location**: `world/assets.py` or new helper function
- **Logic**: Load appropriate summoner sprite based on `gs.rival_gender`:
  - Male: Load from `Assets/SummonersMale/` (random or specific)
  - Female: Load from `Assets/SummonersFemale/` (random or specific)
- **Boss Sprite**: For boss battles, use `Assets/SummonersBoss/` sprites (same as regular bosses)

---

## 3. First Rival Encounter Scene

### 3.1 Trigger Point
- **Location**: `main.py` (after first buff selection completes)
- **Trigger**: After `buff_popup` finishes and `gs.first_overworld_blessing_given == True`
- **New Flag**: `gs.first_rival_encounter_complete = False`
- **Flow**: 
  1. Player selects blessing/curse/punishment/demonpact
  2. Buff popup closes
  3. Check if `gs.first_rival_encounter_complete == False`
  4. If false → trigger first rival encounter scene

### 3.2 Rival Walk-Down Animation
- **New File**: `screens/rival_intro.py` or integrate into `main.py`
- **Scene Flow**:
  1. **Lock player movement**: Set `gs.player_can_move = False` (or similar flag)
  2. **Spawn rival**: Position rival at top of map (off-screen above player)
  3. **Animate walk-down**: 
     - Rival starts at `y = player_pos.y - LOGICAL_HEIGHT` (above screen)
     - Target: `y = player_pos.y` (same Y as player)
     - Use `gs.rival_walk_anim` to animate walking
     - Move rival down at constant speed (e.g., 100 pixels/second)
  4. **Stop at player**: When rival reaches player's Y position, stop animation
  5. **Transition to battle**: Trigger boss battle

### 3.3 First Battle Setup
- **Location**: `world/bosses.py` or new `world/rival.py`
- **Battle Configuration**:
  - **Party Size**: 1 vessel (only starter)
  - **Starter Level**: 1
  - **Starter Vessel**: Use `gs.rival_starter_name` (pre-selected starter)
  - **Battle Type**: Mark as `gs.encounter_type = "RIVAL"` (or reuse "BOSS")
  - **Boss Intro**: Use boss VS screen (`screens/boss_vs.py`)

### 3.4 Battle Outcome Handling
- **Location**: `combat/battle.py` or `combat/summoner_battle.py`
- **Win**: Treat like normal boss win (award points, continue game)
- **Loss**: 
  - **DO NOT** go to death saves screen
  - Set all player vessels to 1 HP (keep them alive)
  - End battle gracefully
  - Continue game normally
- **Flag**: Set `gs.first_rival_encounter_complete = True` after battle ends

---

## 4. Subsequent Rival Encounters

### 4.1 Milestone Tracking
- **Location**: `world/bosses.py` or new `world/rival.py`
- **Milestones**: 
  - First encounter: After first buff selection (handled separately)
  - Second: 10,000 points
  - Third: 25,000 points
  - Fourth: 35,000 points
  - Fifth: 45,000 points
  - Continue: Every odd milestone (55k, 65k, 75k, etc.)
- **Pattern**: After 10k, pattern is: 25k, 35k, 45k, 55k, 65k, 75k... (every 10k starting from 25k)
- **Storage**: `gs.rival_encounter_milestones = [10000, 25000, 35000, 45000, ...]`
- **Tracking**: `gs.rival_encounters_completed = []` (list of milestone scores)

### 4.2 Rival Spawn Logic
- **Location**: `world/actors.py` or new `world/rival.py`
- **Function**: `check_and_spawn_rival(gs)` (similar to `check_and_spawn_bosses()`)
- **Logic**:
  1. Get current score from `systems.points.get_total_points(gs)`
  2. Check if score >= next milestone AND milestone not in `gs.rival_encounters_completed`
  3. If yes → spawn rival ahead of player
  4. Use same spawn logic as bosses (`spawn_boss_ahead()` in `actors.py`)

### 4.3 Rival Party Progression
- **Location**: `world/rival.py` or `world/bosses.py`
- **Function**: `generate_rival_team(gs, encounter_number)`
- **Party Sizes**:
  - Encounter 1 (first): 1 vessel (starter only, level 1)
  - Encounter 2 (10k): 3 vessels (starter + 2 others)
  - Encounter 3 (25k): 5 vessels (starter + 4 others)
  - Encounter 4+ (35k+): 6 vessels (starter + 5 others)
- **Starter Vessel**: Always include `gs.rival_starter_name` in party (level scales with encounter)
- **Other Vessels**: Use `combat/team_randomizer.generate_enemy_team()` logic, but ensure starter is always included

### 4.4 Rival Walk-Down Animation (Subsequent Encounters)
- **Same as first encounter**: Rival walks down from top of map
- **Player Lock**: Player cannot move during walk-down
- **Trigger**: When player gets close to rival spawn point (proximity detection)

---

## 5. Rival Boss Battle Integration

### 5.1 Boss VS Screen
- **Location**: `screens/boss_vs.py`
- **Modification**: Support rival encounters
- **Logic**: 
  - Check `gs.encounter_type == "RIVAL"` (or check `gs.rival_name`)
  - Use `gs.rival_name` instead of boss name
  - Load rival sprite (opposite gender summoner sprite, scaled for VS screen)
  - Use boss music (same as regular bosses)

### 5.2 Battle System Integration
- **Location**: `combat/summoner_battle.py` and `combat/battle.py`
- **Modifications**:
  - Detect rival encounters (`gs.encounter_type == "RIVAL"`)
  - Use rival name in battle UI
  - Use rival sprite in battle
  - Generate rival team using `generate_rival_team()`
  - Award points normally (rivals count as bosses for point multiplier)

### 5.3 Rival Sprite in Battle
- **Location**: `combat/summoner_battle.py`
- **Function**: `_load_rival_sprite(gs)` (similar to `_load_summoner_big()`)
- **Logic**:
  - Check `gs.rival_gender`
  - Load appropriate sprite from `Assets/SummonersBoss/`:
    - Male: `BSummonerM1.png` through `BSummonerM8.png` (random or deterministic)
    - Female: `BSummonerF1.png` through `BSummonerF3.png` (random or deterministic)
  - Scale to match boss sprite size (420px height)

---

## 6. Data Persistence

### 6.1 GameState Fields
Add to `game_state.py`:
```python
# Rival data
rival_gender: str = None  # "male" or "female"
rival_name: str = None  # Player-entered name
rival_starter_class: str = None  # "barbarian", "druid", or "rogue"
rival_starter_name: str = None  # e.g., "StarterRogue1"
rival_encounters_completed: List[int] = []  # List of milestone scores
first_rival_encounter_complete: bool = False

# Rival animation/sprites
rival_walk_anim: Animator = None
rival_idle: pygame.Surface = None
rival_image: pygame.Surface = None
rival_sprite: pygame.Surface = None  # Boss sprite for battles
```

### 6.2 Save System Integration
- **Location**: `systems/save_system.py`
- **Action**: Ensure all rival fields are saved/loaded
- **Fields to save**:
  - `rival_gender`
  - `rival_name`
  - `rival_starter_class`
  - `rival_starter_name`
  - `rival_encounters_completed`
  - `first_rival_encounter_complete`

---

## 7. File Structure

### New Files to Create:
1. `screens/rival_name_entry.py` - Rival name input screen
2. `world/rival.py` - Rival spawning, team generation, and encounter logic
3. `RIVAL_SYSTEM_IMPLEMENTATION_PLAN.md` - This plan document

### Files to Modify:
1. `screens/char_select.py` - Set `gs.rival_gender` after player selection
2. `screens/name_entry.py` - Transition to `RIVAL_NAME_ENTRY` instead of `MASTER_OAK`
3. `screens/black_screen.py` - Determine rival starter after player picks starter
4. `main.py` - 
   - Add rival walk-down animation logic
   - Trigger first rival encounter after buff selection
   - Add rival rendering in overworld
   - Handle rival encounter transitions
5. `world/actors.py` - Add `update_rivals()` and `draw_rivals()` functions (or create in `world/rival.py`)
6. `world/bosses.py` - Add rival milestone checking (or create separate system)
7. `combat/summoner_battle.py` - Support rival encounters
8. `combat/battle.py` - Handle rival battle loss (no death saves)
9. `screens/boss_vs.py` - Support rival VS screen
10. `systems/save_system.py` - Save/load rival data
11. `game_state.py` - Add rival fields

---

## 8. Implementation Order

### Phase 1: Rival Selection & Naming
1. Modify `char_select.py` to set `rival_gender`
2. Create `rival_name_entry.py` screen
3. Update `name_entry.py` to transition to rival name entry
4. Test name entry flow

### Phase 2: Rival Starter Assignment
1. Modify `black_screen.py` to determine rival starter based on player starter
2. Use type chart to determine weakness
3. Pick random starter vessel from rival's class
4. Store rival starter data

### Phase 3: Rival Animation & Sprites
1. Create `world/rival.py` with sprite loading functions
2. Load rival walking animations (male/female)
3. Load rival idle sprite
4. Test sprite loading

### Phase 4: First Rival Encounter
1. Add trigger after buff selection completes
2. Implement rival walk-down animation
3. Create `generate_rival_team()` for first encounter (1 vessel, level 1)
4. Integrate with boss VS screen
5. Handle battle win/loss (special loss handling)
6. Test first encounter flow

### Phase 5: Subsequent Rival Encounters
1. Implement milestone tracking system
2. Create `check_and_spawn_rival()` function
3. Implement `generate_rival_team()` for all encounter types (1/3/5/6 vessels)
4. Add rival to overworld update/draw loops
5. Test milestone encounters

### Phase 6: Battle Integration
1. Modify `summoner_battle.py` to detect rival encounters
2. Modify `battle.py` to handle rival loss (no death saves)
3. Update `boss_vs.py` to support rivals
4. Test battle flow

### Phase 7: Save System & Polish
1. Add rival fields to save/load system
2. Test save/load with rival data
3. Polish animations and transitions
4. Test full flow from character select to multiple rival encounters

---

## 9. Technical Considerations

### 9.1 Type Chart Weakness Logic
Based on `combat/type_chart.py`:
- **Barbarian** deals Bludgeoning, weak to Slashing and Psychic
- **Druid** deals Piercing, weak to Bludgeoning and Fire
- **Rogue** deals Slashing, weak to Piercing and Radiant

**Starter Weakness Mapping**:
- If player picks **Barbarian** → Rival gets **Rogue** (Rogue deals Slashing, which Barbarian is weak to)
- If player picks **Druid** → Rival gets **Barbarian** (Barbarian deals Bludgeoning, which Druid is weak to)
- If player picks **Rogue** → Rival gets **Druid** (Druid deals Piercing, which Rogue is weak to)

### 9.2 Rival Sprite Selection
- Use deterministic selection based on `rival_name` hash (same name = same sprite)
- Or use random selection but store in `gs.rival_sprite_path` for consistency

### 9.3 Player Movement Lock
- During rival walk-down, disable player input
- Use flag: `gs.rival_intro_active = True`
- Check flag in `world.update_player()` to prevent movement

### 9.4 Rival Team Generation
- Always include `gs.rival_starter_name` as first vessel
- For subsequent encounters, use `generate_enemy_team()` but replace first vessel with rival starter
- Scale starter level based on encounter number (use `scaled_enemy_level()` logic)

---

## 10. Testing Checklist

- [ ] Rival gender is opposite of player gender
- [ ] Rival name entry screen appears after player name entry
- [ ] Rival name persists through game
- [ ] Rival starter is correct type (weak against player starter)
- [ ] First rival encounter triggers after buff selection
- [ ] Rival walks down from top of map with animation
- [ ] Player cannot move during rival walk-down
- [ ] First battle has only starter vessel (level 1)
- [ ] Battle loss doesn't trigger death saves (vessels set to 1 HP)
- [ ] Battle win awards points normally
- [ ] Subsequent encounters trigger at correct milestones (10k, 25k, 35k, etc.)
- [ ] Party sizes progress correctly (1 → 3 → 5 → 6)
- [ ] Rival starter is always in party
- [ ] Boss VS screen shows rival name and sprite
- [ ] Rival data saves and loads correctly
- [ ] Multiple rival encounters work throughout game

---

## Summary

This plan covers:
1. ✅ Rival name selection (after player name)
2. ✅ Rival starter assignment (weak against player starter)
3. ✅ Rival boss battle logic (boss intro, boss sprite)
4. ✅ Rival animation (walking animation based on gender)
5. ✅ First encounter scene (walk-down after buff selection)
6. ✅ Subsequent encounters (milestone-based: 10k, 25k, 35k, 45k, etc.)
7. ✅ Battle progression (1 → 3 → 5 → 6 vessels)
8. ✅ Special loss handling (no death saves, 1 HP remaining)

The implementation will integrate seamlessly with existing boss battle systems while adding the unique rival walk-down animation and milestone-based encounters.

