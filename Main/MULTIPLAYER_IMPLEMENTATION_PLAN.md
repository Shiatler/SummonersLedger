# Multiplayer Implementation Plan

## Overview
Transform Summoner's Ledger into a multiplayer battle royale-style game where up to 8 players compete until one remains. Host-based architecture (no external servers needed).

---

## Architecture Overview

### Network Model
- **Host-Client Architecture**: One player hosts, others connect
- **Host Responsibilities**: 
  - Runs server logic (game state authority)
  - Handles matchmaking (lobby management)
  - Synchronizes game state to all clients
  - Manages timers and battle pairings
- **Client Responsibilities**:
  - Sends player actions to host
  - Receives game state updates
  - Renders local view

### Core Components Needed
1. **Networking Module** (`networking/` package)
2. **Lobby Screen** (`screens/multiplayer_lobby.py`)
3. **PvP Battle System** (`combat/pvp_battle.py`)
4. **Spectator System** (`screens/spectator.py`)
5. **Multiplayer Game State** (extend `GameState`)
6. **Timer System** (integrated into game loop)
7. **Player Management** (tracking alive/dead players)

---

## Phase 1: Networking Foundation

### 1.1 Core Networking Module
**File**: `networking/server.py` (host side)
- TCP socket server listening on port (e.g., 12345)
- Accept up to 7 client connections
- Handle connection/disconnection events
- Message serialization/deserialization (JSON or pickle)
- Heartbeat system (detect disconnects)

**File**: `networking/client.py` (client side)
- Connect to host IP/port
- Send/receive messages
- Handle connection errors gracefully
- Reconnection logic

**File**: `networking/messages.py`
- Define message types:
  - `LOBBY_JOIN`, `LOBBY_LEAVE`
  - `PLAYER_MOVE` (lobby movement)
  - `PLAYER_READY`, `GAME_START`
  - `GAME_STATE_UPDATE`
  - `BATTLE_ACTION` (PvP moves)
  - `PLAYER_DIED`, `SPECTATE_REQUEST`
- Message validation and parsing

**File**: `networking/serialization.py`
- Serialize `GameState` to JSON (handle pygame Surfaces separately)
- Serialize player positions, stats, party data
- Handle non-serializable objects (images, sprites)

### 1.2 Network Integration Points
- Add `is_host` and `is_client` flags to `GameState`
- Add `network_manager` to game dependencies
- Wrap existing game logic with network sync checks

---

## Phase 2: Lobby System

### 2.1 Lobby Screen
**File**: `screens/multiplayer_lobby.py`

**Features**:
- Load `TavernMap.png` as background (reuse tavern map loading logic)
- Use same collision boundaries as tavern (reuse `_TAVERN_WALLS`)
- Display connected players (1-8)
- Show player avatars walking around lobby

**Host UI Elements**:
- "Start Game" button (only visible to host)
- Player list showing:
  - Player name/number
  - Gender selection status
  - Ready status (optional)
- Connection status indicators

**Client UI Elements**:
- "Waiting for host..." message
- Player list
- Gender selection buttons (Male/Female)
- Cannot start game (host only)

**Player Movement**:
- Same movement system as tavern (A/D keys, collision detection)
- Sync player positions across network
- Each player sees other players' avatars
- Render player sprites based on gender selection

**Network Sync**:
- Send `PLAYER_MOVE` messages on position change
- Receive other players' positions
- Interpolate remote player movement (smooth rendering)

### 2.2 Lobby State Management
**File**: `networking/lobby_state.py`

**Data Structure**:
```python
{
    "players": [
        {
            "id": 1,
            "name": "Player1",
            "gender": "male" | "female" | None,
            "position": (x, y),
            "is_host": True/False,
            "is_ready": False
        },
        ...
    ],
    "game_started": False
}
```

**Host Logic**:
- Track all connected players
- Validate "Start Game" conditions (all players selected gender)
- Broadcast `GAME_START` message when host clicks play

**Client Logic**:
- Send gender selection to host
- Receive lobby state updates
- Render other players

---

## Phase 3: Multiplayer Game State

### 3.1 Extend GameState
**File**: `game_state.py` (add multiplayer fields)

**New Fields**:
```python
# Multiplayer
is_multiplayer: bool = False
is_host: bool = False
is_client: bool = False
player_id: int = 0  # Unique ID in lobby (0-7)
player_hp: int = 2  # Starting HP (lose 1 per battle loss)
is_alive: bool = True
spectating_player_id: int | None = None  # Who we're spectating

# Lobby
lobby_players: list = field(default_factory=list)  # List of player dicts
lobby_started: bool = False

# Timer
match_timer: float = 300.0  # 5 minutes in seconds
timer_active: bool = False

# PvP Battle
in_pvp_battle: bool = False
pvp_opponent_id: int | None = None
pvp_battle_state: dict | None = None
```

### 3.2 Network State Sync
**File**: `networking/state_sync.py`

**Sync Frequency**:
- High frequency: Player positions (every frame or every 0.1s)
- Medium frequency: Game state changes (events, encounters)
- Low frequency: Full state sync (periodic validation)

**What to Sync**:
- Player positions (overworld)
- Encounter triggers
- Battle outcomes
- Timer state
- Player HP/alive status
- Party changes
- Score/XP changes

**What NOT to Sync**:
- Local UI state (menus, popups)
- Animation frames (client-side)
- Audio (client-side)

---

## Phase 4: Timer System

### 4.1 Timer Implementation
**File**: `systems/match_timer.py`

**Features**:
- 5-minute countdown timer
- Display in HUD (top center or corner)
- Host controls timer (clients receive updates)
- When timer hits 0:
  - Pause all player actions
  - Pair players for PvP battles
  - Transition to battle screen

**Timer Display**:
- Format: `MM:SS` (e.g., "05:00", "04:59", ... "00:01")
- Visual countdown (maybe with warning at 1 minute, 30 seconds)
- Show in overworld HUD

**Pairing Logic**:
- Random pairing (or based on score/position)
- Handle odd number of players (one gets bye if odd)
- Ensure no player fights twice in same round

### 4.2 Timer Integration
- Add timer to main game loop
- Host updates timer, broadcasts to clients
- Clients receive timer updates and display
- When timer expires, trigger battle pairing

---

## Phase 5: PvP Battle System

### 5.1 New PvP Battle Module
**File**: `combat/pvp_battle.py`

**Based on**: `combat/battle.py` (reuse logic where possible)

**Key Differences from Normal Battle**:
- Opponent is a player (not AI)
- Turn-based with time limits (30 seconds per move)
- Both players must choose moves before resolving
- Same animations and visual effects
- Same HUD layout

**Battle Flow**:
1. Both players enter battle screen simultaneously
2. Player 1 chooses move (30 second timer)
3. Player 2 chooses move (30 second timer)
4. If both chose: resolve moves (same as normal battle)
5. If timeout: auto-select basic attack
6. Show results (same as normal battle)
7. Update HP (loser loses 1 HP)
8. Return to overworld

**Network Sync**:
- Send `BATTLE_ACTION` message when player selects move
- Receive opponent's move selection
- Both clients resolve battle (deterministic calculation)
- Host validates results

**Move Selection UI**:
- Same move buttons as normal battle
- Disable buttons after selection (until opponent chooses)
- Show "Waiting for opponent..." message
- Show timer countdown (30 seconds)

### 5.2 Battle State Management
**File**: `combat/pvp_battle_state.py`

**State Structure**:
```python
{
    "phase": "SELECT_MOVE" | "WAITING_OPPONENT" | "RESOLVING" | "RESULTS",
    "player_move": None | "move_name",
    "opponent_move": None | "move_name",
    "timer": 30.0,  # seconds remaining
    "player_party": [...],  # Current party state
    "opponent_party": [...],  # Opponent's party state
    "battle_result": None | "win" | "loss"
}
```

**Reuse from battle.py**:
- Move execution logic
- Damage calculation
- Animation system
- Turn order system
- Party management
- XP calculation (for winner)

---

## Phase 6: Spectator System

### 6.1 Spectator Screen
**File**: `screens/spectator.py`

**Features**:
- Display when player dies (HP reaches 0)
- Show list of alive players
- Arrow buttons (left/right) to switch between players
- Render selected player's view:
  - Their overworld screen
  - Their battles (if in battle)
  - Their HUD and party

**UI Elements**:
- Player list (alive players only)
- Current spectating target indicator
- Arrow navigation buttons
- "Exit Spectator" button (returns to menu)

**Network Requirements**:
- Request spectate data from host
- Receive selected player's game state
- Render their view (same as if playing)

### 6.2 Spectator State
**File**: `game_state.py` (add spectator fields)

**Fields**:
```python
is_spectating: bool = False
spectating_player_id: int | None = None
spectator_camera_pos: Vector2 = field(default_factory=lambda: Vector2(0, 0))
```

**Host Logic**:
- Track which players are spectating whom
- Send spectated player's state to spectators
- Handle spectator requests

---

## Phase 7: Game Flow Integration

### 7.1 Main Menu Integration
**File**: `screens/menu_screen.py`

**Add Options**:
- "Host Game" button
- "Join Game" button (with IP input)
- Keep existing "New Game" and "Continue" for single-player

**Host Flow**:
1. Click "Host Game"
2. Show IP address (for sharing)
3. Enter lobby screen
4. Wait for players to join
5. Click "Start Game" when ready

**Client Flow**:
1. Click "Join Game"
2. Enter host IP address
3. Connect to host
4. Enter lobby screen
5. Wait for host to start

### 7.2 Game Start Sequence
**File**: `main.py` (modify game initialization)

**Multiplayer Start Flow**:
1. All players in lobby → Host clicks "Start Game"
2. Host broadcasts `GAME_START`
3. All clients transition to character selection (same as single-player)
4. Each player chooses starter (independent, like single-player)
5. Each player sets up rival (independent)
6. All players enter overworld simultaneously
7. Timer starts (5 minutes)

### 7.3 Overworld Integration
**File**: `world/world.py`

**Modify**:
- Check if multiplayer mode
- Sync player positions
- Render other players' avatars (if in view)
- Handle encounters (same as single-player, but sync results)
- Sync wild battles, summoner battles, bosses, rivals (all same as single-player)

**Network Sync Points**:
- Player movement (position updates)
- Encounter triggers (sync to all clients)
- Battle outcomes (sync XP, score, party changes)
- Timer state (host controls, clients receive)

### 7.4 Battle Pairing Logic
**File**: `systems/battle_pairing.py`

**When Timer Hits 0**:
1. Host collects all alive players
2. Randomly pairs players (or use scoring/position)
3. If odd number: one player gets bye (no battle, continues)
4. Send `PvP_BATTLE_START` message to paired players
5. Other players continue in overworld (wait for next timer)

**Pairing Algorithm**:
- Simple: Random shuffle, pair adjacent
- Advanced: Match by score (closest scores fight)
- Advanced: Match by position (closest Y position)

---

## Phase 8: HP System & Elimination

### 8.1 HP Management
**File**: `systems/player_hp.py`

**HP Rules**:
- Start with 2 HP
- Lose 1 HP on battle loss
- When HP reaches 0: player dies
- Dead players cannot participate in battles
- Dead players enter spectator mode

**HP Display**:
- Add HP indicator to HUD
- Show hearts or HP number (e.g., "HP: 2/2")
- Update after each battle

**Network Sync**:
- Host tracks all players' HP
- Broadcast HP updates after battles
- Broadcast death events

### 8.2 Elimination Logic
**File**: `systems/elimination.py`

**Check Conditions**:
- After each battle round, check alive players
- If only 1 player alive: declare winner, end match
- If 2+ players alive: continue to next timer

**Winner Screen**:
- Show winner's name/avatar
- Show final scores
- Option to return to menu or rematch

---

## Phase 9: UI/UX Enhancements

### 9.1 Multiplayer HUD
**File**: `systems/multiplayer_hud.py`

**New HUD Elements**:
- Timer display (top center)
- Player list (alive/dead status)
- HP indicator
- Connection status (for clients)
- "Host" indicator (for host)

**Reuse Existing**:
- All existing HUD elements (party, score, etc.)
- Same styling and positioning

### 9.2 Lobby UI Polish
- Player name display
- Gender selection UI (reuse from char_select)
- Ready indicators
- Connection quality indicators (ping)

### 9.3 Battle UI Modifications
- Show "PvP Battle" indicator
- Show opponent's name
- Show move selection timer
- Disable buttons after selection
- "Waiting for opponent" message

---

## Phase 10: Testing & Polish

### 10.1 Testing Checklist
- [ ] Lobby: Players can join/leave
- [ ] Lobby: Movement syncs correctly
- [ ] Lobby: Host can start game
- [ ] Game Start: All players enter overworld
- [ ] Timer: Countdown works, triggers battles
- [ ] PvP Battle: Moves sync, resolve correctly
- [ ] HP: Updates correctly, elimination works
- [ ] Spectator: Can switch between players
- [ ] Disconnects: Handle gracefully
- [ ] Edge Cases: Odd number of players, host disconnects

### 10.2 Error Handling
- Connection failures
- Host disconnection (migrate host or end game)
- Client disconnection (remove from game)
- Network lag (timeout handling)
- Desync detection (periodic state validation)

### 10.3 Performance Optimization
- Reduce network frequency for non-critical updates
- Client-side prediction for movement
- Interpolation for remote player positions
- Batch messages when possible

---

## Implementation Order (Recommended)

### Week 1: Foundation
1. **Day 1-2**: Networking module (server/client basics)
2. **Day 3-4**: Message system and serialization
3. **Day 5**: Basic connection test (two clients connect)

### Week 2: Lobby
1. **Day 1-2**: Lobby screen (UI and rendering)
2. **Day 3**: Player movement sync in lobby
3. **Day 4**: Gender selection and start game logic
4. **Day 5**: Testing lobby with multiple players

### Week 3: Game Integration
1. **Day 1-2**: Extend GameState for multiplayer
2. **Day 3**: Timer system
3. **Day 4**: Overworld sync (positions, encounters)
4. **Day 5**: Testing multiplayer overworld

### Week 4: PvP Battle
1. **Day 1-2**: PvP battle module (based on battle.py)
2. **Day 3**: Move selection and sync
3. **Day 4**: Battle resolution and HP system
4. **Day 5**: Testing PvP battles

### Week 5: Spectator & Polish
1. **Day 1-2**: Spectator system
2. **Day 3**: Elimination logic and winner screen
3. **Day 4**: UI polish and error handling
4. **Day 5**: Full game testing

---

## File Structure

```
Main/
├── networking/
│   ├── __init__.py
│   ├── server.py          # Host server logic
│   ├── client.py          # Client connection logic
│   ├── messages.py        # Message definitions
│   ├── serialization.py   # GameState serialization
│   ├── state_sync.py      # State synchronization
│   └── lobby_state.py     # Lobby state management
├── screens/
│   ├── multiplayer_lobby.py  # Lobby screen
│   └── spectator.py          # Spectator screen
├── combat/
│   ├── pvp_battle.py         # PvP battle system
│   └── pvp_battle_state.py   # PvP battle state
├── systems/
│   ├── match_timer.py        # Timer system
│   ├── battle_pairing.py     # Battle pairing logic
│   ├── player_hp.py          # HP management
│   ├── elimination.py        # Elimination logic
│   └── multiplayer_hud.py    # Multiplayer HUD
└── game_state.py             # Extended with multiplayer fields
```

---

## Key Design Decisions

### 1. Host Authority
- Host is authoritative for game state
- Clients send actions, host validates and broadcasts
- Prevents cheating and ensures consistency

### 2. Deterministic Battles
- Both clients calculate battle results
- Host validates (should match)
- Reduces network traffic

### 3. Turn-Based PvP
- 30-second timer per move
- Prevents stalling
- Clear turn order

### 4. Spectator Mode
- Dead players can watch
- Keeps engagement
- Simple arrow navigation

### 5. Reuse Existing Systems
- Leverage battle.py logic
- Reuse tavern map/collision
- Keep existing HUD/UI systems
- Minimize code duplication

---

## Potential Challenges & Solutions

### Challenge 1: Network Latency
**Solution**: Client-side prediction, interpolation, timeout handling

### Challenge 2: Desync
**Solution**: Periodic full state sync, host validation

### Challenge 3: Host Disconnection
**Solution**: Host migration (promote client to host) or graceful shutdown

### Challenge 4: NAT/Firewall
**Solution**: Start with LAN, add relay server later if needed

### Challenge 5: Cheating
**Solution**: Host validates all actions, don't trust client data

---

## Success Criteria

✅ Players can join lobby and see each other  
✅ Host can start game  
✅ All players enter overworld simultaneously  
✅ Timer counts down and triggers battles  
✅ PvP battles work correctly (moves sync, resolve)  
✅ HP system works (lose HP on loss, die at 0)  
✅ Dead players can spectate  
✅ Game ends when 1 player remains  
✅ All existing features still work (wild battles, bosses, etc.)  

---

## Notes

- Keep single-player mode intact (don't break existing functionality)
- Add multiplayer as optional mode (menu choice)
- Test thoroughly with 2-8 players
- Consider adding replay/recording system later
- May want to add matchmaking server later (for easier connection)

