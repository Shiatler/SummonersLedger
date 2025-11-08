# ============================================================
# systems/buff_applicator.py — Buff Application Logic
# Handles applying blessing effects to game state
# ============================================================

import random
from typing import Optional, Callable, Tuple, List

# Result card state (for displaying dice roll results)
_RESULT_CARD = None

def show_result_card(title: str, subtitle: str, play_dice_sound: bool = False):
    """Show a result card with title and subtitle.
    play_dice_sound: If True, plays the dice roll sound effect.
    """
    global _RESULT_CARD
    
    # Play dice roll sound if requested
    if play_dice_sound:
        try:
            from rolling.sfx import play_dice
            play_dice()
        except Exception as e:
            print(f"⚠️ Failed to play dice sound: {e}")
    
    _RESULT_CARD = {
        "title": title,
        "subtitle": subtitle,
        "active": True,
        "dismissed": False,
    }
    print(f"🔔 Result card shown: {title} - {subtitle}")

def is_result_card_active() -> bool:
    """Check if result card is currently showing."""
    return _RESULT_CARD is not None and _RESULT_CARD.get("active", False) and not _RESULT_CARD.get("dismissed", False)

def dismiss_result_card():
    """Dismiss the current result card."""
    global _RESULT_CARD
    if _RESULT_CARD:
        _RESULT_CARD["dismissed"] = True
        _RESULT_CARD["active"] = False

def get_result_card() -> Optional[dict]:
    """Get the current result card data."""
    return _RESULT_CARD

def clear_result_card():
    """Clear the result card."""
    global _RESULT_CARD
    _RESULT_CARD = None


# Buff application state
_BUFF_APPLICATION_STATE = None

def set_buff_application_state(state: dict):
    """Set the current buff application state."""
    global _BUFF_APPLICATION_STATE
    _BUFF_APPLICATION_STATE = state

def get_buff_application_state() -> Optional[dict]:
    """Get the current buff application state."""
    return _BUFF_APPLICATION_STATE

def clear_buff_application_state():
    """Clear the buff application state."""
    global _BUFF_APPLICATION_STATE
    _BUFF_APPLICATION_STATE = None


def apply_common_blessing(gs, card_name: str, card_data: dict):
    """
    Apply a Common tier blessing.
    Returns a dict with 'action' and related data for the UI to handle.
    """
    if card_name == "Common1":
        # Minor Echo: 1x stat to 1 vessel (max of 20)
        return {
            "action": "stat_selection",
            "blessing": "Common1",
            "description": "1x stat to 1 vessel (max of 20)",
            "stat_bonus": 1,
            "max_stat": 20,
        }
    
    elif card_name == "Common2":
        # Blood Vial: 1d4 hp to 1 vessel (1 time roll)
        return {
            "action": "hp_roll",
            "blessing": "Common2",
            "description": "1d4 hp to 1 vessel",
            "dice": (1, 4),
        }
    
    elif card_name == "Common3":
        # Swift Strike: +2 PP to 1 move
        return {
            "action": "pp_bonus",
            "blessing": "Common3",
            "description": "+2 PP to 1 move",
            "pp_amount": 2,
        }
    
    elif card_name == "Common4":
        # Healer's Satchel: +5 scroll of mending
        return apply_inventory_blessing(gs, "scroll_of_mending", 5)
    
    elif card_name == "Common5":
        # Binder's Supply: +5 scroll of command
        return apply_inventory_blessing(gs, "scroll_of_command", 5)
    
    elif card_name == "Common6":
        # Memory Shard: +1d6 XP to 1 Vessel
        return {
            "action": "xp_roll",
            "blessing": "Common6",
            "description": "+1d6 XP to 1 Vessel",
            "dice": (1, 6),
        }
    
    elif card_name == "Common7":
        # Binding Pouch: +2 Scrolls of Sealing
        return apply_inventory_blessing(gs, "scroll_of_sealing", 2)
    
    elif card_name == "Common8":
        # Healing Pouch: +2 Scrolls of Healing
        return apply_inventory_blessing(gs, "scroll_of_healing", 2)
    
    elif card_name == "Common9":
        # Sharpened Knife: +1 permanent damage to attacks for 1 Vessel
        return {
            "action": "permanent_damage",
            "blessing": "Common9",
            "description": "+1 permanent damage to attacks",
            "damage_bonus": 1,
        }
    
    return {"action": "none"}


def apply_rare_blessing(gs, card_name: str, card_data: dict):
    """
    Apply a Rare tier blessing.
    Returns a dict with 'action' and related data for the UI to handle.
    """
    if card_name == "Rare1":
        # Ward of Resistance: -1d2 dmg from enemy attacks (choose vessel, roll, permanent -dmg)
        return {
            "action": "damage_reduction_roll",
            "blessing": "Rare1",
            "description": "-1d2 dmg from enemy attacks",
            "dice": (1, 2),
        }
    
    elif card_name == "Rare2":
        # Pactbinder's Bundle: +5 Scrolls of Subjugation
        return apply_inventory_blessing(gs, "scroll_of_subjugation", 5)
    
    elif card_name == "Rare3":
        # Echo Infusion: +1 to all stat rolls for the next Vessel you capture
        set_next_capture_stat_bonus(gs, 1)
        return {
            "action": "complete",
            "message": "Next captured vessel will gain +1 to all D&D stats",
        }
    
    elif card_name == "Rare4":
        # Focused Spirit: +5 PP to 1 move
        return {
            "action": "pp_bonus",
            "blessing": "Rare4",
            "description": "+5 PP to 1 move",
            "pp_amount": 5,
        }
    
    elif card_name == "Rare5":
        # Unstable Echo: +2 random stats to 1 random Vessel
        return {
            "action": "random_stat_random_vessel",
            "blessing": "Rare5",
            "description": "+2 random stats to 1 random Vessel",
            "stat_bonus": 1,
            "num_stats": 2,
        }
    
    return {"action": "none"}


def apply_hp_to_all_vessels(gs, hp_amount: int) -> bool:
    """
    Apply HP bonus/penalty to all vessels in the party.
    This permanently modifies max HP for all vessels.
    hp_amount can be negative for penalties.
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    vessels_updated = 0
    for i, stats in enumerate(stats_list):
        if isinstance(stats, dict) and names[i]:
            # Vessel exists - apply HP change (can be negative for penalties)
            current_max_hp = int(stats.get("hp", 10))
            current_hp = int(stats.get("current_hp", current_max_hp))
            
            # Apply HP change (can be negative)
            new_max_hp = max(1, current_max_hp + hp_amount)  # Ensure HP doesn't go below 1
            stats["hp"] = new_max_hp
            
            # Adjust current HP: maintain ratio if not full, or cap at new max if full
            if current_hp >= current_max_hp:
                # Was at full health, cap at new max (or reduce if penalty)
                stats["current_hp"] = new_max_hp
            else:
                # Keep same current HP (so they don't lose HP, but ratio changes)
                # But if max HP was reduced, we need to cap current HP
                stats["current_hp"] = max(1, min(current_hp, new_max_hp))
            
            stats_list[i] = stats
            vessels_updated += 1
    
    if vessels_updated > 0:
        gs.party_vessel_stats = stats_list
        change_str = f"+{hp_amount}" if hp_amount >= 0 else str(hp_amount)
        print(f"✨ Applied {change_str} HP to {vessels_updated} vessel(s)")
        return True
    
    return False


def apply_epic_blessing(gs, card_name: str, card_data: dict):
    """
    Apply an Epic tier blessing.
    Returns a dict with 'action' and related data for the UI to handle.
    """
    if card_name == "Epic1":
        # Sigil of Protection: +1 AC to 1 vessel
        return {
            "action": "ac_bonus",
            "blessing": "Epic1",
            "description": "+1 AC to 1 vessel",
            "ac_amount": 1,
        }
    
    elif card_name == "Epic2":
        # Elixir of Endurance: 1d10 HP to 1 vessel
        return {
            "action": "hp_roll",
            "blessing": "Epic2",
            "description": "1d10 HP to 1 vessel",
            "dice": (1, 10),
        }
    
    elif card_name == "Epic3":
        # Shared Vitality: 1d4 HP to all vessels
        return {
            "action": "hp_all_roll",
            "blessing": "Epic3",
            "description": "1d4 HP to all vessels",
            "dice": (1, 4),
        }
    
    elif card_name == "Epic4":
        # Arcane Overflow: +10 PP to 1 move
        return {
            "action": "pp_bonus",
            "blessing": "Epic4",
            "description": "+10 PP to 1 move",
            "pp_amount": 10,
        }
    
    return {"action": "none"}


def apply_legendary_blessing(gs, card_name: str, card_data: dict):
    """
    Apply a Legendary tier blessing.
    Returns a dict with 'action' and related data for the UI to handle.
    """
    if card_name == "Legendary1":
        # Ward of the Eternal Guard: +1 AC to all vessels
        # Applies directly to all vessels, no selection needed
        return {
            "action": "ac_all",
            "blessing": "Legendary1",
            "description": "+1 AC to all vessels",
            "ac_amount": 1,
        }
    
    elif card_name == "Legendary2":
        # Grand Resonance: +1 stat to all vessels
        return {
            "action": "stat_all_selection",
            "blessing": "Legendary2",
            "description": "+1 stat to all vessels",
            "stat_bonus": 1,
        }
    
    elif card_name == "Legendary3":
        # Vital Convergence: 1d20 HP to 1 vessel
        return {
            "action": "hp_roll",
            "blessing": "Legendary3",
            "description": "1d20 HP to 1 vessel",
            "dice": (1, 20),
        }
    
    elif card_name == "Legendary4":
        # Guardian's Boon: +1 AC and +1d10 HP to 1 vessel
        return {
            "action": "ac_and_hp_roll",
            "blessing": "Legendary4",
            "description": "+1 AC and +1d10 HP to 1 vessel",
            "ac_amount": 1,
            "dice": (1, 10),
        }
    
    elif card_name == "Legendary5":
        # Blessing of Restoration: Healing items heal for 1d8 more
        # Roll 1d8 and store the result as a permanent healing bonus
        from rolling.roller import roll_dice
        total, rolls = roll_dice(1, 8)
        print(f"🔔 Rolled 1d8 for Blessing of Restoration: {rolls} = {total}")
        
        # Store the healing bonus in game state
        if not hasattr(gs, "healing_bonus"):
            gs.healing_bonus = 0
        gs.healing_bonus = total
        
        # Show result card
        show_result_card(
            f"Rolled 1d8",
            f"Result: +{total} healing bonus to all healing items",
            play_dice_sound=True
        )
        
        return {
            "action": "result_card",
            "blessing": "Legendary5",
            "description": f"Healing items heal for +{total} more",
        }
    
    elif card_name == "Legendary6":
        # Scroll of Eternity: +1 Scroll of Eternity
        return apply_inventory_blessing(gs, "scroll_of_eternity", 1)
    
    return {"action": "none"}


def apply_demonpact_blessing(gs, card_name: str, card_data: dict):
    """
    Apply a DemonPact tier blessing.
    Returns a dict with 'action' and related data for the UI to handle.
    """
    if card_name == "DemonPact1":
        # Hell-Forged Hide: Damage reduction 1d6 for entire party
        return {
            "action": "damage_reduction_all_roll",
            "blessing": "DemonPact1",
            "description": "Damage reduction 1d6 for entire party",
            "dice": (1, 6),
        }
    
    elif card_name == "DemonPact2":
        # Infernal Rebirth: First death each battle restores Vessel to 50% HP once per run
        # This is a passive effect, so just mark it as complete
        return {
            "action": "complete",
            "message": "Infernal Rebirth: First death each battle restores to 50% HP (once per run)",
        }
    
    elif card_name == "DemonPact3":
        # Demonheart Surge: 1d20 HP to all vessels
        return {
            "action": "hp_all_roll",
            "blessing": "DemonPact3",
            "description": "1d20 HP to all vessels",
            "dice": (1, 20),
        }
    
    elif card_name == "DemonPact4":
        # Pact of the Legion: +1d6 bonus damage for entire party
        return {
            "action": "permanent_damage_all_roll",
            "blessing": "DemonPact4",
            "description": "+1d6 bonus dmg for entire party",
            "dice": (1, 6),
        }
    
    return {"action": "none"}


def apply_curse_blessing(gs, card_name: str, card_data: dict):
    """
    Apply a Curse tier blessing.
    Returns a dict with 'action' and related data for the UI to handle.
    """
    if card_name == "Curse1":
        # Scream of Terror: +1 to one stat of choice / -1 to another stat of choice
        return {
            "action": "stat_plus_minus_selection",
            "blessing": "Curse1",
            "description": "+1 to one stat / -1 to another stat",
            "stat_plus": 1,
            "stat_minus": 1,
        }
    
    elif card_name == "Curse2":
        # Haunting of Flesh: +2 to one stat of choice / -1 to another random stat
        return {
            "action": "stat_plus_random_minus",
            "blessing": "Curse2",
            "description": "+2 to one stat / -1 to random stat",
            "stat_plus": 2,
            "stat_minus": 1,
        }
    
    elif card_name == "Curse3":
        # Bleeding Moon: +1 AC to all vessels / -1d8 HP to every vessel
        return {
            "action": "ac_all_hp_roll_minus",
            "blessing": "Curse3",
            "description": "+1 AC to all vessels / -1d8 HP to every vessel",
            "ac_amount": 1,
            "dice": (1, 8),
        }
    
    elif card_name == "Curse4":
        # The Hollow's Embrace: +1 random stat / -1 stat of choice
        return {
            "action": "stat_random_plus_minus_selection",
            "blessing": "Curse4",
            "description": "+1 random stat / -1 stat of choice",
            "stat_plus": 1,
            "stat_minus": 1,
        }
    
    elif card_name == "Curse5":
        # Dirge of the Dead: +2 to one stat / -1d12 HP permanently
        return {
            "action": "stat_plus_hp_roll_minus",
            "blessing": "Curse5",
            "description": "+2 to one stat / -1d12 HP",
            "stat_plus": 2,
            "dice": (1, 12),
        }
    
    return {"action": "none"}


def apply_punishment_blessing(gs, card_name: str, card_data: dict):
    """
    Apply a Punishment tier blessing.
    Returns a dict with 'action' and related data for the UI to handle.
    """
    if card_name == "Punishment1":
        # Oathbreaker's Tribute: -10 gold
        return {
            "action": "gold_deduction",
            "blessing": "Punishment1",
            "description": "-10 gold",
            "gold_amount": 10,
        }
    
    elif card_name == "Punishment2":
        # Weight of Sin: -2 random stats (choose vessel)
        return {
            "action": "stat_random_penalty_selection",
            "blessing": "Punishment2",
            "description": "-2 random stats",
            "stat_penalty": 2,
            "num_stats": 2,
        }
    
    elif card_name == "Punishment3":
        # Broken Aegis: -1 AC to a random vessel
        return {
            "action": "ac_penalty_random_vessel",
            "blessing": "Punishment3",
            "description": "-1 AC to a random vessel",
            "ac_penalty": 1,
        }
    
    elif card_name == "Punishment4":
        # Judgment's Cut: -1d6 HP (choose vessel)
        return {
            "action": "hp_roll_penalty",
            "blessing": "Punishment4",
            "description": "-1d6 HP",
            "dice": (1, 6),
        }
    
    elif card_name == "Punishment5":
        # Oathbreaker's Toll: -1 Vessel (choose vessel to remove)
        return {
            "action": "remove_vessel",
            "blessing": "Punishment5",
            "description": "-1 Vessel",
        }
    
    return {"action": "none"}


def apply_gold_deduction(gs, gold_amount: int) -> tuple[bool, int]:
    """
    Deduct gold from the player.
    Returns (success: bool, actual_amount_deducted: int).
    Will not go below 0 (if player has 9 gold and we deduct 10, only 9 is deducted).
    """
    if not hasattr(gs, "gold"):
        gs.gold = 0
    
    current_gold = gs.gold
    actual_deduction = min(gold_amount, current_gold)  # Don't go below 0
    gs.gold = max(0, current_gold - gold_amount)
    
    print(f"💸 Deducted {actual_deduction} gold (had {current_gold}, now {gs.gold})")
    return True, actual_deduction


def apply_random_stat_penalties(gs, vessel_idx: int, penalty: int, num_stats: int = 2) -> tuple[bool, list[str]]:
    """
    Apply random stat penalties to a vessel.
    Returns (success: bool, list of stat names that were penalized).
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    if not (0 <= vessel_idx < len(stats_list)):
        return False, []
    
    vessel_stats = stats_list[vessel_idx]
    if not isinstance(vessel_stats, dict):
        return False, []
    
    # Get abilities dict
    abilities = vessel_stats.get("abilities", {})
    if not isinstance(abilities, dict):
        return False, []
    
    # Get all D&D stats (STR, DEX, CON, INT, WIS, CHA)
    ability_names = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    # Only stats that can be reduced (value > penalty, so reducing by penalty won't go below 1)
    available_stats = [stat for stat in ability_names if abilities.get(stat, 10) > penalty]
    
    if len(available_stats) < num_stats:
        # Not enough stats available, use what we have
        stats_to_penalize = available_stats
    else:
        # Pick random stats (without replacement)
        import random
        stats_to_penalize = random.sample(available_stats, num_stats)
    
    if not stats_to_penalize:
        return False, []
    
    # Apply penalties
    penalized_stats = []
    for stat_name in stats_to_penalize:
        if apply_stat_penalty(gs, vessel_idx, stat_name, penalty):
            penalized_stats.append(stat_name)
    
    if penalized_stats:
        print(f"✨ Applied -{penalty} to {', '.join(penalized_stats)} for vessel {vessel_idx}")
        return True, penalized_stats
    
    return False, []


def apply_ac_penalty_to_random_vessel(gs, ac_penalty: int) -> tuple[bool, Optional[int], Optional[str]]:
    """
    Apply AC penalty to a random vessel.
    Returns (success: bool, vessel_idx: Optional[int], vessel_name: Optional[str]).
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    # Find all vessels that exist
    available_vessels = []
    for i, stats in enumerate(stats_list):
        if isinstance(stats, dict) and names[i]:
            available_vessels.append(i)
    
    if not available_vessels:
        return False, None, None
    
    # Pick a random vessel
    import random
    vessel_idx = random.choice(available_vessels)
    vessel_name = names[vessel_idx]
    
    # Apply AC penalty (negative bonus)
    if apply_ac_bonus(gs, vessel_idx, -ac_penalty):
        return True, vessel_idx, vessel_name
    
    return False, None, None


def remove_vessel_from_party(gs, vessel_idx: int) -> tuple[bool, Optional[str]]:
    """
    Remove a vessel from the party permanently.
    Returns (success: bool, vessel_name: Optional[str]).
    Also handles updating active vessel indices if the removed vessel was active.
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    slots = getattr(gs, "party_slots", None) or [None] * 6
    
    if not (0 <= vessel_idx < len(names)):
        return False, None
    
    # Get vessel name before removal (for display)
    vessel_name = names[vessel_idx] if vessel_idx < len(names) else None
    
    # Check if vessel exists
    if not vessel_name or not stats_list[vessel_idx]:
        return False, None
    
    # Remove vessel from all party data structures
    names[vessel_idx] = None
    stats_list[vessel_idx] = None
    slots[vessel_idx] = None
    
    # Update game state
    gs.party_slots_names = names
    gs.party_vessel_stats = stats_list
    gs.party_slots = slots
    
    # Handle active vessel indices
    # Check if this was the party active vessel
    party_active_idx = getattr(gs, "party_active_idx", 0)
    if party_active_idx == vessel_idx:
        # Find the first available vessel to set as active
        new_active_idx = None
        for i in range(6):
            if names[i] and stats_list[i]:
                new_active_idx = i
                break
        
        if new_active_idx is not None:
            gs.party_active_idx = new_active_idx
            print(f"🔄 Set new active vessel to slot {new_active_idx}")
        else:
            # No vessels left - clear active index
            if hasattr(gs, "party_active_idx"):
                delattr(gs, "party_active_idx")
            print(f"⚠️ No vessels remaining after removal")
    
    # Check if this was the combat active vessel
    if hasattr(gs, "combat_active_idx"):
        combat_active_idx = getattr(gs, "combat_active_idx", 0)
        if combat_active_idx == vessel_idx:
            # Find the first available vessel to set as combat active
            new_active_idx = None
            for i in range(6):
                if names[i] and stats_list[i]:
                    new_active_idx = i
                    break
            
            if new_active_idx is not None:
                gs.combat_active_idx = new_active_idx
                print(f"🔄 Set new combat active vessel to slot {new_active_idx}")
            else:
                # No vessels left - clear combat active index
                delattr(gs, "combat_active_idx")
                print(f"⚠️ No vessels remaining in combat after removal")
    
    print(f"💀 Removed vessel {vessel_idx} from party (name: {vessel_name})")
    return True, vessel_name


def _format_item_name(item_id: str, quantity: int) -> str:
    """Format item name for display (e.g., 'scroll_of_command' -> 'scrolls of command')."""
    # Convert item_id to readable format
    name = item_id.replace("_", " ").lower()
    
    # Handle pluralization for scrolls
    if name.startswith("scroll"):
        # "scroll of command" -> "scrolls of command" (if quantity > 1)
        if quantity == 1:
            return name
        else:
            # Add 's' to 'scroll' but keep 'of X' the same
            if " of " in name:
                parts = name.split(" of ", 1)
                return f"{parts[0]}s of {parts[1]}"
            else:
                return f"{name}s"
    
    # For other items, just pluralize if needed
    if quantity == 1:
        return name
    else:
        return f"{name}s"

def apply_inventory_blessing(gs, item_id: str, quantity: int) -> dict:
    """Apply an inventory blessing (add items and show result card)."""
    if not hasattr(gs, "inventory"):
        gs.inventory = {}
    
    current = gs.inventory.get(item_id, 0)
    gs.inventory[item_id] = current + quantity
    
    # Format item name for display
    item_name = _format_item_name(item_id, quantity)
    
    # Create title (e.g., "+5 Scrolls" or "+2 Scrolls")
    if " of " in item_name:
        # "scrolls of command" -> "Scrolls"
        title_part = item_name.split(" of ")[0].title()
    else:
        title_part = item_name.title()
    title = f"+{quantity} {title_part}"
    
    # Create message
    message = f"You store away {quantity} {item_name} in your bag of holding"
    
    print(f"✨ Added {quantity} {item_name} to inventory")
    
    # Show result card
    show_result_card(title, message)
    
    return {
        "action": "inventory_result",
        "message": message,
        "item_id": item_id,
        "quantity": quantity,
    }


def apply_stat_bonus(gs, vessel_idx: int, stat_name: str, bonus: int, max_stat: Optional[int] = None) -> bool:
    """
    Apply a stat bonus to a vessel.
    Returns True if successful, False otherwise.
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    if not (0 <= vessel_idx < len(stats_list)):
        return False
    
    vessel_stats = stats_list[vessel_idx]
    if not isinstance(vessel_stats, dict):
        return False
    
    # Get abilities dict
    abilities = vessel_stats.get("abilities", {})
    if not isinstance(abilities, dict):
        abilities = {}
        vessel_stats["abilities"] = abilities
    
    # Get current stat value
    current_value = abilities.get(stat_name, 10)
    
    # Apply bonus (can be negative for penalties)
    new_value = current_value + bonus
    
    # Ensure stat doesn't go below 1 (minimum stat value)
    new_value = max(1, new_value)
    
    # Apply max cap if specified
    if max_stat is not None:
        new_value = min(new_value, max_stat)
    
    # Update stat
    abilities[stat_name] = new_value
    vessel_stats["abilities"] = abilities
    
    # Recalculate modifier
    from rolling.roller import ability_mod
    mods = vessel_stats.get("mods", {})
    if not isinstance(mods, dict):
        mods = {}
    mods[stat_name] = ability_mod(new_value)
    vessel_stats["mods"] = mods
    
    # Update stats list
    stats_list[vessel_idx] = vessel_stats
    gs.party_vessel_stats = stats_list
    
    bonus_str = f"+{bonus}" if bonus >= 0 else str(bonus)
    print(f"✨ Applied {bonus_str} to {stat_name} for vessel {vessel_idx} (now {new_value})")
    return True


def apply_stat_penalty(gs, vessel_idx: int, stat_name: str, penalty: int) -> bool:
    """
    Apply a stat penalty to a vessel (reduces stat value).
    Returns True if successful, False otherwise.
    This is essentially apply_stat_bonus with a negative value, but kept separate for clarity.
    """
    return apply_stat_bonus(gs, vessel_idx, stat_name, -penalty)


def apply_hp_bonus(gs, vessel_idx: int, hp_amount: int) -> bool:
    """
    Apply HP bonus to a vessel's MAX HP (permanent buff).
    This increases the maximum HP the vessel can have.
    Current HP is adjusted to maintain ratio or capped at new max.
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    if not (0 <= vessel_idx < len(stats_list)):
        return False
    
    vessel_stats = stats_list[vessel_idx]
    if not isinstance(vessel_stats, dict):
        return False
    
    old_max_hp = int(vessel_stats.get("hp", 10))
    old_current_hp = int(vessel_stats.get("current_hp", old_max_hp))
    
    # Apply HP change (can be negative for penalties)
    new_max_hp = max(1, old_max_hp + hp_amount)  # Ensure HP doesn't go below 1
    vessel_stats["hp"] = new_max_hp
    
    # Adjust current_hp:
    # - If current_hp was at max, keep it at new max
    # - Otherwise, maintain the same HP value (so percentage decreases slightly, but actual HP stays same)
    if old_current_hp >= old_max_hp:
        # Was at full health, keep at full (or new max if reduced)
        new_current_hp = new_max_hp
    else:
        # Keep same current HP (so they don't lose HP, but ratio changes)
        # But if max HP was reduced, we need to cap current HP
        new_current_hp = max(1, min(old_current_hp, new_max_hp))
    
    vessel_stats["current_hp"] = new_current_hp
    
    stats_list[vessel_idx] = vessel_stats
    gs.party_vessel_stats = stats_list
    
    change_str = f"+{hp_amount}" if hp_amount >= 0 else str(hp_amount)
    print(f"✨ Applied {change_str} MAX HP to vessel {vessel_idx} (max: {old_max_hp} → {new_max_hp}, current: {old_current_hp} → {new_current_hp})")
    return True


def apply_hp_penalty(gs, vessel_idx: int, hp_penalty: int) -> bool:
    """
    Apply HP penalty to a vessel's MAX HP (permanent debuff).
    This reduces max HP permanently.
    """
    return apply_hp_bonus(gs, vessel_idx, -hp_penalty)


def apply_xp_bonus(gs, vessel_idx: int, xp_amount: int) -> bool:
    """
    Apply XP bonus to a vessel and handle level-ups.
    Uses the same XP system as combat (xp_current, xp_needed, level-ups).
    """
    from systems import xp
    
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    if not (0 <= vessel_idx < len(stats_list)):
        return False
    
    vessel_stats = stats_list[vessel_idx]
    if not isinstance(vessel_stats, dict):
        return False
    
    # Ensure XP profile is initialized
    xp.ensure_profile(gs)
    
    # Get current level and XP
    lvl = int(vessel_stats.get("level", 1))
    xp_current = int(vessel_stats.get("xp_current", 0))
    xp_total = int(vessel_stats.get("xp_total", 0))
    
    # Add XP
    xp_current += xp_amount
    xp_total += xp_amount
    vessel_stats["xp_total"] = xp_total
    
    # Handle level-ups (may chain if enough XP)
    levelups = []
    while lvl < xp.MAX_LEVEL and xp_current >= xp.xp_needed(lvl):
        xp_needed_for_level = xp.xp_needed(lvl)
        xp_current -= xp_needed_for_level
        old_lvl = lvl
        lvl += 1
        levelups.append((vessel_idx, old_lvl, lvl))
        
        # Apply level-up (rebuilds stats, handles HP, etc.)
        xp.apply_level_up(gs, vessel_idx, lvl)
        
        # Re-get stats after level-up (they may have been updated)
        vessel_stats = stats_list[vessel_idx]
        if not isinstance(vessel_stats, dict):
            break
    
    # Update XP fields
    vessel_stats["xp_current"] = xp_current
    vessel_stats["level"] = lvl
    vessel_stats["xp_needed"] = xp.xp_needed(lvl)
    
    stats_list[vessel_idx] = vessel_stats
    gs.party_vessel_stats = stats_list
    
    # Print results
    if levelups:
        levelup_text = ", ".join([f"L{old}→L{new}" for _, old, new in levelups])
        print(f"✨ Applied +{xp_amount} XP to vessel {vessel_idx} (now {xp_current}/{vessel_stats['xp_needed']} XP, Level-ups: {levelup_text})")
    else:
        print(f"✨ Applied +{xp_amount} XP to vessel {vessel_idx} (now {xp_current}/{vessel_stats['xp_needed']} XP)")
    
    return True


def apply_pp_bonus(gs, vessel_idx: int, move_id: str, pp_amount: int) -> bool:
    """
    Apply PP bonus to a vessel's move's MAX PP (permanent buff).
    This increases the maximum PP the move can have.
    """
    # Initialize move_pp_max_bonuses if it doesn't exist
    if not hasattr(gs, "move_pp_max_bonuses"):
        gs.move_pp_max_bonuses = {}
    
    # Create key: vessel_token_name:move_id
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    if not (0 <= vessel_idx < len(names)) or not names[vessel_idx]:
        return False
    
    vessel_token = str(names[vessel_idx])
    key = f"{vessel_token}:{move_id}"
    
    # Get current bonus (if any)
    current_bonus = gs.move_pp_max_bonuses.get(key, 0)
    
    # Add to the bonus (accumulative - multiple blessings stack)
    new_bonus = current_bonus + pp_amount
    gs.move_pp_max_bonuses[key] = new_bonus
    
    # Get the move's base max_pp directly from the Move object
    try:
        from combat.moves import _MOVE_REGISTRY
        # Find the move in the registry to get its base max_pp
        base_max_pp = None
        for move_list in _MOVE_REGISTRY.values():
            for move in move_list:
                if move.id == move_id:
                    base_max_pp = move.max_pp
                    break
            if base_max_pp is not None:
                break
        
        if base_max_pp is not None:
            new_total_max = base_max_pp + new_bonus
        else:
            new_total_max = None
    except Exception as e:
        print(f"⚠️ Failed to get base max_pp for move {move_id}: {e}")
        new_total_max = None
    
    print(f"✨ Applied +{pp_amount} MAX PP to {move_id} for vessel {vessel_idx} (total bonus: +{new_bonus}, new max: {new_total_max})")
    return True


def apply_permanent_damage_bonus(gs, vessel_idx: int, damage_bonus: int) -> bool:
    """Apply permanent damage bonus to a vessel."""
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    if not (0 <= vessel_idx < len(stats_list)):
        return False
    
    vessel_stats = stats_list[vessel_idx]
    if not isinstance(vessel_stats, dict):
        return False
    
    # Get or initialize permanent damage bonus
    current_bonus = vessel_stats.get("permanent_damage_bonus", 0)
    vessel_stats["permanent_damage_bonus"] = current_bonus + damage_bonus
    
    stats_list[vessel_idx] = vessel_stats
    gs.party_vessel_stats = stats_list
    
    print(f"✨ Applied +{damage_bonus} permanent damage bonus to vessel {vessel_idx}")
    return True


def apply_permanent_damage_bonus_to_all_vessels(gs, damage_bonus: int) -> bool:
    """
    Apply permanent damage bonus to all vessels in the party.
    This increases all outgoing damage by the specified amount for all vessels.
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    vessels_updated = 0
    for i, stats in enumerate(stats_list):
        if isinstance(stats, dict) and names[i]:
            # Vessel exists - apply permanent damage bonus
            current_bonus = stats.get("permanent_damage_bonus", 0)
            stats["permanent_damage_bonus"] = current_bonus + damage_bonus
            
            stats_list[i] = stats
            vessels_updated += 1
    
    if vessels_updated > 0:
        gs.party_vessel_stats = stats_list
        print(f"✨ Applied +{damage_bonus} permanent damage bonus to {vessels_updated} vessel(s)")
        return True
    
    return False


def apply_ac_bonus(gs, vessel_idx: int, ac_bonus: int) -> bool:
    """
    Apply AC bonus to a vessel permanently.
    This increases both the ac_bonus field (for persistence) and updates the base ac field.
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    if not (0 <= vessel_idx < len(stats_list)):
        print(f"⚠️ apply_ac_bonus: Invalid vessel_idx {vessel_idx}")
        return False
    
    vessel_stats = stats_list[vessel_idx]
    if not isinstance(vessel_stats, dict):
        print(f"⚠️ apply_ac_bonus: Vessel stats is not a dict for vessel {vessel_idx}")
        return False
    
    # Get current AC (this might already include previous bonuses)
    current_ac = int(vessel_stats.get("ac", 10))
    current_bonus = vessel_stats.get("ac_bonus", 0)
    
    # Ensure AC doesn't go below 1
    new_ac = max(1, current_ac + ac_bonus)
    
    # Update the ac_bonus field (for persistence through level-ups)
    vessel_stats["ac_bonus"] = current_bonus + ac_bonus
    
    # Update the actual ac field to reflect the new total
    vessel_stats["ac"] = new_ac
    
    stats_list[vessel_idx] = vessel_stats
    gs.party_vessel_stats = stats_list
    
    change_str = f"+{ac_bonus}" if ac_bonus >= 0 else str(ac_bonus)
    print(f"✨ Applied {change_str} AC bonus to vessel {vessel_idx} (old AC: {current_ac}, new AC: {vessel_stats['ac']}, ac_bonus field: {vessel_stats['ac_bonus']})")
    return True


def apply_ac_bonus_to_all_vessels(gs, ac_bonus: int) -> tuple[bool, int]:
    """
    Apply AC bonus to all vessels in the party.
    This permanently increases AC for all vessels.
    Returns (success: bool, vessels_updated: int)
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    vessels_updated = 0
    for i, stats in enumerate(stats_list):
        if isinstance(stats, dict) and names[i]:
            # Vessel exists - apply AC bonus
            current_ac = int(stats.get("ac", 10))
            current_bonus = stats.get("ac_bonus", 0)
            
            # Ensure AC doesn't go below 1
            new_ac = max(1, current_ac + ac_bonus)
            
            # Update the ac_bonus field (for persistence through level-ups)
            stats["ac_bonus"] = current_bonus + ac_bonus
            
            # Update the actual ac field to reflect the new total
            stats["ac"] = new_ac
            
            stats_list[i] = stats
            vessels_updated += 1
    
    if vessels_updated > 0:
        gs.party_vessel_stats = stats_list
        print(f"✨ Applied +{ac_bonus} AC bonus to {vessels_updated} vessel(s)")
        return True, vessels_updated
    
    return False, 0


def apply_stat_bonus_to_all_vessels(gs, stat_name: str, bonus: int, max_stat: Optional[int] = None) -> bool:
    """
    Apply a stat bonus to all vessels in the party.
    This permanently increases the specified stat for all vessels.
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    vessels_updated = 0
    for i, stats in enumerate(stats_list):
        if isinstance(stats, dict) and names[i]:
            # Vessel exists - apply stat bonus
            # Get abilities dict
            abilities = stats.get("abilities", {})
            if not isinstance(abilities, dict):
                abilities = {}
                stats["abilities"] = abilities
            
            # Get current stat value
            current_value = abilities.get(stat_name, 10)
            
            # Apply bonus
            new_value = current_value + bonus
            
            # Apply max cap if specified
            if max_stat is not None:
                new_value = min(new_value, max_stat)
            
            # Update stat
            abilities[stat_name] = new_value
            stats["abilities"] = abilities
            
            # Recalculate modifier
            from rolling.roller import ability_mod
            mods = stats.get("mods", {})
            if not isinstance(mods, dict):
                mods = {}
            mods[stat_name] = ability_mod(new_value)
            stats["mods"] = mods
            
            stats_list[i] = stats
            vessels_updated += 1
    
    if vessels_updated > 0:
        gs.party_vessel_stats = stats_list
        print(f"✨ Applied +{bonus} to {stat_name} for {vessels_updated} vessel(s)")
        return True
    
    return False


def apply_damage_reduction(gs, vessel_idx: int, reduction_amount: int) -> bool:
    """
    Apply permanent damage reduction to a vessel.
    This reduces all incoming damage by the specified amount.
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    if not (0 <= vessel_idx < len(stats_list)):
        return False
    
    vessel_stats = stats_list[vessel_idx]
    if not isinstance(vessel_stats, dict):
        return False
    
    # Get or initialize damage reduction (stacks additively)
    current_reduction = vessel_stats.get("damage_reduction", 0)
    vessel_stats["damage_reduction"] = current_reduction + reduction_amount
    
    stats_list[vessel_idx] = vessel_stats
    gs.party_vessel_stats = stats_list
    
    print(f"✨ Applied -{reduction_amount} damage reduction to vessel {vessel_idx} (total: -{vessel_stats['damage_reduction']})")
    return True


def apply_damage_reduction_to_all_vessels(gs, reduction_amount: int) -> bool:
    """
    Apply permanent damage reduction to all vessels in the party.
    This reduces all incoming damage by the specified amount for all vessels.
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    vessels_updated = 0
    for i, stats in enumerate(stats_list):
        if isinstance(stats, dict) and names[i]:
            # Vessel exists - apply damage reduction
            current_reduction = stats.get("damage_reduction", 0)
            stats["damage_reduction"] = current_reduction + reduction_amount
            
            stats_list[i] = stats
            vessels_updated += 1
    
    if vessels_updated > 0:
        gs.party_vessel_stats = stats_list
        print(f"✨ Applied -{reduction_amount} damage reduction to {vessels_updated} vessel(s)")
        return True
    
    return False


def set_next_capture_stat_bonus(gs, stat_bonus: int) -> bool:
    """
    Set a stat bonus to be applied to the next captured vessel.
    This is a 1-time use buff that applies +stat_bonus to all D&D stats (STR, DEX, CON, INT, WIS, CHA).
    """
    if not hasattr(gs, "next_capture_stat_bonus"):
        gs.next_capture_stat_bonus = 0
    
    # Set the bonus (overwrites any existing bonus)
    gs.next_capture_stat_bonus = stat_bonus
    
    print(f"✨ Set next capture stat bonus: +{stat_bonus} to all D&D stats")
    return True


def apply_next_capture_stat_bonus(gs, vessel_stats: dict, vessel_idx: int = None) -> tuple[bool, list[str]]:
    """
    Apply the next capture stat bonus to a newly captured vessel.
    Returns (success, list of stats that were modified).
    Only applies to D&D stats (STR, DEX, CON, INT, WIS, CHA).
    
    This should be called when a vessel is captured, and it will consume the bonus.
    """
    if not hasattr(gs, "next_capture_stat_bonus") or gs.next_capture_stat_bonus <= 0:
        return False, []
    
    if not isinstance(vessel_stats, dict):
        return False, []
    
    stat_bonus = gs.next_capture_stat_bonus
    modified_stats = []
    
    # Get abilities dict
    abilities = vessel_stats.get("abilities", {})
    if not isinstance(abilities, dict):
        abilities = {}
        vessel_stats["abilities"] = abilities
    
    # Apply bonus to all D&D stats
    dnd_stats = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    for stat_name in dnd_stats:
        current_value = abilities.get(stat_name, 10)
        new_value = current_value + stat_bonus
        abilities[stat_name] = new_value
        
        # Recalculate modifier
        from rolling.roller import ability_mod
        mods = vessel_stats.get("mods", {})
        if not isinstance(mods, dict):
            mods = {}
        mods[stat_name] = ability_mod(new_value)
        vessel_stats["mods"] = mods
        
        modified_stats.append(stat_name)
    
    vessel_stats["abilities"] = abilities
    
    # Consume the bonus (1-time use)
    gs.next_capture_stat_bonus = 0
    
    print(f"✨ Applied next capture stat bonus: +{stat_bonus} to {', '.join(modified_stats)}")
    return True, modified_stats


def apply_random_stat_penalty(gs, vessel_idx: int, penalty: int) -> tuple[bool, Optional[str]]:
    """
    Apply a random stat penalty to a vessel.
    Returns (success: bool, stat_name: Optional[str]).
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    if not (0 <= vessel_idx < len(stats_list)):
        return False, None
    
    vessel_stats = stats_list[vessel_idx]
    if not isinstance(vessel_stats, dict):
        return False, None
    
    # Get abilities dict
    abilities = vessel_stats.get("abilities", {})
    if not isinstance(abilities, dict):
        return False, None
    
    # Get all D&D stats (STR, DEX, CON, INT, WIS, CHA)
    ability_names = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    # Only stats that can be reduced (value > 1, so reducing by 1 won't go below 1)
    available_stats = [stat for stat in ability_names if abilities.get(stat, 10) > 1]
    
    if not available_stats:
        return False, None
    
    # Pick a random stat
    import random
    stat_name = random.choice(available_stats)
    
    # Apply penalty
    if apply_stat_penalty(gs, vessel_idx, stat_name, penalty):
        return True, stat_name
    
    return False, None


def apply_random_stat_to_random_vessel(gs, stat_bonus: int, num_stats: int = 2) -> tuple[bool, Optional[int], list[tuple[str, int]]]:
    """
    Apply random stat bonuses to a random vessel.
    Returns (success, vessel_idx, list of (stat_name, new_value) tuples).
    """
    stats_list = getattr(gs, "party_vessel_stats", None) or [None] * 6
    names = getattr(gs, "party_slots_names", None) or [None] * 6
    
    # Find all vessels that have stats
    available_vessels = []
    for i, stats in enumerate(stats_list):
        if isinstance(stats, dict) and stats.get("abilities"):
            available_vessels.append(i)
    
    if not available_vessels:
        return False, None, []
    
    # Choose random vessel
    import random
    vessel_idx = random.choice(available_vessels)
    vessel_stats = stats_list[vessel_idx]
    
    # Get D&D stats only (no AC, HP, XP)
    dnd_stats = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
    abilities = vessel_stats.get("abilities", {})
    
    # Choose random stats to modify
    available_stats = [stat for stat in dnd_stats if stat in abilities]
    if not available_stats:
        return False, None, []
    
    # Choose random stats (without replacement if possible)
    stats_to_modify = random.sample(available_stats, min(num_stats, len(available_stats)))
    
    modified = []
    for stat_name in stats_to_modify:
        current_value = abilities.get(stat_name, 10)
        new_value = current_value + stat_bonus
        
        abilities[stat_name] = new_value
        
        # Recalculate modifier
        from rolling.roller import ability_mod
        mods = vessel_stats.get("mods", {})
        if not isinstance(mods, dict):
            mods = {}
        mods[stat_name] = ability_mod(new_value)
        vessel_stats["mods"] = mods
        
        modified.append((stat_name, new_value))
    
    vessel_stats["abilities"] = abilities
    stats_list[vessel_idx] = vessel_stats
    gs.party_vessel_stats = stats_list
    
    print(f"✨ Applied random stats to vessel {vessel_idx}: {', '.join([f'{stat}+{stat_bonus}' for stat, _ in modified])}")
    return True, vessel_idx, modified

