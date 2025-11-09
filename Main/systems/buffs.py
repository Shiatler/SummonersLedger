# ============================================================
# systems/buffs.py — Buff rarity system and card selection
# ============================================================

import os
import random
import pygame

# Rarity distribution weights
RARITY_WEIGHTS = {
    "Common": 50.0,
    "Rare": 25.0,
    "Epic": 12.5,
    "Curse": 12.5,  # Same as Epic
    "Legendary": 5.0,
    "DemonPact": 1.2,
    "Punishment": 10.0,
}

# Maximum card IDs per tier
TIER_MAX_IDS = {
    "Common": 9,
    "Rare": 5,
    "Epic": 4,
    "Legendary": 6,
    "DemonPact": 4,
    "Curse": 5,
    "Punishment": 5,
}

# Blessings directory
BLESSINGS_DIR = os.path.join("Assets", "Blessings")

# Card data - name and description for each card
CARD_DATA = {
    # Common
    "Common1": {
        "name": "Minor Echo",
        "description": "1x stat to 1 vessel (max of 20)"
    },
    "Common2": {
        "name": "Blood Vial",
        "description": "1d4 hp to 1 vessel (1 time roll)"
    },
    "Common3": {
        "name": "Swift Strike",
        "description": "+2 PP to 1 move"
    },
    "Common4": {
        "name": "Healer's Satchel",
        "description": "+5 scroll of mending"
    },
    "Common5": {
        "name": "Binder's Supply",
        "description": "+5 scroll of command"
    },
    "Common6": {
        "name": "Memory Shard",
        "description": "+1d6 XP to 1 Vessel"
    },
    "Common7": {
        "name": "Binding Pouch",
        "description": "+2 Scrolls of Sealing"
    },
    "Common8": {
        "name": "Healing Pouch",
        "description": "+2 Scrolls of Healing"
    },
    "Common9": {
        "name": "Sharpened Knife",
        "description": "+1 permanent damage to attacks for 1 Vessel"
    },
    # Rare
    "Rare1": {
        "name": "Ward of Resistance",
        "description": "-1d2 dmg from enemy attacks (1 time roll)"
    },
    "Rare2": {
        "name": "Pactbinder's Bundle",
        "description": "+5 Scrolls of Subjugation"
    },
    "Rare3": {
        "name": "Echo Infusion",
        "description": "+1 to all stat rolls for the next Vessel you capture"
    },
    "Rare4": {
        "name": "Focused Spirit",
        "description": "+5 pp to 1 move"
    },
    "Rare5": {
        "name": "Unstable Echo",
        "description": "+2 random stats to 1 random Vessel"
    },
    # Epic
    "Epic1": {
        "name": "Sigil of Protection",
        "description": "1x AC to 1 vessel"
    },
    "Epic2": {
        "name": "Elixir of Endurance",
        "description": "1d10 hp to 1 vessel"
    },
    "Epic3": {
        "name": "Shared Vitality",
        "description": "1d4 hp to all vessels"
    },
    "Epic4": {
        "name": "Arcane Overflow",
        "description": "+10 pp to 1 move"
    },
    # Legendary
    "Legendary1": {
        "name": "Ward of the Eternal Guard",
        "description": "1x AC to all vessels"
    },
    "Legendary2": {
        "name": "Grand Resonance",
        "description": "1x stat to all vessels"
    },
    "Legendary3": {
        "name": "Vital Convergence",
        "description": "1d20 hp to 1 vessel"
    },
    "Legendary4": {
        "name": "Guardian's Boon",
        "description": "+1 AC and +1d10 HP to 1 vessel"
    },
    "Legendary5": {
        "name": "Blessing of Restoration",
        "description": "Healing items heals for 1d8 more"
    },
    "Legendary6": {
        "name": "Scroll of Eternity",
        "description": "1x Scroll of eternity"
    },
    # DemonPact
    "DemonPact1": {
        "name": "Hell-Forged Hide",
        "description": "Damage reduction 1d6 for entire party (permanent roll)"
    },
    "DemonPact2": {
        "name": "Infernal Rebirth",
        "description": "First death each battle restores Vessel to 50% HP once per run"
    },
    "DemonPact3": {
        "name": "Demonheart Surge",
        "description": "+1d20 HP to all Vessels"
    },
    "DemonPact4": {
        "name": "Pact of the Legion",
        "description": "+1d6 bonus dmg for entire party"
    },
    # Curse
    "Curse1": {
        "name": "Scream of Terror",
        "description": "+1 to one stat of choice / -1 to another stat of choice"
    },
    "Curse2": {
        "name": "Haunting of Flesh",
        "description": "+2 to one stat of choice / -1 to another random stat"
    },
    "Curse3": {
        "name": "Bleeding Moon",
        "description": "+1 AC to all vessels / -1d8 HP to every vessel"
    },
    "Curse4": {
        "name": "The Hollow's Embrace",
        "description": "+1 random stat / -1 stat of choice"
    },
    "Curse5": {
        "name": "Dirge of the Dead",
        "description": "+2 to one stat / -1d12 HP permanently"
    },
    # Punishment
    "Punishment1": {
        "name": "Oathbreaker's Tribute",
        "description": "-10 gold"
    },
    "Punishment2": {
        "name": "Weight of Sin",
        "description": "-2 random stats"
    },
    "Punishment3": {
        "name": "Broken Aegis",
        "description": "-1 AC to a random vessel"
    },
    "Punishment4": {
        "name": "Judgment's Cut",
        "description": "-1d6 HP"
    },
    "Punishment5": {
        "name": "Oathbreaker's Toll",
        "description": "-1 Vessel"
    },
}

def get_card_data(card_name: str) -> dict:
    """Get card data (name and description) for a card."""
    return CARD_DATA.get(card_name, {
        "name": card_name,
        "description": "Unknown blessing"
    })


def roll_buff_tier() -> str:
    """Roll a buff tier based on rarity distribution."""
    # Normalize weights to 100%
    total = sum(RARITY_WEIGHTS.values())
    normalized = {k: v / total * 100 for k, v in RARITY_WEIGHTS.items()}
    
    # Cumulative probabilities
    roll = random.random() * 100
    cumulative = 0
    for tier, prob in normalized.items():
        cumulative += prob
        if roll < cumulative:
            return tier
    return "Common"  # Fallback


def get_3_random_cards_from_tier(tier: str, exclude_cards: list = None) -> list:
    """
    Get 3 random, unique cards from a tier.
    exclude_cards: List of card names (e.g., ["DemonPact2"]) to exclude from selection.
    """
    if exclude_cards is None:
        exclude_cards = []
    
    max_id = TIER_MAX_IDS.get(tier, 1)
    
    # Get all possible card IDs for this tier
    all_ids = list(range(1, max_id + 1))
    
    # Filter out excluded cards
    available_ids = []
    for card_id in all_ids:
        card_name = f"{tier}{card_id}"
        if card_name not in exclude_cards:
            available_ids.append(card_id)
    
    # If no cards available after filtering, return empty list
    if len(available_ids) == 0:
        return []
    
    # If we have fewer than 3 available cards, return all available
    # Otherwise, sample 3 random cards
    if len(available_ids) < 3:
        ids = available_ids
    else:
        ids = random.sample(available_ids, 3)
    
    cards = []
    for card_id in ids:
        card_name = f"{tier}{card_id}"
        image_path = os.path.join(BLESSINGS_DIR, f"{card_name}.png")
        cards.append({
            "tier": tier,
            "id": card_id,
            "name": card_name,
            "image_path": image_path,
        })
    
    return cards


def load_card_image(image_path: str) -> pygame.Surface | None:
    """Load a card image from path."""
    if not os.path.exists(image_path):
        print(f"⚠️ Card image not found: {image_path}")
        return None
    try:
        return pygame.image.load(image_path).convert_alpha()
    except Exception as e:
        print(f"⚠️ Failed to load card image '{image_path}': {e}")
        return None


def generate_buff_selection(gs=None) -> dict:
    """
    Generate a buff selection with 3 random cards from a rolled tier.
    gs: Optional game state object to check for already-obtained cards (for "once per run" cards).
    """
    tier = roll_buff_tier()
    
    # Special handling for Punishment tier: 5% chance to show only Punishment5 (forced card)
    if tier == "Punishment":
        if random.random() < 0.05:  # 5% chance
            # Return only Punishment5 (forced card, player must take it)
            card_name = "Punishment5"
            image_path = os.path.join(BLESSINGS_DIR, f"{card_name}.png")
            cards = [{
                "tier": tier,
                "id": 5,
                "name": card_name,
                "image_path": image_path,
            }]
            print(f"⚠️ Punishment5 forced selection triggered (5% chance)")
            return {
                "tier": tier,
                "cards": cards,
            }
        # Otherwise, continue with normal selection (Punishment5 will be excluded from normal pool)
    
    # If Curse was rolled, check if DemonPact should override
    # Roll DemonPact with its own probability - if it succeeds, override Curse
    if tier == "Curse":
        # Normalize DemonPact probability (0.5% out of total)
        total_weights = sum(RARITY_WEIGHTS.values())
        demonpact_prob = RARITY_WEIGHTS["DemonPact"] / total_weights
        
        # If DemonPact roll succeeds, override Curse
        if random.random() < demonpact_prob:
            tier = "DemonPact"
        # Otherwise, keep Curse (it can still appear)
    
    # Build list of cards to exclude (cards that are "once per run" or special cases)
    exclude_cards = []
    
    # Always exclude Punishment5 from normal selection (it only appears in the 5% forced case)
    if tier == "Punishment":
        exclude_cards.append("Punishment5")
    
    if gs is not None:
        # Check active_buffs and buffs_history for "once per run" cards
        active_buffs = getattr(gs, "active_buffs", [])
        buffs_history = getattr(gs, "buffs_history", [])
        
        # Combine both lists to check
        all_buffs = active_buffs + buffs_history
        
        # Check for DemonPact2 (once per run)
        for buff in all_buffs:
            if isinstance(buff, dict):
                buff_name = buff.get("name", "")
                buff_tier = buff.get("tier", "")
                buff_id = buff.get("id")
                
                # Check if this is DemonPact2 (once per run)
                # DemonPact2 should never appear again if it's already been obtained
                if (buff_name == "DemonPact2" or 
                    (buff_tier == "DemonPact" and (buff_id == 2 or buff_id == "2"))):
                    if "DemonPact2" not in exclude_cards:
                        exclude_cards.append("DemonPact2")
                        print(f"📋 Excluding DemonPact2 from selection (already obtained)")
    
    cards = get_3_random_cards_from_tier(tier, exclude_cards=exclude_cards)
    
    # If we filtered out all cards and got an empty list, we might need to handle this
    # For now, if we get empty cards, we'll still return it and let the caller handle it
    # (This should be rare - only if DemonPact2 was the only DemonPact card available)
    
    return {
        "tier": tier,
        "cards": cards,
    }

