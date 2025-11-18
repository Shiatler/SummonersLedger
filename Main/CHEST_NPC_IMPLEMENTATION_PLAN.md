# Chest NPC Implementation Plan

## Overview
Implement a new overworld NPC (chest) with 5% spawn chance. When opened, 85% chance to receive an item (weighted distribution), 15% chance to trigger a monster battle with Chestmonster (75% stat boost, 4 balanced moves).

---

## Phase 1: Chest Spawn System & Asset Loading

### 1.1 Add Chest Spawn Logic
**File**: `Main/world/actors.py`
- Add `spawn_chest_ahead(gs, start_x, chest_sprite)` function similar to `spawn_tavern_ahead`
- Add `chests_on_map` list to game state (similar to `taverns_on_map`)
- Add `update_chests(gs, dt, player_half)` function to detect proximity (for popup)
- Add `draw_chests(screen, cam, gs)` function for rendering
- Update `_y_too_close()` to include chests in separation check

**File**: `Main/main.py` - `try_trigger_encounter()`
- Add 5% chest spawn chance BEFORE vessel chance
- Adjust probability ranges:
  - Merchant: 10%
  - Tavern: 5%
  - **Chest: 5%** ← NEW
  - Monster: 0.5% (if exists)
  - Vessel: 49.5% (reduced from 55% or 54.5%)
  - Summoner: 30%

### 1.2 Asset Loading
**File**: `Main/world/assets.py`
- Load chest sprite from `Assets/Map/Chest.png`
- Return sprite for chest spawning
- Chest should be similar size to tavern (1.5x player size)

---

## Phase 2: Chest Proximity Detection & Popup

### 2.1 Proximity Detection
**File**: `Main/world/actors.py` - `update_chests()`
- Check if player is near chest (same logic as tavern/merchant)
- Store `gs.near_chest` when player is in proximity
- Use same size multiplier as tavern (1.5x player size)

### 2.2 Popup Display
**File**: `Main/main.py` - Drawing section
- Add `_draw_chest_popup()` function (similar to `_draw_barkeeper_popup()`)
- Display "Press E to Open Chest" when `gs.near_chest` is set
- Use same popup style as merchant/tavern (speech bubble with triangle)
- Position popup above chest sprite

---

## Phase 3: Chest Opening Logic

### 3.1 E Key Handling
**File**: `Main/main.py` - Event handling
- Check for `pygame.K_e` keypress when `gs.near_chest` is set
- Block if other modals are open (bag, party manager, ledger, shop, rest, etc.)
- Call `_open_chest(gs)` function

### 3.2 Chest Opening Function
**File**: `Main/main.py` - New function `_open_chest(gs)`
- Roll random: 85% item, 15% battle
- If item: Call `_give_chest_item(gs)` and remove chest from map
- If battle: Set up Chestmonster encounter and remove chest from map
- Play sound effect (chest opening sound if available)

---

## Phase 4: Item Reward System

### 4.1 Item Distribution Weights
**File**: `Main/main.py` - New function `_give_chest_item(gs)`

**Item Weight Distribution** (total = 100%):
- `scroll_of_command`: 25% (highest chance)
- `scroll_of_mending`: 25% (highest chance)
- `scroll_of_healing`: 15%
- `scroll_of_regeneration`: 10%
- `scroll_of_revivity`: 8%
- `scroll_of_sealing`: 7%
- `scroll_of_subjugation`: 5%
- `rations`: 3%
- `alcohol`: 2%
- **EXCLUDE**: `scroll_of_eternity` (cannot be obtained)

### 4.2 Add Item to Inventory
- Use same logic as `buff_applicator.apply_inventory_blessing()`
- Add 1x of selected item to `gs.inventory`
- Show notification/feedback (optional: result card or simple print)
- Format: `gs.inventory[item_id] = gs.inventory.get(item_id, 0) + 1`

---

## Phase 5: Chestmonster Battle System

### 5.1 Chestmonster Stat Generation
**File**: `Main/combat/vessel_stats.py` or `Main/combat/monster_stats.py`
- Add `CHESTMONSTER_STAT_MULTIPLIER = 1.75` (75% higher = 1.75x stats)
- Create `generate_chestmonster_stats(level, rng)` function
- Use same stat generation as normal vessels but multiply:
  - All ability scores: `* 1.75`
  - HP: `* 1.75`
  - AC: Add bonus (e.g., +3 AC)
  - All modifiers scale accordingly

### 5.2 Chestmonster Moves
**File**: `Main/combat/moves.py` or create `Main/combat/chestmonster_moves.py`
- Create 4 balanced moves for Chestmonster:
  1. **Treasure Trap** - Physical attack, moderate damage
  2. **Coin Barrage** - Ranged attack, multiple hits
  3. **Lock Slam** - High damage, single target
  4. **Chest Slam** - Area attack, moderate damage
- Balance damage/effects similar to other monster moves
- Use appropriate damage types (physical, magical, etc.)

### 5.3 Chestmonster Encounter Setup
**File**: `Main/main.py` - `_open_chest(gs)` battle branch
- Set `gs.encounter_type = "CHESTMONSTER"`
- Set `gs.encounter_name = "Chest Monster"` (or generate name)
- Load Chestmonster sprite from `Assets/VesselMonsters/Chestmonster.png`
- Load token sprite from `Assets/VesselMonsters/TokenChestmonster.png`
- Generate stats using `generate_chestmonster_stats()` with scaled level
- Set `gs.encounter_stats` with generated stats
- Set `gs.encounter_sprite` to Chestmonster sprite
- Set `gs.encounter_token_name = "Chestmonster"`
- Transition to `MODE_WILD_VESSEL` (uses same battle system)

### 5.4 Asset Loading for Battle
**File**: `Main/combat/wild_vessel.py` or `Main/world/assets.py`
- Ensure Chestmonster.png and TokenChestmonster.png are loaded
- Load Chestmonster.mp3 sound effect for battle
- Use same asset loading pattern as other monsters

---

## Phase 6: Integration & Polish

### 6.1 Chest Removal After Opening
**File**: `Main/world/actors.py` - `update_chests()`
- When chest is opened, remove from `gs.chests_on_map`
- Clear `gs.near_chest` flag

### 6.2 Sound Effects
**File**: `Main/main.py` or `Main/systems/audio.py`
- Add chest opening sound (if available)
- Play Chestmonster.mp3 when battle starts
- Use existing audio system

### 6.3 Visual Feedback
- Optional: Add chest opening animation
- Optional: Show item received notification
- Ensure chest disappears after opening

### 6.4 Testing Checklist
- [ ] Chest spawns at 5% rate
- [ ] Popup appears when near chest
- [ ] E key opens chest
- [ ] 85% chance gives item (weighted correctly)
- [ ] 15% chance triggers battle
- [ ] Chestmonster has 75% stat boost
- [ ] Chestmonster has 4 moves
- [ ] Battle uses same system as wild vessels
- [ ] Chest removed after opening
- [ ] No scroll_of_eternity in item pool

---

## File Structure Summary

### New Functions:
- `Main/world/actors.py`:
  - `spawn_chest_ahead(gs, start_x, chest_sprite)`
  - `update_chests(gs, dt, player_half)`
  - `draw_chests(screen, cam, gs)`

- `Main/main.py`:
  - `_draw_chest_popup(screen, gs, ...)` (similar to tavern popup)
  - `_open_chest(gs)`
  - `_give_chest_item(gs)`

- `Main/combat/vessel_stats.py` or `Main/combat/monster_stats.py`:
  - `generate_chestmonster_stats(level, rng)`

- `Main/combat/moves.py` or new file:
  - Chestmonster move definitions (4 moves)

### Modified Files:
- `Main/world/actors.py` - Add chest spawn/update/draw
- `Main/main.py` - Add spawn chance, popup, E key handling, chest opening
- `Main/world/assets.py` - Load chest sprite
- `Main/combat/wild_vessel.py` - Ensure Chestmonster assets load correctly

---

## Implementation Order

1. **Phase 1**: Spawn system & asset loading
2. **Phase 2**: Proximity detection & popup
3. **Phase 3**: E key handling & opening logic
4. **Phase 4**: Item reward system
5. **Phase 5**: Chestmonster battle system
6. **Phase 6**: Integration & polish

---

## Notes

- Chest uses same interaction pattern as merchant/tavern (proximity + E key)
- Item distribution is weighted, with command/mending having highest chance
- Chestmonster uses wild_vessel battle system but with enhanced stats
- All chest assets already exist in the specified paths
- Chestmonster should feel challenging but fair (75% boost is significant but not overwhelming)

