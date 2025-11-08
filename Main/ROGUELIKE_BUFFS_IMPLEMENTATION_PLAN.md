# Roguelike Buffs System - Implementation Plan

## Overview
Implement a roguelike buffs system where players can receive buffs (or curses) after summoner battles. The system will show 3 clickable cards for selection, with different rarity tiers.

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

### Phase 4: Buff Application

#### 4.1 Buff Effects System (`systems/buff_effects.py`)
Define what each buff does:
- Stat modifications (HP, Attack, Defense, etc.)
- Battle effects (damage multipliers, XP bonuses, etc.)
- Special abilities
- Curse effects (negative modifiers)

#### 4.2 Apply Buff to Game State
After selection:
- Add buff to `gs.active_buffs`
- Apply effects to relevant stats
- Save to `gs.buffs_history`
- Return to overworld (MODE_GAME)

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
│   ├── buffs.py              # NEW: Buff metadata, rarity, selection logic
│   ├── buff_effects.py       # NEW: Buff effect definitions and application
│   └── save_system.py        # MODIFY: Add buff saving/loading
├── screens/
│   └── buff_selection.py     # NEW: Buff selection screen UI
├── combat/
│   └── battle.py             # MODIFY: Add buff trigger after victory
├── game_state.py             # MODIFY: Add buff fields
└── main.py                   # MODIFY: Add buff selection mode
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

## Future Enhancements (Optional)

1. **Buff Preview**: Show what each buff does before selection
2. **Buff Removal**: Way to remove curses
3. **Buff Synergies**: Certain buff combinations give bonuses
4. **Buff Display**: Show active buffs in HUD
5. **Buff Archive**: View all buffs received in a run
6. **Tier Colors**: Different border colors for each tier
7. **Animation**: Card flip/reveal animation
8. **Sound**: Different sounds for different tiers

## Notes

- DemonPact should feel special - consider special effects/animations
- Curses should be clearly marked as negative
- Buff effects need to be balanced with game difficulty
- Consider how buffs interact with existing systems (XP, stats, etc.)

