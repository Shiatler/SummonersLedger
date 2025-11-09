# Roguelike Buffs System - Implementation Plan

## Overview
Implement a roguelike buffs system where players can receive buffs (or curses) after summoner battles. The system will show 3 clickable cards for selection, with different rarity tiers.

## Key Design Principles

1. **All Blessing Application Handled in Party Manager**: When a blessing/curse/demonpact is selected, the player is taken to the party manager to select vessels and apply effects.

2. **Stat Selection Popup**: For blessings that modify stats, a dedicated popup (`vessel_stat_selector.py`) shows vessel stats (HP, AC, XP, STR, DEX, CON, INT, WIS, CHA) and allows the player to choose which stat to modify.

3. **Dice Rolling & Result Cards**: Blessings that require dice rolls (e.g., "1d4 HP", "1d6 XP") use the existing rolling system and display result cards similar to combat.

4. **Move Selection**: For PP-related blessings, players select a vessel, then choose which move to add PP to from a list of the vessel's moves.

5. **Permanent Effects**: Effects like permanent damage bonuses are stored in vessel stats and persist across battles and saves.

6. **Direct Inventory Additions**: Scroll/item blessings are added directly to inventory without vessel selection.

## Requirements

### 1. Trigger Conditions
- **10% chance** after winning a summoner battle
- Only triggers after **victory** (not defeat)
- Only triggers in summoner battles (not wild vessel battles)

### 2. Rarity Tiers & Distribution
- **Common**: 9 options (Common1.png - Common9.png)
- **Rare**: 5 options (Rare1.png - Rare5.png)
- **Epic**: 4 options (Epic1.png - Epic4.png)
- **Legendary**: 5 options (Legendary1.png - Legendary5.png)
- **DemonPact**: 4 options (DemonPact1.png - DemonPact4.png) - **INSANELY RARE**
- **Curse**: 5 options (Curse1.png - Curse5.png) - Same rarity as Epic

### 3. Rarity Distribution Logic
Rarity probabilities:
- **Common**: 50%
- **Rare**: 25%
- **Epic**: 12.5%
- **Curse**: 12.5% (same as Epic)
- **Legendary**: 5%
- **DemonPact**: 0.5% (insanely rare)

Note: Percentages will be normalized to sum to 100% in implementation.

### 4. Card Selection Screen
- Display **3 randomly selected cards** from the rolled tier
- Cards should be clickable
- Show card images from `Assets/Blessings/`
- Display card names/tiers
- Player selects ONE card
- After selection, apply the buff and return to overworld

## Implementation Steps

### Phase 1: Data Structure & Game State

#### 1.1 Extend GameState (`game_state.py`)
Add fields to track buffs:
```python
# Buffs system
active_buffs: list = field(default_factory=list)  # List of buff dicts: {"tier": "Common", "id": 1, "name": "Common1", "image_path": "...", "effects": {...}}
buffs_history: list = field(default_factory=list)  # Track all buffs received (for archives/ledger)
```

#### 1.2 Create Buff Data Module (`systems/buffs.py`)
- Define buff metadata (tier, id, name, effects)
- Rarity distribution weights
- Buff effect definitions
- Utility functions to load buff images
- Function to generate 3 random cards from a tier

### Phase 2: Trigger System

#### 2.1 Modify Battle Exit Flow (`combat/battle.py`)
In `_finalize_battle_xp()` or `_exit_battle()`:
- Check if battle was a summoner battle victory
- Roll 10% chance
- If triggered, set a flag: `gs.pending_buff_selection = True`
- Instead of immediately returning to MODE_GAME, transition to buff selection screen

#### 2.2 Track Summoner Battle Type
- Ensure we can distinguish summoner battles from wild vessel battles
- Check `gs.mode` or add a flag like `gs.last_battle_was_summoner = True`

### Phase 3: Buff Selection Screen

#### 3.1 Create Buff Selection Screen (`screens/buff_selection.py`)
Screen structure similar to other modal screens:
- `enter(gs, **kwargs)`: Initialize screen state
  - Roll rarity tier based on probabilities
  - Select 3 random cards from that tier
  - Load card images
  - Set up UI state (card positions, hover states, etc.)
- `handle(events, gs, dt, **kwargs)`: Handle input
  - Mouse clicks on cards
  - Keyboard navigation (optional)
  - Escape to skip (optional)
- `draw(screen, gs, dt, **kwargs)`: Render screen
  - Dark overlay/background
  - 3 card images in a row
  - Card names/tiers
  - Hover effects
  - Selection feedback

#### 3.2 Card Selection UI
- Display 3 cards horizontally centered
- Each card:
  - Image from `Assets/Blessings/{Tier}{id}.png`
  - Tier name label
  - Hover effect (scale up, border highlight)
  - Click detection
- Background: Dark semi-transparent overlay
- Title: "Choose a Blessing" or "Choose a Curse" (if curse tier rolled)

### Phase 4: Buff Application System

#### 4.1 Core Principle: All Blessing/Curse/DemonPact Handling in Party Manager
**All buff application logic will be handled in `party_manager.py`**. When a blessing/curse/demonpact is selected:
1. Transition to party manager (`party_manager.open()`)
2. Player selects a vessel (or multiple vessels if blessing affects all)
3. If stat selection is needed, show stat selection popup
4. If dice roll is needed, roll dice and show result card
5. Apply the blessing effect
6. Return to overworld

#### 4.2 Vessel Stat Selection Popup (`screens/vessel_stat_selector.py` - NEW)
A popup screen that displays vessel stats and allows stat selection:
- **Display**: Shows all vessel information:
  - HP (current/max)
  - AC (Armor Class)
  - XP (current/total for next level)
  - All D&D ability scores: STR, DEX, CON, INT, WIS, CHA
  - Ability modifiers (calculated from scores: (score - 10) // 2)
  - Current stat values (before modification)
- **Selection Logic**:
  - Only show/allow selection of stats that are applicable to the blessing
  - **For "1x stat" or "+1 to one stat of choice"**: Show all 6 ability scores (STR, DEX, CON, INT, WIS, CHA) + AC
  - **For "1d4 HP"**: Skip stat selector entirely, just roll dice
  - **For "+1d6 XP"**: Skip stat selector entirely, just roll dice
  - **For curses with stat penalties**: Show same stats as bonuses
  - **For "1x AC"**: Skip stat selector, just apply directly
  - Disable stats that are at max (e.g., if STR is 20 and blessing has max cap)
- **UI**: 
  - Modal overlay with parchment background (consistent with party_manager)
  - Display vessel name and portrait at top
  - Show stats in a grid or list format
  - Each stat shows: Name, Current Value, Modifier (e.g., "STR: 16 (+3)")
  - Click on stat to select (highlight with border/glow)
  - Show preview of new value after modification (e.g., "STR: 16 (+3) → 17 (+3)")
  - Confirm button to apply modification
  - Cancel button to go back
  - Visual feedback: selected stat should be clearly highlighted

#### 4.3 Dice Rolling & Result Cards
When a blessing requires a dice roll (e.g., "1d4 HP", "1d6 XP"):
1. Use the existing rolling system (`rolling/roller.py`)
2. Roll the dice (e.g., 1d4, 1d6, 1d10, 1d20, etc.)
3. Display result card (similar to combat result cards)
4. Show the rolled value clearly
5. Apply the result to the vessel

#### 4.4 Move Selection (PP-related Blessings)
For blessings that add PP to moves (e.g., "+2 PP to 1 move", "+5 PP to 1 move"):
1. Open party manager
2. Player selects a vessel
3. Show vessel's available moves in a popup/list
4. Display for each move:
   - Move name
   - Current PP / Max PP (e.g., "5/10")
   - Move description (optional)
5. Player selects which move to add PP to
6. Apply PP bonus to selected move (cap at max PP)
7. Close move selector → Close party manager → Return to overworld

**UI Considerations**:
- Can reuse party_manager UI style (parchment background)
- List moves vertically with clickable rows
- Highlight selected move
- Show PP values clearly (current/max format)
- Disable moves that are already at max PP (optional)

#### 4.5 Permanent Damage Bonus
For blessings like "Sharpened Knife" (+1 permanent damage to attacks):
- Add a permanent damage modifier to the vessel's stats
- Store in vessel's stat dict: `permanent_damage_bonus: int`
- Apply this bonus to all damage rolls for that vessel in combat
- Persists across battles and saves

#### 4.6 Buff Effect Types & Implementation Rules

**Stat Modifications**:
- **"1x stat to 1 vessel"**: 
  - Open party manager → select vessel → show stat selector → choose stat → apply +1
  - Enforce max stat cap (e.g., max of 20)
- **"+1 to one stat of choice"**: 
  - Same as above, no cap specified
- **"+2 to one stat of choice"**: 
  - Apply +2 instead of +1
- **"+2 random stats to 1 random Vessel"**: 
  - Auto-select random vessel, roll 2 random stats, apply +1 to each

**HP Modifications**:
- **"1d4 hp to 1 vessel"**: 
  - Open party manager → select vessel → roll 1d4 → show result card → add HP
- **"1d10 hp to 1 vessel"**: 
  - Same as above, roll 1d10
- **"1d4 hp to all vessels"**: 
  - For each vessel in party: roll 1d4 → show result card → add HP
  - Show result card for each vessel sequentially

**AC Modifications**:
- **"1x AC to 1 vessel"**: 
  - Open party manager → select vessel → add +1 AC
- **"1x AC to all vessels"**: 
  - Apply +1 AC to all vessels in party

**XP Modifications**:
- **"+1d6 XP to 1 Vessel"**: 
  - Open party manager → select vessel → roll 1d6 → show result card → add XP
  - Trigger level-up check if XP threshold reached

**PP Modifications**:
- **"+2 PP to 1 move"**: 
  - Open party manager → select vessel → show moves → select move → add +2 PP
- **"+5 PP to 1 move"**: 
  - Same as above, add +5 PP
- **"+10 PP to 1 move"**: 
  - Same as above, add +10 PP

**Scroll/Item Additions**:
- **"+5 scroll of mending"**: 
  - Directly add 5 scrolls of mending to inventory (no vessel selection)
- **"+5 scroll of command"**: 
  - Directly add 5 scrolls of command to inventory
- **"+2 Scrolls of Sealing"**: 
  - Directly add 2 scrolls of sealing to inventory
- **"+2 Scrolls of Healing"**: 
  - Directly add 2 scrolls of healing to inventory
- **"+5 Scrolls of Subjugation"**: 
  - Directly add 5 scrolls of subjugation to inventory

**Permanent Damage**:
- **"+1 permanent damage to attacks for 1 Vessel"**: 
  - Open party manager → select vessel → add permanent_damage_bonus: +1
  - Apply in combat damage calculations

**Damage Reduction**:
- **"-1d2 dmg from enemy attacks (1 time roll)"**: 
  - Open party manager → select vessel → roll 1d2 → show result card → store damage reduction value
  - Apply in combat when vessel takes damage (one-time use)

**Special Effects**:
- **"+1 to all stat rolls for the next Vessel you capture"**: 
  - Set a flag: `next_capture_stat_bonus: +1`
  - Apply during next vessel capture stat rolling
  - Clear flag after capture

**Curse Effects**:
- **"+1 to one stat of choice / -1 to another stat of choice"**: 
  - Open party manager → select vessel → show stat selector → choose stat for +1
  - Then show stat selector again → choose stat for -1
  - Apply both modifications
- **"+2 to one stat of choice / -1 to another random stat"**: 
  - Select vessel → choose stat for +2 → random roll for -1 stat → apply both
- **"+1 to all rolls / -1d8 HP for every vessel"**: 
  - Set global flag: `all_rolls_bonus: +1`
  - For each vessel: roll 1d8 → show result card → subtract HP

**Regeneration/Healing Effects**:
- **"+1d4 healing each round (regeneration aura)"**: 
  - Add to vessel: `regeneration_per_round: 1d4`
  - Apply at start of each combat round

**Party-Wide Effects**:
- **"+1d20 HP to all Vessels"**: 
  - For each vessel: roll 1d20 → show result card → add HP
- **"+1 additional Vessel slot in your active party"**: 
  - Increase `gs.max_party_size` by 1 (if not already at max)
- **"Damage reduction 1d6 for entire party (permanent roll)"**: 
  - Roll 1d6 once → show result card → apply damage reduction to all vessels permanently

#### 4.7 Buff Application Flow Diagram

```
1. Player selects blessing/curse/demonpact card
   ↓
2. Check blessing type:
   ├─→ Direct inventory addition (scrolls) → Add to inventory → Done
   ├─→ Needs vessel selection → Open party_manager
   │   ├─→ Player selects vessel(s)
   │   ├─→ If stat selection needed → Open vessel_stat_selector
   │   │   └─→ Player selects stat → Apply modification → Done
   │   ├─→ If dice roll needed → Roll dice → Show result card → Apply result → Done
   │   ├─→ If move selection needed → Show moves → Select move → Add PP → Done
   │   └─→ If permanent effect → Apply to vessel → Store in stats → Done
   └─→ Party-wide effect → Apply to all vessels (with rolls if needed) → Done
```

#### 4.8 Data Structures for Buff Effects

**Vessel Stats Extensions**:
```python
vessel_stats = {
    # ... existing stats ...
    "permanent_damage_bonus": 0,           # +1, +2, etc.
    "damage_reduction": 0,                 # -1d2, -1d6, etc. (one-time or permanent)
    "regeneration_per_round": None,        # "1d4" or None
    "ac_bonus": 0,                         # +1 AC, etc.
    "stat_bonuses": {                      # Permanent stat bonuses
        "STR": 0,
        "DEX": 0,
        "CON": 0,
        "INT": 0,
        "WIS": 0,
        "CHA": 0,
    },
}
```

**Game State Extensions**:
```python
gs = {
    # ... existing fields ...
    "next_capture_stat_bonus": 0,          # +1 to next capture's stat rolls
    "all_rolls_bonus": 0,                  # +1 to all rolls (curse effect)
    "max_party_size": 6,                   # Can be increased by blessings
}
```

#### 4.9 Integration with Existing Systems

**Combat Integration**:
- Damage calculations: Add `permanent_damage_bonus` to damage rolls
- Damage reduction: Subtract `damage_reduction` from incoming damage
- Regeneration: Apply `regeneration_per_round` at start of each round
- AC: Include `ac_bonus` in AC calculations

**Rolling System Integration**:
- Use `rolling/roller.py` for all dice rolls
- Use result card system from `combat/battle.py` or `combat/wild_vessel.py`
- Apply `all_rolls_bonus` to all dice rolls when active

**Capture System Integration**:
- Check `next_capture_stat_bonus` during vessel capture
- Apply bonus to stat rolls
- Clear bonus after capture

**Save System Integration**:
- Save all vessel stat modifications (permanent_damage_bonus, ac_bonus, stat_bonuses, etc.)
- Save global buff flags (next_capture_stat_bonus, all_rolls_bonus, max_party_size)
- Save active_buffs list for display in archives/ledger

### Phase 5: Save System Integration

#### 5.1 Extend Save System (`systems/save_system.py`)
- Save `active_buffs` to savegame.json
- Save `buffs_history` to savegame.json
- Load buffs on game load

### Phase 6: Integration with Main Loop

#### 6.1 Add Mode to Main Loop (`main.py`)
- Add `MODE_BUFF_SELECTION = "BUFF_SELECTION"`
- Add mode handling in `enter_mode()` function
- Add mode handling in main game loop
- Route events and drawing to buff_selection screen

#### 6.2 Transition Logic
- After battle victory → check for buff trigger → transition to buff selection
- After buff selection → return to overworld

## File Structure

```
Main/
├── systems/
│   ├── buffs.py                    # NEW: Buff metadata, rarity, selection logic
│   └── save_system.py              # MODIFY: Add buff saving/loading
├── screens/
│   ├── buff_selection.py           # NEW: Buff selection screen UI (3 cards)
│   ├── vessel_stat_selector.py     # NEW: Stat selection popup for vessels
│   └── party_manager.py            # MODIFY: Add buff application logic
├── combat/
│   ├── battle.py                   # MODIFY: Add buff trigger after victory
│   └── moves.py                    # MODIFY: Apply permanent_damage_bonus in damage calc
├── rolling/
│   └── roller.py                   # USE: For all dice rolls in blessings
├── game_state.py                   # MODIFY: Add buff fields and global flags
└── main.py                         # MODIFY: Add buff selection mode
```

## Technical Details

### Buff Data Structure
```python
buff = {
    "tier": "Common",           # Tier name
    "id": 1,                    # Card ID within tier (1-9 for Common, etc.)
    "name": "Common1",          # Full name for display
    "image_path": "Assets/Blessings/Common1.png",
    "effects": {                # Effect definitions
        "hp_bonus": 10,
        "attack_multiplier": 1.1,
        # ... other effects
    },
    "acquired_at": timestamp,   # When acquired
}
```

### Rarity Roll Function
```python
def roll_buff_tier() -> str:
    """Roll a buff tier based on rarity distribution."""
    # Raw weights (will be normalized)
    weights = {
        "Common": 50.0,
        "Rare": 25.0,
        "Epic": 12.5,
        "Curse": 12.5,  # Same as Epic
        "Legendary": 5.0,
        "DemonPact": 0.5,
    }
    # Normalize to 100%
    total = sum(weights.values())
    normalized = {k: v / total * 100 for k, v in weights.items()}
    
    # Cumulative probabilities
    roll = random.random() * 100
    cumulative = 0
    for tier, prob in normalized.items():
        cumulative += prob
        if roll < cumulative:
            return tier
    return "Common"  # Fallback
```

### Card Selection from Tier
```python
def get_3_random_cards_from_tier(tier: str) -> list:
    """Get 3 random, unique cards from a tier."""
    max_id = {
        "Common": 9,
        "Rare": 5,
        "Epic": 4,
        "Legendary": 5,
        "DemonPact": 4,
        "Curse": 5,
    }[tier]
    
    ids = random.sample(range(1, max_id + 1), min(3, max_id))
    return [{"tier": tier, "id": id, "name": f"{tier}{id}"} for id in ids]
```

## UI/UX Considerations

1. **Visual Feedback**:
   - Hover effect on cards (scale, glow, border)
   - Selected card highlight
   - Smooth transitions

2. **Accessibility**:
   - Clear visual distinction between tiers
   - Readable text on cards
   - Click area should be large enough

3. **Polish**:
   - Card reveal animation (optional)
   - Sound effects on hover/select
   - Particle effects for rare tiers (optional)

## Detailed Blessing Examples (Common Tier)

### Common1: Minor Echo - "1x stat to 1 vessel (max of 20)"
**Flow**:
1. Player selects Common1 card
2. Open `party_manager.py` in picker mode
3. Player clicks on a vessel
4. Open `vessel_stat_selector.py` popup
5. Show all applicable stats: STR, DEX, CON, INT, WIS, CHA, AC
6. Player selects a stat (e.g., STR)
7. Check if current stat value < 20
8. If valid: Apply +1 to selected stat
9. Close stat selector → Close party manager → Return to overworld

### Common2: Blood Vial - "1d4 hp to 1 vessel (1 time roll)"
**Flow**:
1. Player selects Common2 card
2. Open `party_manager.py` in picker mode
3. Player clicks on a vessel
4. Roll 1d4 using `rolling/roller.py`
5. Show result card (e.g., "Rolled 1d4: 3")
6. Add 3 HP to vessel's current_hp (cap at max_hp)
7. Close party manager → Return to overworld

### Common3: Swift Strike - "+2 PP to 1 move"
**Flow**:
1. Player selects Common3 card
2. Open `party_manager.py` in picker mode
3. Player clicks on a vessel
4. Show vessel's moves list with current PP for each move
5. Player selects a move (e.g., "Thorn Whip" with 5/10 PP)
6. Add +2 PP to selected move (now 7/10 PP)
7. Close party manager → Return to overworld

### Common4: Healer's Satchel - "+5 scroll of mending"
**Flow**:
1. Player selects Common4 card
2. Directly add 5 "scroll_of_mending" items to inventory
3. No vessel selection needed
4. Return to overworld immediately

### Common5: Binder's Supply - "+5 scroll of command"
**Flow**:
1. Player selects Common5 card
2. Directly add 5 "scroll_of_command" items to inventory
3. No vessel selection needed
4. Return to overworld immediately

### Common6: Memory Shard - "+1d6 XP to 1 Vessel"
**Flow**:
1. Player selects Common6 card
2. Open `party_manager.py` in picker mode
3. Player clicks on a vessel
4. Roll 1d6 using `rolling/roller.py`
5. Show result card (e.g., "Rolled 1d6: 4")
6. Add 4 XP to vessel
7. Check if vessel levels up (trigger level-up logic if needed)
8. Close party manager → Return to overworld

### Common7: Binding Pouch - "+2 Scrolls of Sealing"
**Flow**:
1. Player selects Common7 card
2. Directly add 2 "scroll_of_sealing" items to inventory
3. No vessel selection needed
4. Return to overworld immediately

### Common8: Healing Pouch - "+2 Scrolls of Healing"
**Flow**:
1. Player selects Common8 card
2. Directly add 2 "scroll_of_healing" items to inventory
3. No vessel selection needed
4. Return to overworld immediately

### Common9: Sharpened Knife - "+1 permanent damage to attacks for 1 Vessel"
**Flow**:
1. Player selects Common9 card
2. Open `party_manager.py` in picker mode
3. Player clicks on a vessel
4. Add `permanent_damage_bonus: 1` to vessel's stats
5. Store in `gs.party_vessel_stats[vessel_idx]["permanent_damage_bonus"] = 1`
6. In combat, when this vessel deals damage, add +1 to damage roll
7. Close party manager → Return to overworld

## Testing Checklist

- [ ] 10% trigger chance works correctly
- [ ] Only triggers after summoner battle victory
- [ ] Rarity distribution matches probabilities
- [ ] 3 cards are always unique
- [ ] Cards load images correctly
- [ ] Click detection works
- [ ] Buff is applied after selection
- [ ] Buff persists through saves
- [ ] Buff effects work in battles
- [ ] Multiple buffs can stack (if applicable)
- [ ] Curses apply negative effects correctly
- [ ] Vessel stat selector shows all stats correctly
- [ ] Stat selection only shows applicable stats
- [ ] Dice rolls work correctly for HP/XP bonuses
- [ ] Result cards display correctly
- [ ] Move selection works for PP bonuses
- [ ] Permanent damage bonus applies in combat
- [ ] Scroll items are added to inventory correctly
- [ ] Max stat cap (20) is enforced
- [ ] Party-wide effects apply to all vessels
- [ ] Sequential result cards work for multiple vessels

## Future Enhancements (Optional)

1. **Buff Preview**: Show what each buff does before selection
2. **Buff Removal**: Way to remove curses
3. **Buff Synergies**: Certain buff combinations give bonuses
4. **Buff Display**: Show active buffs in HUD
5. **Buff Archive**: View all buffs received in a run
6. **Tier Colors**: Different border colors for each tier
7. **Animation**: Card flip/reveal animation
8. **Sound**: Different sounds for different tiers

## Implementation Priority

### Phase 1: Core Infrastructure
1. Create `vessel_stat_selector.py` screen
2. Extend `party_manager.py` with buff application modes
3. Add buff data structures to `game_state.py`
4. Create buff application flow in `party_manager.py`

### Phase 2: Basic Blessings
1. Implement Common1 (stat selection)
2. Implement Common2 (HP roll)
3. Implement Common4-5, 7-8 (inventory additions)
4. Test stat selector and result cards

### Phase 3: Advanced Blessings
1. Implement Common3 (PP/move selection)
2. Implement Common6 (XP roll)
3. Implement Common9 (permanent damage)
4. Implement Rare/Epic/Legendary blessings

### Phase 4: Curses & Special Effects
1. Implement curse effects (stat penalties)
2. Implement party-wide effects
3. Implement regeneration effects
4. Implement special capture bonuses

### Phase 5: Combat Integration
1. Apply permanent_damage_bonus in combat
2. Apply damage_reduction in combat
3. Apply regeneration_per_round in combat
4. Apply ac_bonus in combat
5. Apply all_rolls_bonus globally

### Phase 6: Polish & Testing
1. Test all blessing types
2. Test save/load functionality
3. Test edge cases (empty party, max stats, etc.)
4. Add sound effects and visual feedback
5. Balance testing

## Notes

- **DemonPact should feel special** - consider special effects/animations
- **Curses should be clearly marked as negative** - use red text/borders
- **Buff effects need to be balanced** with game difficulty
- **Consider how buffs interact** with existing systems (XP, stats, combat, etc.)
- **Result cards should be consistent** with combat result cards for familiarity
- **Stat selector should be intuitive** - clear labels, good visual feedback
- **Party manager integration** - blessings should feel like a natural extension of party management
- **Performance** - ensure result cards and stat selection don't cause lag
- **User experience** - make the flow smooth: select card → select vessel → (select stat/move) → see result → done

