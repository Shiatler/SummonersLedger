# ============================================================
# systems/leaderboard.py — Leaderboard System
# Stores and manages high scores with player name, gender, and score
# ============================================================

import os
import json
from typing import List, Dict, Optional
import settings as S

LEADERBOARD_PATH = os.path.join("Saves", "leaderboard.json")
MAX_ENTRIES = 100


def ensure_leaderboard_dir():
    """Ensure the Saves directory exists."""
    save_dir = os.path.dirname(LEADERBOARD_PATH)
    if not os.path.exists(save_dir):
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as e:
            print(f"⚠️ Failed to create leaderboard directory: {e}")


def add_score(player_name: str, player_gender: str, score: int) -> bool:
    """
    Add a score entry to the leaderboard.
    Returns True if successful, False otherwise.
    """
    ensure_leaderboard_dir()
    
    # Load existing leaderboard
    leaderboard = load_leaderboard()
    
    # Add new entry
    entry = {
        "name": player_name[:20] if player_name else "Unknown",  # Limit name length
        "gender": player_gender if player_gender in ("male", "female") else "male",
        "score": int(score)
    }
    
    leaderboard.append(entry)
    
    # Sort by score (highest first)
    leaderboard.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    # Keep only top MAX_ENTRIES
    leaderboard = leaderboard[:MAX_ENTRIES]
    
    # Save back to file
    try:
        with open(LEADERBOARD_PATH, "w", encoding="utf-8") as f:
            json.dump(leaderboard, f, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ Failed to save leaderboard: {e}")
        return False


def load_leaderboard() -> List[Dict]:
    """Load the leaderboard from file."""
    ensure_leaderboard_dir()
    
    if not os.path.exists(LEADERBOARD_PATH):
        return []
    
    try:
        with open(LEADERBOARD_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                # Validate and clean entries
                cleaned = []
                for entry in data:
                    if isinstance(entry, dict) and "score" in entry:
                        cleaned.append({
                            "name": str(entry.get("name", "Unknown"))[:20],
                            "gender": entry.get("gender", "male") if entry.get("gender") in ("male", "female") else "male",
                            "score": int(entry.get("score", 0))
                        })
                return cleaned
            return []
    except Exception as e:
        print(f"⚠️ Failed to load leaderboard: {e}")
        return []


def get_top_scores(limit: int = MAX_ENTRIES) -> List[Dict]:
    """Get top N scores from leaderboard."""
    leaderboard = load_leaderboard()
    return leaderboard[:limit]


def clear_leaderboard() -> bool:
    """Clear all leaderboard entries."""
    ensure_leaderboard_dir()
    try:
        with open(LEADERBOARD_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
        return True
    except Exception as e:
        print(f"⚠️ Failed to clear leaderboard: {e}")
        return False

